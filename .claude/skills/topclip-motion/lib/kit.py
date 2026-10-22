#!/usr/bin/env python3
"""
kit — mecanica da identidade TOPCLIP PAPEL.

Tudo que NAO e conteudo de cena mora aqui: fundo de mesa, carregamento de asset,
separacao de pecas, relogio com ponteiros desenhados, foto montada em cartao, medida
de texto manual, sombra, camera e as curvas de progresso.

E as RECEITAS (fim do arquivo): pecas de cena que ja foram feitas a mao numa run e
viraram funcao — retalho no tamanho de uso, fita-etiqueta, barra em hachura, item
riscado, etiqueta de preco, tira no topo do video, contagem a mao. Cada uma esta em
`referencias/receitas.md`, com o registro a que pertence e um exemplo renderizado.

O `compose.py` de cada projeto importa daqui e escreve so as cenas. Sem isso cada
projeto reimplementaria a identidade e ela divergiria.

    from kit import *
"""
import sys, math, hashlib, os
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter

import motor as V
try:
    import crt as CRT
except Exception:
    CRT = None
from motor import (W, H, INK, YELLOW, BLUE, RED, PAPER_LIGHT, boil_ctx, boil, boil_full, hand_pie, F_COND, F_MARKER, F_MONO,
                    ink_center, contact_shadow,
                    place, centered, text_layer, hand_circle, hand_arrow,
                    hand_underline, blue_line, clock_hands, rotate_anchor,
                    finish, ease, ease_in, hand_approx, hand_stroke, ink_bbox, ink_span,
                    sem_boil)
import desenho as D

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


def lin(frame, a, b):
    """Progresso LINEAR entre os frames a e b — para quem distribui varios eventos
    dentro de uma janela (os dez tracinhos de `hand_tally`), sem curva por cima."""
    if b <= a:
        return 1.0 if frame >= b else 0.0
    return max(0.0, min(1.0, (frame - a) / (b - a)))


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
_ampliadas = set()


def piece(name, index, width, rotation=0.0):
    """Uma peca isolada de um asset multi-objeto (fita, clipes, retalhos).
    Sem isso os quatro retalhos entram sempre em fileira e viram padrao, nao mesa.

    Peca AMPLIADA borra a fibra e a borda rasgada (o A10 tem ~360px por peca). Para
    papel grande use `scrap()`, que desenha o retalho no tamanho de uso."""
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
    if s > 1.25 and (name, index) not in _ampliadas and not V.SILENCIO:
        _ampliadas.add((name, index))
        print(f"  aviso: {name}#{index} ampliada {s:.1f}x ({im.width}->{width}px) — "
              f"a borda e a fibra borram. Use kit.scrap()/kit.fita() no tamanho de uso.",
              file=sys.stderr)
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
    card = _png("A05_CARD").rotate(90, expand=True)
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
        with sem_boil():      # medida estavel: com boil a largura mudaria por frame
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




# ===================================================================== RECEITAS
# Pecas de cena que foram escritas a mao nos compose.py da run aula-yt-teste (clip-005
# e clip-010) e custaram remontagem. Agora sao funcao. Documentacao, registro de cada
# uma e exemplo renderizado: `referencias/receitas.md`.

def _png(name):
    """Asset do projeto por nome. Se faltar em 07_assets/cutout mas existir em
    desenho.py, desenha na hora e guarda — asset faltando nao derruba o render no
    meio (foi o que o A05_CARD inexistente fazia com a saida wipe)."""
    f = CUT / f"{name}.png"
    if f.exists():
        return Image.open(f).convert("RGBA")
    if name not in D.ASSETS:
        raise FileNotFoundError(f"{f} nao existe e {name} nao esta em desenho.ASSETS")
    print(f"  aviso: {name}.png nao estava em 07_assets/cutout — desenhado agora "
          f"(desenho.py)", file=sys.stderr)
    im = D.ASSETS[name]()
    _salva(im, f)
    return im


def _salva(im, f):
    """Escrita atomica: os frames renderizam em varios processos ao mesmo tempo."""
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f"{f.stem}.{os.getpid()}.tmp")
    im.save(tmp, "PNG", compress_level=3)
    os.replace(tmp, f)


_DESENHO = hashlib.md5(Path(D.__file__).read_bytes()).hexdigest()[:8]
_uso = {}


