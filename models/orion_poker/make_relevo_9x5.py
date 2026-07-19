#!/usr/bin/env python3
"""Gera a variante 9 x 5 cm EXATA da placa em relevo (compressão vertical leve).

Parte do STL fiel gerado por build_orion_relief_9cm.py (90 x ~72 mm) e ajusta a
altura para exatamente 50 mm, mantendo 90 mm de largura e 10 mm de espessura.

Uso:  python3 make_relevo_9x5.py
"""

import os

import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "output_relevo", "orion_poker_relevo_9cm.stl")
DST = os.path.join(HERE, "output_relevo", "orion_poker_relevo_9x5.stl")

mesh = trimesh.load(SRC)
b = mesh.bounds
w, h = b[1][0] - b[0][0], b[1][1] - b[0][1]
mesh.apply_scale([90.0 / w, 50.0 / h, 1.0])
mesh.export(DST)
nb = mesh.bounds
print(f"OK: {nb[1][0]-nb[0][0]:.1f} x {nb[1][1]-nb[0][1]:.1f} x {nb[1][2]-nb[0][2]:.1f} mm | watertight={mesh.is_watertight}")
