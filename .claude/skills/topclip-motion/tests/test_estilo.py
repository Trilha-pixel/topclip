# -*- coding: utf-8 -*-
"""
Estilos: o pacote do Papel, o validador, a resolucao estilo <- variacao <- marca, o
`motion novo --estilo` e a regressao que garante o Papel identico quadro a quadro.
"""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
PAPEL = RAIZ / "biblioteca" / "estilos" / "papel"
sys.path.insert(0, str(SKILL / "lib"))

import captions as CAP  # noqa: E402
import estilo as E  # noqa: E402
import motor as V  # noqa: E402
from PIL import Image  # noqa: E402


def _hex(rgb):
    return "#%02X%02X%02X" % rgb


def _literal(arquivo, nome):
    """O valor de `nome = <literal>` num arquivo, sem importar (importar o kit cria pastas)."""
    arvore = ast.parse(Path(arquivo).read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and any(
                getattr(t, "id", None) == nome or getattr(t, "attr", None) == nome for t in no.targets):
            return ast.literal_eval(no.value) if not isinstance(no.value, ast.Call) else {
                k.arg: ast.literal_eval(k.value) for k in no.value.keywords}
    raise KeyError(nome)


class TestPapel(unittest.TestCase):
    def test_pacote_valido(self):
        erros, _ = E.validar(PAPEL)
        self.assertEqual(erros, [])

    def test_valores_iguais_aos_do_motor(self):
        r = E.resolver(PAPEL)
        for nome, const in {"fundo": V.PAPER, "fundo_claro": V.PAPER_LIGHT, "texto": V.INK,
                            "carvao": V.CHARCOAL, "acento": V.YELLOW, "apoio": V.BLUE,
                            "destaque": V.RED, "fita": V.TAPE}.items():
            self.assertEqual(r["cor"][nome], _hex(const), nome)
        for nome, const in {"titulo": V.F_COND, "mao": V.F_MARKER, "mono": V.F_MONO,
                            "numero": V.F_SERIF, "apoio": V.F_SANS, "impacto": V.F_BLACK,
                            "contraponto": V.F_PLAY, "serifa_italica": V.F_ITAL}.items():
            self.assertEqual(Path(r["fonte"][nome]).name, Path(const).name, nome)
        fx_kit = _literal(SKILL / "lib" / "kit.py", "FX_DESK")
        fx_render = _literal(SKILL / "lib" / "render_template.py", "FX_DESK")
        a = r["acabamento"]
        for fx_t in (fx_kit, fx_render):
            self.assertEqual(fx_t, dict(grain=a["grao"], vignette=a["vinheta"],
                                        chroma=a["aberracao"], sat=a["saturacao"]))
        self.assertEqual(r["boil"], _literal(SKILL / "lib" / "render_template.py", "BOIL_SCALE"))

    def test_legenda_igual_a_do_captions(self):
        leg = E.resolver(PAPEL)["legenda"]
        self.assertEqual(leg["corpo"], CAP.CORPO)
        self.assertAlmostEqual(leg["enfase"], CAP.ENFASE / CAP.CORPO, places=2)
        self.assertEqual(leg["palavras_por_bloco"], CAP.MAXPAL)
        self.assertEqual(leg["cor"], _hex(CAP.BRANCO))
        self.assertEqual(leg["destaque"], _hex(CAP.VERMELHO))
        self.assertEqual(Path(leg["fonte"]).name, Path(V.F_BLACK).name)
        self.assertEqual(Path(leg["fonte_enfase"]).name, Path(V.F_PLAY).name)


class _ComPacote(unittest.TestCase):
    """Cada teste ganha uma copia do Papel numa pasta temporaria para estragar."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="topclip-estilo-")
        self.p = Path(self.tmp.name) / "teste"
        shutil.copytree(PAPEL, self.p)
        self.mexe("estilo.json", id="teste")

    def tearDown(self):
        self.tmp.cleanup()

    def mexe(self, arquivo, **campos):
        f = self.p / arquivo
        d = json.loads(f.read_text(encoding="utf-8"))
        d.update(campos)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d

    def erros(self):
        return "\n".join(E.validar(self.p)[0])


class TestValidador(_ComPacote):
    def test_copia_limpa_passa(self):
        self.assertEqual(self.erros(), "")

    def test_id_diferente_da_pasta(self):
        self.mexe("estilo.json", id="outro")
        self.assertIn("diferente do nome da pasta", self.erros())

    def test_comunidade_sem_codigo(self):
        self.mexe("estilo.json", origem="comunidade", codigo=True)
        self.assertIn("comunidade nao pode ter codigo", self.erros())

    def test_arquivo_executavel(self):
        (self.p / "cena.py").write_text("print('oi')")
        self.assertIn("executavel", self.erros())

    def test_fonte_sem_licenca(self):
        (self.p / "fontes").mkdir()
        shutil.copy(SKILL / "fontes" / "ArchivoBlack-Regular.ttf", self.p / "fontes")
        self.assertIn("sem arquivo de licenca", self.erros())
        shutil.copy(SKILL / "fontes" / "OFL-ArchivoBlack.txt", self.p / "fontes")
        self.assertNotIn("licenca", self.erros())

    def test_asset_sem_alfa(self):
        (self.p / "assets").mkdir()
        Image.new("RGB", (8, 8), "white").save(self.p / "assets" / "CHAPADO.png")
        Image.new("RGBA", (8, 8)).save(self.p / "assets" / "OK.png")
        e = self.erros()
        self.assertIn("CHAPADO.png", e)
        self.assertNotIn("OK.png", e)

    def test_lottie_com_expression(self):
        (self.p / "lottie").mkdir()
        (self.p / "lottie" / "LICENCA.txt").write_text("Lottie Simple License")
        (self.p / "lottie" / "mexe.json").write_text(json.dumps(
            {"layers": [{"ks": {"p": {"a": 0, "k": [0, 0], "x": "wiggle(3, 60)"}}}]}))
        (self.p / "lottie" / "parado.json").write_text(json.dumps(
            {"layers": [{"ks": {"p": {"a": 1, "k": [{"t": 0, "o": {"x": [0.2]}}]}}}]}))
        e = self.erros()
        self.assertIn("mexe.json usa expressions", e)
        self.assertNotIn("parado.json", e)

    def test_cor_e_fonte_invalidas(self):
        tok = json.loads((self.p / "tokens.json").read_text())
        tok["cor"]["acento"]["$value"] = "amarelo"
        tok["fonte"]["titulo"]["$value"] = "Comic Sans"
        (self.p / "tokens.json").write_text(json.dumps(tok))
        e = self.erros()
        self.assertIn("'cor.acento' = 'amarelo'", e)
        self.assertIn("Comic Sans", e)

    def test_peca_slot_e_variacao_desconhecidos(self):
        self.mexe("estilo.json", pecas=["contador", "holograma"], slots_da_marca=["cor.neon"],
                  variacoes={"a": {"nome": "A", "tokens": {"cor.nada": "#000000"}}})
        e = self.erros()
        self.assertIn("holograma", e)
        self.assertIn("cor.neon", e)
        self.assertIn("cor.nada", e)
        self.assertNotIn("'contador'", e)

    def test_legenda_e_capa(self):
        self.mexe("legenda.json", animacao="explode", corpo=12)
        (self.p / "preview" / "capa.png").unlink()
        e = self.erros()
        self.assertIn("legenda.animacao", e)
        self.assertIn("legenda.corpo", e)
        self.assertIn("preview/capa.png", e)


class TestResolucao(_ComPacote):
    def setUp(self):
        super().setUp()
        self.mexe("estilo.json",
                  variacoes={"a": {"nome": "A", "tokens": {}},
                             "b": {"nome": "B", "tokens": {"cor.acento": "#112233"}}},
                  slots_da_marca=["cor.acento", "cor.texto", "fonte.titulo", "logo"])
        (self.p / "fontes").mkdir()
        shutil.copy(SKILL / "fontes" / "ArchivoBlack-Regular.ttf", self.p / "fontes")
        shutil.copy(SKILL / "fontes" / "OFL-ArchivoBlack.txt", self.p / "fontes")
        tok = json.loads((self.p / "tokens.json").read_text())
        tok["fonte"]["apoio"]["$value"] = "fontes/ArchivoBlack-Regular.ttf"
        (self.p / "tokens.json").write_text(json.dumps(tok))
        self.mexe("legenda.json", fonte="fonte.apoio")
        self.marca = Path(self.tmp.name) / "marca"
        self.marca.mkdir()
        Image.new("RGBA", (10, 10)).save(self.marca / "logo.png")

    def poe_marca(self, **m):
        (self.marca / "marca.json").write_text(json.dumps(m))

    def test_variacao_e_fonte_do_pacote(self):
        self.assertEqual(E.validar(self.p)[0], [])
        a, b = E.resolver(self.p, "a"), E.resolver(self.p, "b")
        self.assertEqual(a["cor"]["acento"], "#DBD653")
        self.assertEqual(b["cor"]["acento"], "#112233")
        self.assertEqual(a["variacao"], "a")
        self.assertEqual(a["fonte"]["apoio"], "estilo/fontes/ArchivoBlack-Regular.ttf")
        self.assertEqual(a["legenda"]["fonte"], "estilo/fontes/ArchivoBlack-Regular.ttf")
        self.assertEqual(a["fonte"]["titulo"], "fontes/ArchivoNarrow[wght].ttf")
        with self.assertRaises(SystemExit):
            E.resolver(self.p, "c")

    def test_marca_so_nos_slots_e_com_contraste(self):
        self.poe_marca(cores={"primaria": "#FF0000", "secundaria": "#00FF00", "texto": "#EEEEEE"},
                       logo="logo.png")
        r = E.resolver(self.p, "b", self.marca)
        self.assertEqual(r["cor"]["acento"], "#FF0000")       # marca vence a variacao
        self.assertEqual(r["cor"]["apoio"], "#2E82F7")        # cor.apoio nao e slot
        self.assertEqual(r["cor"]["texto"], "#373639")        # #EEE sobre o papel nao le
        self.assertEqual([x["slot"] for x in r["marca"]["recusado"]], ["cor.texto"])
        self.assertEqual(r["marca"]["logo"], "estilo/marca/logo.png")
        self.assertIn("cor.acento", r["marca"]["aplicado"])

    def test_marca_neutra_nao_vira_acento(self):
        """Branco, preto ou cinza na primaria: o estilo fica com o acento dele (o branco do
        formulario apagava o amarelo do Impacto e a janela acesa sumia no desenho)."""
        for neutra in ("#FFFFFF", "#000000", "#808080", "#F4F4F2"):
            self.poe_marca(cores={"primaria": neutra}, logo="logo.png")
            r = E.resolver(self.p, "a", self.marca)
            self.assertEqual(r["cor"]["acento"], "#DBD653", neutra)
            self.assertEqual([x["slot"] for x in r["marca"]["recusado"]], ["cor.acento"], neutra)
        self.poe_marca(cores={"primaria": "#E04A10"}, logo="logo.png")
        self.assertEqual(E.resolver(self.p, "a", self.marca)["cor"]["acento"], "#E04A10")

    def test_sem_slots_marca_nao_entra(self):
        self.mexe("estilo.json", slots_da_marca=[])
        self.poe_marca(cores={"primaria": "#FF0000"}, logo="logo.png")
        r = E.resolver(self.p, None, self.marca)
        self.assertEqual(r["cor"]["acento"], "#DBD653")
        self.assertEqual(r["marca"], {"aplicado": [], "recusado": [], "logo": None})

    def test_contraste_wcag(self):
        self.assertAlmostEqual(E.contraste("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(E.contraste("#777777", "#FFFFFF"), 4.48, places=2)


def _topclip(*args):
    return subprocess.run(["bash", str(RAIZ / "topclip"), *args], capture_output=True, text=True)


class TestMotionNovo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="topclip-novo-")
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_padrao_e_papel_congelado_no_projeto(self):
        r = _topclip("motion", "novo", str(self.base / "p"))
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads((self.base / "p" / "estilo" / "resolvido.json").read_text())
        self.assertEqual((res["id"], res["variacao"]), ("papel", "marfim"))
        self.assertFalse((self.base / "p" / "estilo" / "preview").exists())
        self.assertTrue((self.base / "p" / "estilo.py").exists())

    def test_estilo_ou_variacao_errados_nao_criam_nada(self):
        for args in (["--estilo", "nao-existe"], ["--estilo", "papel", "--variacao", "kraft"]):
            alvo = self.base / args[-1]
            r = _topclip("motion", "novo", str(alvo), *args)
            self.assertEqual(r.returncode, 2, args)
            self.assertFalse(alvo.exists(), args)

    def test_listar_e_validar(self):
        r = _topclip("estilo", "listar")
        self.assertIn("papel", r.stdout)
        self.assertEqual(_topclip("estilo", "validar", "papel").returncode, 0)


# Renderiza o END de duas cenas do Papel e devolve o MD5 de cada quadro.
_MD5 = (
    "import hashlib, compose as C\n"
    "for s in ('M1', 'R1'):\n"
    "    fn, st, fx = C.SCENES[s]\n"
    "    im = C.finish(fn(st['END']), **fx)\n"
    "    print(s, C.V.BOIL_SCALE, hashlib.md5(im.tobytes()).hexdigest())\n")


class TestRegressaoPapel(unittest.TestCase):
    """O Papel tem que sair byte a byte igual com e sem o estilo resolvido no projeto."""

    def test_quadro_identico(self):
        with tempfile.TemporaryDirectory(prefix="topclip-regressao-") as d:
            com, sem = Path(d) / "com", Path(d) / "sem"
            self.assertEqual(_topclip("motion", "novo", str(com)).returncode, 0)
            shutil.copytree(com, sem)
            shutil.rmtree(sem / "estilo")       # projeto de antes dos estilos
            saidas = []
            for proj in (com, sem):
                r = subprocess.run([sys.executable, "-c", _MD5], cwd=proj,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                saidas.append(r.stdout.split("\n"))
            self.assertEqual(saidas[0], saidas[1])
            self.assertEqual(len([l for l in saidas[0] if l]), 2)


if __name__ == "__main__":
    unittest.main()
