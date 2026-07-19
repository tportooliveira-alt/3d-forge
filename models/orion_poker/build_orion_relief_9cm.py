#!/usr/bin/env python3
"""
ÓRION POKER — relevo 3D gerado DIRETAMENTE da imagem de referência.

Sem reinterpretação: a própria imagem enviada vira a peça. O processo:
  1. corrige a perspectiva da foto (homografia pelos 4 cantos da face frontal,
     com alvo nas proporções reais da própria foto)
  2. extrai a silhueta do escudo da imagem (máscara da moldura dourada,
     preenchida e simetrizada)
  3. converte o brilho de cada pixel em altura de relevo
     (céu preto = base; ouro/estrelas brilhantes = alto)
  4. gera malha estanque de 90 mm de largura e 10 mm de altura total

Saídas (em ./output_relevo):
  - orion_poker_relevo_9cm.stl   -> peça única, fiel à imagem
  - heightmap_preview.png        -> prévia do relevo (sombreado)

Uso:  python3 build_orion_relief_9cm.py [caminho_da_imagem]
"""

import os
import sys

import numpy as np
import trimesh
from PIL import Image, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_relevo")
os.makedirs(OUT, exist_ok=True)

IMG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "referencia.png")

TARGET_W = 90.0        # largura da peça (9 cm)
BASE_Z = 6.0           # base
TOTAL_Z = 10.0         # altura total (1 cm)
CELL = 0.30            # resolução da malha (mm por célula)

# ---------------------------------------------------------------- imagem
im = Image.open(IMG).convert("RGB")
arr = np.asarray(im).astype(float)

# marcos da FACE FRONTAL na foto (IMG_2256): o pico do topo, as duas dobras
# onde a borda superior encontra as laterais, e a ponta inferior
p_left = (203, 1168)    # dobra superior esquerda
p_right = (922, 1088)   # dobra superior direita
p_top = (525, 1015)     # pico do topo
p_tip = (608, 1612)     # ponta inferior da face frontal

# alvo com as PROPORÇÕES DA PRÓPRIA FOTO: as dobras ficam a ~14% da altura e
# a ~80% da largura máxima (o escudo tem bojo lateral abaixo das dobras)
TOTAL_H = TARGET_W * 0.78          # proporção do render (~90 x 70)
Y_TOP = TOTAL_H * 0.40
Y_TIP = Y_TOP - TOTAL_H
Y_KINK = Y_TOP - 0.141 * TOTAL_H
X_KINK = 0.80 * TARGET_W / 2
DST = {
    "left": (-X_KINK, Y_KINK),
    "right": (X_KINK, Y_KINK),
    "top": (0.0, Y_TOP),
    "tip": (0.0, Y_TIP),
}
SRC = {"left": p_left, "right": p_right, "top": p_top, "tip": p_tip}


def homography(src_pts, dst_pts):
    """Resolve H (3x3, h33=1) que leva src -> dst (DLT com 4 pontos)."""
    A, bvec = [], []
    for (sx, sy), (dx, dy) in zip(src_pts, dst_pts):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy]); bvec.append(dx)
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy]); bvec.append(dy)
    h = np.linalg.solve(np.array(A), np.array(bvec))
    return np.array([[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]])


keys = ["left", "right", "top", "tip"]
H = homography([DST[k] for k in keys], [SRC[k] for k in keys])  # peça(mm) -> foto(px)

# ---------------------------------------------------------------- grid simétrico
xmax = TARGET_W / 2 + 1.0
ymin, ymax = Y_TIP - 1.0, Y_TOP + 1.0
nx = 2 * int(np.ceil(xmax / CELL)) + 1               # simétrico em x=0
ny = int(np.ceil((ymax - ymin) / CELL)) + 1
gx = (np.arange(nx) - nx // 2) * CELL
gy = ymin + np.arange(ny) * CELL
GX, GY = np.meshgrid(gx, gy)
pts = np.c_[GX.ravel(), GY.ravel()]

ph = H @ np.c_[pts, np.ones(len(pts))].T
px = (ph[0] / ph[2]).reshape(GY.shape)
py = (ph[1] / ph[2]).reshape(GY.shape)


def sample(channel):
    """Amostragem bilinear da foto no grid da peça."""
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


# ---------------------------------------------------------------- silhueta da imagem
r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
gold_img = ((r > 110) & (g > 70) & (b < r * 0.75) & (r > g) & (g > b * 1.1)).astype(float)
gold_w = sample(gold_img) > 0.5
# preenchimento por varredura: em cada linha, tudo entre a primeira e a última
# borda dourada pertence ao escudo (robusto a falhas na moldura)
solid = np.zeros_like(gold_w)
for row in range(gold_w.shape[0]):
    idx = np.nonzero(gold_w[row])[0]
    if len(idx) >= 2 and idx[-1] - idx[0] > 8:
        solid[row, idx[0]:idx[-1] + 1] = True
solid = solid & solid[:, ::-1]                        # simetriza (remove espessura 3D lateral)
solid = ndimage.binary_closing(solid, iterations=4)
solid = ndimage.binary_opening(solid, iterations=2)
lbl, nl = ndimage.label(solid)
if nl > 1:                                            # mantém só o maior componente
    solid = lbl == (np.bincount(lbl.ravel())[1:].argmax() + 1)
# suaviza o contorno da silhueta (remove serrilhado da simetrização)
solid = ndimage.gaussian_filter(solid.astype(float), sigma=2.2) > 0.5
inside = ndimage.binary_erosion(solid, iterations=1)

# ---------------------------------------------------------------- brilho -> altura
lum_img = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(1.2))).astype(float) / 255.0
lum = sample(lum_img)
lo, hi = np.percentile(lum[inside], [2, 99.5])
ln = np.clip((lum - lo) / (hi - lo), 0, 1)
height = BASE_Z + (TOTAL_Z - BASE_Z) * ln**0.75
height[~inside] = 0.0

