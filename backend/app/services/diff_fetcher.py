import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.github_api import GithubApiError, InstallationClient, PrFile
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.pull_request import PullRequest
from app.models.repository import Repository

log = get_logger("basira.diff")


# default skip patterns: lock files, minified, build artifacts, migrations, vendored
DEFAULT_IGNORE_PATTERNS = [
    r".*/?package-lock\.json$",
    r".*/?yarn\.lock$",
    r".*/?pnpm-lock\.yaml$",
    r".*/?poetry\.lock$",
    r".*/?Pipfile\.lock$",
    r".*/?Cargo\.lock$",
    r".*/?go\.sum$",
    r".*/?composer\.lock$",
    r".*\.min\.(js|css)$",
    r".*\.map$",
    r".*\.(png|jpg|jpeg|gif|webp|svg|ico|pdf|zip|tar|gz|bz2|7z|rar)$",
    r".*\.(woff|woff2|ttf|otf|eot)$",
    r".*\.(mp3|mp4|mov|avi|wav|flac)$",
    r".*/?migrations?/.*",  # django/alembic auto-gen
    r".*/?vendor/.*",
    r".*/?node_modules/.*",
    r".*/?dist/.*",
    r".*/?build/.*",
    r".*\.snap$",  # jest snapshots
    r".*generated.*\.(go|ts|js|py)$",
]


@dataclass(frozen=True)
class DiffHunk:
    header: str
    body: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int


@dataclass
class DiffFile:
    filename: str
    status: str
    additions: int
    deletions: int
    sha: str | None
    previous_filename: str | None
    hunks: list[DiffHunk] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def is_binary(self) -> bool:
        return any(h.body.startswith("Binary files ") for h in self.hunks) or (
            not self.hunks and self.status != "removed"
        )


@dataclass
class DiffBundle:
    pr_number: int
    head_sha: str
    base_sha: str | None
    files: list[DiffFile]

    @property
    def reviewable_files(self) -> list[DiffFile]:
        return [f for f in self.files if not f.skipped and f.hunks]


_HUNK_HEADER = re.compile(r"^@@ -(?P<o>\d+)(?:,(?P<oc>\d+))? \+(?P<n>\d+)(?:,(?P<nc>\d+))? @@.*$")


def parse_patch(patch: str) -> list[DiffHunk]:
    """Parse the `patch` field returned by GitHub /pulls/.../files into hunks."""
    if not patch:
        return []
    hunks: list[DiffHunk] = []
    current_header: str | None = None
    current_body: list[str] = []
    current_meta: tuple[int, int, int, int] | None = None

    def flush():
        if current_header is None or current_meta is None:
            return
        o, oc, n, nc = current_meta
        hunks.append(
            DiffHunk(
                header=current_header,
                body="\n".join(current_body),
                old_start=o,
                old_count=oc,
                new_start=n,
                new_count=nc,
            )
        )

    for line in patch.splitlines():
        m = _HUNK_HEADER.match(line)
        if m:
            flush()
            current_header = line
            current_body = []
            o = int(m.group("o"))
            oc = int(m.group("oc") or "1")
            n = int(m.group("n"))
            nc = int(m.group("nc") or "1")
            current_meta = (o, oc, n, nc)
        else:
            if current_header is None:
                current_header = ""
                current_body = []
                current_meta = (0, 0, 0, 0)
            current_body.append(line)

    flush()
    return hunks


def should_skip(filename: str, custom_patterns: list[str] | None = None) -> str | None:
    """Returns a reason string if file should be skipped, else None."""
    patterns = list(DEFAULT_IGNORE_PATTERNS)
    if custom_patterns:
        patterns.extend(custom_patterns)
    for p in patterns:
        try:
            if re.match(p, filename):
                return f"matched ignore pattern: {p}"
        except re.error:
            continue
    return None


def file_from_github(pf: PrFile, custom_patterns: list[str] | None = None) -> DiffFile:
    skip = should_skip(pf.filename, custom_patterns)
    hunks = parse_patch(pf.patch or "")
    is_bin = (not hunks) and pf.status != "removed" and pf.changes > 0
    df = DiffFile(
        filename=pf.filename,
        status=pf.status,
        additions=pf.additions,
        deletions=pf.deletions,
        sha=pf.sha,
        previous_filename=pf.previous_filename,
        hunks=hunks,
        skipped=bool(skip) or is_bin,
        skip_reason=skip or ("binary file" if is_bin else None),
    )
    return df


async def find_installation_for_repo(db: AsyncSession, repo_id) -> GithubInstallation | None:
    stmt = (
        select(GithubInstallation)
        .join(
            InstallationRepository,
            InstallationRepository.installation_id == GithubInstallation.id,
        )
        .where(
            InstallationRepository.repository_id == repo_id,
            InstallationRepository.deleted_at.is_(None),
            GithubInstallation.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def fetch_diff_bundle(db: AsyncSession, pr: PullRequest, max_files: int) -> DiffBundle:
    repo = await db.get(Repository, pr.repository_id)
    if repo is None:
        raise GithubApiError(404, "repository not found locally")

    inst = await find_installation_for_repo(db, repo.id)
    if inst is None:
        raise GithubApiError(404, f"no installation linked to repo {repo.full_name}")

    client = InstallationClient(inst.installation_id)
    raw_files = await client.list_pr_files(repo.owner, repo.name, pr.number)

    patterns = repo.ignored_paths or None
    files = [file_from_github(pf, patterns) for pf in raw_files]

    # cap to max_files reviewable; keep skipped for transparency
    reviewable = 0
    for f in files:
        if not f.skipped:
            reviewable += 1
            if reviewable > max_files:
                f.skipped = True
                f.skip_reason = "exceeded review_max_files"

    return DiffBundle(
        pr_number=pr.number,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        files=files,
    )