def _no_tamanho(nome, fn):
    """Bitmap desenhado no tamanho de uso, guardado em 07_assets/cutout/_uso/. O nome
    leva o hash de desenho.py: mudou o desenho, o cache antigo deixa de valer."""
    if nome not in _uso:
        f = CUT / "_uso" / f"{nome}_{_DESENHO}.png"
        if f.exists():
            _uso[nome] = Image.open(f).convert("RGBA")
        else:
            _uso[nome] = fn()
            _salva(_uso[nome], f)
    return _uso[nome]


# ---------------------------------------------------------------- papel no tamanho de uso
_TIPOS = {
    "kraft":        (D.KRAFT, {}),
    "pautado":      (D.CADERNO, dict(pauta=D.PAUTA, margem=True)),
    "quadriculado": (D.QUADRICULADO, dict(grade=D.GRADE)),
    "cartao":       (D.CARTAO, {}),
    "folha":        (D.FOLHA, {}),
}


class Papel:
    """
    Retalho desenhado no tamanho de uso. `im` e o bitmap (ja rotacionado).
    `linhas` (y de cada pauta) e `margem` (x da linha vermelha) estao em px do bitmap
    SEM rotacao, `base` e o tamanho dele; `ponto(x, y)` leva um ponto desse referencial
    para o bitmap rotacionado — fracao medida antes de girar nao vale depois
    (armadilha 1).
    """

    def __init__(self, im, base, geo, rotation):
        self.im, self.base, self.rotation = im, base, rotation
        self.linhas, self.margem = geo["linhas"], geo["margem"]
        self.grade, self.pad = geo["grade"], geo["pad"]

    def ponto(self, x, y):
        if not self.rotation:
            return (x, y)
        return rotate_anchor(self.base, self.im.size, self.rotation, (x, y))


def scrap(tipo, w, h, seed=101, rotation=0.0, cor=None, **kw):
    """
    Retalho de papel rasgado JA no tamanho em que aparece (`w` x `h` de papel, sem o
    respiro). Tipos: kraft, pautado, quadriculado, cartao, folha. O pautado e o
    quadriculado saem em escala de caderno real para o quadro (pauta 92px — cabe uma
    linha de marcador de ~72px; grade 44px), nao proporcionais ao retalho.

    Use no lugar de `piece("A10_SCRAPS", ...)` sempre que o papel passar de ~450px:
    a peca do A10 tem ~360px e ampliada borra a fibra e a borda (receitas.md §1).
    `kw` vai para desenho.retalho (pauta=, grade=, margem=, torto=).
    """
    cor0, extra = _TIPOS[tipo]
    extra = {**extra, **kw}
    cor = tuple(cor or cor0)
    nome = (f"{tipo}_{w}x{h}_s{seed}_" + "".join(f"{k}{v}" for k, v in sorted(extra.items()))
            + "_c" + "-".join(str(v) for v in cor))
    base = _no_tamanho(nome, lambda: D.retalho(w, h, seed, cor, **extra))
    geo = D.geometria_retalho(w, h, extra.get("pauta", 0), extra.get("grade", 0),
                              extra.get("margem", False))
    im = base.rotate(rotation, resample=Image.BICUBIC, expand=True) if rotation else base
    return Papel(im, base.size, geo, rotation)


def fita(comprimento, seed=3, altura=None, rotation=0.0):
    """
    Tira de fita crepe desenhada no tamanho de uso, recortada na tinta como a peca do
    A03_TAPE. Sem `altura`, guarda a proporcao da peca 0 (620x190) — a da etiqueta
    aprovada. Fita ampliada engrossa o crepe e borra o rasgo das pontas.
    """
    comp = max(40, int(comprimento))
    alt = int(altura or comp * 190 / 620)
    arco = 14 * comp / 620
    def desenha():
        b = D._fita(comp, alt, seed, arco)
        return b.crop(b.getbbox())

    im = _no_tamanho(f"fita_{comp}x{alt}_s{seed}", desenha)
    return im.rotate(rotation, resample=Image.BICUBIC, expand=True) if rotation else im


