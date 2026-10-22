from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.previa import comando, nome_da_previa, segmentos_da_previa
from scripts.publicabilidade import abaixo_do_gate, estimar_cortes, estimar_momentos, nota
from scripts.reports import consolidate_final
from scripts.vch import config, main

SCORES = {
    "orientation": 7, "hook": 8, "proposition_clarity": 8, "first_value_speed": 9,
    "context_efficiency": 8, "stakes": 7, "curiosity_integrity": 8, "progression": 8,
    "payoff": 8, "closure": 8, "self_contained": 6, "shareability": 8,
    "visual_opportunity": 5, "novelty": 6, "editability": 6, "truthfulness": 9,
}


def _manifest(run: Path, video: str = "") -> None:
    (run / "00-manifest.json").write_text(json.dumps({
        "schema_version": "1.0", "run_id": "t", "created_at": "2026-10-21T00:00:00-03:00",
        "mode": "full", "status": "initialized", "inputs": {"platform": "cross-platform", "video_path": video},
        "stages": {},
    }), encoding="utf-8")


def _vch(*args: str) -> int:
    """Roda o vch sem sujar a saída dos testes."""
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return main(list(args))


class NotaTests(unittest.TestCase):
    def test_mesma_conta_do_finalize(self) -> None:
        """A nota antecipada e a do finalize não podem se separar."""
        feed = {"self_contained": 8, "hook": 7}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            _manifest(run)
            (run / "06-candidates.json").write_text(json.dumps({"schema_version": "1.0", "clips": [
                {"id": "clip-001", "title": "t", "status": "REBUILD", "primary_context": "dinheiro",
                 "profile": "money", "segments": [], "scores": SCORES, "hard_fails": []}]}))
            (run / "07-feed-review.json").write_text(json.dumps({"reviews": [
                {"clip_id": "clip-001", "status": "PASS", "scores": feed}]}))
            cfg = config(run)
            final, rejeitados = consolidate_final(run, cfg)
            do_finalize = (final["clips"] + rejeitados["clips"])[0]["publishability_score"]

            candidatos = json.loads((run / "06-candidates.json").read_text())
            estimar_cortes(candidatos, json.loads((run / "07-feed-review.json").read_text()), cfg)
            self.assertEqual(candidatos["clips"][0]["publishability_estimate"], do_finalize)
            self.assertEqual(nota({**SCORES, **feed}, cfg["scoring_weights"]), do_finalize)

    def test_gate_explica_o_motivo(self) -> None:
        selecao = {"minimum_publishability_score": 7.5, "minimum_critical_score": 7.0, "truthfulness_gate": 9.0}
        self.assertEqual(abaixo_do_gate({**SCORES, "self_contained": 8}, 7.8, selecao), [])
        motivos = abaixo_do_gate(SCORES, 7.483, selecao)
        self.assertIn("se sustenta sozinho 6 < 7", motivos)
        self.assertIn("nota 7,48 < 7,5", motivos)          # 2 casas: "7,5 < 7,5" não explicaria nada
        # fidelidade baixa aparece uma vez só, mesmo sendo também o pior item crítico
        self.assertEqual(abaixo_do_gate({**SCORES, "self_contained": 8, "truthfulness": 6}, 8.0, selecao),
                         ["fidelidade 6 < 9"])

    def test_momento_sem_nota_completa_fica_sem_estimativa(self) -> None:
        cfg = config()
        incompleto = {k: v for k, v in SCORES.items() if k != "truthfulness"}
        doc = {"moments": [{"id": "moment-001", "estimated_scores": SCORES},
                           {"id": "moment-002", "estimated_scores": incompleto},
                           {"id": "moment-003"}]}
        faltando = estimar_momentos(doc, cfg)
        self.assertEqual(set(faltando), {"moment-002", "moment-003"})
        self.assertEqual(faltando["moment-002"], ["truthfulness"])
        self.assertIn("publishability_estimate", doc["moments"][0])
        self.assertNotIn("publishability_estimate", doc["moments"][1])
        self.assertEqual(doc["estimate_gate"], 7.5)


