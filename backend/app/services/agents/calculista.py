"""
AGENTE CALCULISTA
Cruza landmarks do Analista com proporções anatômicas reais.
Gera depth map calibrado e landmarks 3D com Z real.
Zero LLM - só matemática.
"""

import cv2
import numpy as np
from app.services.agents import log

# Proporções anatômicas médias (adulto, em mm)
ANATOMIA = {
    "altura_rosto": 120.0,       # testa ao queixo
    "largura_rosto": 140.0,      # zigomático a zigomático
    "profundidade_nariz": 18.0,  # ponta do nariz ao plano do rosto
    "profundidade_olho": 8.0,    # recuo da órbita
    "profundidade_boca": 5.0,    # lábios
    "profundidade_testa": 12.0,  # curvatura da testa
    "profundidade_queixo": 15.0, # projeção do queixo
}

# Mapa de profundidade por região (índices MediaPipe)
DEPTH_REGIONS = {
    "nariz": {"indices": [1, 2, 3, 4, 5, 6, 195, 197], "depth": 1.0},
    "olho_e": {"indices": [33, 133, 157, 158, 159, 160, 161, 246], "depth": -0.4},
    "olho_d": {"indices": [263, 362, 384, 385, 386, 387, 388, 466], "depth": -0.4},
    "boca": {"indices": [61, 291, 13, 14, 78, 308], "depth": 0.3},
    "testa": {"indices": [10, 67, 109, 338, 297], "depth": 0.65},
    "queixo": {"indices": [152, 148, 176, 377, 400], "depth": 0.8},
    "bochecha_e": {"indices": [123, 117, 118, 119, 120], "depth": 0.5},
    "bochecha_d": {"indices": [352, 346, 347, 348, 349], "depth": 0.5},
}


def executar(ctx: dict) -> dict:
    """Cruza landmarks com anatomia real e gera depth map."""
    log(ctx, "CALCULISTA", "Cruzando landmarks com proporções anatômicas...")

    landmarks = ctx["landmarks"]
    w, h = ctx["resolucao"]["w"], ctx["resolucao"]["h"]

    # 1. ESCALA: calcular fator px → mm usando landmarks reais
    testa = landmarks[10]
    queixo = landmarks[152]
    altura_rosto_px = np.linalg.norm((queixo[:2] - testa[:2]) * [w, h])
    px_para_mm = ANATOMIA["altura_rosto"] / max(altura_rosto_px, 1)

    log(ctx, "CALCULISTA", f"Escala: {px_para_mm:.3f} mm/px (rosto={altura_rosto_px:.0f}px)")

    # 2. MEDIDAS: cruzar distâncias entre landmarks com escala
    olho_e = landmarks[33]
    olho_d = landmarks[263]
    boca_e = landmarks[61]
    boca_d = landmarks[291]

    largura_olhos_px = np.linalg.norm((olho_d[:2] - olho_e[:2]) * [w, h])
    largura_boca_px = np.linalg.norm((boca_d[:2] - boca_e[:2]) * [w, h])

    ctx["medidas"] = {
        "altura_rosto_mm": round(ANATOMIA["altura_rosto"], 1),
        "largura_olhos_mm": round(largura_olhos_px * px_para_mm, 1),
        "largura_boca_mm": round(largura_boca_px * px_para_mm, 1),
        "profundidade_nariz_mm": ANATOMIA["profundidade_nariz"],
        "px_para_mm": round(px_para_mm, 4),
    }

    # 3. PROPORÇÕES: terços faciais (cruza landmarks verticais)
    olhos_y = ((olho_e[1] + olho_d[1]) / 2) * h
    testa_y = testa[1] * h
    nariz_y = landmarks[1][1] * h
    queixo_y = queixo[1] * h

    terco_sup = (olhos_y - testa_y) * px_para_mm
    terco_med = (nariz_y - olhos_y) * px_para_mm
    terco_inf = (queixo_y - nariz_y) * px_para_mm
    total = terco_sup + terco_med + terco_inf

    ctx["proporcoes"] = {
        "terco_superior_mm": round(terco_sup, 1),
        "terco_medio_mm": round(terco_med, 1),
        "terco_inferior_mm": round(terco_inf, 1),
        "ratio_olhos_rosto": round(largura_olhos_px / max(altura_rosto_px, 1), 3),
        "simetria": _calcular_simetria(landmarks, w),
    }
    log(ctx, "CALCULISTA", f"Terços: {terco_sup:.1f}/{terco_med:.1f}/{terco_inf:.1f}mm")

    # 4. DEPTH MAP: MiDaS (IA) cruzado com regiões anatômicas
    try:
        from app.services.midas_service import estimate_depth, depth_to_mm
        depth_raw = estimate_depth(ctx["image_path"])
        if depth_raw is not None:
            # Redimensionar se necessário
            if depth_raw.shape != (h, w):
                depth_raw = cv2.resize(depth_raw, (w, h))
            depth_midas = depth_to_mm(depth_raw, ANATOMIA["profundidade_nariz"])
            log(ctx, "CALCULISTA", f"MiDaS depth OK: min={depth_midas.min():.1f} max={depth_midas.max():.1f}mm")

            # Cruzar MiDaS com regiões anatômicas (70% MiDaS + 30% anatômico)
            depth_anatomico = _gerar_depth_map(landmarks, w, h, ctx["pose"])
            depth_map = depth_midas * 0.7 + depth_anatomico * 0.3
            log(ctx, "CALCULISTA", "Depth cruzado: 70% MiDaS + 30% anatomia")
        else:
            raise ValueError("MiDaS retornou None")
    except Exception as e:
        log(ctx, "CALCULISTA", f"MiDaS falhou ({e}), usando fallback anatômico")
        depth_map = _gerar_depth_map(landmarks, w, h, ctx["pose"])

    ctx["depth_map"] = depth_map
    log(ctx, "CALCULISTA", f"Depth map final: {depth_map.shape}")

    # 5. LANDMARKS 3D: adicionar Z calibrado a cada landmark
    landmarks_3d = landmarks.copy()
    for i, lm in enumerate(landmarks_3d):
        px_x = int(lm[0] * w)
        px_y = int(lm[1] * h)
        px_x = np.clip(px_x, 0, w - 1)
        px_y = np.clip(px_y, 0, h - 1)
        # Z do depth map + Z original do MediaPipe (cruzamento!)
        z_depth = depth_map[px_y, px_x]
        z_mp = lm[2]
        # Média ponderada: depth map tem mais peso que MediaPipe Z
        landmarks_3d[i, 2] = z_depth * 0.7 + (-z_mp * ANATOMIA["profundidade_nariz"]) * 0.3

    ctx["landmarks_3d"] = landmarks_3d
    log(ctx, "CALCULISTA", f"Landmarks 3D calibrados: {len(landmarks_3d)} pontos")

    ctx["status"] = "calculo_ok"
    return ctx


