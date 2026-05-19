"""End-to-end test: webhook arrives, review runs, comments are posted.

Stubs the GitHub PR files endpoint, Claude, and the InstallationClient used
by the poster. Everything else is real (DB, redis dedup of webhook delivery,
arq enqueue path stubbed at the seam in services.webhooks)."""

import json

from sqlalchemy import select

from app.core.webhook_sig import compute_signature
from app.integrations.anthropic_client import ClaudeResponse
from app.integrations.github_api import PrFile
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.review import Review, ReviewComment
from app.workers.main import review_pr as worker_review_pr

SECRET = "test_webhook_secret"


async def _seed_install_and_link(db, repo_id_full_name=("acme/web", 5001), inst_id=99001):
    full_name, github_repo_id = repo_id_full_name
    owner, _, name = full_name.partition("/")
    from app.models.repository import Repository

    repo = Repository(
        github_repo_id=github_repo_id,
        owner=owner,
        name=name,
        full_name=full_name,
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold="minor",
    )
    db.add(repo)
    inst = GithubInstallation(
        installation_id=inst_id,
        account_login=owner,
        account_type="Organization",
        account_id=123,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    await db.commit()


def _pr_payload(number: int = 11):
    return {
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
            "number": number,
            "title": "add login route",
            "body": "ship login",
            "state": "open",
            "draft": False,
            "user": {"login": "alice"},
            "head": {"sha": "HEAD_SHA"},
            "base": {"sha": "BASE_SHA"},
        },
    }


async def test_e2e_webhook_to_posted_review(client, db, monkeypatch):
    await _seed_install_and_link(db)

    # 1. monkeypatch enqueue so we capture the job and run it inline
    captured: dict = {}

    async def fake_enqueue(pr_id, **extra):
        captured["pr_id"] = str(pr_id)
        captured["extra"] = extra
        return f"job:{pr_id}"

    monkeypatch.setattr("app.services.webhooks.enqueue_review", fake_enqueue)

    # 2. monkeypatch GitHub list_pr_files (review path)
    async def fake_list(self, owner, name, number, max_pages=30):
        return [
            PrFile(
                filename="src/login.py",
                status="added",
                additions=3,
                deletions=0,
                changes=3,
                patch=(
                    "@@ -0,0 +1,3 @@\n"
                    "+import secrets\n+def login(t):\n"
                    "+    if t == EXPECTED: return True"
                ),
                sha="abc",
            )
        ]

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    # 3. monkeypatch Claude
    async def fake_claude(*, system, user, model=None, max_tokens=None, temperature=None):
        return ClaudeResponse(
            text=json.dumps(
                {
                    "findings": [
                        {
                            "file": "src/login.py",
                            "line": 3,
                            "side": "RIGHT",
                            "severity": "critical",
                            "category": "security",
                            "message": "Token compared with == — timing attack risk.",
                            "suggestion": "use secrets.compare_digest",
                            "confidence": 0.95,
                        }
                    ],
                    "summary": "One critical security issue.",
                }
            ),
            input_tokens=200,
            output_tokens=80,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_claude)

    # 4. monkeypatch poster's github client (it goes through InstallationClient.create_review)
    created_posts: list = []

    async def fake_list_reviews(self, owner, name, number):
        return []

    async def fake_create_review(
        self, owner, name, number, *, commit_id, body, event, comments=None
    ):
        created_posts.append(
            {
                "owner": owner,
                "name": name,
                "number": number,
                "commit_id": commit_id,
                "body": body,
                "event": event,
                "comments": comments or [],
            }
        )
        return {"id": 4242}

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_reviews", fake_list_reviews
    )
    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.create_review", fake_create_review
    )

    # 5. fire the webhook
    body = json.dumps(_pr_payload(11)).encode()
    r = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "e2e-1",
            "X-Hub-Signature-256": compute_signature(body, SECRET),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json()["result"]["queued"] is True
    assert captured.get("pr_id"), "enqueue should have been called with the new pr"

    # 6. run the worker function inline against the captured pr_id
    result = await worker_review_pr({}, captured["pr_id"])
    assert result["status"] == "posted"
    assert result["comments"] == 1

    # 7. assert DB state
    pr = (await db.execute(select(PullRequest))).scalars().one()
    assert pr.number == 11
    rv = (await db.execute(select(Review))).scalars().one()
    assert rv.status == "posted"
    assert rv.tokens_input == 200
    comments = (await db.execute(select(ReviewComment))).scalars().all()
    assert len(comments) == 1
    assert comments[0].severity == "critical"
    assert comments[0].posted is True

    # 8. github received the post
    assert len(created_posts) == 1
    posted = created_posts[0]
    assert posted["owner"] == "acme"
    assert posted["name"] == "web"
    assert posted["number"] == 11
    assert len(posted["comments"]) == 1
    assert "basira review" in posted["body"].lower()
