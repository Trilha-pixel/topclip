#!/usr/bin/env python3
"""
Peças de marca do TopClip, geradas em código com a mesma identidade do motion.

    ./topclip py docs/marca/gerar_marca.py

Gera em docs/img/:
    banner.png   1280x640 — topo do README e prévia de link do GitHub
    post.png     1080x1350 — post de Instagram (4:5)
    logo.png     512x512  — ícone quadrado (avatar, favicon grande)
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "topclip-motion" / "lib"))
import motor as V  # noqa: E402  — fontes, paleta, sombra e acabamento da identidade

ASSETS = RAIZ / "biblioteca" / "assets"
SAIDA = RAIZ / "docs" / "img"
TINTA = (42, 41, 44)
AMARELO = V.YELLOW
AZUL = V.BLUE
PAPEL_CLARO = (251, 248, 242)


def fonte(caminho, tamanho):
    return V.font(caminho, tamanho)


def papel(w, h):
    bg = Image.open(ASSETS / "BG_PAPER.png").convert("RGBA")
    s = max(w / bg.width, h / bg.height)
    bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1), Image.LANCZOS)
    return bg.crop(((bg.width - w) // 2, (bg.height - h) // 2, (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))


def icone(tam):
    """O símbolo: quadro de vídeo vertical preso por um clipe de papel (clip + clip)."""
    k = tam / 64.0
    ss = 4
    lay = Image.new("RGBA", (int(64 * k * ss), int(64 * k * ss)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    u = k * ss
    quadro = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    dq = ImageDraw.Draw(quadro)
    dq.rounded_rectangle([15.5 * u, 12 * u, 42.5 * u, 60 * u], radius=3.5 * u, fill=PAPEL_CLARO + (255,),
                         outline=TINTA + (255,), width=int(3.6 * u))
    dq.polygon([(24.5 * u, 28.5 * u), (35.5 * u, 36 * u), (24.5 * u, 43.5 * u)], fill=AMARELO + (255,))
    dq.line([(24.5 * u, 28.5 * u), (35.5 * u, 36 * u), (24.5 * u, 43.5 * u), (24.5 * u, 28.5 * u)],
            fill=TINTA + (255,), width=int(2.6 * u), joint="curve")
    quadro = quadro.rotate(7, resample=Image.BICUBIC, center=(29 * u, 36 * u))
    lay.alpha_composite(quadro)

    # clipe: as mesmas voltas do SVG do painel
    def arco(cx, cy, r, a0, a1, n=24):
        return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    pts = [(40.6, 19.3), (40.6, 5.4)] + arco(44, 5.4, 3.4, math.pi, 2 * math.pi) + [(47.4, 23.1)]
    pts += arco(44.68, 23.1, 2.72, 0, math.pi) + [(41.96, 6.4)] + arco(43.32, 6.4, 1.36, math.pi, 2 * math.pi) + [(44.68, 17)]
    d.line([(x * u, y * u) for x, y in pts], fill=AZUL + (255,), width=int(2.3 * u), joint="curve")
    return lay.resize((tam, tam), Image.LANCZOS)


def marca_texto(w, h, cor=AMARELO):
    """Faixa de marca-texto: retângulo levemente torto, com as pontas irregulares."""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).polygon([(w * 0.02, h * 0.18), (w * 0.99, 0), (w, h * 0.86), (0, h)], fill=cor + (255,))
    return lay


def wordmark(altura):
    """'Top' + 'Clip' em Archivo Black, com o marca-texto amarelo atrás de 'Clip'."""
    f = fonte(V.F_BLACK, altura)
    tr = -0.035 * altura                      # Archivo Black em corpo grande pede tracking negativo
    larg = lambda s: sum(f.getlength(ch) + tr for ch in s)
    w_top, w_clip = larg("Top"), larg("Clip")
    W, H = int(w_top + w_clip + altura * 0.3), int(altura * 1.35)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    faixa = marca_texto(int(w_clip + altura * 0.16), int(altura * 0.62))
    lay.alpha_composite(faixa, (int(w_top - altura * 0.06), int(altura * 0.55)))
    d = ImageDraw.Draw(lay)
    x = 0.0
    for ch in "TopClip":
        d.text((x, 0), ch, font=f, fill=TINTA)
        x += f.getlength(ch) + tr
    return lay


def foto_com_fita(largura, rot):
    """O frame de motion como foto colada: margem branca, fita crepe, sombra de contato."""
    img = Image.open(RAIZ / "docs" / "img" / "motion-end.jpg").convert("RGBA")
    h = int(largura * 16 / 9)
    img = img.resize((largura, h), Image.LANCZOS)
    m = int(largura * 0.035)
    card = Image.new("RGBA", (largura + 2 * m, h + 2 * m), PAPEL_CLARO + (255,))
    card.alpha_composite(img, (m, m))
    fita = Image.open(ASSETS / "A03_TAPE.png").convert("RGBA")
    fita = fita.crop(fita.getbbox()).crop((0, 0, int(fita.width * 0.33), fita.height))
    fita = fita.crop(fita.getbbox())
    s = (largura * 0.5) / fita.width
    fita = fita.resize((int(fita.width * s), int(fita.height * s)), Image.LANCZOS).rotate(-4, expand=True, resample=Image.BICUBIC)
    base = Image.new("RGBA", (card.width + 40, card.height + fita.height), (0, 0, 0, 0))
    base.alpha_composite(card, (20, fita.height // 2))
    base.alpha_composite(fita, ((base.width - fita.width) // 2, 0))
    return base.rotate(rot, expand=True, resample=Image.BICUBIC)


def colar(canvas, lay, pos, sombra=True):
    if sombra:
        canvas.alpha_composite(V.contact_shadow(canvas.size, lay, pos, dy=14, blur=22, opacity=0.28))
    canvas.alpha_composite(lay, (int(pos[0]), int(pos[1])))


def texto(canvas, xy, s, caminho, tam, cor=TINTA, tracking=0.0):
    d = ImageDraw.Draw(canvas)
    f = fonte(caminho, tam)
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=cor)
        x += f.getlength(ch) + tracking
    return x


def banner():
    W, H = 1280, 640
    c = papel(W, H)
    colar(c, icone(150), (78, 92), sombra=False)
    colar(c, wordmark(150), (238, 84), sombra=False)
    texto(c, (86, 300), "DO PODCAST AO SHORT,", V.F_COND, 66, tracking=1.5)
    texto(c, (86, 368), "DENTRO DO CLAUDE CODE.", V.F_COND, 66, tracking=1.5)
    c.alpha_composite(V.hand_underline(c.size, 92, 640, 446, progress=1.0, width=6, color=AZUL, seed=5))
    texto(c, (88, 500), "cortes · vertical 9:16 · motion · legenda", V.F_MONO, 26, cor=(91, 89, 94))
    texto(c, (88, 556), "@realfelipetop", V.F_MARKER, 34)
    texto(c, (370, 566), "github.com/realfelipetop/topclip", V.F_MONO, 22, cor=(91, 89, 94))
    colar(c, foto_com_fita(250, -5), (930, 22))
    return V.finish(c, grain=0.03, vignette=0.05, chroma=0, sat=0.96).convert("RGB")


def post():
    W, H = 1080, 1350
    c = papel(W, H)
    colar(c, icone(120), (84, 86), sombra=False)
    colar(c, wordmark(120), (214, 80), sombra=False)
    texto(c, (86, 270), "DO PODCAST", V.F_COND, 118, tracking=2)
    x = texto(c, (86, 392), "AO ", V.F_COND, 118, tracking=2)
    faixa = marca_texto(330, 74)
    c.alpha_composite(faixa, (int(x) - 10, 452))
    texto(c, (x, 392), "SHORT", V.F_COND, 118, tracking=2)
    texto(c, (88, 548), "o Claude corta, enquadra e anima.", V.F_SANS, 38, cor=(91, 89, 94))
    texto(c, (88, 600), "você escolhe o que fica.", V.F_SANS, 38, cor=(91, 89, 94))
    colar(c, foto_com_fita(330, 4), (620, 640))
    c.alpha_composite(V.hand_arrow(c.size, [(430, 905), (520, 945), (600, 1000)], progress=1.0, width=7, color=TINTA, seed=3, head=34))
    texto(c, (96, 820), "grátis e", V.F_MARKER, 52)
    texto(c, (96, 884), "open source", V.F_MARKER, 52)
    texto(c, (90, 1196), "@realfelipetop", V.F_MARKER, 46)
    texto(c, (90, 1262), "github.com/realfelipetop/topclip", V.F_MONO, 28, cor=(91, 89, 94))
    return V.finish(c, grain=0.03, vignette=0.05, chroma=0, sat=0.96).convert("RGB")


def logo():
    c = Image.new("RGBA", (512, 512), V.PAPER_LIGHT + (255,))
    colar(c, icone(430), (41, 41), sombra=False)
    return c.convert("RGB")


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome, fn in (("banner.png", banner), ("post.png", post), ("logo.png", logo)):
        im = fn()
        im.save(SAIDA / nome, optimize=True)
        print(f"  docs/img/{nome}  {im.width}x{im.height}")
