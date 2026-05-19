from dataclasses import dataclass, field
from typing import Any

from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import Review, ReviewComment
from app.services.comment_poster import (
    MAX_INLINE_COMMENTS,
    post_review_to_github,
)


@dataclass
class FakeClient:
    existing_reviews: list[dict] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)
    updated: list[dict[str, Any]] = field(default_factory=list)
    next_id: int = 555

    async def list_reviews(self, owner, name, number):
        return list(self.existing_reviews)

    async def create_review(self, owner, name, number, *, commit_id, body, event, comments=None):
        self.created.append(
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
        self.next_id += 1
        return {"id": self.next_id}

    async def update_review_body(self, owner, name, number, review_id, body):
        self.updated.append(
            {"owner": owner, "name": name, "number": number, "review_id": review_id, "body": body}
        )
        return {"id": review_id}


async def _seed(db, *, severity_threshold="minor"):
    repo = Repository(
        github_repo_id=999,
        owner="acme",
        name="repo",
        full_name="acme/repo",
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold=severity_threshold,
    )
    db.add(repo)
    await db.flush()
    inst = GithubInstallation(
        installation_id=4242,
        account_login="acme",
        account_type="Organization",
        account_id=1,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=11,
        number=3,
        title="feat",
        body=None,
        state="open",
        head_sha="HEAD",
        base_sha="BASE",
        author_login="dev",
        draft=False,
    )
    db.add(pr)
    review = Review(
        pull_request_id=None,
        repository_id=repo.id,
        status="succeeded",
        head_sha="HEAD",
        diff_hash="hash1",
        model="claude-sonnet-4-5",
        summary="Found 1 major issue.",
        counts={"total": 1, "major": 1, "critical": 0, "minor": 0, "nit": 0},
    )
    await db.flush()
    review.pull_request_id = pr.id
    db.add(review)
    await db.commit()
    await db.refresh(pr)
    await db.refresh(review)
    return repo, inst, pr, review


def _comment(
    review_id, *, path="src/a.py", line=12, severity="major", message="x", suggestion=None
):
    return ReviewComment(
        review_id=review_id,
        path=path,
        line=line,
        side="RIGHT",
        severity=severity,
        category="bug",
        message=message,
        suggestion=suggestion,
        confidence=0.9,
        posted=False,
    )


async def test_should_post_review_with_inline_when_no_prior(db):
    _, _, _, review = await _seed(db)
    db.add(_comment(review.id, line=12, message="off by one"))
    db.add(_comment(review.id, line=13, message="use range()"))
    await db.commit()

    fake = FakeClient()
    out = await post_review_to_github(db, review, client_override=fake)

    assert len(fake.created) == 1
    posted = fake.created[0]
    assert posted["event"] == "COMMENT"
    assert len(posted["comments"]) == 2
    assert posted["comments"][0]["path"] == "src/a.py"
    assert "reviewly review" in posted["body"].lower()
    assert out["inline_count"] == 2
    assert review.status == "posted"


async def test_should_cap_inline_at_max(db):
    _, _, _, review = await _seed(db)
    for i in range(30):
        db.add(_comment(review.id, line=10 + i, message=f"issue {i}"))
    await db.commit()

    fake = FakeClient()
    await post_review_to_github(db, review, client_override=fake)

    assert len(fake.created[0]["comments"]) == MAX_INLINE_COMMENTS


async def test_should_update_summary_when_existing_and_no_inline(db):
    _, _, pr, review = await _seed(db)
    # file-level only (no line)
    db.add(_comment(review.id, line=None, path="src/x.py", message="rename suggestion"))
    await db.commit()

    fake = FakeClient(
        existing_reviews=[{"id": 9001, "state": "COMMENTED", "body": "**reviewly review**\nfoo"}]
    )
    await post_review_to_github(db, review, client_override=fake)

    assert fake.updated, "expected update_review_body when no inline"
    assert fake.created == []


async def test_should_post_new_when_existing_but_has_inline(db):
    _, _, _, review = await _seed(db)
    db.add(_comment(review.id, line=5, message="bug"))
    await db.commit()

    fake = FakeClient(
        existing_reviews=[{"id": 9001, "state": "COMMENTED", "body": "**reviewly review**\nold"}]
    )
    await post_review_to_github(db, review, client_override=fake)

    assert fake.created, "should still post since inline can't be edited in place"


async def test_should_include_suggestion_block(db):
    _, _, _, review = await _seed(db)
    db.add(_comment(review.id, line=8, message="use range(n)", suggestion="for i in range(n):"))
    await db.commit()

    fake = FakeClient()
    await post_review_to_github(db, review, client_override=fake)

    body = fake.created[0]["comments"][0]["body"]
    assert "```suggestion" in body
    assert "for i in range(n):" in body


async def test_should_handle_empty_findings(db):
    _, _, _, review = await _seed(db)
    review.summary = "No issues found."
    review.counts = {"total": 0, "critical": 0, "major": 0, "minor": 0, "nit": 0}
    await db.commit()

    fake = FakeClient()
    out = await post_review_to_github(db, review, client_override=fake)
    assert out["inline_count"] == 0
    assert fake.created, "still post a summary comment so devs see the result"
