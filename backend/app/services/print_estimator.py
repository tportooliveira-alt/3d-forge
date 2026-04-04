"""
PRINT ESTIMATOR SERVICE
Calcula tempo, material e custo estimado de impressão 3D.
DIFERENCIAL: nenhum concorrente de IA faz isso.
"""

import trimesh
from pathlib import Path

# Perfis de impressora pré-configurados
PRINTER_PROFILES = {
    "ender3": {
        "name": "Creality Ender 3",
        "build_volume": [220, 220, 250],  # mm
        "nozzle": 0.4,
        "layer_height": 0.2,
        "print_speed": 50,  # mm/s
        "travel_speed": 150,
        "infill_default": 20,
    },
    "prusa_mk4": {
        "name": "Prusa MK4",
        "build_volume": [250, 210, 220],
        "nozzle": 0.4,
        "layer_height": 0.2,
        "print_speed": 70,
        "travel_speed": 200,
        "infill_default": 15,
    },
    "bambu_p1s": {
        "name": "Bambu Lab P1S",
        "build_volume": [256, 256, 256],
        "nozzle": 0.4,
        "layer_height": 0.2,
        "print_speed": 100,
        "travel_speed": 300,
        "infill_default": 15,
    },
    "generic": {
        "name": "Genérica FDM",
        "build_volume": [200, 200, 200],
        "nozzle": 0.4,
        "layer_height": 0.2,
        "print_speed": 50,
        "travel_speed": 150,
        "infill_default": 20,
    },
}

# Filamentos comuns
FILAMENTS = {
    "pla": {"name": "PLA", "density": 1.24, "price_kg": 25.0, "temp": 210},
    "petg": {"name": "PETG", "density": 1.27, "price_kg": 30.0, "temp": 235},
    "abs": {"name": "ABS", "density": 1.04, "price_kg": 28.0, "temp": 240},
    "tpu": {"name": "TPU", "density": 1.21, "price_kg": 40.0, "temp": 225},
}


def estimate_print(stl_path: str, printer: str = "generic", filament: str = "pla", infill: int = 20, scale: float = 1.0) -> dict:
    """Estima tempo, material e custo de impressão."""
    path = Path(stl_path)
    if not path.exists():
        return {"status": "error", "message": "STL não encontrado"}

    try:
        mesh = trimesh.load(str(path), force="mesh")
    except Exception as e:
        return {"status": "error", "message": f"Falha ao carregar: {e}"}

    if scale != 1.0:
        mesh.apply_scale(scale)

    prof = PRINTER_PROFILES.get(printer, PRINTER_PROFILES["generic"])
    fil = FILAMENTS.get(filament, FILAMENTS["pla"])

    # Dimensões do modelo
    bounds = mesh.bounds
    dims = (bounds[1] - bounds[0])
    x, y, z = dims[0], dims[1], dims[2]

    # Checa se cabe na impressora
    bv = prof["build_volume"]
    cabe = bool(x <= bv[0] and y <= bv[1] and z <= bv[2])

    # Volume do modelo (cm³)
    if mesh.is_watertight:
        volume_cm3 = abs(mesh.volume) / 1000
    else:
        volume_cm3 = mesh.convex_hull.volume / 1000 * 0.6

    # Material necessário
    shell_ratio = 1.0 - (infill / 100 * 0.7)  # parede + infill
    volume_real = volume_cm3 * (0.3 + 0.7 * infill / 100)  # paredes sempre sólidas
    peso_g = volume_real * fil["density"]
    comprimento_m = peso_g / (fil["density"] * 3.14159 * (1.75 / 2 / 10) ** 2) / 100

    # Custo
    custo = (peso_g / 1000) * fil["price_kg"]

    # Tempo estimado (simplificado)
    n_layers = z / prof["layer_height"]
    # Perímetro médio por camada + infill
    perimetro_medio = (x + y) * 2 * 3  # 3 paredes
    infill_dist = x * y * (infill / 100) / prof["nozzle"]
    dist_por_camada = perimetro_medio + infill_dist
    dist_total_mm = dist_por_camada * n_layers
    tempo_print_s = dist_total_mm / prof["print_speed"]
    tempo_travel_s = n_layers * (x + y) / prof["travel_speed"]
    tempo_total_min = (tempo_print_s + tempo_travel_s) / 60

    # Formatar tempo
    horas = int(tempo_total_min // 60)
    minutos = int(tempo_total_min % 60)

    return {
        "status": "done",
        "modelo": {
            "dimensoes_mm": {"x": round(x, 1), "y": round(y, 1), "z": round(z, 1)},
            "volume_cm3": round(volume_cm3, 2),
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "watertight": bool(mesh.is_watertight),
        },
        "impressora": {
            "nome": prof["name"],
            "cabe": cabe,
            "escala_sugerida": round(min(bv[0]/max(x,0.1), bv[1]/max(y,0.1), bv[2]/max(z,0.1), 1.0), 2) if not cabe else 1.0,
        },
        "material": {
            "filamento": fil["name"],
            "peso_g": round(peso_g, 1),
            "comprimento_m": round(comprimento_m, 1),
            "custo_usd": round(custo, 2),
        },
        "impressao": {
            "camadas": int(n_layers),
            "layer_height_mm": prof["layer_height"],
            "infill_percent": infill,
            "tempo_estimado": f"{horas}h{minutos:02d}min",
            "tempo_minutos": round(tempo_total_min),
        },
    }
