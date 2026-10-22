#!/usr/bin/env python3
"""
Cenas do estilo LIMPO. O `./topclip motion novo --estilo limpo` copia este arquivo como
`compose.py` do projeto. Escreva uma build_M# por cena; aqui fica so CONTEUDO.

Toda cena do Limpo e OVERLAY (cutaway=False no SHOTS do render.py): a cena desenha o
proprio fundo (`P.fundo`) e entra e sai em fade pelo perfil calmo. Sem corte seco, sem
grao, sem boil. Cena "sobre o video" (M7) simplesmente nao desenha fundo.

As cenas abaixo sao EXEMPLOS PRONTOS, uma por peca. Copie a que a fala pede, troque o
conteudo e trave os eventos nas palavras do transcript:

    frame24 = (t_palavra - t_inicio_do_plano) * 24

    M1   Objeto em destaque   relogio (receitas.objeto_em_destaque), tela cheia
    M2   Processo             etiqueta -> pessoas (receitas.processo), tela cheia
    M3   Dado                 grafico de barras (receitas.dado), tela cheia
    M4   Numero               contador
    M5   Frase marcada        marca_texto
    M6   Lista                cascata
    M7   Cartao no topo       cartao, sobre o video (o rosto fica livre)
    M8   Troca                troca_palavra
    M9   Frase                desfoque
    M10  Comparacao           antes_depois
    M11  Confirmacao          lottie (check na cor do acento) + desfoque

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


# =====================================================================  M4  Numero
M4_FIM = 76
M4_STATES = {"START": 3, "MID": 16, "END": 46, "EXIT": 71}
M4_EVENTS = dict(fundo=(0, M4_FIM), numero=(4, 34), saida=(66, M4_FIM))


def build_M4(frame, overlay_only=True):
    c = P.fundo(frame, 0, M4_FIM, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 4, M4_FIM, ESTILO, valor=3000, prefixo="R$",
                                        sufixo="/mês", rotulo="por cliente, todo mês", conta=30))
    return c


# =====================================================================  M5  Frase marcada
M5_FIM = 84
M5_STATES = {"START": 3, "MID": 26, "END": 50, "EXIT": 79}
M5_EVENTS = dict(fundo=(0, M5_FIM), frase=(4, 19), marca=(22, 34), saida=(74, M5_FIM))


def build_M5(frame, overlay_only=True):
    c = P.fundo(frame, 0, M5_FIM, ESTILO)
    c.alpha_composite(P.marca_texto.quadro(frame, 4, M5_FIM, ESTILO,
                                           texto="Quanto mais barato, piores os clientes",
                                           palavra="piores", tipo="marca", marca_em=22))
    return c


# =====================================================================  M6  Lista
M6_FIM = 96
M6_STATES = {"START": 8, "MID": 30, "END": 62, "EXIT": 91}
M6_EVENTS = dict(fundo=(0, M6_FIM), itens=(6, 60), saida=(86, M6_FIM))


def build_M6(frame, overlay_only=True):
    c = P.fundo(frame, 0, M6_FIM, ESTILO)
    c.alpha_composite(P.cascata.quadro(frame, 6, M6_FIM, ESTILO, entradas=[6, 22, 38],
                                       itens=["Cobra mais caro", "Atende menos clientes",
                                              "Lucra mais no fim do mês"]))
    return c


# =====================================================================  M7  Cartao no topo
# Sobre o video: sem fundo, centro no terco de cima para o rosto ficar livre.
M7_FIM = 84
M7_STATES = {"START": 6, "MID": 14, "END": 40, "EXIT": 79}
M7_EVENTS = dict(cartao=(4, 19), saida=(74, M7_FIM))


def build_M7(frame, overlay_only=True):
    return P.cartao.quadro(frame, 4, M7_FIM, ESTILO, centro=(540, 520), rotulo="dica",
                           titulo="Suba o preço antes de crescer",
                           texto="Cliente que paga mais exige menos e indica mais.")


# =====================================================================  M8  Troca
M8_FIM = 96
M8_STATES = {"START": 6, "MID": 40, "END": 72, "EXIT": 91}
M8_EVENTS = dict(fundo=(0, M8_FIM), troca=(4, 70), saida=(86, M8_FIM))


def build_M8(frame, overlay_only=True):
    c = P.fundo(frame, 0, M8_FIM, ESTILO)
    c.alpha_composite(P.troca_palavra.quadro(frame, 4, M8_FIM, ESTILO, prefixo="Cliente barato é",
                                             palavras=["exigente", "lento", "caro"],
                                             trocas=[34, 56]))
    return c


# =====================================================================  M9  Frase
M9_FIM = 80
M9_STATES = {"START": 6, "MID": 16, "END": 44, "EXIT": 75}
M9_EVENTS = dict(fundo=(0, M9_FIM), frase=(4, 40), saida=(70, M9_FIM))


def build_M9(frame, overlay_only=True):
    c = P.fundo(frame, 0, M9_FIM, ESTILO)
    c.alpha_composite(P.desfoque.quadro(frame, 4, M9_FIM, ESTILO,
                                        texto="O preço baixo atrai o cliente errado"))
    return c


# =====================================================================  M10  Comparacao
M10_FIM = 96
M10_STATES = {"START": 6, "MID": 34, "END": 60, "EXIT": 91}
M10_EVENTS = dict(fundo=(0, M10_FIM), painel=(4, 19), divisor=(24, 53), saida=(86, M10_FIM))


def build_M10(frame, overlay_only=True):
    c = P.fundo(frame, 0, M10_FIM, ESTILO)
    c.alpha_composite(P.antes_depois.quadro(frame, 4, M10_FIM, ESTILO, textos=("R$ 50", "R$ 300"),
                                            rotulos=("Antes", "Depois"), divisor_em=24))
    return c


# =====================================================================  M11  Confirmacao
M11_FIM = 80
M11_STATES = {"START": 6, "MID": 16, "END": 50, "EXIT": 75}
M11_EVENTS = dict(fundo=(0, M11_FIM), check=(4, 34), frase=(18, 44), saida=(70, M11_FIM))


def build_M11(frame, overlay_only=True):
    c = P.fundo(frame, 0, M11_FIM, ESTILO)
    c.alpha_composite(P.lottie.quadro(frame, 4, M11_FIM, ESTILO, arquivo="estilo/lottie/check.json",
                                      slots={"acento": "acento"}, centro=(540, 760), largura=420))
    c.alpha_composite(P.desfoque.quadro(frame, 18, M11_FIM, ESTILO, texto="Preço novo no ar",
                                        centro=(540, 1080), tamanho=84))
    return c


# =====================================================================
# nome: (funcao, estados, acabamento). No Limpo e sempre None: overlay, julgado sobre o
# video no tempo certo (defina <NOME>_T0 = inicio da cena no clipe para usar o plate real).
SCENES = {"M1": (build_M1, M1_STATES, None),
          "M2": (build_M2, M2_STATES, None),
          "M3": (build_M3, M3_STATES, None),
          "M4": (build_M4, M4_STATES, None),
          "M5": (build_M5, M5_STATES, None),
          "M6": (build_M6, M6_STATES, None),
          "M7": (build_M7, M7_STATES, None),
          "M8": (build_M8, M8_STATES, None),
          "M9": (build_M9, M9_STATES, None),
          "M10": (build_M10, M10_STATES, None),
          "M11": (build_M11, M11_STATES, None)}


if __name__ == "__main__":
    estados.main(SCENES, globals())
