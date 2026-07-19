#!/usr/bin/env python3
"""
ÓRION POKER — TROFÉU 29 cm gerado diretamente da imagem de referência.

A imagem do troféu é vista de frente (sem perspectiva relevante), então:
  1. a silhueta exata vem da própria imagem (escudo, braços curvos, haste
     com espada e base — preservando os vãos entre braços e haste)
  2. o brilho de cada pixel vira relevo na face frontal
  3. peça com 290 mm de altura, 30 mm de espessura, costas planas
  4. além da peça completa, gera o corte em 2 partes (superior/base) para
     caber na mesa de impressão (ex.: Bambu 256 x 256, impressas deitadas)

Saídas (em ./output_trofeu):
  - orion_trophy_29cm_completo.stl
  - orion_trophy_29cm_parte_superior.stl
  - orion_trophy_29cm_parte_base.stl
  - preview.png

Uso:  python3 build_orion_trophy_29cm.py
"""

import os

import numpy as np
import trimesh
from PIL import Image, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_trofeu")
os.makedirs(OUT, exist_ok=True)

IMG = os.path.join(HERE, "referencia_trofeu.png")

TOTAL_H = 290.0        # altura do troféu (29 cm)
BACK_Z = 0.0           # costas planas
FACE_Z = 24.0          # nível da face frontal
RELIEF = 6.0           # profundidade do relevo (24 -> 30 mm)
CELL = 0.6             # resolução (mm por célula)
Y_FLOOR = 1315         # linha (px) onde termina a base na foto (abaixo é reflexo)
Y_TOP_PX = 55          # topo do troféu na foto
CUT_MM = 145.0         # altura do corte entre as 2 partes de impressão

# ---------------------------------------------------------------- imagem
im = Image.open(IMG).convert("RGB")
arr = np.asarray(im).astype(float)
lum_full = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(1.0))).astype(float) / 255.0

# máscara do troféu: tudo que não é fundo escuro — ouro, gemas, e o céu
# estrelado azulado do escudo e da base (o fundo é marrom-escuro: r > b)
r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
lum255 = np.asarray(im.convert("L")).astype(float)
gold = (r > 100) & (g > 62) & (b < r * 0.8) & (r > g)
bright = lum255 > 48
bluish_sky = (b > r * 0.92) & (lum255 > 10)
mask_img = gold | bright | bluish_sky
mask_img[Y_FLOOR:, :] = False
mask_img[:Y_TOP_PX, :] = False

# região do pedestal (parte de baixo): o anel inferior fica em sombra — usa
# varredura por linha com limiar baixo, preenchendo entre as bordas
BASE_TOP_PX = 1030
for row in range(BASE_TOP_PX, Y_FLOOR):
    idx = np.nonzero(lum255[row] > 24)[0]
    if len(idx) >= 2 and idx[-1] - idx[0] > 150:
        mask_img[row, idx[0]:idx[-1] + 1] = True

mask_img = ndimage.binary_closing(mask_img, iterations=4)
mask_img = ndimage.binary_fill_holes(mask_img)          # céu dentro do escudo
lbl, nl = ndimage.label(mask_img)
if nl > 1:
    mask_img = lbl == (np.bincount(lbl.ravel())[1:].argmax() + 1)

# eixo de simetria: mediana dos pontos médios por linha
rows = np.nonzero(mask_img.any(axis=1))[0]
mids = [(np.nonzero(mask_img[row])[0][[0, -1]].mean()) for row in rows]
axis_x = float(np.median(mids))

# ---------------------------------------------------------------- grid da peça
mm_per_px = TOTAL_H / (Y_FLOOR - Y_TOP_PX)
step = CELL / mm_per_px                                  # passo em px
cols = np.arange(axis_x - 470, axis_x + 470 + step, step)
rows_px = np.arange(Y_TOP_PX, Y_FLOOR + step, step)
PX, PY = np.meshgrid(cols, rows_px)


def sample(channel, px, py):
    Hpx, Wpx = channel.shape
    x0 = np.clip(np.floor(px).astype(int), 0, Wpx - 2)
    y0 = np.clip(np.floor(py).astype(int), 0, Hpx - 2)
    fx = np.clip(px - x0, 0, 1)
    fy = np.clip(py - y0, 0, 1)
    v = (
        channel[y0, x0] * (1 - fx) * (1 - fy)
        + channel[y0, x0 + 1] * fx * (1 - fy)
        + channel[y0 + 1, x0] * (1 - fx) * fy
        + channel[y0 + 1, x0 + 1] * fx * fy
    )
    v[(px < 0) | (px >= Wpx - 1) | (py < 0) | (py >= Hpx - 1)] = 0.0
    return v


inside = sample(mask_img.astype(float), PX, PY) > 0.5
inside = inside & inside[:, ::-1]                        # simetriza
inside = ndimage.binary_opening(inside, iterations=2)
lbl, nl = ndimage.label(inside)
if nl > 1:                                               # não perde os vãos reais
    keep = np.bincount(lbl.ravel())[1:]
    inside = np.isin(lbl, [i + 1 for i, c in enumerate(keep) if c > 400])
