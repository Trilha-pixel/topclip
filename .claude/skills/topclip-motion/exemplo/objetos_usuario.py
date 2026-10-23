"""
Os seus objetos desenhados — molde de `minha-biblioteca/objetos.py` (copie daqui).

Quando a fala pede um objeto que a biblioteca nao tem (`./topclip objetos` lista o que
ja existe), o Claude desenha ele AQUI, uma vez, e ele passa a sair nos tres lapis (Limpo,
Impacto, Luxo e os remixes deles). Todo `./topclip py` de um projeto de motion leva este
arquivo para o projeto como `objetos_meus.py`; a peca `objeto` encontra os nomes de
OBJETOS sozinha. Nome igual ao de um oficial nao entra.

Como desenhar (o mesmo de `biblioteca/pecas/objetos.py`):
  - a caixa tem largura 1; a altura e sua (devolva-a);
  - cada forma tem um PAPEL: corpo, face, detalhe, destaque, traco, vazado. O lapis do
    estilo decide a tinta de cada papel — nunca ponha cor aqui;
  - a ordem importa: o que vem antes fica atras;
  - `p` (0..1) e a animacao propria (o vapor subindo, a barra crescendo); com p=1 o
    objeto esta pronto;
  - sinal, nao retrato: a anatomia que se reconhece em 1 segundo.

Confira antes de usar: `./topclip objetos` desenha cada objeto seu nos tres lapis, diz o
que estiver errado e grava a folha em minha-biblioteca/objetos.png (o painel mostra).
A primeira frase da docstring e a descricao que aparece na lista e no painel.
"""
import math

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


# Registre aqui cada objeto seu: o nome e o que a cena pede em P.objeto.quadro(..., "nome").
# A xicara acima e o exemplo: registre se for usar (OBJETOS = {"xicara": xicara}), ou apague.
OBJETOS = {}

