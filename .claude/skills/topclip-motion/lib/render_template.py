#!/usr/bin/env python3
"""
TEMPLATE de render. Copie para o projeto como `render.py` e preencha o bloco CLIPE.

Duas decisoes que evitam problema, e que nao devem ser mexidas:

1. A timeline e escrita em frames de 24fps, mas o clipe roda na cadencia do fonte. Em
   vez de converter depois (o que gera judder), cada frame de saida e avaliado no seu
   tempo real: `frame24 = (t - inicio_do_plano) * 24`, com fracao. As curvas aceitam
   float.

2. A montagem e por SOBREPOSICAO, nao por corte-e-concatenacao. Cutaway opaco cobre o
   quadro inteiro; overlay tem alfa. Assim nao ha nenhum corte no container: duracao,
   timestamps e audio do original ficam intocados — e o MD5 do audio tem que sair
   identico ao da fonte.

    python3 render.py            # renderiza tudo e monta
    python3 render.py --frames   # so os frames
    python3 render.py CAP        # so a passada de legenda, e remonta
"""
import subprocess, sys, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

import compose as C
import motor as V
import captions as CAP

ROOT = Path(__file__).resolve().parent

# ======================================================================= CLIPE
# Tudo daqui para baixo ate a proxima barra e DO CLIPE. O resto do arquivo e motor.

SRC = ROOT / "00_brief" / "fonte.mp4"      # o clipe vertical ja cortado
DUR = 55.4554                              # duracao EXATA da fonte, em segundos:
#   ffprobe -v error -show_entries format=duration -of csv=p=0 fonte.mp4
FPS_NUM, FPS_DEN = 30000, 1001             # cadencia EXATA da fonte:
#   ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 f.mp4

# Legenda. Ver `exemplo/clipe06_config.py` para um caso preenchido de verdade.
CAP.configurar(
    words_json=ROOT / "00_brief" / "transcript_palavras.json",
    janelas=[],        # [(t0, t1)] livres de motion, >= 2s, recuadas 0,15s das bordas
    destaque={},       # {("palavra", t): {"cor": None}} — cor em 2-3 do clipe inteiro
    cortes=[],         # todo corte seco do proprio clipe
)

# ======================================================================= /CLIPE

OUT = ROOT / "12_master"
SEQ = ROOT / "10_sequences"
FPS = FPS_NUM / FPS_DEN

FX_DESK = dict(grain=0.050, vignette=0.06, chroma=1.0, sat=0.92)

# Intensidade do boil. 1.0 e a calibracao medida (tinta 6px, objeto 3px); 0.5 e o
# que ficou depois da revisao — o objeto fotografado a 3px ja perdia circunferencia.
V.BOIL_SCALE = 0.5

# SAIDA DESLIZANTE dos cutaways.
#
# Cortar seco de uma composicao cheia direto para o rosto le como tranco — foi a
# primeira coisa que o Paulo apontou no master. A correcao nao e so segurar mais tempo:
# e dar um GESTO de saida. A mesa inteira e puxada para fora do quadro e o video aparece
# atras dela. E o "papel wipe" que o proprio pack indica (09_TRANSITION_MAP §2), com a
# vantagem de usar um objeto que ja existe no mundo da cena: a propria mesa.
#
# Por isso os cutaways agora sao renderizados em RGBA: a area que a mesa liberou fica
# transparente e o `overlay` do ffmpeg deixa o video original passar por baixo.
EXIT_SLIDE = 13          # frames de saida (a 29.97fps ~0,43s)
EXIT_DIR = (-1.06, 0.0)  # para a esquerda, um pouco alem da largura para limpar o quadro

# TRES tipos de saida, alternados. Repetir a mesma saida em sete cenas vira tique.
#
#   slide  a mesa e puxada para fora e o video aparece atras
#   wipe   uma folha atravessa a lente; atras dela o video ja esta la
#   push   a camera acelera para dentro e o corte acontece na velocidade
#
# NAO ha flash branco nem whip pan: o guia de estilo lista os dois entre o que mata o
# estilo, junto com glitch. O "wipe" entrega o mesmo clarao, mas MATERIAL — e o "papel
# que cruza a lente" que o proprio pack indica (09_TRANSITION_MAP §2). O "push" e o
# "zoom na prova" do mesmo documento.
EXIT_KIND = {"M0": "slide", "M1": "wipe", "M2": "push",
             "M4": "slide", "M5": "wipe", "M6": "push"}
