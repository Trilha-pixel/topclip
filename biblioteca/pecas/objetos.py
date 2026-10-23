"""
Os objetos desenhados, escritos UMA vez: geometria e papel de cada forma. O lapis do
estilo (`lapis.py`) decide a tinta — o mesmo relogio sai chapado no Limpo, adesivo no
Impacto e gravura de latao no Luxo.

Cada objeto e uma funcao `nome(p=1.0, **parametros) -> (formas, altura, ancoras)`:
  p        o progresso da animacao PROPRIA do objeto (ponteiro girando, barra crescendo);
           a peca `objeto` calcula a partir do quadro e trava na palavra;
  formas   lista de formas do lapis, numa caixa de largura 1;
  altura   a altura da caixa (em larguras);
  ancoras  pontos nomeados na caixa (onde vai um rotulo, a ponta de uma seta).

Objeto novo: escreva a funcao aqui, registre em OBJETOS, e ele sai nos tres lapis.
Mantenha a anatomia que o espectador reconhece em 1 segundo: e um sinal, nao um retrato.
"""
import math

from .lapis import arco, circulo, elipse, linha, poli, ret


def _suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _gira(formas, graus, cx, cy):
    """Gira as formas em torno de (cx, cy): papel e cedula ficam tortos de proposito."""
    a = math.radians(graus)
    ca, sa = math.cos(a), math.sin(a)

    def g(p):
        x, y = p[0] - cx, p[1] - cy
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)

    out = []
    for f in formas:
        f = dict(f, pts=[g(p) for p in f["pts"]])
        if f.get("circ"):
            x, y = g(f["circ"][:2])
            f["circ"] = (x, y, f["circ"][2])
        out.append(f)
    return out


def relogio(p=1.0, de=(10, 10), ate=None):
    """Despertador de duas campainhas. `de`/`ate` = (hora, minuto): com `ate`, os
    ponteiros andam de um ao outro ao longo de p (a madrugada passando)."""
    cx, cy, Rb, r = 0.5, 0.64, 0.34, 0.27
    h0, m0 = de
    t0 = h0 * 60 + m0
    t1 = (ate[0] * 60 + ate[1]) if ate else t0
    if ate and t1 < t0:
        t1 += 12 * 60
    tot = t0 + (t1 - t0) * _suave(p)
    hh, mm = (tot // 60) % 12, tot % 60

    f = []
    # alca por cima, nascendo atras das campainhas
    alca = [(cx + x, 0.30 - 0.15 * (1 - (x / 0.2) ** 2)) for x in [i / 20 * 0.4 - 0.2 for i in range(21)]]
    f.append(linha(alca, 0.028))
    # pes, atras do corpo
    for lado in (-1, 1):
        a = math.radians(32)
        fx, fy = cx + lado * math.sin(a) * Rb, cy + math.cos(a) * Rb
        f.append(linha([(fx, fy - 0.02), (fx + lado * 0.06, fy + 0.085)], 0.04))
    # campainhas e martelo
    for lado in (-1, 1):
        bx = cx + lado * math.sin(math.radians(38)) * Rb * 0.98
        by = cy - math.cos(math.radians(38)) * Rb * 0.98
        f.append(circulo(bx, by, 0.135, "detalhe"))
    f.append(linha([(cx, cy - Rb * 0.98), (cx, cy - Rb * 1.30)], 0.018))
    f.append(circulo(cx, cy - Rb * 1.32, 0.026, "detalhe"))
    # corpo, aro e mostrador
    f.append(circulo(cx, cy, Rb, "corpo", duplo=True))
    f.append(circulo(cx, cy, r * 1.09, "detalhe"))
    f.append(circulo(cx, cy, r, "face"))
    for i in range(12):
        a = math.radians(i * 30)
        r0 = r * (0.78 if i % 3 == 0 else 0.84)
        f.append(linha([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)),
                        (cx + r * 0.92 * math.sin(a), cy - r * 0.92 * math.cos(a))],
                       0.016 if i % 3 == 0 else 0.009))
    # ponteiros: a hora e dado controlado (animavel), nunca texto
    ah = math.radians((hh + mm / 60) * 30)
    am = math.radians(mm * 6)
    f.append(linha([(cx, cy), (cx + r * 0.50 * math.sin(ah), cy - r * 0.50 * math.cos(ah))], 0.032))
    f.append(linha([(cx, cy), (cx + r * 0.78 * math.sin(am), cy - r * 0.78 * math.cos(am))], 0.02))
    f.append(circulo(cx, cy, 0.032, "destaque"))
    return f, 1.08, {"topo": (cx, 0.12), "base": (cx, 1.04), "centro": (cx, cy)}


