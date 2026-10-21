#!/usr/bin/env python3
"""
kit — mecanica da identidade TOPCLIP PAPEL.

Tudo que NAO e conteudo de cena mora aqui: fundo de mesa, carregamento de asset,
separacao de pecas, relogio com ponteiros desenhados, foto montada em cartao, medida
de texto manual, sombra, camera e as curvas de progresso.

O `compose.py` de cada projeto importa daqui e escreve so as cenas. Sem isso cada
projeto reimplementaria a identidade e ela divergiria.

    from kit import *
"""
import sys, math
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

import motor as V
try:
    import crt as CRT
except Exception:
    CRT = None
from motor import (W, H, INK, YELLOW, BLUE, PAPER_LIGHT, boil_ctx, boil, boil_full, hand_pie, F_COND, F_MARKER, F_MONO,
                    ink_center, contact_shadow,
                    place, centered, text_layer, hand_circle, hand_arrow,
                    hand_underline, blue_line, clock_hands, rotate_anchor,
                    finish, ease)

ROOT = Path(__file__).resolve().parent
CUT = ROOT / "07_assets" / "cutout"
PLATES = ROOT / "09_plates"
OUTF = ROOT / "08_images" / "frames"
OUTF.mkdir(parents=True, exist_ok=True)

# sombras por classe de material (06_VISUAL_IDENTITY §7)
SH_PAPER = dict(dy=6,  blur=14, opacity=0.15)
SH_CARD  = dict(dy=11, blur=24, opacity=0.17)
SH_TALL  = dict(dy=20, blur=32, opacity=0.20)
SH_TAPE  = dict(dy=3,  blur=9,  opacity=0.11)
SH_ONVID = dict(dy=14, blur=26, opacity=0.42)   # sobre video: precisa cravar mais

# acabamento por tipo de cena
FX_DESK  = dict(grain=0.050, vignette=0.06, chroma=1, sat=0.92)   # mesa de papel
FX_PLATE = dict(grain=0.028, vignette=0.02, chroma=0, sat=1.00)   # sobre o video

# CORPOS RECALIBRADOS para as fontes empacotadas: Archivo Narrow e 1,35x mais larga
# que a DIN Condensed do macOS, entao o mesmo corpo estouraria a composicao. Permanent
# Marker fica a 1,04x da Bradley Hand — o marcador quase nao mudou.

# medidas tiradas dos cutouts, em fracao do bitmap
DIAL_CX, DIAL_CY, DIAL_R = 0.4978, 0.6536, 0.4117      # A02_CLOCK
# Caixa da TELA medida em A11_NIGHT (nao centroide de brilho: o centroide puxava
# para o lado errado e o circulo saia grande demais e alto demais).
SCREEN   = (0.681, 0.588)                               # centro, em fracao da foto
SCREEN_WH = (0.202, 0.257)                              # tamanho, em fracao da foto
# A13_EMPTY: o notebook APAGADO ocupa o mesmo papel narrativo da tela acesa.
LAPTOP   = (0.272, 0.505)
LAPTOP_WH = (0.175, 0.200)


def p(frame, a, b):
    """Progresso de um evento entre os frames a e b. Curva de POUSO (ease-out)."""
    if frame <= a:
        return 0.0
    if frame >= b:
        return 1.0
    return ease((frame - a) / (b - a))


def d(frame, a, b):
    """Progresso de um TRACO sendo desenhado. Velocidade quase constante."""
    if frame <= a:
        return 0.0
    if frame >= b:
        return 1.0
    return V.ease_draw((frame - a) / (b - a))


def apply_camera(img, scale, focus=(540, 960)):
    """Push de leitura. Operacao de CAMERA: o quadro inteiro aproxima, nenhum objeto
    cresce sozinho (08_MOTION_BLUEPRINT §6). Sem isso o triptico nao representa o
    que vai ao ar."""
    if scale <= 1.0001:
        return img
    big = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    fx, fy = focus[0] / W, focus[1] / H
    ox = (big.width - W) * fx
    oy = (big.height - H) * fy
    return big.crop((int(ox), int(oy), int(ox) + W, int(oy) + H))


