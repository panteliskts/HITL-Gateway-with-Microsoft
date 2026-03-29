#!/bin/bash
# ============================================================
# HITL Gateway — Complete Startup Script
# ============================================================
# Starts backend, frontend, and activates demo scenarios
# Usage: ./scripts/start-everything.sh
# ============================================================

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           HITL Gateway — Complete Demo Startup                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Start Backend
echo "🚀 Starting Backend Server..."

# Check if already running
if curl -s http://localhost:8000/api/pending > /dev/null 2>&1; then
    echo "✅ Backend already running on port 8000"
else
    echo "   Starting FastAPI server on port 8000..."
    nohup python backend/server.py > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "   Backend PID: $BACKEND_PID"

    # Wait for backend to start
    echo "   Waiting for backend to initialize..."
    for i in {1..20}; do
        if curl -s http://localhost:8000/api/pending > /dev/null 2>&1; then
            echo "✅ Backend ready!"
            break
        fi
        sleep 0.5
        echo -n "."
    done
    echo ""
fi
echo ""

# Start Frontend
echo "🎨 Starting Frontend React App..."
cd frontend

# Check if already running
if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend already running on port 3000"
else
    echo "   Starting React development server..."
    nohup npm start > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "   Frontend PID: $FRONTEND_PID"

    # Wait for frontend to start
    echo "   Waiting for frontend to initialize..."
    for i in {1..30}; do
        if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
            echo "✅ Frontend ready!"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
fi

cd ..
echo ""

# Wait a moment for everything to stabilize
sleep 2

# Run activation script
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Running Demo Activation Sequence                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

"$(dirname "$0")/activate-demo.sh"

echo ""
echo "💡 Logs available at:"
echo "   • Backend:  tail -f backend.log"
echo "   • Frontend: tail -f frontend.log"
echo ""

echo "🛑 To stop everything:"
echo "   • Kill backend:  pkill -f 'python.*server.py'"
echo "   • Kill frontend: pkill -f 'react-scripts'"
echo ""
