"""
FIREBASE SERVICE
Conecta com Firestore pra persistir jobs, resultados e histórico.
Funciona com ou sem Firebase (fallback em memória).
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

_db = None
_USE_FIREBASE = False


def init_firebase():
    """Inicializa Firebase se credenciais existirem."""
    global _db, _USE_FIREBASE

    key_path = os.environ.get("FIREBASE_KEY", "serviceAccountKey.json")
    project_id = os.environ.get("FIREBASE_PROJECT", "")

    if Path(key_path).exists():
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)

            _db = firestore.client()
            _USE_FIREBASE = True
            print(f"[Firebase] Conectado ao Firestore")
            return True
        except Exception as e:
            print(f"[Firebase] Falha ao conectar: {e}")

    print("[Firebase] Sem credenciais — usando memória local")
    return False


# ─── FALLBACK EM MEMÓRIA ───
_memory_store = {"jobs": {}, "chat_history": [], "stats": {"total_jobs": 0, "total_converts": 0, "total_repairs": 0, "total_face3d": 0}}


def save_job(job_id: str, data: dict) -> dict:
    """Salva resultado de um job."""
    doc = {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": data.get("status", "unknown"),
        "action": data.get("action", ""),
        "vertices": data.get("vertices"),
        "faces": data.get("faces"),
        "watertight": data.get("watertight"),
        "score": data.get("score"),
        "output": data.get("output", ""),
        "filename": data.get("filename", ""),
    }

    if _USE_FIREBASE and _db:
        _db.collection("jobs").document(job_id).set(doc)
    else:
        _memory_store["jobs"][job_id] = doc

    # Atualizar stats
    _update_stats(data.get("action", ""))
    return doc


def get_job(job_id: str) -> dict | None:
    """Busca um job pelo ID."""
    if _USE_FIREBASE and _db:
        doc = _db.collection("jobs").document(job_id).get()
        return doc.to_dict() if doc.exists else None
    else:
        return _memory_store["jobs"].get(job_id)


def list_jobs(limit: int = 20) -> list:
    """Lista jobs recentes."""
    if _USE_FIREBASE and _db:
        docs = _db.collection("jobs").order_by("created_at", direction="DESCENDING").limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    else:
        jobs = sorted(_memory_store["jobs"].values(), key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs[:limit]


def save_chat(message: str, action: str | None, response: dict) -> dict:
    """Salva mensagem do chat."""
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "action": action,
        "response_status": response.get("status", ""),
    }

    if _USE_FIREBASE and _db:
        _db.collection("chat_history").add(doc)
    else:
        _memory_store["chat_history"].append(doc)
        if len(_memory_store["chat_history"]) > 100:
            _memory_store["chat_history"] = _memory_store["chat_history"][-100:]

    return doc


def get_stats() -> dict:
    """Retorna estatísticas de uso."""
    if _USE_FIREBASE and _db:
        doc = _db.collection("stats").document("global").get()
        return doc.to_dict() if doc.exists else _memory_store["stats"]
    else:
        return _memory_store["stats"]


def _update_stats(action: str):
    """Incrementa contadores."""
    _memory_store["stats"]["total_jobs"] += 1
    key = f"total_{action}s" if action else ""
    if key in _memory_store["stats"]:
        _memory_store["stats"][key] += 1

    if _USE_FIREBASE and _db:
        from google.cloud.firestore_v1 import Increment
        ref = _db.collection("stats").document("global")
        ref.set({"total_jobs": Increment(1)}, merge=True)
        if action:
            ref.set({f"total_{action}s": Increment(1)}, merge=True)
