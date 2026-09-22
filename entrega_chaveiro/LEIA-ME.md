# Chaveiro "AM Mulheres no Tatame" — arquivos para impressão

Ø40 mm · furo Ø4 mm · face plana na mesa · **sem suporte**.

Cinco versões da mesma peça, mudando só **quantos filamentos** ela usa. Cada
pasta tem os arquivos, a prévia em 3D e um `LEIA-ME.md` próprio.

| Pasta | Peças | Espessura | Massa | Filamento | Verificado |
|---|:--:|---:|---:|---:|:--:|
| `5-filamentos/` | 5 | 5,60 mm | 7,1 g | US$ 0,18 | ✅ |
| `4-filamentos/` | 4 | 5,60 mm | 7,1 g | US$ 0,18 | ✅ |
| `3-filamentos/` | 3 | 5,92 mm | 7,1 g | US$ 0,18 | ✅ |
| `2-filamentos/` | 2 | 6,24 mm | 7,1 g | US$ 0,18 | ✅ |
| `1-filamento/` | 1 | 6,56 mm | 7,2 g | US$ 0,18 | ✅ |

**Comece pela pasta `3-filamentos/`** se estiver em dúvida: é o melhor
equilíbrio entre poucas trocas de cor e desenho fiel.

---

## O que tem em cada pasta

| Arquivo | Para quê |
|---|---|
| `mmu.3mf` | **Abra este.** Multicolor, todas as peças num arquivo, já posicionadas |
| `mmu_*.stl` | As mesmas peças avulsas, se o seu fatiador preferir |
| `glue.3mf` / `glue_*.stl` | Versão para extrusora única: base com rebaixos + insertos para colar |
| `previa_3d.png` | Como a peça fica, renderizada da geometria real |
| `LEIA-ME.md` | Massa, custo, tabela de peças e o resultado da verificação |

## Como reduzir filamento sem perder o desenho

Juntar cores sozinho apagaria as fronteiras entre elas. Então, a cada fusão, os
grupos que se juntam recebem **alturas diferentes** — escalonadas em múltiplos
da altura de camada. O que a cor deixa de separar, o relevo separa. Por isso a
peça fica um pouco mais grossa a cada redução, e por isso a versão de um
filamento só ainda se lê.

## Gerar de novo

```
python3 -m venv tools/keychain/.venv
tools/keychain/.venv/bin/pip install -r tools/keychain/requirements.txt
tools/keychain/.venv/bin/python -m tools.keychain.entrega
```

Apagar esta pasta e rodar de novo produz exatamente os mesmos arquivos.
