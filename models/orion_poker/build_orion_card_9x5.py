#!/usr/bin/env python3
"""
ÓRION POKER — placa formato cartão 9 x 5 cm, 1 cm de altura total (Bambu Lab).

Layout horizontal: escudo com a constelação de Órion e a estrela em destaque
à esquerda; nome ÓRION / POKER em relevo forte à direita, com os naipes.

Dimensões: 90 x 50 mm, altura total 10 mm (base 6 mm + relevos; a estrela
em destaque é o ponto mais alto da peça, chegando aos 10 mm).

Saídas (em ./output_9x5):
  - orion_poker_card_9x5.3mf     -> abrir direto no Bambu Studio (cores por objeto)
  - stl/<parte>.stl              -> 1 STL por cor
  - preview.png

Uso:  python3 build_orion_card_9x5.py
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
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_9x5")
os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)

# ---------------------------------------------------------------- dimensões (mm)
CARD_W, CARD_H = 90.0, 50.0
CORNER_R = 4.0
BASE_Z = 6.0          # base preta
RIM_Z = 1.2           # moldura dourada do cartão
LINE_Z = 1.0          # linhas da constelação
STAR_Z = 1.2          # estrelas pequenas
HERO_Z = 4.0          # estrela em destaque -> topo em 10.0 mm
NAME_Z = 2.4          # ÓRION
SUB_Z = 1.6           # POKER
SUIT_Z = 1.2          # naipes
TOTAL = BASE_Z + HERO_Z  # 10.0 mm

GOLD = (212, 160, 23, 255)
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
    from shapely.geometry import Point

    core = Point(cx, cy).buffer(max(0.55, r * 0.30), resolution=24)
    spikes = sparkle(cx, cy, r, ratio=0.115)
    diag = sparkle(cx, cy, r * 0.58, ratio=0.16, rot=np.pi / 4)
    return unary_union([core, spikes, diag])


def line_strip(pts, width):
    return LineString(pts).buffer(width / 2, cap_style=1, join_style=1)


def extrude(geom, z0, height):
    geom = geom.buffer(0)
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    meshes = [trimesh.creation.extrude_polygon(p, height) for p in polys if p.area > 0.05]
    m = trimesh.util.concatenate(meshes)
    m.apply_translation([0, 0, z0])
    return m


# ---------------------------------------------------------------- cartão
card = box(-CARD_W / 2, -CARD_H / 2, CARD_W / 2, CARD_H / 2).buffer(CORNER_R).buffer(-CORNER_R * 2).buffer(CORNER_R)
card_rim = card.buffer(-1.2).difference(card.buffer(-2.8))

# ---------------------------------------------------------------- escudo (esquerda)
def shield_outline(width):
    """Proporções do logo original: escudo equilibrado, pouco mais alto que largo."""
    hw = width / 2
    top_y, peak_y = 0.50 * width, 0.57 * width
    right = bezier(np.array([hw, top_y]), np.array([hw + 0.02 * width, -0.08 * width]), np.array([hw * 0.66, -0.36 * width]))
    tip = bezier(np.array([hw * 0.66, -0.36 * width]), np.array([hw * 0.32, -0.54 * width]), np.array([0.0, -0.62 * width]))
    upper = [(-hw, top_y), (0.0, peak_y), (hw, top_y)]
    right_side = list(map(tuple, np.vstack([right, tip])))
    left_side = [(-x, y) for x, y in right_side[::-1]]
    return Polygon(upper + right_side + left_side[1:]).buffer(0)


SH_W = 32.0                                  # largura do escudo
SH_CX, SH_CY = -26.0, 0.0                    # posição no cartão
shield_raw = shield_outline(SH_W)
minx, miny, maxx, maxy = shield_raw.bounds
shield = shp_translate(shield_raw, xoff=SH_CX, yoff=SH_CY - (miny + maxy) / 2)
sh_rim = shield.difference(shield.buffer(-1.6))
sh_inner = shield.buffer(-1.6)

# constelação de Órion com posições REAIS: (AR em horas, Dec em graus, magnitude)
# Fonte: coordenadas J2000. Projeção plana x = -AR*15 (céu visto da Terra:
# Betelgeuse em cima à esquerda, Rigel embaixo à direita), y = Dec.
# Escala uniforme -> proporções fiéis às distâncias angulares reais no céu.
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
sminx, sminy, smaxx, smaxy = sh_inner.bounds
CONST_H = 20.0                                          # altura da constelação no escudo
WIDEN_X = 1.25                                          # abertura horizontal estética
CONST_C = (SH_CX - 1.2, (sminy + smaxy) / 2 + 2.5)      # centro no escudo

_raw = {n: (-(ra * 15.0), dec) for n, (ra, dec, _m) in ORION.items()}
_xs, _ys = zip(*_raw.values())
_s = CONST_H / (max(_ys) - min(_ys))
_cx, _cy = (max(_xs) + min(_xs)) / 2, (max(_ys) + min(_ys)) / 2


def cpos(name):
    x, y = _raw[name]
    return (CONST_C[0] + (x - _cx) * _s * WIDEN_X, CONST_C[1] + (y - _cy) * _s)


BELT = ("alnitak", "alnilam", "mintaka")


def star_r(name, mag, base=3.1, slope=0.55, rmin=1.3):
    """Raio proporcional ao brilho real (magnitude menor = estrela maior).
    As três Marias ficam compactas como no céu real."""
    r = max(rmin, base - slope * mag)
    return min(r, 1.5) if name in BELT else r


small_stars = unary_union(
    [flare_star(*cpos(n), r=star_r(n, m)) for n, (_ra, _dec, m) in ORION.items() if n != "rigel"]
)

# a ESTRELA EM DESTAQUE — Rigel, a mais brilhante de Órion (mag 0.13):
# em ouro, ponto mais alto da peça (10 mm), com brilho realista
from shapely.geometry import Point

hero_xy = cpos("rigel")
hero = unary_union([
    Point(hero_xy).buffer(1.4, resolution=32),
    sparkle(*hero_xy, r=4.2, ratio=0.11),
    sparkle(*hero_xy, r=2.6, ratio=0.15, rot=np.pi / 4),
])

# linhas FINAS por baixo, recortadas ao redor das estrelas (sem sobreposição);
# ao redor de Rigel o recorte é circular, para um acabamento limpo
const_lines = unary_union([line_strip([cpos(a), cpos(b)], 0.55) for a, b in EDGES])
const_lines = const_lines.difference(small_stars.buffer(0.1))
const_lines = const_lines.difference(Point(hero_xy).buffer(3.8))

sh_clip = sh_inner.buffer(-0.3)

# ---------------------------------------------------------------- lado direito
TX = 16.0  # centro do bloco de texto
name_txt = center_at(text_poly("ÓRION", SERIF_BOLD, 20), TX, 8.5, target_w=48)
poker_txt = center_at(text_poly("P O K E R", SANS_BOLD, 8), TX, -4.5, target_w=32)
dash_l = Polygon([(TX - 26, -4.0), (TX - 19, -4.5), (TX - 26, -5.0)])
dash_r = Polygon([(TX + 26, -4.0), (TX + 19, -4.5), (TX + 26, -5.0)])
poker_full = unary_union([poker_txt, dash_l, dash_r])

suit_y, suit_s = -14.5, 6.2
spade = center_at(text_poly("♠", SANS_BOLD, 12), TX - 13.5, suit_y, target_h=suit_s)
heart = center_at(text_poly("♥", SANS_BOLD, 12), TX - 4.5, suit_y, target_h=suit_s * 0.92)
diamond = center_at(text_poly("♦", SANS_BOLD, 12), TX + 4.5, suit_y, target_h=suit_s)
club = center_at(text_poly("♣", SANS_BOLD, 12), TX + 13.5, suit_y, target_h=suit_s)

# brilhos decorativos no canto superior direito
DECOR = [(38.5, 19.5, 2.0), (33.0, 15.0, 1.3), (40.0, 12.5, 1.1), (-6.5, 18.5, 1.4)]
decor_stars = unary_union([flare_star(x, y, r) for x, y, r in DECOR])

# linha dourada sob os naipes
underline = Polygon([(TX - 24, -20.6), (TX + 24, -20.6), (TX + 20, -22.0), (TX - 20, -22.0)])

clip = card.buffer(-1.2)


def cc(g):
    return g.intersection(clip)


parts = [
    ("base_cartao_preto", card, 0.0, BASE_Z, BLACK),
    ("moldura_ouro", card_rim, BASE_Z, RIM_Z, GOLD),
    ("escudo_borda_ouro", cc(sh_rim), BASE_Z, RIM_Z + 0.2, GOLD),
    ("constelacao_linhas_branco", sh_clip.intersection(const_lines), BASE_Z, LINE_Z, WHITE),
    ("estrelas_pequenas_branco", sh_clip.intersection(small_stars.difference(hero.buffer(0.3))), BASE_Z, STAR_Z, WHITE),
    ("estrela_soares_destaque_ouro", sh_clip.intersection(hero), BASE_Z, HERO_Z, GOLD),
    ("nome_orion_ouro", cc(name_txt), BASE_Z, NAME_Z, GOLD),
    ("poker_ouro", cc(poker_full), BASE_Z, SUB_Z, GOLD),
    ("naipe_espadas_prata", cc(spade), BASE_Z, SUIT_Z, SILVER),
    ("naipe_copas_vermelho", cc(heart), BASE_Z, SUIT_Z, RED),
    ("naipe_ouros_vermelho", cc(diamond), BASE_Z, SUIT_Z, RED),
    ("naipe_paus_prata", cc(club), BASE_Z, SUIT_Z, SILVER),
    ("estrelas_decor_ouro", cc(decor_stars), BASE_Z, STAR_Z, GOLD),
    ("linha_ouro", cc(underline), BASE_Z, SUB_Z, GOLD),
]

meshes = []
for name, geom, z0, h, color in parts:
    m = extrude(geom, z0, h)
    m.metadata["name"] = name
    m.visual.face_colors = color
    meshes.append((name, m, color))
    m.export(os.path.join(OUT, "stl", f"{name}.stl"))
    print(f"  {name:38s} tris={len(m.faces):6d} z={z0:.1f}->{z0 + h:.1f}mm")

print(f"\n  footprint: {CARD_W:.0f} x {CARD_H:.0f} mm | altura total: {TOTAL:.1f} mm")

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


write_3mf(os.path.join(OUT, "orion_poker_card_9x5.3mf"), meshes)

# ---------------------------------------------------------------- preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly

fig, ax = plt.subplots(figsize=(9, 5.4), facecolor="#111")
ax.set_facecolor("#111")


def draw(geom, color, hole_color, z):
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in geoms:
        if p.is_empty:
            continue
        ax.add_patch(MplPoly(np.array(p.exterior.coords), closed=True, fc=color, ec="none", zorder=z))
        for ring in p.interiors:
            ax.add_patch(MplPoly(np.array(ring.coords), closed=True, fc=hole_color, ec="none", zorder=z + 0.4))


PREV = {"base_cartao_preto": "#1c1a18"}
for i, (name, geom, _z0, _h, color) in enumerate(parts):
    hole = "#1c1a18" if i > 0 else "#111"
    draw(geom, PREV.get(name, "#%02x%02x%02x" % color[:3]), hole, z=i + 1)
ax.set_xlim(-49, 49)
ax.set_ylim(-28, 28)
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "preview.png"), dpi=160, bbox_inches="tight", facecolor="#111")
print("OK ->", OUT)
