#!/usr/bin/env python3
"""
Esqueleto de cena. Copie para o projeto como `compose.py` e escreva uma build_M# por cena.

Toda a mecanica da identidade vem de `kit`. Aqui fica so CONTEUDO: que objeto entra,
onde, em que frame, ancorado em que palavra.

PRINCIPIO: nao existe "imagem do START" e "imagem do END" desenhadas a mao. Existe UMA
timeline em frames por cena, e cada estado e essa timeline avaliada num frame. Por isso
os estados sao coerentes por construcao.

As cenas abaixo sao EXEMPLOS PRONTOS, um por receita do kit (referencias/receitas.md),
tirados das cenas aprovadas da run aula-yt-teste. Comece copiando a do registro que a
cena pede e troque o conteudo; apague as que nao usar (e tire de SCENES).

    M1  Mesa de pesquisa   relogio + fita-etiqueta MVP + circulo + seta
    R1  Dado a mao         barras em hachura crescendo (LTV)          hatch_bar, tape_label
    R2  Anotacao de campo  criterios escritos e riscados              scrap pautado, strike_ink
    R3  Processo           resultado do cliente -> etiqueta R$        price_tag
    R4  Anotacao (overlay) tira no topo do video, "≈" desenhado       bilhete, nota_topo
    R5  Dado a mao         conta montada item a item                  hand_tally, conta

    ./topclip py compose.py            # os 4 estados de todas as cenas + folha de estados
    ./topclip py compose.py R2 R4      # so estas
    ./topclip py compose.py --check    # END depois do ultimo evento, em todas
"""
import sys, math, subprocess, io, contextlib
from concurrent.futures import ProcessPoolExecutor
from kit import *          # noqa: F401,F403  — mecanica da identidade e receitas
import kit as K
import motor as V

V.BOIL_SCALE = 0.5         # a mesma calibracao do render.py: estado = o que vai ao ar


# =====================================================================  M1  Mesa de pesquisa
# Substitua por cenas reais. Cada evento ancorado numa palavra do transcript:
#   frame24 = (t_palavra - t_inicio_do_plano) * 24
M1_STATES = {"START": 0, "MID": 36, "END": 58, "EXIT": 70}
M1_EVENTS = dict(hero=(0, 10), tape=(8, 15), label=(15, 29), headline=(32, 43),
                 circle=(40, 51), arrow=(51, 58), line=(4, 52), camera=(30, 64))


def build_M1(frame):
    boil_ctx(frame)
    c = bg_paper()
    E = M1_EVENTS

    # props periféricos cortados pelas bordas — dao mundo sem somar elemento relevante
    place(c, piece("A10_SCRAPS", 1, 168, rotation=-9), (-58, 1560), shadow=SH_PAPER,
          kind="paper")
    place(c, piece("A04_CLIPS", 0, 124, rotation=24), (-34, 524), shadow=SH_PAPER)

    # linha de continuidade: MESMA altura e MESMO desenho em todas as cenas
    c.alpha_composite(blue_line(c.size, [(-60, 392), (250, 420), (560, 382),
                                         (870, 412), (1140, 396)],
                                progress=d(frame, *E["line"]), width=7))

    # HERO pousando de cima, com overshoot e sombra crescendo junto
    hp = p(frame, *E["hero"])
    clock, dial, dr = clock_at(9.0 * hp, 600, rotation=-3 + 1.5 * hp)
    pos = centered(clock, 540, 852 + voo(hp, 740, 18))
    place(c, clock, pos, shadow=dict(dy=int(5 + 15 * hp), blur=int(12 + 20 * hp),
                                     opacity=0.05 + 0.15 * hp))
    dcx, dcy = pos[0] + dial[0], pos[1] + dial[1]

    # manchete em BLOCO — nunca caractere a caractere
    c.alpha_composite(text_layer(c.size, "UMA MADRUGADA", F_COND, 80, (540, 214),
                                 color=INK, anchor="mt", tracking=3, mode="block",
                                 progress=p(frame, *E["headline"])))

    # etiqueta: a fita e dimensionada PELA PALAVRA e o texto vai no centro optico dela
    tape_label(c, "MVP", 118, 540, 1452, tape=p(frame, *E["tape"]),
               write=d(frame, *E["label"]), rotation=-2.2, seed=21, tracking=4)

    # anotacao: circulo marca o ponto, seta liga causa e efeito — e TOCA o alvo
    c.alpha_composite(hand_circle(c.size, dcx, dcy - dr * 0.99, 72, 56,
                                  progress=d(frame, *E["circle"]),
                                  passes=2, width=7, color=INK, seed=31, amp=7))
    c.alpha_composite(hand_arrow(c.size, [(566, dcy + dr + 56), (556, 1290),
                                          (542, 1452 - 118 * 0.62)],
                                 progress=d(frame, *E["arrow"]),
                                 width=8, color=INK, seed=41, head=42))

    return apply_camera(c, 1.0 + 0.030 * p(frame, *E["camera"]), focus=(548, 1120))


