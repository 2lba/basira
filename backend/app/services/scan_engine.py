import asyncio
import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.integrations.anthropic_client import (
    AnthropicError,
    call_claude,
    estimate_cost_usd,
    parse_json_strict,
)
from app.integrations.github_api import GithubApiError, InstallationClient
from app.models.repository import Repository
from app.models.scan import Scan, ScanFinding
from app.services.diff_fetcher import DEFAULT_IGNORE_PATTERNS, find_installation_for_repo
from app.services.scan_prompt import (
    SCAN_SYSTEM_PROMPT,
    build_scan_user_prompt,
    validate_finding,
)

log = get_logger("basira.scan")

MAX_FINDINGS_PER_SCAN = 200
MAX_FILES = 400
MAX_FILE_BYTES = 60_000
CHARS_PER_TOKEN = 4
CHUNK_TOKEN_BUDGET = 8_000
TOTAL_TOKEN_BUDGET = 100_000

ProgressCallback = Callable[[int, str], Awaitable[None]]

SEVERITY_WEIGHTS = {"critical": 20, "major": 8, "minor": 3, "nit": 1}


def make_dedup_key(path: str, line: int | None, severity: str, category: str, message: str) -> str:
    """Stable signature for a finding, used to suppress repo-level false
    positives and to power compare. Hashes the message to keep keys short."""
    msg_hash = hashlib.sha256(message.strip().encode("utf-8")).hexdigest()[:16]
    return f"{path}|{line or 0}|{severity}|{category}|{msg_hash}"


# code extensions Claude reviews well; everything else is skipped
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".scala",
    ".rb",
    ".php",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".swift",
    ".m",
    ".mm",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".vue",
    ".svelte",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".dockerfile",
    ".tf",
    ".hcl",
    ".md",
}


@dataclass
class ScanFile:
    path: str
    sha: str
    size: int
    content: str = ""


@dataclass
class FileChunk:
    files: list[ScanFile] = field(default_factory=list)

    def estimate_tokens(self) -> int:
        total = 0
        for f in self.files:
            total += (len(f.content) + len(f.path)) // CHARS_PER_TOKEN + 1
        return total


@dataclass
class ScanOutcome:
    scan: Scan
    findings_created: int


def _ext(path: str) -> str:
    i = path.rfind(".")
    return path[i:].lower() if i != -1 else ""


def should_skip_path(path: str, custom_patterns: list[str] | None = None) -> str | None:
    """Return reason if file should be skipped, else None."""
    patterns = list(DEFAULT_IGNORE_PATTERNS)
    if custom_patterns:
        patterns.extend(custom_patterns)
    for p in patterns:
        try:
            if re.match(p, path):
                return f"ignore: {p}"
        except re.error:
            continue
    if _ext(path) not in ALLOWED_EXTENSIONS:
        return "extension not in allowlist"
    return None


def select_files(
    tree_entries: list[dict], custom_patterns: list[str] | None
) -> tuple[list[tuple[str, str, int]], int]:
    """Filter tree entries down to (path, sha, size) for reviewable files.
    Returns (kept, total_skipped)."""
    kept: list[tuple[str, str, int]] = []
    skipped = 0
    for e in tree_entries:
        if e.get("type") != "blob":
            continue
        path = e.get("path") or ""
        sha = e.get("sha") or ""
        size = int(e.get("size") or 0)
        if not path or not sha:
            skipped += 1
            continue
        if size > MAX_FILE_BYTES:
            skipped += 1
            continue
        if should_skip_path(path, custom_patterns):
            skipped += 1
            continue
        kept.append((path, sha, size))
    kept.sort(key=lambda x: x[2])  # smaller files first
    return kept[:MAX_FILES], skipped + max(0, len(kept) - MAX_FILES)


def chunk_files(files: list[ScanFile]) -> list[FileChunk]:
    chunks: list[FileChunk] = []
    current = FileChunk()
    current_tokens = 0
    budget = CHUNK_TOKEN_BUDGET
    for f in files:
        f_tok = (len(f.content) + len(f.path)) // CHARS_PER_TOKEN + 1
        if current.files and current_tokens + f_tok > budget:
            chunks.append(current)
            current = FileChunk()
            current_tokens = 0
        current.files.append(f)
        current_tokens += f_tok
    if current.files:
        chunks.append(current)
    return chunks


