"""
PIPELINE FACE3D
Orquestra os 4 agentes com cruzamento de dados e loop de refinamento.
Analista → Calculista → Escultor → Inspetor → (refina?) → STL
"""

import gc
import uuid
from pathlib import Path
from app.services.agents import create_context, log
from app.services.agents import analista, calculista, escultor, inspetor
from app.core.config import OUTPUTS_DIR


def executar_pipeline(image_path: str) -> dict:
    """Pipeline completo: foto → agentes cruzando dados → STL."""
    job_id = str(uuid.uuid4())[:8]
    ctx = create_context(image_path)
    ctx["max_iteracoes"] = 2  # Limitar pra economizar RAM

    # === AGENTE 1: ANALISTA ===
    ctx = analista.executar(ctx)
    if ctx["status"] == "error":
        return _resultado_erro(job_id, ctx)

    # === AGENTE 2: CALCULISTA (cruza com Analista + MiDaS) ===
    ctx = calculista.executar(ctx)

    # Liberar MiDaS da memória após usar
    try:
        from app.services import midas_service
        midas_service._model = None
        midas_service._transform = None
    except Exception:
        pass
    gc.collect()

    # === LOOP: ESCULTOR + INSPETOR (cruzam e refinam) ===
    while ctx["iteracao"] < ctx["max_iteracoes"]:
        ctx["iteracao"] += 1
        log(ctx, "PIPELINE", f"=== Iteração {ctx['iteracao']} ===")

        ctx = escultor.executar(ctx)
        ctx = inspetor.executar(ctx)

        if ctx["status"] == "aprovado":
            break

        log(ctx, "PIPELINE", f"Score {ctx['score']}/100 - refinando...")

    # === EXPORTAR STL ===
    output_path = OUTPUTS_DIR / f"{job_id}_face3d.stl"
    ctx["mesh"].export(str(output_path), file_type="stl")

    result = {
        "job_id": job_id,
        "status": "done",
        "output": str(output_path),
        "score": ctx["score"],
        "iteracoes": ctx["iteracao"],
        "erros": ctx["erros"],
        "medidas": ctx["medidas"],
        "proporcoes": ctx["proporcoes"],
        "pose": ctx["pose"],
        "qualidade": ctx["qualidade"],
        "vertices": len(ctx["mesh"].vertices),
        "faces": len(ctx["mesh"].faces),
        "watertight": bool(ctx["mesh"].is_watertight),
        "log": ctx["log"],
    }

    # Liberar mesh da memória
    del ctx
    gc.collect()

    return result


def _resultado_erro(job_id: str, ctx: dict) -> dict:
    return {
        "job_id": job_id,
        "status": "error",
        "message": ctx["log"][-1] if ctx["log"] else "Erro desconhecido",
        "qualidade": ctx.get("qualidade"),
        "log": ctx["log"],
    }
