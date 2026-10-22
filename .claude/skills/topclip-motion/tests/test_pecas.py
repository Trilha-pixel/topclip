# -*- coding: utf-8 -*-
"""
Pecas e o estilo Limpo: cada peca renderiza em cada estilo que a declara (e sai vazia fora
do trecho), a legenda do Limpo, as previas, o `motion novo --estilo limpo` com o compose
dele, e um rascunho de verdade com cena overlay em fade — sem tocar o caminho do Papel.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
OFICIAIS = RAIZ / "biblioteca" / "estilos"
LIMPO = OFICIAIS / "limpo"
sys.path.insert(0, str(SKILL / "lib"))
sys.path.insert(0, str(RAIZ / "biblioteca"))

import estilo as E  # noqa: E402
import pecas as P  # noqa: E402
from pecas import contador, legenda as PL, marca_texto, troca_palavra  # noqa: E402
from pecas.base import bezier, lin  # noqa: E402


def _estilo(pasta=LIMPO, variacao=None):
    """O Estilo resolvido, com as fontes do kit (a skill tem fontes/ como um projeto)."""
    return P.Estilo(E.resolver(pasta, variacao), SKILL)


# Roda dentro de um projeto: cada peca declarada, no EXEMPLO dela, dentro e fora do trecho.
_CADA_PECA = (
    "import json, pecas as P\n"
    "from pathlib import Path\n"
    "est = P.carregar(Path.cwd())\n"
    "for nome in json.loads(Path('estilo/estilo.json').read_text())['pecas']:\n"
    "    m = P.TODAS[nome]; ex = m.EXEMPLO; d = ex['dados']\n"
    "    dentro = m.quadro(ex['f'], ex['inicio'], ex['fim'], est, **d)\n"
    "    antes = m.quadro(ex['inicio'] - 1, ex['inicio'], ex['fim'], est, **d)\n"
    "    depois = m.quadro(ex['fim'] + 1, ex['inicio'], ex['fim'], est, **d)\n"
    "    assert dentro.size == (1080, 1920) and dentro.mode == 'RGBA', nome\n"
    "    assert dentro.getbbox() is not None, nome\n"
    "    assert antes.getbbox() is None and depois.getbbox() is None, nome\n"
    "    print(nome, dentro.getbbox())\n")


class TestPecasNosEstilos(unittest.TestCase):
    def test_cada_peca_em_cada_variacao_de_cada_estilo_oficial(self):
        feitos = 0
        for pasta in sorted(p.parent for p in OFICIAIS.glob("*/estilo.json")):
            est = json.loads((pasta / "estilo.json").read_text(encoding="utf-8"))
            for vid in est["variacoes"] if est["pecas"] else []:
                with tempfile.TemporaryDirectory(prefix="topclip-pecas-") as d:
                    proj = Path(d) / "p"
                    E._projeto_temporario(RAIZ, pasta, proj, vid)
                    r = subprocess.run([sys.executable, "-c", _CADA_PECA], cwd=proj,
                                       capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, f"{pasta.name}/{vid}:\n{r.stderr}")
                    for nome in est["pecas"]:
                        self.assertIn(nome, r.stdout, f"{pasta.name}/{vid}")
                    feitos += len(est["pecas"])
        self.assertGreaterEqual(feitos, 16)      # Limpo: 8 pecas x claro e escuro


class TestPecas(unittest.TestCase):
    def test_curvas(self):
        e = bezier(0, 0, 0.38, 0.9)
        self.assertEqual((e(0), e(1)), (0.0, 1.0))
        vals = [e(t / 20) for t in range(21)]
        self.assertEqual(vals, sorted(vals))
        self.assertGreater(bezier(0.34, 1.56, 0.64, 1)(0.6), 1.0)    # o energico passa do alvo
        self.assertEqual((lin(0, 2, 4), lin(3, 2, 4), lin(9, 2, 4)), (0.0, 0.5, 1.0))

    def test_numero_em_portugues(self):
        self.assertEqual(contador.formata(3000), "3.000")
        self.assertEqual(contador.formata(2.5, 1), "2,5")
        self.assertEqual(contador.formata(-1234567), "-1.234.567")

    def test_contador_cabe_na_largura(self):
        est = _estilo()
        im = contador.quadro(60, 0, 96, est, valor=1234567, prefixo="R$", sufixo="/ano")
        x0, _, x1, _ = im.getbbox()
        self.assertLessEqual(x1 - x0, 910)

    def test_erros_de_uso(self):
        est = _estilo()
        with self.assertRaises(ValueError):
            troca_palavra.quadro(10, 0, 90, est, palavras=["a", "b", "c"], trocas=[20])
        with self.assertRaises(ValueError):
            marca_texto.quadro(10, 0, 90, est, texto="x y", palavra="y", tipo="neon")

    def test_cores_de_reserva(self):
        """Estilo so com fundo/texto/acento ainda serve a toda peca."""
        r = E.resolver(LIMPO)
        r["cor"] = {k: r["cor"][k] for k in ("fundo", "texto", "acento")}
        est = P.Estilo(r, SKILL)
        self.assertEqual(est.hexa("superficie"), r["cor"]["fundo"])
        self.assertEqual(est.hexa("apoio"), r["cor"]["texto"])
        self.assertIn(est.hexa("sobre_acento"), ("#FFFFFF", "#111111"))


class TestLegenda(unittest.TestCase):
    def test_papel_fica_com_a_legenda_dele(self):
        self.assertIsNone(PL.para(None))
        self.assertIsNone(PL.para(_estilo(OFICIAIS / "papel")))
        self.assertIsNotNone(PL.para(_estilo()))

    def test_configura_os_blocos_sem_editar_o_captions(self):
        cap = types.SimpleNamespace(MAXPAL=3, ALVO=0.33, MAXDUR=0.62)
        PL.para(_estilo()).configura(cap)
        self.assertEqual((cap.MAXPAL, cap.ALVO, cap.MAXDUR), (4, 0.55, 1.045))

    def test_desenho_destaque_e_fade(self):
        leg = PL.para(_estilo())
        comum = leg.draw({"txt": "Quanto mais barato", "enf": False, "cor": None}, 99, 30, (1330, 1120))
        bb = comum.getbbox()
        self.assertTrue(bb and bb[1] >= 1050, bb)                # abaixo do queixo (teto 1120)
        # a etiqueta do Limpo: texto escuro numa caixa clara, legivel sobre camisa branca
        meio = comum.convert("RGB").getpixel(((bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2))
        self.assertGreater(sum(meio), 600)
        acento = (47, 107, 255)
        pilula = leg.draw({"txt": "piores", "enf": True, "cor": acento}, 99, 30, (1330, 1120))
        import numpy as np
        px = np.asarray(pilula.convert("RGB")).reshape(-1, 3)
        self.assertGreater(int((px == acento).all(axis=1).sum()), 1000)
        cedo = leg.draw({"txt": "Quanto mais barato", "enf": False, "cor": None}, 0, 30, (1330, 1120))
        self.assertLess(cedo.getchannel("A").getextrema()[1], comum.getchannel("A").getextrema()[1])
        self.assertEqual(leg.quadros_entrada(30), 4)


class TestLimpo(unittest.TestCase):
    def test_valida_e_resolve_as_duas_variacoes(self):
        erros, _ = E.validar(LIMPO)
        self.assertEqual(erros, [])
        claro, escuro = E.resolver(LIMPO, "claro"), E.resolver(LIMPO, "escuro")
        self.assertEqual(claro["cenas"], "overlay")
        self.assertIsNone(claro["boil"])
        self.assertEqual(claro["movimento"]["perfil"], "calmo")
        for r in (claro, escuro):
            self.assertGreaterEqual(E.contraste(r["cor"]["fundo"], r["cor"]["texto"]), 4.5)
        self.assertNotEqual(claro["cor"]["fundo"], escuro["cor"]["fundo"])

    def test_previa_gera_capas_e_pecas(self):
        with tempfile.TemporaryDirectory(prefix="topclip-previa-teste-") as d:
            copia = Path(d) / "limpo"
            shutil.copytree(LIMPO, copia, ignore=shutil.ignore_patterns("preview"))
            E.previa(copia, RAIZ)
            prev = copia / "preview"
            self.assertTrue((prev / "capa.png").exists())
            self.assertTrue((prev / "capa-escuro.png").exists())
            self.assertEqual(sorted(p.stem for p in (prev / "pecas").glob("*.png")),
                             sorted(json.loads((LIMPO / "estilo.json").read_text())["pecas"]))
            self.assertEqual(E.validar(copia)[0], [])


def _topclip(*args):
    return subprocess.run(["bash", str(RAIZ / "topclip"), *args], capture_output=True, text=True)


def _roda(args, cwd):
    r = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"{args} falhou:\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


class TestProjetoLimpo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="topclip-limpo-")
        cls.proj = Path(cls.tmp.name) / "motion"
        r = _topclip("motion", "novo", str(cls.proj), "--estilo", "limpo", "--variacao", "escuro")
        assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_1_compose_do_estilo_e_pecas_no_projeto(self):
        self.assertEqual((self.proj / "compose.py").read_text(), (LIMPO / "compose.py").read_text())
        self.assertIn("77, False),  # exemplo", (self.proj / "render.py").read_text())
        self.assertTrue((self.proj / "pecas" / "contador.py").exists())
        self.assertFalse((self.proj / "pecas" / "__pycache__").exists())
        self.assertIn("OK", _roda(["compose.py", "--check"], self.proj))
        out = _roda(["-c", "import compose as C\n"
                           "for s, (fn, st, fx) in C.SCENES.items():\n"
                           "    assert fx is None and fn(st['END'], overlay_only=True).getbbox(), s\n"
                           "    print(s)\n"], self.proj)
        for s in ("M1", "M4", "M8"):
            self.assertIn(s, out)

    def test_2_rascunho_com_cena_overlay_e_legenda_do_limpo(self):
        src = self.proj / "00_brief" / "fonte.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                        "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
        palavras = [{"w": "Isso", "t": 0.10, "e": 0.40}, {"w": "não", "t": 0.45, "e": 0.70},
                    {"w": "é", "t": 0.72, "e": 0.80}, {"w": "difícil.", "t": 0.82, "e": 1.15},
                    {"w": "Tchau", "t": 2.30, "e": 2.70}]
        (self.proj / "00_brief" / "transcript_palavras.json").write_text(json.dumps(palavras))
        r = self.proj / "render.py"
        s = r.read_text()
        for velho, novo in (("DUR = 55.4554", f"DUR = {dur}"),
                            ("FPS_NUM, FPS_DEN = 30000, 1001", "FPS_NUM, FPS_DEN = 30, 1"),
                            ('("M1", C.build_M1, 11.700, 14.900, 77, False)',
                             '("M1", C.build_M1, 1.200, 2.200, 24, False)')):
            self.assertEqual(s.count(velho), 1, velho)
            s = s.replace(velho, novo)
        r.write_text(s)
        out = _roda(["render.py", "--rascunho", "--jobs", "2"], self.proj)
        self.assertNotIn("DIFERE", out)
        self.assertTrue((self.proj / "12_master" / "RASCUNHO.mp4").exists())
        from PIL import Image
        quadros = sorted((self.proj / "10_sequences" / "M1").glob("*.png"))
        self.assertEqual(len(quadros), 30)
        # sem corte seco: o primeiro quadro da cena ainda deixa o video passar
        self.assertLess(Image.open(quadros[0]).getchannel("A").getextrema()[1], 128)
        # a legenda do Limpo (etiqueta) no bloco "Isso nao e dificil."
        cap = Image.open(self.proj / "10_sequences" / "CAP" / "0020.png")
        self.assertIsNotNone(cap.getbbox())

    def test_3_reinstalar_nao_apaga_as_cenas_escritas(self):
        compose = self.proj / "compose.py"
        compose.write_text(compose.read_text() + "\n# cenas do clipe, escritas a mao\n")
        antes = compose.read_text()
        E.instalar(LIMPO, self.proj, "claro", None)
        self.assertEqual(compose.read_text(), antes)
        self.assertEqual(json.loads((self.proj / "estilo" / "resolvido.json").read_text())["variacao"],
                         "claro")


if __name__ == "__main__":
    unittest.main()
