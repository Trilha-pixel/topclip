#!/usr/bin/env python3
"""
Cenas-MODELO das pecas, para estilo de cenas overlay que nao traz compose proprio (o
estilo importado, que chega sem codigo, ou um estilo seu sem cenas). O `motion novo`
copia este arquivo como `compose.py` do projeto. Nada aqui tem cor, fonte ou ritmo
fixo: tudo vem do estilo do projeto, entao a mesma cena veste qualquer estilo.

Toda cena e OVERLAY (cutaway=False no SHOTS do render.py): tela cheia desenha o proprio
fundo (`P.fundo`) e entra e sai em fade; cena sobre o video (M4) nao desenha fundo.
Copie a que a fala pede, troque o conteudo e trave os eventos nas palavras:

    frame24 = (t_palavra - t_inicio_do_plano) * 24

    M1  Numero            contador
    M2  Frase marcada     marca_texto
    M3  Lista             cascata
    M4  Cartao no topo    cartao, sobre o video (o rosto fica livre)
    M5  Troca             troca_palavra
    M6  Frase             desfoque
    M7  Comparacao        antes_depois
    M8  Confirmacao       lottie (se o estilo tiver uma animacao em lottie/) + desfoque
    M9  Abertura          moldura + brilho

    ./topclip py compose.py            # os estados de todas as cenas + folha de estados
    ./topclip py compose.py M2 M4      # so estas
    ./topclip py compose.py --check    # END depois do ultimo evento, em todas
"""
from pathlib import Path

import pecas as P
from pecas import estados

ROOT = Path(__file__).resolve().parent
ESTILO = P.carregar(ROOT)


# =====================================================================  M1  Numero
M1_FIM = 76
M1_STATES = {"START": 3, "MID": 16, "END": 46, "EXIT": 71}
M1_EVENTS = dict(fundo=(0, M1_FIM), numero=(4, 34), saida=(66, M1_FIM))


def build_M1(frame, overlay_only=True):
    c = P.fundo(frame, 0, M1_FIM, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 4, M1_FIM, ESTILO, valor=3000, prefixo="R$",
                                        sufixo="/mês", rotulo="por cliente, todo mês", conta=30))
    return c


# =====================================================================  M2  Frase marcada
M2_FIM = 84
M2_STATES = {"START": 3, "MID": 26, "END": 50, "EXIT": 79}
M2_EVENTS = dict(fundo=(0, M2_FIM), frase=(4, 19), marca=(22, 34), saida=(74, M2_FIM))


def build_M2(frame, overlay_only=True):
    c = P.fundo(frame, 0, M2_FIM, ESTILO)
    c.alpha_composite(P.marca_texto.quadro(frame, 4, M2_FIM, ESTILO,
                                           texto="Quanto mais barato, piores os clientes",
                                           palavra="piores", tipo="marca", marca_em=22))
    return c


# =====================================================================  M3  Lista
M3_FIM = 96
M3_STATES = {"START": 8, "MID": 30, "END": 62, "EXIT": 91}
M3_EVENTS = dict(fundo=(0, M3_FIM), itens=(6, 60), saida=(86, M3_FIM))


def build_M3(frame, overlay_only=True):
    c = P.fundo(frame, 0, M3_FIM, ESTILO)
    c.alpha_composite(P.cascata.quadro(frame, 6, M3_FIM, ESTILO, entradas=[6, 22, 38],
                                       itens=["Cobra mais caro", "Atende menos clientes",
                                              "Lucra mais no fim do mês"]))
    return c


# =====================================================================  M4  Cartao no topo
# Sobre o video: sem fundo, centro no terco de cima para o rosto ficar livre.
M4_FIM = 84
M4_STATES = {"START": 6, "MID": 14, "END": 40, "EXIT": 79}
M4_EVENTS = dict(cartao=(4, 19), saida=(74, M4_FIM))


def build_M4(frame, overlay_only=True):
    return P.cartao.quadro(frame, 4, M4_FIM, ESTILO, centro=(540, 520), rotulo="dica",
                           titulo="Suba o preço antes de crescer",
                           texto="Cliente que paga mais exige menos e indica mais.")


