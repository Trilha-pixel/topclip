"""
Antes e depois: dois paineis com um divisor que corre e revela o "depois". Ideia do Image
Comparison do Motion Primitives (MIT).

    antes_depois.quadro(f, inicio, fim, estilo, antes="07_assets/raw/antes.png",
                        depois="07_assets/raw/depois.png", divisor_em=20)

`antes`/`depois`: caminho (relativo a raiz do projeto), imagem PIL ou None. Sem imagem, o
painel e chapado com `textos` em destaque (por exemplo dois precos). O divisor parte da
borda direita e para em `ate` (0,5 = no meio).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .base import cola, com_sombra, linha, lin, retangulo, vazio

EXEMPLO = dict(inicio=0, fim=110, f=80, dados=dict(textos=("R$ 50", "R$ 300"),
                                                     rotulos=("Antes", "Depois")))


def _painel(img, w, h, estilo, cor, texto, cor_texto, cx, cabe):
    """Painel cheio. O texto (sem imagem) fica centrado em `cx` — o meio da parte do
    painel que aparece com o divisor parado — e encolhe para caber em `cabe` px, longe
    da alca do divisor."""
    if img is not None:
        im = img if isinstance(img, Image.Image) else Image.open(estilo.raiz / img)
        return ImageOps.fit(im.convert("RGBA"), (w, h), Image.LANCZOS)
    p = Image.new("RGBA", (w, h), estilo.cor(cor))
    if texto:
        tam = int(h * 0.12)
        fonte = estilo.fonte("numero", tam, 700)
        if fonte.getlength(texto) > cabe:
            fonte = estilo.fonte("numero", int(tam * cabe / fonte.getlength(texto)), 700)
        t = linha(texto, fonte, estilo.cor(cor_texto))
        p.alpha_composite(t, (int(cx - t.width / 2), (h - t.height) // 2))
    return p


def _pilula(texto, estilo, fundo_cor, cor_texto, tamanho=34):
    t = linha(texto, estilo.fonte("apoio", tamanho, 600), estilo.cor(cor_texto))
    p = retangulo(t.width + tamanho * 1.2, t.height + tamanho * 0.5, tamanho, estilo.cor(fundo_cor))
    p.alpha_composite(t, ((p.width - t.width) // 2, (p.height - t.height) // 2))
    return p


def quadro(f, inicio, fim, estilo, antes=None, depois=None, textos=(None, None),
           rotulos=("Antes", "Depois"), caixa=(96, 470, 984, 1330), divisor_em=None, ate=0.5,
           raio=40):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    x0, y0, x1, y1 = caixa
    w, h = x1 - x0, y1 - y0
    cabe = w * min(ate, 1 - ate) - 2 * 70          # meia largura menos a alca (raio 34) e ar
    a = _painel(antes, w, h, estilo, "superficie", textos[0], "apoio", w * ate / 2, cabe)
    d = _painel(depois, w, h, estilo, "acento", textos[1], "sobre_acento", w * (1 + ate) / 2, cabe)

    ini = divisor_em if divisor_em is not None else inicio + estilo.q_entrada
    pd = estilo.e_mov(lin(f, ini, ini + estilo.q_entrada * 2))
    xd = int(w * (1 - (1 - ate) * pd))

    comp = d.copy()
    comp.alpha_composite(a.crop((0, 0, max(1, xd), h)), (0, 0))
    mask = retangulo(w, h, raio, (255, 255, 255, 255)).getchannel("A")
    comp.putalpha(mask)
    borda = (2, estilo.cor("linha")) if estilo.escuro else None
    if borda:
        comp.alpha_composite(retangulo(w, h, raio, (0, 0, 0, 0), borda))

    dr = ImageDraw.Draw(comp)
    if pd > 0:
        dr.rectangle([xd - 3, 0, xd + 3, h], fill=estilo.cor("sobre_acento"))
        r = 34
        dr.ellipse([xd - r, h / 2 - r, xd + r, h / 2 + r], fill=estilo.cor("sobre_acento"))
        c = estilo.cor("acento")
        dr.polygon([(xd - 8, h / 2 - 11), (xd - 8, h / 2 + 11), (xd - 20, h / 2)], fill=c)
        dr.polygon([(xd + 8, h / 2 - 11), (xd + 8, h / 2 + 11), (xd + 20, h / 2)], fill=c)
    if rotulos[0]:
        comp.alpha_composite(_pilula(rotulos[0], estilo, "fundo", "texto"), (28, 28))
    if rotulos[1] and pd > 0.3:
        p = _pilula(rotulos[1], estilo, "fundo", "texto")
        p.putalpha(p.getchannel("A").point(lambda v: int(v * min(1, (pd - 0.3) / 0.4))))
        comp.alpha_composite(p, (w - p.width - 28, 28))
    if not estilo.escuro:
        comp = com_sombra(comp, desfoque=28, opacidade=0.14, dy=12)
    cola(tela, comp, ((x0 + x1) / 2, (y0 + y1) / 2), k, (1 - ent) * 36 - sai * 18)
    return tela
