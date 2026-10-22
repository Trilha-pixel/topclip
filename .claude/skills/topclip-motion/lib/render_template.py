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
   identico ao da fonte (conferido sozinho no fim de cada montagem).

    ./topclip py render.py                # legenda conferida, cenas, legenda, MASTER final
    ./topclip py render.py --rascunho     # idem, montagem rapida para revisao (RASCUNHO.mp4)
    ./topclip py render.py M2 --rascunho  # so a cena M2, e remonta o rascunho
    ./topclip py render.py CAP            # so a passada de legenda, e remonta
    ./topclip py render.py --frames       # so os frames
    ./topclip py render.py --mux          # so a montagem
    ./topclip py render.py --jobs 1       # sem paralelo (para depurar uma cena)

Revise sempre com --rascunho (veryfast, varias vezes mais rapido que o slow) e monte o
master final UMA vez, quando a revisao aprovar.
"""
import os, subprocess, sys, shutil, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

import compose as C
import kit as K
import motor as V
import captions as CAP
import estilo as E
import pecas as P
from pecas import legenda as PL

ROOT = Path(__file__).resolve().parent

# ======================================================================= CLIPE
# Tudo daqui para baixo ate a proxima barra e DO CLIPE. O resto do arquivo e motor.
# Fica TUDO no nivel do modulo: o render paralelo reimporta este arquivo em cada
# processo, e o que estiver dentro do `if __name__ == "__main__"` nao chega neles.

SRC = ROOT / "00_brief" / "fonte.mp4"      # o clipe vertical ja cortado
DUR = 55.4554                              # duracao EXATA da fonte, em segundos:
#   ffprobe -v error -show_entries format=duration -of csv=p=0 fonte.mp4
FPS_NUM, FPS_DEN = 30000, 1001             # cadencia EXATA da fonte:
#   ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 f.mp4

# nome, funcao, inicio no clipe, fim no clipe, frames24 do plano, cutaway?
#
# Cada janela e escolhida em cima do transcript: comeca antes da palavra-ancora e
# segura depois dela. Overlay (cutaway=False) recebe `overlay_only=True`.
SHOTS = [
    ("M1", C.build_M1, 11.700, 14.900, 77, True),   # exemplo: troque pelas cenas reais
]

# TRES tipos de saida, alternados — nunca dois iguais seguidos (transicoes.md).
#   slide  a mesa e puxada para fora e o video aparece atras
#   wipe   uma folha (A05_SHEET) atravessa a lente; atras dela o video ja esta la
#   push   a camera acelera para dentro e o corte acontece na velocidade
EXIT_KIND = {"M1": "slide"}

# Legenda. Ver `exemplo/clipe06_config.py` para um caso preenchido de verdade.
CAP.configurar(
    words_json=ROOT / "00_brief" / "transcript_palavras.json",
    # janelas COLADAS nas cenas (sem recuo): o recuo de 0,15s apagava a palavra que
    # cai no vao — o "Nao" de "Nao e dificil fazer" no clip-005
    janelas=CAP.janelas_livres(SHOTS, DUR),
    destaque={},       # {("palavra", t): {"cor": None}} — cor em 2-3 do clipe inteiro
    cortes=[],         # todo corte seco do proprio clipe
    video=SRC,         # posiciona a legenda abaixo do queixo mais baixo das janelas
)

# ======================================================================= /CLIPE

OUT = ROOT / "12_master"
SEQ = ROOT / "10_sequences"
FPS = FPS_NUM / FPS_DEN

FX_DESK = dict(grain=0.050, vignette=0.06, chroma=1.0, sat=0.92)

# Intensidade do boil. 1.0 e a calibracao medida (tinta 6px, objeto 3px); 0.5 e o
# que ficou depois da revisao — o objeto fotografado a 3px ja perdia circunferencia.
V.BOIL_SCALE = 0.5

# O estilo do projeto (estilo/resolvido.json, gravado pelo `motion novo`) decide o
# acabamento e o boil. O Papel resolve para estes mesmos valores; sem estilo, ficam eles.
FX_DESK, V.BOIL_SCALE = E.acabamento(ROOT, FX_DESK, V.BOIL_SCALE)

# A legenda do estilo. None = a do Papel (captions.draw, com o boil "print"). Os outros
# estilos reaproveitam os blocos e o tempo do captions e so trocam o desenho.
ESTILO = P.carregar(ROOT, opcional=True)
LEG = PL.para(ESTILO)
if LEG:
    LEG.configura(CAP)

# Compressao dos PNG intermediarios. O nivel padrao (6) leva ~200ms por quadro
# 1080x1920; o 3 leva ~85ms com o mesmo tamanho. PNG e sem perda: a imagem e a mesma.
PNG_NIVEL = 3

# Processos de render. Um quadro custa ~0,6s de composicao num nucleo so; as cenas sao
# independentes quadro a quadro (boil e grao sao semeados pelo numero do quadro).
JOBS = max(1, min(6, (os.cpu_count() or 2) - 2))

# SAIDA DESLIZANTE dos cutaways.
#
# Cortar seco de uma composicao cheia direto para o rosto le como tranco. A correcao
# nao e so segurar mais tempo: e dar um GESTO de saida. Por isso os cutaways sao
# renderizados em RGBA: a area que a mesa liberou fica transparente e o `overlay` do
# ffmpeg deixa o video original passar por baixo.
#
# NAO ha flash branco nem whip pan: o guia de estilo lista os dois entre o que mata o
# estilo, junto com glitch. O "wipe" entrega o mesmo clarao, mas MATERIAL; o "push" e o
# "zoom na prova".
EXIT_SLIDE = 13          # frames de saida (a 29.97fps ~0,43s)
EXIT_DIR = (-1.06, 0.0)  # para a esquerda, um pouco alem da largura para limpar o quadro
PUSH_TO = 1.34           # escala no ultimo frame do push
SAIDAS = ("slide", "wipe", "push")


_sheet = {}


def wipe_sheet(size):
    """A folha que atravessa a lente: A05_SHEET (desenho.py), algodao frio — material
    diferente do fundo marfim, senao a passagem nao le. Se faltar no projeto, o kit
    desenha na hora."""
    if size not in _sheet:
        _sheet[size] = K._png("A05_SHEET").resize(size, Image.LANCZOS)
    return _sheet[size]


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


def confere_saidas():
    """Antes de renderizar: tipo de saida valido, e nunca o mesmo em duas cenas
    seguidas (repetir a saida vira tique). Erro aqui custa segundos; no meio do
    render, minutos."""
    cuts = [s for s in SHOTS if s[5]]
    for name, *_ in cuts:
        k = EXIT_KIND.get(name, "slide")
        if k not in SAIDAS:
            raise SystemExit(f"EXIT_KIND[{name!r}] = {k!r}: use slide, wipe ou push")
    seq = [EXIT_KIND.get(s[0], "slide") for s in cuts]
    for k in range(len(cuts) - 1):
        if seq[k] == seq[k + 1]:
            print(f"  aviso: {cuts[k][0]} e {cuts[k + 1][0]} saem as duas por "
                  f"{seq[k]!r} — alterne", file=sys.stderr)
    if "wipe" in seq:
        wipe_sheet((int(1080 * 0.62), 1920))     # falha ja, nao no quadro 300


_FN = {s[0]: s for s in SHOTS}


def _silencio():
    V.SILENCIO = True


def _frame(job):
    """Um quadro de uma cena. Roda em qualquer processo: tudo vem do numero do quadro."""
    name, i, n = job
    _, fn, t0, t1, total24, cutaway = _FN[name]
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
    img.convert("RGBA").save(SEQ / name / f"{i:04d}.png", compress_level=PNG_NIVEL)
    return name


def render_cenas(nomes=None, jobs=None, avanco=None):
    """Renderiza as cenas pedidas (todas, sem `nomes`), quadro a quadro em paralelo.
    `avanco(feito, total)`, se vier, e chamado a cada quadro pronto."""
    jobs = jobs or JOBS
    tarefas = []
    for name, fn, t0, t1, total24, cutaway in SHOTS:
        if nomes and name not in nomes:
            continue
        d = SEQ / name
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        n = int(round((t1 - t0) * FPS))
        tarefas += [(name, i, n) for i in range(n)]
    if not tarefas:
        return 0
    t = time.time()
    print(f"  {len(tarefas)} quadros em {jobs} processo(s)...", flush=True)
    if jobs <= 1:
        for k, job in enumerate(tarefas):
            _frame(job)
            if avanco:
                avanco(k + 1, len(tarefas))
            if k % 30 == 0:
                print(f"  {k:4d}/{len(tarefas)}", flush=True)
    else:
        with ProcessPoolExecutor(jobs, initializer=_silencio) as ex:
            for k, _ in enumerate(ex.map(_frame, tarefas, chunksize=4)):
                if avanco:
                    avanco(k + 1, len(tarefas))
                if k % 60 == 0:
                    print(f"  {k:4d}/{len(tarefas)}", flush=True)
    print(f"  cenas: {len(tarefas)} quadros em {time.time() - t:.0f}s")
    return len(tarefas)


def _liga(src, dst):
    """Quadro repetido vira hard link, nao PNG novo: a legenda e vazia na maior parte
    do clipe e cada bloco e identico por varios quadros."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def render_captions(avanco=None):
    """
    Legenda TOPCLIP PAPEL v2, no padrao medido frame a frame na referencia: blocos curtos,
    CENTRADOS, em CORTE SECO, correndo nas janelas livres de motion, abaixo do queixo.
    """
    # O boil da tipografia e o preset "print", aplicado DENTRO de CAP.draw. O estado
    # global e zerado aqui de proposito: sem isso o texto herdaria o campo congelado do
    # ultimo frame da ultima cena, deformado e parado.
    V.boil_ctx(None)

    t = time.time()
    d = SEQ / "CAP"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    ph = CAP.blocos()          # ja conferidos por CAP.check(SHOTS) no inicio do render
    total = int(round(DUR * FPS))
    vazio = d / "_vazio.png"
    Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(vazio)
    janelas = [(int(round(x["t"] * FPS)), int(round(x["e"] * FPS)), k)
               for k, x in enumerate(ph)]

    # cada bloco e IDENTICO em todos os seus frames a menos do boil, que anda a 9fps:
    # renderiza uma vez por passo de boil e liga os quadros repetidos ao primeiro. Na
    # legenda de outro estilo, a menos da entrada: so os primeiros quadros mudam.
    feito = {}
    entrada = LEG.quadros_entrada(FPS) if LEG else 0
    for i in range(total):
        if avanco:
            avanco(i + 1, total)
        hit = next(((k, a) for a, b, k in janelas if a <= i < b), None)
        alvo = d / f"{i:04d}.png"
        if hit is None:
            _liga(vazio, alvo)
            continue
        cur, ini = hit
        if LEG is None:
            key = (cur, int(i * 24.0 / FPS * 9 / 24))
        else:
            key = (cur, min(i - ini, entrada))
        if key in feito:
            _liga(feito[key], alvo)
        elif LEG is None:
            CAP.draw(ph[cur], frame=i * 24.0 / FPS).save(alvo, compress_level=PNG_NIVEL)
            feito[key] = alvo
        else:
            LEG.draw(ph[cur], key[1], FPS, CAP.posicao()).save(alvo, compress_level=PNG_NIVEL)
            feito[key] = alvo
    cobertos = sum(b - a for a, b, _ in janelas)
    print(f"  CAP: {total} frames, {len(ph)} blocos, {cobertos} frames com legenda "
          f"({100*cobertos/total:.0f}% do clipe) em {time.time() - t:.0f}s")
    return total


