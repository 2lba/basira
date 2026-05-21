from textwrap import dedent

from app.services.chunker import Chunk, FilePiece

SYSTEM_PROMPT = dedent(
    """\
    You are a senior software engineer doing a code review on a GitHub pull
    request. You read diffs carefully and respond with specific, actionable
    feedback. You do not hedge. You do not pad with praise.

    Rules:
    - Only flag real issues. Don't comment on style preferences unless they
      affect correctness or maintainability.
    - Prefer fewer high-signal comments over many low-signal ones.
    - If the diff is fine, return an empty findings array.
    - Cite the file and the *new* line number from the diff (the right-hand
      side of @@). Never invent line numbers.
    - Keep messages concise (1-3 sentences). Include a "suggestion" only when
      you can give a concrete, small fix.

    Categories: bug, security, performance, maintainability, style, suggestion.
    Severities: critical, major, minor, nit.

    Output strictly a JSON object with this shape and nothing else (no
    markdown, no commentary):

    {
      "findings": [
        {
          "file": "string (path as shown in the diff)",
          "line": 123,
          "side": "RIGHT",
          "severity": "critical|major|minor|nit",
          "category": "bug|security|performance|maintainability|style|suggestion",
          "message": "string",
          "suggestion": "string or null",
          "confidence": 0.0
        }
      ],
      "summary": "one short paragraph or empty string"
    }
    """
).strip()


_EXAMPLE_1_OUTPUT = (
    '{"findings":[{"file":"app/auth.py","line":12,"side":"RIGHT",'
    '"severity":"critical","category":"security",'
    '"message":"Token compared with == - vulnerable to timing attacks. '
    'Use secrets.compare_digest.",'
    '"suggestion":"return secrets.compare_digest(token, EXPECTED)",'
    '"confidence":0.95}],'
    '"summary":"One critical security issue: timing-attack-prone token comparison."}'
)

FEW_SHOT_EXAMPLES = (
    dedent(
        """\
        Example diff:
        --- file: app/auth.py ---
        @@ -10,3 +10,7 @@
         def verify(token: str) -> bool:
        +    if token == EXPECTED:
        +        return True
             return False

        Example output:
        """
    ).strip()
    + "\n"
    + _EXAMPLE_1_OUTPUT
    + "\n\n"
    + dedent(
        """\
        Example diff:
        --- file: util/math.py ---
        @@ -1,2 +1,2 @@
        -def add(a,b): return a+b
        +def add(a, b): return a + b

        Example output:
        {"findings":[],"summary":""}
        """
    ).strip()
)


def _format_piece(piece: FilePiece) -> str:
    parts = [f"--- file: {piece.filename} (status: {piece.status}) ---"]
    for h in piece.hunks:
        parts.append(h.header)
        parts.append(h.body)
    if piece.truncated:
        parts.append("[TRUNCATED: hunk body cut to fit context window]")
    return "\n".join(parts)


def build_user_prompt(
    chunk: Chunk, repo_full_name: str, pr_number: int, custom_rules: str | None
) -> str:
    body = "\n\n".join(_format_piece(p) for p in chunk.files)
    rules = (
        f"\n\nRepo-specific rules to apply:\n{custom_rules.strip()}"
        if custom_rules and custom_rules.strip()
        else ""
    )
    return dedent(
        f"""\
        Review this slice of pull request #{pr_number} on {repo_full_name}.

        {FEW_SHOT_EXAMPLES}

        Now the actual diff to review:{rules}

        {body}

        Return only the JSON object. No prose around it.
        """
    ).strip()


def validate_finding(item: dict) -> dict | None:
    """Coerce/validate a raw model finding. Returns None if it can't be repaired."""
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
    side = str(item.get("side", "RIGHT")).upper()
    if side not in ("LEFT", "RIGHT"):
        side = "RIGHT"
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
        "side": side,
        "severity": severity,
        "category": category,
        "message": str(message).strip(),
        "suggestion": suggestion,
        "confidence": confidence,
    }


SEVERITY_ORDER = {"nit": 0, "minor": 1, "medium": 1, "major": 2, "critical": 3}


def passes_severity_threshold(severity: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(threshold, 1)
