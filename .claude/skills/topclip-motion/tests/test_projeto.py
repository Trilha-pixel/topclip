# -*- coding: utf-8 -*-
"""
Ponta a ponta num projeto LIMPO, criado pelo `./topclip motion novo` de verdade, com um
video sintetico de 3s: o template de compose renderiza as receitas, e o de render
monta o rascunho com saida `wipe` (o A05_CARD que faltava), quadros em paralelo,
legenda conferida e o laudo D5 automatico. Tudo em subprocesso: importar o `kit` cria
as pastas do projeto ao lado dele.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
# No Windows o ./topclip roda no bash do Git; um "bash" solto pegaria o do WSL.
BASH = shutil.which("bash") or "bash"
PY = sys.executable


def _roda(args, cwd):
    r = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"{args} falhou:\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


class TestProjetoLimpo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="topclip-teste-")
        cls.proj = Path(cls.tmp.name) / "motion"
        subprocess.run([BASH, str(RAIZ / "topclip"), "motion", "novo", str(cls.proj)],
                       check=True, stdout=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_1_receitas_renderizam(self):
        out = _roda(["compose.py", "--check"], self.proj)
        self.assertNotIn("<<<", out)
        # o END de cada receita, sem os 24 estados (rapido): nada quebra, e a tira do
        # topo deixa o rosto livre
        codigo = (
            "import compose as C\n"
            "for s, (fn, st, fx) in C.SCENES.items():\n"
            "    im = fn(st['END'], overlay_only=True) if fx is None else fn(st['END'])\n"
            "    bb = im.getbbox()\n"
            "    assert im.size == (1080, 1920) and bb, s\n"
            "    if fx is None:\n"
            "        assert bb[3] < 800, (s, bb)\n"
            "    print(s, bb)\n")
        out = _roda(["-c", codigo], self.proj)
        for s in ("M1", "R1", "R2", "R3", "R4", "R5"):
            self.assertIn(s, out)
        # papel grande sai no tamanho de uso, nao ampliado do A10
        self.assertNotIn("ampliada", out)
        self.assertTrue(list((self.proj / "07_assets" / "cutout" / "_uso").glob("*.png")))

    def test_2_render_rascunho_com_wipe(self):
        src = self.proj / "00_brief" / "fonte.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                        "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)],
                       check=True)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(src)], capture_output=True,
                             text=True).stdout.strip()
        palavras = [{"w": "Isso", "t": 0.10, "e": 0.40}, {"w": "não", "t": 0.45, "e": 0.70},
                    {"w": "é", "t": 0.72, "e": 0.80}, {"w": "difícil.", "t": 0.82, "e": 1.15},
                    {"w": "Tchau", "t": 2.30, "e": 2.70}]
        (self.proj / "00_brief" / "transcript_palavras.json").write_text(json.dumps(palavras))
        r = self.proj / "render.py"
        s = r.read_text()
        for velho, novo in (
                ("DUR = 55.4554", f"DUR = {dur}"),
                ("FPS_NUM, FPS_DEN = 30000, 1001", "FPS_NUM, FPS_DEN = 30, 1"),
                ('("M1", C.build_M1, 11.700, 14.900, 77, True)',
                 '("M1", C.build_M1, 1.200, 2.200, 24, True)'),
                ('EXIT_KIND = {"M1": "slide"}', 'EXIT_KIND = {"M1": "wipe"}')):
            self.assertEqual(s.count(velho), 1, velho)
            s = s.replace(velho, novo)
        r.write_text(s)

        out = _roda(["render.py", "--rascunho", "--jobs", "2"], self.proj)
        self.assertIn("OK: nenhum bloco invade", out)
        self.assertNotIn("DIFERE", out)
        self.assertIn("audio md5", out)
        self.assertTrue((self.proj / "12_master" / "RASCUNHO.mp4").exists())
        self.assertFalse((self.proj / "12_master" / "MASTER_v01.mp4").exists())
        quadros = sorted((self.proj / "10_sequences" / "M1").glob("*.png"))
        self.assertEqual(len(quadros), 30)
        # no meio da saida wipe a folha cobre parte do quadro e o resto ja e video
        from PIL import Image
        meio = Image.open(quadros[-6]).getchannel("A")
        self.assertEqual(meio.getextrema(), (0, 255))

        cmd = _roda(["-c", "import render as R\n"
                           "c, d = R.mux_cmd(True); print('R', ' '.join(c[-12:]), d.name)\n"
                           "c, d = R.mux_cmd(False); print('F', ' '.join(c[-12:]), d.name)"],
                    self.proj)
        self.assertIn("veryfast", cmd.split("\nF")[0])
        self.assertIn("RASCUNHO.mp4", cmd.split("\nF")[0])
        self.assertIn("slow", cmd.split("\nF")[1])
        self.assertIn("MASTER_v01.mp4", cmd.split("\nF")[1])


if __name__ == "__main__":
    unittest.main()
