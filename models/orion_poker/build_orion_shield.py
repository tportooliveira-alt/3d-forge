#!/usr/bin/env python3
"""
ÓRION POKER — placa/escudo em relevo para impressão 3D multicolor (Bambu Lab).

Gera a partir do logo base (Paulo_Poker_02alt.pdf) uma versão modernizada:
  - escudo com borda dourada em relevo
  - constelação de Órion em linhas brancas elevadas
  - estrela principal ("estrela Soares") em destaque — a mais alta da peça
  - nome ÓRION / POKER extrudado, "saindo" do escudo
  - naipes de baralho em relevo
  - chevron dourado na base

Saídas (em ./output):
  - orion_poker_shield.3mf        -> abrir direto no Bambu Studio (cores por objeto)
  - stl/<parte>.stl               -> 1 STL por cor (importar como multi-part)
  - preview.png                   -> pré-visualização das camadas

Uso:  python3 build_orion_shield.py
Deps: shapely, trimesh, numpy, matplotlib, mapbox_earcut
"""

import os
import zipfile
from functools import reduce

import numpy as np
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.affinity import scale as shp_scale, translate as shp_translate
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)

# ---------------------------------------------------------------- dimensões (mm)
W = 110.0            # largura total do escudo
BASE_Z = 3.0         # espessura da base preta
RIM_Z = 1.8          # relevo da borda dourada
LINE_Z = 1.0         # relevo das linhas da constelação
STAR_Z = 1.4         # relevo das estrelas pequenas
HERO_Z = 3.2         # relevo da estrela em destaque (a mais alta da peça)
NAME_Z = 2.4         # relevo do nome ÓRION
SUB_Z = 1.6          # relevo de POKER
SUIT_Z = 1.4         # relevo dos naipes
CHEV_Z = 1.6         # relevo do chevron

GOLD = (212, 160, 23, 255)
DARKGOLD = (140, 95, 20, 255)
BLACK = (28, 26, 24, 255)
WHITE = (240, 240, 245, 255)
RED = (190, 30, 40, 255)
SILVER = (200, 200, 205, 255)

SERIF_BOLD = FontProperties(family="DejaVu Serif", weight="bold")
SANS_BOLD = FontProperties(family="DejaVu Sans", weight="bold")


