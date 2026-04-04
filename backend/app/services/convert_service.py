import trimesh
import numpy as np
from pathlib import Path
from app.core.config import OUTPUTS_DIR


def convert_to_stl(job_id: str, input_path: str) -> dict:
    """Converte arquivo 3D para STL usando trimesh + auto-repair."""
    path = Path(input_path)

    if not path.exists():
        return {"job_id": job_id, "status": "error", "message": "Arquivo não encontrado"}

    try:
        loaded = trimesh.load(str(path))
    except Exception as e:
        return {"job_id": job_id, "status": "error", "message": f"Falha ao carregar: {e}"}

    if isinstance(loaded, trimesh.Scene):
        mesh = loaded.dump(concatenate=True)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        return {"job_id": job_id, "status": "error", "message": "Formato não resultou em malha válida"}

    # Auto-repair: fix normals, merge vertices, fill holes
    mesh.merge_vertices()
    mesh.fix_normals()
    trimesh.repair.fill_holes(mesh)
    mesh.remove_unreferenced_vertices()

    # Remover faces degeneradas
    mask = mesh.area_faces > 0
    if not mask.all():
        mesh.update_faces(mask)

    # Remover faces duplicadas
    unique, idx = np.unique(np.sort(mesh.faces, axis=1), axis=0, return_index=True)
    if len(idx) < len(mesh.faces):
        mesh.update_faces(np.sort(idx))

    output_path = OUTPUTS_DIR / f"{job_id}.stl"
    mesh.export(str(output_path), file_type="stl")

    return {
        "job_id": job_id,
        "status": "done",
        "output": str(output_path),
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": mesh.is_watertight,
    }