# =====================================================================  R1  Dado a mao
# clip-010 M1. LTV@4,70 f4 · que@5,62 f26 · manter@6,24 f41 · uma@7,10 f61 ·
# venda@7,84 f79 · extensa@8,22 f88
R1_STATES = {"START": 0, "MID": 64, "END": 100, "EXIT": 108}
R1_EVENTS = dict(card=(0, 10), tape=(1, 9), label=(4, 17), defn=(24, 40),
                 base=(30, 40), bar1=(40, 50), bar2=(59, 69), bar3=(77, 87),
                 bar4=(86, 96), arrow=(88, 100), camera=(0, 119))
R1_BARS = [(270, 130), (430, 260), (590, 390), (750, 520)]   # (centro x, altura)
R1_BASE, R1_BW = 1290, 104


def build_R1(frame):
    boil_ctx(frame)
    c = bg_paper()
    E = R1_EVENTS

    place(c, piece("A10_SCRAPS", 1, 300, rotation=14), (840, 1590), shadow=SH_PAPER,
          kind="paper")

    # papel quadriculado no tamanho de uso, ja em voo no frame 0 (o corte e a revelacao)
    cp = p(frame, *E["card"])
    grid = scrap("quadriculado", 768, 712, seed=102, rotation=-1.2).im
    rest = centered(grid, 540, 1010)
    gpos = centered(grid, 540, 1010 + voo(cp, 620, 14))
    place(c, grid, gpos, shadow=sombra_pouso(cp), kind="paper")
    place(c, piece("A04_CLIPS", 0, 118, rotation=-28), (gpos[0] + 40, gpos[1] - 42),
          shadow=SH_PAPER, kind="obj")
    oy = gpos[1] - rest[1]          # o grafico anda com o papel

    tape_label(c, "LTV", 132, 300, 352, tape=p(frame, *E["tape"]),
               write=d(frame, *E["label"]), rotation=-3, seed=21)
    c.alpha_composite(text_layer(c.size, "= cliente que\ncompra de novo", F_MARKER, 58,
                                 (470, 292), color=INK, anchor="lt", stroke_w=1,
                                 tracking=1, hand=True, seed=33, mode="write",
                                 line_gap=1.25, progress=d(frame, *E["defn"])))

    c.alpha_composite(hand_underline(c.size, 190, 840, R1_BASE + oy,
                                     progress=d(frame, *E["base"]), passes=1, width=6,
                                     color=INK, seed=7, amp=2.0))
    # barras: a mesma pessoa comprando de novo, o valor acumulando
    for i, (bx, bh) in enumerate(R1_BARS):
        bp = d(frame, *E[f"bar{i + 1}"])
        if bp <= 0:
            continue
        c.alpha_composite(hatch_bar(c.size, bx - R1_BW // 2, R1_BASE - bh + oy,
                                    bx + R1_BW // 2, R1_BASE + oy, bp, seed=100 + i * 7))
        # "1".."4", nunca "1ª": o marcador desenha o ª como um A
        c.alpha_composite(text_layer(c.size, f"{i + 1}", F_MARKER, 48,
                                     (bx, R1_BASE + 18 + oy), color=INK, anchor="mt",
                                     hand=True, seed=40 + i, mode="write",
                                     progress=min(1.0, bp * 1.6)))
    tops = [(bx, R1_BASE - bh - 48 + oy) for bx, bh in R1_BARS]
    c.alpha_composite(hand_arrow(c.size, [(tops[0][0] - 20, tops[0][1] + 10),
                                          (tops[1][0], tops[1][1] - 4),
                                          (tops[2][0], tops[2][1] - 6),
                                          (tops[3][0] + 26, tops[3][1] - 18)],
                                 progress=d(frame, *E["arrow"]), width=7, color=INK,
                                 seed=41, head=38))

    return apply_camera(c, 1.0 + 0.03 * p(frame, *E["camera"]), focus=(540, 980))


# =====================================================================  R2  Anotacao de campo
# clip-010 M3. facilidade@24,70 f29 · dificuldade@25,56 f49 · caro@27,54 f97 ·
# margem@28,90 f130 · Nada@29,20 f137 (os quatro riscados em sequencia)
R2_STATES = {"START": 0, "MID": 112, "END": 152, "EXIT": 160}
R2_EVENTS = dict(sheet=(0, 10), head=(3, 11), it1=(28, 42), it2=(48, 62),
                 it3=(96, 114), it4=(129, 139), s1=(137, 143), s2=(140, 146),
                 s3=(143, 149), s4=(146, 152), camera=(0, 171))
R2_ITEMS = ["facilidade", "dificuldade", "caro ou barato", "margem"]


def build_R2(frame):
    boil_ctx(frame)
    c = bg_paper()
    E = R2_EVENTS

    place(c, piece("A10_SCRAPS", 1, 330, rotation=-16), (-120, 1500), shadow=SH_PAPER,
          kind="paper")

    # caderno pautado no tamanho de uso: a pauta (92px) cabe a linha de marcador de 72
    sp = p(frame, *E["sheet"])
    folha = scrap("pautado", 788, 752, seed=111, rotation=-1.0)
    spos = centered(folha.im, 540, 1020 + voo(sp, -900, -14))      # sobe de baixo
    place(c, folha.im, spos, shadow=sombra_pouso(sp), kind="paper")
    place(c, piece("A04_CLIPS", 1, 112, rotation=8), (spos[0] + 600, spos[1] - 46),
          shadow=SH_PAPER, kind="obj")

    c.alpha_composite(text_layer(c.size, "NÃO PRECIFIQUE POR:", F_COND, 84, (110, 290),
                                 color=INK, anchor="lt", tracking=2, mode="block",
                                 progress=p(frame, *E["head"])))

    for i, txt in enumerate(R2_ITEMS):
        pr = d(frame, *E[f"it{i + 1}"])
        if pr <= 0:
            continue
        # escrita SOBRE a pauta: ponto do papel sem rotacao -> quadro (Papel.ponto)
        lx, ly = folha.ponto(folha.margem + 34, folha.linhas[2 * i])
        xy = (spos[0] + lx, spos[1] + ly - 10)
        kw = dict(anchor="lb", stroke_w=1, tracking=1, hand=True, seed=60 + i)
        c.alpha_composite(text_layer(c.size, txt, F_MARKER, 72, xy, color=INK,
                                     mode="write", progress=pr, **kw))
        # o risco cruza a TINTA da palavra, nao a caixa da fonte
        c.alpha_composite(strike_ink(c.size, ink_bbox(txt, F_MARKER, 72, xy, **kw),
                                     d(frame, *E[f"s{i + 1}"]), seed=80 + i))

    return apply_camera(c, 1.0 + 0.03 * p(frame, *E["camera"]), focus=(540, 900))


# =====================================================================  R3  Processo
# clip-010 M2. precificar@16,22 f17 · solucao@17,72 f53 · agrega@19,02 f84 ·
# cliente@19,86 f105
R3_STATES = {"START": 0, "MID": 60, "END": 102, "EXIT": 111}
R3_EVENTS = dict(tag=(0, 10), price=(12, 26), head=(46, 56), grid=(44, 54),
                 chart=(54, 76), peak=(74, 84), arrow=(84, 100), camera=(0, 122))


def build_R3(frame):
    boil_ctx(frame)
    c = bg_paper()
    E = R3_EVENTS

    place(c, piece("A10_SCRAPS", 3, 280, rotation=-12), (-90, 1520), shadow=SH_PAPER,
          kind="paper")

    # etiqueta de preco com barbante — ja em voo no frame 0
    tag = price_tag(c, 660, 1270, pouso=p(frame, *E["tag"]),
                    write=d(frame, *E["price"]), text="R$", width=400, rotation=-7)

    # o resultado do CLIENTE: grafico de vendas subindo
    gp = p(frame, *E["grid"])
    if gp > 0:
        g = scrap("quadriculado", 438, 372, seed=112, grade=40, rotation=2.0).im
        gpos = centered(g, 360 - (1 - gp) * 520, 690)
        place(c, fade(g, min(1.0, gp * 3)), gpos, shadow=SH_CARD, kind="paper")
        x0, y0 = gpos[0] + 70, gpos[1] + g.height - 80
        pts = [(x0, y0), (x0 + 70, y0 - 30), (x0 + 130, y0 - 20), (x0 + 200, y0 - 110),
               (x0 + 260, y0 - 95), (x0 + 330, y0 - 230)]
        c.alpha_composite(hand_stroke(c.size, pts, d(frame, *E["chart"]), width=8,
                                      seed=3, amp=1.6))
        peak = pts[-1]
        c.alpha_composite(hand_circle(c.size, peak[0], peak[1], 34, 30,
                                      progress=d(frame, *E["peak"]), passes=2, width=6,
                                      color=YELLOW, seed=31, amp=3))
        # seta longa: do resultado do cliente ate o preco — e TOCA a etiqueta
        c.alpha_composite(hand_arrow(c.size, [(peak[0] + 30, peak[1] + 30),
                                              (peak[0] + 190, peak[1] + 170),
                                              (tag["topo"][0], tag["topo"][1] + 6)],
                                     progress=d(frame, *E["arrow"]), width=8, color=INK,
                                     seed=44, head=40))

    c.alpha_composite(text_layer(c.size, "RESULTADO\nDO CLIENTE", F_COND, 104, (128, 210),
                                 color=INK, anchor="lt", tracking=2, mode="block",
                                 line_gap=1.12, progress=p(frame, *E["head"])))

    return apply_camera(c, 1.0 + 0.025 * p(frame, *E["camera"]), focus=(560, 1000))


# =====================================================================  R4  Anotacao (overlay)
# clip-005 O1, sobre o video desde o frame 0. projetos@3,30 f79 · 2.500@4,50 f108 ·
# reais,@6,14 termina f147 (saida no silencio)
R4_T0 = 0.0          # inicio da cena no clipe: o plate de cada estado sai do fonte.mp4
R4_STATES = {"START": 0, "MID": 85, "END": 132, "EXIT": 151}
R4_EVENTS = dict(hero=(-6, 9),        # ja em voo no frame 0 (corte = revelacao)
                 settle=(9, 146),     # assenta devagar: nao fica morto 3s
                 tape=(77, 85), under=(108, 130), exit=(147, 157))


def _r4_bilhete(frame):
    """O bilhete inteiro e UM objeto: monta no canvas local e gira junto."""
    E = R4_EVENTS
    g, _, _ = bilhete(830, 372, seed=104)
    kw = dict(anchor="lt", stroke_w=2, tracking=2, hand=True)
    L1 = (168, 122)
    # "2.500" em duas emendas: no marcador o ponto encosta no pe do "2" e some
    a = ink_bbox("R$ 2", F_MARKER, 98, L1, size=g.size, seed=11, **kw)
    L2 = (a[2] + 12, L1[1])
    g.alpha_composite(text_layer(g.size, "R$ 2", F_MARKER, 98, L1, color=INK, seed=11,
                                 **kw))
    g.alpha_composite(text_layer(g.size, ".500/mês", F_MARKER, 98, L2, color=INK,
                                 seed=14, **kw))
    # o "≈" sai desenhado a caneta: a fonte de marcador nao tem o glifo
    g.alpha_composite(text_layer(g.size, "≈ aluguel de um apê", F_MARKER, 62, (170, 258),
                                 color=INK, seed=12, **kw))
    g.alpha_composite(text_layer(g.size, "de R$ 400–500 mil", F_MARKER, 62, (170, 340),
                                 color=INK, seed=13, **kw))
    # sublinhado so no "2.500", quando ele diz o numero: medido na tinta
    u0 = ink_span("R$ 2", "2", F_MARKER, 98, L1, size=g.size, seed=11, **kw)[0]
    u1 = ink_span(".500/mês", ".500", F_MARKER, 98, L2, size=g.size, seed=14, **kw)[2]
    g.alpha_composite(hand_underline(g.size, u0 - 4, u1 + 6, a[3] + 16,
                                     progress=d(frame, *E["under"]), passes=2, width=8,
                                     color=INK, seed=23, amp=3.0))
    # fita-rotulo em "projetos": presa ao bilhete, abaixo do texto
    tape_label(g, "projetos de\nsite/sistema", 50, 706, 500, tape=p(frame, *E["tape"]),
               rotation=-3.0, seed=31, drop=36, tracking=2, stroke_w=2)
    return g


def build_R4(frame, overlay_only=True):
    boil_ctx(frame)
    E = R4_EVENTS
    saida = ease_in(lin(frame, *E["exit"]))
    return nota_topo(_r4_bilhete(frame), pouso=p(frame, *E["hero"]),
                     assenta=p(frame, *E["settle"]), saida=saida, frame=frame)


# =====================================================================  R5  Dado a mao (conta)
# clip-005 M2. 10@14,80 f14 · projetos@15,66 f35 · 300@16,92 f65 · 3@17,66 f83 ·
# mes.@18,52 f104
R5_STATES = {"START": 0, "MID": 76, "END": 108, "EXIT": 121}
R5_EVENTS = dict(hero=(-5, 8), tape=(3, 9), tally=(14, 36), times=(62, 74),
                 equals=(80, 98), under1=(101, 104), under2=(104, 107), camera=(0, 121))
R5_X = 168                # coluna da conta: alinhada a esquerda, como conta de papel


def build_R5(frame):
    boil_ctx(frame)
    c = bg_paper()
    E = R5_EVENTS

    place(c, piece("A10_SCRAPS", 1, 300, rotation=11), (-120, 1500), shadow=SH_PAPER,
          kind="paper")
    place(c, piece("A04_CLIPS", 0, 150, rotation=-24), (972, 258), shadow=SH_PAPER)

    # heroi: quadriculado no tamanho de uso (o A10 ampliado 3x borrava)
    hp = p(frame, *E["hero"])
    folha = scrap("quadriculado", 818, 660, seed=113, rotation=-1.5 + (1 - hp) * 5)
    pos = centered(folha.im, 512 + (1 - hp) * 260, 930 + (1 - hp) * 520)
    place(c, folha.im, pos, shadow=dict(dy=int(4 + 7 * hp), blur=int(14 + 10 * hp),
                                        opacity=0.10 + 0.07 * hp), kind="paper")
    tp = p(frame, *E["tape"])
    if tp > 0:
        tape = piece("A03_TAPE", 2, 230, rotation=38)
        place(c, fade(tape, tp), centered(tape, pos[0] + 70, pos[1] + 70 - (1 - tp) * 30),
              shadow=SH_TAPE, kind="paper")

    # 1) dez tracinhos ("10 projetos"), um depois do outro
    c.alpha_composite(hand_tally(c.size, R5_X, 668, 10, lin(frame, *E["tally"])))
    # 2) e 3) a conta, linha a linha, cada uma na sua palavra
    caixas = conta(c, [("× R$ 300", 96), ("= R$ 3.000/mês", 86)], R5_X, 850,
                   [d(frame, *E["times"]), d(frame, *E["equals"])], passo=160)
    # 4) sublinhado duplo so no "mes": x medido no desenho, nao na fonte
    x0, _, x1, _ = ink_span("= R$ 3.000/mês", "mês", F_MARKER, 86, (R5_X, 1010),
                            anchor="lt", stroke_w=3, tracking=2, hand=True, seed=71)
    c.alpha_composite(sublinhado_duplo(c.size, x0, x1, caixas[1][3] + 14,
                                       d(frame, *E["under1"]), d(frame, *E["under2"])))

    return apply_camera(c, 1.0 + 0.030 * p(frame, *E["camera"]), focus=(520, 940))


# =====================================================================
# nome: (funcao, estados, acabamento). Acabamento None = OVERLAY: o estado e julgado
# SOBRE o video, no tempo certo (precisa de <NOME>_T0 para achar o plate).
SCENES = {"M1": (build_M1, M1_STATES, FX_DESK),
          "R1": (build_R1, R1_STATES, FX_DESK),
          "R2": (build_R2, R2_STATES, FX_DESK),
          "R3": (build_R3, R3_STATES, FX_DESK),
          "R4": (build_R4, R4_STATES, None),
          "R5": (build_R5, R5_STATES, FX_DESK)}

# eventos continuos (camera, deriva, saida) nao contam como "ultimo evento"
CONTINUOS = ("camera", "hands", "drift", "exit", "line", "boot", "sweep", "settle")


def _plate(scene, st, fr):
    """O quadro do video sob um overlay, no tempo do estado (t = T0 + frame/24). Sai
    do 00_brief/fonte.mp4 uma vez, para 09_plates/. Sem video: plate sintetico."""
    f = K.PLATES / f"{scene}_{st}.png"
    if f.exists():
        return Image.open(f).convert("RGBA")
    src = K.ROOT / "00_brief" / "fonte.mp4"
    t0 = globals().get(f"{scene}_T0")
    if src.exists() and t0 is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + fr / 24.0:.3f}",
                        "-i", str(src), "-frames:v", "1", "-vf", "scale=1080:1920",
                        str(f)], check=True)
        return Image.open(f).convert("RGBA")
    return plate_falso()