def bg_paper():
    im = Image.open(CUT.parent / "raw" / "BG_PAPER.png").convert("RGBA")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s + 1), int(im.height * s + 1)), Image.LANCZOS)
    return im.crop(((im.width - W) // 2, (im.height - H) // 2,
                    (im.width - W) // 2 + W, (im.height - H) // 2 + H))


def asset(name, width, rotation=0.0):
    return V.load_cutout(CUT / f"{name}.png", target_w=width, rotation=rotation)


_pieces = {}


def piece(name, index, width, rotation=0.0):
    """Uma peca isolada de um asset multi-objeto (fita, clipes, retalhos).
    Sem isso os quatro retalhos entram sempre em fileira e viram padrao, nao mesa."""
    if name not in _pieces:
        im = Image.open(CUT / f"{name}.png").convert("RGBA")
        alpha = (np.asarray(im.getchannel("A")) > 110).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(alpha, 8)
        order = sorted(range(1, n), key=lambda i: -st[i, cv2.CC_STAT_AREA])
        out = []
        for i in order:
            x, y, w, h, _ = st[i]
            sub = im.crop((x, y, x + w, y + h)).copy()
            m = Image.fromarray(((lab[y:y + h, x:x + w] == i) * 255).astype(np.uint8))
            a2 = Image.fromarray(np.minimum(np.asarray(sub.getchannel("A")),
                                            np.asarray(m)))
            sub.putalpha(a2)
            out.append(sub)
        _pieces[name] = out
    im = _pieces[name][index % len(_pieces[name])]
    s = width / im.width
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return im.rotate(rotation, resample=Image.BICUBIC, expand=True) if rotation else im


def asset_anchor(name, width, rotation, frac):
    """Onde um ponto marcado em fracao do cutout cai depois de escalar E rotacionar.
    Fracao medida no bitmap original nao vale no bitmap rotacionado (expand muda o
    referencial) — mesmo erro de classe que o do mostrador do relogio."""
    base = V.load_cutout(CUT / f"{name}.png", target_w=width)
    pt = (frac[0] * base.width, frac[1] * base.height)
    if not rotation:
        return base, pt
    rot = base.rotate(rotation, resample=Image.BICUBIC, expand=True)
    return rot, rotate_anchor(base.size, rot.size, rotation, pt)


_night = {}


def photo_card(width, rotation=0.0, photo="A11_NIGHT", focus=None, focus_wh=None):
    """
    Fotografia noturna montada em cartao de papel rasgado, como copia impressa com
    margem branca grossa. A margem nao e enfeite: e ela que separa
    a foto azul-escura do fundo azul-escuro do estudio. Sem cartao, o overlay some.

    Devolve (imagem, ancora_da_tela, rx, ry) — ancora e raios do circulo de anotacao,
    derivados da CAIXA medida da tela, ja corrigidos pela rotacao.
    """
    focus = focus or SCREEN
    focus_wh = focus_wh or SCREEN_WH
    key = (photo, round(width), round(rotation, 2))
    if key in _night:
        return _night[key]
    card = Image.open(CUT / "A05_CARD.png").convert("RGBA").rotate(90, expand=True)
    ph_im = Image.open(CUT / f"{photo}.png").convert("RGBA")

    s = width / card.width
    card = card.resize((int(card.width * s), int(card.height * s)), Image.LANCZOS)
    pw = int(card.width * 0.865)
    ph = int(pw * ph_im.height / ph_im.width)
    ph_im = ph_im.resize((pw, ph), Image.LANCZOS)

    px = (card.width - pw) // 2
    py = int((card.height - ph) * 0.42)          # margem inferior maior, como copia real
    # sombra fina da foto sobre o cartao: sao dois papeis, nao um so
    card.alpha_composite(contact_shadow(card.size, ph_im, (px, py), dy=4, blur=9,
                                        opacity=0.30))
    card.alpha_composite(ph_im, (px, py))

    anchor = (px + focus[0] * pw, py + focus[1] * ph)
    rx, ry = focus_wh[0] * pw * 0.82, focus_wh[1] * ph * 0.88
    if rotation:
        old = card.size
        card = card.rotate(rotation, resample=Image.BICUBIC, expand=True)
        anchor = rotate_anchor(old, card.size, rotation, anchor)
    _night[key] = (card, anchor, rx, ry)
    return card, anchor, rx, ry


_hw_cache = {}


def hand_width(text, fontpath, size, tracking, seed, stroke_w=2):
    """
    Largura REAL do texto manual, medida no desenho.
    `V.text_width` soma avancos de fonte e ignora que o modo `hand` rotaciona e desloca
    cada caractere — subestima em ate 20%. Foi por isso que "VIBE CODING" e
    "FUNCIONANDO" vazaram para fora da fita: a fita era dimensionada por uma largura
    menor que a do texto que ia por cima dela.
    """
    key = (text, fontpath, size, tracking, seed, stroke_w)
    if key not in _hw_cache:
        lay = text_layer((W, H), text, fontpath, size, (W // 2, H // 2), anchor="mm",
                         stroke_w=stroke_w, tracking=tracking, hand=True, seed=seed)
        bb = lay.getbbox()
        _hw_cache[key] = (bb[2] - bb[0]) if bb else V.text_width(text, fontpath, size,
                                                                tracking)
    return _hw_cache[key]


def fade(im, k):
    if k >= 1.0:
        return im
    o = im.copy()
    o.putalpha(o.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, k)))))
    return o


