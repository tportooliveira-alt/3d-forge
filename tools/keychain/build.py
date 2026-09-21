"""Montagem das camadas 2D e extrusao para malhas.

Estrategia: a peca e puramente 2.5D (costas planas, relevo so na frente), entao
TODO booleano acontece em 2D com shapely e so no fim cada poligono e extrudado
para a sua faixa de Z. Isso evita CSG 3D -- que e a parte fragil de qualquer
pipeline de malha -- e o resultado sai watertight por construcao.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from .params import GLUE_BASE_ABSORBS, GLUE_INSERTS, Params
from .text_arc import layout_on_arc
from .trace import _iter_polygons, as_multipolygon, trace_artwork


# Uma camada: poligono 2D + faixa de Z.
@dataclass(frozen=True)
class Slab:
    geom: MultiPolygon
    z0: float
    z1: float


def _circle(r: float, p: Params) -> Polygon:
    return Point(0, 0).buffer(r, quad_segs=max(4, p.arc_segments // 4))


def base_outline(p: Params) -> Polygon:
    """Contorno do disco + aba, ja com o furo da argola."""
    disc = _circle(p.radius, p)
    boss = Point(0, p.tab_hole_center_y).buffer(p.tab_boss_diameter / 2.0,
                                                quad_segs=p.arc_segments // 4)
    # Pescoco ligando a aba ao disco, para nao ficar so tangente.
    neck = box(-p.tab_width / 2.0, p.radius - p.tab_width / 2.0,
               p.tab_width / 2.0, p.tab_hole_center_y)
    solid = unary_union([disc, boss, neck])
    # Concordancia: fecha o angulo vivo do encontro aba/disco.
    solid = solid.buffer(p.tab_width * 0.18, quad_segs=24) \
                 .buffer(-p.tab_width * 0.18, quad_segs=24)
    solid = max(_iter_polygons(solid), key=lambda q: q.area)
    hole = Point(0, p.tab_hole_center_y).buffer(p.hole_radius,
                                                quad_segs=p.arc_segments // 4)
    return Polygon(solid.exterior, list(solid.interiors) + [hole.exterior])


def text_exclusion_zone(text: MultiPolygon, p: Params) -> MultiPolygon:
    """Regiao onde o texto do render original mora, a ser descartada no traçado.

    Duas partes somadas, porque nenhuma sozinha e confiavel:
      1. o proprio texto gerado, dilatado -- pega as letras onde o layout bate;
      2. a coroa circular no setor angular do texto -- pega o resto, caso o
         layout gerado esteja ligeiramente deslocado do render.
    A coroa comeca em r=12.4mm, folgadamente acima do alcance da figura (r<10.7)
    e do "M" no setor inferior, entao nao morde a arte.
    """
    if text.is_empty:
        return MultiPolygon()
    dilated = text.buffer(1.6, quad_segs=8)

    # Setor angular ocupado pelo texto, com 5 graus de folga de cada lado.
    angs = []
    for g in _iter_polygons(text):
        for x, y in g.exterior.coords:
            angs.append(np.arctan2(y, x))
    angs = np.unwrap(np.sort(np.array(angs)))
    a0, a1 = angs.min() - np.deg2rad(5), angs.max() + np.deg2rad(5)

    steps = max(24, int(np.degrees(a1 - a0)))
    th = np.linspace(a0, a1, steps)
    r_in, r_out = 12.4, p.field_radius + 0.5
    pts = [(r_out * np.cos(a), r_out * np.sin(a)) for a in th]
    pts += [(r_in * np.cos(a), r_in * np.sin(a)) for a in th[::-1]]
    wedge = Polygon(pts)

    return as_multipolygon(unary_union([dilated, wedge]))


def artwork(p: Params, image_path: str) -> dict[str, MultiPolygon]:
    """Arte vetorizada por cor: figura/M tracados + texto gerado de fonte."""
    text = layout_on_arc(p)
    art = trace_artwork(image_path, p, exclude=text_exclusion_zone(text, p))

    # As linhas pretas do desenho (separacao manga/tronco/perna, banda sob o
    # obi) tem ~0.3mm nesta escala -- mais finas do que um bico de 0.4mm
    # consegue imprimir. Engrossa-se so o que e fino, e o acrescimo e
    # descontado dos vizinhos para as cores seguirem sem sobreposicao.
    art["hair"] = _thicken_lines(art.get("hair", MultiPolygon()), p)
    black = art["hair"]
    if not black.is_empty:
        for k in ("white", "pink", "skin"):
            if k in art and not art[k].is_empty:
                art[k] = as_multipolygon(art[k].difference(black))

    # Folga entre a figura e as letras: sao a mesma cor, e encostando virariam
    # uma unica regiao no STL branco.
    gap = text.buffer(p.min_feature, quad_segs=8)
    if "white" in art and not art["white"].is_empty:
        art["white"] = as_multipolygon(art["white"].difference(gap))
    art["white"] = as_multipolygon(
        unary_union([art.get("white", MultiPolygon()), text]))

    # As placas elevadas sao recortadas na cor JA finalizada. Recortar antes
    # deixava um fio para fora -- o branco ainda perdia o preto e a folga do
    # texto depois -- e o QA de sobreposicao pegava, certeiro.
    for key, color in (("_raised_skin", "skin"), ("_raised_white", "white")):
        up = art.get(key)
        if up is None or up.is_empty or art.get(color, MultiPolygon()).is_empty:
            art[key] = MultiPolygon()
            continue
        art[key] = as_multipolygon(up.intersection(art[color]))
    return art


def _thicken_lines(black: MultiPolygon, p: Params) -> MultiPolygon:
    """Leva a largura minima imprimivel os pedacos de preto que sao finos.

    A decisao e por componente, nao por regiao: subtrair a abertura do proprio
    poligono marca como "fino" tambem a casca ondulada do contorno do cabelo, e
    dilatar aquilo transformava o cabelo numa fieira de bolhas. Se um
    componente inteiro some ao ser erodido em min_feature/2, ele e uma linha e
    cresce; se sobra miolo, e uma mancha e fica como esta.

    O crescimento e o minimo necessario: a largura caracteristica da fita e
    2*area/perimetro, e cresce-se so o que falta para chegar a min_feature. As
    linhas do desenho tem 0.19-0.33mm, abaixo do que um bico de 0.4mm imprime;
    ou elas engrossam, ou desaparecem da peca.
    """
    if black.is_empty:
        return black
    half = p.min_feature / 2.0
    out = []
    for q in _iter_polygons(black):
        if q.length <= 0 or not q.buffer(-half, quad_segs=8).is_empty:
            out.append(q)
            continue
        width = 2.0 * q.area / q.length
        grow = max(0.0, (p.min_feature - width) / 2.0)
        out.append(q.buffer(grow, quad_segs=12) if grow > 1e-4 else q)
    return as_multipolygon(unary_union(out))


# ---------------------------------------------------------------------------
# Variante A -- MMU/AMS: um solido por cor, no mesmo sistema de coordenadas
# ---------------------------------------------------------------------------
def build_slabs_mmu(p: Params, art: dict[str, MultiPolygon]) -> dict[str, list[Slab]]:
    outline = base_outline(p)
    field = _circle(p.field_radius, p)
    groove = _circle(p.groove_outer, p).difference(field)
    rim = _circle(p.radius, p).difference(_circle(p.groove_outer, p))

    # Com uma cor so nao ha por que recortar o campo: o relevo e a mesma peca.
    # E recortar seria ativamente ruim -- campo e relevo ficariam encostados em
    # paredes verticais, a uniao devolveria corpos separados, e ao RELER o
    # arquivo a solda de vertices criaria arestas com 4 faces. Deixando o campo
    # inteiro, cada platô se sobrepoe a ele de verdade e tudo funde num corpo.
    mono = len(p.color_groups) == 1
    if mono:
        field_purple = as_multipolygon(field)
    else:
        art_union = unary_union([g for k, g in art.items()
                                 if not k.startswith("_") and not g.is_empty])
        field_purple = as_multipolygon(field.difference(art_union))

    slabs: dict[str, list[Slab]] = {c: [] for c in p.color_groups}

    # Roxo: base (com a aba) + sulco + aro + o campo recortado pela arte.
    purple: list[Slab] = [
        Slab(as_multipolygon(outline), 0.0, p.z_base_top),
        Slab(as_multipolygon(groove), p.z_base_top, p.z_groove_top),
        Slab(as_multipolygon(rim), p.z_base_top, p.z_rim_top),
        Slab(field_purple, p.z_base_top, p.z_field_top),
    ]

    # Cada grupo tracado vira um pilar do topo da base ate a SUA altura. Com 5
    # filamentos todas as alturas sao iguais e o relevo e plano; com menos, os
    # grupos fundidos sobem alturas distintas, que e o que mantem o desenho
    # legivel quando a cor deixa de separa-los.
    levels = p.art_levels
    for color, groups in p.color_groups.items():
        for g in groups:
            if g == "purple" or g not in art or art[g].is_empty:
                continue
            geom = art[g]
            if mono:
                # Duas regioes de arte que se tocam em UM UNICO PONTO produzem
                # uma aresta vertical compartilhada por 4 faces -- a malha
                # parece fechada em memoria e volta aberta do arquivo. Com tudo
                # na mesma cor, basta um engorde imperceptivel (1/16 da largura
                # de extrusao) para elas se sobreporem em vez de se tocarem.
                geom = as_multipolygon(geom.buffer(0.01, quad_segs=4))
            z1 = p.z_field_top + levels.get(g, p.art_h)
            slabs[color].append(Slab(geom, p.z_base_top, z1))

    # As placas de cima sobem um degrau. Mesma cor, so mais altas: e assim que
    # o queixo ganha aresta em vez de se fundir com o pescoco, e que a manga
    # passa a ler como estando por cima do joelho.
    for key, group in (("_raised_skin", "skin"), ("_raised_white", "white")):
        up = art.get(key)
        if up is None or up.is_empty:
            continue
        color = next((c for c, gs in p.color_groups.items() if group in gs), None)
        if color is None or color not in slabs:
            continue
        z1 = p.z_field_top + levels.get(group, p.art_h) + p.face_lift
        slabs[color].append(Slab(up, p.z_base_top, z1))

    slabs["purple"] = purple + slabs.get("purple", [])
    return {c: s for c, s in slabs.items() if s}


# ---------------------------------------------------------------------------
# Variante B -- extrusora unica: base com bolsos + insertos colados
# ---------------------------------------------------------------------------
def build_slabs_glue(p: Params, art: dict[str, MultiPolygon]
                     ) -> tuple[dict[str, list[Slab]], MultiPolygon]:
    outline = base_outline(p)
    field = _circle(p.field_radius, p)
    groove = _circle(p.groove_outer, p).difference(field)
    rim = _circle(p.radius, p).difference(_circle(p.groove_outer, p))

    # So branco e rosa viram insertos. Pele e preto, nesta escala, sao cacos de
    # 1-3mm: imprimiveis num AMS, mas impossiveis de manusear e colar. Ficam em
    # relevo na propria base roxa.
    inserts = {c: art[c] for c in GLUE_INSERTS
               if c in art and not art[c].is_empty}   # "_*" nunca esta aqui
    absorbed = unary_union([art[c] for c in GLUE_BASE_ABSORBS
                            if c in art and not art[c].is_empty])

    pockets = as_multipolygon(unary_union(
        [g.buffer(p.clearance, quad_segs=8) for g in inserts.values()]
    ).intersection(field).difference(absorbed))

    z_pocket = p.z_field_top - p.pocket_depth
    field_top = as_multipolygon(field.difference(pockets).difference(absorbed))

    purple: list[Slab] = [
        Slab(as_multipolygon(outline), 0.0, p.z_base_top),
        Slab(as_multipolygon(groove), p.z_base_top, p.z_groove_top),
        Slab(as_multipolygon(rim), p.z_base_top, p.z_rim_top),
        # campo cheio ate o fundo do bolso; so acima disso ele e recortado
        Slab(as_multipolygon(field), p.z_base_top, z_pocket),
        Slab(field_top, z_pocket, p.z_field_top),
    ]
    if not absorbed.is_empty:
        purple.append(Slab(as_multipolygon(absorbed), p.z_base_top, p.z_art_top))
        up = art.get("_raised_skin")
        if up is not None and not up.is_empty:
            purple.append(Slab(up, p.z_base_top, p.z_face_top))

    slabs: dict[str, list[Slab]] = {"purple": purple}
    for color, geom in inserts.items():
        slabs[color] = [Slab(geom, z_pocket, p.z_art_top)]
    return slabs, pockets


# ---------------------------------------------------------------------------
# Extrusao
# ---------------------------------------------------------------------------
def _clean_poly(poly: Polygon, min_area: float = 2e-3):
    """Descarta lascas e normaliza o poligono antes de extrudar."""
    if poly.is_empty or poly.area < min_area:
        return None
    if not poly.is_valid:
        fixed = poly.buffer(0)
        cands = [q for q in _iter_polygons(fixed) if q.area >= min_area]
        if not cands:
            return None
        poly = max(cands, key=lambda q: q.area)
    # Furos minusculos nao sobrevivem a impressao e quebram a triangulacao.
    holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
    if len(holes) != len(poly.interiors):
        poly = Polygon(poly.exterior, holes)
    return poly if poly.is_valid and poly.area >= min_area else None


# Quanto uma laje desce dentro da laje de baixo, da MESMA cor, para que a
# uniao funda as duas de verdade. Sem isso elas so se encostam: o booleano
# devolve corpos separados em contato face a face, e ao RELER o arquivo a solda
# de vertices cria arestas com 4 faces -- a peca monocromatica voltava com 5
# arestas defeituosas mesmo com o volume identico. Fica bem abaixo de uma
# camada, entao nao muda nada no fatiamento.
_OVERLAP = 0.05


def extrude_slabs(slabs: list[Slab]) -> trimesh.Trimesh:
    """Extruda cada poligono na sua faixa de Z e une os solidos."""
    # So vale afundar se esta cor tambem possui a laje da base; senao o
    # rebaixo invadiria a peca de outra cor.
    tem_base = any(s.z0 <= 1e-9 for s in slabs)

    parts: list[trimesh.Trimesh] = []
    for s in slabs:
        z0 = s.z0 - _OVERLAP if (tem_base and s.z0 > 1e-9) else s.z0
        h = s.z1 - z0
        if h <= 1e-9 or s.geom.is_empty:
            continue
        T = trimesh.transformations.translation_matrix([0.0, 0.0, z0])
        for poly in _iter_polygons(s.geom):
            poly = _clean_poly(poly)
            if poly is None:
                continue
            try:
                m = trimesh.creation.extrude_polygon(poly, height=h, transform=T)
            except Exception:
                continue
            # Lascas degeneradas produzem malha que nao e solida, e o engine de
            # booleano rejeita o lote inteiro por causa de uma so. Filtra aqui.
            if m.is_volume:
                parts.append(m)
    if not parts:
        raise ValueError("nenhuma geometria para extrudar")
    if len(parts) == 1:
        return _tidy(parts[0])
    # Unico booleano 3D do pipeline, e num caso bem-comportado (prismas
    # alinhados ao eixo, empilhados). Sem ele, duas lajes que se tocam em z
    # ficam com arestas compartilhadas por 4 faces depois de soldar os
    # vertices, e a malha deixa de ser watertight.
    return _tidy(trimesh.boolean.union(parts, engine="manifold"))


def _tidy(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Tira as faces de area zero que o booleano deixa para tras.

    Elas nao mudam o volume, mas sobrevivem a exportacao e quebram a malha na
    RELEITURA -- o fatiador le o arquivo, nao o objeto em memoria.

    Nao basta apaga-las: essas faces tem DOIS VERTICES NA MESMA POSICAO com
    indices diferentes, entao sao topologicamente necessarias e remove-las
    abre buracos. Primeiro colapsam-se os vertices coincidentes, e so entao as
    faces somem sem deixar vao. A tolerancia do colapso sobe so ate a malha
    fechar, e qualquer mudanca real de volume reprova a limpeza.
    """
    if not (mesh.area_faces < 1e-12).any():
        out = mesh.copy()
        out.merge_vertices()
        return out if out.is_volume else mesh

    for digits in (8, 7, 6, 5):
        out = mesh.copy()
        out.merge_vertices(digits_vertex=digits)
        keep = out.nondegenerate_faces(height=1e-9)
        if not keep.all():
            out.update_faces(keep)
            out.remove_unreferenced_vertices()
        if (out.is_watertight and out.is_volume
                and not (out.area_faces < 1e-12).any()
                and abs(out.volume - mesh.volume) < 1e-4):
            return out

    # Ultimo recurso: devolver a malha ao engine manifold, que a reconstroi
    # como variedade limpa. Custa uma remalha de leve (na peca monocromatica,
    # 0.0013% do volume -- ordem de grandeza muito abaixo de uma camada), e e
    # preferivel a exportar um arquivo que o fatiador vai reclamar.
    try:
        out = trimesh.boolean.union([mesh], engine="manifold")
    except Exception:
        return mesh
    if (out.is_watertight and out.is_volume
            and not (out.area_faces < 1e-12).any()
            and abs(out.volume - mesh.volume) < 1e-2 * max(mesh.volume, 1.0)):
        return out
    return mesh


def build(p: Params, image_path: str, variant: str
          ) -> tuple[dict[str, trimesh.Trimesh], dict[str, list[Slab]]]:
    """Gera as malhas de uma variante. `variant` em {"mmu", "glue"}."""
    art = artwork(p, image_path)
    if variant == "mmu":
        slabs = build_slabs_mmu(p, art)
    elif variant == "glue":
        slabs, _ = build_slabs_glue(p, art)
    else:
        raise ValueError(f"variante desconhecida: {variant}")
    meshes = {c: extrude_slabs(s) for c, s in slabs.items() if s}
    return meshes, slabs
