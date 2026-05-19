import pytest

from app.core.webhook_sig import (
    WebhookSigError,
    compute_signature,
    verify_github_signature,
)


def test_should_accept_when_signature_matches():
    body = b'{"hello":"world"}'
    secret = "shh"
    sig = compute_signature(body, secret)
    verify_github_signature(body, secret, sig)


def test_should_reject_when_signature_mismatch():
    with pytest.raises(WebhookSigError, match="mismatch"):
        verify_github_signature(b"x", "s", "sha256=0000")


def test_should_reject_when_secret_missing():
    with pytest.raises(WebhookSigError, match="secret"):
        verify_github_signature(b"x", "", "sha256=00")


def test_should_reject_when_header_missing():
    with pytest.raises(WebhookSigError, match="missing"):
        verify_github_signature(b"x", "s", None)


def test_should_reject_when_scheme_unexpected():
    with pytest.raises(WebhookSigError, match="scheme"):
        verify_github_signature(b"x", "s", "sha1=00")


def test_should_reject_when_body_too_large():
    with pytest.raises(WebhookSigError, match="too large"):
        verify_github_signature(b"a" * (10 * 1024 * 1024 + 1), "s", "sha256=00")
