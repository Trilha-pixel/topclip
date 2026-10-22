# -*- coding: utf-8 -*-
"""
Legenda: as regressoes da run aula-yt-teste.

1. O recuo de 0,15s das janelas apagava a palavra do vao — o "Nao" de "Nao e dificil
   fazer" (clip-005). check() tem que parar com erro, destacando a negacao.
2. Palavra que atravessa a borda da cena ("consegue" no clip-010) nao estava inteira em
   lugar nenhum e sumia. Vai pelo meio.
3. A enfase de 168px estourava a largura em palavra longa ("MENSALIDADE,").
4. CY/TETO fixos cobriam a boca num video selfie: a altura sai do queixo.
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB))

import captions as CAP  # noqa: E402

# clip-005, 14-27s: a cena M2 vai ate 19,25 e o "Nao" comeca em 19,30
PALAVRAS = [
    {"w": "Se", "t": 13.76, "e": 14.20}, {"w": "você", "t": 14.20, "e": 14.40},
    {"w": "fechar", "t": 14.40, "e": 14.70},
    {"w": "Não", "t": 19.30, "e": 19.45}, {"w": "é", "t": 19.66, "e": 19.80},
    {"w": "difícil", "t": 20.38, "e": 20.72}, {"w": "fazer,", "t": 20.72, "e": 21.00},
    {"w": "tá?", "t": 21.10, "e": 21.40},
]
SHOTS = [("M2", None, 14.20, 19.25, 121, True)]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.words = Path(self.tmp.name) / "transcript_palavras.json"
        self.words.write_text(json.dumps(PALAVRAS))

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, janelas, **kw):
        CAP.configurar(self.words, janelas, **kw)


class TestJanelas(Base):
    def test_janelas_livres_sao_o_complemento_colado(self):
        shots = [("A", None, 4.0, 6.0, 0, True), ("B", None, 9.0, 11.0, 0, True)]
        self.assertEqual(CAP.janelas_livres(shots, 14.0),
                         [(0.0, 4.0), (6.0, 9.0), (11.0, 14.0)])

    def test_negacao_no_vao_e_erro(self):
        # janela recuada demais: o "Nao" (meio em 19,375) nao e de janela nem de cena
        self.config([(13.0, 14.20), (19.50, 21.5)])
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            with self.assertRaises(RuntimeError):
                CAP.check(SHOTS)
        self.assertIn("'Não'", err.getvalue())
        self.assertIn("NEGACAO", err.getvalue())

    def test_janela_colada_mostra_o_nao_sem_invadir_a_cena(self):
        self.config(CAP.janelas_livres(SHOTS, 21.5))
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            b = CAP.check(SHOTS)
        texto = " ".join(x["txt"] for x in b)
        self.assertIn("Não", texto)
        self.assertIn("Se", texto)
        for x in b:
            self.assertTrue(x["e"] <= 14.20 + 1e-6 or x["t"] >= 19.25 - 1e-6, x)

    def test_palavra_na_borda_fica_com_quem_tem_o_meio(self):
        # "Se" 13,76-14,20 com a janela terminando em 14,05: meio 13,98 -> janela
        self.config([(13.0, 14.05), (19.25, 21.5)])
        b = CAP.blocos()
        primeiro = b[0]
        self.assertTrue(primeiro["txt"].startswith("Se"))
        self.assertLessEqual(primeiro["e"], 14.05 + 1e-6)

    def test_bloco_preso_ao_fim_da_janela(self):
        self.config([(19.25, 21.42)])
        b = CAP.blocos()
        self.assertLessEqual(max(x["e"] for x in b), 21.42 + 1e-6)


class TestSincronia(Base):
    """clip-010: "mas tambem para" saia em 38,12 pelo MAXDUR — o "para" (38,14) ia a
    tela antes da hora e sumia justo quando era dito."""
    FIM = [{"w": "bolso,", "t": 36.98, "e": 37.50}, {"w": "mas", "t": 37.50, "e": 37.84},
           {"w": "também", "t": 37.84, "e": 38.14}, {"w": "para", "t": 38.14, "e": 38.72},
           {"w": "a", "t": 38.72, "e": 38.80}, {"w": "sua", "t": 38.80, "e": 38.86},
           {"w": "cartela", "t": 38.86, "e": 39.24}, {"w": "de", "t": 39.24, "e": 39.36},
           {"w": "clientes.", "t": 39.36, "e": 39.82}]

    def test_toda_palavra_na_tela_enquanto_e_dita(self):
        self.words.write_text(json.dumps(self.FIM))
        self.config([(36.9, 39.98)], destaque={("bolso,", 36.98): dict(cor=None)})
        b = CAP.blocos()
        self.assertEqual(CAP.fora_de_hora(b), [])
        para = next(x for x in b if "para" in x["txt"].split())
        self.assertGreaterEqual(para["e"], 38.72 - 1e-6)

    def test_bloco_lento_divide_sem_deixar_so_palavra_fraca(self):
        lento = [{"w": "de", "t": 7.46, "e": 7.70}, {"w": "você", "t": 7.70, "e": 7.98},
                 {"w": "ter", "t": 8.10, "e": 8.40}, {"w": "um", "t": 8.40, "e": 8.62}]
        self.words.write_text(json.dumps(lento))
        self.config([(7.0, 9.0)])
        b = CAP.blocos()
        self.assertEqual([x["txt"] for x in b], ["de você", "ter um"])
        self.assertEqual(CAP.fora_de_hora(b), [])


class TestDesenho(Base):
    def test_enfase_longa_desce_ate_caber_e_curta_fica(self):
        self.assertEqual(CAP.corpo("aluguel", True), CAP.ENFASE)
        self.assertEqual(CAP.corpo("casa", False), CAP.CORPO)
        k = CAP.corpo("MENSALIDADE,", True)
        self.assertLess(k, CAP.ENFASE)
        self.assertGreater(k, CAP.CORPO)
        self.config([(0, 30)], posicao=(1545, 1410))
        x0, _, x1, _ = CAP.caixa(dict(txt="MENSALIDADE,", enf=True, cor=None))
        self.assertGreaterEqual(x0, 1080 - CAP.ZONA_DIR)
        self.assertLessEqual(x1, CAP.ZONA_DIR)

    def test_posicao_pelo_queixo(self):
        # clip-005: queixo mais baixo em y=1486 -> a run achou CY 1545 a mao
        cy, teto = CAP.posicao_pelo_queixo(1486)
        self.assertEqual(teto, 1498)
        self.assertAlmostEqual(cy, 1545, delta=5)
        # podcast (queixo alto): o padrao medido
        self.assertEqual(CAP.posicao_pelo_queixo(1000), (CAP.CY_PADRAO, CAP.TETO_PADRAO))
        # rosto baixissimo: nunca dentro da faixa de interface
        self.assertLessEqual(CAP.posicao_pelo_queixo(1800)[0], CAP.ZONA_INF - CAP.MEIO_BLOCO)

    def test_posicao_manual_e_fixa(self):
        self.config([(0, 30)], posicao=(1500, 1400))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CAP.posicao(), (1500, 1400))
        self.config([(0, 30)])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(CAP.posicao(), (CAP.CY_PADRAO, CAP.TETO_PADRAO))

    def test_video_sem_rosto_cai_no_fixo_com_aviso(self):
        video = Path(self.tmp.name) / "fonte.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=540x960:rate=10", "-t", "1.5", "-pix_fmt",
                        "yuv420p", str(video)], check=True)
        self.config([(0.0, 1.4)], video=video)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(CAP.posicao(), (CAP.CY_PADRAO, CAP.TETO_PADRAO))
        self.assertIn("FIXA", err.getvalue())
        self.assertTrue((video.parent / "legenda_rosto.json").exists())


if __name__ == "__main__":
    unittest.main()
