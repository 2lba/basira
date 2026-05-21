from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.workers.queue import enqueue_review

log = get_logger("basira.webhooks")

SUPPORTED_EVENTS = {
    "ping",
    "pull_request",
    "installation",
    "installation_repositories",
}

REVIEW_TRIGGER_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


class WebhookProcessError(Exception):
    pass


async def record_event(
    db: AsyncSession,
    delivery_id: str,
    event: str,
    action: str | None,
    payload: dict[str, Any] | None,
) -> tuple[WebhookEvent, bool]:
    """Insert webhook event; returns (event, is_new). On duplicate delivery_id
    returns the existing row (idempotent replay)."""
    stmt = (
        pg_insert(WebhookEvent)
        .values(
            delivery_id=delivery_id,
            event=event,
            action=action,
            payload=payload,
            status="received",
        )
        .on_conflict_do_nothing(index_elements=["delivery_id"])
        .returning(WebhookEvent.id)
    )
    res = await db.execute(stmt)
    row_id = res.scalar_one_or_none()
    await db.commit()
    if row_id is None:
        existing = (
            await db.execute(select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id))
        ).scalar_one()
        return existing, False
    rec = await db.get(WebhookEvent, row_id)
    assert rec is not None
    return rec, True


async def mark_processed(
    db: AsyncSession, event: WebhookEvent, status: str, error: str | None = None
) -> None:
    event.status = status
    event.error = error
    event.processed_at = datetime.now(UTC)
    await db.commit()