def grafico_barras(p=1.0, valores=(0.28, 0.46, 0.70, 1.0), destaque=-1, seta=True):
    """Barras que crescem uma depois da outra, da esquerda para a direita, com a seta da
    tendencia no fim. `destaque` = indice da barra que importa (a do numero dito)."""
    n = len(valores)
    base, alto = 0.74, 0.62
    gap = 0.06
    larg = (0.88 - gap * (n - 1)) / n
    destaque = destaque % n if destaque is not None else None
    f = [linha([(0.03, base), (0.97, base)], 0.012)]
    topos, centros = [], []
    for i, v in enumerate(valores):
        k = _suave((p - i * 0.12) / 0.5)
        x0 = 0.06 + i * (larg + gap)
        hgt = alto * v * k
        centros.append((x0 + larg / 2, base + 0.07))
        topos.append((x0 + larg / 2, base - alto * v))
        if hgt > 0.004:
            f.append(ret(x0, base - hgt, x0 + larg, base, raio=0.018,
                         papel="destaque" if i == destaque else "detalhe"))
    ps = _suave((p - 0.78) / 0.22)
    if seta and ps > 0:
        a, b = (topos[0][0], topos[0][1] - 0.07), (topos[-1][0], topos[-1][1] - 0.07)
        fim = (a[0] + (b[0] - a[0]) * ps, a[1] + (b[1] - a[1]) * ps)
        f.append(linha([a, fim], 0.016))
        if ps > 0.95:
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            ponta = [(fim[0] + 0.05 * math.cos(ang + s), fim[1] + 0.05 * math.sin(ang + s))
                     for s in (math.pi * 0.82, -math.pi * 0.82)]
            f.append(poli([fim, ponta[0], ponta[1]], "destaque"))
    return f, 0.84, {"rotulos": centros, "topos": topos}


def grafico_pizza(p=1.0, fatia=0.35):
    """Pizza com a fatia dita crescendo a partir do topo, no sentido do relogio."""
    cx, cy, r = 0.5, 0.5, 0.42
    f = [circulo(cx, cy, r, "detalhe", duplo=True)]
    k = fatia * _suave(p)
    if k > 0.003:
        n = max(3, int(64 * k))
        borda = [(cx + r * math.sin(2 * math.pi * k * i / n), cy - r * math.cos(2 * math.pi * k * i / n))
                 for i in range(n + 1)]
        f.append(poli([(cx, cy)] + borda, "destaque"))
    f.append(circulo(cx, cy, 0.035, "face"))
    meio = 2 * math.pi * fatia / 2
    return f, 1.0, {"fatia": (cx + r * 0.62 * math.sin(meio), cy - r * 0.62 * math.cos(meio)),
                    "centro": (cx, cy)}


def cedula(p=1.0, quantas=2):
    """Notas de dinheiro empilhadas (a de tras torta). Sem cifrao: o desenho ja diz."""
    f = []
    for i in range(quantas):
        k = _suave((p - i * 0.18) / 0.5)
        if k <= 0:
            continue
        dy = (1 - k) * -0.25
        nota = [ret(0.06, 0.22 + dy, 0.94, 0.70 + dy, 0.03, "corpo"),
                ret(0.12, 0.28 + dy, 0.88, 0.64 + dy, 0.02, "face"),
                elipse(0.5, 0.46 + dy, 0.13, 0.13, "detalhe"),
                circulo(0.5, 0.46 + dy, 0.06, "corpo"),
                circulo(0.19, 0.35 + dy, 0.025, "detalhe"),
                circulo(0.81, 0.57 + dy, 0.025, "detalhe")]
        f += _gira(nota, -9 + i * 9 if quantas > 1 else 0, 0.5, 0.46)
    return f, 0.9, {"centro": (0.5, 0.46)}


