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

    def test_anotar_nunca_quebra(self):
        S.ATV.registrar(self.tmp / "nao-existe", "x")          # pasta inexistente: ignora
        self.assertEqual(S.ATV.main(["fim", "lixo"]), 0)       # argumentos faltando: ignora
