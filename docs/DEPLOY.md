# DEPLOY: Firebase + Vercel + Railway

## ARQUITETURA DE DEPLOY

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│   VERCEL    │      │   RAILWAY    │      │   FIREBASE   │
│  (Frontend) │─────▶│  (Backend)   │─────▶│ (Firestore)  │
│  React+Vite │ API  │  FastAPI     │  DB  │  NoSQL       │
│  GRÁTIS     │      │  $5/mês free │      │  GRÁTIS      │
└─────────────┘      └──────────────┘      └──────────────┘
```

---

## PASSO 1: FIREBASE (5 min)

1. Acesse https://console.firebase.google.com
2. Crie um projeto novo: "3d-forge"
3. Vá em **Firestore Database** → Criar banco de dados
4. Escolha modo **Produção** e região **southamerica-east1**
5. Vá em **Configurações do projeto** → **Contas de serviço**
6. Clique em **Gerar nova chave privada** → Baixa o JSON
7. Renomeie pra `serviceAccountKey.json`
8. Coloque na pasta `backend/`

## PASSO 2: BACKEND NO RAILWAY (10 min)

1. Acesse https://railway.app e faça login com GitHub
2. Clique em **New Project** → **Deploy from GitHub repo**
3. Selecione o repo `3d-forge`, pasta `backend/`
4. Em **Settings**:
   - Root Directory: `/backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Em **Variables**, adicione:
   - `FIREBASE_KEY` = `serviceAccountKey.json`
   - `PORT` = `8000`
6. Faça upload do `serviceAccountKey.json` via Railway CLI:
   ```bash
   railway link
   railway up
   ```
7. Copie a URL do deploy (ex: `https://3d-forge-production.up.railway.app`)

## PASSO 3: FRONTEND NA VERCEL (5 min)

1. Acesse https://vercel.com e faça login com GitHub
2. Clique em **Add New** → **Project**
3. Importe o repo `3d-forge`
4. Configure:
   - Framework: **Vite**
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
5. Em **Environment Variables**:
   - `VITE_API_URL` = `https://SEU-BACKEND.railway.app`
6. Deploy!

## PASSO 4: CONECTAR FRONTEND → BACKEND

No `frontend/src/App.jsx`, troque:
```javascript
const API = ""; // troque por:
const API = import.meta.env.VITE_API_URL || "";
```

No `frontend/vercel.json`, troque `SEU-BACKEND-URL` pela URL do Railway.

---

## ALTERNATIVA: TUDO NO RAILWAY

Se preferir não separar, o Railway pode servir tudo:

1. Build do frontend: `cd frontend && npm run build`
2. O FastAPI serve os arquivos estáticos do `dist/`
3. Um deploy só, uma URL só

---

## CUSTOS

| Serviço | Plano | Custo |
|---------|-------|-------|
| Firebase Firestore | Spark (grátis) | $0 (1GB storage, 50K reads/dia) |
| Vercel | Hobby | $0 (100GB bandwidth) |
| Railway | Trial | $5 crédito grátis/mês |
| **Total** | | **$0/mês** (dentro dos limites) |

---

## FIREBASE FIRESTORE - COLLECTIONS

```
firestore/
├── jobs/                    ← cada processamento
│   └── {job_id}/
│       ├── status: "done"
│       ├── action: "convert"
│       ├── vertices: 2903
│       ├── faces: 5804
│       ├── watertight: true
│       ├── output: "abc123.stl"
│       └── created_at: timestamp
│
├── chat_history/            ← mensagens do chat
│   └── {auto_id}/
│       ├── message: "converte pra stl"
│       ├── action: "convert"
│       └── timestamp: timestamp
│
└── stats/                   ← contadores globais
    └── global/
        ├── total_jobs: 150
        ├── total_converts: 80
        ├── total_repairs: 40
        └── total_face3ds: 30
```
