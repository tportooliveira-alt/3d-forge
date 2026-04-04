import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import TEMP_DIR, ALLOWED_ALL, ALLOWED_EXTENSIONS, ALLOWED_IMAGES, MAX_FILE_SIZE


def get_file_type(filename: str) -> str:
    """Retorna 'model', 'image' ou 'unknown'."""
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        return "model"
    if ext in ALLOWED_IMAGES:
        return "image"
    return "unknown"


def validate_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_ALL


def save_upload(file: UploadFile) -> dict:
    """Salva arquivo no temp/ e retorna metadata."""
    job_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename).suffix.lower()
    dest = TEMP_DIR / f"{job_id}{ext}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size = dest.stat().st_size
    if size > MAX_FILE_SIZE:
        dest.unlink()
        raise ValueError(f"Arquivo muito grande: {size} bytes (max {MAX_FILE_SIZE})")

    return {
        "job_id": job_id,
        "filename": file.filename,
        "extension": ext,
        "type": get_file_type(file.filename),
        "size": size,
        "path": str(dest),
    }


def save_from_url(url: str) -> dict:
    """Placeholder - baixa arquivo de URL."""
    job_id = str(uuid.uuid4())[:8]
    # TODO: implementar download com httpx
    return {
        "job_id": job_id,
        "url": url,
        "status": "pending",
    }
