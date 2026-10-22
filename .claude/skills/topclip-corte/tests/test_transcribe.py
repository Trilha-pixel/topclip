from __future__ import annotations

import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from scripts import transcribe as T
from scripts.validation import validate_json_data


def _fake_faster_whisper(texto: str = " Olá mundo.") -> types.ModuleType:
    """faster_whisper de mentira: 2 segmentos, 4 palavras, sem baixar modelo."""
    Palavra = types.SimpleNamespace

    class WhisperModel:
        def __init__(self, *_, **__):
            pass

        def transcribe(self, *_, **__):
            segs = [
                types.SimpleNamespace(start=0.0, end=1.2, text=texto, words=[
                    Palavra(word=" Olá", start=0.0, end=0.5, probability=0.9),
                    Palavra(word=" mundo.", start=0.5, end=1.2, probability=0.8),
                ]),
                types.SimpleNamespace(start=1.5, end=2.6, text=" Tudo bem?", words=[
                    Palavra(word=" Tudo", start=1.5, end=1.9, probability=0.95),
                    Palavra(word=" bem?", start=1.9, end=2.6, probability=None),
                ]),
            ]
            return iter(segs), types.SimpleNamespace(language="pt", language_probability=0.99, duration=3.0)

    mod = types.ModuleType("faster_whisper")
    mod.WhisperModel = WhisperModel
    return mod


def _fake_mlx_whisper(chamadas: list | None = None, falha: Exception | None = None) -> dict[str, types.ModuleType]:
    """mlx_whisper de mentira, com a barra tqdm que o contador de progresso troca."""
    pacote = types.ModuleType("mlx_whisper")
    modulo_transcribe = types.ModuleType("mlx_whisper.transcribe")
    audio = types.ModuleType("mlx_whisper.audio")
    audio.FRAMES_PER_SECOND = 100
    modulo_transcribe.tqdm = types.SimpleNamespace(tqdm=None)   # o original, que precisa voltar

    def transcribe(_audio, **kwargs):
        if chamadas is not None:
            chamadas.append(kwargs)
        if falha:
            raise falha
        barra = modulo_transcribe.tqdm.tqdm
        if barra is not None:
            with barra(total=30000, unit="frames", disable=True) as pbar:
                for _ in range(10):
                    pbar.update(3000)
        return {
            "language": "pt",
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.2, "text": " Olá mundo.", "words": [
                    {"word": " Olá", "start": 0.0, "end": 0.5, "probability": 1.0000001},
                    {"word": " mundo.", "start": 0.5, "end": 1.2, "probability": 0.8},
                ]},
                {"id": 1, "start": 1.2, "end": 1.2, "text": "", "words": []},   # descartado pelo mlx
                {"id": 2, "start": 1.5, "end": 2.6, "text": " Tudo bem?", "words": [
                    {"word": " Tudo", "start": 1.5, "end": 1.9, "probability": 0.95},
                    {"word": " bem?", "start": 1.9, "end": 2.6, "probability": 0.7},
                ]},
            ],
        }

    pacote.transcribe = transcribe   # como no pacote real: o nome do submódulo fica sombreado
    return {"mlx_whisper": pacote, "mlx_whisper.transcribe": modulo_transcribe, "mlx_whisper.audio": audio}


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class SemRuido(unittest.TestCase):
    """O progresso também vai para o stderr; nos testes, ele fica calado."""

    def setUp(self):
        stderr = mock.patch("sys.stderr", new_callable=io.StringIO)
        stderr.start()
        self.addCleanup(stderr.stop)


