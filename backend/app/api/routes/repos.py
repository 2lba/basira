import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.schemas.dashboard import RepoOut, RepoUpdate
from app.services.visibility import list_user_repos, user_can_access_repo

router = APIRouter(prefix="/api/repos", tags=["repos"])

ALLOWED_SEVERITIES = {"nit", "minor", "major", "critical"}
ALLOWED_MODELS = {"claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"}


def _to_out(r: Repository) -> RepoOut:
    return RepoOut(
        id=str(r.id),
        owner=r.owner,
        name=r.name,
        full_name=r.full_name,
        default_branch=r.default_branch,
        private=r.private,
        review_enabled=r.review_enabled,
        severity_threshold=r.severity_threshold,
        ignored_paths=r.ignored_paths,
        custom_rules=r.custom_rules,
        model_override=r.model_override,
    )


@router.get("", response_model=list[RepoOut])
async def list_repos(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    repos = await list_user_repos(db, user.id)
    return [_to_out(r) for r in repos]


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(
    repo_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(repo_id)
    except ValueError as e:
        raise AppError("BAD_ID", "invalid repo id", status.HTTP_400_BAD_REQUEST) from e
    if not await user_can_access_repo(db, user.id, rid):
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, rid)
    if repo is None or repo.deleted_at is not None:
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
    return _to_out(repo)


@router.patch("/{repo_id}", response_model=RepoOut)
async def update_repo(
    repo_id: str,
    update: RepoUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(repo_id)
    except ValueError as e:
        raise AppError("BAD_ID", "invalid repo id", status.HTTP_400_BAD_REQUEST) from e
    if not await user_can_access_repo(db, user.id, rid):
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
    repo = await db.get(Repository, rid)
    if repo is None or repo.deleted_at is not None:
        raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)

    if update.review_enabled is not None:
        repo.review_enabled = update.review_enabled
    if update.severity_threshold is not None:
        if update.severity_threshold not in ALLOWED_SEVERITIES:
            raise AppError(
                "BAD_SEVERITY",
                f"severity must be one of {sorted(ALLOWED_SEVERITIES)}",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        repo.severity_threshold = update.severity_threshold
    if update.ignored_paths is not None:
        cleaned = [p.strip() for p in update.ignored_paths if p and p.strip()]
        if len(cleaned) > 200:
            raise AppError(
                "TOO_MANY_PATTERNS",
                "max 200 ignored paths",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        repo.ignored_paths = cleaned or None
    if update.custom_rules is not None:
        repo.custom_rules = update.custom_rules.strip() or None
    if update.model_override is not None:
        if update.model_override and update.model_override not in ALLOWED_MODELS:
            raise AppError(
                "BAD_MODEL",
                f"model must be one of {sorted(ALLOWED_MODELS)}",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        repo.model_override = update.model_override or None

    await db.commit()
    await db.refresh(repo)
    return _to_out(repo)
