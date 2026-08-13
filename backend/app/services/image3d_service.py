"""
IMAGE3D SERVICE
Qualquer imagem (foto, logo, desenho) → sólido watertight pronto pra impressão 3D.

Modos:
  litofania    — espessura varia com o brilho (escuro = grosso). Frente plana, luz atrás.
  relevo       — mapa de altura: brilho vira relevo sobre uma base sólida.
  silhueta     — recorta por limiar e extruda (logo, ícone, chaveiro, stencil).
  profundidade — profundidade estimada por IA (MiDaS) vira relevo 3D.

Diferente do /api/face3d, aqui não há detecção de rosto: funciona com qualquer imagem.
"""

import cv2
import numpy as np
import trimesh
from pathlib import Path
from PIL import Image, ImageOps

from app.core.config import OUTPUTS_DIR

MODOS = ["auto", "litofania", "relevo", "silhueta", "profundidade"]
FORMATOS = ["stl", "obj", "glb", "ply", "3mf"]

# Defaults por modo (mm) — valores conservadores pra FDM com bico 0.4
DEFAULTS = {
    "litofania": {"espessura_min": 0.8, "espessura_max": 3.0, "base": 0.0},
    "relevo": {"espessura_min": 0.0, "espessura_max": 4.0, "base": 2.0},
    "silhueta": {"espessura_min": 0.0, "espessura_max": 4.0, "base": 0.0},
    "profundidade": {"espessura_min": 0.0, "espessura_max": 12.0, "base": 3.0},
}


