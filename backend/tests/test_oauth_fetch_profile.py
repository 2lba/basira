import json
from unittest.mock import patch

import httpx
import pytest

from app.integrations.github_oauth import _noreply_email, fetch_profile


def _resp(status: int, body=None) -> httpx.Response:
    if body is None:
        content = b""
    elif isinstance(body, (dict, list)):
        content = json.dumps(body).encode()
    else:
        content = str(body).encode()
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("GET", "http://x"),
    )


@pytest.fixture(autouse=True)
def _no_db():
    # this module hits the GitHub API only; no DB needed.
    yield


async def test_returns_noreply_when_user_emails_is_403():
    user_payload = {"id": 248282963, "login": "2lba", "email": None, "avatar_url": None}

    async def fake_get(self, url, *args, **kwargs):
        if url.endswith("/user"):
            return _resp(200, user_payload)
        if url.endswith("/user/emails"):
            return _resp(403, "Forbidden")
        return _resp(404)

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        p = await fetch_profile("fake-token")
    assert p.login == "2lba"
    assert p.email == _noreply_email(248282963, "2lba")
    assert "noreply.github.com" in p.email


async def test_returns_public_email_when_user_endpoint_exposes_it():
    user_payload = {
        "id": 7,
        "login": "alice",
        "email": "alice@example.com",
        "avatar_url": None,
    }

    async def fake_get(self, url, *args, **kwargs):
        if url.endswith("/user"):
            return _resp(200, user_payload)
        raise AssertionError(f"should not call {url}")

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        p = await fetch_profile("fake-token")
    assert p.email == "alice@example.com"


async def test_returns_primary_verified_when_user_emails_is_200():
    user_payload = {"id": 9, "login": "bob", "email": None, "avatar_url": None}
    emails = [
        {"email": "bob@public.example", "primary": False, "verified": True},
        {"email": "bob@private.example", "primary": True, "verified": True},
    ]

    async def fake_get(self, url, *args, **kwargs):
        if url.endswith("/user"):
            return _resp(200, user_payload)
        if url.endswith("/user/emails"):
            return _resp(200, emails)
        return _resp(404)

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        p = await fetch_profile("fake-token")
    assert p.email == "bob@private.example"


async def test_returns_noreply_when_user_emails_request_blows_up():
    user_payload = {"id": 1, "login": "x", "email": None, "avatar_url": None}

    async def fake_get(self, url, *args, **kwargs):
        if url.endswith("/user"):
            return _resp(200, user_payload)
        raise httpx.ConnectError("boom", request=httpx.Request("GET", "http://x"))

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        p = await fetch_profile("fake-token")
    assert p.email == _noreply_email(1, "x")