def mux_cmd(rascunho=False):
    """O comando do ffmpeg e o arquivo de saida. `rascunho`: x264 veryfast/CRF 23 em
    RASCUNHO.mp4, para revisao — o slow levava ~2 min por montagem e a run remontou 3
    vezes por clipe. O master final (slow/CRF 20, MASTER_v01.mp4) sai uma vez, quando a
    revisao aprovar."""
    dst = OUT / ("RASCUNHO.mp4" if rascunho else "MASTER_v01.mp4")
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
    # CRF 20: a 18 o master dava 173MB. O grao de filme e caro de codificar e a
    # plataforma reencoda tudo de novo — 18 so gasta banda sem ganhar imagem.
    enc = (["-preset", "veryfast", "-crf", "23"] if rascunho
           else ["-preset", "slow", "-crf", "20"])
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(SRC)] + ins +
           ["-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "0:a",
            "-c:v", "libx264"] + enc +
           ["-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)])
    return cmd, dst


def _ffmpeg(cmd, avanco=None):
    """Roda o ffmpeg. Com `avanco(segundos, total)`, le o `-progress` dele: quantos
    segundos do clipe ja foram codificados."""
    if not avanco:
        return subprocess.run(cmd, check=True)
    proc = subprocess.Popen(cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:],
                            stdout=subprocess.PIPE, text=True)
    for linha in proc.stdout:
        chave, _, valor = linha.strip().partition("=")
        if chave == "out_time_us" and valor.isdigit():
            avanco(int(valor) / 1e6, DUR)
    if proc.wait():
        raise subprocess.CalledProcessError(proc.returncode, cmd)


