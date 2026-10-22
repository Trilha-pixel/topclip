"""Testes do download por link (YouTube, Instagram). Sem rede: o yt-dlp nunca é chamado."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import baixar as B
import servidor as S


class Links(unittest.TestCase):
    def test_reconhece_link_e_site(self):
        self.assertTrue(B.eh_link("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(B.eh_link("  https://youtu.be/abc  "))
        self.assertFalse(B.eh_link("youtube.com/watch?v=abc"))
        self.assertFalse(B.eh_link("--exec=rm"))                   # nunca vira opção do yt-dlp
        self.assertFalse(B.eh_link("https://x.com/a b"))
        self.assertEqual(B.site("https://youtu.be/abc"), "YouTube")
        self.assertEqual(B.site("https://m.youtube.com/watch?v=abc"), "YouTube")
        self.assertEqual(B.site("https://www.instagram.com/reel/abc/"), "Instagram")

    def test_duracao_e_tamanho_em_portugues(self):
        self.assertEqual(B.duracao_txt(257), "4min17s")
        self.assertEqual(B.duracao_txt(5400), "1h30")
        self.assertEqual(B.duracao_txt(None), "")
        self.assertEqual(B._mb(98_000), "98 KB")
        self.assertEqual(B._mb(5_200_000), "5,2 MB")
        self.assertEqual(B._mb(2_300_000_000), "2,3 GB")

    def test_titulo_do_reel_vem_da_legenda_do_post(self):
        reel = {"title": "Video by fulano", "channel": "fulano", "description": "Como eu edito meus vídeos #ia @x"}
        self.assertEqual(B.titulo_do_video(reel, "Instagram"), "Como eu edito meus vídeos")
        so_emoji = {"title": "Video by fulano", "channel": "fulano", "description": "😂😂😂"}
        self.assertEqual(B.titulo_do_video(so_emoji, "Instagram"), "Reel de @fulano")
        self.assertEqual(B.titulo_do_video({"title": " Podcast 12 "}, "YouTube"), "Podcast 12")


class Legenda(unittest.TestCase):
    def _auto(self, *chaves):
        return {k: [{"ext": "json3", "url": f"j/{k}"}, {"ext": "vtt", "url": f"v/{k}"}] for k in chaves}

    def test_escolhe_a_original_no_idioma_do_video(self):
        """Vídeo dublado lista um -orig por faixa de áudio; as sem -orig são traduções."""
        v = {"language": "pt-BR", "automatic_captions": self._auto("en-US-orig", "pt-orig", "es-US-orig", "pt", "en")}
        self.assertEqual(B.legenda_original(v), ("pt-orig", "v/pt-orig"))

    def test_sem_idioma_so_vale_se_houver_uma_original(self):
        self.assertEqual(B.legenda_original({"automatic_captions": self._auto("pt-orig", "en")}), ("pt-orig", "v/pt-orig"))
        self.assertIsNone(B.legenda_original({"automatic_captions": self._auto("pt-orig", "en-orig")}))
        self.assertIsNone(B.legenda_original({"automatic_captions": self._auto("pt", "en")}))   # só tradução
        self.assertIsNone(B.legenda_original({}))


class Erros(unittest.TestCase):
    def test_erro_do_yt_dlp_vira_o_que_fazer(self):
        casos = {
            "ERROR: [youtube] abc: This video is unavailable": "privado",
            "ERROR: [youtube] abc: Private video. Sign in if you've been granted access": "pediu login",
            "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser": "pediu login",
            "ERROR: [Instagram] abc: Instagram sent an empty media response. use --cookies-from-browser": "pediu login",
            "ERROR: Unsupported URL: https://exemplo.com": "Não sei baixar",
            "ERROR: [youtube] abc: Requested format is not available": "JavaScript",
            "ERROR: You have requested merging of multiple formats but ffmpeg is not installed": "ffmpeg",
            "ERROR: Unable to download webpage: <urlopen error [Errno 8] getaddrinfo failed>": "conexão",
        }
        for bruto, esperado in casos.items():
            with self.subTest(bruto=bruto):
                self.assertIn(esperado, str(B.traduzir(Exception(bruto), "https://www.youtube.com/watch?v=abc")))

    def test_playlist_carrossel_e_live_sao_recusados(self):
        with self.assertRaises(B.ErroDownload):
            B._video_unico({"_type": "playlist", "entries": [{"_type": "url"}, {"_type": "url"}]})
        with self.assertRaises(B.ErroDownload):
            B._video_unico({"_type": "playlist", "entries": [{"_type": "url", "url": "x"}]})
        with self.assertRaises(B.ErroDownload):
            B._video_unico({"title": "ao vivo", "live_status": "is_live"})
        self.assertEqual(B._video_unico({"_type": "playlist", "entries": [{"title": "só um"}]}), {"title": "só um"})

    def test_info_recusa_o_que_nao_e_link_sem_chamar_o_yt_dlp(self):
        with self.assertRaises(B.ErroDownload):
            B.info("youtube.com/watch?v=abc")


class ComProjetosTemporarios(unittest.TestCase):
    """Troca projetos/ por uma pasta temporária: os testes nunca tocam nos do usuário."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=S.RAIZ, prefix=".teste-painel-"))
        self._orig = (S.PROJETOS, S.ATV.PROJETOS)
        S.PROJETOS = S.ATV.PROJETOS = self.tmp / "projetos"
        S.PROJETOS.mkdir()

    def tearDown(self):
        S.PROJETOS, S.ATV.PROJETOS = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)


