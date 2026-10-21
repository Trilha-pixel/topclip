#!/usr/bin/env python3
"""
desenho — assets da identidade TOPCLIP PAPEL desenhados em codigo.

O padrao do TopClip: o Claude DESENHA o objeto em vez de pedir a um gerador de imagem.
O PNG ja sai com alfa (nao passa pelo recorte), nao tem texto de IA, e cada parte do
objeto pode virar camada animavel.

    ./topclip py .claude/skills/topclip-motion/lib/desenho.py biblioteca/assets
    ./topclip py .claude/skills/topclip-motion/lib/desenho.py biblioteca/assets --so A02_CLOCK

Os nomes e as GEOMETRIAS seguem o que `kit.py` espera. O relogio, por exemplo, tem o
mostrador exatamente em (DIAL_CX, DIAL_CY, DIAL_R) e os tracinhos alem de 0,80r — dentro
desse raio o `clean_dial()` apaga tudo que for escuro para redesenhar os ponteiros.

Para um objeto novo: escreva uma funcao `desenha_<NOME>(seed) -> Image RGBA`, registre
em ASSETS e siga as mesmas regras — textura de papel/material, borda nunca vetorial
perfeita, nenhuma sombra embutida (sombra e camada, ver `kit.SH_*`).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

# A geometria que `kit.clock_at()` le do relogio. Copiada, nao importada: importar o kit
# cria as pastas de projeto ao lado dele. Se mudar la, mude aqui.
DIAL_CX, DIAL_CY, DIAL_R = 0.4978, 0.6536, 0.4117

SS = 2          # supersampling: desenha em 2x e reduz, para borda suave sem vetor perfeito

PAPER = (217, 216, 209)
TAPE = (191, 187, 174)
INK = (55, 54, 57)


# ------------------------------------------------------------------ textura
def ruido(h, w, seed, escalas=((96, 0.5), (24, 0.3), (6, 0.2))):
    """Ruido multiescala em [-1, 1]. Mancha grande + grao medio + fibra fina."""
    r = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    for s, peso in escalas:
        pequeno = r.standard_normal((max(2, h // s), max(2, w // s))).astype(np.float32)
        out += cv2.resize(pequeno, (w, h), interpolation=cv2.INTER_CUBIC) * peso
    return out / (np.abs(out).max() + 1e-6)


def fibras(h, w, seed, n, comp=(6, 22)):
    """Fibras curtas de papel em direcoes aleatorias. Campo em [-1, 1]."""
    r = np.random.default_rng(seed)
    f = np.zeros((h, w), np.float32)
    for _ in range(n):
        x, y = r.uniform(0, w), r.uniform(0, h)
        L, a = r.uniform(*comp), r.uniform(0, math.pi)
        cv2.line(f, (int(x), int(y)), (int(x + L * math.cos(a)), int(y + L * math.sin(a))),
                 float(r.choice([-1.0, 1.0]) * r.uniform(0.4, 1.0)), 1, cv2.LINE_AA)
    return cv2.GaussianBlur(f, (0, 0), 0.6)


def textura(rgb, h, w, seed, mancha=0.035, fibra=0.05, n_fibras=None):
    """Base de cor com mancha e fibra. Devolve array float32 HxWx3."""
    base = np.ones((h, w, 3), np.float32) * np.array(rgb, np.float32)
    k = 1.0 + mancha * ruido(h, w, seed)
    k += fibra * fibras(h, w, seed + 1, n_fibras or (h * w) // 900)
    return base * k[..., None]


def para_rgba(rgb_f, alfa_f):
    """rgb float HxWx3 + alfa float HxW [0..1] -> Image RGBA reduzida do supersampling."""
    rgb = np.clip(rgb_f, 0, 255).astype(np.uint8)
    a = np.clip(alfa_f * 255, 0, 255).astype(np.uint8)
    im = Image.fromarray(np.dstack([rgb, a]), "RGBA")
    if SS > 1:
        im = im.resize((im.width // SS, im.height // SS), Image.LANCZOS)
    return im


# ------------------------------------------------------------------ contornos
def _suave(n, seed, corr):
    """Passeio aleatorio suavizado: deslocamento correlacionado ao longo da borda."""
    r = np.random.default_rng(seed)
    v = r.standard_normal(n + 2 * corr)
    k = np.hanning(2 * corr + 1)
    v = np.convolve(v, k / k.sum(), mode="same")[corr:corr + n]
    return v / (np.abs(v).max() + 1e-6)


def contorno(cantos, seed, amp=5.0, fino=1.6, passo=4.0, corr=10, por_lado=None):
    """
    Poligono fechado passando pelos cantos, com cada lado deslocado na normal por ruido
    correlacionado (amp) + serrilhado fino (fino). Borda de papel rasgado, nunca reta.
    `por_lado` permite amp diferente por lado: [(amp, fino), ...].
    """
    pts = []
    r = np.random.default_rng(seed + 99)
    for i, p0 in enumerate(cantos):
        p1 = cantos[(i + 1) % len(cantos)]
        a, f = por_lado[i] if por_lado else (amp, fino)
        L = math.dist(p0, p1)
        n = max(3, int(L / passo))
        nx, ny = -(p1[1] - p0[1]) / L, (p1[0] - p0[0]) / L
        desl = _suave(n, seed + i * 17, corr) * a + r.standard_normal(n) * f
        desl[0] = desl[-1] = 0
        for j in range(n):
            t = j / n
            pts.append((p0[0] + (p1[0] - p0[0]) * t + nx * desl[j],
                        p0[1] + (p1[1] - p0[1]) * t + ny * desl[j]))
    return pts


def mascara(h, w, pts):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.asarray(m, np.float32) / 255.0


def borda_clara(rgb_f, m, largura, ganho):
    """Fibra exposta no rasgo: a borda do papel rasgado e mais clara que a face."""
    er = cv2.erode((m > 0.5).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=largura)
    rim = np.clip(m - er.astype(np.float32), 0, 1)
    rim = cv2.GaussianBlur(rim, (0, 0), 0.8)
    return rgb_f + (255 - rgb_f) * (rim * ganho)[..., None]


def lado_a_lado(pecas, gap=40):
    """Junta pecas numa folha so, separadas por transparencia — `kit.piece()` separa de
    volta por componente conexo, entao o gap tem que ser transparente de verdade."""
    W = sum(p.width for p in pecas) + gap * (len(pecas) + 1)
    H = max(p.height for p in pecas) + 2 * gap
    folha = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = gap
    for p in pecas:
        folha.alpha_composite(p, (x, (H - p.height) // 2))
        x += p.width + gap
    return folha


# ------------------------------------------------------------------ BG_PAPER
def desenha_BG_PAPER(seed=1):
    """Papel marfim pontilhado, 1080x1920. O chao de toda cena de mesa."""
    w, h = 1080 * SS, 1920 * SS
    rgb = textura(PAPER, h, w, seed, mancha=0.022, fibra=0.035, n_fibras=(w * h) // 500)
    # envelhecimento irregular, bem discreto
    rgb *= (1.0 - 0.018 * np.clip(ruido(h, w, seed + 5, ((400, 1.0),)), 0, 1))[..., None]

    pontos = np.zeros((h, w), np.float32)
    r = np.random.default_rng(seed + 7)
    passo = 40 * SS
    for y in range(passo // 2, h, passo):
        for x in range(passo // 2, w, passo):
            rad = (1.85 + r.uniform(-0.25, 0.25)) * SS
            cv2.circle(pontos, (int(x + r.uniform(-0.4, 0.4) * SS), int(y + r.uniform(-0.4, 0.4) * SS)),
                       int(round(rad)), float(r.uniform(0.70, 0.95)), -1, cv2.LINE_AA)
    pontos = cv2.GaussianBlur(pontos, (0, 0), 0.5 * SS)
    tinta = np.array((150, 146, 138), np.float32)
    rgb = rgb * (1 - pontos[..., None]) + tinta * pontos[..., None]
    im = para_rgba(rgb, np.ones((h, w), np.float32))
    return im.convert("RGB").convert("RGBA")


# ------------------------------------------------------------------ A03_TAPE
def _fita(comp, alt, seed, arco):
    w, h = comp * SS, alt * SS
    pad = 14 * SS
    W, H = w + 2 * pad, h + 2 * pad + int(arco * SS) + 4 * SS
    cantos = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
    # pontas rasgadas a mao (serrilha forte), lados longos quase retos
    lados = [(0.8 * SS, 0.35 * SS), (3.2 * SS, 2.6 * SS), (0.8 * SS, 0.35 * SS), (3.2 * SS, 2.6 * SS)]
    pts = contorno(cantos, seed, passo=2.2 * SS, corr=3, por_lado=lados)
    m = mascara(H, W, pts)

    rgb = textura(TAPE, H, W, seed, mancha=0.03, fibra=0.03)
    # crepe: rugas finas ATRAVESSANDO a fita, levemente onduladas
    r = np.random.default_rng(seed + 3)
    crepe = np.zeros((H, W), np.float32)
    x = 0.0
    while x < W:
        x += r.uniform(2.0, 5.5) * SS
        off = r.uniform(-1.5, 1.5) * SS
        cv2.line(crepe, (int(x), 0), (int(x + off), H), float(r.uniform(0.3, 1.0)), 1, cv2.LINE_AA)
    crepe = cv2.GaussianBlur(crepe, (0, 0), 0.7 * SS)
    rgb *= (1.0 - 0.10 * crepe)[..., None]
    rgb = borda_clara(rgb, m, 1, 0.10)

    # fita crepe e meio translucida: o papel de baixo aparece um pouco
    alfa = m * 0.93

    # arco: a fita pousa curva, nunca como retangulo
    xs = np.arange(W, dtype=np.float32)
    dy = arco * SS * (1 - ((2 * xs / W) - 1) ** 2)
    mapx = np.tile(xs, (H, 1))
    mapy = np.arange(H, dtype=np.float32)[:, None] - dy[None, :]
    rgb = cv2.remap(rgb, mapx, mapy, cv2.INTER_LINEAR, borderValue=0)
    alfa = cv2.remap(alfa, mapx, mapy, cv2.INTER_LINEAR, borderValue=0)
    return para_rgba(rgb, alfa)


def desenha_A03_TAPE(seed=3):
    """Quatro tiras de fita crepe. A primeira e a de etiqueta: o texto vai por cima."""
    tiras = [_fita(620, 190, seed, 14), _fita(420, 112, seed + 1, 7),
             _fita(300, 104, seed + 2, -5), _fita(240, 100, seed + 3, 4)]
    return lado_a_lado(tiras)


# ------------------------------------------------------------------ A04_CLIPS
def _clipe(comp, seed, rot):
    """Clipe Gem: tres voltas aninhadas, arame cilindrico fosco."""
    u = comp / 7.0                      # unidade: o clipe tem 7u x 2u
    t = max(3.0, u * 0.17)              # espessura do arame
    pad = int(t * 3)
    L = 7.0

    def arco(cx, cy, r, a0, a1, n=28):
        return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
                for i in range(n + 1)]

    # y para baixo; o desenho em u, centrado em y = 0
    path = [(L - 1.9, -1.0), (1.0, -1.0)]
    path += arco(1.0, 0.0, 1.0, -math.pi / 2, -3 * math.pi / 2)
    path += [(L - 0.8, 1.0)]
    path += arco(L - 0.8, 0.2, 0.8, math.pi / 2, -math.pi / 2)
    path += [(1.3, -0.6)]
    path += arco(1.3, -0.2, 0.4, -math.pi / 2, -3 * math.pi / 2)
    path += [(L - 2.6, 0.2)]

    W, H = int(comp + 2 * pad) * SS, int(2 * u + 2 * pad) * SS
    pts = [((x * u + pad) * SS, ((y + 1) * u + pad) * SS) for x, y in path]
    rgb = np.zeros((H, W, 3), np.float32)
    alfa = np.zeros((H, W), np.float32)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # cilindro fosco: escuro na borda, meio-tom, brilho estreito deslocado para a luz
    camadas = [((96, 98, 103), 1.00, (0, 0)), ((150, 152, 157), 0.62, (-0.18, -0.18)),
               ((196, 198, 202), 0.24, (-0.26, -0.26))]
    for cor, k, (ox, oy) in camadas:
        larg = max(1, int(t * k * SS))
        q = [(x + ox * t * SS, y + oy * t * SS) for x, y in pts]
        d.line(q, fill=cor + (255,), width=larg, joint="curve")
        for x, y in (q[0], q[-1]):
            rr = larg / 2
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=cor + (255,))
    arr = np.asarray(im, np.float32)
    rgb, alfa = arr[..., :3], arr[..., 3] / 255.0
    rgb = rgb * (1 + 0.04 * ruido(H, W, seed, ((8, 1.0),)))[..., None]
    out = para_rgba(rgb, alfa)
    return out.rotate(rot, resample=Image.BICUBIC, expand=True)


def desenha_A04_CLIPS(seed=4):
    return lado_a_lado([_clipe(300, seed, 8), _clipe(260, seed + 1, -14), _clipe(230, seed + 2, 3)])


# ------------------------------------------------------------------ A10_SCRAPS
def _retalho(w, h, seed, cor, pautado=False, quadriculado=False):
    w, h = w * SS, h * SS
    pad = 16 * SS
    W, H = w + 2 * pad, h + 2 * pad
    r = np.random.default_rng(seed)
    j = lambda: r.uniform(-0.07, 0.07) * min(w, h)
    cantos = [(pad + j(), pad + j()), (pad + w + j(), pad + j()),
              (pad + w + j(), pad + h + j()), (pad + j(), pad + h + j())]
    pts = contorno(cantos, seed, amp=7.5 * SS, fino=2.2 * SS, passo=3 * SS, corr=7)
    m = mascara(H, W, pts)
    rgb = textura(cor, H, W, seed, mancha=0.04, fibra=0.06)
    if pautado:
        for y in range(pad + 34 * SS, H, 34 * SS):
            cv2.line(rgb, (0, y), (W, y), (148, 172, 196), max(1, SS), cv2.LINE_AA)
        cv2.line(rgb, (pad + 48 * SS, 0), (pad + 48 * SS, H), (196, 126, 126), max(1, SS), cv2.LINE_AA)
    if quadriculado:
        for v in range(pad, max(W, H), 22 * SS):
            cv2.line(rgb, (v, 0), (v, H), (176, 186, 194), 1, cv2.LINE_AA)
            cv2.line(rgb, (0, v), (W, v), (176, 186, 194), 1, cv2.LINE_AA)
    rgb = borda_clara(rgb, m, 2, 0.22)
    return para_rgba(rgb, m)


def desenha_A10_SCRAPS(seed=10):
    """Quatro retalhos de papel rasgado: kraft, caderno pautado, quadriculado, cartao."""
    return lado_a_lado([
        _retalho(300, 220, seed, (190, 164, 126)),
        _retalho(340, 250, seed + 1, (238, 234, 223), pautado=True),
        _retalho(260, 210, seed + 2, (226, 226, 220), quadriculado=True),
        _retalho(230, 180, seed + 3, (206, 200, 184)),
    ])


# ------------------------------------------------------------------ A02_CLOCK
def desenha_A02_CLOCK(seed=2):
    """
    Despertador de duas campainhas, mostrador SEM numeros (so tracinhos).
    Os ponteiros nao estao aqui: `kit.clock_at()` desenha a hora que a cena pedir.
    """
    w = 900 * SS
    h = int(w * 1.5)
    cx, cy, r = DIAL_CX * w, DIAL_CY * h, DIAL_R * w
    Rb = r * 1.17                       # corpo
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cromo_esc, cromo, cromo_cla = (118, 120, 125), (168, 170, 175), (206, 208, 211)

    def disco(x, y, rr, cor):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=cor + (255,))

    # alca: nasce ATRAS das campainhas (desenhada antes delas) e passa por cima
    ax, ay, topo = Rb * 0.58, cy - Rb * 1.10, cy - Rb * 1.62
    alca = [(cx + x, topo + (ay - topo) * (x / ax) ** 2)
            for x in np.linspace(-ax, ax, 60)]
    for cor, k in ((cromo_esc, 1.0), (cromo, 0.50)):
        d.line(alca, fill=cor + (255,), width=int(w * 0.034 * k), joint="curve")
    # campainhas (atras do corpo)
    for lado in (-1, 1):
        bx = cx + lado * math.sin(math.radians(38)) * Rb * 0.98
        by = cy - math.cos(math.radians(38)) * Rb * 0.98
        rb = w * 0.20
        disco(bx, by, rb, cromo_esc)
        disco(bx - rb * 0.10, by - rb * 0.10, rb * 0.86, cromo)
        disco(bx - rb * 0.24, by - rb * 0.26, rb * 0.42, cromo_cla)
    # martelo entre as campainhas
    d.line([(cx, cy - Rb * 0.98), (cx, cy - Rb * 1.32)], fill=cromo_esc + (255,), width=int(w * 0.018))
    disco(cx, cy - Rb * 1.34, w * 0.026, cromo)
    # pes
    for lado in (-1, 1):
        a = math.radians(32)
        fx, fy = cx + lado * math.sin(a) * Rb, cy + math.cos(a) * Rb
        d.line([(fx, fy - w * 0.02), (fx + lado * w * 0.05, fy + w * 0.085)],
               fill=cromo_esc + (255,), width=int(w * 0.04))
    # corpo grafite e aro cromado
    disco(cx, cy, Rb, (52, 52, 56))
    disco(cx - Rb * 0.04, cy - Rb * 0.04, Rb * 0.93, (66, 66, 70))
    disco(cx, cy, r * 1.085, cromo_esc)
    disco(cx - r * 0.01, cy - r * 0.01, r * 1.05, cromo)
    disco(cx, cy, r, (236, 232, 222))

    # tracinhos: SEMPRE alem de 0,80r — dentro disso o clean_dial() apaga o que e escuro
    for i in range(60):
        a = math.radians(i * 6)
        hora = i % 5 == 0
        r0, r1 = (r * 0.82, r * 0.95) if hora else (r * 0.88, r * 0.94)
        larg = int(w * (0.011 if hora else 0.0045))
        d.line([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)),
                (cx + r1 * math.sin(a), cy - r1 * math.cos(a))], fill=INK + (255,), width=max(1, larg))

    arr = np.asarray(im, np.float32)
    H, W = arr.shape[:2]
    rgb = arr[..., :3] * (1 + 0.03 * ruido(H, W, seed, ((40, 0.6), (6, 0.4))))[..., None]
    return para_rgba(rgb, arr[..., 3] / 255.0)


ASSETS = {
    "BG_PAPER": desenha_BG_PAPER,
    "A02_CLOCK": desenha_A02_CLOCK,
    "A03_TAPE": desenha_A03_TAPE,
    "A04_CLIPS": desenha_A04_CLIPS,
    "A10_SCRAPS": desenha_A10_SCRAPS,
}


def main():
    ap = argparse.ArgumentParser(description="Desenha os assets da identidade em codigo")
    ap.add_argument("destino", help="pasta de saida, normalmente biblioteca/assets")
    ap.add_argument("--so", nargs="*", help="so estes nomes")
    a = ap.parse_args()
    out = Path(a.destino)
    out.mkdir(parents=True, exist_ok=True)
    for nome, fn in ASSETS.items():
        if a.so and nome not in a.so:
            continue
        im = fn()
        im.save(out / f"{nome}.png")
        print(f"  {nome}.png  {im.width}x{im.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
