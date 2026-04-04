"""
AGENTE INSPETOR
Cruza mesh final com TODOS os dados dos outros agentes.
Dá score de qualidade e feedback pro Escultor se precisar refinar.
"""

import numpy as np
from app.services.agents import log


def executar(ctx: dict) -> dict:
    """Inspeciona mesh cruzando com landmarks, proporções e depth."""
    log(ctx, "INSPETOR", "Cruzando mesh com dados de referência...")

    mesh = ctx["mesh"]
    landmarks_3d = ctx["landmarks_3d"]
    medidas = ctx["medidas"]
    proporcoes = ctx["proporcoes"]
    depth_map = ctx["depth_map"]
    px_mm = medidas["px_para_mm"]
    w, h = ctx["resolucao"]["w"], ctx["resolucao"]["h"]

    erros = {}

    # 1. CRUZA: landmarks vs mesh
    #    Pra cada landmark 3D, encontra ponto mais próximo no mesh
    #    O drift médio mostra se o mesh respeita a anatomia
    lm_points = []
    for lm in landmarks_3d:
        lm_points.append([
            lm[0] * w * px_mm,
            -lm[1] * h * px_mm,
            lm[2],
        ])
    lm_points = np.array(lm_points)

    closest, distances, _ = mesh.nearest.on_surface(lm_points)
    drift_mm = float(np.mean(distances))
    drift_max = float(np.max(distances))
    erros["landmark_drift_medio_mm"] = round(drift_mm, 2)
    erros["landmark_drift_max_mm"] = round(drift_max, 2)
    log(ctx, "INSPETOR", f"Drift landmarks: médio={drift_mm:.2f}mm max={drift_max:.2f}mm")

    # 2. CRUZA: proporções do mesh vs proporções calculadas
    bounds = mesh.bounds
    base_espessura = 3.0  # mm (mesmo valor do Escultor)
    mesh_altura = (bounds[1][1] - bounds[0][1]) - base_espessura
    mesh_largura = bounds[1][0] - bounds[0][0]
    mesh_prof = bounds[1][2] - bounds[0][2]

    esperado_altura = medidas["altura_rosto_mm"]
    erro_altura = abs(mesh_altura - esperado_altura) / max(esperado_altura, 0.1) * 100
    erros["proporcao_altura_erro_%"] = round(erro_altura, 1)
    log(ctx, "INSPETOR", f"Proporção altura: mesh={mesh_altura:.1f}mm esperado={esperado_altura:.1f}mm erro={erro_altura:.1f}%")

    # 3. CRUZA: simetria do mesh vs simetria detectada
    center_x = (bounds[0][0] + bounds[1][0]) / 2
    verts = mesh.vertices
    esquerda = verts[verts[:, 0] < center_x]
    direita = verts[verts[:, 0] >= center_x]

    if len(esquerda) > 0 and len(direita) > 0:
        z_esq = float(np.mean(esquerda[:, 2]))
        z_dir = float(np.mean(direita[:, 2]))
        simetria_mesh = 1.0 - min(abs(z_esq - z_dir) / max(abs(z_esq), abs(z_dir), 0.001), 1.0)
    else:
        simetria_mesh = 0.0

    simetria_ref = proporcoes.get("simetria", 1.0)
    erros["simetria_mesh"] = round(simetria_mesh, 3)
    erros["simetria_referencia"] = simetria_ref
    log(ctx, "INSPETOR", f"Simetria: mesh={simetria_mesh:.3f} ref={simetria_ref:.3f}")

    # 4. CRUZA: depth do mesh vs depth map original
    #    Amostra pontos do mesh e compara Z com depth map
    sample_n = min(500, len(verts))
    indices = np.random.choice(len(verts), sample_n, replace=False)
    sample_verts = verts[indices]

    depth_corr_values = []
    for v in sample_verts:
        img_x = int(v[0] / px_mm)
        img_y = int(-v[1] / px_mm)
        if 0 <= img_x < w and 0 <= img_y < h:
            depth_ref = depth_map[img_y, img_x]
            depth_mesh = v[2]
            depth_corr_values.append((depth_ref, depth_mesh))

    if len(depth_corr_values) > 10:
        refs, meshs = zip(*depth_corr_values)
        correlation = float(np.corrcoef(refs, meshs)[0, 1])
        if np.isnan(correlation):
            correlation = 0.0
    else:
        correlation = 0.0

    erros["depth_correlacao"] = round(correlation, 3)
    log(ctx, "INSPETOR", f"Correlação depth: {correlation:.3f}")

    # 5. GEOMETRIA: watertight e manifold
    erros["watertight"] = mesh.is_watertight
    erros["vertices"] = len(mesh.vertices)
    erros["faces"] = len(mesh.faces)

    # 6. SCORE FINAL (cruzamento de todos os critérios)
    score = _calcular_score(erros, proporcoes)
    ctx["score"] = score
    ctx["erros"] = erros
    log(ctx, "INSPETOR", f"Score final: {score}/100")

    # 7. FEEDBACK: se score baixo, dizer pro Escultor o que melhorar
    if score < 70:
        feedback = _gerar_feedback(erros, score)
        ctx["feedback"] = feedback
        ctx["status"] = "refinar"
        log(ctx, "INSPETOR", f"Feedback: {feedback}")
    else:
        ctx["feedback"] = None
        ctx["status"] = "aprovado"
        log(ctx, "INSPETOR", "Mesh APROVADO!")

    return ctx


def _calcular_score(erros: dict, proporcoes: dict) -> int:
    """Score 0-100 cruzando todos os critérios."""
    score = 100

    # Drift de landmarks (peso 30)
    drift = erros.get("landmark_drift_medio_mm", 10)
    score -= min(30, drift * 5)

    # Erro de proporção (peso 20)
    prop_erro = erros.get("proporcao_altura_erro_%", 50)
    score -= min(20, prop_erro * 0.4)

    # Correlação depth (peso 25)
    corr = erros.get("depth_correlacao", 0)
    score -= max(0, (1.0 - max(corr, 0)) * 25)

    # Simetria (peso 15)
    sim = erros.get("simetria_mesh", 0)
    score -= max(0, (1.0 - sim) * 15)

    # Geometria (peso 10)
    if not erros.get("watertight", False):
        score -= 5
    if erros.get("faces", 0) < 1000:
        score -= 5

    return max(0, min(100, int(score)))


def _gerar_feedback(erros: dict, score: int) -> str:
    """Gera instrução específica pro Escultor."""
    problemas = []

    if erros.get("landmark_drift_medio_mm", 0) > 2:
        problemas.append("landmarks distantes - forçar mais âncoras")
    if erros.get("proporcao_altura_erro_%", 0) > 15:
        problemas.append("proporções fora - recalibrar escala")
    if erros.get("depth_correlacao", 0) < 0.5:
        problemas.append("depth fraco - mais detalhe no depth map")
    if erros.get("simetria_mesh", 0) < 0.8:
        problemas.append("assimétrico - suavizar mais")

    return "; ".join(problemas) if problemas else "refinamento geral"
