"""
O lapis de cada estilo: o MESMO objeto, desenhado do jeito do estilo.

Um objeto (`pecas/objetos.py`) e uma lista de FORMAS com PAPEL, numa caixa de largura 1:

  corpo     a massa principal (o corpo do relogio)
  face      a area clara de leitura (o mostrador)
  detalhe   as partes secundarias (campainhas, barras comuns)
  destaque  a parte que importa (a barra do numero dito, o centro do ponteiro)
  traco     linha sem area (ponteiro, tracinho, eixo, alca)

O lapis decide como cada papel vira tinta, com as cores do estilo:

  limpo    ilustracao flat de produto: chapado em dois tons + o acento, sombra macia do
           objeto inteiro, sem contorno.
  impacto  adesivo: contorno preto grosso em toda forma, cor chapada, borda branca em volta
           da silhueta e sombra dura deslocada.
  luxo     gravura em latao: so traco fino (duplo no corpo), preenchimento escuro discreto,
           brilho atras e um reflexo; o traco SE DESENHA na entrada.

O Papel tem o desenho dele (`lib/desenho.py` + `lib/kit.py`): textura, mao, boil.
Objeto novo se escreve uma vez, em `objetos.py`, e sai nos tres lapis.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2
LAPIS = ("limpo", "impacto", "luxo")


# ---------------------------------------------------------------- formas

def _pontos_circulo(cx, cy, rx, ry=None, n=96, a0=-90.0, a1=270.0):
    ry = rx if ry is None else ry
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def circulo(cx, cy, r, papel="corpo", duplo=False):
    return dict(pts=_pontos_circulo(cx, cy, r), fechada=True, papel=papel, duplo=duplo,
                circ=(cx, cy, r))


def elipse(cx, cy, rx, ry, papel="corpo"):
    return dict(pts=_pontos_circulo(cx, cy, rx, ry), fechada=True, papel=papel, duplo=False)


def ret(x0, y0, x1, y1, raio=0.0, papel="corpo", duplo=False):
    raio = min(raio, (x1 - x0) / 2, (y1 - y0) / 2)
    if raio <= 0:
        pts = [(x0, y1), (x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    else:
        pts = []
        for cx, cy, a in ((x0 + raio, y0 + raio, 180), (x1 - raio, y0 + raio, 270),
                          (x1 - raio, y1 - raio, 0), (x0 + raio, y1 - raio, 90)):
            pts += _pontos_circulo(cx, cy, raio, n=12, a0=a, a1=a + 90)
        pts.append(pts[0])
    return dict(pts=pts, fechada=True, papel=papel, duplo=duplo)


def poli(pts, papel="corpo"):
    pts = list(pts)
    return dict(pts=pts + [pts[0]], fechada=True, papel=papel, duplo=False)


def linha(pts, esp=0.02, papel="traco"):
    return dict(pts=list(pts), fechada=False, papel=papel, esp=esp, duplo=False)


def arco(cx, cy, r, a0, a1, esp=0.02, papel="traco"):
    return dict(pts=_pontos_circulo(cx, cy, r, n=48, a0=a0, a1=a1), fechada=False,
                papel=papel, esp=esp, duplo=False)


def _corta(pts, p):
    """Os primeiros p (0..1) do comprimento da polilinha."""
    if p >= 1:
        return pts
    segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    falta = sum(segs) * max(0.0, p)
    out = [pts[0]]
    for (a, b), L in zip(zip(pts, pts[1:]), segs):
        if falta >= L:
            out.append(b)
            falta -= L
        else:
            k = falta / L if L else 0
            out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            break
    return out


# ---------------------------------------------------------------- cores por lapis

def _cores(lapis, estilo):
    """Papel da forma -> cor do estilo, por lapis. Tudo vem dos tokens: a marca entra."""
    c = estilo.cor
    # `vazado`: linha que precisa contrastar com a area de baixo (o check no disco do acento)
    if lapis == "limpo":
        # detalhe = um tom claro do proprio acento: contraste no fundo claro sem virar um
        # segundo acento (o bege da `linha` sumia no off-white)
        return {"corpo": c("acento"), "face": c("superficie"), "detalhe": _mistura(c("acento"), c("fundo"), 0.24),
                "destaque": c("acento"), "traco": c("texto"), "vazado": c("superficie")}
    if lapis == "impacto":
        return {"corpo": c("acento"), "face": (255, 255, 255, 255), "detalhe": c("apoio"),
                "destaque": c("acento"), "traco": (0, 0, 0, 255), "vazado": (255, 255, 255, 255)}
    # luxo: o latao e linha e luz; area e escura e discreta
    return {"corpo": c("superficie"), "face": c("superficie"), "detalhe": c("fundo"),
            "destaque": c("acento"), "traco": c("acento"), "vazado": c("fundo")}


def _mistura(a, b, k):
    """k de `a` sobre `b` (cores RGBA)."""
    return tuple(int(a[i] * k + b[i] * (1 - k)) for i in range(3)) + (255,)


# ---------------------------------------------------------------- desenho

def desenha(formas, largura, altura, estilo, lapis, progresso=1.0):
    """
    As formas (caixa de largura 1 e altura `altura`) desenhadas com o lapis, numa camada
    de `largura` px com margem para contorno, borda e sombra. `progresso` (0..1) e a
    entrada do lapis luxo, que se desenha; os outros ignoram (a peca anima por fora).
    """
    if lapis not in LAPIS:
        raise ValueError(f"lapis '{lapis}': use {', '.join(LAPIS)}")
    W = int(largura)
    m = int(W * 0.12)
    Wp, Hp = W + 2 * m, int(W * altura) + 2 * m
    s = W * SS

    def px(p):
        return ((p[0] * W + m) * SS, (p[1] * W + m) * SS)

    big = Image.new("RGBA", (Wp * SS, Hp * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    cores = _cores(lapis, estilo)

    if lapis == "limpo":
        for f in formas:
            pts = [px(p) for p in f["pts"]]
            if f["fechada"]:
                d.polygon(pts, fill=cores[f["papel"]])
            else:
                _traco(d, pts, f["esp"] * s, cores.get(f["papel"], cores["traco"]))
        lay = big.resize((Wp, Hp), Image.LANCZOS)
        return _sombra_macia(lay, W, estilo)

    if lapis == "impacto":
        contorno = max(3, int(0.026 * s))
        preto = (0, 0, 0, 255)
        for f in formas:
            pts = [px(p) for p in f["pts"]]
            if f["fechada"]:
                d.polygon(pts, fill=cores[f["papel"]])
                _traco(d, pts, contorno, preto)
            else:
                _traco(d, pts, f["esp"] * s * 1.25 + contorno * 0.3, cores.get(f["papel"], preto))
        lay = big.resize((Wp, Hp), Image.LANCZOS)
        return _adesivo(lay, W)

    # luxo: gravura. Cada forma, na ordem, cobre o que esta atras (area escura opaca) e
    # recebe o traco de latao, que corre com o progresso; o latao chapado do destaque
    # entra por ultimo. Sem a area opaca, o traco de tras aparecia atraves do corpo.
    p = max(0.0, min(1.0, progresso))
    p_traco = min(1.0, p / 0.75)
    p_area = max(0.0, (p - 0.45) / 0.55)
    fino = max(2, int(0.0075 * s))
    latao = estilo.cor("acento")
    if p_traco <= 0:
        return Image.new("RGBA", (Wp, Hp), (0, 0, 0, 0))
    for f in formas:
        pts = [px(q) for q in f["pts"]]
        if f["fechada"]:
            if f["papel"] == "destaque":
                if p_area > 0:
                    d.polygon(pts, fill=latao[:3] + (int(235 * p_area),))
            else:
                d.polygon(pts, fill=cores[f["papel"]])
        esp = fino if f["fechada"] else max(fino, f["esp"] * s * 0.55)
        if f["papel"] == "vazado":                 # vazado no latao: a cor do fundo, cheia
            _traco(d, _corta(pts, p_traco), max(esp, f["esp"] * s * 0.8), cores["vazado"])
            continue
        _traco(d, _corta(pts, p_traco), esp, latao)
        if f.get("duplo") and f.get("circ"):
            cx, cy, r = f["circ"]
            dentro = [px(q) for q in _pontos_circulo(cx, cy, r * 0.93)]
            _traco(d, _corta(dentro, p_traco), max(1, fino * 0.6), latao)
    lay = big.resize((Wp, Hp), Image.LANCZOS)
    return _brilho_de_latao(lay, W, m, estilo, p)


def _traco(d, pts, esp, cor):
    if len(pts) < 2 or esp <= 0:
        return
    esp = max(1, int(esp))
    d.line(pts, fill=cor, width=esp, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - esp / 2, y - esp / 2, x + esp / 2, y + esp / 2], fill=cor)


def _sombra_macia(lay, W, estilo):
    a = lay.getchannel("A")
    op = 0.10 if estilo.escuro else 0.20
    sombra = a.filter(ImageFilter.GaussianBlur(W * 0.035)).point(lambda v: int(v * op))
    out = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    base = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    base.putalpha(sombra)
    out.alpha_composite(base, (0, int(W * 0.03)))
    out.alpha_composite(lay)
    return out


def _adesivo(lay, W):
    """Borda branca em volta da silhueta (o recorte do adesivo) e sombra dura."""
    a = (np.asarray(lay.getchannel("A")) > 30).astype(np.uint8) * 255
    k = max(3, int(W * 0.045)) | 1
    # dilatacao pelo OpenCV (ja e dependencia): o MaxFilter do PIL levava ~4x o render
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    borda = Image.fromarray(cv2.dilate(a, disco))
    out = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sombra = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sombra.putalpha(borda.point(lambda v: int(v * 0.55)))
    d = int(W * 0.03)
    out.alpha_composite(sombra, (d, d))
    branco = Image.new("RGBA", lay.size, (255, 255, 255, 0))
    branco.putalpha(borda)
    out.alpha_composite(branco)
    out.alpha_composite(lay)
    return out


def _brilho_de_latao(lay, W, m, estilo, p):
    """Um halo quente atras do objeto: luz de vitrine, nao neon."""
    w, h = lay.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / (w * 0.55)) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)
    alfa = (np.clip(1 - r, 0, 1) ** 2 * 60 * min(1.0, p * 1.5)).astype(np.uint8)
    halo = Image.new("RGBA", lay.size, estilo.cor("acento")[:3] + (0,))
    halo.putalpha(Image.fromarray(alfa))
    out = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    out.alpha_composite(halo)
    out.alpha_composite(lay)
    return out
