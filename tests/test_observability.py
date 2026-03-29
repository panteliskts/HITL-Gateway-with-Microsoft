"""
test_observability.py — Unit tests for the observability module
=================================================================
Covers metrics collection, audit logging, and health checks.
"""
import pytest

from gateway.observability import (
    MetricsCollector,
    AuditLogger,
    record_request_received,
    record_decision,
    metrics,
)


# ============================================================================
# MetricsCollector
# ============================================================================

class TestMetricsCollector:
    def setup_method(self):
        self.mc = MetricsCollector()

    def test_counter_increment(self):
        self.mc.increment("requests.total")
        self.mc.increment("requests.total")
        assert self.mc.get_counter("requests.total") == 2

    def test_counter_with_value(self):
        self.mc.increment("errors", value=5)
        assert self.mc.get_counter("errors") == 5

    def test_counter_with_labels(self):
        self.mc.increment("req", labels={"urgency": "CRITICAL"})
        self.mc.increment("req", labels={"urgency": "CRITICAL"})
        self.mc.increment("req", labels={"urgency": "LOW"})

        breakdown = self.mc.get_label_breakdown("req")
        assert breakdown["urgency"]["CRITICAL"] == 2
        assert breakdown["urgency"]["LOW"] == 1

    def test_histogram_observation(self):
        self.mc.observe("latency", 100.0)
        self.mc.observe("latency", 200.0)
        self.mc.observe("latency", 300.0)

        stats = self.mc.get_histogram_stats("latency")
        assert stats["count"] == 3
        assert stats["avg"] == 200.0
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0

    def test_histogram_empty(self):
        stats = self.mc.get_histogram_stats("nonexistent")
        assert stats["count"] == 0

    def test_gauge_set(self):
        self.mc.set_gauge("active_agents", 5.0)
        assert self.mc.get_gauge("active_agents") == 5.0

    def test_gauge_overwrite(self):
        self.mc.set_gauge("temp", 1.0)
        self.mc.set_gauge("temp", 2.0)
        assert self.mc.get_gauge("temp") == 2.0

    def test_snapshot_structure(self):
        self.mc.increment("test_counter")
        self.mc.observe("test_hist", 42.0)
        self.mc.set_gauge("test_gauge", 3.14)

        snap = self.mc.snapshot()
        assert "uptime_seconds" in snap
        assert "captured_at" in snap
        assert "counters" in snap
        assert "histograms" in snap
        assert "gauges" in snap
        assert snap["counters"]["test_counter"] == 1
        assert snap["gauges"]["test_gauge"] == 3.14


# ============================================================================
# AuditLogger
# ============================================================================

class TestAuditLogger:
    def setup_method(self):
        self.al = AuditLogger()

    def test_log_returns_record(self):
        record = self.al.log(
            instance_id="test-123",
            event="PENDING",
            agent_id="secops-agent",
            urgency="CRITICAL",
        )
        assert record["instance_id"] == "test-123"
        assert record["event"] == "PENDING"
        assert "timestamp" in record

    def test_recent_events_ordered(self):
        self.al.log(instance_id="a", event="PENDING", agent_id="agent1")
        self.al.log(instance_id="b", event="APPROVED", agent_id="agent1")
        self.al.log(instance_id="c", event="REJECTED", agent_id="agent2")

        events = self.al.get_recent_events(limit=10)
        # Most recent first
        assert events[0]["instance_id"] == "c"
        assert events[2]["instance_id"] == "a"

    def test_events_for_instance(self):
        self.al.log(instance_id="x", event="PENDING", agent_id="agent1")
        self.al.log(instance_id="y", event="PENDING", agent_id="agent2")
        self.al.log(instance_id="x", event="APPROVED", agent_id="agent1")

        events = self.al.get_events_for_instance("x")
        assert len(events) == 2
        assert all(e["instance_id"] == "x" for e in events)

    def test_buffer_limit(self):
        """Should keep at most 1000 events."""
        for i in range(1050):
            self.al.log(instance_id=str(i), event="PENDING", agent_id="agent")

        events = self.al.get_recent_events(limit=2000)
        assert len(events) <= 1000

    def test_metadata_stored(self):
        record = self.al.log(
            instance_id="test",
            event="PENDING",
            metadata={"tenant_id": "contoso"},
        )
        assert record["metadata"]["tenant_id"] == "contoso"


# ============================================================================
# HITL-specific metric helpers
# ============================================================================

class TestHITLMetrics:
    def test_record_request(self):
        initial = metrics.get_counter("hitl.requests.total")
        record_request_received("agent-1", "CRITICAL")
        assert metrics.get_counter("hitl.requests.total") == initial + 1

    def test_record_decision(self):
        initial = metrics.get_counter("hitl.decisions.total")
        record_decision("APPROVED", "HIGH", 42.5)
        assert metrics.get_counter("hitl.decisions.total") == initial + 1

        stats = metrics.get_histogram_stats("hitl.decision.duration_seconds")
        assert stats["count"] >= 1
