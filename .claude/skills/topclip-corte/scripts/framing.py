# -*- coding: utf-8 -*-
"""
Planejador de enquadramento vertical com locutor ativo.

Arquitetura (a ordem importa):
  1. divide o intervalo em PLANOS reais (cortes de camera, PySceneDetect;
     o limite fixo do ffmpeg fica de reserva quando o pacote falta);
  2. por plano, AMOSTRA ESPARSA: rostos em 3 frames (inicio, meio, fim; plano
     longo, 1 a cada ~5s). Um rosto so, parado e do mesmo tamanho em todas as
     amostras -> crop estatico na mediana, e a analise densa nem roda;
  3. qualquer outra coisa (varios rostos, rosto andando, zoom, rosto sumindo)
     -> analise DENSA, que decide o tipo: close (um rosto dominante) ou aberto;
     close  -> crop estatico no rosto (sem perseguir microgesto);
     aberto -> segue o LOCUTOR ATIVO, com histerese para nao ficar pingando;
  4. suaviza e limita velocidade dentro do plano.

O enquadramento so "salta" onde ja existe corte de camera, que e onde salto e natural.
"""
from __future__ import annotations
import subprocess, re, math
import numpy as np

try:  # como pacote (scripts.framing)
    from scripts.active_speaker import analyze_shot, audio_envelope, sample_faces, SAMPLE_FPS, _corr
except ImportError:  # executado de dentro de scripts/
    from active_speaker import analyze_shot, audio_envelope, sample_faces, SAMPLE_FPS, _corr

SRC_W, SRC_H = 1920, 1080
CROP_W, CROP_H = 608, 1080
CENTER = (SRC_W-CROP_W)//2

WINDOW      = 2.0     # s por janela de decisao
SWITCH_MARGIN = 0.28  # o desafiante precisa vencer por esta margem
SWITCH_HOLD   = 3     # ...em 3 janelas seguidas, para trocar de locutor
SWITCH_MIN_ABS = 0.18 # ...e ainda ter correlacao propria minima (evita ruido)
MIN_SHOT_FOR_SWITCH = 6.0  # planos curtos: decisao global e final
DEADZONE    = 55      # px
MAX_SPEED   = 150.0   # px/s
MAX_ZOOM    = 1.45    # teto de punch-in em plano aberto (fonte 1080p: acima disso borra)
TARGET_FACE_H = 0.16  # altura de rosto desejada como fracao da altura de saida
CLOSEUP_W   = 0.085   # largura do rosto (fracao do frame) que caracteriza close
                      # medido: close ~0.12 | plano aberto ~0.03-0.05

# amostra esparsa, antes da analise densa
PROBE_EDGE  = 0.25    # s: amostra de borda fica dentro do plano, longe do frame do corte
PROBE_LONG  = 20.0    # s: plano mais longo que isso amostra por passo, nao 3 fixos
PROBE_STEP  = 5.0     # s entre amostras no plano longo
PROBE_ZOOM_TOL = 0.25 # variacao da largura do rosto que denuncia zoom de camera (docs/12)


def detect_cuts(src, a, b, thresh=0.35):
    """Cortes de camera em [a,b], em segundos absolutos."""
    return _detect_cuts(src, a, b, thresh)[0]


def _detect_cuts(src, a, b, thresh=0.35):
    """(cortes, detector usado). `thresh` so vale para o ffmpeg de reserva."""
    if b-a < 1.2: return [], "nenhum"
    raw, detector = _cuts_pyscenedetect(src, a, b), "pyscenedetect"
    if raw is None:
        raw, detector = _cuts_ffmpeg(src, a, b, thresh), "ffmpeg"
    out=sorted(set(round(t,2) for t in raw if a+0.25 < t < b-0.25))
    merged=[]
    for c in out:
        if merged and c-merged[-1] < 1.0: continue
        merged.append(c)
    return merged, detector


def _cuts_pyscenedetect(src, a, b):
    """AdaptiveDetector compara cada frame com a media movel dos vizinhos, entao
    pan e zoom de camera (mudanca gradual) nao viram corte - o limite fixo do
    ffmpeg nao separa uma coisa da outra. None quando o pacote falta ou o video
    nao abre: quem chama cai para o ffmpeg."""
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import AdaptiveDetector
    except Exception:
        return None
    try:
        video=open_video(src)
        if a > 0: video.seek(a)
        sm=SceneManager()
        sm.add_detector(AdaptiveDetector())
        sm.detect_scenes(video, end_time=b)
        return [inicio.get_seconds() for (inicio,_) in sm.get_scene_list()[1:]]
    except Exception:
        return None


def _cuts_ffmpeg(src, a, b, thresh=0.35):
    r=subprocess.run(["ffmpeg","-nostdin","-ss",f"{a:.3f}","-i",src,"-t",f"{b-a:.3f}",
                      "-vf",f"select='gt(scene,{thresh})',showinfo","-f","null","-"],
                     capture_output=True,text=True)
    return [a+float(m.group(1)) for m in re.finditer(r'pts_time:([\d.]+)', r.stdout+r.stderr)]


