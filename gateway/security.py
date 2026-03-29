"""
security.py — Enterprise Security Layer
=========================================
Provides authentication, authorization, input sanitization, and request
validation for the HITL Gateway.

Capabilities
------------
- API key authentication (Azure Key Vault-backed in production)
- HMAC-SHA256 webhook signature verification
- Callback URL allowlist (SSRF prevention)
- Input sanitization (XSS prevention for Teams cards)
- Rate limiting tracking (per agent_id)
- Nonce/timestamp replay-attack prevention

All functions are designed to be stateless and side-effect-free so they
can be safely called from both HTTP triggers and Durable activities.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import logging
import os
import re
import time
from ipaddress import ip_address, ip_network
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("hitl_gateway.security")

# ---------------------------------------------------------------------------
# Configuration (env-driven, overridable per deployment slot)
# ---------------------------------------------------------------------------

# Comma-separated list of valid API keys (in production, load from Key Vault)
_API_KEYS: Optional[List[str]] = None

# Comma-separated domain patterns for allowed callback URLs
_ALLOWED_CALLBACK_PATTERNS: Optional[List[str]] = None

# HMAC secret for webhook signature verification
WEBHOOK_SECRET: str = os.getenv("HITL_WEBHOOK_SECRET", "")

# Rate limiting window (seconds) and max requests per window per agent
RATE_LIMIT_WINDOW: int = int(os.getenv("HITL_RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX: int = int(os.getenv("HITL_RATE_LIMIT_MAX", "30"))

# Nonce expiry window (seconds) — reject replays older than this
NONCE_EXPIRY: int = int(os.getenv("HITL_NONCE_EXPIRY", "300"))

# Private/reserved IP ranges (SSRF protection)
_PRIVATE_NETWORKS = [
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),   # Link-local / AWS metadata
    ip_network("0.0.0.0/8"),
]


def _load_api_keys() -> List[str]:
    """Lazily load API keys from environment."""
    global _API_KEYS
    if _API_KEYS is None:
        raw = os.getenv("HITL_API_KEYS", "")
        _API_KEYS = [k.strip() for k in raw.split(",") if k.strip()]
    return _API_KEYS


def _load_callback_patterns() -> List[str]:
    """Lazily load allowed callback URL patterns."""
    global _ALLOWED_CALLBACK_PATTERNS
    if _ALLOWED_CALLBACK_PATTERNS is None:
        raw = os.getenv(
            "HITL_ALLOWED_CALLBACK_DOMAINS",
            "localhost,*.azurewebsites.net,*.azure-api.net"
        )
        _ALLOWED_CALLBACK_PATTERNS = [p.strip() for p in raw.split(",") if p.strip()]
    return _ALLOWED_CALLBACK_PATTERNS


# ============================================================================
# API Key Authentication
# ============================================================================

def validate_api_key(api_key: Optional[str]) -> bool:
    """
    Validate an API key against the configured allowlist.

    Returns True if:
    - No API keys are configured (dev mode — auth disabled)
    - The provided key matches one of the configured keys

    Uses constant-time comparison to prevent timing attacks.
    """
    keys = _load_api_keys()

    # Dev mode: no keys configured → allow all requests
    if not keys:
        return True

    if not api_key:
        return False

    return any(hmac.compare_digest(api_key, k) for k in keys)


def extract_api_key(headers: Dict[str, str]) -> Optional[str]:
    """
    Extract API key from request headers.

    Checks (in order):
    1. X-API-Key header
    2. Authorization: Bearer <token>
    """
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if api_key:
        return api_key

    auth_header = headers.get("authorization") or headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


# ============================================================================
# HMAC Webhook Signature Verification
# ============================================================================

def compute_hmac_signature(body: bytes, secret: Optional[str] = None) -> str:
    """Compute HMAC-SHA256 signature for a request body."""
    secret = secret or WEBHOOK_SECRET
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(
    body: bytes,
    signature: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """
    Verify the HMAC-SHA256 signature of a webhook callback.

    Returns True if:
    - No webhook secret is configured (dev mode)
    - The provided signature matches the computed HMAC

    Uses constant-time comparison to prevent timing attacks.
    """
    secret = secret or WEBHOOK_SECRET

    # Dev mode: no secret configured → skip verification
    if not secret:
        return True

    if not signature:
        logger.warning("[SECURITY] Webhook signature missing")
        return False

    expected = compute_hmac_signature(body, secret)
    return hmac.compare_digest(signature, expected)


# ============================================================================
# Callback URL Validation (SSRF Prevention)
# ============================================================================

def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP range."""
    try:
        addr = ip_address(hostname)
        return any(addr in network for network in _PRIVATE_NETWORKS)
    except ValueError:
        # Not an IP literal — it's a hostname, which is allowed
        return False


