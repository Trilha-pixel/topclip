#!/usr/bin/env python3
"""
Renderiza a galeria das receitas do kit: os 4 estados de cada cena-exemplo do
`lib/compose_template.py`, lado a lado, em `exemplo/receitas/`.

    ./topclip py .claude/skills/topclip-motion/exemplo/gerar_receitas.py

Roda num projeto LIMPO, criado por `./topclip motion novo` numa pasta temporaria —
so com o que a skill entrega. E o teste de instalacao limpa (armadilha 31): constante
fora do modulo, asset que nao existe na biblioteca, nome divergindo entre kit e
template — tudo isso so aparece aqui, nao na leitura.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
DESTINO = AQUI / "receitas"

# cena do template -> nome do arquivo da galeria
GALERIA = {
    "M1": "M1_mesa-de-pesquisa",
    "R1": "R1_barras-em-hachura",
    "R2": "R2_item-riscado",
    "R3": "R3_etiqueta-de-preco",
    "R4": "R4_tira-no-topo",
    "R5": "R5_conta-a-mao",
}
LARGURA = 300          # cada estado a 300px: a leitura do laudo D2 ("legivel a 300px?")


def projeto_limpo(pasta):
    """Um projeto de motion como o usuario recebe, pelo lancador de verdade."""
    subprocess.run(["bash", str(RAIZ / "topclip"), "motion", "novo", str(pasta)],
                   check=True, stdout=subprocess.DEVNULL)
    return pasta


def renderiza(pasta, cenas=None):
    """Os estados das cenas, com o Python da venv. Devolve a saida (com os avisos)."""
    r = subprocess.run([sys.executable, "compose.py", *(cenas or [])], cwd=pasta,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"compose.py falhou:\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def main():
    cenas = [a for a in sys.argv[1:] if not a.startswith("--")] or list(GALERIA)
    with tempfile.TemporaryDirectory(prefix="topclip-receitas-") as tmp:
        pasta = projeto_limpo(Path(tmp) / "motion")
        r = subprocess.run([sys.executable, "compose.py", "--check"], cwd=pasta,
                           capture_output=True, text=True)
        print(r.stdout.rstrip())
        if r.returncode != 0:
            raise SystemExit("compose.py --check falhou")
        print(renderiza(pasta, cenas).rstrip())
        DESTINO.mkdir(exist_ok=True)
        for c in cenas:
            src = pasta / "08_images" / "frames" / f"{c}_ESTADOS.png"
            im = Image.open(src)
            s = LARGURA / 360
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            out = DESTINO / f"{GALERIA[c]}.png"
            # 256 cores com dither: no grao do papel nao se ve a diferenca, e o arquivo
            # cai pela metade (o repositorio e publico)
            im.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT,
                                       dither=Image.Dither.FLOYDSTEINBERG).save(
                out, optimize=True)
            print(f"  -> {out.relative_to(RAIZ)}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
