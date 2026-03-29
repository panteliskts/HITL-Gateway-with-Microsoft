"""
function_app.py — Azure Durable Functions HITL Gateway (Enterprise Edition)
===========================================================================
Azure Functions **Python V2 Programming Model** — all triggers, orchestrators,
and activities are registered via decorators on a single ``DFApp`` instance.

Architecture
------------
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  AI Agent  (any language / framework)                                  │
  │     │  POST /api/hitl_ingress  (HITLRequest JSON + X-API-Key header)  │
  │     ▼                                                                  │
  │  [HTTP Trigger] hitl_ingress                                           │
  │     │  auth ► rate-limit ► validate ► sanitize ► start orchestration  │
  │     ▼                                                                  │
  │  [Orchestrator] hitl_orchestrator                                      │
  │     ├─ Activity: log_audit          ("PENDING")                       │
  │     ├─ Activity: send_teams_card    → fires Logic App / Teams webhook │
  │     ├─ Durable Timer (SLA deadline driven by urgency)                 │
  │     ├─ wait_for_external_event("HumanDecision")  ← races the timer   │
  │     │       └─ winner resolves to APPROVED/REJECTED  or  ESCALATED   │
  │     ├─ [if Timeout]  Activity: send_slack_escalation                  │
  │     ├─ Activity: log_audit          (terminal state)                  │
  │     └─ Activity: notify_agent       → POSTs HITLResponse to callback │
  │                                                                        │
  │  Microsoft Teams / Slack / Logic App                                  │
  │     │  POST /api/teams_webhook_callback/{instance_id}                 │
  │     │  (X-Webhook-Signature HMAC verification)                        │
  │     ▼                                                                  │
  │  [HTTP Trigger] teams_webhook_callback                                 │
  │     │  raises "HumanDecision" event on the paused orchestration       │
  │     ▼                                                                  │
  │  Orchestrator resumes → notify_agent fires callback to AI Agent       │
  │                                                                        │
  │  Dashboard API (for frontend integration)                             │
  │     GET  /api/health           → deep health check                    │
  │     GET  /api/metrics          → Prometheus-style metrics snapshot    │
  │     GET  /api/pending          → list active HITL requests            │
  │     GET  /api/audit/{id}       → audit trail for a specific instance │
  │     GET  /api/stats            → aggregated dashboard stats          │
  └─────────────────────────────────────────────────────────────────────────┘

Security
--------
  - API key authentication on agent-facing endpoints
  - HMAC-SHA256 signature verification on webhook callbacks
  - Callback URL allowlist (SSRF prevention)
  - Input sanitization (XSS prevention)
  - Rate limiting per agent_id
  - Nonce-based replay prevention

Observability
-------------
  - Structured [AUDIT] log lines for Azure Monitor / KQL
  - Custom metrics (counters, histograms, gauges)
  - Health check endpoint for Traffic Manager probes
  - In-memory audit trail buffer for API exposure
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import azure.durable_functions as df
import azure.functions as func
import httpx

from gateway import settings
from gateway.observability import (
    audit_logger,
    health_checker,
    metrics,
    record_auth_result,
    record_callback_delivery,
    record_decision,
    record_rate_limit_hit,
    record_request_received,
    record_webhook_delivery,
)
from gateway.schemas import (
    DEFAULT_CHANNEL,
    HITLRequest,
    HITLResponse,
    HITLStatus,
    HITLSummary,
    HumanDecisionEvent,
    ROLE_CHANNEL_MAP,
    SLA_TIMEOUT_SECONDS,
    UrgencyLevel,
)
from gateway.security import (
    check_rate_limit,
    check_nonce,
    compute_hmac_signature,
    extract_api_key,
    sanitize_context,
    sanitize_text,
    validate_api_key,
    validate_callback_url,
    verify_webhook_signature,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("hitl_gateway")

# Log configuration summary at startup
settings.log_summary()

# ---------------------------------------------------------------------------
# DFApp
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# In-memory request tracker (for dashboard API — replaced by Cosmos in prod)
# ---------------------------------------------------------------------------

_active_requests: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# HTTP TRIGGER — hitl_ingress  (Agent → Gateway)
# ============================================================================

@app.route(route="hitl_ingress", methods=["POST"])
@app.durable_client_input(client_name="client")
async def hitl_ingress(
    req: func.HttpRequest,
    client: df.DurableOrchestrationClient,
) -> func.HttpResponse:
    """
    Entry point for AI agents.

    Pipeline: authenticate → rate-limit → validate → sanitize → orchestrate.
    """
    request_start = time.time()

    # ── Step 1: Authentication ───────────────────────────────────────────────
    api_key = extract_api_key(dict(req.headers))
    if not validate_api_key(api_key):
        record_auth_result(success=False)
        logger.warning("[INGRESS][AUTH] Unauthorized request — invalid or missing API key")
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized", "detail": "Invalid or missing API key"}),
            mimetype="application/json",
            status_code=401,
        )
    record_auth_result(success=True)

    # ── Step 2: Parse + validate ─────────────────────────────────────────────
    try:
        body: Dict[str, Any] = req.get_json()
    except ValueError:
        logger.error("[INGRESS] Received non-JSON body — rejecting with 400.")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            mimetype="application/json",
            status_code=400,
        )

    try:
        hitl_req = HITLRequest(**body)
    except Exception as exc:
        logger.error("[INGRESS] Schema validation failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Schema validation failed", "detail": str(exc)}),
            mimetype="application/json",
            status_code=422,
        )

    # ── Step 3: Rate limiting ────────────────────────────────────────────────
    allowed, remaining = check_rate_limit(hitl_req.agent_id)
    if not allowed:
        record_rate_limit_hit(hitl_req.agent_id)
        logger.warning(
            "[INGRESS][RATELIMIT] Agent %s exceeded rate limit", hitl_req.agent_id
        )
        return func.HttpResponse(
            json.dumps({
                "error": "Rate limit exceeded",
                "detail": f"Agent '{hitl_req.agent_id}' exceeded {settings.rate_limit_max} requests per {settings.rate_limit_window}s",
                "retry_after": settings.rate_limit_window,
            }),
            mimetype="application/json",
            status_code=429,
            headers={"Retry-After": str(settings.rate_limit_window)},
        )

    # ── Step 4: Callback URL validation (SSRF prevention) ───────────────────
    url_valid, url_reason = validate_callback_url(
        hitl_req.callback_url,
        allow_localhost=settings.is_development,
    )
    if not url_valid:
        logger.warning(
            "[INGRESS][SECURITY] Rejected callback_url: %s | reason=%s",
            hitl_req.callback_url, url_reason,
        )
        return func.HttpResponse(
            json.dumps({"error": "Invalid callback_url", "detail": url_reason}),
            mimetype="application/json",
            status_code=400,
        )

    # ── Step 5: Sanitize inputs ──────────────────────────────────────────────
    sanitized_description = sanitize_text(hitl_req.action_description)
    sanitized_context = sanitize_context(hitl_req.context)

    # ── Step 6: Record metrics ───────────────────────────────────────────────
    record_request_received(hitl_req.agent_id, hitl_req.urgency.value)

    # ── Step 7: Idempotency check ────────────────────────────────────────────
    instance_id: str = hitl_req.idempotency_key

    existing = await client.get_status(instance_id)
    if existing and existing.runtime_status not in (
        df.OrchestrationRuntimeStatus.Failed,
        df.OrchestrationRuntimeStatus.Terminated,
        None,
    ):
        if existing.runtime_status == df.OrchestrationRuntimeStatus.Completed:
            output = existing.output or {}
            mapped_status = output.get("status", HITLStatus.APPROVED.value)
        elif existing.runtime_status == df.OrchestrationRuntimeStatus.Running:
            mapped_status = HITLStatus.PENDING.value
        else:
            mapped_status = HITLStatus.PENDING.value

        logger.info(
            "[INGRESS][IDEMPOTENT] instance_id=%s already exists (runtime=%s, mapped=%s)",
            instance_id, existing.runtime_status, mapped_status,
        )
        return func.HttpResponse(
            json.dumps({
                "instance_id":     instance_id,
                "status":          mapped_status,
                "idempotency_key": hitl_req.idempotency_key,
                "idempotent":      True,
            }),
            mimetype="application/json",
            status_code=202,
        )

    # ── Step 8: Start orchestration ──────────────────────────────────────────
    # Build the orchestrator input with sanitized data
    orchestrator_input = hitl_req.model_dump()
    orchestrator_input["action_description"] = sanitized_description
    orchestrator_input["context"] = sanitized_context
    orchestrator_input["_created_at"] = datetime.now(timezone.utc).isoformat()

    await client.start_new(
        "hitl_orchestrator",
        instance_id=instance_id,
        client_input=orchestrator_input,
    )

    # Track in memory for dashboard API
    _active_requests[instance_id] = {
        "instance_id": instance_id,
        "agent_id": hitl_req.agent_id,
        "action_description": sanitized_description,
        "required_role": hitl_req.required_role,
        "urgency": hitl_req.urgency.value,
        "status": HITLStatus.PENDING.value,
        "tenant_id": hitl_req.tenant_id,
        "tags": hitl_req.tags,
        "priority": hitl_req.priority,
        "created_at": orchestrator_input["_created_at"],
        "dry_run": hitl_req.dry_run,
    }

    # Audit log
    audit_logger.log(
        instance_id=instance_id,
        event="PENDING",
        agent_id=hitl_req.agent_id,
        urgency=hitl_req.urgency.value,
        metadata={
            "required_role": hitl_req.required_role,
            "tenant_id": hitl_req.tenant_id,
            "dry_run": hitl_req.dry_run,
            "tags": hitl_req.tags,
        },
    )

    logger.info(
        "[INGRESS] %s — PENDING | agent=%s urgency=%s role=%s tenant=%s dry_run=%s (%.0fms)",
        instance_id, hitl_req.agent_id, hitl_req.urgency.value,
        hitl_req.required_role, hitl_req.tenant_id, hitl_req.dry_run,
        (time.time() - request_start) * 1000,
    )

    return func.HttpResponse(
        json.dumps({
            "instance_id":     instance_id,
            "status":          HITLStatus.PENDING.value,
            "idempotency_key": hitl_req.idempotency_key,
            "idempotent":      False,
            "tenant_id":       hitl_req.tenant_id,
            "dry_run":         hitl_req.dry_run,
        }),
        mimetype="application/json",
        status_code=202,
    )


# ============================================================================
# DURABLE ORCHESTRATOR — hitl_orchestrator
# ============================================================================

@app.orchestration_trigger(context_name="context")
def hitl_orchestrator(context: df.DurableOrchestrationContext):
    """
    Manages the full HITL lifecycle for a single agent request.

    Flow
    ----
    1. Log audit entry for PENDING state.
    2. Map ``required_role`` → Teams channel; send Adaptive Card.
    3. Start a durable SLA timer (duration driven by urgency).
    4. Race the timer against ``wait_for_external_event("HumanDecision")``.
    5a. TIMER wins  → status = ESCALATED, fire Slack escalation activity.
    5b. HUMAN wins  → status = APPROVED / REJECTED, cancel timer.
    6. Log audit entry for terminal state.
    7. Fire ``notify_agent`` to POST the HITLResponse to the agent's callback.
    """
    # ── Unpack input ────────────────────────────────────────────────────────
    payload:     Dict[str, Any] = context.get_input()
    instance_id: str            = context.instance_id
    urgency:     str            = payload.get("urgency", UrgencyLevel.NORMAL.value)
    agent_id:    str            = payload.get("agent_id", "unknown")
    role:        str            = payload.get("required_role", "unknown")
    tenant_id:   str            = payload.get("tenant_id", "default")
    dry_run:     bool           = payload.get("dry_run", False)
    created_at:  str            = payload.get("_created_at", "")

    # ── Retry Policy ─────────────────────────────────────────────────────────
    retry_opts = df.RetryOptions(
        first_retry_interval_in_milliseconds=settings.retry_initial_interval_ms,
        max_number_of_attempts=settings.retry_max_attempts,
    )

    # ── Step 1: Audit log — PENDING ─────────────────────────────────────────
    yield context.call_activity_with_retry("log_audit", retry_opts, {
        "instance_id": instance_id,
        "agent_id":    agent_id,
        "state":       HITLStatus.PENDING.value,
        "urgency":     urgency,
        "tenant_id":   tenant_id,
        "message":     f"Orchestration started for agent={agent_id}, role={role}, tenant={tenant_id}",
    })

    # ── Step 2: Route to Teams channel & send Adaptive Card ─────────────────
    channel: str = ROLE_CHANNEL_MAP.get(role, DEFAULT_CHANNEL)

    if not context.is_replaying:
        logger.info(
            "[ORCHESTRATOR] %s — Routing to channel=%s for role=%s (tenant=%s)",
            instance_id, channel, role, tenant_id,
        )

    yield context.call_activity_with_retry("send_teams_card", retry_opts, {
        "instance_id":        instance_id,
        "agent_id":           agent_id,
        "action_description": payload.get("action_description", ""),
        "required_role":      role,
        "urgency":            urgency,
        "channel":            channel,
        "context":            payload.get("context", {}),
        "tenant_id":          tenant_id,
        "tags":               payload.get("tags", []),
        "dry_run":            dry_run,
    })

    # ── Step 3 & 4: SLA Timer vs HumanDecision ──────────────────────────────
    # Use configurable SLA timeouts
    timeout_secs: int = settings.sla_timeouts.get(urgency, 3600)
    deadline = context.current_utc_datetime + timedelta(seconds=timeout_secs)

    if not context.is_replaying:
        logger.info(
            "[ORCHESTRATOR] %s — SLA timer: %ds (urgency=%s) deadline=%s",
            instance_id, timeout_secs, urgency, deadline.isoformat(),
        )

    timer_task = context.create_timer(deadline)
    human_task = context.wait_for_external_event("HumanDecision")

    winner = yield context.task_any([timer_task, human_task])

    # ── Step 5: Resolution ──────────────────────────────────────────────────
    final_response: Dict[str, Any]
    decided_at = context.current_utc_datetime.isoformat()

    if winner == timer_task:
        # ── TIMEOUT → ESCALATED ──────────────────────────────────────────────
        if not context.is_replaying:
            logger.warning(
                "[ORCHESTRATOR] %s — ESCALATED: SLA of %ds expired for agent=%s (urgency=%s)",
                instance_id, timeout_secs, agent_id, urgency,
            )

        yield context.call_activity_with_retry("send_slack_escalation", retry_opts, {
            "instance_id":        instance_id,
            "agent_id":           agent_id,
            "urgency":            urgency,
            "required_role":      role,
            "action_description": payload.get("action_description", ""),
            "timeout_seconds":    timeout_secs,
            "tenant_id":          tenant_id,
        })

        final_response = {
            "instance_id":      instance_id,
            "status":           HITLStatus.ESCALATED.value,
            "reviewer_id":      "SYSTEM_TIMEOUT",
            "reason":           f"SLA timeout after {timeout_secs}s — auto-escalated.",
            "decided_at":       decided_at,
            "duration_seconds": timeout_secs,
            "dry_run":          dry_run,
        }

    else:
        # ── HUMAN DECISION ───────────────────────────────────────────────────
        timer_task.cancel()

        decision:    Dict[str, Any] = human_task.result
        status_val:  str            = decision.get("status", HITLStatus.APPROVED.value)
        reviewer_id: str            = decision.get("reviewer_id", "unknown")
        reason:      str            = decision.get("reason", "")

        if not context.is_replaying:
            logger.info(
                "[ORCHESTRATOR] %s — %s: decision from %s",
                instance_id, status_val, reviewer_id,
            )

        final_response = {
            "instance_id":      instance_id,
            "status":           status_val,
            "reviewer_id":      reviewer_id,
            "reason":           reason,
            "decided_at":       decided_at,
            "dry_run":          dry_run,
        }

    # ── Step 6: Audit log — terminal state ──────────────────────────────────
    yield context.call_activity_with_retry("log_audit", retry_opts, {
        "instance_id": instance_id,
        "agent_id":    agent_id,
        "state":       final_response["status"],
        "urgency":     urgency,
        "tenant_id":   tenant_id,
        "message":     (
            f"Terminal: {final_response['status']} | "
            f"reviewer={final_response['reviewer_id']} dry_run={dry_run}"
        ),
    })

    # ── Step 7: Callback to originating agent ───────────────────────────────
    if not dry_run:
        yield context.call_activity_with_retry("notify_agent", retry_opts, {
            "callback_url": payload.get("callback_url", ""),
            "response":     final_response,
        })
    else:
        if not context.is_replaying:
            logger.info(
                "[ORCHESTRATOR] %s — DRY RUN: skipping agent callback", instance_id
            )

    if not context.is_replaying:
        logger.info(
            "[ORCHESTRATOR] %s — COMPLETE: status=%s dry_run=%s",
            instance_id, final_response["status"], dry_run,
        )

    # Update in-memory tracker
    if instance_id in _active_requests:
        _active_requests[instance_id]["status"] = final_response["status"]

    return final_response


# ============================================================================
# HTTP TRIGGER — teams_webhook_callback  (Logic App / Teams → Gateway)
# ============================================================================

@app.route(route="teams_webhook_callback/{instance_id}", methods=["POST"])
@app.durable_client_input(client_name="client")
async def teams_webhook_callback(
    req: func.HttpRequest,
    client: df.DurableOrchestrationClient,
) -> func.HttpResponse:
    """
    Endpoint for human decisions. Includes HMAC verification and replay prevention.
    """
    instance_id: str = req.route_params.get("instance_id", "")
    if not instance_id:
        return func.HttpResponse(
            json.dumps({"error": "instance_id path parameter is required"}),
            mimetype="application/json",
            status_code=400,
        )

    # ── HMAC Signature Verification ──────────────────────────────────────────
    raw_body = req.get_body()
    signature = req.headers.get("X-Webhook-Signature") or req.headers.get("x-webhook-signature")
    if not verify_webhook_signature(raw_body, signature):
        logger.warning(
            "[WEBHOOK][SECURITY] Invalid signature | instance_id=%s", instance_id
        )
        return func.HttpResponse(
            json.dumps({"error": "Invalid webhook signature"}),
            mimetype="application/json",
            status_code=403,
        )

    # ── Parse + validate ─────────────────────────────────────────────────────
    try:
        body: Dict[str, Any] = req.get_json()
    except ValueError:
        logger.error("[WEBHOOK] Invalid JSON | instance_id=%s", instance_id)
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            mimetype="application/json",
            status_code=400,
        )

    try:
        decision = HumanDecisionEvent(**body)
    except Exception as exc:
        logger.error("[WEBHOOK] Schema error | instance_id=%s error=%s", instance_id, exc)
        return func.HttpResponse(
            json.dumps({"error": "Schema validation failed", "detail": str(exc)}),
            mimetype="application/json",
            status_code=422,
        )

    # ── Replay prevention ────────────────────────────────────────────────────
    if not check_nonce(decision.nonce, decision.timestamp):
        logger.warning("[WEBHOOK][SECURITY] Replay detected | instance_id=%s", instance_id)
        return func.HttpResponse(
            json.dumps({"error": "Replay attack detected"}),
            mimetype="application/json",
            status_code=409,
        )

    # ── Guard: orchestration must exist and be running ───────────────────────
    status = await client.get_status(instance_id)
    if not status:
        logger.warning("[WEBHOOK] No orchestration found | instance_id=%s", instance_id)
        return func.HttpResponse(
            json.dumps({"error": "Orchestration not found", "instance_id": instance_id}),
            mimetype="application/json",
            status_code=404,
        )

    if status.runtime_status != df.OrchestrationRuntimeStatus.Running:
        logger.warning(
            "[WEBHOOK] Orchestration not running | instance_id=%s status=%s",
            instance_id, status.runtime_status,
        )
        return func.HttpResponse(
            json.dumps({
                "error":          "Orchestration already completed",
                "instance_id":    instance_id,
                "runtime_status": str(status.runtime_status),
            }),
            mimetype="application/json",
            status_code=409,
        )

    # ── Raise the external event ────────────────────────────────────────────
    await client.raise_event(
        instance_id=instance_id,
        event_name="HumanDecision",
        event_data=decision.model_dump(),
    )

    # Audit log
    audit_logger.log(
        instance_id=instance_id,
        event=decision.status.value,
        reviewer_id=decision.reviewer_id,
        reason=decision.reason,
    )

    logger.info(
        "[WEBHOOK] HumanDecision raised | instance_id=%s status=%s reviewer=%s",
        instance_id, decision.status.value, decision.reviewer_id,
    )

    return func.HttpResponse(
        json.dumps({
            "status":      "event_raised",
            "instance_id": instance_id,
            "decision":    decision.status.value,
        }),
        mimetype="application/json",
        status_code=200,
    )


# ============================================================================
# ACTIVITY — send_teams_card
# ============================================================================

@app.activity_trigger(input_name="payload")
async def send_teams_card(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds and delivers a Teams Adaptive Card with sanitized content.
    """
    instance_id: str = payload.get("instance_id", "unknown")
    agent_id:    str = payload.get("agent_id", "unknown")
    urgency:     str = payload.get("urgency", "NORMAL")
    channel:     str = payload.get("channel", DEFAULT_CHANNEL)
    role:        str = payload.get("required_role", "N/A")
    action_desc: str = payload.get("action_description", "")
    ctx:         Dict = payload.get("context", {})
    tenant_id:   str = payload.get("tenant_id", "default")
    tags:        list = payload.get("tags", [])
    dry_run:     bool = payload.get("dry_run", False)

    # Build Adaptive Card facts
    facts = [
        {"title": "Instance ID",   "value": instance_id},
        {"title": "Agent",         "value": agent_id},
        {"title": "Required Role", "value": role},
        {"title": "Urgency",       "value": urgency},
        {"title": "Action",        "value": action_desc},
        {"title": "Tenant",        "value": tenant_id},
    ]
    if tags:
        facts.append({"title": "Tags", "value": ", ".join(tags)})
    if dry_run:
        facts.append({"title": "Mode", "value": "DRY RUN (test only)"})

    for key, value in ctx.items():
        facts.append({"title": key, "value": str(value)})

    adaptive_card: Dict[str, Any] = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type":    "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type":   "TextBlock",
                        "size":   "Medium",
                        "weight": "Bolder",
                        "text":   f"{'[DRY RUN] ' if dry_run else ''}[{urgency}] Human Decision Required — {agent_id}",
                        "color":  "Attention" if urgency in ("CRITICAL", "HIGH") else "Default",
                    },
                    {
                        "type":  "FactSet",
                        "facts": facts,
                    },
                ],
                "actions": [
                    {
                        "type":  "Action.OpenUrl",
                        "title": "Review & Decide",
                        "url":   f"{settings.dashboard_url}/review/{instance_id}",
                    },
                ],
            },
        }],
    }

    logger.info("========== TEAMS ADAPTIVE CARD ==========")
    logger.info("Channel   : %s", channel)
    logger.info("Urgency   : %s", urgency)
    logger.info("Agent     : %s", agent_id)
    logger.info("Tenant    : %s", tenant_id)
    logger.info("Dry Run   : %s", dry_run)
    logger.info("==========================================")

    delivered = False
    if settings.teams_webhook_url:
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(settings.teams_webhook_url, json=adaptive_card)
                resp.raise_for_status()
            latency = (time.time() - start) * 1000
            delivered = True
            record_webhook_delivery("teams", success=True, latency_ms=latency)
            logger.info(
                "[TEAMS] %s — Adaptive Card delivered | channel=%s HTTP=%d (%.0fms)",
                instance_id, channel, resp.status_code, latency,
            )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            record_webhook_delivery("teams", success=False, latency_ms=latency)
            logger.error("[TEAMS] Webhook failed | instance_id=%s error=%s", instance_id, exc)
    else:
        logger.info("[TEAMS][MOCK] TEAMS_WEBHOOK_URL not set — dev mode.")
        logger.debug("[TEAMS][MOCK] Card JSON:\n%s", json.dumps(adaptive_card, indent=2))

    return {"channel": channel, "instance_id": instance_id, "delivered": delivered}


