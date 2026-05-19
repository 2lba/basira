from dataclasses import dataclass, field

from app.services.diff_fetcher import DiffBundle, DiffFile, DiffHunk

# rough char-based proxy for tokens (avg ~4 chars/token in code)
CHARS_PER_TOKEN = 4
DEFAULT_CHUNK_TOKEN_BUDGET = 8000
DEFAULT_TOTAL_TOKEN_BUDGET = 100_000


@dataclass
class FilePiece:
    filename: str
    status: str
    hunks: list[DiffHunk] = field(default_factory=list)
    truncated: bool = False

    @property
    def char_size(self) -> int:
        return sum(len(h.header) + 1 + len(h.body) for h in self.hunks) + len(self.filename) + 8

    def estimate_tokens(self) -> int:
        return self.char_size // CHARS_PER_TOKEN + 1


@dataclass
class Chunk:
    files: list[FilePiece] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    def estimate_tokens(self) -> int:
        return sum(f.estimate_tokens() for f in self.files)


def _piece_for_file(f: DiffFile) -> FilePiece:
    return FilePiece(filename=f.filename, status=f.status, hunks=list(f.hunks))


def _split_oversized_file(f: DiffFile, budget_tokens: int) -> list[FilePiece]:
    """If one file exceeds budget, split its hunks across pieces, each piece
    keeps the same filename but only carries hunks that fit."""
    budget_chars = budget_tokens * CHARS_PER_TOKEN
    pieces: list[FilePiece] = []
    current = FilePiece(filename=f.filename, status=f.status)
    for h in f.hunks:
        h_size = len(h.header) + 1 + len(h.body)
        if current.hunks and current.char_size + h_size > budget_chars:
            pieces.append(current)
            current = FilePiece(filename=f.filename, status=f.status)
        if h_size > budget_chars:
            # truncate hunk body to fit
            allowed = budget_chars - (len(h.header) + 1)
            if allowed > 0:
                truncated_body = h.body[:allowed]
                current.hunks.append(
                    DiffHunk(
                        header=h.header,
                        body=truncated_body,
                        old_start=h.old_start,
                        old_count=h.old_count,
                        new_start=h.new_start,
                        new_count=h.new_count,
                    )
                )
                current.truncated = True
            pieces.append(current)
            current = FilePiece(filename=f.filename, status=f.status)
        else:
            current.hunks.append(h)
    if current.hunks:
        pieces.append(current)
    return pieces


def chunk_bundle(
    bundle: DiffBundle,
    chunk_token_budget: int = DEFAULT_CHUNK_TOKEN_BUDGET,
    total_token_budget: int = DEFAULT_TOTAL_TOKEN_BUDGET,
) -> list[Chunk]:
    """Pack reviewable files into chunks bounded by chunk_token_budget. Splits
    files larger than a single chunk across multiple chunks. Stops once
    total_token_budget is exhausted across all chunks."""
    chunks: list[Chunk] = []
    current = Chunk()
    spent = 0

    for f in bundle.reviewable_files:
        piece = _piece_for_file(f)

        if piece.estimate_tokens() > chunk_token_budget:
            # flush current
            if current.files:
                chunks.append(current)
                spent += current.estimate_tokens()
                current = Chunk()
                if spent >= total_token_budget:
                    break
            split = _split_oversized_file(f, chunk_token_budget)
            for sp in split:
                if spent + sp.estimate_tokens() > total_token_budget:
                    return chunks
                chunks.append(Chunk(files=[sp]))
                spent += sp.estimate_tokens()
            continue

        # would adding this piece overflow the current chunk?
        if current.estimate_tokens() + piece.estimate_tokens() > chunk_token_budget:
            if current.files:
                chunks.append(current)
                spent += current.estimate_tokens()
                if spent >= total_token_budget:
                    return chunks
                current = Chunk()

        if spent + current.estimate_tokens() + piece.estimate_tokens() > total_token_budget:
            break
        current.files.append(piece)

    if current.files:
        chunks.append(current)
    return chunks