class EscolhaDoBackend(unittest.TestCase):
    def test_auto_usa_mlx_so_quando_disponivel(self):
        with mock.patch.object(T, "mlx_disponivel", return_value=True):
            self.assertEqual(T.escolher_backend("auto", "small"), "mlx-whisper")
            self.assertEqual(T.escolher_backend("auto", "large-v3-turbo"), "mlx-whisper")
            # device fixado ou modelo sem versão MLX: faster-whisper
            self.assertEqual(T.escolher_backend("auto", "small", "cpu"), "faster-whisper")
            self.assertEqual(T.escolher_backend("auto", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"), "faster-whisper")
            self.assertEqual(T.escolher_backend("auto", "mlx-community/whisper-small-mlx-q4"), "mlx-whisper")
        with mock.patch.object(T, "mlx_disponivel", return_value=False):
            self.assertEqual(T.escolher_backend("auto", "small"), "faster-whisper")

    def test_backend_explicito_e_invalido(self):
        self.assertEqual(T.escolher_backend("faster-whisper", "small"), "faster-whisper")
        self.assertEqual(T.escolher_backend("mlx-whisper", "small"), "mlx-whisper")
        with self.assertRaises(T.HarnessError):
            T.escolher_backend("whisperx", "small")


class MesmoSchemaNosDoisBackends(SemRuido):
    def _rodar(self, backend: str, modulos: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.dict(sys.modules, modulos), \
                mock.patch.object(T, "apple_silicon", return_value=True), \
                mock.patch.object(T, "mlx_disponivel", return_value=True):
            saida = Path(temp) / "02-transcript.json"
            T.transcribe(Path(temp) / "video.mp4", saida, backend=backend)
            return json.loads(saida.read_text(encoding="utf-8"))

    def test_mlx_e_faster_whisper_gravam_o_mesmo_formato(self):
        fw = self._rodar("faster-whisper", {"faster_whisper": _fake_faster_whisper()})
        mlx = self._rodar("mlx-whisper", _fake_mlx_whisper())
        self.assertEqual(validate_json_data(fw, "transcript.schema.json"), [])
        self.assertEqual(validate_json_data(mlx, "transcript.schema.json"), [])
        self.assertEqual(set(fw), set(mlx))
        self.assertEqual([set(s) for s in fw["segments"]], [set(s) for s in mlx["segments"]])
        self.assertEqual([set(w) for s in fw["segments"] for w in s["words"]],
                         [set(w) for s in mlx["segments"] for w in s["words"]])
        self.assertEqual((fw["backend"], mlx["backend"]), ("faster-whisper", "mlx-whisper"))
        # o segmento vazio que o mlx descarta sai, e os ids continuam seguidos
        self.assertEqual([s["id"] for s in mlx["segments"]], [0, 1])
        self.assertEqual([w["word"] for w in mlx["segments"][0]["words"]], ["Olá", "mundo."])
        self.assertEqual(mlx["segments"][0]["words"][0]["probability"], 1.0)   # fp16 1.0000001 -> 1.0
        self.assertEqual(mlx["duration_seconds"], 2.6)

    def test_auto_cai_no_faster_whisper_quando_o_mlx_falha(self):
        chamadas: list = []
        modulos = {**_fake_mlx_whisper(chamadas, falha=RuntimeError("Metal indisponível")),
                   "faster_whisper": _fake_faster_whisper()}
        out = self._rodar("auto", modulos)
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(out["backend"], "faster-whisper")
        with self.assertRaises(RuntimeError):   # pedido explícito de mlx não esconde a falha
            self._rodar("mlx-whisper", modulos)

    def test_mlx_recebe_repo_mlx_e_timestamps_por_palavra(self):
        chamadas: list = []
        self._rodar("mlx-whisper", _fake_mlx_whisper(chamadas))
        self.assertEqual(chamadas[0]["path_or_hf_repo"], "mlx-community/whisper-small-mlx")
        self.assertTrue(chamadas[0]["word_timestamps"])
        self.assertEqual(chamadas[0]["language"], "pt")


class ProgressoNoPainel(SemRuido):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.proj = Path(self.temp.name) / "projetos" / "teste"
        self.proj.mkdir(parents=True)
        self.relogio = Relogio()
        self.prog = T.ProgressoTranscricao(None, intervalo_s=15, relogio=self.relogio)
        self.prog.projeto = self.proj

    def tearDown(self):
        self.temp.cleanup()

    def _diario(self) -> list[dict]:
        p = self.proj / "atividade.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def test_anuncia_algumas_vezes_por_minuto_nao_a_cada_segmento(self):
        self.assertIsNotNone(self.prog.atividade, "painel/atividade.py deveria carregar")
        self.prog.comecar("mlx-whisper", "small")
        for i in range(1, 121):          # 2 min de relógio, um segmento por segundo
            self.relogio.t = float(i)
            self.prog(i * 10.0, 1200.0)
        progresso = [e for e in self._diario() if e["tipo"] == "progresso"]
        self.assertEqual(len(progresso), 8)       # a cada 15 s
        primeiro, ultimo = progresso[0], progresso[-1]
        self.assertEqual((primeiro["segundo"], primeiro["duracao"], primeiro["pct"]), (150.0, 1200.0, 12))
        self.assertEqual(primeiro["msg"], "transcrevendo: 02:30 de 20:00 (12%) · faltam ~2 min")
        self.assertEqual(ultimo["pct"], 100)
        self.assertNotIn("faltam", ultimo["msg"])

    def test_comeco_e_fim_vao_para_o_diario(self):
        self.prog.comecar("faster-whisper", "small")
        self.relogio.t = 125.0
        self.prog.terminar(2163.0)
        msgs = [e["msg"] for e in self._diario()]
        self.assertIn("faster-whisper, modelo small, no processador", msgs[0])
        self.assertEqual(msgs[-1], "transcrição pronta: 36:03 de áudio em 2min 05s (faster-whisper)")

    def test_contador_mlx_troca_a_barra_e_devolve_a_original(self):
        recebidos = []
        modulos = _fake_mlx_whisper()
        with mock.patch.dict(sys.modules, modulos):
            original = modulos["mlx_whisper.transcribe"].tqdm
            with T._ContadorMlx(lambda s, d: recebidos.append((s, d))):
                modulos["mlx_whisper"].transcribe("x")
            self.assertIs(modulos["mlx_whisper.transcribe"].tqdm, original)
        self.assertEqual(recebidos[0], (30.0, 300.0))
        self.assertEqual(recebidos[-1], (300.0, 300.0))

    def test_sem_projeto_nao_escreve_nada(self):
        prog = T.ProgressoTranscricao(Path(self.temp.name) / "fora" / "02-transcript.json", relogio=self.relogio)
        self.assertIsNone(prog.projeto)
        prog.comecar("mlx-whisper", "small")
        self.relogio.t = 30.0
        prog(10.0, 100.0)
        self.assertEqual(self._diario(), [])


if __name__ == "__main__":
    unittest.main()
