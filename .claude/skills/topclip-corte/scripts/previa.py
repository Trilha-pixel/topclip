"""Prévias da fase 2: cada corte, do bruto, horizontal, para o usuário assistir.

A prévia segue a timeline do Clip Builder — os mesmos segmentos, na mesma ordem,
sem os marcados `remove_from_body` — porque é ela que a revisão cega julga: o
usuário assiste à mesma versão que os revisores leram. Sem reenquadrar, sem
legenda, sem normalizar; reduzida a 720p, que basta para aprovar e corta o tempo
de encode.

Cada segmento entra como um `-ss/-t` próprio antes do `-i`: com reencode, a busca
na entrada é exata e não decodifica o vídeo desde o começo. Todas as prévias
rodam em paralelo.
"""
from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from scripts.utils import slugify

ALTURA = 720


def segmentos_da_previa(clip: dict[str, Any]) -> list[tuple[float, float]]:
    segs = [s for s in clip.get("segments", []) if not s.get("remove_from_body")]
    segs.sort(key=lambda s: s.get("order", 0))
    return [(float(s["source_start"]), float(s["source_end"])) for s in segs
            if float(s["source_end"]) > float(s["source_start"])]


def nome_da_previa(posicao: int, clip: dict[str, Any]) -> str:
    """`<NN>-<clip-id>-<titulo>.mp4` — NN é a posição em 06-candidates.json; o painel casa pelo id."""
    titulo = slugify(clip.get("title") or "", 40) if clip.get("title") else ""
    return f"{posicao:02d}-{slugify(str(clip.get('id')))}" + (f"-{titulo}" if titulo else "") + ".mp4"


def comando(video: str, segmentos: list[tuple[float, float]], saida: Path, com_audio: bool = True) -> list[str]:
    cmd = ["ffmpeg", "-y", "-v", "error", "-nostdin"]
    for inicio, fim in segmentos:
        cmd += ["-ss", f"{inicio:.3f}", "-t", f"{fim - inicio:.3f}", "-i", video]
    n = len(segmentos)
    if com_audio:
        entradas = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
        grafo = f"{entradas}concat=n={n}:v=1:a=1[v][a];[v]scale=-2:'min({ALTURA},ih)'[vs]"
        mapas = ["-map", "[vs]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    else:
        entradas = "".join(f"[{i}:v:0]" for i in range(n))
        grafo = f"{entradas}concat=n={n}:v=1:a=0[v];[v]scale=-2:'min({ALTURA},ih)'[vs]"
        mapas = ["-map", "[vs]"]
    return cmd + ["-filter_complex", grafo, *mapas, "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)]


def _apagar_antigas(pasta: Path, clip_id: str) -> None:
    """Uma prévia por corte: a versão anterior sai, mesmo que o título tenha mudado."""
    padrao = re.compile(rf"(^|-){re.escape(slugify(clip_id))}(-|$)")
    for p in pasta.glob("*.mp4"):
        if padrao.search(p.stem):
            p.unlink()


def cortar_previas(run: Path, video: str, candidatos: dict[str, Any], ids: set[str] | None = None,
                   com_audio: bool = True, paralelo: int = 4, progresso=None) -> dict[str, Any]:
    """`progresso(feito, total, clip_id)`, se vier, é chamado a cada prévia pronta."""
    pasta = run / "preview"
    pasta.mkdir(parents=True, exist_ok=True)
    trabalhos = []
    for posicao, clip in enumerate(candidatos.get("clips", []), 1):
        clip_id = str(clip.get("id"))
        if ids is not None and clip_id not in ids:
            continue
        segmentos = segmentos_da_previa(clip)
        if not segmentos:
            continue
        trabalhos.append((clip_id, segmentos, pasta / nome_da_previa(posicao, clip)))

    def cortar(trabalho):
        clip_id, segmentos, saida = trabalho
        _apagar_antigas(pasta, clip_id)
        proc = subprocess.run(comando(video, segmentos, saida, com_audio), capture_output=True, text=True)
        if proc.returncode != 0:
            return {"clip_id": clip_id, "erro": (proc.stderr or "ffmpeg falhou").strip()[-400:]}
        return {"clip_id": clip_id, "arquivo": str(saida.relative_to(run)),
                "segundos": round(sum(f - i for i, f in segmentos), 2), "segmentos": len(segmentos)}

    avisar = progresso or (lambda *_: None)
    resultados = []
    avisar(0, len(trabalhos), "")
    with ThreadPoolExecutor(max_workers=max(1, min(paralelo, len(trabalhos)))) as pool:
        for r in pool.map(cortar, trabalhos):
            resultados.append(r)
            avisar(len(resultados), len(trabalhos), r["clip_id"])
    nao_achados = sorted(ids - {t[0] for t in trabalhos}) if ids is not None else []
    return {
        "previas": [r for r in resultados if "arquivo" in r],
        "erros": [r for r in resultados if "erro" in r] + [{"clip_id": i, "erro": "não está em 06-candidates.json ou não tem segmento"} for i in nao_achados],
    }
