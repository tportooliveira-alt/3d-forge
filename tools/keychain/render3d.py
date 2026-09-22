"""Render 3D da peca a partir da malha exportada.

Rasterizador proprio com z-buffer, em numpy. Nao ha OpenGL neste ambiente e os
visualizadores do trimesh dependem dele; alem disso, um render feito da MALHA
(e nao dos poligonos 2D) e a unica previa que mostra a peca como ela sai da
impressora, com o relevo visto de angulo.

Sombreamento: Lambert difuso + um especular fraco. Filamento fosco quase nao
brilha, entao o especular fica baixo de proposito -- exagera-lo faria a previa
parecer plastico injetado, que e justamente o que a peca nao e.
"""

from __future__ import annotations

import numpy as np
import trimesh

from .params import PALETTE


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Matriz de visao (mundo -> camera)."""
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def _camera(bounds: np.ndarray, elev_deg: float, azim_deg: float,
            dist_mult: float) -> tuple[np.ndarray, np.ndarray]:
    """Posiciona a camera em torno da peca e devolve (view, eye)."""
    center = bounds.mean(axis=0)
    radius = float(np.linalg.norm(bounds[1] - bounds[0]) / 2.0)
    e, a = np.deg2rad(elev_deg), np.deg2rad(azim_deg)
    direction = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    eye = center + direction * radius * dist_mult
    return _look_at(eye, center, np.array([0.0, 0.0, 1.0])), eye


def render(meshes: dict[str, trimesh.Trimesh], out_path: str,
           size: int = 1100, supersample: int = 2,
           elev: float = 34.0, azim: float = -68.0, dist: float = 2.9,
           fov_deg: float = 26.0, background=(0.94, 0.94, 0.95),
           palette: dict | None = None) -> str:
    """Rasteriza as malhas coloridas por filamento e grava um PNG."""
    palette = palette or PALETTE
    res = size * supersample

    verts, faces, colors = [], [], []
    offset = 0
    for name, m in meshes.items():
        rgb = np.array(palette.get(name, (150, 150, 150)), np.float64) / 255.0
        verts.append(m.vertices)
        faces.append(m.faces + offset)
        colors.append(np.repeat(rgb[None, :], len(m.faces), axis=0))
        offset += len(m.vertices)
    V = np.vstack(verts)
    F = np.vstack(faces)
    C = np.vstack(colors)

    all_bounds = np.array([V.min(axis=0), V.max(axis=0)])
    view, eye = _camera(all_bounds, elev, azim, dist)

    # Mundo -> camera
    Vc = (view[:3, :3] @ V.T).T + view[:3, 3]

    # Projecao em perspectiva. z da camera e negativo a frente (convencao OpenGL).
    f = 1.0 / np.tan(np.deg2rad(fov_deg) / 2.0)
    depth = -Vc[:, 2]
    depth = np.maximum(depth, 1e-6)
    sx = (Vc[:, 0] * f / depth * 0.5 + 0.5) * res
    sy = (1.0 - (Vc[:, 1] * f / depth * 0.5 + 0.5)) * res

    # Normais por face, no espaco do mundo (a malha nao e escalada).
    tri = V[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 1e-12)

    # Descarta faces de costas: metade dos triangulos, metade do trabalho.
    centroid = tri.mean(axis=1)
    to_eye = eye[None, :] - centroid
    to_eye /= np.maximum(np.linalg.norm(to_eye, axis=1, keepdims=True), 1e-12)
    front = (n * to_eye).sum(axis=1) > 0.0

    # Luz principal alta e a esquerda, mais um preenchimento fraco do outro lado.
    key = np.array([-0.45, -0.35, 0.82]); key /= np.linalg.norm(key)
    fill = np.array([0.55, 0.25, 0.35]); fill /= np.linalg.norm(fill)
    lam = np.clip((n * key).sum(axis=1), 0, 1)
    lam2 = np.clip((n * fill).sum(axis=1), 0, 1)
    half = key + to_eye
    half /= np.maximum(np.linalg.norm(half, axis=1, keepdims=True), 1e-12)
    spec = np.clip((n * half).sum(axis=1), 0, 1) ** 48
    shade = (0.34 + 0.62 * lam + 0.16 * lam2)[:, None] + 0.10 * spec[:, None]
    face_rgb = np.clip(C * shade, 0, 1)

    img = np.empty((res, res, 3), np.float32)
    img[:] = np.array(background, np.float32)
    zbuf = np.full((res, res), np.inf, np.float64)

    P = np.stack([sx, sy], axis=1)
    order = np.nonzero(front)[0]
    for i in order:
        a, b, c = F[i]
        p0, p1, p2 = P[a], P[b], P[c]
        z0, z1, z2 = depth[a], depth[b], depth[c]

        minx = max(int(np.floor(min(p0[0], p1[0], p2[0]))), 0)
        maxx = min(int(np.ceil(max(p0[0], p1[0], p2[0]))), res - 1)
        miny = max(int(np.floor(min(p0[1], p1[1], p2[1]))), 0)
        maxy = min(int(np.ceil(max(p0[1], p1[1], p2[1]))), res - 1)
        if minx > maxx or miny > maxy:
            continue

        area = ((p1[0] - p0[0]) * (p2[1] - p0[1])
                - (p2[0] - p0[0]) * (p1[1] - p0[1]))
        if abs(area) < 1e-12:
            continue

        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((p1[0] - p0[0]) * (gy - p0[1]) - (gx - p0[0]) * (p1[1] - p0[1])) / area
        w1 = ((gx - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (gy - p0[1])) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue

        # Interpolacao de profundidade correta em perspectiva (1/z e que e linear).
        inv = w2 / z0 + w1 / z1 + w0 / z2
        z = np.divide(1.0, inv, out=np.full_like(inv, np.inf), where=inv > 1e-12)

        sub = zbuf[miny:maxy + 1, minx:maxx + 1]
        win = inside & (z < sub)
        if not win.any():
            continue
        sub[win] = z[win]
        img[miny:maxy + 1, minx:maxx + 1][win] = face_rgb[i]

    if supersample > 1:
        img = img.reshape(size, supersample, size, supersample, 3).mean(axis=(1, 3))

    import cv2
    cv2.imwrite(out_path, (np.clip(img, 0, 1)[:, :, ::-1] * 255).astype(np.uint8))
    return out_path
