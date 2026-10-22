"""
Lottie: toca uma animacao Lottie (.json do After Effects/LottieFiles) no trecho, com as
cores do estilo e da marca. Renderiza com o thorvg-python, sem Node e sem navegador.

    lottie.quadro(f, inicio, fim, estilo, arquivo="estilo/lottie/check.json",
                  slots={"acento": "acento"}, largura=520)

`slots`: {id do slot no arquivo: cor do estilo (nome ou #RRGGBB)}. E assim que a mesma
animacao assume a cor da marca sem editar o arquivo.

O que o teste de 2026-10-22 mediu e vira regra aqui:
- `Colorspace.ABGR8888S` (alfa reto). O padrao e pre-multiplicado e o `get_pillow()` nao
  converte: a borda saia escura (RGB 119 onde devia ser 255).
- o tempo do Lottie e `segundos x fps do arquivo`: arquivo a 60fps funciona sem ajuste.
- expressions (wiggle, loopOut) NAO rodam no wheel do pip: o validador do estilo recusa
  arquivo que as usa.
"""
import json
from pathlib import Path

from PIL import Image

from .base import cola, vazio

EXEMPLO = dict(inicio=0, fim=72, f=40, dados=dict(arquivo="estilo/lottie/check.json",
                                                    slots={"acento": "acento"}, largura=520))

_ENGINE = None
_CACHE = {}


def _abre(caminho, largura, slots):
    global _ENGINE
    import thorvg_python as tvg      # so quem usa Lottie precisa do pacote
    chave = (str(caminho), int(largura), tuple((k, tuple(v)) for k, v in sorted(slots.items())))
    if chave in _CACHE:
        return _CACHE[chave]
    if _ENGINE is None:
        _ENGINE = tvg.Engine(threads=0)
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    w = int(largura)
    h = max(1, int(round(w * dados["h"] / dados["w"])))
    cv = tvg.SwCanvas(_ENGINE)
    cv.set_target(w, h, cs=tvg.Colorspace.ABGR8888S)
    an = tvg.LottieAnimation(_ENGINE)
    pic = an.get_picture()
    if pic.load(str(caminho)) != tvg.Result.SUCCESS:
        raise ValueError(f"Lottie nao carregou: {caminho}")
    pic.set_size(w, h)
    cv.add(pic)
    if slots:
        sid = an.gen_slot(json.dumps({k: {"p": {"a": 0, "k": v}} for k, v in slots.items()}))
        an.apply_slot(sid)
    total = an.get_total_frame()[1]
    _CACHE[chave] = (cv, an, float(dados["fr"]), total)
    return _CACHE[chave]


def _rgba(estilo, cor):
    r, g, b, _ = estilo.cor(cor)
    return [round(r / 255, 4), round(g / 255, 4), round(b / 255, 4), 1]


def quadro(f, inicio, fim, estilo, arquivo, centro=(540, 860), largura=520, slots=None,
           loop=False, velocidade=1.0):
    tela = vazio()
    if not inicio <= f <= fim:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    caminho = Path(arquivo) if Path(arquivo).is_absolute() else estilo.raiz / arquivo
    cores = {k: _rgba(estilo, v) for k, v in (slots or {}).items()}
    cv, an, fr, total = _abre(caminho, largura, cores)
    lf = (f - inicio) / 24.0 * velocidade * fr
    lf = lf % total if loop else min(lf, total - 1)
    an.set_frame(max(0.0, lf))
    cv.update()
    cv.draw(True)
    cv.sync()
    lay = cv.get_pillow().copy()
    cola(tela, lay, centro, min(1.0, ent) * (1 - sai), -sai * 16, escala=estilo.escala(ent))
    return tela