PUSH_TO = 1.34           # escala no ultimo frame do push

# nome, funcao, inicio no clipe, fim no clipe, frames24 do plano, cutaway?
#
# Seis motions, 20,45s de 55,45s = 37% do clipe (antes eram tres, 18%). Cada janela e
# escolhida em cima do transcript: comeca antes da palavra-ancora e segura depois dela.
SHOTS = [
    ("M0", C.build_M0,  7.100,  9.900,  67, True),   # teclado + VIBE CODING
    ("M1", C.build_M1, 11.700, 14.900,  77, True),   # relogio 00:00 + MVP
    ("M2", C.build_M2, 17.900, 21.600,  89, True),   # CRT com terminal + varredura
    ("M3", C.build_M3, 28.350, 30.600,  54, False),  # foto noturna, overlay
    ("M4", C.build_M4, 31.800, 34.900,  74, True),   # pizza a mao, 50%
    ("M5", C.build_M5, 43.800, 49.200, 130, True),   # ideia -> produto
    ("M6", C.build_M6, 50.100, 53.500,  82, True),   # poucas notas -> maco
]

# Sete motions, seis REGISTROS visuais diferentes. Tres cenas seguidas de "mesa + objeto
# + fita" liam como a mesma cena; agora ha mesa-de-pesquisa, documentario retro, foto
# montada em cartao, dado desenhado a mao, processo, e anotacao de campo.


_sheet = {}


def wipe_sheet(size):
    """A folha que atravessa a lente. Papel de algodao frio — material diferente do
    fundo marfim, senao a passagem nao le."""
    if "im" not in _sheet:
        im = Image.open(ROOT / "07_assets" / "cutout" / "A05_CARD.png").convert("RGBA")
        _sheet["im"] = im.resize(size, Image.LANCZOS)
    return _sheet["im"]


def exit_frame(img, kind, sl):
    """Um frame da saida. `sl` vai de 0 a 1 ao longo dos EXIT_SLIDE frames."""
    w, h = img.size
    if kind == "push":
        # camera acelera para dentro; o quadro segue opaco e o corte cai na velocidade
        return C.apply_camera(img, 1.0 + (PUSH_TO - 1.0) * sl, focus=(540, 900))

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if kind == "wipe":
        # a folha varre da esquerda para a direita; atras dela nao ha mais cena
        sw = int(w * 0.62)
        x = int(-sw + (w + sw) * sl)
        keep = img.convert("RGBA").copy()
        m = Image.new("L", (w, h), 255)
        ImageDraw.Draw(m).rectangle([0, 0, x + sw, h], fill=0)
        keep.putalpha(ImageChops.multiply(keep.getchannel("A"), m))
        canvas.alpha_composite(keep)
        canvas.alpha_composite(wipe_sheet((sw, h)), (x, 0))
        return canvas

    canvas.alpha_composite(img.convert("RGBA"),
                           (int(EXIT_DIR[0] * w * sl), int(EXIT_DIR[1] * h * sl)))
    return canvas