inside = ndimage.gaussian_filter(inside.astype(float), sigma=1.8) > 0.5

lum = sample(lum_full, PX, PY)
lo, hi = np.percentile(lum[inside], [3, 99.5])
ln = np.clip((lum - lo) / (hi - lo), 0, 1)
height = FACE_Z + RELIEF * ln**0.8
height[~inside] = 0.0

# coordenadas da peça (mm): y cresce para cima, base em y=0
GX = (PX - axis_x) * mm_per_px
GY = (Y_FLOOR - PY) * mm_per_px


# ---------------------------------------------------------------- malha estanque
def build_mesh(sel):
    vidx_top = -np.ones(sel.shape, dtype=int)
    vidx_bot = -np.ones(sel.shape, dtype=int)
    verts = []
    for yy, xx in zip(*np.nonzero(sel)):
        vidx_top[yy, xx] = len(verts); verts.append((GX[yy, xx], GY[yy, xx], height[yy, xx]))
        vidx_bot[yy, xx] = len(verts); verts.append((GX[yy, xx], GY[yy, xx], BACK_Z))
    verts = np.array(verts)
    quad = sel[:-1, :-1] & sel[:-1, 1:] & sel[1:, :-1] & sel[1:, 1:]
    faces = []
    pad = np.zeros((quad.shape[0] + 1, quad.shape[1] + 1), dtype=bool)
    pad[:-1, :-1] = quad
    for yy, xx in zip(*np.nonzero(quad)):
        a, bb = vidx_top[yy, xx], vidx_top[yy, xx + 1]
        c, d = vidx_top[yy + 1, xx], vidx_top[yy + 1, xx + 1]
        faces += [(a, bb, d), (a, d, c)]
        a2, b2 = vidx_bot[yy, xx], vidx_bot[yy, xx + 1]
        c2, d2 = vidx_bot[yy + 1, xx], vidx_bot[yy + 1, xx + 1]
        faces += [(a2, d2, b2), (a2, c2, d2)]
        if xx == 0 or not pad[yy, xx - 1]:
            t0, t1 = vidx_top[yy, xx], vidx_top[yy + 1, xx]
            b0, b1 = vidx_bot[yy, xx], vidx_bot[yy + 1, xx]
            faces += [(t0, t1, b1), (t0, b1, b0)]
        if not pad[yy, xx + 1]:
            t0, t1 = vidx_top[yy, xx + 1], vidx_top[yy + 1, xx + 1]
            b0, b1 = vidx_bot[yy, xx + 1], vidx_bot[yy + 1, xx + 1]
            faces += [(t0, b1, t1), (t0, b0, b1)]
        if yy == 0 or not pad[yy - 1, xx]:
            t0, t1 = vidx_top[yy, xx], vidx_top[yy, xx + 1]
            b0, b1 = vidx_bot[yy, xx], vidx_bot[yy, xx + 1]
            faces += [(t0, b1, t1), (t0, b0, b1)]
        if not pad[yy + 1, xx]:
            t0, t1 = vidx_top[yy + 1, xx], vidx_top[yy + 1, xx + 1]
            b0, b1 = vidx_bot[yy + 1, xx], vidx_bot[yy + 1, xx + 1]
            faces += [(t0, t1, b1), (t0, b1, b0)]
    m = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    m.remove_unreferenced_vertices()
    return m


full = build_mesh(inside)
full.export(os.path.join(OUT, "orion_trophy_29cm_completo.stl"))
fb = full.bounds
print(f"completo: {len(full.faces)} tris | watertight={full.is_watertight}")
print(f"  {fb[1][0]-fb[0][0]:.0f} x {fb[1][1]-fb[0][1]:.0f} x {fb[1][2]-fb[0][2]:.0f} mm (L x A x P)")

lower = inside & (GY <= CUT_MM)
upper = inside & (GY > CUT_MM)
for sel, name in [(upper, "parte_superior"), (lower, "parte_base")]:
    m = build_mesh(sel)
    m.export(os.path.join(OUT, f"orion_trophy_29cm_{name}.stl"))
    mb = m.bounds
    print(f"{name}: {mb[1][0]-mb[0][0]:.0f} x {mb[1][1]-mb[0][1]:.0f} mm | watertight={m.is_watertight}")

# ---------------------------------------------------------------- preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

hm = np.where(inside, height, np.nan)
ls_ = LightSource(azdeg=315, altdeg=55)
shaded = ls_.shade(np.nan_to_num(hm, nan=FACE_Z - 2), cmap=plt.cm.copper, vert_exag=2.0, blend_mode="overlay")
shaded[~inside] = [0.07, 0.07, 0.07, 1.0]
fig, ax = plt.subplots(figsize=(7, 10), facecolor="#111")
ax.imshow(shaded)
ax.axhline((Y_FLOOR - Y_TOP_PX) / (CELL / mm_per_px) - CUT_MM / CELL, color="cyan", lw=0.8, ls="--")
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "preview.png"), dpi=140, bbox_inches="tight", facecolor="#111")
print("OK ->", OUT)
