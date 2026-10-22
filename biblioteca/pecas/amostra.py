"""
Um quadro do clipe da propria pessoa no estilo do projeto: o video no instante --t, uma
frase sobre ele (no terco de cima, onde o rosto nao fica) e a legenda do estilo, na altura
que o rosto deixa. E a "direcao" que a criacao de estilo com o Claude mostra para escolher.

Quem chama e o `./topclip estilo amostra`; rodar a mao, na raiz de um projeto de motion:

    python -m pecas.amostra --video clipe.mp4 --t 12.5 --saida amostra.png
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
W, H = 1080, 1920


def _quadro_do_video(video, t):
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "q.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                        "-frames:v", "1", "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                        str(png)], check=True)
        return Image.open(png).convert("RGBA")


def _posicao_da_legenda(cap, video, t):
    """A altura da legenda pelo rosto, como no render (cai no padrao sem rosto)."""
    with tempfile.TemporaryDirectory() as d:
        palavras = Path(d) / "p.json"
        palavras.write_text(json.dumps([{"w": "x", "t": t, "e": t + 0.05}]))
        cap.configurar(words_json=palavras, janelas=[(max(0.0, t - 0.6), t + 0.6)], video=video)
        return cap.posicao()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--t", type=float, default=3.0)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--texto", default="Seu conteúdo com a sua cara")
    ap.add_argument("--legenda", default="é assim que fica a legenda")
    a = ap.parse_args(argv)

    import captions as CAP
    import pecas as P
    from pecas import legenda as PL

    estilo = P.carregar(ROOT)
    tela = _quadro_do_video(a.video, a.t)
    declaradas = json.loads((ROOT / "estilo" / "estilo.json").read_text(encoding="utf-8"))["pecas"]
    # Sobre o video, frase solta so le com contorno (Impacto); sem contorno (Limpo, Luxo), a
    # frase vai num cartao, que e como esses estilos poem texto em cima do rosto.
    contorno = estilo.tipo["contorno"] > 0
    if "marca_texto" in declaradas and (contorno or "cartao" not in declaradas):
        palavra = max(a.texto.split(), key=len).strip(".,!?")
        tela.alpha_composite(P.marca_texto.quadro(60, 0, 200, estilo, texto=a.texto,
                                                  palavra=palavra, centro=(540, 520),
                                                  tamanho=88, marca_em=20))
    elif "cartao" in declaradas:
        tela.alpha_composite(P.cartao.quadro(60, 0, 200, estilo, titulo=a.texto,
                                             rotulo=estilo.r["nome"], centro=(540, 520)))

    cy, teto = _posicao_da_legenda(CAP, a.video, a.t)
    leg = PL.para(estilo)
    bloco = {"txt": a.legenda, "enf": False, "cor": None}
    if leg:
        leg.configura(CAP)
        tela.alpha_composite(leg.draw(bloco, 99, 30, (cy, teto)))
    else:                                     # o Papel: a legenda dele, com o boil "print"
        tela.alpha_composite(CAP.draw(bloco, frame=0.0))
    tela.convert("RGB").save(a.saida)
    print(a.saida)


if __name__ == "__main__":
    main()
