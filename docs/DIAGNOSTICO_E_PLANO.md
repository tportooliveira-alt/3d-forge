# DIAGNÓSTICO CIRÚRGICO + PLANO DE MELHORIA
## STL Pipeline API - 3D FORGE

---

## RESUMO DA ANÁLISE

| Categoria | Testado | Passou | Taxa |
|-----------|---------|--------|------|
| Importações | 19 | 19 | 100% |
| Rotas HTTP | 16 | 15 | 94% |
| Services | 22 | 22 | 100% |
| Edge cases | 9 | 9 | 100% |
| Pipeline Face3D | 1 | 1 | 100% |
| **TOTAL** | **67** | **66** | **98.5%** |

---

## BUGS ENCONTRADOS

### BUG 1: MediaPipe versão incompatível [CORRIGIDO]
- Problema: mediapipe 0.10.33 removeu `mp.solutions`, usa API `tasks`
- Onde: `agents/analista.py` linha 46
- Fix: pin mediapipe==0.10.14 no requirements
- Status: ✅ Corrigido em runtime

### BUG 2: Módulo rtree ausente [CORRIGIDO]
- Problema: `inspetor.py` usa `mesh.nearest.on_surface()` que precisa de rtree
- Onde: `agents/inspetor.py` linha 37
- Fix: adicionar rtree + scipy ao requirements
- Status: ✅ Corrigido em runtime

### BUG 3: Proporção altura 133% de erro no Inspetor
- Problema: mesh tem 279mm de altura mas esperado era 120mm
- Causa: Escultor gera mesh com base adicionada, Inspetor mede bounds incluindo base
- Onde: `agents/inspetor.py` → `_calcular_score()` e `agents/escultor.py` → `_adicionar_base()`
- Fix: Inspetor deve subtrair espessura da base ao comparar proporções
- Status: ⚠️ Pendente

### BUG 4: chat face3d falha com foto fake de teste
- Problema: PNG de 100 bytes inválido causa erro no pipeline
- Causa: foto de teste `temp/foto.png` era fake (bytes aleatórios)
- Impacto: Teste específico do chat, não é bug do código
- Status: ℹ️ Esperado (imagem inválida)

---

## PROBLEMAS ARQUITETURAIS

### P1: STLs convertidos não são watertight
- Evidência: bunny, teapot, suzanne → watertight=False
- Causa: OBJs de teste têm buracos/edges abertos
- Impacto: Modelos não imprimíveis sem pós-processamento
- Melhoria: Adicionar step automático de repair após convert
- Prioridade: **ALTA**

### P2: Outputs poluídos com arquivos de teste
- Evidência: 20 STLs em outputs/, misturando teste com modelos nomeados
- Causa: cada teste gera novo arquivo com UUID
- Melhoria: Limpar outputs após testes, ou usar pasta temp pra testes
- Prioridade: MÉDIA

### P3: Face3D depth map é calculado por interpolação manual
- Evidência: depth_map gerado com regiões fixas + GaussianBlur
- Causa: MiDaS não está integrado ainda
- Impacto: Profundidade imprecisa, especialmente em detalhes finos
- Melhoria: Integrar MiDaS para depth real
- Prioridade: **ALTA**

### P4: Pipeline face3d não gera mesh watertight
- Evidência: watertight=False no STL gerado
- Causa: grid de vértices + base separada não formam malha fechada
- Impacto: Não imprimível diretamente
- Melhoria: Fechar laterais do mesh entre superfície e base
- Prioridade: **ALTA**

### P5: Sem validação de tamanho de imagem no face3d
- Evidência: Imagem 400x500 gera 50K vértices (grid 250x200)
- Causa: step calculado por min(w,h)//150 sem limite
- Impacto: Foto 4K geraria mesh enorme (1M+ verts)
- Melhoria: Redimensionar imagem pra max 800px antes de processar
- Prioridade: MÉDIA

### P6: Sem limpeza de arquivos temporários
- Evidência: temp/ acumula arquivos indefinidamente
- Causa: nenhum mecanismo de cleanup
- Melhoria: Job scheduler ou cleanup por idade do arquivo
- Prioridade: MÉDIA

### P7: requirements.txt desatualizado
- Evidência: Não inclui mediapipe, opencv, rtree, scipy
- Causa: Foram instalados ad-hoc durante desenvolvimento
- Melhoria: Gerar requirements completo
- Prioridade: **ALTA** (deploy vai quebrar)

