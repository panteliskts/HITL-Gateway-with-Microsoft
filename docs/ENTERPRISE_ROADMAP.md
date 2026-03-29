# 🚀 HITL Gateway: S+ Tier Enterprise Roadmap

> **Mission**: Transform the Human-in-the-Loop Gateway from hackathon MVP to enterprise-grade, production-ready platform that demonstrates Microsoft Azure excellence

---

## 📋 Executive Summary

This roadmap outlines the strategic path from prototype to **production-ready enterprise platform** that showcases:

- **Azure architectural excellence** (Durable Functions, Cosmos DB, Service Bus, Event Grid)
- **Enterprise security & compliance** (Zero Trust, SOC 2, GDPR, audit trails)
- **Production-grade reliability** (99.95% SLA, multi-region, disaster recovery)
- **Advanced AI integration** (Azure OpenAI, AI-assisted decisions, anomaly detection)
- **Developer experience** (SDK, Terraform modules, comprehensive docs)

**Target Audience**: Microsoft engineers, Azure architects, enterprise decision-makers

---

## 🎯 Success Criteria (What "S+ Tier" Means)

### Technical Excellence

- [ ] **Cloud-native architecture** following Azure Well-Architected Framework pillars
- [ ] **Production SLA**: 99.95% uptime with multi-region failover
- [ ] **Security**: Zero Trust architecture, RBAC, managed identities
- [ ] **Scalability**: Handle 10,000+ concurrent HITL requests
- [ ] **Observability**: Distributed tracing, metrics, alerting via Azure Monitor

### Business Impact

- [ ] **Clear ROI**: Demonstrate cost savings and risk reduction
- [ ] **Compliance-ready**: SOC 2, ISO 27001, HIPAA, GDPR alignment
- [ ] **Enterprise adoption**: SDK + docs enabling Fortune 500 deployment
- [ ] **Thought leadership**: Azure blog post, Microsoft Learn module

### Innovation

- [ ] **AI-powered insights**: GPT-4 decision recommendations
- [ ] **Advanced patterns**: Multi-stage approvals, collaborative review
- [ ] **Ecosystem integration**: Works with Sentinel, Defender, Logic Apps

---

## 📅 Phased Implementation (6-Month Timeline)

```
Phase 1: Foundation       Phase 2: Production      Phase 3: Scale         Phase 4: Innovation
  (Weeks 1-4)              (Weeks 5-8)              (Weeks 9-12)          (Weeks 13-24)
      │                        │                        │                     │
      ├─ Security              ├─ Web Dashboard         ├─ Multi-Region       ├─ AI Assistance
      ├─ Architecture          ├─ Persistent Storage    ├─ Enterprise Auth    ├─ Advanced Analytics
      ├─ Observability         ├─ RBAC                  ├─ SDK + Terraform    ├─ Ecosystem Integration
      └─ Testing               └─ CI/CD                 └─ Performance        └─ Thought Leadership
```

---

## 🏗️ Phase 1: Production Foundation (Weeks 1-4)

**Goal**: Transform MVP into secure, observable, testable foundation

### 1.1 Security Hardening (Week 1)

#### Critical Fixes

```python
# Priority 1: API Authentication
- [ ] Azure AD B2C integration for dashboard users
- [ ] Managed Identity authentication for agent-to-gateway calls
- [ ] API key validation with Azure Key Vault rotation
- [ ] mTLS (mutual TLS) for agent connections in production

# Priority 2: Input Validation & Sanitization
- [ ] Strict schema validation with Pydantic v2
- [ ] XSS protection (escape all user inputs in Teams cards)
- [ ] SSRF protection (whitelist callback_url domains)
- [ ] SQL injection prevention (use parameterized queries)

# Priority 3: Webhook Security
- [ ] HMAC signature validation for Teams/SMS webhooks
- [ ] Replay attack prevention (nonce + timestamp validation)
- [ ] Rate limiting per agent_id (10 requests/min default)
```

**Deliverable**: Security audit report with penetration test results

#### Implementation Example

```python
# function_app.py - Secure endpoint
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import hmac
import hashlib

# Load secrets from Key Vault
kv_client = SecretClient(
    vault_url=os.getenv("KEY_VAULT_URL"),
    credential=DefaultAzureCredential()
)

@app.route(route="hitl_ingress", auth_level=func.AuthLevel.ANONYMOUS)
@limiter.limit("10/minute")
async def hitl_ingress(req: HttpRequest) -> HttpResponse:
    # 1. Validate API key from Key Vault
    api_key = req.headers.get("X-API-Key")
    expected_key = kv_client.get_secret("hitl-api-key").value

    if not hmac.compare_digest(api_key or "", expected_key):
        logger.warning("Unauthorized access attempt")
        return HttpResponse("Unauthorized", status_code=401)

    # 2. Validate callback URL
    body = await req.get_json()
    callback_url = body.get("callback_url", "")

    if not is_allowed_callback_domain(callback_url):
        return HttpResponse("Invalid callback_url domain", status_code=400)

    # 3. Sanitize inputs
    body["action_description"] = sanitize_html(body["action_description"])

    # Proceed with orchestration...
```

---

### 1.2 Cloud Architecture Refactoring (Week 2)

