from fastapi import APIRouter, Query
from app.services.firebase_service import list_jobs, get_job, get_stats

router = APIRouter()


@router.get("/jobs")
async def jobs(limit: int = Query(20, description="Máximo de jobs")):
    """Lista jobs recentes."""
    return {"jobs": list_jobs(limit)}


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str):
    """Detalhe de um job."""
    job = get_job(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@router.get("/stats")
async def stats():
    """Estatísticas de uso."""
    return get_stats()
