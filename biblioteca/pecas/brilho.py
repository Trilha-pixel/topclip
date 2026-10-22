"""
Brilho: um titulo que entra e recebe um reflexo atravessando as letras, da esquerda para a
direita — como luz passando em metal. Ideia do Animated Shiny Text do Magic UI (MIT).

    brilho.quadro(f, inicio, fim, estilo, texto="Mentoria", passa_em=24)

O reflexo passa UMA vez, em `passa_em` (por padrao, quando o titulo termina de entrar):
trave na palavra. Brilho em loop vira enfeite de interface (regra universal 8).
"""
import numpy as np
from PIL import Image

from .base import cola, lin, quebra, vazio

EXEMPLO = dict(inicio=0, fim=96, f=34, dados=dict(texto="Clientes que pagam mais", passa_em=20))


def quadro(f, inicio, fim, estilo, texto, passa_em=None, centro=(540, 860), tamanho=120,
           largura=900, peso=700, cor="texto", reflexo="acento", fonte="titulo"):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    ft = estilo.fonte(fonte, tamanho, peso)
    linhas = quebra(ft, estilo.caixa(texto), largura)
    lay, _ = estilo.bloco(linhas, ft, estilo.cor(cor), entrelinha=1.08)

    ini = passa_em if passa_em is not None else inicio + estilo.q_entrada
    p = lin(f, ini, ini + estilo.q_entrada * 2)
    if 0 < p < 1:
        # faixa de luz inclinada: gaussiana em x, com o x deslocado pela altura (inclinacao)
        w, h = lay.size
        banda = w * 0.22
        xc = -banda + (w + 2 * banda) * estilo.e_mov(p)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        perfil = np.exp(-(((xx + (yy - h / 2) * 0.35) - xc) / (banda / 2)) ** 2)
        alfa = np.asarray(lay.getchannel("A"), dtype=np.float32) / 255.0
        a = (perfil * alfa * 235).astype(np.uint8)
        luz = Image.new("RGBA", lay.size, estilo.cor(reflexo))
        luz.putalpha(Image.fromarray(a))
        lay = lay.copy()
        lay.alpha_composite(luz)
    cola(tela, lay, centro, k, (1 - ent) * estilo.desloca - sai * 18, escala=estilo.escala(ent))
    return tela