def render(name, fn, t0, t1, total24, cutaway):
    d = SEQ / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    n = int(round((t1 - t0) * FPS))
    for i in range(n):
        t = i / FPS                                    # tempo local, em segundos
        f24 = min(total24, t * 24.0)                   # frame na timeline de 24fps
        if cutaway:
            # grao "on twos": cada campo de grao segura 2 frames. E o mesmo recurso que
            # a identidade ja pede para os props (12fps dentro de 24), cintila como
            # filme, e reduz pela metade o numero de campos novos que o codec precisa
            # engolir.
            img = V.finish(fn(f24), seed=1000 + i // 2, **FX_DESK)
            k = n - EXIT_SLIDE
            if i >= k:
                sl = V.ease_in((i - k + 1) / EXIT_SLIDE)
                img = exit_frame(img, EXIT_KIND.get(name, "slide"), sl)
        else:
            img = fn(f24, overlay_only=True)           # plate intocado
        img.convert("RGBA").save(d / f"{i:04d}.png")
        if i % 30 == 0:
            print(f"  {name} {i:4d}/{n}", flush=True)
    print(f"  {name}: {n} frames -> {d}")
    return n


def render_captions():
    """
    Legenda TOPCLIP PAPEL v2, no padrao medido frame a frame na referencia: blocos curtos,
    CENTRADOS, em CORTE SECO, correndo nas janelas livres de motion.

    Nao ha mais extracao de plate: a v1 lia o fundo para inverter a cor e para escurecer
    uma tarja. Nenhuma das duas coisas existe no padrao medido — a referencia usa branco
    com sombra projetada, sempre, e resolve a legibilidade pela ALTURA (peito, sobre a
    roupa escura) em vez de por tratamento do fundo.
    """
    # O boil da tipografia e o preset "print", aplicado DENTRO de CAP.draw. O estado
    # global e zerado aqui de proposito: sem isso o texto herdaria o campo congelado do
    # ultimo frame da ultima cena, deformado e parado.
    V.boil_ctx(None)

    d = SEQ / "CAP"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    ph = CAP.check(SHOTS)
    total = int(round(DUR * FPS))
    blank = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    janelas = [(int(round(x["t"] * FPS)), int(round(x["e"] * FPS)), k)
               for k, x in enumerate(ph)]

    # cada bloco e IDENTICO em todos os seus frames a menos do boil, que anda a 9fps:
    # renderiza uma vez por passo de boil e reaproveita. Sem isso seriam 46 blocos x ~13
    # frames de desenho repetido.
    cache = {}
    for i in range(total):
        cur = next((k for a, b, k in janelas if a <= i < b), None)
        if cur is None:
            blank.save(d / f"{i:04d}.png")
            continue
        passo = int(i * 24.0 / FPS * 9 / 24)
        key = (cur, passo)
        if key not in cache:
            cache.clear()
            cache[key] = CAP.draw(ph[cur], frame=i * 24.0 / FPS)
        cache[key].save(d / f"{i:04d}.png")
    cobertos = sum(b - a for a, b, _ in janelas)
    print(f"  CAP: {total} frames, {len(ph)} blocos, {cobertos} frames com legenda "
          f"({100*cobertos/total:.0f}% do clipe)")
    return total


def mux():
    OUT.mkdir(exist_ok=True)
    dst = OUT / "MASTER_v01.mp4"
    ins = []
    for name, *_ in SHOTS:
        ins += ["-framerate", f"{FPS_NUM}/{FPS_DEN}", "-i", str(SEQ / name / "%04d.png")]
    ins += ["-framerate", f"{FPS_NUM}/{FPS_DEN}", "-i", str(SEQ / "CAP" / "%04d.png")]
    chains, prev = [], "0:v"
    for k, (name, _, t0, t1, _, _) in enumerate(SHOTS, start=1):
        chains.append(f"[{k}:v]setpts=PTS-STARTPTS+{t0}/TB[o{k}]")
        chains.append(f"[{prev}][o{k}]overlay=0:0:eof_action=pass:"
                      f"enable='between(t,{t0},{t1})'[v{k}]")
        prev = f"v{k}"
    # legenda por ultimo: fica acima de tudo
    kc = len(SHOTS) + 1
    chains.append(f"[{prev}][{kc}:v]overlay=0:0:eof_action=pass[vout]")
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(SRC)] + ins +
           ["-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "0:a",
            # CRF 20: a 18 o master dava 173MB. O grao de filme e caro de codificar e
            # a plataforma reencoda tudo de novo — 18 so gasta banda sem ganhar imagem.
            "-c:v", "libx264", "-preset", "slow", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)])
    print("  montando...", flush=True)
    subprocess.run(cmd, check=True)
    print(f"  master -> {dst}")
    return dst


if __name__ == "__main__":
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--mux" not in sys.argv:
        for name, fn, t0, t1, tot, op in SHOTS:
            if not only or name in only:
                render(name, fn, t0, t1, tot, op)
        if not only or "CAP" in only:
            render_captions()
    if "--frames" not in sys.argv:
        mux()
