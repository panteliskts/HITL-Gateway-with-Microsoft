# HITL Gateway Platform

**Enterprise Human-in-the-Loop Middleware for Autonomous AI Agent Governance**

Built on Azure Durable Functions, this gateway intercepts high-risk AI agent actions, routes them to human reviewers with SLA-driven urgency, and resumes agent execution with a cryptographically verified decision — all with full audit trail, multi-tenant isolation, and zero-compute wait states.

> **TechBiz 2026 Hackathon** | Microsoft Challenge | Brought to us by **TechBiz**

---

## Platform Features

| Feature | Description |
|---------|-------------|
| **Login & Auth** | Enterprise mock JWT authentication, session management, change password |
| **Dark / Light Theme** | SOC palette with system preference detection and manual toggle |
| **Live Demo** | Watch Azure Durable Functions orchestration in real-time across 7 stages |
| **Pending Inbox** | Review and approve/reject requests with SLA countdown timers |
| **Review Page** | Deep-link `/review/:id` with AI-generated One-Click Remediation actions |
| **Audit Trail** | Timeline compliance view with CSV export, filterable by time/urgency/role/event |
| **Help Bot** | AI-powered assistant with knowledge base (Azure AI branding) |
| **Dashboard** | Real-time stats, approval rates, decision time metrics, health monitoring |
| **Telegram Alerts** | Auto-escalation with LLM summaries + Inline Keyboard one-click remediation |
| **Weekly CSV Reports** | Automated Friday 5PM reports via Telegram + Resend email |
| **Emergency Phone Pager** | Twilio voice call for CRITICAL SLA breaches (2min unacknowledged) |
| **Email Reports** | Resend API with base64-encoded CSV attachments |

> **Login credentials:** `admin` / `password123`

---

## Why This Exists

Autonomous AI agents are powerful but dangerous without guardrails. When an AI decides to isolate a production host, approve a $2M transaction, or modify compliance records, a human must sign off. This gateway is the **trust boundary** between AI autonomy and human oversight.

**The problem:** Agents block while waiting for humans (minutes to hours). Traditional polling wastes compute. Webhooks are fragile. There's no standard middleware.

