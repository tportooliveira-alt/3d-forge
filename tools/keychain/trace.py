"""Vetorizacao da arte a partir do render de referencia.

Porque classificacao supervisionada e nao k-means: rodando k-means em LAB sobre o
render, os clusters saem separados por ILUMINACAO, nao por material -- o roxo vira
tres clusters (claro/medio/sombra) e o rosa, que e 1.8% dos pixels, se perde. A
solucao e classificar por CROMATICIDADE (a*, b*), que e praticamente invariante a
sombra, usando L* apenas para desempatar branco (claro) de cabelo (escuro).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from .params import MIN_AREA_MM2, Params


# Painel da vista frontal dentro de assets/ref_render.jpg (1254x1254).
# Escolhido em vez do render do topo porque a razao da elipse ajustada e 0.9946
# (circulo -- vista ortografica), contra 0.8608 do hero (perspectiva).
FRONT_PANEL = (14, 716, 462, 1246)  # x0, y0, x1, y1 (folgado: o disco vai ate y=1202)

# Referencias em (L*, a*-128, b*-128), medidas no proprio render.
# A distancia de classificacao usa so (a*, b*); L entra como faixa permitida.
@dataclass(frozen=True)
class Swatch:
    name: str
    a: float
    b: float
    l_min: float = 0.0
    l_max: float = 255.0
    weight: float = 1.0  # < 1 torna a cor mais "atraente" (usada p/ cores raras)


SWATCHES: tuple[Swatch, ...] = (
    Swatch("pink", a=58.0, b=4.0, l_min=60.0),
    # Medido no rosto e nas maos: a pele e bem mais QUENTE do que parece
    # (b* ~ +27, nao +10). Com b* subestimado, o swatch caia entre branco e
    # pele, e todo branco sombreado do quimono virava pele -- 6.7x de area
    # de pele a mais do que a referencia.
    Swatch("skin", a=16.0, b=27.0, l_min=70.0),
    # l_min baixo de proposito: branco SOMBREADO continua branco. O que o
    # separa do cabelo e o l_max=48 do cabelo, nao um limiar alto aqui.
    Swatch("white", a=3.0, b=0.0, l_min=52.0),
    # Medido no render: o cabelo e escuro e quase NEUTRO (a*~+5, b*~-3),
    # praticamente a mesma cromaticidade do branco. Quem separa os dois e
    # o L*, nao a cor -- por isso o par l_max/l_min e obrigatorio aqui.
    Swatch("hair", a=5.0, b=-3.0, l_max=48.0),
    Swatch("purple", a=29.0, b=-24.0),
)


# ---------------------------------------------------------------------------
# Localizacao do disco
# ---------------------------------------------------------------------------
def load_front_panel(path: str) -> np.ndarray:
    """Le a referencia e devolve a vista frontal em RGB.

    Aceita as duas formas: a prancha de 4 vistas (recorta o painel frontal) e
    uma imagem que ja e so o medalhao (usa inteira).
    """
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"nao consegui abrir {path}")
    if _is_contact_sheet(bgr):
        x0, y0, x1, y1 = FRONT_PANEL
        bgr = bgr[y0:y1, x0:x1]
    return np.ascontiguousarray(bgr[:, :, ::-1])


def _is_contact_sheet(bgr: np.ndarray) -> bool:
    """Prancha de varias vistas: o medalhao ocupa pouco da largura."""
    h, w = bgr.shape[:2]
    m = _silhouette(np.ascontiguousarray(bgr[:, :, ::-1]))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n < 2:
        return False
    big = stats[1:, cv2.CC_STAT_AREA].max()
    return big < 0.34 * h * w


def _silhouette(rgb: np.ndarray) -> np.ndarray:
    """Mascara do medalhao: tudo que nao e o fundo neutro claro."""
    hsv = cv2.cvtColor(rgb[:, :, ::-1], cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    m = (~((s < 40) & (v > 195))).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def find_disc(rgb: np.ndarray, open_kernel: int = 0) -> tuple[float, float, float]:
    """Centro e raio do disco em pixels.

    A abertura morfologica com nucleo grande elimina o pescoco fino da aba, de
    modo que a elipse ajustada descreve o disco e nao a silhueta inteira.
    """
    h, w = rgb.shape[:2]
    m = _silhouette(rgb)
    k = open_kernel if open_kernel else max(3, int(min(h, w) * 0.09) | 1)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    disc = cv2.morphologyEx(m, cv2.MORPH_OPEN, ker)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(disc, 8)
    if n < 2:
        raise RuntimeError("nao encontrei o disco na imagem de referencia")
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cnts, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_NONE)
    pts = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)

    # Descarta os pontos encostados na moldura: numa imagem em que o disco sai
    # cortado, sao eles que puxam o ajuste e fazem o circulo virar elipse.
    pad = max(2.0, 0.004 * min(h, w))
    keep = ((pts[:, 0] > pad) & (pts[:, 0] < w - 1 - pad) &
            (pts[:, 1] > pad) & (pts[:, 1] < h - 1 - pad))
    if keep.sum() >= 0.2 * len(pts):
        pts = pts[keep]

    return _fit_circle(pts)


def _fit_circle(pts: np.ndarray) -> tuple[float, float, float]:
    """Ajuste de circulo por minimos quadrados (Kasa): linear e estavel."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones(len(x))])
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0] / 2.0, sol[1] / 2.0
    r = float(np.sqrt(max(sol[2] + cx ** 2 + cy ** 2, 1e-12)))
    return float(cx), float(cy), r


