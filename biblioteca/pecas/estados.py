"""
Os estados de revisao (START/MID/END/EXIT) e a folha, para o compose.py dos estilos.
O mesmo contrato do compose do Papel: o estado e a timeline avaliada num quadro, e cena
de overlay e julgada SOBRE o video, no tempo certo (`<NOME>_T0` no compose).

    if __name__ == "__main__":
        estados.main(SCENES, globals())
"""
import subprocess
import sys

from PIL import Image

# eventos continuos nao contam como "ultimo evento" no --check
CONTINUOS = ("fundo", "cinema", "saida", "camera", "deriva")


def _plate(nome, st, fr, glb):
    import kit as K                      # importa so aqui: o kit cria as pastas do projeto
    f = K.PLATES / f"{nome}_{st}.png"
    if f.exists():
        return Image.open(f).convert("RGBA")
    src = K.ROOT / "00_brief" / "fonte.mp4"
    t0 = glb.get(f"{nome}_T0")
    if src.exists() and t0 is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + fr / 24.0:.3f}",
                        "-i", str(src), "-frames:v", "1", "-vf", "scale=1080:1920", str(f)],
                       check=True)
        return Image.open(f).convert("RGBA")
    return K.plate_falso()


def render(cenas, SCENES, glb, tag=""):
    import kit as K
    for s in cenas:
        fn, states, _ = SCENES[s]
        caminhos = []
        for st, fr in states.items():
            im = _plate(s, st, fr, glb)
            im.alpha_composite(fn(fr, overlay_only=True))
            out = K.OUTF / f"{s}{tag}_{st}.png"
            im.convert("RGB").save(out)
            caminhos.append(out)
            print(f"  {out.name}  (frame {fr})", flush=True)
        K.folha_de_estados(caminhos, K.OUTF / f"{s}{tag}_ESTADOS.png",
                           rotulos=[f"{s} {st} {fr}" for st, fr in states.items()])
        print(f"  {s}{tag}_ESTADOS.png")


def check(SCENES, glb):
    """END tem que cair DEPOIS do ultimo evento, senao o estado mostra a peca pela metade."""
    ok = True
    for sc, (_, st, _) in SCENES.items():
        ev = glb[sc + "_EVENTS"]
        ultimo = max(b for k, (a, b) in ev.items() if k not in CONTINUOS)
        bom = st["END"] >= ultimo
        ok &= bom
        print(f"  {sc}: ultimo evento {ultimo:3d}  END {st['END']:3d}  "
              f"{'OK' if bom else 'END ANTES DO FIM <<<'}")
    return ok


def main(SCENES, glb):
    if "--check" in sys.argv:
        sys.exit(0 if check(SCENES, glb) else 1)
    pedidas = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SCENES)
    render(pedidas, SCENES, glb)
