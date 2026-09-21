"""QA das malhas antes de exportar. Falha o build se algo nao for imprimivel."""

from __future__ import annotations

from dataclasses import dataclass

import trimesh
from shapely.ops import unary_union

from .build import Slab
from .params import Params


@dataclass
class Report:
    errors: list[str]
    warnings: list[str]
    rows: list[tuple[str, bool, float, tuple[float, float, float], int]]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_meshes(meshes: dict[str, trimesh.Trimesh], p: Params) -> Report:
    errors: list[str] = []
    warnings: list[str] = []
    rows = []
    for name, m in sorted(meshes.items()):
        ext = tuple(float(v) for v in m.extents)
        rows.append((name, bool(m.is_watertight), float(m.volume), ext,
                     int(len(m.faces))))
        if not m.is_watertight:
            errors.append(f"{name}: malha nao e watertight")
        if m.volume <= 0:
            errors.append(f"{name}: volume nao positivo ({m.volume:.3f})")
        zmax = float(m.bounds[1][2])
        if zmax > p.total_height + 1e-6:
            errors.append(f"{name}: topo em z={zmax:.3f} acima do esperado "
                          f"({p.total_height:.3f})")
        if float(m.bounds[0][2]) < -1e-6:
            errors.append(f"{name}: geometria abaixo de z=0")
    return Report(errors, warnings, rows)


def check_no_overlap(slabs: dict[str, list[Slab]], tol: float = 1e-6) -> list[str]:
    """Verifica em 2D que cores diferentes nao se sobrepoem em Z.

    Feito em 2D de proposito: booleano 3D entre malhas e caro e nada confiavel
    para detectar interpenetracao. Aqui basta, para cada par de camadas cujas
    faixas de Z se cruzam, medir a area de intersecao dos poligonos.
    """
    errors: list[str] = []
    flat = [(c, s) for c, items in slabs.items() for s in items]
    for i in range(len(flat)):
        ci, si = flat[i]
        for j in range(i + 1, len(flat)):
            cj, sj = flat[j]
            if ci == cj:
                continue
            lo, hi = max(si.z0, sj.z0), min(si.z1, sj.z1)
            if hi - lo <= tol:          # faixas de Z nao se cruzam
                continue
            if si.geom.is_empty or sj.geom.is_empty:
                continue
            a = si.geom.intersection(sj.geom).area
            if a > 1e-3:
                errors.append(
                    f"sobreposicao {ci} x {cj}: {a:.4f} mm^2 "
                    f"na faixa z {lo:.2f}-{hi:.2f}")
    return errors


def check_printability(slabs: dict[str, list[Slab]], p: Params) -> list[str]:
    warnings: list[str] = []
    if p.art_h < 2 * p.layer_height:
        warnings.append(
            f"relevo da arte ({p.art_h}mm) tem menos de 2 camadas de "
            f"{p.layer_height}mm")
    # Detalhe mais fino que o bico: uma erosao de min_feature/2 nao pode zerar
    # uma cor inteira.
    for color, items in slabs.items():
        geom = unary_union([s.geom for s in items if not s.geom.is_empty])
        if geom.is_empty:
            continue
        eroded = geom.buffer(-p.min_feature / 2.0, quad_segs=8)
        if eroded.is_empty:
            warnings.append(
                f"{color}: toda a geometria e mais fina que {p.min_feature}mm")
        elif eroded.area < geom.area * 0.25:
            warnings.append(
                f"{color}: {100 * (1 - eroded.area / geom.area):.0f}% da area "
                f"esta perto do limite de {p.min_feature}mm")
    return warnings


def full_check(meshes: dict[str, trimesh.Trimesh], slabs: dict[str, list[Slab]],
               p: Params) -> Report:
    rep = check_meshes(meshes, p)
    rep.errors.extend(check_no_overlap(slabs))
    rep.warnings.extend(check_printability(slabs, p))
    return rep


# ---------------------------------------------------------------------------
# Prontidao para o fatiador
# ---------------------------------------------------------------------------
def check_slicer_ready(meshes: dict[str, trimesh.Trimesh]) -> tuple[list[str], list[str]]:
    """Checagens que decidem se o arquivo entra limpo num fatiador.

    Sao caras (booleano 3D par a par), por isso ficam separadas do QA rapido.
    """
    import numpy as np

    errors: list[str] = []
    notes: list[str] = []

    for name, m in sorted(meshes.items()):
        if not m.is_volume:
            errors.append(f"{name}: nao e um solido fechado (is_volume=False)")
        if not m.is_winding_consistent:
            errors.append(f"{name}: orientacao das faces inconsistente")
        if m.volume <= 0:
            errors.append(f"{name}: volume nao positivo -> normais invertidas")
        if (m.area_faces < 1e-12).any():
            errors.append(f"{name}: tem faces degeneradas (area zero)")

    # Interseccao 3D real entre cores. O QA rapido ja checa em 2D faixa a faixa;
    # aqui e o teste definitivo, que o fatiador faria ao fundir as partes.
    names = sorted(meshes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ma, mb = meshes[a], meshes[b]
            if (ma.bounds[0] > mb.bounds[1]).any() or (mb.bounds[0] > ma.bounds[1]).any():
                continue
            try:
                inter = trimesh.boolean.intersection([ma, mb], engine="manifold")
            except Exception as exc:
                errors.append(f"booleano {a} x {b} falhou: {exc}")
                continue
            vol = abs(inter.volume) if inter is not None and len(inter.faces) else 0.0
            if vol > 1e-4:
                errors.append(f"{a} x {b} se interpenetram em {vol:.4f} mm3")

    # Uniao == soma dos volumes: se bater, nao ha vao nem sobreposicao em lugar
    # nenhum. E o teste mais forte do conjunto, numa linha so.
    try:
        union = trimesh.boolean.union(list(meshes.values()), engine="manifold")
        total = sum(m.volume for m in meshes.values())
        diff = union.volume - total
        if abs(diff) > 1e-3:
            errors.append(f"uniao {union.volume:.3f} != soma {total:.3f} "
                          f"(diferenca {diff:+.4f} mm3: ha vao ou sobreposicao)")
        if not union.is_watertight:
            errors.append("a peca montada nao e watertight")
        notes.append(f"peca montada: {union.volume:.1f} mm3, "
                     f"{len(union.faces)} faces, watertight={union.is_watertight}")
    except Exception as exc:
        errors.append(f"uniao falhou: {exc}")
        union = None

    # Nada pode flutuar: cada ilha de arte precisa de material logo abaixo.
    base = max(meshes.values(), key=lambda m: m.volume)
    for name, m in sorted(meshes.items()):
        if m is base:
            continue
        for body in m.split(only_watertight=False):
            z0 = float(body.bounds[0][2])
            if z0 <= 1e-6:
                continue                      # ja nasce na mesa
            probe = np.array([[body.centroid[0], body.centroid[1], z0 * 0.5]])
            if not bool(base.contains(probe)[0]):
                errors.append(f"{name}: ilha em ({probe[0][0]:+.2f},{probe[0][1]:+.2f}) "
                              f"comeca em z={z0:.2f} sem material abaixo")
    return errors, notes
