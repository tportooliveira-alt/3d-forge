#!/usr/bin/env python3
"""
ÓRION POKER — escudo em relevo multicolor para impressão 3D (Bambu Lab).

Layout baseado na referência aprovada (render dourado com céu estrelado):
  - escudo LARGO (mais largo que alto), moldura dupla dourada
  - céu com campo de microestrelas + constelação de Órion (posições reais)
  - Rigel em ouro como estrela em destaque (ponto mais alto da peça)
  - ÓRION em letras douradas grandes atravessando o escudo
  - POKER entre traços afilados, naipes com aro dourado, chevron na base

Saídas (em ./output):
  - orion_poker_shield.3mf        -> abrir direto no Bambu Studio (cores por objeto)
  - stl/<parte>.stl               -> 1 STL por cor (importar como multi-part)
  - preview.png

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
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)

# ---------------------------------------------------------------- dimensões (mm)
W = 120.0            # largura total do escudo
BASE_Z = 3.0         # espessura da base preta
RIM_Z = 1.8          # relevo da moldura dourada
LIP_Z = 1.2          # relevo do filete interno dourado
DOT_Z = 0.6          # relevo das microestrelas do céu
LINE_Z = 1.0         # relevo das linhas da constelação
STAR_Z = 1.4         # relevo das estrelas da constelação
HERO_Z = 3.2         # relevo de Rigel (ponto mais alto da peça)
NAME_Z = 2.6         # relevo do nome ÓRION
SUB_Z = 1.6          # relevo de POKER
SUIT_Z = 1.5         # relevo dos naipes
OUTL_Z = 1.0         # relevo do aro dourado dos naipes
CHEV_Z = 1.6         # relevo do chevron

GOLD = (212, 160, 23, 255)
BLACK = (24, 22, 26, 255)
WHITE = (240, 240, 245, 255)
RED = (185, 28, 40, 255)
DARK = (58, 56, 60, 255)

SERIF_BOLD = FontProperties(family="DejaVu Serif", weight="bold")
SANS_BOLD = FontProperties(family="DejaVu Sans", weight="bold")


# ---------------------------------------------------------------- helpers
def bezier(p0, p1, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2


def text_poly(txt, font, size):
    """TextPath -> shapely polygon com furos (regra even-odd via XOR)."""
    tp = TextPath((0, 0), txt, size=size, prop=font)
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    polys = [p for p in polys if p.is_valid and p.area > 1e-6]
    if not polys:
        return MultiPolygon()
    return reduce(lambda a, b: a.symmetric_difference(b), polys).buffer(0)


def center_at(geom, cx, cy, target_w=None, target_h=None):
    minx, miny, maxx, maxy = geom.bounds
    if target_w:
        f = target_w / (maxx - minx)
    elif target_h:
        f = target_h / (maxy - miny)
    else:
        f = 1.0
    geom = shp_scale(geom, xfact=f, yfact=f, origin=(0, 0))
    minx, miny, maxx, maxy = geom.bounds
    return shp_translate(geom, xoff=cx - (minx + maxx) / 2, yoff=cy - (miny + maxy) / 2)


def sparkle(cx, cy, r, ratio=0.22, points=4, rot=0.0):
    ang = np.linspace(0, 2 * np.pi, points * 2, endpoint=False) + np.pi / 2 + rot
    rad = np.where(np.arange(points * 2) % 2 == 0, r, r * ratio)
    return Polygon(np.c_[cx + rad * np.cos(ang), cy + rad * np.sin(ang)])


def flare_star(cx, cy, r):
    """Estrela realista estilo astrofotografia: núcleo redondo + espículos de
    difração longos e finos (cruz principal + cruz diagonal menor)."""
    core = Point(cx, cy).buffer(max(0.75, r * 0.30), resolution=24)
    spikes = sparkle(cx, cy, r, ratio=0.115)
    diag = sparkle(cx, cy, r * 0.58, ratio=0.16, rot=np.pi / 4)
    return unary_union([core, spikes, diag])


def line_strip(pts, width):
    return LineString(pts).buffer(width / 2, cap_style=1, join_style=1)


def extrude(geom, z0, height):
    geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError("geometria vazia")
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    meshes = [trimesh.creation.extrude_polygon(p, height) for p in polys if p.area > 0.04]
    m = trimesh.util.concatenate(meshes)
    m.apply_translation([0, 0, z0])
    return m


# ---------------------------------------------------------------- escudo LARGO
def shield_outline():
    """Como na referência: mais largo que alto, ombros amplos, ponta suave."""
    hw = W / 2                                    # 60
    top_y, peak_y = 30.0, 34.5
    right = bezier(np.array([hw, top_y]), np.array([hw + 1.5, -4.0]), np.array([hw * 0.72, -22.0]))
    tip = bezier(np.array([hw * 0.72, -22.0]), np.array([hw * 0.34, -42.0]), np.array([0.0, -52.0]))
    upper = [(-hw, top_y), (0.0, peak_y), (hw, top_y)]
    right_side = list(map(tuple, np.vstack([right, tip])))
    left_side = [(-x, y) for x, y in right_side[::-1]]
    return Polygon(upper + right_side + left_side[1:]).buffer(0)


shield = shield_outline()                          # ~120 x 80 mm
rim = shield.difference(shield.buffer(-4.5))       # moldura dourada externa
lip = shield.buffer(-6.0).difference(shield.buffer(-7.2))  # filete interno
inner = shield.buffer(-7.2)
sky_clip = inner.buffer(-0.4)

# ---------------------------------------------------------------- constelação (posições reais)
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
CONST_H = 16.0                                          # altura da constelação
WIDEN_X = 3.0                                           # abertura horizontal (referência aprovada)
CONST_C = (0.0, 16.5)                                   # centro no céu do escudo

_raw = {n: (-(ra * 15.0), dec) for n, (ra, dec, _m) in ORION.items()}
_xs, _ys = zip(*_raw.values())
_s = CONST_H / (max(_ys) - min(_ys))
_ccx, _ccy = (max(_xs) + min(_xs)) / 2, (max(_ys) + min(_ys)) / 2


def cpos(name):
    x, y = _raw[name]
    return (CONST_C[0] + (x - _ccx) * _s * WIDEN_X, CONST_C[1] + (y - _ccy) * _s)


BELT = ("alnitak", "alnilam", "mintaka")


def star_r(name, mag, base=3.6, slope=0.62, rmin=1.5):
    """Raio proporcional ao brilho real (magnitude menor = estrela maior)."""
    r = max(rmin, base - slope * mag)
    return min(r, 1.8) if name in BELT else r


small_stars = unary_union(
    [flare_star(*cpos(n), r=star_r(n, m)) for n, (_ra, _dec, m) in ORION.items() if n != "rigel"]
)

# Rigel — a mais brilhante de Órion, em ouro, ponto mais alto da peça
hero_xy = cpos("rigel")
hero = unary_union([
    Point(hero_xy).buffer(2.0, resolution=32),
    sparkle(*hero_xy, r=6.2, ratio=0.11),
    sparkle(*hero_xy, r=3.8, ratio=0.15, rot=np.pi / 4),
])

const_lines = unary_union([line_strip([cpos(a), cpos(b)], 0.85) for a, b in EDGES])
const_lines = const_lines.difference(small_stars.buffer(0.15))
const_lines = const_lines.difference(Point(hero_xy).buffer(5.4))

# ---------------------------------------------------------------- textos
name_txt = center_at(text_poly("ÓRION", SERIF_BOLD, 20), 0, -4.5, target_w=96)
poker_txt = center_at(text_poly("P O K E R", SANS_BOLD, 8), 0, -20.5, target_w=42)
dash_l = Polygon([(-36, -19.9), (-24, -20.5), (-36, -21.1)])
dash_r = Polygon([(36, -19.9), (24, -20.5), (36, -21.1)])
poker_full = unary_union([poker_txt, dash_l, dash_r])

# ---------------------------------------------------------------- naipes com aro dourado
suit_y, suit_s = -28.5, 9.0
spade = center_at(text_poly("♠", SANS_BOLD, 12), -19.5, suit_y, target_h=suit_s)
heart = center_at(text_poly("♥", SANS_BOLD, 12), -6.5, suit_y, target_h=suit_s * 0.92)
diamond = center_at(text_poly("♦", SANS_BOLD, 12), 6.5, suit_y, target_h=suit_s)
club = center_at(text_poly("♣", SANS_BOLD, 12), 19.5, suit_y, target_h=suit_s)
suits_all = unary_union([spade, heart, diamond, club])
suit_rings = unary_union([g.buffer(0.7) for g in (spade, heart, diamond, club)]).difference(
    suits_all.buffer(0.05)
)

# ---------------------------------------------------------------- chevron
chevron = Polygon([(-24, -36.0), (24, -36.0), (0, -42.0)]).difference(
    Polygon([(-17, -37.2), (17, -37.2), (0, -40.6)])
)

# ---------------------------------------------------------------- céu estrelado (microestrelas)
rng = np.random.RandomState(42)
_keepout = unary_union([
    name_txt.buffer(1.5), poker_full.buffer(1.5), suit_rings.buffer(1.2),
    chevron.buffer(1.5), small_stars.buffer(1.2), hero.buffer(1.5),
    const_lines.buffer(1.0),
])
_dots_w, _dots_g = [], []
_minx, _miny, _maxx, _maxy = sky_clip.bounds
_tries = 0
while len(_dots_w) + len(_dots_g) < 85 and _tries < 4000:
    _tries += 1
    x = rng.uniform(_minx, _maxx)
    y = rng.uniform(_miny, _maxy)
    p = Point(x, y)
    if not sky_clip.contains(p) or _keepout.distance(p) < 1.2:
        continue
    if _dots_w or _dots_g:
        existing = _dots_w + _dots_g
        if min((x - a) ** 2 + (y - b) ** 2 for a, b, _r in existing) < 5.0**2:
            continue
    r = rng.uniform(0.35, 0.62)
    (_dots_g if rng.rand() < 0.35 else _dots_w).append((x, y, r))
star_dots_w = unary_union([Point(x, y).buffer(r, resolution=12) for x, y, r in _dots_w])
star_dots_g = unary_union([Point(x, y).buffer(r, resolution=12) for x, y, r in _dots_g])
# alguns brilhos maiores decorativos (como na referência)
DECOR = [(-46, 12, 2.2), (46, 14, 2.4), (-40, 27, 1.7), (42, 27, 1.8)]
decor_stars = unary_union([flare_star(x, y, r) for x, y, r in DECOR])


def clipped(g):
    return g.intersection(sky_clip)


parts = [
    ("base_escudo_preto", shield, 0.0, BASE_Z, BLACK),
    ("moldura_ouro", rim, BASE_Z, RIM_Z, GOLD),
    ("filete_ouro", lip, BASE_Z, LIP_Z, GOLD),
    ("ceu_microestrelas_branco", clipped(star_dots_w), BASE_Z, DOT_Z, WHITE),
    ("ceu_microestrelas_ouro", clipped(star_dots_g), BASE_Z, DOT_Z, GOLD),
    ("constelacao_linhas_branco", clipped(const_lines.difference(name_txt.buffer(1.0))), BASE_Z, LINE_Z, WHITE),
    ("estrelas_constelacao_branco", clipped(small_stars.difference(hero.buffer(0.4)).difference(name_txt.buffer(1.0))), BASE_Z, STAR_Z, WHITE),
    ("estrelas_decor_ouro", clipped(decor_stars.difference(name_txt.buffer(1.0))), BASE_Z, STAR_Z, GOLD),
    ("estrela_rigel_destaque_ouro", clipped(hero.difference(name_txt.buffer(1.0))), BASE_Z, HERO_Z, GOLD),
    ("nome_orion_ouro", clipped(name_txt), BASE_Z, NAME_Z, GOLD),
    ("poker_ouro", clipped(poker_full), BASE_Z, SUB_Z, GOLD),
    ("naipes_aro_ouro", clipped(suit_rings), BASE_Z, OUTL_Z, GOLD),
    ("naipe_espadas_grafite", clipped(spade), BASE_Z, SUIT_Z, DARK),
    ("naipe_copas_vermelho", clipped(heart), BASE_Z, SUIT_Z, RED),
    ("naipe_ouros_vermelho", clipped(diamond), BASE_Z, SUIT_Z, RED),
    ("naipe_paus_grafite", clipped(club), BASE_Z, SUIT_Z, DARK),
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

b = shield.bounds
print(f"\n  footprint: {b[2] - b[0]:.0f} x {b[3] - b[1]:.0f} mm | altura max: {BASE_Z + HERO_Z:.1f} mm")

# ---------------------------------------------------------------- 3MF
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


write_3mf(os.path.join(OUT, "orion_poker_shield.3mf"), meshes)

# ---------------------------------------------------------------- preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly

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


PREV = {"base_escudo_preto": "#18161a"}
for i, (name, geom, _z0, _h, color) in enumerate(parts):
    hole = "#18161a" if i > 0 else "#111"
    draw(geom, PREV.get(name, "#%02x%02x%02x" % color[:3]), hole, z=i + 1)
ax.set_xlim(-64, 64)
ax.set_ylim(-52, 40)
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "preview.png"), dpi=160, bbox_inches="tight", facecolor="#111")
print("OK ->", OUT)
