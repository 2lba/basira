"""Security simulation tests. Each one tries to attack the API the way a
real attacker would and asserts the right defense kicks in.

Mapped to OWASP Top 10 where applicable:
- A01 Broken Access Control → IDOR
- A02 Cryptographic Failures → JWT tampering
- A03 Injection → SQL injection through API inputs
- A07 Auth Failures → webhook signature + replay
- A10 SSRF → webhook URL validation
"""

import hashlib
import hmac
import json

import pytest

from app.config import get_settings
from app.core.crypto import issue_access_token
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.repository import Repository
from app.models.scan import Scan, ScanFinding
from app.models.user import User
from app.models.user_repository import UserRepository


async def _seed_user_with_repo(db, github_login: str, github_user_id: int):
    """Create a user, repo, install, and link them. Returns (user, repo)."""
    u = User(github_user_id=github_user_id, github_login=github_login)
    db.add(u)
    await db.flush()
    repo = Repository(
        github_repo_id=github_user_id * 100,
        owner=github_login,
        name="demo",
        full_name=f"{github_login}/demo",
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold="minor",
        connected=True,
    )
    db.add(repo)
    await db.flush()
    inst = GithubInstallation(
        installation_id=github_user_id + 9_000_000,
        account_login=github_login,
        account_type="User",
        account_id=github_user_id,
        user_id=u.id,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    db.add(UserRepository(user_id=u.id, repository_id=repo.id))
    await db.commit()
    return u, repo


def _auth_cookies(user_id: str, login: str) -> dict:
    return {"basira_access": issue_access_token(user_id, {"login": login})}


# A01 - Broken Access Control (IDOR) -------------------------------------


async def test_user_b_cannot_read_user_a_repo(client, db):
    user_a, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    user_b = User(github_user_id=2002, github_login="bob")
    db.add(user_b)
    await db.commit()
    await db.refresh(user_b)

    client.cookies.update(_auth_cookies(str(user_b.id), "bob"))
    r = await client.get(f"/api/repos/{repo_a.id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] in {"REPO_NOT_FOUND", "NOT_FOUND"}


async def test_user_b_cannot_start_scan_on_user_a_repo(client, db):
    _, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    user_b = User(github_user_id=2002, github_login="bob")
    db.add(user_b)
    await db.commit()
    await db.refresh(user_b)

    client.cookies.update(_auth_cookies(str(user_b.id), "bob"))
    r = await client.post(f"/api/repos/{repo_a.id}/scans")
    assert r.status_code == 404


async def test_user_b_cannot_read_user_a_scan(client, db):
    user_a, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    scan = Scan(
        repository_id=repo_a.id,
        triggered_by_user_id=user_a.id,
        status="succeeded",
        progress=100,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    user_b = User(github_user_id=2002, github_login="bob")
    db.add(user_b)
    await db.commit()
    await db.refresh(user_b)

    client.cookies.update(_auth_cookies(str(user_b.id), "bob"))
    r = await client.get(f"/api/scans/{scan.id}")
    assert r.status_code == 404


async def test_user_b_cannot_act_on_user_a_finding(client, db):
    _, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    scan = Scan(repository_id=repo_a.id, status="succeeded", progress=100)
    db.add(scan)
    await db.flush()
    finding = ScanFinding(
        scan_id=scan.id,
        path="src/x.py",
        line=1,
        severity="minor",
        category="bug",
        message="x",
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)

    user_b = User(github_user_id=2002, github_login="bob")
    db.add(user_b)
    await db.commit()
    await db.refresh(user_b)

    client.cookies.update(_auth_cookies(str(user_b.id), "bob"))
    r = await client.post(f"/api/findings/{finding.id}/resolve")
    assert r.status_code == 404


async def test_unauthenticated_caller_gets_401_not_500(client, db):
    _, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    r = await client.get(f"/api/repos/{repo_a.id}")
    assert r.status_code == 401


# A02 - JWT tampering ----------------------------------------------------


async def test_tampered_jwt_payload_is_rejected(client, db):
    user_a, _ = await _seed_user_with_repo(db, "alice", 1001)
    user_b = User(github_user_id=2002, github_login="bob")
    db.add(user_b)
    await db.commit()
    await db.refresh(user_b)

    import base64

    bob_jwt = issue_access_token(str(user_b.id), {"login": "bob"})
    header_b64, payload_b64, sig_b64 = bob_jwt.split(".")
    payload_raw = base64.urlsafe_b64decode(payload_b64 + "==").decode()
    payload = json.loads(payload_raw)
    payload["sub"] = str(user_a.id)
    payload["login"] = "alice"
    bad_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    forged = f"{header_b64}.{bad_payload_b64}.{sig_b64}"

    client.cookies.update({"basira_access": forged})
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_jwt_with_empty_signature_is_rejected(client):
    fake = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJoYWNrZXIifQ."
    client.cookies.update({"basira_access": fake})
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_random_garbage_jwt_is_rejected(client):
    client.cookies.update({"basira_access": "not-a-jwt-at-all"})
    r = await client.get("/auth/me")
    assert r.status_code == 401


# A07 - Webhook auth -----------------------------------------------------


async def test_webhook_missing_signature_returns_401(client):
    body = b'{"action":"created","installation":{"id":1}}'
    r = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "no-sig",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


async def test_webhook_bad_signature_returns_401(client):
    body = b'{"action":"created","installation":{"id":1}}'
    r = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "bad-sig",
            "X-Hub-Signature-256": "sha256=ffff",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


async def test_webhook_replay_is_deduped(client, db):
    secret = get_settings().github_app_webhook_secret or "test_webhook_secret"
    payload = {
        "action": "opened",
        "repository": {
            "id": 5001,
            "name": "web",
            "full_name": "acme/web",
            "default_branch": "main",
            "private": False,
        },
        "pull_request": {
            "id": 70001,
            "number": 7,
            "title": "x",
            "body": "",
            "state": "open",
            "draft": False,
            "user": {"login": "alice"},
            "head": {"sha": "abc"},
            "base": {"sha": "def"},
        },
    }
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    delivery_id = "replay-test"

    h = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sig,
        "Content-Type": "application/json",
    }
    r1 = await client.post("/webhooks/github", content=body, headers=h)
    assert r1.status_code == 200
    r2 = await client.post("/webhooks/github", content=body, headers=h)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True


# A03 - Injection --------------------------------------------------------


async def test_sql_injection_in_uuid_param_is_rejected_cleanly(client, db):
    user_a, _ = await _seed_user_with_repo(db, "alice", 1001)
    client.cookies.update(_auth_cookies(str(user_a.id), "alice"))
    payloads = [
        "'; DROP TABLE users; --",
        "1 OR 1=1",
        "../etc/passwd",
        "%00",
    ]
    for p in payloads:
        r = await client.get(f"/api/repos/{p}")
        assert r.status_code in {400, 404}, f"got {r.status_code} for {p!r}"


async def test_xss_payload_in_settings_is_stored_verbatim_not_executed(client, db):
    """React escapes by default; backend doesn't pre-sanitize. We just
    confirm the data flows through without server-side eval / template
    expansion."""
    user_a, repo_a = await _seed_user_with_repo(db, "alice", 1001)
    client.cookies.update(_auth_cookies(str(user_a.id), "alice"))
    xss = "<script>alert('xss')</script>"
    r = await client.patch(
        f"/api/repos/{repo_a.id}",
        json={"custom_rules": xss},
    )
    assert r.status_code == 200
    assert r.json()["custom_rules"] == xss


# A10 - SSRF on webhook URL fields --------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
        "http://metadata.google.internal/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "javascript:alert(1)",
    ],
)
async def test_slack_webhook_rejects_non_http_schemes(client, db, bad_url):
    """Non-http(s) schemes (file, ftp, javascript) must be rejected; the
    backend posts to whatever URL it stores, so SSRF/scheme abuse is
    blocked at write-time."""
    user_a, _ = await _seed_user_with_repo(db, "alice", 1001)
    client.cookies.update(_auth_cookies(str(user_a.id), "alice"))
    r = await client.patch("/api/me/slack", json={"url": bad_url})
    assert r.status_code in {400, 422}, f"{bad_url!r} got {r.status_code}"