def _calcular_simetria(landmarks: np.ndarray, w: int) -> float:
    """Cruza lado esquerdo vs direito do rosto. 1.0 = perfeito."""
    centro_x = landmarks[1][0]  # nariz como eixo
    pares = [(33, 263), (133, 362), (61, 291), (67, 297), (123, 352)]

    diffs = []
    for e, d in pares:
        dist_e = abs(landmarks[e][0] - centro_x)
        dist_d = abs(landmarks[d][0] - centro_x)
        ratio = min(dist_e, dist_d) / max(dist_e, dist_d, 0.001)
        diffs.append(ratio)

    return round(float(np.mean(diffs)), 3)


def _gerar_depth_map(landmarks: np.ndarray, w: int, h: int, pose: dict) -> np.ndarray:
    """Gera depth map cruzando regiões anatômicas + landmarks + pose."""
    depth = np.zeros((h, w), dtype=np.float32)

    # Base: Z do MediaPipe interpolado
    for lm in landmarks:
        px_x = int(lm[0] * w)
        px_y = int(lm[1] * h)
        if 0 <= px_x < w and 0 <= px_y < h:
            depth[px_y, px_x] = -lm[2] * ANATOMIA["profundidade_nariz"]

    # Preencher regiões com profundidades anatômicas
    for region, data in DEPTH_REGIONS.items():
        pts = []
        for idx in data["indices"]:
            if idx < len(landmarks):
                pts.append([int(landmarks[idx][0] * w), int(landmarks[idx][1] * h)])

        if len(pts) >= 3:
            pts = np.array(pts, dtype=np.int32)
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillConvexPoly(mask, pts, 255)
            region_depth = data["depth"] * ANATOMIA["profundidade_nariz"]
            # Cruza: onde mask > 0, mistura depth existente com anatômico
            valid = mask > 0
            depth[valid] = depth[valid] * 0.4 + region_depth * 0.6

    # Suavizar (Gaussian blur forte pra transições naturais)
    depth = cv2.GaussianBlur(depth, (31, 31), 0)

    # Compensar pose: se rosto virado, ajustar depth
    if abs(pose["yaw"]) > 5:
        correction = np.linspace(0, pose["yaw"] / 45 * 3, w)
        depth += correction[np.newaxis, :]
        log({"log": []}, "CALCULISTA", f"Compensando yaw={pose['yaw']:.1f}°")

    # Normalizar para 0..max_depth_mm
    depth = np.clip(depth, 0, None)
    if depth.max() > 0:
        depth = depth / depth.max() * ANATOMIA["profundidade_nariz"]

    return depth
