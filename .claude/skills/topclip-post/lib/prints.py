"""
Os prints: os melhores quadros com rosto, perto de cada frase e no vídeo inteiro.

Quadro de vídeo não é foto: pega a boca no meio da palavra, o olho piscando, o borrão
de quem mexeu a cabeça. Por isso nenhum print sai de um instante só — em volta de cada
frase o vídeo é lido a 3 quadros por segundo e cada quadro ganha nota:

  * rosto (o detector YuNet do enquadramento) e o tamanho dele no quadro;
  * nitidez no próprio rosto (variância do laplaciano) — derruba borrão e transição;
  * olhos abertos (o detector de olhos do OpenCV quase não acha olho fechado);
  * sorriso, que vira etiqueta e um empurrãozinho para o último print da frase.

Ficam os ~10 melhores de cada frase, espalhados no tempo (`candidatos`), e a escolha
automática para 1, 2 e 3 prints (`auto`): cada parte pega um quadro de perto de quando
foi dita, e os quadros do mesmo post precisam ser diferentes entre si. O `banco` são os
melhores rostos do vídeo inteiro — os prints da frase que a pessoa escreveu (um salmo,
uma frase dela) e a reserva da frase sem rosto por perto.

Grava em projetos/<nome>/posts/: prints.json e prints/<id>.jpg (+ prints/mini/).
"""
from __future__ import annotations

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import permutations
from pathlib import Path

import cv2
import numpy as np

import frases as F

AQUI = Path(__file__).resolve().parent
MODELO = AQUI.parents[1] / "topclip-corte" / "models" / "face_detection_yunet_2023mar.onnx"
LARGURA_MAX = 2560        # 4K desce para 2560: sobra para o post de 1080 e o JPG não pesa
FPS_FRASE = 3.0
FOLGA_S = 1.2             # lê um pouco antes e depois da frase
CANDIDATOS = 10
BANCO = 24
DET_W = 960


class ErroPrints(RuntimeError):
    pass


