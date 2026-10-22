from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import sys
import time
import types
from pathlib import Path
from typing import Any, Callable

from scripts.utils import REPO_ROOT, HarnessError, format_timecode, write_json

BACKENDS = ("auto", "mlx-whisper", "faster-whisper")

# Nome curto do config -> repositório MLX no Hugging Face. O faster-whisper
# resolve os mesmos nomes curtos sozinho (Systran/faster-whisper-<nome>).
MLX_MODELOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


def apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_disponivel() -> bool:
    return apple_silicon() and importlib.util.find_spec("mlx_whisper") is not None


def escolher_backend(backend: str = "auto", model_name: str = "small", device: str = "auto") -> str:
    """
    `auto`: mlx-whisper (GPU do Mac) quando roda em Apple Silicon, o pacote está
    instalado e o modelo tem versão MLX; senão faster-whisper (CPU, ou CUDA).
    Um `device` fixado no config (cpu/cuda) é pedido explícito de faster-whisper.
    """
    if backend not in BACKENDS:
        raise HarnessError(f"Backend de transcrição desconhecido: {backend} (use {', '.join(BACKENDS)})")
    if backend != "auto":
        return backend
    if device == "auto" and mlx_disponivel() and _repo_mlx(model_name):
        return "mlx-whisper"
    return "faster-whisper"


def transcribe(
    media_path: str | Path,
    output_path: str | Path,
    *,
    backend: str = "auto",
    model_name: str = "small",
    language: str | None = "pt",
    device: str = "auto",
    compute_type: str = "auto",
    vad_filter: bool = True,
    progress: "ProgressoTranscricao | None" = None,
) -> dict[str, Any]:
    escolhido = escolher_backend(backend, model_name, device)
    if escolhido == "mlx-whisper":
        if progress:
            progress.comecar(escolhido, model_name)
        try:
            return transcribe_mlx_whisper(
                media_path, output_path, model_name=model_name, language=language,
                compute_type=compute_type, progress=progress,
            )
        except Exception as exc:
            if backend != "auto":
                raise
            # No automático, uma falha da GPU não pode custar a run: refaz na CPU.
            aviso = f"mlx-whisper falhou ({str(exc)[:160]}); refazendo com faster-whisper na CPU"
            if progress:
                progress.avisar(aviso)
            else:
                print(f"[transcrição] {aviso}", file=sys.stderr, flush=True)
    if progress:
        progress.comecar("faster-whisper", model_name)
    return transcribe_faster_whisper(
        media_path, output_path, model_name=model_name, language=language, device=device,
        compute_type=compute_type, vad_filter=vad_filter, progress=progress,
    )


def transcribe_faster_whisper(
    media_path: str | Path,
    output_path: str | Path,
    *,
    model_name: str = "small",
    language: str | None = "pt",
    device: str = "auto",
    compute_type: str = "auto",
    vad_filter: bool = True,
    progress: "ProgressoTranscricao | None" = None,
) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise HarnessError(
            "faster-whisper não está instalado. Forneça uma transcrição ou execute: pip install faster-whisper"
        ) from exc
    if device == "auto":
        device = "cuda" if _cuda_available() else "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    if progress and not _em_cache_faster_whisper(model_name):
        progress.avisar(f"baixando o modelo de transcrição ({model_name}) — só na primeira vez")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(Path(media_path).expanduser().resolve()),
        language=language,
        word_timestamps=True,
        vad_filter=vad_filter,
        beam_size=5,
    )
    duracao = float(getattr(info, "duration", 0) or 0)
    segments = []
    for idx, segment in enumerate(segments_iter):
        segments.append(_segmento(
            idx, segment.start, segment.end, segment.text,
            [(w.word, w.start, w.end, w.probability) for w in segment.words or []],
        ))
        if progress:
            progress(float(segment.end), duracao)
    return _gravar(
        output_path, media_path, segments,
        backend="faster-whisper", model_name=model_name,
        language=getattr(info, "language", language or "unknown"),
        language_probability=getattr(info, "language_probability", None),
        progress=progress,
    )


