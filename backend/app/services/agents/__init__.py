"""
CONTEXT: Dados compartilhados entre todos os agentes.
Cada agente lê o que precisa e escreve seus resultados aqui.
"""


def create_context(image_path: str) -> dict:
    return {
        "image_path": image_path,
        "status": "iniciado",
        "landmarks": None,
        "pose": None,
        "qualidade": None,
        "resolucao": None,
        "depth_map": None,
        "medidas": None,
        "proporcoes": None,
        "landmarks_3d": None,
        "mesh": None,
        "score": 0,
        "erros": None,
        "feedback": None,
        "iteracao": 0,
        "max_iteracoes": 3,
        "log": [],
    }


def log(ctx: dict, agente: str, msg: str):
    ctx["log"].append(f"[{agente}] {msg}")