def mux(rascunho=False, avanco=None):
    OUT.mkdir(exist_ok=True)
    cmd, dst = mux_cmd(rascunho)
    t = time.time()
    print(f"  montando {'RASCUNHO (veryfast)' if rascunho else 'MASTER (slow)'}...",
          flush=True)
    _ffmpeg(cmd, avanco)
    print(f"  {dst.name} em {time.time() - t:.0f}s -> {dst}")
    confere(dst)
    return dst


def _probe(f, *args):
    return subprocess.run(["ffprobe", "-v", "error", *args, "-of", "csv=p=0", str(f)],
                          capture_output=True, text=True).stdout.strip()


def _md5_audio(f):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-map", "0:a", "-c",
                        "copy", "-f", "md5", "-"], capture_output=True, text=True)
    return r.stdout.strip().split("=")[-1]


def confere(dst):
    """Laudo D5 automatico: duracao, cadencia, quadros e MD5 do audio contra a fonte.
    Qualquer diferenca e erro — o master nao pode mexer no tempo nem no audio."""
    linhas = [("duracao", ("-show_entries", "format=duration")),
              ("cadencia", ("-select_streams", "v:0", "-show_entries",
                            "stream=r_frame_rate")),
              ("quadros", ("-select_streams", "v:0", "-count_packets", "-show_entries",
                           "stream=nb_read_packets"))]
    ruim = []
    for nome, args in linhas:
        a, b = _probe(SRC, *args), _probe(dst, *args)
        print(f"  {nome:9s} fonte {a:>14s}  master {b:>14s}  "
              f"{'ok' if a == b else '<<< DIFERE'}")
        if a != b:
            ruim.append(nome)
    a, b = _md5_audio(SRC), _md5_audio(dst)
    print(f"  {'audio md5':9s} fonte {a[:12]}...  master {b[:12]}...  "
          f"{'ok' if a == b else '<<< DIFERE'}")
    if a != b:
        ruim.append("audio")
    if ruim:
        raise SystemExit(f"master difere da fonte em: {', '.join(ruim)}")