**Current State**: Monolithic function app with in-memory state
**Target State**: Distributed, event-driven, cloud-native architecture

#### Architecture Diagram (Target)

```
┌─────────────────────────────────────────────────────────────────┐
│  Edge Layer: Azure Front Door + WAF                             │
│  • Global load balancing                                         │
│  • DDoS protection                                               │
│  • SSL/TLS termination                                           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  API Layer: Azure API Management                                │
│  • Rate limiting (per agent, per tenant)                        │
│  • OAuth2 token validation                                      │
│  • Request/response caching                                     │
│  • API versioning (v1, v2)                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────┬──────────────────────┬───────────────────┐
│  Gateway Functions   │  Dashboard API       │  Analytics Jobs   │
│  (Durable)           │  (HTTP triggers)     │  (Timer triggers) │
│  • Orchestrator      │  • GET /pending      │  • Daily rollups  │
│  • Activities        │  • POST /decide      │  • SLA reports    │
│  Port: 7072          │  Port: 7073          │                   │
└──────────────────────┴──────────────────────┴───────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Event Bus: Azure Event Grid                                    │
│  • hitl.request.created                                         │
│  • hitl.decision.approved                                       │
│  • hitl.sla.timeout                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────┬──────────────┬──────────────┬──────────────────┐
│ Cosmos DB    │ Azure Cache  │ Blob Storage │ Service Bus      │
│ • Requests   │ for Redis    │ • Attachments│ • Dead letter    │
│ • Audit logs │ • Sessions   │ • Exports    │ • Retry queue    │
│ • Analytics  │ • Rate limit │              │                  │
└──────────────┴──────────────┴──────────────┴──────────────────┘
```

#### Key Changes

```yaml
# Infrastructure as Code (Bicep)
- [ ] Separate Function Apps (gateway, dashboard, analytics)
- [ ] Azure Event Grid for event-driven communication
- [ ] Azure Service Bus for reliable message queueing
- [ ] Azure Cache for Redis (replace in-memory state)
- [ ] Azure Cosmos DB (replace console logs)
- [ ] Azure Blob Storage (attachments, exports)
- [ ] Azure Application Gateway (L7 load balancing)
```

**Deliverable**: Bicep/Terraform templates for full infrastructure

---

### 1.3 Observability & Monitoring (Week 2)

**Implement Azure Monitor stack for production-grade observability**

#### Distributed Tracing

```python
# Enable OpenTelemetry with Azure Monitor
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics

configure_azure_monitor(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
)

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Custom metrics
hitl_requests_counter = meter.create_counter(
    "hitl.requests.total",
    description="Total HITL requests received"
)

approval_time_histogram = meter.create_histogram(
    "hitl.approval.duration_seconds",
    description="Time from request to decision"
)

# In orchestrator
with tracer.start_as_current_span("hitl_orchestrator") as span:
    span.set_attribute("agent_id", request.agent_id)
    span.set_attribute("urgency", request.urgency)

    start_time = datetime.utcnow()
    # ... wait for decision ...
    duration = (datetime.utcnow() - start_time).total_seconds()

    approval_time_histogram.record(duration, {
        "urgency": request.urgency,
        "status": final_status
    })
```

#### Alerts & Dashboards

```kql
-- Alert: High SLA timeout rate
let threshold = 0.10; // 10%
HITLRequests
| where timestamp > ago(1h)
| summarize
    total = count(),
    timeouts = countif(status == "ESCALATED")
| extend timeout_rate = todouble(timeouts) / todouble(total)
| where timeout_rate > threshold
```

**Deliverables**:

- [ ] Application Insights workspace configured
- [ ] 10+ custom metrics instrumented
- [ ] 5+ alerts (SLA timeout rate, error rate, latency p95)
- [ ] Grafana dashboard (or Azure Workbooks)
- [ ] Log Analytics queries for audit trail

---

### 1.4 Testing & Quality Assurance (Week 3-4)

**Build comprehensive test suite for production confidence**

#### Test Pyramid

```
                    ▲
                   ╱ ╲
                  ╱ E2E╲           5 tests  (Playwright)
                 ╱─────╲
                ╱       ╲
               ╱Integration╲      20 tests (pytest-asyncio)
              ╱───────────╲
             ╱             ╲
            ╱  Unit Tests   ╲    100 tests (pytest)
           ╱─────────────────╲
```

#### Unit Tests (pytest)

```python
# tests/test_schemas.py
import pytest
from schemas import HITLRequest, UrgencyLevel

def test_hitl_request_validation():
    """Test Pydantic validation catches invalid urgency"""
    with pytest.raises(ValidationError):
        HITLRequest(
            agent_id="test",
            action_description="test",
            urgency="INVALID",  # Should fail
            required_role="test"
        )

def test_sla_timeout_mapping():
    """Verify SLA timeouts match spec"""
    assert SLA_TIMEOUT_SECONDS[UrgencyLevel.CRITICAL] == 300
    assert SLA_TIMEOUT_SECONDS[UrgencyLevel.HIGH] == 900

# tests/test_security.py
def test_callback_url_ssrf_protection():
    """Ensure internal IPs are blocked"""
    assert not is_allowed_callback_domain("http://localhost:8080")
    assert not is_allowed_callback_domain("http://169.254.169.254")  # AWS metadata
    assert is_allowed_callback_domain("https://agent.mycompany.com")
```

