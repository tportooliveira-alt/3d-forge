#!/usr/bin/env python3
"""
Converte uma imagem em STL imprimível, sem precisar subir a API.

Exemplos:
    python scripts/imagem_para_stl.py foto.jpg
    python scripts/imagem_para_stl.py foto.jpg --modo litofania --largura 120 --moldura 3
    python scripts/imagem_para_stl.py logo.png --modo silhueta --espessura-max 5
    python scripts/imagem_para_stl.py paisagem.jpg --modo profundidade --largura 150
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.image3d_service import gerar_modelo, MODOS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Imagem → STL pronto pra impressão 3D")
    p.add_argument("imagem", help="Caminho da imagem (png, jpg, webp, bmp, tiff)")
    p.add_argument("--modo", default="auto", choices=MODOS)
    p.add_argument("--largura", type=float, default=100.0, help="Largura da peça em mm (padrão 100)")
    p.add_argument("--altura", type=float, default=None, help="Altura máxima em mm (mantém proporção)")
    p.add_argument("--espessura-max", type=float, default=None, help="Espessura/relevo máximo em mm")
    p.add_argument("--espessura-min", type=float, default=None, help="Espessura mínima em mm (litofania)")
    p.add_argument("--base", type=float, default=None, help="Base sólida sob o relevo em mm")
    p.add_argument("--resolucao", type=int, default=260, help="Maior lado do grid em pontos")
    p.add_argument("--inverter", action="store_true", help="Inverte claro/escuro")
    p.add_argument("--suavizar", type=float, default=1.0, help="Blur antes de gerar o relevo")
    p.add_argument("--gamma", type=float, default=1.0, help="Contraste do relevo (<1 realça sombras)")
    p.add_argument("--limiar", type=int, default=128, help="Limiar de corte da silhueta (0-255)")
    p.add_argument("--moldura", type=float, default=0.0, help="Borda sólida em volta, em mm")
    p.add_argument("--formato", default="stl", choices=["stl", "obj", "glb", "ply", "3mf"])
    p.add_argument("--saida", default=None, help="Caminho do arquivo de saída")
    args = p.parse_args()

    job_id = str(uuid.uuid4())[:8]
    r = gerar_modelo(
        job_id=job_id,
        image_path=args.imagem,
        modo=args.modo,
        largura_mm=args.largura,
        altura_mm=args.altura,
        espessura_max=args.espessura_max,
        espessura_min=args.espessura_min,
        base_mm=args.base,
        resolucao=args.resolucao,
        inverter=args.inverter,
        suavizar=args.suavizar,
        gamma=args.gamma,
        limiar=args.limiar,
        moldura_mm=args.moldura,
        formato=args.formato,
    )

    if r["status"] == "error":
        print(f"erro: {r['message']}", file=sys.stderr)
        return 1

    if args.saida:
        destino = Path(args.saida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        Path(r["output"]).replace(destino)
        r["output"] = str(destino)

    print(json.dumps(r, indent=2, ensure_ascii=False))
    for aviso in r["avisos"]:
        print(f"aviso: {aviso}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
