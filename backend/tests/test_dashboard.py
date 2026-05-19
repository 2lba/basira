from app.core.crypto import issue_access_token
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import Review, ReviewComment
from app.models.user import User


async def _make_user(db, gh_id=1, login="alice"):
    u = User(
        github_user_id=gh_id,
        github_login=login,
        email=f"{login}@example.com",
        avatar_url=None,
    )
    db.add(u)
    await db.flush()
    await db.commit()
    await db.refresh(u)
    return u


async def _link_repo(db, user, owner="acme", name="app", github_repo_id=100):
    repo = Repository(
        github_repo_id=github_repo_id,
        owner=owner,
        name=name,
        full_name=f"{owner}/{name}",
        default_branch="main",
        private=False,
        review_enabled=True,
        severity_threshold="medium",
    )
    db.add(repo)
    await db.flush()
    inst = GithubInstallation(
        installation_id=github_repo_id + 1000,
        account_login=owner,
        account_type="Organization",
        account_id=github_repo_id + 2000,
        user_id=user.id,
    )
    db.add(inst)
    await db.flush()
    db.add(InstallationRepository(installation_id=inst.id, repository_id=repo.id))
    await db.commit()
    await db.refresh(repo)
    return repo


def _auth(client, user):
    token = issue_access_token(str(user.id), {"login": user.github_login})
    client.cookies.set("reviewly_access", token)


async def test_should_list_only_user_repos(client, db):
    alice = await _make_user(db, gh_id=1, login="alice")
    bob = await _make_user(db, gh_id=2, login="bob")
    a_repo = await _link_repo(db, alice, name="alice-app", github_repo_id=10)
    await _link_repo(db, bob, name="bob-app", github_repo_id=20)

    _auth(client, alice)
    r = await client.get("/api/repos")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "acme/alice-app"
    assert data[0]["id"] == str(a_repo.id)


