# PLANO: Sistema Multi-Agente para Foto → 3D Perfeito

## VISÃO GERAL

```
FOTO DE ROSTO
     │
     ▼
┌─────────────────────────────────────────────┐
│           AGENTE 1: ANALISTA                │
│  "Olha a foto e entende o rosto"            │
│  - qualidade da imagem                      │
│  - pose/ângulo do rosto                     │
│  - iluminação                               │
│  - pontos de referência (landmarks)         │
│  Saída: JSON com análise completa           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           AGENTE 2: CALCULISTA              │
│  "Faz as contas de proporção"               │
│  - proporções áureas do rosto               │
│  - distâncias entre landmarks               │
│  - depth map por região                     │
│  - mapa de alturas calibrado                │
│  Saída: Depth Map + Medidas em mm           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           AGENTE 3: ESCULTOR                │
│  "Constrói a malha 3D"                      │
│  - gera mesh a partir do depth map          │
│  - aplica suavização inteligente            │
│  - adiciona base para impressão             │
│  - otimiza para impressora 3D              │
│  Saída: STL pronto                          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           AGENTE 4: INSPETOR                │
│  "Verifica se ficou bom"                    │
│  - checa watertight                         │
│  - valida proporções vs análise original    │
│  - simula impressão (estimativa tempo/mat)  │
│  - score de qualidade 0-100                 │
│  Saída: Relatório + STL aprovado            │
└─────────────────────────────────────────────┘
```

## ESTRUTURA DE ARQUIVOS

```
app/
  services/
    agents/
      analista.py      ← Agente 1: lê foto com IA
      calculista.py    ← Agente 2: proporções e depth
      escultor.py      ← Agente 3: gera mesh 3D
      inspetor.py      ← Agente 4: valida resultado
    orchestrator.py    ← adiciona action "face3d"
    interpreter.py     ← adiciona keywords
  routes/
    face3d.py          ← POST /api/face3d
```

## TECNOLOGIAS POR AGENTE

### Agente 1 - Analista (IA + OpenCV)
- MediaPipe Face Mesh (468 landmarks, grátis, roda local)
- OpenCV para qualidade/iluminação
- LLM (Gemini Flash gratuito) para análise semântica da foto

### Agente 2 - Calculista (Math + NumPy)
- Proporções áureas reais do rosto humano
- Depth estimation com MiDaS (modelo Intel, grátis)
- Calibração de profundidade por região anatômica
- Zero LLM - só matemática pura

### Agente 3 - Escultor (Trimesh + NumPy)
- Depth map → mesh via marching cubes ou extrusão
- Suavização laplaciana adaptativa
- Geração de base cilíndrica para busto
- Exporta STL binário otimizado

### Agente 4 - Inspetor (Trimesh + LLM)
- Validação geométrica (watertight, manifold)
- Compara proporções calculadas vs mesh final
- Estimativa de impressão (tempo, material, custo)
- LLM gera relatório legível

## ORDEM DE IMPLEMENTAÇÃO

Sprint 1: Agente Analista + Agente Escultor (pipeline básico funcional)
Sprint 2: Agente Calculista (melhora precisão com proporções reais)
Sprint 3: Agente Inspetor (validação e relatório)
Sprint 4: Integração com Hunyuan3D (upgrade pro pipeline IA generativa)