# ---------------------------------------------------------------- movimento de pouso
def voo(prog, dist=620, bounce=14):
    """Deslocamento vertical de um heroi que entra JA EM VOO no frame 0 (o corte e a
    revelacao): cai `dist` px e passa um pouco do ponto (overshoot). Para subir de
    baixo, use dist e bounce negativos."""
    return -(1 - prog) * dist + math.sin(prog * math.pi) * bounce


def sombra_pouso(prog):
    """Sombra que cresce enquanto o papel desce: alto (pequena e clara) -> SH_CARD."""
    return dict(dy=int(5 + 6 * prog), blur=int(12 + 12 * prog),
                opacity=0.08 + 0.09 * prog)


# ---------------------------------------------------------------- fita-etiqueta
def tape_label(c, text, size, cx, cy, tape=1.0, write=1.0, rotation=-2.0, seed=21,
               drop=46, tracking=3, stroke_w=3, ratio=0.64, line_gap=1.12,
               shadow=SH_TAPE):
    """
    Fita-etiqueta: a fita e dimensionada PELA PALAVRA (largura = texto / 0,64) e a
    palavra vai no centro optico da fita. Registros: Mesa de pesquisa, Anotacao de
    campo. Aceita duas linhas ("projetos de\\nsite/sistema"): a fita cresce em altura.

    `tape` = pouso da fita (desce `drop` px aparecendo); `write` = a mao escrevendo.
    Fita e palavra sao UM objeto: montados juntos sem boil, giram juntos e recebem um
    campo de boil so — com campos separados a etiqueta descola do papel (armadilha 34).

    Desenha em `c` (quadro ou grupo local). Devolve a caixa da etiqueta em `c`.
    """
    if tape <= 0:
        return None
    nl = text.count("\n") + 1
    lab_w = hand_width(text, F_MARKER, size, tracking, seed, stroke_w) + size * 0.20
    comp = int(lab_w / ratio)
    alt = max(int(comp * 190 / 620), int(size * (1.15 * nl + 0.9))) if nl > 1 else None
    strip = fita(comp, seed=seed, altura=alt)
    pad = int(size * 0.6)
    lay = Image.new("RGBA", (strip.width + 2 * pad, strip.height + 2 * pad), (0, 0, 0, 0))
    icx, icy = ink_center(strip)
    with sem_boil():
        lay.alpha_composite(strip, (pad, pad))
        lay.alpha_composite(text_layer(lay.size, text, F_MARKER, size,
                                       (pad + icx, pad + icy), color=INK, anchor="mm",
                                       stroke_w=stroke_w, tracking=tracking, hand=True,
                                       seed=seed, mode="write", optical=True,
                                       line_gap=line_gap, progress=write))
    if rotation:
        lay = lay.rotate(rotation, resample=Image.BICUBIC, expand=True)
    pos = centered(lay, cx, cy - (1 - tape) * drop)
    place(c, fade(lay, tape), pos, shadow=shadow, kind="paper", boil_seed=seed)
    bb = lay.getbbox() or (0, 0, lay.width, lay.height)
    return (pos[0] + bb[0], pos[1] + bb[1], pos[0] + bb[2], pos[1] + bb[3])