def gerar_modelo(
    job_id: str,
    image_path: str,
    modo: str = "auto",
    largura_mm: float = 100.0,
    altura_mm: float | None = None,
    espessura_max: float | None = None,
    espessura_min: float | None = None,
    base_mm: float | None = None,
    resolucao: int = 260,
    inverter: bool = False,
    suavizar: float = 1.0,
    gamma: float = 1.0,
    limiar: int = 128,
    moldura_mm: float = 0.0,
    formato: str = "stl",
) -> dict:
    """Converte uma imagem em malha 3D sólida e exporta pro formato pedido."""
    path = Path(image_path)
    if not path.exists():
        return {"job_id": job_id, "status": "error", "message": "Imagem não encontrada"}

    modo = (modo or "auto").lower().strip()
    if modo not in MODOS:
        return {"job_id": job_id, "status": "error", "message": f"Modo inválido. Use: {MODOS}"}

    fmt = (formato or "stl").lower().strip(".")
    if fmt not in FORMATOS:
        return {"job_id": job_id, "status": "error", "message": f"Formato '{fmt}' não suportado. Use: {FORMATOS}"}

    try:
        cinza, alpha, orig_shape = _carregar_imagem(path, resolucao)
    except Exception as e:
        return {"job_id": job_id, "status": "error", "message": f"Falha ao ler imagem: {e}"}

    if modo == "auto":
        modo = _detectar_modo(cinza, alpha)

    d = DEFAULTS[modo]
    e_max = espessura_max if espessura_max is not None else d["espessura_max"]
    e_min = espessura_min if espessura_min is not None else d["espessura_min"]
    base = base_mm if base_mm is not None else d["base"]

    if e_max <= 0:
        return {"job_id": job_id, "status": "error", "message": "espessura_max deve ser > 0"}
    if e_min < 0 or e_min >= e_max:
        return {"job_id": job_id, "status": "error", "message": "espessura_min deve ser >= 0 e < espessura_max"}

    nr, nc = cinza.shape
    px_mm = _px_para_mm(nr, nc, largura_mm, altura_mm)

    avisos = []
    if modo == "profundidade":
        campo = _campo_profundidade(path, nr, nc)
        if campo is None:
            modo = "relevo"
            avisos.append("MiDaS indisponível — usei o modo 'relevo' com o brilho da imagem")
            campo = _normalizar(cinza)
    elif modo == "silhueta":
        campo = None
    else:
        campo = _normalizar(cinza)

    if campo is not None:
        if gamma != 1.0 and gamma > 0:
            campo = np.power(campo, gamma)
        if suavizar > 0:
            campo = cv2.GaussianBlur(campo, (0, 0), sigmaX=float(suavizar))
        # Blur e gamma comprimem os extremos; reescala pra espessura_max ser respeitada de fato
        campo = _reescalar(campo)

    # ── Construção da malha ───────────────────────────────────────────
    if modo == "silhueta":
        mascara = _mascara_silhueta(cinza, alpha, limiar, inverter)
        if not mascara.any():
            return {"job_id": job_id, "status": "error", "message": "Silhueta vazia — ajuste o limiar ou use inverter=true"}
        mesh = _extrudar_mascara(mascara, px_mm, e_max)
        cobertura = float(mascara.mean())
    else:
        if modo == "litofania":
            # escuro = grosso (bloqueia mais luz)
            valor = campo if inverter else 1.0 - campo
        else:
            # claro = alto
            valor = 1.0 - campo if inverter else campo

        altura_campo = e_min + valor * (e_max - e_min) + base
        if moldura_mm > 0:
            altura_campo = _aplicar_moldura(altura_campo, px_mm, moldura_mm, e_max + base)

        mesh = _solido_do_heightmap(altura_campo, px_mm)
        cobertura = 1.0

    # ── Limpeza / correções ───────────────────────────────────────────
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
        mesh.fix_normals()

    mesh.apply_translation(-mesh.bounds[0])  # apoia em z=0, canto na origem

    # Heightmap é sempre um bloco só; só a silhueta pode sair em pedaços
    corpos = len(mesh.split(only_watertight=False)) if modo == "silhueta" else 1

    output_path = OUTPUTS_DIR / f"{job_id}_image3d.{fmt}"
    mesh.export(str(output_path), file_type=fmt)

    dims = mesh.extents
    espessura_real = float(dims[2])
    if espessura_real < 0.8:
        avisos.append(f"Espessura total de {espessura_real:.2f}mm é frágil — considere espessura_max maior")
    if modo == "litofania" and e_min < 0.6:
        avisos.append(f"espessura_min {e_min}mm pode gerar furos — 0.8mm é o mínimo seguro pra bico 0.4")
    if px_mm < 0.25:
        avisos.append(f"Cada pixel virou {px_mm:.2f}mm, abaixo da largura do bico (0.4mm) — detalhe será perdido")
    if not mesh.is_watertight:
        avisos.append("Malha não ficou 100% fechada — rode /api/repair antes de fatiar")
    if corpos > 1:
        avisos.append(f"A peça saiu em {corpos} partes soltas — sem uma base ou moldura elas imprimem separadas")

    return {
        "job_id": job_id,
        "status": "done",
        "modo": modo,
        "output": str(output_path),
        "formato": fmt,
        "size_bytes": output_path.stat().st_size,
        "dimensoes_mm": {
            "largura": round(float(dims[0]), 2),
            "altura": round(float(dims[1]), 2),
            "espessura": round(espessura_real, 2),
        },
        "parametros": {
            "espessura_min": e_min,
            "espessura_max": e_max,
            "base_mm": base,
            "resolucao_grid": [int(nr), int(nc)],
            "resolucao_original": [int(orig_shape[0]), int(orig_shape[1])],
            "px_mm": round(px_mm, 3),
            "inverter": inverter,
            "limiar": limiar if modo == "silhueta" else None,
            "moldura_mm": moldura_mm or None,
        },
        "malha": {
            "vertices": int(len(mesh.vertices)),
            "faces": int(len(mesh.faces)),
            "watertight": bool(mesh.is_watertight),
            "volume_cm3": round(float(mesh.volume) / 1000.0, 2) if mesh.is_watertight else None,
            "corpos": corpos,
            "cobertura": round(cobertura, 3),
        },
        "avisos": avisos,
    }


# ── Leitura e preparo da imagem ───────────────────────────────────────

