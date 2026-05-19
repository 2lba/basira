from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.logging import get_logger

log = get_logger("basira.anthropic")


class AnthropicError(Exception):
    pass


@dataclass(frozen=True)
class ClaudeResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str | None


_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    s = get_settings()
    if not s.anthropic_api_key:
        raise AnthropicError("ANTHROPIC_API_KEY not configured")
    if _client is None:
        _client = AsyncAnthropic(api_key=s.anthropic_api_key)
    return _client


_RETRYABLE_EXCEPTIONS: tuple = ()
try:
    from anthropic import APIConnectionError, APIStatusError, RateLimitError

    _RETRYABLE_EXCEPTIONS = (APIConnectionError, RateLimitError, APIStatusError)
except ImportError:  # pragma: no cover
    _RETRYABLE_EXCEPTIONS = (Exception,)


async def call_claude(
    *,
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> ClaudeResponse:
    s = get_settings()
    chosen_model = model or s.claude_model
    chosen_max = max_tokens or s.claude_max_tokens
    chosen_temp = s.claude_temperature if temperature is None else temperature

    async def _do() -> ClaudeResponse:
        client = _get_client()
        msg = await client.messages.create(
            model=chosen_model,
            max_tokens=chosen_max,
            temperature=chosen_temp,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = ""
        for block in msg.content:
            if getattr(block, "type", "") == "text":
                text += block.text
        usage = getattr(msg, "usage", None)
        return ClaudeResponse(
            text=text,
            input_tokens=int(getattr(usage, "input_tokens", 0)) if usage else 0,
            output_tokens=int(getattr(usage, "output_tokens", 0)) if usage else 0,
            model=str(getattr(msg, "model", chosen_model)),
            stop_reason=getattr(msg, "stop_reason", None),
        )

    last: Exception | None = None
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=False,
    ):
        with attempt:
            try:
                return await _do()
            except Exception as e:
                last = e
                raise
    if last is not None:
        raise AnthropicError(f"claude call failed: {last.__class__.__name__}") from last
    raise AnthropicError("claude call failed: unknown")


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Approximate cost; pricing is intentionally a rough placeholder. Sonnet-4-5 is
    roughly $3/Mtok input, $15/Mtok output (as of 2026). Tracked to surface usage,
    not to bill anyone."""
    pricing: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-5": (3.0, 15.0),
        "claude-opus-4-5": (15.0, 75.0),
        "claude-haiku-4-5": (1.0, 5.0),
    }
    in_rate, out_rate = pricing.get(model, (3.0, 15.0))
    return round((input_tokens * in_rate + output_tokens * out_rate) / 1_000_000, 6)


def parse_json_strict(text: str) -> Any:
    """Pull JSON out of a Claude response. Tries direct json.loads, then strips
    common markdown fences, then locates first balanced object/array."""
    import json

    s = text.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    if s.startswith("```"):
        s = s.strip("`")
        # remove optional language label
        first_nl = s.find("\n")
        if first_nl != -1:
            head = s[:first_nl].strip().lower()
            if head and head.isalpha():
                s = s[first_nl + 1 :]
        s = s.rstrip("`").strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

    # prefer objects over arrays since our schema is an object
    for opener, closer in (("{", "}"), ("[", "]")):
        start = s.find(opener)
        end = s.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise AnthropicError("could not parse JSON from claude response")
