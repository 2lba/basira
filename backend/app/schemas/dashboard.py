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
    connected: bool = False
    schedule_kind: str = "none"
    schedule_dow: int | None = None
    schedule_dom: int | None = None
    schedule_hour: int | None = None
    schedule_minute: int | None = None
    last_scheduled_run_at: datetime | None = None


class RepoUpdate(BaseModel):
    review_enabled: bool | None = None
    severity_threshold: str | None = Field(default=None, max_length=32)
    ignored_paths: list[str] | None = None
    custom_rules: str | None = Field(default=None, max_length=10_000)
    model_override: str | None = Field(default=None, max_length=64)
    schedule_kind: str | None = Field(default=None, max_length=16)
    schedule_dow: int | None = Field(default=None, ge=0, le=6)
    schedule_dom: int | None = Field(default=None, ge=1, le=31)
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)


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
    error: str | None = None


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
    resolved_at: datetime | None = None
    false_positive_at: datetime | None = None
    dedup_key: str | None = None


class ScanDetail(ScanListItem):
    findings: list[ScanFindingOut]
    tokens_input: int | None
    tokens_output: int | None
    cost_usd: float | None
    model: str | None


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


class ScanShareResponse(BaseModel):
    token: str
    url: str


class PublicScanFinding(BaseModel):
    path: str
    line: int | None
    severity: str
    category: str
    message: str
    suggestion: str | None


class PublicScan(BaseModel):
    repo_full_name: str
    head_sha: str | None
    ref: str | None
    score: int | None
    summary: str | None
    counts: dict[str, int] | None
    files_scanned: int | None
    model: str | None
    finished_at: datetime | None
    findings: list[PublicScanFinding]
