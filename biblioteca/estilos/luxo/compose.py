#!/usr/bin/env python3
"""
Cenas do estilo LUXO. O `./topclip motion novo --estilo luxo` copia este arquivo como
`compose.py` do projeto. Escreva uma build_M# por cena; aqui fica so CONTEUDO.

Toda cena do Luxo e OVERLAY (cutaway=False no SHOTS do render.py). Tela cheia usa
`P.fundo`; sobre o video, `P.cinema` (faixas de letterbox) da o tom de filme sem cobrir o
rosto. Pesos finos, latao e o ritmo lento vem do estilo: nunca escreva cor, fonte ou
duracao fixa aqui.

Trave cada evento numa palavra do transcript:

    frame24 = (t_palavra - t_inicio_do_plano) * 24

    M1   Objeto em destaque   relogio (receitas.objeto_em_destaque), tela cheia
    M2   Processo             etiqueta -> pessoas (receitas.processo), tela cheia
    M3   Dado                 grafico de barras (receitas.dado), tela cheia
    M4   Abertura             moldura + brilho, tela cheia
    M5   Numero               contador, tela cheia
    M6   Frase                marca_texto (sublinhado) sobre o video, com cinema
    M7   Principio            cartao, tela cheia
    M8   Troca                troca_palavra, tela cheia
    M9   Citacao              desfoque, tela cheia
    M10  Confirmacao          lottie (check no latao) + brilho, tela cheia

    ./topclip py compose.py            # os estados de todas as cenas + folha de estados
    ./topclip py compose.py M2 M4      # so estas
    ./topclip py compose.py --check    # END depois do ultimo evento, em todas
"""
from pathlib import Path

import pecas as P
from pecas import estados, receitas as R

ROOT = Path(__file__).resolve().parent
ESTILO = P.carregar(ROOT)


# ---------------------------------------------------------------------  o desenho
# As tres primeiras cenas sao o fluxo do Papel no lapis do estilo: a frase tem objeto, o
# objeto e desenhado (`pecas/objetos.py`, ou um seu em minha-biblioteca/objetos.py) e
# entra preso a palavra. A receita escolhe o registro (`pecas/receitas.py`).

# =====================================================================  M1  Objeto em destaque
M1_FIM = 96
M1_STATES = {"START": 6, "MID": 30, "END": 70, "EXIT": 91}
M1_EVENTS = dict(fundo=(0, M1_FIM), titulo=(4, 19), objeto=(10, 54), etiqueta=(40, 52),
                 saida=(86, M1_FIM))


def build_M1(frame, overlay_only=True):
    # "atendendo de madrugada": o relogio com os ponteiros andando da meia-noite as tres
    return R.objeto_em_destaque(frame, 0, M1_FIM, ESTILO, "relogio", titulo="Atendendo de madrugada",
                                etiqueta="cliente barato", objeto_em=10, anima_em=18, dur=36,
                                etiqueta_em=40, de=(0, 0), ate=(3, 0))


# =====================================================================  M2  Processo
M2_FIM = 110
M2_STATES = {"START": 6, "MID": 40, "END": 92, "EXIT": 106}
M2_EVENTS = dict(fundo=(0, M2_FIM), titulo=(4, 19), de=(8, 44), seta=(34, 48), para=(48, 90),
                 saida=(104, M2_FIM))


def build_M2(frame, overlay_only=True):
    # "o preco baixo atrai o cliente errado": etiqueta -> seta -> as pessoas
    return R.processo(frame, 0, M2_FIM, ESTILO, "etiqueta_preco", "pessoas", titulo="Preço baixo atrai",
                      de_em=8, seta_em=34, para_em=48, params_para=dict(quantas=3, destaque=1),
                      rotulos=("preço baixo", "o cliente errado"))


# =====================================================================  M3  Dado
M3_FIM = 110
M3_STATES = {"START": 6, "MID": 44, "END": 84, "EXIT": 106}
M3_EVENTS = dict(fundo=(0, M3_FIM), titulo=(4, 19), subtitulo=(18, 40), grafico=(20, 76),
                 saida=(104, M3_FIM))


def build_M3(frame, overlay_only=True):
    # "o LTV cresce": as barras sobem uma a uma, a ultima no acento
    return R.dado(frame, 0, M3_FIM, ESTILO, "grafico_barras", titulo="LTV",
                  subtitulo="cliente que compra de novo", grafico_em=20, dur=48,
                  rotulos=["1", "2", "3", "4"])


# ---------------------------------------------------------------------  o texto


# =====================================================================  M4  Abertura
M4_FIM = 110
M4_STATES = {"START": 6, "MID": 30, "END": 84, "EXIT": 104}
M4_EVENTS = dict(fundo=(0, M4_FIM), moldura=(4, 46), titulo=(14, 33), brilho=(40, 78),
                 saida=(98, M4_FIM))


