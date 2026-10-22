#!/usr/bin/env python3
"""
Legenda TOPCLIP PAPEL v2 — MOTOR. Os dados do clipe entram por `configurar()`.

Padrao MEDIDO frame a frame numa referencia do estilo (talking head vertical, 1492
frames a 30fps, 720x1280) — nao estimado a olho. Os numeros abaixo sao o contrato.

A v1 era um dispositivo de quatro frases longas, alinhadas a esquerda em cascata, com
entrada animada de 4 frames. A medicao da referencia mostrou que quase nada disso e o
padrao. O que foi medido, e nao estimado:

  eixo horizontal   centro da linha 359,5px de 360  (desvio mediano 1,0px)  -> CENTRADO
  entrada           93% da massa ja no 1o frame; deslocamento vertical 0,7px;
                    variacao de escala 0,0%                                -> CORTE SECO
  duracao do bloco  mediana 10 frames a 30fps = 0,33s  (p25 0,20s / p75 0,53s)
  cadencia          2,45 blocos por segundo
  linhas por bloco  1 na maioria (41 de 54); 2 a 4 quando ha enfase
  corpo             glifo 38px a 720 de largura -> 57px a 1080 -> corpo ~78px
  enfase            2,1x o corpo  (nao 2,4x)
  cor               94% branco, 3,5% verde, 2,4% vermelho  -> A COR E RARA
  vertical          centro do bloco em 0,696H -> y=1337 em 1920
  largura de linha  p90 = 0,48W -> 520px de 1080

As duas correcoes que mais mudam o resultado:

  1. A FLUIDEZ NAO VEM DE EASING, VEM DE RITMO. Eu animava a entrada porque "entrar
     duro" parecia bruto. Medido: a referencia nao anima nada. O que da fluidez e a
     CADENCIA — blocos curtos trocando 2,45 vezes por segundo, cada um no lugar exato
     da palavra. Animar a entrada de um bloco que dura 10 frames gasta metade da vida
     dele em transicao, e e isso que lia como arrastado.

  2. A COR NAO E O DISPOSITIVO. Eu pintava a palavra-chave de vermelho em TODA frase.
     Na referencia 94% das linhas sao brancas. O acento so existe porque e raro.

O que NAO veio da referencia, e por que: a referencia e um talking head sem motion
graphics, entao legenda o video inteiro. Aqui 37% do clipe e cutaway com tipografia
propria (MVP, VIBE CODING, HORAS) — duas tipografias no mesmo quadro brigam. Entao a
legenda corre nas JANELAS LIVRES e cala sob os motions. Janela menor que 2s fica de
fora: legenda que pisca entre dois motions le como defeito.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import motor as V

ROOT = Path(__file__).resolve().parent
W, H = 1080, 1920

# --- tipografia, dos numeros medidos ------------------------------------------------
CORPO = 80           # glifo 57px a 1080 / cap-ratio 0,73 do Archivo Black
ENFASE = 168         # 2,1x o corpo, medido dentro dos blocos multilinha
TRACKING = -0.022    # o black ja fecha sozinho; a referencia nao e apertada
LARGURA = 560        # p90 medido = 520px; 560 da folga sem virar linha longa
# Teto de largura de UMA palavra, que nunca quebra. A enfase a 168px estoura em
# palavra longa ("MENSALIDADE," media 946px, de x=67 a 1014, no clip-005: invadia os
# 120px da direita). Acima disto o corpo DESSA palavra desce ate caber; as curtas
# ficam nos 168. 780px centrados = 150px de cada lado. O clip-005 aprovado resolveu
# a mao com 136px (~770px) — LARGURA (560) levaria a enfase a 1,24x o corpo e mataria
# o dispositivo.
LARGURA_MAX = 780
LEAD = 0.96          # entrelinha por TINTA. <1 = as linhas se tocam, como na referencia

# --- posicao vertical ---------------------------------------------------------------
# PADRAO MEDIDO num podcast (queixo ate y=1102). Num video selfie o rosto fica mais
# baixo: no clip-005 o queixo desce ate y=1486 e o padrao cobria a boca — a run
# corrigiu a mao para CY 1545 / TETO 1410. Agora a posicao sai do ROSTO detectado no
# pior frame das janelas (ver `posicionar_pelo_rosto`); o padrao e so o fallback.
CY = 1330            # centro vertical do bloco (0,693H). Medido: 0,696H
TETO = 1120          # o queixo desce ate y=1102 nos frames medidos: nada acima disto
CY_PADRAO, TETO_PADRAO = CY, TETO
QUEIXO_FOLGA = 12    # entre o queixo mais baixo e o topo da tinta
MEIO_BLOCO = 48      # metade de um bloco de uma linha + ar: o centro fica abaixo disso
ZONA_INF = H - 260   # a faixa de baixo e da interface da plataforma
ZONA_DIR = W - 120   # e a da direita tambem

BRANCO = (250, 249, 246)
VERMELHO = (201, 72, 80)      # #C94850 da paleta. Raro por design.

# --- cadencia ------------------------------------------------------------------------
ALVO = 0.33          # duracao alvo do bloco (mediana medida)
MAXDUR = 0.62        # acima disso o bloco fica pendurado
MAXPAL = 3           # palavras por bloco (medido ~1,7)
PAUSA = 0.34         # silencio que sempre fecha o bloco

# Bloco de uma palavra so existe se ela CARREGA sentido. Na referencia as palavras
# sozinhas sao sempre de conteudo ("converter", "explicacoes"); uma conjuncao sozinha
# no meio da tela le como erro de corte.
_FRACAS = {"e", "o", "a", "os", "as", "um", "uma", "de", "do", "da", "em", "no", "na",
           "que", "se", "com", "para", "pra", "por", "ou", "mas", "ao", "aos", "as",
           "seu", "sua", "te", "me", "lhe", "ja", "já", "so", "só", "e,", "a,"}

# Palavra que inverte o sentido da frase. Sumir com ela e o pior erro possivel da
# legenda: no clip-005 a tela dizia "e dificil fazer" enquanto o audio dizia "Nao e
# dificil fazer".
NEGACOES = {"não", "nao", "nunca", "nem", "nada", "ninguém", "ninguem", "jamais",
            "nenhum", "nenhuma", "sem", "tampouco", "not", "never", "don't"}

# ---------------------------------------------------------------------- CONFIGURACAO
# Estes valores sao DO CLIPE, nao da identidade. O render do projeto chama
# `configurar(...)` antes de qualquer outra coisa. Sem isso `blocos()` levanta erro em
# vez de devolver lista vazia — legenda que some silenciosamente e pior que erro.
#
#   words_json  caminho do transcript palavra-a-palavra (ver lib/transcrever.py)
#   janelas     [(inicio, fim)] em segundos, COLADAS nas bordas das cenas: a janela
#               comeca no fim de uma cena e termina no inicio da proxima. Use
#               `janelas_livres(SHOTS, DUR)`. NAO recue: o recuo de 0,15s apagava a
#               palavra que cai no vao (o "Nao" do clip-005). O bloco nunca invade a
#               cena — ele e preso a janela.
#   destaque    {(palavra_minuscula, t): {"cor": None|RGB}} — a palavra ganha a serifa
#               italica e aparece SOZINHA no bloco. Na referencia so 6% das linhas tem
#               cor: use `cor` em duas ou tres do clipe inteiro, nao mais.
#   cortes      [t] pontos onde o bloco SEMPRE fecha. Todo corte seco do proprio clipe
#               precisa estar aqui, senao um bloco junta o fim de uma frase com o
#               comeco de outra e le como erro de decupagem.
#   video       o clipe vertical (00_brief/fonte.mp4). Com ele a legenda se posiciona
#               ABAIXO DO QUEIXO mais baixo detectado nas janelas. Sem ele, ou sem
#               rosto detectado, fica na posicao fixa CY/TETO.
#   posicao     (cy, teto) para fixar a mao — vence a deteccao.
WORDS_JSON = None
JANELAS = []
DESTAQUE = {}
CORTES = []
VIDEO = None
_POS = {}


def configurar(words_json, janelas, destaque=None, cortes=None, video=None,
               posicao=None):
    global WORDS_JSON, JANELAS, DESTAQUE, CORTES, VIDEO, _WORDS
    WORDS_JSON = Path(words_json)
    JANELAS = [(float(a), float(b)) for a, b in janelas]
    DESTAQUE = dict(destaque or {})
    CORTES = list(cortes or [])
    VIDEO = Path(video) if video else None
    _WORDS = None
    _POS.clear()
    if posicao:
        _POS.update(cy=int(posicao[0]), teto=int(posicao[1]), metodo="manual")
    return WORDS_JSON


def janelas_livres(shots, dur, inicio=0.0):
    """
    As janelas da legenda: o complemento das cenas no clipe, COLADAS nas bordas —
    cada janela comeca exatamente onde uma cena termina e termina onde a proxima
    comeca. `shots` = a lista SHOTS do render (nome, fn, t0, t1, ...).

    Janela curta (< 2s) entre duas cenas sai do mesmo jeito: tirar a janela some com as
    palavras dela. Se a legenda piscar ali, ESTIQUE uma das cenas sobre o vao — o
    `check()` acusa palavra sem legenda e sem cena.
    """
    cenas = sorted((float(t0), float(t1)) for _, _, t0, t1, *_ in shots)
    out, cur = [], float(inicio)
    for t0, t1 in cenas:
        if t0 > cur + 1e-3:
            out.append((round(cur, 3), round(t0, 3)))
        cur = max(cur, t1)
    if dur > cur + 1e-3:
        out.append((round(cur, 3), round(float(dur), 3)))
    return out


_WORDS = None


def palavras():
    global _WORDS
    if _WORDS is None:
        if WORDS_JSON is None:
            raise RuntimeError(
                "captions.configurar(words_json, janelas, ...) nao foi chamado. "
                "Ver lib/render_template.py e exemplo/clipe06_config.py.")
        _WORDS = json.loads(Path(WORDS_JSON).read_text(encoding="utf-8"))
    return _WORDS


def _chave(x):
    return (x["w"].lower(), round(x["t"], 2))


def _meio(x):
    return (x["t"] + x["e"]) / 2


def _na_janela(x, ja, jb):
    """A palavra e da janela se o MEIO dela cai na janela. Com janela e cena coladas,
    o meio reparte o tempo sem buraco: palavra que atravessa a borda ("consegue" em
    4,26-4,62 com a cena entrando em 4,55, no clip-010) fica com quem tem a maior parte
    dela — a regra antiga (palavra INTEIRA dentro da janela) jogava essa no vao."""
    return ja <= _meio(x) < jb


def blocos():
    """
    Agrupa as palavras em blocos curtos. Regras, nesta ordem:
      - palavra de enfase SEMPRE forma bloco sozinha (na referencia a linha grande
        nunca divide espaco com texto de apoio no mesmo tempo);
      - fecha em pontuacao, em pausa > PAUSA, em MAXPAL palavras, ou quando ja passou
        de ALVO segundos;
      - o fim de um bloco e o INICIO do proximo: sem buraco, corte seco, como medido;
      - todo bloco fica DENTRO da sua janela: com a janela colada na cena, a sobra de
        0,10s depois da ultima palavra invadiria a cena seguinte.
    """
    ws = palavras()
    out = []
    for k, (ja, jb) in enumerate(JANELAS):
        grupo = [x for x in ws if _na_janela(x, ja, jb)]
        if not grupo:
            continue
        cur = []
        for i, x in enumerate(grupo):
            dest = DESTAQUE.get(_chave(x))
            if dest is not None and cur:
                out.append(_fecha(cur, None, k))
                cur = []
            cur.append(x)
            prox = grupo[i + 1] if i + 1 < len(grupo) else None
            dur = x["e"] - cur[0]["t"]
            gap = (prox["t"] - x["e"]) if prox else 99
            corta = prox is not None and any(x["e"] <= c <= prox["t"] + 0.02
                                             for c in CORTES)
            fim = (dest is not None or prox is None or corta or len(cur) >= MAXPAL
                   or dur >= ALVO or gap > PAUSA
                   or x["w"].rstrip()[-1:] in ".,!?;:"
                   or DESTAQUE.get(_chave(prox)) is not None)
            if fim:
                out.append(_fecha(cur, dest, k))
                cur = []
        if cur:
            out.append(_fecha(cur, None, k))
    # junta bloco de uma palavra fraca ao seguinte (nunca a um bloco de enfase, que na
    # referencia sempre aparece sozinho) — e nunca atravessando uma cena
    j, i = [], 0
    while i < len(out):
        x = out[i]
        prox = out[i + 1] if i + 1 < len(out) else None
        so_fraca = (len(x["txt"].split()) == 1
                    and x["txt"].strip(".,!?;:").lower() in _FRACAS and not x["enf"])
        if (so_fraca and prox and not prox["enf"] and prox["jan"] == x["jan"]
                and prox["t"] - x["e"] < PAUSA):
            prox["txt"] = x["txt"] + " " + prox["txt"]
            prox["t"] = x["t"]
            prox["ws"] = x["ws"] + prox["ws"]
        elif so_fraca and j and not j[-1]["enf"] and j[-1]["jan"] == x["jan"]:
            j[-1]["txt"] += " " + x["txt"]
            j[-1]["e"] = x["e"]
            j[-1]["ws"] = j[-1]["ws"] + x["ws"]
        else:
            j.append(x)
        i += 1
    out = j
    # encosta cada bloco no seguinte quando nao ha pausa de verdade
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        if 0 < b["t"] - a["e"] <= PAUSA:
            a["e"] = b["t"]
    # bloco que sobra pendurado numa pausa longa sai de cena em vez de segurar: com
    # mediana de 0,50s, um bloco de 1,0s le como travado. MAS nunca antes de a ultima
    # palavra dele acabar de ser dita: no clip-010 "mas tambem para" saia em 38,12 e o
    # "para" (38,14) aparecia antes da hora e sumia justo quando ele falava.
    for x in out:
        x["e"] = min(x["e"], max(x["t"] + MAXDUR, x["ws"][-1]["e"]))
    # e o bloco que ficou longo porque as palavras dele sao lentas se divide em dois,
    # cada palavra na tela enquanto e dita — o ritmo medido e de blocos curtos
    out = [y for x in out for y in _divide(x)]
    # nenhum bloco pode invadir o seguinte: com sobreposicao o render escolhe o
    # primeiro que casa e o bloco de baixo entra atrasado — perde a sincronia que e
    # justamente o que faz o corte seco funcionar.
    for i in range(len(out) - 1):
        out[i]["e"] = min(out[i]["e"], out[i + 1]["t"])
    # preso a janela: comeca no fim da cena anterior, termina no inicio da proxima
    for x in out:
        ja, jb = JANELAS[x["jan"]]
        x["t"], x["e"] = max(x["t"], ja), min(x["e"], jb)
    return [x for x in out if x["e"] - x["t"] >= 0.08]


def _fecha(cur, dest, jan):
    txt = " ".join(x["w"] for x in cur)
    return dict(t=cur[0]["t"], e=cur[-1]["e"] + 0.10, txt=txt, ws=list(cur),
                enf=dest is not None, cor=(dest or {}).get("cor"), jan=jan)


def _fraca(ws):
    """Pedaco so de palavras fracas ("de um", "e o"): nao carrega sentido sozinho."""
    return all(w["w"].strip(".,!?;:").lower() in _FRACAS for w in ws)


def _divide(x):
    """Bloco acima de MAXDUR com 2+ palavras vira dois, na fronteira de palavra mais
    perto do meio do tempo — e so onde os DOIS lados tem palavra de conteudo. Sem
    fronteira assim ("mas tambem para") o bloco fica inteiro: longo, mas na hora."""
    ws = x["ws"]
    if x["enf"] or len(ws) < 2 or x["e"] - x["t"] <= MAXDUR + 1e-6:
        return [x]
    meio = (x["t"] + x["e"]) / 2
    ks = [k for k in range(1, len(ws)) if not _fraca(ws[:k]) and not _fraca(ws[k:])]
    if not ks:
        return [x]
    k = min(ks, key=lambda k: abs(ws[k]["t"] - meio))
    corte = ws[k]["t"]
    a = dict(x, e=corte, ws=ws[:k], txt=" ".join(w["w"] for w in ws[:k]))
    b = dict(x, t=corte, ws=ws[k:], txt=" ".join(w["w"] for w in ws[k:]))
    return _divide(a) + _divide(b)


def fora_de_hora(b):
    """Palavras que estao num bloco mas NAO estao na tela enquanto sao ditas (o bloco
    sai antes, ou entra depois). Texto certo na hora errada contradiz o audio igual."""
    out = []
    for x in b:
        for w in x["ws"]:
            junto = min(x["e"], w["e"]) - max(x["t"], w["t"])
            if junto < min(0.08, (w["e"] - w["t"]) * 0.5):
                out.append((w, x))
    return out


# --- posicao pelo rosto --------------------------------------------------------------
YUNET = "face_detection_yunet_2023mar.onnx"


def _modelo_yunet():
    """O YuNet da skill de corte. Procura subindo as pastas: funciona da skill e de um
    projeto em projetos/<nome>/motion/..."""
    here = Path(__file__).resolve()
    for d in [here.parent, *here.parents]:
        for f in (d / ".claude" / "skills" / "topclip-corte" / "models" / YUNET,
                  d / "topclip-corte" / "models" / YUNET):
            if f.exists():
                return f
    return None


def _dimensoes(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        str(video)], capture_output=True, text=True)
    w, h = (int(v) for v in r.stdout.strip().split(",")[:2])
    return w, h


def queixos(video, janelas, fps=4.0, det_w=540):
    """
    A base do rosto (~queixo) em cada frame amostrado das janelas, em px do quadro de
    saida (1080x1920). Devolve ([(t, y_queixo)], metodo).

    YuNet (o mesmo da skill de corte): a borda de baixo da caixa cai no queixo, +-20px,
    conferido no clip-005 e no clip-010. Sem o modelo, cascata Haar do OpenCV — caixa
    mais curta (para na boca/queixo), corrigida em 1,10x a altura, e com falso positivo
    no peito: por isso usa so o MAIOR rosto do frame.
    """
    import cv2
    import numpy as np
    vw, vh = _dimensoes(video)
    det_h = int(round(det_w * vh / vw / 2) * 2)
    escala = H / det_h                     # o clipe vertical e esticado a 1080x1920
    modelo = _modelo_yunet()
    if modelo:
        det = cv2.FaceDetectorYN.create(str(modelo), "", (det_w, det_h),
                                        score_threshold=0.7, nms_threshold=0.3, top_k=10)
        metodo = "YuNet"
    else:
        haar = cv2.CascadeClassifier(cv2.data.haarcascades +
                                     "haarcascade_frontalface_default.xml")
        metodo = "Haar"
    out = []
    for ja, jb in janelas:
        if jb - ja < 0.05:
            continue
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{ja:.3f}", "-i", str(video),
               "-t", f"{jb - ja:.3f}", "-vf", f"fps={fps},scale={det_w}:{det_h}",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        raw = subprocess.run(cmd, capture_output=True).stdout
        n = len(raw) // (det_w * det_h * 3)
        frames = np.frombuffer(raw[:n * det_w * det_h * 3], np.uint8).reshape(
            n, det_h, det_w, 3)
        for i in range(n):
            if modelo:
                _, faces = det.detect(frames[i])
                caixas = [] if faces is None else [f[:4] for f in faces]
                fator = 1.0
            else:
                g = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                caixas = list(haar.detectMultiScale(g, 1.1, 5, minSize=(det_w // 9,) * 2))
                fator = 1.10
            if len(caixas):
                x, y, w, h = max(caixas, key=lambda c: c[2] * c[3])
                out.append((ja + i / fps, float((y + h * fator) * escala)))
    return out, metodo


def posicao_pelo_queixo(queixo):
    """(CY, TETO) para um queixo em y: a tinta comeca QUEIXO_FOLGA abaixo dele e o
    centro do bloco desce o necessario, nunca acima do padrao medido nem dentro da
    faixa de interface de baixo."""
    teto = max(TETO_PADRAO, int(round(queixo + QUEIXO_FOLGA)))
    cy = min(max(CY_PADRAO, teto + MEIO_BLOCO), ZONA_INF - MEIO_BLOCO)
    return cy, teto


def posicionar_pelo_rosto(video=None, janelas=None, cache=True):
    """
    Detecta o rosto no PIOR frame das janelas (queixo mais baixo — a pessoa se inclina
    durante a frase, e o meio da janela engana: armadilha 38) e posiciona a legenda
    abaixo dele. Resultado guardado ao lado do video (legenda_rosto.json), refeito se
    o video ou as janelas mudarem. Sem rosto: posicao fixa, com aviso.
    """
    video = Path(video or VIDEO)
    janelas = JANELAS if janelas is None else janelas
    arq = video.parent / "legenda_rosto.json"
    st = video.stat()
    chave = dict(video=video.name, tam=st.st_size, mtime=int(st.st_mtime),
                 janelas=[[round(a, 3), round(b, 3)] for a, b in janelas])
    if cache and arq.exists():
        try:
            d = json.loads(arq.read_text())
            if d.get("chave") == chave:
                return d
        except Exception:
            pass
    qs, metodo = queixos(video, janelas)
    if not qs:
        d = dict(chave=chave, metodo="fixo", cy=CY_PADRAO, teto=TETO_PADRAO, frames=0)
    else:
        ys = sorted(y for _, y in qs)
        if metodo == "YuNet":
            t_pior, queixo = max(qs, key=lambda q: q[1])
        else:   # Haar tem falso positivo: o p90 e mais honesto que o maximo
            queixo = ys[int(0.9 * (len(ys) - 1))]
            t_pior = min(qs, key=lambda q: abs(q[1] - queixo))[0]
        cy, teto = posicao_pelo_queixo(queixo)
        d = dict(chave=chave, metodo=metodo, frames=len(qs), queixo=round(queixo),
                 t_pior=round(t_pior, 2), cy=cy, teto=teto)
    if cache:
        try:
            arq.write_text(json.dumps(d, indent=1, ensure_ascii=False))
        except OSError:
            pass
    return d


def posicao():
    """(CY, TETO) em uso. Ordem: `configurar(posicao=...)`; CY/TETO mudados a mao no
    modulo (render.py antigo); rosto detectado no `video`; padrao fixo."""
    if not _POS:
        if CY != CY_PADRAO or TETO != TETO_PADRAO:
            _POS.update(cy=CY, teto=TETO, metodo="manual (CAP.CY/CAP.TETO)")
        elif VIDEO is not None and VIDEO.exists() and JANELAS:
            _POS.update(posicionar_pelo_rosto())
        else:
            _POS.update(cy=CY, teto=TETO, metodo="fixo")
        _relata_posicao()
    return _POS["cy"], _POS["teto"]


def _relata_posicao():
    m = _POS["metodo"]
    if m in ("YuNet", "Haar"):
        print(f"  legenda: queixo mais baixo em y={_POS['queixo']} (t={_POS['t_pior']}s, "
              f"{m}, {_POS['frames']} frames) -> CY {_POS['cy']} / TETO {_POS['teto']}")
    elif m == "fixo":
        print(f"  AVISO legenda: posicao FIXA (CY {_POS['cy']} / TETO {_POS['teto']}) — "
              f"{'nenhum rosto detectado nas janelas' if VIDEO else 'sem video em configurar()'}."
              f" Confira num frame que a legenda nao cobre a boca.", file=sys.stderr)
    else:
        print(f"  legenda: posicao {m} -> CY {_POS['cy']} / TETO {_POS['teto']}")


# --- desenho -------------------------------------------------------------------------
def _trk(size):
    return TRACKING * size          # motor conta tracking em px por caractere


def _larg(f, txt, tk):
    return sum(f.getlength(c) + tk for c in txt)


def corpo(txt, enf):
    """Corpo do bloco. A palavra que nao cabe em LARGURA_MAX desce ate caber (palavra
    nunca quebra); as que cabem ficam no corpo medido — a enfase curta continua 168."""
    base = ENFASE if enf else CORPO
    f = V.font(V.F_PLAY if enf else V.F_BLACK, base)
    maior = max((_larg(f, p, _trk(base)) for p in txt.split()), default=0)
    if maior <= LARGURA_MAX:
        return base
    return max(int(CORPO * 0.75), int(base * LARGURA_MAX / maior))


def _f(enf, size):
    return V.font(V.F_PLAY if enf else V.F_BLACK, size)


def _linha_layer(txt, f, tk, cor):
    """Uma linha desenhada num layer justo. Devolve (layer recortado na tinta)."""
    w = int(_larg(f, txt, tk)) + 2 * ENFASE
    h = int(f.size * 2.4) + 40
    lay = Image.new("RGBA", (max(8, w), max(8, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x, y = ENFASE, 20
    for c in txt:
        d.text((x, y), c, font=f, fill=cor + (255,))
        x += f.getlength(c) + tk
    bb = lay.getbbox()
    return lay.crop(bb) if bb else lay


def _linhas(txt, enf):
    """Quebra em linhas que caibam em LARGURA. Palavra sozinha nunca quebra."""
    size = corpo(txt, enf)
    f = _f(enf, size)
    tk = _trk(size)
    out, cur = [], []
    for p in txt.split():
        if cur and _larg(f, " ".join(cur + [p]), tk) > LARGURA:
            out.append(" ".join(cur))
            cur = [p]
        else:
            cur.append(p)
    if cur:
        out.append(" ".join(cur))
    return out, f, tk


def _layout(bloco):
    """As linhas do bloco e onde cada uma vai: [(layer, (x, y))]. Empilha por TINTA, nao
    por metrica da fonte: so assim uma entrelinha < 1 fica previsivel em vez de
    colidir. E a entrelinha apertada e a diagramacao da referencia."""
    linhas, f, tk = _linhas(bloco["txt"], bloco["enf"])
    cor = bloco.get("cor") or BRANCO
    caps = [_linha_layer(l, f, tk, cor) for l in linhas]
    passos = [caps[i].height * LEAD for i in range(len(caps) - 1)]
    total = sum(passos) + caps[-1].height
    cy, teto = posicao()
    y = max(teto, cy - total / 2)
    out = []
    for i, c in enumerate(caps):
        out.append((c, (int((W - c.width) / 2), int(y))))
        if i < len(passos):
            y += passos[i]
    return out


def caixa(bloco):
    """Caixa da tinta do bloco no quadro (x0, y0, x1, y1), sem sombra nem boil."""
    lay = _layout(bloco)
    return (min(p[0] for _, p in lay), lay[0][1][1],
            max(p[0] + c.width for c, p in lay), lay[-1][1][1] + lay[-1][0].height)


def draw(bloco, progress=1.0, backdrop=None, frame=0.0):
    """
    Uma legenda. `progress` existe so por compatibilidade e e IGNORADO: a referencia
    entra em CORTE SECO — 93% da massa ja no primeiro frame, deslocamento vertical de
    0,7px e variacao de escala de 0,0%, tudo medido. Animar a entrada de um bloco que
    dura 10 frames gastaria metade da vida dele em transicao.

    A tipografia leva boil no preset "print": ruido fino que erode a BORDA da letra,
    como tinta em papel aspero. Nao e o boil dos objetos — aquele tem ruido grosso e
    deformaria a forma da letra.
    """
    tinta = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for c, pos in _layout(bloco):
        tinta.alpha_composite(c, pos)

    # sombra: a referencia tem uma, e sem ela o branco some no pescoco iluminado
    a = tinta.getchannel("A").filter(ImageFilter.GaussianBlur(7)).point(
        lambda v: int(v * 0.62))
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sombra.putalpha(ImageChops.offset(a, 0, 5))

    out = Image.alpha_composite(sombra, tinta)
    return V.boil_full(out, frame, seed=int(frame * 9 / 24) * 131 + 7,
                       **V.BOIL_PRESETS["print"])


def build(*_a, **_kw):
    return blocos()


def palavras_orfas(shots=()):
    """
    Palavras ditas com o ROSTO na tela e sem legenda: fora de toda janela e fora de toda
    cena. Debaixo de uma cena a legenda cala de proposito (duas tipografias brigam);
    fora dela, palavra sem legenda e texto contradizendo o audio.
    """
    cenas = [(float(t0), float(t1)) for _, _, t0, t1, *_ in (shots or ())]
    out = []
    for x in palavras():
        if any(_na_janela(x, ja, jb) for ja, jb in JANELAS):
            continue
        if any(t0 <= _meio(x) <= t1 for t0, t1 in cenas):
            continue
        out.append(x)
    return out


def _e_negacao(w):
    return w.lower().strip(".,!?;:\"'()…-") in NEGACOES


def check(shots=None):
    """
    Confere a legenda ANTES do render. Levanta erro (lista tudo antes) se:
      - alguma palavra dita fica sem legenda e sem cena (negacao destacada);
      - algum bloco invade uma cena, ou estoura a largura (120px da direita).
    Avisa se o bloco desce para a faixa de interface (260px de baixo), se uma janela e
    curta demais, e se a fonte nao tem algum glifo.
    """
    if not JANELAS:
        raise RuntimeError("nenhuma janela configurada — chame captions.configurar()")
    erros = []
    b = blocos()
    ws = palavras()
    livre = sum(j[1] - j[0] for j in JANELAS)
    print(f"{len(b)} blocos em {livre:.1f}s de janela livre")
    dur = sorted(x["e"] - x["t"] for x in b)
    if dur:
        print(f"  duracao: med {dur[len(dur)//2]:.2f}s  min {dur[0]:.2f}  max {dur[-1]:.2f}")
        print(f"  cadencia: {len(b)/livre:.2f} blocos/s (referencia 2,45)")
        npal = [len(x["txt"].split()) for x in b]
        print(f"  palavras/bloco: med {sorted(npal)[len(npal)//2]}  "
              f"media {sum(npal)/len(npal):.2f} (referencia ~1,7)")
        enf = [x for x in b if x["enf"]]
        print(f"  enfase: {len(enf)} ({100*len(enf)/len(b):.0f}%)  "
              f"com cor: {len([x for x in enf if x['cor']])} "
              f"({100*len([x for x in enf if x['cor']])/len(b):.0f}%, referencia 6%)")

    # 1. toda palavra dita com o rosto na tela tem que estar na tela
    orfas = palavras_orfas(shots)
    if orfas:
        neg = [x for x in orfas if _e_negacao(x["w"])]
        linhas = []
        for x in orfas:
            marca = ("   <<< NEGACAO: sem ela a legenda diz o CONTRARIO do audio"
                     if _e_negacao(x["w"]) else "")
            linhas.append(f"      {x['t']:6.2f}s  {x['w']!r}{marca}")
        erros.append(
            f"{len(orfas)} palavra(s) dita(s) com o rosto na tela e SEM legenda"
            + (f" — {len(neg)} negacao(oes)" if neg else "") + ":\n" + "\n".join(linhas)
            + "\n    Cole o inicio da janela no FIM da cena (e o fim no inicio da "
              "proxima): janelas=captions.janelas_livres(SHOTS, DUR). Janela curta "
              "demais? Estique a cena sobre o vao.")
    faladas = []
    for ja, jb in JANELAS:
        faladas += [x["w"] for x in ws if _na_janela(x, ja, jb)]
    na_tela = " ".join(x["txt"] for x in b).split()
    if faladas != na_tela:
        erros.append(f"palavra perdida dentro da janela: {set(faladas) ^ set(na_tela)}")
    else:
        print(f"  OK: as {len(faladas)} palavras das janelas estao todas na tela")
    for w, x in fora_de_hora(b):
        erros.append(f"{w['w']!r} ({w['t']:.2f}-{w['e']:.2f}s) nao esta na tela enquanto "
                     f"e dita: o bloco {x['txt']!r} fica de {x['t']:.2f} a {x['e']:.2f}s"
                     + ("   <<< NEGACAO" if _e_negacao(w["w"]) else ""))

    # 2. nenhum bloco invade cena
    if shots:
        for name, _, t0, t1, *_ in shots:
            for x in b:
                if not (x["e"] <= t0 + 0.01 or x["t"] >= t1 - 0.01):
                    erros.append(f"bloco {x['txt']!r} ({x['t']:.2f}-{x['e']:.2f}s) "
                                 f"invade {name} ({t0}-{t1}s)")
    for ja, jb in JANELAS:
        if jb - ja < 2.0 and any(_na_janela(x, ja, jb) for x in ws):
            print(f"  aviso: janela {ja:.2f}-{jb:.2f}s tem so {jb - ja:.1f}s — a legenda "
                  f"pisca entre duas cenas. Se ler mal, estique uma cena sobre o vao.")

    # 3. geometria: largura, faixa de baixo, glifos
    if b:
        cxs = [(x, caixa(x)) for x in b]
        x0 = min(c[0] for _, c in cxs)
        x1 = max(c[2] for _, c in cxs)
        y0 = min(c[1] for _, c in cxs)
        y1 = max(c[3] for _, c in cxs)
        print(f"  tinta da legenda: x {x0}-{x1}  y {y0}-{y1}")
        for x, c in cxs:
            if c[2] > ZONA_DIR or c[0] < W - ZONA_DIR:
                erros.append(f"bloco {x['txt']!r} estoura a largura: x {c[0]}-{c[2]}")
            if c[3] > ZONA_INF:
                print(f"  aviso: bloco {x['txt']!r} desce ate y={c[3]} (faixa de "
                      f"interface comeca em {ZONA_INF})")
        reduz = [x for x in b if corpo(x["txt"], x["enf"]) < (ENFASE if x["enf"] else CORPO)]
        for x in reduz:
            print(f"  enfase longa {x['txt']!r}: corpo {corpo(x['txt'], x['enf'])} "
                  f"para caber em {LARGURA_MAX}px")
        for x in b:
            fonte = V.F_PLAY if x["enf"] else V.F_BLACK
            for ch, motivo in V.glifos_problema(x["txt"], fonte):
                print(f"  aviso glifo: {ch!r} em {x['txt']!r}: {motivo}")

    if erros:
        for e in erros:
            print(f"  ERRO legenda: {e}", file=sys.stderr)
        raise RuntimeError(f"{len(erros)} erro(s) na legenda — corrija antes do render")
    if shots:
        print("  OK: nenhum bloco invade janela de motion; nenhuma palavra sem legenda")
    return b


if __name__ == "__main__":
    check()
