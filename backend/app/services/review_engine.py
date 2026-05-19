import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

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
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import Review, ReviewComment
from app.services.chunker import Chunk, chunk_bundle
from app.services.diff_fetcher import DiffBundle, fetch_diff_bundle
from app.services.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    passes_severity_threshold,
    validate_finding,
)

log = get_logger("reviewly.review")

MAX_FINDINGS_PER_REVIEW = 30
DEFAULT_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class ReviewOutcome:
    review: Review
    comments_created: int
    skipped_existing: bool = False
    findings_raw: list[dict] = field(default_factory=list)
    summary: str = ""
    counts: dict[str, int] = field(default_factory=dict)


def compute_diff_hash(bundle: DiffBundle) -> str:
    h = hashlib.sha256()
    for f in bundle.reviewable_files:
        h.update(f.filename.encode())
        h.update(b"\x00")
        for hunk in f.hunks:
            h.update(hunk.header.encode())
            h.update(b"\x00")
            h.update(hunk.body.encode())
            h.update(b"\xff")
    return h.hexdigest()


async def _existing_review(db: AsyncSession, pr_id: uuid.UUID, diff_hash: str) -> Review | None:
    stmt = select(Review).where(
        Review.pull_request_id == pr_id,
        Review.diff_hash == diff_hash,
        Review.status.in_(("succeeded", "posted")),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _claude_review_chunk(
    chunk: Chunk,
    repo_full_name: str,
    pr_number: int,
    custom_rules: str | None,
    model: str,
) -> tuple[list[dict], str, int, int]:
    """Call claude on one chunk, parse the JSON, return validated findings."""
    user = build_user_prompt(chunk, repo_full_name, pr_number, custom_rules)
    response = await call_claude(system=SYSTEM_PROMPT, user=user, model=model)
    try:
        data = parse_json_strict(response.text)
    except AnthropicError:
        # one re-prompt with stricter instruction
        stricter = user + "\n\nIMPORTANT: respond with ONLY the JSON object. No prose."
        response = await call_claude(system=SYSTEM_PROMPT, user=stricter, model=model)
        data = parse_json_strict(response.text)

    raw = data.get("findings", []) if isinstance(data, dict) else []
    summary = str(data.get("summary", "")) if isinstance(data, dict) and data.get("summary") else ""
    cleaned: list[dict] = []
    for item in raw:
        v = validate_finding(item)
        if v is not None:
            cleaned.append(v)
    return cleaned, summary, response.input_tokens, response.output_tokens


def _file_lines_in_chunk(chunk: Chunk) -> dict[str, set[int]]:
    """For each filename in chunk, set of new-side line numbers it covers.
    Used to validate that model-cited line numbers are real."""
    out: dict[str, set[int]] = {}
    for piece in chunk.files:
        lines = out.setdefault(piece.filename, set())
        for h in piece.hunks:
            new = h.new_start
            for ln in h.body.split("\n"):
                if ln.startswith("+") and not ln.startswith("+++"):
                    lines.add(new)
                    new += 1
                elif not ln.startswith("-") and not ln.startswith("---"):
                    new += 1
    return out


def _filter_findings(
    findings: list[dict],
    chunk: Chunk,
    severity_threshold: str,
    confidence_threshold: float,
) -> list[dict]:
    valid_lines = _file_lines_in_chunk(chunk)
    kept: list[dict] = []
    for f in findings:
        if f["confidence"] < confidence_threshold:
            continue
        if not passes_severity_threshold(f["severity"], severity_threshold):
            continue
        if f["file"] not in valid_lines:
            # tolerate: model may use a slightly different path; still post but without line anchor
            f["line"] = None
        elif f["line"] is not None and f["line"] not in valid_lines[f["file"]]:
            # cited line not in our diff; drop the anchor, keep the finding
            f["line"] = None
        kept.append(f)
    return kept


async def run_review(
    db: AsyncSession,
    pr: PullRequest,
    *,
    model_override: str | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> ReviewOutcome:
    settings = get_settings()
    repo = await db.get(Repository, pr.repository_id)
    if repo is None:
        raise AnthropicError("repository not found")

    bundle = await fetch_diff_bundle(db, pr, max_files=settings.review_max_files)
    if not bundle.reviewable_files:
        review = Review(
            pull_request_id=pr.id,
            repository_id=repo.id,
            status="succeeded",
            head_sha=pr.head_sha,
            diff_hash=compute_diff_hash(bundle),
            model=model_override or repo.model_override or settings.claude_model,
            summary="No reviewable changes (all files skipped or empty).",
            counts={"findings": 0},
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        return ReviewOutcome(review=review, comments_created=0, summary=review.summary or "")

    diff_hash = compute_diff_hash(bundle)
    existing = await _existing_review(db, pr.id, diff_hash)
    if existing is not None:
        return ReviewOutcome(
            review=existing,
            comments_created=0,
            skipped_existing=True,
            summary=existing.summary or "",
        )

    chunks = chunk_bundle(bundle)
    model = model_override or repo.model_override or settings.claude_model
    severity_threshold = repo.severity_threshold or settings.review_severity_threshold

    review = Review(
        pull_request_id=pr.id,
        repository_id=repo.id,
        status="running",
        head_sha=pr.head_sha,
        diff_hash=diff_hash,
        model=model,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    all_findings: list[dict] = []
    summaries: list[str] = []
    total_in = 0
    total_out = 0

    try:
        for chunk in chunks:
            findings, summary, t_in, t_out = await _claude_review_chunk(
                chunk, repo.full_name, pr.number, repo.custom_rules, model
            )
            kept = _filter_findings(findings, chunk, severity_threshold, confidence_threshold)
            all_findings.extend(kept)
            if summary:
                summaries.append(summary)
            total_in += t_in
            total_out += t_out

        # cap volume
        all_findings.sort(
            key=lambda f: (
                -_severity_rank(f["severity"]),
                -f.get("confidence", 0),
            )
        )
        capped = all_findings[:MAX_FINDINGS_PER_REVIEW]

        counts = _counts(capped)
        summary_text = " ".join(summaries).strip() or _default_summary(counts)

        review.status = "succeeded"
        review.summary = summary_text
        review.tokens_input = total_in
        review.tokens_output = total_out
        review.cost_usd = estimate_cost_usd(model, total_in, total_out)
        review.counts = counts

        # persist comments
        for c in capped:
            db.add(
                ReviewComment(
                    review_id=review.id,
                    path=c["file"],
                    line=c["line"],
                    side=c["side"],
                    severity=c["severity"],
                    category=c["category"],
                    message=c["message"],
                    suggestion=c["suggestion"],
                    confidence=c["confidence"],
                    posted=False,
                )
            )

        await db.commit()
        await db.refresh(review)
        log.info(
            "review.done",
            pr=pr.number,
            repo=repo.full_name,
            findings=len(capped),
            in_tok=total_in,
            out_tok=total_out,
        )
        return ReviewOutcome(
            review=review,
            comments_created=len(capped),
            findings_raw=capped,
            summary=summary_text,
            counts=counts,
        )
    except Exception as e:
        review.status = "failed"
        review.error = f"{e.__class__.__name__}: {str(e)[:500]}"
        await db.commit()
        log.exception("review.failed", pr=pr.number, repo=repo.full_name)
        raise


def _severity_rank(s: str) -> int:
    return {"critical": 3, "major": 2, "minor": 1, "nit": 0}.get(s, 0)


def _counts(findings: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {
        "total": len(findings),
        "critical": 0,
        "major": 0,
        "minor": 0,
        "nit": 0,
    }
    for f in findings:
        sev = f["severity"]
        if sev in out:
            out[sev] += 1
    return out


def _default_summary(counts: dict[str, int]) -> str:
    if counts.get("total", 0) == 0:
        return "No issues found."
    parts: list[str] = []
    for sev in ("critical", "major", "minor", "nit"):
        n = counts.get(sev, 0)
        if n:
            parts.append(f"{n} {sev}")
    return "Found " + ", ".join(parts) + " " + ("issue" if counts["total"] == 1 else "issues") + "."


def _counts_to_dict(c: dict[str, int]) -> dict[str, Any]:
    return dict(c)