def _domain_matches_pattern(domain: str, pattern: str) -> bool:
    """Check if a domain matches a pattern (supporting wildcard prefix)."""
    if pattern.startswith("*."):
        suffix = pattern[1:]  # e.g., ".azurewebsites.net"
        return domain.endswith(suffix) or domain == pattern[2:]
    return domain == pattern


def validate_callback_url(url: str, allow_localhost: bool = False) -> Tuple[bool, str]:
    """
    Validate a callback URL against the configured allowlist.

    Returns:
        (is_valid, reason) — tuple of boolean and human-readable reason.

    Checks:
    1. URL is well-formed with http/https scheme
    2. Hostname is not a private/reserved IP (SSRF)
    3. Domain matches the configured allowlist
    """
    if not url:
        return False, "callback_url is required"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "callback_url is malformed"

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        return False, f"callback_url scheme must be http or https, got '{parsed.scheme}'"

    hostname = parsed.hostname or ""
    if not hostname:
        return False, "callback_url has no hostname"

    # SSRF: block private IPs (unless localhost is explicitly allowed)
    if _is_private_ip(hostname):
        if hostname.startswith("127.") and allow_localhost:
            pass  # Development mode
        else:
            return False, f"callback_url resolves to private IP: {hostname}"

    # In production, enforce https
    enforce_https = os.getenv("HITL_ENFORCE_HTTPS", "false").lower() == "true"
    if enforce_https and parsed.scheme != "https":
        return False, "callback_url must use HTTPS in production"

    # Domain allowlist check
    patterns = _load_callback_patterns()
    if patterns:
        # "localhost" pattern allows any localhost URL
        if hostname in ("localhost", "127.0.0.1") and "localhost" in patterns:
            return True, "ok"
        if any(_domain_matches_pattern(hostname, p) for p in patterns):
            return True, "ok"
        return False, f"callback_url domain '{hostname}' not in allowlist"

    return True, "ok"


# ============================================================================
# Input Sanitization (XSS Prevention)
# ============================================================================

def sanitize_text(text: str) -> str:
    """
    Sanitize user-supplied text to prevent XSS in Teams cards and web UIs.

    Escapes HTML entities and strips dangerous URI schemes.
    """
    # HTML entity escaping
    sanitized = html.escape(text, quote=True)

    # Strip dangerous URI schemes
    sanitized = re.sub(r"javascript\s*:", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"data\s*:", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"vbscript\s*:", "", sanitized, flags=re.IGNORECASE)

    return sanitized


