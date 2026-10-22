"""
Moldura: filete duplo no acento que se desenha em volta do conteudo, com leques Art Deco
nos cantos. A assinatura do Luxo (pesquisa de 2026: Neo Deco), mas serve a qualquer estilo
que queira emoldurar uma cena.

    moldura.quadro(f, inicio, fim, estilo, caixa=(120, 420, 960, 1500))

O traco corre a partir do meio de cima, nos dois sentidos, e fecha embaixo; os leques
abrem quando o filete chega no canto. Combine com outra peca dentro da caixa.
"""
import math

from PIL import Image, ImageDraw

from .base import SS, W, H, cola, lin, vazio

EXEMPLO = dict(inicio=0, fim=96, f=60, dados=dict(caixa=(150, 560, 930, 1360)))


def _ponto(perimetro, d):
    """Ponto a distancia d ao longo do perimetro (lista de segmentos)."""
    for a, b in perimetro:
        L = math.dist(a, b)
        if d <= L:
            k = d / L if L else 0
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        d -= L
    return perimetro[-1][1]


def _meia(x0, y0, x1, y1, lado):
    """Meio perimetro: do meio de cima, descendo pelo `lado` (-1 esquerda, 1 direita), ate
    o meio de baixo."""
    cx = (x0 + x1) / 2
    xl = x0 if lado < 0 else x1
    pts = [(cx, y0), (xl, y0), (xl, y1), (cx, y1)]
    return list(zip(pts, pts[1:]))


def quadro(f, inicio, fim, estilo, caixa=(120, 420, 960, 1500), cor="acento", espessura=3,
           vao=14, leque=True):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    _, sai = estilo.envelope(f, inicio, fim)
    p = estilo.e_mov(lin(f, inicio, inicio + estilo.q_entrada * 2.2))
    x0, y0, x1, y1 = caixa
    m = 40                                   # respiro para os leques
    w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    c = estilo.cor(cor)
    lw = max(1, int(espessura * SS))

    for ins in ((0, vao) if vao else (0,)):
        a0, b0, a1, b1 = m + ins, m + ins, w - m - ins, h - m - ins
        for lado in (-1, 1):
            seg = _meia(a0, b0, a1, b1, lado)
            total = sum(math.dist(a, b) for a, b in seg)
            alvo = total * p
            pts, feito = [seg[0][0]], 0.0
            for a, b in seg:
                L = math.dist(a, b)
                if feito + L <= alvo:
                    pts.append(b)
                    feito += L
                else:
                    pts.append(_ponto([(a, b)], alvo - feito))
                    break
            if len(pts) > 1:
                d.line([(x * SS, y * SS) for x, y in pts], fill=c, width=lw, joint="curve")

    if leque and p > 0.25:
        k = min(1.0, (p - 0.25) / 0.6)
        for (cx, cy), ini in (((m, m), 0), ((w - m, m), 90), ((w - m, h - m), 180), ((m, h - m), 270)):
            for i, r in enumerate((18, 30, 42)):
                ri = r * k
                if ri < 2:
                    continue
                d.arc([(cx - ri) * SS, (cy - ri) * SS, (cx + ri) * SS, (cy + ri) * SS],
                      start=ini, end=ini + 90, fill=c, width=max(1, int(espessura * 0.8 * SS)))
    lay = big.resize((w, h), Image.LANCZOS)
    cola(tela, lay, ((x0 + x1) / 2, (y0 + y1) / 2), 1 - sai, -sai * 12)
    return tela
