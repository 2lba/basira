from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    name: str
    full_name: str
    default_branch: str | None
    private: bool
    review_enabled: bool
    severity_threshold: str
    ignored_paths: list[str] | None = None
    custom_rules: str | None = None
    model_override: str | None = None


class RepoUpdate(BaseModel):
    review_enabled: bool | None = None
    severity_threshold: str | None = Field(default=None, max_length=32)
    ignored_paths: list[str] | None = None
    custom_rules: str | None = Field(default=None, max_length=10_000)
    model_override: str | None = Field(default=None, max_length=64)


class ReviewListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    pull_request_id: str
    pr_number: int
    pr_title: str
    repo_full_name: str
    status: str
    head_sha: str
    model: str | None
    summary: str | None
    counts: dict[str, int] | None = None
    created_at: datetime


class ReviewCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    path: str
    line: int | None
    side: str | None
    severity: str
    category: str
    message: str
    suggestion: str | None
    confidence: float | None
    posted: bool


class ReviewDetail(ReviewListItem):
    comments: list[ReviewCommentOut]
    tokens_input: int | None
    tokens_output: int | None
    cost_usd: float | None
    error: str | None


class ScanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    repo_full_name: str
    status: str
    progress: int
    progress_message: str | None
    ref: str | None
    head_sha: str | None
    score: int | None
    summary: str | None
    counts: dict[str, int] | None = None
    files_scanned: int | None
    files_skipped: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ScanFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    path: str
    line: int | None
    severity: str
    category: str
    message: str
    suggestion: str | None
    confidence: float | None


class ScanDetail(ScanListItem):
    findings: list[ScanFindingOut]
    tokens_input: int | None
    tokens_output: int | None
    cost_usd: float | None
    model: str | None
    error: str | None


class ScanCompareEntry(BaseModel):
    path: str
    line: int | None
    severity: str
    category: str
    message: str
    suggestion: str | None


class ScanCompareResult(BaseModel):
    a: ScanListItem
    b: ScanListItem
    score_delta: int | None
    new_findings: list[ScanCompareEntry]
    resolved_findings: list[ScanCompareEntry]
    persisting_findings: list[ScanCompareEntry]
    counts_delta: dict[str, int]
