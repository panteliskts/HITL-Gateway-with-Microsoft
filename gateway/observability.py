"""
observability.py — Enterprise Observability Layer
===================================================
Provides structured logging, custom metrics, distributed tracing helpers,
and health check logic for the HITL Gateway.

In production, this integrates with Azure Monitor / Application Insights
via OpenTelemetry. In development, metrics are collected in-memory and
exposed via the /api/metrics endpoint.

Architecture
------------
  ┌──────────────────────────────────────────────┐
  │  Application Code                            │
  │    ├─ metrics.record_request(...)            │
  │    ├─ metrics.record_decision(...)           │
  │    └─ metrics.record_latency(...)            │
  └──────────────────────────────────────────────┘
                    ↓
  ┌──────────────────────────────────────────────┐
  │  MetricsCollector (in-memory aggregation)    │
  │    ├─ counters: { name: value }              │
  │    ├─ histograms: { name: [values] }         │
  │    └─ gauges: { name: value }                │
  └──────────────────────────────────────────────┘
                    ↓
  ┌──────────────────────────────────────────────┐
  │  Azure Monitor / App Insights                │
  │    (via OpenTelemetry when configured)       │
  └──────────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hitl_gateway.observability")


# ============================================================================
# Metrics Collector
# ============================================================================

class MetricsCollector:
    """
    In-memory metrics collector with support for counters, histograms,
    and gauges. Thread-safe enough for single-process Azure Functions.

    In production, these metrics are also emitted to Azure Monitor via
    OpenTelemetry (when APPLICATIONINSIGHTS_CONNECTION_STRING is set).
    """

    def __init__(self) -> None:
        self._counters: Dict[str, int] = defaultdict(int)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._gauges: Dict[str, float] = {}
        self._labels: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self._start_time = time.time()

    # ── Counters ─────────────────────────────────────────────────────────────

    def increment(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""
        self._counters[name] += value
        if labels:
            for lk, lv in labels.items():
                self._labels[name][lk][lv] += value

    # ── Histograms ───────────────────────────────────────────────────────────

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation (e.g., latency)."""
        self._histograms[name].append(value)
        if labels:
            for lk, lv in labels.items():
                self._labels[name][lk][lv] += 1

    # ── Gauges ───────────────────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge to a specific value."""
        self._gauges[name] = value

    # ── Query ────────────────────────────────────────────────────────────────

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Return histogram statistics (count, sum, avg, p50, p95, p99)."""
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        return {
            "count": count,
            "sum":   round(sum(sorted_vals), 3),
            "avg":   round(sum(sorted_vals) / count, 3),
            "min":   round(sorted_vals[0], 3),
            "max":   round(sorted_vals[-1], 3),
            "p50":   round(sorted_vals[int(count * 0.50)], 3),
            "p95":   round(sorted_vals[min(int(count * 0.95), count - 1)], 3),
            "p99":   round(sorted_vals[min(int(count * 0.99), count - 1)], 3),
        }

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0)

    def get_label_breakdown(self, metric_name: str) -> Dict[str, Dict[str, int]]:
        """Return label breakdown for a metric."""
        return dict(self._labels.get(metric_name, {}))

    def snapshot(self) -> Dict[str, Any]:
        """Return a full snapshot of all metrics."""
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "counters": dict(self._counters),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms
            },
            "gauges": dict(self._gauges),
        }


# Module-level singleton
metrics = MetricsCollector()


# ============================================================================
# HITL-specific metric recording helpers
# ============================================================================

def record_request_received(agent_id: str, urgency: str) -> None:
    """Record an incoming HITL request."""
    metrics.increment("hitl.requests.total", labels={"urgency": urgency, "agent_id": agent_id})
    metrics.increment(f"hitl.requests.by_urgency.{urgency}")
    logger.debug("[METRICS] Request received: agent=%s urgency=%s", agent_id, urgency)


def record_decision(status: str, urgency: str, duration_seconds: float) -> None:
    """Record a HITL decision (approval, rejection, or escalation)."""
    metrics.increment("hitl.decisions.total", labels={"status": status, "urgency": urgency})
    metrics.increment(f"hitl.decisions.by_status.{status}")
    metrics.observe("hitl.decision.duration_seconds", duration_seconds, labels={"status": status, "urgency": urgency})

    if status == "ESCALATED":
        metrics.increment("hitl.sla.timeouts.total", labels={"urgency": urgency})

    logger.debug("[METRICS] Decision: status=%s urgency=%s duration=%.2fs", status, urgency, duration_seconds)


def record_webhook_delivery(target: str, success: bool, latency_ms: float) -> None:
    """Record a webhook delivery attempt."""
    status = "success" if success else "failure"
    metrics.increment(f"hitl.webhook.{target}.{status}")
    metrics.observe(f"hitl.webhook.{target}.latency_ms", latency_ms)


def record_callback_delivery(success: bool, latency_ms: float) -> None:
    """Record an agent callback delivery attempt."""
    status = "success" if success else "failure"
    metrics.increment(f"hitl.callback.{status}")
    metrics.observe("hitl.callback.latency_ms", latency_ms)


def record_auth_result(success: bool, method: str = "api_key") -> None:
    """Record an authentication attempt."""
    result = "success" if success else "failure"
    metrics.increment(f"hitl.auth.{result}", labels={"method": method})


def record_rate_limit_hit(agent_id: str) -> None:
    """Record a rate limit rejection."""
    metrics.increment("hitl.rate_limit.rejected", labels={"agent_id": agent_id})


# ============================================================================
# Health Check
# ============================================================================

class HealthChecker:
    """
    Deep health checker for Azure Traffic Manager and load balancer probes.

    Checks:
    - Gateway process is alive
    - Durable Functions storage is accessible (via env var presence)
    - External dependencies (configurable)
    """

    def __init__(self) -> None:
        self._start_time = datetime.now(timezone.utc)

    async def check(self) -> Dict[str, Any]:
        """Run all health checks and return aggregated result."""
        checks: Dict[str, Any] = {}

        # Process health
        checks["process"] = {
            "status": "healthy",
            "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
        }

        # Storage health (Durable Functions requires Azure Storage)
        storage_configured = bool(os.getenv("AzureWebJobsStorage"))
        checks["durable_storage"] = {
            "status": "healthy" if storage_configured else "degraded",
            "configured": storage_configured,
        }

        # Cosmos DB health (optional)
        cosmos_configured = bool(os.getenv("COSMOS_CONNECTION_STRING"))
        checks["cosmos_db"] = {
            "status": "healthy" if cosmos_configured else "not_configured",
            "configured": cosmos_configured,
        }

        # App Insights health
        insights_configured = bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
        checks["app_insights"] = {
            "status": "healthy" if insights_configured else "not_configured",
            "configured": insights_configured,
        }

        # Aggregate
        all_critical_healthy = all(
            checks[k]["status"] == "healthy"
            for k in ["process", "durable_storage"]
        )

        return {
            "status": "healthy" if all_critical_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": os.getenv("HITL_VERSION", "1.0.0"),
            "environment": os.getenv("HITL_ENVIRONMENT", "development"),
            "checks": checks,
        }


# Module-level singleton
health_checker = HealthChecker()


# ============================================================================
# Structured Audit Logger
# ============================================================================

class AuditLogger:
    """
    Structured audit logger that emits events in a consistent format
    for Azure Monitor / App Insights ingestion.

    Every event is tagged with [AUDIT] for easy KQL filtering:
        traces | where message contains "[AUDIT]"
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("hitl_gateway.audit")
        self._events: List[Dict[str, Any]] = []  # In-memory buffer for API exposure

    def log(
        self,
        instance_id: str,
        event: str,
        agent_id: str = "unknown",
        urgency: str = "UNKNOWN",
        reviewer_id: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Emit a structured audit event.

        Returns the audit record dict (for persistence to Cosmos DB).
        """
        record = {
            "instance_id": instance_id,
            "event": event,
            "agent_id": agent_id,
            "urgency": urgency,
            "reviewer_id": reviewer_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        # Structured log line
        log_line = (
            f"[AUDIT] {instance_id} — {event} | "
            f"agent={agent_id} urgency={urgency}"
        )
        if reviewer_id:
            log_line += f" reviewer={reviewer_id}"
        if reason:
            log_line += f" reason={reason}"

        # Use WARNING for escalations, INFO for everything else
        if event == "ESCALATED":
            self._logger.warning(log_line)
        else:
            self._logger.info(log_line)

        # Buffer for API exposure (keep last 1000 events)
        self._events.append(record)
        if len(self._events) > 1000:
            self._events = self._events[-1000:]

        return record

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit events (newest first)."""
        return list(reversed(self._events[-limit:]))

    def get_events_for_instance(self, instance_id: str) -> List[Dict[str, Any]]:
        """Return all audit events for a specific instance."""
        return [e for e in self._events if e["instance_id"] == instance_id]


# Module-level singleton
audit_logger = AuditLogger()