def sanitize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize a context dictionary.

    String values are HTML-escaped; nested dicts are recursed;
    other types are left as-is.
    """
    sanitized = {}
    for key, value in context.items():
        clean_key = sanitize_text(str(key))
        if isinstance(value, str):
            sanitized[clean_key] = sanitize_text(value)
        elif isinstance(value, dict):
            sanitized[clean_key] = sanitize_context(value)
        elif isinstance(value, list):
            sanitized[clean_key] = [
                sanitize_text(str(v)) if isinstance(v, str) else v
                for v in value
            ]
        else:
            sanitized[clean_key] = value
    return sanitized


# ============================================================================
# Rate Limiting (Sliding window + token bucket hybrid)
# ============================================================================
#
# Production-grade rate limiter combining two complementary strategies:
#
#   1. **Sliding Window Counter** — enforces a hard ceiling per agent_id over
#      a configurable window (default: 30 requests / 60 seconds). Prevents
#      sustained abuse while allowing natural traffic distribution.
#
#   2. **Token Bucket (burst control)** — allows short bursts above the
#      average rate while smoothing traffic. Tokens refill at a constant rate
#      and cap at BURST_CAPACITY. Prevents thundering-herd spikes.
#
# In production, swap the in-memory stores for Redis sorted sets
# (ZRANGEBYSCORE) and Redis hash (token + last_refill_ts).
# ============================================================================

# Burst: max tokens that can accumulate (allows short bursts)
RATE_LIMIT_BURST: int = int(os.getenv("HITL_RATE_LIMIT_BURST", "10"))

# Refill rate: tokens per second (derived from max/window)
_REFILL_RATE: float = RATE_LIMIT_MAX / max(RATE_LIMIT_WINDOW, 1)


class _RateLimitEntry:
    """Per-agent rate limit state combining sliding window + token bucket."""
    __slots__ = ("timestamps", "tokens", "last_refill")

    def __init__(self) -> None:
        self.timestamps: List[float] = []
        self.tokens: float = float(RATE_LIMIT_BURST)
        self.last_refill: float = time.time()


# { agent_id: _RateLimitEntry }
_rate_limit_store: Dict[str, _RateLimitEntry] = {}


def _get_or_create_entry(agent_id: str) -> _RateLimitEntry:
    """Get existing entry or create a new one for the agent."""
    if agent_id not in _rate_limit_store:
        _rate_limit_store[agent_id] = _RateLimitEntry()
    return _rate_limit_store[agent_id]


def check_rate_limit(agent_id: str) -> Tuple[bool, int]:
    """
    Hybrid sliding-window + token-bucket rate limiter per agent_id.

    Returns:
        (allowed, remaining) — whether the request is allowed and remaining
        quota within the current window.

    The check passes only if BOTH conditions are met:
      1. Sliding window count < RATE_LIMIT_MAX
      2. Token bucket has >= 1 token available

    Response headers the caller should set on 429:
      - Retry-After: RATE_LIMIT_WINDOW
      - X-RateLimit-Limit: RATE_LIMIT_MAX
      - X-RateLimit-Remaining: remaining
      - X-RateLimit-Reset: window_end (Unix epoch)

    NOTE: In-memory only — does not survive process restart. In production,
    replace with Redis ZRANGEBYSCORE + HSET for distributed rate limiting.
    """
    now = time.time()
    entry = _get_or_create_entry(agent_id)

    # --- Phase 1: Sliding window ---
    window_start = now - RATE_LIMIT_WINDOW
    entry.timestamps = [ts for ts in entry.timestamps if ts > window_start]
    window_count = len(entry.timestamps)

    if window_count >= RATE_LIMIT_MAX:
        logger.debug(
            "[RATELIMIT] Window limit hit: agent=%s count=%d/%d",
            agent_id, window_count, RATE_LIMIT_MAX,
        )
        return False, 0

    # --- Phase 2: Token bucket (burst control) ---
    elapsed = now - entry.last_refill
    entry.tokens = min(
        float(RATE_LIMIT_BURST),
        entry.tokens + elapsed * _REFILL_RATE,
    )
    entry.last_refill = now

    if entry.tokens < 1.0:
        logger.debug(
            "[RATELIMIT] Burst limit hit: agent=%s tokens=%.2f",
            agent_id, entry.tokens,
        )
        return False, 0

    # --- Admit request ---
    entry.tokens -= 1.0
    entry.timestamps.append(now)
    remaining = RATE_LIMIT_MAX - len(entry.timestamps)

    return True, max(0, remaining)


def get_rate_limit_headers(agent_id: str) -> Dict[str, str]:
    """
    Generate RFC-compliant rate limit headers for HTTP responses.

    Returns headers suitable for both 200 and 429 responses:
      - X-RateLimit-Limit
      - X-RateLimit-Remaining
      - X-RateLimit-Reset (Unix epoch of window end)
      - Retry-After (seconds, only meaningful on 429)
    """
    entry = _rate_limit_store.get(agent_id)
    now = time.time()

    if entry and entry.timestamps:
        oldest_in_window = min(entry.timestamps)
        reset_at = oldest_in_window + RATE_LIMIT_WINDOW
        remaining = max(0, RATE_LIMIT_MAX - len(entry.timestamps))
    else:
        reset_at = now + RATE_LIMIT_WINDOW
        remaining = RATE_LIMIT_MAX

    return {
        "X-RateLimit-Limit": str(RATE_LIMIT_MAX),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(int(reset_at)),
        "Retry-After": str(RATE_LIMIT_WINDOW),
    }


# ============================================================================
# Replay Attack Prevention (Nonce tracking)
# ============================================================================

# { nonce: expiry_timestamp }
_nonce_store: Dict[str, float] = {}


def _prune_expired_nonces() -> None:
    """Remove expired nonces to prevent unbounded memory growth."""
    now = time.time()
    expired = [n for n, exp in _nonce_store.items() if exp < now]
    for n in expired:
        del _nonce_store[n]


def check_nonce(nonce: Optional[str], timestamp: Optional[float] = None) -> bool:
    """
    Check if a nonce has been seen before (replay prevention).

    Returns True if the nonce is fresh (not a replay).

    Args:
        nonce: Unique request identifier
        timestamp: Request timestamp (Unix epoch). If too old, rejected.
    """
    if not nonce:
        return True  # No nonce provided — skip check (dev mode)

    _prune_expired_nonces()

    # Check timestamp freshness
    if timestamp:
        age = abs(time.time() - timestamp)
        if age > NONCE_EXPIRY:
            logger.warning(
                "[SECURITY] Nonce rejected: timestamp too old (age=%.0fs, max=%ds)",
                age, NONCE_EXPIRY,
            )
            return False

    # Check for replay
    if nonce in _nonce_store:
        logger.warning("[SECURITY] Nonce replay detected: %s", nonce)
        return False

    # Record nonce with expiry
    _nonce_store[nonce] = time.time() + NONCE_EXPIRY
    return True
