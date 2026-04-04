"""
MIDAS DEPTH SERVICE
Gera depth map real a partir de foto usando MiDaS (Intel).
"""

import cv2
import numpy as np
import torch
from pathlib import Path

_model = None
_transform = None


def _load_model():
    global _model, _transform
    if _model is not None:
        return
    _model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
    _model.eval()
    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
    _transform = midas_transforms.small_transform


def estimate_depth(image_path: str) -> np.ndarray | None:
    """Gera depth map normalizado (0-1) de uma imagem."""
    path = Path(image_path)
    if not path.exists():
        return None

    img = cv2.imread(str(path))
    if img is None:
        return None

    _load_model()

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    input_batch = _transform(rgb)

    with torch.no_grad():
        prediction = _model(input_batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    depth = prediction.cpu().numpy()
    depth = depth - depth.min()
    if depth.max() > 0:
        depth = depth / depth.max()

    return depth.astype(np.float32)


def depth_to_mm(depth_norm: np.ndarray, max_depth_mm: float = 18.0) -> np.ndarray:
    """Converte depth normalizado (0-1) pra milímetros."""
    return depth_norm * max_depth_mm
