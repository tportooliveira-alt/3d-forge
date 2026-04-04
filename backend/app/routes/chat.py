from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.interpreter import interpret_command
from app.services.orchestrator import process_request, ACTIONS

router = APIRouter()


class ChatInput(BaseModel):
    message: str
    file_path: str


@router.post("/chat")
async def chat(data: ChatInput):
    """Recebe texto livre, interpreta e executa."""
    action = interpret_command(data.message)

    if action is None:
        return {
            "status": "unknown",
            "message": "Não entendi. Tente: converter, corrigir, analisar, estimar impressão, exportar",
            "available_actions": ACTIONS,
        }

    try:
        result = process_request(action, data.file_path)
    except Exception as e:
        return {"interpreted_action": action, "status": "error", "message": str(e)}

    if result is None:
        return {"interpreted_action": action, "status": "error", "message": "Ação não retornou resultado"}

    if result.get("status") == "error":
        return {"interpreted_action": action, **result}

    return {"interpreted_action": action, **result}
