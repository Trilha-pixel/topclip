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

    M1  Numero         contador, tela cheia preta
    M2  Frase          marca_texto, sobre o video
    M3  Troca          troca_palavra, sobre o video
    M4  Lista          cascata numerada, tela cheia
    M5  Comparacao     antes_depois, tela cheia
    M6  Cartao         cartao, sobre o video
    M7  Confirmacao    lottie (check no acento), sobre o video

    ./topclip py compose.py            # os estados de todas as cenas + folha de estados
    ./topclip py compose.py M2 M4      # so estas
    ./topclip py compose.py --check    # END depois do ultimo evento, em todas
"""
from pathlib import Path

import pecas as P
from pecas import estados

ROOT = Path(__file__).resolve().parent
ESTILO = P.carregar(ROOT)
TOPO = (540, 560)               # sobre o video: centro no terco de cima


# =====================================================================  M1  Numero
M1_FIM = 60
M1_STATES = {"START": 2, "MID": 8, "END": 34, "EXIT": 58}
M1_EVENTS = dict(fundo=(0, M1_FIM), numero=(2, 26), saida=(56, M1_FIM))


def build_M1(frame, overlay_only=True):
    c = P.fundo(frame, 0, M1_FIM, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 2, M1_FIM, ESTILO, valor=10000, prefixo="R$",
                                        sufixo="/mês", rotulo="de faturamento", conta=24,
                                        tamanho=280))
    return c


# =====================================================================  M2  Frase
M2_FIM = 64
M2_STATES = {"START": 3, "MID": 10, "END": 30, "EXIT": 62}
M2_EVENTS = dict(frase=(2, 8), marca=(16, 26), saida=(60, M2_FIM))


def build_M2(frame, overlay_only=True):
    return P.marca_texto.quadro(frame, 2, M2_FIM, ESTILO, centro=TOPO,
                                texto="Quanto mais barato, piores os clientes",
                                palavra="piores", tipo="marca", marca_em=16, tamanho=92)


# =====================================================================  M3  Troca
M3_FIM = 72
M3_STATES = {"START": 3, "MID": 26, "END": 52, "EXIT": 70}
M3_EVENTS = dict(troca=(2, 50), saida=(68, M3_FIM))


def build_M3(frame, overlay_only=True):
    return P.troca_palavra.quadro(frame, 2, M3_FIM, ESTILO, centro=TOPO, prefixo="Isso é",
                                  palavras=["simples", "rápido", "lucrativo"], trocas=[22, 42],
                                  tamanho=130)


# =====================================================================  M4  Lista
M4_FIM = 80
M4_STATES = {"START": 3, "MID": 22, "END": 50, "EXIT": 78}
M4_EVENTS = dict(fundo=(0, M4_FIM), itens=(2, 44), saida=(76, M4_FIM))


def build_M4(frame, overlay_only=True):
    c = P.fundo(frame, 0, M4_FIM, ESTILO)
    c.alpha_composite(P.cascata.quadro(frame, 2, M4_FIM, ESTILO, entradas=[2, 16, 30],
                                       marcador="numero",
                                       itens=["Cobra mais", "Atende menos", "Lucra mais"],
                                       tamanho=64))
    return c


# =====================================================================  M5  Comparacao
M5_FIM = 80
M5_STATES = {"START": 3, "MID": 22, "END": 50, "EXIT": 78}
M5_EVENTS = dict(fundo=(0, M5_FIM), painel=(2, 8), divisor=(14, 40), saida=(76, M5_FIM))


def build_M5(frame, overlay_only=True):
    c = P.fundo(frame, 0, M5_FIM, ESTILO)
    c.alpha_composite(P.antes_depois.quadro(frame, 2, M5_FIM, ESTILO, textos=("R$ 50", "R$ 300"),
                                            rotulos=("Antes", "Depois"), divisor_em=14))
    return c


# =====================================================================  M6  Cartao
M6_FIM = 72
M6_STATES = {"START": 3, "MID": 8, "END": 30, "EXIT": 70}
M6_EVENTS = dict(cartao=(2, 8), saida=(68, M6_FIM))


def build_M6(frame, overlay_only=True):
    return P.cartao.quadro(frame, 2, M6_FIM, ESTILO, centro=(540, 520), rotulo="regra",
                           titulo="Nunca baixe o preço", texto="Suba o valor que você entrega.")


# =====================================================================  M7  Confirmacao
M7_FIM = 60
M7_STATES = {"START": 3, "MID": 10, "END": 34, "EXIT": 58}
M7_EVENTS = dict(check=(2, 26), frase=(10, 16), saida=(56, M7_FIM))


def build_M7(frame, overlay_only=True):
    c = P.lottie.quadro(frame, 2, M7_FIM, ESTILO, arquivo="estilo/lottie/check.json",
                        slots={"acento": "acento"}, centro=(540, 460), largura=360)
    c.alpha_composite(P.marca_texto.quadro(frame, 10, M7_FIM, ESTILO, texto="Feito",
                                           centro=(540, 760), tamanho=130))
    return c


# =====================================================================
SCENES = {"M1": (build_M1, M1_STATES, None),
          "M2": (build_M2, M2_STATES, None),
          "M3": (build_M3, M3_STATES, None),
          "M4": (build_M4, M4_STATES, None),
          "M5": (build_M5, M5_STATES, None),
          "M6": (build_M6, M6_STATES, None),
          "M7": (build_M7, M7_STATES, None)}


if __name__ == "__main__":
    estados.main(SCENES, globals())
