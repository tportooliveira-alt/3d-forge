# 3D FORGE 🔮
### Photo to Print — Pipeline completo de foto/modelo 3D para impressão

![Version](https://img.shields.io/badge/version-2.0-00E5FF)
![Python](https://img.shields.io/badge/python-3.12-blue)
![React](https://img.shields.io/badge/react-19-61DAFB)
![License](https://img.shields.io/badge/license-MIT-green)

## O que é

API + Frontend para converter fotos e modelos 3D em arquivos prontos para impressão 3D. Inclui sistema multi-agente com IA para reconstrução facial, estimativa de impressão e análise de malha.

## Features

- **Upload** — Arraste modelos 3D (STL, OBJ, PLY, FBX, 3MF) ou fotos de rosto
- **Conversão** — OBJ → STL com auto-repair (watertight)
- **Reparo** — Fix normals, fill holes, suavização laplaciana
- **Face3D** — Foto de rosto → modelo 3D via 4 agentes IA com cruzamento de dados
- **Exportação** — STL, OBJ, GLB, PLY, 3MF
- **Análise** — Geometria, topologia, printability score
- **Estimativa** — Tempo, peso, custo por impressora/filamento
- **Viewer 3D** — Preview interativo no browser
- **Chat** — Comandos por linguagem natural ("converte pra STL")

## Stack

**Backend:** FastAPI + Trimesh + MediaPipe + MiDaS + OpenCV  
**Frontend:** React + Vite  
**IA:** 4 agentes (Analista → Calculista → Escultor → Inspetor) com loop de refinamento

## Rodar local

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## API Endpoints (20 rotas)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | /api/upload | Upload arquivo |
| POST | /api/convert | Converter → STL |
| POST | /api/repair | Reparar malha |
| POST | /api/export?format=glb | Exportar formato |
| POST | /api/analyze | Análise completa |
| POST | /api/estimate | Estimativa impressão |
| POST | /api/face3d | Foto → modelo 3D |
| POST | /api/chat | Chat linguagem natural |
| GET | /api/view/{id} | Viewer 3D |
| GET | /api/download/{id} | Download |
| GET | /api/formats | Formatos suportados |
| GET | /api/printers | Impressoras |
| GET | /api/filaments | Filamentos |
| GET | /api/health | Status |
| GET | /docs | Swagger UI |

## Impressoras suportadas

Ender 3 · Prusa MK4 · Bambu Lab P1S · Genérica FDM

## Filamentos

PLA ($25/kg) · PETG ($30/kg) · ABS ($28/kg) · TPU ($40/kg)