# ------------------------------------------------------------------ vídeo
def medir(video: Path) -> dict:
    """Largura e altura do quadro como o ffmpeg entrega (já girado) e a duração."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration",
           "-of", "json", str(video)]
    try:
        d = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        raise ErroPrints(f"não consegui ler o vídeo {video}: {e}")
    s = (d.get("streams") or [{}])[0]
    w, h = int(s.get("width") or 0), int(s.get("height") or 0)
    rot = 0
    for sd in s.get("side_data_list") or []:
        rot = int(sd.get("rotation") or rot)
    rot = int((s.get("tags") or {}).get("rotate") or rot)
    if abs(rot) % 180 == 90:
        w, h = h, w
    if not w or not h:
        raise ErroPrints(f"o vídeo {video} não tem imagem")
    if w > LARGURA_MAX:
        w, h = LARGURA_MAX, int(round(h * LARGURA_MAX / w / 2)) * 2
    return {"largura": w, "altura": h, "duracao": float((d.get("format") or {}).get("duration") or 0)}


def quadros_da_janela(video: Path, ini: float, fim: float, med: dict, fps=FPS_FRASE):
    """(t, quadro BGR) de ini a fim, decodificados de uma vez só (uma busca, não uma por quadro)."""
    w, h = med["largura"], med["altura"]
    ini = max(0.0, ini)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{max(0.4, fim - ini):.3f}",
           "-i", str(video), "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    tam, k = w * h * 3, 0
    try:
        while True:
            buf = proc.stdout.read(tam)
            if len(buf) < tam:
                break
            yield ini + k / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            k += 1
    finally:
        proc.stdout.close()
        proc.wait()


def um_quadro(video: Path, t: float, med: dict):
    w, h = med["largura"], med["altura"]
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video),
           "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if len(p.stdout) < w * h * 3:
        return None
    return np.frombuffer(p.stdout[: w * h * 3], np.uint8).reshape(h, w, 3)


# ------------------------------------------------------------------ nota do quadro
class Avaliador:
    """Um por thread: o YuNet e as cascatas do OpenCV não são seguros entre threads."""

    def __init__(self):
        if not MODELO.is_file():
            raise ErroPrints(f"falta o detector de rosto: {MODELO} (rode ./topclip instalar)")
        self.det = cv2.FaceDetectorYN.create(str(MODELO), "", (DET_W, 540), score_threshold=0.6,
                                             nms_threshold=0.3, top_k=10)
        base = cv2.data.haarcascades
        self.olhos = cv2.CascadeClassifier(base + "haarcascade_eye_tree_eyeglasses.xml")
        self.sorriso = cv2.CascadeClassifier(base + "haarcascade_smile.xml")

    def __call__(self, bgr) -> dict | None:
        H, W = bgr.shape[:2]
        k = DET_W / W
        pequeno = cv2.resize(bgr, (DET_W, int(round(H * k))))
        self.det.setInputSize((pequeno.shape[1], pequeno.shape[0]))
        _, faces = self.det.detect(pequeno)
        if faces is None or not len(faces):
            return None
        faces = sorted(faces, key=lambda f: -f[2] * f[3])
        x, y, w, h = (float(v) / k for v in faces[0][:4])
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(W, int(x + w)), min(H, int(y + h))
        if x1 - x0 < 24 or y1 - y0 < 24:
            return None
        cinza = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        rosto = cv2.resize(cinza, (200, int(200 * (y1 - y0) / (x1 - x0))))
        nitidez = float(cv2.Laplacian(rosto, cv2.CV_64F).var())
        rh = rosto.shape[0]
        olhos = self.olhos.detectMultiScale(rosto[: int(rh * 0.6)], 1.1, 6, minSize=(22, 22))
        sorriso = self.sorriso.detectMultiScale(rosto[int(rh * 0.55):], 1.6, 22, minSize=(40, 20))
        outros = [f for f in faces[1:] if f[2] * f[3] > 0.45 * faces[0][2] * faces[0][3]]
        miniatura = cv2.resize(rosto, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        return {"rosto": [round(x), round(y), round(w), round(h)], "conf": float(faces[0][-1]),
                "nitidez": nitidez, "tamanho": h / H, "olhos": int(min(2, len(olhos))),
                "sorrindo": bool(len(sorriso)), "rostos": 1 + len(outros), "miniatura": miniatura}


_por_thread = threading.local()


def avaliador() -> "Avaliador":
    """O Avaliador desta thread (carregar o detector a cada quadro custaria segundos no banco)."""
    if not hasattr(_por_thread, "av"):
        _por_thread.av = Avaliador()
    return _por_thread.av


def dar_notas(itens: list[dict]) -> None:
    """Nota de 0 a 1 de cada quadro, relativa ao grupo (a nitidez de um vídeo não se compara
    com a de outro)."""
    if not itens:
        return
    nit = sorted(i["nitidez"] for i in itens)
    teto = nit[int(0.9 * (len(nit) - 1))] or 1.0
    for i in itens:
        i["nota"] = round(
            0.42 * min(1.0, i["nitidez"] / teto)
            + 0.20 * min(1.0, i["tamanho"] / 0.30)
            + 0.14 * (i["olhos"] >= 1) + 0.08 * (i["olhos"] == 2)
            + 0.10 * min(1.0, max(0.0, (i["conf"] - 0.6) / 0.35))
            - 0.08 * (i["rostos"] > 1), 3)


def diferenca(a: dict, b: dict) -> float:
    """O quanto dois quadros parecem diferentes (rosto em miniatura): 0 = iguais."""
    return float(np.abs(a["miniatura"] - b["miniatura"]).mean())


def espalhar(itens: list[dict], k: int, gap_s: float) -> list[dict]:
    """Os k de maior nota, a pelo menos gap_s um do outro."""
    saida = []
    for i in sorted(itens, key=lambda i: -i["nota"]):
        if all(abs(i["t"] - j["t"]) >= gap_s for j in saida):
            saida.append(i)
            if len(saida) >= k:
                break
    return saida


def escolher(cands: list[dict], tempos: list[float], n: int) -> list[dict]:
    """O melhor conjunto de n quadros: cada parte perto de quando foi dita, quadros
    diferentes entre si, e um sorriso ajuda no último."""
    if len(cands) < n:
        return list(cands)
    pool = sorted(cands, key=lambda c: -c["nota"])[:9]
    melhor, nota_melhor = None, -1e9
    for combo in permutations(pool, n):
        nota = 0.0
        for i, c in enumerate(combo):
            nota += c["nota"]
            if tempos:
                nota -= 0.05 * min(6.0, abs(c["t"] - tempos[i]))
            if i == n - 1 and n > 1 and c.get("sorrindo"):
                nota += 0.06
        for a in range(n):
            for b in range(a + 1, n):
                d = diferenca(combo[a], combo[b])
                nota += 0.25 * min(1.0, d / 0.12)
                if abs(combo[a]["t"] - combo[b]["t"]) < 0.9:
                    nota -= 0.5
        if tempos and n > 1 and any(combo[i]["t"] > combo[i + 1]["t"] for i in range(n - 1)):
            nota -= 0.04                       # na ordem da fala, quando dá
        if nota > nota_melhor:
            melhor, nota_melhor = combo, nota
    return list(melhor)


# ------------------------------------------------------------------ gravar
def _salvar(pasta: Path, pid: str, bgr) -> None:
    (pasta / "mini").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(pasta / f"{pid}.jpg"), bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    h, w = bgr.shape[:2]
    cv2.imwrite(str(pasta / "mini" / f"{pid}.jpg"), cv2.resize(bgr, (360, int(360 * h / w)), interpolation=cv2.INTER_AREA),
                [cv2.IMWRITE_JPEG_QUALITY, 80])


def _publico(i: dict, pid: str) -> dict:
    return {"t": round(i["t"], 2), "arquivo": f"prints/{pid}.jpg", "mini": f"prints/mini/{pid}.jpg",
            "rosto": i["rosto"], "nota": i["nota"], "sorrindo": i["sorrindo"], "olhos": i["olhos"],
            "rostos": i["rostos"], "miniatura": [round(float(v), 3) for v in i["miniatura"].ravel()]}


def _interno(q: dict) -> dict:
    return {**q, "miniatura": np.array(q.get("miniatura") or [0.0] * 256, np.float32).reshape(16, 16)}


def ler(pasta_posts: Path) -> dict:
    try:
        return json.loads((pasta_posts / "prints.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# ------------------------------------------------------------------ o trabalho
def gerar(video: Path, pasta_posts: Path, frases: list[dict], *, refazer=False, banco=True,
          progresso=None, avisar=print) -> dict:
    """Escolhe os prints das frases (as que ainda não têm) e o banco do vídeo inteiro."""
    video = Path(video).expanduser()
    if not video.is_file():
        raise ErroPrints(f"não achei o vídeo: {video}")
    med = medir(video)
    pasta = pasta_posts / "prints"
    pasta.mkdir(parents=True, exist_ok=True)
    doc = {} if refazer else ler(pasta_posts)
    if doc.get("video") and doc["video"] != str(video):
        doc = {}                                  # outro vídeo: começa do zero
    quadros = doc.get("quadros") or {}
    por_frase = doc.get("frases") or {}
    ids_frases = {f["id"] for f in frases}
    por_frase = {k: v for k, v in por_frase.items() if k in ids_frases}
    faltam = [f for f in frases if f["id"] not in por_frase]
    fazer_banco = banco and (refazer or not doc.get("banco"))
    total = len(faltam) + (1 if fazer_banco else 0)
    feitos = [0]
    contador = [max([int(k[2:]) for k in quadros if k[2:].isdigit()] or [0])]

    def novo_id():
        contador[0] += 1
        return f"p-{contador[0]:04d}"

    def avancar(detalhe):
        feitos[0] += 1
        if progresso:
            progresso(feitos[0], total, detalhe)

    def da_frase(f):
        av = avaliador()
        itens, guardados = [], []
        for t, bgr in quadros_da_janela(video, f["inicio"] - FOLGA_S, f["fim"] + FOLGA_S, med):
            r = av(bgr)
            if r:
                r["t"] = t
                itens.append(r)
                guardados.append((r, bgr))
                if len(guardados) > 18:          # memória: fica com os mais nítidos
                    guardados.sort(key=lambda x: -x[0]["nitidez"] * x[0]["tamanho"])
                    guardados = guardados[:14]
        dar_notas(itens)
        mantidos = {id(r) for r, _ in guardados}
        escolhidos = espalhar([i for i in itens if id(i) in mantidos], CANDIDATOS, 0.6)
        return f, escolhidos, {id(r): bgr for r, bgr in guardados}

    if faltam:
        with ThreadPoolExecutor(max_workers=3) as ex:
            for f, escolhidos, imgs in ex.map(da_frase, faltam):
                ids = []
                for i in escolhidos:
                    pid = novo_id()
                    _salvar(pasta, pid, imgs[id(i)])
                    quadros[pid] = _publico(i, pid)
                    ids.append(pid)
                por_frase[f["id"]] = {"candidatos": ids}
                if not ids:
                    avisar(f"{f['id']}: nenhum rosto nítido perto da frase — o painel usa o banco do vídeo")
                avancar(f["id"])

    if fazer_banco:
        dur = med["duracao"] or 60.0
        n = int(min(160, max(40, dur / 8)))
        tempos = [dur * (k + 0.5) / n for k in range(n)]

        def amostra(t):
            bgr = um_quadro(video, t, med)
            if bgr is None:
                return None
            r = avaliador()(bgr)
            if r:
                r["t"] = t
                return r, bgr
            return None

        with ThreadPoolExecutor(max_workers=4) as ex:
            achados = [a for a in ex.map(amostra, tempos) if a]
        itens = [r for r, _ in achados]
        dar_notas(itens)
        # espalhados no vídeo e diferentes entre si: o banco é para variar
        escolhidos = []
        gap = min(max(6.0, dur / 120), dur / (BANCO * 1.5))      # vídeo curto: os rostos ficam mais perto
        for i in sorted(itens, key=lambda i: -i["nota"]):
            if all(abs(i["t"] - j["t"]) >= gap and diferenca(i, j) > 0.035 for j in escolhidos):
                escolhidos.append(i)
                if len(escolhidos) >= BANCO:
                    break
        imgs = {id(r): bgr for r, bgr in achados}
        for pid_velho in doc.get("banco") or []:
            if not any(pid_velho in v.get("candidatos", []) for v in por_frase.values()):
                quadros.pop(pid_velho, None)
        doc["banco"] = []
        for i in escolhidos:
            pid = novo_id()
            _salvar(pasta, pid, imgs[id(i)])
            quadros[pid] = _publico(i, pid)
            doc["banco"].append(pid)
        if not escolhidos:
            avisar("não achei nenhum rosto no vídeo — os posts saem com o quadro do meio da frase")
        avancar("banco do vídeo")

    # a escolha automática de 1, 2 e 3 prints de cada frase (refeita sempre: é barata)
    banco_int = [_interno({**quadros[p], "id": p}) for p in doc.get("banco", []) if p in quadros]
    for f in frases:
        info = por_frase.setdefault(f["id"], {"candidatos": []})
        cands = [_interno({**quadros[p], "id": p}) for p in info["candidatos"] if p in quadros]
        info["auto"] = {}
        for n in F.PRINTS:
            usados = escolher(cands, F.tempos_para(f, n), n)
            if len(usados) < n:                   # pouco rosto perto da frase: completa com o banco
                extra = [b for b in banco_int if all(diferenca(b, u) > 0.03 for u in usados)]
                usados += escolher(extra or banco_int, [], n - len(usados))
            info["auto"][str(n)] = [c["id"] for c in usados]

    usados = {p for v in por_frase.values() for p in v["candidatos"]} | set(doc.get("banco", []))
    for pid in [p for p in quadros if p not in usados]:
        quadros.pop(pid)
        for arq in (pasta / f"{pid}.jpg", pasta / "mini" / f"{pid}.jpg"):
            arq.unlink(missing_ok=True)
    doc.update({"versao": 1, "video": str(video), "largura": med["largura"], "altura": med["altura"],
                "gerado": datetime.now().isoformat(timespec="seconds"), "quadros": quadros, "frases": por_frase})
    (pasta_posts / "prints.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def do_banco(doc: dict, n: int, deslocamento: int = 0) -> list[str]:
    """n prints do banco para uma frase sem prints próprios (a da pessoa). O deslocamento
    (a posição da frase) faz cada frase dela começar num ponto diferente do banco."""
    banco = [p for p in doc.get("banco") or [] if p in (doc.get("quadros") or {})]
    if not banco:
        return []
    inicio = (deslocamento * n) % len(banco)
    girado = banco[inicio:] + banco[:inicio]
    cands = [_interno({**doc["quadros"][p], "id": p}) for p in girado[: max(n, 6)]]
    if len(cands) >= n:
        return [c["id"] for c in escolher(cands, [], n)]
    return ([c["id"] for c in cands] * n)[:n]                 # banco pequeno: repete, melhor que print vazio
