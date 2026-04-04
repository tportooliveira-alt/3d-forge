"""
MESH ANALYZER
Análise completa de um modelo 3D: geometria, printability, problemas.
"""

import trimesh
import numpy as np
from pathlib import Path


def analyze_mesh(file_path: str) -> dict:
    """Análise completa de um arquivo 3D."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": "Arquivo não encontrado"}

    try:
        loaded = trimesh.load(str(path))
        if isinstance(loaded, trimesh.Scene):
            mesh = loaded.dump(concatenate=True)
        else:
            mesh = loaded
    except Exception as e:
        return {"status": "error", "message": f"Falha ao carregar: {e}"}

    bounds = mesh.bounds
    dims = bounds[1] - bounds[0]

    # Problemas de printability
    problems = []
    if not mesh.is_watertight:
        problems.append("Malha não é watertight (tem buracos)")
    if not mesh.is_winding_consistent:
        problems.append("Winding inconsistente (normais invertidas)")
    if dims.min() < 0.5:
        problems.append(f"Dimensão mínima muito fina: {dims.min():.2f}mm")

    thin_walls = _check_thin_walls(mesh)
    if thin_walls > 0:
        problems.append(f"{thin_walls} regiões com parede fina (<0.8mm)")

    # Faces degeneradas
    degen = (mesh.area_faces < 1e-10).sum()
    if degen > 0:
        problems.append(f"{degen} faces degeneradas (área zero)")

    printable = len(problems) == 0

    result = {
        "status": "done",
        "geometria": {
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "edges": len(mesh.edges_unique),
            "dimensoes_mm": {"x": round(float(dims[0]), 2), "y": round(float(dims[1]), 2), "z": round(float(dims[2]), 2)},
            "bounding_box_mm3": round(float(np.prod(dims)), 2),
        },
        "topologia": {
            "watertight": mesh.is_watertight,
            "winding_consistent": mesh.is_winding_consistent,
            "euler_number": int(mesh.euler_number),
            "bodies": len(mesh.split()),
        },
        "metricas": {
            "area_superficie_mm2": round(float(mesh.area), 2),
            "volume_mm3": round(float(abs(mesh.volume)), 2) if mesh.is_watertight else None,
            "volume_cm3": round(float(abs(mesh.volume)) / 1000, 3) if mesh.is_watertight else None,
            "centro_massa": [round(float(x), 2) for x in mesh.center_mass],
        },
        "printability": {
            "printable": printable,
            "score": max(0, 100 - len(problems) * 20),
            "problemas": problems,
        },
    }

    return result


def _check_thin_walls(mesh: trimesh.Trimesh, threshold: float = 0.8) -> int:
    """Checa regiões com paredes finas demais pra impressão."""
    try:
        edges = mesh.edges_unique_length
        thin = (edges < threshold).sum()
        return int(thin) if thin > len(edges) * 0.1 else 0
    except Exception:
        return 0
