from app.integrations.anthropic_client import ClaudeResponse
from app.integrations.github_api import PrFile
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.review_engine import run_review


async def _seed(db, **repo_overrides):
    defaults = dict(
        github_repo_id=300,
        owner="acme",
        name="cfg",
        full_name="acme/cfg",
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold="minor",
    )
    defaults.update(repo_overrides)
    repo = Repository(**defaults)
    db.add(repo)
    await db.flush()
    inst = GithubInstallation(
        installation_id=8001,
        account_login="acme",
        account_type="Organization",
        account_id=1,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=1,
        number=1,
        title="t",
        body="",
        state="open",
        head_sha="H",
        base_sha="B",
        author_login="x",
        draft=False,
    )
    db.add(pr)
    await db.commit()
    await db.refresh(repo)
    await db.refresh(pr)
    return repo, pr


def _pf(name: str, patch: str) -> PrFile:
    return PrFile(
        filename=name,
        status="modified",
        additions=1,
        deletions=0,
        changes=1,
        patch=patch,
        sha="abc",
    )


def _patch(line: int) -> str:
    return f"@@ -1,1 +{line},1 @@\n+x"


async def test_should_skip_files_matching_repo_ignored_paths(db, monkeypatch):
    repo, pr = await _seed(db, ignored_paths=[r"^secrets/.*"])

    captured: dict = {}

    async def fake_list(self, *a, **k):
        return [_pf("src/main.py", _patch(10)), _pf("secrets/key.txt", _patch(5))]

    async def fake_call(*, system, user, model=None, max_tokens=None, temperature=None):
        captured["prompt"] = user
        return ClaudeResponse(
            text='{"findings":[],"summary":""}',
            input_tokens=1,
            output_tokens=1,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_pr_files", fake_list
    )
    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.review.status == "succeeded"
    assert "src/main.py" in captured["prompt"]
    assert "secrets/key.txt" not in captured["prompt"]


async def test_should_include_custom_rules_in_prompt(db, monkeypatch):
    repo, pr = await _seed(db, custom_rules="never use print(); use logger instead")

    captured: dict = {}

    async def fake_list(self, *a, **k):
        return [_pf("src/main.py", _patch(10))]

    async def fake_call(*, system, user, model=None, max_tokens=None, temperature=None):
        captured["prompt"] = user
        return ClaudeResponse(
            text='{"findings":[],"summary":""}',
            input_tokens=1,
            output_tokens=1,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_pr_files", fake_list
    )
    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    await run_review(db, pr)
    assert "never use print()" in captured["prompt"]


async def test_should_pass_model_override_to_claude(db, monkeypatch):
    repo, pr = await _seed(db, model_override="claude-opus-4-5")

    captured: dict = {}

    async def fake_list(self, *a, **k):
        return [_pf("src/main.py", _patch(10))]

    async def fake_call(*, system, user, model=None, max_tokens=None, temperature=None):
        captured["model"] = model
        return ClaudeResponse(
            text='{"findings":[],"summary":""}',
            input_tokens=1,
            output_tokens=1,
            model=model or "x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_pr_files", fake_list
    )
    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    await run_review(db, pr)
    assert captured["model"] == "claude-opus-4-5"


async def test_should_filter_by_repo_severity_threshold(db, monkeypatch):
    # repo threshold "major" should drop "minor" findings
    repo, pr = await _seed(db, severity_threshold="major")

    async def fake_list(self, *a, **k):
        return [_pf("src/main.py", _patch(10))]

    payload = {
        "findings": [
            {
                "file": "src/main.py",
                "line": 10,
                "severity": "minor",
                "category": "style",
                "message": "spacing nitpick",
                "confidence": 0.9,
            },
            {
                "file": "src/main.py",
                "line": 10,
                "severity": "major",
                "category": "bug",
                "message": "real bug",
                "confidence": 0.9,
            },
        ]
    }

    async def fake_call(**kw):
        import json

        return ClaudeResponse(
            text=json.dumps(payload),
            input_tokens=1,
            output_tokens=1,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_pr_files", fake_list
    )
    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.comments_created == 1
    from sqlalchemy import select

    from app.models.review import ReviewComment

    rows = (await db.execute(select(ReviewComment))).scalars().all()
    assert rows[0].severity == "major"
