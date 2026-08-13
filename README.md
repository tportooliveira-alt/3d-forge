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
- **Image3D** — Qualquer imagem → sólido imprimível: litofania, relevo, silhueta ou profundidade IA
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
| POST | /api/face3d | Foto de rosto → modelo 3D |
| POST | /api/image3d | Imagem → sólido imprimível |
| GET | /api/image3d/modos | Modos e defaults do Image3D |
| POST | /api/chat | Chat linguagem natural |
| GET | /api/view/{id} | Viewer 3D |
| GET | /api/download/{id} | Download |
| GET | /api/formats | Formatos suportados |
| GET | /api/printers | Impressoras |
| GET | /api/filaments | Filamentos |
| GET | /api/health | Status |
| GET | /docs | Swagger UI |

## Image3D — imagem → peça imprimível

Funciona com qualquer imagem (foto, logo, desenho). Diferente do `/api/face3d`, não exige rosto.

| Modo | O que faz | Bom pra |
|------|-----------|---------|
| `auto` | Detecta sozinho: recorte/arte de linha → silhueta, foto → litofania | Padrão |
| `litofania` | Espessura varia com o brilho (escuro = grosso), frente plana | Quadro com luz atrás |
| `relevo` | Brilho vira altura sobre uma base sólida | Placa, medalha, moeda |
| `silhueta` | Recorta por limiar/alpha e extruda | Logo, ícone, chaveiro, stencil |
| `profundidade` | Profundidade estimada por IA (MiDaS) vira relevo | Foto de objeto ou paisagem |

A saída é sempre um sólido fechado (watertight), apoiado em z=0 e já na escala em mm.

**Recorte de fundo.** Numa imagem sobre fundo liso, "claro = alto" faria o fundo virar a parte
mais alta da peça. Por isso `relevo` e `profundidade` recortam o contorno do objeto por padrão,
e a peça sai no formato dele. A `litofania` não recorta (é painel de luz, quer a placa inteira).
Force com `recorte=true` ou desligue com `recorte=false`.

```bash
# Via API
curl -F "file=@foto.jpg" \
  "http://localhost:8000/api/image3d?modo=litofania&largura_mm=120&espessura_max=3&moldura_mm=3"

# Via CLI, sem subir o servidor
cd backend
python scripts/imagem_para_stl.py foto.jpg --modo litofania --largura 120 --moldura 3
python scripts/imagem_para_stl.py logo.png --modo silhueta --espessura-max 5
```

Parâmetros principais: `modo`, `largura_mm`, `altura_mm`, `espessura_max`, `espessura_min`,
`base_mm`, `resolucao`, `inverter`, `suavizar`, `gamma`, `limiar`, `moldura_mm`, `recorte`, `formato`.

A resposta traz dimensões em mm, volume, contagem de corpos soltos e **avisos de impressão**
(parede fina demais pro bico 0.4, detalhe abaixo da resolução da impressora, peça em partes soltas).

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Impressoras suportadas

Ender 3 · Prusa MK4 · Bambu Lab P1S · Genérica FDM

## Filamentos

PLA ($25/kg) · PETG ($30/kg) · ABS ($28/kg) · TPU ($40/kg)
