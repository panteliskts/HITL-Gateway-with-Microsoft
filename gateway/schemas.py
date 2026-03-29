"""
schemas.py — The Shared HITL Contract (Enterprise Edition)
============================================================
Pydantic v2 models defining the canonical wire-format between any AI agent
and the Azure Durable Functions HITL Gateway.

Design principles
-----------------
- **Agent-agnostic**: any service that speaks JSON can use this contract.
- **Idempotency-safe**: every request carries an ``idempotency_key`` so the
  gateway can de-duplicate retried submissions.
- **Urgency-driven SLA**: the ``UrgencyLevel`` enum drives both the
  notification channel and the durable timer duration.
- **Rich context**: ``context`` is a free-form dict so agents can pass cost
  estimates, trace IDs, model outputs, etc. alongside the human-readable
  ``action_description``.
- **Multi-tenant**: optional ``tenant_id`` for enterprise isolation.
- **Extensible**: optional fields for tags, priority overrides, and
  multi-stage approval workflows.

This module is intentionally free of FastAPI, Azure Functions, and database
dependencies so it can be imported by both the gateway and the edge agent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UrgencyLevel(str, Enum):
    """
    SLA urgency tiers.

    Each tier controls two things inside the orchestrator:
      1. **Notification channel** — CRITICAL routes to Slack; all others to Teams.
      2. **Timer duration** — how long the gateway waits before auto-escalating.

    SLA map (seconds):
      CRITICAL  →  5 min  (300 s)
      HIGH      → 15 min  (900 s)
      NORMAL    → 60 min  (3 600 s)
      LOW       → 24 hr   (86 400 s)
    """
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    NORMAL   = "NORMAL"
    LOW      = "LOW"


class HITLStatus(str, Enum):
    """
    Terminal (and interim) lifecycle states of a single HITL interaction.

    These appear verbatim in [AUDIT] log lines so Azure Monitor / App Insights
    can filter and alert on them.
    """
    PENDING   = "PENDING"     # Orchestration started; waiting for human
    APPROVED  = "APPROVED"    # Human explicitly approved the action
    REJECTED  = "REJECTED"    # Human explicitly rejected the action
    ESCALATED = "ESCALATED"   # SLA timer expired → auto-escalated


class ApprovalPolicy(str, Enum):
    """
    Multi-approver policy for enterprise workflows.

    - ANY: any single approver from the required_roles list is sufficient.
    - ALL: every role in the required_roles list must approve.
    - MAJORITY: more than half of the required_roles must approve.
    """
    ANY      = "ANY"
    ALL      = "ALL"
    MAJORITY = "MAJORITY"


# ---------------------------------------------------------------------------
# SLA timeout map (seconds) — referenced by the orchestrator and agent mock
# ---------------------------------------------------------------------------

SLA_TIMEOUT_SECONDS: Dict[str, int] = {
    UrgencyLevel.CRITICAL:  5   * 60,      #   5 minutes
    UrgencyLevel.HIGH:      15  * 60,      #  15 minutes
    UrgencyLevel.NORMAL:    60  * 60,      #  60 minutes
    UrgencyLevel.LOW:       24  * 3600,    #  24 hours
}

# ---------------------------------------------------------------------------
# Role → Teams channel mapping (mock)
# In production this would be backed by Azure AD group lookups.
# ---------------------------------------------------------------------------

ROLE_CHANNEL_MAP: Dict[str, str] = {
    "Finance_Manager":    "#finance-approvals",
    "SecOps_Lead":        "#secops-alerts",
    "Compliance_Officer": "#compliance-reviews",
    "Risk_Manager":       "#risk-management",
}
DEFAULT_CHANNEL: str = "#hitl-general"


# ---------------------------------------------------------------------------
# Inbound contract  (AI Agent → Azure Gateway)
# ---------------------------------------------------------------------------

class HITLRequest(BaseModel):
    """
    Payload an AI agent POSTs to ``/api/hitl_ingress`` when it encounters
    a high-risk action that requires human approval.

    Enterprise additions (all optional, backward-compatible):
    - ``tenant_id``: multi-tenant isolation
    - ``tags``: searchable labels for filtering and analytics
    - ``priority``: optional numeric priority within the same urgency tier
    - ``approval_policy``: multi-approver workflow policy
    - ``required_roles``: list of roles for multi-stage approval
    - ``expires_at``: hard expiry (overrides SLA timer if earlier)
    - ``dry_run``: test mode — log but don't execute
    """
    idempotency_key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description=(
            "Caller-supplied or auto-generated dedup key.  "
            "The gateway uses this as the Durable Functions instance_id."
        ),
    )
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier of the requesting agent (e.g. 'finance-agent-v3').",
    )
    action_description: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description=(
            "Plain-language description of the action awaiting approval.  "
            "This is displayed verbatim inside the Teams Adaptive Card."
        ),
    )
    required_role: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description=(
            "The organisational role that must approve this action "
            "(e.g. 'Finance_Manager', 'SecOps_Lead').  "
            "Used to route to the correct Teams channel."
        ),
    )
    urgency: UrgencyLevel = Field(
        default=UrgencyLevel.NORMAL,
        description="Urgency tier — drives SLA timeout and notification channel.",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured context the reviewer may need (cost estimates, trace IDs, etc.).",
    )
    callback_url: str = Field(
        ...,
        description="HTTP(S) endpoint where the gateway POSTs the final HITLResponse.",
    )

    # ── Enterprise extensions (all optional) ──────────────────────────────────

    tenant_id: str = Field(
        default="default",
        max_length=128,
        description="Tenant identifier for multi-tenant deployments.",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Searchable tags for filtering and analytics (e.g. ['security', 'pci-dss']).",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Numeric priority within the same urgency tier (0=default, 100=highest).",
    )
    approval_policy: ApprovalPolicy = Field(
        default=ApprovalPolicy.ANY,
        description="Multi-approver policy: ANY (one is enough), ALL, or MAJORITY.",
    )
    required_roles: List[str] = Field(
        default_factory=list,
        description=(
            "For multi-stage approval: list of roles that must approve. "
            "If empty, falls back to the single 'required_role' field."
        ),
    )
    expires_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 hard expiry timestamp. Overrides SLA timer if earlier.",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, the request is logged and tracked but the agent callback is skipped.",
    )

    @field_validator("agent_id", "required_role")
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        """Reject blank or whitespace-only values."""
        if not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip()

    @field_validator("callback_url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Ensure callback URL has a valid scheme."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("callback_url must start with http:// or https://")
        return v

    @property
    def effective_roles(self) -> List[str]:
        """Return the list of roles that must approve (multi-stage or single)."""
        if self.required_roles:
            return self.required_roles
        return [self.required_role]


# ---------------------------------------------------------------------------
# Outbound contract  (Azure Gateway → AI Agent callback)
# ---------------------------------------------------------------------------

class HITLResponse(BaseModel):
    """
    Terminal payload the gateway fires to the agent's ``callback_url``
    once the human responds or the SLA timer expires.
    """
    instance_id: str = Field(
        ...,
        description="Durable Functions instance_id (= original idempotency_key).",
    )
    status: HITLStatus = Field(
        ...,
        description="Terminal outcome: APPROVED | REJECTED | ESCALATED.",
    )
    reviewer_id: str = Field(
        ...,
        description=(
            "Identity of the human who decided.  "
            "Set to 'SYSTEM_TIMEOUT' when the SLA expires before a human responds."
        ),
    )
    reason: str = Field(
        default="",
        description="Free-text rationale provided by the reviewer (or system).",
    )
    decided_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of when the decision was made.",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Seconds from request creation to decision.",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, this was a test run and no action should be executed.",
    )


# ---------------------------------------------------------------------------
# Internal event contract (Teams / Logic App → Gateway webhook)
# ---------------------------------------------------------------------------

class HumanDecisionEvent(BaseModel):
    """
    Shape of the JSON body the Teams Logic App POSTs to
    ``/api/teams_webhook_callback/{instance_id}`` when a reviewer
    clicks Approve or Reject on the Adaptive Card.
    """
    status: HITLStatus = Field(
        ...,
        description="The reviewer's decision: APPROVED or REJECTED.",
    )
    reviewer_id: str = Field(
        ...,
        min_length=1,
        description="Reviewer identity (e.g. AAD UPN 'jane.doe@contoso.com').",
    )
    reason: str = Field(
        default="",
        max_length=2048,
        description="Optional free-text rationale from the reviewer.",
    )
    nonce: Optional[str] = Field(
        default=None,
        description="Anti-replay nonce (HMAC-verified by the gateway).",
    )
    timestamp: Optional[float] = Field(
        default=None,
        description="Unix epoch timestamp of the decision (for replay prevention).",
    )


# ---------------------------------------------------------------------------
# Dashboard API models (for frontend integration)
# ---------------------------------------------------------------------------

class HITLSummary(BaseModel):
    """Lightweight summary of a HITL request for dashboard list views."""
    instance_id: str
    agent_id: str
    action_description: str
    required_role: str
    urgency: UrgencyLevel
    status: HITLStatus
    tenant_id: str = "default"
    tags: List[str] = Field(default_factory=list)
    priority: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    sla_deadline: Optional[str] = None
    sla_remaining_seconds: Optional[int] = None


class DashboardStats(BaseModel):
    """Aggregated statistics for the dashboard overview."""
    total_requests: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    escalated: int = 0
    avg_decision_time_seconds: float = 0.0
    sla_compliance_rate: float = 0.0
    active_agents: int = 0
