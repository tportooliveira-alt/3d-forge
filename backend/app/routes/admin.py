from fastapi import APIRouter, Query
from app.services.cleanup_service import cleanup_temp, get_storage_info

router = APIRouter()


@router.get("/health")
async def health():
    """Status de saúde da API."""
    storage = get_storage_info()
    return {
        "status": "healthy",
        "storage": storage,
    }


@router.post("/cleanup")
async def cleanup(max_age_hours: int = Query(24, description="Remover temp mais velho que N horas")):
    """Remove arquivos temporários antigos."""
    result = cleanup_temp(max_age_hours)
    return {"status": "done", **result}
