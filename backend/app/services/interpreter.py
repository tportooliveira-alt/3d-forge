KEYWORDS = {
    "face3d": ["rosto", "face", "foto", "retrato", "busto", "cabeça", "escultura", "réplica", "imprimir rosto", "3d do rosto", "modelo do rosto"],
    "convert": ["converter", "converte", "conversão", "transformar", "transforma", "convert", "virar stl", "gerar stl"],
    "repair": ["corrigir", "corrige", "reparar", "repara", "consertar", "conserta", "repair", "fix", "arrumar", "arruma", "suavizar"],
    "analyze": ["analisar", "analisa", "análise", "inspecionar", "verificar", "checar", "diagnóstico", "printable", "imprimível"],
    "estimate": ["estimar", "estimativa", "tempo de impressão", "custo", "material", "filamento", "quanto custa", "quanto tempo", "impressão"],
    "export": ["exportar", "export", "baixar", "download", "glb", "obj", "fbx", "ply", "formato"],
}


def interpret_command(text: str) -> str | None:
    """Interpreta texto e retorna ação correspondente."""
    text = text.lower().strip()

    for action, words in KEYWORDS.items():
        for word in words:
            if word in text:
                return action

    return None
