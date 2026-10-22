"""Tempos de clipe recalculados pela posição na fonte quando uma borda muda."""
from __future__ import annotations

import copy
import unittest

from scripts.tempos import Faixa, Remapeador, pais_por_sequencia, recalcular_plano, remapear_candidato, verificar_plano


def plano() -> dict:
    """Três segmentos: fonte 10–12, 20–25, 30–33 -> clipe 0–2, 2–7, 7–10."""
    return {
        "clip_id": "clip-001",
        "timeline": [
            {"order": 1, "source_start": 10.0, "source_end": 12.0, "clip_start": 0.0, "clip_end": 2.0},
            {"order": 2, "source_start": 20.0, "source_end": 25.0, "clip_start": 2.0, "clip_end": 7.0,
             "breath_cut_before": {"removed_source": [12.0, 20.0], "removed_s": 8.0, "confidence": "alta"}},
            {"order": 3, "source_start": 30.0, "source_end": 33.0, "clip_start": 7.0, "clip_end": 10.0},
        ],
        "captions": {"chunks": [
            {"clip_start": 0.0, "text": "abre"},
            {"clip_start": 2.0, "text": "na borda do 2"},
            {"clip_start": 2.05, "text": "fala que vai sair do corte"},
            {"clip_start": 4.0, "text": "meio do 2"},
            {"clip_start": 8.0, "text": "meio do 3"},
        ]},
        "cards": [{"id": "c1", "clip_start": 2.0, "clip_end": 7.0}, {"id": "c2", "clip_start": 0.5, "clip_end": 9.5}],
        "motion_anchors": [{"clip_t": 8.0, "word": "x"}, {"clip_t": 7.0, "word": "na emenda 2|3"}],
        "punch_ins": [{"source_start": 30.0, "source_end": 33.0, "clip_start": 7.0, "clip_end": 10.0, "zoom_factor": 1.08}],
        "breath_decupage": {"candidate_duration_s": 11.0, "final_duration_s": 10.0, "removed_s": 1.0,
                            "removed_pct": 9.1, "untouched_edges": [10.0, 12.0, 20.0, 25.0, 30.0, 33.0]},
    }


class RecalcularPlano(unittest.TestCase):
    def test_borda_movida_desliza_tudo_que_vem_depois(self) -> None:
        p = plano()
        antiga = copy.deepcopy(p["timeline"])
        p["timeline"][1]["source_start"] = 20.1   # início do 2 avança 0,1 s
        p["timeline"][2]["source_end"] = 33.2     # fim do 3 recua... avança 0,2 s
        resumo = recalcular_plano(p, antiga, origem="bordas")
        self.assertTrue(resumo["mudou"])
        tl = p["timeline"]
        self.assertEqual([(s["clip_start"], s["clip_end"]) for s in tl], [(0.0, 2.0), (2.0, 6.9), (6.9, 10.1)])
        self.assertEqual(tl[1]["synced_source"], [20.1, 25.0])
        chunks = [c["clip_start"] for c in p["captions"]["chunks"]]
        # borda acompanha a borda; fala acompanha a fala; fala cortada gruda na borda
        self.assertEqual(chunks, [0.0, 2.0, 2.0, 3.9, 7.9])
        self.assertEqual((p["cards"][0]["clip_start"], p["cards"][0]["clip_end"]), (2.0, 6.9))
        self.assertEqual((p["cards"][1]["clip_start"], p["cards"][1]["clip_end"]), (0.5, 9.4))
        self.assertEqual([a["clip_t"] for a in p["motion_anchors"]], [7.9, 6.9])
        punch = p["punch_ins"][0]
        self.assertEqual((punch["clip_start"], punch["clip_end"]), (6.9, 10.1))
        self.assertEqual((punch["source_start"], punch["source_end"]), (30.0, 33.2))
        self.assertEqual(tl[1]["breath_cut_before"]["removed_source"], [12.0, 20.1])
        self.assertEqual(tl[1]["breath_cut_before"]["removed_s"], 8.1)
        self.assertEqual(tl[1]["breath_cut_before"]["confidence"], "alta")
        dec = p["breath_decupage"]
        self.assertEqual((dec["final_duration_s"], dec["removed_s"], dec["removed_pct"]), (10.1, 0.9, 8.2))
        self.assertEqual(dec["untouched_edges"], [10.0, 12.0, 20.1, 25.0, 30.0, 33.2])
        self.assertEqual(p["timing_sync"]["by"], "bordas")
        self.assertEqual(verificar_plano(p), [])

    def test_borda_editada_a_mao_e_recuperada_pelo_synced_source(self) -> None:
        p = plano()
        recalcular_plano(p)  # primeira passada: só registra synced_source
        self.assertEqual(p["timeline"][0]["synced_source"], [10.0, 12.0])
        self.assertEqual(p["captions"]["chunks"][3]["clip_start"], 4.0)
        p["timeline"][1]["source_start"] = 19.8  # alguém abriu 0,2 s antes, à mão, sem recalcular
        self.assertEqual(len(verificar_plano(p)), 1)
        recalcular_plano(p)
        self.assertEqual(verificar_plano(p), [])
        self.assertEqual(p["timeline"][1]["clip_end"], 7.2)
        self.assertEqual(p["captions"]["chunks"][3]["clip_start"], 4.0 + 0.2)
        self.assertEqual(p["motion_anchors"][0]["clip_t"], 8.2)

    def test_sem_referencia_avisa_em_vez_de_inventar(self) -> None:
        p = plano()
        p["timeline"][1]["source_start"] = 19.8  # edição à mão sem synced_source gravado
        resumo = recalcular_plano(p)
        self.assertTrue(resumo["avisos"])
        self.assertTrue(any(w.startswith("tempos_sem_referencia: segmento 2") for w in p["warnings"]))
        self.assertEqual(verificar_plano(p), [])

    def test_plano_sem_tempo_de_clipe_ganha_os_tempos(self) -> None:
        p = {"clip_id": "c", "timeline": [
            {"order": 2, "source_start": 0.0, "source_end": 3.0},
            {"order": 1, "source_start": 3.0, "source_end": 9.0},
        ]}
        recalcular_plano(p)
        por_ordem = sorted(p["timeline"], key=lambda s: s["order"])
        self.assertEqual([(s["clip_start"], s["clip_end"]) for s in por_ordem], [(0.0, 6.0), (6.0, 9.0)])

    def test_subsegmentos_do_autoframe_ganham_tempos_proprios(self) -> None:
        p = plano()
        antiga = copy.deepcopy(p["timeline"])
        p["timeline"][1]["edge_audio"] = {"start": {"t": 20.0, "action": "kept_silence"}, "end": {"t": 25.0, "action": "kept_silence"}}
        seg2 = p["timeline"][1]
        a = {**copy.deepcopy(seg2), "source_start": 20.0, "source_end": 22.5, "crop_anchor_x": 0.3}
        b = {**copy.deepcopy(seg2), "source_start": 22.5, "source_end": 25.0, "crop_anchor_x": 0.7}
        p["timeline"] = [p["timeline"][0], a, b, p["timeline"][2]]  # autoframe: herdaram clip_start/clip_end do pai
        recalcular_plano(p, antiga, dividido=True, origem="autoframe")
        tl = p["timeline"]
        self.assertEqual([(s["clip_start"], s["clip_end"]) for s in tl], [(0.0, 2.0), (2.0, 4.5), (4.5, 7.0), (7.0, 10.0)])
        self.assertIn("breath_cut_before", tl[1])
        self.assertNotIn("breath_cut_before", tl[2])
        self.assertEqual(set(tl[1]["edge_audio"]), {"start"})
        self.assertEqual(set(tl[2]["edge_audio"]), {"end"})
        self.assertEqual([c["clip_start"] for c in p["captions"]["chunks"]], [0.0, 2.0, 2.05, 4.0, 8.0])
        self.assertEqual(verificar_plano(p), [])


