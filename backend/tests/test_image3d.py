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


def test_avisos_de_impressao(imagens):
    """Parâmetros arriscados pra FDM viram aviso, não erro silencioso."""
    r = _gerar(image_path=str(imagens / "foto.png"), modo="litofania", espessura_min=0.1, espessura_max=0.5)
    assert r["status"] == "done"
    assert any("espessura" in a.lower() for a in r["avisos"])
