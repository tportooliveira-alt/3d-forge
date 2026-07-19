#!/usr/bin/env python3
"""
BULLDOG 3D — reconstrução LOCAL por visual hull a partir das 4 fotos.

Sem serviços externos: as silhuetas das 4 vistas (frente, traseira e os dois
perfis) esculpem um volume de voxels; marching cubes + suavização geram a
malha; as cores das próprias fotos são projetadas nos vértices.

Eixos: X = comprimento (focinho +X), Y = largura, Z = altura.

Saídas (em ./output_local):
  - bulldog_local_cores.ply    -> cor por vértice (cor total)
  - bulldog_local_cores.3mf    -> cores quantizadas em N grupos (Bambu + AMS)
  - stl_cores/<cor>.stl        -> 1 STL por grupo de cor
  - bulldog_local.stl          -> malha sem cor
  - preview.png                -> 3 vistas coloridas da malha

Uso:  python3 build_bulldog_local.py [comprimento_mm] [n_cores]
"""

import os
import sys
import zipfile

import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_local")
os.makedirs(os.path.join(OUT, "stl_cores"), exist_ok=True)

TARGET_LEN = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
N_COLORS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
VOX = 0.6                                   # tamanho do voxel (mm)


# ---------------------------------------------------------------- segmentação
def segment(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(float)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    core = (lum < 112) | ((b < r * 0.55) & (r > 85))
    core = ndimage.binary_opening(core, iterations=2)
    lbl, nl = ndimage.label(core)
    if nl > 1:
        core = lbl == (np.bincount(lbl.ravel())[1:].argmax() + 1)
    # brancos do peito/patas: claros, pequenos, que não tocam a borda
    bright = lum > 128
    lblb, nb = ndimage.label(bright)
    core_dil = ndimage.binary_dilation(core, iterations=6)
    keep = np.zeros_like(bright)
    for k in range(1, nb + 1):
        comp = lblb == k
        if comp[0, :].any() or comp[-1, :].any() or comp[:, 0].any() or comp[:, -1].any():
            continue
        if comp.sum() > 0.06 * bright.size:
            continue
        if (comp & core_dil).sum() > 30:
            keep |= comp
    # preenchimento por coluna: recupera o peito entre cabeça e barriga
    filled = np.zeros_like(core)
    for col in range(core.shape[1]):
        idx = np.nonzero(core[:, col])[0]
        if len(idx) >= 2:
            filled[idx[0]:idx[-1] + 1, col] = True
    mask = core | keep | (bright & filled)
    mask = ndimage.binary_closing(mask, iterations=8)
    mask = ndimage.binary_fill_holes(mask)
    mask = ndimage.binary_opening(mask, iterations=2)
    lbl, nl = ndimage.label(mask)
    if nl > 1:
        mask = lbl == (np.bincount(lbl.ravel())[1:].argmax() + 1)
    return np.asarray(im), mask


def bbox(m):
    ys, xs = np.nonzero(m)
    return xs.min(), xs.max(), ys.min(), ys.max()


print("segmentando as 4 vistas...")
img_f, m_f = segment(os.path.join(HERE, "views/dog_frente.jpg"))
img_t, m_t = segment(os.path.join(HERE, "views/dog_tras.jpg"))
img_d, m_d = segment(os.path.join(HERE, "views/dog_perfil_dir.jpg"))
img_e, m_e = segment(os.path.join(HERE, "views/dog_perfil_esq.jpg"))

# traseira espelhada para alinhar com a frente (esquerda da foto = direita do cão)
img_t, m_t = img_t[:, ::-1], m_t[:, ::-1]
# perfil esquerdo espelhado para focinho no mesmo lado do direito
img_e, m_e = img_e[:, ::-1], m_e[:, ::-1]

# proporções reais a partir das silhuetas
dx0, dx1, dy0, dy1 = bbox(m_d)
L_over_H = (dx1 - dx0) / (dy1 - dy0)
fx0, fx1, fy0, fy1 = bbox(m_f)
W_over_H = (fx1 - fx0) / (fy1 - fy0)

L = TARGET_LEN
H = L / L_over_H
W = H * W_over_H
print(f"dimensões do cão: {L:.0f} x {W:.0f} x {H:.0f} mm (C x L x A)")

nx, ny, nz = int(L / VOX), int(W / VOX), int(H / VOX)
print(f"voxels: {nx} x {ny} x {nz}")


def sample_mask(mask, u, v):
    """u, v em [0,1] dentro do bbox da máscara -> bool."""
    x0, x1, y0, y1 = bbox(mask)
    px = (x0 + u * (x1 - x0)).astype(int)
    py = (y0 + v * (y1 - y0)).astype(int)
    return mask[np.clip(py, 0, mask.shape[0] - 1), np.clip(px, 0, mask.shape[1] - 1)]


# grades normalizadas (u ao longo do eixo da imagem, v = de cima para baixo)
gx = (np.arange(nx) + 0.5) / nx             # comprimento: 0 = focinho
gy = (np.arange(ny) + 0.5) / ny             # largura: 0 = lado direito do cão
gz = (np.arange(nz) + 0.5) / nz             # altura: 0 = chão

X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
V = 1.0 - Z                                  # v da imagem: topo = 0

# a escultura usa as 2 vistas mais limpas (a pose muda entre fotos, então
# cruzar as 4 silhuetas corta as patas); as 4 fotos entram nas CORES
side = sample_mask(m_d, X.ravel(), V.ravel()).reshape(X.shape)
front = sample_mask(m_f, Y.ravel(), V.ravel()).reshape(X.shape)

vol = side & front
vol = ndimage.binary_opening(vol, iterations=1)
lbl, nl = ndimage.label(vol)
if nl > 1:
    vol = lbl == (np.bincount(lbl.ravel())[1:].argmax() + 1)
print(f"voxels ocupados: {vol.sum():,}")

# ---------------------------------------------------------------- malha
pad = np.pad(vol, 2)
verts, faces, _, _ = measure.marching_cubes(pad.astype(np.uint8), level=0.5)
verts = (verts - 2) * VOX                    # para mm
mesh = trimesh.Trimesh(vertices=verts[:, [0, 1, 2]], faces=faces, process=True)
trimesh.smoothing.filter_mut_dif_laplacian(mesh, iterations=12)
mesh.remove_unreferenced_vertices()
print(f"malha: {len(mesh.faces)} tris | watertight={mesh.is_watertight}")

# ---------------------------------------------------------------- cores
def sample_color(img, mask, u, v):
    """Cor da foto em (u,v) do bbox; se cair fora da máscara, usa o pixel
    válido mais próximo (evita pegar fundo)."""
    x0, x1, y0, y1 = bbox(mask)
    px = np.clip((x0 + u * (x1 - x0)).astype(int), 0, mask.shape[1] - 1)
    py = np.clip((y0 + v * (y1 - y0)).astype(int), 0, mask.shape[0] - 1)
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    py2, px2 = iy[py, px], ix[py, px]
    return img[py2, px2]


nrm = mesh.vertex_normals
u_len = mesh.vertices[:, 0] / (nx * VOX)
u_wid = mesh.vertices[:, 1] / (ny * VOX)
v_img = 1.0 - mesh.vertices[:, 2] / (nz * VOX)

c_d = sample_color(img_d, m_d, u_len, v_img)
c_e = sample_color(img_e, m_e, u_len, v_img)
c_f = sample_color(img_f, m_f, u_wid, v_img)
c_t = sample_color(img_t, m_t, u_wid, v_img)

vcol = np.zeros((len(mesh.vertices), 3))
ax_dom = np.argmax(np.abs(nrm), axis=1)
sel_side = ax_dom == 1
vcol[sel_side & (nrm[:, 1] < 0)] = c_d[sel_side & (nrm[:, 1] < 0)]
vcol[sel_side & (nrm[:, 1] >= 0)] = c_e[sel_side & (nrm[:, 1] >= 0)]
sel_len = ax_dom == 0
vcol[sel_len & (nrm[:, 0] < 0)] = c_f[sel_len & (nrm[:, 0] < 0)]
vcol[sel_len & (nrm[:, 0] >= 0)] = c_t[sel_len & (nrm[:, 0] >= 0)]
sel_top = ax_dom == 2
vcol[sel_top] = (c_d[sel_top].astype(float) + c_e[sel_top]) / 2

# ---------------------------------------------------------------- exportações
mesh.export(os.path.join(OUT, "bulldog_local.stl"))

ply = mesh.copy()
ply.visual = trimesh.visual.ColorVisuals(
    ply, vertex_colors=np.c_[vcol, np.full(len(vcol), 255)].astype(np.uint8)
)
ply.export(os.path.join(OUT, "bulldog_local_cores.ply"))

fcolors = vcol[mesh.faces].mean(axis=1)
from scipy.cluster.vq import kmeans2

centroids, labels = kmeans2(fcolors, N_COLORS, minit="++", seed=42)
parts = []
for k in range(N_COLORS):
    fsel = np.nonzero(labels == k)[0]
    if len(fsel) < 20:
        continue
    sub = mesh.submesh([fsel], append=True)
    c = tuple(int(x) for x in np.clip(centroids[k], 0, 255))
    name = f"cor_{k+1}_{c[0]:02x}{c[1]:02x}{c[2]:02x}"
    parts.append((name, sub, c))
    sub.export(os.path.join(OUT, "stl_cores", f"{name}.stl"))


def write_3mf(path, items):
    def hexc(c):
        return "#%02X%02X%02X" % c[:3]

    objs, build = [], []
    mats = "".join(f'<base name="{n}" displaycolor="{hexc(c)}" />' for n, _, c in items)
    for i, (n, m, _c) in enumerate(items):
        vs = "".join(f'<vertex x="{v[0]:.3f}" y="{v[1]:.3f}" z="{v[2]:.3f}" />' for v in m.vertices)
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


write_3mf(os.path.join(OUT, "bulldog_local_cores.3mf"), parts)
print(f"3MF: {len(parts)} grupos de cor")

# ---------------------------------------------------------------- preview
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor="#181818")
vp = mesh.vertices
cp = vcol / 255.0
for ax, (a_, b_), title in [
    (axes[0], (0, 2), "perfil"),
    (axes[1], (1, 2), "frente"),
    (axes[2], (0, 1), "de cima"),
]:
    depth_axis = 3 - a_ - b_
    order = np.argsort(vp[:, depth_axis])
    ax.scatter(vp[order, a_], vp[order, b_], c=cp[order], s=1.2, linewidths=0)
    ax.set_aspect("equal")
    ax.set_title(title, color="w", fontsize=10)
    ax.axis("off")
plt.tight_layout()
fig.savefig(os.path.join(OUT, "preview.png"), dpi=130, facecolor="#181818")
print("OK ->", OUT)