# BYOK-focused attacks --------------------------------------------------


async def test_byok_mass_assignment_ignores_extra_fields(client, db):
    """The PUT schema only declares api_key. Anything else (provider,
    is_valid, user_id) must be silently dropped by pydantic, never used
    to upsert as someone else."""
    from sqlalchemy import select

    from app.models.user_api_key import UserApiKey

    user_a, _ = await _seed_user_with_repo(db, "alice", 1001)
    user_b, _ = await _seed_user_with_repo(db, "bob", 2002)
    client.cookies.update(_auth_cookies(str(user_a.id), "alice"))

    import app.api.routes.user_api_keys as uapi_routes
    from app.services.user_api_key import ValidationResult

    async def fake_validate(api_key: str) -> ValidationResult:
        return ValidationResult(True, None)

    uapi_routes.validate_anthropic_key = fake_validate

    r = await client.put(
        "/api/me/api-keys/anthropic",
        json={
            "api_key": "sk-ant-massassign-1234567890",
            "user_id": str(user_b.id),
            "is_valid": False,
            "provider": "openai",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "anthropic"
    assert body["is_valid"] is True

    rows = (await db.execute(select(UserApiKey))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == user_a.id
    assert rows[0].provider == "anthropic"


async def test_byok_api_key_not_in_error_response_or_logs(client, db, caplog):
    """If validation rejects the key we must NOT echo the plaintext into
    the error payload or the structured logs."""
    user_a, _ = await _seed_user_with_repo(db, "alice", 1001)
    client.cookies.update(_auth_cookies(str(user_a.id), "alice"))

    import app.api.routes.user_api_keys as uapi_routes
    from app.services.user_api_key import ValidationResult

    async def fake_validate(api_key: str) -> ValidationResult:
        return ValidationResult(False, "rejected")

    uapi_routes.validate_anthropic_key = fake_validate
    secret = "sk-ant-this-must-not-be-logged-XXXX"

    import logging

    with caplog.at_level(logging.DEBUG):
        r = await client.put(
            "/api/me/api-keys/anthropic",
            json={"api_key": secret},
        )
    assert r.status_code == 400
    assert secret not in r.text
    for record in caplog.records:
        assert secret not in record.getMessage()
