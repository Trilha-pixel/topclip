# -*- coding: utf-8 -*-
"""Testes do enquadramento por locutor ativo (sem exigir midia real)."""
import importlib.util, math, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.versoes import hash_corte

# cv2/numpy sao dependencias OPCIONAIS (so o autoframe usa). Sem elas a skill
# continua funcionando com anchor manual, entao estes testes pulam em vez de falhar.
try:
    import numpy as np
    from scripts.autoframe import anchor_from_cx
    from scripts.active_speaker import _corr, Track, sample_faces
    from scripts import autoframe, framing
    AUTOFRAME_OK, AUTOFRAME_ERR = True, ""
except ImportError as exc:  # pragma: no cover
    AUTOFRAME_OK, AUTOFRAME_ERR = False, str(exc)

requires_autoframe = unittest.skipUnless(
    AUTOFRAME_OK, f"autoframe indisponivel (opcional): {AUTOFRAME_ERR}"
)
MODEL = Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx"


@requires_autoframe
class TestAnchorMath(unittest.TestCase):
    """anchor_from_cx precisa ser o inverso exato do filtro de scripts/render.py."""

    def _render_center(self, anchor, zoom, src_w=1920, src_h=1080, out_w=1080, out_h=1920):
        s = max(out_w*zoom/src_w, out_h*zoom/src_h)
        scaled_w = src_w*s
        x = max(0.0, min(scaled_w-out_w, (scaled_w-out_w)*anchor))
        return (x + out_w/2)/s

    def test_centro(self):
        self.assertAlmostEqual(anchor_from_cx(960, 1.0), 0.5, places=3)

    def test_roundtrip_varios_zooms(self):
        for zoom in (1.0, 1.2, 1.45, 2.0):
            for cx in (400, 700, 960, 1300, 1600):
                a = anchor_from_cx(cx, zoom)
                self.assertGreaterEqual(a, 0.0); self.assertLessEqual(a, 1.0)
                if 0.0 < a < 1.0:   # fora do clamp, tem de bater
                    self.assertAlmostEqual(self._render_center(a, zoom), cx, delta=1.5)

    def test_clamp_nas_bordas(self):
        self.assertEqual(anchor_from_cx(-500, 1.0), 0.0)
        self.assertEqual(anchor_from_cx(99999, 1.0), 1.0)


@requires_autoframe
class TestCorrelacao(unittest.TestCase):
    """A correlacao e o que separa locutor real de anuncio tocando na TV."""

    def test_boca_sincronizada_com_audio(self):
        audio  = [0.0, 0.9, 0.8, 0.0, 0.0, 0.9, 0.7, 0.0]
        mouth  = [0.1, 0.8, 0.9, 0.1, 0.0, 0.7, 0.8, 0.1]
        self.assertGreater(_corr(mouth, audio), 0.8)

    def test_movimento_constante_nao_correlaciona(self):
        audio  = [0.0, 0.9, 0.8, 0.0, 0.0, 0.9, 0.7, 0.0]
        tv     = [0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6]   # variancia zero
        self.assertEqual(_corr(tv, audio), 0.0)

    def test_serie_curta_e_neutra(self):
        self.assertEqual(_corr([1, 2], [1, 2]), 0.0)


def _amostra(rostos):
    """Fake de sample_faces: rostos(t) -> [(cx, cy, w, h)] no espaco 960x540.
    Gerador como o real: `pedidos` sao os instantes planejados, `lidas` os que o
    consumidor de fato pediu (o resto nem seria decodificado)."""
    def fake(src, times, model):
        fake.pedidos = list(times)
        for t in times:
            fake.lidas.append(t)
            yield t, rostos(t)
    fake.pedidos, fake.lidas = [], []
    return fake


