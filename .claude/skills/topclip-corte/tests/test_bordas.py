"""`bordas`: a borda vai para o vale de energia sem atravessar palavra.

O áudio é sintético e reproduz os dois casos da run real de docs/12: o Whisper
cola "Mas|você" no meio da cauda do "Mas", e estica "fazer" por cima da pausa.
"""
from __future__ import annotations

import array
import contextlib
import io
import json
import math
import random
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from scripts.bordas import PADRAO, FonteAudio, ajustar_bordas_run, ajustar_segmentos, decidir, envelope, vao_entre_palavras
from scripts.vch import main as vch_main

SR = 16000
DURACAO = 12.0

# (início, fim, dB RMS no começo, dB RMS no fim) — tom de 220 Hz com rampa em dB
SONS = [
    (1.00, 1.40, -20, -20),   # "Mas"
    (1.40, 1.52, -25, -60),   # cauda do "Mas", que o Whisper deu ao "você"
    (1.95, 2.40, -20, -20),   # "você"
    (3.00, 3.50, -20, -20),   # "fazer"
    (3.50, 3.58, -25, -60),   # cauda do "fazer"
    (3.95, 4.50, -20, -20),   # "então"
    (5.00, 6.00, -20, -20),   # "colado" + "sem" em fala contínua: nenhum vale
    (7.00, 7.40, -20, -20),   # "um"
    (7.40, 7.50, -45, -45),   # respiração: vale de -45 dB, sem silêncio claro
    (7.50, 8.00, -20, -20),   # "dois"
    (8.40, 8.80, -20, -20),   # "de"
    (9.00, 9.06, -20, -20),   # "t" de "tomar"
    (9.11, 9.30, -20, -20),   # "omar": a oclusiva deixa 50 ms de silêncio dentro da palavra
    (9.60, 9.90, -20, -20),   # "depois"
]

# Como o Whisper devolve: intervalos colados, um engolindo a pausa do outro.
PALAVRAS = [
    ("Mas", 1.00, 1.30), ("você", 1.30, 2.40),
    ("fazer", 3.00, 3.96), ("então", 3.96, 4.90),
    ("colado", 5.00, 5.50), ("sem", 5.50, 6.00),
    ("um", 7.00, 7.45), ("dois", 7.45, 8.00),
    ("de", 8.40, 8.80), ("tomar", 9.00, 9.30), ("depois", 9.60, 9.90),
]


def escrever_wav(path: Path) -> None:
    rng = random.Random(7)
    piso = 10 ** (-72 / 20) * math.sqrt(3)  # ruído uniforme com RMS de -72 dB
    amostras = [rng.uniform(-piso, piso) for _ in range(int(DURACAO * SR))]
    for ini, fim, db0, db1 in SONS:
        i0, i1 = int(ini * SR), int(fim * SR)
        for i in range(i0, i1):
            frac = (i - i0) / max(1, i1 - i0)
            amp = 10 ** ((db0 + (db1 - db0) * frac) / 20) * math.sqrt(2)
            amostras[i] += amp * math.sin(2 * math.pi * 220 * i / SR)
    dados = array.array("h", (max(-32768, min(32767, int(x * 32767))) for x in amostras))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(dados.tobytes())


def transcript() -> dict:
    return {
        "schema_version": "1.0",
        "segments": [{
            "id": 0, "start": 1.0, "end": 9.9, "text": " ".join(p[0] for p in PALAVRAS),
            "words": [{"word": w, "start": a, "end": b, "probability": 0.9} for w, a, b in PALAVRAS],
        }],
    }


def palavras() -> list[dict]:
    return [{"word": w, "start": a, "end": b} for w, a, b in PALAVRAS]


