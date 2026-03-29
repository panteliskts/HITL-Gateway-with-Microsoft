#!/bin/bash
# ============================================================
# HITL Gateway — Live Demo Activation
# ============================================================
# Usage:  ./activate-demo.sh
# ============================================================

BASE="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          HITL Gateway — Live Demo Activation              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ── Preflight ──────────────────────────────────────────────────
echo -e "${CYAN}[1/6] Preflight checks...${NC}"
if ! curl -sf "$BASE/api/health" > /dev/null 2>&1; then
  echo -e "${RED}  Backend is not running at $BASE${NC}"
  echo "  Start it first:  cd backend && python server.py"
  exit 1
fi
echo -e "${GREEN}  Backend ✓${NC}"

if curl -sf "http://localhost:3000" > /dev/null 2>&1; then
  echo -e "${GREEN}  Frontend ✓${NC}"
else
  echo -e "${YELLOW}  Frontend not detected (optional)${NC}"
fi
echo ""

# ── Reset state ────────────────────────────────────────────────
echo -e "${CYAN}[2/6] Resetting workflow state...${NC}"
curl -sf -X POST "$BASE/api/reset" > /dev/null 2>&1
echo -e "${GREEN}  Clean slate ✓${NC}"
echo ""

# ── Trigger all 5 scenarios ───────────────────────────────────
echo -e "${CYAN}[3/6] Triggering threat scenarios...${NC}"
echo ""

for scenario in lateral_movement data_exfil large_transaction compliance_review risk_assessment; do
  RESULT=$(curl -sf -X POST "$BASE/api/trigger/$scenario" 2>/dev/null)
  URGENCY=$(echo "$RESULT" | python -c "import sys,json; print(json.load(sys.stdin).get('urgency','?'))" 2>/dev/null)
  ID=$(echo "$RESULT" | python -c "import sys,json; print(json.load(sys.stdin).get('instance_id','?')[:8])" 2>/dev/null)

  case "$URGENCY" in
    CRITICAL) COLOR=$RED   ; ICON="🔴" ;;
    HIGH)     COLOR=$YELLOW; ICON="🟠" ;;
    NORMAL)   COLOR=$CYAN  ; ICON="🟡" ;;
    LOW)      COLOR=$GREEN ; ICON="🟢" ;;
    *)        COLOR=$NC    ; ICON="⚪" ;;
  esac

  printf "  %s %-22s  ${COLOR}%-8s${NC}  id=%s\n" "$ICON" "$scenario" "$URGENCY" "$ID"
done
echo ""

# ── Wait for workflows to settle ──────────────────────────────
sleep 2

# ── Send notifications ─────────────────────────────────────────
echo -e "${CYAN}[4/6] Sending Telegram alert...${NC}"
TG=$(curl -sf -X POST "$BASE/api/test/telegram" 2>/dev/null)
TG_STATUS=$(echo "$TG" | python -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null)
if [ "$TG_STATUS" = "sent" ]; then
  echo -e "${GREEN}  Telegram message sent ✓${NC}"
else
  echo -e "${RED}  Telegram failed: $TG${NC}"
fi
echo ""

echo -e "${CYAN}[5/6] Triggering emergency phone call...${NC}"
CALL=$(curl -sf -X POST "$BASE/api/test/call" 2>/dev/null)
CALL_SID=$(echo "$CALL" | python -c "import sys,json; print(json.load(sys.stdin).get('call_sid','error'))" 2>/dev/null)
CALL_PHONE=$(echo "$CALL" | python -c "import sys,json; print(json.load(sys.stdin).get('phone_number','?'))" 2>/dev/null)
if [ "$CALL_SID" != "error" ]; then
  echo -e "${GREEN}  Call initiated ✓  SID=${CALL_SID:0:16}...  Phone=${CALL_PHONE}${NC}"
else
  echo -e "${RED}  Call failed: $CALL${NC}"
fi
echo ""

echo -e "${CYAN}[6/6] Sending weekly report to email + Telegram...${NC}"
REPORT=$(curl -sf -X POST "$BASE/api/report/weekly" 2>/dev/null)
RPT_STATUS=$(echo "$REPORT" | python -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null)
RPT_COUNT=$(echo "$REPORT" | python -c "import sys,json; print(json.load(sys.stdin).get('event_count','0'))" 2>/dev/null)
if [ "$RPT_STATUS" = "sent" ]; then
  echo -e "${GREEN}  Weekly report sent ✓  (${RPT_COUNT} events)${NC}"
else
  echo -e "${RED}  Report failed: $REPORT${NC}"
fi
echo ""

# ── Summary ────────────────────────────────────────────────────
PENDING=$(curl -sf "$BASE/api/pending" | python -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "?")

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  Demo Activated!                          ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║                                                          ║"
echo "║  Workflows pending:  $PENDING                              ║"
echo "║                                                          ║"
echo "║  📱 Telegram   — Alert sent with inline keyboard         ║"
echo "║  📞 Phone Call — Emergency call initiated via Twilio     ║"
echo "║  📧 Email      — CSV report sent to Gmail               ║"
echo "║                                                          ║"
echo "║  Dashboard:  http://localhost:3000                       ║"
echo "║  Pending:    http://localhost:3000/pending               ║"
echo "║  Live Demo:  http://localhost:3000/live                  ║"
echo "║  Audit:      http://localhost:3000/audit                 ║"
echo "║                                                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