#### Integration Tests

```python
# tests/test_integration.py
import pytest
from azure.durable_functions.models import DurableOrchestrationClient

@pytest.mark.asyncio
async def test_full_hitl_flow_approval():
    """Test complete flow: submit → approve → callback"""
    # 1. Submit HITL request
    response = await client.post("/api/hitl_ingress", json={
        "agent_id": "test-agent",
        "action_description": "Delete user account",
        "urgency": "HIGH",
        "required_role": "Security_Admin",
        "callback_url": "https://test-agent.example.com/resume"
    })
    assert response.status_code == 202
    instance_id = response.json()["instance_id"]

    # 2. Submit approval within SLA
    await client.post(f"/api/teams_webhook_callback/{instance_id}", json={
        "status": "APPROVED",
        "reviewer_id": "test@example.com",
        "reason": "Integration test"
    })

    # 3. Verify audit trail
    audit_logs = await cosmos_client.query(
        f"SELECT * FROM c WHERE c.instance_id = '{instance_id}'"
    )
    assert len(audit_logs) >= 3  # PENDING, APPROVED, COMPLETE
```

#### E2E Tests (Playwright)

```typescript
// tests/e2e/dashboard.spec.ts
test('reviewer can approve CRITICAL request', async ({ page }) => {
  // 1. Navigate to dashboard
  await page.goto('https://dashboard.example.com');

  // 2. Trigger mock CRITICAL request
  await page.click('[data-testid="mock-critical-btn"]');

  // 3. Verify card appears
  await expect(page.locator('.hitl-card-CRITICAL')).toBeVisible();

  // 4. Click Review
  await page.click('.hitl-card-CRITICAL [data-testid="review-btn"]');

  // 5. Enter reason and approve
  await page.fill('[data-testid="reason-input"]', 'E2E test approval');
  await page.click('[data-testid="approve-btn"]');

  // 6. Verify card disappears (optimistic UI)
  await expect(page.locator('.hitl-card-CRITICAL')).toBeHidden();
});
```

**Deliverables**:

- [ ] 100+ unit tests (>85% code coverage)
- [ ] 20+ integration tests (API + Azure Functions)
- [ ] 5+ E2E tests (critical user flows)
- [ ] Load tests (1000 concurrent requests, <200ms p95 latency)
- [ ] Chaos tests (region failover, Cosmos DB throttling)

---

## 🎨 Phase 2: Production Experience (Weeks 5-8)

**Goal**: Build enterprise-grade UI, persistent storage, and CI/CD

### 2.1 Web Dashboard (Next.js 15) (Week 5-6)

**Replace `demo_ui.html` with production-ready React dashboard**

#### Tech Stack

```json
{
  "framework": "Next.js 15 (App Router)",
  "ui": "shadcn/ui + Radix UI",
  "state": "Zustand + React Query",
  "realtime": "Azure SignalR Service",
  "auth": "NextAuth.js + Azure AD B2C",
  "deployment": "Azure Static Web Apps (Standard)"
}
```

#### Features (Must-Have)

```yaml
Pages:
  - Dashboard (/) : Live HITL queue with auto-refresh
  - Request Detail (/request/[id]) : Full context, attachments, history
  - Audit Trail (/audit) : Filterable timeline, CSV export
  - Analytics (/analytics) : Charts, KPIs, trends
  - Settings (/settings) : Webhooks, SLA overrides, RBAC

Components:
  - HITLCard : Urgency-coded, SLA countdown, quick actions
  - ReviewModal : Full context, reason input, approve/reject
  - AuditTimeline : Vertical timeline with state transitions
  - AnalyticsChart : Recharts-based, responsive
  - NotificationBanner : Toast notifications (Sonner)
```

#### Real-Time Updates (SignalR)

```typescript
// lib/signalr.ts
import * as signalR from '@microsoft/signalr';

export const createConnection = () => {
  return new signalR.HubConnectionBuilder()
    .withUrl(`${process.env.NEXT_PUBLIC_API_URL}/api/dashboard/hub`, {
      accessTokenFactory: () => session?.accessToken
    })
    .withAutomaticReconnect({
      nextRetryDelayInMilliseconds: (context) => {
        return Math.min(1000 * Math.pow(2, context.previousRetryCount), 30000);
      }
    })
    .configureLogging(signalR.LogLevel.Information)
    .build();
};

// app/dashboard/page.tsx
useEffect(() => {
  const connection = createConnection();

  connection.on('NewHITLRequest', (request: HITLRequest) => {
    queryClient.setQueryData(['hitl', 'pending'], (old) => [request, ...old]);

    if (request.urgency === 'CRITICAL') {
      playNotificationSound();
      showToast('CRITICAL request received', { variant: 'destructive' });
    }
  });

  connection.start();
  return () => connection.stop();
}, []);
```

**Deliverables**:

- [ ] Next.js dashboard with 5 core pages
- [ ] Real-time updates via SignalR
- [ ] Azure AD B2C authentication
- [ ] Mobile-responsive (Tailwind breakpoints)
- [ ] Accessibility (WCAG 2.1 AA compliance)

---

### 2.2 Persistent Storage Architecture (Week 6)

