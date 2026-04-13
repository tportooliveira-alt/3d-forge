#!/bin/bash
# deploy.sh — Deploy completo do 3D Forge no Firebase
set -e

echo "🔥 3D FORGE — DEPLOY FIREBASE"
echo "=============================="

# 1. Build do frontend
echo ""
echo "📦 [1/3] Build do frontend React..."
cd frontend
npm install --silent
npm run build
cd ..
echo "✅ Frontend buildado em frontend/dist/"

# 2. Deploy do Hosting (frontend)
echo ""
echo "🌐 [2/3] Deploy do Frontend no Firebase Hosting..."
firebase deploy --only hosting --project forge-3d-c12ff
echo "✅ Frontend no ar!"

# 3. Deploy do backend via Cloud Run / App Hosting
echo ""
echo "🐳 [3/3] Deploy do Backend (Docker → Cloud Run)..."
echo "   Buildando imagem Docker..."

cd backend
gcloud builds submit \
  --tag gcr.io/forge-3d-c12ff/3d-forge-backend:latest \
  --project forge-3d-c12ff

echo "   Fazendo deploy no Cloud Run..."
gcloud run deploy 3d-forge-backend \
  --image gcr.io/forge-3d-c12ff/3d-forge-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars FIREBASE_PROJECT=forge-3d-c12ff \
  --project forge-3d-c12ff

cd ..

echo ""
echo "=============================="
echo "✅ DEPLOY COMPLETO!"
echo ""
echo "URLs:"
echo "  Frontend: https://forge-3d-c12ff.web.app"
echo "  Backend:  https://3d-forge-backend-<hash>-uc.a.run.app"
echo ""
echo "Próximo passo: copie a URL do backend e configure"
echo "  VITE_API_URL no frontend para apontar pra ela."
