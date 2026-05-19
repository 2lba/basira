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
    ScanCompareEntry,
    ScanCompareResult,
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


@router.get("/scans/compare", response_model=ScanCompareResult)
async def compare_scans(
    a: str,
    b: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    a_id = _parse_uuid(a, "BAD_SCAN_ID")
    b_id = _parse_uuid(b, "BAD_SCAN_ID")
    if a_id == b_id:
        raise AppError(
            "SAME_SCAN", "cannot compare a scan with itself", status.HTTP_400_BAD_REQUEST
        )

    scan_a = await db.get(Scan, a_id)
    scan_b = await db.get(Scan, b_id)
    for s in (scan_a, scan_b):
        if s is None or s.deleted_at is not None:
            raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)
    if scan_a.repository_id != scan_b.repository_id:
        raise AppError(
            "REPO_MISMATCH",
            "scans must belong to the same repo",
            status.HTTP_400_BAD_REQUEST,
        )
    if not await user_can_access_repo(db, user.id, scan_a.repository_id):
        raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)

    repo = await db.get(Repository, scan_a.repository_id)
    if repo is None:
        raise AppError("SCAN_NOT_FOUND", "scan not found", status.HTTP_404_NOT_FOUND)

    f_a = (
        await db.execute(
            select(ScanFinding).where(
                ScanFinding.scan_id == scan_a.id, ScanFinding.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    f_b = (
        await db.execute(
            select(ScanFinding).where(
                ScanFinding.scan_id == scan_b.id, ScanFinding.deleted_at.is_(None)
            )
        )
    ).scalars().all()

    def key(f: ScanFinding) -> tuple:
        return (f.path, f.line, f.severity, f.category, f.message)

    map_a = {key(f): f for f in f_a}
    map_b = {key(f): f for f in f_b}
    keys_a = set(map_a)
    keys_b = set(map_b)

    def to_entry(f: ScanFinding) -> ScanCompareEntry:
        return ScanCompareEntry(
            path=f.path,
            line=f.line,
            severity=f.severity,
            category=f.category,
            message=f.message,
            suggestion=f.suggestion,
        )

    new = [to_entry(map_b[k]) for k in keys_b - keys_a]
    resolved = [to_entry(map_a[k]) for k in keys_a - keys_b]
    persisting = [to_entry(map_b[k]) for k in keys_a & keys_b]

    counts_delta: dict[str, int] = {}
    counts_a = scan_a.counts or {}
    counts_b = scan_b.counts or {}
    for k in ("total", "critical", "major", "minor", "nit"):
        counts_delta[k] = int(counts_b.get(k, 0)) - int(counts_a.get(k, 0))

    score_delta = None
    if scan_a.score is not None and scan_b.score is not None:
        score_delta = int(scan_b.score) - int(scan_a.score)

    return ScanCompareResult(
        a=_item(scan_a, repo),
        b=_item(scan_b, repo),
        score_delta=score_delta,
        new_findings=new,
        resolved_findings=resolved,
        persisting_findings=persisting,
        counts_delta=counts_delta,
    )


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
