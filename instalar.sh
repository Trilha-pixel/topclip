#!/usr/bin/env bash
# Instalador do TopClip. Roda no macOS (Homebrew) e no Linux (apt).
# No Windows, use o WSL (Ubuntu) e rode este mesmo script lá dentro.
#
#   ./topclip instalar            instala tudo
#   ./topclip instalar --sem-whisper   pula a transcrição (faster-whisper e mlx-whisper)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
MODELOS="$ROOT/.claude/skills/topclip-corte/models"
YUNET="$MODELOS/face_detection_yunet_2023mar.onnx"
YUNET_URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

COM_WHISPER=1
for arg in "$@"; do
    case "$arg" in
        --sem-whisper) COM_WHISPER=0 ;;
        *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done

passo() { printf '\n==> %s\n' "$1"; }

python_ok() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null
}

achar_python() {
    for c in python3.13 python3.12 python3.11 python3.10 python3; do
        local p
        p="$(command -v "$c" 2>/dev/null || true)"
        if [ -n "$p" ] && python_ok "$p"; then echo "$p"; return 0; fi
    done
    return 1
}

passo "Dependências do sistema (ffmpeg e Python 3.10+)"
SO="$(uname -s)"
if [ "$SO" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "ERRO: Homebrew não encontrado. Instale em https://brew.sh e rode de novo." >&2
        exit 1
    fi
    command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
    achar_python >/dev/null || brew install python@3.11
elif [ "$SO" = "Linux" ]; then
    if command -v apt-get >/dev/null 2>&1; then
        precisa=()
        command -v ffmpeg >/dev/null 2>&1 || precisa+=(ffmpeg)
        achar_python >/dev/null || precisa+=(python3 python3-venv)
        if [ ${#precisa[@]} -gt 0 ]; then
            sudo apt-get update && sudo apt-get install -y "${precisa[@]}"
        fi
    else
        echo "Instale ffmpeg e Python 3.10+ pelo gerenciador da sua distro e rode de novo."
    fi
else
    echo "ERRO: sistema $SO não suportado direto. No Windows, use o WSL (Ubuntu)." >&2
    exit 1
fi

PYTHON="$(achar_python)" || { echo "ERRO: nenhum Python 3.10+ encontrado." >&2; exit 1; }
echo "ffmpeg: $(command -v ffmpeg)"
echo "python: $PYTHON ($("$PYTHON" --version))"

passo "Ambiente Python em .venv/"
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
if [ "$COM_WHISPER" = 1 ]; then
    "$VENV/bin/python" -m pip install --quiet -r "$ROOT/requirements.txt"
else
    grep -v -i "faster-whisper" "$ROOT/requirements.txt" > "$VENV/requirements-sem-whisper.txt"
    "$VENV/bin/python" -m pip install --quiet -r "$VENV/requirements-sem-whisper.txt"
fi

# Mac com Apple Silicon: transcrição na GPU (mlx-whisper), 2 a 2,5x mais rápida que
# o faster-whisper na CPU (medido num M2), que fica instalado como reserva. --no-deps porque o
# mlx-whisper lista o torch (~400 MB) só para um módulo de teste que nunca é
# carregado; as dependências que ele usa de fato vão na linha de cima. Falhar aqui
# (macOS antigo, sem rede) não para a instalação: a transcrição cai na CPU.
if [ "$COM_WHISPER" = 1 ] && "$VENV/bin/python" -c 'import platform, sys; sys.exit(0 if sys.platform == "darwin" and platform.machine() == "arm64" else 1)'; then
    passo "Transcrição na GPU do Mac (mlx-whisper)"
    if "$VENV/bin/python" -m pip install --quiet "mlx>=0.11" numba scipy tiktoken more-itertools tqdm huggingface_hub \
        && "$VENV/bin/python" -m pip install --quiet --no-deps "mlx-whisper>=0.4.3,<0.5"; then
        echo "mlx-whisper instalado: a transcrição usa a GPU do Mac"
    else
        echo "aviso: mlx-whisper não instalou; a transcrição vai usar a CPU (faster-whisper), mais devagar"
    fi
fi

passo "Modelo de detecção de rosto (YuNet, OpenCV Zoo, licença MIT)"
mkdir -p "$MODELOS"
if [ ! -s "$YUNET" ]; then
    curl -fL --retry 3 -o "$YUNET.part" "$YUNET_URL"
    # Um ponteiro do Git LFS tem ~130 bytes; o modelo de verdade tem ~230 KB.
    if [ "$(wc -c < "$YUNET.part")" -lt 100000 ]; then
        rm -f "$YUNET.part"
        echo "ERRO: o download do YuNet veio incompleto. Tente de novo." >&2
        exit 1
    fi
    mv "$YUNET.part" "$YUNET"
fi
echo "YuNet: $YUNET"

chmod +x "$ROOT/topclip" "$ROOT/.claude/skills/topclip-corte/vch" 2>/dev/null || true

passo "Verificação"
"$ROOT/topclip" verificar || {
    echo
    echo "A verificação acusou problema acima. Corrija e rode ./topclip verificar de novo."
    exit 1
}

cat <<'FIM'

Pronto. Agora abra o Claude Code nesta pasta e peça, por exemplo:

    corta esse podcast: ~/Videos/meu-podcast.mp4

FIM
