import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.services.file_service import validate_extension, save_upload
from app.services.convert_service import convert_to_stl
from app.services.firebase_service import save_job
from pathlib import Path

router = APIRouter()


@router.post("/convert")
async def convert(file: UploadFile = File(...)):
    """Recebe arquivo 3D e retorna STL convertido."""
    if not validate_extension(file.filename):
        raise HTTPException(400, "Extensão não suportada")

    saved = save_upload(file)
    result = convert_to_stl(saved["job_id"], saved["path"])

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    save_job(saved["job_id"], {**result, "action": "convert", "filename": file.filename})
    return result


@router.get("/download/{job_id}")
async def download(job_id: str):
    """Baixa o STL convertido."""
    from app.core.config import OUTPUTS_DIR
    path = OUTPUTS_DIR / f"{job_id}.stl"
    if not path.exists():
        raise HTTPException(404, "STL não encontrado")
    return FileResponse(str(path), filename=f"{job_id}.stl", media_type="application/octet-stream")