**Migrate from in-memory/temp storage to production data layer**

#### Cosmos DB Schema Design

```javascript
// Container: hitl_requests (PartitionKey: /tenant_id)
{
  "id": "req-20260327-abc123",
  "type": "request",
  "tenant_id": "contoso-corp",
  "instance_id": "durablefunc-xyz789",
  "agent_id": "secops-agent-v2",
  "status": "PENDING",  // PENDING | APPROVED | REJECTED | ESCALATED | COMPLETE
  "urgency": "CRITICAL",
  "required_role": "SecOps_Lead",
  "action_description": "Isolate host 10.0.5.42",
  "context": { "source_ip": "10.0.5.42", "confidence": 0.97 },
  "callback_url": "https://agent.example.com/resume",
  "timestamps": {
    "created": "2026-03-27T10:00:00Z",
    "decided": "2026-03-27T10:02:34Z",
    "completed": "2026-03-27T10:02:35Z"
  },
  "reviewer_id": "jane.doe@contoso.com",
  "reason": "Reviewed logs — isolate immediately",
  "ttl": 2592000  // 30 days auto-delete
}

// Container: audit_trail (PartitionKey: /instance_id)
{
  "id": "audit-abc123-pending",
  "type": "audit",
  "instance_id": "durablefunc-xyz789",
  "event": "PENDING",
  "timestamp": "2026-03-27T10:00:00Z",
  "metadata": { "agent_id": "secops-agent-v2", "urgency": "CRITICAL" }
}

// Container: analytics (PartitionKey: /date)
{
  "id": "analytics-20260327",
  "type": "daily_rollup",
  "date": "2026-03-27",
  "tenant_id": "contoso-corp",
  "metrics": {
    "total_requests": 247,
    "approved": 189,
    "rejected": 42,
    "escalated": 16,
    "avg_approval_time_seconds": 134.5
  }
}
```

#### Redis Cache Strategy

```python
# Use Redis for:
# 1. Rate limiting (sliding window)
# 2. Active session tracking (reviewer presence)
# 3. Hot data caching (pending requests < 1 hour old)

import redis.asyncio as redis

redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

async def check_rate_limit(agent_id: str) -> bool:
    """Sliding window rate limiter (10 req/min)"""
    key = f"ratelimit:{agent_id}"
    now = int(datetime.utcnow().timestamp())

    # Remove old entries (>60 sec ago)
    await redis_client.zremrangebyscore(key, 0, now - 60)

    # Count recent requests
    count = await redis_client.zcard(key)
    if count >= 10:
        return False

    # Add current timestamp
    await redis_client.zadd(key, {str(now): now})
    await redis_client.expire(key, 60)
    return True
```

**Deliverables**:

- [ ] Cosmos DB containers with optimized partitioning
- [ ] Redis cache layer for hot paths
- [ ] Blob Storage for attachments (SAS tokens)
- [ ] Data retention policies (GDPR compliance)

---

### 2.3 Role-Based Access Control (Week 7)

**Implement enterprise-grade authorization**

#### Azure AD B2C Integration

```typescript
// NextAuth.js configuration
import { NextAuthOptions } from 'next-auth';
import AzureADB2CProvider from 'next-auth/providers/azure-ad-b2c';

export const authOptions: NextAuthOptions = {
  providers: [
    AzureADB2CProvider({
      tenantId: process.env.AZURE_AD_B2C_TENANT_NAME,
      clientId: process.env.AZURE_AD_B2C_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_B2C_CLIENT_SECRET!,
      primaryUserFlow: process.env.AZURE_AD_B2C_PRIMARY_USER_FLOW,
      authorization: { params: { scope: 'openid profile email offline_access' } },
    })
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token;
        token.roles = account.roles; // AD groups
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.user.roles = token.roles;
      return session;
    }
  }
};
```

#### Role Mapping

```python
# Map Azure AD groups to HITL roles
ROLE_MAPPINGS = {
    "AAD-SecOps-Lead": "SecOps_Lead",
    "AAD-Finance-Manager": "Finance_Manager",
    "AAD-Compliance-Officer": "Compliance_Officer",
    "AAD-Risk-Manager": "Risk_Manager"
}

async def authorize_decision(user_roles: List[str], required_role: str) -> bool:
    """Check if user has permission to decide this HITL request"""
    mapped_roles = [ROLE_MAPPINGS.get(r) for r in user_roles]
    return required_role in mapped_roles or "Admin" in user_roles
```

**Deliverables**:

- [ ] Azure AD B2C tenant configured
- [ ] Role-based UI (users only see requests for their roles)
- [ ] Admin panel for role management
- [ ] Audit log for authorization failures

---

### 2.4 CI/CD Pipeline (Week 8)

**Automate build, test, deploy with GitHub Actions**

#### Pipeline Architecture

```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'

  deploy-infra:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    steps:
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy Bicep templates
        run: |
          az deployment group create \
            --resource-group rg-hitl-prod \
            --template-file infra/main.bicep \
            --parameters @infra/params.prod.json

  deploy-functions:
    needs: deploy-infra
    runs-on: ubuntu-latest
    steps:
      - name: Deploy Azure Functions
        uses: Azure/functions-action@v1
        with:
          app-name: func-hitl-gateway-prod
          package: ./gateway
          respect-funcignore: true
```

