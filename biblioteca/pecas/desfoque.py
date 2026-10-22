"""
Desfoque: a frase entra palavra a palavra, saindo do desfoque. Ideia do Text Effect do
Motion Primitives e do Blur Fade do Magic UI (MIT).

    desfoque.quadro(f, inicio, fim, estilo, texto="O preço baixo atrai o cliente errado")

O intervalo entre palavras e o `stagger` do perfil, encolhido se preciso para a frase
inteira entrar dentro do limite de coreografia do perfil (regra universal 6).
"""
from PIL import Image, ImageFilter

from .base import cola, largura_texto, linha, quebra, vazio

EXEMPLO = dict(inicio=0, fim=96, f=40, dados=dict(texto="O preço baixo atrai o cliente errado"))


def quadro(f, inicio, fim, estilo, texto, centro=(540, 860), tamanho=92, largura=880,
           peso=700, cor="texto", desfoque_max=18):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    _, sai = estilo.envelope(f, inicio, fim)
    fonte = estilo.fonte("titulo", tamanho, peso)
    linhas = quebra(fonte, texto, largura)
    n = sum(len(l.split()) for l in linhas)
    teto = estilo.mov["coreografia_max_s"] * 24
    passo = min(estilo.stagger, teto / max(1, n - 1))

    m = int(desfoque_max * 2)
    alt = int(tamanho * 1.14)
    lay_w = int(max(largura_texto(fonte, l) for l in linhas)) + 2 * m
    lay = Image.new("RGBA", (lay_w, alt * len(linhas) + 2 * m), (0, 0, 0, 0))
    espaco = fonte.getlength(" ")
    i = 0
    for li, l in enumerate(linhas):
        x = m + (lay_w - 2 * m - largura_texto(fonte, l)) / 2
        for p in l.split():
            kp = estilo.entrada(f, inicio + i * passo)
            if kp > 0:
                pal = linha(p, fonte, estilo.cor(cor))
                r = desfoque_max * (1 - min(1.0, kp))
                if r > 0.3:
                    grande = Image.new("RGBA", (pal.width + 2 * m, pal.height + 2 * m), (0, 0, 0, 0))
                    grande.alpha_composite(pal, (m, m))
                    pal = grande.filter(ImageFilter.GaussianBlur(r))
                    pos = (int(x - m), int(m + li * alt - m + (1 - kp) * 16))
                else:
                    pos = (int(x), int(m + li * alt))
                pal.putalpha(pal.getchannel("A").point(lambda v, a=min(1.0, kp): int(v * a)))
                lay.alpha_composite(pal, pos)
            x += fonte.getlength(p) + espaco
            i += 1
    cola(tela, lay, centro, 1 - sai, -sai * 18)
    return tela