def compute_score(counts: dict[str, int]) -> int:
    penalty = 0
    for sev, w in SEVERITY_WEIGHTS.items():
        penalty += counts.get(sev, 0) * w
    return max(0, min(100, 100 - penalty))


def aggregate_counts(findings: list[dict]) -> dict[str, int]:
    out = {"total": len(findings), "critical": 0, "major": 0, "minor": 0, "nit": 0}
    for f in findings:
        sev = f.get("severity", "minor")
        if sev in out:
            out[sev] += 1
    return out


def build_summary(counts: dict[str, int], files_scanned: int) -> str:
    if counts.get("total", 0) == 0:
        return f"Scanned {files_scanned} files. No issues found."
    parts: list[str] = []
    for sev in ("critical", "major", "minor", "nit"):
        n = counts.get(sev, 0)
        if n:
            parts.append(f"{n} {sev}")
    issues = "issue" if counts["total"] == 1 else "issues"
    return f"Scanned {files_scanned} files. Found " + ", ".join(parts) + f" {issues}."


async def _call_claude_for_chunk(
    chunk: FileChunk,
    repo_full_name: str,
    custom_rules: str | None,
    model: str,
    api_key: str | None = None,
) -> tuple[list[dict], int, int]:
    user = build_scan_user_prompt(
        [(f.path, f.content) for f in chunk.files], repo_full_name, custom_rules
    )
    response = await call_claude(system=SCAN_SYSTEM_PROMPT, user=user, model=model, api_key=api_key)
    try:
        data = parse_json_strict(response.text)
    except AnthropicError:
        stricter = user + "\n\nIMPORTANT: respond with ONLY the JSON object. No prose."
        response = await call_claude(
            system=SCAN_SYSTEM_PROMPT, user=stricter, model=model, api_key=api_key
        )
        data = parse_json_strict(response.text)
    raw = data.get("findings", []) if isinstance(data, dict) else []
    cleaned: list[dict] = []
    paths_in_chunk = {f.path for f in chunk.files}
    for item in raw:
        v = validate_finding(item)
        if v is None:
            continue
        if v["file"] not in paths_in_chunk:
            continue
        cleaned.append(v)
    return cleaned, response.input_tokens, response.output_tokens


async def _set_progress(db: AsyncSession, scan: Scan, progress: int, message: str) -> None:
    scan.progress = max(0, min(100, progress))
    scan.progress_message = message[:255] if message else None
    await db.commit()
    await db.refresh(scan)


