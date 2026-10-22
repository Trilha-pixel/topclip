# -*- coding: utf-8 -*-
"""
Fase 5, o estilo do usuario: remixar, ajustar, aprovar, exportar, importar, apagar, a
paleta e a amostra. Tudo numa raiz falsa (biblioteca/ e .claude/ apontam para o
repositorio; minha-biblioteca/ e temporaria): os testes nunca tocam na do Felipe.
"""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "lib"))

import estilo as E  # noqa: E402
import meu_estilo as M  # noqa: E402
from PIL import Image  # noqa: E402


class _Raiz(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="topclip-meu-")
        self.raiz = Path(self.tmp.name) / "repo"
        self.raiz.mkdir()
        for nome in ("biblioteca", ".claude"):
            (self.raiz / nome).symlink_to(RAIZ / nome)

    def tearDown(self):
        self.tmp.cleanup()

    def remix(self, base="limpo", novo="minha-marca", **kw):
        return M.remixar(self.raiz, base, novo, **kw)


class TestRemixarEAjustar(_Raiz):
    def test_remix_nasce_rascunho_nos_seus(self):
        p = self.remix(nome="Minha marca")
        self.assertEqual(p, self.raiz / "minha-biblioteca" / "estilos" / "minha-marca")
        est = json.loads((p / "estilo.json").read_text())
        self.assertEqual((est["id"], est["nome"], est["origem"], est["versao"]),
                         ("minha-marca", "Minha marca", "meu", "0.1.0"))
        self.assertTrue(est["remix_de"].startswith("limpo@"))
        self.assertEqual(E.validar(p, exigir_previa=False)[0], [])

    def test_remix_recusa_id_ruim_oficial_ou_repetido(self):
        for novo in ("Com Espaço", "limpo"):
            with self.assertRaises(M.ErroEstilo):
                self.remix(novo=novo)
        self.remix()
        with self.assertRaises(M.ErroEstilo):
            self.remix()

    def test_ajustar_aplica_valida_e_sobe_versao(self):
        self.remix()
        v, _ = M.ajustar(self.raiz, "minha-marca", [
            "cor.acento=#FF5A1F", "fonte.titulo=Archivo Black", "energia=energico",
            "tipografia.caixa_alta=true", "tipografia.peso.titulo=800", "legenda.corpo=70",
            "bom_para=vendas, cursos", "variacao.laranja.cor.acento=#FF8800"])
        self.assertEqual(v, "0.1.1")
        r = E.resolver(self.raiz / "minha-biblioteca" / "estilos" / "minha-marca")
        self.assertEqual(r["cor"]["acento"], "#FF5A1F")
        self.assertEqual(r["energia"], "energico")
        self.assertEqual(r["movimento"]["perfil"], "energico")
        self.assertTrue(r["tipografia"]["caixa_alta"])
        self.assertEqual(r["legenda"]["corpo"], 70)
        est = json.loads((self.raiz / "minha-biblioteca/estilos/minha-marca/estilo.json").read_text())
        self.assertEqual(est["bom_para"], ["vendas", "cursos"])
        self.assertIn("laranja", est["variacoes"])

    def test_ajuste_errado_nao_muda_nada(self):
        p = self.remix()
        antes = (p / "tokens.json").read_text()
        for pares in (["cor.acento=laranja"], ["chave.que.nao.existe=1"], ["sem-igual"]):
            with self.assertRaises(M.ErroEstilo):
                M.ajustar(self.raiz, "minha-marca", pares)
        self.assertEqual((p / "tokens.json").read_text(), antes)
        self.assertEqual(json.loads((p / "estilo.json").read_text())["versao"], "0.1.0")

    def test_oficial_nao_se_ajusta_nem_apaga(self):
        for f in (lambda: M.ajustar(self.raiz, "limpo", ["cor.acento=#000000"]),
                  lambda: M.apagar(self.raiz, "papel")):
            with self.assertRaises(M.ErroEstilo):
                f()


