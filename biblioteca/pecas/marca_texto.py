"""
Marca-texto: uma frase com a palavra-chave marcada. Ideia do rough-notation e do
Highlighter do Magic UI (MIT), em versao limpa.

    marca_texto.quadro(f, inicio, fim, estilo, texto="Quanto mais barato, piores os clientes",
                       palavra="piores", tipo="marca", marca_em=20)

`tipo`: "marca" (barra do acento atras da palavra, que vira cor de fundo), "sublinhado"
ou "circulo". A marcacao corre da esquerda para a direita a partir de `marca_em` (por
padrao, quando a frase termina de entrar) — trave na palavra do transcript.
"""
from PIL import Image

from .base import (acha_palavra, arco, bloco, cola, lin, mascara_retangulo, quebra,
                   recorta, retangulo, traco, vazio)

EXEMPLO = dict(inicio=0, fim=96, f=60, dados=dict(
    texto="Quanto mais barato, piores os clientes", palavra="piores", tipo="marca"))

TIPOS = ("marca", "sublinhado", "circulo")


def quadro(f, inicio, fim, estilo, texto, palavra=None, tipo="marca", marca_em=None,
           centro=(540, 860), tamanho=96, largura=880, peso=700, cor="texto"):
    if tipo not in TIPOS:
        raise ValueError(f"tipo '{tipo}': use {', '.join(TIPOS)}")
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    fonte = estilo.fonte("titulo", tamanho, peso)
    linhas = quebra(fonte, texto, largura)
    txt, caixas = bloco(linhas, fonte, estilo.cor(cor), entrelinha=1.14)

    m = 40                                          # respiro para a marca sair do texto
    lay = Image.new("RGBA", (txt.width + 2 * m, txt.height + 2 * m), (0, 0, 0, 0))
    cx = acha_palavra(linhas, caixas, fonte, palavra) if palavra else None
    inicio_marca = marca_em if marca_em is not None else inicio + estilo.q_entrada
    pm = estilo.e_mov(lin(f, inicio_marca, inicio_marca + max(8, estilo.q_entrada * 0.8)))

    if cx and tipo == "marca" and pm > 0:
        x0, y0, x1, y1 = cx
        pad = tamanho * 0.07                      # menos que meio espaco: nao encosta no vizinho
        bw, bh = (x1 - x0) + 2 * pad, (y1 - y0) * 0.86
        bx, by = x0 - pad + m, y0 + (y1 - y0) * 0.1 + m
        barra = retangulo(bw * pm, bh, tamanho * 0.14, estilo.cor("acento"))
        lay.alpha_composite(barra, (int(bx), int(by)))
        lay.alpha_composite(txt, (m, m))
        # a palavra vira a cor sobre o acento, so onde a barra ja passou
        sobre, _ = bloco(linhas, fonte, estilo.cor("sobre_acento"), entrelinha=1.14)
        cheio = Image.new("RGBA", lay.size, (0, 0, 0, 0))
        cheio.alpha_composite(sobre, (m, m))
        lay.alpha_composite(recorta(cheio, mascara_retangulo(
            lay.size, (bx, by, bx + bw * pm, by + bh))))
    else:
        lay.alpha_composite(txt, (m, m))
        if cx and pm > 0:
            x0, y0, x1, y1 = cx
            espessura = max(6, tamanho * 0.09)
            if tipo == "sublinhado":
                y = y1 + m - (y1 - y0) * 0.12
                lay.alpha_composite(traco(lay.width, lay.height, [(x0 + m, y), (x1 + m, y)],
                                          espessura, estilo.cor("acento"), pm))
            else:
                pw, ph = (x1 - x0) * 0.16 + 24, (y1 - y0) * 0.22
                el = arco((x1 - x0) + 2 * pw, (y1 - y0) + 2 * ph, espessura * 0.8,
                          estilo.cor("acento"), pm)
                lay.alpha_composite(el, (int(x0 - pw + m), int(y0 - ph + m)))

    cola(tela, lay, centro, k, (1 - ent) * 30 - sai * 18)
    return tela
