#!/usr/bin/env python3
"""
Cenas do estilo IMPACTO. O `./topclip motion novo --estilo impacto` copia este arquivo
como `compose.py` do projeto. Escreva uma build_M# por cena; aqui fica so CONTEUDO.

Toda cena do Impacto e OVERLAY (cutaway=False no SHOTS do render.py). Frase e cartao vao
SOBRE o video, no terco de cima, para o rosto ficar livre; numero grande vai em tela cheia
preta (`P.fundo`). A tipografia (caixa alta, contorno, sombra dura) e o pop vem do estilo:
nunca escreva cor, fonte ou efeito fixo aqui.

Trave cada evento numa palavra do transcript:

    frame24 = (t_palavra - t_inicio_do_plano) * 24

    M1   Objeto em destaque   relogio (receitas.objeto_em_destaque), tela cheia
    M2   Processo             etiqueta -> pessoas (receitas.processo), tela cheia
    M3   Dado                 grafico de barras (receitas.dado), tela cheia
    M4   Numero               contador, tela cheia preta
    M5   Frase                marca_texto, sobre o video
    M6   Troca                troca_palavra, sobre o video
    M7   Lista                cascata numerada, tela cheia
    M8   Comparacao           antes_depois, tela cheia
    M9   Cartao               cartao, sobre o video
    M10  Confirmacao          lottie (check no acento), sobre o video

    ./topclip py compose.py            # os estados de todas as cenas + folha de estados
    ./topclip py compose.py M2 M4      # so estas
    ./topclip py compose.py --check    # END depois do ultimo evento, em todas
"""
from pathlib import Path

import pecas as P
from pecas import estados, receitas as R

ROOT = Path(__file__).resolve().parent
ESTILO = P.carregar(ROOT)
TOPO = (540, 560)               # sobre o video: centro no terco de cima


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


# =====================================================================  M4  Numero
M4_FIM = 60
M4_STATES = {"START": 2, "MID": 8, "END": 34, "EXIT": 58}
M4_EVENTS = dict(fundo=(0, M4_FIM), numero=(2, 26), saida=(56, M4_FIM))


def build_M4(frame, overlay_only=True):
    c = P.fundo(frame, 0, M4_FIM, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 2, M4_FIM, ESTILO, valor=10000, prefixo="R$",
                                        sufixo="/mês", rotulo="de faturamento", conta=24,
                                        tamanho=280))
    return c


# =====================================================================  M5  Frase
M5_FIM = 64
M5_STATES = {"START": 3, "MID": 10, "END": 30, "EXIT": 62}
M5_EVENTS = dict(frase=(2, 8), marca=(16, 26), saida=(60, M5_FIM))


def build_M5(frame, overlay_only=True):
    return P.marca_texto.quadro(frame, 2, M5_FIM, ESTILO, centro=TOPO,
                                texto="Quanto mais barato, piores os clientes",
                                palavra="piores", tipo="marca", marca_em=16, tamanho=92)


# =====================================================================  M6  Troca
M6_FIM = 72
M6_STATES = {"START": 3, "MID": 26, "END": 52, "EXIT": 70}
M6_EVENTS = dict(troca=(2, 50), saida=(68, M6_FIM))


def build_M6(frame, overlay_only=True):
    return P.troca_palavra.quadro(frame, 2, M6_FIM, ESTILO, centro=TOPO, prefixo="Isso é",
                                  palavras=["simples", "rápido", "lucrativo"], trocas=[22, 42],
                                  tamanho=130)


# =====================================================================  M7  Lista
M7_FIM = 80
M7_STATES = {"START": 3, "MID": 22, "END": 50, "EXIT": 78}
M7_EVENTS = dict(fundo=(0, M7_FIM), itens=(2, 44), saida=(76, M7_FIM))


def build_M7(frame, overlay_only=True):
    c = P.fundo(frame, 0, M7_FIM, ESTILO)
    c.alpha_composite(P.cascata.quadro(frame, 2, M7_FIM, ESTILO, entradas=[2, 16, 30],
                                       marcador="numero",
                                       itens=["Cobra mais", "Atende menos", "Lucra mais"],
                                       tamanho=64))
    return c


# =====================================================================  M8  Comparacao
M8_FIM = 80
M8_STATES = {"START": 3, "MID": 22, "END": 50, "EXIT": 78}
M8_EVENTS = dict(fundo=(0, M8_FIM), painel=(2, 8), divisor=(14, 40), saida=(76, M8_FIM))


def build_M8(frame, overlay_only=True):
    c = P.fundo(frame, 0, M8_FIM, ESTILO)
    c.alpha_composite(P.antes_depois.quadro(frame, 2, M8_FIM, ESTILO, textos=("R$ 50", "R$ 300"),
                                            rotulos=("Antes", "Depois"), divisor_em=14))
    return c


# =====================================================================  M9  Cartao
M9_FIM = 72
M9_STATES = {"START": 3, "MID": 8, "END": 30, "EXIT": 70}
M9_EVENTS = dict(cartao=(2, 8), saida=(68, M9_FIM))


def build_M9(frame, overlay_only=True):
    return P.cartao.quadro(frame, 2, M9_FIM, ESTILO, centro=(540, 520), rotulo="regra",
                           titulo="Nunca baixe o preço", texto="Suba o valor que você entrega.")


# =====================================================================  M10  Confirmacao
M10_FIM = 60
M10_STATES = {"START": 3, "MID": 10, "END": 34, "EXIT": 58}
M10_EVENTS = dict(check=(2, 26), frase=(10, 16), saida=(56, M10_FIM))


def build_M10(frame, overlay_only=True):
    c = P.lottie.quadro(frame, 2, M10_FIM, ESTILO, arquivo="estilo/lottie/check.json",
                        slots={"acento": "acento"}, centro=(540, 460), largura=360)
    c.alpha_composite(P.marca_texto.quadro(frame, 10, M10_FIM, ESTILO, texto="Feito",
                                           centro=(540, 760), tamanho=130))
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
