"""Monta a pasta de entrega do chaveiro, com tudo pronto para imprimir.

Gera os cinco niveis (5 a 1 filamento), nas duas variantes, com previa 3D e um
LEIA-ME por nivel trazendo massa, custo e tempo estimados. Roda tudo do zero,
entao a pasta e reproduzivel: apagar e rodar de novo da o mesmo resultado.

    tools/keychain/.venv/bin/python -m tools.keychain.entrega
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import trimesh

from .build import build
from .params import PALETTE, Params
from .render3d import render
from .validate import check_slicer_ready, full_check

# Densidade e preco vem do servico que ja existe no projeto, para a entrega
# falar a mesma lingua do estimador da API.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
try:
    from app.services.print_estimator import FILAMENTS
except Exception:                                     # pragma: no cover
    FILAMENTS = {"pla": {"name": "PLA", "density": 1.24, "price_kg": 25.0}}

NOME_PT = {
    "purple": "roxo", "white": "branco", "pink": "rosa",
    "skin": "pele", "hair": "preto",
}

# Texto que o usuario le, entao vai acentuado -- diferente dos comentarios e
# docstrings do codigo, que seguem sem acento por consistencia com o resto.
RESUMO_NIVEL = {
    5: ("Paleta cheia: cada cor do desenho tem o seu filamento.",
        "Você tem AMS/MMU com 5 slots, ou extrusora dupla."),
    4: ("O preto passa a ser impresso em roxo. É a versão para AMS de 4 slots,"
        " que é o mais comum.",
        "O contorno preto deixa de ter cor própria, mas continua ali em relevo."),
    3: ("A pele vira branco — rosto e quimono na mesma cor, como um desenho de"
        " uma cor só. O degrau do queixo é o que segura a forma da cabeça.",
        "**É a que eu recomendo.** Melhor equilíbrio entre poucas trocas de cor"
        " e desenho fiel."),
    2: ("O rosa também vira branco. Só o relevo distingue a faixa do quimono.",
        "Duas cores resolvem quase tudo: o medalhão ainda lê perfeitamente."),
    1: ("Uma peça só, monocromática. O desenho fica inteiramente por conta do"
        " relevo, como numa medalha gravada.",
        "Imprime em qualquer impressora, sem nenhuma troca de filamento."),
}


def _massa_custo(volume_mm3: float, filamento: str = "pla") -> tuple[float, float]:
    """Massa em gramas e custo em dolares de um volume solido."""
    f = FILAMENTS.get(filamento, FILAMENTS["pla"])
    gramas = volume_mm3 / 1000.0 * f["density"]        # mm3 -> cm3 -> g
    return gramas, gramas / 1000.0 * f["price_kg"]


def _num(valor: float, casas: int = 0) -> str:
    """Numero no padrao brasileiro: ponto separa milhar, virgula separa decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _tabela_pecas(meshes: dict[str, trimesh.Trimesh]) -> tuple[str, float, float]:
    linhas = ["| Peça | Filamento | Volume | Massa | Triângulos |",
              "|---|---|---:|---:|---:|"]
    tot_v = tot_g = 0.0
    for nome, m in sorted(meshes.items(), key=lambda kv: -kv[1].volume):
        g, _ = _massa_custo(m.volume)
        tot_v += m.volume
        tot_g += g
        linhas.append(f"| `{nome}` | {NOME_PT.get(nome, nome)} | "
                      f"{_num(m.volume)} mm³ | {_num(g, 2)} g | "
                      f"{_num(len(m.faces))} |")
    linhas.append(f"| **total** | | **{_num(tot_v)} mm³** | "
                  f"**{_num(tot_g, 2)} g** | |")
    return "\n".join(linhas), tot_v, tot_g


def _leia_me_nivel(n: int, p: Params, mmu, glue, ok_mmu: bool, ok_glue: bool) -> str:
    tab_mmu, _, g_mmu = _tabela_pecas(mmu)
    tab_glue, _, g_glue = _tabela_pecas(glue)
    _, custo = _massa_custo(sum(m.volume for m in mmu.values()))
    o_que, quando = RESUMO_NIVEL[n]
    plural = "s" if n > 1 else ""

    return f"""# {n} filamento{plural} — chaveiro "AM Mulheres no Tatame"

{o_que}

**Quando usar:** {quando}

- Diâmetro **Ø{p.diameter:.0f} mm**, furo da argola **Ø{p.hole_diameter:.0f} mm**
- Espessura **{_num(p.total_height, 2)} mm**, altura total **{_num(p.overall_height, 1)} mm**
- Massa estimada **{_num(g_mmu, 1)} g** em PLA · ~US$ {_num(custo, 2)} de filamento
- Imprime com a **face plana na mesa**, sem suporte

![prévia](previa_3d.png)

---

## Opção A — impressão multicolor (`mmu.3mf`)

**Abra o `mmu.3mf`.** Ele já traz as {len(mmu)} peça{'s' if len(mmu) > 1 else ''} \
nomeada{'s' if len(mmu) > 1 else ''} e na posição certa: é só atribuir um filamento \
a cada uma.

{tab_mmu}

Os STLs avulsos (`mmu_*.stl`) estão aqui para quem preferir. Se usar eles,
importe todos juntos e responda **sim** ao *"carregar como objeto único"* —
eles compartilham a origem, mas se o fatiador recentralizar um sozinho o
alinhamento se perde. Com o 3MF isso não acontece.

## Opção B — peças coladas (`glue.3mf`)

Para impressora de extrusora única. A base roxa sai com os **rebaixos já
escavados** (folga de {_num(p.clearance, 1)} mm por lado) e os insertos encaixam neles.
Imprima separado, encaixe e fixe com cianoacrilato ou cola de PLA.

{tab_glue}

Massa total {_num(g_glue, 1)} g. Pele e preto não viram insertos: nesta escala
seriam cacos de 1 a 3 mm, impossíveis de manusear. Ficam em relevo na própria
base — pinte se quiser.

---

## Verificação

| Checagem | mmu | glue |
|---|:--:|:--:|
| Watertight, sólido, winding consistente | {'✅' if ok_mmu else '❌'} | {'✅' if ok_glue else '❌'} |
| Sem interpenetração entre cores (booleano 3D par a par) | {'✅' if ok_mmu else '❌'} | {'✅' if ok_glue else '❌'} |
| União == soma dos volumes (sem vão nem sobra) | {'✅' if ok_mmu else '❌'} | {'✅' if ok_glue else '❌'} |
| Nada flutuando sem apoio | {'✅' if ok_mmu else '❌'} | {'✅' if ok_glue else '❌'} |
| Arquivo **gravado e relido** sem aresta defeituosa | {'✅' if ok_mmu else '❌'} | {'✅' if ok_glue else '❌'} |

A última linha é a que importa: o fatiador lê o arquivo, não o objeto em
memória. Duas vezes neste projeto uma malha íntegra em memória voltou aberta
do disco.
"""


