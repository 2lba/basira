import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.installation import GithubInstallation, InstallationRepository
from app.models.repository import Repository
from app.models.user_repository import UserRepository


async def user_repo_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Union of repos visible to the user: those linked via app installation
    AND those discovered via OAuth /user/repos (user_repositories)."""
    from_install = (
        select(InstallationRepository.repository_id)
        .join(
            GithubInstallation,
            GithubInstallation.id == InstallationRepository.installation_id,
        )
        .where(
            GithubInstallation.user_id == user_id,
            GithubInstallation.deleted_at.is_(None),
            InstallationRepository.deleted_at.is_(None),
        )
    )
    from_oauth = select(UserRepository.repository_id).where(
        UserRepository.user_id == user_id,
        UserRepository.deleted_at.is_(None),
    )
    install_ids = (await db.execute(from_install)).scalars().all()
    oauth_ids = (await db.execute(from_oauth)).scalars().all()
    return list({*install_ids, *oauth_ids})


async def user_can_access_repo(db: AsyncSession, user_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
    ids = await user_repo_ids(db, user_id)
    return repo_id in ids


async def list_user_repos(db: AsyncSession, user_id: uuid.UUID) -> list[Repository]:
    ids = await user_repo_ids(db, user_id)
    if not ids:
        return []
    stmt = (
        select(Repository)
        .where(Repository.id.in_(ids), Repository.deleted_at.is_(None))
        .order_by(Repository.connected.desc(), Repository.full_name)
    )
    return list((await db.execute(stmt)).scalars().all())
