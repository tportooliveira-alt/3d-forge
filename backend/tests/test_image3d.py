"""
Testes do image3d_service: cada modo precisa gerar sólido fechado e imprimível.
Rodar de dentro de backend/:  pytest tests/ -v
"""

import sys
import uuid
from pathlib import Path

import numpy as np
import pytest
import trimesh
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.image3d_service import (  # noqa: E402
    gerar_modelo,
    _carregar_imagem,
    _corrigir_pinos,
    _extrudar_mascara,
    _mascara_objeto,
    _mascara_sujeito,
)


@pytest.fixture(scope="module")
def imagens(tmp_path_factory):
    d = tmp_path_factory.mktemp("imgs")

    # Anel com furo: testa topologia (genus 1) e alpha
    anel = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    dr = ImageDraw.Draw(anel)
    dr.ellipse([40, 40, 360, 360], fill=(20, 20, 20, 255))
    dr.ellipse([140, 140, 260, 260], fill=(0, 0, 0, 0))
    anel.save(d / "anel.png")

    # Arte de linha preto e branco, sem alpha
    line = Image.new("L", (300, 300), 255)
    ImageDraw.Draw(line).rectangle([50, 50, 250, 250], fill=0)
    line.save(d / "lineart.png")

    # Objeto sólido sobre fundo branco: o caso do render de produto
    obj = Image.new("L", (400, 500), 252)
    dr2 = ImageDraw.Draw(obj)
    dr2.ellipse([60, 40, 340, 380], fill=90)
    dr2.rectangle([90, 360, 310, 460], fill=140)
    obj.save(d / "objeto_fundo_branco.png")

    # "Foto": gradiente com ruído
    rng = np.random.default_rng(0)
    g = np.tile(np.linspace(0, 255, 320, dtype=np.uint8), (240, 1)).astype(int)
    g = (g + rng.integers(0, 40, (240, 320))).clip(0, 255).astype(np.uint8)
    Image.fromarray(g, "L").save(d / "foto.png")

    Image.new("L", (64, 64), 128).save(d / "uniforme.png")
    return d


def _gerar(**kw):
    return gerar_modelo(job_id=str(uuid.uuid4())[:8], **kw)


@pytest.mark.parametrize("modo,arquivo", [
    ("litofania", "foto.png"),
    ("relevo", "foto.png"),
    ("silhueta", "anel.png"),
    ("silhueta", "lineart.png"),
    ("litofania", "uniforme.png"),
])
def test_solido_fechado(imagens, modo, arquivo):
    """Todo modo entrega malha fechada, com winding consistente e volume positivo."""
    r = _gerar(image_path=str(imagens / arquivo), modo=modo, largura_mm=60)
    assert r["status"] == "done", r.get("message")

    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0
    assert (mesh.area_faces < 1e-12).sum() == 0


def test_auto_detecta_silhueta_e_litofania(imagens):
    assert _gerar(image_path=str(imagens / "anel.png"), modo="auto")["modo"] == "silhueta"
    assert _gerar(image_path=str(imagens / "lineart.png"), modo="auto")["modo"] == "silhueta"
    assert _gerar(image_path=str(imagens / "foto.png"), modo="auto")["modo"] == "litofania"


def test_furo_preservado(imagens):
    """O buraco do anel precisa sobreviver: genus 1 → característica de Euler 0."""
    r = _gerar(image_path=str(imagens / "anel.png"), modo="silhueta", largura_mm=60, espessura_max=5)
    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.euler_number == 0
    assert len(mesh.split(only_watertight=False)) == 1

    # Anel de Ø48mm externo e Ø18mm interno, 5mm de altura
    esperado = np.pi * (24**2 - 9**2) * 5
    assert mesh.volume == pytest.approx(esperado, rel=0.05)