def _mesa(a, b):
    """Plano aberto com duas pessoas. O OUVINTE tem o rosto maior (mais perto da
    camera) e mexe a boca sem ritmo; o LOCUTOR e menor e mexe junto com o audio."""
    n = int(round((b - a) * framing.SAMPLE_FPS))
    env = np.array([0.5 if (i // 5) % 2 == 0 else 0.05 for i in range(n)])
    ouvinte, locutor = Track(250, 270, 75, 90), Track(700, 260, 60, 70)
    for i in range(n):
        t = a + i / framing.SAMPLE_FPS
        ouvinte.update(t, 250, 270, 75, 90); ouvinte.motion.append((t, 15 + 3 * math.sin(i * 1.7)))
        locutor.update(t, 700, 260, 60, 70); locutor.motion.append((t, 2 + 30 * env[i]))
    return [ouvinte, locutor], env


@requires_autoframe
class TestAmostragemAdaptativa(unittest.TestCase):
    """Amostra esparsa primeiro; analise densa so quando a amostra nao basta."""

    def _planejar(self, a, b, rostos, tracks=(), env=None, zones=None):
        amostra = _amostra(rostos)
        densa = mock.Mock(return_value=(list(tracks), 960))
        audio = mock.Mock(return_value=np.zeros(0) if env is None else env)
        with mock.patch.object(framing, "sample_faces", amostra), \
             mock.patch.object(framing, "analyze_shot", densa), \
             mock.patch.object(framing, "audio_envelope", audio):
            keys, diag = framing._plan_single_shot("sintetico.mp4", a, b, "yunet.onnx", [], zones)
        return keys, diag, amostra, densa, audio

    def test_close_parado_fica_estatico_sem_analise_densa(self):
        # jitter de deteccao de 1-2px: bem abaixo do DEADZONE
        rostos = lambda t: [(479 if t < 2 else 481 if t < 6 else 483, 250, 120, 140)]
        keys, diag, amostra, densa, audio = self._planejar(0.0, 8.0, rostos)
        densa.assert_not_called(); audio.assert_not_called()
        self.assertEqual(len(amostra.lidas), 3)                # inicio, meio, fim
        self.assertEqual(keys, [(0.0, 962 - framing.CROP_W // 2, framing.CROP_W)])  # mediana
        self.assertEqual(diag["caminho"], "amostrado")
        self.assertEqual(diag["tipo"], "close")
        self.assertEqual(diag["variacao_px"], 8.0)

    def test_varios_rostos_vao_para_analise_densa_e_seguem_o_locutor(self):
        tracks, env = _mesa(0.0, 10.0)
        rostos = lambda t: [(250, 270, 75, 90), (700, 260, 60, 70)]
        keys, diag, amostra, densa, audio = self._planejar(0.0, 10.0, rostos, tracks, env)
        densa.assert_called_once()
        self.assertEqual(densa.call_args.args[1:3], (0.0, 10.0))
        audio.assert_called_once()
        self.assertEqual(diag["caminho"], "denso")
        self.assertIn("2 rostos", diag["motivo"])
        self.assertEqual(diag["tipo"], "aberto")
        # o primeiro frame ja decide: os outros dois nem sao decodificados
        self.assertEqual(len(amostra.pedidos), 3)
        self.assertEqual(len(amostra.lidas), 1); self.assertEqual(diag["amostras"], 1)
        # crop no LOCUTOR (cx 700 -> 1400px na fonte), nao no rosto maior (500px)
        for _, x, w in keys:
            self.assertAlmostEqual(x + w / 2, 1400, delta=2)

    def test_rosto_que_anda_vai_para_analise_densa(self):
        rostos = lambda t: [(400 + 16 * t, 250, 120, 140)]   # 160px no espaco 960 em 10s
        tr = Track(400, 250, 120, 140)
        for i in range(50): tr.update(i / 5, 400 + 16 * i / 5, 250, 120, 140)
        _, diag, _, densa, _ = self._planejar(0.0, 10.0, rostos, [tr])
        densa.assert_called_once()
        self.assertEqual(diag["caminho"], "denso")
        self.assertIn("andou", diag["motivo"])

    def test_zoom_de_camera_vai_para_analise_densa(self):
        rostos = lambda t: [(480, 250, 60 + 4 * t, 70 + 4 * t)]   # rosto cresce, centro parado
        _, diag, _, densa, _ = self._planejar(0.0, 10.0, rostos)
        densa.assert_called_once()
        self.assertIn("largura", diag["motivo"])

    def test_plano_longo_amostra_a_cada_5s(self):
        # 40s; a pessoa sai do lugar so entre 108s e 114s. Tres amostras fixas
        # (inicio, meio, fim) nao veriam; uma a cada ~5s ve.
        a, b = 100.0, 140.0
        fixas = framing.probe_times(a, a + framing.PROBE_LONG)   # 3 amostras
        self.assertEqual(len(fixas), 3)
        self.assertFalse(any(108 <= t <= 114 for t in (a + 0.25, (a + b) / 2, b - 0.25)))
        rostos = lambda t: [(650 if 108 <= t <= 114 else 480, 250, 120, 140)]
        _, diag, amostra, densa, _ = self._planejar(a, b, rostos)
        tempos = amostra.pedidos
        self.assertGreaterEqual(len(tempos), 8)
        self.assertLessEqual(max(t1 - t0 for t0, t1 in zip(tempos, tempos[1:])), framing.PROBE_STEP)
        self.assertGreaterEqual(tempos[0], a); self.assertLessEqual(tempos[-1], b)
        densa.assert_called_once()
        self.assertIn("andou", diag["motivo"])
        self.assertTrue(108 <= amostra.lidas[-1] <= 114)     # parou onde viu o movimento

    def test_plano_longo_parado_continua_estatico(self):
        _, diag, amostra, densa, _ = self._planejar(0.0, 30.0, lambda t: [(480, 250, 120, 140)])
        densa.assert_not_called()
        self.assertEqual(diag["caminho"], "amostrado")
        self.assertEqual(diag["amostras"], len(amostra.pedidos))
        self.assertGreater(diag["amostras"], 3)

    def test_sem_rosto_na_amostra_confere_na_densa(self):
        keys, diag, _, densa, _ = self._planejar(0.0, 6.0, lambda t: [])
        densa.assert_called_once()
        self.assertIn("nenhum rosto", diag["motivo"])
        self.assertEqual(diag["tipo"], "sem-rosto")
        self.assertEqual(keys, [(0.0, framing.CENTER, framing.CROP_W)])

    def test_frame_ilegivel_nao_conta_como_sem_rosto(self):
        amostra = lambda src, times, model: [(t, None if i == 1 else [(480, 250, 120, 140)])
                                             for i, t in enumerate(times)]
        densa = mock.Mock(return_value=([], 960))
        with mock.patch.object(framing, "sample_faces", amostra), \
             mock.patch.object(framing, "analyze_shot", densa):
            _, diag = framing._plan_single_shot("sintetico.mp4", 0.0, 6.0, "m", [], None)
        densa.assert_called_once()
        self.assertIn("nao decodificou", diag["motivo"])

    def test_rosto_em_zona_excluida_nao_conta(self):
        # foto de rosto na TV do cenario (canto direito) + uma pessoa real
        rostos = lambda t: [(300, 250, 120, 140), (850, 200, 50, 60)]
        keys, diag, _, densa, _ = self._planejar(0.0, 8.0, rostos, zones=[[0.8, 0.0, 1.0, 0.6]])
        densa.assert_not_called()
        self.assertEqual(diag["caminho"], "amostrado")
        self.assertEqual(keys, [(0.0, 600 - framing.CROP_W // 2, framing.CROP_W)])


def _planejar_segmentos(segmentos, keys_por_segmento):
    """plan_segments com plan_range simulado: keys_por_segmento(a, b) -> [(t, x, w)]."""
    fake = lambda src, a, b, model, silences, zones=None: (keys_por_segmento(a, b), [])
    with mock.patch.object(autoframe, "plan_range", side_effect=fake):
        timeline, _ = autoframe.plan_segments("sintetico.mp4", segmentos, "m.onnx", silences=[])
    return timeline


@requires_autoframe
class TestZoomDoEditDirector(unittest.TestCase):
    """O zoom do Edit Director e punch-in: o autoframe nao pode apaga-lo (docs/12, 12.8)."""

    W = framing.CROP_W if AUTOFRAME_OK else 608

    def _seg(self, a, b, zoom, ordem):
        return {"source_start": a, "source_end": b, "zoom": zoom, "crop_anchor_x": 0.5,
                "order": ordem, "layout": "cover", "framing_reason": f"seg {ordem}"}

    def test_punch_in_em_close_sobrevive(self):
        # clip-005 da run aula-yt-teste: close parado, punch-in 1.08 no seg 3 saia 1.0
        segs = [self._seg(2093.38, 2104.8, 1.0, 2), self._seg(2117.45, 2122.96, 1.08, 3)]
        tl = _planejar_segmentos(segs, lambda a, b: [(a, 625, self.W)])
        self.assertEqual([s["zoom"] for s in tl], [1.0, 1.08])
        # o crop do punch-in continua centrado no rosto (cx 929px na fonte)
        self.assertEqual(tl[1]["crop_anchor_x"], round(anchor_from_cx(625 + self.W / 2, 1.08), 4))
        self.assertEqual(tl[1]["framing_reason"], "seg 3")

    def test_punch_in_em_plano_aberto_multiplica_o_zoom_do_rosto(self):
        # plano aberto: o rosto ja pede ~1.3; com max() o punch-in de 1.08 sumiria
        w = int(round(self.W / 1.3))
        segs = [self._seg(10.0, 14.0, 1.0, 1), self._seg(14.0, 18.0, 1.08, 2)]
        tl = _planejar_segmentos(segs, lambda a, b: [(a, 800, w)])
        rosto = round(self.W / w, 4)
        self.assertEqual(tl[0]["zoom"], rosto)
        self.assertAlmostEqual(tl[1]["zoom"], rosto * 1.08, places=3)

    def test_teto_do_schema(self):
        w = int(round(self.W / framing.MAX_ZOOM))
        tl = _planejar_segmentos([self._seg(0.0, 4.0, 1.5, 1)], lambda a, b: [(a, 700, w)])
        self.assertEqual(tl[0]["zoom"], autoframe.ZOOM_MAX)

    def test_sem_pedido_ou_pedido_invalido_fica_o_zoom_do_rosto(self):
        segs = [[0.0, 2.0], self._seg(2.0, 4.0, "1.1x", 2), self._seg(4.0, 6.0, 0.5, 3),
                {"source_start": 6.0, "source_end": 8.0}]
        tl = _planejar_segmentos(segs, lambda a, b: [(a, 656, self.W)])
        self.assertEqual([s["zoom"] for s in tl], [1.0] * 4)


@requires_autoframe
class TestCoberturaDaFonte(unittest.TestCase):
    """Os subsegmentos cobrem a faixa do segmento inteira: buraco = audio pulado no render."""

    W = framing.CROP_W if AUTOFRAME_OK else 608

    def _faixas(self, timeline):
        return [(s["source_start"], s["source_end"], s["crop_anchor_x"]) for s in timeline]

    def assertCobre(self, timeline, a, b):
        self.assertEqual(timeline[0]["source_start"], a)
        self.assertEqual(timeline[-1]["source_end"], b)
        for antes, depois in zip(timeline, timeline[1:]):
            self.assertEqual(antes["source_end"], depois["source_start"])
            self.assertGreaterEqual(antes["source_end"] - antes["source_start"], autoframe.MIN_SUBSEG)

    def test_trecho_curto_entre_keyframes_fica_com_o_vizinho(self):
        # o caso do descarte: 0,1s entre 12,0 e 12,1 sumia do corte
        keys = [(10.0, 100, self.W), (12.0, 300, self.W), (12.1, 500, self.W), (14.0, 700, self.W)]
        tl = _planejar_segmentos([{"source_start": 10.0, "source_end": 16.0}], lambda a, b: keys)
        self.assertCobre(tl, 10.0, 16.0)
        self.assertEqual([(s["source_start"], s["source_end"]) for s in tl],
                         [(10.0, 12.1), (12.1, 14.0), (14.0, 16.0)])
        anchors = [round(anchor_from_cx(x + self.W / 2, 1.0), 4) for x in (100, 500, 700)]
        self.assertEqual([s["crop_anchor_x"] for s in tl], anchors)   # a piscada (300) nao aparece

    def test_trecho_curto_no_fim_do_plano(self):
        # janela final de 0,1s antes do corte de camera: o tempo fica com a key anterior
        keys = [(20.0, 100, self.W), (22.95, 300, self.W), (23.05, 900, self.W)]
        tl = _planejar_segmentos([{"source_start": 20.0, "source_end": 26.0}], lambda a, b: keys)
        self.assertCobre(tl, 20.0, 26.0)
        self.assertEqual([(s["source_start"], s["source_end"]) for s in tl], [(20.0, 23.05), (23.05, 26.0)])

    def test_trecho_curto_no_inicio_vai_para_o_seguinte(self):
        keys = [(0.0, 100, self.W), (0.1, 300, self.W)]
        tl = _planejar_segmentos([[0.0, 3.0]], lambda a, b: keys)
        self.assertEqual(self._faixas(tl), [(0.0, 3.0, round(anchor_from_cx(300 + self.W / 2, 1.0), 4))])

    def test_primeira_key_depois_do_inicio(self):
        # plano de 0,28s no inicio: o plan_range pula, e a primeira key vem em 5,28
        tl = _planejar_segmentos([[5.0, 9.0]], lambda a, b: [(5.28, 400, self.W)])
        self.assertCobre(tl, 5.0, 9.0)
        self.assertEqual(len(tl), 1)

    def test_segmento_inteiro_curto_nao_some(self):
        tl = _planejar_segmentos([[1.0, 1.1]], lambda a, b: [(1.0, 100, self.W), (1.04, 300, self.W)])
        self.assertEqual([(s["source_start"], s["source_end"]) for s in tl], [(1.0, 1.1)])

    def test_versao_do_corte_nao_muda(self):
        # buraco mudava o segments_hash e tornava velha a revisao do QC (scripts/versoes.py)
        segs = [{"source_start": 2080.98, "source_end": 2082.93, "order": 1},
                {"source_start": 2093.38, "source_end": 2104.8, "order": 2}]

        def keys(a, b):
            meio = round((a + b) / 2, 2)
            return [(a, 600, self.W), (meio, 640, self.W), (meio + 0.08, 700, self.W)]

        tl = _planejar_segmentos(segs, keys)
        self.assertGreater(len(tl), len(segs))
        self.assertEqual(hash_corte(tl), hash_corte(segs))


@requires_autoframe
class TestDeteccaoDeCortes(unittest.TestCase):

    def test_pyscenedetect_tem_prioridade(self):
        with mock.patch.object(framing, "_cuts_pyscenedetect", return_value=[10.1, 13.0, 13.4, 19.9]), \
             mock.patch.object(framing.subprocess, "run") as run:
            cortes, detector = framing._detect_cuts("x.mp4", 10.0, 20.0)
        run.assert_not_called()
        self.assertEqual(detector, "pyscenedetect")
        self.assertEqual(cortes, [13.0])    # bordas descartadas; 13.4 fundido no 13.0

    def test_ffmpeg_de_reserva_quando_o_pacote_falta(self):
        saida = "pts_time:3.5 \n pts_time:3.9 \n pts_time:7.2"
        feito = subprocess.CompletedProcess([], 0, stdout="", stderr=saida)
        with mock.patch.dict(sys.modules, {"scenedetect": None, "scenedetect.detectors": None}), \
             mock.patch.object(framing.subprocess, "run", return_value=feito):
            self.assertIsNone(framing._cuts_pyscenedetect("x.mp4", 10.0, 20.0))
            self.assertEqual(framing._detect_cuts("x.mp4", 10.0, 20.0), ([13.5, 17.2], "ffmpeg"))

    def test_trecho_curto_nao_procura_corte(self):
        with mock.patch.object(framing, "_cuts_pyscenedetect") as pysd:
            self.assertEqual(framing.detect_cuts("x.mp4", 5.0, 6.0), [])
        pysd.assert_not_called()


@requires_autoframe
@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg ausente")
class TestVideoSintetico(unittest.TestCase):
    """Cores chapadas geradas pelo ffmpeg: cortes conhecidos em 2s e 4s, nenhum rosto."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = str(Path(cls.tmp.name) / "cortes.mp4")
        cores = ["red", "blue", "green"]
        cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error"]
        for c in cores: cmd += ["-f", "lavfi", "-i", f"color=c={c}:s=160x90:r=30:d=2"]
        cmd += ["-filter_complex", "".join(f"[{i}]" for i in range(3)) + "concat=n=3:v=1:a=0,format=yuv420p",
                "-c:v", "libx264", "-g", "30", cls.src]
        subprocess.run(cmd, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @unittest.skipUnless(importlib.util.find_spec("scenedetect"), "scenedetect ausente (opcional)")
    def test_pyscenedetect_acha_os_cortes(self):
        # inteiros de proposito: o SceneManager le int como numero de FRAME (docs/12);
        # se alguem trocar o pipe do ffmpeg por ele, (0, 6) para no frame 6 e falha aqui
        for (a, b), esperado in [((0, 6), [2.0, 4.0]), ((3.0, 6.0), [4.0])]:
            cortes, detector = framing._detect_cuts(self.src, a, b)
            self.assertEqual(detector, "pyscenedetect")
            self.assertEqual(len(cortes), len(esperado), cortes)
            for c, e in zip(cortes, esperado): self.assertAlmostEqual(c, e, delta=0.05)

    def test_ffmpeg_de_reserva_acha_os_mesmos_cortes(self):
        with mock.patch.dict(sys.modules, {"scenedetect": None, "scenedetect.detectors": None}):
            cortes, detector = framing._detect_cuts(self.src, 0.0, 6.0)
        self.assertEqual(detector, "ffmpeg")
        self.assertEqual(len(cortes), 2, cortes)

    @unittest.skipUnless(MODEL.exists(), "modelo YuNet ausente")
    def test_sample_faces_real(self):
        amostras = list(sample_faces(self.src, [0.5, 3.0, 99.0], str(MODEL)))
        self.assertEqual([t for t, _ in amostras], [0.5, 3.0, 99.0])
        self.assertEqual(amostras[0][1], []); self.assertEqual(amostras[1][1], [])
        self.assertIsNone(amostras[2][1])     # depois do fim: inconclusivo, nao "sem rosto"


if __name__ == "__main__":
    unittest.main()