**Deliverables**:

- [ ] GitHub Actions workflows (test, deploy)
- [ ] Blue-green deployment strategy
- [ ] Automated rollback on health check failure
- [ ] Secrets management (GitHub secrets + Key Vault)

---

## 🌍 Phase 3: Enterprise Scale (Weeks 9-12)

**Goal**: Multi-region, high availability, global scalability

### 3.1 Multi-Region Deployment (Week 9-10)

#### Architecture

```
Primary Region: East US 2
  ├─ Azure Functions (active)
  ├─ Cosmos DB (write region)
  └─ Redis Cache (primary)

Secondary Region: West Europe
  ├─ Azure Functions (standby)
  ├─ Cosmos DB (read replica)
  └─ Redis Cache (replica)

Global Services:
  ├─ Azure Front Door (global load balancer)
  ├─ Azure Traffic Manager (DNS-based routing)
  └─ Cosmos DB (multi-region write via Strong Consistency)
```

#### Health Checks & Failover

```python
# health_check.py
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
async def health_check(req: HttpRequest) -> HttpResponse:
    """Deep health check for Traffic Manager probe"""
    checks = {
        "cosmos_db": await check_cosmos_health(),
        "redis": await check_redis_health(),
        "storage": await check_blob_health(),
        "durable_functions": await check_durable_state()
    }

    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503

    return HttpResponse(
        json.dumps({"status": "healthy" if all_healthy else "degraded", "checks": checks}),
        status_code=status_code,
        mimetype="application/json"
    )
```

**Deliverables**:

- [ ] Active-active multi-region setup
- [ ] Automatic failover (Traffic Manager)
- [ ] Cross-region replication (Cosmos DB)
- [ ] Disaster recovery runbook

---

### 3.2 SDK & Developer Experience (Week 10-11)

**Make it trivial for agents to integrate**

#### Python SDK

```python
# hitl_sdk/client.py
from hitl_sdk import HITLClient

client = HITLClient(
    gateway_url="https://hitl-gateway.contoso.com",
    api_key=os.getenv("HITL_API_KEY"),
    agent_id="my-python-agent"
)

# Simple synchronous call
decision = await client.request_approval(
    action="Delete production database 'users'",
    urgency="CRITICAL",
    required_role="DBA_Lead",
    context={"database": "users", "size_gb": 450}
)

if decision.approved:
    execute_deletion()
else:
    logger.info(f"Deletion rejected: {decision.reason}")
```

#### JavaScript SDK

```typescript
// @hitl/sdk
import { HITLClient } from '@hitl/sdk';

const client = new HITLClient({
  gatewayUrl: process.env.HITL_GATEWAY_URL,
  apiKey: process.env.HITL_API_KEY,
  agentId: 'nodejs-trading-bot'
});

// With timeout handling
const decision = await client.requestApproval({
  action: 'Execute $100k trade: BUY 1000 AAPL @ $150',
  urgency: 'HIGH',
  requiredRole: 'Trading_Manager',
  context: { symbol: 'AAPL', quantity: 1000, price: 150 },
  timeoutMs: 60000  // Fail-fast after 1 min
});
```

#### Terraform Module

```hcl
# terraform/modules/hitl-agent/main.tf
module "hitl_integration" {
  source  = "hashicorp/hitl-gateway/azure"
  version = "~> 1.0"

  gateway_url       = "https://hitl-gateway.contoso.com"
  agent_id          = "terraform-provisioner"
  required_role     = "InfraOps_Lead"
  callback_endpoint = azurerm_function_app.agent.default_hostname

  managed_identity_id = azurerm_user_assigned_identity.agent.id
}

resource "azurerm_function_app" "agent" {
  # ... agent function app config ...

  app_settings = {
    HITL_GATEWAY_URL = module.hitl_integration.gateway_url
    HITL_API_KEY     = module.hitl_integration.api_key_secret_id  # Ref to Key Vault
  }
}
```

**Deliverables**:

- [ ] Python SDK (PyPI package)
- [ ] TypeScript SDK (npm package)
- [ ] Terraform module (Terraform Registry)
- [ ] Comprehensive docs (readthedocs.io)

---

### 3.3 Performance Optimization (Week 11)

**Target: <100ms p50, <500ms p95 latency**

#### Optimizations

```yaml
Database:
  - [ ] Cosmos DB: Utilize session consistency (not strong)
  - [ ] Cosmos DB: Partition by tenant_id (not instance_id)
  - [ ] Redis: Cache pending requests (TTL 5 min)
  - [ ] Query optimization: Use indexed fields only

Functions:
  - [ ] Cold start mitigation: Premium plan with always-on
  - [ ] Connection pooling: Reuse HTTP clients
  - [ ] Async everything: FastAPI + asyncio

API Gateway:
  - [ ] Response caching (304 Not Modified)
  - [ ] Compression (gzip, brotli)
  - [ ] CDN for static assets (Front Door)
```

#### Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between

class HITLUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def submit_request(self):
        self.client.post("/api/hitl_ingress", json={
            "agent_id": f"agent-{self.user_id}",
            "action_description": "Load test action",
            "urgency": "NORMAL",
            "required_role": "Test_Admin",
            "callback_url": "https://agent.example.com/resume"
        })

    @task(1)
    def get_pending(self):
        self.client.get("/api/dashboard/pending")

