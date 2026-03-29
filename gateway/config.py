"""
config.py — Centralized Configuration Management
==================================================
Single source of truth for all HITL Gateway configuration. Loads from
environment variables with validated defaults, supporting local dev,
staging, and production deployment slots.

Usage
-----
    from config import settings
    print(settings.gateway_url)
    print(settings.sla_timeouts)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("hitl_gateway.config")


def _env(key: str, default: str = "") -> str:
    """Read an environment variable with a default."""
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    """Read an environment variable as int."""
    raw = os.getenv(key, "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            logger.warning("[CONFIG] Invalid int for %s: '%s', using default %d", key, raw, default)
    return default


def _env_bool(key: str, default: bool = False) -> bool:
    """Read an environment variable as bool."""
    raw = os.getenv(key, "").lower()
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    return default


def _env_list(key: str, default: str = "") -> List[str]:
    """Read a comma-separated environment variable as a list of strings."""
    raw = os.getenv(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class GatewaySettings:
    """Immutable configuration for the HITL Gateway."""

    # ── Environment ──────────────────────────────────────────────────────────
    environment: str = field(default_factory=lambda: _env("HITL_ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _env_bool("HITL_DEBUG", True))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())

    # ── Networking ───────────────────────────────────────────────────────────
    gateway_url: str = field(default_factory=lambda: _env("GATEWAY_URL", "http://localhost:7072/api"))
    dashboard_url: str = field(default_factory=lambda: _env("DASHBOARD_URL", "https://your-dashboard.azurewebsites.net"))
    agent_port: int = field(default_factory=lambda: _env_int("AGENT_PORT", 7071))

    # ── Webhooks ─────────────────────────────────────────────────────────────
    teams_webhook_url: str = field(default_factory=lambda: _env("TEAMS_WEBHOOK_URL"))
    slack_webhook_url: str = field(default_factory=lambda: _env("SLACK_WEBHOOK_URL"))
    escalation_webhook_url: str = field(default_factory=lambda: _env("ESCALATION_WEBHOOK_URL"))

    # ── Security ─────────────────────────────────────────────────────────────
    api_keys: List[str] = field(default_factory=lambda: _env_list("HITL_API_KEYS"))
    webhook_secret: str = field(default_factory=lambda: _env("HITL_WEBHOOK_SECRET"))
    enforce_https: bool = field(default_factory=lambda: _env_bool("HITL_ENFORCE_HTTPS", False))
    allowed_callback_domains: List[str] = field(
        default_factory=lambda: _env_list(
            "HITL_ALLOWED_CALLBACK_DOMAINS",
            "localhost,*.azurewebsites.net,*.azure-api.net"
        )
    )

    # ── Rate Limiting ────────────────────────────────────────────────────────
    rate_limit_window: int = field(default_factory=lambda: _env_int("HITL_RATE_LIMIT_WINDOW", 60))
    rate_limit_max: int = field(default_factory=lambda: _env_int("HITL_RATE_LIMIT_MAX", 30))

    # ── SLA Timeouts (seconds) ───────────────────────────────────────────────
    sla_critical: int = field(default_factory=lambda: _env_int("HITL_SLA_CRITICAL", 300))
    sla_high: int = field(default_factory=lambda: _env_int("HITL_SLA_HIGH", 900))
    sla_normal: int = field(default_factory=lambda: _env_int("HITL_SLA_NORMAL", 3600))
    sla_low: int = field(default_factory=lambda: _env_int("HITL_SLA_LOW", 86400))

    # ── Retry Policy ─────────────────────────────────────────────────────────
    retry_max_attempts: int = field(default_factory=lambda: _env_int("HITL_RETRY_MAX_ATTEMPTS", 3))
    retry_initial_interval_ms: int = field(default_factory=lambda: _env_int("HITL_RETRY_INITIAL_MS", 5000))

    # ── Observability ────────────────────────────────────────────────────────
    app_insights_connection_string: str = field(
        default_factory=lambda: _env("APPLICATIONINSIGHTS_CONNECTION_STRING")
    )
    enable_metrics: bool = field(default_factory=lambda: _env_bool("HITL_ENABLE_METRICS", True))

    # ── Cosmos DB (Phase 2 — persistent storage) ─────────────────────────────
    cosmos_connection_string: str = field(default_factory=lambda: _env("COSMOS_CONNECTION_STRING"))
    cosmos_database: str = field(default_factory=lambda: _env("COSMOS_DATABASE", "hitl_gateway"))

    # ── Redis (Phase 2 — distributed cache) ──────────────────────────────────
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL"))

    @property
    def is_production(self) -> bool:
        """True if running in production environment."""
        return self.environment.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        """True if running in local development."""
        return self.environment.lower() in ("development", "dev", "local")

    @property
    def sla_timeouts(self) -> Dict[str, int]:
        """Return SLA timeout map keyed by urgency level string."""
        return {
            "CRITICAL": self.sla_critical,
            "HIGH":     self.sla_high,
            "NORMAL":   self.sla_normal,
            "LOW":      self.sla_low,
        }

    @property
    def auth_enabled(self) -> bool:
        """True if API key authentication is configured."""
        return len(self.api_keys) > 0

    @property
    def webhook_verification_enabled(self) -> bool:
        """True if webhook HMAC verification is configured."""
        return bool(self.webhook_secret)

    @property
    def cosmos_enabled(self) -> bool:
        """True if Cosmos DB is configured."""
        return bool(self.cosmos_connection_string)

    @property
    def redis_enabled(self) -> bool:
        """True if Redis is configured."""
        return bool(self.redis_url)

    @property
    def escalation_url(self) -> str:
        """Escalation webhook, falling back to Slack webhook."""
        return self.escalation_webhook_url or self.slack_webhook_url

    def validate(self) -> List[str]:
        """
        Validate configuration and return a list of warnings.

        Production environments will have stricter requirements.
        """
        warnings = []

        if self.is_production:
            if not self.auth_enabled:
                warnings.append("CRITICAL: No API keys configured in production (set HITL_API_KEYS)")
            if not self.webhook_verification_enabled:
                warnings.append("HIGH: No webhook secret configured (set HITL_WEBHOOK_SECRET)")
            if not self.enforce_https:
                warnings.append("HIGH: HTTPS not enforced for callbacks (set HITL_ENFORCE_HTTPS=true)")
            if not self.app_insights_connection_string:
                warnings.append("MEDIUM: Application Insights not configured")
            if not self.cosmos_connection_string:
                warnings.append("MEDIUM: Cosmos DB not configured — audit trail is log-only")

        if self.rate_limit_max <= 0:
            warnings.append("LOW: Rate limiting effectively disabled (max=0)")

        return warnings

    def log_summary(self) -> None:
        """Log configuration summary at startup (masking secrets)."""
        logger.info("=" * 60)
        logger.info("HITL Gateway Configuration Summary")
        logger.info("=" * 60)
        logger.info("  Environment        : %s", self.environment)
        logger.info("  Debug              : %s", self.debug)
        logger.info("  Gateway URL        : %s", self.gateway_url)
        logger.info("  Dashboard URL      : %s", self.dashboard_url)
        logger.info("  Auth enabled       : %s", self.auth_enabled)
        logger.info("  Webhook verify     : %s", self.webhook_verification_enabled)
        logger.info("  HTTPS enforced     : %s", self.enforce_https)
        logger.info("  Rate limit         : %d req / %ds", self.rate_limit_max, self.rate_limit_window)
        logger.info("  Teams webhook      : %s", "configured" if self.teams_webhook_url else "mock")
        logger.info("  Slack webhook      : %s", "configured" if self.slack_webhook_url else "mock")
        logger.info("  App Insights       : %s", "configured" if self.app_insights_connection_string else "disabled")
        logger.info("  Cosmos DB          : %s", "configured" if self.cosmos_enabled else "disabled")
        logger.info("  Redis              : %s", "configured" if self.redis_enabled else "disabled")
        logger.info("=" * 60)

        warnings = self.validate()
        for w in warnings:
            logger.warning("[CONFIG] %s", w)


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

settings = GatewaySettings()