def test_litofania_tem_face_plana(imagens):
    """A frente da litofania encosta na mesa: plano contínuo em z=0."""
    r = _gerar(image_path=str(imagens / "foto.png"), modo="litofania", largura_mm=80)
    mesh = trimesh.load(r["output"], force="mesh")
    z = mesh.vertices[:, 2]
    assert z.min() == pytest.approx(0.0, abs=1e-6)
    assert (np.abs(z) < 1e-9).sum() == len(mesh.vertices) // 2
    assert r["dimensoes_mm"]["espessura"] == pytest.approx(3.0, abs=0.01)


def test_escala_respeita_proporcao(imagens):
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100)
    d = r["dimensoes_mm"]
    assert d["largura"] == pytest.approx(100, abs=0.5)
    assert d["altura"] == pytest.approx(100 * 240 / 320, rel=0.02)  # 320x240 → 3:4


def test_altura_mm_limita_a_peca(imagens):
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=200, altura_mm=40)
    assert r["dimensoes_mm"]["altura"] <= 40.5
    assert r["dimensoes_mm"]["largura"] < 200


def test_inverter_troca_o_relevo(imagens):
    normal = _gerar(image_path=str(imagens / "foto.png"), modo="relevo")
    invertido = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", inverter=True)
    assert normal["malha"]["volume_cm3"] != invertido["malha"]["volume_cm3"]


def test_moldura_engrossa_a_borda(imagens):
    sem = _gerar(image_path=str(imagens / "foto.png"), modo="litofania")
    com = _gerar(image_path=str(imagens / "foto.png"), modo="litofania", moldura_mm=4)
    assert com["malha"]["volume_cm3"] > sem["malha"]["volume_cm3"]


@pytest.mark.parametrize("fmt", ["stl", "obj", "ply", "glb", "3mf"])
def test_formatos_de_saida(imagens, fmt):
    r = _gerar(image_path=str(imagens / "lineart.png"), modo="silhueta", formato=fmt)
    assert r["status"] == "done"
    assert Path(r["output"]).suffix == f".{fmt}"
    assert r["size_bytes"] > 0


def test_erros(imagens):
    assert _gerar(image_path="/nao/existe.png")["status"] == "error"
    assert _gerar(image_path=str(imagens / "foto.png"), modo="xpto")["status"] == "error"
    assert _gerar(image_path=str(imagens / "foto.png"), espessura_min=5, espessura_max=2)["status"] == "error"
    # Limiar que não captura nada → silhueta vazia, não malha quebrada
    vazio = _gerar(image_path=str(imagens / "foto.png"), modo="silhueta", limiar=1)
    assert vazio["status"] == "error" and "vazia" in vazio["message"]


def test_celulas_na_diagonal_nao_furam_a_malha():
    """
    Regressão: duas células tocando só pela quina faziam a aresta vertical ficar com
    4 faces em vez de 2, e a peça saía aberta.
    """
    m = np.zeros((4, 4), bool)
    m[1, 1] = m[2, 2] = True
    assert _extrudar_mascara(m, 1.0, 2.0).is_watertight

    # Xadrez: o pior caso, todo contato é diagonal
    xadrez = np.indices((20, 20)).sum(axis=0) % 2 == 0
    assert _extrudar_mascara(xadrez, 1.0, 2.0).is_watertight


def test_corrigir_pinos_e_idempotente():
    m = np.zeros((6, 6), bool)
    m[1, 1] = m[2, 2] = m[3, 1] = True
    uma = _corrigir_pinos(m)
    assert (_corrigir_pinos(uma) == uma).all()
    assert uma[m].all()  # só acrescenta, nunca apaga o que era objeto


def test_silhueta_com_diagonais_fecha(imagens, tmp_path):
    """Um X em diagonal é cheio de contato de quina — precisa sair fechado."""
    img = Image.new("L", (300, 300), 255)
    dr = ImageDraw.Draw(img)
    dr.line([(30, 270), (270, 30)], fill=0, width=3)
    dr.line([(30, 30), (270, 270)], fill=0, width=3)
    p = tmp_path / "x.png"
    img.save(p)

    r = _gerar(image_path=str(p), modo="silhueta", largura_mm=60)
    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.is_watertight
    assert mesh.volume > 0