def moedas(p=1.0, pilhas=(5, 3)):
    """Pilhas de moedas; cada moeda cai na pilha em sequencia (a grana juntando)."""
    f, n = [], 0
    larg = 0.36
    for j, alt in enumerate(pilhas):
        x0 = 0.12 + j * 0.42
        cx = x0 + larg / 2
        for i in range(alt):
            k = _suave((p - n * 0.08) / 0.3)
            n += 1
            if k <= 0:
                continue
            y = 0.86 - i * 0.075 - (1 - k) * 0.35
            f.append(ret(x0, y - 0.035, x0 + larg, y + 0.035, 0.0, "corpo"))
            f.append(elipse(cx, y + 0.035, larg / 2, 0.04, "corpo"))
            f.append(elipse(cx, y - 0.035, larg / 2, 0.04, "detalhe"))
    return f, 0.96, {"topo": (0.3, 0.4)}


def celular(p=1.0):
    """Celular com a tela montando: tres cartoes e um botao no acento (o app, a compra)."""
    f = [ret(0.27, 0.03, 0.73, 0.97, 0.07, "corpo", duplo=True),
         ret(0.30, 0.07, 0.70, 0.93, 0.045, "face"),
         ret(0.44, 0.09, 0.56, 0.115, 0.012, "corpo")]
    for i in range(3):
        k = _suave((p - i * 0.15) / 0.4)
        if k > 0:
            y = 0.18 + i * 0.17
            f.append(ret(0.34, y, 0.34 + 0.32 * k, y + 0.12, 0.02, "detalhe"))
    if p > 0.6:
        f.append(ret(0.36, 0.76, 0.64, 0.84, 0.04, "destaque"))
    return f, 1.0, {"tela": (0.5, 0.5), "botao": (0.5, 0.8)}


def calendario(p=1.0, dia=(3, 2)):
    """Calendario com o dia circulado na hora em que e dito. `dia` = (coluna, linha)."""
    f = [ret(0.08, 0.16, 0.92, 0.94, 0.05, "face", duplo=False),
         ret(0.08, 0.16, 0.92, 0.34, 0.05, "corpo"),
         ret(0.08, 0.26, 0.92, 0.34, 0.0, "corpo")]
    for x in (0.30, 0.70):
        f.append(linha([(x, 0.08), (x, 0.24)], 0.03))
    for lin_ in range(4):
        for col in range(5):
            cx, cy = 0.20 + col * 0.15, 0.45 + lin_ * 0.13
            papel = "destaque" if (col, lin_) == tuple(dia) and p > 0.98 else "detalhe"
            f.append(ret(cx - 0.045, cy - 0.04, cx + 0.045, cy + 0.04, 0.012, papel))
    cx, cy = 0.20 + dia[0] * 0.15, 0.45 + dia[1] * 0.13
    if p > 0:
        f.append(arco(cx, cy, 0.085, -110, -110 + 340 * _suave(p), 0.02, "destaque"))
    return f, 1.0, {"dia": (cx, cy)}


def etiqueta_preco(p=1.0):
    """Etiqueta de preco com barbante, levemente torta (o destino de uma seta de processo)."""
    corpo = poli([(0.14, 0.5), (0.32, 0.26), (0.9, 0.26), (0.9, 0.74), (0.32, 0.74)], "corpo")
    furo = circulo(0.30, 0.5, 0.045, "face")
    faixa = ret(0.42, 0.40, 0.80, 0.60, 0.02, "face")
    barb = linha([(0.30, 0.5), (0.18, 0.40), (0.06, 0.28), (0.02, 0.12)], 0.012)
    k = _suave(p)
    return _gira([barb, corpo, furo, faixa], -12 * k, 0.3, 0.5), 0.9, {"valor": (0.61, 0.5)}


