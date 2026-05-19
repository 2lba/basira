from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.installation import GithubInstallation
from app.models.repository import Repository
from app.models.scan import Scan
from app.workers.queue import enqueue_scan

log = get_logger("reviewly.scheduler")

ALLOWED_KINDS = {"none", "daily", "weekly", "monthly"}

_MIN_GAP = {
    "daily": timedelta(hours=22),
    "weekly": timedelta(days=6),
    "monthly": timedelta(days=27),
}


def is_due(repo: Repository, now: datetime) -> bool:
    kind = repo.schedule_kind
    if kind not in ("daily", "weekly", "monthly"):
        return False
    if not repo.review_enabled:
        return False
    hour = repo.schedule_hour or 0
    minute = repo.schedule_minute or 0
    if now.hour != hour or now.minute != minute:
        return False
    if kind == "weekly":
        if repo.schedule_dow is None or now.weekday() != repo.schedule_dow:
            return False
    elif kind == "monthly":
        if repo.schedule_dom is None or now.day != repo.schedule_dom:
            return False
    last = repo.last_scheduled_run_at
    if last is not None:
        if (now - last) < _MIN_GAP[kind]:
            return False
    return True


async def _installation_user(
    db: AsyncSession, repo: Repository
) -> "uuid.UUID | None":  # noqa: F821
    import uuid as _uuid  # noqa: F401

    from app.models.installation import InstallationRepository

    stmt = (
        select(GithubInstallation.user_id)
        .join(
            InstallationRepository,
            InstallationRepository.installation_id == GithubInstallation.id,
        )
        .where(
            InstallationRepository.repository_id == repo.id,
            InstallationRepository.deleted_at.is_(None),
            GithubInstallation.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def run_due_scheduled_scans(
    db: AsyncSession, now: datetime | None = None
) -> list[str]:
    """Look at every repo with a schedule_kind != 'none' and enqueue a scan for
    each one whose schedule matches `now`. Returns the list of scan ids that
    were created."""
    if now is None:
        now = datetime.now(UTC)
    stmt = select(Repository).where(
        Repository.schedule_kind.in_(("daily", "weekly", "monthly")),
        Repository.deleted_at.is_(None),
    )
    repos = (await db.execute(stmt)).scalars().all()
    created: list[str] = []
    for repo in repos:
        if not is_due(repo, now):
            continue
        # avoid duplicate concurrent scans
        in_flight = (
            await db.execute(
                select(Scan).where(
                    Scan.repository_id == repo.id,
                    Scan.status.in_(("pending", "running")),
                    Scan.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if in_flight is not None:
            continue

        user_id = await _installation_user(db, repo)
        scan = Scan(
            repository_id=repo.id,
            triggered_by_user_id=user_id,
            status="pending",
            progress=0,
            progress_message="scheduled",
            ref=repo.default_branch,
        )
        db.add(scan)
        repo.last_scheduled_run_at = now
        await db.commit()
        await db.refresh(scan)
        await enqueue_scan(scan.id)
        created.append(str(scan.id))
        log.info(
            "scheduler.enqueued",
            repo=repo.full_name,
            kind=repo.schedule_kind,
            scan_id=str(scan.id),
        )
    return created
