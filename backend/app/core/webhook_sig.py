import hashlib
import hmac

WEBHOOK_BODY_MAX_BYTES = 10 * 1024 * 1024  # 10MB


class WebhookSigError(Exception):
    pass


def verify_github_signature(body: bytes, secret: str, header_value: str | None) -> None:
    if not secret:
        raise WebhookSigError("webhook secret not configured")
    if not header_value:
        raise WebhookSigError("missing X-Hub-Signature-256")
    if not header_value.startswith("sha256="):
        raise WebhookSigError("unexpected signature scheme")
    if len(body) > WEBHOOK_BODY_MAX_BYTES:
        raise WebhookSigError("body too large")

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = header_value[len("sha256=") :]
    if not hmac.compare_digest(expected, provided):
        raise WebhookSigError("signature mismatch")


def compute_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
