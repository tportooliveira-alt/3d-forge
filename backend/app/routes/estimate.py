from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.file_service import save_upload
from app.services.print_estimator import estimate_print, PRINTER_PROFILES, FILAMENTS

router = APIRouter()


@router.post("/estimate")
async def estimate(
    file: UploadFile = File(...),
    printer: str = Query("generic", description="Perfil: ender3, prusa_mk4, bambu_p1s, generic"),
    filament: str = Query("pla", description="Material: pla, petg, abs, tpu"),
    infill: int = Query(20, description="Infill % (0-100)"),
    scale: float = Query(1.0, description="Escala do modelo"),
):
    """Estima tempo, material e custo de impressão 3D."""
    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    if ext not in [".stl", ".obj", ".ply", ".3mf"]:
        raise HTTPException(400, "Envie STL, OBJ, PLY ou 3MF")

    saved = save_upload(file)
    result = estimate_print(saved["path"], printer, filament, infill, scale)

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result


@router.get("/printers")
async def list_printers():
    """Lista impressoras disponíveis."""
    return {k: v["name"] for k, v in PRINTER_PROFILES.items()}


@router.get("/filaments")
async def list_filaments():
    """Lista filamentos disponíveis."""
    return {k: {"name": v["name"], "price_kg_usd": v["price_kg"]} for k, v in FILAMENTS.items()}