class Barra:
    """A barra do painel (Atividade, em painel/atividade.py), achada subindo de pasta
    em pasta a partir do projeto. Cada fase do render ocupa uma faixa, pelo peso.
    Fora de um projeto do TopClip, nao anota nada — e nunca derruba o render."""

    def __init__(self, fases, rotulo):
        total = sum(peso for _, peso in fases) or 1
        self.faixa, acc = {}, 0
        for nome, peso in fases:
            self.faixa[nome] = (acc / total, peso / total)
            acc += peso
        self.prog = None
        for base in Path(__file__).resolve().parents:
            alvo = base / "painel" / "atividade.py"
            if alvo.exists():
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("topclip_atividade", alvo)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    self.prog = mod.Progresso(Path(__file__), rotulo, etapa="motion")
                except Exception:
                    pass
                break

    def __call__(self, fase, fracao, msg):
        if not self.prog:
            return
        ini, largura = self.faixa.get(fase, (0, 0))
        pct = 100 * (ini + largura * max(0.0, min(1.0, fracao)))
        self.prog.marcar(pct, f"{msg} ({pct:.0f}%)", final=pct >= 100)


if __name__ == "__main__":
    args = sys.argv[1:]
    jobs = None
    if "--jobs" in args:
        k = args.index("--jobs")
        jobs = int(args[k + 1])
        del args[k:k + 2]
    so = [a for a in args if not a.startswith("--")]
    cenas = [s for s in so if s != "CAP"]
    rascunho = "--rascunho" in args
    fazer_cenas = "--mux" not in args and (not so or bool(cenas))
    fazer_cap = "--mux" not in args and (not so or "CAP" in so)
    fazer_mux = "--frames" not in args
    final = "rascunho" if rascunho else "master"
    # o peso de cada fase ~ o tempo que ela leva; o slow do master e o mais caro
    fases = ([("cenas", 60)] if fazer_cenas else []) + ([("CAP", 10)] if fazer_cap else []) \
        + ([("mux", 10 if rascunho else 30)] if fazer_mux else [])
    barra = Barra(fases, f"montando o {final} do motion")
    t = time.time()
    if "--mux" not in args:
        # legenda e saidas conferidas ANTES: o erro aparece em segundos, nao depois de
        # minutos de render
        if not so or "CAP" in so:
            CAP.check(SHOTS)
        confere_saidas()
        if fazer_cenas:
            render_cenas(cenas or None, jobs, avanco=lambda k, n: barra(
                "cenas", k / n, f"desenhando os quadros das cenas: {k} de {n}"))
        if fazer_cap:
            render_captions(avanco=lambda i, n: barra(
                "CAP", i / n, f"desenhando a legenda: {i} de {n} quadros"))
    if fazer_mux:
        mux(rascunho, avanco=lambda s, d: barra(
            "mux", s / d if d else 0, f"juntando tudo no {final}: {s:.0f}s de {d:.0f}s"))
    print(f"  total {time.time() - t:.0f}s")