# ---------------------------------------------------------------- malha estanque
vidx_top = -np.ones(GY.shape, dtype=int)
vidx_bot = -np.ones(GY.shape, dtype=int)
verts = []
iy, ix = np.nonzero(inside)
for yy, xx in zip(iy, ix):
    vidx_top[yy, xx] = len(verts); verts.append((GX[yy, xx], GY[yy, xx], height[yy, xx]))
    vidx_bot[yy, xx] = len(verts); verts.append((GX[yy, xx], GY[yy, xx], 0.0))
verts = np.array(verts)

quad_ok = inside[:-1, :-1] & inside[:-1, 1:] & inside[1:, :-1] & inside[1:, 1:]
faces = []
for yy, xx in zip(*np.nonzero(quad_ok)):
    a, bb = vidx_top[yy, xx], vidx_top[yy, xx + 1]
    c, d = vidx_top[yy + 1, xx], vidx_top[yy + 1, xx + 1]
    faces += [(a, bb, d), (a, d, c)]                  # topo
    a2, b2 = vidx_bot[yy, xx], vidx_bot[yy, xx + 1]
    c2, d2 = vidx_bot[yy + 1, xx], vidx_bot[yy + 1, xx + 1]
    faces += [(a2, d2, b2), (a2, c2, d2)]             # fundo (invertido)

padded = np.zeros((quad_ok.shape[0] + 1, quad_ok.shape[1] + 1), dtype=bool)
padded[:-1, :-1] = quad_ok
for yy, xx in zip(*np.nonzero(quad_ok)):
    if xx == 0 or not padded[yy, xx - 1]:             # oeste
        t0, t1 = vidx_top[yy, xx], vidx_top[yy + 1, xx]
        b0, b1 = vidx_bot[yy, xx], vidx_bot[yy + 1, xx]
        faces += [(t0, t1, b1), (t0, b1, b0)]
    if not padded[yy, xx + 1]:                        # leste
        t0, t1 = vidx_top[yy, xx + 1], vidx_top[yy + 1, xx + 1]
        b0, b1 = vidx_bot[yy, xx + 1], vidx_bot[yy + 1, xx + 1]
        faces += [(t0, b1, t1), (t0, b0, b1)]
    if yy == 0 or not padded[yy - 1, xx]:             # sul
        t0, t1 = vidx_top[yy, xx], vidx_top[yy, xx + 1]
        b0, b1 = vidx_bot[yy, xx], vidx_bot[yy, xx + 1]
        faces += [(t0, b1, t1), (t0, b0, b1)]
    if not padded[yy + 1, xx]:                        # norte
        t0, t1 = vidx_top[yy + 1, xx], vidx_top[yy + 1, xx + 1]
        b0, b1 = vidx_bot[yy + 1, xx], vidx_bot[yy + 1, xx + 1]
        faces += [(t0, t1, b1), (t0, b1, b0)]

mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
mesh.remove_unreferenced_vertices()
# garante exatamente 90 mm de largura (a simetrização pode aparar o bojo)
_w = mesh.bounds[1][0] - mesh.bounds[0][0]
mesh.apply_scale([TARGET_W / _w, TARGET_W / _w, 1.0])
mesh.export(os.path.join(OUT, "orion_poker_relevo_9cm.stl"))
mb = mesh.bounds
print(f"malha: {len(mesh.faces)} tris | watertight={mesh.is_watertight}")
print(f"footprint: {mb[1][0] - mb[0][0]:.1f} x {mb[1][1] - mb[0][1]:.1f} mm | altura: {mb[1][2] - mb[0][2]:.1f} mm")

# ---------------------------------------------------------------- preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

hm = np.where(inside, height, np.nan)
ls_ = LightSource(azdeg=315, altdeg=55)
shaded = ls_.shade(np.nan_to_num(hm, nan=BASE_Z - 1), cmap=plt.cm.copper, vert_exag=3.0, blend_mode="overlay")
shaded[~inside] = [0.07, 0.07, 0.07, 1.0]
fig, ax = plt.subplots(figsize=(9, 7), facecolor="#111")
ax.imshow(shaded, origin="lower", extent=[gx[0], gx[-1], gy[0], gy[-1]])
ax.set_aspect("equal")
ax.axis("off")
fig.savefig(os.path.join(OUT, "heightmap_preview.png"), dpi=150, bbox_inches="tight", facecolor="#111")
print("OK ->", OUT)
