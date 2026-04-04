from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import save_upload
from app.services.repair_service import repair_mesh

router = APIRouter()

ALLOWED_STL = [".stl", ".obj", ".ply", ".3mf"]


@router.post("/repair")
async def repair(file: UploadFile = File(...)):
    """Recebe STL/mesh, repara e retorna resultado."""
    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_STL:
        raise HTTPException(400, f"Extensão {ext} não suportada. Use: {ALLOWED_STL}")

    saved = save_upload(file)
    result = repair_mesh(saved["job_id"], saved["path"])

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result