# ============================================================================
# ACTIVITY — send_slack_escalation
# ============================================================================

@app.activity_trigger(input_name="payload")
async def send_slack_escalation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fires Slack escalation on SLA timeout with tenant context.
    """
    instance_id: str = payload.get("instance_id", "unknown")
    agent_id:    str = payload.get("agent_id", "unknown")
    urgency:     str = payload.get("urgency", "unknown")
    role:        str = payload.get("required_role", "unknown")
    timeout_sec: int = payload.get("timeout_seconds", 0)
    action_desc: str = payload.get("action_description", "")
    tenant_id:   str = payload.get("tenant_id", "default")

    logger.warning(
        "[AUDIT] %s — Escalated: SLA timeout of %ds | agent=%s urgency=%s role=%s tenant=%s",
        instance_id, timeout_sec, agent_id, urgency, role, tenant_id,
    )

    # Record metric
    record_decision("ESCALATED", urgency, float(timeout_sec))

    escalation_body: Dict[str, Any] = {
        "text": (
            f":rotating_light: *SLA TIMEOUT ESCALATION*\n"
            f"*Instance:*  `{instance_id}`\n"
            f"*Agent:*  `{agent_id}`\n"
            f"*Urgency:*  {urgency}\n"
            f"*Role:*  {role}\n"
            f"*Tenant:*  {tenant_id}\n"
            f"*Action:*  {action_desc}\n"
            f"*Timeout:*  {timeout_sec}s\n\n"
            f"HITL request `{instance_id}` exceeded its {timeout_sec}s SLA."
        ),
    }

    for label, url in [("SLACK", settings.slack_webhook_url), ("ESCALATION", settings.escalation_url)]:
        if url:
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.post(url, json=escalation_body)
                    resp.raise_for_status()
                latency = (time.time() - start) * 1000
                record_webhook_delivery(label.lower(), success=True, latency_ms=latency)
                logger.info("[ESCALATE] %s delivered | instance_id=%s (%.0fms)", label, instance_id, latency)
            except Exception as exc:
                latency = (time.time() - start) * 1000
                record_webhook_delivery(label.lower(), success=False, latency_ms=latency)
                logger.error("[ESCALATE] %s failed | instance_id=%s error=%s", label, instance_id, exc)
        else:
            logger.warning("[ESCALATE][MOCK] %s_WEBHOOK_URL not set — dev mode.", label)

    return {"escalated": True, "instance_id": instance_id}


# ============================================================================
# ACTIVITY — log_audit
# ============================================================================

@app.activity_trigger(input_name="payload")
def log_audit(payload: Dict[str, Any]) -> str:
    """
    Emit a structured audit event via the AuditLogger.
    """
    instance_id = payload.get("instance_id", "unknown")
    agent_id    = payload.get("agent_id", "unknown")
    state       = payload.get("state", "UNKNOWN")
    urgency     = payload.get("urgency", "UNKNOWN")
    message     = payload.get("message", "")
    tenant_id   = payload.get("tenant_id", "default")

    audit_logger.log(
        instance_id=instance_id,
        event=state,
        agent_id=agent_id,
        urgency=urgency,
        metadata={"message": message, "tenant_id": tenant_id},
    )

    return f"Audit logged: {instance_id} -> {state}"


# ============================================================================
# ACTIVITY — notify_agent
# ============================================================================

@app.activity_trigger(input_name="payload")
async def notify_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POSTs the terminal HITLResponse to the agent's callback_url with metrics.
    """
    callback_url:  str            = payload.get("callback_url", "")
    response_body: Dict[str, Any] = payload.get("response", {})
    instance_id:   str            = response_body.get("instance_id", "unknown")

    if not callback_url:
        logger.warning("[CALLBACK] No callback_url | instance_id=%s — skipping.", instance_id)
        return {"delivered": False, "reason": "no callback_url"}

    logger.info(
        "[CALLBACK] Delivering HITLResponse | instance_id=%s url=%s status=%s",
        instance_id, callback_url, response_body.get("status"),
    )

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(callback_url, json=response_body)
            resp.raise_for_status()
        latency = (time.time() - start) * 1000
        record_callback_delivery(success=True, latency_ms=latency)
        logger.info(
            "[CALLBACK] %s — Agent notified | HTTP=%d (%.0fms)",
            instance_id, resp.status_code, latency,
        )
        return {"delivered": True, "http_status": resp.status_code}
    except Exception as exc:
        latency = (time.time() - start) * 1000
        record_callback_delivery(success=False, latency_ms=latency)
        logger.error("[CALLBACK] Failed | instance_id=%s error=%s", instance_id, exc)
        return {"delivered": False, "reason": str(exc)}


