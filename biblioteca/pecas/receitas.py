"""
Receitas por registro, para os estilos que desenham com lapis (Limpo, Impacto, Luxo e os
remixes deles). E o mesmo papel das receitas do kit do Papel (`lib/kit.py`): a cena que a
fala pede, ja montada, travada nas palavras — so que vestindo o estilo do projeto.

    Registro              Quando                                  Receita
    Objeto em destaque    a frase nomeia uma coisa concreta       objeto_em_destaque
    Processo              "de X para Y", causa e efeito           processo
    Dado                  numero, crescimento, proporcao          dado

Os registros de texto (frase marcada, lista, troca de palavra, cartao sobre o video) sao
as pecas direto. Nunca repita o registro em cenas vizinhas: tres "objeto em destaque"
seguidos leem como a mesma cena, por mais que o objeto mude.

Toda receita devolve a camada RGBA 1080x1920 da cena no quadro `f` (cena overlay: o fundo
entra e sai em fade). `inicio`/`fim` = a cena; os `*_em` = a palavra que dispara cada parte.
"""
from . import desfoque, marca_texto, objeto
from .base import cola, fundo, retangulo, vazio


def pilula(f, inicio, estilo, texto, centro, tamanho=64):
    """A etiqueta curta no acento (o "MVP" da fita-etiqueta do Papel)."""
    ent = estilo.entrada(f, inicio)
    tela = vazio()
    if ent <= 0:
        return tela
    fonte = estilo.fonte("titulo", tamanho, 700)
    t = estilo.linha(estilo.caixa(texto), fonte, estilo.cor("sobre_acento"))
    p = retangulo(t.width + tamanho * 1.1, t.height + tamanho * 0.4, tamanho * 0.34, estilo.cor("acento"))
    p.alpha_composite(t, ((p.width - t.width) // 2, (p.height - t.height) // 2))
    return cola(tela, p, centro, min(1.0, ent), (1 - ent) * estilo.desloca, escala=estilo.escala(ent))


def objeto_em_destaque(f, inicio, fim, estilo, nome, titulo=None, etiqueta=None, objeto_em=None,
                       anima_em=None, dur=36, etiqueta_em=None, largura=640, **params):
    """Titulo em cima, o objeto no centro, uma etiqueta embaixo. Ex.: "uma madrugada" ->
    relogio com os ponteiros andando; "MVP" na etiqueta."""
    c = fundo(f, inicio, fim, estilo)
    oi = objeto_em if objeto_em is not None else inicio + 6
    if titulo:
        c.alpha_composite(marca_texto.quadro(f, inicio + 4, fim, estilo, texto=titulo,
                                             centro=(540, 380), tamanho=96))
    c.alpha_composite(objeto.quadro(f, oi, fim, estilo, nome, centro=(540, 960), largura=largura,
                                    anima_em=anima_em if anima_em is not None else oi + 8,
                                    dur=dur, **params))
    if etiqueta:
        c.alpha_composite(pilula(f, etiqueta_em if etiqueta_em is not None else oi + 20, estilo,
                                 etiqueta, (540, 1520)))
    return c


def processo(f, inicio, fim, estilo, de, para, titulo=None, de_em=None, seta_em=None,
             para_em=None, params_de=None, params_para=None, rotulos=(None, None)):
    """De um objeto ao outro, de cima para baixo, com a seta grossa entre eles. Cada parte
    entra na sua palavra: `de_em` (o ponto de partida), `seta_em` (o "vira", "gera",
    "leva a"), `para_em` (o resultado)."""
    c = fundo(f, inicio, fim, estilo)
    di = de_em if de_em is not None else inicio + 6
    si = seta_em if seta_em is not None else di + 18
    pi = para_em if para_em is not None else si + 12
    if titulo:
        c.alpha_composite(marca_texto.quadro(f, inicio + 4, fim, estilo, texto=titulo,
                                             centro=(540, 300), tamanho=84))
    c.alpha_composite(objeto.quadro(f, di, fim, estilo, de, centro=(540, 640), largura=470,
                                    anima_em=di + 6, **(params_de or {})))
    # a seta comeca abaixo do rotulo do `de` (y 880) e termina antes do `para`
    c.alpha_composite(objeto.quadro(f, si, fim, estilo, "seta", centro=(540, 1045), largura=200,
                                    anima_em=si, dur=14, angulo=90))
    c.alpha_composite(objeto.quadro(f, pi, fim, estilo, para, centro=(540, 1340), largura=470,
                                    anima_em=pi + 6, **(params_para or {})))
    # o rotulo entra junto do objeto: o "para" costuma cair no fim da cena
    for txt, y, ini in ((rotulos[0], 880, di + 6), (rotulos[1], 1615, pi + 2)):
        if txt:
            c.alpha_composite(desfoque.quadro(f, ini, fim, estilo, texto=txt, centro=(540, y),
                                              tamanho=52))
    return c


def dado(f, inicio, fim, estilo, grafico="grafico_barras", titulo=None, subtitulo=None,
         grafico_em=None, dur=48, rotulos=None, **params):
    """Titulo grande, subtitulo, e o grafico se montando (barras crescendo, fatia abrindo).
    Numero que o falante ESTIMA continua indo em marcador (Papel) ou texto, nao em grafico
    limpo: o grafico da autoridade que a fala nao tem."""
    c = fundo(f, inicio, fim, estilo)
    gi = grafico_em if grafico_em is not None else inicio + 10
    if titulo:
        c.alpha_composite(marca_texto.quadro(f, inicio + 4, fim, estilo, texto=titulo,
                                             centro=(540, 400), tamanho=150))
    if subtitulo:
        c.alpha_composite(desfoque.quadro(f, inicio + 14, fim, estilo, texto=subtitulo,
                                          centro=(540, 570), tamanho=60))
    c.alpha_composite(objeto.quadro(f, gi, fim, estilo, grafico, centro=(540, 1100), largura=820,
                                    anima_em=gi + 8, dur=dur, rotulos=rotulos, **params))
    return c