async def upsert_repository(db: AsyncSession, repo_data: dict[str, Any]) -> Repository:
    repo_id = int(repo_data["id"])
    stmt = select(Repository).where(Repository.github_repo_id == repo_id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    full_name = repo_data["full_name"]
    owner, _, name = full_name.partition("/")
    if repo is None:
        repo = Repository(
            github_repo_id=repo_id,
            owner=owner,
            name=name or repo_data.get("name", ""),
            full_name=full_name,
            default_branch=repo_data.get("default_branch"),
            private=bool(repo_data.get("private", False)),
            review_enabled=True,
            severity_threshold="medium",
        )
        db.add(repo)
    else:
        repo.owner = owner
        repo.name = name or repo.name
        repo.full_name = full_name
        repo.default_branch = repo_data.get("default_branch") or repo.default_branch
        repo.private = bool(repo_data.get("private", repo.private))
    await db.flush()
    return repo


async def _resolve_installation_owner(
    db: AsyncSession, account: dict[str, Any]
) -> "uuid.UUID | None":  # noqa: F821
    """For a User-type installation, map the account back to a local user by
    matching github_user_id (preferred) then github_login. Org installs leave
    user_id NULL - they don't have a single owning user."""
    import uuid as _uuid  # noqa: F401

    if str(account.get("type", "")).lower() != "user":
        return None
    gh_id = account.get("id")
    login = account.get("login")
    if gh_id:
        stmt = select(User).where(User.github_user_id == int(gh_id))
        u = (await db.execute(stmt)).scalar_one_or_none()
        if u is not None:
            return u.id
    if login:
        stmt = select(User).where(User.github_login == str(login))
        u = (await db.execute(stmt)).scalar_one_or_none()
        if u is not None:
            return u.id
    return None


async def upsert_installation(db: AsyncSession, inst_data: dict[str, Any]) -> GithubInstallation:
    inst_id = int(inst_data["id"])
    stmt = select(GithubInstallation).where(GithubInstallation.installation_id == inst_id)
    inst = (await db.execute(stmt)).scalar_one_or_none()
    account = inst_data.get("account", {}) or {}
    owner_id = await _resolve_installation_owner(db, account)
    if inst is None:
        inst = GithubInstallation(
            installation_id=inst_id,
            account_login=str(account.get("login", "")),
            account_type=str(account.get("type", "User")),
            account_id=int(account.get("id", 0)),
            user_id=owner_id,
        )
        db.add(inst)
    else:
        inst.account_login = str(account.get("login", inst.account_login))
        inst.account_type = str(account.get("type", inst.account_type))
        inst.account_id = int(account.get("id", inst.account_id))
        # only fill user_id when we can resolve it AND it's currently blank,
        # so a later GH-side reinstall doesn't reassign an installation
        # silently.
        if owner_id is not None and inst.user_id is None:
            inst.user_id = owner_id
    await db.flush()
    return inst


async def upsert_pull_request(
    db: AsyncSession, repo: Repository, pr_data: dict[str, Any]
) -> PullRequest:
    number = int(pr_data["number"])
    stmt = select(PullRequest).where(
        PullRequest.repository_id == repo.id, PullRequest.number == number
    )
    pr = (await db.execute(stmt)).scalar_one_or_none()
    head = pr_data.get("head", {}) or {}
    base = pr_data.get("base", {}) or {}
    author = (pr_data.get("user") or {}).get("login")
    if pr is None:
        pr = PullRequest(
            repository_id=repo.id,
            github_pr_id=int(pr_data["id"]),
            number=number,
            title=str(pr_data.get("title", ""))[:1024],
            body=pr_data.get("body"),
            state=str(pr_data.get("state", "open")),
            head_sha=str(head.get("sha", "")),
            base_sha=base.get("sha"),
            author_login=author,
            draft=bool(pr_data.get("draft", False)),
        )
        db.add(pr)
    else:
        pr.title = str(pr_data.get("title", pr.title))[:1024]
        pr.body = pr_data.get("body", pr.body)
        pr.state = str(pr_data.get("state", pr.state))
        pr.head_sha = str(head.get("sha", pr.head_sha))
        pr.base_sha = base.get("sha", pr.base_sha)
        pr.author_login = author or pr.author_login
        pr.draft = bool(pr_data.get("draft", pr.draft))
    await db.flush()
    return pr


async def process_event(db: AsyncSession, event_record: WebhookEvent) -> dict[str, Any]:
    event = event_record.event
    action = event_record.action
    payload = event_record.payload or {}

    if event == "ping":
        return {"acknowledged": True}

    if event == "installation":
        inst_data = payload.get("installation") or {}
        if action in ("created", "new_permissions_accepted"):
            inst = await upsert_installation(db, inst_data)
            repos = payload.get("repositories") or []
            await _link_installation_repos(db, inst, repos)
            await db.commit()
            return {"installation_id": inst.installation_id, "repos_linked": len(repos)}
        if action == "deleted":
            inst_id = int(inst_data.get("id", 0))
            stmt = select(GithubInstallation).where(GithubInstallation.installation_id == inst_id)
            inst = (await db.execute(stmt)).scalar_one_or_none()
            if inst is not None:
                inst.deleted_at = datetime.now(UTC)
                await db.commit()
            return {"installation_id": inst_id, "deleted": True}
        return {"installation": "ignored", "action": action}

    if event == "installation_repositories":
        inst_data = payload.get("installation") or {}
        inst = await upsert_installation(db, inst_data)
        added = payload.get("repositories_added") or []
        removed = payload.get("repositories_removed") or []
        if added:
            await _link_installation_repos(db, inst, added)
        if removed:
            await _unlink_installation_repos(db, inst, removed)
        await db.commit()
        return {"added": len(added), "removed": len(removed)}

    if event == "pull_request":
        repo_data = payload.get("repository") or {}
        pr_data = payload.get("pull_request") or {}
        if not repo_data or not pr_data:
            raise WebhookProcessError("missing repository or pull_request in payload")

        repo = await upsert_repository(db, repo_data)
        pr = await upsert_pull_request(db, repo, pr_data)
        await db.commit()

        should_review = action in REVIEW_TRIGGER_ACTIONS and repo.review_enabled and not pr.draft
        job_id: str | None = None
        if should_review:
            job_id = await enqueue_review(pr.id, action=action, head_sha=pr.head_sha)
        return {
            "repository": repo.full_name,
            "pr_number": pr.number,
            "queued": bool(job_id),
            "job_id": job_id,
        }

    return {"event": event, "ignored": True}


async def _link_installation_repos(
    db: AsyncSession, inst: GithubInstallation, repos: list[dict[str, Any]]
) -> None:
    from app.models.user_repository import UserRepository

    for r in repos:
        repo = await upsert_repository(db, r)
        repo.connected = True
        stmt = (
            pg_insert(InstallationRepository)
            .values(installation_id=inst.id, repository_id=repo.id)
            .on_conflict_do_nothing(index_elements=["installation_id", "repository_id"])
        )
        await db.execute(stmt)
        # also surface the repo in the owning user's list so it appears on
        # /api/repos right after the install webhook lands.
        if inst.user_id is not None:
            link_stmt = (
                pg_insert(UserRepository)
                .values(user_id=inst.user_id, repository_id=repo.id)
                .on_conflict_do_nothing(index_elements=["user_id", "repository_id"])
            )
            await db.execute(link_stmt)
    await db.flush()


async def _unlink_installation_repos(
    db: AsyncSession, inst: GithubInstallation, repos: list[dict[str, Any]]
) -> None:
    now = datetime.now(UTC)
    for r in repos:
        repo_id = int(r.get("id", 0))
        stmt = select(Repository).where(Repository.github_repo_id == repo_id)
        repo = (await db.execute(stmt)).scalar_one_or_none()
        if repo is None:
            continue
        link_stmt = select(InstallationRepository).where(
            InstallationRepository.installation_id == inst.id,
            InstallationRepository.repository_id == repo.id,
        )
        link = (await db.execute(link_stmt)).scalar_one_or_none()
        if link is not None:
            link.deleted_at = now
        # if no other live installation still links this repo, flip
        # connected=False so the UI puts the "connect" button back.
        remaining_stmt = select(InstallationRepository).where(
            InstallationRepository.repository_id == repo.id,
            InstallationRepository.deleted_at.is_(None),
        )
        remaining = (await db.execute(remaining_stmt)).scalar_one_or_none()
        if remaining is None:
            repo.connected = False
    await db.flush()
