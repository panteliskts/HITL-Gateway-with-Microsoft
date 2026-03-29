"""
test_schemas.py — Unit tests for the HITL contract models
===========================================================
Covers validation rules, defaults, edge cases, and backward compatibility.
"""
import uuid

import pytest
from pydantic import ValidationError

from gateway.schemas import (
    ApprovalPolicy,
    HITLRequest,
    HITLResponse,
    HITLStatus,
    HITLSummary,
    HumanDecisionEvent,
    SLA_TIMEOUT_SECONDS,
    UrgencyLevel,
)


# ============================================================================
# UrgencyLevel
# ============================================================================

class TestUrgencyLevel:
    def test_all_levels_defined(self):
        assert set(UrgencyLevel) == {
            UrgencyLevel.CRITICAL,
            UrgencyLevel.HIGH,
            UrgencyLevel.NORMAL,
            UrgencyLevel.LOW,
        }

    def test_string_values(self):
        assert UrgencyLevel.CRITICAL.value == "CRITICAL"
        assert UrgencyLevel.LOW.value == "LOW"

    def test_sla_timeouts_cover_all_levels(self):
        for level in UrgencyLevel:
            assert level in SLA_TIMEOUT_SECONDS or level.value in SLA_TIMEOUT_SECONDS


# ============================================================================
# HITLRequest
# ============================================================================

class TestHITLRequest:
    """Tests for the inbound agent → gateway contract."""

    def _valid_request(self, **overrides) -> dict:
        base = {
            "agent_id": "test-agent-v1",
            "action_description": "Test action requiring approval",
            "required_role": "SecOps_Lead",
            "urgency": "NORMAL",
            "callback_url": "http://localhost:7071/resume_agent",
        }
        base.update(overrides)
        return base

    def test_valid_request(self):
        req = HITLRequest(**self._valid_request())
        assert req.agent_id == "test-agent-v1"
        assert req.urgency == UrgencyLevel.NORMAL
        assert req.tenant_id == "default"
        assert req.dry_run is False
        assert req.priority == 0

    def test_auto_generated_idempotency_key(self):
        req = HITLRequest(**self._valid_request())
        assert req.idempotency_key  # Should auto-generate a UUID
        uuid.UUID(req.idempotency_key)  # Should be a valid UUID

    def test_custom_idempotency_key(self):
        req = HITLRequest(**self._valid_request(idempotency_key="custom-key-123"))
        assert req.idempotency_key == "custom-key-123"

    def test_missing_agent_id_fails(self):
        data = self._valid_request()
        del data["agent_id"]
        with pytest.raises(ValidationError):
            HITLRequest(**data)

    def test_blank_agent_id_fails(self):
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(agent_id="   "))

    def test_missing_callback_url_fails(self):
        data = self._valid_request()
        del data["callback_url"]
        with pytest.raises(ValidationError):
            HITLRequest(**data)

    def test_invalid_callback_url_scheme(self):
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(callback_url="ftp://bad.com/hook"))

    def test_invalid_urgency_fails(self):
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(urgency="ULTRA_CRITICAL"))

    def test_default_urgency(self):
        data = self._valid_request()
        del data["urgency"]
        req = HITLRequest(**data)
        assert req.urgency == UrgencyLevel.NORMAL

    def test_context_accepts_arbitrary_data(self):
        ctx = {"ip": "10.0.5.42", "score": 0.97, "nested": {"a": 1}}
        req = HITLRequest(**self._valid_request(context=ctx))
        assert req.context["ip"] == "10.0.5.42"
        assert req.context["nested"]["a"] == 1

    def test_enterprise_fields_optional(self):
        """All enterprise extensions should have defaults."""
        req = HITLRequest(**self._valid_request())
        assert req.tenant_id == "default"
        assert req.tags == []
        assert req.priority == 0
        assert req.approval_policy == ApprovalPolicy.ANY
        assert req.required_roles == []
        assert req.expires_at is None
        assert req.dry_run is False

    def test_enterprise_fields_set(self):
        req = HITLRequest(**self._valid_request(
            tenant_id="contoso-corp",
            tags=["security", "pci"],
            priority=75,
            approval_policy="ALL",
            required_roles=["SecOps_Lead", "CISO"],
            dry_run=True,
        ))
        assert req.tenant_id == "contoso-corp"
        assert "security" in req.tags
        assert req.priority == 75
        assert req.approval_policy == ApprovalPolicy.ALL
        assert req.dry_run is True

    def test_priority_bounds(self):
        HITLRequest(**self._valid_request(priority=0))
        HITLRequest(**self._valid_request(priority=100))
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(priority=-1))
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(priority=101))

    def test_effective_roles_single(self):
        req = HITLRequest(**self._valid_request())
        assert req.effective_roles == ["SecOps_Lead"]

    def test_effective_roles_multi(self):
        req = HITLRequest(**self._valid_request(
            required_roles=["SecOps_Lead", "CISO"]
        ))
        assert req.effective_roles == ["SecOps_Lead", "CISO"]

    def test_action_description_max_length(self):
        # 4096 chars should work
        HITLRequest(**self._valid_request(action_description="x" * 4096))
        # 4097 should fail
        with pytest.raises(ValidationError):
            HITLRequest(**self._valid_request(action_description="x" * 4097))

    def test_serialization_roundtrip(self):
        req = HITLRequest(**self._valid_request(
            tenant_id="acme", tags=["test"], priority=50,
        ))
        data = req.model_dump()
        req2 = HITLRequest(**data)
        assert req2.agent_id == req.agent_id
        assert req2.tenant_id == req.tenant_id
        assert req2.tags == req.tags