def test_recorte_remove_fundo_no_relevo(imagens):
    """
    Sem recorte, fundo branco vira a parte MAIS ALTA da peça (claro = alto).
    No relevo o recorte é automático.
    """
    r = _gerar(image_path=str(imagens / "objeto_fundo_branco.png"), modo="relevo", largura_mm=100)
    assert r["status"] == "done"
    assert r["malha"]["cobertura"] < 0.85          # o fundo saiu fora
    assert any("Fundo removido" in a for a in r["avisos"])

    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.is_watertight
    assert r["dimensoes_mm"]["largura"] < 100      # a peça é menor que o quadro

    # E o topo tem que seguir o relevo, não sair plano
    z = mesh.vertices[:, 2]
    assert z.max() - z[z > 0.01].min() > 0.5


def test_litofania_nao_recorta_sozinha(imagens):
    """Litofania é painel de luz: quer a placa inteira, mesmo com fundo liso."""
    r = _gerar(image_path=str(imagens / "objeto_fundo_branco.png"), modo="litofania", largura_mm=100)
    assert r["malha"]["cobertura"] == 1.0
    assert r["dimensoes_mm"]["largura"] == pytest.approx(100, abs=0.5)


def test_recorte_explicito_na_litofania(imagens):
    r = _gerar(image_path=str(imagens / "objeto_fundo_branco.png"), modo="litofania",
               largura_mm=100, recorte=True)
    assert r["malha"]["cobertura"] < 0.85
    assert trimesh.load(r["output"], force="mesh").is_watertight


def test_recorte_desligado(imagens):
    r = _gerar(image_path=str(imagens / "objeto_fundo_branco.png"), modo="relevo",
               largura_mm=100, recorte=False)
    assert r["malha"]["cobertura"] == 1.0


def test_nao_recorta_traco_fino(imagens):
    """
    Desenho de linha sobre branco não é objeto recortável: recortar no traço daria
    uma peça frágil em vez da placa. Melhor deixar a placa inteira.
    """
    cinza, alpha, rgb, _ = _carregar_imagem(imagens / "lineart.png", 260)
    assert _mascara_objeto(rgb, cinza, alpha) is not None  # retângulo cheio é objeto

    fino = Image.new("L", (300, 300), 255)
    dr = ImageDraw.Draw(fino)
    for k in range(0, 300, 40):
        dr.line([(k, 0), (k, 299)], fill=0, width=2)
    p = imagens / "listras.png"
    fino.save(p)
    cinza, alpha, rgb, _ = _carregar_imagem(p, 260)
    assert _mascara_objeto(rgb, cinza, alpha) is None


def test_corpos_soltos_sao_contados_na_peca_recortada(imagens, tmp_path):
    """Peça recortada que sai em pedaços precisa avisar, não só no modo silhueta."""
    img = Image.new("L", (300, 300), 252)
    dr = ImageDraw.Draw(img)
    dr.ellipse([20, 20, 130, 130], fill=80)
    dr.ellipse([170, 170, 280, 280], fill=80)
    p = tmp_path / "dois.png"
    img.save(p)

    r = _gerar(image_path=str(p), modo="relevo", largura_mm=80, recorte=True)
    if r["malha"]["corpos"] > 1:
        assert any("partes soltas" in a for a in r["avisos"])


def test_alto_relevo_e_mais_fundo_e_menos_ruidoso(imagens):
    """
    forma_mm separa forma de detalhe. Sem isso, subir a espessura só amplifica o ruído
    do sombreamento e a peça vira uma serra de picos.
    """
    raso = _gerar(image_path=str(imagens / "foto.png"), modo="relevo",
                  largura_mm=100, espessura_max=30, recorte=False)
    alto = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100,
                  espessura_max=30, forma_mm=6, detalhe_mm=3, recorte=False)

    ma = trimesh.load(alto["output"], force="mesh")
    assert ma.is_watertight
    assert alto["dimensoes_mm"]["espessura"] > 20      # continua fundo

    # Rugosidade: variação média de z entre vértices vizinhos no topo
    def aspereza(caminho):
        m = trimesh.load(caminho, force="mesh")
        a, b = m.edges_unique[:, 0], m.edges_unique[:, 1]
        z = m.vertices[:, 2]
        topo = (z[a] > 0.5) & (z[b] > 0.5)
        return float(np.abs(z[a][topo] - z[b][topo]).mean())

    assert aspereza(alto["output"]) < aspereza(raso["output"])


