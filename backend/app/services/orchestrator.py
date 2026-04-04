import uuid
from app.services.convert_service import convert_to_stl
from app.services.repair_service import repair_mesh
from app.services.agents.pipeline import executar_pipeline
from app.services.analyze_service import analyze_mesh
from app.services.print_estimator import estimate_print
from app.services.export_service import convert_format

ACTIONS = ["convert", "repair", "face3d", "analyze", "estimate", "export"]


def process_request(action: str, file_path: str) -> dict:
    """Orquestrador: recebe ação e arquivo, executa o serviço certo."""
    if action not in ACTIONS:
        return {"status": "error", "message": f"Ação inválida. Use: {ACTIONS}"}

    job_id = str(uuid.uuid4())[:8]

    if action == "convert":
        return convert_to_stl(job_id, file_path)

    if action == "repair":
        return repair_mesh(job_id, file_path)

    if action == "face3d":
        return executar_pipeline(file_path)

    if action == "analyze":
        return analyze_mesh(file_path)

    if action == "estimate":
        return estimate_print(file_path)

    if action == "export":
        return convert_format(file_path, job_id, "glb")

    return {"status": "error", "message": "Ação não implementada"}
