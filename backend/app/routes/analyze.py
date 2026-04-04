from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import save_upload
from app.services.analyze_service import analyze_mesh

router = APIRouter()


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """Análise completa de modelo 3D: geometria, topologia, printability."""
    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    if ext not in [".stl", ".obj", ".ply", ".3mf", ".glb"]:
        raise HTTPException(400, "Envie STL, OBJ, PLY, 3MF ou GLB")

    saved = save_upload(file)
    result = analyze_mesh(saved["path"])

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result