# ---------------------------------------------------------------- barra em hachura
def hatch_bar(size, x0, y0, x1, y1, progress, seed=0, hatch=YELLOW, ink=INK, gap=22):
    """
    Barra desenhada a mao: contorno em duas passadas (sobe pela esquerda, cruza o
    topo, desce pela direita), depois hachura de marcador. A ordem e a da mao.
    Registro: Dado a mao — numero estimado nao ganha grafico limpo.
    """
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    if progress <= 0:
        return lay
    po = min(1.0, progress / 0.45)            # contorno primeiro
    ph = max(0.0, (progress - 0.45) / 0.55)   # depois a hachura
    if ph > 0:
        hl = Image.new("RGBA", size, (0, 0, 0, 0))
        dh = ImageDraw.Draw(hl)
        h = y1 - y0
        lines = []
        k = -h
        while k < (x1 - x0):
            lines.append([(x0 + k, y1), (x0 + k + h, y0)])
            k += gap
        shown = ph * len(lines)
        for i, ln in enumerate(lines):
            if i >= shown:
                break
            part = min(1.0, shown - i)
            pts = V.jitter([ln[0], ((ln[0][0] + ln[1][0]) / 2, (ln[0][1] + ln[1][1]) / 2),
                            ln[1]], 2.0, seed + i)
            pts = V.cut(V.smooth_path(pts, 10), part)
            V.stroke(dh, pts, 11, hatch + (230,), pressure=0.15, seed=seed + i)
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rectangle([x0 + 3, y0 + 3, x1 - 3, y1], fill=255)
        hl.putalpha(Image.fromarray(np.minimum(np.asarray(hl.getchannel("A")),
                                               np.asarray(m))))
        lay.alpha_composite(hl)
    d0 = ImageDraw.Draw(lay)
    for pas in range(2):
        loc = min(1.0, max(0.0, po * 2 - pas))
        if loc <= 0:
            break
        o = (pas * 3.0, -pas * 2.0)
        pts = [(x0 + o[0], y1), (x0 + o[0], y0 + o[1]), (x1 + o[0], y0 + o[1]),
               (x1 + o[0], y1)]
        dense = []
        for a, b in zip(pts[:-1], pts[1:]):
            st = max(2, int(math.dist(a, b) / 6))
            dense += [(a[0] + (b[0] - a[0]) * t / st, a[1] + (b[1] - a[1]) * t / st)
                      for t in range(st)]
        dense.append(pts[-1])
        dense = V.jitter(dense, 2.2, seed + 50 + pas)
        V.stroke(d0, V.cut(dense, loc), 6, ink + (255,), seed=seed + 60 + pas)
    return V._auto_boil(lay, "ink")


# ---------------------------------------------------------------- item riscado
def strike(size, x1, x2, y, progress, seed=0, color=RED, width=9):
    """Risco de caneta atravessando uma palavra: uma passada, subindo levemente."""
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    if progress <= 0:
        return lay
    n = 60
    pts = [(x1 + (x2 - x1) * i / n, y + 6 - 12 * i / n) for i in range(n + 1)]
    pts = V.jitter(pts, 2.6, seed)
    V.stroke(ImageDraw.Draw(lay), V.cut(pts, progress), width, color + (255,),
             pressure=0.18, seed=seed)
    return V._auto_boil(lay, "ink")


def strike_ink(size, bbox, progress, seed=0, color=RED, width=9, over=18):
    """
    Risca um texto pela CAIXA DA TINTA (`ink_bbox`), nao pela da fonte: o risco tem
    que cruzar o meio da palavra desenhada — medido pela fonte, ele passava acima das
    palavras (clip-010, laudo D2). Registro: Anotacao de campo ("nada disso").
    """
    x0, y0, x1, y1 = bbox
    return strike(size, x0 - over, x1 + over, (y0 + y1) / 2 + 2, progress, seed=seed,
                  color=color, width=width)


# ---------------------------------------------------------------- etiqueta de preco
def price_tag(c, cx, cy, pouso=1.0, write=1.0, text="R$", width=400, rotation=-7.0,
              seed=101, text_seed=52, text_size=None, fio_ate=None, drop=560):
    """
    Etiqueta de preco em kraft, com barbante saindo do furo e escapando pela borda.
    Registro: Processo — o preco e o DESTINO da seta ("o preco sai do que voce gera").

    Ja em voo no frame 0: `pouso` e a queda (cai `drop` px com overshoot). O barbante
    e o furo andam com a etiqueta. `write` escreve o texto (marcador, modo write).
    Devolve dict(pos, size, furo, topo, centro) no quadro, para a seta chegar nela.
    """
    pw = width - 2 * D.PAD
    papel = scrap("kraft", pw, int(pw * 250 / 360), seed=seed, rotation=rotation)
    tag = papel.im
    tpos = centered(tag, cx, cy + voo(pouso, drop, 12))
    bw, bh = papel.base
    hx, hy = papel.ponto(bw * 0.155, bh * 0.52)
    furo = (tpos[0] + hx, tpos[1] + hy)
    alvo = fio_ate or (-40, furo[1] - 150)
    fio = [furo, (furo[0] - 120, furo[1] - 60), (furo[0] - 260, furo[1] - 40), alvo]
    sl = Image.new("RGBA", c.size, (0, 0, 0, 0))
    V.stroke(ImageDraw.Draw(sl), V.smooth_path(V.jitter(fio, 3, 5), 18), 5,
             (238, 232, 214, 255), pressure=0.1, seed=5)
    c.alpha_composite(contact_shadow(c.size, sl, (0, 0), dy=3, blur=6, opacity=0.25))
    c.alpha_composite(sl)
    place(c, tag, tpos, shadow=SH_CARD, kind="paper")
    c.alpha_composite(hand_circle(c.size, furo[0], furo[1], 15, 15, progress=1.0,
                                  passes=1, width=5, color=INK, seed=9, amp=1.5))
    tx, ty = papel.ponto(bw * 0.58, bh * 0.5)
    centro = (tpos[0] + tx, tpos[1] + ty)
    c.alpha_composite(text_layer(c.size, text, F_MARKER, int(text_size or width * 0.375),
                                 centro, color=INK, anchor="mm", stroke_w=3, tracking=2,
                                 hand=True, seed=text_seed, mode="write", optical=True,
                                 progress=write))
    return dict(pos=tpos, size=tag.size, furo=furo, centro=centro,
                topo=(tpos[0] + tag.width / 2, tpos[1]))


