# ÓRION POKER — modelos 3D para impressão (Bambu Lab)

Redesign moderno do logo **ÓRION POKER** (base: `Paulo_Poker_02alt.pdf`) como peça
física em relevo multicolor, com a estrela em destaque como ponto mais alto da peça
e o nome/escudo "saindo" da base em camadas.

## Formatos

| Modelo | Script | Dimensões | Saída |
|---|---|---|---|
| Cartão 9×5 (formato empresa) | `build_orion_card_9x5.py` | **90 × 50 × 10 mm** | `output_9x5/` |
| Escudo grande (parede/mesa) | `build_orion_shield.py` | 110 × 109 × 6,2 mm | `output/` |

## Como imprimir (Bambu Studio)

1. Abra o arquivo `.3mf` (`output_9x5/orion_poker_card_9x5.3mf` ou
   `output/orion_poker_shield.3mf`). Cada elemento vem como objeto separado,
   já posicionado e com a cor indicada no nome.
2. Com AMS: atribua um filamento a cada grupo de cor —
   **preto** (base), **dourado** (borda, nome, chevron, estrela destaque),
   **branco** (constelação), **vermelho** (copas/ouros), **prata** (espadas/paus).
   Sem AMS: use os STLs de `stl/` com troca de filamento por altura (pause em Z).
3. Perfil sugerido: layer 0,2 mm; 10–15 % de preenchimento; sem suportes
   (todos os relevos são extrusões verticais diretas da base).

## Alturas de relevo (cartão 9×5)

- Base preta: 0 → 6,0 mm
- Moldura/borda do escudo (ouro): 6,0 → 7,2/7,4 mm
- Constelação (branco): 6,0 → 7,0/7,2 mm
- POKER + linha (ouro): 6,0 → 7,6 mm
- Naipes: 6,0 → 7,2 mm
- Nome ÓRION (ouro): 6,0 → 8,4 mm
- **Estrela em destaque (ouro): 6,0 → 10,0 mm** — o ponto mais alto da peça

## Regenerar

```bash
pip install shapely trimesh numpy matplotlib mapbox_earcut
python3 build_orion_card_9x5.py   # cartão 9×5
python3 build_orion_shield.py     # escudo grande
```

Os scripts são paramétricos: dimensões, alturas de relevo e cores estão nas
constantes no topo de cada arquivo.
