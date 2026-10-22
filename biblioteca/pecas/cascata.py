"""
Cascata: itens que entram um por um, cada um num cartao com o marcador do acento.
Ideia do Animated List do Magic UI (MIT).

    cascata.quadro(f, inicio, fim, estilo, itens=["Cobra mais", "Atende menos", "Lucra mais"],
                   entradas=[0, 14, 30])

`entradas`: o quadro em que cada item entra — trave cada um na palavra do transcript.
Sem elas, o intervalo e de 3 x o stagger do perfil (no minimo 8 quadros).
"""
from .base import circulo, cola, com_sombra, lin, linha, quebra, retangulo, traco, vazio

EXEMPLO = dict(inicio=0, fim=110, f=70, dados=dict(
    itens=["Cobra mais caro", "Atende menos clientes", "Lucra mais no fim do mês"]))

MARCADORES = ("check", "numero")


def _cartao(texto, num, estilo, largura, tamanho, marcador, pc):
    fonte = estilo.fonte("apoio", tamanho, 600)
    pad, icone = int(tamanho * 0.62), int(tamanho * 1.05)
    linhas = quebra(fonte, estilo.caixa(texto), largura - 3 * pad - icone)
    passo = int(tamanho * 1.22)
    alt_l = sum(fonte.getmetrics())
    h = max(icone, passo * (len(linhas) - 1) + alt_l) + 2 * pad
    borda = (2, estilo.cor("linha")) if estilo.escuro else None
    card = retangulo(largura, h, tamanho * 0.5, estilo.cor("superficie"), borda)
    ic = circulo(icone, estilo.cor("acento"))
    if marcador == "check":
        ic.alpha_composite(traco(icone, icone, [(icone * .29, icone * .52), (icone * .44, icone * .66),
                                                (icone * .72, icone * .36)],
                                 icone * 0.1, estilo.cor("sobre_acento"), pc))
    else:
        n = linha(str(num), estilo.fonte("numero", int(icone * 0.5), 700), estilo.cor("sobre_acento"))
        ic.alpha_composite(n, ((icone - n.width) // 2, (icone - n.height) // 2))
    card.alpha_composite(ic, (pad, (h - icone) // 2))
    ty = (h - (passo * (len(linhas) - 1) + alt_l)) // 2
    extra = estilo.pad(fonte, estilo.cor("texto")) - 2
    for i, l in enumerate(linhas):
        card.alpha_composite(estilo.linha(l, fonte, estilo.cor("texto")),
                             (2 * pad + icone - extra, ty + i * passo - extra))
    return card if estilo.escuro else com_sombra(card, desfoque=22, opacidade=0.12, dy=8, margem=40)


def quadro(f, inicio, fim, estilo, itens, entradas=None, centro=(540, 900), largura=880,
           tamanho=54, marcador="check", espaco=26):
    if marcador not in MARCADORES:
        raise ValueError(f"marcador '{marcador}': use {', '.join(MARCADORES)}")
    tela = vazio()
    if not inicio <= f <= fim or not itens:
        return tela
    _, sai = estilo.envelope(f, inicio, fim)
    if entradas is None:
        passo = max(8, 3 * estilo.stagger)
        entradas = [inicio + i * passo for i in range(len(itens))]
    margem = 0 if estilo.escuro else 40
    cards = []
    for i, (t, e) in enumerate(zip(itens, entradas)):
        pc = lin(f, e + estilo.q_entrada * 0.5, e + estilo.q_entrada * 0.5 + 8)
        cards.append(_cartao(t, i + 1, estilo, largura, tamanho, marcador, pc))
    alturas = [c.height - 2 * margem for c in cards]
    total = sum(alturas) + espaco * (len(cards) - 1)
    y = centro[1] - total / 2
    for c, a, e in zip(cards, alturas, entradas):
        k = estilo.entrada(f, e)
        if k > 0:
            cola(tela, c, (centro[0], y + a / 2), min(1.0, k) * (1 - sai),
                 (1 - k) * (estilo.desloca * 1.2) - sai * 18, escala=estilo.escala(k))
        y += a + espaco
    return tela
