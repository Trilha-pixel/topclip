"""
Exemplo REAL: o bloco CLIPE do `render.py` do clipe 06 de um podcast ("faça um MVP nesta
madrugada", 55,4554s, 30000/1001). Copiado do projeto que calibrou esta identidade.

Serve para ver como os quatro valores da legenda sao escolhidos de verdade.
"""
from pathlib import Path
import captions as CAP

ROOT = Path(__file__).resolve().parent

SRC = ROOT / "00_brief" / "fonte.mp4"
DUR = 55.4554
FPS_NUM, FPS_DEN = 30000, 1001

# Os sete motions do clipe. As JANELAS da legenda sao o COMPLEMENTO disto.
#   nome, funcao, inicio, fim, frames24 do plano, cutaway?
SHOTS = [
    ("M0", None,  7.100,  9.900,  67, True),   # teclado + VIBE CODING
    ("M1", None, 11.700, 14.900,  77, True),   # relogio 00:00 + MVP
    ("M2", None, 17.900, 21.600,  89, True),   # CRT com terminal
    ("M3", None, 28.350, 30.600,  54, False),  # foto noturna, overlay
    ("M4", None, 31.800, 34.900,  74, True),   # pizza a mao, 50%
    ("M5", None, 43.800, 49.200, 130, True),   # ideia -> produto
    ("M6", None, 50.100, 53.500,  82, True),   # poucas notas -> maco
]

CAP.configurar(
    words_json=ROOT / "00_brief" / "transcript_palavras.json",

    # Janelas livres de motion. Os valores abaixo sao os do clipe 06, que ainda recuava
    # 0,15s das bordas — NAO repita: o recuo apagou palavras na run seguinte (o "Nao" de
    # "Nao e dificil fazer"). Hoje: janelas=CAP.janelas_livres(SHOTS, DUR), coladas nas
    # cenas, e o check() acusa palavra sem legenda. Repare nos vaos de 0,90s
    # (49,20-50,10) e 1,20s (30,60-31,80) entre motions: legenda de um segundo entre
    # dois cutaways pisca — se ler mal, estique uma das cenas sobre o vao.
    janelas=[(0.20, 6.95), (15.05, 17.75), (21.75, 28.20), (35.05, 43.65),
             (53.65, 55.30)],

    # Uma enfase por janela, no maximo, e cor em DUAS do clipe inteiro. Na referencia
    # 94% das linhas sao brancas: o acento so funciona porque e raro.
    destaque={
        ("madrugada", 2.20): dict(cor=None),            # serifa italica, branca
        ("crack", 16.22): dict(cor=(201, 72, 80)),      # o unico vermelho da 1a metade
        ("velho,", 26.98): dict(cor=(201, 72, 80)),     # a virada do clipe
        ("história", 41.78): dict(cor=None),
    },

    # O clipe e a concatenacao de dois trechos do episodio e tem um corte seco em 25,86
    # ("e esse nivel" | "faca isso, velho"). Sem isso um bloco escrevia "nivel faca",
    # juntando o fim de uma frase com o comeco de outra.
    cortes=[25.86],
)
