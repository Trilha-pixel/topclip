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
import subprocess, re, math, json
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

CUT_W, CUT_H = 256, 144  # frame que o AdaptiveDetector ve (o SceneManager tambem reduz a 256px)

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


def _video_fps(src):
    """(taxa como fracao do ffprobe, taxa em float) do primeiro stream de video."""
    r=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                      "-show_entries","stream=avg_frame_rate,r_frame_rate","-of","json",src],
                     capture_output=True,text=True)
    try:
        st=json.loads(r.stdout or "{}").get("streams",[{}])[0]
    except (ValueError, IndexError):
        return None
    for k in ("avg_frame_rate","r_frame_rate"):
        n,_,d=(st.get(k) or "0/0").partition("/")
        try:
            if float(n) > 0 and float(d or 1) > 0: return st[k], float(n)/float(d or 1)
        except ValueError:
            continue
    return None


def _cuts_pyscenedetect(src, a, b):
    """AdaptiveDetector do PySceneDetect: compara cada frame com a media movel dos
    vizinhos, entao pan e zoom de camera (mudanca gradual) nao viram corte - o
    limite fixo do ffmpeg nao separa uma coisa da outra.

    Quem decodifica e o ffmpeg, ja em CUT_W x CUT_H, nao o VideoCapture do
    open_video(): este converte cada frame 1080p numa thread so e levava o dobro
    do tempo de parede. A resolucao e a mesma que o SceneManager usaria (ele
    tambem reduz para 256px). fps=<taxa nativa> deixa a saida em taxa constante,
    entao t = a + n/fps vale ate em video VFR.
    None quando o pacote falta ou a leitura falha: quem chama cai para o ffmpeg."""
    try:
        from scenedetect.detectors import AdaptiveDetector
    except Exception:
        return None
    taxa=_video_fps(src)
    if taxa is None: return None
    frac,fps=taxa
    p=subprocess.Popen(["ffmpeg","-nostdin","-v","error","-ss",f"{a:.3f}","-i",src,"-t",f"{b-a:.3f}",
                        "-vf",f"fps={frac},scale={CUT_W}:{CUT_H}","-f","rawvideo","-pix_fmt","bgr24","-"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    det=AdaptiveDetector(); fsize=CUT_W*CUT_H*3; out=[]; n=0
    try:
        while True:
            buf=p.stdout.read(fsize)
            if len(buf) < fsize: break
            frame=np.frombuffer(buf,np.uint8).reshape(CUT_H,CUT_W,3)
            out+=[a+i/fps for i in det.process_frame(n, frame)]
            n+=1
    except Exception:
        p.kill(); n=0
    finally:
        p.stdout.close(); p.wait()
    return out if n else None


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
    """Le a amostra esparsa, uma a uma. Devolve (fixo, motivo, lidas): `fixo`
    quando o plano tem um rosto so, parado e do mesmo tamanho em TODAS as
    amostras; senao None e o motivo de cair na analise densa (vai para o
    diagnostico). Para na primeira amostra que ja decide pela densa - numa mesa,
    o primeiro frame basta, e os outros nem sao decodificados.

    Na duvida, densa: nenhum rosto, rosto sumindo ou frame ilegivel tambem caem
    nela, porque errar o crop custa mais que 5 fps de deteccao."""
    xs=[]; ws=[]; lidas=0
    for t,fs in samples:
        lidas+=1
        if fs is None: return None, f"frame em {t:.2f}s nao decodificou", lidas
        fs=[f for f in fs if not ex(f[0],f[1])]
        if not fs:     return None, f"nenhum rosto em {t:.2f}s", lidas
        if len(fs)>1:  return None, f"{len(fs)} rostos em {t:.2f}s", lidas
        xs.append(fs[0][0]*SRC_W/960.0); ws.append(fs[0][2])
        anda=max(xs)-min(xs)
        if anda >= DEADZONE:
            return None, f"rosto andou {anda:.0f}px ate {t:.2f}s (deadzone {DEADZONE}px)", lidas
        zoom=(max(ws)-min(ws))/max(1e-6,float(np.median(ws)))
        if zoom > PROBE_ZOOM_TOL:
            return None, f"rosto mudou {zoom:.0%} de largura ate {t:.2f}s (zoom de camera)", lidas
    if not xs: return None, "sem amostra", lidas
    return {"cx":float(np.median(xs)),"w":float(np.median(ws)),
            "variacao_px":round(max(xs)-min(xs),1)}, None, lidas


def _plan_single_shot(src, a, b, model, silences, zones):
    """Amostra esparsa primeiro; a analise densa so roda quando a amostra nao basta."""
    times=probe_times(a,b)
    fixo,motivo,lidas=_probe_verdict(sample_faces(src,times,model), _excluder(zones))
    if fixo:
        x=int(np.clip(round(fixo["cx"]-CROP_W/2),0,SRC_W-CROP_W))
        return [(a,x,CROP_W)], {"tipo":"close" if fixo["w"]/960.0 >= CLOSEUP_W else "unico",
                                "tracks":1,"zoom":1.0,"caminho":"amostrado",
                                "amostras":lidas,"variacao_px":fixo["variacao_px"]}
    keys,diag=_plan_dense(src,a,b,model,silences,zones)
    diag.update({"caminho":"denso","amostras":lidas,"motivo":motivo})
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
