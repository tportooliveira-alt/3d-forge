"""
CLEANUP SERVICE
Remove arquivos temporários antigos.
"""

import os
import time
from pathlib import Path
from app.core.config import TEMP_DIR, OUTPUTS_DIR


def cleanup_temp(max_age_hours: int = 24) -> dict:
    """Remove arquivos em temp/ mais velhos que max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    freed = 0

    for f in TEMP_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            size = f.stat().st_size
            f.unlink()
            removed += 1
            freed += size

    return {
        "removed": removed,
        "freed_bytes": freed,
        "freed_mb": round(freed / 1024 / 1024, 2),
    }


def get_storage_info() -> dict:
    """Info de uso de disco."""
    temp_size = sum(f.stat().st_size for f in TEMP_DIR.iterdir() if f.is_file())
    output_size = sum(f.stat().st_size for f in OUTPUTS_DIR.iterdir() if f.is_file())
    temp_count = sum(1 for f in TEMP_DIR.iterdir() if f.is_file())
    output_count = sum(1 for f in OUTPUTS_DIR.iterdir() if f.is_file())

    return {
        "temp": {"files": temp_count, "size_mb": round(temp_size / 1024 / 1024, 2)},
        "outputs": {"files": output_count, "size_mb": round(output_size / 1024 / 1024, 2)},
        "total_mb": round((temp_size + output_size) / 1024 / 1024, 2),
    }