async def run_scan(db: AsyncSession, scan_id: uuid.UUID) -> ScanOutcome:
    settings = get_settings()
    scan = await db.get(Scan, scan_id)
    if scan is None:
        raise ValueError(f"scan {scan_id} not found")

    repo = await db.get(Repository, scan.repository_id)
    if repo is None:
        scan.status = "failed"
        scan.error = "repository not found"
        scan.finished_at = datetime.now(UTC)
        await db.commit()
        raise ValueError("repository not found")

    if settings.e2e_test_mode:
        from app.services.user_api_key import get_user_anthropic_key

        owner_id = scan.triggered_by_user_id
        if owner_id is None:
            inst_for_owner = await find_installation_for_repo(db, repo.id)
            if inst_for_owner is not None:
                owner_id = inst_for_owner.user_id
        if owner_id is not None and not await get_user_anthropic_key(db, owner_id):
            scan.status = "failed"
            scan.error = "MISSING_API_KEY: add your Anthropic API key in Settings"
            scan.finished_at = datetime.now(UTC)
            await db.commit()
            raise AnthropicError("missing user anthropic api key")
        return await _run_scan_e2e_stub(db, scan, repo)

    inst = await find_installation_for_repo(db, repo.id)
    if inst is None:
        scan.status = "failed"
        scan.error = "no installation linked to repo"
        scan.finished_at = datetime.now(UTC)
        await db.commit()
        raise ValueError("no installation")

    # BYOK - fetch the user's Anthropic key BEFORE we touch GitHub. Fail
    # fast with a clear, user-facing error so the user knows what to fix.
    from app.services.user_api_key import get_user_anthropic_key

    api_key_owner_id = scan.triggered_by_user_id or inst.user_id
    user_anthropic_key: str | None = None
    if api_key_owner_id is not None:
        user_anthropic_key = await get_user_anthropic_key(db, api_key_owner_id)
    if not user_anthropic_key:
        scan.status = "failed"
        scan.error = "MISSING_API_KEY: add your Anthropic API key in Settings"
        scan.finished_at = datetime.now(UTC)
        await db.commit()
        raise AnthropicError("missing user anthropic api key")

    model = repo.model_override or settings.claude_model
    scan.status = "running"
    scan.started_at = datetime.now(UTC)
    scan.model = model
    await _set_progress(db, scan, 2, "preparing")

    try:
        client = InstallationClient(inst.installation_id)
        await _set_progress(db, scan, 5, "fetching repository")

        branch = scan.ref or repo.default_branch or "main"
        try:
            head_sha = await client.get_branch_sha(repo.owner, repo.name, branch)
        except GithubApiError as e:
            if repo.default_branch and branch != repo.default_branch:
                head_sha = await client.get_branch_sha(repo.owner, repo.name, repo.default_branch)
                branch = repo.default_branch
            else:
                raise e
        scan.head_sha = head_sha
        scan.ref = branch
        await _set_progress(db, scan, 10, f"fetching tree @ {branch}")

        tree = await client.get_tree(repo.owner, repo.name, head_sha)
        kept, skipped_count = select_files(tree, repo.ignored_paths)
        scan.files_skipped = skipped_count
        await _set_progress(db, scan, 15, f"selected {len(kept)} files to scan")

        if not kept:
            scan.status = "succeeded"
            scan.files_scanned = 0
            scan.score = 100
            scan.summary = "No reviewable files in this repository."
            scan.counts = {"total": 0, "critical": 0, "major": 0, "minor": 0, "nit": 0}
            scan.finished_at = datetime.now(UTC)
            await _set_progress(db, scan, 100, "done")
            return ScanOutcome(scan=scan, findings_created=0)

        # download file contents (budget-bounded)
        files: list[ScanFile] = []
        bytes_used = 0
        max_total_bytes = TOTAL_TOKEN_BUDGET * CHARS_PER_TOKEN
        for i, (path, sha, size) in enumerate(kept):
            if bytes_used + size > max_total_bytes:
                break
            try:
                content = await client.get_blob_text(repo.owner, repo.name, sha)
            except GithubApiError:
                continue
            if not content:
                continue
            files.append(ScanFile(path=path, sha=sha, size=size, content=content))
            bytes_used += len(content)
            if i % 20 == 0:
                pct = 15 + int(30 * (i + 1) / max(1, len(kept)))
                await _set_progress(db, scan, pct, f"fetched {i + 1}/{len(kept)} files")

        await _set_progress(db, scan, 45, f"fetched {len(files)} files")

        chunks = chunk_files(files)
        all_findings: list[dict] = []
        total_in = 0
        total_out = 0

        for idx, chunk in enumerate(chunks, start=1):
            pct = 45 + int(50 * idx / max(1, len(chunks)))
            await _set_progress(db, scan, pct, f"reviewing chunk {idx}/{len(chunks)}")
            findings, t_in, t_out = await _call_claude_for_chunk(
                chunk,
                repo.full_name,
                repo.custom_rules,
                model,
                api_key=user_anthropic_key,
            )
            all_findings.extend(findings)
            total_in += t_in
            total_out += t_out
            if len(all_findings) >= MAX_FINDINGS_PER_SCAN:
                break

        # rank and cap
        all_findings.sort(
            key=lambda f: (
                -SEVERITY_WEIGHTS.get(f["severity"], 0),
                -f.get("confidence", 0),
            )
        )
        capped = all_findings[:MAX_FINDINGS_PER_SCAN]
        counts = aggregate_counts(capped)
        score = compute_score(counts)

        ignored_cats = set(repo.ignored_categories or [])
        fp_keys = set(repo.false_positive_keys or [])
        for c in capped:
            if c["category"] in ignored_cats:
                continue
            key = make_dedup_key(c["file"], c["line"], c["severity"], c["category"], c["message"])
            if key in fp_keys:
                continue
            db.add(
                ScanFinding(
                    scan_id=scan.id,
                    path=c["file"],
                    line=c["line"],
                    severity=c["severity"],
                    category=c["category"],
                    message=c["message"],
                    suggestion=c["suggestion"],
                    confidence=c["confidence"],
                    dedup_key=key,
                )
            )

        scan.status = "succeeded"
        scan.files_scanned = len(files)
        scan.score = score
        scan.counts = counts
        scan.summary = build_summary(counts, len(files))
        scan.tokens_input = total_in
        scan.tokens_output = total_out
        scan.cost_usd = estimate_cost_usd(model, total_in, total_out)
        scan.finished_at = datetime.now(UTC)
        await _set_progress(db, scan, 100, "done")

        log.info(
            "scan.done",
            repo=repo.full_name,
            findings=len(capped),
            score=score,
            files=len(files),
        )
        return ScanOutcome(scan=scan, findings_created=len(capped))
    except Exception as e:
        scan.status = "failed"
        scan.error = f"{e.__class__.__name__}: {str(e)[:500]}"
        scan.finished_at = datetime.now(UTC)
        await db.commit()
        log.exception("scan.failed", repo_id=str(scan.repository_id))
        raise