def transcribe_mlx_whisper(
    media_path: str | Path,
    output_path: str | Path,
    *,
    model_name: str = "small",
    language: str | None = "pt",
    compute_type: str = "auto",
    progress: "ProgressoTranscricao | None" = None,
) -> dict[str, Any]:
    """
    Whisper na GPU do Apple Silicon (MLX). Mesmo modelo e mesmo schema do
    faster-whisper; as diferenças são de decodificação: gulosa (o mlx-whisper
    não tem beam search) e sem filtro de VAD.
    """
    if not apple_silicon():
        raise HarnessError("mlx-whisper só roda em Mac com Apple Silicon (M1 ou mais novo)")
    try:
        import mlx_whisper
    except ImportError as exc:
        raise HarnessError("mlx-whisper não está instalado. Rode ./topclip instalar") from exc
    repo = _repo_mlx(model_name) or model_name
    if progress and not _em_cache_hf(repo):
        progress.avisar(f"baixando o modelo de transcrição ({model_name}) — só na primeira vez")
    with _ContadorMlx(progress):
        result = mlx_whisper.transcribe(
            str(Path(media_path).expanduser().resolve()),
            path_or_hf_repo=repo,
            language=language,
            word_timestamps=True,
            fp16=compute_type != "float32",
            verbose=None,
        )
    segments = []
    for raw in result.get("segments", []):
        texto = str(raw.get("text", "")).strip()
        if not texto:   # o mlx-whisper devolve, esvaziados, os trechos que descartou
            continue
        segments.append(_segmento(
            len(segments), raw["start"], raw["end"], texto,
            [(w["word"], w["start"], w["end"], w.get("probability")) for w in raw.get("words") or []],
        ))
    return _gravar(
        output_path, media_path, segments,
        backend="mlx-whisper", model_name=model_name,
        language=result.get("language") or language or "unknown",
        language_probability=None,
        progress=progress,
    )


def _segmento(idx: int, start: Any, end: Any, text: str, words: list[tuple]) -> dict[str, Any]:
    return {
        "id": idx,
        "start": float(start),
        "end": float(end),
        "text": text.strip(),
        "speaker": "UNKNOWN",
        "confidence": None,
        "words": [
            {
                "word": str(word).strip(),
                "start": float(w_start),
                "end": float(w_end),
                # fp16 às vezes devolve 1.0000001; o schema exige [0, 1]
                "probability": min(1.0, max(0.0, float(prob))) if prob is not None else None,
            }
            for word, w_start, w_end, prob in words
        ],
    }


def _gravar(
    output_path: str | Path,
    media_path: str | Path,
    segments: list[dict[str, Any]],
    *,
    backend: str,
    model_name: str,
    language: str,
    language_probability: float | None,
    progress: "ProgressoTranscricao | None",
) -> dict[str, Any]:
    if not segments:
        raise HarnessError("O backend de transcrição não retornou segmentos")
    output = {
        "schema_version": "1.0",
        "source": str(Path(media_path).expanduser().resolve()),
        "language": language,
        "language_probability": language_probability,
        "duration_seconds": max(s["end"] for s in segments),
        "backend": backend,
        "model": model_name,
        "segments": segments,
    }
    write_json(output_path, output)
    if progress:
        progress.terminar(output["duration_seconds"])
    return output


def _repo_mlx(model_name: str) -> str | None:
    if model_name in MLX_MODELOS:
        return MLX_MODELOS[model_name]
    if "/" in model_name and "mlx" in model_name.lower():
        return model_name
    return None


def _em_cache_hf(repo: str) -> bool:
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo, local_files_only=True)
        return True
    except Exception:
        return False


def _em_cache_faster_whisper(model_name: str) -> bool:
    try:
        from faster_whisper.utils import download_model
        download_model(model_name, local_files_only=True)
        return True
    except Exception:
        return False


class _ContadorMlx:
    """
    O mlx-whisper só expõe o avanço pela barra tqdm dele (`pbar.update(frames)`
    a cada janela de 30 s). Troca a barra por um contador enquanto transcreve.
    Se uma versão futura mudar isso, a transcrição segue — só sem progresso.
    """

    def __init__(self, progress: "ProgressoTranscricao | None"):
        self.progress = progress
        self.modulo = None
        self.original = None

    def __enter__(self):
        if not self.progress:
            return self
        try:
            modulo = importlib.import_module("mlx_whisper.transcribe")
            from mlx_whisper.audio import FRAMES_PER_SECOND
            self.original = modulo.tqdm
        except Exception:
            return self
        progress = self.progress

        class Barra:
            def __init__(self, total=0, **_):
                self.total, self.n = total or 0, 0

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def update(self, n=1):
                self.n += n
                progress(self.n / FRAMES_PER_SECOND, self.total / FRAMES_PER_SECOND)

        modulo.tqdm = types.SimpleNamespace(tqdm=Barra)
        self.modulo = modulo
        return self

    def __exit__(self, *_):
        if self.modulo is not None:
            self.modulo.tqdm = self.original
        return False