def lampada(p=1.0):
    """Lampada que acende (a ideia): vidro, rosca, filamento; os raios saem quando acende."""
    acesa = p > 0.5
    f = []
    if acesa:
        k = _suave((p - 0.5) / 0.5)
        for i in range(7):
            a = math.radians(-90 + (i - 3) * 30)
            r0, r1 = 0.36, 0.36 + 0.10 * k
            f.append(linha([(0.5 + r0 * math.cos(a), 0.42 + r0 * math.sin(a)),
                            (0.5 + r1 * math.cos(a), 0.42 + r1 * math.sin(a))], 0.02, "destaque"))
    f.append(circulo(0.5, 0.42, 0.25, "destaque" if acesa else "face", duplo=True))
    f.append(poli([(0.38, 0.6), (0.62, 0.6), (0.58, 0.72), (0.42, 0.72)], "destaque" if acesa else "face"))
    for i in range(3):
        f.append(ret(0.40, 0.72 + i * 0.055, 0.60, 0.765 + i * 0.055, 0.015, "detalhe"))
    f.append(linha([(0.44, 0.62), (0.44, 0.44), (0.5, 0.36), (0.56, 0.44), (0.56, 0.62)], 0.012))
    return f, 0.95, {"luz": (0.5, 0.42)}


def alvo(p=1.0):
    """Alvo com a flecha cravando no centro no fim da animacao (a meta batida)."""
    cx, cy = 0.46, 0.54
    f = [circulo(cx, cy, 0.40, "corpo", duplo=True), circulo(cx, cy, 0.30, "face"),
         circulo(cx, cy, 0.20, "corpo"), circulo(cx, cy, 0.10, "face"),
         circulo(cx, cy, 0.045, "destaque")]
    k = _suave(p)
    sx, sy = cx + 0.5 * (1 - k) + 0.04, cy - 0.5 * (1 - k) - 0.04
    cauda = (sx + 0.34, sy - 0.34)
    f.append(linha([(sx, sy), cauda], 0.022))
    f.append(poli([cauda, (cauda[0] + 0.03, cauda[1] - 0.09), (cauda[0] + 0.09, cauda[1] - 0.03)], "destaque"))
    return f, 1.0, {"centro": (cx, cy)}


def funil(p=1.0):
    """Funil de vendas: gente (gotas) cai em cima, menos sai embaixo."""
    f = [poli([(0.08, 0.22), (0.92, 0.22), (0.58, 0.66), (0.42, 0.66)], "corpo"),
         ret(0.42, 0.64, 0.58, 0.86, 0.0, "corpo"),
         elipse(0.5, 0.22, 0.42, 0.06, "detalhe")]
    for i in range(3):
        y = 0.36 + i * 0.1
        meia = 0.34 - i * 0.1
        f.append(linha([(0.5 - meia, y), (0.5 + meia, y)], 0.012, "face"))
    for i, x in enumerate((0.26, 0.42, 0.58, 0.74, 0.5)):
        k = (p * 1.6 - i * 0.18)
        if 0 < k < 1:
            y = 0.02 + k * (0.95 if i == 4 else 0.22)
            f.append(circulo(x if i < 4 else 0.5, y, 0.035, "destaque"))
    return f, 1.0, {"entrada": (0.5, 0.18), "saida": (0.5, 0.9)}