async def _run_scan_e2e_stub(db: AsyncSession, scan: Scan, repo: Repository) -> ScanOutcome:
    """Deterministic scan path for end-to-end tests. Steps through progress so
    the UI can render the progress bar, then emits canned findings. Subsequent
    scans for the same repo drop a nit and add a new minor so the compare view
    has something to show."""
    from sqlalchemy import func

    scan.status = "running"
    scan.started_at = datetime.now(UTC)
    scan.model = "claude-sonnet-4-5"
    scan.ref = scan.ref or repo.default_branch or "main"
    scan.head_sha = "deadbeefcafef00d1234567890abcdef12345678"

    steps = [
        (15, "fetching tree @ main"),
        (40, "fetched 8 files"),
        (70, "reviewing chunk 1/1"),
        (95, "finalizing"),
    ]
    for pct, msg in steps:
        await _set_progress(db, scan, pct, msg)
        await asyncio.sleep(0.5)

    prior = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(
                Scan.repository_id == repo.id,
                Scan.id != scan.id,
                Scan.status == "succeeded",
                Scan.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    base = [
        {
            "path": "app/auth.py",
            "line": 42,
            "severity": "critical",
            "category": "security",
            "message": "Token compared with ==, vulnerable to timing attack.",
            "suggestion": "use secrets.compare_digest(a, b)",
            "confidence": 0.95,
        },
        {
            "path": "app/db.py",
            "line": 117,
            "severity": "major",
            "category": "performance",
            "message": "N+1 query in user listing; preload memberships.",
            "suggestion": None,
            "confidence": 0.82,
        },
        {
            "path": "app/views.py",
            "line": 8,
            "severity": "minor",
            "category": "maintainability",
            "message": "Function is 60 lines; consider extracting permission check.",
            "suggestion": None,
            "confidence": 0.6,
        },
    ]
    if prior == 0:
        findings = base + [
            {
                "path": "scripts/build.sh",
                "line": None,
                "severity": "nit",
                "category": "style",
                "message": "Missing trailing newline at end of file.",
                "suggestion": None,
                "confidence": 0.4,
            },
        ]
    else:
        findings = base + [
            {
                "path": "app/cache.py",
                "line": 21,
                "severity": "minor",
                "category": "bug",
                "message": "Cache key collision possible when user_id is None.",
                "suggestion": None,
                "confidence": 0.7,
            },
        ]
    ignored_cats = set(repo.ignored_categories or [])
    fp_keys = set(repo.false_positive_keys or [])
    kept_findings: list[dict] = []
    for f in findings:
        if f["category"] in ignored_cats:
            continue
        key = make_dedup_key(f["path"], f["line"], f["severity"], f["category"], f["message"])
        if key in fp_keys:
            continue
        kept_findings.append(f)
        db.add(
            ScanFinding(
                scan_id=scan.id,
                path=f["path"],
                line=f["line"],
                severity=f["severity"],
                category=f["category"],
                message=f["message"],
                suggestion=f["suggestion"],
                confidence=f["confidence"],
                dedup_key=key,
            )
        )
    counts = aggregate_counts(kept_findings)
    scan.counts = counts
    scan.score = compute_score(counts)
    scan.summary = build_summary(counts, 8)
    scan.files_scanned = 8
    scan.files_skipped = 2
    scan.tokens_input = 4200
    scan.tokens_output = 380
    scan.cost_usd = 0.018
    scan.status = "succeeded"
    scan.finished_at = datetime.now(UTC)
    await _set_progress(db, scan, 100, "done")
    return ScanOutcome(scan=scan, findings_created=len(kept_findings))