# ---------------------------------------------------------------------------
# Segmentacao por cor
# ---------------------------------------------------------------------------
def segment_colors(rgb: np.ndarray, disc: tuple[float, float, float],
                   tolerance: float, mm_per_px: float = 0.106,
                   field_mm: float | None = None) -> dict[str, np.ndarray]:
    """Classifica cada pixel na cor de referencia mais proxima.

    A area util e o CAMPO INTERNO, nao o disco inteiro: o sulco e o aro sao
    escuros e brilhantes e so introduziriam ruido -- o sulco chegava a formar
    um anel escuro gigante que engolia a deteccao do cabelo.
    """
    cx, cy, r = disc
    h, w, _ = rgb.shape
    yy, xx = np.mgrid[0:h, 0:w]
    lim = r * 0.99 if field_mm is None else field_mm / mm_per_px
    inside = ((xx - cx) ** 2 + (yy - cy) ** 2) <= lim ** 2

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0]
    A = lab[:, :, 1] - 128.0
    B = lab[:, :, 2] - 128.0

    best = np.full((h, w), np.inf, np.float32)
    who = np.full((h, w), -1, np.int16)
    for idx, sw in enumerate(SWATCHES):
        d = np.sqrt((A - sw.a) ** 2 + (B - sw.b) ** 2) * sw.weight
        ok = (L >= sw.l_min) & (L <= sw.l_max) & (d <= tolerance)
        take = ok & (d < best)
        best = np.where(take, d, best)
        who = np.where(take, idx, who)

    who = np.where(inside, who, -1).astype(np.int16)
    who = _split_figure_from_background(who, A, B, L, inside, mm_per_px)

    masks: dict[str, np.ndarray] = {}
    for idx, sw in enumerate(SWATCHES):
        m = ((who == idx) & inside).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        masks[sw.name] = m
    return masks


_IDX = {sw.name: i for i, sw in enumerate(SWATCHES)}
_ART_NAMES = ("white", "pink", "skin", "hair")