class RemapeadorComRepeticao(unittest.TestCase):
    def test_hook_repetido_no_corpo_nao_confunde_os_pais(self) -> None:
        # hook 100–105 repetido dentro do corpo 95–110, autoframe divide o corpo em três
        antigas = [Faixa(100, 105, 0, 5), Faixa(95, 110, 5, 20)]
        novas = [Faixa(100, 105, 0, 5), Faixa(95, 100, 5, 10), Faixa(100, 105, 10, 15), Faixa(105, 110, 15, 20)]
        self.assertEqual(pais_por_sequencia(antigas, novas), [0, 1, 1, 1])
        mapa = Remapeador(antigas, novas, [0, 1, 1, 1])
        self.assertEqual(mapa.tempo(2.0), 2.0)     # no hook
        self.assertEqual(mapa.tempo(12.0), 12.0)   # o mesmo trecho da fonte, no corpo


class CandidatoRecalculado(unittest.TestCase):
    def test_eventos_e_beats_do_06_acompanham_a_fala(self) -> None:
        clip = {
            "id": "clip-001",
            "segments": [{"order": 1, "source_start": 10.0, "source_end": 12.0}, {"order": 2, "source_start": 20.0, "source_end": 25.0}],
            "events": {"timebase": "final", "proposition_at": 0.0, "payoff_at": 4.0, "closure_at": None},
            "semantic_beats": [{"at": 2.0, "type": "virada", "description": "d"}, {"at": 6.0, "type": "payoff", "description": "d"}],
            "estimated_final_duration_seconds": 7.0,
        }
        antigos = copy.deepcopy(clip["segments"])
        clip["segments"][0]["source_start"] = 10.2
        resumo = remapear_candidato(clip, antigos)
        self.assertTrue(resumo["mudou"])
        self.assertEqual(clip["events"]["proposition_at"], 0.0)
        self.assertEqual(clip["events"]["payoff_at"], 3.8)
        self.assertIsNone(clip["events"]["closure_at"])
        self.assertEqual([b["at"] for b in clip["semantic_beats"]], [1.8, 5.8])
        self.assertEqual(clip["estimated_final_duration_seconds"], 6.8)


if __name__ == "__main__":
    unittest.main()
