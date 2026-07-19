#!/usr/bin/env python3
"""
Converte o GLB texturizado do bulldog em 3 FORMATOS QUE GUARDAM AS CORES:

  1. bulldog_cores.3mf   -> 3MF multicolor QUANTIZADO (para Bambu Studio + AMS):
                            as cores da textura viram N grupos de cor, cada um
                            um objeto separado — é só atribuir um filamento a
                            cada grupo e imprimir colorido em FDM.
                            (+ 1 STL por cor em stl_cores/ como alternativa)
  2. bulldog_textura.obj -> OBJ + MTL + PNG da textura (cor TOTAL, formato
                            aceito por serviços de impressão full-color como
                            JLC3DP/Craftcloud e por qualquer visualizador)
  3. bulldog_cores.ply   -> PLY com cor por vértice (cor total embutida em um
                            arquivo só; aceito por serviços full-color)

Uso:  python3 convert_glb_cores.py <arquivo.glb> [comprimento_mm] [n_cores]
      padrão: 100 mm de comprimento, 6 cores no 3MF
"""

import os
import sys
import zipfile

import numpy as np
import trimesh

if len(sys.argv) < 2:
    sys.exit("uso: python3 convert_glb_cores.py <arquivo.glb> [comprimento_mm] [n_cores]")

SRC = sys.argv[1]
TARGET_LEN = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
N_COLORS = int(sys.argv[3]) if len(sys.argv) > 3 else 6

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_cores")
os.makedirs(os.path.join(OUT, "stl_cores"), exist_ok=True)

# ---------------------------------------------------------------- carrega GLB
loaded = trimesh.load(SRC)
if isinstance(loaded, trimesh.Scene):
    meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
    mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
else:
    mesh = loaded

# textura -> cor por vértice (mantém a pintura original do modelo)
try:
    color_visual = mesh.visual.to_color()
    vcolors = np.asarray(color_visual.vertex_colors)[:, :3].astype(float)
except Exception:
    vcolors = np.full((len(mesh.vertices), 3), 180.0)
    print("aviso: sem textura — usando cor neutra")

# escala para o tamanho alvo e assenta no chão
scale = TARGET_LEN / mesh.extents.max()
mesh.apply_scale(scale)
mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
b = mesh.bounds
print(f"malha: {len(mesh.faces)} tris | {b[1][0]-b[0][0]:.0f} x {b[1][1]-b[0][1]:.0f} x {b[1][2]-b[0][2]:.0f} mm")

# ---------------------------------------------------------------- 1) OBJ + MTL + textura (cor total)
obj_path = os.path.join(OUT, "bulldog_textura.obj")
try:
    mesh.export(obj_path, include_texture=True)
except TypeError:
    mesh.export(obj_path)
print("->", obj_path, "(+ .mtl/.png da textura, se houver)")

# ---------------------------------------------------------------- 2) PLY com cor por vértice (cor total)
ply = mesh.copy()
ply.visual = trimesh.visual.ColorVisuals(
    ply, vertex_colors=np.c_[vcolors, np.full(len(vcolors), 255)].astype(np.uint8)
)
ply_path = os.path.join(OUT, "bulldog_cores.ply")
ply.export(ply_path)
print("->", ply_path)

# ---------------------------------------------------------------- 3) 3MF quantizado (Bambu + AMS)
# cor média por face -> k-means em N_COLORS grupos -> um objeto por cor
fcolors = vcolors[mesh.faces].mean(axis=1)
from scipy.cluster.vq import kmeans2

centroids, labels = kmeans2(fcolors, N_COLORS, minit="++", seed=42)
parts = []
for k in range(N_COLORS):
    fsel = np.nonzero(labels == k)[0]
    if len(fsel) < 10:
        continue
    sub = mesh.submesh([fsel], append=True)
    c = tuple(int(x) for x in np.clip(centroids[k], 0, 255))
    name = f"cor_{k+1}_{c[0]:02x}{c[1]:02x}{c[2]:02x}"
    parts.append((name, sub, c))
    sub.export(os.path.join(OUT, "stl_cores", f"{name}.stl"))
print(f"3MF: {len(parts)} grupos de cor")


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


mmf_path = os.path.join(OUT, "bulldog_cores.3mf")
write_3mf(mmf_path, parts)
print("->", mmf_path)
print("\nOK! Formatos com cor prontos em", OUT)
