"""Testes do painel. Rodam com ./topclip testes."""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import servidor as S


class Utilidades(unittest.TestCase):
    def test_slug_sem_acento_nem_espaco(self):
        self.assertEqual(S.slug("Podcast com a Ána — ep. 12!"), "podcast-com-a-ana-ep-12")
        self.assertEqual(S.slug("   "), "projeto")

    def test_quadros_na_ordem_da_cena(self):
        nomes = ["M1_END.png", "M1_EXIT.png", "M1_MID.png", "M1_START.png", "M2_START.png"]
        ordem = [p.name for p in sorted((Path(n) for n in nomes), key=S.ordem_do_quadro)]
        self.assertEqual(ordem, ["M1_START.png", "M1_MID.png", "M1_END.png", "M1_EXIT.png", "M2_START.png"])

    def test_dentro_barra_caminho_que_escapa(self):
        self.assertTrue(S.dentro(S.PROJETOS / "x" / "a.mp4", S.PROJETOS))
        self.assertFalse(S.dentro(S.PROJETOS / ".." / "README.md", S.PROJETOS))


class ComProjetosTemporarios(unittest.TestCase):
    """Troca projetos/ por uma pasta temporária: os testes nunca tocam nos do usuário."""

    def setUp(self):
        # dentro do repositório (e apagada no fim): só assim /midia consegue enderecá-la
        self.tmp = Path(tempfile.mkdtemp(dir=S.RAIZ, prefix=".teste-painel-"))
        self._orig = S.PROJETOS
        S.PROJETOS = self.tmp / "projetos"
        S.PROJETOS.mkdir()

    def tearDown(self):
        S.PROJETOS = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)


class Projetos(ComProjetosTemporarios):
    def test_criar_projeto_e_salvar_escolhas(self):
        r = S.criar_projeto("Meu Podcast", "/caminho/que/nao/existe.mp4")
        self.assertEqual(r["slug"], "meu-podcast")
        self.assertIsNotNone(r["aviso"])                       # vídeo inexistente avisa, não quebra
        proj = S.PROJETOS / "meu-podcast"
        self.assertTrue((proj / "runs").is_dir())
        info = json.loads((proj / "projeto.json").read_text())
        self.assertEqual(info["nome"], "Meu Podcast")

        S.salvar_escolhas(proj, {"momentos": ["moment-001"], "lixo": "ignorado"})
        S.salvar_escolhas(proj, {"cortes": ["clip-002"]})      # salvar cortes não apaga momentos
        esc = json.loads((proj / "escolhas.json").read_text())
        self.assertEqual(esc["momentos"], ["moment-001"])
        self.assertEqual(esc["cortes"], ["clip-002"])
        self.assertNotIn("lixo", esc)

    def test_nome_repetido_nao_sobrescreve(self):
        S.criar_projeto("Repetido", "")
        with self.assertRaises(ValueError):
            S.criar_projeto("Repetido", "")

    def test_etapas_deduzidas_dos_arquivos(self):
        S.criar_projeto("Etapas", "")
        proj = S.PROJETOS / "etapas"
        run = proj / "runs" / "r1"
        run.mkdir(parents=True)
        (run / "00-manifest.json").write_text("{}")
        (run / "05-viral-moments.json").write_text('{"moments": []}')
        m = proj / "motion" / "clipe"
        (m / "12_master").mkdir(parents=True)
        (m / "compose.py").write_text("")
        et = S.etapas(proj, S.run_mais_recente(proj))
        self.assertEqual(et["momentos"], "feito")
        self.assertEqual(et["motion"], "andamento")          # projeto sem master ainda não é "feito"
        (m / "12_master" / "final.mp4").write_bytes(b"x")
        self.assertEqual(S.etapas(proj, S.run_mais_recente(proj))["motion"], "feito")


