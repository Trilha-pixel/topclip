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
from .base import cola, fundo, largura_texto, quebra, retangulo, vazio
from .objetos import OBJETOS

FUNDO_SEGURO = 1640          # abaixo disso fica a interface do app (260 px do quadro)


def _layout_processo(de, para, params_de, params_para, titulo, largura=470):
    """Os y do processo pela altura real dos objetos (o predio e mais alto que as
    pessoas): o `de` logo abaixo do titulo, o `para` com o rotulo acima da interface do
    app, e o conector no meio do vao. Sem espaco, os dois objetos encolhem juntos.
    Devolve (largura, y_de, y_rotulo_de, y_conector, y_para, y_rotulo_para)."""
    a_de = OBJETOS[de](p=1.0, **(params_de or {}))[1]
    a_pa = OBJETOS[para](p=1.0, **(params_para or {}))[1]
    topo = 420 if titulo else 330
    # 400 px para os dois rotulos (~90 cada) e o conector (~220)
    L = min(largura, (FUNDO_SEGURO - topo - 400) / (a_de + a_pa))
    rot_de = topo + a_de * L + 40
    y_pa = FUNDO_SEGURO - 100 - a_pa * L / 2
    return (int(L), topo + a_de * L / 2, rot_de, (rot_de + 40 + y_pa - a_pa * L / 2) / 2,
            y_pa, FUNDO_SEGURO - 60)


def _cabe(estilo, texto, tamanho, largura=880, minimo=96):
    """O maior tamanho (ate `tamanho`) em que o titulo cabe numa linha, sem passar de
    `minimo`; abaixo disso ele quebra em linhas equilibradas."""
    t = estilo.caixa(texto)
    while tamanho > minimo and largura_texto(estilo.fonte("titulo", tamanho, 700), t) > largura:
        tamanho -= 6
    return tamanho


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
             para_em=None, params_de=None, params_para=None, rotulos=(None, None),
             rotulos_em=(None, None), liga="seta", anima_de=None, anima_para=None, dur=24):
    """De um objeto ao outro, de cima para baixo, com o conector entre eles. Cada parte
    entra na sua palavra: `de_em` (o ponto de partida), `seta_em` (o "vira", "gera",
    "leva a" — ou o "e o mesmo que"), `para_em` (o resultado); `rotulos_em`, a palavra de
    cada rotulo (sem ela, o rotulo entra com o objeto). `liga`: "seta" para causa e
    efeito, "igual" para equivalencia ("isso e o mesmo que ter um aluguel"). `anima_*` e
    `dur`: a animacao propria de cada objeto (padrao: logo depois de entrar)."""
    c = fundo(f, inicio, fim, estilo)
    di = de_em if de_em is not None else inicio + 6
    si = seta_em if seta_em is not None else di + 18
    pi = para_em if para_em is not None else si + 12
    L, y_de, y_rot_de, y_liga, y_pa, y_rot_pa = _layout_processo(de, para, params_de, params_para,
                                                                titulo)
    if titulo:
        c.alpha_composite(marca_texto.quadro(f, inicio + 4, fim, estilo, texto=titulo,
                                             centro=(540, 300), tamanho=84))
    c.alpha_composite(objeto.quadro(f, di, fim, estilo, de, centro=(540, int(y_de)), largura=L,
                                    anima_em=di + 6 if anima_de is None else anima_de, dur=dur,
                                    **(params_de or {})))
    if liga == "igual":
        c.alpha_composite(objeto.quadro(f, si, fim, estilo, "igual", centro=(540, int(y_liga)),
                                        largura=180, anima_em=si, dur=12))
    else:
        c.alpha_composite(objeto.quadro(f, si, fim, estilo, "seta", centro=(540, int(y_liga)),
                                        largura=200, anima_em=si, dur=14, angulo=90))
    c.alpha_composite(objeto.quadro(f, pi, fim, estilo, para, centro=(540, int(y_pa)), largura=L,
                                    anima_em=pi + 6 if anima_para is None else anima_para, dur=dur,
                                    **(params_para or {})))
    # sem palavra propria, o rotulo entra junto do objeto: o "para" costuma cair no fim
    em = (rotulos_em[0] if rotulos_em[0] is not None else di + 6,
          rotulos_em[1] if rotulos_em[1] is not None else pi + 2)
    for txt, y, ini in ((rotulos[0], y_rot_de, em[0]), (rotulos[1], y_rot_pa, em[1])):
        if txt:
            c.alpha_composite(desfoque.quadro(f, ini, fim, estilo, texto=txt, centro=(540, int(y)),
                                              tamanho=52))
    return c


def dado(f, inicio, fim, estilo, grafico="grafico_barras", titulo=None, subtitulo=None,
         grafico_em=None, dur=48, rotulos=None, titulo_em=None, subtitulo_em=None,
         anima_em=None, total=None, total_em=None, **params):
    """Titulo grande, subtitulo, e o grafico se montando (barras crescendo, moedas caindo,
    fatia abrindo). `*_em` = a palavra de cada parte; `total` = a pilula do resultado
    embaixo ("R$ 3 mil por mes"), na palavra `total_em`. Numero que o falante ESTIMA
    continua indo em marcador (Papel) ou texto, nao em grafico limpo: o grafico da
    autoridade que a fala nao tem."""
    c = fundo(f, inicio, fim, estilo)
    gi = grafico_em if grafico_em is not None else inicio + 10
    y_sub = 570
    if titulo:
        # o titulo cabe numa linha se der; quebrando, o subtitulo desce para baixo dele
        tam = _cabe(estilo, titulo, 150)
        linhas = len(quebra(estilo.fonte("titulo", tam, 700), estilo.caixa(titulo), 880))
        y_sub = max(570, int(400 + linhas * tam * 1.14 / 2 + 70))
        c.alpha_composite(marca_texto.quadro(f, titulo_em if titulo_em is not None else inicio + 4,
                                             fim, estilo, texto=titulo, centro=(540, 400), tamanho=tam))
    if subtitulo:
        c.alpha_composite(desfoque.quadro(f, subtitulo_em if subtitulo_em is not None else inicio + 14,
                                          fim, estilo, texto=subtitulo, centro=(540, y_sub), tamanho=60))
    c.alpha_composite(objeto.quadro(f, gi, fim, estilo, grafico, centro=(540, 1100), largura=820,
                                    anima_em=gi + 8 if anima_em is None else anima_em, dur=dur,
                                    rotulos=rotulos, **params))
    if total:
        c.alpha_composite(pilula(f, total_em if total_em is not None else gi + dur, estilo, total,
                                 (540, 1600), tamanho=72))
    return c