class AudioSintetico(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.wav = Path(cls._tmp.name) / "audio.wav"
        escrever_wav(cls.wav)
        cls.fonte = FonteAudio(cls.wav)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def decidir(self, t: float, lado: str):
        env = envelope(self.fonte, t - 1.2, t + 1.2)
        esq, dir_ = vao_entre_palavras(t, palavras(), env, PADRAO)
        return decidir(env, t, lado, esq, dir_, PADRAO), env


class DecisaoPorBorda(AudioSintetico):
    def test_inicio_na_cauda_da_palavra_anterior_vai_para_a_pausa(self) -> None:
        # Corte em 1,30 (fronteira do Whisper) pegava a cauda do "Mas".
        decisao, env = self.decidir(1.30, "start")
        self.assertEqual(decisao.acao, "moved")
        self.assertGreater(decisao.novo, 1.45)    # depois da cauda do "Mas"
        self.assertLess(decisao.novo, 1.95)       # antes do "você"
        self.assertLess(decisao.db_novo, PADRAO["silencio_db"])

    def test_fim_que_cortava_a_cauda_de_palavra_esticada(self) -> None:
        # "fazer" esticado pelo Whisper até 3,96: o meio do intervalo (3,48) mentiria.
        decisao, _ = self.decidir(3.47, "end")
        self.assertEqual(decisao.acao, "moved")
        self.assertGreaterEqual(decisao.novo, 3.52)
        self.assertLess(decisao.novo, 3.95)
        self.assertLess(decisao.db_novo, PADRAO["silencio_db"])

    def test_borda_em_silencio_claro_fica(self) -> None:
        decisao, _ = self.decidir(2.70, "end")
        self.assertEqual(decisao.acao, "kept_silence")
        self.assertEqual(decisao.novo, 2.70)

    def test_sem_vale_e_borda_fraca(self) -> None:
        decisao, _ = self.decidir(5.50, "end")
        self.assertEqual(decisao.acao, "weak")
        self.assertEqual(decisao.novo, 5.50)
        self.assertGreater(decisao.db_original, PADRAO["vale_db"])

    def test_vale_sem_silencio_claro_ainda_serve(self) -> None:
        decisao, _ = self.decidir(7.36, "end")
        self.assertEqual(decisao.acao, "moved")
        self.assertGreaterEqual(decisao.novo, 7.40)
        self.assertLessEqual(decisao.novo, 7.50)
        self.assertLess(decisao.db_novo, PADRAO["vale_db"])
        self.assertGreater(decisao.db_novo, PADRAO["silencio_db"])

    def test_nao_cai_no_silencio_dentro_da_palavra_mantida(self) -> None:
        # Início em 9,05, dentro do "t" de "tomar": o silêncio mais perto (9,07,
        # a oclusiva) fica DENTRO da palavra. Tem de sair pela esquerda.
        decisao, _ = self.decidir(9.05, "start")
        self.assertEqual(decisao.acao, "moved")
        self.assertLess(decisao.novo, 9.00)
        self.assertGreater(decisao.novo, 8.80)

    def test_nao_atravessa_palavra_curta_vizinha(self) -> None:
        # Fim em 8.95, antes de "tomar": nunca pode cair depois do começo dele.
        decisao, _ = self.decidir(8.95, "end")
        self.assertLessEqual(decisao.novo, 9.00)


class AjusteDeSegmentos(AudioSintetico):
    def test_emenda_interna_nao_e_mexida_e_vizinho_nao_e_invadido(self) -> None:
        segmentos = [
            {"order": 1, "source_start": 1.30, "source_end": 2.50},
            {"order": 2, "source_start": 2.50, "source_end": 3.47},  # emenda contínua com o 1
            {"order": 3, "source_start": 9.03, "source_end": 9.95},
        ]
        moveu, decisoes, avisos = ajustar_segmentos(segmentos, self.fonte, palavras(), dict(PADRAO))
        self.assertTrue(moveu)
        self.assertEqual(segmentos[0]["source_end"], 2.50)
        self.assertEqual(segmentos[1]["source_start"], 2.50)
        self.assertNotIn("end", segmentos[0]["edge_audio"])
        self.assertNotIn("start", segmentos[1]["edge_audio"])
        self.assertEqual(segmentos[0]["edge_audio"]["start"]["action"], "moved")
        self.assertEqual(segmentos[0]["edge_audio"]["start"]["from"], 1.30)
        self.assertEqual(avisos, [])
        # segunda passada reaproveita a medida: idempotente
        antes = json.dumps(segmentos, sort_keys=True)
        moveu2, decisoes2, _ = ajustar_segmentos(segmentos, self.fonte, palavras(), dict(PADRAO))
        self.assertFalse(moveu2)
        self.assertEqual(json.dumps(segmentos, sort_keys=True), antes)
        self.assertTrue(all(d.get("reaproveitada") for d in decisoes2))

    def test_borda_fraca_vira_aviso(self) -> None:
        segmentos = [{"order": 1, "source_start": 4.70, "source_end": 5.50}]
        _, _, avisos = ajustar_segmentos(segmentos, self.fonte, palavras(), dict(PADRAO))
        self.assertEqual(len(avisos), 1)
        self.assertTrue(avisos[0].startswith("borda_fraca: segmento 1, fim em 5.50s"))
        self.assertEqual(segmentos[0]["source_end"], 5.50)


def criar_run(raiz: Path, wav: Path | None, video: str = "") -> Path:
    run = raiz / "run"
    (run / "assets").mkdir(parents=True)
    (run / "iterations").mkdir()
    if wav:
        shutil.copy2(wav, run / "assets" / "audio-analysis.wav")
    (run / "00-manifest.json").write_text(json.dumps({
        "schema_version": "1.0", "run_id": "teste", "created_at": "2026-10-21T00:00:00-03:00",
        "mode": "full", "status": "prepared", "inputs": {"video_path": video, "platform": "cross-platform"},
        "stages": {},
    }), encoding="utf-8")
    (run / "02-transcript.json").write_text(json.dumps(transcript()), encoding="utf-8")
    return run


def candidatos() -> dict:
    return {"schema_version": "1.0", "clips": [{
        "id": "clip-001", "title": "t", "status": "APPROVED", "primary_context": "outro", "profile": "p",
        "scores": {}, "hard_fails": [], "warnings": ["aviso do Clip Builder"],
        "segments": [
            {"order": 1, "role": "hook", "source_start": 1.30, "source_end": 2.50},
            {"order": 2, "role": "payoff", "source_start": 2.80, "source_end": 3.47},
        ],
        "events": {"timebase": "final", "proposition_at": 0.5, "payoff_at": 1.5},
        "semantic_beats": [{"at": 1.3, "type": "payoff", "description": "fazer"}],
        "estimated_final_duration_seconds": 1.87,
    }]}


class BordasNaRun(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.wav = self.raiz / "fonte.wav"
        escrever_wav(self.wav)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_06_move_bordas_e_recalcula_eventos(self) -> None:
        run = criar_run(self.raiz, self.wav)
        (run / "06-candidates.json").write_text(json.dumps(candidatos()), encoding="utf-8")
        relatorio = ajustar_bordas_run(run)
        self.assertEqual(relatorio["arquivo"], "06-candidates.json")
        clip = json.loads((run / "06-candidates.json").read_text())["clips"][0]
        inicio, fim = clip["segments"][0]["source_start"], clip["segments"][1]["source_end"]
        self.assertGreater(inicio, 1.45)
        self.assertGreater(fim, 3.52)
        deslocamento = inicio - 1.30
        # eventos de clipe: a fala anda para trás o quanto o início avançou
        self.assertAlmostEqual(clip["events"]["proposition_at"], round(max(0.0, 0.5 - deslocamento), 2), places=2)
        duracao = (2.50 - inicio) + (fim - 2.80)
        self.assertAlmostEqual(clip["estimated_final_duration_seconds"], round(duracao, 2), places=2)
        self.assertIn("aviso do Clip Builder", clip["warnings"])
        self.assertTrue((run / "iterations" / "bordas-06.json").exists())

    def test_cli_escolhe_11_quando_existe(self) -> None:
        run = criar_run(self.raiz, self.wav)
        (run / "06-candidates.json").write_text(json.dumps(candidatos()), encoding="utf-8")
        plano = {"schema_version": "1.0", "plans": [{
            "clip_id": "clip-001", "output_slug": "s", "primary_context": "outro", "captions": {}, "audio": {},
            "timeline": [
                {"order": 1, "source_start": 1.30, "source_end": 2.50, "clip_start": 0.0, "clip_end": 1.2},
                {"order": 2, "source_start": 2.80, "source_end": 3.47, "clip_start": 1.2, "clip_end": 1.87},
            ],
            "cards": [{"id": "c1", "clip_start": 1.2, "clip_end": 1.87, "text": "fazer"}],
        }]}
        (run / "11-edit-plans.json").write_text(json.dumps(plano), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            codigo = vch_main(["bordas", "--run", str(run)])
        self.assertEqual(codigo, 0)
        novo = json.loads((run / "11-edit-plans.json").read_text())["plans"][0]
        tl = novo["timeline"]
        self.assertGreater(tl[0]["source_start"], 1.45)
        self.assertAlmostEqual(tl[0]["clip_end"], round(2.50 - tl[0]["source_start"], 3), places=3)
        self.assertAlmostEqual(tl[1]["clip_start"], tl[0]["clip_end"], places=3)
        # o card grudado nas bordas do segmento 2 acompanha as bordas novas
        self.assertAlmostEqual(novo["cards"][0]["clip_start"], round(tl[1]["clip_start"], 2), places=2)
        self.assertAlmostEqual(novo["cards"][0]["clip_end"], round(tl[1]["clip_end"], 2), places=2)
        # o 06 não foi tocado na fase 3
        self.assertEqual(json.loads((run / "06-candidates.json").read_text())["clips"][0]["segments"][0]["source_start"], 1.30)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg ausente")
    def test_sem_wav_de_analise_le_do_video_pelo_ffmpeg(self) -> None:
        video = self.raiz / "video.m4a"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(self.wav), "-c:a", "aac", "-b:a", "192k", str(video)],
            check=True,
        )
        run = criar_run(self.raiz, None, str(video))
        (run / "06-candidates.json").write_text(json.dumps(candidatos()), encoding="utf-8")
        ajustar_bordas_run(run, "06")
        seg = json.loads((run / "06-candidates.json").read_text())["clips"][0]["segments"][0]
        self.assertEqual(seg["edge_audio"]["start"]["action"], "moved")
        # o AAC some com parte da cauda baixa: basta sair do corpo do "Mas" e não chegar no "você"
        self.assertGreater(seg["source_start"], 1.40)
        self.assertLess(seg["source_start"], 1.95)


if __name__ == "__main__":
    unittest.main()