# ============================================================================
# HITLResponse
# ============================================================================

class TestHITLResponse:
    def test_valid_response(self):
        resp = HITLResponse(
            instance_id="test-123",
            status=HITLStatus.APPROVED,
            reviewer_id="jane@contoso.com",
            reason="Reviewed and approved",
        )
        assert resp.status == HITLStatus.APPROVED
        assert resp.dry_run is False

    def test_escalated_response(self):
        resp = HITLResponse(
            instance_id="test-456",
            status=HITLStatus.ESCALATED,
            reviewer_id="SYSTEM_TIMEOUT",
            reason="SLA timeout after 300s",
            duration_seconds=300.0,
        )
        assert resp.duration_seconds == 300.0

    def test_dry_run_response(self):
        resp = HITLResponse(
            instance_id="test-789",
            status=HITLStatus.APPROVED,
            reviewer_id="test@example.com",
            dry_run=True,
        )
        assert resp.dry_run is True


# ============================================================================
# HumanDecisionEvent
# ============================================================================

class TestHumanDecisionEvent:
    def test_valid_event(self):
        event = HumanDecisionEvent(
            status=HITLStatus.APPROVED,
            reviewer_id="jane@contoso.com",
            reason="Looks good",
        )
        assert event.status == HITLStatus.APPROVED
        assert event.nonce is None

    def test_event_with_nonce(self):
        event = HumanDecisionEvent(
            status=HITLStatus.REJECTED,
            reviewer_id="bob@contoso.com",
            nonce="abc123",
            timestamp=1711545600.0,
        )
        assert event.nonce == "abc123"

    def test_blank_reviewer_fails(self):
        with pytest.raises(ValidationError):
            HumanDecisionEvent(
                status=HITLStatus.APPROVED,
                reviewer_id="",
            )

    def test_reason_max_length(self):
        HumanDecisionEvent(
            status=HITLStatus.APPROVED,
            reviewer_id="test@example.com",
            reason="x" * 2048,
        )
        with pytest.raises(ValidationError):
            HumanDecisionEvent(
                status=HITLStatus.APPROVED,
                reviewer_id="test@example.com",
                reason="x" * 2049,
            )


# ============================================================================
# SLA Timeout Map
# ============================================================================

class TestSLATimeouts:
    def test_critical_is_5_minutes(self):
        assert SLA_TIMEOUT_SECONDS[UrgencyLevel.CRITICAL] == 300

    def test_high_is_15_minutes(self):
        assert SLA_TIMEOUT_SECONDS[UrgencyLevel.HIGH] == 900

    def test_normal_is_60_minutes(self):
        assert SLA_TIMEOUT_SECONDS[UrgencyLevel.NORMAL] == 3600

    def test_low_is_24_hours(self):
        assert SLA_TIMEOUT_SECONDS[UrgencyLevel.LOW] == 86400
