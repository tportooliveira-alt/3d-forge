from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query

from app.core.config import ALLOWED_IMAGES
from app.services.file_service import save_upload
from app.services.image3d_service import gerar_modelo, MODOS, DEFAULTS

router = APIRouter()


@router.post("/image3d")
async def image3d(
    file: UploadFile = File(...),
    modo: str = Query("auto", description=f"Modo: {', '.join(MODOS)}"),
    largura_mm: float = Query(100.0, gt=1, le=1000, description="Largura da imagem inteira em mm (na silhueta a peça sai menor se houver margem)"),
    altura_mm: float | None = Query(None, gt=1, le=1000, description="Altura máxima em mm (mantém proporção)"),
    espessura_max: float | None = Query(None, gt=0, le=200, description="Espessura/relevo máximo em mm"),
    espessura_min: float | None = Query(None, ge=0, le=200, description="Espessura mínima em mm (litofania)"),
    base_mm: float | None = Query(None, ge=0, le=100, description="Base sólida sob o relevo em mm"),
    resolucao: int = Query(260, ge=32, le=800, description="Maior lado do grid em pontos"),
    inverter: bool = Query(False, description="Inverte claro/escuro (ou dentro/fora na silhueta)"),
    suavizar: float = Query(1.0, ge=0, le=10, description="Blur gaussiano antes de gerar o relevo"),
    gamma: float = Query(1.0, gt=0, le=5, description="Ajuste de contraste do relevo (<1 realça sombras)"),
    limiar: int = Query(128, ge=1, le=254, description="Limiar de corte da silhueta (0-255)"),
    moldura_mm: float = Query(0.0, ge=0, le=50, description="Borda sólida em volta, em mm"),
    recorte: bool | None = Query(None, description="Recorta o fundo liso. Padrão: liga no relevo/profundidade, desliga na litofania"),
    forma_mm: float = Query(0.0, ge=0, le=50, description="Alto-relevo: raio da forma em mm. >0 separa forma de detalhe e permite relevo profundo sem virar picos"),
    detalhe_mm: float | None = Query(None, ge=0, le=50, description="Espessura reservada ao detalhe fino em mm (padrão: 12% do relevo)"),
    sujeito_mascara: str | None = Query(None, description="Caminho de uma máscara de primeiro plano (branco = sujeito)"),
    salto_mm: float = Query(0.0, ge=0, le=200, description="Quanto o sujeito da máscara sobe acima do resto, em mm"),
    sujeito_borda_mm: float = Query(2.0, ge=0, le=20, description="Suavização da borda do salto, em mm"),
    textos: str | None = Query(None, description='Gravações em relevo, JSON: [{"texto":"BF","x":0.7,"y":0.62,"tamanho":0.05,"altura_mm":3}]'),
    formato: str = Query("stl", description="Saída: stl, obj, glb, ply, 3mf"),
):
    """Qualquer imagem → sólido imprimível (litofania, relevo, silhueta ou profundidade IA)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGES:
        raise HTTPException(400, f"Envie uma imagem: {ALLOWED_IMAGES}")

    lista_textos = None
    if textos:
        import json
        try:
            lista_textos = json.loads(textos)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"textos não é JSON válido: {e}")
        if not isinstance(lista_textos, list) or not all(isinstance(i, dict) for i in lista_textos):
            raise HTTPException(400, "textos deve ser uma lista de objetos")

    try:
        saved = save_upload(file)
    except ValueError as e:
        raise HTTPException(413, str(e))

    result = gerar_modelo(
        job_id=saved["job_id"],
        image_path=saved["path"],
        modo=modo,
        largura_mm=largura_mm,
        altura_mm=altura_mm,
        espessura_max=espessura_max,
        espessura_min=espessura_min,
        base_mm=base_mm,
        resolucao=resolucao,
        inverter=inverter,
        suavizar=suavizar,
        gamma=gamma,
        limiar=limiar,
        moldura_mm=moldura_mm,
        recorte=recorte,
        forma_mm=forma_mm,
        detalhe_mm=detalhe_mm,
        textos=lista_textos,
        sujeito_mascara=sujeito_mascara,
        salto_mm=salto_mm,
        sujeito_borda_mm=sujeito_borda_mm,
        formato=formato,
    )

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    try:
        from app.services.firebase_service import save_job
        save_job(result["job_id"], {"tipo": "image3d", **result})
    except Exception:
        pass

    return result


@router.get("/image3d/modos")
async def listar_modos():
    """Modos disponíveis e seus defaults em mm."""
    descricoes = {
        "auto": "Detecta sozinho: recorte/arte de linha → silhueta, foto → litofania",
        "litofania": "Espessura varia com o brilho (escuro = grosso). Frente plana, luz por trás",
        "relevo": "Mapa de altura: brilho vira relevo sobre uma base sólida",
        "silhueta": "Recorta por limiar e extruda — logo, ícone, chaveiro, stencil",
        "profundidade": "Profundidade estimada por IA (MiDaS) vira relevo 3D",
    }
    return {
        "modos": [
            {"nome": m, "descricao": descricoes[m], "defaults_mm": DEFAULTS.get(m)}
            for m in MODOS
        ]
    }
