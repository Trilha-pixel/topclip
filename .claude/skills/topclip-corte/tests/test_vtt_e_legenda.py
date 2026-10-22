# -*- coding: utf-8 -*-
"""
Regressoes de decupagem e legenda, as duas encontradas rodando o pipeline real.

1. VTT do YouTube perdia o timing por palavra (o parser era de SRT generico) e
   duplicava o texto por causa da cue rolante.
2. O piso de duracao minima da cue vencia a regra de nao sobrepor, gerando
   `srt_entries_overlap_or_out_of_order` no verify-output.
"""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.normalize_transcript import _looks_like_youtube_vtt, _parse_youtube_vtt
from scripts.subtitles import Token, chunk_tokens

# Trecho real de legenda automatica do YouTube: cue rolante + timing por palavra
VTT_YOUTUBE = """WEBVTT
Kind: captions
Language: pt

00:00:03.480 --> 00:00:05.190 align:start position:0%
Papo.
&gt;&gt; Salve<00:00:03.800><c> salve</c><00:00:04.080><c> familia,</c><00:00:04.440><c> bem-vindos</c><00:00:04.880><c> a</c><00:00:05.040><c> mais</c>

00:00:05.190 --> 00:00:05.200 align:start position:0%
&gt;&gt; Salve salve familia, bem-vindos a mais


00:00:05.200 --> 00:00:07.030 align:start position:0%
&gt;&gt; Salve salve familia, bem-vindos a mais
um<00:00:05.400><c> Papo.</c><00:00:05.720><c> Eu</c><00:00:05.799><c> sou</c><00:00:06.040><c> o</c><00:00:06.399><c> Leo</c>

00:00:07.040 --> 00:00:09.870 align:start position:0%
um Papo. Eu sou o Leo
&gt;&gt; Fala<00:00:07.400><c> ai</c><00:00:07.800><c> pessoal.</c>
"""


class TestVttYouTube(unittest.TestCase):
    def setUp(self):
        self.doc = _parse_youtube_vtt(VTT_YOUTUBE, "teste.vtt")
        self.words = [w for s in self.doc["segments"] for w in s["words"]]

    def test_detecta_o_formato(self):
        self.assertTrue(_looks_like_youtube_vtt(VTT_YOUTUBE))
        self.assertFalse(_looks_like_youtube_vtt("1\n00:00:01,000 --> 00:00:02,000\noi\n"))

    def test_todo_segmento_tem_timing_por_palavra(self):
        """Sem isto o in/out do corte nao pode ser preciso - e a premissa da skill."""
        self.assertTrue(self.doc["segments"])
        for s in self.doc["segments"]:
            self.assertTrue(s.get("words"), f"segmento sem palavras: {s['text']!r}")

    def test_nao_duplica_a_cue_rolante(self):
        """'Salve salve familia' aparece em 3 cues; so pode ser emitido uma vez."""
        texto = [w["word"] for w in self.words]
        self.assertEqual(texto.count("Salve"), 1)
        self.assertEqual(texto.count("familia,"), 1)
        self.assertEqual(texto.count("bem-vindos"), 1)

    def test_usa_o_timestamp_real_e_nao_interpolado(self):
        por_palavra = {w["word"]: w["start"] for w in self.words}
        self.assertAlmostEqual(por_palavra["salve"], 3.800, places=2)
        self.assertAlmostEqual(por_palavra["Leo"], 6.399, places=2)

    def test_marcador_de_locutor_vira_fronteira_e_some_do_texto(self):
        self.assertNotIn(">>", [w["word"] for w in self.words])
        self.assertGreaterEqual(len({s["speaker"] for s in self.doc["segments"]}), 2)

    def test_palavras_em_ordem_e_sem_sobreposicao(self):
        for anterior, atual in zip(self.words, self.words[1:]):
            self.assertLessEqual(anterior["end"], atual["start"] + 1e-6,
                                 f"{anterior['word']!r} invade {atual['word']!r}")
            self.assertGreater(anterior["end"], anterior["start"])

    def test_cue_que_comeca_com_linha_so_de_espaco(self):
        """
        No início do vídeo (e depois de pausa longa) o YouTube abre a cue com uma
        linha só com espaço no lugar da linha anterior. Tratada como linha vazia,
        ela partia a cue do texto: a frase perdia o tempo real e era espalhada
        depois, na cue seguinte.
        """
        vtt = (
            "WEBVTT\nKind: captions\nLanguage: pt\n\n"
            "00:00:00.140 --> 00:00:02.389 align:start position:0%\n \n"
            "três<00:00:01.140><c> conselhos</c><00:00:01.380><c> para</c>\n\n"
            "00:00:02.389 --> 00:00:02.399 align:start position:0%\ntrês conselhos para\n \n\n"
            "00:00:02.399 --> 00:00:05.269 align:start position:0%\ntrês conselhos para\n"
            "quem<00:00:02.760><c> começa</c>\n"
        )
        palavras = [w for s in _parse_youtube_vtt(vtt, "t.vtt")["segments"] for w in s["words"]]
        self.assertEqual([w["word"] for w in palavras], ["três", "conselhos", "para", "quem", "começa"])
        inicio = {w["word"]: w["start"] for w in palavras}
        self.assertAlmostEqual(inicio["três"], 0.140, places=2)
        self.assertAlmostEqual(inicio["conselhos"], 1.140, places=2)
        self.assertAlmostEqual(inicio["começa"], 2.760, places=2)


class TestLegendaSemSobreposicao(unittest.TestCase):
    def _tokens(self, tempos):
        return [Token(text=f"p{i}", start=a, end=b, source_start=a, source_end=b)
                for i, (a, b) in enumerate(tempos)]

    def test_piso_de_duracao_nao_invade_a_proxima_cue(self):
        """
        Palavras muito juntas: o piso de 200ms empurrava o fim da cue para
        depois do inicio da seguinte e reprovava no verify-output.
        """
        tokens = self._tokens([(0.0, 0.05), (0.06, 0.11), (0.12, 0.17),
                               (0.18, 0.23), (0.24, 0.29), (0.30, 0.35)])
        caps = chunk_tokens(tokens, min_words=1, max_words=1,
                            min_duration=0.55, target_max_duration=2.2, max_words_per_second=10.0)
        self.assertGreater(len(caps), 1)
        for anterior, atual in zip(caps, caps[1:]):
            self.assertLessEqual(anterior.end, atual.start,
                                 f"cue {anterior.index} termina em {anterior.end} e a proxima comeca em {atual.start}")

    def test_toda_cue_tem_duracao_positiva(self):
        tokens = self._tokens([(0.0, 0.02), (0.021, 0.04), (0.041, 0.06)])
        for c in chunk_tokens(tokens, min_words=1, max_words=1,
                              min_duration=0.55, target_max_duration=2.2, max_words_per_second=10.0):
            self.assertGreater(c.end, c.start)


if __name__ == "__main__":
    unittest.main()