class EstimateCommandTests(unittest.TestCase):
    def test_estimate_grava_e_cobra_o_que_falta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            _manifest(run)
            momentos = run / "05-viral-moments.json"
            base = {"start": 10, "end": 60, "quote": "q", "trigger": "t", "profile": "money",
                    "context_needed": "c", "payoff_candidate": "p"}
            momentos.write_text(json.dumps({"schema_version": "1.0", "moments": [
                {**base, "id": "moment-001", "estimated_scores": SCORES},
                {**base, "id": "moment-002", "estimated_scores": {**SCORES, "self_contained": 9, "hook": 9}}]}))
            self.assertEqual(_vch("estimate", "--run", tmp), 0)
            doc = json.loads(momentos.read_text())
            self.assertGreater(doc["moments"][1]["publishability_estimate"], doc["moments"][0]["publishability_estimate"])
            self.assertEqual(doc["moments"][1]["estimate_below_gate"], [])

            doc["moments"].append({**base, "id": "moment-003"})                 # sem estimated_scores
            momentos.write_text(json.dumps(doc))
            self.assertEqual(_vch("estimate", "--run", tmp), 3)

            doc["moments"][2] = {"id": "moment-003", "estimated_scores": SCORES}  # fora do schema
            momentos.write_text(json.dumps(doc))
            self.assertEqual(_vch("estimate", "--run", tmp), 3)


class PreviaTests(unittest.TestCase):
    CLIP = {"id": "clip-007", "title": "Quanto mais barato você vende, piores são os clientes", "segments": [
        {"source_start": 4.0, "source_end": 5.0, "order": 2, "role": "body"},
        {"source_start": 1.0, "source_end": 2.5, "order": 1, "role": "hook"},
        {"source_start": 3.0, "source_end": 3.5, "order": 3, "role": "x", "remove_from_body": True},
    ]}

    def test_segue_a_timeline_do_builder(self) -> None:
        self.assertEqual(segmentos_da_previa(self.CLIP), [(1.0, 2.5), (4.0, 5.0)])
        self.assertEqual(nome_da_previa(3, self.CLIP), "03-clip-007-quanto-mais-barato-voce-vende-piores-sao.mp4")
        cmd = comando("v.mp4", [(1.0, 2.5), (4.0, 5.0)], Path("o.mp4"))
        self.assertEqual(cmd.count("-i"), 2)
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))   # busca na entrada: rápida e, com reencode, exata
        self.assertIn("concat=n=2:v=1:a=1", cmd[cmd.index("-filter_complex") + 1])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg ausente")
    def test_corta_em_paralelo_e_troca_a_versao_antiga(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            video = run / "bruto.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=25:d=6",
                            "-f", "lavfi", "-i", "sine=f=440:d=6", "-shortest", "-c:v", "libx264",
                            "-c:a", "aac", str(video)], check=True)
            _manifest(run, str(video))
            (run / "01-media.json").write_text(json.dumps({"audio": [{"codec": "aac"}]}))
            outro = {"id": "clip-008", "title": "Outro", "segments": [
                {"source_start": 0.5, "source_end": 1.5, "order": 1, "role": "hook"}]}
            (run / "06-candidates.json").write_text(json.dumps({"clips": [self.CLIP, outro]}))
            (run / "preview").mkdir()
            antiga = run / "preview" / "01-clip-007-titulo-velho.mp4"
            antiga.write_bytes(b"velha")

            self.assertEqual(_vch("previews", "--run", tmp), 0)
            nomes = sorted(p.name for p in (run / "preview").glob("*.mp4"))
            self.assertEqual(nomes, ["01-clip-007-quanto-mais-barato-voce-vende-piores-sao.mp4", "02-clip-008-outro.mp4"])
            dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(run / "preview" / nomes[0])], capture_output=True, text=True).stdout
            self.assertAlmostEqual(float(dur), 2.5, delta=0.15)

            self.assertEqual(_vch("previews", "--run", tmp, "--clips", "clip-008,clip-999"), 3)  # id inexistente acusa


if __name__ == "__main__":
    unittest.main()
