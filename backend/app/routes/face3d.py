from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import save_upload
from app.services.agents.pipeline import executar_pipeline

router = APIRouter()

ALLOWED = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]


@router.post("/face3d")
async def face3d(file: UploadFile = File(...)):
    """Foto de rosto → modelo 3D via pipeline multi-agente."""
    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Use imagem: {ALLOWED}")

    saved = save_upload(file)
    result = executar_pipeline(saved["path"])

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result
