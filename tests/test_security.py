"""
test_security.py — Unit tests for the security module
=======================================================
Covers authentication, HMAC verification, SSRF protection,
input sanitization, rate limiting, and replay prevention.
"""
import os
import time
from unittest.mock import patch

import pytest

from gateway.security import (
    _domain_matches_pattern,
    _is_private_ip,
    check_nonce,
    check_rate_limit,
    compute_hmac_signature,
    extract_api_key,
    sanitize_context,
    sanitize_text,
    validate_api_key,
    validate_callback_url,
    verify_webhook_signature,
    _rate_limit_store,
    _nonce_store,
)


# ============================================================================
# API Key Authentication
# ============================================================================

class TestAPIKeyAuth:
    def test_no_keys_configured_allows_all(self):
        """Dev mode: no keys → everything passes."""
        with patch.dict(os.environ, {"HITL_API_KEYS": ""}, clear=False):
            # Force reload
            import gateway.security as security
            assert validate_api_key(None) is True

    def test_valid_key_passes(self):
        with patch.dict(os.environ, {"HITL_API_KEYS": "key-one,key-two"}, clear=False):
            import gateway.security as security
            security._API_KEYS = None
            assert validate_api_key("key-one") is True
            assert validate_api_key("key-two") is True

    def test_invalid_key_rejected(self):
        with patch.dict(os.environ, {"HITL_API_KEYS": "valid-key"}, clear=False):
            import gateway.security as security
            security._API_KEYS = None
            assert validate_api_key("wrong-key") is False
            assert validate_api_key("") is False
            assert validate_api_key(None) is False

    def test_extract_from_x_api_key_header(self):
        assert extract_api_key({"X-API-Key": "my-key"}) == "my-key"
        assert extract_api_key({"x-api-key": "my-key"}) == "my-key"

    def test_extract_from_bearer_token(self):
        assert extract_api_key({"Authorization": "Bearer tok123"}) == "tok123"
        assert extract_api_key({"authorization": "Bearer tok123"}) == "tok123"

    def test_extract_prefers_x_api_key(self):
        headers = {"X-API-Key": "key1", "Authorization": "Bearer key2"}
        assert extract_api_key(headers) == "key1"

    def test_extract_returns_none_if_missing(self):
        assert extract_api_key({}) is None
        assert extract_api_key({"Content-Type": "application/json"}) is None


# ============================================================================
# HMAC Webhook Verification
# ============================================================================

class TestHMACVerification:
    def test_no_secret_skips_verification(self):
        """Dev mode: no secret → always passes."""
        assert verify_webhook_signature(b"body", None, secret="") is True

    def test_valid_signature_passes(self):
        secret = "test-secret-123"
        body = b'{"status":"APPROVED"}'
        sig = compute_hmac_signature(body, secret)
        assert verify_webhook_signature(body, sig, secret) is True

    def test_invalid_signature_fails(self):
        secret = "test-secret-123"
        body = b'{"status":"APPROVED"}'
        assert verify_webhook_signature(body, "bad-signature", secret) is False

    def test_missing_signature_fails(self):
        assert verify_webhook_signature(b"body", None, secret="my-secret") is False

    def test_tampered_body_fails(self):
        secret = "test-secret"
        body = b'{"status":"APPROVED"}'
        sig = compute_hmac_signature(body, secret)
        tampered = b'{"status":"REJECTED"}'
        assert verify_webhook_signature(tampered, sig, secret) is False


# ============================================================================
# SSRF Prevention — Callback URL Validation
# ============================================================================

class TestCallbackURLValidation:
    def setup_method(self):
        """Reset callback pattern cache before each test."""
        import gateway.security as security
        security._ALLOWED_CALLBACK_PATTERNS = None

    def test_valid_azure_url(self):
        ok, _ = validate_callback_url("https://myapp.azurewebsites.net/hook")
        assert ok is True

    def test_valid_custom_domain(self):
        with patch.dict(os.environ, {"HITL_ALLOWED_CALLBACK_DOMAINS": "*.mycompany.com"}, clear=False):
            import gateway.security as security
            security._ALLOWED_CALLBACK_PATTERNS = None
            ok, _ = validate_callback_url("https://agent.mycompany.com/resume")
            assert ok is True

    def test_localhost_allowed_in_dev(self):
        ok, _ = validate_callback_url("http://localhost:7071/resume", allow_localhost=True)
        assert ok is True

    def test_localhost_blocked_in_production(self):
        ok, _ = validate_callback_url("http://127.0.0.1:7071/resume", allow_localhost=False)
        assert ok is False  # Private IP blocked when allow_localhost=False

    def test_private_ip_blocked(self):
        ok, reason = validate_callback_url("http://169.254.169.254/latest/meta-data")
        assert ok is False
        assert "private IP" in reason

    def test_empty_url_rejected(self):
        ok, _ = validate_callback_url("")
        assert ok is False

    def test_ftp_scheme_rejected(self):
        ok, reason = validate_callback_url("ftp://bad.com/hook")
        assert ok is False
        assert "scheme" in reason

    def test_no_hostname_rejected(self):
        ok, _ = validate_callback_url("http://")
        assert ok is False