_dial_cache = {}


def clean_dial():
    """Mostrador com os ponteiros originais apagados. Calculado uma vez."""
    if "im" in _dial_cache:
        return _dial_cache["im"]
    im = Image.open(CUT / "A02_CLOCK.png").convert("RGBA")
    a = np.asarray(im).copy()
    h, w = a.shape[:2]
    cx, cy, r = DIAL_CX * w, DIAL_CY * h, DIAL_R * w
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    hands = ((d < r * 0.80) & (lum < 175)).astype(np.uint8)
    hands = cv2.dilate(hands, np.ones((3, 3), np.uint8), iterations=3)
    ring = (d > r * 0.30) & (d < r * 0.60) & (lum > 205)
    dial_rgb = a[..., :3][ring].mean(axis=0)
    patch = a[..., :3].astype(np.float32).copy()
    for c in range(3):
        patch[..., c] = np.where(hands > 0, dial_rgb[c], patch[..., c])
    patch = cv2.GaussianBlur(patch, (0, 0), 1.6)
    a[..., :3] = np.where(hands[..., None] > 0, patch, a[..., :3]).astype(np.uint8)
    _dial_cache["im"] = Image.fromarray(a)
    return _dial_cache["im"]


def clock_at(minutes, width, rotation=0.0):
    """
    Relogio com os ponteiros DESENHADOS POR NOS, a partir de um total em minutos
    (aceita fracao, entao o ponteiro pode varrer). A hora vira dado controlado e
    animavel — antes era estatica, o que deixava o objeto morto em cena.

    Devolve (imagem, centro_do_mostrador, raio) ja corrigidos pela rotacao.
    """
    im = clean_dial().copy()
    w, h = im.size
    cx, cy, r = DIAL_CX * w, DIAL_CY * h, DIAL_R * w
    hh, mm = int(minutes // 60), minutes % 60.0
    im.alpha_composite(clock_hands(im.size, cx, cy, r, hh, mm,
                                   width=max(5, int(r * 0.070))))
    s = width / im.width
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    c2, r2 = (cx * s, cy * s), r * s
    if rotation:
        old = im.size
        im = im.rotate(rotation, resample=Image.BICUBIC, expand=True)
        c2 = rotate_anchor(old, im.size, rotation, c2)
    return im, c2, r2


