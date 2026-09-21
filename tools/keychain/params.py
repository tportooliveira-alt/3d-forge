"""Parametros do chaveiro "AM Mulheres no Tatame".

Todas as cotas em milimetros. As imagens enviadas sao renders ilustrativos, nao
saidas de CAD: a folha tecnica tem texto corrompido e cotas contraditorias (a
vista explodida soma 6.5mm, o corte lateral diz 6.0mm). Entao, em vez de copiar
cota, as proporcoes abaixo foram MEDIDAS no proprio render, no painel da vista
frontal (razao de elipse 0.9946 = ortografica), com o disco normalizado a Q40mm:

  - sulco entre campo e aro ....... r 17.8 .. 18.4 mm  (vale de L* no perfil radial)
  - aro externo ................... r 18.4 .. 20.0 mm
  - banda do texto ................ r 13.0 .. 16.1 mm  (maiuscula ~3.05mm)
  - letra "M" ..................... 12.2 x 14.9 mm, a direita do centro
  - figura ........................ ~11 x 16 mm, a esquerda do centro

Mude os valores aqui; nada de numero magico espalhado pelos outros modulos.
"""

from dataclasses import dataclass, replace


# --------------------------------------------------------------------------
# Paleta de referencia (RGB 0-255), usada no preview e no debug das mascaras.
# A classificacao em si usa cromaticidade LAB -- ver trace.SWATCHES.
# --------------------------------------------------------------------------
PALETTE: dict[str, tuple[int, int, int]] = {
    "purple": (106, 27, 138),
    "white": (238, 236, 240),
    "pink": (226, 42, 129),
    "skin": (198, 140, 96),
    "hair": (30, 24, 32),
}

# Precedencia quando dois grupos disputam o mesmo pixel: o primeiro vence.
# O roxo e o fundo, entao fica por ultimo.
COLOR_PRIORITY = ("hair", "pink", "skin", "white", "purple")

# Area minima por cor (mm^2) ao limpar o traçado.
# O cabelo tem um limiar alto de proposito: sombras escuras em volta dos relevos
# brancos sao classificadas como "escuro", e so o cabelo de verdade e um blob
# grande e compacto. Sem isso o traçado do cabelo sai em ~50 cacos.
MIN_AREA_MM2: dict[str, float] = {
    # O preto e cor ESTRUTURAL (cabelo + as linhas que separam manga, tronco e
    # perna). As linhas tem area pequena por natureza: um limiar alto aqui as
    # apagava e o lugar virava um buraco roxo no meio do quimono.
    "hair": 0.45,
    "skin": 1.8,
    "pink": 2.0,
    "white": 1.2,
}


@dataclass(frozen=True)
class Params:
    """Geometria, tolerancias de impressao e ajustes de traçado."""

    # ---------------- Silhueta ----------------
    diameter: float = 40.0           # diametro externo do disco
    hole_diameter: float = 4.0       # furo da argola
    tab_width: float = 10.5          # largura do "pescoco" da aba
    tab_boss_diameter: float = 10.0  # diametro do ressalto (medido: 9.2-10.0)
    tab_center_offset: float = 1.5   # centro do furo acima da borda (medido: +21.5mm)

    # ---------------- Pilha em Z (costas planas em z=0) ----------------
    base_h: float = 3.0       # z 0.0 -> 3.0   disco base + aba
    groove_h: float = 0.55    # z 3.0 -> 3.55  fundo do sulco
    field_h: float = 1.25     # z 3.0 -> 4.25  campo interno elevado
    rim_h: float = 1.45       # z 3.0 -> 4.45  aro externo (ligeiramente + alto)
    art_h: float = 1.0        # +1.0 sobre o campo: figura, "M" e texto

    # ---------------- Aneis concentricos (medidos no render) ----------------
    field_radius: float = 17.8    # campo interno elevado
    groove_outer: float = 18.4    # fim do sulco / inicio do aro

    # ---------------- Texto ----------------
    text: str = "MULHERES NO TATAME"
    text_baseline_radius: float = 16.05  # medido (base no raio externo)
    text_cap_height: float = 3.05        # medido
    text_tracking: float = 1.06          # multiplicador do avanco entre letras
    text_xscale: float = 0.92            # compressao horizontal (simula condensada)
    font_path: str = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

    # ---------------- Impressao ----------------
    clearance: float = 0.2        # folga dos bolsos na variante colada
    pocket_depth: float = 0.8     # profundidade do bolso na variante colada
    min_feature: float = 0.55     # detalhe mais fino que isso e removido (bico 0.4)
    layer_height: float = 0.16    # so para checar se o relevo tem >= 2 camadas
    simplify_tol: float = 0.05    # simplificacao dos contornos tracados

    # ---------------- Traçado ----------------
    trace_tolerance: float = 34.0  # distancia maxima em cromaticidade LAB
    n_colors: int = 5              # 5 = paleta cheia; 4 funde cabelo no roxo

    arc_segments: int = 512        # resolucao angular dos circulos

    # ---------------- Derivados ----------------
    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    @property
    def hole_radius(self) -> float:
        return self.hole_diameter / 2.0

    @property
    def z_base_top(self) -> float:
        return self.base_h

    @property
    def z_groove_top(self) -> float:
        return self.base_h + self.groove_h

    @property
    def z_field_top(self) -> float:
        return self.base_h + self.field_h

    @property
    def z_rim_top(self) -> float:
        return self.base_h + self.rim_h

    @property
    def z_art_top(self) -> float:
        return self.z_field_top + self.art_h

    @property
    def total_height(self) -> float:
        return max(self.z_art_top, self.z_rim_top)

    @property
    def tab_hole_center_y(self) -> float:
        return self.radius + self.tab_center_offset

    @property
    def overall_height(self) -> float:
        """Altura total da peca deitada (disco + aba)."""
        return self.radius + self.tab_center_offset + self.tab_boss_diameter / 2.0 \
            + self.radius

    @property
    def color_groups(self) -> dict[str, tuple[str, ...]]:
        """Cor final -> grupos de cor tracados que ela absorve."""
        if self.n_colors >= 5:
            return {c: (c,) for c in PALETTE}
        # 4 cores: cabelo vira roxo (e quase preto e encosta no campo roxo)
        return {
            "purple": ("purple", "hair"),
            "white": ("white",),
            "pink": ("pink",),
            "skin": ("skin",),
        }

    def with_overrides(self, **kwargs) -> "Params":
        clean = {k: v for k, v in kwargs.items() if v is not None}
        return replace(self, **clean) if clean else self


# Variante colada: pele e cabelo viram fragmentos de 1-3mm nesta escala,
# impossiveis de imprimir soltos e colar. Ficam incorporados a base roxa.
GLUE_INSERTS: tuple[str, ...] = ("white", "pink")
GLUE_BASE_ABSORBS: tuple[str, ...] = ("skin", "hair")