def test_forma_respeita_o_piso_da_base(imagens):
    """O detalhe não pode furar a base: nada abaixo de base_mm."""
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100,
               espessura_max=25, base_mm=5, forma_mm=6, detalhe_mm=8, recorte=False)
    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.is_watertight
    assert r["dimensoes_mm"]["espessura"] >= 5


def test_gravacao_de_texto_sobe_o_relevo(imagens):
    """Texto gravado tem que virar material a mais, na altura pedida."""
    sem = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False)
    com = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False,
                 textos=[{"texto": "BF", "x": 0.5, "y": 0.5, "tamanho": 0.20, "altura_mm": 3.0}])

    assert com["malha"]["volume_cm3"] > sem["malha"]["volume_cm3"]
    # A gravação soma sobre a cota local, não sobre o pico — então sobe, mas nunca mais que 3mm
    delta = com["dimensoes_mm"]["espessura"] - sem["dimensoes_mm"]["espessura"]
    assert 0 < delta <= 3.0 + 0.2
    assert trimesh.load(com["output"], force="mesh").is_watertight

    # Numa superfície plana a altura da gravação é exata
    plano_sem = _gerar(image_path=str(imagens / "uniforme.png"), modo="relevo",
                       largura_mm=60, base_mm=3, recorte=False)
    plano_com = _gerar(image_path=str(imagens / "uniforme.png"), modo="relevo",
                       largura_mm=60, base_mm=3, recorte=False,
                       textos=[{"texto": "BF", "x": 0.5, "y": 0.5, "tamanho": 0.3, "altura_mm": 3.0}])
    assert plano_com["dimensoes_mm"]["espessura"] == pytest.approx(
        plano_sem["dimensoes_mm"]["espessura"] + 3.0, abs=0.15)


def test_gravacao_acompanha_a_superficie(imagens):
    """A gravação soma sobre a altura existente, então segue o relevo embaixo dela."""
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False,
               espessura_max=10, textos=[{"texto": "IIIIII", "x": 0.5, "y": 0.5,
                                          "tamanho": 0.3, "altura_mm": 2.0}])
    mesh = trimesh.load(r["output"], force="mesh")
    assert mesh.is_watertight
    # foto.png é um gradiente: o texto no meio não pode ficar todo na mesma cota
    v = mesh.vertices
    faixa = v[(np.abs(v[:, 1] - v[:, 1].mean()) < 5) & (v[:, 2] > 1)]
    assert faixa[:, 2].std() > 0.3


def test_texto_fora_da_peca_e_ignorado_com_aviso(imagens):
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False,
               textos=[{"texto": "X", "x": 9.0, "y": 9.0, "tamanho": 0.05, "altura_mm": 2.0}])
    assert r["status"] == "done"
    assert trimesh.load(r["output"], force="mesh").is_watertight


def test_texto_vazio_nao_quebra(imagens):
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False,
               textos=[{"texto": "   ", "x": 0.5, "y": 0.5}, {}])
    assert r["status"] == "done"


