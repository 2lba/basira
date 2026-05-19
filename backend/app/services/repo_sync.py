import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.github_oauth import OAuthRepo
from app.models.installation import InstallationRepository
from app.models.repository import Repository
from app.models.user_repository import UserRepository

log = get_logger("basira.repo_sync")


async def sync_user_repos(
    db: AsyncSession, user_id: uuid.UUID, repos: list[OAuthRepo]
) -> dict:
    """Upsert each OAuth-discovered repo and link it to the user. Repositories
    that already have an InstallationRepository row are marked connected=True;
    new ones default to False until the user installs the app on them."""
    if not repos:
        return {"upserted": 0, "linked": 0}

    incoming_ids = [r.github_repo_id for r in repos]
    existing = (
        await db.execute(
            select(Repository).where(Repository.github_repo_id.in_(incoming_ids))
        )
    ).scalars().all()
    by_gh_id = {r.github_repo_id: r for r in existing}

    upserted_ids: list[uuid.UUID] = []
    for oauth in repos:
        repo = by_gh_id.get(oauth.github_repo_id)
        if repo is None:
            repo = Repository(
                github_repo_id=oauth.github_repo_id,
                owner=oauth.owner,
                name=oauth.name,
                full_name=oauth.full_name,
                default_branch=oauth.default_branch,
                private=oauth.private,
                review_enabled=True,
                severity_threshold="minor",
                connected=False,
            )
            db.add(repo)
            await db.flush()
        else:
            repo.owner = oauth.owner
            repo.name = oauth.name
            repo.full_name = oauth.full_name
            repo.private = oauth.private
            if oauth.default_branch:
                repo.default_branch = oauth.default_branch
        upserted_ids.append(repo.id)

    # mark connected for any repos that have a live installation_repositories row
    connected_rows = (
        await db.execute(
            select(InstallationRepository.repository_id).where(
                InstallationRepository.repository_id.in_(upserted_ids),
                InstallationRepository.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    connected_set = set(connected_rows)
    for rid in upserted_ids:
        repo = await db.get(Repository, rid)
        if repo is not None:
            repo.connected = rid in connected_set

    # user_repositories link table — one row per (user, repo)
    existing_links = (
        await db.execute(
            select(UserRepository.repository_id).where(
                UserRepository.user_id == user_id,
                UserRepository.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    linked_set = set(existing_links)
    linked = 0
    for rid in upserted_ids:
        if rid not in linked_set:
            db.add(UserRepository(user_id=user_id, repository_id=rid))
            linked += 1

    await db.commit()
    log.info(
        "repo_sync.done",
        user_id=str(user_id),
        upserted=len(upserted_ids),
        linked=linked,
        connected=len(connected_set),
    )
    return {"upserted": len(upserted_ids), "linked": linked, "connected": len(connected_set)}
