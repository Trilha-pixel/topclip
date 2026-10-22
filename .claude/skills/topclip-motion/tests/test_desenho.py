# -*- coding: utf-8 -*-
"""
O desenho dos estilos com lapis (fase 6): cada objeto sai em cada lapis, as receitas por
registro montam a cena, o objeto do usuario (minha-biblioteca/objetos.py) entra na lista,
o validador cobra o lapis, e a animacao propria do objeto segue a fala em qualquer estilo.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SKILL = Path(__file__).resolve().parent.parent
RAIZ = SKILL.parents[2]
OFICIAIS = RAIZ / "biblioteca" / "estilos"
sys.path.insert(0, str(SKILL / "lib"))
sys.path.insert(0, str(RAIZ / "biblioteca"))

import estilo as E  # noqa: E402
import meu_estilo as M  # noqa: E402
import pecas as P  # noqa: E402
from pecas import lapis as L, objeto, receitas as R  # noqa: E402
from pecas.base import quebra  # noqa: E402
from pecas.objetos import OBJETOS  # noqa: E402

LAPIS_DO = {"limpo": "limpo", "impacto": "impacto", "luxo": "luxo"}


def _estilo(nome, variacao=None):
    return P.Estilo(E.resolver(OFICIAIS / nome, variacao), SKILL)


class TestObjetosEmCadaLapis(unittest.TestCase):
    def test_todo_objeto_sai_em_todo_lapis(self):
        for nome_estilo, lapis in LAPIS_DO.items():
            est = _estilo(nome_estilo)
            self.assertEqual(est.r["lapis"], lapis)
            for nome, fn in OBJETOS.items():
                formas, altura, ancoras = fn(p=1.0)
                self.assertTrue(formas, nome)
                self.assertGreater(altura, 0, nome)
                for f in formas:
                    self.assertIn(f["papel"], ("corpo", "face", "detalhe", "destaque", "traco", "vazado"),
                                  nome)
                lay = L.desenha(formas, 300, altura, est, lapis, 1.0)
                self.assertIsNotNone(lay.getbbox(), f"{nome} no lapis {lapis}")

    def test_animacao_propria_comeca_e_termina(self):
        for nome, fn in OBJETOS.items():
            for p in (0.0, 0.5, 1.0):
                formas, _, _ = fn(p=p)
                self.assertIsInstance(formas, list, f"{nome} p={p}")

    def test_cada_lapis_tem_cor_para_cada_papel(self):
        for nome_estilo, lapis in LAPIS_DO.items():
            cores = L._cores(lapis, _estilo(nome_estilo))
            self.assertEqual(set(cores), {"corpo", "face", "detalhe", "destaque", "traco", "vazado"})

    def test_vazado_contrasta_com_o_disco_no_luxo(self):
        """O check do `marca` no luxo: o disco e latao, o check sai na cor do fundo."""
        est = _estilo("luxo")
        formas, altura, _ = OBJETOS["marca"](p=1.0)
        lay = L.desenha(formas, 300, altura, est, "luxo", 1.0)
        fundo = est.cor("fundo")[:3]
        px = [lay.getpixel((x, y))[:3] for x in range(lay.width) for y in range(lay.height)
              if lay.getpixel((x, y))[3] == 255]
        perto = [c for c in px if sum(abs(a - b) for a, b in zip(c, fundo)) < 30]
        self.assertGreater(len(perto), 50)

    def test_luxo_se_desenha(self):
        est = _estilo("luxo")
        formas, altura, _ = OBJETOS["relogio"](p=1.0)
        vazio = L.desenha(formas, 300, altura, est, "luxo", 0.0)
        meio = L.desenha(formas, 300, altura, est, "luxo", 0.4)
        cheio = L.desenha(formas, 300, altura, est, "luxo", 1.0)
        self.assertIsNone(vazio.getbbox())
        soma = lambda im: int(np.asarray(im.getchannel("A")).sum())
        self.assertLess(soma(meio), soma(cheio))

    def test_lapis_desconhecido(self):
        with self.assertRaises(ValueError):
            L.desenha([], 100, 1.0, _estilo("limpo"), "giz", 1.0)
        with self.assertRaises(ValueError):
            objeto.quadro(10, 0, 40, _estilo("limpo"), "nave_espacial")

    def test_folha_de_objetos(self):
        est = _estilo("impacto")
        f = objeto.folha(est, ["relogio", "alvo"], cel=200, cols=2)
        self.assertEqual(f.width, 400)
        self.assertIsNotNone(f.getbbox())


class TestPecaObjeto(unittest.TestCase):
    def test_animacao_propria_segue_a_fala_em_todo_estilo(self):
        """No meio da animacao, as barras tem a mesma altura em qualquer estilo: a curva
        energica do Impacto nao adianta o crescimento (a barra chega na palavra)."""
        alturas = {}
        for nome in LAPIS_DO:
            est = _estilo(nome)
            visto = {}
            original = OBJETOS["grafico_barras"]
            OBJETOS["grafico_barras"] = lambda p=1.0, **k: (visto.setdefault("p", p), original(p=p, **k))[1]
            try:
                objeto.quadro(30, 0, 200, est, "grafico_barras", anima_em=20, dur=20)
            finally:
                OBJETOS["grafico_barras"] = original
            alturas[nome] = visto["p"]
        self.assertEqual(set(alturas.values()), {0.5})

    def test_luxo_termina_de_desenhar_antes_da_saida(self):
        """Objeto que entra no fim da cena: o traco do luxo fecha antes da saida."""
        est = _estilo("luxo")
        fim = 60
        inicio = fim - int(est.q_saida) - int(est.q_entrada) - 2
        antes_da_saida = int(fim - est.q_saida)
        a = objeto.quadro(antes_da_saida, inicio, fim, est, "etiqueta_preco", centro=(540, 960))
        b = objeto.quadro(antes_da_saida, inicio - 200, fim, est, "etiqueta_preco", centro=(540, 960))
        self.assertEqual(a.getbbox(), b.getbbox())

    def test_fora_do_trecho_sai_vazio(self):
        est = _estilo("limpo")
        self.assertIsNone(objeto.quadro(5, 10, 40, est, "relogio").getbbox())
        self.assertIsNone(objeto.quadro(41, 10, 40, est, "relogio").getbbox())


class TestReceitas(unittest.TestCase):
    def test_cada_receita_em_cada_estilo(self):
        for nome in LAPIS_DO:
            est = _estilo(nome)
            cenas = {
                "objeto_em_destaque": R.objeto_em_destaque(70, 0, 96, est, "relogio", titulo="Madrugada",
                                                           etiqueta="MVP", de=(0, 0), ate=(3, 0)),
                "processo": R.processo(92, 0, 110, est, "etiqueta_preco", "pessoas", titulo="Atrai",
                                       params_para=dict(quantas=3, destaque=1),
                                       rotulos=("preço", "cliente")),
                "dado": R.dado(84, 0, 110, est, "grafico_barras", titulo="LTV", subtitulo="de novo",
                               rotulos=["1", "2", "3", "4"]),
            }
            for receita, im in cenas.items():
                self.assertEqual(im.size, (1080, 1920), receita)
                # cena de tela cheia: o fundo cobre o quadro inteiro no meio da cena
                self.assertEqual(im.getchannel("A").getextrema()[0], 255, f"{receita} em {nome}")

    def test_cenas_com_objeto_no_compose_de_cada_estilo(self):
        for nome in ("limpo", "impacto", "luxo"):
            txt = (OFICIAIS / nome / "compose.py").read_text(encoding="utf-8")
            for receita in ("R.objeto_em_destaque", "R.processo", "R.dado"):
                self.assertIn(receita, txt, nome)
        self.assertIn("R.dado", (RAIZ / "biblioteca" / "pecas" / "compose_modelo.py").read_text())


class TestObjetosDoUsuario(unittest.TestCase):
    def test_objetos_meus_entra_na_lista(self):
        molde = SKILL / "exemplo" / "objetos_usuario.py"
        with tempfile.TemporaryDirectory(prefix="topclip-objetos-") as d:
            (Path(d) / "objetos_meus.py").write_text(molde.read_text(encoding="utf-8"), encoding="utf-8")
            r = subprocess.run([sys.executable, "-c",
                                "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]\n"
                                "import pecas\n"
                                "print('xicara' in pecas.objeto.OBJETOS)",
                                d, str(RAIZ / "biblioteca")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "True")

    def test_molde_desenha_nos_tres_lapis(self):
        sys.path.insert(0, str(SKILL / "exemplo"))
        try:
            import objetos_usuario as U
        finally:
            sys.path.remove(str(SKILL / "exemplo"))
        for nome, fn in U.OBJETOS.items():
            formas, altura, _ = fn(p=1.0)
            for nome_estilo, lapis in LAPIS_DO.items():
                lay = L.desenha(formas, 200, altura, _estilo(nome_estilo), lapis, 1.0)
                self.assertIsNotNone(lay.getbbox(), f"{nome} no {lapis}")

    def test_motion_novo_copia_os_objetos_do_usuario(self):
        txt = (RAIZ / "topclip").read_text(encoding="utf-8")
        self.assertIn('"$ROOT/minha-biblioteca/objetos.py" "$destino/objetos_meus.py"', txt)


class TestValidadorELapis(unittest.TestCase):
    def test_oficiais_com_objeto_tem_lapis(self):
        for nome in ("limpo", "impacto", "luxo"):
            erros, _ = E.validar(OFICIAIS / nome, exigir_previa=False)
            self.assertEqual(erros, [], nome)
            self.assertTrue((OFICIAIS / nome / "preview" / "objetos.png").is_file(), nome)

    def test_lapis_invalido_e_objeto_sem_lapis(self):
        import json
        import shutil
        with tempfile.TemporaryDirectory(prefix="topclip-lapis-") as d:
            pasta = Path(d) / "teste"
            shutil.copytree(OFICIAIS / "limpo", pasta)
            tok = json.loads((pasta / "tokens.json").read_text())
            tok["$extensions"]["topclip"]["lapis"] = "giz"
            (pasta / "tokens.json").write_text(json.dumps(tok))
            erros, _ = E.validar(pasta, exigir_previa=False)
            self.assertTrue(any("lapis" in e for e in erros), erros)
            tok["$extensions"]["topclip"].pop("lapis")
            (pasta / "tokens.json").write_text(json.dumps(tok))
            erros, _ = E.validar(pasta, exigir_previa=False)
            self.assertTrue(any("peca objeto" in e for e in erros), erros)

    def test_ajustar_troca_o_lapis(self):
        d = {"estilo": {"variacoes": {}}, "tokens": {}, "legenda": {}}
        M._aplica(d, "lapis", "impacto")
        self.assertEqual(d["tokens"]["$extensions"]["topclip"]["lapis"], "impacto")
        M._aplica(d, "lapis", None)
        self.assertNotIn("lapis", d["tokens"]["$extensions"]["topclip"])


class TestQuebraEquilibrada(unittest.TestCase):
    def test_sem_palavra_orfa(self):
        est = _estilo("impacto")
        fonte = est.fonte("titulo", 60, 700)
        texto = "CLIENTE QUE COMPRA DE NOVO"
        guloso = quebra(fonte, texto, 880, equilibra=False)
        linhas = quebra(fonte, texto, 880)
        self.assertEqual(len(linhas), len(guloso))
        self.assertGreater(len(linhas[-1].split()), 1)
        self.assertEqual(" ".join(linhas), texto)

    def test_quebra_forcada_fica(self):
        fonte = _estilo("limpo").fonte("titulo", 60, 700)
        self.assertEqual(quebra(fonte, "um\ndois tres", 2000), ["um", "dois tres"])


if __name__ == "__main__":
    unittest.main()