def montar(destino: Path, imagem: str, niveis=(5, 4, 3, 2, 1)) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    resumo = {}

    for n in niveis:
        p = Params().with_overrides(n_colors=n)
        pasta = destino / f"{n}-filamento{'s' if n > 1 else ''}"
        pasta.mkdir(exist_ok=True)
        print(f"\n=== {n} filamento(s) -> {pasta} ===")

        guardado = {}
        okays = {}
        for variante in ("mmu", "glue"):
            meshes, slabs = build(p, imagem, variante)
            rep = full_check(meshes, slabs, p)
            errs, _ = check_slicer_ready(meshes)
            ok = rep.ok and not errs
            okays[variante] = ok
            for e in rep.errors + errs:
                print(f"   ERRO ({variante}): {e}")

            for nome, m in sorted(meshes.items()):
                m.export(str(pasta / f"{variante}_{nome}.stl"))
            cena = trimesh.Scene()
            for nome, m in sorted(meshes.items()):
                cena.add_geometry(m, geom_name=nome, node_name=nome)
            cena.export(str(pasta / f"{variante}.3mf"))
            guardado[variante] = meshes
            print(f"   {variante}: {len(meshes)} peca(s), auditoria "
                  f"{'OK' if ok else 'REPROVADA'}")

        render(guardado["mmu"], str(pasta / "previa_3d.png"),
               size=1000, supersample=2, elev=58, azim=-90, dist=3.85)

        (pasta / "LEIA-ME.md").write_text(
            _leia_me_nivel(n, p, guardado["mmu"], guardado["glue"],
                           okays["mmu"], okays["glue"]), encoding="utf-8")

        vol = sum(m.volume for m in guardado["mmu"].values())
        g, custo = _massa_custo(vol)
        resumo[n] = {"pecas": len(guardado["mmu"]), "espessura": p.total_height,
                     "gramas": g, "custo": custo, "ok": all(okays.values())}

    (destino / "LEIA-ME.md").write_text(_indice(resumo), encoding="utf-8")
    return resumo


def _indice(resumo: dict) -> str:
    linhas = ["| Pasta | Peças | Espessura | Massa | Filamento | Verificado |",
              "|---|:--:|---:|---:|---:|:--:|"]
    for n in sorted(resumo, reverse=True):
        r = resumo[n]
        linhas.append(
            f"| `{n}-filamento{'s' if n > 1 else ''}/` | {r['pecas']} | "
            f"{_num(r['espessura'], 2)} mm | {_num(r['gramas'], 1)} g | "
            f"US$ {_num(r['custo'], 2)} | {'✅' if r['ok'] else '❌'} |")
    tabela = "\n".join(linhas)

    return f"""# Chaveiro "AM Mulheres no Tatame" — arquivos para impressão

Ø40 mm · furo Ø4 mm · face plana na mesa · **sem suporte**.

Cinco versões da mesma peça, mudando só **quantos filamentos** ela usa. Cada
pasta tem os arquivos, a prévia em 3D e um `LEIA-ME.md` próprio.

{tabela}

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
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monta a pasta de entrega.")
    ap.add_argument("--out", default="entrega_chaveiro")
    ap.add_argument("--image", default="tools/keychain/assets/ref_hires.webp")
    ap.add_argument("--zip", action="store_true", help="tambem gera um .zip")
    a = ap.parse_args(argv)

    destino = Path(a.out)
    if destino.exists():
        shutil.rmtree(destino)
    resumo = montar(destino, a.image)

    if a.zip:
        shutil.make_archive(str(destino), "zip", root_dir=destino.parent,
                            base_dir=destino.name)
        print(f"\nzip: {destino}.zip")

    print(f"\npasta pronta: {destino}")
    return 0 if all(r["ok"] for r in resumo.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