def _split_figure_from_background(who, A, B, L, inside, mm_per_px):
    """Separa fundo roxo de arte, e dentro da arte proibe roxo por construcao.

    Esta e a decisao central do traçado. Classificar pixel a pixel pela cor nao
    funciona nas bordas: o render tem sombras projetadas duras (linhas quase
    pretas) em volta de cada relevo, e elas eram lidas ora como roxo, ora como
    nada -- o que abria canais de roxo dentro do quimono e comia as abas da
    faixa. Aqui o fundo e definido TOPOLOGICAMENTE (a mancha roxa que alcanca a
    borda do campo) e tudo que nao e fundo recebe obrigatoriamente uma cor de
    arte, escolhida pela cromaticidade mais proxima.
    """
    art_idx = np.array([_IDX[n] for n in _ART_NAMES], np.int16)

    # 1. fundo = componente roxo que encosta na borda do campo
    purple = ((who == _IDX["purple"]) & inside).astype(np.uint8)
    k = max(3, int(round(0.45 / mm_per_px)) | 1)
    purple = cv2.morphologyEx(purple, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(purple, 8)
    if n < 2:
        return who
    border = cv2.dilate(inside.astype(np.uint8), np.ones((3, 3), np.uint8)) \
        & ~inside.astype(np.uint8)
    ring = cv2.dilate(border, np.ones((9, 9), np.uint8)) > 0
    touching = {int(v) for v in np.unique(lab[ring]) if v > 0}
    if not touching:
        touching = {1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))}
    bg = np.isin(lab, list(touching)) & inside

    # 2. figura = dentro do campo e fora do fundo
    fig = inside & ~bg
    if not fig.any():
        return who

    # 3. dentro da figura, so cores de arte competem
    best = np.full(who.shape, np.inf, np.float32)
    pick = np.zeros(who.shape, np.int16)
    for i in art_idx:
        sw = SWATCHES[int(i)]
        d = np.sqrt((A - sw.a) ** 2 + (B - sw.b) ** 2) * sw.weight
        # A faixa de L de cada cor vale tambem aqui. Cabelo e branco tem quase
        # a mesma cromaticidade; so o brilho os distingue.
        d = np.where((L >= sw.l_min) & (L <= sw.l_max), d, np.inf)
        take = d < best
        best = np.where(take, d, best)
        pick = np.where(take, i, pick)

    out = np.where(fig, pick, np.int16(_IDX["purple"]))
    out = np.where(inside, out, np.int16(-1)).astype(np.int16)

    # 4. O escuro DENTRO da figura nao e sombra: e cor do desenho. O logo usa
    # preto estruturalmente -- cabelo, as separacoes manga/tronco/perna, a
    # banda sob o obi. Dissolver esse preto nas cores vizinhas resolvia o
    # vazamento de roxo, mas FUNDIA as formas (manga virava perna, faixa
    # virava lapela). Entao ele fica. Fora da figura o escuro e sombra
    # projetada de verdade, e volta a ser fundo.
    out[(out == _IDX["hair"]) & ~fig] = _IDX["purple"]
    orphan = inside & (out < 0)
    if orphan.any():
        src = (out >= 0) & inside
        if src.any():
            out[orphan] = _nearest_label(out, orphan, src)

    # 5. tira a pimenta: maioria numa vizinhanca pequena
    return _majority_filter(out, inside, mm_per_px)


def _majority_filter(who, inside, mm_per_px, mm=0.30):
    """Suaviza rotulos: cada pixel toma a cor dominante na sua vizinhanca."""
    k = max(3, int(round(mm / mm_per_px)) | 1)
    ker = np.ones((k, k), np.float32)
    votes = []
    for idx in range(len(SWATCHES)):
        v = cv2.filter2D((who == idx).astype(np.float32), -1, ker)
        votes.append(v)
    stack = np.stack(votes, 0)
    win = np.argmax(stack, 0).astype(np.int16)
    return np.where(inside, win, np.int16(-1)).astype(np.int16)