# ============================================================================
# DASHBOARD API — Health, Metrics, Pending Requests, Audit, Stats
# ============================================================================

@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def health_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Deep health check for Traffic Manager / load balancer probes."""
    result = await health_checker.check()
    status_code = 200 if result["status"] == "healthy" else 503
    return func.HttpResponse(
        json.dumps(result, indent=2),
        mimetype="application/json",
        status_code=status_code,
    )


@app.route(route="metrics", methods=["GET"])
async def metrics_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Expose internal metrics snapshot (Prometheus-style)."""
    return func.HttpResponse(
        json.dumps(metrics.snapshot(), indent=2),
        mimetype="application/json",
        status_code=200,
    )


@app.route(route="pending", methods=["GET"])
@app.durable_client_input(client_name="client")
async def pending_requests(
    req: func.HttpRequest,
    client: df.DurableOrchestrationClient,
) -> func.HttpResponse:
    """
    List active (pending) HITL requests for the dashboard.

    Query params:
    - tenant_id: filter by tenant (optional)
    - urgency: filter by urgency (optional)
    - role: filter by required_role (optional)
    """
    tenant_filter = req.params.get("tenant_id")
    urgency_filter = req.params.get("urgency")
    role_filter = req.params.get("role")

    results = []
    for req_id, req_data in _active_requests.items():
        if req_data.get("status") != HITLStatus.PENDING.value:
            continue
        if tenant_filter and req_data.get("tenant_id") != tenant_filter:
            continue
        if urgency_filter and req_data.get("urgency") != urgency_filter:
            continue
        if role_filter and req_data.get("required_role") != role_filter:
            continue

        # Calculate SLA remaining
        created_at = req_data.get("created_at", "")
        urgency = req_data.get("urgency", "NORMAL")
        sla_seconds = settings.sla_timeouts.get(urgency, 3600)
        sla_remaining = None
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                elapsed = (datetime.now(timezone.utc) - created).total_seconds()
                sla_remaining = max(0, int(sla_seconds - elapsed))
            except (ValueError, TypeError):
                pass

        results.append({
            **req_data,
            "sla_deadline_seconds": sla_seconds,
            "sla_remaining_seconds": sla_remaining,
        })

    # Sort by priority (highest first), then urgency (CRITICAL first)
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
    results.sort(key=lambda r: (urgency_order.get(r.get("urgency", "LOW"), 99), -r.get("priority", 0)))

    return func.HttpResponse(
        json.dumps({"count": len(results), "requests": results}),
        mimetype="application/json",
        status_code=200,
    )


