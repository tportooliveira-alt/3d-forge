#!/usr/bin/env python3
"""
Converte o GLB do bulldog (gerado no Higgsfield/Meshy) para formatos de
impressão: STL, 3MF, OBJ e PLY, escalando para o tamanho desejado.

Uso:  python3 convert_glb.py <arquivo.glb> [comprimento_mm]
      (comprimento padrão: 100 mm da frente à traseira)
"""

import os
import sys

import numpy as np
import trimesh

if len(sys.argv) < 2:
    sys.exit("uso: python3 convert_glb.py <arquivo.glb> [comprimento_mm]")

SRC = sys.argv[1]
TARGET_LEN = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)

scene = trimesh.load(SRC)
mesh = scene.to_mesh() if isinstance(scene, trimesh.Scene) else scene
mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces, process=True)

# orienta: maior dimensão = comprimento; assenta no chão (z=0)
ext = mesh.extents
scale = TARGET_LEN / ext.max()
mesh.apply_scale(scale)
mesh.apply_translation([0, 0, -mesh.bounds[0][2]])

# limpeza básica
mesh.remove_degenerate_faces()
mesh.remove_duplicate_faces()
mesh.remove_unreferenced_vertices()
trimesh.repair.fix_normals(mesh)
if not mesh.is_watertight:
    trimesh.repair.fill_holes(mesh)

b = mesh.bounds
print(f"malha: {len(mesh.faces)} tris | watertight={mesh.is_watertight}")
print(f"dimensões: {b[1][0]-b[0][0]:.1f} x {b[1][1]-b[0][1]:.1f} x {b[1][2]-b[0][2]:.1f} mm")

for ext_name in ("stl", "obj", "ply"):
    p = os.path.join(OUT, f"bulldog.{ext_name}")
    mesh.export(p)
    print("->", p)

# 3MF simples (um objeto)
import zipfile


def write_3mf(path, m):
    vs = "".join(f'<vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}" />' for v in m.vertices)
    ts = "".join(f'<triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" />' for f in m.faces)
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources><object id="2" type="model" name="bulldog">'
        f"<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>"
        '</resources><build><item objectid="2" /></build></model>'
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


write_3mf(os.path.join(OUT, "bulldog.3mf"), mesh)
print("->", os.path.join(OUT, "bulldog.3mf"))
