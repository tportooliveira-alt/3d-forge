"""Comparacao lado a lado: referencia real x vetores gerados.

E o instrumento do loop de qualidade -- o agente critico olha esta imagem e
aponta os defeitos ate a peca ficar fiel ao original.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from shapely.geometry.polygon import orient

from .build import _circle, artwork, base_outline
from .params import PALETTE, Params
from .trace import _iter_polygons, find_disc, load_front_panel


def _patch(poly, **kw) -> PathPatch:
    # orient(): exterior anti-horario, furos horarios. matplotlib preenche
    # pela regra nonzero -- sem isso o furo da argola some no preview.
    poly = orient(poly, 1.0)
    v, c = [], []
    for ring in [poly.exterior, *poly.interiors]:
        pts = np.asarray(ring.coords)
        v.extend(pts)
        c.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY])
    return PathPatch(Path(v, c), **kw)


def draw_generated(ax, p: Params, art: dict) -> None:
    """Desenha a peca gerada como o slicer a vera, de cima."""
    dark = np.array(PALETTE["purple"]) / 255.0
    for g in _iter_polygons(base_outline(p)):
        ax.add_patch(_patch(g, facecolor=dark * 0.82, ec="none", zorder=1))
    for g in _iter_polygons(_circle(p.groove_outer, p)):
        ax.add_patch(_patch(g, facecolor=dark * 0.66, ec="none", zorder=2))
    for g in _iter_polygons(_circle(p.field_radius, p)):
        ax.add_patch(_patch(g, facecolor=dark, ec="none", zorder=3))
    for name in ("white", "skin", "pink", "hair"):
        if name not in art or art[name].is_empty:
            continue
        rgb = np.array(PALETTE[name]) / 255.0
        for g in _iter_polygons(art[name]):
            ax.add_patch(_patch(g, facecolor=rgb, ec="none", zorder=4))


def render(p: Params, image_path: str, out_path: str,
           zoom: str = "full") -> str:
    """Gera o PNG de comparacao. `zoom` em {"full", "figura", "texto"}."""
    rgb = load_front_panel(image_path)
    cx, cy, r = find_disc(rgb)
    art = artwork(p, image_path)

    windows = {
        "full":   (-23, 23, -23, 23),
        "figura": (-15.5, 1.5, -8.5, 13.5),
        "texto":  (-19, 19, -19, -8),
    }
    x0, x1, y0, y1 = windows[zoom]

    fig, axes = plt.subplots(1, 2, figsize=(15, 15 * (y1 - y0) / (2 * (x1 - x0))))
    scale = p.radius / r
    extent = [(0 - cx) * scale, (rgb.shape[1] - cx) * scale,
              (cy - rgb.shape[0]) * scale, cy * scale]
    axes[0].imshow(rgb, extent=extent, origin="upper", interpolation="lanczos")
    axes[0].set_title("REFERENCIA (real)", fontsize=13)

    axes[1].set_facecolor("#ffffff")
    draw_generated(axes[1], p, art)
    axes[1].set_title("GERADO (vetores que viram STL)", fontsize=13)

    for a in axes:
        a.set_xlim(x0, x1)
        a.set_ylim(y0, y1)
        a.set_aspect("equal")
        a.set_xticks([])
        a.set_yticks([])

    fig.tight_layout()
    fig.savefig(out_path, dpi=130, facecolor="white")
    plt.close(fig)
    return out_path
