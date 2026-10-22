"""
Cartao: rotulo, titulo e texto num cartao da superficie do estilo. Serve em tela cheia ou
sobre o video (deixe o rosto livre: centro no terco de cima).

    cartao.quadro(f, inicio, fim, estilo, rotulo="dica", titulo="Suba o preço antes",
                  texto="Cliente que paga mais cobra menos e indica mais.")

Em fundo claro o cartao tem sombra difusa; em fundo escuro, borda fina.
"""
from PIL import Image

from .base import bloco, cola, com_sombra, linha, quebra, retangulo, vazio

EXEMPLO = dict(inicio=0, fim=96, f=48, dados=dict(
    rotulo="dica", titulo="Suba o preço antes de crescer",
    texto="Cliente que paga mais exige menos e indica mais."))


def montar(estilo, titulo, texto=None, rotulo=None, largura=880, tamanho=72):
    pad = int(tamanho * 0.78)
    miolo = largura - 2 * pad
    partes, gap = [], int(tamanho * 0.32)
    if rotulo:
        partes.append(linha(rotulo.upper(), estilo.fonte("rotulo", max(36, int(tamanho * 0.48))),
                            estilo.cor("acento"), tracking=3))
    ft = estilo.fonte("titulo", tamanho, 700)
    partes.append(bloco(quebra(ft, titulo, miolo), ft, estilo.cor("texto"), 1.1, "esquerda")[0])
    if texto:
        fx = estilo.fonte("apoio", int(tamanho * 0.56), 500)
        partes.append(bloco(quebra(fx, texto, miolo), fx, estilo.cor("apoio"), 1.38, "esquerda")[0])
    h = sum(p.height for p in partes) + gap * (len(partes) - 1) + 2 * pad
    borda = (2, estilo.cor("linha")) if estilo.escuro else None
    card = retangulo(largura, h, tamanho * 0.5, estilo.cor("superficie"), borda)
    y = pad
    for p in partes:
        card.alpha_composite(p, (pad - 2, y))
        y += p.height + gap
    return card if estilo.escuro else com_sombra(card, desfoque=28, opacidade=0.14, dy=12)


def quadro(f, inicio, fim, estilo, titulo, texto=None, rotulo=None, centro=(540, 640),
           largura=880, tamanho=72):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    card = montar(estilo, titulo, texto, rotulo, largura, tamanho)
    cola(tela, card, centro, min(1.0, ent) * (1 - sai), (1 - ent) * 40 - sai * 20)
    return tela
