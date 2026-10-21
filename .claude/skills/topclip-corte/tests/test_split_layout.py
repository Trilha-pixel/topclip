# -*- coding: utf-8 -*-
"""Layout split: metade de cima e o quadro inteiro, metade de baixo e o crop fechado."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.render import split_geometry, _split_filter, _video_filter
from scripts.utils import HarnessError


class TestSplitGeometry(unittest.TestCase):
    def test_metades_fecham_a_altura_exata(self):
        """Se as metades nao somam a altura, sobra faixa preta - o erro classico."""
        for src in [(1920, 1080), (3840, 2160), (1280, 720), (1440, 1080)]:
            g = split_geometry(1080, 1920, *src)
            self.assertEqual(g["top_h"] + g["bottom_h"], 1920, f"fonte {src}")

    def test_dimensoes_sao_pares(self):
        """yuv420p rejeita dimensao impar."""
        for src in [(1920, 1080), (1280, 720), (1600, 900)]:
            g = split_geometry(1080, 1920, *src)
            for key in ("top_h", "bottom_h", "crop_w", "crop_h"):
                self.assertEqual(g[key] % 2, 0, f"{key} impar em {src}")

    def test_crop_de_baixo_preserva_aspecto(self):
        """Sem isso a imagem estica na horizontal - a rejeicao nº 4 da etapa vertical."""
        for src in [(1920, 1080), (3840, 2160), (1280, 720)]:
            g = split_geometry(1080, 1920, *src)
            self.assertAlmostEqual(g["crop_w"] / g["crop_h"], 1080 / g["bottom_h"], delta=0.005)

    def test_1080p_bate_com_a_geometria_documentada(self):
        g = split_geometry(1080, 1920, 1920, 1080)
        self.assertEqual(g["top_h"], 608)
        self.assertEqual(g["bottom_h"], 1312)

    def test_zoom_fecha_o_crop_de_baixo(self):
        largo = split_geometry(1080, 1920, 1920, 1080, zoom=1.0)["crop_w"]
        fechado = split_geometry(1080, 1920, 1920, 1080, zoom=1.4)["crop_w"]
        self.assertLess(fechado, largo)

    def test_crop_nunca_excede_a_fonte(self):
        g = split_geometry(1080, 1920, 1280, 720)
        self.assertLessEqual(g["crop_w"], 1280)

    def test_fonte_ja_vertical_e_recusada(self):
        """Split numa fonte 9:16 nao deixa leitura embaixo: falhar e melhor que entregar."""
        with self.assertRaises(HarnessError):
            split_geometry(1080, 1920, 1080, 1920)

    def test_fonte_sem_dimensao_e_recusada(self):
        with self.assertRaises(HarnessError):
            split_geometry(1080, 1920, 0, 0)


class TestSplitFilter(unittest.TestCase):
    def test_anchor_desloca_o_crop_sem_estourar(self):
        esq = _split_filter(1080, 1920, 1920, 1080, 0.0, 1.0)
        dir_ = _split_filter(1080, 1920, 1920, 1080, 1.0, 1.0)
        self.assertIn("crop=890:1080:0:0", esq)
        self.assertIn("crop=890:1080:1030:0", dir_)  # 1920-890
        for f in (esq, dir_):
            self.assertIn("vstack=inputs=2", f)
            self.assertIn("[vout]", f)

    def test_cover_continua_sendo_um_filtro_simples(self):
        """O caminho antigo nao pode ter regredido: cover usa -vf, nao filter_complex."""
        vf = _video_filter(1080, 1920, 0.5, 1.0)
        self.assertNotIn("vstack", vf)
        self.assertIn("crop=1080:1920", vf)


if __name__ == "__main__":
    unittest.main()