---

## PONTOS FORTES ✅

1. Arquitetura modular impecável: 1 arquivo por responsabilidade
2. Orquestrador + interpretador funcionam 100%
3. Sistema de agentes com cruzamento de dados é bem pensado
4. Loop de refinamento do Inspetor é um diferencial
5. Tratamento de erros consistente em todas as rotas
6. Edge cases bem cobertos (extensão inválida, arquivo grande, etc)
7. Conversão via Trimesh robusta (cena multi-objeto → mesh único)
8. Repair funcional (faces degeneradas, duplicadas, suavização)

---

## PLANO DE MELHORIA (por sprint)

### SPRINT EMERGENCIAL: Fixes críticos
1. Atualizar requirements.txt com TODAS as dependências
2. Fix Inspetor: subtrair base ao calcular proporções
3. Adicionar auto-repair após convert (watertight pipeline)
4. Fechar mesh lateral no Escultor (watertight face3d)
5. Limitar resolução de entrada no face3d (max 800px)

### SPRINT A: Depth com IA (MiDaS)
1. Integrar MiDaS small no Calculista
2. Substituir depth por interpolação → depth por IA
3. Cruzar depth MiDaS com landmarks MediaPipe
4. Calibrar escala MiDaS com proporções anatômicas
5. Benchmark: depth manual vs MiDaS (correlação com mesh)

### SPRINT B: Mesh watertight e print-ready
1. Fechar laterais entre superfície e base (mesh sólido)
2. Adicionar voxelization como alternativa (marching cubes)
3. Verificar manifold (non-manifold edges/vertices)
4. Estimar tempo de impressão e material (volume × densidade)
5. Gerar relatório de printability (espessura mínima, overhangs)

### SPRINT C: Pipeline DECA/FLAME
1. Integrar DECA como subprocess
2. Download automático de FLAME model
3. Pipeline: foto → DECA → OBJ → repair → STL
4. Comparar resultado DECA vs nosso depth map
5. Merge: usar DECA pra geometria base + nosso depth pra detalhe

### SPRINT D: Multi-view e refinamento
1. Aceitar múltiplas fotos (frente + perfil)
2. Triangulação entre landmarks de diferentes ângulos
3. ICP (Iterative Closest Point) pra alinhar meshes parciais
4. Cruzar depth maps de múltiplos ângulos
5. Score de confiança por região (frente=alto, nuca=baixo)

### SPRINT E: Hunyuan3D
1. Integrar via API local (GPU) ou HuggingFace Space (grátis)
2. Pipeline: foto → Hunyuan3D → GLB → Trimesh → STL
3. Pós-processamento: repair + escala + base
4. A/B test: nosso pipeline vs Hunyuan3D puro
5. Híbrido: Hunyuan3D pra base + nosso refinamento pra detalhes

### SPRINT F: Frontend e UX
1. Interface web React (upload foto, preview 3D com Three.js)
2. Barra de progresso por agente (Analista → Calculista → etc)
3. Preview interativo do mesh antes de baixar
4. Comparação antes/depois (foto vs mesh renderizado)
5. Opções de impressão (escala, base, suporte)

### SPRINT G: Produção
1. Docker + docker-compose
2. Rate limiting e autenticação
3. Queue de jobs (Celery ou similar)
4. Monitoramento (logs, métricas, alertas)
5. CDN pra entrega dos STLs
6. Testes automatizados (CI/CD)

---

## MÉTRICAS DE SUCESSO

| Métrica | Atual | Meta Sprint A | Meta Final |
|---------|-------|---------------|------------|
| Score face3d médio | 73 | 85 | 95+ |
| Watertight rate | 30% | 70% | 99% |
| Drift landmarks | 0.20mm | 0.10mm | 0.05mm |
| Correlação depth | 1.0* | 0.95+ | 0.98+ |
| Proporção erro | 133% | <15% | <5% |
| Tempo pipeline | ~3s | <5s | <10s com MiDaS |

*1.0 atual é inflado porque depth map e mesh usam a mesma fonte

---

## DECISÃO TÉCNICA PRINCIPAL

O maior salto de qualidade virá de:
1. **MiDaS** → depth map real em vez de interpolado (Sprint A)
2. **Mesh watertight** → imprimível de verdade (Sprint B)
3. **DECA** → geometria facial precisa (Sprint C)

Esses 3 sprints transformam o projeto de "protótipo" em "produto funcional".
