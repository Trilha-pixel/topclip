# -*- coding: utf-8 -*-
"""
Autoframe: preenche crop_anchor_x e zoom por segmento usando LOCUTOR ATIVO.

Alimenta o renderer que ja existe (scripts/render.py) em vez de criar um caminho
paralelo: a saida sao entradas de `timeline` validas pelo edit-plans.schema.json.

Cadeia de decisao por segmento:
    corte de camera -> amostra esparsa (3 frames, ou 1 a cada ~5s em plano longo)
      -> um rosto parado: anchor estatico, fim
      -> o resto: tipo de plano -> locutor ativo (5 fps) -> anchor + zoom

O relatorio diz, por plano, qual caminho rodou ("caminho": amostrado|denso) e
por que a amostra nao bastou ("motivo").

Uso:
    python3 scripts/autoframe.py --video V.mp4 --segments segs.json --out plano.json
    python3 scripts/autoframe.py --video V.mp4 --edit-plans 11-edit-plans.json --in-place
"""
from __future__ import annotations
import argparse, json, math, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # como pacote (scripts.autoframe)
    from scripts.framing import plan_range, SRC_W, SRC_H, CROP_W, CROP_H, CENTER  # noqa: E402
except ImportError:  # executado de dentro de scripts/
    from framing import plan_range, SRC_W, SRC_H, CROP_W, CROP_H, CENTER  # noqa: E402

DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx"


def detect_silences(video, noise_db=-32, min_dur=0.18):
    r = subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",str(video),"-vn",
                        "-af",f"silencedetect=noise={noise_db}dB:d={min_dur}","-f","null","-"],
                       capture_output=True, text=True)
    out=[]; cur=None
    for line in (r.stderr or "").splitlines():
        m=re.search(r"silence_start: ([\d.]+)", line)
        if m: cur=float(m.group(1))
        m=re.search(r"silence_end: ([\d.]+)", line)
        if m and cur is not None: out.append((cur,float(m.group(1)))); cur=None
    return out


def anchor_from_cx(cx, zoom, out_w=1080, out_h=1920, src_w=SRC_W, src_h=SRC_H):
    """Converte centro-x em pixels da fonte para crop_anchor_x (0..1) do renderer."""
    s = max(out_w*zoom/src_w, out_h*zoom/src_h)
    scaled_w = src_w*s
    denom = scaled_w - out_w
    if denom <= 0: return 0.5
    return float(min(1.0, max(0.0, (s*cx - out_w/2)/denom)))


MECANICOS = {"source_start", "source_end", "crop_anchor_x", "zoom"}
MIN_SUBSEG = 0.15   # s: enquadramento que dura menos que isso e piscada, nao subsegmento
ZOOM_MAX = 2.0      # teto do edit-plans.schema.json (o render tambem corta em 2.0)


def _zoom_pedido(valor):
    """O zoom que o Edit Director escreveu no segmento: o punch-in dele (1.0 = nenhum)."""
    try:
        z = float(valor)
    except (TypeError, ValueError):
        return 1.0
    return max(1.0, min(ZOOM_MAX, z)) if math.isfinite(z) else 1.0


def _normalizar(segments):
    """Aceita [(a,b)] ou [{"source_start":..,"source_end":..,...}].

    Devolve (a, b, herdaveis, punch) onde herdaveis sao os campos EDITORIAIS do
    segmento de origem - layout, framing_reason, transition_in, preserve_pause,
    order - e punch e o zoom que o Edit Director pediu para o segmento.
    """
    saida = []
    for item in segments:
        if isinstance(item, dict):
            a, b = float(item["source_start"]), float(item["source_end"])
            herda = {k: v for k, v in item.items() if k not in MECANICOS}
            punch = _zoom_pedido(item.get("zoom"))
        else:
            a, b = float(item[0]), float(item[1])
            herda, punch = {}, 1.0
        saida.append((a, b, herda, punch))
    return saida


def _fundir_iguais(subs):
    out = []
    for s in subs:
        if out and out[-1][2:] == s[2:]:
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


