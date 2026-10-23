#!/usr/bin/env bash
# Instalador do TopClip. Roda no macOS (Homebrew), no Linux (apt) e no Windows (winget),
# pelo Git Bash — o terminal que o Claude Code usa no Windows. No WSL vale o do Linux.
#
#   ./topclip instalar            instala tudo
#   ./topclip instalar --sem-whisper   pula a transcrição (faster-whisper e mlx-whisper)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
SO="$(uname -s)"
case "$SO" in MINGW*|MSYS*|CYGWIN*) SO=Windows ;; esac
VPY="$VENV/bin/python"
[ "$SO" = Windows ] && VPY="$VENV/Scripts/python.exe"
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

tem_js() {
    command -v deno >/dev/null 2>&1 || command -v node >/dev/null 2>&1 || command -v bun >/dev/null 2>&1
}

achar_python() {
    local c p
    for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
        p="$(command -v "$c" 2>/dev/null || true)"
        if [ -n "$p" ] && python_ok "$p"; then echo "$p"; return 0; fi
    done
    if [ "$SO" = Windows ]; then
        # O winget instala em AppData sem mexer no PATH deste terminal; o `py` acha os outros.
        for p in "$(py -3 -c 'import sys; print(sys.executable)' 2>/dev/null | tr -d '\r')" \
                 "$(cygpath -u "${LOCALAPPDATA:-}")"/Programs/Python/Python31{3,2,1,0}/python.exe; do
            if [ -n "$p" ] && [ -f "$p" ] && python_ok "$p"; then echo "$p"; return 0; fi
        done
    fi
    return 1
}

# Windows: o winget põe ffmpeg e Deno em WinGet/Links, que só entra no PATH dos terminais
# abertos depois. O ./topclip faz o mesmo a cada comando.
path_winget() {
    local d
    for d in "${LOCALAPPDATA:-}/Microsoft/WinGet/Links" "${PROGRAMFILES:-}/WinGet/Links" \
             "${USERPROFILE:-}/.deno/bin"; do
        d="$(cygpath -u "$d" 2>/dev/null || echo "$d")"
        [ -d "$d" ] && PATH="$PATH:$d"
    done
    export PATH
}

winget_instala() {
    echo "instalando $1 pelo winget..."
    # Já instalado (só fora do PATH) também sai com erro: quem decide é a checagem depois.
    winget install --id "$1" --exact --silent --accept-package-agreements \
        --accept-source-agreements "${@:2}" || true
}

passo "Dependências do sistema (ffmpeg, Python 3.10+ e JavaScript para o YouTube)"
if [ "$SO" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "ERRO: Homebrew não encontrado. Instale em https://brew.sh e rode de novo." >&2
        exit 1
    fi
    command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
    achar_python >/dev/null || brew install python@3.11
    # baixar do YouTube por link: o yt-dlp precisa de um interpretador de JavaScript
    tem_js || brew install deno
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
    # o Node do apt costuma ser velho demais para o yt-dlp: o Deno vem do site oficial
    tem_js || echo "aviso: para baixar vídeo do YouTube por link, instale o Deno: https://deno.com"
elif [ "$SO" = Windows ]; then
    path_winget
    precisa=0
    command -v ffmpeg >/dev/null 2>&1 || precisa=1
    achar_python >/dev/null || precisa=1
    tem_js || precisa=1
    if [ "$precisa" = 1 ] && ! command -v winget >/dev/null 2>&1; then
        echo "ERRO: não achei o winget, que instala os programas no Windows." >&2
        echo "      Atualize o \"Instalador de Aplicativo\" na Microsoft Store e rode de novo." >&2
        exit 1
    fi
    command -v ffmpeg >/dev/null 2>&1 || winget_instala Gyan.FFmpeg
    achar_python >/dev/null || winget_instala Python.Python.3.11 --scope user
    tem_js || winget_instala DenoLand.Deno
    path_winget
    command -v ffmpeg >/dev/null 2>&1 || {
        echo "ERRO: o ffmpeg não ficou disponível. Feche e abra o Claude (ou o terminal) e rode de novo." >&2
        exit 1
    }
    tem_js || echo "aviso: sem o Deno, baixar vídeo do YouTube por link não funciona: https://deno.com"
else
    echo "ERRO: sistema $SO não suportado. Use macOS, Linux ou Windows (pelo Git Bash)." >&2
    exit 1
fi

PYTHON="$(achar_python)" || { echo "ERRO: nenhum Python 3.10+ encontrado." >&2; exit 1; }
echo "ffmpeg: $(command -v ffmpeg)"
echo "python: $PYTHON ($("$PYTHON" --version))"

passo "Ambiente Python em .venv/"
[ -x "$VPY" ] || "$PYTHON" -m venv "$VENV"
"$VPY" -m pip install --quiet --upgrade pip
if [ "$COM_WHISPER" = 1 ]; then
    "$VPY" -m pip install --quiet -r "$ROOT/requirements.txt"
else
    grep -v -i "faster-whisper" "$ROOT/requirements.txt" > "$VENV/requirements-sem-whisper.txt"
    "$VPY" -m pip install --quiet -r "$VENV/requirements-sem-whisper.txt"
fi
# O YouTube muda e yt-dlp velho para de baixar: rodar o instalador de novo atualiza.
"$VPY" -m pip install --quiet --upgrade "yt-dlp[default]" \
    || echo "aviso: não consegui atualizar o yt-dlp; baixar por link pode falhar no YouTube"

# Mac com Apple Silicon: transcrição na GPU (mlx-whisper), 2 a 2,5x mais rápida que
# o faster-whisper na CPU (medido num M2), que fica instalado como reserva. --no-deps porque o
# mlx-whisper lista o torch (~400 MB) só para um módulo de teste que nunca é
# carregado; as dependências que ele usa de fato vão na linha de cima. Falhar aqui
# (macOS antigo, sem rede) não para a instalação: a transcrição cai na CPU.
if [ "$COM_WHISPER" = 1 ] && "$VPY" -c 'import platform, sys; sys.exit(0 if sys.platform == "darwin" and platform.machine() == "arm64" else 1)'; then
    passo "Transcrição na GPU do Mac (mlx-whisper)"
    if "$VPY" -m pip install --quiet "mlx>=0.11" numba scipy tiktoken more-itertools tqdm huggingface_hub \
        && "$VPY" -m pip install --quiet --no-deps "mlx-whisper>=0.4.3,<0.5"; then
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

EXEMPLO="~/Videos/meu-podcast.mp4"
[ "$SO" = Windows ] && EXEMPLO='C:\Users\voce\Videos\meu-podcast.mp4'
cat <<FIM

Pronto. Agora abra o Claude Code nesta pasta e peça, por exemplo:

    corta esse podcast: $EXEMPLO

FIM
