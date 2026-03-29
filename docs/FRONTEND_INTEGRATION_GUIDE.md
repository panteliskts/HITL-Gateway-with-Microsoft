# Frontend Integration Guide

**Complete reference for building a fullstack dashboard that connects to the HITL Gateway backend.**

This document contains everything your frontend generator needs: API contracts with exact request/response shapes, real-time update patterns, recommended architecture, UI component specifications, and production deployment considerations.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Backend Base URLs](#backend-base-urls)
3. [Authentication](#authentication)
4. [API Contracts](#api-contracts)
   - [Submit HITL Request](#1-submit-hitl-request)
   - [Submit Human Decision](#2-submit-human-decision)
   - [List Pending Requests](#3-list-pending-requests)
   - [Get Dashboard Statistics](#4-get-dashboard-statistics)
   - [Get Audit Trail (Instance)](#5-get-audit-trail-instance)
   - [Get Recent Audit Events](#6-get-recent-audit-events)
   - [Health Check](#7-health-check)
   - [Metrics Snapshot](#8-metrics-snapshot)
5. [Data Models](#data-models)
6. [Real-Time Updates](#real-time-updates)
7. [Recommended Pages & Components](#recommended-pages--components)
8. [CORS Configuration](#cors-configuration)
9. [Error Handling](#error-handling)
10. [Environment Variables](#environment-variables)
11. [Deployment Architecture](#deployment-architecture)
12. [Agent Mock Endpoints](#agent-mock-endpoints)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR FULLSTACK APP                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Frontend (React / Next.js / etc.)                       │  │
│  │                                                          │  │
│  │  Pages:                                                  │  │
│  │    /dashboard        — Live overview + stats             │  │
│  │    /pending          — Queue of pending approvals        │  │
│  │    /review/:id       — Single request review + decide    │  │
│  │    /audit            — Audit trail explorer              │  │
│  │    /audit/:id        — Instance audit detail             │  │
│  │    /metrics          — System health + performance       │  │
│  │    /scenarios        — Trigger test scenarios            │  │
│  │                                                          │  │
│  │  Polling Strategy:                                       │  │
│  │    /api/pending  — every 3-5s (pending queue)            │  │
│  │    /api/stats    — every 5-10s (dashboard counters)      │  │
│  │    /api/health   — every 30s (status indicator)          │  │
│  │    /api/metrics  — every 10-15s (charts)                 │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │  HTTP (fetch / axios / SWR / React Query)    │
│  ┌──────────────▼───────────────────────────────────────────┐  │
│  │  Optional BFF / API Route Layer (Next.js API routes)     │  │
│  │  - Proxies to gateway, adds auth headers                 │  │
│  │  - Aggregates multiple backend calls                     │  │
│  │  - Caches responses, manages sessions                    │  │
│  └──────────────┬───────────────────────────────────────────┘  │
└─────────────────┼───────────────────────────────────────────────┘
                  │
                  │ HTTPS
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              HITL GATEWAY (Azure Functions)                      │
│                                                                 │
│  Core:    POST /api/hitl_ingress                                │
│           POST /api/teams_webhook_callback/{instance_id}        │
│                                                                 │
│  Dashboard API:                                                 │
│           GET  /api/pending?tenant_id=&urgency=&role=          │
│           GET  /api/stats                                       │
│           GET  /api/audit/{instance_id}                         │
│           GET  /api/audit?limit=100                             │
│           GET  /api/health                                      │
│           GET  /api/metrics                                     │
└─────────────────────────────────────────────────────────────────┘
                  │
                  │ POST callback_url
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│          AGENT MOCK (FastAPI, port 7071)                        │
│  POST /trigger/{scenario}    GET /status    GET /scenarios      │
└─────────────────────────────────────────────────────────────────┘
```

**Key points for your frontend:**

1. The gateway backend is a **standalone Azure Functions app** — your frontend talks to it over HTTP.
2. There is no WebSocket server built into the gateway. Use **polling** (recommended) or add a WebSocket layer in your BFF.
3. The dashboard API endpoints are **read-only** (GET). The only write endpoints are `hitl_ingress` (submit requests) and `teams_webhook_callback` (submit decisions).
4. All responses are JSON. All timestamps are ISO 8601 UTC.

---

## Backend Base URLs

| Environment | Gateway URL | Agent Mock URL |
|-------------|-------------|----------------|
| Local dev | `http://localhost:7072/api` | `http://localhost:7071` |
| Azure staging | `https://<func-app>.azurewebsites.net/api` | N/A |
| Azure production | `https://<func-app>.azurewebsites.net/api` | N/A |

Configure these in your frontend's environment:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:7072/api
NEXT_PUBLIC_AGENT_URL=http://localhost:7071
```

---

## Authentication

### For agent-facing endpoints (`/api/hitl_ingress`)

Send the API key in one of two ways:

```http
X-API-Key: your-api-key-here
```

```http
Authorization: Bearer your-api-key-here
```

### For dashboard API endpoints (`/api/pending`, `/api/stats`, etc.)

Currently no authentication required (anonymous access). In production, consider adding:
- Azure AD / Entra ID token validation in a BFF layer
- Function-level auth keys via `AuthLevel.FUNCTION`
- A session-based auth layer in your fullstack app

### For webhook callbacks (`/api/teams_webhook_callback/{id}`)

Requires HMAC-SHA256 signature in `X-Webhook-Signature` header when `HITL_WEBHOOK_SECRET` is configured:

```
X-Webhook-Signature: <hex-encoded HMAC-SHA256 of request body>
```

**Computing the signature (for your frontend's approve/reject action):**

```typescript
import { createHmac } from 'crypto';

function computeSignature(body: string, secret: string): string {
  return createHmac('sha256', secret)
    .update(body)
    .digest('hex');
}

// Usage in API route / BFF:
const bodyStr = JSON.stringify(decisionPayload);
const signature = computeSignature(bodyStr, process.env.HITL_WEBHOOK_SECRET);

await fetch(`${GATEWAY_URL}/teams_webhook_callback/${instanceId}`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Webhook-Signature': signature,
  },
  body: bodyStr,
});
```

**Important:** Never expose `HITL_WEBHOOK_SECRET` to the browser. Compute the HMAC server-side in your BFF / API route.

---

## API Contracts

### 1. Submit HITL Request

**`POST /api/hitl_ingress`**

Used by agents or your frontend's "Create Test Request" feature.

#### Request

```typescript
interface HITLRequest {
  agent_id: string;                    // Required. Min 1, max 256 chars.
  action_description: string;          // Required. Min 1, max 4096 chars.
  required_role: string;               // Required. Min 1, max 128 chars.
  callback_url: string;                // Required. http:// or https://
  urgency?: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';  // Default: 'NORMAL'
  context?: Record<string, any>;       // Default: {}
  idempotency_key?: string;            // Default: auto-generated UUID
  tenant_id?: string;                  // Default: 'default'. Max 128 chars.
  tags?: string[];                     // Default: []. Max 20 items.
  priority?: number;                   // Default: 0. Range: 0-100.
  approval_policy?: 'ANY' | 'ALL' | 'MAJORITY';  // Default: 'ANY'
  required_roles?: string[];           // Default: []
  expires_at?: string;                 // ISO 8601. Optional hard expiry.
  dry_run?: boolean;                   // Default: false
}
```

#### Response — 202 Accepted

```json
{
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
  "idempotent": false,
  "tenant_id": "default",
  "dry_run": false
}
```

#### Response — 202 (Idempotent duplicate)

```json
{
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
  "idempotent": true
}
```

#### Error Responses

| Status | Body | When |
|--------|------|------|
| 401 | `{"error": "Unauthorized", "detail": "Invalid or missing API key"}` | Bad/missing API key |
| 400 | `{"error": "Invalid JSON body"}` | Non-JSON request body |
| 400 | `{"error": "Invalid callback_url", "detail": "..."}` | SSRF-blocked or malformed URL |
| 422 | `{"error": "Schema validation failed", "detail": "..."}` | Pydantic validation failure |
| 429 | `{"error": "Rate limit exceeded", "detail": "...", "retry_after": 60}` | Too many requests |

---

### 2. Submit Human Decision

**`POST /api/teams_webhook_callback/{instance_id}`**

This is the endpoint your frontend's **Approve/Reject** buttons should call.

#### Path Parameters

| Param | Type | Description |
|-------|------|-------------|
| `instance_id` | string | The orchestration instance ID from the pending request |

#### Request

```typescript
interface HumanDecisionEvent {
  status: 'APPROVED' | 'REJECTED';     // Required
  reviewer_id: string;                  // Required. Min 1 char. e.g., "jane@contoso.com"
  reason?: string;                      // Optional. Max 2048 chars.
  nonce?: string;                       // Optional. For replay prevention.
  timestamp?: number;                   // Optional. Unix epoch seconds.
}
```

#### Headers

```http
Content-Type: application/json
X-Webhook-Signature: <hmac-hex>    # Required when HITL_WEBHOOK_SECRET is set
```

#### Response — 200 OK

```json
{
  "status": "event_raised",
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "APPROVED"
}
```

#### Error Responses

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "instance_id path parameter is required"}` | Missing path param |
| 400 | `{"error": "Invalid JSON body"}` | Non-JSON body |
| 403 | `{"error": "Invalid webhook signature"}` | HMAC mismatch |
| 404 | `{"error": "Orchestration not found", "instance_id": "..."}` | No such orchestration |
| 409 | `{"error": "Replay attack detected"}` | Duplicate nonce |
| 409 | `{"error": "Orchestration already completed", ...}` | Already decided |
| 422 | `{"error": "Schema validation failed", "detail": "..."}` | Bad payload |

---

### 3. List Pending Requests

**`GET /api/pending`**

The primary endpoint for your pending queue / approval inbox.

#### Query Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | string | No | Filter by tenant |
| `urgency` | string | No | Filter by urgency: `CRITICAL`, `HIGH`, `NORMAL`, `LOW` |
| `role` | string | No | Filter by required_role |

#### Response — 200 OK

```typescript
interface PendingResponse {
  count: number;
  requests: PendingRequest[];
}

interface PendingRequest {
  instance_id: string;
  agent_id: string;
  action_description: string;
  required_role: string;
  urgency: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';
  status: 'PENDING';
  tenant_id: string;
  tags: string[];
  priority: number;               // 0-100
  created_at: string;             // ISO 8601 UTC
  dry_run: boolean;
  sla_deadline_seconds: number;   // Total SLA timeout for this urgency
  sla_remaining_seconds: number | null;  // Seconds until SLA breach (null if calc failed)
}
```

**Sort order:** CRITICAL first, then HIGH, NORMAL, LOW. Within same urgency, highest `priority` first.

#### Example

```json
{
  "count": 2,
  "requests": [
    {
      "instance_id": "abc-123",
      "agent_id": "secops-agent-v2",
      "action_description": "Isolate host 10.0.5.42 - lateral movement detected",
      "required_role": "SecOps_Lead",
      "urgency": "CRITICAL",
      "status": "PENDING",
      "tenant_id": "contoso",
      "tags": ["security", "automated"],
      "priority": 90,
      "created_at": "2026-03-27T10:30:00+00:00",
      "dry_run": false,
      "sla_deadline_seconds": 300,
      "sla_remaining_seconds": 142
    }
  ]
}
```

---

### 4. Get Dashboard Statistics

**`GET /api/stats`**

Aggregated numbers for your dashboard overview cards.

#### Response — 200 OK

```typescript
interface DashboardStats {
  total_requests: number;
  pending: number;
  approved: number;
  rejected: number;
  escalated: number;
  active_agents: number;
  approval_rate: number;                  // Percentage (0-100)
  avg_decision_time_seconds: number;
  p95_decision_time_seconds: number;
  metrics_snapshot: MetricsSnapshot;      // Full metrics object (see /api/metrics)
}
```

#### Example

```json
{
  "total_requests": 47,
  "pending": 3,
  "approved": 28,
  "rejected": 8,
  "escalated": 8,
  "active_agents": 4,
  "approval_rate": 63.6,
  "avg_decision_time_seconds": 45.2,
  "p95_decision_time_seconds": 285.0,
  "metrics_snapshot": { ... }
}
```

---

### 5. Get Audit Trail (Instance)

**`GET /api/audit/{instance_id}`**

Full event history for one HITL request.

#### Response — 200 OK

```typescript
interface AuditTrailResponse {
  instance_id: string;
  events: AuditEvent[];
}

interface AuditEvent {
  instance_id: string;
  event: string;           // 'PENDING', 'APPROVED', 'REJECTED', 'ESCALATED'
  agent_id: string;
  urgency: string;
  reviewer_id: string;
  reason: string;
  timestamp: string;       // ISO 8601
  metadata: Record<string, any>;
}
```

---

### 6. Get Recent Audit Events

**`GET /api/audit`**

#### Query Parameters

| Param | Type | Default | Max | Description |
|-------|------|---------|-----|-------------|
| `limit` | int | 100 | 500 | Number of events to return |

#### Response — 200 OK

```typescript
interface AuditListResponse {
  count: number;
  events: AuditEvent[];   // Newest first
}
```

---

### 7. Health Check

**`GET /api/health`**

Use for your status indicator (green/yellow/red dot).

#### Response — 200 (healthy) or 503 (degraded)

```typescript
interface HealthResponse {
  status: 'healthy' | 'degraded';
  timestamp: string;                  // ISO 8601
  version: string;
  environment: string;
  checks: {
    process: { status: string; uptime_seconds: number; memory_mb: number };
    durable_storage: { status: string; note?: string };
    cosmos_db: { status: string; note?: string };
    app_insights: { status: string; note?: string };
  };
}
```

---

### 8. Metrics Snapshot

**`GET /api/metrics`**

Raw metrics data for charts and visualizations.

#### Response — 200 OK

```typescript
interface MetricsSnapshot {
  uptime_seconds: number;
  captured_at: string;                // ISO 8601
  counters: Record<string, number>;   // e.g. "hitl.requests.total": 47
  histograms: Record<string, {
    count: number;
    sum: number;
    avg: number;
    min: number;
    max: number;
    p50: number;
    p95: number;
    p99: number;
  }>;
  gauges: Record<string, number>;
}
```

**Key metrics to display:**

| Metric Key | Type | What to Show |
|-----------|------|-------------|
| `hitl.requests.total` | counter | Total requests badge |
| `hitl.decisions.total` | counter | Total decisions badge |
| `hitl.sla.timeouts.total` | counter | SLA breaches count |
| `hitl.decision.duration_seconds` | histogram | Decision time chart (p50, p95, p99 lines) |
| `hitl.auth.failure` | counter | Failed auth attempts (security alert) |
| `hitl.rate_limit.rejected` | counter | Rate-limited requests |
| `hitl.webhook.teams.latency_ms` | histogram | Teams webhook latency chart |
| `hitl.callback.latency_ms` | histogram | Agent callback latency chart |

---

## Data Models

### Enumerations

```typescript
type UrgencyLevel = 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';
type HITLStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'ESCALATED';
type ApprovalPolicy = 'ANY' | 'ALL' | 'MAJORITY';
```

### Urgency → SLA Mapping (for client-side countdown timers)

```typescript
const SLA_TIMEOUT_SECONDS: Record<UrgencyLevel, number> = {
  CRITICAL: 300,    // 5 minutes
  HIGH:     900,    // 15 minutes
  NORMAL:   3600,   // 60 minutes
  LOW:      86400,  // 24 hours
};
```

### Role → Channel Mapping (for display purposes)

```typescript
const ROLE_CHANNEL_MAP: Record<string, string> = {
  Finance_Manager:    '#finance-approvals',
  SecOps_Lead:        '#secops-alerts',
  Compliance_Officer: '#compliance-reviews',
  Risk_Manager:       '#risk-management',
};
const DEFAULT_CHANNEL = '#hitl-general';
```

### Urgency Color Scheme

```typescript
const URGENCY_COLORS: Record<UrgencyLevel, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: '#FEE2E2', text: '#991B1B', border: '#EF4444' },  // Red
  HIGH:     { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B' },  // Amber
  NORMAL:   { bg: '#DBEAFE', text: '#1E40AF', border: '#3B82F6' },  // Blue
  LOW:      { bg: '#F3F4F6', text: '#374151', border: '#9CA3AF' },  // Gray
};
```

### Status Color Scheme

```typescript
const STATUS_COLORS: Record<HITLStatus, { bg: string; text: string }> = {
  PENDING:   { bg: '#FEF3C7', text: '#92400E' },  // Amber
  APPROVED:  { bg: '#D1FAE5', text: '#065F46' },  // Green
  REJECTED:  { bg: '#FEE2E2', text: '#991B1B' },  // Red
  ESCALATED: { bg: '#EDE9FE', text: '#5B21B6' },  // Purple
};
```

---

## Real-Time Updates

The gateway does not provide WebSocket or SSE endpoints. Use **polling** with the following recommended intervals:

### Polling Strategy

```typescript
// In your frontend data layer (SWR / React Query / custom hooks)

// Pending queue — fast refresh for urgency
useSWR('/api/pending', fetcher, { refreshInterval: 3000 });    // 3 seconds

// Dashboard stats — moderate refresh
useSWR('/api/stats', fetcher, { refreshInterval: 5000 });      // 5 seconds

// Health status — slow refresh
useSWR('/api/health', fetcher, { refreshInterval: 30000 });    // 30 seconds

// Metrics — moderate refresh
useSWR('/api/metrics', fetcher, { refreshInterval: 10000 });   // 10 seconds

// Audit trail — on-demand (click to load), no auto-refresh
// GET /api/audit/{instance_id} — fetch on page load only
```

### Optimistic UI Updates

When a user clicks **Approve** or **Reject**, immediately update the local state before the server responds:

```typescript
async function submitDecision(instanceId: string, status: 'APPROVED' | 'REJECTED', reason: string) {
  // 1. Optimistically remove from pending list
  mutate('/api/pending', (current) => ({
    ...current,
    requests: current.requests.filter(r => r.instance_id !== instanceId),
    count: current.count - 1,
  }), false);

  // 2. Submit to gateway (via your BFF for HMAC signing)
  const response = await fetch(`/api/bff/decide/${instanceId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, reviewer_id: currentUser.email, reason }),
  });

  // 3. Revalidate on success, rollback on error
  if (response.ok) {
    mutate('/api/pending');
    mutate('/api/stats');
  } else {
    mutate('/api/pending');  // Reload true state
    throw new Error(`Decision failed: ${response.status}`);
  }
}
```

### Optional: Add WebSocket Layer

If you want true real-time updates (sub-second), add a WebSocket relay in your BFF that polls the gateway and broadcasts changes:

```typescript
// BFF pseudo-code
const wss = new WebSocket.Server({ port: 3001 });

setInterval(async () => {
  const pending = await fetch(`${GATEWAY_URL}/pending`).then(r => r.json());
  const stats = await fetch(`${GATEWAY_URL}/stats`).then(r => r.json());

  wss.clients.forEach(client => {
    client.send(JSON.stringify({ type: 'pending', data: pending }));
    client.send(JSON.stringify({ type: 'stats', data: stats }));
  });
}, 2000);
```

---

## Recommended Pages & Components

### 1. Dashboard Overview (`/dashboard`)

**Data sources:** `GET /api/stats`, `GET /api/health`, `GET /api/pending`

**Components:**
- **Status Bar** — gateway health status (green/amber/red dot) from `/api/health`
- **Stat Cards** — total, pending, approved, rejected, escalated counts
- **Approval Rate** — circular progress / percentage from `stats.approval_rate`
- **Decision Time** — bar showing avg + p95 from `stats.avg_decision_time_seconds`
- **Active Agents** — count from `stats.active_agents`
- **SLA Compliance** — percentage of decisions within SLA
- **Recent Activity Feed** — last 10 events from `/api/audit?limit=10`
- **Urgency Distribution** — pie or donut chart from pending request urgencies

### 2. Pending Queue / Approval Inbox (`/pending`)

**Data source:** `GET /api/pending` (poll every 3s)

**Components:**
- **Filter Bar** — dropdown filters for `tenant_id`, `urgency`, `role`
- **Request Cards / Table Rows** — one per pending request showing:
  - Urgency badge (color-coded)
  - Agent ID
  - Action description (truncated, expandable)
  - Required role
  - Tags as chips
  - SLA countdown timer (computed client-side from `sla_remaining_seconds`)
  - Priority indicator
  - Tenant badge
  - **Approve / Reject** action buttons
  - Link to `/review/{instance_id}`
- **Empty State** — "No pending requests" illustration
- **Sound/Notification** — optional audio alert when CRITICAL request arrives

**SLA countdown timer logic:**

```typescript
function SLACountdown({ slaRemainingSeconds, urgency }: Props) {
  const [remaining, setRemaining] = useState(slaRemainingSeconds);

  useEffect(() => {
    const interval = setInterval(() => setRemaining(r => Math.max(0, r - 1)), 1000);
    return () => clearInterval(interval);
  }, []);

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const isExpiring = remaining < 60;

  return (
    <span className={isExpiring ? 'text-red-600 animate-pulse font-bold' : ''}>
      {minutes}:{seconds.toString().padStart(2, '0')}
    </span>
  );
}
```

### 3. Review Page (`/review/{instance_id}`)

**Data sources:** `GET /api/pending` (find by ID), `GET /api/audit/{instance_id}`

**Components:**
- **Request Detail Card:**
  - Full action description
  - All context key-value pairs in a table
  - Agent ID, required role, urgency, priority, tags
  - Tenant ID
  - Created timestamp
  - SLA countdown (prominent)
- **Audit Timeline:**
  - Vertical timeline of all events for this instance
  - Each event shows: timestamp, event type, reviewer (if any), reason
- **Decision Form:**
  - "Approve" button (green, primary)
  - "Reject" button (red, secondary)
  - Reason text area (optional, max 2048 chars)
  - Reviewer ID (auto-filled from session, or manual input)
  - Confirmation modal: "Are you sure you want to [approve/reject] this action?"
- **Decision Result:**
  - After submitting, show success banner
  - Redirect to `/pending` after 2 seconds

### 4. Audit Trail (`/audit`)

**Data source:** `GET /api/audit?limit=100`

**Components:**
- **Event Table:**
  - Columns: Timestamp, Instance ID (link to detail), Event, Agent, Urgency, Reviewer, Reason
  - Color-coded event badges
  - Sortable columns
  - Click row to navigate to `/audit/{instance_id}`
- **Limit Selector:** 25, 50, 100, 250, 500
- **Search/Filter:** by instance_id, agent_id, event type

### 5. Instance Audit Detail (`/audit/{instance_id}`)

**Data source:** `GET /api/audit/{instance_id}`

**Components:**
- **Instance Header:** instance_id, current status, total events
- **Event Timeline:** ordered chronological timeline
- **Metadata Viewer:** expandable JSON viewer for each event's metadata

### 6. System Metrics (`/metrics`)

**Data source:** `GET /api/metrics` (poll every 10s)

**Components:**
- **Uptime Counter:** from `metrics.uptime_seconds`
- **Request Counter:** `hitl.requests.total`
- **Decision Counter:** `hitl.decisions.total`
- **SLA Breach Counter:** `hitl.sla.timeouts.total`
- **Decision Latency Chart:** line chart with p50, p95, p99 from `hitl.decision.duration_seconds`
- **Auth Metrics:** success/failure counts
- **Rate Limit Rejected:** count
- **Webhook Latency:** Teams + callback latency histograms

### 7. Scenario Trigger (`/scenarios`)

**Data source:** Agent mock `GET /scenarios`, `POST /trigger/{scenario}`

**Components:**
- **Scenario Cards:** one per available scenario, showing:
  - Name, urgency, required role, description, tags
  - "Trigger" button
- **Recent Triggers:** list of recently triggered workflows with status

---

## CORS Configuration

The **agent mock** (FastAPI) has CORS fully open for development:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The **gateway** (Azure Functions) does NOT have CORS configured by default. For local development, add to `local.settings.json`:

```json
{
  "Host": {
    "CORS": "*",
    "CORSCredentials": false
  }
}
```

**For production**, restrict to your frontend domain:

```json
{
  "Host": {
    "CORS": "https://your-dashboard.azurewebsites.net",
    "CORSCredentials": true
  }
}
```

**Alternative: BFF proxy.** If your frontend has API routes (e.g., Next.js), proxy all calls through your backend to avoid CORS entirely:

```typescript
// pages/api/gateway/[...path].ts  (Next.js API route example)
export default async function handler(req, res) {
  const path = req.query.path.join('/');
  const gatewayResponse = await fetch(`${process.env.GATEWAY_URL}/${path}`, {
    method: req.method,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': process.env.HITL_API_KEY,
    },
    body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
  });

  const data = await gatewayResponse.json();
  res.status(gatewayResponse.status).json(data);
}
```

---

## Error Handling

### HTTP Status Code Reference

| Status | Meaning | Frontend Action |
|--------|---------|-----------------|
| 200 | Success | Display data |
| 202 | Accepted (async) | Show "submitted" state, poll for updates |
| 400 | Bad Request | Show validation error message from `detail` field |
| 401 | Unauthorized | Redirect to login / show auth error |
| 403 | Forbidden (HMAC) | Show security error, check HMAC config |
| 404 | Not Found | Show "not found" state |
| 409 | Conflict | Show "already decided" or "replay detected" |
| 422 | Validation Error | Show field-level errors from `detail` field |
| 429 | Rate Limited | Show retry message, respect `Retry-After` header |
| 500 | Server Error | Show generic error, log details |
| 503 | Unhealthy | Show degraded status indicator |

### Standard Error Shape

All errors from the gateway follow this structure:

```typescript
interface GatewayError {
  error: string;          // Short error code/message
  detail?: string;        // Human-readable detail (may contain Pydantic validation info)
  instance_id?: string;   // When relevant
  retry_after?: number;   // Seconds (for 429 responses)
}
```

### Recommended Error Handling Pattern

```typescript
async function gatewayFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${process.env.NEXT_PUBLIC_GATEWAY_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: 'Unknown error' }));

    if (res.status === 429) {
      const retryAfter = error.retry_after || 60;
      throw new RateLimitError(error.detail, retryAfter);
    }
    if (res.status === 401) {
      throw new AuthError(error.detail);
    }
    if (res.status === 409) {
      throw new ConflictError(error.detail);
    }

    throw new GatewayApiError(res.status, error.error, error.detail);
  }

  return res.json();
}
```

---

## Environment Variables

### Your Frontend App

```env
# Gateway connection
NEXT_PUBLIC_GATEWAY_URL=http://localhost:7072/api
NEXT_PUBLIC_AGENT_URL=http://localhost:7071

# Authentication (server-side only — never expose to browser)
HITL_API_KEY=your-api-key-here
HITL_WEBHOOK_SECRET=your-webhook-secret

# App config
NEXT_PUBLIC_POLLING_INTERVAL_PENDING=3000
NEXT_PUBLIC_POLLING_INTERVAL_STATS=5000
NEXT_PUBLIC_POLLING_INTERVAL_HEALTH=30000
```

### Gateway `local.settings.json` (backend)

Ensure these are set for local development:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "HITL_ENVIRONMENT": "development",
    "HITL_API_KEYS": "",
    "HITL_WEBHOOK_SECRET": "",
    "TEAMS_WEBHOOK_URL": "",
    "SLACK_WEBHOOK_URL": "",
    "ESCALATION_WEBHOOK_URL": "",
    "DASHBOARD_URL": "http://localhost:3000",
    "LOG_LEVEL": "INFO",
    "HITL_RATE_LIMIT_MAX": "30",
    "HITL_RATE_LIMIT_WINDOW": "60"
  },
  "Host": {
    "CORS": "*",
    "CORSCredentials": false
  }
}
```

---

## Deployment Architecture

### Local Development

```
localhost:3000   — Your fullstack app (Next.js / etc.)
localhost:7071   — Agent mock (FastAPI + uvicorn)
localhost:7072   — HITL Gateway (Azure Functions Core Tools)
localhost:10000  — Azurite (storage emulator)
```

### Azure Production

```
https://hitl-dashboard.azurewebsites.net    — Your frontend (Azure Static Web Apps or App Service)
https://hitl-gateway.azurewebsites.net/api  — HITL Gateway (Azure Functions)

Supporting services:
  - Azure Key Vault          — API keys, webhook secrets
  - Azure Cosmos DB          — Persistent audit trail (future)
  - Azure Cache for Redis    — Distributed rate limiting (future)
  - Application Insights     — Telemetry, logs, metrics
  - Azure Traffic Manager    — Global load balancing
```

### Recommended Azure Static Web App Setup

```yaml
# staticwebapp.config.json
{
  "routes": [
    {
      "route": "/api/gateway/*",
      "rewrite": "https://hitl-gateway.azurewebsites.net/api/*"
    }
  ],
  "navigationFallback": {
    "rewrite": "/index.html"
  }
}
```

---

## Agent Mock Endpoints

For testing and demo purposes, your frontend can interact with the agent mock directly.

### List Scenarios

**`GET http://localhost:7071/scenarios`**

```json
{
  "agent_id": "secops-agent-v2",
  "scenarios": [
    {
      "name": "lateral_movement",
      "urgency": "CRITICAL",
      "required_role": "SecOps_Lead",
      "description": "Isolate host 10.0.5.42...",
      "tags": ["security", "automated"]
    },
    {
      "name": "data_exfil",
      "urgency": "HIGH",
      "required_role": "SecOps_Lead",
      "description": "Block outbound traffic...",
      "tags": ["security", "dlp"]
    },
    {
      "name": "large_transaction",
      "urgency": "HIGH",
      "required_role": "Finance_Manager",
      "description": "Approve wire transfer...",
      "tags": ["finance", "high-value"]
    },
    {
      "name": "compliance_review",
      "urgency": "NORMAL",
      "required_role": "Compliance_Officer",
      "description": "Review data retention policy change...",
      "tags": ["compliance", "policy"]
    },
    {
      "name": "risk_assessment",
      "urgency": "LOW",
      "required_role": "Risk_Manager",
      "description": "Evaluate vendor risk score update...",
      "tags": ["risk", "vendor"]
    }
  ]
}
```

### Trigger Scenario

**`POST http://localhost:7071/trigger/{scenario_name}`**

> **Note:** This endpoint blocks until the HITL decision is made (by design — it simulates a real agent waiting). Use it in a fire-and-forget manner, or call it from a background process.

### Agent Status

**`GET http://localhost:7071/status`**

```json
{
  "agent_id": "secops-agent-v2",
  "tenant_id": "default",
  "total_workflows": 5,
  "active_workflows": 1,
  "processed_callbacks": 4,
  "workflows": [...],
  "available_scenarios": ["lateral_movement", "data_exfil", ...]
}
```

---

## Quick Reference: Frontend → Backend Flow

### Approve/Reject Flow

```
1. User opens /pending page
2. Frontend polls GET /api/pending every 3s
3. User clicks "Review" on a request → navigates to /review/{instance_id}
4. Frontend loads GET /api/audit/{instance_id} for timeline
5. User enters reason, clicks "Approve"
6. Frontend sends to BFF: POST /api/bff/decide/{instance_id}
7. BFF computes HMAC, sends POST /api/teams_webhook_callback/{instance_id}
8. Gateway raises HumanDecision event, orchestrator resumes
9. Gateway calls notify_agent → agent resumes
10. Frontend shows success, redirects to /pending
```

### Dashboard Load Flow

```
1. Page loads → parallel fetch:
   - GET /api/stats    → stat cards
   - GET /api/pending  → pending count + list
   - GET /api/health   → status indicator
2. Set up polling intervals
3. On each poll, update components reactively
```

### Scenario Trigger Flow (Demo/Testing)

```
1. User opens /scenarios
2. Frontend loads GET http://localhost:7071/scenarios
3. User clicks "Trigger" on a scenario
4. Frontend sends POST http://localhost:7071/trigger/{scenario} (fire-and-forget)
5. Agent mock sends HITLRequest to gateway
6. Request appears in /pending within 3s (next poll)
7. User can approve/reject from /pending or /review page
```
