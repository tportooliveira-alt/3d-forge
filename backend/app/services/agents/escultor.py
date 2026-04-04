"""
AGENTE ESCULTOR
Constrói mesh 3D cruzando: depth map + landmarks 3D + medidas.
Aceita feedback do Inspetor pra refinar.
"""

import trimesh
import numpy as np
from app.services.agents import log
from app.core.config import OUTPUTS_DIR


def executar(ctx: dict) -> dict:
    """Gera mesh 3D a partir dos dados cruzados dos outros agentes."""
    iteracao = ctx["iteracao"]
    log(ctx, "ESCULTOR", f"Construindo mesh 3D (iteração {iteracao})...")

    depth_map = ctx["depth_map"]
    medidas = ctx["medidas"]
    landmarks_3d = ctx["landmarks_3d"]
    feedback = ctx.get("feedback")

    h, w = depth_map.shape
    px_mm = medidas["px_para_mm"]

    # 0. LIMITAR RESOLUÇÃO: max 800px no maior eixo
    import cv2
    max_dim = 400
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        depth_map = cv2.resize(depth_map, (int(w * scale), int(h * scale)))
        h, w = depth_map.shape
        px_mm = px_mm / scale
        log(ctx, "ESCULTOR", f"Redimensionado pra {w}x{h}")

    # 1. RESOLUÇÃO: cada N pixels = 1 vértice
    step = max(2, min(w, h) // 120)
    if feedback and "mais detalhe" in str(feedback):
        step = max(1, step // 2)
        log(ctx, "ESCULTOR", f"Feedback: aumentando resolução (step={step})")

    # 2. GRID DE VÉRTICES
    rows = list(range(0, h, step))
    cols = list(range(0, w, step))
    nr = len(rows)
    nc = len(cols)

    vertices = []
    for i, y in enumerate(rows):
        for j, x in enumerate(cols):
            vx = x * px_mm
            vy = -y * px_mm
            vz = depth_map[y, x]
            vertices.append([vx, vy, vz])

    vertices = np.array(vertices, dtype=np.float64)
    log(ctx, "ESCULTOR", f"Grid: {nr}x{nc} = {len(vertices)} vértices")

    # 3. FACES: triangular o grid (superfície superior)
    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1):
            v0 = i * nc + j
            v1 = v0 + 1
            v2 = (i + 1) * nc + j
            v3 = v2 + 1
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces)
    log(ctx, "ESCULTOR", f"Triangulação: {len(faces)} faces")

    # 4. ÂNCORAS: forçar landmarks 3D
    anchors_applied = 0
    for lm in landmarks_3d:
        lm_x = lm[0] * ctx["resolucao"]["w"] * medidas["px_para_mm"]
        lm_y = -lm[1] * ctx["resolucao"]["h"] * medidas["px_para_mm"]
        lm_z = lm[2]

        dists = np.sqrt((vertices[:, 0] - lm_x)**2 + (vertices[:, 1] - lm_y)**2)
        closest = np.argmin(dists)

        if dists[closest] < step * px_mm * 2:
            old_z = vertices[closest, 2]
            vertices[closest, 2] = old_z * 0.5 + lm_z * 0.5
            anchors_applied += 1

    log(ctx, "ESCULTOR", f"Âncoras: {anchors_applied}/{len(landmarks_3d)}")

    # 5. SUAVIZAÇÃO
    smooth_iter = 2
    smooth_factor = 0.3
    if feedback and "suavizar" in str(feedback):
        smooth_iter = 4
        smooth_factor = 0.5

    mesh_top = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh_top = _suavizar(mesh_top, iterations=smooth_iter, factor=smooth_factor)

    # 6. FECHAR MESH: criar base + laterais → watertight
    mesh = _fechar_mesh_solido(mesh_top, nr, nc, espessura_base=3.0)

    # 7. CORREÇÕES
    mesh.fix_normals()
    trimesh.repair.fill_holes(mesh)

    ctx["mesh"] = mesh
    ctx["status"] = "mesh_ok"
    log(ctx, "ESCULTOR", f"Mesh final: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, watertight={mesh.is_watertight}")

    return ctx


def _suavizar(mesh: trimesh.Trimesh, iterations: int = 2, factor: float = 0.3) -> trimesh.Trimesh:
    """Suavização laplaciana."""
    verts = mesh.vertices.copy()
    adj = mesh.vertex_neighbors

    for _ in range(iterations):
        new_v = verts.copy()
        for i, nbrs in enumerate(adj):
            if len(nbrs) > 0:
                avg = verts[nbrs].mean(axis=0)
                new_v[i] = verts[i] + factor * (avg - verts[i])
        verts = new_v

    mesh.vertices = verts
    return mesh


def _fechar_mesh_solido(mesh_top: trimesh.Trimesh, nr: int, nc: int, espessura_base: float = 3.0) -> trimesh.Trimesh:
    """Fecha o mesh com base + laterais → sólido watertight pra impressão."""
    verts_top = mesh_top.vertices.copy()
    faces_top = mesh_top.faces.copy()
    n_top = len(verts_top)

    # Base: mesmos vértices XY mas Z fixo (abaixo do mínimo)
    z_base = verts_top[:, 2].min() - espessura_base
    verts_base = verts_top.copy()
    verts_base[:, 2] = z_base

    # Faces da base: mesmas faces mas invertidas (winding oposto)
    faces_base = faces_top.copy()[:, ::-1] + n_top

    # Laterais: conectar bordas do topo com bordas da base
    faces_sides = []

    # Borda superior (primeira linha: i=0)
    for j in range(nc - 1):
        a = j
        b = j + 1
        faces_sides.append([a, b, b + n_top])
        faces_sides.append([a, b + n_top, a + n_top])

    # Borda inferior (última linha: i=nr-1)
    for j in range(nc - 1):
        a = (nr - 1) * nc + j
        b = a + 1
        faces_sides.append([a, a + n_top, b + n_top])
        faces_sides.append([a, b + n_top, b])

    # Borda esquerda (primeira coluna: j=0)
    for i in range(nr - 1):
        a = i * nc
        b = (i + 1) * nc
        faces_sides.append([a, a + n_top, b + n_top])
        faces_sides.append([a, b + n_top, b])

    # Borda direita (última coluna: j=nc-1)
    for i in range(nr - 1):
        a = i * nc + (nc - 1)
        b = (i + 1) * nc + (nc - 1)
        faces_sides.append([a, b, b + n_top])
        faces_sides.append([a, b + n_top, a + n_top])

    # Combinar tudo
    all_verts = np.vstack([verts_top, verts_base])
    all_faces = np.vstack([faces_top, faces_base, np.array(faces_sides)])

    mesh = trimesh.Trimesh(vertices=all_verts, faces=all_faces)
    return mesh