def pessoas(p=1.0, quantas=3, destaque=None):
    """Pessoas (os clientes, a equipe). `destaque` = indice da que importa."""
    f = []
    larg = 1.0 / quantas
    for i in range(quantas):
        k = _suave((p - i * 0.12) / 0.4)
        if k <= 0:
            continue
        cx = larg * (i + 0.5)
        esc = min(1.0, 3.0 / quantas) * 0.95
        dy = (1 - k) * 0.2
        # com uma em destaque, as outras recuam para detalhe (senao todas saem no acento)
        papel = "destaque" if i == destaque else ("corpo" if destaque is None else "detalhe")
        ombro = [(cx + 0.16 * esc * math.cos(math.radians(a)), 0.86 + dy - 0.2 * esc * math.sin(math.radians(a)))
                 for a in range(0, 181, 12)]
        f.append(poli([(cx + 0.16 * esc, 0.9 + dy)] + ombro + [(cx - 0.16 * esc, 0.9 + dy)], papel))
        f.append(circulo(cx, 0.52 + dy - (1 - esc) * 0.1, 0.1 * esc, papel))
    return f, 0.95, {}


def seta(p=1.0, curva=0.0, angulo=0):
    """A seta grossa do processo ("de X para Y"): cresce da ponta de tras para a frente.
    `angulo` 90 = apontando para baixo (no 9:16 o processo desce de um objeto ao outro)."""
    k = max(0.02, _suave(p))
    x1 = 0.06 + 0.88 * k
    y = 0.5
    corpo = [(0.06, y - 0.07), (x1 - 0.14, y - 0.07 - curva * 0.1), (x1 - 0.14, y - 0.18),
             (x1, y), (x1 - 0.14, y + 0.18), (x1 - 0.14, y + 0.07 - curva * 0.1), (0.06, y + 0.07)]
    return _gira([poli(corpo, "destaque")], angulo, 0.5, 0.5), 1.0, {"ponta": (x1, y)}


def igual(p=1.0):
    """O sinal de igual do processo de equivalencia ("isso e o mesmo que"): as duas barras
    crescem do centro para fora, a de cima primeiro."""
    f = []
    for i, y in enumerate((0.36, 0.64)):
        k = _suave((p - i * 0.25) / 0.75)
        if k > 0:
            m = 0.40 * k
            f.append(ret(0.5 - m, y - 0.075, 0.5 + m, y + 0.075, 0.05, "destaque"))
    return f, 1.0, {}


def marca(p=1.0, tipo="sim"):
    """Sim (check) ou nao (x), desenhado no disco do acento."""
    f = [circulo(0.5, 0.5, 0.42, "destaque" if tipo == "sim" else "corpo", duplo=True)]
    k = _suave(p)
    if tipo == "sim":
        pts = [(0.30, 0.52), (0.44, 0.66), (0.72, 0.36)]
        from .lapis import _corta
        f.append(linha(_corta(pts, k), 0.06, "vazado"))
    else:
        from .lapis import _corta
        f.append(linha(_corta([(0.33, 0.33), (0.67, 0.67)], min(1, k * 2)), 0.06, "vazado"))
        if k > 0.5:
            f.append(linha(_corta([(0.67, 0.33), (0.33, 0.67)], (k - 0.5) * 2), 0.06, "vazado"))
    return f, 1.0, {}


OBJETOS = {"relogio": relogio, "grafico_barras": grafico_barras, "grafico_pizza": grafico_pizza,
           "cedula": cedula, "moedas": moedas, "celular": celular, "calendario": calendario,
           "etiqueta_preco": etiqueta_preco, "lampada": lampada, "alvo": alvo, "funil": funil,
           "pessoas": pessoas, "seta": seta, "igual": igual, "marca": marca}

# Os objetos que a pessoa desenhou nas runs dela (minha-biblioteca/objetos.py, que o
# `motion novo` copia para o projeto como objetos_meus.py) entram na mesma lista.
try:
    import objetos_meus as _meus           # noqa: E402
    OBJETOS.update({k: v for k, v in getattr(_meus, "OBJETOS", {}).items() if k not in OBJETOS})
except ImportError:
    pass
except Exception as _e:                    # o arquivo do usuario com erro nao derruba o render
    import sys as _sys
    print(f"AVISO: objetos_meus.py com erro ({_e}); sigo sem os seus objetos. "
          "Confira com ./topclip objetos", file=_sys.stderr)