def build_M4(frame, overlay_only=True):
    c = P.fundo(frame, 0, M4_FIM, ESTILO)
    c.alpha_composite(P.moldura.quadro(frame, 4, M4_FIM, ESTILO, caixa=(150, 600, 930, 1320)))
    c.alpha_composite(P.brilho.quadro(frame, 14, M4_FIM, ESTILO, texto="Mentoria de alto padrão",
                                      passa_em=40, centro=(540, 960), tamanho=104, largura=640))
    return c


# =====================================================================  M5  Numero
M5_FIM = 100
M5_STATES = {"START": 6, "MID": 20, "END": 60, "EXIT": 95}
M5_EVENTS = dict(fundo=(0, M5_FIM), numero=(6, 40), saida=(88, M5_FIM))


def build_M5(frame, overlay_only=True):
    c = P.fundo(frame, 0, M5_FIM, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 6, M5_FIM, ESTILO, valor=25000, prefixo="R$",
                                        rotulo="investimento", conta=34, tamanho=230))
    return c


# =====================================================================  M6  Frase
M6_FIM = 100
M6_STATES = {"START": 6, "MID": 26, "END": 60, "EXIT": 95}
M6_EVENTS = dict(cinema=(0, M6_FIM), frase=(8, 27), marca=(36, 52), saida=(88, M6_FIM))


def build_M6(frame, overlay_only=True):
    c = P.cinema(frame, 0, M6_FIM, ESTILO)
    c.alpha_composite(P.marca_texto.quadro(frame, 8, M6_FIM, ESTILO, centro=(540, 560),
                                           texto="O cliente certo paga pelo valor",
                                           palavra="valor", tipo="sublinhado", marca_em=36,
                                           tamanho=96))
    return c


# =====================================================================  M7  Principio
M7_FIM = 100
M7_STATES = {"START": 6, "MID": 22, "END": 60, "EXIT": 95}
M7_EVENTS = dict(fundo=(0, M7_FIM), cartao=(8, 27), saida=(88, M7_FIM))


def build_M7(frame, overlay_only=True):
    c = P.fundo(frame, 0, M7_FIM, ESTILO)
    c.alpha_composite(P.cartao.quadro(frame, 8, M7_FIM, ESTILO, centro=(540, 900),
                                      rotulo="princípio", titulo="Exclusividade não se explica",
                                      texto="Ela se percebe nos detalhes."))
    return c


# =====================================================================  M8  Troca
M8_FIM = 120
M8_STATES = {"START": 6, "MID": 50, "END": 92, "EXIT": 115}
M8_EVENTS = dict(fundo=(0, M8_FIM), troca=(8, 90), saida=(108, M8_FIM))


def build_M8(frame, overlay_only=True):
    c = P.fundo(frame, 0, M8_FIM, ESTILO)
    c.alpha_composite(P.troca_palavra.quadro(frame, 8, M8_FIM, ESTILO, prefixo="Quem compra busca",
                                             palavras=["exclusividade", "resultado", "confiança"],
                                             trocas=[40, 70], tamanho=118))
    return c


# =====================================================================  M9  Citacao
M9_FIM = 100
M9_STATES = {"START": 6, "MID": 22, "END": 64, "EXIT": 95}
M9_EVENTS = dict(fundo=(0, M9_FIM), frase=(8, 60), saida=(88, M9_FIM))


def build_M9(frame, overlay_only=True):
    c = P.fundo(frame, 0, M9_FIM, ESTILO)
    c.alpha_composite(P.desfoque.quadro(frame, 8, M9_FIM, ESTILO, tamanho=88,
                                        texto="Preço é o que você paga. Valor é o que você leva."))
    return c


# =====================================================================  M10  Confirmacao
M10_FIM = 100
M10_STATES = {"START": 6, "MID": 24, "END": 64, "EXIT": 95}
M10_EVENTS = dict(fundo=(0, M10_FIM), check=(6, 40), titulo=(20, 39), saida=(88, M10_FIM))


def build_M10(frame, overlay_only=True):
    c = P.fundo(frame, 0, M10_FIM, ESTILO)
    c.alpha_composite(P.lottie.quadro(frame, 6, M10_FIM, ESTILO, arquivo="estilo/lottie/check.json",
                                      slots={"acento": "acento"}, centro=(540, 760), largura=300))
    c.alpha_composite(P.brilho.quadro(frame, 20, M10_FIM, ESTILO, texto="Vaga confirmada",
                                      passa_em=44, centro=(540, 1040), tamanho=92))
    return c


# =====================================================================
SCENES = {"M1": (build_M1, M1_STATES, None),
          "M2": (build_M2, M2_STATES, None),
          "M3": (build_M3, M3_STATES, None),
          "M4": (build_M4, M4_STATES, None),
          "M5": (build_M5, M5_STATES, None),
          "M6": (build_M6, M6_STATES, None),
          "M7": (build_M7, M7_STATES, None),
          "M8": (build_M8, M8_STATES, None),
          "M9": (build_M9, M9_STATES, None),
          "M10": (build_M10, M10_STATES, None)}


if __name__ == "__main__":
    estados.main(SCENES, globals())