# Run: locust -f locustfile.py --users 1000 --spawn-rate 50
```

**Deliverables**:

- [ ] Load test results (10K concurrent users)
- [ ] Performance tuning report
- [ ] Cost optimization analysis

---

### 3.4 Compliance & Governance (Week 12)

**Prepare for SOC 2, ISO 27001, GDPR audits**

#### Compliance Checklist

```yaml
Data Protection (GDPR):
  - [ ] Data residency controls (EU data stays in EU regions)
  - [ ] Right to erasure (DELETE /api/user/{id}/data)
  - [ ] Data portability (export in JSON/CSV)
  - [ ] Consent management (opt-in for analytics)
  - [ ] Privacy policy and terms of service

Security (SOC 2):
  - [ ] Encryption at rest (Cosmos DB, Blob Storage)
  - [ ] Encryption in transit (TLS 1.3 min)
  - [ ] Access logging (all API calls)
  - [ ] Incident response plan
  - [ ] Annual penetration testing

Auditability:
  - [ ] Immutable audit trail (Cosmos DB with append-only)
  - [ ] Tamper-proof logs (blockchain anchoring optional)
  - [ ] Retention policies (7 years for financial)
  - [ ] Export to SIEM (Sentinel, Splunk)
```

**Deliverables**:

- [ ] Compliance documentation
- [ ] GDPR data processing agreement template
- [ ] Security whitepaper

---

## 🤖 Phase 4: AI & Innovation (Weeks 13-24)

**Goal**: Differentiate with cutting-edge AI features

### 4.1 AI-Assisted Approvals (Week 13-15)

**Use Azure OpenAI to recommend decisions**

#### Implementation

```python
# ai_assistant.py
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01"
)

async def get_ai_recommendation(request: HITLRequest) -> dict:
    """GPT-4 analyzes context and suggests decision"""

    # Fetch similar past cases
    similar_cases = await cosmos_client.query(
        f"""
        SELECT TOP 10 * FROM c
        WHERE c.agent_id = '{request.agent_id}'
          AND c.urgency = '{request.urgency}'
        ORDER BY c.timestamps.created DESC
        """
    )

    prompt = f"""
You are an AI assistant helping security reviewers make HITL decisions.

Current Request:
- Agent: {request.agent_id}
- Action: {request.action_description}
- Urgency: {request.urgency}
- Context: {json.dumps(request.context)}

Similar Past Cases (last 10):
{json.dumps(similar_cases, indent=2)}

Analyze this request and provide:
1. Recommendation: APPROVE | REJECT | UNCERTAIN
2. Confidence: 0-100%
3. Reasoning: 2-3 sentences
4. Risk factors: List any concerns

Format your response as JSON.
"""

    response = await client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a security analyst AI assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
```

#### UI Integration

```typescript
// Show AI recommendation in review modal
<Card className="border-blue-500 bg-blue-50">
  <CardHeader>
    <CardTitle>AI Recommendation</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="flex items-center gap-2">
      <Badge variant={recommendation.decision === 'APPROVE' ? 'success' : 'warning'}>
        {recommendation.decision}
      </Badge>
      <span className="text-sm text-muted-foreground">
        {recommendation.confidence}% confidence
      </span>
    </div>
    <p className="mt-2 text-sm">{recommendation.reasoning}</p>
    {recommendation.risk_factors.length > 0 && (
      <Alert variant="warning" className="mt-3">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Risk Factors</AlertTitle>
        <AlertDescription>
          <ul className="list-disc list-inside">
            {recommendation.risk_factors.map(r => <li key={r}>{r}</li>)}
          </ul>
        </AlertDescription>
      </Alert>
    )}
  </CardContent>
</Card>
```

**Deliverables**:

- [ ] GPT-4 integration for decision recommendations
- [ ] UI showing AI suggestions (human has final say)
- [ ] Feedback loop (track when humans override AI)

---

### 4.2 Advanced Analytics & ML (Week 16-18)

**Build predictive models for insights**

#### Anomaly Detection

```python
# Detect unusual patterns (e.g., spike in rejections for an agent)
from azure.ai.anomalydetector import AnomalyDetectorClient