class TestAprovarExportarImportar(_Raiz):
    def test_ciclo_completo(self):
        p = self.remix(base="impacto", novo="vendas")
        M.ajustar(self.raiz, "vendas", ["cor.acento=#FF5A1F"])
        v, _ = M.aprovar(self.raiz, "vendas")
        self.assertEqual(v, "1.0.0")
        self.assertTrue((p / "preview" / "capa.png").exists())
        self.assertEqual(E.validar(p)[0], [])
        self.assertEqual(M.aprovar(self.raiz, "vendas")[0], "1.1.0")

        arq = M.exportar(self.raiz, "vendas", Path(self.tmp.name) / "saida")
        self.assertEqual(arq.name, "vendas.topclip-estilo")
        with zipfile.ZipFile(arq) as z:
            nomes = z.namelist()
            est = json.loads(z.read("vendas/estilo.json"))
        self.assertFalse(any(n.endswith(".py") for n in nomes))       # o compose fica
        self.assertEqual((est["codigo"], est["origem"]), (False, "comunidade"))

        M.apagar(self.raiz, "vendas")
        self.assertFalse(p.exists())
        q = M.importar(self.raiz, arq)
        self.assertEqual(q, p)
        est = json.loads((q / "estilo.json").read_text())
        self.assertEqual((est["origem"], est["codigo"], est["versao"]), ("comunidade", False, "1.1.0"))
        with self.assertRaises(M.ErroEstilo):
            M.importar(self.raiz, arq)                                # ja existe
        M.importar(self.raiz, arq, substituir=True)

        # estilo overlay importado (sem codigo) recebe as cenas-modelo das pecas
        proj = Path(self.tmp.name) / "proj"
        E._projeto_temporario(self.raiz, q, proj, "amarelo")
        self.assertEqual((proj / "compose.py").read_text(),
                         (RAIZ / "biblioteca" / "pecas" / "compose_modelo.py").read_text())
        r = subprocess.run([sys.executable, "compose.py", "--check"], cwd=proj,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_importar_recusa_arquivo_perigoso(self):
        base = Path(self.tmp.name)

        def zipa(nome, itens):
            arq = base / nome
            with zipfile.ZipFile(arq, "w") as z:
                for n, conteudo in itens.items():
                    z.writestr(n, conteudo)
            return arq

        casos = {
            "fuga.topclip-estilo": {"x/../../fora.json": "{}"},
            "absoluto.topclip-estilo": {"/etc/x.json": "{}"},
            "codigo.topclip-estilo": {"x/estilo.json": "{}", "x/compose.py": "import os"},
            "duas.topclip-estilo": {"a/estilo.json": "{}", "b/estilo.json": "{}"},
        }
        for nome, itens in casos.items():
            with self.assertRaises(M.ErroEstilo, msg=nome):
                M.importar(self.raiz, zipa(nome, itens))
        (base / "nao-zip.topclip-estilo").write_text("oi")
        with self.assertRaises(M.ErroEstilo):
            M.importar(self.raiz, base / "nao-zip.topclip-estilo")
        # pacote com o nome de um oficial nao entra
        arq = M.exportar(self.raiz, "limpo", base / "oficial")
        with self.assertRaises(M.ErroEstilo):
            M.importar(self.raiz, arq)
        self.assertFalse((self.raiz / "minha-biblioteca" / "estilos" / "limpo").exists())

    def test_apagar_o_padrao_volta_para_o_papel(self):
        self.remix()
        pref = self.raiz / "minha-biblioteca" / "preferencias.json"
        pref.write_text(json.dumps({"estilo": "minha-marca", "variacao": "claro"}))
        M.apagar(self.raiz, "minha-marca")
        self.assertFalse(pref.exists())


class TestPaletaEAmostra(_Raiz):
    def test_paleta_acha_as_cores_e_sugere_com_contraste(self):
        im = Image.new("RGB", (300, 300), "#F4F1EA")
        for x in range(0, 300):
            for y in range(200, 300):
                im.putpixel((x, y), (255, 90, 31) if x < 150 else (20, 20, 20))
        f = Path(self.tmp.name) / "print.png"
        im.save(f)
        r = M.paleta([f], n=3)
        self.assertEqual(len(r["cores"]), 3)
        self.assertEqual(r["sugestao"]["fundo"][:3], "#F4")
        self.assertGreaterEqual(r["contraste"]["texto"], 4.5)
        a = r["sugestao"]["acento"]
        self.assertGreater(int(a[1:3], 16), 200)                       # o laranja
        with self.assertRaises(M.ErroEstilo):
            M.paleta([Path(self.tmp.name) / "nao-existe.png"])

    def test_amostra_num_quadro_do_video(self):
        video = Path(self.tmp.name) / "v.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=1080x1920:rate=30", "-t", "1", "-pix_fmt", "yuv420p",
                        str(video)], check=True)
        saida = M.amostra(self.raiz, ["impacto", "luxo:marfim"], video, 0.5,
                          Path(self.tmp.name) / "a.png")
        with Image.open(saida) as im:
            self.assertGreater(im.width, im.height)                    # duas, lado a lado
        um = M.amostra(self.raiz, ["limpo"], video, 0.5, Path(self.tmp.name) / "b.png")
        with Image.open(um) as im:
            self.assertEqual(im.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
