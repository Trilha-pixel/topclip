#!/usr/bin/env python3
"""
Os assets que VOCE desenhou nas suas runs. Mora em `minha-biblioteca/desenho.py`, fora
do git: atualizar o TopClip nunca mexe aqui, e aqui nunca da conflito no `git pull`.

Molde: `.claude/skills/topclip-motion/exemplo/desenho_usuario.py`. Copie uma vez:

    mkdir -p minha-biblioteca && cp .claude/skills/topclip-motion/exemplo/desenho_usuario.py minha-biblioteca/desenho.py

Desenhe como no `lib/desenho.py` da skill (as ferramentas vem de la: textura, contorno,
mascara, para_rgba...), registre em ASSETS e gere:

    ./topclip py minha-biblioteca/desenho.py minha-biblioteca/assets --so <NOME>

O PNG vai para `minha-biblioteca/assets/`, com uma linha em `minha-biblioteca/MANIFESTO.md`
(mesma tabela do `biblioteca/MANIFESTO.md`). O `./topclip motion novo` copia esses assets
para todo projeto novo, junto com os oficiais.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "topclip-motion" / "lib"))
from desenho import *  # noqa: E402,F401,F403  — as ferramentas de desenho da skill


# Exemplo do formato (apague ao escrever o seu):
#
# def desenha_GARRAFA(seed=200):
#     h, w = 900, 360
#     ...                        # textura(), contorno(), mascara(), para_rgba()
#     return im                  # Image RGBA, sem sombra e sem texto


ASSETS = {
    # "GARRAFA": desenha_GARRAFA,
}


def main():
    ap = argparse.ArgumentParser(description="Desenha os seus assets em codigo")
    ap.add_argument("destino", help="normalmente minha-biblioteca/assets")
    ap.add_argument("--so", nargs="*", help="so estes nomes")
    a = ap.parse_args()
    out = Path(a.destino)
    out.mkdir(parents=True, exist_ok=True)
    for nome, fn in ASSETS.items():
        if a.so and nome not in a.so:
            continue
        im = fn()
        im.save(out / f"{nome}.png")
        print(f"  {nome}.png  {im.width}x{im.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
