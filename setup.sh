#!/bin/bash
# ============================================
# 3D FORGE - Setup Firebase + Vercel
# Execute: bash setup.sh
# ============================================

echo "==========================================="
echo "  3D FORGE - Setup Firebase + Vercel"
echo "==========================================="
echo ""

# ── PASSO 1: FIREBASE ──
echo "PASSO 1: FIREBASE"
echo "─────────────────"
echo "1. Abra: https://console.firebase.google.com"
echo "2. Clique 'Adicionar projeto' → nome: forge-3d"
echo "3. Desative Google Analytics → Criar projeto"
echo "4. Menu esquerdo → Firestore Database → Criar banco de dados"
echo "5. Selecione 'Iniciar no modo de teste' → região: southamerica-east1"
echo "6. Engrenagem ⚙ → Configurações do projeto → Contas de serviço"
echo "7. Clique 'Gerar nova chave privada' → Baixa o JSON"
echo "8. Renomeie pra: serviceAccountKey.json"
echo "9. Coloque na pasta backend/"
echo ""
read -p "Pronto? (Enter pra continuar) "

# ── VERIFICAR CREDENCIAL ──
if [ -f "backend/serviceAccountKey.json" ]; then
    echo "✓ serviceAccountKey.json encontrado!"
    PROJECT_ID=$(python3 -c "import json; print(json.load(open('backend/serviceAccountKey.json'))['project_id'])" 2>/dev/null)
    echo "  Projeto: $PROJECT_ID"
else
    echo "⚠ serviceAccountKey.json NÃO encontrado em backend/"
    echo "  A API vai funcionar sem Firebase (dados em memória)"
    echo "  Coloque o arquivo depois e reinicie"
fi

echo ""

# ── PASSO 2: BACKEND ──
echo "PASSO 2: INSTALAR BACKEND"
echo "─────────────────────────"
cd backend
pip install -r requirements.txt
mkdir -p temp outputs
echo "✓ Backend instalado"
cd ..

echo ""

# ── PASSO 3: FRONTEND ──
echo "PASSO 3: INSTALAR FRONTEND"
echo "──────────────────────────"
cd frontend
npm install
echo "✓ Frontend instalado"
cd ..

echo ""

# ── PASSO 4: TESTAR LOCAL ──
echo "PASSO 4: RODAR LOCAL"
echo "────────────────────"
echo "Terminal 1: cd backend && uvicorn app.main:app --port 8000"
echo "Terminal 2: cd frontend && npm run dev"
echo "Acesse: http://localhost:3000"
echo ""

# ── PASSO 5: DEPLOY ──
echo "PASSO 5: DEPLOY"
echo "────────────────"
echo ""
echo "VERCEL (Frontend):"
echo "  1. vercel.com → New Project → importar repo GitHub"
echo "  2. Root Directory: frontend"
echo "  3. Framework: Vite"
echo "  4. Deploy!"
echo ""
echo "RAILWAY (Backend):"
echo "  1. railway.app → New Project → Deploy from GitHub"
echo "  2. Root Directory: backend"
echo "  3. Start Command: uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
echo "  4. Adicionar variable: PORT=8000"
echo "  5. Upload serviceAccountKey.json como volume"
echo ""
echo "Depois: atualize VITE_API_URL na Vercel com a URL do Railway"
echo ""
echo "==========================================="
echo "  Setup concluído! 🚀"
echo "==========================================="