detector_client = AnomalyDetectorClient(
    endpoint=os.getenv("ANOMALY_DETECTOR_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("ANOMALY_DETECTOR_KEY"))
)

async def detect_agent_anomalies(agent_id: str):
    """Check if agent's HITL pattern is unusual"""
    # Get last 30 days of request counts
    timeseries = await get_agent_daily_counts(agent_id, days=30)

    response = detector_client.detect_entire_series(
        body={
            "granularity": "daily",
            "series": timeseries
        }
    )

    if response.is_anomaly[-1]:  # Latest datapoint
        await send_alert(
            f"Anomaly detected: {agent_id} has unusual HITL volume",
            severity="WARNING"
        )
```

#### Dashboards

```typescript
// Analytics page with ML insights
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {/* Predictive SLA */}
  <Card>
    <CardHeader>
      <CardTitle>SLA Prediction</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-3xl font-bold">87%</div>
      <p className="text-sm text-muted-foreground">
        Predicted approval rate for next 24h
      </p>
    </CardContent>
  </Card>

  {/* Agent Health Score */}
  <Card>
    <CardHeader>
      <CardTitle>Agent Health</CardTitle>
    </CardHeader>
    <CardContent>
      <AgentHealthChart data={agentHealthScores} />
    </CardContent>
  </Card>
</div>
```

**Deliverables**:

- [ ] Anomaly detection for unusual patterns
- [ ] Predictive analytics (SLA forecast)
- [ ] Agent health scoring
- [ ] Automated insights reports (weekly email)

---

### 4.3 Ecosystem Integration (Week 19-21)

**Connect to Microsoft security stack**

#### Microsoft Sentinel Integration

```python
# Ingest Sentinel incidents as HITL requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.securityinsight import SecurityInsights

sentinel_client = SecurityInsights(
    credential=DefaultAzureCredential(),
    subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
    resource_group_name="rg-sentinel",
    workspace_name="workspace-soc"
)

@app.timer_trigger(schedule="0 */5 * * * *")  # Every 5 min
async def poll_sentinel_incidents(timer: func.TimerRequest):
    """Check for high-severity Sentinel incidents requiring HITL"""
    incidents = sentinel_client.incidents.list(
        filter="properties/severity eq 'High' and properties/status eq 'New'"
    )

    for incident in incidents:
        # Create HITL request for each new high-severity incident
        await submit_hitl_request(
            agent_id="sentinel-integration",
            action_description=f"Close incident: {incident.title}",
            urgency="HIGH",
            required_role="SecOps_Lead",
            context={
                "incident_id": incident.name,
                "severity": incident.properties.severity,
                "tactics": incident.properties.additional_data.tactics
            }
        )
```

#### Microsoft Defender Integration

```python
# Execute approved actions in Defender
async def execute_defender_action(decision: HITLResponse):
    """Isolate machine in Defender after HITL approval"""
    if decision.status != "APPROVED":
        return

    defender_client = MicrosoftDefenderClient(
        credential=DefaultAzureCredential()
    )

    machine_id = decision.context["machine_id"]
    await defender_client.machines.isolate(
        machine_id=machine_id,
        isolation_type="Full",
        comment=f"HITL approved by {decision.reviewer_id}: {decision.reason}"
    )
```

**Deliverables**:

- [ ] Sentinel incident ingestion
- [ ] Defender action execution
- [ ] Logic Apps connectors
- [ ] Power Automate integrations

---

### 4.4 Thought Leadership (Week 22-24)

**Establish credibility with Microsoft and community**

#### Content Strategy

```yaml
Blog Posts (Microsoft Tech Community):
  - [ ] "Building a Human-in-the-Loop Gateway for Autonomous AI Agents"
  - [ ] "Zero Trust Architecture for AI Agent Authorization"
  - [ ] "Lessons Learned: Running HITL at 10K Requests/Day"

Microsoft Learn Module:
  - [ ] "Tutorial: Implement HITL for Azure AI Agents"
  - [ ] Learning path: AI Safety & Governance

Conference Talks:
  - [ ] Microsoft Build 2026: Demo booth
  - [ ] Azure + AI Conference: 30-min session
  - [ ] Local meetups (Azure user groups)

Open Source:
  - [ ] GitHub repo (MIT license)
  - [ ] Sample integrations (Python, Node.js, .NET)
  - [ ] Community contributions (issues, PRs)
```

#### Case Studies

```markdown
# Case Study: Contoso Financial Services

**Challenge**: Trading bots executing $100K+ trades without oversight

**Solution**: HITL Gateway with 5-minute SLA for high-value trades

**Results**:
- Prevented $2.4M in fraudulent trades (14 catches in 6 months)
- 97% approval rate (low false positive rate)
- Average decision time: 2 min 34 sec
- ROI: 12x (cost of gateway vs. prevented losses)
```

**Deliverables**:

- [ ] 3+ blog posts published
- [ ] Microsoft Learn module submitted
- [ ] 2+ case studies
- [ ] Conference talk accepted

---

## 📊 Success Metrics & KPIs

### Technical Metrics

| Metric                   | Target | Measurement                |
| ------------------------ | ------ | -------------------------- |
| **Uptime**         | 99.95% | Azure Monitor availability |
| **Latency (p95)**  | <500ms | Application Insights       |
| **Error Rate**     | <0.1%  | Failed requests / total    |
| **Test Coverage**  | >85%   | pytest --cov               |
| **Security Score** | A+     | Azure Security Center      |

### Business Metrics

| Metric                     | Target      | Measurement           |
| -------------------------- | ----------- | --------------------- |
| **Approval Rate**    | 80-90%      | Approved / total      |
| **SLA Compliance**   | >95%        | Decisions within SLA  |
| **Cost per Request** | <$0.01      | Azure Cost Management |
| **Adoption**         | 10+ tenants | Active customers      |
| **NPS**              | >50         | User surveys          |

---

## 💰 Cost Analysis

### Monthly Cost Estimate (Production)

```
Azure Functions (Premium EP2, 3 instances):        $450
Cosmos DB (10K RU/s autoscale, multi-region):      $600
Redis Cache (Enterprise E10, 12 GB):               $400
SignalR Service (Standard S1, 2 units):            $100
Front Door (Premium, 100K requests/day):           $200
Application Insights (20 GB/month):                $40
Blob Storage (500 GB):                             $10
Azure Monitor (alerts, dashboards):                $30
─────────────────────────────────────────────────
TOTAL:                                             $1,830/month
                                                   ($21,960/year)
```

### Cost Optimization Strategies

- [ ] Use Cosmos DB serverless for dev/test ($0 when idle)
- [ ] Reserved instances (1-year commitment = 38% savings)
- [ ] Auto-shutdown for non-prod environments
- [ ] Compression for storage (reduce blob costs)

---

## 🎓 Learning Resources for Team

### Prerequisites

```yaml
Azure Fundamentals:
  - [ ] AZ-900: Azure Fundamentals
  - [ ] Azure Well-Architected Framework (5 pillars)

Development:
  - [ ] Python async/await patterns
  - [ ] Azure Durable Functions deep dive
  - [ ] Cosmos DB data modeling

Security:
  - [ ] Azure AD B2C configuration
  - [ ] Zero Trust architecture principles
  - [ ] OWASP Top 10 for APIs
```

### Recommended Courses

- Microsoft Learn: "Build serverless apps with Azure Functions"
- Pluralsight: "Azure Cosmos DB Deep Dive"
- LinkedIn Learning: "Azure Security Engineering"

---

## 🚀 Next Steps (Immediate Actions)

### Week 1 Priorities

1. **Set up environments**:

   ```bash
   # Create resource groups
   az group create --name rg-hitl-dev --location eastus2
   az group create --name rg-hitl-staging --location eastus2
   az group create --name rg-hitl-prod --location eastus2
   ```
2. **Security first**:

   - Implement API key validation (1 day)
   - Add webhook signature verification (1 day)
   - Set up Azure Key Vault (0.5 day)
3. **Start observability**:

   - Configure Application Insights (0.5 day)
   - Add custom metrics (1 day)
   - Create first Grafana dashboard (1 day)
4. **Documentation**:

   - Architecture diagram (Visio/draw.io)
   - API reference (OpenAPI/Swagger)
   - Deployment guide

---

## 📞 Support & Escalation

### Decision Framework

| Decision Type        | Approver         | Timeline  |
| -------------------- | ---------------- | --------- |
| Architecture changes | Tech Lead        | 1-2 days  |
| New Azure services   | Team consensus   | 3-5 days  |
| Security exceptions  | CISO + Tech Lead | 1 week    |
| Budget overruns      | Program Manager  | Immediate |

### Regular Checkpoints

- **Daily**: Standup (15 min, blockers only)
- **Weekly**: Sprint review (demo progress)
- **Bi-weekly**: Architecture review (design decisions)
- **Monthly**: Stakeholder demo (Microsoft liaisons)

---

## ✅ Go-Live Checklist

### Pre-Production (T-2 weeks)

- [ ] All Phase 1-2 deliverables complete
- [ ] Load testing passed (10K users)
- [ ] Security audit passed (no critical/high vulns)
- [ ] Documentation complete (runbooks, API docs)
- [ ] Team training complete (ops runbooks)

### Production Cutover (T-0)

- [ ] Deploy infrastructure (Bicep)
- [ ] Deploy applications (Functions, Dashboard)
- [ ] Configure monitoring (alerts, dashboards)
- [ ] Run smoke tests (critical user flows)
- [ ] Enable Traffic Manager (gradual rollout)

### Post-Launch (T+1 week)

- [ ] Monitor error rates (daily)
- [ ] Collect user feedback (surveys)
- [ ] Fix critical bugs (hotfix process)
- [ ] Retrospective (what went well/wrong)

---

## 🎯 Final Words

This roadmap transforms your HITL Gateway from a hackathon prototype to a **production-ready, enterprise-grade platform** that showcases:

✅ **Azure mastery** (Durable Functions, Cosmos DB, multi-region)
✅ **Security best practices** (Zero Trust, RBAC, encryption)
✅ **AI innovation** (GPT-4 recommendations, ML insights)
✅ **Developer experience** (SDKs, Terraform, comprehensive docs)
✅ **Business value** (compliance, cost optimization, ROI)

**You're not just building a feature — you're building a platform** that could become a critical component of enterprise AI governance.

**Now go make Microsoft engineers say "WOW!" 🚀**

---

## 📚 Appendix

### A. Glossary

- **HITL**: Human-in-the-Loop
- **SLA**: Service Level Agreement
- **RBAC**: Role-Based Access Control
- **SSRF**: Server-Side Request Forgery
- **XSS**: Cross-Site Scripting

### B. References

- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/architecture/framework/)
- [Azure Durable Functions](https://learn.microsoft.com/azure/azure-functions/durable/)
- [Cosmos DB Best Practices](https://learn.microsoft.com/azure/cosmos-db/best-practices)

### C. Contact

- **Project Lead**: [Your Name]
- **Architecture**: [Architect Name]
- **Security**: [Security Lead]
- **Microsoft Liaison**: [Contact if applicable]

---

**Document Version**: 1.0
**Last Updated**: 2026-03-27
**Status**: DRAFT → REVIEW → **APPROVED**
