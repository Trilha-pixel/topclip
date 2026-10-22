"""
Contador: o numero conta ate o valor dito. Ideia do Number Ticker do Magic UI (MIT).

    contador.quadro(f, inicio, fim, estilo, valor=3000, prefixo="R$", sufixo="/mês",
                    rotulo="por cliente")

O numero vem grande no acento; prefixo e sufixo menores, na cor do texto, na mesma linha
de base. Os digitos ocupam celulas de largura fixa (o numero nao treme enquanto conta), e
o conjunto encolhe para caber em `largura`. A contagem desacelera (curva de movimento do
perfil) e termina em `conta` quadros. Contorno e sombra dura vem da tipografia do estilo.
"""
from PIL import Image, ImageDraw

from .base import cola, lin, vazio

EXEMPLO = dict(inicio=0, fim=96, f=48, dados=dict(valor=3000, prefixo="R$", sufixo="/mês",
                                                     rotulo="por cliente, todo mês"))


def formata(v, casas=0):
    """3000 -> '3.000'; 2.5 com casas=1 -> '2,5' (separadores do portugues)."""
    s = f"{abs(v):,.{casas}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"{'-' if v < 0 else ''}{s}"


def _celulas(texto, fonte):
    cel = max(fonte.getlength(d) for d in "0123456789")
    return [cel if c.isdigit() else fonte.getlength(c) for c in texto]


def _linha_numero(numero, prefixo, sufixo, f_num, f_peq, cor_num, cor_peq, estilo):
    """Prefixo, numero e sufixo numa linha so, alinhados pela linha de base."""
    gap = f_num.size * 0.08
    wp = f_peq.getlength(prefixo) + gap if prefixo else 0
    cel = _celulas(numero, f_num)
    ws = gap + f_peq.getlength(sufixo) if sufixo else 0
    e_num, e_peq = estilo.efeitos(f_num), estilo.efeitos(f_peq)
    extra = e_num["contorno"] + max(map(abs, e_num["sombra"]))
    asc, desc = f_num.getmetrics()
    lay = Image.new("RGBA", (int(wp + sum(cel) + ws) + 4 + 2 * extra, asc + desc + 2 * extra),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    base = asc + extra

    def escreve(x, txt, fonte, cor, e):
        kw = dict(stroke_width=e["contorno"], stroke_fill=e["cor_contorno"]) if e["contorno"] else {}
        if e["sombra"] != (0, 0):
            d.text((x + e["sombra"][0], base + e["sombra"][1]), txt, font=fonte,
                   fill=e["cor_contorno"], anchor="ls", **kw)
        d.text((x, base), txt, font=fonte, fill=cor, anchor="ls", **kw)

    x = 2.0 + extra
    if prefixo:
        escreve(x, prefixo, f_peq, cor_peq, e_peq)
        x += wp
    for c, w in zip(numero, cel):
        dx = (w - f_num.getlength(c)) / 2 if c.isdigit() else 0
        escreve(x + dx, c, f_num, cor_num, e_num)
        x += w
    if sufixo:
        escreve(x + gap, sufixo, f_peq, cor_peq, e_peq)
    return lay


def quadro(f, inicio, fim, estilo, valor, de=0, prefixo="", sufixo="", casas=0, rotulo=None,
           centro=(540, 860), tamanho=230, conta=30, cor="acento", largura=900):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    prefixo, sufixo = estilo.caixa(prefixo), estilo.caixa(sufixo)
    v = de + (valor - de) * estilo.e_mov(lin(f, inicio, inicio + conta))
    v = round(v, casas) if casas else round(v)

    # cabe na largura pelo tamanho FINAL: o numero so cresce enquanto conta
    preto = (0, 0, 0, 255)
    final = _linha_numero(formata(valor, casas), prefixo, sufixo, estilo.fonte("numero", tamanho, 700),
                          estilo.fonte("numero", int(tamanho * 0.4), 600), preto, preto, estilo)
    if final.width > largura:
        tamanho = int(tamanho * largura / final.width)
    f_num = estilo.fonte("numero", tamanho, 700)
    f_peq = estilo.fonte("numero", int(tamanho * 0.4), 600)
    num = _linha_numero(formata(v, casas), prefixo, sufixo, f_num, f_peq, estilo.cor(cor),
                        estilo.cor("texto"), estilo)

    dy = (1 - ent) * estilo.desloca - sai * 18
    s = estilo.escala(ent)
    cy = centro[1] - (tamanho * 0.2 if rotulo else 0)
    cola(tela, num, (centro[0], cy), k, dy, escala=s)
    if rotulo:
        rot = estilo.linha(estilo.caixa(rotulo), estilo.fonte("apoio", max(40, int(tamanho * 0.22)), 500),
                           estilo.cor("apoio"))
        cola(tela, rot, (centro[0], cy + num.height / 2 + rot.height / 2 + tamanho * 0.06),
             k, dy * 1.4, escala=s)
    return tela
