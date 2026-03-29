"""
telegram_client.py — Isolated Telegram Notification Module
============================================================
Enterprise Business Value:
    This module provides a multi-stage escalation matrix for critical HITL decisions.
    When an AI agent escalates a request, the system:
      1. Generates a 2-sentence executive summary of the technical payload
      2. Sends a formatted Telegram alert to the C-Suite / SecOps channel
      3. If unacknowledged within 2 minutes, triggers an emergency phone call
         via Azure Communication Services as a "wake-up call" pager

    This ensures that CRITICAL and HIGH-urgency decisions are never missed,
    even if the human reviewer is away from their desk.
"""
import os
import io
import csv
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Configuration — loaded once at import time
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

# Dashboard base URL for deep-link review buttons
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")

URGENCY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "NORMAL": "🟡",
    "LOW": "🟢",
}


# ---------------------------------------------------------------------------
# Core: Send a Telegram text message
# ---------------------------------------------------------------------------

async def send_telegram_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a text message to a Telegram chat. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] Bot token not configured — skipping message")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            if resp.status_code == 200:
                print(f"[TELEGRAM] Message sent to chat_id={chat_id}")
                return True
            else:
                print(f"[TELEGRAM] Failed: {resp.status_code} — {resp.text}")
                return False
    except Exception as exc:
        print(f"[TELEGRAM] Error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Core: Send a Telegram message with Inline Keyboard Buttons
# ---------------------------------------------------------------------------
# Enterprise Business Value:
#   Inline Keyboard Buttons allow admins to take remediation actions
#   directly from within the Telegram chat — no need to context-switch
#   to the dashboard. Each button POSTs a callback_data string that can
#   be handled by a Telegram Bot webhook to route the decision back into
#   the HITL Gateway's teams_webhook_callback endpoint.
# ---------------------------------------------------------------------------

async def send_telegram_message_with_inline_keyboard(
    chat_id: str,
    text: str,
    inline_buttons: list,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send a text message with Telegram Inline Keyboard Buttons.

    Args:
        chat_id: Target Telegram chat ID.
        text: The message body (HTML formatted).
        inline_buttons: List of dicts with 'text' and 'callback_data' keys.
                        These render as clickable buttons beneath the message.
        parse_mode: Telegram parse mode (default HTML).

    Returns:
        True on success, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] Bot token not configured — skipping inline keyboard message")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Build the inline_keyboard layout — one button per row for clarity
    keyboard_rows = [
        [{"text": btn["text"], "callback_data": btn["callback_data"]}]
        for btn in inline_buttons
    ]

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": keyboard_rows,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            if resp.status_code == 200:
                print(f"[TELEGRAM] Inline keyboard message sent to chat_id={chat_id}")
                return True
            else:
                print(f"[TELEGRAM] Inline keyboard failed: {resp.status_code} — {resp.text}")
                return False
    except Exception as exc:
        print(f"[TELEGRAM] Inline keyboard error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Core: Send a Telegram document (file upload)
# ---------------------------------------------------------------------------

async def send_telegram_document(
    chat_id: str,
    file_bytes: bytes,
    filename: str,
    caption: str = "",
) -> bool:
    """Upload a file to a Telegram chat via sendDocument. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] Bot token not configured — skipping document")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"document": (filename, file_bytes, "text/csv")},
                timeout=30.0,
            )
            if resp.status_code == 200:
                print(f"[TELEGRAM] Document '{filename}' sent to chat_id={chat_id}")
                return True
            else:
                print(f"[TELEGRAM] Document upload failed: {resp.status_code} — {resp.text}")
                return False
    except Exception as exc:
        print(f"[TELEGRAM] Document error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Executive Summary Generator (LLM-powered in production)
# ---------------------------------------------------------------------------

def generate_executive_summary(hitl_request_data: Dict[str, Any]) -> str:
    """
    Generate a 2-sentence executive summary from a technical HITL payload.

    In production, this would call Azure OpenAI / GPT-4 to distill the payload.
    For the hackathon demo, we use a deterministic template-based approach
    that covers the key facts a C-suite executive needs to know.
    """
    agent_id = hitl_request_data.get("agent_id", "unknown-agent")
    urgency = hitl_request_data.get("urgency", "NORMAL")
    action = hitl_request_data.get("action_description", "perform an action")
    role = hitl_request_data.get("required_role", "Reviewer")
    context = hitl_request_data.get("context", {})

    # Extract key data points from context for the summary
    highlights = []
    if "confidence" in context:
        highlights.append(f"{int(context['confidence'] * 100)}% confidence")
    if "data_volume_gb" in context:
        highlights.append(f"{context['data_volume_gb']}GB data involved")
    if "amount" in context:
        highlights.append(f"${context['amount']:,} transaction")
    if "violations" in context:
        highlights.append(f"{context['violations']} violations detected")
    if "risk_score" in context:
        highlights.append(f"risk score {context['risk_score']}/10")

    detail = f" ({', '.join(highlights)})" if highlights else ""

    summary = (
        f"AI agent '{agent_id}' has flagged a {urgency}-urgency action requiring "
        f"immediate {role} approval: {action}{detail}. "
        f"This request has been escalated through the HITL Gateway and is awaiting "
        f"human review before the agent can proceed."
    )
    return summary


# ---------------------------------------------------------------------------
# LLM Remediation Draft Generator (mock — production uses Azure OpenAI)
# ---------------------------------------------------------------------------
# Enterprise Business Value:
#   Instead of presenting generic Approve/Reject buttons, the LLM analyzes
#   the request's urgency, context, and role to generate 3 precise,
#   actionable remediation strings. This enables one-click decision-making
#   directly from Telegram, reducing mean-time-to-resolution (MTTR) by
#   eliminating the cognitive overhead of composing a custom response.
# ---------------------------------------------------------------------------

def generate_remediation_drafts(hitl_request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Mock an LLM response that generates 3 actionable remediation strings
    based on the request's urgency, required role, and context payload.

    In production, this would call Azure OpenAI GPT-4 with a system prompt:
        "Given this HITL request payload, generate exactly 3 remediation
         options: one APPROVE variant, one REJECT variant, and one MODIFY
         variant. Each must be a concise, actionable instruction."

    Returns:
        A list of 3 dicts with 'text' (display label) and 'callback_data'
        (the exact string POSTed back to the Gateway callback).
    """
    urgency = hitl_request_data.get("urgency", "NORMAL")
    role = hitl_request_data.get("required_role", "Reviewer")
    instance_id = hitl_request_data.get("instance_id", "unknown")

    # Role + urgency-aware remediation options
    drafts = {
        ("CRITICAL", "SecOps_Lead"): [
            {"text": "✅ Approve: Isolate Host", "callback_data": f"approve:{instance_id}:Isolate Host, Block Lateral"},
            {"text": "❌ Reject: False Positive", "callback_data": f"reject:{instance_id}:False Positive, Resume Mon"},
            {"text": "🔧 Modify: Block IP", "callback_data": f"modify:{instance_id}:Quarantine, Preserve Evidence"},
        ],
        ("HIGH", "SecOps_Lead"): [
            {"text": "✅ Approve: Block Transfer", "callback_data": f"approve:{instance_id}:Block Outbound, Alert DLP"},
            {"text": "❌ Reject: Whitelist Dest", "callback_data": f"reject:{instance_id}:False Positive, Whitelist"},
            {"text": "🔧 Modify: Throttle 24h", "callback_data": f"modify:{instance_id}:Throttle, Monitor 24h"},
        ],
        ("HIGH", "Finance_Manager"): [
            {"text": "✅ Approve: Authorize", "callback_data": f"approve:{instance_id}:Authorize Dual Sign-Off"},
            {"text": "❌ Reject: Insufficient Docs", "callback_data": f"reject:{instance_id}:Insufficient Docs, Return"},
            {"text": "🔧 Modify: Partial Amount", "callback_data": f"modify:{instance_id}:Approve Partial, Flag Audit"},
        ],
        ("NORMAL", "Compliance_Officer"): [
            {"text": "✅ Approve: Auto-Remediate", "callback_data": f"approve:{instance_id}:Auto-Remediate Configs"},
            {"text": "❌ Reject: Manual Review", "callback_data": f"reject:{instance_id}:Manual Review Required"},
            {"text": "🔧 Modify: Stage First", "callback_data": f"modify:{instance_id}:Stage First Then Prod"},
        ],
    }

    # Fallback generic options
    default_drafts = [
        {"text": "✅ Approve: Execute Action", "callback_data": f"approve:{instance_id}:Approved, Execute"},
        {"text": "❌ Reject: Deny Action", "callback_data": f"reject:{instance_id}:Rejected, Deny"},
        {"text": "⬆️ Escalate: Senior Review", "callback_data": f"escalate:{instance_id}:Escalate Senior"},
    ]

    return drafts.get((urgency, role), default_drafts)


# ---------------------------------------------------------------------------
# Escalation Summary — Formatted Telegram Alert
# ---------------------------------------------------------------------------

async def send_escalation_summary(
    chat_id: str,
    hitl_request_data: Dict[str, Any],
) -> bool:
    """
    Send a richly formatted escalation alert to Telegram with One-Click
    Remediation Inline Keyboard Buttons.

    Uses the LLM-powered executive summary to distill the technical payload
    into a 2-sentence brief that C-suite / senior reviewers can act on immediately.
    Attaches 3 AI-generated remediation options as Telegram Inline Keyboard Buttons
    so the admin can click them directly in the chat without switching to the dashboard.
    """
    urgency = hitl_request_data.get("urgency", "NORMAL")
    agent_id = hitl_request_data.get("agent_id", "unknown")
    role = hitl_request_data.get("required_role", "Reviewer")
    action = hitl_request_data.get("action_description", "N/A")
    instance_id = hitl_request_data.get("instance_id", "N/A")
    emoji = URGENCY_EMOJI.get(urgency, "⚪")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # LLM-generated executive summary (mocked for demo)
    summary = generate_executive_summary(hitl_request_data)

    # LLM-generated remediation drafts (mocked — 3 actionable options)
    remediation_drafts = generate_remediation_drafts(hitl_request_data)

    message = (
        f"🚨 <b>HITL GATEWAY — ESCALATION ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{emoji} <b>Urgency:</b> {urgency}\n"
        f"🤖 <b>Agent:</b> <code>{agent_id}</code>\n"
        f"👤 <b>Required Role:</b> {role}\n"
        f"🔗 <b>Instance:</b> <code>{instance_id[:8]}...</code>\n\n"
        f"📋 <b>Action:</b>\n{action}\n\n"
        f"📝 <b>Executive Summary:</b>\n<i>{summary}</i>\n\n"
        f"🕐 <b>Time:</b> {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>One-Click Remediation:</b> Select an action below."
    )

    # Send with inline keyboard buttons for one-click remediation
    return await send_telegram_message_with_inline_keyboard(
        chat_id, message, remediation_drafts
    )


# ---------------------------------------------------------------------------
# Emergency Phone Call — "Wake Up Call" Pager Stub
# ---------------------------------------------------------------------------

async def trigger_emergency_phone_call(phone_number: str) -> Dict[str, Any]:
    """
    Trigger an emergency phone call if the Telegram SLA (2 minutes) is breached.

    Multi-Stage Escalation Matrix:
    ──────────────────────────────
      Stage 1 (0s):   Telegram Inline Keyboard message with LLM remediation drafts
      Stage 2 (30s):  Reminder ping in Telegram (automated)
      Stage 3 (120s): THIS FUNCTION FIRES — Emergency phone call via Twilio/ACS
      Stage 4 (180s): Slack #incident channel broadcast + PagerDuty trigger

    Enterprise Business Value:
    ──────────────────────────
      If a Telegram alert goes unacknowledged for 2 minutes, this function fires
      via Twilio to ring the reviewer's cell phone once and hang up — acting as
      an emergency pager. A phone ringing at 3am cuts through notification fatigue
      faster than any push notification or chat message.

    Twilio Implementation (production):
    ────────────────────────────────────
      This fires via Twilio if the Telegram SLA (2 minutes) is breached.
      Required env vars:
        - TWILIO_ACCOUNT_SID: Your Twilio Account SID (starts with AC...)
        - TWILIO_AUTH_TOKEN:   Your Twilio Auth Token
        - TWILIO_PHONE_NUMBER: Your Twilio phone number in E.164 format (+1234567890)

      Production code:

        from twilio.rest import Client

        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_from = os.getenv("TWILIO_PHONE_NUMBER")

        client = Client(twilio_sid, twilio_token)
        call = client.calls.create(
            to=phone_number,
            from_=twilio_from,
            # TwiML: ring for 3 seconds, play a short beep, then hang up
            twiml='<Response>'
                  '<Say voice="alice">HITL Gateway emergency. A critical request '
                  'is pending your review. Check Telegram immediately.</Say>'
                  '<Pause length="2"/>'
                  '<Hangup/>'
                  '</Response>',
            timeout=15,  # Ring for max 15 seconds
            status_callback="https://gateway.azurewebsites.net/api/call_status",
        )
        return {"status": "called", "call_sid": call.sid}

    Azure Communication Services Alternative:
    ──────────────────────────────────────────
        from azure.communication.callautomation import CallAutomationClient
        from azure.communication.callautomation import PhoneNumberIdentifier

        client = CallAutomationClient(os.getenv("ACS_CONNECTION_STRING"))
        call = client.create_call(
            target=PhoneNumberIdentifier(phone_number),
            source_caller_id=PhoneNumberIdentifier(os.getenv("ACS_PHONE_NUMBER")),
            callback_url="https://gateway.azurewebsites.net/api/call_events",
        )
        # Auto-hangup after 5 seconds (just ring once as a pager)
        await asyncio.sleep(5)
        client.hang_up(call.call_connection_id)

    Args:
        phone_number: The reviewer's phone number in E.164 format (e.g., +30XXXXXXXXXX)

    Returns:
        A dict with the call status.
    """
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_PHONE_NUMBER", "")

    if not twilio_sid or not twilio_token or not twilio_from:
        print(f"[EMERGENCY CALL] Twilio credentials not configured — running in stub mode")
        print(f"[EMERGENCY CALL] STUB — Would call {phone_number} via Twilio")
        return {
            "status": "stub",
            "phone_number": phone_number,
            "provider": "twilio",
            "note": "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to enable.",
        }

    twiml = (
        '<Response>'
        '<Say voice="alice">HITL Gateway emergency. A critical request '
        'is pending your review. Check Telegram immediately.</Say>'
        '<Pause length="2"/>'
        '<Hangup/>'
        '</Response>'
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Calls.json",
                data={
                    "To": phone_number,
                    "From": twilio_from,
                    "Twiml": twiml,
                    "Timeout": 15,
                },
                auth=(twilio_sid, twilio_token),
                timeout=15.0,
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                call_sid = result.get("sid", "unknown")
                print(f"[EMERGENCY CALL] Call initiated to {phone_number} — SID: {call_sid}")
                return {
                    "status": "called",
                    "call_sid": call_sid,
                    "phone_number": phone_number,
                    "provider": "twilio",
                }
            else:
                print(f"[EMERGENCY CALL] Twilio error: {resp.status_code} — {resp.text}")
                return {
                    "status": "error",
                    "phone_number": phone_number,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }
    except Exception as exc:
        print(f"[EMERGENCY CALL] Error: {exc}")
        return {
            "status": "error",
            "phone_number": phone_number,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Weekly CSV Report Generator
# ---------------------------------------------------------------------------

def generate_weekly_csv_report(audit_events: List[Dict[str, Any]]) -> bytes:
    """
    Generate an in-memory CSV report from the week's HITL audit trail.

    Enterprise Business Value:
        Automated weekly compliance reports eliminate manual data collection,
        ensure consistent formatting for regulatory audits, and provide
        C-suite visibility into AI governance metrics without requiring
        dashboard access.

    The CSV categorizes requests by:
      - Status (Approved / Rejected / Escalated)
      - Required Role
      - Average time-to-resolution
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Instance ID",
        "Agent ID",
        "Urgency",
        "Status",
        "Reviewer",
        "Required Role",
        "Action Description",
        "Timestamp",
        "Resolution Time (s)",
    ])

    # Data rows
    for event in audit_events:
        writer.writerow([
            event.get("instance_id", "N/A"),
            event.get("agent_id", "N/A"),
            event.get("urgency", "N/A"),
            event.get("event", event.get("status", "N/A")),
            event.get("reviewer_id", "system"),
            event.get("required_role", "N/A"),
            event.get("detail", event.get("action_description", "N/A")),
            event.get("timestamp", "N/A"),
            event.get("resolution_seconds", "N/A"),
        ])

    # Summary section
    writer.writerow([])
    writer.writerow(["=== WEEKLY SUMMARY ==="])

    total = len(audit_events)
    approved = sum(1 for e in audit_events if e.get("event") == "APPROVED")
    rejected = sum(1 for e in audit_events if e.get("event") == "REJECTED")
    escalated = sum(1 for e in audit_events if e.get("event") == "ESCALATED")

    writer.writerow(["Total Requests", total])
    writer.writerow(["Approved", approved])
    writer.writerow(["Rejected", rejected])
    writer.writerow(["Escalated", escalated])
    writer.writerow(["Approval Rate", f"{round(approved / max(total, 1) * 100, 1)}%"])

    csv_bytes = output.getvalue().encode("utf-8")
    output.close()
    return csv_bytes


async def send_weekly_report(chat_id: str, audit_events: List[Dict[str, Any]]) -> bool:
    """
    Generate and send the weekly CSV report to the Telegram admin channel.

    Enterprise Business Value:
        Automated Friday 5pm report delivery ensures leadership has
        governance metrics before the weekend, supports SOX/SOC2 compliance
        evidence trails, and creates a searchable Telegram archive of
        weekly performance snapshots.
    """
    now = datetime.now(timezone.utc)
    week_str = now.strftime("%Y-W%W")
    filename = f"hitl_weekly_report_{week_str}.csv"

    csv_bytes = generate_weekly_csv_report(audit_events)

    total = len(audit_events)
    approved = sum(1 for e in audit_events if e.get("event") == "APPROVED")
    rejected = sum(1 for e in audit_events if e.get("event") == "REJECTED")
    escalated = sum(1 for e in audit_events if e.get("event") == "ESCALATED")

    caption = (
        f"📊 <b>HITL Gateway — Weekly Report</b>\n"
        f"📅 Week: {week_str}\n\n"
        f"✅ Approved: {approved}\n"
        f"❌ Rejected: {rejected}\n"
        f"⚠️ Escalated: {escalated}\n"
        f"📈 Total: {total}\n\n"
        f"<i>Auto-generated by HITL Gateway Cron</i>"
    )

    return await send_telegram_document(chat_id, csv_bytes, filename, caption)
