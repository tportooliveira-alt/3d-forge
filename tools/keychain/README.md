# Chaveiro "AM Mulheres no Tatame" — gerador de STL multi-peça

Gera os STLs imprimíveis do chaveiro a partir do render de referência, em duas
variantes que saem do **mesmo modelo paramétrico**.

```
python3 -m venv tools/keychain/.venv
tools/keychain/.venv/bin/pip install -r tools/keychain/requirements.txt
tools/keychain/.venv/bin/python -m tools.keychain.cli --variant both --check-slicer
```

Saída em `tools/keychain/out/` (não versionada).

**Abra o `.3mf`, não os STLs.** Cada variante gera um `mmu.3mf` / `glue.3mf`
com todas as peças nomeadas e já na posição certa: o fatiador abre um arquivo
só e você atribui o filamento de cada parte. Com STLs soltos você teria que
importar cinco e torcer para o slicer não recentralizar nenhum. Os STLs
continuam sendo gerados para quem precisar deles avulsos.

`--check-slicer` roda a auditoria pesada (booleano 3D par a par). Ela é o que
garante que o arquivo entra limpo:

| Checagem | O que pega |
|---|---|
| `is_volume`, winding, faces degeneradas | malha que o fatiador rejeita ou fecha errado |
| interseção 3D real entre cada par de cores | interpenetração — filamento disputando o mesmo espaço |
| união == soma dos volumes | vão ou sobreposição em qualquer lugar, num número só |
| cada ilha tem material abaixo | relevo flutuando no ar |

Foi ela que pegou um defeito que passava despercebido: a base da variante
colada saía com duas faces de área zero, sobreviviam à gravação e o arquivo
voltava `is_watertight=False` na releitura — embora o objeto em memória
parecesse íntegro. O fatiador lê o arquivo, não a memória.

---

## Qual variante usar

### A — `mmu_*.stl` (AMS / MMU / extrusora dupla)

Um STL por cor, **todos no mesmo sistema de coordenadas**, sem sobreposição
entre eles. Juntos formam o medalhão completo.

No slicer (Bambu Studio / PrusaSlicer / OrcaSlicer):

1. Importe os 5 arquivos de uma vez.
2. Quando perguntar "carregar como objeto único?" / *"load as a single object"*,
   responda **sim** (em inglês costuma ser *"Multi-part object"*).
3. Atribua um filamento a cada parte: roxo, branco, rosa, pele, preto.
4. Imprima com a face plana na mesa — não precisa de suporte.

> Um AMS padrão tem 4 slots e esta variante usa 5 cores. Para caber em 4,
> rode com `--colors 4`: o cabelo passa a ser impresso em roxo.

### B — `glue_*.stl` (extrusora única, peças coladas)

- `glue_purple.stl` — corpo roxo **já com os rebaixos (bolsos)** escavados.
- `glue_white.stl` e `glue_pink.stl` — insertos que encaixam nos bolsos.

Os bolsos têm **0,2 mm de folga** por lado (`--clearance`). Imprima as três
peças separadamente, encaixe os insertos e fixe com cola de cianoacrilato ou
cola de PLA.

Pele e cabelo **não** viram insertos nesta variante: nesta escala seriam cacos
de 1–3 mm, impossíveis de manusear e colar. Eles ficam em relevo na própria
base roxa — pinte se quiser, ou deixe monocromático.

---

## Geometria

Peça 2,5D: costas planas em z=0, relevo só na frente.

```
z 0,00 → 3,00   Disco base roxo Ø40 + aba com furo Ø4
z 3,00 → 3,55   Fundo do sulco (r 17,8 → 18,4 mm)
z 3,00 → 4,25   Campo interno elevado (r < 17,8 mm)
z 3,00 → 4,45   Aro externo (r 18,4 → 20,0 mm)
z 4,25 → 5,25   Figura, "M" e texto em relevo sobre o campo
```

