import json

from sqlalchemy import select

from app.integrations.anthropic_client import ClaudeResponse
from app.integrations.github_api import PrFile
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewComment
from app.services.diff_fetcher import DiffBundle, file_from_github
from app.services.review_engine import compute_diff_hash, run_review


async def _seed(db):
    repo = Repository(
        github_repo_id=200,
        owner="acme",
        name="app",
        full_name="acme/app",
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold="minor",
    )
    db.add(repo)
    await db.flush()
    inst = GithubInstallation(
        installation_id=12345,
        account_login="acme",
        account_type="Organization",
        account_id=999,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=70001,
        number=42,
        title="add login",
        body="",
        state="open",
        head_sha="head_sha_abc",
        base_sha="base_sha_def",
        author_login="someone",
        draft=False,
    )
    db.add(pr)
    await db.commit()
    await db.refresh(repo)
    await db.refresh(pr)
    return repo, inst, pr


def _pr_file(name: str, patch: str) -> PrFile:
    return PrFile(
        filename=name,
        status="modified",
        additions=1,
        deletions=0,
        changes=1,
        patch=patch,
        sha="abc",
    )


def _patch_for_lines(*lines: int) -> str:
    """Build a small valid patch that lists adds at given new-side line numbers."""
    parts = [f"@@ -1,1 +{lines[0]},{len(lines)} @@"]
    for ln in lines:
        parts.append(f"+line at {ln}")
    return "\n".join(parts)


async def test_should_complete_when_claude_returns_valid_json(db, monkeypatch):
    repo, inst, pr = await _seed(db)

    files = [_pr_file("src/main.py", _patch_for_lines(5, 6, 7))]

    async def fake_list_pr_files(self, owner, repo_name, number, max_pages=30):
        return files

    monkeypatch.setattr(
        "app.integrations.github_api.InstallationClient.list_pr_files",
        fake_list_pr_files,
    )

    async def fake_call(*, system, user, model=None, max_tokens=None, temperature=None):
        payload = {
            "findings": [
                {
                    "file": "src/main.py",
                    "line": 5,
                    "side": "RIGHT",
                    "severity": "major",
                    "category": "bug",
                    "message": "off by one in loop",
                    "suggestion": "use < instead of <=",
                    "confidence": 0.9,
                }
            ],
            "summary": "One bug found.",
        }
        return ClaudeResponse(
            text=json.dumps(payload),
            input_tokens=120,
            output_tokens=40,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.review.status == "succeeded"
    assert outcome.comments_created == 1
    assert outcome.review.tokens_input == 120
    assert outcome.review.tokens_output == 40

    rows = (await db.execute(select(ReviewComment))).scalars().all()
    assert len(rows) == 1
    assert rows[0].severity == "major"
    assert rows[0].path == "src/main.py"


async def test_should_skip_when_diff_hash_already_reviewed(db, monkeypatch):
    repo, inst, pr = await _seed(db)
    files = [_pr_file("src/main.py", _patch_for_lines(10))]

    async def fake_list(self, owner, repo_name, number, max_pages=30):
        return files

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    async def fake_call(**kw):
        return ClaudeResponse(
            text='{"findings":[],"summary":"clean"}',
            input_tokens=10,
            output_tokens=5,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    o1 = await run_review(db, pr)
    assert o1.review.status == "succeeded"

    calls = []

    async def fake_call_2(**kw):
        calls.append(kw)
        return ClaudeResponse(
            text="{}", input_tokens=0, output_tokens=0, model="m", stop_reason=None
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call_2)

    o2 = await run_review(db, pr)
    assert o2.skipped_existing
    assert calls == [], "should not call claude on identical diff"


async def test_should_filter_when_confidence_below_threshold(db, monkeypatch):
    repo, inst, pr = await _seed(db)
    files = [_pr_file("a.py", _patch_for_lines(2, 3))]

    async def fake_list(self, *a, **k):
        return files

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    payload = {
        "findings": [
            {
                "file": "a.py",
                "line": 2,
                "severity": "minor",
                "category": "style",
                "message": "low confidence noise",
                "confidence": 0.1,
            }
        ]
    }

    async def fake_call(**kw):
        return ClaudeResponse(
            text=json.dumps(payload),
            input_tokens=1,
            output_tokens=1,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr, confidence_threshold=0.5)
    assert outcome.comments_created == 0


async def test_should_drop_line_anchor_when_line_not_in_diff(db, monkeypatch):
    repo, inst, pr = await _seed(db)
    files = [_pr_file("a.py", _patch_for_lines(20))]

    async def fake_list(self, *a, **k):
        return files

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    payload = {
        "findings": [
            {
                "file": "a.py",
                "line": 999,
                "severity": "major",
                "category": "bug",
                "message": "wrong line cited",
                "confidence": 0.9,
            }
        ]
    }

    async def fake_call(**kw):
        return ClaudeResponse(
            text=json.dumps(payload),
            input_tokens=1,
            output_tokens=1,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.comments_created == 1
    saved = (await db.execute(select(ReviewComment))).scalars().first()
    assert saved.line is None


async def test_should_succeed_with_empty_findings_when_diff_clean(db, monkeypatch):
    repo, inst, pr = await _seed(db)
    files = [_pr_file("clean.py", _patch_for_lines(1))]

    async def fake_list(self, *a, **k):
        return files

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    async def fake_call(**kw):
        return ClaudeResponse(
            text='{"findings":[],"summary":""}',
            input_tokens=5,
            output_tokens=2,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.review.status == "succeeded"
    assert outcome.comments_created == 0
    assert "No issues" in (outcome.review.summary or "")


async def test_should_recover_when_first_response_not_json(db, monkeypatch):
    repo, inst, pr = await _seed(db)
    files = [_pr_file("a.py", _patch_for_lines(3))]

    async def fake_list(self, *a, **k):
        return files

    monkeypatch.setattr("app.integrations.github_api.InstallationClient.list_pr_files", fake_list)

    calls = {"n": 0}

    async def fake_call(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return ClaudeResponse(
                text="not json at all", input_tokens=1, output_tokens=1, model="x", stop_reason=None
            )
        return ClaudeResponse(
            text='{"findings":[],"summary":""}',
            input_tokens=2,
            output_tokens=2,
            model="x",
            stop_reason="end_turn",
        )

    monkeypatch.setattr("app.services.review_engine.call_claude", fake_call)

    outcome = await run_review(db, pr)
    assert outcome.review.status == "succeeded"
    assert calls["n"] == 2


def test_diff_hash_changes_when_content_changes():
    f1 = file_from_github(_pr_file("a.py", _patch_for_lines(1, 2)))
    f2 = file_from_github(_pr_file("a.py", _patch_for_lines(3, 4)))
    b1 = DiffBundle(pr_number=1, head_sha="s", base_sha="b", files=[f1])
    b2 = DiffBundle(pr_number=1, head_sha="s", base_sha="b", files=[f2])
    assert compute_diff_hash(b1) != compute_diff_hash(b2)


def test_diff_hash_stable_when_same_content():
    f = file_from_github(_pr_file("a.py", _patch_for_lines(1, 2)))
    b = DiffBundle(pr_number=1, head_sha="s", base_sha="b", files=[f])
    assert compute_diff_hash(b) == compute_diff_hash(b)
