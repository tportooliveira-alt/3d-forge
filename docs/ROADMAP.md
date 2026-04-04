# ROADMAP - STL Pipeline API + Impressão 3D

## ✅ FEITO

### Base da API
- [x] FastAPI rodando com CORS
- [x] POST /api/upload (arquivo único + múltiplo + URL)
- [x] POST /api/convert (OBJ/PLY/3MF → STL via Trimesh)
- [x] POST /api/repair (fix normals, fill holes, suavização)
- [x] POST /api/process (orquestrador central)
- [x] POST /api/chat (interpretador de linguagem natural)
- [x] GET /api/download/{job_id}
- [x] 10 STLs de teste prontos (bunny, cow, teapot, etc.)

### Sistema Multi-Agente (Sprint 1)
- [x] Agente Analista (MediaPipe 468 landmarks + qualidade + pose)
- [x] Agente Calculista (proporções anatômicas + depth map + landmarks 3D)
- [x] Agente Escultor (mesh 3D + âncoras + suavização + base)
- [x] Agente Inspetor (cruzamento total + score + feedback)
- [x] Pipeline com loop de refinamento (até 3 iterações)
- [x] POST /api/face3d

### Pesquisa
- [x] Catálogo de 12+ projetos open source
- [x] Script de clone rápido
- [x] Guia técnico Foto → 3D → STL

## 🔜 PRÓXIMO

### Sprint 2: MiDaS Depth (melhora precisão)
- [ ] Integrar MiDaS small no Agente Calculista
- [ ] Depth map com IA em vez de interpolação manual
- [ ] Cruzar depth MiDaS com landmarks MediaPipe

### Sprint 3: pic2stl (pipeline rápido)
- [ ] Integrar pic2stl como fallback rápido
- [ ] Lithophane mode (relevo com luz)
- [ ] Ajuste de altura/base pra impressão

### Sprint 4: DECA/FLAME (reconstrução precisa)
- [ ] Setup DECA como subprocess
- [ ] Download automático dos modelos
- [ ] Pipeline: foto → DECA → OBJ → Trimesh → STL

### Sprint 5: Hunyuan3D (state of art)
- [ ] Integrar via API local ou HuggingFace
- [ ] Cabeça 360° completa
- [ ] Textura PBR opcional

### Sprint 6: Frontend
- [ ] Interface web pra upload de foto
- [ ] Preview 3D do resultado (Three.js)
- [ ] Download direto do STL