class Http(ComProjetosTemporarios):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Painel)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def pedir(self, caminho, cabecalhos=None, dados=None):
        req = urllib.request.Request(self.base + caminho, headers=cabecalhos or {},
                                     data=json.dumps(dados).encode() if dados is not None else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_video_responde_a_range(self):
        S.criar_projeto("Video", "")
        alvo = S.PROJETOS / "video" / "entregas" / "a.mp4"
        alvo.write_bytes(bytes(range(256)) * 4)                # 1024 bytes
        status, cab, corpo = self.pedir(S.url_midia(alvo), {"Range": "bytes=10-19"})
        self.assertEqual(status, 206)
        self.assertEqual(cab["Content-Range"], "bytes 10-19/1024")
        self.assertEqual(corpo, (bytes(range(256)) * 4)[10:20])

    def test_midia_fora_das_pastas_permitidas_e_proibida(self):
        for caminho in ("/midia/README.md", "/midia/../README.md", "/midia/.claude/skills/topclip/SKILL.md",
                        "/fontes/../../../README.md", "/static/../servidor.py"):
            status, _, _ = self.pedir(caminho)
            self.assertIn(status, (403, 404), caminho)

    def test_post_de_outra_origem_e_recusado(self):
        status, _, _ = self.pedir("/api/projetos", {"Origin": "https://site-malicioso.com",
                                                    "Content-Type": "application/json"},
                                  {"nome": "invasao", "video": ""})
        self.assertEqual(status, 403)
        self.assertFalse((S.PROJETOS / "invasao").exists())

    def test_api_lista_projetos(self):
        S.criar_projeto("Listado", "")
        status, _, corpo = self.pedir("/api/projetos")
        self.assertEqual(status, 200)
        self.assertEqual([p["slug"] for p in json.loads(corpo)["projetos"]], ["listado"])

    def test_host_estranho_e_recusado(self):
        """DNS rebinding: um site que aponte o próprio domínio para 127.0.0.1 chega com outro Host."""
        status, _, _ = self.pedir("/api/projetos", {"Host": "site-malicioso.com"})
        self.assertEqual(status, 403)


class NotaEstimada(ComProjetosTemporarios):
    """A nota do gate aparece já nos momentos — não só no fim, quando não dá mais para trocar."""

    def setUp(self):
        super().setUp()
        S.criar_projeto("Notas", "")
        self.proj = S.PROJETOS / "notas"
        self.run = self.proj / "runs" / "r1"
        (self.run / "preview").mkdir(parents=True)
        (self.run / "00-manifest.json").write_text("{}")

    def escrever(self, nome, dados):
        (self.run / nome).write_text(json.dumps(dados), encoding="utf-8")

    def test_momentos_em_ordem_de_nota(self):
        self.escrever("05-viral-moments.json", {"estimate_gate": 7.5, "moments": [
            {"id": "moment-001", "start": 10, "end": 70, "quote": "a"},          # sem nota: vai para o fim
            {"id": "moment-002", "start": 80, "end": 140, "quote": "b", "publishability_estimate": 6.547,
             "estimate_below_gate": ["se sustenta sozinho 6 < 7"]},
            {"id": "moment-003", "start": 150, "end": 200, "quote": "c", "publishability_estimate": 7.802,
             "estimate_below_gate": []},
        ]})
        d = S.detalhe(self.proj)
        self.assertEqual([m["id"] for m in d["momentos"]], ["moment-003", "moment-002", "moment-001"])
        self.assertEqual(d["momentos"][0]["nota"], 7.8)
        self.assertEqual(d["momentos"][1]["abaixo_do_gate"], ["se sustenta sozinho 6 < 7"])
        self.assertIsNone(d["momentos"][2]["nota"])
        self.assertEqual(d["gate"], 7.5)

    def test_corte_mostra_a_nota_do_gate_e_acha_a_previa_pelo_id(self):
        # 06 refeito só com os 2 escolhidos: a posição 01 agora é o clip-005, não o clip-003 da rodada velha
        self.escrever("06-candidates.json", {"clips": [
            {"id": "clip-005", "title": "x", "publishability_estimate": 6.852,
             "estimate_below_gate": ["nota 6,85 < 7,5"], "scores": {"hook": 9}},
            {"id": "clip-010", "title": "y", "scores": {"hook": 8, "payoff": 6}},
        ]})
        for nome in ("01-clip-003-velho.mp4", "05-clip-005-mensalidade.mp4", "10-clip-010-barato.mp4"):
            (self.run / "preview" / nome).write_bytes(b"x")
        cortes = {c["id"]: c for c in S.detalhe(self.proj)["cortes"]}
        self.assertTrue(cortes["clip-005"]["preview"].endswith("05-clip-005-mensalidade.mp4"))
        self.assertTrue(cortes["clip-010"]["preview"].endswith("10-clip-010-barato.mp4"))
        self.assertEqual((cortes["clip-005"]["nota"], cortes["clip-005"]["nota_do_gate"]), (6.9, True))
        self.assertEqual((cortes["clip-010"]["nota"], cortes["clip-010"]["nota_do_gate"]), (7.0, False))  # run antiga: média

    def test_previa_sem_id_no_nome_casa_pela_posicao(self):
        previas = [Path("01-clip-003-velho.mp4"), Path("02-feita-a-mao.mp4")]
        self.assertIsNone(S.previa_do_corte(previas, ["clip-005", "clip-010"], 1))   # 01 é de outro corte
        self.assertEqual(S.previa_do_corte(previas, ["clip-005", "clip-010"], 2), Path("02-feita-a-mao.mp4"))

    def test_painel_redesenha_quando_a_nota_entra(self):
        import os
        self.escrever("05-viral-moments.json", {"moments": [{"id": "moment-001"}]})
        antes = S._assinatura(self.proj, self.run)
        self.escrever("05-viral-moments.json", {"moments": [{"id": "moment-001", "publishability_estimate": 7.9}]})
        st = (self.run / "05-viral-moments.json").stat()
        os.utime(self.run / "05-viral-moments.json", ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
        self.assertNotEqual(S._assinatura(self.proj, self.run), antes)


class CortesJaFeitos(ComProjetosTemporarios):
    """Fez 2 de 14, postou, volta depois para o resto: o painel mostra quais já saíram."""

    def setUp(self):
        super().setUp()
        S.criar_projeto("Parcial", "")
        self.proj = S.PROJETOS / "parcial"
        self.run = self.proj / "runs" / "r1"
        self.run.mkdir(parents=True)
        (self.run / "00-manifest.json").write_text("{}")
        (self.run / "05-viral-moments.json").write_text(json.dumps({"moments": [
            {"id": f"moment-{i:03d}"} for i in (1, 5, 10, 11)]}))
        (self.run / "06-candidates.json").write_text(json.dumps({"clips": [
            {"id": f"clip-{i:03d}", "moment_id": f"moment-{i:03d}"} for i in (1, 5, 10, 11)]}))

    def test_entrega_e_pronto_vertical_sem_entrega_e_andamento(self):
        (self.proj / "entregas" / "clip-010-quanto-mais-barato.mp4").write_bytes(b"x")
        vert = self.run / "output" / "final-clips" / "dinheiro" / "clip-005-mensalidade"
        vert.mkdir(parents=True)
        (vert / "clip-vertical.mp4").write_bytes(b"x")
        (self.proj / "motion" / "clip-0011").mkdir(parents=True)        # outro id: não é o clip-001
        d = S.detalhe(self.proj)
        cortes = {c["id"]: c["feito"] for c in d["cortes"]}
        self.assertEqual(cortes, {"clip-001": None, "clip-005": "andamento", "clip-010": "pronto", "clip-011": None})
        momentos = {m["id"]: m["feito"] for m in d["momentos"]}
        self.assertEqual((momentos["moment-010"], momentos["moment-005"], momentos["moment-001"]),
                         ("pronto", "andamento", None))
        self.assertEqual((d["n_cortes"], d["n_prontos"]), (4, 1))

    def test_entregue_conta_mesmo_se_o_06_foi_refeito_sem_ele(self):
        (self.proj / "entregas" / "clip-010-quanto-mais-barato.mp4").write_bytes(b"x")
        (self.proj / "entregas" / "clip-099-sem-corte-no-06.mp4").write_bytes(b"x")
        r = S.resumo(self.proj)
        self.assertEqual((r["n_cortes"], r["n_prontos"]), (5, 2))


class LocalizarVideo(ComProjetosTemporarios):
    """O vídeo arrastado para a página: só nome e tamanho chegam ao servidor."""

    def test_acha_pelo_nome_e_tamanho(self):
        pasta = self.tmp / "Downloads" / "podcasts"
        pasta.mkdir(parents=True)
        (pasta / "ep12.mp4").write_bytes(b"x" * 100)
        r = S.localizar_video("ep12.mp4", 100, pastas=[self.tmp / "Downloads"])
        self.assertEqual(r.get("caminho"), str(pasta / "ep12.mp4"))

    def test_mesmo_nome_tamanho_diferente_nao_serve(self):
        (self.tmp / "a").mkdir()
        (self.tmp / "b").mkdir()
        (self.tmp / "a" / "ep.mp4").write_bytes(b"x" * 10)
        (self.tmp / "b" / "ep.mp4").write_bytes(b"x" * 99)
        r = S.localizar_video("ep.mp4", 99, pastas=[self.tmp])
        self.assertEqual(r.get("caminho"), str(self.tmp / "b" / "ep.mp4"))

    def test_recusa_o_que_nao_e_video_e_caminho_disfarcado(self):
        self.assertIn("erro", S.localizar_video("senhas.txt", 10, pastas=[self.tmp]))
        r = S.localizar_video("../../etc/passwd.mp4", 10, pastas=[self.tmp])   # só o nome conta
        self.assertIn("erro", r)

    def test_nao_achou_avisa(self):
        self.assertIn("erro", S.localizar_video("sumiu.mp4", 5, pastas=[self.tmp]))


if __name__ == "__main__":
    unittest.main()


class Atividade(ComProjetosTemporarios):
    """O diário que diz se o TopClip está mesmo trabalhando."""

    def setUp(self):
        super().setUp()
        self._orig_atv = S.ATV.PROJETOS
        S.ATV.PROJETOS = S.PROJETOS
        S.criar_projeto("Diario", "")
        self.proj = S.PROJETOS / "diario"

    def tearDown(self):
        S.ATV.PROJETOS = self._orig_atv
        super().tearDown()

    def test_projeto_novo_espera_o_claude(self):
        self.assertEqual(S.atividade(self.proj)["estado"], "esperando_claude")

    def test_acha_o_projeto_pelos_argumentos(self):
        acha = S.ATV.achar_projeto
        self.assertEqual(acha(["init", "/x/v.mp4", "--workspace", "projetos/diario/runs"]), self.proj)
        self.assertEqual(acha(["digest", "--run", f"{S.PROJETOS}/diario/runs/r1"]), self.proj)
        self.assertIsNone(acha(["preflight"]))
        self.assertIsNone(acha(["--run", "projetos/nao-existe/runs/r1"]))

    def test_comando_rodando_com_processo_vivo(self):
        import os
        S.ATV.main(["inicio", str(self.proj), "id1", str(os.getpid()), "corte", "prepare", "--run", "projetos/diario/runs/r"])
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "rodando")
        self.assertIn("transcrevendo", a["rodando"]["msg"])

    def test_processo_que_sumiu_vira_interrompido(self):
        S.ATV.main(["inicio", str(self.proj), "id2", "999999", "corte", "render"])
        a = S.atividade(self.proj)
        self.assertNotEqual(a["estado"], "rodando")
        self.assertEqual(a["eventos"][0]["tipo"], "erro")
        self.assertIn("interrompido", a["eventos"][0]["msg"])

    def test_fim_com_erro_e_com_sucesso(self):
        S.ATV.main(["fim", str(self.proj), "id3", "1", "75", "corte", "render"])
        S.ATV.main(["fim", str(self.proj), "id4", "0", "3700", "corte", "subtitles"])
        msgs = [e["msg"] for e in S.atividade(self.proj)["eventos"]]
        self.assertTrue(any("falhou (código 1) depois de 1min 15s" in m for m in msgs))
        self.assertTrue(any("pronto em 1h 01min" in m for m in msgs))

    def test_sua_vez_e_depois_avisar_o_claude(self):
        run = self.proj / "runs" / "r1"
        run.mkdir(parents=True)
        (run / "00-manifest.json").write_text("{}")
        (run / "05-viral-moments.json").write_text('{"moments": [{"id": "moment-001"}]}')
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "sua_vez")
        self.assertEqual(S.resumo(self.proj)["etapa_atual"], "momentos")
        S.salvar_escolhas(self.proj, {"momentos": ["moment-001"]})
        self.assertEqual(S.atividade(self.proj)["estado"], "avisar_claude")

    def test_progresso_vai_para_a_manchete_do_comando_rodando(self):
        import os
        S.ATV.main(["inicio", str(self.proj), "id5", str(os.getpid()), "corte", "prepare", "--run", "projetos/diario/runs/r"])
        for pct in (10, 20, 30):
            S.ATV.registrar(self.proj, f"transcrevendo ({pct}%)", tipo="progresso", pct=pct)
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "rodando")
        self.assertEqual((a["rodando"]["progresso"], a["rodando"]["pct"]), ("transcrevendo (30%)", 30))
        self.assertFalse([e for e in a["eventos"] if e["tipo"] == "progresso"])   # não entope a lista

    def test_progresso_sem_comando_fica_so_o_mais_recente(self):
        for pct in (10, 20, 30):
            S.ATV.registrar(self.proj, f"transcrevendo ({pct}%)", tipo="progresso", pct=pct)
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "ativo")
        self.assertEqual([e["msg"] for e in a["eventos"] if e["tipo"] == "progresso"], ["transcrevendo (30%)"])
        self.assertEqual(a["eventos"][0]["msg"], "transcrevendo (30%)")
        S.ATV.registrar(self.proj, "transcrição pronta", tipo="info")   # depois dela, o progresso sai
        a = S.atividade(self.proj)
        self.assertEqual(a["eventos"][0]["msg"], "transcrição pronta")
        self.assertFalse([e for e in a["eventos"] if e["tipo"] == "progresso"])

    def _fase2(self, momentos_com_nota=True):
        """Run na fase 2: momentos prontos, 06 e prévias ainda por escrever."""
        self.run = self.proj / "runs" / "r1"
        (self.run / "preview").mkdir(parents=True)
        (self.run / "00-manifest.json").write_text("{}")
        momentos = {"moments": [{"id": "moment-001"}, {"id": "moment-002"}]}
        if momentos_com_nota:                       # a fase 1 nova passa pelo `estimate`
            momentos["estimate_gate"] = 7.5
        self.gravar("05-viral-moments.json", momentos, ha_s=900)

    def gravar(self, nome, dados, ha_s):
        import os
        import time
        p = self.run / nome
        if isinstance(dados, bytes):
            p.write_bytes(dados)
        else:
            p.write_text(json.dumps(dados), encoding="utf-8")
        os.utime(p, (time.time() - ha_s,) * 2)

    def assert_ainda_nao(self):
        a = S.atividade(self.proj)
        self.assertIsNone(a["sua_vez"])
        self.assertIn(a["estado"], ("ativo", "parado"))
        self.assertEqual(S.resumo(self.proj)["etapa_atual"], "cortes")   # e não "vertical"

    def test_cortes_sem_nota_ainda_nao_e_a_vez_dela(self):
        self._fase2()
        cortes = {"clips": [{"id": "clip-001", "scores": {"hook": 8}}, {"id": "clip-002", "scores": {"hook": 7}}]}
        self.gravar("06-candidates.json", cortes, ha_s=600)               # Clip Builder
        self.gravar("preview/01-clip-001-x.mp4", b"x", ha_s=500)
        self.assert_ainda_nao()
        # revisões de volta e o rebuild correndo (subagente: não é processo)
        self.gravar("07-feed-review.json", {"reviews": []}, ha_s=300)
        self.gravar("09-blind-review.json", {"reviews": []}, ha_s=300)
        self.assert_ainda_nao()
        # nota só em parte dos cortes
        cortes["clips"][0]["publishability_estimate"] = 7.8
        self.gravar("06-candidates.json", cortes, ha_s=60)
        self.assert_ainda_nao()

    def test_cortes_com_nota_em_todos_e_a_vez_dela(self):
        self._fase2()
        self.gravar("08-technical-audit.json", {}, ha_s=500)
        self.gravar("preview/01-clip-001-x.mp4", b"x", ha_s=450)
        self.gravar("07-feed-review.json", {"reviews": []}, ha_s=300)
        self.gravar("09-blind-review.json", {"reviews": []}, ha_s=300)
        cortes = {"estimate_gate": 7.5, "clips": [{"id": "clip-001", "publishability_estimate": 7.8},
                                                  {"id": "clip-002", "publishability_estimate": 6.9}]}
        self.gravar("06-candidates.json", cortes, ha_s=60)                # `estimate --cortes`
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "sua_vez")
        self.assertEqual(a["sua_vez"]["etapa"], "cortes")
        # pediu para refazer um: o rebuild regrava o 06 com a nota velha, e a auditoria vem depois
        self.gravar("08-technical-audit.json", {}, ha_s=10)
        self.assert_ainda_nao()

    def test_run_antiga_sem_nota_fica_como_era(self):
        # de antes do `estimate`: a nota nunca vai chegar, e o aviso não pode sumir para sempre
        self._fase2(momentos_com_nota=False)
        self.gravar("06-candidates.json", {"clips": [{"id": "clip-001", "scores": {"hook": 8}}]}, ha_s=600)
        self.assertEqual(S.atividade(self.proj)["sua_vez"]["etapa"], "cortes")     # como o exemplo antigo
        self.gravar("07-feed-review.json", {"reviews": []}, ha_s=300)
        self.gravar("09-blind-review.json", {"reviews": []}, ha_s=700)
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "sua_vez")
        self.assertEqual(a["sua_vez"]["etapa"], "cortes")
        self.assertEqual(S.etapas(self.proj, self.run)["cortes"], "feito")

    def test_anotar_nunca_quebra(self):
        S.ATV.registrar(self.tmp / "nao-existe", "x")          # pasta inexistente: ignora
        self.assertEqual(S.ATV.main(["fim", "lixo"]), 0)       # argumentos faltando: ignora