def _estado(job):
    """Um estado, em qualquer processo. Os avisos (glifo, peca ampliada) voltam para o
    processo principal, que mostra cada um UMA vez."""
    scene, st, fr, tag = job
    fn, states, fx = SCENES[scene]
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        if fx is None:
            im = _plate(scene, st, fr)
            im.alpha_composite(fn(fr, overlay_only=True))
        else:
            im = finish(fn(fr), **fx)
    out = OUTF / f"{scene}{tag}_{st}.png"
    im.convert("RGB").save(out)
    return f"  {out.name}  (frame {fr})", err.getvalue().splitlines()


def render(scenes, tag=""):
    """Os 4 estados de cada cena, em paralelo, e a folha com os 4 lado a lado
    (<cena>_ESTADOS.png) — uma imagem para revisar em vez de quatro."""
    jobs = [(s, st, fr, tag) for s in scenes for st, fr in SCENES[s][1].items()]
    n = max(1, min(len(jobs), 6))
    avisos = {}
    with ProcessPoolExecutor(n) as ex:
        for linha, av in ex.map(_estado, jobs):
            print(linha, flush=True)
            avisos.update(dict.fromkeys(av))
    for a in avisos:
        print(a, file=sys.stderr)
    for s in scenes:
        sts = SCENES[s][1]
        folha_de_estados([OUTF / f"{s}{tag}_{st}.png" for st in sts],
                         OUTF / f"{s}{tag}_ESTADOS.png",
                         rotulos=[f"{s} {st} {fr}" for st, fr in sts.items()])
        print(f"  {s}{tag}_ESTADOS.png")


def check():
    """END tem que cair DEPOIS do ultimo evento, senao o estado mostra texto pela metade."""
    ok = True
    for sc, (fn, st, fx) in SCENES.items():
        ev = globals()[sc + "_EVENTS"]
        last = max(b for k, (a, b) in ev.items() if k not in CONTINUOS)
        bom = st["END"] >= last
        ok &= bom
        print(f"  {sc}: ultimo evento {last:3d}  END {st['END']:3d}  "
              f"{'OK' if bom else 'END ANTES DO FIM <<<'}")
    return ok


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    pedidas = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SCENES)
    render(pedidas)
