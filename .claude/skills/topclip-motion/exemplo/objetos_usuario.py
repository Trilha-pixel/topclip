"""
Os seus objetos desenhados — molde de `minha-biblioteca/objetos.py` (copie daqui).

Quando a fala pede um objeto que a biblioteca nao tem (uma xicara, um carro, um troféu),
o Claude desenha ele AQUI, uma vez, e ele passa a sair nos tres lapis (Limpo, Impacto,
Luxo e os remixes deles). O `./topclip motion novo` copia este arquivo para cada projeto
como `objetos_meus.py`; a peca `objeto` encontra os nomes de OBJETOS sozinha.

Como desenhar (o mesmo de `biblioteca/pecas/objetos.py`):
  - a caixa tem largura 1; a altura e sua (devolva-a);
  - cada forma tem um PAPEL: corpo, face, detalhe, destaque, traco, vazado. O lapis do
    estilo decide a tinta de cada papel — nunca ponha cor aqui;
  - a ordem importa: o que vem antes fica atras;
  - `p` (0..1) e a animacao propria (o vapor subindo, a barra crescendo); com p=1 o
    objeto esta pronto;
  - sinal, nao retrato: a anatomia que se reconhece em 1 segundo.

Confira na folha antes de usar: `./topclip py <projeto>/objetos_meus.py <projeto>`
grava <projeto>/11_qa/objetos_meus.png com cada objeto seu nos tres lapis.
"""
import math
import sys
from pathlib import Path

from pecas.lapis import arco, circulo, elipse, linha, poli, ret  # noqa: F401


def xicara(p=1.0):
    """Xicara de cafe com o vapor subindo (a pausa, a manha, o 'tomando um cafe')."""
    f = [elipse(0.46, 0.86, 0.36, 0.06, "detalhe")]                       # pires
    f.append(arco(0.74, 0.62, 0.10, -80, 80, 0.035))                      # alca
    f.append(poli([(0.18, 0.44), (0.74, 0.44), (0.68, 0.80), (0.24, 0.80)], "corpo"))
    f.append(elipse(0.46, 0.44, 0.28, 0.045, "face"))                     # o cafe
    for i, x in enumerate((0.36, 0.46, 0.56)):                            # vapor
        k = max(0.0, min(1.0, p * 1.4 - i * 0.2))
        if k > 0:
            onda = [(x + 0.025 * math.sin(j / 20 * 2 * math.pi + i), 0.38 - 0.24 * k * j / 20)
                    for j in range(21)]
            f.append(linha(onda, 0.018, "destaque"))
    return f, 0.96, {"rotulos": [(0.46, 0.93)]}


OBJETOS = {"xicara": xicara}


if __name__ == "__main__":
    # a folha de conferencia: cada objeto seu nos tres lapis, no estilo do projeto
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.path.insert(0, str(raiz))
    import pecas as P
    from PIL import Image

    estilo = P.carregar(raiz)
    folhas = [P.objeto.folha(estilo, list(OBJETOS), lapis=l, cols=max(1, len(OBJETOS)))
              for l in ("limpo", "impacto", "luxo")]
    out = Image.new("RGBA", (max(x.width for x in folhas), sum(x.height for x in folhas)))
    y = 0
    for x in folhas:
        out.alpha_composite(x, (0, y))
        y += x.height
    destino = raiz / "11_qa" / "objetos_meus.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    out.convert("RGB").save(destino)
    print(destino)