Ø40 mm · furo Ø4 mm · espessura 5,25 mm · altura total ~46,5 mm.

**As cotas foram medidas no render, não copiadas da folha técnica.** A folha
enviada tem texto corrompido ("Attam hole", "Smoothess collourre smoothanss") e
cotas que se contradizem — a vista explodida soma 6,5 mm e o corte lateral diz
6,0 mm. O que se mediu, com o disco normalizado a Ø40 mm, foi:

| Elemento | Medida |
|---|---|
| Sulco campo↔aro | r 17,8 → 18,4 mm (vale de L\* no perfil radial) |
| Banda do texto | r 13,0 → 16,1 mm, maiúscula 3,05 mm |
| Letra "M" | 12,2 × 14,9 mm |
| Furo da argola | centro em Y +21,5 mm, Ø3,8 mm |

Tudo isso está em `params.py`, num lugar só.

---

## Como a arte é obtida

| Elemento | Origem | Por quê |
|---|---|---|
| Figura e "M" | traçados do render | é a arte original |
| "MULHERES NO TATAME" | gerado de fonte real | a maiúscula tem 3 mm ≈ 29 px no render; traçar isso vira mingau |
| Disco, aba, aro, sulco | geometria paramétrica | são formas exatas, não há o que traçar |

O traçado usa **classificação supervisionada por cromaticidade LAB**, não
k-means: rodando k-means no render, os clusters saem separados por *iluminação*
e o roxo vira três clusters, enquanto o rosa (1,8 % dos pixels) se perde.

Duas decisões que valem registro, porque não são óbvias e custaram depuração:

- **Fundo vs. figura é resolvido topologicamente**, não por cor. O fundo é a
  mancha roxa que alcança a borda do campo; tudo que não é fundo recebe
  obrigatoriamente uma cor de arte. Sem isso, as sombras duras que o render
  projeta em volta de cada relevo abriam canais de roxo dentro do quimono.
- **Cabelo e branco têm quase a mesma cromaticidade** (o cabelo é escuro
  *neutro*, a\*≈+5, não roxo-escuro). Só o L\* os separa, e por isso o par
  `l_min`/`l_max` de cada cor é obrigatório na competição.

As máscaras são **super-amostradas 4× antes de contornar**: contornar na
resolução nativa devolve uma escada de pixel, e a simplificação posterior só
escolhe quais degraus manter.

---

## Parâmetros úteis

| Flag | Default | Para quê |
|---|---|---|
| `--variant` | `both` | `mmu`, `glue` ou `both` |
| `--colors` | 5 | `4` funde o cabelo no roxo (AMS de 4 slots) |
| `--diameter` | 40 | diâmetro do disco (mm) |
| `--clearance` | 0.2 | folga dos bolsos na variante colada |
| `--pocket-depth` | 0.8 | profundidade dos bolsos |
| `--min-feature` | 0.55 | detalhe mais fino que isso é removido |
| `--art-h` | 1.0 | altura do relevo da arte |
| `--text-cap-height` | 3.05 | altura das maiúsculas |
| `--text-xscale` | 0.92 | compressão horizontal do texto |
| `--preview` | — | gera PNG de conferência |

## QA

`validate.py` roda automaticamente e **bloqueia a exportação** se algo reprovar:

- cada malha `is_watertight`, volume positivo, dentro da caixa esperada;
- **nenhuma sobreposição entre cores** — verificada em 2D, faixa de Z por faixa
  de Z (`intersection().area ≈ 0`), que é bem mais confiável do que booleano 3D;
- relevo com pelo menos 2 camadas de altura;
- aviso quando muita área de uma cor está perto do limite do bico.

Para comparar com a referência lado a lado:

```python
from tools.keychain.compare import render
from tools.keychain.params import Params
render(Params(), "tools/keychain/assets/ref_render.jpg",
       "tools/keychain/out/cmp.png", zoom="figura")   # ou "full"
```
