"""
As previas de um estilo, renderizadas dentro de um projeto temporario. Quem chama e o
`./topclip estilo previa <id>`; rodar a mao: `python -m pecas.previa <destino>` na raiz
de um projeto de motion.

    --capa NOME     arquivo da capa (a cena --cena, ou a primeira do compose, no END)
    --pecas         tambem cada peca declarada pelo estilo, no EXEMPLO dela, sobre o fundo
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
TAMANHO = (540, 960)            # metade do quadro: a galeria mostra pequeno


def _salva(im, f):
    f.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").resize(TAMANHO, Image.LANCZOS).save(f, optimize=True)
    print(f.relative_to(f.parents[2]) if len(f.parents) > 2 else f)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("destino")
    ap.add_argument("--capa", default="capa.png")
    ap.add_argument("--pecas", action="store_true")
    ap.add_argument("--cena")
    a = ap.parse_args(argv)
    destino = Path(a.destino)

    import compose as C
    import pecas as P
    estilo = P.carregar(ROOT)

    nome = a.cena or next(iter(C.SCENES))
    fn, st, fx = C.SCENES[nome]
    if fx is None:
        import kit as K
        im = K.plate_falso()
        im.alpha_composite(fn(st["END"], overlay_only=True))
    else:
        im = C.finish(fn(st["END"]), **fx)
    _salva(im, destino / a.capa)

    if a.pecas:
        declaradas = json.loads((ROOT / "estilo" / "estilo.json").read_text(encoding="utf-8"))["pecas"]
        for p in declaradas:
            mod = P.TODAS[p]
            ex = mod.EXEMPLO
            dados = dict(ex["dados"])
            if p == "lottie" and not (ROOT / dados["arquivo"]).is_file():
                achados = sorted((ROOT / "estilo" / "lottie").glob("*.json"))
                if not achados:
                    print(f"lottie: o estilo nao traz nenhum .json em lottie/ — previa pulada")
                    continue
                dados["arquivo"] = str(achados[0].relative_to(ROOT))
            c = P.fundo(ex["f"], ex["inicio"] - 100, ex["fim"] + 100, estilo)
            c.alpha_composite(mod.quadro(ex["f"], ex["inicio"], ex["fim"], estilo, **dados))
            _salva(c, destino / "pecas" / f"{p}.png")


if __name__ == "__main__":
    main()
