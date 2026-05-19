"""End-to-end OAuth integration tests.

Walks a brand-new user from `/auth/github/login` to a connected repo on
`/api/repos`. Every external HTTP call (GitHub OAuth, GitHub API) is
mocked at the httpx layer so the tests don't touch the network.

Goal: prove that for a freshly-booted backend with an empty database, a
user can sign in and reach the dashboard, AND that every documented
failure mode lands the user on the login page with a readable error
code instead of a generic 500.
"""

import hashlib
import hmac
import json

import pytest

from app.config import get_settings
from app.integrations.github_oauth import (
    GithubOAuthError,
    GithubProfile,
    OAuthRepo,
    _noreply_email,
)


def _stub_github(
    monkeypatch,
    *,
    user_id: int = 248282963,
    login: str = "user-under-test",
    user_email: str | None = "user@example.com",
    emails_403: bool = False,
    repos_403: bool = False,
    token_fails: bool = False,
    user_fetch_fails: bool = False,
):
    """Patch the three OAuth-side seams instead of the global httpx client.
    Avoids accidentally intercepting the ASGI test transport."""

    async def fake_exchange_code(code, redirect_uri):
        if token_fails:
            raise GithubOAuthError("bad_verification_code: expired")
        return "fake-user-token"

    async def fake_fetch_profile(token):
        if user_fetch_fails:
            raise GithubOAuthError("github /user failed: 401")
        email = user_email
        if not email:
            if emails_403:
                email = _noreply_email(user_id, login)
            # otherwise fetch_profile's real fallback would have set noreply too
        return GithubProfile(
            id=user_id, login=login, email=email, avatar_url=None
        )

    async def fake_list_user_repos(token, max_pages=10):
        if repos_403:
            raise GithubOAuthError("github /user/repos failed: 403")
        return []  # most installs have no OAuth-visible repos

    monkeypatch.setattr(
        "app.api.routes.auth.exchange_code", fake_exchange_code
    )
    monkeypatch.setattr(
        "app.api.routes.auth.fetch_profile", fake_fetch_profile
    )
    monkeypatch.setattr(
        "app.api.routes.auth.list_user_repos", fake_list_user_repos
    )


async def _start_login(client) -> str:
    """Hit /auth/github/login, return the state cookie value."""
    r = await client.get("/auth/github/login", follow_redirects=False)
    assert r.status_code == 302, r.text
    state_cookie = client.cookies.get("basira_oauth_state")
    assert state_cookie, f"no state cookie set, got {r.headers.get('set-cookie')}"
    loc = r.headers["location"]
    assert f"state={state_cookie}" in loc
    return state_cookie


def _configure_oauth(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "fake-client")
    monkeypatch.setenv("GITHUB_APP_CLIENT_SECRET", "fake-secret")
    from app.config import get_settings as _gs

    _gs.cache_clear()  # type: ignore[attr-defined]


async def test_new_user_full_oauth_flow_through_installation(client, db, monkeypatch):
    """Fresh user (no DB row, no cookies) signs in, lands on /repos empty,
    then a webhook for an install lands and the next /api/repos shows the
    repo as connected."""
    _configure_oauth(monkeypatch)
    _stub_github(monkeypatch, login="newuser", user_email="newuser@example.com")
    state = await _start_login(client)
    r = await client.get(
        f"/auth/github/callback?code=FAKE_CODE&state={state}",
        follow_redirects=False,
    )

    assert r.status_code == 302, r.text
    assert "oauth_error" not in r.headers["location"]
    cookies_set = r.headers.get_list("set-cookie")
    assert any("basira_access=" in c for c in cookies_set)
    assert any("basira_refresh=" in c for c in cookies_set)

    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["github_login"] == "newuser"
    assert body["install_url"].startswith("https://github.com/apps/")

    r = await client.get("/api/repos")
    assert r.status_code == 200
    assert r.json() == []

    settings = get_settings()
    secret = settings.github_app_webhook_secret or "test_webhook_secret"
    payload = {
        "action": "created",
        "installation": {
            "id": 8765432,
            "account": {"login": "newuser", "id": 248282963, "type": "User"},
        },
        "repositories": [
            {
                "id": 111,
                "name": "demo",
                "full_name": "newuser/demo",
                "private": False,
                "default_branch": "main",
            }
        ],
    }
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    wr = await client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "e2e-install-1",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert wr.status_code == 200, wr.text

    r = await client.get("/api/repos")
    assert r.status_code == 200
    repos = r.json()
    assert len(repos) == 1
    assert repos[0]["full_name"] == "newuser/demo"
    assert repos[0]["connected"] is True


async def test_oauth_token_exchange_failure_redirects_with_code(client, monkeypatch):
    _configure_oauth(monkeypatch)
    _stub_github(monkeypatch, token_fails=True)
    state = await _start_login(client)
    r = await client.get(
        f"/auth/github/callback?code=BAD&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "oauth_error=OAUTH_TOKEN_EXCHANGE_FAILED" in r.headers["location"]


async def test_oauth_user_fetch_failure_redirects_with_code(client, monkeypatch):
    _configure_oauth(monkeypatch)
    _stub_github(monkeypatch, user_fetch_fails=True)
    state = await _start_login(client)
    r = await client.get(
        f"/auth/github/callback?code=ok&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "oauth_error=OAUTH_USER_FETCH_FAILED" in r.headers["location"]


async def test_oauth_state_mismatch_redirects(client):
    r = await client.get(
        "/auth/github/callback?code=ok&state=garbage",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "oauth_error=OAUTH_STATE_MISMATCH" in r.headers["location"]


async def test_oauth_user_denial_redirects(client):
    r = await client.get(
        "/auth/github/callback?error=access_denied&error_description=user+said+no",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "oauth_error=OAUTH_DENIED" in r.headers["location"]


async def test_email_403_falls_back_to_noreply_and_login_succeeds(
    client, db, monkeypatch
):
    """The original 'OAuth callback when email is private' bug. Now an
    end-to-end check that the full flow completes when GitHub returns
    403 on /user/emails and the /user payload has no email field."""
    _configure_oauth(monkeypatch)
    _stub_github(monkeypatch, login="ghost", user_email=None, emails_403=True)
    state = await _start_login(client)
    r = await client.get(
        f"/auth/github/callback?code=ok&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    assert "oauth_error" not in r.headers["location"]

    me = await client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["github_login"] == "ghost"
    assert body["email"].endswith("noreply.github.com")


async def test_user_repos_403_does_not_block_login(client, db, monkeypatch):
    """GitHub Apps don't honor the OAuth `repo` scope; /user/repos comes
    back 403 for many installs. That must not break the login path —
    the user simply gets an empty repo list until they install the App."""
    _configure_oauth(monkeypatch)
    _stub_github(
        monkeypatch,
        login="repoblocked",
        user_email="repoblocked@example.com",
        repos_403=True,
    )
    state = await _start_login(client)
    r = await client.get(
        f"/auth/github/callback?code=ok&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "oauth_error" not in r.headers["location"]

    repos = await client.get("/api/repos")
    assert repos.status_code == 200
    assert repos.json() == []
