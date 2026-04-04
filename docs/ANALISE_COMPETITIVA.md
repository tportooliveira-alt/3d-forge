# ANÁLISE COMPETITIVA: 3D FORGE vs Mercado
## O que os concorrentes oferecem e o que falta no nosso projeto

---

## CONCORRENTES MAPEADOS

### TIER 1 — Apps de Scan 3D (mobile)
| App | Preço | Diferencial | Nosso status |
|-----|-------|------------|--------------|
| **KIRI Engine** | Free / $7/mês | Fotogrametria IA + Gaussian Splatting + PBR + Quad Mesh | ❌ Não temos |
| **Polycam** | Free / $10/mês | LiDAR + fotogrametria + floor plans + 12 formatos export | ❌ Não temos |
| **Scaniverse** | Grátis | LiDAR + Gaussian Splatting + compartilhamento | ❌ Não temos |
| **EM3D** | Grátis | Específico pra rosto, exporta STL/OBJ/PLY | ⚠️ Temos face3d mas sem qualidade deles |
| **Heges** | Grátis | Face scan via FaceID/LiDAR | ❌ Dependemos só de foto |
| **Widar** | Free / Pro | Editor 3D integrado + texturas + iluminação | ❌ Não temos editor |

### TIER 2 — Plataformas IA Image-to-3D (cloud)
| Plataforma | Preço | Diferencial | Nosso status |
|-----------|-------|------------|--------------|
| **Meshy** | $10-80/mês | Text-to-3D + Image-to-3D + plugins Blender/Unity | ❌ Só image |
| **Tripo AI** | $10-50/mês | 10-30s geração + auto-rigging + segmentação | ❌ Não temos |
| **Rodin/Hyper3D** | $99/mês | Avatares fotorrealistas + PBR 4K | ❌ Não temos |
| **Luma AI** | Free / Pro | Gaussian Splatting + vídeo-to-3D | ❌ Não temos |
| **CSM AI** | Enterprise | API robusta + separação de partes | ❌ Não temos |
| **Hunyuan3D** | Grátis (open source) | Melhor qualidade grátis + API local | ⚠️ Planejado Sprint E |
| **3D AI Studio** | $14-29/mês | Acesso a TODOS os modelos (Rodin+Meshy+Tripo) | ❌ Não temos |

### TIER 3 — Software Desktop
| Software | Preço | Diferencial | Nosso status |
|----------|-------|------------|--------------|
| **Artec Studio** | $$$$ | Fotogrametria profissional + workflows automáticos | ❌ Outro nível |
| **RealityCapture** | $$ | Velocidade + qualidade de referência | ❌ Outro nível |
| **Meshroom** | Grátis | Open source fotogrametria (AliceVision) | ❌ Não integrado |

---

## GAP ANALYSIS: O QUE FALTA NO 3D FORGE

### 🔴 CRÍTICO (sem isso não compete)

**1. Text-to-3D**
- TODOS os concorrentes pagos oferecem
- Usuário digita "busto romano" → recebe mesh
- Precisamos: integrar Hunyuan3D (text-to-3D grátis) ou API do Meshy/Tripo

**2. Qualidade do face3d**
- EM3D e Heges usam sensor TrueDepth (hardware real)
- KIRI Engine usa fotogrametria multi-foto
- Nós usamos depth map por interpolação (muito inferior)
- Precisamos: MiDaS + DECA mínimo, Hunyuan3D ideal

**3. Preview 3D interativo**
- TODOS os concorrentes mostram o modelo 3D girando na tela
- Nós retornamos só JSON + arquivo pra download
- Precisamos: viewer Three.js no frontend

**4. Múltiplos formatos de exportação**
- Concorrentes: GLB, OBJ, FBX, STL, PLY, USDZ, 3MF (12+ formatos)
- Nós: só STL
- Precisamos: ao menos GLB + OBJ + STL + FBX

### 🟡 IMPORTANTE (diferencial competitivo)

**5. Texturas PBR**
- Concorrentes geram Albedo + Normal + Roughness + Metallic
- Nós geramos mesh sem textura nenhuma
- Precisamos: ao menos textura básica (vertex colors do depth map)

