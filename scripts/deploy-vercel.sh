#!/bin/bash
# ============================================================
# HITL Gateway — Vercel Deployment Script
# ============================================================
# Deploys the frontend to Vercel
# Usage: ./deploy-vercel.sh
# ============================================================

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              HITL Gateway — Vercel Deployment                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI is not installed"
    echo "💡 Install it with: npm install -g vercel"
    exit 1
fi
echo "✅ Vercel CLI found"
echo ""

# Build frontend first
echo "🏗️  Building frontend..."
cd frontend
npm install
npm run build
cd ..
echo "✅ Frontend build complete"
echo ""

# Deploy to Vercel
echo "🚀 Deploying to Vercel..."
echo ""

if [ "$1" == "--prod" ]; then
    echo "📦 Deploying to PRODUCTION..."
    vercel --prod
else
    echo "🧪 Deploying to PREVIEW..."
    echo "💡 Use './deploy-vercel.sh --prod' for production deployment"
    vercel
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   Deployment Complete! 🎉                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "📝 Next Steps:"
echo "   1. Configure environment variables in Vercel dashboard:"
echo "      - REACT_APP_API_URL (your backend API URL)"
echo ""
echo "   2. Set up your backend separately on:"
echo "      - Azure Functions (recommended for production)"
echo "      - Heroku, Railway, or any Python hosting"
echo "      - Keep local backend running for development"
echo ""
echo "   3. Update vercel.json with your backend URL"
echo ""
