"""Bordas de segmento no vale de energia do áudio.

O timing por palavra do Whisper erra 0,1–0,5 s em palavras coladas. Na run de
docs/12, o corte em 113,58 s (fim de "Mas" pelo Whisper) pegava o fim do "Mas",
que pela energia ia até 113,70 s; outro cortava a cauda de "fazer". Medir RMS
a 10 ms à mão e corrigir custou a cascata de checagens refeitas da fase 3.

Aqui a medida é do script. Para cada borda de segmento que é corte de verdade
(não a emenda interna de dois segmentos seguidos na fonte):

* borda já em silêncio claro (abaixo de `silencio_db`, -50 dB) fica;
* senão, vai para o silêncio claro mais próximo dentro de ±`janela_s` (0,15 s).
  Se o vale começa dentro da janela e continua descendo além dela, segue a
  descida até `janela_max_s` (0,30 s);
* sem silêncio claro, vai para o ponto mais baixo, se ele passar de `vale_db`
  (-40 dB);
* sem vale abaixo de -40 dB, não mexe e devolve `borda_fraca`.

Nunca atravessa palavra: a borda só cai no vão entre o corpo da palavra de
antes e o da palavra de depois (corpo = onde a palavra soa de fato, dentro do
intervalo que o Whisper deu — o intervalo de palavra colada engole a pausa e a
cauda da vizinha), cada palavra fica do lado em que está a maior parte dela, a
busca não sobe por cima de som mais alto que a borda (+`subida_db`) e não
invade o segmento vizinho. Nenhuma palavra entra ou sai do corte por causa dela.

Energia: RMS em janelas de 10 ms sobre PCM 16 kHz mono — o WAV de análise que o
`prepare` já gravou, ou ffmpeg direto do vídeo quando ele não existe.
"""
from __future__ import annotations

import array
import bisect
import copy
import math
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.tempos import GAP_CONTIGUO, ordenar, recalcular_plano, remapear_candidato
from scripts.utils import HarnessError, load_json, now_iso, which, write_json

SR = 16000
PISO_DB = -120.0
PADRAO = {
    "janela_s": 0.15,
    "janela_max_s": 0.30,
    "silencio_db": -50.0,
    "vale_db": -40.0,
    "subida_db": 6.0,
    "hop_s": 0.010,
}
# Folga de contexto em volta da borda: palavra esticada pelo Whisper chega a ~1 s.
CONTEXTO_S = 1.2
DURACAO_MINIMA = 0.2
FOLGA_VIZINHO = 0.02
LADOS = (("start", "source_start", "início"), ("end", "source_end", "fim"))