# =====================================================================  M5  Troca
M5_FIM = 96
M5_STATES = {"START": 6, "MID": 40, "END": 72, "EXIT": 91}
M5_EVENTS = dict(fundo=(0, M5_FIM), troca=(4, 70), saida=(86, M5_FIM))


def build_M5(frame, overlay_only=True):
    c = P.fundo(frame, 0, M5_FIM, ESTILO)
    c.alpha_composite(P.troca_palavra.quadro(frame, 4, M5_FIM, ESTILO, prefixo="Cliente barato é",
                                             palavras=["exigente", "lento", "caro"],
                                             trocas=[34, 56]))
    return c


# =====================================================================  M6  Frase
M6_FIM = 80
M6_STATES = {"START": 6, "MID": 16, "END": 44, "EXIT": 75}
M6_EVENTS = dict(fundo=(0, M6_FIM), frase=(4, 40), saida=(70, M6_FIM))


def build_M6(frame, overlay_only=True):
    c = P.fundo(frame, 0, M6_FIM, ESTILO)
    c.alpha_composite(P.desfoque.quadro(frame, 4, M6_FIM, ESTILO,
                                        texto="O preço baixo atrai o cliente errado"))
    return c


# =====================================================================  M7  Comparacao
M7_FIM = 96
M7_STATES = {"START": 6, "MID": 34, "END": 60, "EXIT": 91}
M7_EVENTS = dict(fundo=(0, M7_FIM), painel=(4, 19), divisor=(24, 53), saida=(86, M7_FIM))


def build_M7(frame, overlay_only=True):
    c = P.fundo(frame, 0, M7_FIM, ESTILO)
    c.alpha_composite(P.antes_depois.quadro(frame, 4, M7_FIM, ESTILO, textos=("R$ 50", "R$ 300"),
                                            rotulos=("Antes", "Depois"), divisor_em=24))
    return c


# =====================================================================  M8  Confirmacao
M8_FIM = 80
M8_STATES = {"START": 6, "MID": 16, "END": 50, "EXIT": 75}
M8_EVENTS = dict(fundo=(0, M8_FIM), check=(4, 34), frase=(18, 44), saida=(70, M8_FIM))


def build_M8(frame, overlay_only=True):
    c = P.fundo(frame, 0, M8_FIM, ESTILO)
    animacoes = sorted((ROOT / "estilo" / "lottie").glob("*.json"))
    if animacoes:                        # estilo sem animacao: a cena fica so com a frase
        c.alpha_composite(P.lottie.quadro(frame, 4, M8_FIM, ESTILO,
                                          arquivo=str(animacoes[0].relative_to(ROOT)),
                                          slots={"acento": "acento"}, centro=(540, 760),
                                          largura=420))
    c.alpha_composite(P.desfoque.quadro(frame, 18, M8_FIM, ESTILO, texto="Preço novo no ar",
                                        centro=(540, 1080), tamanho=84))
    return c


# =====================================================================  M9  Abertura
M9_FIM = 110
M9_STATES = {"START": 6, "MID": 30, "END": 84, "EXIT": 104}
M9_EVENTS = dict(fundo=(0, M9_FIM), moldura=(4, 46), titulo=(14, 33), brilho=(40, 78),
                 saida=(98, M9_FIM))


def build_M9(frame, overlay_only=True):
    c = P.fundo(frame, 0, M9_FIM, ESTILO)
    c.alpha_composite(P.moldura.quadro(frame, 4, M9_FIM, ESTILO, caixa=(150, 600, 930, 1320)))
    c.alpha_composite(P.brilho.quadro(frame, 14, M9_FIM, ESTILO, texto="O seu conteúdo",
                                      passa_em=40, centro=(540, 960), tamanho=104, largura=640))
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
          "M9": (build_M9, M9_STATES, None)}


if __name__ == "__main__":
    estados.main(SCENES, globals())
