"""Preview PNG das camadas 2D -- a forma de conferir o resultado sem GUI."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from shapely.geometry.polygon import orient
import numpy as np

from .build import Slab
from .params import PALETTE, Params
from .trace import _iter_polygons


def _patch(poly, **kw) -> PathPatch:
    """PathPatch de um Polygon shapely respeitando os buracos."""
    poly = orient(poly, 1.0)
    verts, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        pts = np.asarray(ring.coords)
        verts.extend(pts)
        codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY])
    return PathPatch(Path(verts, codes), **kw)


def render(slabs: dict[str, list[Slab]], p: Params, out_path: str,
           title: str = "") -> str:
    """Desenha as camadas de cima para baixo, por altura de topo crescente."""
    fig, (ax, axz) = plt.subplots(
        1, 2, figsize=(13, 7), gridspec_kw={"width_ratios": [1.35, 1]})

    flat: list[tuple[float, str, Slab]] = []
    for color, items in slabs.items():
        for s in items:
            flat.append((s.z1, color, s))
    flat.sort(key=lambda t: t[0])

    for _, color, s in flat:
        rgb = np.array(PALETTE.get(color, (128, 128, 128))) / 255.0
        for poly in _iter_polygons(s.geom):
            ax.add_patch(_patch(poly, facecolor=rgb, edgecolor=(0, 0, 0, 0.30),
                                linewidth=0.35, zorder=s.z1))

    lim = p.radius + 14
    ax.set_xlim(-lim * 0.75, lim * 0.75)
    ax.set_ylim(-p.radius - 4, p.tab_hole_center_y + p.tab_boss_diameter)
    ax.set_aspect("equal")
    ax.set_facecolor("#e9e9ec")
    ax.set_title(title or "Vista de topo (camadas 2D)", fontsize=11)
    ax.set_xlabel("mm")
    ax.grid(alpha=0.15, linewidth=0.4)

    # Corte lateral esquematico: mostra a pilha em Z de cada cor.
    axz.set_title("Pilha em Z por cor (mm)", fontsize=11)
    ordered = sorted(slabs.keys())
    for i, color in enumerate(ordered):
        rgb = np.array(PALETTE.get(color, (128, 128, 128))) / 255.0
        for s in slabs[color]:
            axz.barh(i, s.z1 - s.z0, left=s.z0, height=0.6, color=rgb,
                     edgecolor="black", linewidth=0.5)
    axz.set_yticks(range(len(ordered)))
    axz.set_yticklabels(ordered)
    axz.set_xlabel("z (mm)")
    axz.grid(axis="x", alpha=0.25, linewidth=0.4)
    axz.set_xlim(0, p.total_height + 0.5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Render do relevo: como a peca fica depois de impressa
# ---------------------------------------------------------------------------
def render_relief(slabs: dict[str, list[Slab]], p: Params, out_path: str,
                  px_per_mm: float = 26.0, window=None) -> str:
    """Rasteriza as camadas num mapa de altura e ilumina, como um hillshade.

    E o unico jeito de conferir os DEGRAUS (o do queixo, o do aro) sem abrir um
    visualizador 3D: a vista de topo achatada nao os mostra, porque cor e
    altura sao coisas diferentes aqui.
    """
    import cv2

    x0, x1, y0, y1 = window or (-p.radius - 1, p.radius + 1,
                                -p.radius - 1, p.tab_hole_center_y +
                                p.tab_boss_diameter / 2 + 1)
    w = int((x1 - x0) * px_per_mm)
    h = int((y1 - y0) * px_per_mm)
    height = np.zeros((h, w), np.float32)
    color = np.zeros((h, w, 3), np.float32)

    def to_px(pts):
        q = np.empty_like(pts)
        q[:, 0] = (pts[:, 0] - x0) * px_per_mm
        q[:, 1] = (y1 - pts[:, 1]) * px_per_mm       # Y da imagem cresce p/ baixo
        return np.round(q).astype(np.int32)

    flat = sorted(((s.z1, c, s) for c, items in slabs.items() for s in items),
                  key=lambda t: t[0])
    for _, cname, s in flat:
        rgb = np.array(PALETTE.get(cname, (128, 128, 128)), np.float32) / 255.0
        for poly in _iter_polygons(s.geom):
            m = np.zeros((h, w), np.uint8)
            cv2.fillPoly(m, [to_px(np.asarray(poly.exterior.coords))], 1)
            for ring in poly.interiors:
                cv2.fillPoly(m, [to_px(np.asarray(ring.coords))], 0)
            sel = m > 0
            if not sel.any():
                continue
            higher = sel & (s.z1 >= height)
            height[higher] = s.z1
            color[higher] = rgb

    # Iluminacao: normal do mapa de altura, luz vinda do alto a esquerda.
    hs = cv2.GaussianBlur(height, (0, 0), 1.1)
    gx = cv2.Sobel(hs, cv2.CV_32F, 1, 0, ksize=3) * px_per_mm / 8.0
    gy = cv2.Sobel(hs, cv2.CV_32F, 0, 1, ksize=3) * px_per_mm / 8.0
    nz = 1.0 / np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    lx, ly, lz = -0.45, -0.55, 0.70
    lam = np.clip((-gx * lx - gy * ly + lz) * nz, 0.0, 1.0)
    shade = (0.38 + 0.62 * lam)[..., None]

    img = np.clip(color * shade, 0, 1)
    img[height <= 0] = 0.93                      # fundo
    cv2.imwrite(out_path, (img[:, :, ::-1] * 255).astype(np.uint8))
    return out_path
