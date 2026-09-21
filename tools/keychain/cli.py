"""Gerador de STLs do chaveiro "AM Mulheres no Tatame".

Uso tipico:
    tools/keychain/.venv/bin/python -m tools.keychain.cli --variant both --preview
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build
from .params import Params
from .preview import render
from .validate import full_check

DEFAULT_IMAGE = "tools/keychain/assets/ref_render.jpg"
DEFAULT_OUT = "tools/keychain/out"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="tools.keychain.cli",
        description="Gera STLs multi-peca do chaveiro a partir do render de referencia.")
    ap.add_argument("--variant", choices=["mmu", "glue", "both"], default="both",
                    help="mmu = um STL por cor (AMS/MMU); "
                         "glue = base com bolsos + insertos colados")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help="render de referencia")
    ap.add_argument("--out", default=DEFAULT_OUT, help="diretorio de saida")
    ap.add_argument("--preview", action="store_true", help="gera PNG de conferencia")

    g = ap.add_argument_group("geometria (mm)")
    g.add_argument("--diameter", type=float)
    g.add_argument("--hole-diameter", type=float, dest="hole_diameter")
    g.add_argument("--art-h", type=float, dest="art_h")
    g.add_argument("--base-h", type=float, dest="base_h")

    t = ap.add_argument_group("texto")
    t.add_argument("--text")
    t.add_argument("--text-cap-height", type=float, dest="text_cap_height")
    t.add_argument("--text-xscale", type=float, dest="text_xscale")
    t.add_argument("--text-tracking", type=float, dest="text_tracking")

    pr = ap.add_argument_group("impressao")
    pr.add_argument("--colors", type=int, choices=[4, 5], dest="n_colors",
                    help="5 = paleta cheia; 4 funde o cabelo no roxo (AMS de 4 slots)")
    pr.add_argument("--clearance", type=float)
    pr.add_argument("--pocket-depth", type=float, dest="pocket_depth")
    pr.add_argument("--min-feature", type=float, dest="min_feature")
    pr.add_argument("--layer-height", type=float, dest="layer_height")
    pr.add_argument("--trace-tolerance", type=float, dest="trace_tolerance")
    return ap.parse_args(argv)


def run_variant(p: Params, image: str, variant: str, out: Path,
                want_preview: bool) -> bool:
    print(f"\n=== variante: {variant} ===")
    meshes, slabs = build(p, image, variant)
    rep = full_check(meshes, slabs, p)

    print(f"{'peca':<16}{'watertight':>11}{'volume mm3':>13}"
          f"{'bbox X x Y x Z (mm)':>28}{'tri':>9}")
    for name, wt, vol, ext, nf in rep.rows:
        print(f"{name:<16}{'sim' if wt else 'NAO':>11}{vol:>13.1f}"
              f"{ext[0]:>10.2f} x{ext[1]:>6.2f} x{ext[2]:>5.2f}{nf:>9}")

    for w in rep.warnings:
        print(f"  aviso: {w}")
    for e in rep.errors:
        print(f"  ERRO:  {e}")

    if want_preview:
        png = out / f"preview_{variant}.png"
        render(slabs, p, str(png), title=f"{variant} - vista de topo")
        print(f"  preview: {png}")

    if not rep.ok:
        print(f"  -> STLs NAO exportados (variante {variant} reprovada no QA)")
        return False

    for name, mesh in sorted(meshes.items()):
        path = out / f"{variant}_{name}.stl"
        mesh.export(str(path))
        print(f"  gravado: {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    overrides = {k: v for k, v in vars(args).items()
                 if k not in {"variant", "image", "out", "preview"}}
    p = Params().with_overrides(**overrides)

    print(f"Q{p.diameter:.1f}mm | furo Q{p.hole_diameter:.1f}mm | "
          f"espessura {p.total_height:.2f}mm | altura total {p.overall_height:.1f}mm | "
          f"{p.n_colors} cores")

    variants = ["mmu", "glue"] if args.variant == "both" else [args.variant]
    ok = all([run_variant(p, args.image, v, out, args.preview) for v in variants])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