class ApagarProjeto(ComProjetosTemporarios):
    """A Lixeira de verdade fica fora dos testes: `para_lixeira` só move para uma pasta temporária."""
    pedir = Http.pedir

    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Painel)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.lixeira = self.tmp / "lixeira"
        self.lixeira.mkdir()
        self._orig_lixeira = S.para_lixeira
        S.para_lixeira = lambda p: shutil.move(str(p), str(self.lixeira / p.name))
        S.criar_projeto("Criado Errado", "")
        self.proj = S.PROJETOS / "criado-errado"

    def tearDown(self):
        S.para_lixeira = self._orig_lixeira
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def apagar(self, slug="criado-errado", origem=None):
        cab = {"Content-Type": "application/json", **({"Origin": origem} if origem else {})}
        return self.pedir(f"/api/projetos/{slug}/apagar", cab, {})

    def test_vai_para_a_lixeira_e_some_da_lista(self):
        status, _, _ = self.apagar(origem=self.base)
        self.assertEqual(status, 200)
        self.assertFalse(self.proj.exists())
        self.assertTrue((self.lixeira / "criado-errado" / "projeto.json").exists())   # dá para recuperar
        self.assertEqual(json.loads(self.pedir("/api/projetos")[2])["projetos"], [])

    def test_nao_apaga_com_o_topclip_rodando(self):
        import os
        S.ATV.main(["inicio", str(self.proj), "id1", str(os.getpid()), "corte", "prepare"])
        status, _, corpo = self.apagar()
        self.assertEqual(status, 400)
        self.assertIn("trabalhando neste projeto", json.loads(corpo)["erro"])
        self.assertTrue(self.proj.exists())

    def test_outra_origem_e_projeto_inexistente_nao_apagam(self):
        self.assertEqual(self.apagar(origem="https://site-malicioso.com")[0], 403)
        self.assertEqual(self.apagar("nao-existe")[0], 404)
        self.assertEqual(self.apagar("..")[0], 404)
        self.assertTrue(self.proj.exists())

    def test_lixeira_que_falha_avisa_e_nao_finge_que_apagou(self):
        def falha(p):
            raise ValueError("Não consegui mandar para a Lixeira: sem permissão")
        S.para_lixeira = falha
        status, _, corpo = self.apagar()
        self.assertEqual(status, 400)
        self.assertIn("sem permissão", json.loads(corpo)["erro"])
        S.para_lixeira = lambda p: None                       # o comando "deu certo" e a pasta ficou
        self.assertIn("não saiu do lugar", json.loads(self.apagar()[2])["erro"])

    def test_avisa_quando_o_video_mora_no_projeto(self):
        self.assertFalse(S.detalhe(self.proj)["video_no_projeto"])
        S.criar_projeto("Baixado", str(S.PROJETOS / "baixado" / "video.mp4"))
        self.assertTrue(S.detalhe(S.PROJETOS / "baixado")["video_no_projeto"])


