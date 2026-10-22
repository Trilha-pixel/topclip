"""
Objeto: um objeto desenhado (`objetos.py`) entrando em cena com o lapis do estilo.

    objeto.quadro(f, inicio, fim, estilo, "relogio", de=(23, 0), ate=(3, 0), anima_em=20)
    objeto.quadro(f, inicio, fim, estilo, "grafico_barras", rotulos=["1", "2", "3", "4"])

E o mesmo fluxo do Papel — a frase tem objeto, o objeto e desenhado e entra preso a
palavra — com o desenho de cada estilo: chapado no Limpo, adesivo no Impacto, gravura de
latao no Luxo (que se desenha na entrada). `anima_em`/`dur`: quando a animacao propria do
objeto (ponteiro andando, barra crescendo) comeca e quanto dura, em quadros.
"""
from PIL import Image, ImageDraw

from .base import cola, lin, vazio
from .lapis import desenha
from .objetos import OBJETOS

EXEMPLO = dict(inicio=0, fim=96, f=60, dados=dict(nome="relogio", de=(23, 0), ate=(3, 0),
                                                    anima_em=12, dur=36))


def quadro(f, inicio, fim, estilo, nome, centro=(540, 900), largura=600, anima_em=None, dur=24,
           rotulos=None, lapis=None, **params):
    if nome not in OBJETOS:
        raise ValueError(f"objeto '{nome}' nao existe: {', '.join(sorted(OBJETOS))}")
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    lapis = lapis or estilo.r.get("lapis") or "limpo"
    ent, sai = estilo.envelope(f, inicio, fim)
    ini = inicio if anima_em is None else anima_em
    # a animacao propria segue a FALA (a barra chega na palavra), nao a curva do estilo: a
    # curva energica do Impacto jogava o crescimento todo para o comeco. Os objetos ja
    # suavizam cada parte por dentro.
    formas, altura, ancoras = OBJETOS[nome](p=lin(f, ini, ini + dur), **params)
    # o lapis luxo se desenha: a entrada dele e o traco correndo, mais lenta que um fade,
    # mas sempre terminando antes da saida da peca (objeto que entra tarde na cena)
    sobra = (fim - estilo.q_saida) - inicio
    traco = estilo.entrada(f, inicio, max(estilo.q_entrada, min(estilo.q_entrada * 2.2, sobra)))
    lay = desenha(formas, largura, altura, estilo, lapis, traco)

    if rotulos and ancoras.get("rotulos"):
        m = int(largura * 0.12)
        fonte = estilo.fonte("numero", int(largura * 0.075), 700)
        for txt, (x, y) in zip(rotulos, ancoras["rotulos"]):
            r = estilo.linha(estilo.caixa(str(txt)), fonte, estilo.cor("texto"))
            lay.alpha_composite(r, (int(x * largura + m - r.width / 2), int(y * largura + m)))

    k = min(1.0, ent * (3 if lapis == "luxo" else 1)) * (1 - sai)
    cola(tela, lay, centro, k, (1 - ent) * estilo.desloca - sai * 18, escala=estilo.escala(ent))
    return tela


def folha(estilo, nomes=None, cel=270, cols=4, lapis=None):
    """Os objetos (todos, ou `nomes`) desenhados no lapis do estilo, com o nome embaixo:
    a previa do desenho do estilo (preview/objetos.png) e a conferencia de objeto novo."""
    lapis = lapis or estilo.r.get("lapis") or "limpo"
    nomes = list(nomes or OBJETOS)
    rot = 34
    linhas = (len(nomes) + cols - 1) // cols
    out = Image.new("RGBA", (cols * cel, linhas * (cel + rot)), estilo.cor("fundo"))
    d = ImageDraw.Draw(out)
    fonte = estilo.fonte("apoio", int(cel * 0.075), 500)
    for i, nome in enumerate(nomes):
        formas, altura, _ = OBJETOS[nome](p=1.0)
        lay = desenha(formas, int(cel * 0.8), altura, estilo, lapis, 1.0)
        lay.thumbnail((cel, cel), Image.LANCZOS)
        x, y = (i % cols) * cel, (i // cols) * (cel + rot)
        out.alpha_composite(lay, (x + (cel - lay.width) // 2, y + (cel - lay.height) // 2))
        w = d.textlength(nome, font=fonte)
        d.text((x + (cel - w) / 2, y + cel + 2), nome, font=fonte, fill=estilo.cor("apoio"))
    return out
