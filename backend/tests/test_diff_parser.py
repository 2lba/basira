from app.integrations.github_api import PrFile
from app.services.diff_fetcher import (
    DEFAULT_IGNORE_PATTERNS,
    file_from_github,
    parse_patch,
    should_skip,
)

PATCH = """@@ -1,3 +1,4 @@
 def hello():
-    return 'hi'
+    return 'hello'
+    # added line
@@ -10,2 +11,2 @@ class Foo:
 a
-b
+c"""


def test_should_parse_two_hunks_when_patch_has_two_headers():
    hunks = parse_patch(PATCH)
    assert len(hunks) == 2
    assert hunks[0].old_start == 1
    assert hunks[0].new_count == 4
    assert hunks[1].old_start == 10
    assert "class Foo" in hunks[1].header


def test_should_return_empty_when_patch_is_empty():
    assert parse_patch("") == []
    assert parse_patch(None or "") == []


def test_should_match_lock_files_in_default_ignore():
    assert should_skip("package-lock.json") is not None
    assert should_skip("src/yarn.lock") is not None
    assert should_skip("Cargo.lock") is not None
    assert should_skip("vendor/foo/file.go") is not None
    assert should_skip("alembic/migrations/0001.py") is not None


def test_should_not_skip_when_normal_source_file():
    assert should_skip("src/main.py") is None
    assert should_skip("app/api/routes/auth.py") is None
    assert should_skip("frontend/src/App.jsx") is None


def test_should_skip_when_custom_pattern_supplied():
    assert should_skip("config/secrets.yml", [r".*/secrets\.yml$"]) is not None


def test_should_mark_binary_when_no_hunks_and_changes_present():
    pf = PrFile(
        filename="logo.png",
        status="modified",
        additions=0,
        deletions=0,
        changes=1,
        patch=None,
        sha="abc",
    )
    df = file_from_github(pf)
    # png is in default ignore, so it's skipped via pattern not binary detection
    assert df.skipped


def test_should_mark_binary_when_unknown_extension_no_patch():
    pf = PrFile(
        filename="data.bin",
        status="modified",
        additions=0,
        deletions=0,
        changes=1,
        patch=None,
        sha="abc",
    )
    df = file_from_github(pf)
    assert df.skipped
    assert df.skip_reason == "binary file"


def test_should_skip_minified_js():
    pf = PrFile(
        filename="static/app.min.js",
        status="modified",
        additions=1,
        deletions=1,
        changes=2,
        patch="@@ -1 +1 @@\n-a\n+b\n",
        sha="abc",
    )
    df = file_from_github(pf)
    assert df.skipped
    assert df.skip_reason and "ignore pattern" in df.skip_reason


def test_should_keep_when_python_source_changed():
    pf = PrFile(
        filename="app/main.py",
        status="modified",
        additions=2,
        deletions=1,
        changes=3,
        patch=PATCH,
        sha="abc",
    )
    df = file_from_github(pf)
    assert not df.skipped
    assert len(df.hunks) == 2


def test_default_ignore_patterns_compile():
    # ensure all default patterns are valid regex
    import re

    for p in DEFAULT_IGNORE_PATTERNS:
        re.compile(p)
