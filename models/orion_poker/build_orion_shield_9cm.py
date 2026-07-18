#!/usr/bin/env python3
"""
ÓRION POKER — escudo da referência em 9 cm de largura e 1 cm de altura total.

Reaproveita a geometria de build_orion_shield.py (layout fiel à imagem de
referência), reduz o footprint para 90 mm de largura (proporção preservada ->
~65 mm de altura) e recalcula os relevos para 10 mm totais: base preta de
6 mm + relevos, com Rigel (estrela em destaque) chegando aos 10 mm exatos.

Saídas (em ./output_9cm):
  - orion_poker_shield_9cm.3mf          -> multicolor para Bambu Studio
  - orion_poker_shield_9cm_completo.stl -> peça inteira em um único STL
  - stl/<parte>.stl                     -> 1 STL por cor
  - preview.png

Uso:  python3 build_orion_shield_9cm.py
"""

import os

import trimesh
from shapely.affinity import scale as shp_scale

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_9cm")
os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)

TARGET_W = 90.0      # largura alvo (9 cm)
BASE_Z = 6.0         # base preta
TOTAL_Z = 10.0       # altura total da peça (1 cm)

# relevos recalculados (a partir de z = 6 mm)
HEIGHTS = {
    "base_escudo_preto": (0.0, BASE_Z),
    "moldura_ouro": (BASE_Z, 1.5),
    "filete_ouro": (BASE_Z, 1.0),
    "ceu_microestrelas_branco": (BASE_Z, 0.6),
    "ceu_microestrelas_ouro": (BASE_Z, 0.6),
    "constelacao_linhas_branco": (BASE_Z, 0.8),
    "estrelas_constelacao_branco": (BASE_Z, 1.2),
    "estrelas_decor_ouro": (BASE_Z, 1.2),
    "estrela_rigel_destaque_ouro": (BASE_Z, TOTAL_Z - BASE_Z),   # topo em 10 mm
    "nome_orion_ouro": (BASE_Z, 2.2),
    "poker_ouro": (BASE_Z, 1.4),
    "naipes_aro_ouro": (BASE_Z, 0.9),
    "naipe_espadas_grafite": (BASE_Z, 1.2),
    "naipe_copas_vermelho": (BASE_Z, 1.2),
    "naipe_ouros_vermelho": (BASE_Z, 1.2),
    "naipe_paus_grafite": (BASE_Z, 1.2),
    "chevron_ouro": (BASE_Z, 1.4),
}

# ------------------------------------------------------------------ geometria
# executa o script base só até a lista `parts` (sem extrusão/exportação)
_src = open(os.path.join(HERE, "build_orion_shield.py")).read()
_src = _src.split("meshes = []")[0]
_ns = {"__file__": os.path.join(HERE, "build_orion_shield.py")}
exec(compile(_src, "build_orion_shield.py", "exec"), _ns)

parts_full = _ns["parts"]
extrude = _ns["extrude"]
write_3mf_src = _src  # (write_3mf é definido depois; recriado abaixo)

_shield = _ns["shield"]
_b = _shield.bounds
SCALE = TARGET_W / (_b[2] - _b[0])

print(f"escala XY: {SCALE:.4f}  ({_b[2] - _b[0]:.1f} mm -> {TARGET_W:.1f} mm)")

meshes = []
for name, geom, _z0, _h, color in parts_full:
    z0, h = HEIGHTS[name]
    g = shp_scale(geom, xfact=SCALE, yfact=SCALE, origin=(0, 0))
    m = extrude(g, z0, h)
    m.metadata["name"] = name
    m.visual.face_colors = color
    meshes.append((name, m, color))
    m.export(os.path.join(OUT, "stl", f"{name}.stl"))
    print(f"  {name:38s} tris={len(m.faces):6d} z={z0:.1f}->{z0 + h:.1f}mm")

# peça inteira em um único STL
full = trimesh.util.concatenate([m for _n, m, _c in meshes])
full.export(os.path.join(OUT, "orion_poker_shield_9cm_completo.stl"))
fb = full.bounds
print(f"\n  footprint: {fb[1][0] - fb[0][0]:.1f} x {fb[1][1] - fb[0][1]:.1f} mm | altura total: {fb[1][2] - fb[0][2]:.1f} mm")

# ------------------------------------------------------------------ 3MF
import zipfile


def write_3mf(path, items):
    def hexc(c):
        return "#%02X%02X%02X" % c[:3]

    objs, build = [], []
    mats = "".join(f'<base name="{n}" displaycolor="{hexc(c)}" />' for n, _, c in items)
    for i, (n, m, _c) in enumerate(items):
        vs = "".join(f'<vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}" />' for v in m.vertices)
        ts = "".join(f'<triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" />' for f in m.faces)
        objs.append(
            f'<object id="{i + 2}" type="model" name="{n}" pid="1" pindex="{i}">'
            f"<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>"
        )
        build.append(f'<item objectid="{i + 2}" />')
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'
        f'<resources><basematerials id="1">{mats}</basematerials>'
        f'{"".join(objs)}</resources><build>{"".join(build)}</build></model>'
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


write_3mf(os.path.join(OUT, "orion_poker_shield_9cm.3mf"), meshes)

# ------------------------------------------------------------------ preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon as MplPoly
from shapely.geometry import MultiPolygon

fig, ax = plt.subplots(figsize=(9, 7), facecolor="#111")
ax.set_facecolor("#111")


def draw(geom, color, hole_color, z):
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in geoms:
        if p.is_empty:
            continue
        ax.add_patch(MplPoly(np.array(p.exterior.coords), closed=True, fc=color, ec="none", zorder=z))
        for ring in p.interiors:
            ax.add_patch(MplPoly(np.array(ring.coords), closed=True, fc=hole_color, ec="none", zorder=z + 0.4))


for i, (name, geom, _z0, _h, color) in enumerate(parts_full):
    g = shp_scale(geom, xfact=SCALE, yfact=SCALE, origin=(0, 0))
    hole = "#18161a" if i > 0 else "#111"
    draw(g, "#18161a" if name == "base_escudo_preto" else "#%02x%02x%02x" % color[:3], hole, z=i + 1)
ax.set_xlim(-48, 48)
ax.set_ylim(-40, 30)
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "preview.png"), dpi=160, bbox_inches="tight", facecolor="#111")
print("OK ->", OUT)