def _carregar_atividade():
    """painel/atividade.py — o diário que o painel mostra. Ausente: só terminal."""
    caminho = REPO_ROOT / "painel" / "atividade.py"
    if not caminho.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("topclip_atividade", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    except Exception:
        return None


class ProgressoTranscricao:
    """
    Anuncia o avanço da transcrição algumas vezes por minuto (não a cada
    segmento) no stderr e, quando a run mora em projetos/<nome>/, no diário que
    o painel mostra em Atividade. Anunciar nunca derruba a transcrição.
    """

    def __init__(self, destino: str | Path | None = None, *, intervalo_s: float = 15.0,
                 relogio: Callable[[], float] = time.monotonic):
        self.intervalo_s = float(intervalo_s)
        self.relogio = relogio
        self.atividade = _carregar_atividade()
        self.projeto = None
        if self.atividade and destino is not None:
            try:
                self.projeto = self.atividade.achar_projeto([str(Path(destino).expanduser().resolve())])
            except Exception:
                self.projeto = None
        self.backend = ""
        self.t0 = self.relogio()
        self.ultimo = None

    def comecar(self, backend: str, model_name: str) -> None:
        self.backend = backend
        self.t0 = self.relogio()
        self.ultimo = None
        onde = "na placa de vídeo do Mac" if backend == "mlx-whisper" else "no processador"
        self._anunciar(f"transcrição começou: {backend}, modelo {model_name}, {onde}", "info")

    def avisar(self, msg: str) -> None:
        self._anunciar(msg, "info")

    def __call__(self, segundo: float, duracao: float) -> None:
        try:
            agora = self.relogio()
            # O primeiro anúncio também espera um intervalo: no começo não há o que dizer.
            if agora - (self.ultimo if self.ultimo is not None else self.t0) < self.intervalo_s:
                return
            self.ultimo = agora
            segundo = max(0.0, min(segundo, duracao) if duracao > 0 else segundo)
            if duracao > 0:
                pct = int(100 * segundo / duracao)
                msg = f"transcrevendo: {_mmss(segundo)} de {_mmss(duracao)} ({pct}%)"
                falta = _estimar_falta(agora - self.t0, segundo, duracao)
                if falta:
                    msg += f" · faltam {falta}"
            else:
                pct, msg = None, f"transcrevendo: {_mmss(segundo)}"
            self._anunciar(msg, "progresso", segundo=round(segundo, 1),
                           duracao=round(duracao, 1) if duracao > 0 else None, pct=pct)
        except Exception:
            pass

    def terminar(self, duracao_audio: float) -> None:
        gasto = self.relogio() - self.t0
        self._anunciar(f"transcrição pronta: {_mmss(duracao_audio)} de áudio em {_duracao(gasto)} ({self.backend})",
                       "info", segundos=round(gasto, 1))

    def _anunciar(self, msg: str, tipo: str, **extra) -> None:
        try:
            print(f"[transcrição] {msg}", file=sys.stderr, flush=True)
        except Exception:
            pass
        if self.atividade and self.projeto:
            try:
                if tipo == "progresso":         # casa com o comando que o lançador abriu
                    extra["id"] = os.environ.get("TOPCLIP_ATIVIDADE") or None
                self.atividade.registrar(self.projeto, msg, tipo=tipo, etapa="momentos", **extra)
            except Exception:
                pass


def _mmss(segundos: float) -> str:
    return format_timecode(segundos, decimals=0).removeprefix("00:")


def _duracao(segundos: float) -> str:
    s = int(round(segundos))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}min {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}min"


def _estimar_falta(gasto: float, feito: float, total: float) -> str | None:
    # Antes de 5% o ritmo ainda é ruído (modelo carregando, primeira janela).
    if feito <= 0 or total <= 0 or feito / total < 0.05 or feito >= total:
        return None
    restante = gasto * (total - feito) / feito
    if restante < 60:
        return "menos de 1 min"
    return f"~{round(restante / 60)} min"


def _cuda_available() -> bool:
    try:
        import ctranslate2
        return any("cuda" in device.lower() for device in ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        return False
