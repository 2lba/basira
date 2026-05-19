async def test_should_redirect_when_login_called_with_client_id(client, monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "x")
    monkeypatch.setenv("GITHUB_APP_CLIENT_SECRET", "y")
    # force re-read of settings
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    r = await client.get("/auth/github/login", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert "github.com/login/oauth/authorize" in loc
    assert "state=" in loc


async def test_should_503_when_github_not_configured(client, monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "")
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    r = await client.get("/auth/github/login", follow_redirects=False)
    assert r.status_code == 503


async def test_should_reject_callback_when_state_missing(client):
    r = await client.get("/auth/github/callback?code=abc&state=xyz", follow_redirects=False)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "OAUTH_STATE_MISMATCH"


async def test_should_reject_callback_when_state_mismatch(client):
    client.cookies.set("basira_oauth_state", "different")
    r = await client.get("/auth/github/callback?code=abc&state=xyz", follow_redirects=False)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


async def test_should_401_when_me_unauthenticated(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "NOT_AUTHENTICATED"
