import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.repository import Repository
from app.models.scan import Scan, ScanFinding
from app.models.user import User
from app.services.visibility import user_can_access_repo

router = APIRouter(prefix="/api/findings", tags=["findings"])


async def _load(db: AsyncSession, finding_id: str, user: User) -> tuple[ScanFinding, Scan, Repository]:
    try:
        fid = uuid.UUID(finding_id)
    except ValueError as e:
        raise AppError("BAD_ID", "invalid id", status.HTTP_400_BAD_REQUEST) from e
    finding = await db.get(ScanFinding, fid)
    if finding is None or finding.deleted_at is not None:
        raise AppError("NOT_FOUND", "finding not found", status.HTTP_404_NOT_FOUND)
    scan = await db.get(Scan, finding.scan_id)
    if scan is None:
        raise AppError("NOT_FOUND", "finding not found", status.HTTP_404_NOT_FOUND)
    if not await user_can_access_repo(db, user.id, scan.repository_id):
        raise AppError("NOT_FOUND", "finding not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, scan.repository_id)
    if repo is None:
        raise AppError("NOT_FOUND", "finding not found", status.HTTP_404_NOT_FOUND)
    return finding, scan, repo


@router.post("/{finding_id}/resolve")
async def resolve(
    finding_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    finding, _, _ = await _load(db, finding_id, user)
    finding.resolved_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}


@router.post("/{finding_id}/unresolve")
async def unresolve(
    finding_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    finding, _, _ = await _load(db, finding_id, user)
    finding.resolved_at = None
    await db.commit()
    return {"ok": True}


@router.post("/{finding_id}/false-positive")
async def false_positive(
    finding_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    finding, _, repo = await _load(db, finding_id, user)
    finding.false_positive_at = datetime.now(UTC)
    if finding.dedup_key:
        keys = list(repo.false_positive_keys or [])
        if finding.dedup_key not in keys:
            keys.append(finding.dedup_key)
            repo.false_positive_keys = keys
    await db.commit()
    return {"ok": True, "dedup_key": finding.dedup_key}


@router.post("/{finding_id}/ignore-rule")
async def ignore_rule(
    finding_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    finding, _, repo = await _load(db, finding_id, user)
    cats = list(repo.ignored_categories or [])
    if finding.category not in cats:
        cats.append(finding.category)
        repo.ignored_categories = cats
    await db.commit()
    return {"ok": True, "category": finding.category}
