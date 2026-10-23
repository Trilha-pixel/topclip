# -*- coding: utf-8 -*-
"""
Posts virais: o negrito e a divisão das frases, o frases.json, a arte (tamanhos, recorte,
texto), a escolha dos prints e o estado que o painel grava. Nada aqui lê vídeo: os quadros
são imagens geradas na hora.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "lib"))

import arte as A  # noqa: E402
import frases as F  # noqa: E402
import prints as P  # noqa: E402
import projeto as PJ  # noqa: E402


def frase(**extra):
    base = {"id": "frase-001", "tipo": "contraste", "inicio": 10.0, "fim": 16.0, "original": "o trecho",
            "partes": {"2": ["Você não está **vendendo um site.**", "Está vendendo **confiança e resultado.**"]}}
    base.update(extra)
    return base


class Negrito(unittest.TestCase):
    def test_tokens_e_volta(self):
        t = "O resultado **vira consequência.**"
        self.assertEqual(F.tokens(t), [("O", False), ("resultado", False), ("vira", True), ("consequência.", True)])
        self.assertEqual(F.marcar(F.tokens(t)), t)

    def test_negrito_no_meio_e_no_comeco(self):
        t = "**Seja obcecado** pelo **processo.**"
        self.assertEqual(F.marcar(F.tokens(t)), t)
        self.assertEqual(F.limpo(t), "Seja obcecado pelo processo.")


class Divisao(unittest.TestCase):
    def test_divide_na_pontuacao(self):
        self.assertEqual(F.dividir("O Senhor é o meu pastor; nada me faltará.", 2),
                         ["O Senhor é o meu pastor;", "nada me faltará."])

    def test_tres_partes_sem_perder_palavra_nem_negrito(self):
        t = "Quanto **mais barato** você vende, **piores** são os seus clientes."
        partes = F.dividir(t, 3)
        self.assertEqual(len(partes), 3)
        self.assertEqual(" ".join(F.limpo(p) for p in partes), F.limpo(t))
        self.assertIn("**piores**", " ".join(partes))

    def test_poucas_palavras(self):
        self.assertEqual(F.dividir("Começa hoje.", 3), ["Começa", "hoje.", ""])

    def test_partes_para_usa_a_propria_ou_divide_outra(self):
        f = frase()
        self.assertEqual(F.partes_para(f, 2), f["partes"]["2"])
        tres = F.partes_para(f, 3)
        self.assertEqual(len(tres), 3)
        self.assertEqual(F.limpo(" ".join(tres)), F.limpo(" ".join(f["partes"]["2"])))
        self.assertEqual(len(F.partes_para({"id": "minha-1", "partes": {"1": ["Uma frase só, de teste."]}}, 2)), 2)

    def test_tempos_pelo_tamanho_ou_os_dados(self):
        ts = F.tempos_para(frase(), 2)
        self.assertEqual(len(ts), 2)
        self.assertTrue(10 < ts[0] < ts[1] < 16)
        self.assertEqual(F.tempos_para(frase(tempos={"2": [11, 15]}), 2), [11.0, 15.0])
        self.assertEqual(F.tempos_para({"partes": {"2": ["a", "b"]}}, 2), [])


class Conferir(unittest.TestCase):
    def test_frase_boa_passa_com_aviso_da_falta_do_3(self):
        frases, avisos = F.conferir({"frases": [frase()]})
        self.assertEqual(len(frases), 1)
        self.assertTrue(any("divisão em 3" in a for a in avisos))

    def test_erros_juntos(self):
        ruins = [frase(id="Frase 1"), frase(id="frase-002", partes={"2": ["só uma"]}),
                 frase(id="frase-003", inicio=20, fim=10), frase(id="frase-004", partes={"2": ["**aberto", "b"]})]
        with self.assertRaises(F.ErroFrases) as c:
            F.conferir({"frases": ruins})
        msg = str(c.exception)
        for trecho in ("Frase 1", "frase-002", "frase-003", "frase-004"):
            self.assertIn(trecho, msg)

    def test_id_repetido(self):
        with self.assertRaises(F.ErroFrases):
            F.conferir({"frases": [frase(), frase()]})

    def test_legenda_e_carrossel(self):
        _, avisos = F.conferir({"frases": [frase()]})
        self.assertTrue(any("sem legenda" in a for a in avisos))
        _, avisos = F.conferir({"frases": [frase(legenda="Texto. " + " ".join(f"#t{k}" for k in range(7)))],
                                "carrossel": {"capa": "5 verdades sobre **preço**", "legenda": "Arrasta."}})
        self.assertTrue(any("7 hashtags" in a for a in avisos))
        self.assertFalse(any("sem legenda" in a for a in avisos))
        with self.assertRaises(F.ErroFrases):
            F.conferir({"frases": [frase(legenda=["não é texto"])]})
        with self.assertRaises(F.ErroFrases):
            F.conferir({"frases": [frase()], "carrossel": {"capa": "**aberto"}})
        self.assertEqual(F.carrossel({"carrossel": {"capa": "  Título   **forte** ", "legenda": " "}}),
                         {"capa": "Título **forte**"})


def quadro(caminho: Path, w=1920, h=1080, cor=(120, 110, 100)):
    img = Image.new("RGB", (w, h), cor)
    img.save(caminho, quality=90)
    return caminho


class Arte(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="topclip-post-"))
        self.img = quadro(self.tmp / "q.jpg")
        self.rosto = [820, 300, 280, 360]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def painel(self, texto="Quanto **mais barato** você vende,"):
        return {"imagem": str(self.img), "rosto": self.rosto, "texto": texto}

    def test_tamanhos_de_cada_formato(self):
        self.assertEqual(A.montar([self.painel()] * 2).size, (1080, 1350))
        self.assertEqual(A.montar([self.painel()] * 3, formato="stories").size, (1080, 1920))
        self.assertEqual(A.montar([self.painel()], formato="stories", escala=0.5).size, (540, 960))

    def test_stories_deixa_o_pe_escuro_para_a_caixa_de_resposta(self):
        img = A.montar([self.painel()] * 3, formato="stories")
        pe = np.asarray(img.crop((0, 1920 - A.RESPIRO_STORIES + 10, 1080, 1920)))
        self.assertLess(pe.mean(), 30)

    def test_texto_branco_aparece_no_pe_do_print(self):
        img = np.asarray(A.montar([self.painel("**TESTE TESTE TESTE**"), self.painel("")]).convert("L"))
        faixa = img[480:675]                  # pé do primeiro print
        self.assertGreater(faixa.max(), 240)

    def test_sem_imagem_nao_quebra(self):
        self.assertEqual(A.montar([{"imagem": None, "texto": "só texto"}] * 2).size, (1080, 1350))

    def test_recorte_dentro_do_quadro_e_rosto_acima_do_texto(self):
        for pw, ph, livre in ((1080, 675, 0.78), (1080, 450, 0.6), (1080, 1350, 0.8), (1080, 556, 0.5)):
            x0, y0, x1, y1 = A.recorte(1920, 1080, pw, ph, self.rosto, livre=livre)
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, 1920.001)
            self.assertLessEqual(y1, 1080.001)
            self.assertAlmostEqual((x1 - x0) / (y1 - y0), pw / ph, places=2)

    def test_zoom_aproxima(self):
        a = A.recorte(1920, 1080, 1080, 675, self.rosto)
        b = A.recorte(1920, 1080, 1080, 675, self.rosto, zoom=1.4)
        self.assertLess(b[2] - b[0], a[2] - a[0])

    def test_texto_cabe_em_duas_linhas(self):
        fam = A.familia("inter")
        bloco = A.compor_texto("Na cabeça das pessoas, **se é caro, é bom.**", fam, 54, 1080 - 2 * A.MARGEM_LADO)
        self.assertLessEqual(len(bloco["linhas"]), 2)

    def test_fontes_do_kit_disponiveis(self):
        self.assertIn("inter", A.fontes_disponiveis())

    def test_pb_tira_a_cor_da_foto_e_nao_do_destaque(self):
        quadro(self.img, cor=(200, 40, 40))
        A._cache_img.clear()
        cor = np.asarray(A.montar([self.painel("")] * 2).convert("RGB")).astype(int)
        pb = np.asarray(A.montar([self.painel(""), self.painel("**DESTAQUE**")], pb=True, destaque="#FFD43B")).astype(int)
        saturacao = lambda a: (a.max(axis=2) - a.min(axis=2))
        self.assertGreater(saturacao(cor[:300]).mean(), 60)
        self.assertLess(saturacao(pb[:300]).mean(), 3)           # a foto ficou cinza
        self.assertGreater(saturacao(pb[675:]).max(), 100)        # o destaque amarelo continua

    def test_assinatura_no_pe_do_ultimo_print(self):
        sem = np.asarray(A.montar([self.painel("Uma parte."), self.painel("Outra parte.")]).convert("L")).astype(int)
        com = np.asarray(A.montar([self.painel("Uma parte."), self.painel("Outra parte.")], assinatura="@perfil").convert("L")).astype(int)
        self.assertEqual(np.abs(sem[:675] - com[:675]).max(), 0)  # o primeiro print não muda
        self.assertGreater(np.abs(sem[675:] - com[675:]).max(), 60)

    def test_capa_tem_um_print_so(self):
        img = A.montar([self.painel("5 verdades sobre **cobrar caro**")], capa=True)
        self.assertEqual(img.size, (1080, 1350))
        with self.assertRaises(ValueError):
            A.montar([self.painel()] * 2, capa=True)


class EscolherPrints(unittest.TestCase):
    def cand(self, pid, t, nota, tom=0.0, sorrindo=False):
        return {"id": pid, "t": t, "nota": nota, "sorrindo": sorrindo,
                "miniatura": np.full((16, 16), tom, np.float32)}

    def test_quadros_diferentes_e_perto_da_parte(self):
        cands = [self.cand("a", 10.0, 0.9, 0.2), self.cand("b", 10.3, 0.89, 0.2),
                 self.cand("c", 14.5, 0.8, 0.6), self.cand("d", 15.0, 0.7, 0.7)]
        ids = [c["id"] for c in P.escolher(cands, [10.5, 14.8], 2)]
        self.assertEqual(len(set(ids)), 2)
        self.assertIn(ids[0], ("a", "b"))               # os dois perto da 1ª parte
        self.assertIn(ids[1], ("c", "d"))               # e o 2º perto da 2ª, não o vizinho igual

    def test_espalhar_respeita_a_distancia(self):
        itens = [{"t": t, "nota": n} for t, n in ((1.0, 0.9), (1.2, 0.95), (3.0, 0.5))]
        self.assertEqual([i["t"] for i in P.espalhar(itens, 3, 0.6)], [1.2, 3.0])

    def test_do_banco_gira_para_cada_frase(self):
        quadros = {f"p-{k:04d}": {"t": k, "nota": 0.5, "miniatura": [k / 20] * 256} for k in range(1, 11)}
        doc = {"quadros": quadros, "banco": list(quadros)}
        a, b = P.do_banco(doc, 2, 0), P.do_banco(doc, 2, 1)
        self.assertEqual(len(a), 2)
        self.assertNotEqual(set(a), set(b))


class Estado(unittest.TestCase):
    def setUp(self):
        self.proj = Path(tempfile.mkdtemp(prefix="topclip-post-proj-"))
        (self.proj / "projeto.json").write_text(json.dumps({"nome": "t", "video": ""}))
        (self.proj / "posts").mkdir()
        (self.proj / "posts" / "frases.json").write_text(json.dumps({"frases": [frase()]}, ensure_ascii=False))
        quadro(self.proj / "posts" / "q1.jpg")
        quadro(self.proj / "posts" / "q2.jpg", cor=(40, 40, 40))
        doc = {"quadros": {"p-0001": {"t": 11, "arquivo": "q1.jpg", "mini": "q1.jpg", "rosto": [820, 300, 280, 360], "nota": 0.9},
                           "p-0002": {"t": 15, "arquivo": "q2.jpg", "mini": "q2.jpg", "rosto": [820, 300, 280, 360], "nota": 0.8}},
               "frases": {"frase-001": {"candidatos": ["p-0001", "p-0002"], "auto": {"2": ["p-0001", "p-0002"]}}},
               "banco": ["p-0002", "p-0001"]}
        (self.proj / "posts" / "prints.json").write_text(json.dumps(doc))

    def tearDown(self):
        shutil.rmtree(self.proj, ignore_errors=True)

    def test_padrao_feed_2_e_stories_3(self):
        e = PJ.ler_estado(self.proj)
        self.assertEqual((e["formato"], e["prints"]), ("feed", {"feed": 2, "stories": 3}))

    def test_valida_o_que_o_painel_manda(self):
        for ruim in ({"formato": "tiktok"}, {"prints": {"feed": 5}}, {"destaque": "amarelo"}, {"fonte": "comic-sans"}):
            with self.assertRaises(ValueError):
                PJ.salvar_estado(self.proj, ruim)
        e = PJ.salvar_estado(self.proj, {"formato": "stories", "destaque": "#ffd43b", "escolhidas": ["frase-001", "x x"]})
        self.assertEqual((e["formato"], e["destaque"], e["escolhidas"]), ("stories", "#FFD43B", ["frase-001"]))

    def test_edicao_vale_no_post(self):
        PJ.salvar_estado(self.proj, {"edicoes": {"frase-001": {
            "partes": {"2": ["Outro **texto**", "aqui"]}, "prints": {"2": ["p-0002", "p-0001"]},
            "ajustes": {"feed-2": [{"zoom": 9, "x": 0.1, "y": 0}, {}]}, "referencia": "Ref 1:1"}}})
        e = PJ.ler_estado(self.proj)
        m = PJ.montagem(self.proj, PJ.achar_frase(self.proj, "frase-001", e), e)
        self.assertEqual(m["partes"], ["Outro **texto**", "aqui"])
        self.assertEqual(m["prints"], ["p-0002", "p-0001"])
        self.assertEqual(m["paineis"][0]["zoom"], 3.0)          # o teto do zoom
        self.assertEqual(m["referencia"], "Ref 1:1")
        PJ.salvar_estado(self.proj, {"edicoes": {"frase-001": None}})
        m = PJ.montagem(self.proj, PJ.achar_frase(self.proj, "frase-001"), PJ.ler_estado(self.proj))
        self.assertEqual(m["prints"], ["p-0001", "p-0002"])

    def test_carrossel_so_no_feed(self):
        e = PJ.salvar_estado(self.proj, {"formato": "stories"})
        e = PJ.salvar_estado(self.proj, {"modo": "carrossel"})
        self.assertEqual((e["modo"], e["formato"]), ("carrossel", "feed"))
        e = PJ.salvar_estado(self.proj, {"formato": "stories"})
        self.assertEqual((e["modo"], e["formato"]), ("unico", "stories"))
        for ruim in ({"modo": "carrossel", "formato": "stories"}, {"modo": "slides"}, {"pb": "sim"}):
            with self.assertRaises(ValueError):
                PJ.salvar_estado(self.proj, ruim)

    def test_pb_e_assinatura_chegam_na_montagem(self):
        orig = PJ.arroba
        try:
            PJ.arroba = lambda: None
            with self.assertRaises(ValueError):               # sem @ na marca não liga a assinatura
                PJ.salvar_estado(self.proj, {"assinatura": True})
            PJ.arroba = lambda: "@perfil"
            e = PJ.salvar_estado(self.proj, {"assinatura": True, "pb": True})
            m = PJ.montagem(self.proj, PJ.achar_frase(self.proj, "frase-001", e), e)
            self.assertEqual((m["pb"], m["assinatura"]), (True, "@perfil"))
        finally:
            PJ.arroba = orig

    def test_arroba_da_marca(self):
        orig = PJ.MARCA
        try:
            PJ.MARCA = self.proj / "marca"
            PJ.MARCA.mkdir()
            for digitado, esperado in (("realfelipetop", "@realfelipetop"), ("@realfelipetop", "@realfelipetop"),
                                       ("https://instagram.com/real.felipe_top/", "@real.felipe_top"), ("", None), ("não é @", None)):
                (PJ.MARCA / "marca.json").write_text(json.dumps({"arroba": digitado}))
                self.assertEqual(PJ.arroba(), esperado, digitado)
        finally:
            PJ.MARCA = orig

    def test_legenda_do_claude_ou_a_editada(self):
        doc = {"frases": [frase(legenda="A do Claude.")], "carrossel": {"capa": "Título **forte**", "legenda": "A do carrossel."}}
        (self.proj / "posts" / "frases.json").write_text(json.dumps(doc, ensure_ascii=False))
        e = PJ.ler_estado(self.proj)
        f = PJ.achar_frase(self.proj, "frase-001", e)
        self.assertEqual(PJ.legenda_da_frase(f, e), "A do Claude.")
        e = PJ.salvar_estado(self.proj, {"edicoes": {"frase-001": {"legenda": "Minha.\r\n\nCom linhas."}}})
        self.assertEqual(PJ.legenda_da_frase(f, e), "Minha.\n\nCom linhas.")
        e = PJ.salvar_estado(self.proj, {"edicoes": {"frase-001": {"legenda": None}}})
        self.assertEqual(PJ.legenda_da_frase(f, e), "A do Claude.")
        with self.assertRaises(ValueError):
            PJ.salvar_estado(self.proj, {"legenda_carrossel": "x" * 2201})
        c = PJ.carrossel_do_projeto(self.proj, e)
        self.assertEqual((c["usar"], c["texto"], c["legenda"], c["print"]), (True, "Título **forte**", "A do carrossel.", "p-0002"))
        e = PJ.salvar_estado(self.proj, {"capa": {"usar": False, "texto": "Outro"}, "legenda_carrossel": "Minha do carrossel."})
        c = PJ.carrossel_do_projeto(self.proj, e)
        self.assertEqual((c["usar"], c["texto"], c["legenda"]), (False, "Outro", "Minha do carrossel."))

    def test_exporta_o_carrossel_na_ordem_com_capa_e_legenda(self):
        doc = {"frases": [frase(), frase(id="frase-002", partes={"2": ["Segunda **frase** aqui,", "com duas partes."]})],
               "carrossel": {"capa": "Duas **verdades**", "legenda": "Legenda do carrossel."}}
        (self.proj / "posts" / "frases.json").write_text(json.dumps(doc, ensure_ascii=False))
        e = PJ.salvar_estado(self.proj, {"modo": "carrossel", "escolhidas": ["frase-002", "frase-001"]})
        feitos = PJ.exportar_carrossel(self.proj, estado=e)
        self.assertEqual([p.name[:3] for p in feitos], ["01-", "02-", "03-"])
        self.assertEqual(feitos[0].name, "01-capa.png")
        self.assertTrue(feitos[1].name.startswith("02-segunda-frase"))
        self.assertEqual((feitos[0].parent / "legenda.txt").read_text(encoding="utf-8").strip(), "Legenda do carrossel.")
        for f in feitos:
            with Image.open(f) as img:
                self.assertEqual(img.size, (1080, 1350))
        # a ordem mudou e a capa saiu: os números velhos não ficam para trás
        e = PJ.salvar_estado(self.proj, {"capa": {"usar": False}, "escolhidas": ["frase-001"]})
        feitos = PJ.exportar_carrossel(self.proj, estado=e)
        self.assertEqual(sorted(p.name for p in feitos[0].parent.glob("*.png")), [feitos[0].name])
        self.assertTrue(feitos[0].name.startswith("01-voce-nao-esta"))

    def test_foto_propria_vira_print_e_sai(self):
        pasta = self.proj / "posts"
        pid = P.adicionar_foto(pasta, Image.new("RGB", (900, 1200), (90, 120, 150)))
        self.assertEqual(pid, "f-0001")
        doc = P.ler(pasta)
        self.assertEqual(doc["proprias"], ["f-0001"])
        self.assertTrue((pasta / "prints" / "f-0001.jpg").is_file() and (pasta / "prints" / "mini" / "f-0001.jpg").is_file())
        self.assertTrue(doc["quadros"]["f-0001"]["propria"])
        self.assertIn("p-0001", doc["quadros"])                 # os prints do vídeo continuam
        e = PJ.salvar_estado(self.proj, {"edicoes": {"frase-001": {"prints": {"2": ["f-0001", "p-0002"]}}}})
        m = PJ.montagem(self.proj, PJ.achar_frase(self.proj, "frase-001", e), e)
        self.assertEqual(m["prints"], ["f-0001", "p-0002"])
        self.assertEqual(PJ.renderizar(self.proj, PJ.achar_frase(self.proj, "frase-001", e), e).size, (1080, 1350))
        self.assertEqual(P.adicionar_foto(pasta, Image.new("RGB", (640, 480))), "f-0002")
        P.remover_foto(pasta, "f-0001")
        self.assertFalse((pasta / "prints" / "f-0001.jpg").exists())
        m = PJ.montagem(self.proj, PJ.achar_frase(self.proj, "frase-001", e), e)
        self.assertEqual(m["prints"], ["p-0001", "p-0002"])      # o post volta ao automático
        with self.assertRaises(P.ErroPrints):
            P.remover_foto(pasta, "p-0001")                       # print do vídeo não se apaga por aqui
        with self.assertRaises(P.ErroPrints):
            P.adicionar_foto(pasta, Image.new("RGB", (120, 90)))

    def test_frase_da_pessoa_usa_o_banco_e_renderiza(self):
        e = PJ.salvar_estado(self.proj, {"minhas": [{"id": "minha-1", "partes": {"1": ["O Senhor é o meu pastor; nada me faltará."]}}],
                                         "escolhidas": ["minha-1"]})
        f = PJ.achar_frase(self.proj, "minha-1", e)
        m = PJ.montagem(self.proj, f, e)
        self.assertEqual(m["partes"], ["O Senhor é o meu pastor;", "nada me faltará."])
        self.assertEqual(len(m["prints"]), 2)
        feitos = PJ.exportar(self.proj)
        self.assertEqual(len(feitos), 1)
        with Image.open(feitos[0]) as img:
            self.assertEqual(img.size, (1080, 1350))