@app.route(route="audit/{instance_id}", methods=["GET"])
async def audit_trail(req: func.HttpRequest) -> func.HttpResponse:
    """Return the audit trail for a specific instance."""
    instance_id = req.route_params.get("instance_id", "")
    if not instance_id:
        return func.HttpResponse(
            json.dumps({"error": "instance_id is required"}),
            mimetype="application/json",
            status_code=400,
        )

    events = audit_logger.get_events_for_instance(instance_id)
    return func.HttpResponse(
        json.dumps({"instance_id": instance_id, "events": events}),
        mimetype="application/json",
        status_code=200,
    )


@app.route(route="audit", methods=["GET"])
async def audit_recent(req: func.HttpRequest) -> func.HttpResponse:
    """Return recent audit events across all instances."""
    limit = int(req.params.get("limit", "100"))
    events = audit_logger.get_recent_events(limit=min(limit, 500))
    return func.HttpResponse(
        json.dumps({"count": len(events), "events": events}),
        mimetype="application/json",
        status_code=200,
    )


@app.route(route="stats", methods=["GET"])
async def stats_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Aggregated dashboard statistics."""
    total = len(_active_requests)
    pending = sum(1 for r in _active_requests.values() if r.get("status") == "PENDING")
    approved = sum(1 for r in _active_requests.values() if r.get("status") == "APPROVED")
    rejected = sum(1 for r in _active_requests.values() if r.get("status") == "REJECTED")
    escalated = sum(1 for r in _active_requests.values() if r.get("status") == "ESCALATED")
    unique_agents = len(set(r.get("agent_id", "") for r in _active_requests.values()))

    # Decision duration stats from metrics
    duration_stats = metrics.get_histogram_stats("hitl.decision.duration_seconds")

    return func.HttpResponse(
        json.dumps({
            "total_requests":             total,
            "pending":                    pending,
            "approved":                   approved,
            "rejected":                   rejected,
            "escalated":                  escalated,
            "active_agents":              unique_agents,
            "approval_rate":              round(approved / max(total - pending, 1) * 100, 1),
            "avg_decision_time_seconds":  duration_stats.get("avg", 0),
            "p95_decision_time_seconds":  duration_stats.get("p95", 0),
            "metrics_snapshot":           metrics.snapshot(),
        }),
        mimetype="application/json",
        status_code=200,
    )


# ============================================================================
# TIMER TRIGGER — Weekly CSV Compliance Report (Friday 5 PM UTC)
# ============================================================================
# Enterprise Business Value:
#   Automated weekly reporting eliminates manual data collection for SOX/SOC2
#   compliance audits. The report categorizes all HITL requests by Status
#   (Approved/Rejected/Escalated), Role, and average time-to-resolution.
#   It is automatically delivered via two channels for redundancy:
#     1. Telegram sendDocument API → Admin channel (instant mobile visibility)
#     2. Resend transactional email API → Compliance officer inbox (archivable)
#
# Multi-Stage Escalation Matrix (Telegram -> Voice Call):
#   1. Telegram Message — Immediate delivery of formatted escalation alert
#      with Inline Keyboard Buttons for one-click remediation
#   2. If unacknowledged (2min) — Twilio voice call rings the reviewer's
#      phone once as an emergency pager ("wake-up call")
#   3. Concurrent Slack/Teams notifications for redundant coverage
# ============================================================================

@app.timer_trigger(schedule="0 17 * * 5", arg_name="timer", run_on_startup=False)
async def weekly_report_trigger(timer: func.TimerRequest) -> None:
    """
    Azure Timer Trigger — Fires every Friday at 5:00 PM UTC.

    Generates an in-memory CSV compliance report from the week's HITL audit
    trail and sends it via:
      1. Telegram sendDocument → Admin channel
      2. Resend email API → Compliance officer inbox (CSV attachment)
    """
    import io
    import csv

    logger.info("[WEEKLY REPORT] Timer fired at %s", datetime.now(timezone.utc).isoformat())

    # In production, this would query Azure Cosmos DB for the week's events.
    # For the hackathon MVP, we use the in-memory audit trail.
    events = list(audit_logger.get_recent_events(limit=500))

    if not events:
        logger.info("[WEEKLY REPORT] No events this week — skipping report generation")
        return

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Instance ID", "Agent ID", "Urgency", "Status",
        "Reviewer", "Required Role", "Timestamp", "Resolution Time (s)",
    ])
    for event in events:
        writer.writerow([
            event.get("instance_id", "N/A"),
            event.get("agent_id", "N/A"),
            event.get("urgency", "N/A"),
            event.get("event", "N/A"),
            event.get("reviewer_id", "system"),
            event.get("required_role", "N/A"),
            event.get("timestamp", "N/A"),
            event.get("resolution_seconds", "N/A"),
        ])

    # Summary rows
    total = len(events)
    approved = sum(1 for e in events if e.get("event") == "APPROVED")
    rejected = sum(1 for e in events if e.get("event") == "REJECTED")
    escalated = sum(1 for e in events if e.get("event") == "ESCALATED")
    writer.writerow([])
    writer.writerow(["=== WEEKLY SUMMARY ==="])
    writer.writerow(["Total", total])
    writer.writerow(["Approved", approved])
    writer.writerow(["Rejected", rejected])
    writer.writerow(["Escalated", escalated])
    writer.writerow(["Approval Rate", f"{round(approved / max(total, 1) * 100, 1)}%"])

    csv_string = output.getvalue()
    csv_bytes = csv_string.encode("utf-8")
    output.close()

    # ── Channel 1: Send via Telegram sendDocument ─────────────────────────
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if telegram_bot_token and telegram_chat_id:
        week_str = datetime.now(timezone.utc).strftime("%Y-W%W")
        filename = f"hitl_weekly_report_{week_str}.csv"
        caption = (
            f"📊 <b>HITL Gateway — Weekly Compliance Report</b>\n"
            f"📅 Week: {week_str}\n\n"
            f"✅ Approved: {approved}  ❌ Rejected: {rejected}  ⚠️ Escalated: {escalated}\n"
            f"📈 Total: {total}  |  Approval Rate: {round(approved / max(total, 1) * 100, 1)}%\n\n"
            f"<i>Auto-generated by HITL Gateway Azure Timer Trigger</i>"
        )

        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendDocument"
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.post(
                    url,
                    data={"chat_id": telegram_chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"document": (filename, csv_bytes, "text/csv")},
                )
            if resp.status_code == 200:
                logger.info("[WEEKLY REPORT] Telegram: Report sent to chat_id=%s", telegram_chat_id)
            else:
                logger.error("[WEEKLY REPORT] Telegram upload failed: %s — %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("[WEEKLY REPORT] Telegram error: %s", exc)
    else:
        logger.warning("[WEEKLY REPORT] Telegram not configured — skipping Telegram delivery")

    # ── Channel 2: Send via Resend email API ──────────────────────────────
    # Enterprise Business Value:
    #   Email delivery ensures compliance officers receive an archivable,
    #   searchable copy of the weekly report in their inbox — independent
    #   of Telegram availability. The Resend API provides high deliverability
    #   and native CSV attachment support.
    resend_api_key = os.getenv("RESEND_API_KEY", "")
    report_email = os.getenv("REPORT_EMAIL", "")

    if resend_api_key and report_email:
        try:
            from backend.email_service import send_simple_csv_report
            result = await send_simple_csv_report(csv_string, report_email)
            if result["success"]:
                logger.info("[WEEKLY REPORT] Email: Report sent to %s — id=%s", report_email, result["message_id"])
            else:
                logger.error("[WEEKLY REPORT] Email failed: %s", result["error"])
        except Exception as exc:
            logger.error("[WEEKLY REPORT] Email error: %s", exc)
    else:
        logger.warning("[WEEKLY REPORT] Resend not configured — skipping email delivery")