class FonteAudio:
    """PCM mono da run: o WAV de análise do `prepare` ou ffmpeg direto do vídeo."""

    def __init__(self, wav: Path | None = None, video: str | None = None):
        self.wav = wav if wav and Path(wav).exists() else None
        self.video = video or None
        if not self.wav and not self.video:
            raise HarnessError("Sem áudio para medir as bordas: a run não tem vídeo nem assets/audio-analysis.wav.")

    def ler(self, ini: float, fim: float) -> tuple[float, int, list[float]]:
        """(instante da primeira amostra, taxa, amostras em -1..1)."""
        ini = max(0.0, ini)
        if fim <= ini:
            return ini, SR, []
        if self.wav:
            lido = self._ler_wav(ini, fim)
            if lido is not None:
                return lido
        if not self.video:
            return ini, SR, []
        return self._ler_ffmpeg(ini, fim)

    def _ler_wav(self, ini: float, fim: float) -> tuple[float, int, list[float]] | None:
        with wave.open(str(self.wav), "rb") as wf:
            if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
                return None
            taxa = wf.getframerate()
            total = wf.getnframes()
            i0 = min(total, int(ini * taxa))
            i1 = min(total, int(math.ceil(fim * taxa)))
            wf.setpos(i0)
            bruto = wf.readframes(i1 - i0)
        amostras = array.array("h")
        amostras.frombytes(bruto)
        if sys.byteorder == "big":
            amostras.byteswap()
        return i0 / taxa, taxa, [x / 32768.0 for x in amostras]

    def _ler_ffmpeg(self, ini: float, fim: float) -> tuple[float, int, list[float]]:
        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            raise HarnessError("FFmpeg não encontrado (preciso dele para medir as bordas sem o WAV de análise).")
        comando = [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(self.video),
            "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-",
        ]
        resultado = subprocess.run(comando, capture_output=True, check=False)
        if resultado.returncode != 0:
            detalhe = resultado.stderr.decode("utf-8", "replace").strip()
            raise HarnessError(f"ffmpeg não leu o áudio em {ini:.2f}–{fim:.2f}s: {detalhe}")
        amostras = array.array("h")
        amostras.frombytes(resultado.stdout[: len(resultado.stdout) // 2 * 2])
        if sys.byteorder == "big":
            amostras.byteswap()
        return ini, SR, [x / 32768.0 for x in amostras]


@dataclass
class Envelope:
    centros: list[float]
    db: list[float]

    def indice(self, t: float) -> int:
        i = bisect.bisect_left(self.centros, t)
        if i <= 0:
            return 0
        if i >= len(self.centros):
            return len(self.centros) - 1
        return i if self.centros[i] - t < t - self.centros[i - 1] else i - 1


def envelope(fonte: FonteAudio, ini: float, fim: float, hop: float = 0.010) -> Envelope:
    """RMS em dBFS, janelas de `hop` centradas em múltiplos de `hop` (borda nova cai no centésimo)."""
    t0, taxa, amostras = fonte.ler(ini - hop, fim + hop)
    centros, valores = [], []
    meio = hop / 2
    for k in range(math.ceil(max(0.0, ini) / hop), math.floor(fim / hop) + 1):
        c = k * hop
        i0 = max(0, int(round((c - meio - t0) * taxa)))
        i1 = min(len(amostras), int(round((c + meio - t0) * taxa)))
        if i1 <= i0:
            continue
        energia = sum(x * x for x in amostras[i0:i1]) / (i1 - i0)
        rms = math.sqrt(energia)
        centros.append(round(c, 6))
        valores.append(max(PISO_DB, 20 * math.log10(rms)) if rms > 0 else PISO_DB)
    return Envelope(centros, valores)


def carregar_palavras(transcript_path: Path) -> list[dict[str, float]]:
    if not transcript_path.exists():
        return []
    dados = load_json(transcript_path)
    palavras = []
    for seg in dados.get("segments", []):
        for w in seg.get("words") or []:
            try:
                a, b = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if b > a:
                palavras.append({"start": a, "end": b, "word": str(w.get("word", "")).strip()})
    palavras.sort(key=lambda w: w["start"])
    return palavras


def _blocos_de_som(env: Envelope, a: float, b: float, limiar: float) -> list[list[float]]:
    blocos: list[list[float]] = []
    for c, db in zip(env.centros, env.db):
        if c < a or c > b or db < limiar:
            continue
        if blocos and c - blocos[-1][1] <= 0.05:
            blocos[-1][1] = c
        else:
            blocos.append([c, c])
    return blocos


def _tem_som_em(env: Envelope, t: float, limiar: float) -> bool:
    return bool(env.centros) and env.db[env.indice(t)] >= limiar


def _aparar(env: Envelope, bloco: list[float], limiar: float, para_frente: bool) -> list[float] | None:
    """Tira de um bloco a cauda da vizinha que entrou nele: anda descendo a partir
    da beira até o mergulho; se o mergulho fica abaixo do limiar, o bloco começa
    (ou termina) depois dele. None se o bloco inteiro era da vizinha."""
    idx = [i for i, c in enumerate(env.centros) if bloco[0] - 1e-9 <= c <= bloco[1] + 1e-9]
    if not para_frente:
        idx.reverse()
    k = 0
    while k + 1 < len(idx) and env.db[idx[k + 1]] <= env.db[idx[k]] + 1.0:
        k += 1
    if env.db[idx[k]] >= limiar:
        return bloco  # não há mergulho de verdade: o bloco é da própria palavra
    resto = [i for i in idx[k + 1:] if env.db[i] >= limiar]
    if not resto:
        return None
    novo = env.centros[resto[0]]
    return [novo, bloco[1]] if para_frente else [bloco[0], novo]


def corpo(palavra: dict[str, float], env: Envelope, limiar: float) -> tuple[float, float]:
    """Onde a palavra soa de fato, dentro do intervalo que o Whisper deu.

    Em palavra colada o intervalo engole a pausa e a cauda da vizinha: o "você"
    de 113,58–114,34 s começava com o fim do "Mas" e só soava a partir de 114,17.
    Quando há som logo antes do intervalo, o primeiro bloco é (ao menos em parte)
    da vizinha: sai inteiro se houver outro bloco; se for o único, perde o
    trecho até o primeiro mergulho. O mesmo no fim, com som logo depois.
    """
    a, b = palavra["start"], palavra["end"]
    blocos = _blocos_de_som(env, a, b, limiar)
    if not blocos:
        return a, b
    hop = env.centros[1] - env.centros[0] if len(env.centros) > 1 else 0.01
    if blocos[0][0] - a <= hop and _tem_som_em(env, a - hop, limiar):
        if len(blocos) > 1:
            blocos = blocos[1:]
        else:
            aparado = _aparar(env, blocos[0], limiar, para_frente=True)
            blocos = [aparado] if aparado else blocos
    if b - blocos[-1][1] <= hop and _tem_som_em(env, b + hop, limiar):
        if len(blocos) > 1:
            blocos = blocos[:-1]
        else:
            aparado = _aparar(env, blocos[-1], limiar, para_frente=False)
            blocos = [aparado] if aparado else blocos
    return blocos[0][0], blocos[-1][1]


def vao_entre_palavras(t: float, palavras: list[dict[str, float]], env: Envelope, cfg: dict[str, float]) -> tuple[float, float]:
    """Onde a borda pode cair: no vão entre o corpo da palavra de antes e o da de depois.

    Cada palavra fica do lado em que está a maior parte dela (meio do corpo). Se
    a borda está dentro de um corpo, o vão fica fora dela e a busca tem de sair
    da palavra — para o lado que a mantém onde já estava.
    """
    esq, dir_ = -math.inf, math.inf
    for w in palavras:
        if w["end"] <= t - CONTEXTO_S or w["start"] >= t + CONTEXTO_S:
            continue
        a, b = corpo(w, env, cfg["vale_db"])
        if (a + b) / 2 <= t:
            esq = max(esq, b)
        else:
            dir_ = min(dir_, a)
    return esq, dir_


def guardas_de_vizinhos(seg: dict[str, Any], lado: str, segmentos: list[dict[str, Any]]) -> tuple[float, float]:
    """Não invade outro segmento do mesmo clipe nem deixa o próprio com menos de 0,2 s."""
    a, b = float(seg["source_start"]), float(seg["source_end"])
    if lado == "start":
        esq = max([float(o["source_end"]) + FOLGA_VIZINHO for o in segmentos
                   if o is not seg and a - 1.0 < float(o["source_end"]) <= a + 1e-6] or [-math.inf])
        return esq, b - DURACAO_MINIMA
    dir_ = min([float(o["source_start"]) - FOLGA_VIZINHO for o in segmentos
                if o is not seg and b - 1e-6 <= float(o["source_start"]) < b + 1.0] or [math.inf])
    return a + DURACAO_MINIMA, dir_


@dataclass
class Decisao:
    lado: str
    original: float
    novo: float
    db_original: float
    db_novo: float
    acao: str  # kept_silence | moved | kept_valley | weak | no_audio
    melhor: float | None = None
    melhor_db: float | None = None

    def registro(self) -> dict[str, Any]:
        dados: dict[str, Any] = {"t": round(self.novo, 3), "db": round(self.db_novo, 1), "action": self.acao}
        if self.acao == "moved":
            dados["from"] = round(self.original, 3)
            dados["from_db"] = round(self.db_original, 1)
        if self.acao == "weak" and self.melhor is not None:
            dados["best"] = round(self.melhor, 3)
            dados["best_db"] = round(self.melhor_db or PISO_DB, 1)
        return dados


def decidir(env: Envelope, t: float, lado: str, esq: float, dir_: float, cfg: dict[str, float]) -> Decisao:
    """Onde a borda fica. `esq`/`dir_`: a faixa onde ela pode cair (vão entre palavras e vizinhos)."""
    if not env.centros:
        return Decisao(lado, t, t, PISO_DB, PISO_DB, "no_audio")
    db, centros = env.db, env.centros
    e = env.indice(t)
    db_e = db[e]
    if db_e < cfg["silencio_db"]:
        return Decisao(lado, t, t, db_e, db_e, "kept_silence")

    eps = 1e-6
    lo, hi = t - cfg["janela_s"], t + cfg["janela_s"]
    lo_max, hi_max = t - cfg["janela_max_s"], t + cfg["janela_max_s"]
    teto = db_e + cfg["subida_db"]
    visitados = [e]
    for passo in (1, -1):
        i = e
        while 0 <= i + passo < len(centros):
            j = i + passo
            c = centros[j]
            if db[j] > teto:
                break  # som mais alto que a própria borda: não atravessa
            if not (lo - eps <= c <= hi + eps):
                # fora da janela: só segue um vale que já vinha descendo
                if not (lo_max - eps <= c <= hi_max + eps):
                    break
                if db[i] < cfg["silencio_db"] or db[j] > db[i] + 1.0:
                    break
            visitados.append(j)
            i = j
    candidatos = [j for j in visitados if esq - eps <= centros[j] <= dir_ + eps]
    if not candidatos:
        return Decisao(lado, t, t, db_e, db_e, "weak")

    no_vao = esq - eps <= t <= dir_ + eps
    ja_no_vale = no_vao and db_e <= cfg["vale_db"]
    perto = cfg["hop_s"] + eps  # uma janela de 10 ms: mexer tão pouco não muda nada audível
    silenciosos = [j for j in candidatos if db[j] < cfg["silencio_db"]]
    if silenciosos:
        j = min(silenciosos, key=lambda k: (abs(centros[k] - t), db[k]))
        if ja_no_vale and abs(centros[j] - t) <= perto:
            return Decisao(lado, t, t, db_e, db_e, "kept_valley")
        return Decisao(lado, t, centros[j], db_e, db[j], "moved")
    j_min = min(candidatos, key=lambda k: (db[k], abs(centros[k] - t)))
    if ja_no_vale:
        minimo_local = db_e <= min(db[max(0, e - 3): e + 4]) + 0.5
        if minimo_local or db_e <= db[j_min] + 1.0 or abs(centros[j_min] - t) <= perto:
            return Decisao(lado, t, t, db_e, db_e, "kept_valley")
        return Decisao(lado, t, centros[j_min], db_e, db[j_min], "moved")
    if db[j_min] < cfg["vale_db"]:
        return Decisao(lado, t, centros[j_min], db_e, db[j_min], "moved")
    return Decisao(lado, t, t, db_e, db_e, "weak", centros[j_min], db[j_min])


def _aviso_fraca(ordem: Any, rotulo: str, reg: dict[str, Any], cfg: dict[str, float]) -> str:
    melhor = ""
    if reg.get("best") is not None:
        melhor = f" (melhor ponto: {float(reg['best']):.2f}s a {float(reg['best_db']):.1f} dB)"
    return (
        f"borda_fraca: segmento {ordem}, {rotulo} em {float(reg['t']):.2f}s está em som "
        f"({float(reg['db']):.1f} dB) e não há vale abaixo de {cfg['vale_db']:.0f} dB em "
        f"±{cfg['janela_s']:.2f}s{melhor} — conferir no ouvido ou mover a borda para uma pausa real"
    )


def ajustar_segmentos(
    segmentos: list[dict[str, Any]],
    fonte: FonteAudio,
    palavras: list[dict[str, float]],
    cfg: dict[str, float],
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """Ajusta in loco as bordas de corte de uma lista de segmentos (06 ou 11)."""
    ordem = ordenar(segmentos)
    moveu = False
    decisoes: list[dict[str, Any]] = []
    avisos: list[str] = []
    for i, seg in enumerate(ordem):
        for lado, chave, rotulo in LADOS:
            t = float(seg[chave])
            if lado == "start" and i > 0 and abs(t - float(ordem[i - 1]["source_end"])) < GAP_CONTIGUO:
                continue  # emenda interna, não é corte
            if lado == "end" and i < len(ordem) - 1 and abs(float(ordem[i + 1]["source_start"]) - t) < GAP_CONTIGUO:
                continue
            numero = seg.get("order", i + 1)
            anterior = (seg.get("edge_audio") or {}).get(lado)
            if isinstance(anterior, dict) and abs(float(anterior.get("t", -1)) - t) < 0.0005:
                # já medida nesta posição: reaproveita, e a run fica idempotente
                if anterior.get("action") == "weak":
                    avisos.append(_aviso_fraca(numero, rotulo, anterior, cfg))
                decisoes.append({"segmento": numero, "lado": lado, **anterior, "reaproveitada": True})
                continue
            env = envelope(fonte, t - CONTEXTO_S, t + CONTEXTO_S, cfg["hop_s"])
            pe, pd = vao_entre_palavras(t, palavras, env, cfg)
            ve, vd = guardas_de_vizinhos(seg, lado, ordem)
            decisao = decidir(env, t, lado, max(pe, ve), min(pd, vd), cfg)
            registro = decisao.registro()
            if decisao.acao == "moved":
                seg[chave] = round(decisao.novo, 3)
                moveu = True
            seg.setdefault("edge_audio", {})[lado] = registro
            if decisao.acao == "weak":
                avisos.append(_aviso_fraca(numero, rotulo, registro, cfg))
            decisoes.append({"segmento": numero, "lado": lado, **registro})
    return moveu, decisoes, avisos


def _trocar_avisos(dono: dict[str, Any], avisos: list[str]) -> None:
    mantidos = [w for w in dono.get("warnings", []) if not str(w).startswith("borda_fraca")]
    if avisos or "warnings" in dono:
        dono["warnings"] = mantidos + avisos


def ajustar_bordas_run(run: Path, arquivo: str = "auto", cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """`./topclip corte bordas`: 06 depois do Clip Builder, 11 depois do Edit Director."""
    cfg = {**PADRAO, **(cfg or {})}
    cfg = {k: float(v) for k, v in cfg.items()}
    alvo = arquivo
    if alvo == "auto":
        alvo = "11" if (run / "11-edit-plans.json").exists() else "06"
    nome = {"06": "06-candidates.json", "11": "11-edit-plans.json"}.get(alvo)
    if not nome:
        raise HarnessError(f"--arquivo deve ser 06, 11 ou auto (veio {arquivo!r})")
    caminho = run / nome
    if not caminho.exists():
        raise HarnessError(f"{nome} não encontrado: rode o {'Clip Builder' if alvo == '06' else 'Edit Director'} antes.")
    manifest = load_json(run / "00-manifest.json")
    fonte = FonteAudio(run / "assets" / "audio-analysis.wav", manifest.get("inputs", {}).get("video_path"))
    palavras = carregar_palavras(run / "02-transcript.json")
    doc = load_json(caminho)
    original = copy.deepcopy(doc)
    clipes = []
    if alvo == "06":
        for clip in doc.get("clips", []):
            antigos = copy.deepcopy(clip.get("segments") or [])
            moveu, decisoes, avisos = ajustar_segmentos(clip.get("segments") or [], fonte, palavras, cfg)
            tempos = remapear_candidato(clip, antigos) if moveu else {"mudou": False}
            _trocar_avisos(clip, avisos)
            clipes.append(_resumo(str(clip.get("id")), decisoes, avisos, tempos))
    else:
        for plan in doc.get("plans", []):
            recalcular_plano(plan, origem="bordas")  # absorve borda editada à mão antes de medir
            antigos = copy.deepcopy(plan.get("timeline") or [])
            moveu, decisoes, avisos = ajustar_segmentos(plan.get("timeline") or [], fonte, palavras, cfg)
            tempos = recalcular_plano(plan, antigos, origem="bordas") if moveu else {"mudou": False}
            _trocar_avisos(plan, avisos)
            clipes.append(_resumo(str(plan.get("clip_id")), decisoes, avisos, tempos))
    gravou = doc != original
    if gravou:
        write_json(caminho, doc)
    relatorio = {
        "schema_version": "1.0",
        "gerado_em": now_iso(),
        "arquivo": nome,
        "gravou": gravou,
        "parametros": cfg,
        "clipes": clipes,
    }
    write_json(run / "iterations" / f"bordas-{alvo}.json", relatorio)
    return relatorio


def _resumo(clip_id: str, decisoes: list[dict[str, Any]], avisos: list[str], tempos: dict[str, Any]) -> dict[str, Any]:
    contagem: dict[str, int] = {}
    for d in decisoes:
        contagem[d["action"]] = contagem.get(d["action"], 0) + 1
    resumo: dict[str, Any] = {
        "clip_id": clip_id,
        "bordas": contagem,
        "movidas": [
            {"segmento": d["segmento"], "lado": d["lado"], "de": d["from"], "para": d["t"],
             "db_de": d["from_db"], "db_para": d["db"]}
            for d in decisoes if d["action"] == "moved" and not d.get("reaproveitada")
        ],
        "borda_fraca": avisos,
        "decisoes": decisoes,
    }
    if tempos.get("mudou"):
        resumo["duracao"] = {"antes": tempos.get("duracao_antiga"), "depois": tempos.get("duracao_nova")}
    return resumo
