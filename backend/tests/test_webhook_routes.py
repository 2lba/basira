import json

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.core.webhook_sig import compute_signature
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.webhook_event import WebhookEvent


def _secret() -> str:
    return get_settings().github_webhook_secret or "test_webhook_secret"


SECRET = _secret()


def _pr_payload(action: str = "opened") -> dict:
    return {
        "action": action,
        "repository": {
            "id": 100,
            "name": "repo",
            "full_name": "alice/repo",
            "default_branch": "main",
            "private": False,
        },
        "pull_request": {
            "id": 9001,
            "number": 7,
            "title": "fix typo",
            "body": "small fix",
            "state": "open",
            "draft": False,
            "user": {"login": "alice"},
            "head": {"sha": "abc123"},
            "base": {"sha": "def456"},
        },
    }


def _post(body: bytes, event: str, delivery: str = "del-1"):
    return {
        "content": body,
        "headers": {
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": compute_signature(body, SECRET),
            "Content-Type": "application/json",
        },
    }


async def test_should_reject_when_signature_invalid(client):
    body = b'{"hello":"world"}'
    r = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "d-bad",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"


async def test_should_ack_when_ping_received(client):
    body = b'{"zen":"design for failure"}'
    r = await client.post("/webhooks/github", **_post(body, "ping", "d-ping"))
    assert r.status_code == 200
    assert r.json()["received"] is True


async def test_should_400_when_event_header_missing(client):
    body = b"{}"
    r = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Delivery": "d-x",
            "X-Hub-Signature-256": compute_signature(body, SECRET),
        },
    )
    assert r.status_code == 400


async def test_should_reject_when_body_not_json(client):
    body = b"not json"
    r = await client.post("/webhooks/github", **_post(body, "ping", "d-nj"))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "WEBHOOK_BAD_REQUEST"


async def test_should_upsert_when_pull_request_opened(client, db):
    payload = _pr_payload("opened")
    body = json.dumps(payload).encode()
    r = await client.post("/webhooks/github", **_post(body, "pull_request", "d-pr-1"))
    assert r.status_code == 200
    out = r.json()
    assert out["received"] is True
    assert out["result"]["pr_number"] == 7
    assert out["result"]["queued"] is True

    repos = (await db.execute(select(Repository))).scalars().all()
    assert len(repos) == 1
    assert repos[0].full_name == "alice/repo"

    prs = (await db.execute(select(PullRequest))).scalars().all()
    assert len(prs) == 1
    assert prs[0].number == 7
    assert prs[0].head_sha == "abc123"


async def test_should_dedupe_when_delivery_replayed(client, db):
    payload = _pr_payload("opened")
    body = json.dumps(payload).encode()
    r1 = await client.post("/webhooks/github", **_post(body, "pull_request", "d-rep"))
    assert r1.status_code == 200
    r2 = await client.post("/webhooks/github", **_post(body, "pull_request", "d-rep"))
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True

    count = (await db.execute(select(func.count(WebhookEvent.id)))).scalar_one()
    assert count == 1


async def test_should_skip_review_when_pr_is_draft(client, monkeypatch):
    enqueue_called: list = []

    async def fake_enqueue(*args, **kwargs):
        enqueue_called.append((args, kwargs))
        return "fake-job"

    monkeypatch.setattr("app.services.webhooks.enqueue_review", fake_enqueue)

    payload = _pr_payload("opened")
    payload["pull_request"]["draft"] = True
    body = json.dumps(payload).encode()
    r = await client.post("/webhooks/github", **_post(body, "pull_request", "d-draft"))
    assert r.status_code == 200
    assert r.json()["result"]["queued"] is False
    assert enqueue_called == []


async def test_should_ignore_unsupported_event(client):
    body = b"{}"
    r = await client.post("/webhooks/github", **_post(body, "label", "d-label"))
    assert r.status_code == 200
    assert r.json()["ignored"] is True


@pytest.mark.parametrize("action", ["closed", "edited", "labeled"])
async def test_should_not_queue_when_action_not_trigger(client, monkeypatch, action):
    enqueue_called: list = []

    async def fake_enqueue(*args, **kwargs):
        enqueue_called.append(args)
        return "fake-job"

    monkeypatch.setattr("app.services.webhooks.enqueue_review", fake_enqueue)

    payload = _pr_payload(action)
    body = json.dumps(payload).encode()
    r = await client.post("/webhooks/github", **_post(body, "pull_request", f"d-{action}"))
    assert r.status_code == 200
    assert r.json()["result"]["queued"] is False
    assert enqueue_called == []