# ---------------------------------------------------------------- helpers
def bezier(p0, p1, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2


def text_poly(txt, font, size):
    """TextPath -> shapely polygon com furos (regra even-odd via XOR)."""
    tp = TextPath((0, 0), txt, size=size, prop=font)
    polys = []
    for pts in tp.to_polygons():
        if len(pts) >= 3:
            p = Polygon(pts)
            if p.is_valid and p.area > 1e-6:
                polys.append(p)
    if not polys:
        return MultiPolygon()
    geom = reduce(lambda a, b: a.symmetric_difference(b), polys)
    return geom.buffer(0)


def center_at(geom, cx, cy, target_w=None):
    minx, miny, maxx, maxy = geom.bounds
    if target_w:
        f = target_w / (maxx - minx)
        geom = shp_scale(geom, xfact=f, yfact=f, origin=(0, 0))
        minx, miny, maxx, maxy = geom.bounds
    return shp_translate(geom, xoff=cx - (minx + maxx) / 2, yoff=cy - (miny + maxy) / 2)


def sparkle(cx, cy, r, ratio=0.22, points=4, rot=0.0):
    """Estrela tipo 'brilho' de N pontas."""
    ang = np.linspace(0, 2 * np.pi, points * 2, endpoint=False) + np.pi / 2 + rot
    rad = np.where(np.arange(points * 2) % 2 == 0, r, r * ratio)
    pts = np.c_[cx + rad * np.cos(ang), cy + rad * np.sin(ang)]
    return Polygon(pts)


def line_strip(pts, width):
    from shapely.geometry import LineString

    return LineString(pts).buffer(width / 2, cap_style=1, join_style=1)


def extrude(geom, z0, height):
    geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError("geometria vazia")
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    meshes = [trimesh.creation.extrude_polygon(p, height) for p in polys if p.area > 0.05]
    m = trimesh.util.concatenate(meshes)
    m.apply_translation([0, 0, z0])
    return m


# ---------------------------------------------------------------- escudo
def shield_outline():
    """Escudo moderno: topo em leve pico, laterais curvas, ponta embaixo."""
    hw = W / 2
    top_y, peak_y = 46.0, 51.0
    right = bezier(np.array([hw, top_y]), np.array([hw + 2, -8.0]), np.array([hw * 0.62, -32.0]))
    tip = bezier(np.array([hw * 0.62, -32.0]), np.array([hw * 0.30, -50.0]), np.array([0.0, -58.0]))
    upper = [(-hw, top_y), (0.0, peak_y), (hw, top_y)]
    right_side = list(map(tuple, np.vstack([right, tip])))
    left_side = [(-x, y) for x, y in right_side[::-1]]
    return Polygon(upper + right_side + left_side[1:]).buffer(0)


shield = shield_outline()
rim = shield.difference(shield.buffer(-4.2))          # borda dourada
inner = shield.buffer(-4.2)

# ---------------------------------------------------------------- constelação de Órion
# posições REAIS: (AR em horas, Dec em graus, magnitude aparente), J2000.
# Projeção plana x = -AR*15 (céu visto da Terra: Betelgeuse em cima à
# esquerda, Rigel embaixo à direita), y = Dec. Escala uniforme -> proporções
# fiéis às distâncias angulares reais no céu.
ORION = {
    "betelgeuse": (5.9195, 7.4071, 0.50),
    "bellatrix": (5.4189, 6.3497, 1.64),
    "meissa": (5.5856, 9.9342, 3.33),
    "alnitak": (5.6793, -1.9426, 1.77),
    "alnilam": (5.6036, -1.2019, 1.69),
    "mintaka": (5.5334, -0.2991, 2.23),
    "hatysa": (5.5904, -5.9099, 2.77),
    "saiph": (5.7959, -9.6696, 2.09),
    "rigel": (5.2423, -8.2016, 0.13),
}
EDGES = [
    ("meissa", "betelgeuse"), ("meissa", "bellatrix"),
    ("betelgeuse", "alnitak"), ("bellatrix", "mintaka"),
    ("alnitak", "alnilam"), ("alnilam", "mintaka"),
    ("alnilam", "hatysa"),                              # espada de Órion
    ("alnitak", "saiph"), ("mintaka", "rigel"), ("saiph", "rigel"),
]
CONST_H = 36.0                                          # altura da constelação
CONST_C = (-4.0, 27.0)                                  # centro no céu do escudo

_raw = {n: (-(ra * 15.0), dec) for n, (ra, dec, _m) in ORION.items()}
_xs, _ys = zip(*_raw.values())
_s = CONST_H / (max(_ys) - min(_ys))                    # mesma escala nos dois eixos
_ccx, _ccy = (max(_xs) + min(_xs)) / 2, (max(_ys) + min(_ys)) / 2


def cpos(name):
    x, y = _raw[name]
    return (CONST_C[0] + (x - _ccx) * _s, CONST_C[1] + (y - _ccy) * _s)


BELT = ("alnitak", "alnilam", "mintaka")


def star_r(name, mag, base=3.4, slope=0.62, rmin=1.3):
    """Raio proporcional ao brilho real (magnitude menor = estrela maior).
    As Três Marias ficam compactas: na escala real distam ~2,5 mm entre si."""
    r = max(rmin, base - slope * mag)
    return min(r, 1.6) if name in BELT else r


small_stars = unary_union(
    [sparkle(*cpos(n), r=star_r(n, m), ratio=0.34) for n, (_ra, _dec, m) in ORION.items() if n != "rigel"]
)

# brilhos decorativos espalhados no céu
DECOR = [(-34, 18, 2.2), (-40, 32, 1.6), (36, 12, 2.0), (-26, 44, 1.5), (24, 47, 1.4), (32, 34, 2.4)]
decor_stars = unary_union([sparkle(x, y, r, ratio=0.32) for x, y, r in DECOR])

# a ESTRELA EM DESTAQUE — Rigel, a mais brilhante de Órion (mag 0.13):
# em ouro, ponto mais alto da peça, na posição real
hero_xy = cpos("rigel")
hero = sparkle(*hero_xy, r=7.0, ratio=0.26, points=4).union(
    sparkle(*hero_xy, r=4.2, ratio=0.34, points=4, rot=np.pi / 4)
)

# linhas por baixo recortadas ao redor das estrelas (sem sólidos sobrepostos)
const_lines = unary_union([line_strip([cpos(a), cpos(b)], 1.3) for a, b in EDGES])
const_lines = const_lines.difference(small_stars.buffer(0.15))

# ---------------------------------------------------------------- textos
name_txt = center_at(text_poly("ÓRION", SERIF_BOLD, 20), 0, -12.5, target_w=78)
poker_txt = center_at(text_poly("P O K E R", SANS_BOLD, 8), 0, -27.0, target_w=46)
dash_l = Polygon([(-38, -26.2), (-27, -27.0), (-38, -27.8)])
dash_r = Polygon([(38, -26.2), (27, -27.0), (38, -27.8)])
poker_full = unary_union([poker_txt, dash_l, dash_r])

# ---------------------------------------------------------------- naipes
suit_y, suit_s = -37.5, 8.5
spade = center_at(text_poly("♠", SANS_BOLD, 12), -19.5, suit_y, target_w=suit_s)
heart = center_at(text_poly("♥", SANS_BOLD, 12), -6.5, suit_y, target_w=suit_s)
diamond = center_at(text_poly("♦", SANS_BOLD, 12), 6.5, suit_y, target_w=suit_s * 0.85)
club = center_at(text_poly("♣", SANS_BOLD, 12), 19.5, suit_y, target_w=suit_s)

# ---------------------------------------------------------------- chevron
chevron = Polygon([(-24, -44.5), (24, -44.5), (0, -51.5)]).difference(
    Polygon([(-17, -45.7), (17, -45.7), (0, -50.0)])
).union(Polygon([(-11, -46.4), (11, -46.4), (0, -49.3)]))

# ---------------------------------------------------------------- recorte e montagem
clip = inner.buffer(-0.4)


def clipped(g):
    return g.intersection(clip)


parts = [
    # (nome, geometria, z0, altura, cor RGBA)
    ("base_escudo_preto", shield, 0.0, BASE_Z, BLACK),
    ("borda_ouro", rim, BASE_Z, RIM_Z, GOLD),
    ("constelacao_linhas_branco", clipped(const_lines.difference(hero.buffer(2.2))), BASE_Z, LINE_Z, WHITE),
    ("estrelas_pequenas_branco", clipped(small_stars.difference(hero.buffer(1.6))), BASE_Z, STAR_Z, WHITE),
    ("estrelas_decor_ouro", clipped(decor_stars), BASE_Z, STAR_Z, GOLD),
    ("estrela_soares_destaque_ouro", clipped(hero), BASE_Z, HERO_Z, GOLD),
    ("nome_orion_ouro", clipped(name_txt), BASE_Z, NAME_Z, GOLD),
    ("poker_ouro", clipped(poker_full), BASE_Z, SUB_Z, GOLD),
    ("naipe_espadas_prata", clipped(spade), BASE_Z, SUIT_Z, SILVER),
    ("naipe_copas_vermelho", clipped(heart), BASE_Z, SUIT_Z, RED),
    ("naipe_ouros_vermelho", clipped(diamond), BASE_Z, SUIT_Z, RED),
    ("naipe_paus_prata", clipped(club), BASE_Z, SUIT_Z, SILVER),
    ("chevron_ouro", clipped(chevron), BASE_Z, CHEV_Z, GOLD),
]

meshes = []
for name, geom, z0, h, color in parts:
    m = extrude(geom, z0, h)
    m.metadata["name"] = name
    m.visual.face_colors = color
    meshes.append((name, m, color))
    m.export(os.path.join(OUT, "stl", f"{name}.stl"))
    print(f"  {name:38s} tris={len(m.faces):6d} z={z0:.1f}->{z0 + h:.1f}mm")

# ---------------------------------------------------------------- 3MF (cores por objeto)
def write_3mf(path, items):
    """3MF mínimo com basematerials — Bambu Studio importa cada parte com sua cor."""
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


write_3mf(os.path.join(OUT, "orion_poker_shield.3mf"), meshes)

# ---------------------------------------------------------------- preview 2D
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly

fig, ax = plt.subplots(figsize=(8, 8), facecolor="#111")
ax.set_facecolor("#111")


def draw(geom, color, hole_color, z=1):
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in geoms:
        if p.is_empty:
            continue
        ax.add_patch(MplPoly(np.array(p.exterior.coords), closed=True, fc=color, ec="none", zorder=z))
        for ring in p.interiors:
            ax.add_patch(MplPoly(np.array(ring.coords), closed=True, fc=hole_color, ec="none", zorder=z + 0.4))


PREV = {"base_escudo_preto": "#1c1a18"}
for i, (name, geom, _z0, _h, color) in enumerate(parts):
    hole = "#1c1a18" if i > 0 else "#111"
    draw(geom, PREV.get(name, "#%02x%02x%02x" % color[:3]), hole, z=i + 1)
ax.set_xlim(-62, 62)
ax.set_ylim(-66, 60)
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "preview.png"), dpi=160, bbox_inches="tight", facecolor="#111")
print("\nOK ->", OUT)
