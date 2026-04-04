# PLANO v2: Agentes com Cruzamento de Dados

## FILOSOFIA
Cada agente gera dados. O cruzamento entre eles é o que gera PRECISÃO.
Nenhum agente trabalha sozinho - todos alimentam e validam uns aos outros.

```
                    ┌──────────────┐
        FOTO ──────►│  ANALISTA    │──── landmarks + qualidade + pose
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
  landmarks ───────►│ CALCULISTA   │──── depth map + medidas + proporções
  qualidade ───────►│              │     (cruza landmarks COM proporções reais)
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
  depth map ───────►│  ESCULTOR    │──── mesh 3D bruto
  medidas ─────────►│              │     (cruza depth COM medidas pra escalar)
  landmarks ───────►│              │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
  mesh 3D ─────────►│  INSPETOR    │──── score + correções
  landmarks ───────►│              │     (cruza mesh COM landmarks originais)
  medidas ─────────►│              │     (cruza mesh COM proporções esperadas)
  depth map ───────►│              │     (cruza mesh COM depth original)
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │  score < 70? │
                    │  SIM → volta │──── feedback pro ESCULTOR refinar
                    │  NÃO → done │──── STL final aprovado
                    └──────────────┘
```

## CRUZAMENTOS CHAVE

1. ANALISTA × CALCULISTA
   - Landmarks → distâncias reais entre pontos
   - Pose detectada → corrige distorção de perspectiva no depth
   - Qualidade baixa → calculista compensa com proporções padrão humanas

2. CALCULISTA × ESCULTOR
   - Depth map → geometria base
   - Medidas em mm → escala real do modelo
   - Landmarks 3D → pontos âncora que o mesh DEVE respeitar

3. INSPETOR × TODOS
   - Compara mesh final vs landmarks originais (erro em mm)
   - Compara proporções do mesh vs proporções calculadas
   - Compara depth do mesh vs depth map original
   - Se erro > threshold → manda feedback e ESCULTOR refina

## DADOS COMPARTILHADOS (context dict)

```python
context = {
    # Agente 1: Analista
    "landmarks": np.array,        # 468 pontos xyz
    "pose": {"yaw", "pitch", "roll"},
    "qualidade": {"score", "nitidez", "brilho"},
    "resolucao": {"w", "h"},

    # Agente 2: Calculista
    "depth_map": np.array,        # HxW float32
    "medidas": {
        "altura_rosto_mm": float,
        "largura_mm": float,
        "profundidade_nariz_mm": float,
    },
    "proporcoes": {
        "tercos": [sup, med, inf],
        "ratio_olhos": float,
    },
    "landmarks_3d": np.array,     # landmarks com Z calibrado

    # Agente 3: Escultor
    "mesh": trimesh.Trimesh,
    "mesh_landmarks": np.array,   # onde landmarks caíram no mesh

    # Agente 4: Inspetor
    "score": int,                 # 0-100
    "erros": {
        "landmark_drift_mm": float,
        "proporcao_erro_%": float,
        "depth_correlacao": float,
    },
    "feedback": str,              # instrução pro escultor
}
```
