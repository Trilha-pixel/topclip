#!/usr/bin/env python3
"""
Checagem de instalacao. Rode ANTES do primeiro projeto:

    ./topclip verificar

Verifica o que a skill precisa e o que ela carrega junto. Sai com codigo != 0 se algo
essencial faltar, para nao descobrir no meio de um render de 20 minutos.
"""
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
falhas, avisos = [], []


def ok(t):
    print(f"  \033[32mok\033[0m    {t}")


def erro(t):
    print(f"  \033[31mFALTA\033[0m {t}")
    falhas.append(t)


def aviso(t):
    print(f"  \033[33maviso\033[0m {t}")
    avisos.append(t)


print(f"TOPCLIP PAPEL — verificacao\n  skill em {S}\n")

print("python")
if sys.version_info < (3, 10):
    erro(f"python {sys.version_info.major}.{sys.version_info.minor} — precisa 3.10+ (./topclip instalar)")
else:
    ok(f"python {sys.version_info.major}.{sys.version_info.minor}")

print("\nbibliotecas")
for mod, pip in [("PIL", "Pillow"), ("numpy", "numpy"), ("cv2", "opencv-contrib-python")]:
    try:
        importlib.import_module(mod)
        ok(pip)
    except ImportError:
        erro(f"{pip}   ->  ./topclip instalar")
try:
    importlib.import_module("faster_whisper")
    ok("faster-whisper")
except ImportError:
    erro("faster-whisper   ->  ./topclip instalar")

print("\nferramentas")
for exe in ("ffmpeg", "ffprobe"):
    if shutil.which(exe):
        v = subprocess.run([exe, "-version"], capture_output=True, text=True)
        ok(f"{exe}  {v.stdout.splitlines()[0].split(' version ')[-1][:24]}")
    else:
        erro(f"{exe}   ->  brew install ffmpeg  |  apt install ffmpeg")

print("\nkit que viaja com a skill")
fontes = sorted((S / "fontes").glob("*.ttf"))
(ok if len(fontes) >= 9 else erro)(f"{len(fontes)} fontes em fontes/ (esperado 9)")
# A biblioteca comeca vazia e cresce com o uso: cada asset desenhado num video
# volta para ca. Vazia nao impede nada — o Claude desenha o que faltar.
BIBLIOTECA = S.parents[2] / "biblioteca" / "assets"
assets = sorted(BIBLIOTECA.glob("*.png"))
(ok if assets else aviso)(f"{len(assets)} asset(s) em biblioteca/assets/"
                          + ("" if assets else " — o Claude desenha o que faltar"))
for f in ("lib/motor.py", "lib/kit.py", "lib/desenho.py", "lib/captions.py",
          "lib/cutout.py", "lib/crt.py", "lib/night_photo.py", "lib/render_template.py",
          "lib/compose_template.py", "lib/transcrever.py", "referencias/legenda.md",
          "referencias/armadilhas.md", "referencias/receitas.md", "IDENTIDADE.md"):
    (ok if (S / f).exists() else erro)(f)
# O que o template e o kit pedem por nome. Faltando na biblioteca, o kit desenha na
# hora (desenho.py) — so nao pode faltar nos dois lugares.
sys.path.insert(0, str(S / "lib"))
try:
    import desenho as D
    for nome in ("BG_PAPER", "A02_CLOCK", "A03_TAPE", "A04_CLIPS", "A05_CARD",
                 "A05_SHEET", "A10_SCRAPS"):
        if (BIBLIOTECA / f"{nome}.png").exists():
            ok(f"{nome}.png na biblioteca")
        elif nome in D.ASSETS:
            aviso(f"{nome}.png fora da biblioteca — o kit desenha na hora "
                  f"(./topclip py .claude/skills/topclip-motion/lib/desenho.py "
                  f"biblioteca/assets --so {nome})")
        else:
            erro(f"{nome}: nem na biblioteca nem em desenho.ASSETS")
except Exception as e:
    erro(f"desenho.py: {type(e).__name__}: {e}")

print("\nmotor")
try:
    import motor as V
    f = V.font(V.F_BLACK, 80)
    w = V.text_width("MOTION", V.F_BLACK, 80, -1.8)
    ok(f"motor carrega e mede tipo ({w:.0f}px para 'MOTION' em 80px)")
    im = V.boil_full(V.text_layer((400, 200), "topclip", V.F_BLACK, 90, (200, 100),
                                  anchor="mm"), 0.0, **V.BOIL_PRESETS["print"])
    ok(f"boil preset 'print' aplica ({im.size[0]}x{im.size[1]})")
    if V.glifo(V.F_MARKER, "≈") != "ok" and V.glifo(V.F_MARKER, "A") == "ok":
        ok("detecta glifo que a fonte nao tem ('≈' no marcador sai desenhado)")
    else:
        erro("deteccao de glifo ausente nao funciona")
except Exception as e:
    erro(f"motor: {type(e).__name__}: {e}")
try:
    import captions as CAP
    CAP.blocos()
    erro("captions deveria exigir configurar() e nao exigiu")
except RuntimeError:
    ok("captions exige configurar() antes de rodar")
except Exception as e:
    erro(f"captions: {type(e).__name__}: {e}")
try:
    if CAP._modelo_yunet():
        ok("YuNet encontrado: a legenda se posiciona pelo rosto")
    else:
        aviso("YuNet ausente (./topclip instalar) — a legenda acha o rosto pela "
              "cascata Haar do OpenCV, menos precisa")
except Exception as e:
    erro(f"captions: {type(e).__name__}: {e}")

print("\nmodelo de transcricao")
try:
    from huggingface_hub import scan_cache_dir
    nomes = [r.repo_id for r in scan_cache_dir().repos]
    if any("large-v3-turbo" in n for n in nomes):
        ok("large-v3-turbo em cache")
    else:
        aviso("large-v3-turbo nao esta em cache — baixa ~1,5 GB no primeiro uso")
except Exception:
    aviso("nao deu para checar o cache do modelo (baixa no primeiro uso)")

print()
if falhas:
    print(f"\033[31m{len(falhas)} item(ns) faltando.\033[0m Resolva antes de comecar.")
    sys.exit(1)
print("\033[32mTudo pronto.\033[0m Peça motion ao Claude, ou leia SKILL.md, secao 'Ordem de execucao'."
      + (f"  ({len(avisos)} aviso(s))" if avisos else ""))