def _excluder(zones):
    def f(cx, cy):
        X, Y = cx*SRC_W/960.0, cy*SRC_H/540.0
        for (x0,y0,x1,y1) in zones or []:
            if x0*SRC_W <= X <= x1*SRC_W and y0*SRC_H <= Y <= y1*SRC_H: return True
        return False
    return f


def probe_times(a, b):
    """Instantes da amostra esparsa: inicio, meio e fim. Plano longo ganha 1 amostra
    a cada ~PROBE_STEP, porque 3 fixas num plano de 40s nao veem a pessoa sair do
    lugar no meio nem a camera zoomando dentro do proprio corte."""
    dur=b-a
    edge=min(PROBE_EDGE, dur*0.15)
    t0,t1=a+edge,b-edge
    n=3 if dur <= PROBE_LONG else int(math.ceil((t1-t0)/PROBE_STEP))+1
    return [round(float(t),3) for t in np.linspace(t0,t1,n)]


def _probe_verdict(samples, ex):
    """Le a amostra esparsa. Devolve (fixo, motivo): `fixo` quando o plano tem um
    rosto so, parado e do mesmo tamanho em TODAS as amostras; senao None e o
    motivo de cair na analise densa, que vai para o diagnostico.

    Na duvida, densa: nenhum rosto, rosto sumindo ou frame ilegivel tambem caem
    nela, porque errar o crop custa mais que 5 fps de deteccao."""
    if not samples: return None, "sem amostra"
    if any(fs is None for _,fs in samples): return None, "frame da amostra nao decodificou"
    faces=[[f for f in fs if not ex(f[0],f[1])] for _,fs in samples]
    n=[len(fs) for fs in faces]
    if max(n)==0: return None, "nenhum rosto na amostra"
    if max(n)>1:  return None, f"{max(n)} rostos na amostra"
    if min(n)==0: return None, f"rosto ausente em {n.count(0)} de {len(n)} amostras"
    xs=[fs[0][0]*SRC_W/960.0 for fs in faces]
    ws=[fs[0][2] for fs in faces]
    anda=max(xs)-min(xs)
    if anda >= DEADZONE:
        return None, f"rosto andou {anda:.0f}px (deadzone {DEADZONE}px)"
    zoom=(max(ws)-min(ws))/max(1e-6,float(np.median(ws)))
    if zoom > PROBE_ZOOM_TOL:
        return None, f"rosto mudou {zoom:.0%} de largura (zoom de camera)"
    return {"cx":float(np.median(xs)),"w":float(np.median(ws)),"variacao_px":round(anda,1)}, None


def _plan_single_shot(src, a, b, model, silences, zones):
    """Amostra esparsa primeiro; a analise densa so roda quando a amostra nao basta."""
    times=probe_times(a,b)
    fixo,motivo=_probe_verdict(sample_faces(src,times,model), _excluder(zones))
    if fixo:
        x=int(np.clip(round(fixo["cx"]-CROP_W/2),0,SRC_W-CROP_W))
        return [(a,x,CROP_W)], {"tipo":"close" if fixo["w"]/960.0 >= CLOSEUP_W else "unico",
                                "tracks":1,"zoom":1.0,"caminho":"amostrado",
                                "amostras":len(times),"variacao_px":fixo["variacao_px"]}
    keys,diag=_plan_dense(src,a,b,model,silences,zones)
    diag.update({"caminho":"denso","amostras":len(times),"motivo":motivo})
    return keys,diag


