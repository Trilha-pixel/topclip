# -*- coding: utf-8 -*-
"""
Motor e desenho: glifo que a fonte nao tem, medida pela tinta, retalho no tamanho de
uso, e os assets que os templates pedem por nome.
"""
import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

import numpy as np

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "lib"))

import desenho as D  # noqa: E402
import motor as V  # noqa: E402


class TestGlifos(unittest.TestCase):
    def test_marcador_tabela_do_que_engana(self):
        self.assertNotEqual(V.glifo(V.F_MARKER, "≈"), "ok")
        self.assertIn("A", V.glifo(V.F_MARKER, "ª"))
        self.assertEqual(V.glifo(V.F_MARKER, "→"), "ausente")
        for ch in "Açãê.$/":
            self.assertEqual(V.glifo(V.F_MARKER, ch), "ok", ch)

    def test_ausente_detectado_tambem_em_fonte_com_notdef_desenhado(self):
        self.assertEqual(V.glifo(V.F_BLACK, "✓"), "ausente")
        self.assertEqual(V.glifo(V.F_BLACK, "≈"), "ok")

    def test_text_layer_avisa_uma_vez_e_desenha_o_aprox(self):
        V._avisados.clear()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            V.text_layer((600, 200), "1≈2", V.F_MARKER, 98, (20, 40), hand=True, seed=3)
            V.text_layer((600, 200), "1≈2", V.F_MARKER, 98, (20, 40), hand=True, seed=3)
        self.assertEqual(err.getvalue().count("'≈'"), 1)
        # o sinal desenhado e largo e baixo (duas ondas), nao o traco vertical da fonte
        cheio = V.text_layer((600, 200), "1≈2", V.F_MARKER, 98, (20, 40), seed=3)
        so_1 = V.text_layer((600, 200), "1", V.F_MARKER, 98, (20, 40), seed=3)
        x0 = so_1.getbbox()[2] + 4
        x1 = x0 + V.font(V.F_MARKER, 98).getlength("=") * 1.2
        a = np.asarray(cheio.getchannel("A"))[:, int(x0):int(x1)] > 128
        ys, xs = np.nonzero(a)
        self.assertGreater(xs.max() - xs.min(), ys.max() - ys.min())

    def test_texto_comum_nao_avisa(self):
        V._avisados.clear()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            V.text_layer((600, 200), "R$ 3.000/mês", V.F_MARKER, 60, (10, 40), hand=True)
        self.assertEqual(err.getvalue(), "")

    def test_ink_span_mede_o_pedaco_desenhado(self):
        kw = dict(anchor="lt", stroke_w=3, tracking=2, hand=True, seed=71)
        cheio = V.ink_bbox("= R$ 3.000/mês", V.F_MARKER, 86, (168, 1010), **kw)
        mes = V.ink_span("= R$ 3.000/mês", "mês", V.F_MARKER, 86, (168, 1010), **kw)
        self.assertAlmostEqual(mes[2], cheio[2], delta=3)
        self.assertGreater(mes[0], cheio[0] + 300)
        # ancora centrada: mesmo pedaco, mesma tinta
        mm = V.ink_span("= R$ 3.000/mês", "mês", V.F_MARKER, 86, (540, 1050),
                        **dict(kw, anchor="mm"))
        cmm = V.ink_bbox("= R$ 3.000/mês", V.F_MARKER, 86, (540, 1050),
                         **dict(kw, anchor="mm"))
        self.assertAlmostEqual(mm[2], cmm[2], delta=3)

    def test_sem_boil_restaura_o_frame(self):
        V.boil_ctx(12)
        with V.sem_boil():
            self.assertIsNone(V._BOIL["frame"])
        self.assertEqual(V._BOIL["frame"], 12)
        V.boil_ctx(None)


class TestDesenho(unittest.TestCase):
    def test_retalho_pautado_em_escala_de_caderno(self):
        g = D.geometria_retalho(788, 752, pauta=D.PAUTA, margem=True)
        self.assertEqual(g["linhas"][0], D.PAD + int(D.PAUTA * 1.6))
        self.assertEqual(g["linhas"][1] - g["linhas"][0], D.PAUTA)
        self.assertEqual(g["margem"], D.PAD + D.MARGEM)
        im = D.retalho(300, 200, 7, D.CADERNO, pauta=D.PAUTA, margem=True)
        self.assertEqual(im.size, (300 + 2 * D.PAD, 200 + 2 * D.PAD))
        self.assertEqual(im.getpixel((0, 0))[3], 0)          # canto transparente

    def test_folha_do_wipe_na_biblioteca_e_no_manifesto(self):
        for nome in ("A05_SHEET", "A05_CARD"):
            self.assertIn(nome, D.ASSETS)
            png = RAIZ / "biblioteca" / "assets" / f"{nome}.png"
            self.assertTrue(png.exists(), png)
            self.assertIn(f"`{nome}.png`", (RAIZ / "biblioteca" / "MANIFESTO.md").read_text())

    def test_todo_asset_pedido_pelos_templates_existe(self):
        """O defeito do A05_CARD: o template pedia um asset que ninguem desenhou."""
        pedidos = set()
        for f in ("kit.py", "render_template.py", "compose_template.py"):
            txt = (SKILL / "lib" / f).read_text()
            pedidos |= set(re.findall(r'"((?:A\d\d|BG)_[A-Z_]+)"', txt))
        pedidos -= {"A11_NIGHT"}            # foto de gerador: opcional, ver night_photo.py
        self.assertTrue(pedidos)
        for nome in sorted(pedidos):
            na_biblioteca = (RAIZ / "biblioteca" / "assets" / f"{nome}.png").exists()
            self.assertTrue(na_biblioteca or nome in D.ASSETS, nome)

    def test_wipe_nao_pede_mais_o_card(self):
        txt = (SKILL / "lib" / "render_template.py").read_text()
        self.assertIn("A05_SHEET", txt)
        self.assertNotIn("A05_CARD", txt)


if __name__ == "__main__":
    unittest.main()
