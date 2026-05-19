from textwrap import dedent

SCAN_SYSTEM_PROMPT = dedent(
    """\
    You are a senior software engineer auditing a repository's source code. You
    read files carefully and respond with specific, actionable feedback. You do
    not hedge. You do not pad with praise.

    Rules:
    - Only flag real issues. Don't comment on style preferences unless they
      affect correctness or maintainability.
    - Prefer fewer high-signal findings over many low-signal ones.
    - Cite the exact file path as shown and a 1-based line number when possible.
    - Keep messages concise (1-3 sentences). Include "suggestion" only when you
      can give a concrete, small fix.
    - If files look clean, return an empty findings array.

    Categories: bug, security, performance, maintainability, style, suggestion.
    Severities: critical, major, minor, nit.

    Output strictly a JSON object and nothing else (no markdown):

    {
      "findings": [
        {
          "file": "string (path exactly as labeled)",
          "line": 12,
          "severity": "critical|major|minor|nit",
          "category": "bug|security|performance|maintainability|style|suggestion",
          "message": "string",
          "suggestion": "string or null",
          "confidence": 0.0
        }
      ]
    }
    """
).strip()


def _format_file(path: str, content: str) -> str:
    lines = content.splitlines()
    numbered = "\n".join(f"{i + 1:>5}  {line}" for i, line in enumerate(lines))
    return f"--- file: {path} ---\n{numbered}"


def build_scan_user_prompt(
    files: list[tuple[str, str]], repo_full_name: str, custom_rules: str | None
) -> str:
    body = "\n\n".join(_format_file(p, c) for p, c in files)
    rules = (
        f"\n\nRepo-specific rules to apply:\n{custom_rules.strip()}"
        if custom_rules and custom_rules.strip()
        else ""
    )
    return dedent(
        f"""\
        Audit the following files from {repo_full_name}.{rules}

        Lines are pre-numbered for citation. Use those numbers in the "line" field.

        {body}

        Return only the JSON object.
        """
    ).strip()


def validate_finding(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    file = item.get("file")
    message = item.get("message")
    if not file or not message:
        return None
    severity = str(item.get("severity", "minor")).lower()
    if severity not in ("critical", "major", "minor", "nit"):
        severity = "minor"
    category = str(item.get("category", "suggestion")).lower()
    if category not in ("bug", "security", "performance", "maintainability", "style", "suggestion"):
        category = "suggestion"
    line = item.get("line")
    try:
        line_val = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_val = None
    confidence_raw = item.get("confidence", 0.7)
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except (TypeError, ValueError):
        confidence = 0.7
    suggestion = item.get("suggestion")
    if suggestion is not None:
        suggestion = str(suggestion)
    return {
        "file": str(file),
        "line": line_val,
        "severity": severity,
        "category": category,
        "message": str(message).strip(),
        "suggestion": suggestion,
        "confidence": confidence,
    }
