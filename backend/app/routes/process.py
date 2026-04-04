from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.orchestrator import process_request, ACTIONS

router = APIRouter()


class ProcessInput(BaseModel):
    action: str
    file_path: str


@router.post("/process")
async def process(data: ProcessInput):
    """Orquestrador: executa ação no arquivo."""
    result = process_request(data.action, data.file_path)

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    return result