class Projeto(ComProjetosTemporarios):
    LINK = "https://www.youtube.com/watch?v=abc"

    def test_projeto_do_link_guarda_o_link_e_ainda_nao_tem_video(self):
        r = S.criar_projeto("Podcast do link", "/ignorado.mp4", link=self.LINK)
        info = json.loads((S.PROJETOS / r["slug"] / "projeto.json").read_text())
        self.assertEqual(info["link"], self.LINK)
        self.assertEqual(info["video"], "")
        self.assertIsNone(r["aviso"])
        self.assertEqual(S.resumo(S.PROJETOS / r["slug"])["link"], self.LINK)

    def test_link_invalido_nao_cria_projeto(self):
        with self.assertRaises(ValueError):
            S.criar_projeto("Ruim", "", link="nao-e-link")
        self.assertFalse((S.PROJETOS / "ruim").exists())

    def test_destino_so_dentro_de_projetos(self):
        self.assertEqual(B.pasta_do_projeto(str(S.PROJETOS / "meu-video")), (S.PROJETOS / "meu-video").resolve())
        for ruim in (str(self.tmp / "fora"), str(S.PROJETOS / ".." / "x"), str(S.PROJETOS / "Com Espaco")):
            with self.subTest(ruim=ruim), self.assertRaises(B.ErroDownload):
                B.pasta_do_projeto(ruim)

    def test_mesmo_link_de_novo_nao_baixa_outra_vez(self):
        r = S.criar_projeto("Ja baixado", "", link=self.LINK)
        proj = S.PROJETOS / r["slug"]
        (proj / "video.mp4").write_bytes(b"x")
        B.gravar_projeto(proj, video=str(proj / "video.mp4"))
        with mock.patch.object(B, "_baixar_travado", side_effect=AssertionError("baixou de novo")):
            self.assertEqual(B.baixar(self.LINK, proj), proj / "video.mp4")

    def test_baixar_sem_link_aponta_o_video_que_ja_existe(self):
        video = self.tmp / "local.mp4"
        video.write_bytes(b"x")
        S.criar_projeto("Local", str(video))
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(B.main([str(S.PROJETOS / "local")]), 0)
        self.assertIn(f"VIDEO={video}", saida.getvalue())

    def test_dois_reels_do_mesmo_perfil_viram_dois_projetos(self):
        with mock.patch.object(B, "info", return_value={"titulo": "Reel de @fulano"}):
            a = B.criar_do_link("https://www.instagram.com/reel/AAA/", None, None)
            b = B.criar_do_link("https://www.instagram.com/reel/BBB/", None, None)
            de_novo = B.criar_do_link("https://www.instagram.com/reel/AAA/", None, None)
        self.assertEqual((a.name, b.name), ("reel-de-fulano", "reel-de-fulano-2"))
        self.assertEqual(de_novo, a)                             # o mesmo link retoma o mesmo projeto


class AtividadeDoDownload(ComProjetosTemporarios):
    def setUp(self):
        super().setUp()
        self.proj = S.PROJETOS / S.criar_projeto("Baixando", "", link="https://youtu.be/abc")["slug"]

    def test_download_rodando_mostra_a_barra(self):
        S.ATV.registrar(self.proj, "baixando o vídeo do YouTube", tipo="inicio", id="d1", pid=os.getpid(), **B.ANOTAR)
        S.ATV.registrar(self.proj, "baixando o vídeo: 40 MB de 80 MB (50%)", tipo="progresso", pct=50, id="d1", **B.ANOTAR)
        a = S.atividade(self.proj)
        self.assertEqual(a["estado"], "rodando")
        self.assertEqual(a["rodando"]["pct"], 50)

    def test_video_baixado_ainda_e_esperando_o_claude(self):
        """Baixar é preparação: sem isso o painel diria "parado" e esconderia o comando."""
        S.ATV.registrar(self.proj, "baixando o vídeo do YouTube", tipo="inicio", id="d1", pid=os.getpid(), **B.ANOTAR)
        S.ATV.registrar(self.proj, "vídeo baixado", tipo="fim", id="d1", codigo=0, **B.ANOTAR)
        self.assertEqual(S.atividade(self.proj)["estado"], "esperando_claude")

    def test_falha_no_download_aparece(self):
        S.ATV.registrar(self.proj, "baixando o vídeo do YouTube", tipo="inicio", id="d1", pid=os.getpid(), **B.ANOTAR)
        S.ATV.registrar(self.proj, "Esse vídeo é privado", tipo="erro", id="d1", codigo=1, **B.ANOTAR)
        a = S.atividade(self.proj)
        self.assertNotEqual(a["estado"], "esperando_claude")
        self.assertEqual(a["eventos"][0]["tipo"], "erro")


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

    def postar(self, caminho, dados):
        req = urllib.request.Request(self.base + caminho, data=json.dumps(dados).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_info_do_link_invalido_explica(self):
        status, r = self.postar("/api/info-link", {"link": "isso nao e link"})
        self.assertEqual(status, 200)
        self.assertIn("link", r["erro"])

    def test_criar_com_link_dispara_o_download(self):
        with mock.patch.object(S, "iniciar_download") as iniciar:
            status, r = self.postar("/api/projetos", {"nome": "Do link", "link": "https://youtu.be/abc"})
        self.assertEqual(status, 200)
        iniciar.assert_called_once_with(S.PROJETOS / r["slug"])

    def test_criar_sem_link_nao_baixa_nada(self):
        with mock.patch.object(S, "iniciar_download") as iniciar:
            self.postar("/api/projetos", {"nome": "Do arquivo", "video": "/x.mp4"})
        iniciar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
