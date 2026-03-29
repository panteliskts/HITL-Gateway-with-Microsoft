"""
agent_mock.py — Enterprise Edge AI Agent (Upgraded)
=====================================================
A FastAPI service simulating an autonomous AI agent with enterprise features:

Improvements over MVP
---------------------
- **Concurrent HITL support**: multiple workflows can run simultaneously
- **Idempotent callbacks**: duplicate decisions are safely ignored
- **State tracking**: per-instance state machine with full history
- **CORS support**: ready for dashboard integration
- **Health & readiness probes**: Kubernetes/Azure-native
- **Configurable scenarios**: multiple threat profiles for demo variety

Endpoints
---------
  POST /trigger                  Start a simulated AI workflow
  POST /trigger/{scenario}       Start a specific scenario (lateral_movement, data_exfil, etc.)
  POST /resume_agent             Receive HITLResponse callback from Gateway
  GET  /status                   Current agent state (all workflows)
  GET  /status/{instance_id}     State for a specific workflow
  GET  /health                   Health probe
  GET  /ready                    Readiness probe
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gateway.schemas import HITLRequest, HITLResponse, HITLStatus, UrgencyLevel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | [agent] %(message)s",
)
logger = logging.getLogger("agent_mock")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GATEWAY_URL:  str = os.getenv("GATEWAY_URL",  "http://localhost:7072/api")
AGENT_PORT:   int = int(os.getenv("AGENT_PORT", "7071"))
CALLBACK_URL: str = os.getenv("CALLBACK_URL", f"http://localhost:{AGENT_PORT}/resume_agent")
AGENT_ID:     str = os.getenv("AGENT_ID", "secops-agent-v2")
API_KEY:      str = os.getenv("HITL_API_KEY", "")  # Sent to gateway if configured
TENANT_ID:    str = os.getenv("HITL_TENANT_ID", "default")

# ---------------------------------------------------------------------------
# Per-instance state tracking (supports concurrent HITL workflows)
# ---------------------------------------------------------------------------

class WorkflowState:
    """State for a single HITL workflow instance."""
    __slots__ = ("instance_id", "scenario", "status", "created_at",
                 "decided_at", "result", "pause_event")

    def __init__(self, instance_id: str, scenario: str) -> None:
        self.instance_id = instance_id
        self.scenario = scenario
        self.status = "SUSPENDED"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.decided_at: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.pause_event = asyncio.Event()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario": self.scenario,
            "status": self.status,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "result": self.result,
        }


# Active workflows keyed by instance_id
_workflows: Dict[str, WorkflowState] = {}

# Processed instance IDs for idempotent callback handling
_processed_instances: set = set()

# ---------------------------------------------------------------------------
# Threat scenarios for demo variety
# ---------------------------------------------------------------------------

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "lateral_movement": {
        "urgency": UrgencyLevel.CRITICAL,
        "required_role": "SecOps_Lead",
        "action_description": (
            "Detected anomalous lateral movement from host 10.0.5.42 "
            "targeting domain controller 10.0.1.10 over SMB (port 445). "
            "Proposed action: isolate host and revoke credentials. "
            "This action is irreversible without manual re-provisioning."
        ),
        "context": {
            "source_ip": "10.0.5.42",
            "target_ip": "10.0.1.10",
            "protocol": "SMB/445",
            "confidence": 0.97,
            "model_version": "threat-detector-v4.1",
            "mitre_technique": "T1021 - Remote Services",
        },
        "tags": ["security", "lateral-movement", "critical"],
    },
    "data_exfil": {
        "urgency": UrgencyLevel.HIGH,
        "required_role": "SecOps_Lead",
        "action_description": (
            "Large data transfer detected: 2.3 GB exfiltrated from file server "
            "FS-PROD-01 to external IP 203.0.113.42 (GeoIP: Unknown). "
            "Proposed action: block external IP and quarantine source user."
        ),
        "context": {
            "source_host": "FS-PROD-01",
            "destination_ip": "203.0.113.42",
            "data_volume_gb": 2.3,
            "confidence": 0.89,
            "affected_user": "jsmith@contoso.com",
            "mitre_technique": "T1048 - Exfiltration Over Alternative Protocol",
        },
        "tags": ["security", "data-exfiltration"],
    },
    "large_transaction": {
        "urgency": UrgencyLevel.HIGH,
        "required_role": "Finance_Manager",
        "action_description": (
            "Wire transfer of $847,000 to new vendor account (first-time payee). "
            "Vendor: Acme Global LLC. Account verification pending. "
            "Proposed action: execute wire transfer."
        ),
        "context": {
            "amount_usd": 847000,
            "vendor": "Acme Global LLC",
            "account_verified": False,
            "requester": "procurement-bot-v3",
            "invoice_id": "INV-2026-04821",
        },
        "tags": ["finance", "wire-transfer", "first-time-payee"],
    },
    "compliance_review": {
        "urgency": UrgencyLevel.NORMAL,
        "required_role": "Compliance_Officer",
        "action_description": (
            "Automated PCI-DSS scan flagged 3 non-compliant configurations on "
            "payment processing servers. Proposed action: auto-remediate by "
            "applying security patches and rotating TLS certificates."
        ),
        "context": {
            "scan_id": "PCI-2026-Q1-0047",
            "findings_count": 3,
            "severity": "medium",
            "affected_servers": ["pay-proc-01", "pay-proc-02", "pay-proc-03"],
            "remediation_type": "auto-patch",
        },
        "tags": ["compliance", "pci-dss", "auto-remediation"],
    },
    "risk_assessment": {
        "urgency": UrgencyLevel.LOW,
        "required_role": "Risk_Manager",
        "action_description": (
            "Quarterly risk model update ready for deployment. "
            "14 rule changes, 3 threshold adjustments. "
            "Proposed action: deploy updated risk model to production."
        ),
        "context": {
            "model_version": "risk-model-v7.2",
            "rule_changes": 14,
            "threshold_adjustments": 3,
            "backtest_accuracy": 0.94,
        },
        "tags": ["risk", "model-deployment"],
    },
}

# ---------------------------------------------------------------------------
# FastAPI app with CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HITL Edge Agent (Enterprise)",
    version="2.0.0",
    description=(
        "Simulated AI agent with concurrent HITL support, "
        "idempotent callbacks, and multiple threat scenarios."
    ),
)

# CORS — allow dashboard frontends to call this agent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set to specific dashboard origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# POST /resume_agent — Callback from the Azure Gateway
# ============================================================================

@app.post("/resume_agent", status_code=200)
async def resume_agent(request: Request) -> JSONResponse:
    """
    Receives HITLResponse with idempotent duplicate handling.
    """
    body: Dict[str, Any] = await request.json()
    logger.info("[AGENT] /resume_agent called | body=%s", body)

    try:
        hitl_response = HITLResponse(**body)
    except Exception as exc:
        logger.error("[AGENT] Invalid HITLResponse: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=422)

    # ── Idempotency: ignore duplicate callbacks ──────────────────────────────
    if hitl_response.instance_id in _processed_instances:
        logger.info(
            "[AGENT] Duplicate callback ignored | instance_id=%s",
            hitl_response.instance_id,
        )
        return JSONResponse({
            "acknowledged": True,
            "duplicate": True,
            "instance_id": hitl_response.instance_id,
        })

    _processed_instances.add(hitl_response.instance_id)

    # ── Update workflow state ────────────────────────────────────────────────
    workflow = _workflows.get(hitl_response.instance_id)
    if workflow:
        workflow.status = f"RESOLVED_{hitl_response.status.value}"
        workflow.decided_at = datetime.now(timezone.utc).isoformat()
        workflow.result = hitl_response.model_dump()
        workflow.pause_event.set()  # Unblock the suspended /trigger request

    # ── Act on the decision ──────────────────────────────────────────────────
    logger.info("========== CALLBACK RECEIVED ==========")
    logger.info("Instance  : %s", hitl_response.instance_id)
    logger.info("Status    : %s", hitl_response.status.value)
    logger.info("Reviewer  : %s", hitl_response.reviewer_id)
    logger.info("Reason    : %s", hitl_response.reason)
    logger.info("Dry Run   : %s", hitl_response.dry_run)
    logger.info("=======================================")

    if hitl_response.dry_run:
        logger.info("[AGENT] DRY RUN — no action taken | instance_id=%s", hitl_response.instance_id)
    elif hitl_response.status == HITLStatus.APPROVED:
        logger.info("[AGENT] APPROVED by '%s' — executing action | instance_id=%s",
                     hitl_response.reviewer_id, hitl_response.instance_id)
    elif hitl_response.status == HITLStatus.REJECTED:
        logger.warning("[AGENT] REJECTED by '%s' — aborting | instance_id=%s",
                        hitl_response.reviewer_id, hitl_response.instance_id)
    else:
        logger.error("[AGENT] ESCALATED — applying safe default | instance_id=%s",
                      hitl_response.instance_id)

    return JSONResponse({
        "acknowledged":  True,
        "duplicate":     False,
        "agent_status":  "resumed",
        "hitl_decision": hitl_response.status.value,
        "instance_id":   hitl_response.instance_id,
    })


# ============================================================================
# POST /trigger — Start a simulated AI workflow
# POST /trigger/{scenario} — Start a specific scenario
# ============================================================================

@app.post("/trigger", status_code=200)
async def trigger_default() -> JSONResponse:
    """Trigger the default lateral_movement scenario."""
    return await _run_scenario("lateral_movement")


@app.post("/trigger/{scenario}", status_code=200)
async def trigger_scenario(scenario: str) -> JSONResponse:
    """Trigger a specific threat scenario."""
    if scenario not in SCENARIOS:
        return JSONResponse(
            {
                "error": f"Unknown scenario: {scenario}",
                "available": list(SCENARIOS.keys()),
            },
            status_code=400,
        )
    return await _run_scenario(scenario)


async def _run_scenario(scenario: str) -> JSONResponse:
    """Core workflow logic for all scenarios."""
    scenario_config = SCENARIOS[scenario]

    logger.info("[AGENT] --- %s Workflow Starting ---", scenario.upper())

    logger.info("[AGENT] Step 1/4 — Ingesting telemetry ...")
    await asyncio.sleep(0.3)

    logger.info("[AGENT] Step 2/4 — Running detection model ...")
    await asyncio.sleep(0.5)

    logger.warning("[AGENT] Step 3/4 — RISK THRESHOLD EXCEEDED for scenario: %s", scenario)
    await asyncio.sleep(0.2)

    logger.info("[AGENT] Step 4/4 — Constructing HITLRequest ...")

    # ── Build the HITL request ──────────────────────────────────────────────
    idempotency_key = str(uuid.uuid4())
    context = {
        **scenario_config["context"],
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
    }

    hitl_request = HITLRequest(
        agent_id=AGENT_ID,
        required_role=scenario_config["required_role"],
        urgency=scenario_config["urgency"],
        action_description=scenario_config["action_description"],
        callback_url=CALLBACK_URL,
        idempotency_key=idempotency_key,
        context=context,
        tenant_id=TENANT_ID,
        tags=scenario_config.get("tags", []),
    )

    # ── POST to the Gateway ─────────────────────────────────────────────────
    ingest_url = f"{GATEWAY_URL}/hitl_ingress"
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    logger.info("[AGENT] POSTing to gateway | url=%s urgency=%s", ingest_url, hitl_request.urgency.value)

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                ingest_url,
                json=hitl_request.model_dump(),
                headers=headers,
            )
            resp.raise_for_status()
            gateway_response: Dict[str, Any] = resp.json()
    except Exception as exc:
        logger.error("[AGENT] Gateway unreachable at %s — error=%s", ingest_url, exc)
        return JSONResponse({"error": f"Cannot reach gateway: {exc}"}, status_code=502)

    instance_id = gateway_response.get("instance_id", idempotency_key)

    # ── Track workflow state ────────────────────────────────────────────────
    workflow = WorkflowState(instance_id=instance_id, scenario=scenario)
    _workflows[instance_id] = workflow

    logger.info("[AGENT] SUSPENDED — instance_id=%s scenario=%s", instance_id, scenario)
    logger.info(
        '[AGENT] Approve with: curl -X POST %s/teams_webhook_callback/%s '
        '-H "Content-Type: application/json" '
        '-d \'{"status":"APPROVED","reviewer_id":"you@contoso.com","reason":"Reviewed."}\'',
        GATEWAY_URL, instance_id,
    )

    # ── Block until decision ────────────────────────────────────────────────
    logger.info("[AGENT] Request BLOCKING — awaiting decision ...")
    await workflow.pause_event.wait()
    logger.info("[AGENT] Request UNBLOCKED — decision received.")

    return JSONResponse({
        "status":          "resumed",
        "instance_id":     instance_id,
        "scenario":        scenario,
        "idempotency_key": gateway_response.get("idempotency_key"),
        "callback_url":    CALLBACK_URL,
        "decision":        workflow.result,
    })


# ============================================================================
# GET /status — Agent state overview
# ============================================================================

@app.get("/status")
async def agent_status() -> JSONResponse:
    """Overview of all workflows."""
    return JSONResponse({
        "agent_id": AGENT_ID,
        "tenant_id": TENANT_ID,
        "total_workflows": len(_workflows),
        "active_workflows": sum(1 for w in _workflows.values() if w.status == "SUSPENDED"),
        "processed_callbacks": len(_processed_instances),
        "workflows": {
            wid: w.to_dict() for wid, w in list(_workflows.items())[-20:]
        },
        "available_scenarios": list(SCENARIOS.keys()),
    })


@app.get("/status/{instance_id}")
async def workflow_status(instance_id: str) -> JSONResponse:
    """State for a specific workflow."""
    workflow = _workflows.get(instance_id)
    if not workflow:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    return JSONResponse(workflow.to_dict())


# ============================================================================
# Health & Readiness probes
# ============================================================================

@app.get("/health")
async def health() -> JSONResponse:
    """Liveness probe — is the process alive?"""
    return JSONResponse({"status": "healthy", "agent_id": AGENT_ID})


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe — can we accept traffic?"""
    return JSONResponse({
        "status": "ready",
        "agent_id": AGENT_ID,
        "gateway_url": GATEWAY_URL,
    })


# ============================================================================
# GET /scenarios — List available scenarios
# ============================================================================

@app.get("/scenarios")
async def list_scenarios() -> JSONResponse:
    """List all available threat scenarios with metadata."""
    return JSONResponse({
        "scenarios": {
            name: {
                "urgency": config["urgency"].value,
                "required_role": config["required_role"],
                "description": config["action_description"][:100] + "...",
                "tags": config.get("tags", []),
            }
            for name, config in SCENARIOS.items()
        }
    })


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "agents.agent_mock:app",
        host="0.0.0.0",
        port=AGENT_PORT,
        reload=False,
        log_level="info",
    )
