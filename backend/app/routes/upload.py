from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import validate_extension, save_upload, save_from_url
from app.core.config import ALLOWED_ALL
from pydantic import BaseModel
from typing import List

router = APIRouter()


class UrlInput(BaseModel):
    url: str


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload de arquivo 3D ou imagem."""
    if not validate_extension(file.filename):
        raise HTTPException(400, f"Extensão não suportada. Aceitos: {ALLOWED_ALL}")
    try:
        result = save_upload(file)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(413, str(e))


@router.post("/upload-multiple")
async def upload_multiple(files: List[UploadFile] = File(...)):
    """Upload de vários arquivos de uma vez."""
    results = []
    for file in files:
        if not validate_extension(file.filename):
            results.append({"filename": file.filename, "status": "error", "message": "Extensão não suportada"})
            continue
        try:
            result = save_upload(file)
            results.append({"status": "ok", **result})
        except ValueError as e:
            results.append({"filename": file.filename, "status": "error", "message": str(e)})
    return {"total": len(results), "files": results}


@router.post("/upload-url")
async def upload_from_url(data: UrlInput):
    """Recebe URL de arquivo para download."""
    result = save_from_url(data.url)
    return {"status": "ok", **result}