def _carregar_imagem(path: Path, resolucao: int) -> tuple[np.ndarray, np.ndarray | None, tuple]:
    """Abre a imagem, corrige orientação EXIF e devolve (cinza, alpha, shape original)."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)

    alpha = None
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        alpha = np.array(rgba.getchannel("A"), dtype=np.uint8)
        # Compõe sobre branco pra o cinza não escurecer nas áreas transparentes
        fundo = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(fundo, rgba)

    cinza = np.array(img.convert("L"), dtype=np.uint8)
    orig_shape = cinza.shape

    h, w = cinza.shape
    maior = max(h, w)
    if maior > resolucao:
        escala = resolucao / maior
        novo = (max(2, int(round(w * escala))), max(2, int(round(h * escala))))
        cinza = cv2.resize(cinza, novo, interpolation=cv2.INTER_AREA)
        if alpha is not None:
            alpha = cv2.resize(alpha, novo, interpolation=cv2.INTER_AREA)

    return cinza, alpha, orig_shape


def _normalizar(cinza: np.ndarray) -> np.ndarray:
    """uint8 → float32 0-1 com contraste esticado."""
    f = cinza.astype(np.float32)
    lo, hi = float(f.min()), float(f.max())
    if hi - lo < 1e-6:
        return np.zeros_like(f)
    return (f - lo) / (hi - lo)


def _reescalar(campo: np.ndarray) -> np.ndarray:
    """Estica o campo de volta pra 0-1. Campo constante vira zero (peça de espessura mínima)."""
    lo, hi = float(campo.min()), float(campo.max())
    if hi - lo < 1e-6:
        return np.zeros_like(campo)
    return (campo - lo) / (hi - lo)


def _px_para_mm(nr: int, nc: int, largura_mm: float, altura_mm: float | None) -> float:
    """Tamanho de um pixel em mm, preservando proporção da imagem."""
    if altura_mm is not None and altura_mm > 0:
        return min(largura_mm / max(1, nc - 1), altura_mm / max(1, nr - 1))
    return largura_mm / max(1, nc - 1)


def _detectar_modo(cinza: np.ndarray, alpha: np.ndarray | None) -> str:
    """Escolhe o modo pela cara da imagem: recorte/arte de linha → silhueta, resto → litofania."""
    if alpha is not None and (alpha < 250).mean() > 0.05:
        return "silhueta"

    hist = np.bincount(cinza.ravel(), minlength=256).astype(np.float32)
    hist /= hist.sum()
    extremos = float(hist[:24].sum() + hist[232:].sum())
    niveis = int((hist > 0.001).sum())
    if extremos > 0.85 or niveis < 24:
        return "silhueta"
    return "litofania"


def _mascara_silhueta(cinza: np.ndarray, alpha: np.ndarray | None, limiar: int, inverter: bool) -> np.ndarray:
    """Máscara booleana do que vira material sólido."""
    if alpha is not None and (alpha < 250).mean() > 0.05:
        mascara = alpha >= 128
    else:
        # Sem canal alpha: assume traço escuro sobre fundo claro
        mascara = cinza < int(limiar)
    if inverter:
        mascara = ~mascara
    return mascara


def _aplicar_moldura(altura: np.ndarray, px_mm: float, moldura_mm: float, z_topo: float) -> np.ndarray:
    """Cria uma borda cheia em volta (reforço estrutural da litofania)."""
    n = max(1, int(round(moldura_mm / px_mm)))
    out = altura.copy()
    out[:n, :] = z_topo
    out[-n:, :] = z_topo
    out[:, :n] = z_topo
    out[:, -n:] = z_topo
    return out


def _campo_profundidade(path: Path, nr: int, nc: int) -> np.ndarray | None:
    """Depth map do MiDaS reamostrado pro grid. None se torch/MiDaS não estiver disponível."""
    try:
        from app.services.midas_service import estimate_depth
        depth = estimate_depth(str(path))
    except Exception:
        return None
    if depth is None:
        return None
    return cv2.resize(depth.astype(np.float32), (nc, nr), interpolation=cv2.INTER_AREA)


# ── Construção de malha ───────────────────────────────────────────────

def _solido_do_heightmap(altura: np.ndarray, px_mm: float) -> trimesh.Trimesh:
    """
    Mapa de altura (mm) → sólido fechado.
    Topo = superfície da altura, fundo = plano z=0, laterais fechando as 4 bordas.
    """
    nr, nc = altura.shape
    xs = np.arange(nc, dtype=np.float64) * px_mm
    ys = -np.arange(nr, dtype=np.float64) * px_mm
    gx, gy = np.meshgrid(xs, ys)

    z_topo = np.maximum(altura.astype(np.float64), 1e-3)
    verts_topo = np.column_stack([gx.ravel(), gy.ravel(), z_topo.ravel()])
    verts_base = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(nr * nc)])
    n = nr * nc

    # Topo: dois triângulos por célula, normal +z
    i, j = np.meshgrid(np.arange(nr - 1), np.arange(nc - 1), indexing="ij")
    v0 = (i * nc + j).ravel()
    v1 = v0 + 1
    v2 = v0 + nc
    v3 = v2 + 1
    faces_topo = np.vstack([
        np.column_stack([v0, v2, v1]),
        np.column_stack([v1, v2, v3]),
    ])
    faces_base = faces_topo[:, ::-1] + n

    faces_lados = []
    # Borda de cima (linha 0) — normal +y
    a = np.arange(nc - 1)
    b = a + 1
    faces_lados.append(np.column_stack([a, b, b + n]))
    faces_lados.append(np.column_stack([a, b + n, a + n]))
    # Borda de baixo (última linha) — normal -y
    a = (nr - 1) * nc + np.arange(nc - 1)
    b = a + 1
    faces_lados.append(np.column_stack([a, a + n, b + n]))
    faces_lados.append(np.column_stack([a, b + n, b]))
    # Borda esquerda (coluna 0) — normal -x
    a = np.arange(nr - 1) * nc
    b = a + nc
    faces_lados.append(np.column_stack([a, a + n, b + n]))
    faces_lados.append(np.column_stack([a, b + n, b]))
    # Borda direita (última coluna) — normal +x
    a = np.arange(nr - 1) * nc + (nc - 1)
    b = a + nc
    faces_lados.append(np.column_stack([a, b, b + n]))
    faces_lados.append(np.column_stack([a, b + n, a + n]))

    vertices = np.vstack([verts_topo, verts_base])
    faces = np.vstack([faces_topo, faces_base] + faces_lados)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _extrudar_mascara(mascara: np.ndarray, px_mm: float, altura: float) -> trimesh.Trimesh:
    """
    Máscara booleana → sólido extrudado.
    Cada célula marcada vira topo + fundo; paredes só nas fronteiras da máscara.
    """
    nr, nc = mascara.shape
    # Lattice de cantos: (nr+1) x (nc+1), em dois níveis (z=0 e z=altura)
    lc = nc + 1
    xs = np.arange(nc + 1, dtype=np.float64) * px_mm
    ys = -np.arange(nr + 1, dtype=np.float64) * px_mm
    gx, gy = np.meshgrid(xs, ys)
    n = (nr + 1) * lc

    base = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(n)])
    topo = np.column_stack([gx.ravel(), gy.ravel(), np.full(n, float(altura))])
    vertices = np.vstack([base, topo])

    def canto(i, j, nivel):
        return i * lc + j + (nivel * n)

    ii, jj = np.nonzero(mascara)
    A = canto(ii, jj, 1)
    B = canto(ii, jj + 1, 1)
    C = canto(ii + 1, jj + 1, 1)
    D = canto(ii + 1, jj, 1)
    faces = [
        np.column_stack([A, D, C]), np.column_stack([A, C, B]),          # topo (+z)
        np.column_stack([A - n, B - n, C - n]), np.column_stack([A - n, C - n, D - n]),  # fundo (-z)
    ]

    pad = np.pad(mascara, 1, mode="constant", constant_values=False)
    # (vizinho ausente, cantos P e Q da parede) — ordem [P_base, P_topo, Q_topo, Q_base] = normal pra fora
    paredes = [
        (~pad[:-2, 1:-1], (0, 0), (0, 1)),   # acima livre  → +y
        (~pad[2:, 1:-1], (1, 1), (1, 0)),    # abaixo livre → -y
        (~pad[1:-1, :-2], (1, 0), (0, 0)),   # esquerda livre → -x
        (~pad[1:-1, 2:], (0, 1), (1, 1)),    # direita livre  → +x
    ]
    for livre, (pi, pj), (qi, qj) in paredes:
        bi, bj = np.nonzero(mascara & livre)
        if len(bi) == 0:
            continue
        P = canto(bi + pi, bj + pj, 0)
        Q = canto(bi + qi, bj + qj, 0)
        faces.append(np.column_stack([P, P + n, Q + n]))
        faces.append(np.column_stack([P, Q + n, Q]))

    mesh = trimesh.Trimesh(vertices=vertices, faces=np.vstack(faces), process=False)
    mesh.remove_unreferenced_vertices()
    return mesh
