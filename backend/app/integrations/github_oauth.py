from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import get_settings

GH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GH_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105
GH_API = "https://api.github.com"

DEFAULT_SCOPES = "read:user user:email repo"


class GithubOAuthError(Exception):
    pass


@dataclass(frozen=True)
class GithubProfile:
    id: int
    login: str
    email: str | None
    avatar_url: str | None


def authorize_url(redirect_uri: str, state: str, scopes: str = DEFAULT_SCOPES) -> str:
    s = get_settings()
    if not s.github_app_client_id:
        raise GithubOAuthError("GITHUB_APP_CLIENT_ID not configured")
    params = {
        "client_id": s.github_app_client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scopes,
        "allow_signup": "true",
    }
    return f"{GH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> str:
    s = get_settings()
    if not s.github_app_client_id or not s.github_app_client_secret:
        raise GithubOAuthError("github oauth client not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            GH_TOKEN_URL,
            data={
                "client_id": s.github_app_client_id,
                "client_secret": s.github_app_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if r.status_code != 200:
        raise GithubOAuthError(f"token exchange failed: {r.status_code}")
    body = r.json()
    if "error" in body:
        raise GithubOAuthError(body.get("error_description") or body["error"])
    token = body.get("access_token")
    if not token:
        raise GithubOAuthError("missing access_token in github response")
    return token


def _noreply_email(user_id: int, login: str) -> str:
    """GitHub's official anonymous email for users who keep their address
    private. Apps without the 'Email addresses' permission can't see the
    real address but this address is deliverable through GitHub's relay."""
    return f"{user_id}+{login}@users.noreply.github.com"


async def fetch_profile(access_token: str) -> GithubProfile:
    """Read the OAuth user. Email is best-effort:

    1. /user.email - public email if the user exposes one
    2. /user/emails - primary verified address (needs the App's "Email
       addresses" permission; returns 403 otherwise)
    3. {user_id}+{login}@users.noreply.github.com - GitHub's deliverable
       anonymous relay; used so we always have a non-null string in DB and
       /auth/me doesn't break for users who never installed the email
       permission.
    """
    import logging

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        ur = await client.get(f"{GH_API}/user")
        if ur.status_code != 200:
            raise GithubOAuthError(f"github /user failed: {ur.status_code}")
        user = ur.json()
        email = user.get("email")
        if not email:
            try:
                er = await client.get(f"{GH_API}/user/emails")
                if er.status_code == 200:
                    emails = er.json()
                    primary = next(
                        (e for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    if primary:
                        email = primary.get("email")
                elif er.status_code in (403, 404):
                    # GitHub App lacks the Email addresses permission, or the
                    # user denied it. Not an error - fall through to noreply.
                    logging.getLogger("basira.oauth").info(
                        "fetch_profile.emails_unavailable status=%s", er.status_code
                    )
                else:
                    logging.getLogger("basira.oauth").warning(
                        "fetch_profile.emails_unexpected status=%s body=%s",
                        er.status_code,
                        er.text[:200],
                    )
            except httpx.HTTPError as e:
                logging.getLogger("basira.oauth").warning(
                    "fetch_profile.emails_request_failed err=%s", e
                )
    if not email:
        email = _noreply_email(int(user["id"]), str(user["login"]))
    return GithubProfile(
        id=int(user["id"]),
        login=str(user["login"]),
        email=email,
        avatar_url=user.get("avatar_url"),
    )


@dataclass(frozen=True)
class OAuthRepo:
    github_repo_id: int
    owner: str
    name: str
    full_name: str
    default_branch: str | None
    private: bool


async def list_user_repos(access_token: str, max_pages: int = 10) -> list[OAuthRepo]:
    """Paginate /user/repos with the user's OAuth token. Caps at
    100*max_pages results to keep first-login latency bounded."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    out: list[OAuthRepo] = []
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        page = 1
        while page <= max_pages:
            r = await client.get(
                f"{GH_API}/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "affiliation": "owner,collaborator,organization_member",
                    "sort": "updated",
                },
            )
            if r.status_code != 200:
                raise GithubOAuthError(f"github /user/repos failed: {r.status_code}")
            items = r.json()
            if not isinstance(items, list) or not items:
                break
            for it in items:
                full = it.get("full_name") or ""
                if "/" not in full:
                    continue
                owner, name = full.split("/", 1)
                out.append(
                    OAuthRepo(
                        github_repo_id=int(it["id"]),
                        owner=owner,
                        name=name,
                        full_name=full,
                        default_branch=it.get("default_branch"),
                        private=bool(it.get("private", False)),
                    )
                )
            if len(items) < 100:
                break
            page += 1
    return out