**Our solution:** Azure Durable Functions' `wait_for_external_event` + durable timers create a **zero-compute wait state** that survives process restarts, supports SLA-driven escalation, and resumes deterministically.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    AI AGENT (any language/framework)                     │
│                                  |                                       │
│                      POST /api/hitl_ingress                              │
│                      + X-API-Key header                                  │
│                      + HITLRequest JSON                                  │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    v
        ┌──────────────────────────────────────────────────────────────┐
        |      HITL GATEWAY (Azure Durable Functions)                  |
        |                                                              |
        |  [Auth] -> [Rate Limit] -> [SSRF Check]                      |
        |      -> [Sanitize] -> [Start Orchestration]                  |
        |                                                              |
        |  ┌──────────── Durable Orchestrator ───────────────┐         |
        |  | 1. log_audit(PENDING)                           |         |
        |  | 2. send_teams_card -> Teams/Slack               |         |
        |  | 3. task_any([SLA_timer, HumanDecision])         |         |
        |  |    |                                            |         |
        |  |    |-- Timer wins -> ESCALATED                  |         |
        |  |    |      -> send_telegram_escalation           |         |
        |  |    |      -> trigger_emergency_call (2min)      |         |
        |  |    |-- Human wins -> APPROVED/REJECTED          |         |
        |  | 4. log_audit(terminal)                          |         |
        |  | 5. notify_agent -> POST callback_url            |         |
        |  └─────────────────────────────────────────────────┘         |
        |                                                              |
        |  Timer Trigger (Fri 5PM UTC):                                |
        |    weekly_report_trigger -> CSV -> Telegram + Resend email   |
        |                                                              |
        |  Dashboard API (BFF):                                        |
        |    GET /api/health        GET /api/metrics                   |
        |    GET /api/pending       GET /api/workflows                 |
        |    GET /api/audit         GET /api/audit/csv                 |
        |    POST /api/trigger/{s}  POST /api/decide/{id}              |
        |    POST /api/report/weekly GET /api/events (SSE)             |
        |    POST /api/test/telegram POST /api/test/call               |
        |    POST /api/test/sms      POST /api/test/email              |
        └──────────────────────────────────────────────────────────────┘
                                    |
                        POST /resume_agent (HITLResponse)
                                    |
                                    v
                        AI AGENT RESUMES EXECUTION
                                    |
        ┌───────────────────────────┴───────────────────────────┐
        |         REACT DASHBOARD (http://localhost:3000)       |
        |                                                       |
        |  • Login Page — Enterprise mock JWT authentication    |
        |  • Dark / Light Theme — SOC palette + toggle          |
        |  • Live Demo — 7-stage orchestration visualizer       |
        |  • Pending Inbox — Approve/Reject with SLA timers     |
        |  • Review Page — AI remediation one-click buttons     |
        |  • Audit Trail — Filterable compliance timeline + CSV |
        |  • Help Bot — AI assistant                            |
        |  • Dashboard — Real-time metrics                      |
        └───────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Azure Durable Functions | Zero-compute waiting, survives restarts, built-in replay |
| `task_any([timer, event])` | SLA enforcement without polling — deterministic race |
| HMAC-SHA256 webhook verification | Prevents spoofed approvals from external actors |
| Idempotency via `idempotency_key` | Exactly-once orchestration startup, safe retries |
| React + SWR for frontend | Real-time polling with automatic cache invalidation |
| Isolated `telegram_client.py` | Clean separation of notification concerns from gateway |
| Inline Keyboard Buttons | One-click remediation directly from Telegram chat |
| Resend email delivery | Redundant CSV report channel for compliance archival |
| Twilio emergency fallback | Phone pager ensures CRITICAL alerts are never missed |
| Multi-stage escalation | Telegram → Phone Call → Auto-escalate chain |

---

## Project Structure

```
microsoft-challenge2/
├── function_app.py              # Azure Durable Functions gateway + weekly report timer
├── agent_mock.py                # FastAPI agent simulator (5 threat scenarios)
├── schemas.py                   # Pydantic v2 contracts (HITLRequest, HITLResponse, enums)
├── security.py                  # Auth, HMAC, SSRF prevention, sanitization, rate limiting
├── config.py                    # Centralized env-driven configuration (frozen dataclass)
├── observability.py             # Metrics, audit logging, health checks
│
├── backend/
│   ├── server.py                # FastAPI BFF — live workflow simulation + dashboard API
│   ├── telegram_client.py       # Telegram module — escalation + inline keyboard + CSV reports
│   └── email_service.py         # Resend email API — automated CSV report delivery
│
├── frontend/                    # React Dashboard (Tailwind CSS)
│   ├── src/
│   │   ├── App.js               # Routes + AuthProvider + ThemeProvider
│   │   ├── context/
│   │   │   ├── AuthContext.js    # Mock JWT auth, login/logout/changePassword
│   │   │   └── ThemeContext.js   # Dark/Light theme with system preference
│   │   ├── pages/
│   │   │   ├── Login.js          # Enterprise login page
│   │   │   ├── Dashboard.js      # Real-time stats and metrics
│   │   │   ├── LiveDemo.js       # 7-stage orchestration visualizer
│   │   │   ├── PendingInbox.js   # Approve/reject with SLA timers
│   │   │   ├── ReviewRequest.js  # Deep-link review with AI remediation buttons
│   │   │   └── AuditTrail.js     # Timeline + CSV export + filters
│   │   ├── components/
│   │   │   ├── Layout.js         # Sidebar + top bar + theme toggle + user menu
│   │   │   └── HelpBot.js       # AI-powered assistant
│   │   └── types/hitl.js
│   ├── tailwind.config.js        # CSS variable-based theming with dark mode
│   └── package.json
│
├── tests/
│   ├── test_schemas.py           # 31 tests — contract validation
│   ├── test_security.py          # 41 tests — auth, HMAC, SSRF, sanitization, rate limit
│   └── test_observability.py     # 15 tests — metrics, audit, health
│
├── docs/
│   ├── qr-repo.png              # QR code → GitHub repository
│   ├── qr-website.png           # QR code → Live website
│   ├── DEMO_SCRIPT.md
│   ├── FRONTEND_INTEGRATION_GUIDE.md
│   ├── TELEGRAM_SETUP.md
│   ├── ENTERPRISE_ROADMAP.md
│   └── IMPROVEMENT_ROADMAP.md
│
├── host.json                     # Azure Functions runtime configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
└── .gitignore                    # Protects secrets and junk files
```

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for React frontend)
- *(Optional)* [Azure Functions Core Tools v4](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- *(Optional)* [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite)

### Install & Run

```bash
# 1. Install Python dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Install frontend dependencies
cd frontend
npm install
cd ..

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys (Telegram, Twilio, Resend)

# 4. Start backend BFF server (Terminal 1)
python -m uvicorn backend.server:app --port 8000 --reload

# 5. Start frontend dev server (Terminal 2)
cd frontend
REACT_APP_BACKEND_URL=http://localhost:8000 npm start
# Frontend opens at http://localhost:3000

# 6. Login with: admin / password123
```

### Run Tests

```bash
pytest tests/ -v --tb=short
# 91 tests, all passing
```

---

## API Reference

### Core Endpoints (Azure Functions)

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/hitl_ingress` | API Key | Agent submits approval request, starts orchestration |
| `POST` | `/api/teams_webhook_callback/{id}` | HMAC | Human decision callback (from Teams/Logic App) |
| `TIMER` | `0 17 * * 5` | N/A | Weekly CSV compliance report |

### Dashboard API (BFF — FastAPI)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/health` | Deep health check (200/503) for load balancer probes |
| `GET` | `/api/stats` | Aggregated stats: approval rate, decision times, counts |
| `GET` | `/api/metrics` | Prometheus-style metrics snapshot |
| `GET` | `/api/scenarios` | List available threat scenarios |
| `POST` | `/api/trigger/{scenario}` | Trigger a live workflow simulation |
| `GET` | `/api/workflows` | List all workflows with SLA remaining |
| `GET` | `/api/workflow/{id}` | Get specific workflow state |
| `POST` | `/api/decide/{id}` | Submit approve/reject/escalate decision |
| `GET` | `/api/pending` | Active HITL requests with SLA countdowns |
| `GET` | `/api/audit` | Recent audit events (max 500) |
| `GET` | `/api/audit/csv` | Download audit trail as filtered CSV |
| `GET` | `/api/events` | Server-Sent Events stream for real-time updates |
| `POST` | `/api/report/weekly` | Manually trigger weekly report generation |
| `POST` | `/api/test/telegram` | Test Telegram escalation with inline keyboard |
| `POST` | `/api/test/call` | Test Twilio emergency phone call |
| `POST` | `/api/test/sms` | Test Twilio SMS notification |
| `POST` | `/api/test/email` | Test Resend email CSV report |
| `POST` | `/api/reset` | Clear all workflows (demo mode only) |

---

## Multi-Channel Notification System

### SLA Escalation Matrix

| Urgency | Timeout | Primary Channel | Escalation | Emergency |
|---------|---------|-----------------|------------|-----------|
| `CRITICAL` | 5 min | Teams + Telegram | Slack + Telegram summary | Twilio phone call (2min) |
| `HIGH` | 15 min | Teams + Telegram | Slack webhook | Twilio phone call (2min) |
| `NORMAL` | 60 min | Teams | Slack webhook | — |
| `LOW` | 24 hr | Teams | Slack webhook | — |

### Escalation Flow

```
1. AI Agent escalates → HITL Gateway receives request
2. Telegram Alert (immediate) — LLM summary + Inline Keyboard remediation buttons
3. Teams Adaptive Card — Full context for reviewer
4. If unacknowledged (2 min) → Emergency Phone Call via Twilio
5. If SLA timeout → Auto-escalate to senior reviewer + Telegram
6. Weekly CSV Report (Friday 5PM) → Telegram document + Resend email
```

### Telegram Integration

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

| Event | Trigger | Format |
|-------|---------|--------|
| **Escalation Alert** | Manual escalate or SLA timeout | Rich HTML + Inline Keyboard buttons |
| **Weekly Report** | Friday 5PM UTC (Timer Trigger) | CSV file via Telegram + Resend email |
| **Emergency Call** | Telegram unacknowledged (2min) | Phone ring via Twilio |

---

## Security Model

| Layer | Mechanism | Details |
|-------|-----------|---------|
| **Authentication** | API key (`X-API-Key` / `Bearer`) | Constant-time comparison, Key Vault-backed in prod |
| **Frontend Auth** | Mock JWT with session management | Enterprise login, protected routes, change password |
| **Webhook Integrity** | HMAC-SHA256 (`X-Webhook-Signature`) | Prevents spoofed approval decisions |
| **SSRF Prevention** | Callback URL allowlist + private IP blocking | Blocks `169.254.x.x`, `10.x.x.x`, `192.168.x.x` |
| **XSS Prevention** | HTML entity escaping + protocol stripping | Sanitizes all user text before Teams cards |
| **Rate Limiting** | Sliding window per `agent_id` | 30 req/60s default, Redis-ready |
| **Replay Prevention** | Nonce tracking + timestamp freshness | 5-minute nonce expiry window |
| **Dev Mode** | Graceful degradation | All security layers auto-disable when unconfigured |

---

## Configuration

All settings are loaded from environment variables. Create a `.env` file from `.env.example`:

| Variable | Description |
|----------|-------------|
| `REACT_APP_BACKEND_URL` | Frontend → backend API URL |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Telegram chat/group ID for notifications |
| `TELEGRAM_ADMIN_CHAT_ID` | Admin chat ID for escalation alerts |
| `DASHBOARD_URL` | Frontend URL for deep-link review buttons |
| `RESEND_API_KEY` | Resend API key for email delivery |
| `RESEND_FROM_EMAIL` | Verified sender email in Resend |
| `REPORT_EMAIL` | Compliance officer email for weekly reports |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID for emergency calls |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Twilio phone number (E.164 format) |
| `EMERGENCY_PHONE_TO` | Destination phone for emergency calls |
| `HITL_API_KEYS` | Comma-separated API keys (empty = auth disabled) |
| `HITL_WEBHOOK_SECRET` | HMAC secret for webhook verification |
| `TEAMS_WEBHOOK_URL` | Teams incoming webhook (empty = mock mode) |
| `SLACK_WEBHOOK_URL` | Slack webhook for escalations |

---

## Test Coverage

| Module | Tests | Coverage Areas |
|--------|-------|---------------|
| `test_schemas.py` | 31 | Validation rules, defaults, edge cases, backward compat |
| `test_security.py` | 41 | Auth, HMAC, SSRF, sanitization, rate limit, replay |
| `test_observability.py` | 15 | Counters, histograms, gauges, audit buffer, metrics |
| **Total** | **91** | **All passing** |

---

## Azure Services
| Azure Service | Usage |
|---------------|-------|
| **Durable Functions** | Zero-compute wait states, SLA timers, orchestration |
| **Event Grid** | Event-driven architecture for audit trail |
| **Application Insights** | Observability, KQL queries, structured logging |
| **Communication Services** | Emergency phone call escalation (ACS fallback) |
| **Cosmos DB** | Persistent audit trail (Phase 2) |
| **Redis** | Distributed rate limiting (Phase 2) |
| **Resend** | Transactional email for weekly CSV reports |
| **Twilio** | Emergency phone pager (primary) |

---

## License

Built for the **TechBiz 2026 Hackathon — Microsoft Challenge**. All rights reserved.