class ProgressoDasEtapas(ComProjetosTemporarios):
    """A barra de % de cada etapa e o log separado por etapa."""

    def setUp(self):
        super().setUp()
        self._orig_atv = S.ATV.PROJETOS
        S.ATV.PROJETOS = S.PROJETOS
        S.criar_projeto("Barra", "")
        self.proj = S.PROJETOS / "barra"
        self.run = self.proj / "runs" / "r1"
        self.run.mkdir(parents=True)
        (self.run / "00-manifest.json").write_text("{}")

    def tearDown(self):
        S.ATV.PROJETOS = self._orig_atv
        super().tearDown()

    def etapas(self):
        return S.atividade(self.proj)["etapas"]

    def test_momentos_somam_os_passos_e_so_fecham_no_05(self):
        self.assertEqual(self.etapas()["momentos"]["estado"], "andamento")
        (self.run / "01-media.json").write_text("{}")
        (self.run / "02-transcript.json").write_text("{}")
        (self.run / "02-digest.md").write_text("")
        (self.run / "04-context-map.json").write_text("{}")
        m = self.etapas()["momentos"]
        self.assertEqual(m["pct"], 65)                      # 2 + 3 + 33 + 2 + 25
        self.assertEqual([p["nome"] for p in m["passos"] if not p["feito"]],
                         ["momentos encontrados (Clip Hunter)", "nota estimada de cada momento"])
        (self.run / "05-viral-moments.json").write_text('{"moments": []}')
        m = self.etapas()["momentos"]
        self.assertEqual((m["pct"], m["estado"]), (100, "feito"))
        self.assertTrue(all(p["feito"] for p in m["passos"]))   # fechada: run antiga sem a nota não fica pela metade

    def test_comando_rodando_enche_o_passo_dele(self):
        import os
        ident = "id-prep"
        S.ATV.main(["inicio", str(self.proj), ident, str(os.getpid()), "corte", "prepare", "--run", "projetos/barra/runs/r1"])
        os.environ[S.ATV.ENV_ID] = ident
        try:
            S.ATV.Progresso(self.run, "transcrevendo", etapa="momentos")(50, 100)
        finally:
            del os.environ[S.ATV.ENV_ID]
        a = S.atividade(self.proj)
        self.assertEqual((a["rodando"]["pct"], a["rodando"]["etapa"], a["rodando"]["sub"]), (50, "momentos", "prepare"))
        transcricao = next(p for p in a["etapas"]["momentos"]["passos"] if p["nome"].startswith("transcrição"))
        self.assertEqual(transcricao, {"nome": "transcrição palavra a palavra", "feito": False, "pct": 50})
        self.assertEqual(a["etapas"]["momentos"]["pct"], 18)      # 2 + metade de 33 = 18,5

    def test_dois_comandos_em_paralelo_cada_um_com_a_sua_barra(self):
        import os
        for clipe, pct in (("clip-001", 30), ("clip-002", 80)):
            m = self.proj / "motion" / clipe
            (m / "12_master").mkdir(parents=True)
            (m / "compose.py").write_text("")
            ident = f"id-{clipe}"
            S.ATV.main(["inicio", str(self.proj), ident, str(os.getpid()), "py", str(m / "render.py")])
            S.ATV.registrar(self.proj, f"quadros ({pct}%)", tipo="progresso", pct=pct, id=ident, etapa="motion")
        a = S.atividade(self.proj)
        self.assertEqual(sorted((r["clipe"], r["pct"]) for r in a["rodando_todos"]), [("clip-001", 30), ("clip-002", 80)])
        itens = {i["nome"]: i["pct"] for i in a["etapas"]["motion"]["itens"]}
        self.assertEqual(itens, {"clip-001": 10, "clip-002": 23})   # 3 de criado + 25 de master × pct
        self.assertEqual(a["etapas"]["motion"]["estado"], "andamento")
        (self.proj / "motion" / "clip-001" / "12_master" / "RASCUNHO.mp4").write_bytes(b"x")
        self.assertEqual(self.etapas()["motion"]["estado"], "andamento")   # rascunho não é master
        for clipe in ("clip-001", "clip-002"):
            (self.proj / "motion" / clipe / "12_master" / "MASTER_v01.mp4").write_bytes(b"x")
        self.assertEqual(self.etapas()["motion"]["pct"], 100)

    def test_vertical_so_fecha_com_todos_os_aprovados_renderizados(self):
        (self.run / "05-viral-moments.json").write_text('{"moments": [{"id": "moment-001"}]}')
        S.salvar_escolhas(self.proj, {"momentos": ["moment-001"], "cortes": ["clip-001", "clip-002"]})
        (self.run / "13-final-clips.json").write_text(json.dumps({"clips": [
            {"id": "clip-001", "status": "APPROVED"}, {"id": "clip-002", "status": "APPROVED"},
            {"id": "clip-003", "status": "REJECT"}]}))
        v = self.run / "output" / "final-clips" / "ctx" / "clip-001-x"
        v.mkdir(parents=True)
        (v / "clip-vertical.mp4").write_bytes(b"x")
        vert = self.etapas()["vertical"]
        self.assertEqual(vert["estado"], "andamento")
        render = next(p for p in vert["passos"] if p["nome"] == "clipes renderizados")
        self.assertEqual((render["pct"], render["detalhe"]), (50, "1 de 2"))
        self.assertEqual(S.resumo(self.proj)["etapa_atual"], "vertical")   # não pula para o motion no 1º clipe

    def test_log_separado_por_etapa(self):
        S.ATV.registrar(self.proj, "Context Mapper lendo o vídeo")                 # sem etapa: herda
        (self.run / "05-viral-moments.json").write_text('{"moments": [{"id": "moment-001"}]}')
        S.salvar_escolhas(self.proj, {"momentos": ["moment-001"]})
        S.ATV.registrar(self.proj, "Clip Builder montando os cortes")              # depois da escolha: cortes
        S.ATV.main(["registrar", str(self.proj), "info", "--etapa", "vertical", "Edit Director planejando"])
        S.ATV.main(["inicio", str(self.proj), "x", "999999", "corte", "estimate", "--cortes", "--run", "r"])
        etapa = {e["msg"]: e["etapa"] for e in S.atividade(self.proj)["eventos"]}
        self.assertEqual(etapa["Context Mapper lendo o vídeo"], "momentos")
        self.assertEqual(etapa["você escolheu 1 momento no painel"], "momentos")
        self.assertEqual(etapa["Clip Builder montando os cortes"], "cortes")
        self.assertEqual(etapa["Edit Director planejando"], "vertical")
        self.assertEqual(etapa["dando a nota estimada de cada corte — interrompido"], "cortes")

    def test_classificar_o_comando(self):
        c = S.ATV.classificar(["py", "projetos/barra/motion/clip-005/render.py", "--rascunho"])
        self.assertEqual((c["sub"], c["etapa"], c["clipe"]), ("render.py:rascunho", "motion", "clip-005"))
        self.assertTrue(c["msg"].startswith("clip-005: montando o rascunho"))
        self.assertEqual(S.ATV.classificar(["corte", "validate-artifact", "--run", "r", "--file", "11-edit-plans.json"])["etapa"], "vertical")
        self.assertEqual(S.ATV.classificar(["corte", "digest", "--run", "r", "--windows", "1-2"])["etapa"], "cortes")
        self.assertIsNone(S.ATV.classificar(["corte", "bordas", "--run", "r"])["etapa"])

    def test_progresso_pula_anuncio_em_cima_de_anuncio(self):
        relogio = iter([0.0, 1.0, 5.0, 6.0]).__next__
        prog = S.ATV.Progresso(self.run, "renderizando", etapa="vertical", intervalo_s=4, relogio=relogio)
        for feito in (0, 1, 2, 3):          # t=0 passa, t=1 não, t=5 passa, t=6 é o fim: passa
            prog(feito, 3)
        diario = [json.loads(l) for l in (self.proj / "atividade.jsonl").read_text().splitlines()]
        self.assertEqual([e["pct"] for e in diario if e["tipo"] == "progresso"], [0, 66, 100])
        self.assertEqual([e["msg"] for e in S.ATV.ler(self.proj) if e["tipo"] == "progresso"],
                         ["renderizando: 3 de 3 (100%)"])                    # o diário lido guarda só o último
        S.ATV.Progresso(self.tmp / "fora", "x")(1, 2)                        # fora de projetos/: não anota, não quebra