**6. Multi-view input**
- KIRI Engine aceita 20-70 fotos de vários ângulos
- Polycam faz vídeo walk-around
- Nós aceitamos foto única
- Precisamos: ao menos 2-3 fotos (frente + perfil)

**7. Auto-rigging (esqueleto)**
- Tripo AI faz rigging automático pra animação
- KIRI Engine faz rigging com IA
- Nós não temos nada disso
- Futuro: integrar Mixamo ou similar

**8. Editor 3D integrado**
- Widar tem editor completo (texturas, iluminação, escala)
- Polycam tem crop, rotate, measure
- Nós: zero edição pós-geração
- Precisamos: ao menos escala, rotação, crop

**9. App mobile**
- KIRI, Polycam, Scaniverse, EM3D → todos mobile-first
- Nós: só API backend
- Precisamos: PWA no mínimo

**10. Estimativa de impressão**
- Nenhum concorrente de IA faz isso bem
- OPORTUNIDADE: calcular tempo, material, custo de impressão
- Diferencial nosso se implementarmos

### 🟢 BÔNUS (nice-to-have)

**11. Gaussian Splatting (3DGS)**
- Nova tecnologia, resultados fotorrealistas
- KIRI Engine, Polycam, Luma AI já usam
- Complexo mas poderoso

**12. Plugins Blender/Unity/Unreal**
- Meshy tem plugins nativos
- Amplia público-alvo enormemente

**13. Marketplace / comunidade**
- KIRI Engine tem galeria de modelos
- Polycam tem compartilhamento público
- Gera engajamento e marketing orgânico

**14. Batch processing**
- Poucos oferecem (CSM, 3D AI Studio)
- Útil pra uso industrial

---

## NOSSOS DIFERENCIAIS ÚNICOS (que concorrentes NÃO têm)

| Diferencial | Detalhe |
|-------------|---------|
| **Open source / self-hosted** | KIRI=$7/mês, Meshy=$10/mês... nós = grátis |
| **Pipeline multi-agente com cruzamento** | Nenhum concorrente documenta IA que cruza dados entre agentes |
| **Foco em impressão 3D** | Concorrentes focam em games/AR. Nós focamos em print |
| **Watertight automático** | Muitos concorrentes geram mesh não-imprimível |
| **Chat em linguagem natural** | "converte isso", "corrige essa malha" |
| **Pecuária / agro** | Nicho zero explorado por concorrentes |
| **API-first** | Pode ser integrado em qualquer sistema |

---

## PLANO DE AÇÃO PRIORIZADO

### FASE 1: Paridade mínima (competir)
1. ✅ Integrar MiDaS no Calculista (depth real)
2. ✅ Integrar Hunyuan3D como backend (qualidade state-of-art)
3. ✅ Frontend com preview Three.js
4. ✅ Export GLB + OBJ além de STL
5. ✅ Estimativa de impressão (tempo/material/custo) ← DIFERENCIAL

### FASE 2: Diferenciação (se destacar)
6. Multi-view input (2-3 fotos)
7. Texturas básicas (vertex colors)
8. PWA mobile
9. Editor básico (escala, rotação)
10. Text-to-3D via Hunyuan3D

### FASE 3: Dominação do nicho (impressão 3D)
11. Slicer integrado (STL → G-Code)
12. Perfis de impressora pré-configurados
13. Suporte automático gerado por IA
14. Estimativa de custo por filamento
15. Marketplace de modelos printáveis

---

## CONCLUSÃO

O mercado tem dois tipos de players:
- **Apps mobile** (KIRI, Polycam) → dependem de hardware (LiDAR, câmera)
- **Plataformas cloud** (Meshy, Tripo, Rodin) → cobram por geração

Nosso espaço é ser o **pipeline open source, self-hosted, focado em impressão 3D** que ninguém ocupa. Os concorrentes geram mesh bonito pra games/AR mas raramente imprimível. Nós geramos mesh watertight, com base, estimativa de impressão e tudo pronto pra mandar pra impressora.

A integração com Hunyuan3D (grátis, open source) nos dá qualidade comparável a Meshy/Tripo sem custo de API.
