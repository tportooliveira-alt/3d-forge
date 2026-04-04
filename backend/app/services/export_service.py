"""
EXPORT SERVICE
Exporta mesh em múltiplos formatos: STL, OBJ, GLB, PLY, 3MF
"""

import trimesh
from pathlib import Path
from app.core.config import OUTPUTS_DIR

SUPPORTED_FORMATS = {
    "stl": "application/octet-stream",
    "obj": "model/obj",
    "glb": "model/gltf-binary",
    "ply": "application/octet-stream",
    "3mf": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
}


def export_mesh(mesh: trimesh.Trimesh, job_id: str, fmt: str = "stl") -> dict:
    """Exporta mesh no formato pedido."""
    fmt = fmt.lower().strip(".")
    if fmt not in SUPPORTED_FORMATS:
        return {"status": "error", "message": f"Formato '{fmt}' não suportado. Use: {list(SUPPORTED_FORMATS.keys())}"}

    output_path = OUTPUTS_DIR / f"{job_id}.{fmt}"
    mesh.export(str(output_path), file_type=fmt)

    return {
        "job_id": job_id,
        "status": "done",
        "format": fmt,
        "output": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "mime": SUPPORTED_FORMATS[fmt],
    }


def export_all(mesh: trimesh.Trimesh, job_id: str) -> dict:
    """Exporta em todos os formatos de uma vez."""
    results = {}
    for fmt in SUPPORTED_FORMATS:
        try:
            r = export_mesh(mesh, f"{job_id}_{fmt}", fmt)
            results[fmt] = r
        except Exception as e:
            results[fmt] = {"status": "error", "message": str(e)}
    return {"job_id": job_id, "formats": results}


def convert_format(input_path: str, job_id: str, target_fmt: str) -> dict:
    """Carrega arquivo 3D e converte pra outro formato."""
    path = Path(input_path)
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

    return export_mesh(mesh, job_id, target_fmt)
