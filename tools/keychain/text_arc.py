"""Texto curvo "MULHERES NO TATAME" a partir de uma fonte real.

Porque gerar de fonte e nao tracar da imagem: a maiuscula tem ~3mm, que no render
de referencia da ~29px. Tracar isso produz contornos serrilhados e ilegiveis
depois da limpeza para impressao. Gerando de fonte, as curvas sao exatas.

Cada glifo recebe uma transformacao RIGIDA (rotacao tangencial + translacao),
nunca uma deformacao -- as letras nao ficam esticadas ao seguir a curva.
"""

from __future__ import annotations

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.affinity import affine_transform, scale
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from .params import Params
from .trace import as_multipolygon


# Tamanho em que os glifos sao gerados antes de escalar para mm. Grande o
# bastante para que a discretizacao das curvas da fonte nao apareca.
_GEN_SIZE = 100.0


def _rings_to_polygons(rings: list[np.ndarray]) -> MultiPolygon:
    """Resolve quais aneis sao contorno externo e quais sao buraco.

    TextPath.to_polygons devolve uma lista plana de aneis sem dizer o que e
    buraco (o 'O' de "NO" vem como dois aneis). Classifico por containment:
    um anel contido num numero IMPAR de outros e buraco.
    """
    polys = [Polygon(r) for r in rings if len(r) >= 4]
    polys = [q if q.is_valid else q.buffer(0) for q in polys]
    polys = [q for q in polys if not q.is_empty and q.area > 0]
    if not polys:
        return MultiPolygon()

    # Classificacao por containment de ANEL INTEIRO, e nao de ponto
    # representativo: o ponto representativo do anel externo de um "O" cai no
    # meio do vazio, ou seja, DENTRO do anel interno, e o "O" inteiro seria
    # classificado como buraco -- foi exatamente assim que O e A sumiram.
    # Aneis de glifo nunca se cruzam, entao containment total e inequivoco.
    order = sorted(range(len(polys)), key=lambda i: -polys[i].area)
    depth = [0] * len(polys)
    for pos, i in enumerate(order):
        depth[i] = sum(1 for j in order[:pos] if polys[j].contains(polys[i]))

    shells = [q for q, d in zip(polys, depth) if d % 2 == 0]
    holes = [q for q, d in zip(polys, depth) if d % 2 == 1]
    if not shells:
        return MultiPolygon()

    geom = unary_union(shells)
    if holes:
        geom = geom.difference(unary_union(holes))
    return as_multipolygon(geom)


def glyph_polygons(char: str, font: FontProperties) -> tuple[MultiPolygon, float]:
    """Contornos de um glifo (normalizados para altura de maiuscula 1.0) e avanco.

    A altura de maiuscula e medida no proprio "H" da fonte, e nao em `size`, que
    se refere ao corpo (em) e incluiria ascendentes/descendentes.
    """
    # O espaco nao tem contorno; matplotlib quebra ao construir o Path vazio.
    if char.isspace():
        geom = MultiPolygon()
    else:
        tp = TextPath((0, 0), char, size=_GEN_SIZE, prop=font)
        geom = _rings_to_polygons(
            [np.asarray(r) for r in tp.to_polygons(closed_only=True)])
    # Avanco: largura ate o proximo caractere, medindo "char + H" menos "H".
    # Precisa do sufixo justamente para que o espaco tenha avanco nao nulo.
    advance = TextPath((0, 0), char + "H", size=_GEN_SIZE, prop=font).get_extents().x1 \
        - TextPath((0, 0), "H", size=_GEN_SIZE, prop=font).get_extents().x1
    return geom, float(advance)


def _cap_height(font: FontProperties) -> float:
    return float(TextPath((0, 0), "H", size=_GEN_SIZE, prop=font).get_extents().height)


def layout_on_arc(p: Params) -> MultiPolygon:
    """Dispoe o texto ao longo do arco inferior, com as letras em pe.

    Convencao do arco INFERIOR: para o texto ser lido normalmente, o topo das
    letras aponta para o CENTRO. Logo a linha de base fica no raio externo
    (text_baseline_radius) e as maiusculas crescem para DENTRO. Foi isso que a
    medicao do render mostrou: a banda branca do texto vai de r=13.0 a r=16.1mm,
    com a base em 16.1 e os topos em 13.05.

    Cada glifo sofre so rotacao + translacao; nada de deformar para seguir a
    curva. No ponto mais baixo do circulo a transformacao e a identidade.
    """
    font = FontProperties(fname=p.font_path)
    cap = _cap_height(font)
    if cap <= 0:
        raise RuntimeError(f"nao consegui medir a altura de maiuscula em {p.font_path}")

    # Altura de maiuscula -> text_cap_height (mm). X leva ainda a compressao
    # horizontal, para imitar a condensada do desenho original.
    sy = p.text_cap_height / cap
    sx = sy * p.text_xscale

    glyphs: list[tuple[MultiPolygon, float]] = []
    total = 0.0
    for ch in p.text:
        geom, adv = glyph_polygons(ch, font)
        w = adv * sx * p.text_tracking
        glyphs.append((geom, w))
        total += w

    r = p.text_baseline_radius
    cursor = -total / 2.0   # texto centrado na base do circulo

    placed: list[MultiPolygon] = []
    for geom, w in glyphs:
        if not geom.is_empty:
            s_arc = cursor + w / 2.0
            # s cresce para a direita => theta cresce a partir de -90 graus
            theta = -np.pi / 2.0 + s_arc / r
            ux, uy = np.cos(theta), np.sin(theta)      # radial para FORA
            # X local -> tangente (-uy, ux); Y local -> radial para DENTRO
            a, b = -uy, -ux
            d, e = ux, -uy
            g = scale(geom, xfact=sx, yfact=sy, origin=(0, 0))
            gx = (g.bounds[0] + g.bounds[2]) / 2.0     # centra o glifo no avanco
            off_x = ux * r - a * gx
            off_y = uy * r - d * gx
            # shapely: [a, b, d, e, xoff, yoff] com x' = a*x + b*y + xoff
            placed.append(affine_transform(g, [a, b, d, e, off_x, off_y]))
        cursor += w

    if not placed:
        return MultiPolygon()
    return as_multipolygon(unary_union(placed))
