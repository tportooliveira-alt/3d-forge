from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUTS_DIR = BASE_DIR / "outputs"

TEMP_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = [".obj", ".fbx", ".step", ".stp", ".stl", ".ply", ".3mf", ".dxf"]
ALLOWED_IMAGES = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]
ALLOWED_ALL = ALLOWED_EXTENSIONS + ALLOWED_IMAGES
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
