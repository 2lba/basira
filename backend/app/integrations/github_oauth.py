from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import get_settings

GH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GH_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105
GH_API = "https://api.github.com"

DEFAULT_SCOPES = "read:user user:email"


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


async def fetch_profile(access_token: str) -> GithubProfile:
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
            er = await client.get(f"{GH_API}/user/emails")
            if er.status_code == 200:
                emails = er.json()
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if primary:
                    email = primary.get("email")
    return GithubProfile(
        id=int(user["id"]),
        login=str(user["login"]),
        email=email,
        avatar_url=user.get("avatar_url"),
    )
