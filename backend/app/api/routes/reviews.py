import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import Review, ReviewComment
from app.models.user import User
from app.schemas.dashboard import ReviewCommentOut, ReviewDetail, ReviewListItem
from app.services.visibility import user_can_access_repo, user_repo_ids

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _item(review: Review, repo: Repository, pr: PullRequest) -> ReviewListItem:
    return ReviewListItem(
        id=str(review.id),
        repository_id=str(review.repository_id),
        pull_request_id=str(review.pull_request_id),
        pr_number=pr.number,
        pr_title=pr.title,
        repo_full_name=repo.full_name,
        status=review.status,
        head_sha=review.head_sha,
        model=review.model,
        summary=review.summary,
        counts=review.counts,
        created_at=review.created_at,
    )


@router.get("", response_model=list[ReviewListItem])
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_repos = await user_repo_ids(db, user.id)
    if not allowed_repos:
        return []

    if repo_id is not None:
        try:
            rid = uuid.UUID(repo_id)
        except ValueError as e:
            raise AppError("BAD_ID", "invalid repo id", status.HTTP_400_BAD_REQUEST) from e
        if rid not in allowed_repos:
            raise AppError("REPO_NOT_FOUND", "repo not found", status.HTTP_404_NOT_FOUND)
        target_repos = [rid]
    else:
        target_repos = allowed_repos

    stmt = (
        select(Review, Repository, PullRequest)
        .join(Repository, Repository.id == Review.repository_id)
        .join(PullRequest, PullRequest.id == Review.pull_request_id)
        .where(Review.repository_id.in_(target_repos), Review.deleted_at.is_(None))
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(Review.status == status_filter)

    rows = (await db.execute(stmt)).all()
    return [_item(r, repo, pr) for r, repo, pr in rows]


@router.get("/{review_id}", response_model=ReviewDetail)
async def get_review(
    review_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rvid = uuid.UUID(review_id)
    except ValueError as e:
        raise AppError("BAD_ID", "invalid review id", status.HTTP_400_BAD_REQUEST) from e
    review = await db.get(Review, rvid)
    if review is None or review.deleted_at is not None:
        raise AppError("REVIEW_NOT_FOUND", "review not found", status.HTTP_404_NOT_FOUND)
    if not await user_can_access_repo(db, user.id, review.repository_id):
        raise AppError("REVIEW_NOT_FOUND", "review not found", status.HTTP_404_NOT_FOUND)

    repo = await db.get(Repository, review.repository_id)
    pr = await db.get(PullRequest, review.pull_request_id)
    if repo is None or pr is None:
        raise AppError("REVIEW_NOT_FOUND", "review not found", status.HTTP_404_NOT_FOUND)

    cstmt = (
        select(ReviewComment)
        .where(ReviewComment.review_id == review.id, ReviewComment.deleted_at.is_(None))
        .order_by(ReviewComment.path, ReviewComment.line.nulls_last())
    )
    comments = (await db.execute(cstmt)).scalars().all()

    base = _item(review, repo, pr)
    return ReviewDetail(
        **base.model_dump(),
        comments=[
            ReviewCommentOut(
                id=str(c.id),
                path=c.path,
                line=c.line,
                side=c.side,
                severity=c.severity,
                category=c.category,
                message=c.message,
                suggestion=c.suggestion,
                confidence=float(c.confidence) if c.confidence is not None else None,
                posted=c.posted,
            )
            for c in comments
        ],
        tokens_input=review.tokens_input,
        tokens_output=review.tokens_output,
        cost_usd=float(review.cost_usd) if review.cost_usd is not None else None,
        error=review.error,
    )
