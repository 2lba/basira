from app.integrations.github_api import PrFile
from app.services.chunker import (
    CHARS_PER_TOKEN,
    Chunk,
    chunk_bundle,
)
from app.services.diff_fetcher import DiffBundle, file_from_github


def _bundle(files: list[PrFile]) -> DiffBundle:
    return DiffBundle(
        pr_number=1,
        head_sha="head",
        base_sha="base",
        files=[file_from_github(f) for f in files],
    )


def _pr_file(name: str, body_lines: int = 5) -> PrFile:
    patch = "@@ -1,3 +1,4 @@\n" + "\n".join(f"+line {i}" for i in range(body_lines))
    return PrFile(
        filename=name,
        status="modified",
        additions=body_lines,
        deletions=0,
        changes=body_lines,
        patch=patch,
        sha="abc",
    )


def test_should_emit_one_chunk_when_small_diffs_fit():
    bundle = _bundle([_pr_file("a.py"), _pr_file("b.py"), _pr_file("c.py")])
    chunks = chunk_bundle(bundle, chunk_token_budget=10_000)
    assert len(chunks) == 1
    assert chunks[0].file_count == 3


def test_should_split_when_chunk_budget_exceeded():
    big = _pr_file("big.py", body_lines=500)
    bundle = _bundle([big, _pr_file("small.py")])
    # tiny budget forces splits
    chunks = chunk_bundle(bundle, chunk_token_budget=200, total_token_budget=100_000)
    assert len(chunks) >= 2


def test_should_split_oversized_file_across_chunks():
    # build a file with multiple hunks adding up beyond budget
    patch_parts = []
    for i in range(10):
        patch_parts.append(f"@@ -{i*10},5 +{i*10},6 @@")
        patch_parts.append("\n".join(f"+line {j}" for j in range(100)))
    patch = "\n".join(patch_parts)
    huge = PrFile(
        filename="huge.py",
        status="modified",
        additions=1000,
        deletions=0,
        changes=1000,
        patch=patch,
        sha="abc",
    )
    bundle = _bundle([huge])
    # very small budget per chunk
    chunks = chunk_bundle(bundle, chunk_token_budget=300, total_token_budget=100_000)
    assert len(chunks) >= 2
    # all pieces should keep huge.py as filename
    for c in chunks:
        for piece in c.files:
            assert piece.filename == "huge.py"


def test_should_respect_total_budget():
    files = [_pr_file(f"f{i}.py", body_lines=200) for i in range(20)]
    bundle = _bundle(files)
    chunks = chunk_bundle(bundle, chunk_token_budget=500, total_token_budget=2000)
    total = sum(c.estimate_tokens() for c in chunks)
    # allow a small over-by-one due to per-chunk overhead estimate
    assert total <= 2200


def test_should_skip_ignored_files_in_chunks():
    files = [
        _pr_file("a.py"),
        _pr_file("package-lock.json"),
        _pr_file("dist/bundle.js"),
        _pr_file("src/b.py"),
    ]
    bundle = _bundle(files)
    chunks = chunk_bundle(bundle, chunk_token_budget=10_000)
    names = [p.filename for c in chunks for p in c.files]
    assert "package-lock.json" not in names
    assert "dist/bundle.js" not in names
    assert "a.py" in names
    assert "src/b.py" in names


def test_empty_chunk_helpers():
    c = Chunk()
    assert c.estimate_tokens() == 0
    assert c.file_count == 0


def test_chars_per_token_assumption():
    assert CHARS_PER_TOKEN >= 1
