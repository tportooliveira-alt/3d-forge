from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from app.services.file_service import save_upload, validate_extension
from app.services.export_service import convert_format, SUPPORTED_FORMATS
from pathlib import Path

router = APIRouter()


@router.post("/export")
async def export_file(
    file: UploadFile = File(...),
    format: str = Query("stl", description="Formato: stl, obj, glb, ply, 3mf"),
):
    """Converte arquivo 3D pra qualquer formato suportado."""
    ext = Path(file.filename).suffix.lower()
    if ext not in [".obj", ".fbx", ".stl", ".ply", ".3mf", ".glb", ".gltf"]:
        raise HTTPException(400, "Formato de entrada não suportado")

    saved = save_upload(file)
    result = convert_format(saved["path"], saved["job_id"], format)

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result


@router.get("/formats")
async def list_formats():
    """Lista formatos de exportação suportados."""
    return {"formats": list(SUPPORTED_FORMATS.keys())}