class TestPrivateIPDetection:
    def test_loopback(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_private_10(self):
        assert _is_private_ip("10.255.0.1") is True

    def test_private_172(self):
        assert _is_private_ip("172.16.0.1") is True

    def test_private_192(self):
        assert _is_private_ip("192.168.1.1") is True

    def test_link_local(self):
        assert _is_private_ip("169.254.169.254") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_hostname_not_flagged(self):
        assert _is_private_ip("example.com") is False


class TestDomainPatternMatching:
    def test_exact_match(self):
        assert _domain_matches_pattern("example.com", "example.com") is True

    def test_wildcard_suffix(self):
        assert _domain_matches_pattern("app.azurewebsites.net", "*.azurewebsites.net") is True

    def test_wildcard_no_match(self):
        assert _domain_matches_pattern("evil.com", "*.azurewebsites.net") is False

    def test_wildcard_apex(self):
        assert _domain_matches_pattern("azurewebsites.net", "*.azurewebsites.net") is True


# ============================================================================
# Input Sanitization
# ============================================================================

class TestSanitization:
    def test_html_escaping(self):
        assert sanitize_text("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

    def test_javascript_protocol_stripped(self):
        assert "javascript" not in sanitize_text("javascript:alert(1)")

    def test_data_protocol_stripped(self):
        assert "data:" not in sanitize_text("data:text/html,<h1>evil</h1>")

    def test_normal_text_unchanged(self):
        text = "Isolate host 10.0.5.42 — anomalous lateral movement detected."
        assert sanitize_text(text) == text

    def test_context_sanitization(self):
        ctx = {
            "safe_key": "safe_value",
            "<script>": "bad_key",
            "normal": "<img onerror=alert(1)>",
        }
        sanitized = sanitize_context(ctx)
        assert "<script>" not in str(sanitized)
        assert "onerror" not in str(sanitized) or "&" in sanitized.get("normal", "")

    def test_nested_context(self):
        ctx = {"outer": {"inner": "<script>alert(1)</script>"}}
        sanitized = sanitize_context(ctx)
        assert "<script>" not in sanitized["outer"]["inner"]


# ============================================================================
# Rate Limiting
# ============================================================================

class TestRateLimiting:
    def setup_method(self):
        """Clear rate limit state before each test."""
        _rate_limit_store.clear()

    def test_first_request_allowed(self):
        allowed, remaining = check_rate_limit("test-agent")
        assert allowed is True
        assert remaining >= 0

    def test_rate_limit_enforced(self):
        # Exhaust the rate limit
        with patch("gateway.security.RATE_LIMIT_MAX", 3):
            check_rate_limit("agent-a")
            check_rate_limit("agent-a")
            check_rate_limit("agent-a")
            allowed, remaining = check_rate_limit("agent-a")
            assert allowed is False
            assert remaining == 0

    def test_different_agents_independent(self):
        with patch("gateway.security.RATE_LIMIT_MAX", 2):
            check_rate_limit("agent-a")
            check_rate_limit("agent-a")
            # agent-a is exhausted
            allowed_a, _ = check_rate_limit("agent-a")
            assert allowed_a is False

            # agent-b is fresh
            allowed_b, _ = check_rate_limit("agent-b")
            assert allowed_b is True


# ============================================================================
# Replay Prevention
# ============================================================================

class TestReplayPrevention:
    def setup_method(self):
        """Clear nonce store before each test."""
        _nonce_store.clear()

    def test_no_nonce_passes(self):
        """Dev mode: no nonce → skip check."""
        assert check_nonce(None) is True

    def test_fresh_nonce_passes(self):
        assert check_nonce("nonce-abc") is True

    def test_duplicate_nonce_fails(self):
        check_nonce("nonce-123")
        assert check_nonce("nonce-123") is False

    def test_old_timestamp_rejected(self):
        old_time = time.time() - 600  # 10 minutes ago
        with patch("gateway.security.NONCE_EXPIRY", 300):
            assert check_nonce("nonce-old", timestamp=old_time) is False

    def test_fresh_timestamp_passes(self):
        assert check_nonce("nonce-fresh", timestamp=time.time()) is True
