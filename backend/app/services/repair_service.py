import trimesh
import numpy as np
from pathlib import Path
from app.core.config import OUTPUTS_DIR


def repair_mesh(job_id: str, stl_path: str) -> dict:
    """Repara malha STL: remove lixo, preenche buracos, suaviza."""
    path = Path(stl_path)

    if not path.exists():
        return {"job_id": job_id, "status": "error", "message": "STL não encontrado"}

    try:
        mesh = trimesh.load(str(path), force="mesh")
    except Exception as e:
        return {"job_id": job_id, "status": "error", "message": f"Falha ao carregar: {e}"}

    before = {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": mesh.is_watertight,
    }

    # 1. Remove faces degeneradas (área zero)
    mask = mesh.area_faces > 0
    if not mask.all():
        mesh.update_faces(mask)

    # 2. Remove faces duplicadas
    mesh.merge_vertices()
    unique, idx = np.unique(np.sort(mesh.faces, axis=1), axis=0, return_index=True)
    if len(idx) < len(mesh.faces):
        mesh.update_faces(np.sort(idx))

    # 3. Corrige normais (todas pra fora)
    mesh.fix_normals()

    # 4. Preenche buracos simples
    trimesh.repair.fill_holes(mesh)

    # 5. Remove vértices soltos
    mesh.remove_unreferenced_vertices()

    # 6. Suavização leve (laplacian)
    mesh = _laplacian_smooth(mesh, iterations=2, factor=0.3)

    output_path = OUTPUTS_DIR / f"{job_id}_repaired.stl"
    mesh.export(str(output_path), file_type="stl")

    after = {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": mesh.is_watertight,
    }

    # Score de qualidade pós-reparo (0-100)
    score = 100
    if not mesh.is_watertight:
        score -= 40
    if not mesh.is_winding_consistent:
        score -= 20
    degen = int((mesh.area_faces < 1e-10).sum())
    if degen > 0:
        score -= min(30, degen)

    return {
        "job_id": job_id,
        "status": "done",
        "output": str(output_path),
        "watertight": bool(mesh.is_watertight),
        "score": max(0, score),
        "before": before,
        "after": after,
    }


def _laplacian_smooth(mesh: trimesh.Trimesh, iterations: int = 2, factor: float = 0.3) -> trimesh.Trimesh:
    """Suavização laplaciana simples."""
    vertices = mesh.vertices.copy()
    adjacency = mesh.vertex_neighbors

    for _ in range(iterations):
        new_verts = vertices.copy()
        for i, neighbors in enumerate(adjacency):
            if len(neighbors) == 0:
                continue
            avg = vertices[neighbors].mean(axis=0)
            new_verts[i] = vertices[i] + factor * (avg - vertices[i])
        vertices = new_verts

    mesh.vertices = vertices
    return mesh