def test_salto_poe_o_sujeito_pra_fora(imagens, tmp_path):
    """
    Regressão do erro mais grave: num render, o fundo claro sobe e o sujeito escuro
    AFUNDA. Brilho não diz o que está na frente — a máscara diz, e o salto põe pra fora.
    """
    # Sujeito escuro sobre fundo claro: sem máscara ele afunda
    img = Image.new("L", (300, 300), 210)
    ImageDraw.Draw(img).ellipse([90, 90, 210, 210], fill=70)
    p = tmp_path / "sujeito_escuro.png"
    img.save(p)

    mascara = Image.new("L", (300, 300), 0)
    ImageDraw.Draw(mascara).ellipse([90, 90, 210, 210], fill=255)
    pm = tmp_path / "mascara.png"
    mascara.save(pm)

    def cota(caminho_stl, x, y):
        """Altura do TOPO em (x, y) normalizado. O fundo da peça também tem vértices
        nesse XY, em z=0 — usar a média deles derrubaria a leitura pela metade."""
        m = trimesh.load(caminho_stl, force="mesh")
        v = m.vertices
        px = (v[:, 0] - v[:, 0].min()) / np.ptp(v[:, 0])
        py = 1 - (v[:, 1] - v[:, 1].min()) / np.ptp(v[:, 1])
        d = (px - x) ** 2 + (py - y) ** 2
        return v[np.argsort(d)[:30], 2].max()

    sem = _gerar(image_path=str(p), modo="relevo", largura_mm=100,
                 espessura_max=10, recorte=False)
    queda = cota(sem["output"], 0.5, 0.5) - cota(sem["output"], 0.12, 0.12)
    assert queda < 0, "o sujeito escuro precisa afundar sem máscara — se não, o teste não prova nada"

    com = _gerar(image_path=str(p), modo="relevo", largura_mm=100, espessura_max=10,
                 recorte=False, sujeito_mascara=str(pm), salto_mm=15, sujeito_borda_mm=1)
    subida = cota(com["output"], 0.5, 0.5) - cota(com["output"], 0.12, 0.12)
    assert subida > 0, "com a máscara o sujeito tem que ficar acima do fundo"
    assert subida - queda == pytest.approx(15, abs=0.5)  # o salto entra inteiro
    assert trimesh.load(com["output"], force="mesh").is_watertight


def test_domo_arredonda_a_lateral_do_sujeito(tmp_path):
    """
    Sem domo o salto é um platô: parede vertical na borda, e a peça lê como recorte de
    papelão levantado. Com domo a altura sobe com a distância até a borda, e o sujeito
    ganha volume de corpo.
    """
    disco = Image.new("L", (400, 400), 0)
    ImageDraw.Draw(disco).ellipse([100, 100, 300, 300], fill=255)
    p = tmp_path / "disco.png"
    disco.save(p)

    plato = _mascara_sujeito(str(p), (400, 400), borda_px=1.0, domo_px=0)
    domo = _mascara_sujeito(str(p), (400, 400), borda_px=1.0, domo_px=60)

    centro, meio = (200, 200), (200, 265)  # meio fica a ~35px da borda do disco
    assert plato[centro] == pytest.approx(1.0, abs=0.02)
    assert plato[meio] == pytest.approx(1.0, abs=0.02)      # platô: mesma cota
    assert domo[centro] == pytest.approx(1.0, abs=0.02)
    assert domo[meio] < 0.95                                 # domo: cai indo pra borda
    assert domo[meio] > 0.4                                  # mas sem despencar

    # E o perfil tem que ser monótono do centro pra fora
    raio = domo[200, 200:300]
    assert np.all(np.diff(raio) <= 1e-6)


def test_mascara_de_sujeito_ilegivel_avisa(imagens):
    r = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100,
               recorte=False, sujeito_mascara="/nao/existe.png", salto_mm=10)
    assert r["status"] == "done"
    assert any("máscara de sujeito" in a for a in r["avisos"])


def test_salto_sem_mascara_e_ignorado(imagens):
    sem = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100, recorte=False)
    com = _gerar(image_path=str(imagens / "foto.png"), modo="relevo", largura_mm=100,
                 recorte=False, salto_mm=20)
    assert com["dimensoes_mm"]["espessura"] == pytest.approx(sem["dimensoes_mm"]["espessura"], abs=0.01)


def test_avisos_de_impressao(imagens):
    """Parâmetros arriscados pra FDM viram aviso, não erro silencioso."""
    r = _gerar(image_path=str(imagens / "foto.png"), modo="litofania", espessura_min=0.1, espessura_max=0.5)
    assert r["status"] == "done"
    assert any("espessura" in a.lower() for a in r["avisos"])
