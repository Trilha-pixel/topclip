"""Versão por corte, revisão sobre versão velha e o `--seguir` do usuário."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.render import render_all
from scripts.vch import main as vch_main
from scripts.versoes import VERSAO_ANTERIOR, hash_corte, sincronizar

BONS = {k: 9 for k in (
    "hook", "proposition_clarity", "first_value_speed", "context_efficiency", "curiosity_integrity",
    "progression", "payoff", "self_contained", "shareability", "visual_opportunity", "novelty", "editability",
)} | {"truthfulness": 10}
FRACOS = {k: 6 for k in BONS} | {"truthfulness": 9.5}


def _escrever(path: Path, dados: dict, mtime: float | None = None) -> None:
    path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _clip(clip_id: str, inicio: float) -> dict:
    return {
        "id": clip_id, "title": clip_id, "status": "APPROVED", "primary_context": "outro", "profile": "p",
        "scores": {}, "hard_fails": [],
        "segments": [{"order": 1, "role": "r", "source_start": inicio, "source_end": inicio + 30.0}],
    }


class RunFalsa(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.run = Path(self._tmp.name) / "run"
        self.run.mkdir()
        _escrever(self.run / "00-manifest.json", {
            "schema_version": "1.0", "run_id": "teste", "created_at": "2026-10-21T00:00:00-03:00",
            "mode": "full", "status": "prepared", "inputs": {"video_path": "", "platform": "cross-platform"},
            "stages": {},
        })
        self.agora = time.time()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def t(self, segundos_atras: float) -> float:
        return self.agora - segundos_atras

    def candidatos(self, inicio_002: float = 100.0, mtime: float | None = None) -> None:
        _escrever(self.run / "06-candidates.json",
                  {"schema_version": "1.0", "clips": [_clip("clip-001", 10.0), _clip("clip-002", inicio_002)]}, mtime)

    def feed(self, mtime: float | None = None, scores_001: dict = BONS, problemas_002: str = "nada") -> None:
        _escrever(self.run / "07-feed-review.json", {"schema_version": "1.0", "reviews": [
            {"clip_id": "clip-001", "status": "PASS", "scores": scores_001, "events": {}, "problems": []},
            {"clip_id": "clip-002", "status": "PASS", "scores": BONS, "events": {}, "problems": [problemas_002]},
        ]}, mtime)

    def ler(self, nome: str) -> dict:
        return json.loads((self.run / nome).read_text(encoding="utf-8"))


class VersaoPorCorte(RunFalsa):
    def test_revisao_carimbada_fica_velha_quando_o_corte_muda(self) -> None:
        self.candidatos(mtime=self.t(100))
        self.feed(mtime=self.t(90))
        resultado = sincronizar(self.run)
        self.assertEqual(resultado["desatualizadas"], [])
        carimbos = {r["clip_id"]: r["segments_hash"] for r in self.ler("07-feed-review.json")["reviews"]}
        self.assertEqual(carimbos["clip-002"], hash_corte(_clip("clip-002", 100.0)["segments"]))

        self.candidatos(inicio_002=101.5, mtime=self.t(50))  # Clip Builder refez o clip-002
        resultado = sincronizar(self.run)
        self.assertEqual([(d["clip_id"], d["refazer_com"]) for d in resultado["desatualizadas"]],
                         [("clip-002", "feed-psychologist")])

        # o feed-psychologist reescreve a entrada por cima, mantendo o carimbo velho
        doc = self.ler("07-feed-review.json")
        doc["reviews"][1]["problems"] = ["revisto na versão nova"]
        _escrever(self.run / "07-feed-review.json", doc, self.t(10))
        self.assertEqual(sincronizar(self.run)["desatualizadas"], [])

    def test_revisao_sem_carimbo_gravada_antes_da_mudanca_e_velha(self) -> None:
        self.candidatos(mtime=self.t(100))
        sincronizar(self.run)                                 # registra a versão original
        self.candidatos(inicio_002=101.5, mtime=self.t(50))   # muda o clip-002 em T-50
        self.feed(mtime=self.t(70))                           # revisão gravada em T-70: antes da mudança
        resultado = sincronizar(self.run)
        self.assertEqual([d["clip_id"] for d in resultado["desatualizadas"]], ["clip-002"])
        reviews = {r["clip_id"]: r for r in self.ler("07-feed-review.json")["reviews"]}
        self.assertEqual(reviews["clip-002"]["segments_hash"], VERSAO_ANTERIOR)
        self.assertNotEqual(reviews["clip-001"]["segments_hash"], VERSAO_ANTERIOR)
        # o carimbo fica: regravar o arquivo (mtime novo) não ressuscita a revisão velha
        self.assertEqual([d["clip_id"] for d in sincronizar(self.run)["desatualizadas"]], ["clip-002"])

    def test_run_antiga_tem_as_revisoes_aceitas_na_primeira_passada(self) -> None:
        # run de antes do registro: 06 regravado depois do 07, sem histórico do que mudou
        self.candidatos(mtime=self.t(50))
        self.feed(mtime=self.t(90))
        self.assertEqual(sincronizar(self.run)["desatualizadas"], [])
        self.candidatos(inicio_002=101.5, mtime=self.t(10))  # daqui em diante, rastreia
        self.assertEqual([d["clip_id"] for d in sincronizar(self.run)["desatualizadas"]], ["clip-002"])

    def test_ajuste_do_bordas_e_emenda_do_autoframe_nao_mudam_a_versao(self) -> None:
        autoral = [{"order": 1, "source_start": 113.58, "source_end": 123.58}]
        ajustado = [{"order": 1, "source_start": 113.74, "source_end": 123.58, "edge_audio": {
            "start": {"t": 113.74, "db": -51.5, "action": "moved", "from": 113.58, "from_db": -30.7}}}]
        dividido = [
            {"order": 1, "source_start": 113.58, "source_end": 118.0},
            {"order": 1, "source_start": 118.0, "source_end": 123.58},
        ]
        self.assertEqual(hash_corte(autoral), hash_corte(ajustado))
        self.assertEqual(hash_corte(autoral), hash_corte(dividido))
        movido_a_mao = [{"order": 1, "source_start": 113.9, "source_end": 123.58, "edge_audio": ajustado[0]["edge_audio"]}]
        self.assertNotEqual(hash_corte(autoral), hash_corte(movido_a_mao))


class Finalize(RunFalsa):
    def montar(self, scores_001: dict = BONS) -> None:
        self.candidatos(mtime=self.t(100))
        self.feed(mtime=self.t(90), scores_001=scores_001)
        _escrever(self.run / "09-blind-review.json", {"schema_version": "1.0", "reviews": [
            {"clip_id": c, "decision": "PASS", "would_continue_after_3s": True, "makes_sense_alone": True,
             "promise_delivered": True, "problems": []} for c in ("clip-001", "clip-002")
        ]}, self.t(85))
        _escrever(self.run / "10-deduplication.json", {"schema_version": "1.0", "decisions": []}, self.t(84))
        _escrever(self.run / "11-edit-plans.json", {"schema_version": "1.0", "plans": [
            {"clip_id": c, "output_slug": c, "primary_context": "outro", "captions": {}, "audio": {},
             "timeline": [{"order": 1, "source_start": s, "source_end": s + 30.0}]}
            for c, s in (("clip-001", 10.0), ("clip-002", 100.0))
        ]}, self.t(80))
        self.qc(self.t(70))

    def qc(self, mtime: float) -> None:
        _escrever(self.run / "12-quality-review.json", {"schema_version": "1.0", "reviews": [
            {"clip_id": c, "decision": "PASS", "hard_fails": [], "warnings": [], "reasons": []}
            for c in ("clip-001", "clip-002")
        ]}, mtime)

    def finalize(self, *extra: str) -> tuple[int, str, str]:
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = vch_main(["finalize", "--run", str(self.run), *extra])
        return codigo, saida.getvalue(), erro.getvalue()

    def test_para_antes_de_consolidar_revisao_velha(self) -> None:
        self.montar()
        self.assertEqual(self.finalize()[0], 0)
        plano = self.ler("11-edit-plans.json")
        plano["plans"][1]["timeline"][0]["source_start"] = 100.4   # corte mudou depois do QC
        _escrever(self.run / "11-edit-plans.json", plano, self.t(5))
        codigo, _, erro = self.finalize()
        self.assertEqual(codigo, 2)
        self.assertIn("12-quality-review.json · clip-002", erro)
        self.assertIn("quality-controller", erro)
        self.assertNotIn("clip-001", erro)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(vch_main(["revisoes", "--run", str(self.run)]), 3)
        self.qc(self.t(1))  # QC refeito na versão nova
        self.assertEqual(self.finalize()[0], 0)

    def test_seguir_leva_weak_para_render_sem_mudar_o_status(self) -> None:
        self.montar(scores_001=FRACOS)
        self.finalize()
        self.assertEqual([c["id"] for c in self.ler("13-final-clips.json")["clips"]], ["clip-002"])
        self.assertEqual(self.ler("14-rejected-clips.json")["clips"][0]["status"], "WEAK")

        codigo, saida, _ = self.finalize("--seguir", "clip-001", "--motivo", "quero publicar mesmo assim")
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(saida)["user_override"], ["clip-001"])
        final = {c["id"]: c for c in self.ler("13-final-clips.json")["clips"]}
        self.assertEqual(final["clip-001"]["status"], "WEAK")
        self.assertEqual(final["clip-001"]["user_override"]["motivo"], "quero publicar mesmo assim")
        self.assertEqual(final["clip-001"]["user_override"]["status_kept"], "WEAK")
        relatorio = (self.run / "15-run-report.md").read_text(encoding="utf-8")
        self.assertIn("- Fracos: 1", relatorio)
        self.assertIn("## Seguem por decisão do usuário", relatorio)
        self.assertIn("`WEAK` (mantido)", relatorio)

        # o próximo finalize lembra da decisão
        self.finalize()
        self.assertIn("clip-001", [c["id"] for c in self.ler("13-final-clips.json")["clips"]])

        # versão nova do corte: a decisão era para a outra, não vale mais
        plano = self.ler("11-edit-plans.json")
        plano["plans"][0]["timeline"][0]["source_end"] = 41.0
        _escrever(self.run / "11-edit-plans.json", plano, self.t(5))
        self.qc(self.t(1))
        codigo, saida, _ = self.finalize()
        self.assertEqual(codigo, 0)
        self.assertNotIn("clip-001", [c["id"] for c in self.ler("13-final-clips.json")["clips"]])
        self.assertEqual(json.loads(saida)["user_override_ignorado"][0]["clip_id"], "clip-001")

    def test_seguir_nao_forca_hard_fail(self) -> None:
        self.montar()
        doc = self.ler("12-quality-review.json")
        doc["reviews"][0]["hard_fails"] = ["truncated_word"]
        doc["reviews"][0]["decision"] = "REJECT"
        _escrever(self.run / "12-quality-review.json", doc, self.t(60))
        self.finalize("--seguir", "clip-001")
        self.assertNotIn("clip-001", [c["id"] for c in self.ler("13-final-clips.json")["clips"]])
        rejeitado = self.ler("14-rejected-clips.json")["clips"][0]
        self.assertEqual(rejeitado["status"], "REJECTED")
        self.assertTrue(any(r.startswith("user_override_ignorado") for r in rejeitado["final_decision_reasons"]))


class RenderAceitaOverride(unittest.TestCase):
    def test_render_all_pula_weak_sem_override(self) -> None:
        final = {"clips": [
            {"id": "a", "status": "APPROVED"},
            {"id": "b", "status": "WEAK", "user_override": {"motivo": "usuário mandou"}},
            {"id": "c", "status": "WEAK"},
        ]}
        planos = {"plans": [{"clip_id": c, "output_slug": c, "primary_context": "outro"} for c in "abc"]}
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.render.render_clip", side_effect=lambda v, clip, *a: {"clip_id": clip["id"]}) as fake:
            feitos = render_all(tmp, "video.mp4", final, planos, {})
        self.assertEqual([f["clip_id"] for f in feitos], ["a", "b"])
        self.assertEqual(fake.call_count, 2)


if __name__ == "__main__":
    unittest.main()