def _nearest_label(who: np.ndarray, todo: np.ndarray,
                   sources: np.ndarray) -> np.ndarray:
    """Para cada pixel de `todo`, o rotulo do pixel de `sources` mais proximo."""
    src = (~sources).astype(np.uint8) * 255
    _, nearest = cv2.distanceTransformWithLabels(
        src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    # Os zeros (os pixels de `sources`) sao numerados 1..N na ordem de varredura
    # da imagem; e assim que se volta do indice para o rotulo.
    zeros = np.flatnonzero(sources.ravel())
    lut = np.zeros(len(zeros) + 1, np.int16)
    lut[1:] = who.ravel()[zeros]
    return lut[nearest[todo]]


def _keep_hair_on_head(who: np.ndarray, fig: np.ndarray) -> np.ndarray:
    """Mantem como cabelo so o escuro que esta na CABECA da figura.

    Cor nao distingue cabelo de sombra: o render projeta sombra escura em volta
    de cada relevo, e esse contorno escuro CIRCUNDA a figura inteira -- por
    componente conexo, cabeca e pes viram um unico blob, que era entao
    rejeitado e deixava a cabeca branca. Por isso o teste e puramente
    posicional: escuro dentro do terco superior da figura. O contorno fino que
    sobrar na zona (ombros) morre depois na abertura morfologica de
    clean_for_print; o cabelo, com ~3x4mm, sobrevive.
    """
    hair = (who == _IDX["hair"])
    if not hair.any():
        return who

    n, lab, stats, _ = cv2.connectedComponentsWithStats(fig.astype(np.uint8), 8)
    if n < 2:
        return who
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    y0 = stats[idx, cv2.CC_STAT_TOP]
    hgt = stats[idx, cv2.CC_STAT_HEIGHT]

    head = np.zeros(who.shape, bool)
    head[y0:y0 + int(hgt * 0.45), :] = True
    head &= cv2.dilate((lab == idx).astype(np.uint8),
                       np.ones((5, 5), np.uint8)).astype(bool)

    out = who.copy()
    out[hair & ~head] = -1
    return out


# ---------------------------------------------------------------------------
# Contornos -> poligonos em milimetros
# ---------------------------------------------------------------------------
def mask_to_polygons(mask: np.ndarray, disc: tuple[float, float, float],
                     mm_per_px: float) -> list[Polygon]:
    """Contornos da mascara como poligonos shapely em mm, com buracos.

    RETR_CCOMP devolve dois niveis: externos (hierarquia pai = -1) e buracos.
    O eixo Y da imagem cresce para baixo; o do modelo cresce para cima.
    """
    cx, cy, _ = disc

    # Super-amostragem antes de contornar. Contornar a mascara na resolucao
    # nativa devolve uma escada de pixel: cada degrau vira um vertice, e a
    # simplificacao posterior so escolhe QUAIS degraus manter -- a arte sai
    # serrilhada. Ampliando com interpolacao linear e limiarizando em 50%, a
    # fronteira passa a cair em posicao sub-pixel e sai suave.
    ss = 4
    big = cv2.resize(mask, None, fx=ss, fy=ss, interpolation=cv2.INTER_LINEAR)
    big = cv2.GaussianBlur(big, (0, 0), ss * 0.45)
    big = (big >= 128).astype(np.uint8) * 255

    cnts, hier = cv2.findContours(big, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    hier = hier[0]

    # +0.5/ss recoloca a amostra no centro do pixel original apos o upsample.
    def to_mm(cnt: np.ndarray) -> np.ndarray:
        pts = cnt.reshape(-1, 2).astype(np.float64)
        pts = (pts + 0.5) / ss - 0.5
        return np.column_stack([(pts[:, 0] - cx) * mm_per_px,
                                (cy - pts[:, 1]) * mm_per_px])

    out: list[Polygon] = []
    for i, cnt in enumerate(cnts):
        if hier[i][3] != -1:      # e buraco: tratado junto com o pai
            continue
        if len(cnt) < 4:
            continue
        holes = [to_mm(cnts[j]) for j in range(len(cnts))
                 if hier[j][3] == i and len(cnts[j]) >= 4]
        try:
            p = Polygon(to_mm(cnt), holes)
        except Exception:
            continue
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        out.extend(_iter_polygons(p))
    return out


def _iter_polygons(geom) -> list[Polygon]:
    """Achata qualquer geometria shapely numa lista de Polygon nao vazios."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        out: list[Polygon] = []
        for g in geom.geoms:
            out.extend(_iter_polygons(g))
        return out
    return []


def as_multipolygon(geom) -> MultiPolygon:
    """Normaliza qualquer saida de buffer/difference para MultiPolygon."""
    return MultiPolygon(_iter_polygons(geom))



def _pick_hair(dark: list[Polygon], skin: MultiPolygon, p: Params) -> MultiPolygon:
    """Escolhe, entre os poligonos escuros, os que sao mesmo cabelo.

    Cor nao basta: as sombras projetadas em volta dos relevos brancos caem na
    mesma faixa escura e chegam a ser MAIORES que o cabelo (a maior mancha
    escura do render e a sombra sob o quimono, 6.96mm2, contra 5.64mm2 do
    cabelo). O que distingue o cabelo e a posicao: ele encosta no rosto.
    Entao seleciono os escuros adjacentes a mancha de pele mais alta (a face).
    """
    if not dark or skin.is_empty:
        return MultiPolygon()
    face = max(skin.geoms, key=lambda q: q.centroid.y)
    zone = face.buffer(2.0, quad_segs=8)

    # Fecha antes de escolher: a abertura posterior tende a pinçar o cabelo em
    # dois, e ai cada pedaco cai abaixo da area minima.
    merged = unary_union([q.buffer(0) for q in dark])
    merged = merged.buffer(0.35, quad_segs=8).buffer(-0.35, quad_segs=8)

    keep = [q for q in _iter_polygons(merged) if q.intersects(zone)]
    if not keep:
        return MultiPolygon()
    return as_multipolygon(unary_union(keep))

def clean_for_print(polys: list[Polygon], p: Params,
                    min_area: float | None = None) -> MultiPolygon:
    """Simplifica, remove detalhe mais fino que o bico e descarta cacos."""
    if not polys:
        return MultiPolygon()
    geom = unary_union([q.buffer(0) for q in polys])

    # Abertura morfologica: apaga tudo que for mais estreito que min_feature.
    # Raio menor que min_feature/2: a abertura serve para matar filetes,
    # nao para arredondar a arte. min_feature continua valendo no QA.
    r = p.min_feature / 3.0
    geom = as_multipolygon(geom.buffer(-r, quad_segs=12).buffer(r * 1.02, quad_segs=12))
    if geom.is_empty:
        return MultiPolygon()

    geom = as_multipolygon(geom.simplify(p.simplify_tol, preserve_topology=True))

    if min_area is None:
        min_area = (p.min_feature * 2.0) ** 2
    kept: list[Polygon] = []
    for q in geom.geoms:
        if q.area < min_area:
            continue
        holes = [ring for ring in q.interiors
                 if Polygon(ring).area >= min_area * 0.5]
        kept.append(Polygon(q.exterior, holes))
    return MultiPolygon(kept)


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def _masked_blur(L: np.ndarray, mask: np.ndarray, sigma_px: float) -> np.ndarray:
    """Media local de L calculada SO sobre `mask` (convolucao normalizada).

    Um blur comum puxaria o cabelo escuro em volta do rosto e o fundo local
    sairia mais escuro que o proprio rosto -- o vale do queixo ficava com sinal
    invertido e nunca era detectado.
    """
    m = mask.astype(np.float32)
    num = cv2.GaussianBlur(L * m, (0, 0), sigma_px)
    den = cv2.GaussianBlur(m, (0, 0), sigma_px)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-3)


def find_raised(rgb: np.ndarray, mask: np.ndarray, disc, mm_per_px: float,
                p: Params, anchor: np.ndarray | None = None) -> MultiPolygon:
    """As partes da pele que ficam POR CIMA de outra parte da pele.

    Na peca real, rosto, antebracos e maos sao placas sobrepostas ao pescoco e
    as canelas. Mas todas tem exatamente a mesma cromaticidade (a*~18, b*~26):
    o que separa uma da outra e uma queda de ~9 em L*, uma linha de SOMBRA. Um
    tracador por cor e cego para isso e devolve tudo como um bloco unico -- era
    por isso que o queixo nao aparecia.

    Detecta-se o vale de sombra, corta-se a pele nele, e das partes resultantes
    sobem as que tem outra parte logo ABAIXO. A luz do render vem de cima, entao
    a sombra cai embaixo da aresta elevada: quem esta acima do vale e a placa de
    cima. Isso vale igual para o queixo e para as maos.
    """
    L = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, 0].astype(np.float32)
    skin = mask > 0
    if anchor is not None:
        # So os pedacos da mascara que encostam na ancora. Para o quimono a
        # ancora e a pele: assim o "M" e as letras do texto, que tambem sao
        # brancos mas sao elementos soltos e nao placas sobrepostas, ficam de
        # fora e nao ganham degrau nenhum.
        n, lab, _, _ = cv2.connectedComponentsWithStats(skin.astype(np.uint8), 8)
        near = cv2.dilate(anchor.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        keep = {int(v) for v in np.unique(lab[near & skin]) if v > 0}
        skin = np.isin(lab, list(keep)) if keep else np.zeros_like(skin)
    if not skin.any():
        return MultiPolygon()

    bg = _masked_blur(L, skin, p.shadow_sigma / mm_per_px)
    valley = ((bg - L) > p.shadow_thr) & skin
    valley = cv2.dilate(valley.astype(np.uint8), np.ones((3, 3), np.uint8))

    cut = (skin & ~(valley > 0)).astype(np.uint8)
    cut = cv2.morphologyEx(cut, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(cut, 8)
    if n < 3:
        return MultiPolygon()

    min_px = 1.2 / (mm_per_px ** 2)
    ids = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_px]
    if len(ids) < 2:
        return MultiPolygon()

    # Alcance da busca: pouco mais que a espessura do vale.
    reach = max(3, int(round(2.5 * p.shadow_sigma / mm_per_px)) | 1)
    ker = np.ones((reach, reach), np.uint8)

    raised = np.zeros(cut.shape, bool)
    for i in ids:
        comp = (lab == i).astype(np.uint8)
        near = cv2.dilate(comp, ker) > 0
        for j in ids:
            if j == i:
                continue
            # y cresce para baixo na imagem: centroide maior = mais embaixo
            if cent[j][1] <= cent[i][1]:
                continue
            if (near & (lab == j)).any():
                raised |= comp > 0
                break

    if not raised.any():
        return MultiPolygon()
    m = cv2.dilate((raised.astype(np.uint8)) * 255, np.ones((3, 3), np.uint8))
    return clean_for_print(mask_to_polygons(m, disc, mm_per_px), p, 1.0)


def trace_artwork(image_path: str, p: Params,
                  exclude=None) -> dict[str, MultiPolygon]:
    """Devolve a arte vetorizada por cor, em mm, centrada na origem.

    `exclude` e a zona onde o texto do render original mora. Ela e removida
    porque o texto e REGERADO de fonte em text_arc.py -- sem isso, as letras
    tracadas do JPEG ficariam sobrepostas as letras geradas.
    """
    rgb = load_front_panel(image_path)
    disc = find_disc(rgb)
    mm_per_px = p.radius / disc[2]

    masks = segment_colors(rgb, disc, p.trace_tolerance, mm_per_px,
                           field_mm=p.field_radius - 0.3)

    # Recorte: so o que esta dentro do campo interno elevado.
    field = Point(0, 0).buffer(p.field_radius - p.min_feature / 2.0,
                               quad_segs=p.arc_segments // 4)

    raw = {name: mask_to_polygons(mask, disc, mm_per_px)
           for name, mask in masks.items() if name != "purple"}
    skin_clean = clean_for_print(raw.get("skin", []), p, MIN_AREA_MM2.get("skin"))

    art: dict[str, MultiPolygon] = {}
    for name, polys in raw.items():
        cleaned = clean_for_print(polys, p, MIN_AREA_MM2.get(name))
        # Refiltra DEPOIS do recorte: cortar no campo/zona de texto pode partir
        # um poligono valido em lascas minusculas.
        clipped = as_multipolygon(cleaned.intersection(field))
        min_area = MIN_AREA_MM2.get(name, (p.min_feature * 2.0) ** 2)
        kept = [q for q in clipped.geoms if q.area >= min_area * 0.5]
        # A zona do texto descarta o POLIGONO INTEIRO quando a maior parte dele
        # cai la dentro, em vez de recortar geometricamente. Recortar mutilava
        # o "M", cuja perna direita entra na coroa do texto (r=13.5) sem ser
        # texto. Uma letra tracada fica ~100% dentro da zona; o "M", ~10%.
        if exclude is not None and not exclude.is_empty:
            kept = [q for q in kept
                    if q.intersection(exclude).area < 0.6 * q.area]
        art[name] = MultiPolygon(kept)

    art = _resolve_overlaps(art)

    # Sub-regiao (nao e uma cor): o rosto, que ganha um degrau a mais em Z.
    # Recortado na propria pele: a dilatacao usada para achar as placas
    # empurra a borda ~1px para fora, e esse fio invadia branco e roxo -- o QA
    # de sobreposicao pegava, corretamente, alguns centesimos de mm2.
    # Recortadas na cor correspondente so depois, em build.artwork: aqui o
    # branco ainda vai encolher (perde o preto e a folga do texto).
    art["_raised_skin"] = find_raised(rgb, masks["skin"], disc, mm_per_px, p)
    # O quimono tem o mesmo empilhamento: a manga passa por cima do joelho, e a
    # divisa entre eles tambem e so sombra.
    art["_raised_white"] = find_raised(rgb, masks["white"], disc, mm_per_px, p,
                                       anchor=masks["skin"] > 0)
    return art


def _resolve_overlaps(art: dict[str, MultiPolygon]) -> dict[str, MultiPolygon]:
    """Garante que as cores nao se sobreponham, respeitando a precedencia.

    Necessario porque a limpeza morfologica dilata cada cor de forma
    independente e pode fazer duas vizinhas invadirem uma a outra.
    """
    from .params import COLOR_PRIORITY

    claimed = None
    out: dict[str, MultiPolygon] = {}
    for name in COLOR_PRIORITY:
        if name not in art:
            continue
        geom = art[name]
        if claimed is not None and not geom.is_empty:
            geom = as_multipolygon(geom.difference(claimed))
        out[name] = geom
        if not geom.is_empty:
            claimed = geom if claimed is None else unary_union([claimed, geom])
    return out
