import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.repository import Repository
from app.models.scan import Scan, ScanFinding
from app.models.user import User
from app.schemas.dashboard import (
    ScanDetail,
    ScanFindingOut,
    ScanListItem,
)
from app.services.visibility import user_can_access_repo, user_repo_ids
from app.workers.queue import enqueue_scan

router = APIRouter(prefix="/api", tags=["scans"])


def _item(scan: Scan, repo: Repository) -> ScanListItem:
    return ScanListItem(
        id=str(scan.id),
        repository_id=str(scan.repository_id),
        repo_full_name=repo.full_name,
        status=scan.status,
        progress=scan.progress,
        progress_message=scan.progress_message,
        ref=scan.ref,
        head_sha=scan.head_sha,
        score=scan.score,
        summary=scan.summary,
        counts=scan.counts,
        files_scanned=scan.files_scanned,
        files_skipped=scan.files_skipped,
        created_at=scan.created_at,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
    )


def _parse_uuid(v: str, code: str = "BAD_ID") -> uuid.UUID:
    try:
        return uuid.UUID(v)
    except ValueError as e:
        raise AppError(code, "invalid id", status.HTTP_400_BAD_REQUEST) from e


@router.post(
    "/repos/{repo_id}/scans",
    response_model=ScanListItem,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_scan(
    repo_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rid = _parse_uuid(repo_id)
    if not await user_can_access_repo(db, user.id, rid):
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, rid)
    if repo is None or repo.deleted_at is not None:
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)

    # block concurrent scans for the same repo
    in_flight = (
        await db.execute(
            select(Scan)
            .where(
                Scan.repository_id == rid,
                Scan.status.in_(("pending", "running")),
                Scan.deleted_at.is_(None),
            )
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if in_flight is not None:
        return _item(in_flight, repo)

    scan = Scan(
        repository_id=rid,
        triggered_by_user_id=user.id,
        status="pending",
        progress=0,
        progress_message="queued",
        ref=repo.default_branch,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    await enqueue_scan(scan.id)
    return _item(scan, repo)


@router.get("/repos/{repo_id}/scans", response_model=list[ScanListItem])
async def list_repo_scans(
    repo_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rid = _parse_uuid(repo_id)
    if not await user_can_access_repo(db, user.id, rid):
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, rid)
    if repo is None or repo.deleted_at is not None:
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)

    stmt = (
        select(Scan)
        .where(Scan.repository_id == rid, Scan.deleted_at.is_(None))
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_item(s, repo) for s in rows]


@router.get("/scans", response_model=list[ScanListItem])
async def list_scans(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = await user_repo_ids(db, user.id)
    if not allowed:
        return []
    stmt = (
        select(Scan, Repository)
        .join(Repository, Repository.id == Scan.repository_id)
        .where(Scan.repository_id.in_(allowed), Scan.deleted_at.is_(None))
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [_item(s, repo) for s, repo in rows]


@router.get("/scans/{scan_id}", response_model=ScanDetail)
async def get_scan(
    scan_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    sid = _parse_uuid(scan_id, "BAD_SCAN_ID")
    scan = await db.get(Scan, sid)
    if scan is None or scan.deleted_at is not None:
        raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)
    if not await user_can_access_repo(db, user.id, scan.repository_id):
        raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, scan.repository_id)
    if repo is None:
        raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)

    fstmt = (
        select(ScanFinding)
        .where(ScanFinding.scan_id == scan.id, ScanFinding.deleted_at.is_(None))
        .order_by(ScanFinding.path, ScanFinding.line.nulls_last())
    )
    findings = (await db.execute(fstmt)).scalars().all()

    base = _item(scan, repo)
    return ScanDetail(
        **base.model_dump(),
        findings=[
            ScanFindingOut(
                id=str(f.id),
                path=f.path,
                line=f.line,
                severity=f.severity,
                category=f.category,
                message=f.message,
                suggestion=f.suggestion,
                confidence=float(f.confidence) if f.confidence is not None else None,
            )
            for f in findings
        ],
        tokens_input=scan.tokens_input,
        tokens_output=scan.tokens_output,
        cost_usd=float(scan.cost_usd) if scan.cost_usd is not None else None,
        model=scan.model,
        error=scan.error,
    )