def _cobrir(keys, a, b, minimo=MIN_SUBSEG):
    """keys [(t, x, w)] -> [[ini, fim, x, w]] cobrindo [a, b] inteiro, sem buraco.

    Cada key vale da sua vez ate a seguinte; a primeira vale desde `a` (o
    plan_range pula plano < 0,3s, entao ela pode vir depois). Trecho mais curto
    que `minimo` nao vira subsegmento, mas o TEMPO dele fica com o vizinho de
    tras (ou com o da frente, se nao houver). Descartar o trecho abria buraco na
    fonte, e o render concatenava os vizinhos pulando esse audio (docs/12).
    """
    keys = list(keys) or [(a, CENTER, CROP_W)]
    inicios = [a]
    for (t, _, _) in keys[1:]:
        inicios.append(min(b, max(inicios[-1], float(t))))
    fins = inicios[1:] + [b]
    brutos = _fundir_iguais([[i, f, x, w] for i, f, (_, x, w) in zip(inicios, fins, keys)])
    subs = []; sem_dono = None
    for ini, fim, x, w in brutos:
        if fim - ini < minimo:
            if subs: subs[-1][1] = fim
            elif sem_dono is None: sem_dono = ini
            continue
        subs.append([ini if sem_dono is None else sem_dono, fim, x, w]); sem_dono = None
    if not subs:   # segmento inteiro mais curto que `minimo`: o enquadramento mais longo
        ini, fim, x, w = max(brutos, key=lambda s: s[1] - s[0])
        subs = [[a, b, x, w]]
    return _fundir_iguais(subs)


def plan_segments(video, segments, model=None, silences=None, zones=None):
    """segments: [(start,end)] ou [{...}] -> subsegmentos com anchor/zoom.

    O autoframe decide ENQUADRAMENTO MECANICO (para onde apontar, quanto fechar).
    A decisao editorial do Edit Director - layout split/cover, o motivo do
    enquadramento - e herdada intacta por cada subsegmento. Sobrescreve-la
    apagaria a etapa anterior.

    O zoom do Edit Director e punch-in RELATIVO ao enquadramento do rosto: zoom
    final = zoom do rosto x zoom pedido, ate ZOOM_MAX. Com max() em vez de
    produto, o punch-in sumiria num plano aberto em que o rosto ja pede mais.

    Os subsegmentos de cada segmento cobrem a faixa dele na fonte inteira: a
    versao do corte (scripts/versoes.py) e o audio do render nao mudam.
    """
    model = str(model or DEFAULT_MODEL)
    if silences is None:
        silences = detect_silences(video)
    timeline=[]; report=[]
    for (a,b,herda,punch) in _normalizar(segments):
        keys, diags = plan_range(str(video), float(a), float(b), model, silences, zones)
        # keys = [(t, crop_x_px, crop_w_px)] -> subsegmentos constantes e contiguos
        merged = _cobrir(keys, a, b)
        for (s0,e0,x,w) in merged:
            zoom_rosto = CROP_W/float(w) if w else 1.0
            zoom = round(max(1.0, min(ZOOM_MAX, zoom_rosto*punch)), 4)
            cx = x + w/2.0
            timeline.append({**herda,
                             "source_start": round(s0,3), "source_end": round(e0,3),
                             "crop_anchor_x": round(anchor_from_cx(cx, zoom),4),
                             "zoom": zoom})
        rel = {"segmento": [round(a,3), round(b,3)],
               "subsegmentos": len(merged), "planos": diags,
               "caminhos": {c: sum(1 for d in diags if d.get("caminho")==c)
                            for c in ("amostrado", "denso")}}
        if punch != 1.0:
            rel["zoom_pedido"] = punch
        report.append(rel)
    return timeline, report


def main():
    ap=argparse.ArgumentParser(description="Enquadramento automatico por locutor ativo")
    ap.add_argument("--video", required=True)
    ap.add_argument("--segments", help='JSON: [[inicio,fim],...]')
    ap.add_argument("--edit-plans", help="11-edit-plans.json para enriquecer")
    ap.add_argument("--out"); ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--exclude-zones", help='JSON: [[x0,y0,x1,y1],...] normalizado (ex.: telas do cenario)')
    a=ap.parse_args()

    if not Path(a.model).exists():
        print(f"ERRO: modelo YuNet ausente em {a.model}", file=sys.stderr); return 2
    zones=json.loads(a.exclude_zones) if a.exclude_zones else None
    sil=detect_silences(a.video)

    if a.edit_plans:
        doc=json.loads(Path(a.edit_plans).read_text())
        for plan in doc.get("plans",[]):
            segs=plan.get("timeline",[])
            tl,_=plan_segments(a.video,segs,a.model,sil,zones)
            plan["timeline"]=tl
        dest=Path(a.edit_plans if a.in_place else (a.out or "edit-plans.autoframed.json"))
        dest.write_text(json.dumps(doc,ensure_ascii=False,indent=1))
        print(f"edit-plans atualizado: {dest}")
        return 0

    segs=json.loads(Path(a.segments).read_text()) if Path(a.segments).exists() else json.loads(a.segments)
    tl,rep=plan_segments(a.video,segs,a.model,sil,zones)
    out={"schema_version":"1.0","timeline":tl,"report":rep}
    if a.out:
        Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=1)); print(f"gravado: {a.out}")
    else:
        print(json.dumps(out,ensure_ascii=False,indent=1))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