async def test_should_404_when_repo_not_visible_to_user(client, db):
    alice = await _make_user(db, gh_id=1, login="alice")
    bob = await _make_user(db, gh_id=2, login="bob")
    bob_repo = await _link_repo(db, bob, name="bob-app", github_repo_id=20)

    _auth(client, alice)
    r = await client.get(f"/api/repos/{bob_repo.id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "REPO_NOT_FOUND"


async def test_should_update_repo_settings(client, db):
    alice = await _make_user(db)
    repo = await _link_repo(db, alice)
    _auth(client, alice)

    r = await client.patch(
        f"/api/repos/{repo.id}",
        json={
            "review_enabled": False,
            "severity_threshold": "major",
            "ignored_paths": ["foo/", "bar/"],
            "custom_rules": "no print statements",
            "model_override": "claude-opus-4-5",
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["review_enabled"] is False
    assert out["severity_threshold"] == "major"
    assert out["ignored_paths"] == ["foo/", "bar/"]
    assert out["custom_rules"] == "no print statements"
    assert out["model_override"] == "claude-opus-4-5"


async def test_should_reject_invalid_severity(client, db):
    alice = await _make_user(db)
    repo = await _link_repo(db, alice)
    _auth(client, alice)

    r = await client.patch(f"/api/repos/{repo.id}", json={"severity_threshold": "yolo"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_SEVERITY"


async def test_should_reject_invalid_model(client, db):
    alice = await _make_user(db)
    repo = await _link_repo(db, alice)
    _auth(client, alice)

    r = await client.patch(f"/api/repos/{repo.id}", json={"model_override": "gpt-4"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_MODEL"


async def test_should_list_reviews_scoped_to_user(client, db):
    alice = await _make_user(db)
    bob = await _make_user(db, gh_id=2, login="bob")
    a_repo = await _link_repo(db, alice, name="alice-app", github_repo_id=10)
    b_repo = await _link_repo(db, bob, name="bob-app", github_repo_id=20)

    for repo, n in ((a_repo, 1), (a_repo, 2), (b_repo, 3)):
        pr = PullRequest(
            repository_id=repo.id,
            github_pr_id=1000 + n,
            number=n,
            title=f"pr-{n}",
            body=None,
            state="open",
            head_sha=f"sha{n}",
            base_sha="base",
            author_login="x",
            draft=False,
        )
        db.add(pr)
        await db.flush()
        rv = Review(
            pull_request_id=pr.id,
            repository_id=repo.id,
            status="succeeded",
            head_sha=pr.head_sha,
            diff_hash=f"h{n}",
            model="claude-sonnet-4-5",
            summary="ok",
            counts={"total": 0},
        )
        db.add(rv)
    await db.commit()

    _auth(client, alice)
    r = await client.get("/api/reviews")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert all("alice-app" in it["repo_full_name"] for it in items)


async def test_should_paginate_reviews(client, db):
    alice = await _make_user(db)
    repo = await _link_repo(db, alice)
    for n in range(5):
        pr = PullRequest(
            repository_id=repo.id,
            github_pr_id=2000 + n,
            number=n + 1,
            title=f"pr {n}",
            body=None,
            state="open",
            head_sha=f"s{n}",
            base_sha=None,
            author_login=None,
            draft=False,
        )
        db.add(pr)
        await db.flush()
        rv = Review(
            pull_request_id=pr.id,
            repository_id=repo.id,
            status="succeeded",
            head_sha=pr.head_sha,
            diff_hash=f"hh{n}",
            model="m",
            summary="s",
        )
        db.add(rv)
    await db.commit()

    _auth(client, alice)
    r1 = await client.get("/api/reviews?limit=2&offset=0")
    r2 = await client.get("/api/reviews?limit=2&offset=2")
    assert len(r1.json()) == 2
    assert len(r2.json()) == 2
    ids1 = {it["id"] for it in r1.json()}
    ids2 = {it["id"] for it in r2.json()}
    assert ids1.isdisjoint(ids2)


async def test_should_return_review_detail_with_comments(client, db):
    alice = await _make_user(db)
    repo = await _link_repo(db, alice)
    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=5000,
        number=1,
        title="x",
        body=None,
        state="open",
        head_sha="HEAD",
        base_sha=None,
        author_login=None,
        draft=False,
    )
    db.add(pr)
    await db.flush()
    rv = Review(
        pull_request_id=pr.id,
        repository_id=repo.id,
        status="succeeded",
        head_sha="HEAD",
        diff_hash="h",
        model="m",
        summary="found stuff",
        counts={"total": 1, "major": 1},
        tokens_input=100,
        tokens_output=50,
    )
    db.add(rv)
    await db.flush()
    db.add(
        ReviewComment(
            review_id=rv.id,
            path="src/a.py",
            line=10,
            side="RIGHT",
            severity="major",
            category="bug",
            message="leak",
            suggestion=None,
            confidence=0.9,
            posted=True,
        )
    )
    await db.commit()

    _auth(client, alice)
    r = await client.get(f"/api/reviews/{rv.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "found stuff"
    assert len(body["comments"]) == 1
    assert body["comments"][0]["path"] == "src/a.py"


async def test_should_404_review_not_for_user(client, db):
    alice = await _make_user(db)
    bob = await _make_user(db, gh_id=2, login="bob")
    bob_repo = await _link_repo(db, bob, name="bob-app", github_repo_id=20)
    pr = PullRequest(
        repository_id=bob_repo.id,
        github_pr_id=7000,
        number=1,
        title="x",
        body=None,
        state="open",
        head_sha="HEAD",
        base_sha=None,
        author_login=None,
        draft=False,
    )
    db.add(pr)
    await db.flush()
    rv = Review(
        pull_request_id=pr.id,
        repository_id=bob_repo.id,
        status="succeeded",
        head_sha="HEAD",
        diff_hash="h",
        model="m",
    )
    db.add(rv)
    await db.commit()

    _auth(client, alice)
    r = await client.get(f"/api/reviews/{rv.id}")
    assert r.status_code == 404


async def test_should_401_when_dashboard_unauthenticated(client):
    r = await client.get("/api/repos")
    assert r.status_code == 401
    r2 = await client.get("/api/reviews")
    assert r2.status_code == 401