# ---------------------------------------------------------------- tira no topo (overlay)
BILHETE = (1080, 660)       # canvas local do bilhete: monta tudo nele e gira junto


def bilhete(w=830, h=372, seed=104, tipo="cartao", at=(110, 92), size=BILHETE):
    """
    O papel da tira do topo, num canvas local. Escreva sobre ele (text_layer,
    hand_underline, tape_label com `c=grupo`) e entregue o grupo a `nota_topo`.
    Devolve (grupo, papel, origem_do_papel_no_grupo).
    """
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    papel = scrap(tipo, w, h, seed=seed)
    place(g, papel.im, at, kind="paper")
    return g, papel, at


def nota_topo(grupo, pouso, assenta=0.0, saida=0.0, frame=0, y=314, rot=-1.6):
    """
    Tira de papel no ALTO do video, sobre o cenario: o rosto fica livre. Registro:
    Anotacao de campo, em overlay (clip-005: a escala "R$ 2.500/mes ≈ aluguel" na tela
    desde o frame 0).

      pouso    0->1  cai ja em voo no frame 0, girando ate assentar
      assenta  0->1  deriva lenta (8px, 0,6 grau) — nao fica 3s parado
      saida    0->1  sobe e sai levando tudo junto; passe JA com ease_in

    Sombra SH_ONVID: sobre video a sombra precisa cravar mais, senao flutua. Devolve o
    frame RGBA do overlay com grao leve so na materia (o plate nao e tocado).
    Confira contra o plate que nada desce ate o topo da cabeca.
    """
    r = rot - (1 - pouso) * 3.0 + 0.6 * assenta + 2.5 * saida
    g = grupo.rotate(r, resample=Image.BICUBIC, expand=True)
    dy = -(1 - pouso) * 560 + 8 * assenta - saida * 760
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    place(c, g, centered(g, W / 2, y + dy), shadow=SH_ONVID, kind=None)
    return overlay_grain(c, frame)