def _plan_dense(src, a, b, model, silences, zones):
    """Analise densa: 5 fps de deteccao + correlacao boca x audio, com histerese."""
    tracks,_ = analyze_shot(src, a, b, model, silences)
    ex=_excluder(zones)
    tracks=[t for t in tracks if not ex(t.cx,t.cy)]
    if not tracks:
        return [(a, CENTER, CROP_W)], {"tipo":"sem-rosto","tracks":0,"zoom":1.0}

    areas={id(t): float(np.mean([w*h for (_,_,_,w,h) in t.frames])) for t in tracks}
    widths={id(t): float(np.mean([w for (_,_,_,w,_) in t.frames])) for t in tracks}
    big=max(tracks,key=lambda t:areas[id(t)])

    # --- CLOSE: um rosto grande ocupa o quadro -> estatico, sem perseguicao ---
    # NAO usar "maior area" como criterio em plano aberto: quem esta mais perto da
    # camera tem o maior rosto e frequentemente NAO e quem fala.
    is_closeup = widths[id(big)]/960.0 >= CLOSEUP_W
    only_one  = len(tracks) == 1
    if is_closeup or only_one:
        cx=float(np.median([c for (_,c,_,_,_) in big.frames]))*SRC_W/960.0
        x=int(np.clip(round(cx-CROP_W/2),0,SRC_W-CROP_W))
        return [(a,x,CROP_W)], {"tipo":"close" if is_closeup else "unico",
                                "tracks":len(tracks),"zoom":1.0}

    # --- ABERTO: seguir locutor ativo com histerese ---
    env=audio_envelope(src,a,b)
    wins=[]; t=a
    while t < b-0.05:
        wins.append((t,min(t+WINDOW,b))); t+=WINDOW

    # decisao GLOBAL primeiro: correlacao no plano inteiro e muito mais estavel
    # que a de uma janela de 2s. As janelas depois so refinam e detectam troca real.
    gscore={}
    for tr in tracks:
        if len(tr.motion)<4: continue
        idx=[int(round((tt-a)*SAMPLE_FPS)) for (tt,_) in tr.motion]
        m=[e for (_,e) in tr.motion]
        aud=[env[i] for i in idx if 0<=i<len(env)]
        m=[m[j] for j,i in enumerate(idx) if 0<=i<len(env)]
        if len(m)<4: continue
        gscore[id(tr)]=_corr(m,aud)+min(float(np.mean(m)),30.0)/30.0*0.25
    cur = max(gscore,key=gscore.get) if gscore else id(big)
    pend=None; pend_n=0; keys=[]
    for (wa,wb) in wins:
        scores={}
        for tr in tracks:
            mm=[(tt,e) for (tt,e) in tr.motion if wa<=tt<wb]
            if len(mm)<4: continue
            idx=[int(round((tt-a)*SAMPLE_FPS)) for (tt,_) in mm]
            m=[e for (_,e) in mm]
            aud=[env[i] for i in idx if 0<=i<len(env)]
            m=[m[j] for j,i in enumerate(idx) if 0<=i<len(env)]
            if len(m)<4: continue
            mot=float(np.mean(m))
            scores[id(tr)] = _corr(m,aud) + min(mot,30.0)/30.0*0.25
        if scores and (b-a) >= MIN_SHOT_FOR_SWITCH:
            best=max(scores,key=scores.get)
            if best!=cur:
                margem = scores[best]-scores.get(cur,-9)
                if margem >= SWITCH_MARGIN and scores[best] >= SWITCH_MIN_ABS:
                    pend_n = pend_n+1 if pend==best else 1
                    pend=best
                    if pend_n >= SWITCH_HOLD:
                        cur=best; pend=None; pend_n=0
                else:
                    pend=None; pend_n=0
        tr=next((t for t in tracks if id(t)==cur), big)
        pos=[c for (tt,c,_,_,_) in tr.frames if wa<=tt<wb] or [tr.cx]
        keys.append(((wa+wb)/2.0, float(np.median(pos))*SRC_W/960.0))

    # punch-in adaptativo: aproxima ate o rosto do locutor ter altura util,
    # limitado por MAX_ZOOM porque a fonte e 1080p e upscale demais borra.
    spk=next((t for t in tracks if id(t)==cur), big)
    fh=float(np.median([h for (_,_,_,_,h) in spk.frames]))*SRC_H/540.0   # 540 -> 1080
    face_frac = (fh/CROP_H)                      # altura do rosto na saida, sem zoom
    zoom = 1.0 if face_frac<=0 else min(MAX_ZOOM, max(1.0, TARGET_FACE_H/face_frac))
    cw = int(round(CROP_W/zoom)); ch = int(round(CROP_H/zoom))
    cw -= cw%2; ch -= ch%2

    out=[]; curx=None
    for t,cx in keys:
        target=float(np.clip(cx-cw/2,0,SRC_W-cw))
        if curx is None: curx=target
        elif abs(target-curx)>DEADZONE:
            dt=max(1e-3,t-out[-1][0])
            curx=float(np.clip(curx+math.copysign(min(abs(target-curx),MAX_SPEED*dt),target-curx),
                               0,SRC_W-cw))
        out.append((float(t),int(round(curx)),cw))
    if out and out[0][0]>a: out.insert(0,(a,out[0][1],cw))
    mov=int(max(x for _,x,_ in out)-min(x for _,x,_ in out)) if out else 0
    return out, {"tipo":"aberto","tracks":len(tracks),"movimento_px":mov,
                 "zoom":round(zoom,2),"rosto_frac":round(face_frac,3)}


def plan_range(src, a, b, model, silences, zones=None):
    """Planeja o intervalo inteiro, dividindo por cortes de camera."""
    cuts,detector=_detect_cuts(src,a,b)
    bounds=[a]+cuts+[b]
    allkeys=[]; diags=[]
    for i in range(len(bounds)-1):
        s,e=bounds[i],bounds[i+1]
        if e-s < 0.3: continue
        k,d=_plan_single_shot(src,s,e,model,silences,zones)
        d["plano"]=f"{s:.2f}-{e:.2f}"; d["detector_cortes"]=detector
        allkeys.extend(k); diags.append(d)
    if not allkeys: allkeys=[(a,CENTER,CROP_W)]
    return allkeys, diags


def sendcmd_file(keys, path, t0):
    lines=[f"{max(0.0,t-t0):.3f} crop x {x};" for t,x,_ in keys]
    open(path,'w').write("\n".join(lines)+"\n")
    return path
