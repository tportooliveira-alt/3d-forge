"""
AGENTE ANALISTA
Lê a foto, detecta 468 landmarks, avalia qualidade e pose.
Alimenta: Calculista, Escultor, Inspetor.
"""

import cv2
import numpy as np
import mediapipe as mp
from pathlib import Path
from app.services.agents import log


def executar(ctx: dict) -> dict:
    """Executa análise completa da foto."""
    log(ctx, "ANALISTA", "Iniciando análise da foto...")

    img = cv2.imread(ctx["image_path"])
    if img is None:
        ctx["status"] = "error"
        log(ctx, "ANALISTA", "Erro: não consegui ler a imagem")
        return ctx

    h, w = img.shape[:2]
    ctx["resolucao"] = {"w": w, "h": h}

    # 1. Qualidade
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    nitidez = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brilho = float(gray.mean())
    contraste = float(gray.std())
    score_q = min(100, max(0, int(
        (min(nitidez, 500) / 500 * 40) +
        (30 - abs(brilho - 127) / 80 * 20) +
        (min(contraste, 80) / 80 * 30)
    )))
    ctx["qualidade"] = {
        "nitidez": round(nitidez, 1),
        "brilho": round(brilho, 1),
        "contraste": round(contraste, 1),
        "score": score_q,
    }
    log(ctx, "ANALISTA", f"Qualidade: {score_q}/100 (nitidez={nitidez:.0f})")

    # 2. Landmarks (468 pontos)
    mp_face = mp.solutions.face_mesh
    with mp_face.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            ctx["status"] = "error"
            log(ctx, "ANALISTA", "Erro: nenhum rosto detectado")
            return ctx

        face = results.multi_face_landmarks[0]
        landmarks = np.array([[lm.x, lm.y, lm.z] for lm in face.landmark])
        ctx["landmarks"] = landmarks
        log(ctx, "ANALISTA", f"Detectados {len(landmarks)} landmarks")

    # 3. Pose (cruzando landmarks chave)
    nariz = landmarks[1]
    queixo = landmarks[152]
    olho_e = landmarks[33]
    olho_d = landmarks[263]

    dist_ne = abs(nariz[0] - olho_e[0])
    dist_nd = abs(nariz[0] - olho_d[0])
    yaw = (dist_ne - dist_nd) / max(dist_ne, dist_nd, 0.001) * 45

    olhos_y = (olho_e[1] + olho_d[1]) / 2
    range_y = queixo[1] - olhos_y
    pitch = ((nariz[1] - olhos_y) / max(range_y, 0.001) - 0.4) * 60

    roll = float(np.degrees(np.arctan2(olho_d[1] - olho_e[1], olho_d[0] - olho_e[0])))

    ctx["pose"] = {
        "yaw": round(float(yaw), 1),
        "pitch": round(float(pitch), 1),
        "roll": round(float(roll), 1),
        "frontal": abs(yaw) < 15 and abs(pitch) < 15 and abs(roll) < 10,
    }
    log(ctx, "ANALISTA", f"Pose: yaw={yaw:.1f} pitch={pitch:.1f} roll={roll:.1f} frontal={ctx['pose']['frontal']}")

    ctx["status"] = "analise_ok"
    return ctx