def overlay_grain(img, frame):
    """Grao leve so na materia do papel; o alfa fica intacto (o plate nao e tocado)."""
    a = img.getchannel("A")
    out = finish(img, grain=0.028, vignette=0.0, chroma=0, sat=1.0,
                 seed=3000 + int(frame) // 2)
    out.putalpha(a)
    return out


# ---------------------------------------------------------------- conta a mao
def hand_tally(size, x, y, n, progress, passo=46, grupo=5, vao=34, altura=116,
               width=10, seed=50, color=INK):
    """
    Tracinhos de contagem, um depois do outro ("10 projetos" = dez tracinhos), em
    grupos de `grupo` separados por `vao`. `progress` 0->1 cobre os n em sequencia;
    cada tracinho leva ~14% do tempo. Um campo de boil para o conjunto.
    Registro: Dado a mao.
    """
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    dur = min(1.0, 3.0 / 22.0 * 10 / max(1, n))
    for i in range(n):
        a = i * (1 - dur) / max(1, n - 1)
        pk = max(0.0, min(1.0, (progress - a) / dur))
        if pk <= 0:
            break
        xx = x + 8 + i * passo + (i // grupo) * vao
        pts = [(xx, y), (xx + 3, y + altura * 0.45), (xx + 7, y + altura)]
        lay.alpha_composite(hand_stroke(size, pts, V.ease_draw(pk), width, color,
                                        seed + i, boil=False))
    return V._auto_boil(lay, "ink", seed=seed + 851)


def conta(c, linhas, x, y, progressos, passo=None, seed=61, stroke_w=3, tracking=2):
    """
    Conta montada a mao, item a item: cada linha e ESCRITA (modo write) quando o
    progresso dela anda — ancore cada uma na palavra do audio ("x R$ 300" no "300").
    Coluna alinhada a esquerda, como conta de papel. Registro: Dado a mao.

    `linhas` = [(texto, corpo), ...]. Devolve a caixa da tinta de cada linha, para
    sublinhar/circular o resultado (`ink_span` mede so um pedaco dela).
    """
    caixas, yy = [], y
    for k, ((texto, corpo), pr) in enumerate(zip(linhas, progressos)):
        kw = dict(anchor="lt", stroke_w=stroke_w, tracking=tracking, hand=True,
                  seed=seed + 10 * k)
        c.alpha_composite(text_layer(c.size, texto, F_MARKER, corpo, (x, yy), color=INK,
                                     mode="write", progress=pr, **kw))
        caixas.append(ink_bbox(texto, F_MARKER, corpo, (x, yy), size=c.size, **kw))
        yy += passo or int(corpo * 1.67)
    return caixas


def sublinhado_duplo(size, x0, x1, y, p1, p2, seed=81, width=9, color=INK):
    """Dois sublinhados curtos, o segundo um pouco menor — o "isto e o resultado" da
    conta. Ancore o primeiro na palavra (ex.: "mes"), o segundo logo depois."""
    lay = hand_underline(size, x0 - 6, x1 + 10, y, progress=p1, passes=1, width=width,
                         color=color, seed=seed, amp=2.5)
    lay.alpha_composite(hand_underline(size, x0 + 2, x1 + 4, y + 20, progress=p2,
                                       passes=1, width=width, color=color, seed=seed + 2,
                                       amp=2.5))
    return lay


# ---------------------------------------------------------------- revisao
def plate_falso():
    """Plate SINTETICO para julgar um overlay quando nao ha video (galeria de receitas,
    teste): parede escura, prateleira, cabeca e ombros em silhueta onde o rosto
    costuma ficar num selfie vertical. Nao serve para laudo D4 — so para composicao."""
    if "plate" not in _uso:
        im = Image.new("RGB", (W, H), (58, 54, 50))
        dr = ImageDraw.Draw(im)
        for y in range(H):
            k = y / H
            dr.line([(0, y), (W, y)], fill=(int(46 + 30 * k), int(43 + 27 * k),
                                              int(40 + 22 * k)))
        dr.rectangle([0, 520, W, 560], fill=(84, 70, 58))
        dr.rectangle([0, 560, W, 590], fill=(36, 32, 30))
        dr.ellipse([300, 760, 780, 1420], fill=(150, 118, 100))
        dr.ellipse([60, 1380, 1020, 2300], fill=(214, 210, 200))
        im = im.filter(ImageFilter.GaussianBlur(6))
        dr = ImageDraw.Draw(im)
        dr.text((40, H - 60), "plate sintetico", font=V.font(F_MONO, 26),
                fill=(150, 146, 138))
        _uso["plate"] = im.convert("RGBA")
    return _uso["plate"].copy()


def folha_de_estados(caminhos, destino, largura=360, rotulos=None):
    """Os estados de uma cena lado a lado, a 1/3 do tamanho (360px: a leitura a ~300px
    do laudo D2). Uma imagem para revisar em vez de quatro."""
    ims = [Image.open(c).convert("RGB") for c in caminhos]
    h = int(largura * 16 / 9)
    gap, topo = 10, 44
    folha = Image.new("RGB", (len(ims) * largura + (len(ims) + 1) * gap, h + topo + gap),
                      (32, 31, 33))
    dr = ImageDraw.Draw(folha)
    f = V.font(F_MONO, 22)
    for k, im in enumerate(ims):
        x = gap + k * (largura + gap)
        folha.paste(im.resize((largura, h), Image.LANCZOS), (x, topo))
        if rotulos:
            dr.text((x + 2, 12), rotulos[k], font=f, fill=(219, 214, 83))
    folha.save(destino)
    return destino
