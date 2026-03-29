"""
HITL Gateway Dashboard — BFF (Backend for Frontend)
=====================================================
FastAPI service with real-time workflow simulation.
Demonstrates the full Azure Durable Functions HITL lifecycle.
"""
import os
import sys
import asyncio
import random
import uuid
import json
import csv
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import httpx

# Load .env from project root (parent of backend/)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import the isolated Telegram client module
try:
    from backend.telegram_client import (
        send_telegram_message,
        send_telegram_message_with_inline_keyboard,
        send_escalation_summary,
        trigger_emergency_phone_call,
        send_weekly_report,
        generate_weekly_csv_report,
        generate_remediation_drafts,
        TELEGRAM_CHAT_ID,
    )
except ModuleNotFoundError:
    from telegram_client import (
        send_telegram_message,
        send_telegram_message_with_inline_keyboard,
        send_escalation_summary,
        trigger_emergency_phone_call,
        send_weekly_report,
        generate_weekly_csv_report,
        generate_remediation_drafts,
        TELEGRAM_CHAT_ID,
    )

app = FastAPI(title="HITL Gateway BFF", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


async def send_telegram_notification(message: str):
    """Convenience wrapper that sends to the configured default chat."""
    if TELEGRAM_CHAT_ID:
        await send_telegram_message(TELEGRAM_CHAT_ID, message)
    else:
        print(f"[TELEGRAM] Chat ID not configured — skipping")

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

workflows: Dict[str, dict] = {}
audit_log: List[dict] = []
sse_subscribers: List[asyncio.Queue] = []

START_TIME = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = {
    "lateral_movement": {
        "agent_id": "secops-agent-v2",
        "urgency": "CRITICAL",
        "required_role": "SecOps_Lead",
        "sla_seconds": 300,
        "action_description": "Isolate host 10.0.5.42 — anomalous lateral movement detected via SMB/445 targeting domain controller 10.0.1.10",
        "tags": ["security", "lateral-movement", "critical"],
        "context": {
            "source_ip": "10.0.5.42",
            "target_ip": "10.0.1.10",
            "protocol": "SMB/445",
            "confidence": 0.97,
            "ioc_matches": 14,
            "affected_hosts": ["10.0.5.42", "10.0.5.43"],
            "mitre_technique": "T1021.002 - Remote Services: SMB",
        },
        "steps": [
            ("agent_analysis", "AI Agent Analysis", "Ingesting network telemetry from 842 endpoints..."),
            ("agent_analysis", "AI Agent Analysis", "Running anomaly detection model on traffic patterns..."),
            ("threat_detection", "Threat Detection", "RISK THRESHOLD EXCEEDED — Anomalous lateral movement detected (confidence: 97%)"),
            ("threat_detection", "Threat Detection", "14 IOC matches found. MITRE ATT&CK: T1021.002"),
            ("gateway_ingress", "Azure HTTP Trigger", "HITLRequest received at /api/hitl_ingress"),
            ("gateway_ingress", "Azure HTTP Trigger", "Schema validated. Idempotency key generated."),
            ("orchestrator", "Durable Orchestrator", "Orchestration instance started. Racing SLA timer (300s) vs human decision event."),
            ("orchestrator", "Durable Orchestrator", "Durable Timer created — deadline: {deadline}"),
            ("notification", "Teams Notification", "Adaptive Card sent to #secops-alerts channel"),
            ("notification", "Teams Notification", "Reviewer assigned: SecOps_Lead on-call rotation"),
            ("human_review", "Human Review", "Awaiting human decision..."),
        ],
    },
    "data_exfil": {
        "agent_id": "dlp-monitor-v3",
        "urgency": "HIGH",
        "required_role": "SecOps_Lead",
        "sla_seconds": 900,
        "action_description": "Block outbound transfer — 2.3 GB exfiltration from file server FS-PROD-01 to external IP 203.0.113.42",
        "tags": ["security", "data-exfiltration", "dlp"],
        "context": {
            "source_server": "FS-PROD-01",
            "destination_ip": "203.0.113.42",
            "data_volume_gb": 2.3,
            "file_count": 847,
            "classification": "CONFIDENTIAL",
            "protocol": "HTTPS",
            "geo_location": "Unknown — Tor exit node",
        },
        "steps": [
            ("agent_analysis", "AI Agent Analysis", "DLP agent monitoring outbound data flows..."),
            ("agent_analysis", "AI Agent Analysis", "Abnormal transfer volume detected: 2.3 GB to external IP"),
            ("threat_detection", "Threat Detection", "Data classification scan: 847 files marked CONFIDENTIAL"),
            ("threat_detection", "Threat Detection", "Destination IP resolves to Tor exit node — high risk"),
            ("gateway_ingress", "Azure HTTP Trigger", "HITLRequest received at /api/hitl_ingress"),
            ("gateway_ingress", "Azure HTTP Trigger", "Request validated. Priority: HIGH"),
            ("orchestrator", "Durable Orchestrator", "Orchestration started. SLA timer: 900s"),
            ("orchestrator", "Durable Orchestrator", "Durable Timer created — deadline: {deadline}"),
            ("notification", "Teams Notification", "Adaptive Card sent to #secops-alerts"),
            ("human_review", "Human Review", "Awaiting human decision..."),
        ],
    },
    "large_transaction": {
        "agent_id": "finance-agent-v3",
        "urgency": "HIGH",
        "required_role": "Finance_Manager",
        "sla_seconds": 900,
        "action_description": "Approve wire transfer of $847,000 to new vendor Acme Global LLC (first-time payee)",
        "tags": ["finance", "wire-transfer", "first-time-payee"],
        "context": {
            "amount": 847000,
            "currency": "USD",
            "vendor": "Acme Global LLC",
            "account_ending": "4891",
            "first_time_payee": True,
            "budget_remaining": 2400000,
            "department": "Procurement",
        },
        "steps": [
            ("agent_analysis", "AI Agent Analysis", "Finance agent processing wire transfer request..."),
            ("agent_analysis", "AI Agent Analysis", "First-time payee detected — elevated risk"),
            ("threat_detection", "Threat Detection", "Transaction exceeds $100K threshold. Manual approval required."),
            ("gateway_ingress", "Azure HTTP Trigger", "HITLRequest received — financial workflow"),
            ("gateway_ingress", "Azure HTTP Trigger", "Validated. Routing to Finance_Manager role."),
            ("orchestrator", "Durable Orchestrator", "Orchestration started. SLA timer: 900s"),
            ("orchestrator", "Durable Orchestrator", "Durable Timer created — deadline: {deadline}"),
            ("notification", "Teams Notification", "Adaptive Card sent to #finance-approvals"),
            ("human_review", "Human Review", "Awaiting Finance Manager approval..."),
        ],
    },
    "compliance_review": {
        "agent_id": "compliance-bot-v1",
        "urgency": "NORMAL",
        "required_role": "Compliance_Officer",
        "sla_seconds": 3600,
        "action_description": "Auto-remediate 3 PCI-DSS non-compliant configurations on payment processing servers",
        "tags": ["compliance", "pci-dss", "auto-remediation"],
        "context": {
            "framework": "PCI-DSS v4.0",
            "violations": 3,
            "affected_servers": ["PAY-PROD-01", "PAY-PROD-02", "PAY-STAGING"],
            "remediation_type": "automatic",
            "risk_score": 6.2,
        },
        "steps": [
            ("agent_analysis", "AI Agent Analysis", "Compliance bot scanning payment infrastructure..."),
            ("agent_analysis", "AI Agent Analysis", "PCI-DSS v4.0 scan complete: 3 violations found"),
            ("threat_detection", "Threat Detection", "Auto-remediation plan generated for 3 servers"),
            ("gateway_ingress", "Azure HTTP Trigger", "HITLRequest received — compliance workflow"),
            ("orchestrator", "Durable Orchestrator", "Orchestration started. SLA timer: 3600s"),
            ("orchestrator", "Durable Orchestrator", "Durable Timer created — deadline: {deadline}"),
            ("notification", "Teams Notification", "Adaptive Card sent to #compliance-reviews"),
            ("human_review", "Human Review", "Awaiting Compliance Officer review..."),
        ],
    },
    "risk_assessment": {
        "agent_id": "risk-analyzer-v2",
        "urgency": "LOW",
        "required_role": "Risk_Manager",
        "sla_seconds": 86400,
        "action_description": "Deploy quarterly risk model update — 14 rule changes, 3 threshold adjustments",
        "tags": ["risk", "model-deployment", "quarterly"],
        "context": {
            "model_version": "4.2.0",
            "rule_changes": 14,
            "threshold_adjustments": 3,
            "backtest_accuracy": 0.94,
            "deployment_target": "production",
        },
        "steps": [
            ("agent_analysis", "AI Agent Analysis", "Risk analyzer preparing model deployment..."),
            ("agent_analysis", "AI Agent Analysis", "Model v4.2.0 — backtest accuracy: 94%"),
            ("threat_detection", "Threat Detection", "14 rule changes require human sign-off"),
            ("gateway_ingress", "Azure HTTP Trigger", "HITLRequest received — risk workflow"),
            ("orchestrator", "Durable Orchestrator", "Orchestration started. SLA timer: 86400s"),
            ("notification", "Teams Notification", "Adaptive Card sent to #risk-management"),
            ("human_review", "Human Review", "Awaiting Risk Manager review..."),
        ],
    },
}

AGENTS = ["secops-agent-v2", "dlp-monitor-v3", "finance-agent-v3", "compliance-bot-v1", "risk-analyzer-v2"]
ROLES = ["SecOps_Lead", "Finance_Manager", "Compliance_Officer", "Risk_Manager"]
URGENCIES = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
STATUSES = ["PENDING", "APPROVED", "REJECTED", "ESCALATED"]
SLA_MAP = {"CRITICAL": 300, "HIGH": 900, "NORMAL": 3600, "LOW": 86400}

# ---------------------------------------------------------------------------
# SSE Broadcasting
# ---------------------------------------------------------------------------

async def broadcast_event(event: dict):
    """Send event to all SSE subscribers."""
    dead = []
    for q in sse_subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        sse_subscribers.remove(q)


async def event_stream():
    """SSE generator for a single client."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_subscribers.append(q)
    try:
        while True:
            event = await asyncio.wait_for(q.get(), timeout=30.0)
            yield f"data: {json.dumps(event)}\n\n"
    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if q in sse_subscribers:
            sse_subscribers.remove(q)

# ---------------------------------------------------------------------------
# Workflow Simulation
# ---------------------------------------------------------------------------

async def simulate_workflow(instance_id: str, scenario_key: str):
    """Background task: simulate the HITL orchestration flow with timed stages."""
    scenario = SCENARIOS[scenario_key]
    wf = workflows[instance_id]
    deadline = datetime.now(timezone.utc) + timedelta(seconds=scenario["sla_seconds"])

    for stage_id, stage_label, detail in scenario["steps"]:
        if wf.get("_cancelled"):
            return

        detail = detail.replace("{deadline}", deadline.strftime("%H:%M:%S UTC"))
        ts = datetime.now(timezone.utc).isoformat()

        # Update stage status
        for s in wf["stages"]:
            if s["id"] == stage_id and s["status"] != "completed":
                s["status"] = "active"
                s["detail"] = detail
                s["timestamp"] = ts
                break

        # Add event
        event_entry = {
            "timestamp": ts,
            "stage_id": stage_id,
            "stage_label": stage_label,
            "message": detail,
            "type": "warning" if "RISK" in detail or "EXCEEDED" in detail or "violation" in detail else "info",
        }
        wf["events"].append(event_entry)

        # Broadcast to SSE
        await broadcast_event({
            "type": "stage_update",
            "instance_id": instance_id,
            "event": event_entry,
            "stages": wf["stages"],
        })

        # Add audit entry
        if stage_id in ("gateway_ingress", "orchestrator", "notification"):
            audit_log.append({
                "instance_id": instance_id,
                "event": "PENDING",
                "agent_id": scenario["agent_id"],
                "urgency": scenario["urgency"],
                "required_role": scenario.get("required_role", "N/A"),
                "detail": detail,
                "timestamp": ts,
            })

        # Delay between steps
        delay = random.uniform(0.8, 1.5) if stage_id != "human_review" else 0.3
        await asyncio.sleep(delay)

        # Mark stage completed (unless it's human_review which stays waiting)
        if stage_id != "human_review":
            for s in wf["stages"]:
                if s["id"] == stage_id:
                    s["status"] = "completed"
                    break

    # Mark workflow as waiting for human
    wf["status"] = "waiting_for_human"
    wf["waiting_since"] = datetime.now(timezone.utc).isoformat()

    await broadcast_event({
        "type": "waiting_for_human",
        "instance_id": instance_id,
        "stages": wf["stages"],
    })

    # Start SLA timeout monitoring
    asyncio.create_task(monitor_sla_timeout(instance_id, scenario["sla_seconds"]))


async def monitor_sla_timeout(instance_id: str, sla_seconds: int):
    """Monitor SLA timeout and auto-escalate if no decision is made."""
    await asyncio.sleep(sla_seconds)

    wf = workflows.get(instance_id)
    if not wf:
        return

    # Check if still waiting for decision
    if wf["status"] == "waiting_for_human" and not wf.get("decision"):
        now = datetime.now(timezone.utc)

        # Auto-escalate
        wf["decision"] = {
            "status": "ESCALATED",
            "reviewer_id": "system",
            "reason": f"SLA timeout exceeded ({sla_seconds}s) - Auto-escalated to senior reviewer",
            "decided_at": now.isoformat(),
            "auto_escalated": True,
        }

        # Update human_review stage
        for s in wf["stages"]:
            if s["id"] == "human_review":
                s["status"] = "completed"
                s["detail"] = f"ESCALATED by system: SLA timeout - Auto-escalated"
                s["timestamp"] = now.isoformat()
                break

        wf["events"].append({
            "timestamp": now.isoformat(),
            "stage_id": "human_review",
            "stage_label": "Human Review",
            "message": f"⏱️ SLA TIMEOUT - Auto-escalated to senior reviewer",
            "type": "warning",
        })

        await broadcast_event({
            "type": "escalation",
            "instance_id": instance_id,
            "decision": wf["decision"],
            "stages": wf["stages"],
        })

        audit_log.append({
            "instance_id": instance_id,
            "event": "ESCALATED",
            "agent_id": wf["agent_id"],
            "urgency": wf["urgency"],
            "required_role": wf.get("required_role", "N/A"),
            "detail": f"SLA timeout exceeded - Auto-escalated",
            "reviewer_id": "system",
            "timestamp": now.isoformat(),
        })

        # Send Telegram notification via telegram_client (LLM-powered summary)
        if TELEGRAM_CHAT_ID:
            await send_escalation_summary(TELEGRAM_CHAT_ID, {
                "instance_id": instance_id,
                "agent_id": wf["agent_id"],
                "urgency": wf["urgency"],
                "action_description": wf["action_description"],
                "required_role": wf["required_role"],
                "context": wf.get("context", {}),
            })

        # Stage 3: Emergency phone call for CRITICAL urgency
        emergency_phone = os.getenv("EMERGENCY_PHONE_TO", "")
        if emergency_phone and wf["urgency"] == "CRITICAL":
            call_result = await trigger_emergency_phone_call(emergency_phone)
            print(f"[SLA ESCALATION] Emergency call result: {call_result}")

        # Complete the workflow with safe default
        await asyncio.sleep(1.0)

        for s in wf["stages"]:
            if s["id"] == "agent_callback":
                s["status"] = "completed"
                s["detail"] = "Agent applying safe default: passive monitoring."
                s["timestamp"] = datetime.now(timezone.utc).isoformat()
                break

        wf["status"] = "completed"
        wf["completed_at"] = datetime.now(timezone.utc).isoformat()

        wf["events"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage_id": "agent_callback",
            "stage_label": "Agent Callback",
            "message": "Agent applying safe default: passive monitoring.",
            "type": "warning",
        })

        await broadcast_event({
            "type": "workflow_complete",
            "instance_id": instance_id,
            "status": "ESCALATED",
            "stages": wf["stages"],
        })


def create_workflow(scenario_key: str) -> dict:
    """Create a new workflow from a scenario template."""
    scenario = SCENARIOS[scenario_key]
    instance_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(seconds=scenario["sla_seconds"])

    wf = {
        "instance_id": instance_id,
        "scenario": scenario_key,
        "status": "running",
        "created_at": now.isoformat(),
        "agent_id": scenario["agent_id"],
        "urgency": scenario["urgency"],
        "required_role": scenario["required_role"],
        "action_description": scenario["action_description"],
        "tags": scenario["tags"],
        "context": scenario["context"],
        "sla_seconds": scenario["sla_seconds"],
        "sla_deadline": deadline.isoformat(),
        "stages": [
            {"id": "agent_analysis", "label": "AI Agent Analysis", "azure_service": "Agent Runtime", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "threat_detection", "label": "Threat Detection", "azure_service": "AI Model", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "gateway_ingress", "label": "HITL Gateway", "azure_service": "Azure HTTP Trigger", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "orchestrator", "label": "Orchestrator", "azure_service": "Durable Functions", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "notification", "label": "Notification", "azure_service": "Teams / Slack", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "human_review", "label": "Human Review", "azure_service": "Decision Event", "status": "idle", "detail": "", "timestamp": ""},
            {"id": "agent_callback", "label": "Agent Callback", "azure_service": "HTTP Callback", "status": "idle", "detail": "", "timestamp": ""},
        ],
        "events": [],
        "decision": None,
    }

    workflows[instance_id] = wf
    return wf

# ---------------------------------------------------------------------------
# Mock data generators (kept for stats)
# ---------------------------------------------------------------------------

def _mock_stats():
    total = len(audit_log) + random.randint(20, 40)
    pending = len([w for w in workflows.values() if w["status"] in ("running", "waiting_for_human")])
    approved = len([w for w in workflows.values() if w.get("decision", {}) and w["decision"] and w["decision"]["status"] == "APPROVED"])
    rejected = len([w for w in workflows.values() if w.get("decision", {}) and w["decision"] and w["decision"]["status"] == "REJECTED"])
    escalated = len([w for w in workflows.values() if w.get("decision", {}) and w["decision"] and w["decision"]["status"] == "ESCALATED"])
    # Add some baseline numbers
    approved += random.randint(15, 25)
    rejected += random.randint(3, 8)
    escalated += random.randint(1, 4)
    total = pending + approved + rejected + escalated

    return {
        "total_requests": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "escalated": escalated,
        "active_agents": len(set(w["agent_id"] for w in workflows.values())) or len(AGENTS),
        "approval_rate": round((approved / max(approved + rejected, 1)) * 100, 1),
        "avg_decision_time_seconds": round(random.uniform(30, 90), 1),
        "p95_decision_time_seconds": round(random.uniform(200, 400), 1),
        "metrics_snapshot": {},
    }

# ---------------------------------------------------------------------------
# API Endpoints — Existing (Dashboard)
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.1.0",
        "environment": "development",
        "checks": {
            "process": {"status": "ok", "uptime_seconds": round(uptime, 1), "memory_mb": round(random.uniform(120, 180), 1)},
            "durable_storage": {"status": "ok", "note": "Azurite local emulator"},
            "cosmos_db": {"status": "ok", "note": "In-memory mock"},
            "app_insights": {"status": "ok", "note": "Telemetry active"},
        },
    }


@app.get("/api/stats")
async def stats():
    return _mock_stats()


@app.get("/api/metrics")
async def metrics():
    uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    return {
        "uptime_seconds": round(uptime, 1),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "counters": {
            "hitl.requests.total": len(workflows),
            "hitl.decisions.total": len([w for w in workflows.values() if w["decision"]]),
            "hitl.sla.timeouts.total": random.randint(0, 3),
        },
        "histograms": {
            "hitl.decision.duration_seconds": {
                "count": max(len(workflows), 1),
                "avg": round(random.uniform(30, 90), 1),
                "p95": round(random.uniform(200, 400), 1),
            },
        },
        "gauges": {
            "hitl.pending.count": len([w for w in workflows.values() if w["status"] in ("running", "waiting_for_human")]),
            "hitl.active_agents": len(set(w["agent_id"] for w in workflows.values())) or 4,
        },
    }


# ---------------------------------------------------------------------------
# API Endpoints — Live Workflow
# ---------------------------------------------------------------------------

@app.get("/api/scenarios")
async def list_scenarios():
    return {
        name: {
            "urgency": s["urgency"],
            "required_role": s["required_role"],
            "agent_id": s["agent_id"],
            "description": s["action_description"],
            "tags": s["tags"],
            "sla_seconds": s["sla_seconds"],
        }
        for name, s in SCENARIOS.items()
    }


@app.post("/api/trigger/{scenario}")
async def trigger_scenario(scenario: str, background_tasks: BackgroundTasks):
    if scenario not in SCENARIOS:
        return {"error": f"Unknown scenario: {scenario}"}, 400

    wf = create_workflow(scenario)
    background_tasks.add_task(simulate_workflow, wf["instance_id"], scenario)

    audit_log.append({
        "instance_id": wf["instance_id"],
        "event": "TRIGGERED",
        "agent_id": wf["agent_id"],
        "urgency": wf["urgency"],
        "required_role": wf.get("required_role", "N/A"),
        "detail": f"Scenario '{scenario}' triggered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "instance_id": wf["instance_id"],
        "scenario": scenario,
        "status": "started",
        "agent_id": wf["agent_id"],
        "urgency": wf["urgency"],
    }


@app.get("/api/workflow/{instance_id}")
async def get_workflow(instance_id: str):
    wf = workflows.get(instance_id)
    if not wf:
        return {"error": "Workflow not found"}, 404

    # Calculate remaining SLA
    if wf["status"] in ("running", "waiting_for_human"):
        deadline = datetime.fromisoformat(wf["sla_deadline"])
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        wf["sla_remaining_seconds"] = max(0, round(remaining))
    else:
        wf["sla_remaining_seconds"] = 0

    return wf


@app.post("/api/decide/{instance_id}")
async def submit_decision(instance_id: str, body: dict):
    wf = workflows.get(instance_id)
    if not wf:
        return {"error": "Workflow not found"}, 404
    if wf["status"] not in ("waiting_for_human", "running"):
        return {"error": "Workflow not in reviewable state"}, 400

    status = body.get("status", "APPROVED").upper()
    reviewer = body.get("reviewer_id", "jane.doe@contoso.com")
    reason = body.get("reason", "Reviewed and approved")

    now = datetime.now(timezone.utc)
    wf["decision"] = {
        "status": status,
        "reviewer_id": reviewer,
        "reason": reason,
        "decided_at": now.isoformat(),
    }

    # Update human_review stage
    for s in wf["stages"]:
        if s["id"] == "human_review":
            s["status"] = "completed"
            s["detail"] = f"{status} by {reviewer}: {reason}"
            s["timestamp"] = now.isoformat()
            break

    wf["events"].append({
        "timestamp": now.isoformat(),
        "stage_id": "human_review",
        "stage_label": "Human Review",
        "message": f"Decision: {status} by {reviewer} — \"{reason}\"",
        "type": "success" if status == "APPROVED" else "error" if status == "REJECTED" else "warning",
    })

    await broadcast_event({
        "type": "decision",
        "instance_id": instance_id,
        "decision": wf["decision"],
        "stages": wf["stages"],
    })

    audit_log.append({
        "instance_id": instance_id,
        "event": status,
        "agent_id": wf["agent_id"],
        "urgency": wf["urgency"],
        "required_role": wf.get("required_role", "N/A"),
        "detail": f"{status} by {reviewer}: {reason}",
        "reviewer_id": reviewer,
        "timestamp": now.isoformat(),
    })

    # Send Telegram notification if escalated (uses LLM-powered summary from telegram_client)
    if status == "ESCALATED" and TELEGRAM_CHAT_ID:
        await send_escalation_summary(TELEGRAM_CHAT_ID, {
            "instance_id": instance_id,
            "agent_id": wf["agent_id"],
            "urgency": wf["urgency"],
            "action_description": wf["action_description"],
            "required_role": wf["required_role"],
            "context": wf.get("context", {}),
        })

    # Simulate agent callback (async)
    await asyncio.sleep(1.0)

    for s in wf["stages"]:
        if s["id"] == "agent_callback":
            s["status"] = "active"
            s["detail"] = "Delivering decision to agent..."
            s["timestamp"] = datetime.now(timezone.utc).isoformat()
            break

    wf["events"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage_id": "agent_callback",
        "stage_label": "Agent Callback",
        "message": f"Callback delivered to {wf['agent_id']}. Status: {status}",
        "type": "info",
    })

    await broadcast_event({
        "type": "stage_update",
        "instance_id": instance_id,
        "event": wf["events"][-1],
        "stages": wf["stages"],
    })

    await asyncio.sleep(0.8)

    # Final completion
    action_result = {
        "APPROVED": f"Agent executing action: {wf['action_description']}",
        "REJECTED": "Agent standing down. Action cancelled.",
        "ESCALATED": "Agent applying safe default: passive monitoring.",
    }.get(status, "Unknown")

    for s in wf["stages"]:
        if s["id"] == "agent_callback":
            s["status"] = "completed"
            s["detail"] = action_result
            s["timestamp"] = datetime.now(timezone.utc).isoformat()
            break

    wf["status"] = "completed"
    wf["completed_at"] = datetime.now(timezone.utc).isoformat()

    wf["events"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage_id": "agent_callback",
        "stage_label": "Agent Callback",
        "message": action_result,
        "type": "success" if status == "APPROVED" else "error" if status == "REJECTED" else "warning",
    })

    await broadcast_event({
        "type": "workflow_complete",
        "instance_id": instance_id,
        "status": status,
        "stages": wf["stages"],
    })

    audit_log.append({
        "instance_id": instance_id,
        "event": "COMPLETE",
        "agent_id": wf["agent_id"],
        "urgency": wf["urgency"],
        "required_role": wf.get("required_role", "N/A"),
        "detail": action_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"status": "decided", "decision": wf["decision"], "result": action_result}


@app.get("/api/workflows")
async def list_workflows():
    result = []
    for wf in workflows.values():
        # Recalculate SLA
        if wf["status"] in ("running", "waiting_for_human"):
            deadline = datetime.fromisoformat(wf["sla_deadline"])
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            wf["sla_remaining_seconds"] = max(0, round(remaining))
        result.append(wf)
    result.sort(key=lambda w: (
        {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}.get(w["urgency"], 4),
        w["created_at"],
    ))
    return {"count": len(result), "workflows": result}


@app.get("/api/pending")
async def pending():
    pending_wfs = [w for w in workflows.values() if w["status"] in ("running", "waiting_for_human")]
    for wf in pending_wfs:
        deadline = datetime.fromisoformat(wf["sla_deadline"])
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        wf["sla_remaining_seconds"] = max(0, round(remaining))

    pending_wfs.sort(key=lambda w: (
        {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}.get(w["urgency"], 4),
        w["created_at"],
    ))
    requests = [{
        "instance_id": w["instance_id"],
        "agent_id": w["agent_id"],
        "action_description": w["action_description"],
        "required_role": w["required_role"],
        "urgency": w["urgency"],
        "status": "PENDING",
        "tags": w["tags"],
        "created_at": w["created_at"],
        "sla_deadline_seconds": w["sla_seconds"],
        "sla_remaining_seconds": w.get("sla_remaining_seconds", 0),
        "context": w["context"],
    } for w in pending_wfs]
    return {"count": len(requests), "requests": requests}


@app.get("/api/audit")
async def audit(limit: int = 100):
    events = sorted(audit_log, key=lambda e: e["timestamp"], reverse=True)[:limit]
    return {"count": len(events), "events": events}


@app.get("/api/audit/csv")
async def audit_csv(
    urgency: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
):
    """Download audit trail as CSV with optional filters."""
    events = sorted(audit_log, key=lambda e: e["timestamp"], reverse=True)

    # Apply filters
    if urgency:
        events = [e for e in events if e.get("urgency", "").upper() == urgency.upper()]
    if event:
        events = [e for e in events if e.get("event", "").upper() == event.upper()]
    if role:
        events = [e for e in events if role.lower() in e.get("required_role", "").lower()]
    if since:
        events = [e for e in events if e.get("timestamp", "") >= since]
    if until:
        events = [e for e in events if e.get("timestamp", "") <= until]

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Instance ID", "Event", "Agent ID", "Urgency", "Required Role",
        "Reviewer", "Detail", "Timestamp",
    ])
    for ev in events:
        writer.writerow([
            ev.get("instance_id", "N/A"),
            ev.get("event", "N/A"),
            ev.get("agent_id", "N/A"),
            ev.get("urgency", "N/A"),
            ev.get("required_role", "N/A"),
            ev.get("reviewer_id", "N/A"),
            ev.get("detail", "N/A"),
            ev.get("timestamp", "N/A"),
        ])

    # Summary
    writer.writerow([])
    total = len(events)
    approved = sum(1 for e in events if e.get("event") == "APPROVED")
    rejected = sum(1 for e in events if e.get("event") == "REJECTED")
    escalated = sum(1 for e in events if e.get("event") == "ESCALATED")
    writer.writerow(["Summary"])
    writer.writerow(["Total Events", total])
    writer.writerow(["Approved", approved])
    writer.writerow(["Rejected", rejected])
    writer.writerow(["Escalated", escalated])
    if total > 0:
        rate = round(approved / max(1, approved + rejected + escalated) * 100, 1)
        writer.writerow(["Approval Rate", f"{rate}%"])

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="hitl_audit_{now_str}.csv"'},
    )


@app.get("/api/events")
async def sse_events():
    """Server-Sent Events stream for real-time updates."""
    async def generate():
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        sse_subscribers.append(q)
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in sse_subscribers:
                sse_subscribers.remove(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/reset")
async def reset():
    """Reset all workflows and audit log."""
    workflows.clear()
    audit_log.clear()
    return {"status": "reset", "message": "All workflows and audit data cleared"}


# ---------------------------------------------------------------------------
# Weekly Report Endpoint (mirrors the Azure Timer Trigger for demo/manual use)
# ---------------------------------------------------------------------------

@app.post("/api/report/weekly")
async def generate_and_send_weekly_report():
    """
    Generate and send the weekly HITL compliance report to Telegram.

    Enterprise Business Value:
        This endpoint mirrors the Azure Timer Trigger (schedule="0 17 * * 5")
        that runs every Friday at 5:00 PM UTC. It generates an in-memory CSV
        that categorizes the week's HITL requests by Status, Role, and average
        time-to-resolution, then blasts it to the C-Suite / Admin Telegram chat
        via the sendDocument API.

        In production, this data would be sourced from Azure Cosmos DB.
        For the hackathon demo, it uses the in-memory audit log with
        supplemental mock data to show a realistic report.
    """
    # Combine real audit data with mock data for a fuller report
    mock_events = [
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "secops-agent-v2", "urgency": "CRITICAL", "event": "APPROVED", "reviewer_id": "jane.doe@contoso.com", "required_role": "SecOps_Lead", "detail": "Isolate compromised host — verified lateral movement", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 145},
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "dlp-monitor-v3", "urgency": "HIGH", "event": "REJECTED", "reviewer_id": "john.smith@contoso.com", "required_role": "SecOps_Lead", "detail": "Block outbound transfer — false positive confirmed", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 312},
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "finance-agent-v3", "urgency": "HIGH", "event": "APPROVED", "reviewer_id": "sarah.chen@contoso.com", "required_role": "Finance_Manager", "detail": "Wire transfer $847K to Acme Global — verified vendor", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 89},
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "compliance-bot-v1", "urgency": "NORMAL", "event": "APPROVED", "reviewer_id": "mike.johnson@contoso.com", "required_role": "Compliance_Officer", "detail": "Auto-remediate 3 PCI-DSS violations", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 1800},
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "secops-agent-v2", "urgency": "CRITICAL", "event": "ESCALATED", "reviewer_id": "system", "required_role": "SecOps_Lead", "detail": "SLA timeout — auto-escalated to senior reviewer", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 300},
        {"instance_id": str(uuid.uuid4())[:8], "agent_id": "risk-analyzer-v2", "urgency": "LOW", "event": "APPROVED", "reviewer_id": "lisa.wang@contoso.com", "required_role": "Risk_Manager", "detail": "Risk model update v4.2.0 — approved for production", "timestamp": datetime.now(timezone.utc).isoformat(), "resolution_seconds": 43200},
    ]

    all_events = audit_log + mock_events

    if not TELEGRAM_CHAT_ID:
        # Generate CSV but can't send — return it as JSON preview
        csv_bytes = generate_weekly_csv_report(all_events)
        return {
            "status": "generated",
            "note": "TELEGRAM_CHAT_ID not configured — report generated but not sent",
            "event_count": len(all_events),
            "csv_preview": csv_bytes.decode("utf-8")[:1000],
        }

    success = await send_weekly_report(TELEGRAM_CHAT_ID, all_events)
    return {
        "status": "sent" if success else "failed",
        "event_count": len(all_events),
        "chat_id": TELEGRAM_CHAT_ID,
    }


# ---------------------------------------------------------------------------
# Test Endpoints — Manual integration testing for Telegram, Twilio, Email
# ---------------------------------------------------------------------------

@app.post("/api/test/telegram")
async def test_telegram():
    """Send a test Telegram message with inline keyboard buttons."""
    chat_id = TELEGRAM_CHAT_ID
    if not chat_id:
        return {"status": "error", "detail": "TELEGRAM_CHAT_ID not configured"}

    test_data = {
        "instance_id": "test-" + str(uuid.uuid4())[:8],
        "agent_id": "secops-agent-v2",
        "urgency": "CRITICAL",
        "action_description": "TEST: Isolate compromised endpoint 10.0.0.42",
        "required_role": "SecOps_Lead",
        "context": {"source_ip": "10.0.0.42", "alert_type": "Lateral Movement Detected"},
    }

    result = await send_escalation_summary(chat_id, test_data)
    return {"status": "sent" if result else "failed", "chat_id": chat_id}


@app.post("/api/test/call")
async def test_call():
    """Trigger a test emergency phone call via Twilio."""
    phone = os.getenv("EMERGENCY_PHONE_TO", "")
    if not phone:
        return {"status": "error", "detail": "EMERGENCY_PHONE_TO not configured in .env"}

    result = await trigger_emergency_phone_call(phone)
    return result


@app.post("/api/test/sms")
async def test_sms():
    """Send a test SMS via Twilio."""
    phone = os.getenv("EMERGENCY_PHONE_TO", "")
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_PHONE_NUMBER", "")

    if not all([phone, twilio_sid, twilio_token, twilio_from]):
        return {"status": "error", "detail": "Twilio credentials or EMERGENCY_PHONE_TO not configured"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                data={
                    "To": phone,
                    "From": twilio_from,
                    "Body": "🚨 HITL Gateway Test: Critical security request pending your review. Check Telegram or dashboard immediately.",
                },
                auth=(twilio_sid, twilio_token),
                timeout=15.0,
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                return {"status": "sent", "sid": result.get("sid"), "to": phone}
            else:
                return {"status": "error", "code": resp.status_code, "detail": resp.text}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/api/test/email")
async def test_email():
    """Send a test weekly CSV report via Resend email."""
    try:
        from backend.email_service import send_simple_csv_report
    except ModuleNotFoundError:
        from email_service import send_simple_csv_report
    report_email = os.getenv("REPORT_EMAIL", "")
    if not report_email:
        return {"status": "error", "detail": "REPORT_EMAIL not configured"}

    test_events = audit_log + [
        {"instance_id": "test-001", "agent_id": "secops-agent-v2", "urgency": "CRITICAL",
         "event": "APPROVED", "reviewer_id": "test@contoso.com", "required_role": "SecOps_Lead",
         "detail": "Test event for email delivery", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]
    csv_bytes = generate_weekly_csv_report(test_events)
    result = send_simple_csv_report(csv_bytes.decode("utf-8"), report_email)
    return {"status": "sent" if result else "failed", "to": report_email}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
