#!/usr/bin/env python3
"""
Baixa o vídeo de um link (YouTube, Instagram e a maioria dos sites de vídeo, pelo
yt-dlp) para dentro do projeto: `projetos/<nome>/video.mp4`.

    ./topclip baixar <link>                     cria projetos/<título-do-vídeo>/ e baixa
    ./topclip baixar <link> projetos/<nome>     baixa para esse projeto (cria se não existir)
    ./topclip baixar projetos/<nome>            baixa o link que o painel gravou no projeto.json,
                                                ou espera o download que o painel já começou

    --nome "Podcast com a Ana"       nome do projeto, ao criar (padrão: o título do vídeo)
    --cookies-do-navegador chrome    usa o login do navegador — para o Instagram que pede login

No fim imprime `VIDEO=<caminho>` e grava em `projeto.json`: video, link, titulo, duracao
e, no YouTube, `legenda` — a legenda automática no idioma original, com tempo por palavra,
que a topclip-corte usa no lugar do Whisper (fases/1-momentos.md).

Vai até 1080p, com H.264 e AAC quando o site oferece: é a fonte para a qual o
enquadramento foi calibrado (`max_zoom` no config) e decodifica rápido. 4K num podcast
de 3h passa de 10 GB e deixa a transcrição e o autoframe mais lentos sem ganho no 9:16.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import fcntl
except ImportError:      # Windows
    fcntl = None
    import msvcrt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atividade as ATV  # noqa: E402
import servidor  # noqa: E402  — slug, criar_projeto e a pasta projetos/ são os do painel

TRAVA = ".baixando"
NAVEGADORES = ("chrome", "safari", "firefox", "edge", "brave", "opera", "chromium", "vivaldi")
INTERVALO_PAINEL_S = 3      # progresso no diário: algumas vezes por minuto, como a transcrição
INTERVALO_TERMINAL_PCT = 10
# Toda notícia do download: `origem` deixa o painel separar o download do trabalho do
# Claude (vídeo baixado não é "o Claude começou"); a etapa é a primeira, a dos momentos.
ANOTAR = {"origem": "baixar", "etapa": "momentos"}


class ErroDownload(Exception):
    """Erro já em português de gente, pronto para o painel e o terminal."""


def eh_link(texto: str) -> bool:
    return bool(re.fullmatch(r"https?://[^\s/$.?#][^\s]*", (texto or "").strip(), re.IGNORECASE))


def site(link: str) -> str:
    host = (urlparse(link).hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host in ("youtu.be", "youtube.com", "music.youtube.com") or host.endswith(".youtube.com"):
        return "YouTube"
    if host in ("instagram.com", "instagr.am") or host.endswith(".instagram.com"):
        return "Instagram"
    return host or "o site"


def duracao_txt(seg) -> str:
    try:
        s = int(float(seg))
    except (TypeError, ValueError):
        return ""
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h{m:02d}" if h else f"{m}min{s:02d}s" if m else f"{s}s"


def _mb(n) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB".replace(".", ",")
    if n < 1e6:
        return f"{n / 1e3:.0f} KB"
    return f"{n / 1e6:.0f} MB" if n >= 10e6 else f"{n / 1e6:.1f} MB".replace(".", ",")


def titulo_do_video(v: dict, s: str) -> str:
    """O Instagram chama todo Reel de "Video by <perfil>": vale mais a legenda do post."""
    titulo = (v.get("title") or "").strip()
    if s == "Instagram":
        perfil = v.get("channel") or v.get("uploader_id") or ""
        legenda = re.sub(r"[#@]\S+", "", ((v.get("description") or "").strip().splitlines() or [""])[0]).strip()
        if len(re.findall(r"\w", legenda)) >= 6:
            return legenda[:80].strip()
        return f"Reel de @{perfil}" if perfil else "Reel do Instagram"
    return titulo or "Vídeo sem título"


def duracao_do_arquivo(p: Path):
    """O Instagram nem sempre informa a duração: o ffprobe mede no arquivo baixado."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return round(float(out), 1)
    except Exception:
        return None


class _Calado:
    """O yt-dlp imprime o erro em inglês mesmo com quiet; aqui ele vira ErroDownload em português."""

    def debug(self, msg):
        pass

    info = warning = error = debug


def opcoes(cookies: str | None = None) -> dict:
    # Desde o fim de 2025 o YouTube só libera os formatos bons para quem resolve o
    # desafio em JavaScript dele. O yt-dlp usa o primeiro destes que achar instalado.
    o = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",     # link de playlist: recusa sem abrir vídeo por vídeo
        "logger": _Calado(),
        "js_runtimes": {"deno": {}, "node": {}, "bun": {}},
        "format": "bv*+ba/b",
        "format_sort": ["res:1080", "vcodec:h264", "acodec:aac"],
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
    }
    if cookies:
        if cookies not in NAVEGADORES:
            raise ErroDownload(f"Navegador desconhecido: {cookies}. Use um de: {', '.join(NAVEGADORES)}.")
        o["cookiesfrombrowser"] = (cookies,)
    return o


def traduzir(e: Exception, link: str) -> ErroDownload:
    """O erro do yt-dlp vem em inglês técnico; a pessoa precisa saber o que fazer."""
    if isinstance(e, ErroDownload):
        return e
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "").strip()
    baixo = msg.lower()
    s = site(link)
    if "unsupported url" in baixo:
        return ErroDownload("Não sei baixar desse link. Cole o link de um vídeo do YouTube ou do Instagram.")
    if "ffmpeg" in baixo:
        return ErroDownload("O ffmpeg não foi encontrado para juntar vídeo e áudio. Rode ./topclip instalar.")
    if any(t in baixo for t in ("javascript", "js runtime", "challenge", "requested format is not available")):
        return ErroDownload("O YouTube não liberou o vídeo: falta um interpretador de JavaScript (Deno ou "
                            "Node). Rode ./topclip instalar e tente de novo.")
    if any(t in baixo for t in ("unable to extract", "nsig", "signature extraction", "please update")):
        return ErroDownload(f"O {s} mudou algo e o baixador precisa de atualização. Rode ./topclip instalar "
                            f"(atualiza o yt-dlp) e tente de novo.")
    if any(t in baixo for t in ("sign in", "login required", "log in", "rate-limit", "rate limit",
                                "--cookies", "age-restricted", "confirm your age", "members-only")):
        return ErroDownload(
            f"O {s} pediu login para liberar esse vídeo. Peça ao Claude para baixar com o login "
            f"do seu navegador (./topclip baixar <link> --cookies-do-navegador chrome) ou baixe o "
            f"vídeo pelo navegador e use “Escolher vídeo no computador”.")
    if any(t in baixo for t in ("private video", "unavailable", "this video is not available",
                                "has been removed", "does not exist", "404")):
        return ErroDownload(f"Esse vídeo é privado, foi apagado ou não existe mais no {s}. Confira o link.")
    if any(t in baixo for t in ("timed out", "connection", "network", "getaddrinfo", "temporary failure")):
        return ErroDownload(f"A conexão com o {s} caiu. Confira a internet e tente de novo — o download "
                            f"continua de onde parou.")
    primeira = msg.splitlines()[0] if msg else type(e).__name__
    return ErroDownload(f"Não consegui baixar do {s}: {primeira[:300]}")


def _video_unico(bruto: dict) -> dict:
    if bruto.get("_type") in ("playlist", "multi_video"):
        entradas = [x for x in (bruto.get("entries") or []) if x]
        if len(entradas) == 1 and entradas[0].get("_type") != "url":
            return entradas[0]
        raise ErroDownload("Esse link tem vários vídeos (playlist ou carrossel). Cole o link de um vídeo só.")
    if bruto.get("live_status") in ("is_live", "is_upcoming"):
        raise ErroDownload("Essa live ainda não terminou. Espere acabar e cole o link de novo.")
    return bruto


def info(link: str, cookies: str | None = None) -> dict:
    """Título, duração e canal — para o painel confirmar o vídeo antes de criar o projeto."""
    link = (link or "").strip()
    if not eh_link(link):
        raise ErroDownload("Isso não parece um link. Cole o endereço completo, começando com https://")
    try:
        import yt_dlp
    except ImportError:
        raise ErroDownload("Falta o yt-dlp, que baixa vídeos de links. Rode ./topclip instalar.") from None
    try:
        with yt_dlp.YoutubeDL(opcoes(cookies)) as y:
            v = _video_unico(y.extract_info(link, download=False))
    except Exception as e:
        raise traduzir(e, link) from None
    return {
        "link": link,
        "site": site(link),
        "titulo": titulo_do_video(v, site(link)),
        "canal": v.get("channel") or v.get("uploader") or "",
        "duracao": v.get("duration"),
        "duracao_txt": duracao_txt(v.get("duration")),
    }


def legenda_original(v: dict) -> tuple[str, str] | None:
    """
    A legenda automática do YouTube no idioma em que se fala no vídeo: `pt-orig`.
    As outras (`pt`, `es`…) são traduções e perdem o tempo por palavra. Vídeo dublado
    lista um `-orig` por faixa de áudio — vale a do idioma do vídeo.
    """
    auto = v.get("automatic_captions") or {}
    originais = [k for k in auto if k.endswith("-orig")]
    idioma = (v.get("language") or "").split("-")[0].lower()
    chave = next((k for k in originais if k.split("-")[0].lower() == idioma), None) if idioma else None
    if not chave and len(originais) == 1:
        chave = originais[0]
    if not chave:
        return None
    url = next((f.get("url") for f in auto[chave] if f.get("ext") == "vtt" and f.get("url")), None)
    return (chave, url) if url else None


# ------------------------------------------------------------------ projeto
def pasta_do_projeto(arg: str) -> Path:
    """`projetos/<nome>` (relativo à raiz ou absoluto). Nada do usuário sai de projetos/."""
    p = Path(arg).expanduser()
    if not p.is_absolute():
        p = servidor.RAIZ / p
    p = p.resolve()
    if p.parent != servidor.PROJETOS.resolve() or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", p.name):
        raise ErroDownload(f"O destino precisa ser projetos/<nome> (minúsculas e hífen): {arg}")
    return p


def ler_projeto(proj: Path) -> dict:
    try:
        return json.loads((proj / "projeto.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def gravar_projeto(proj: Path, **campos) -> None:
    dados = {**ler_projeto(proj), **campos}
    tmp = proj / "projeto.json.tmp"
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(proj / "projeto.json")


def ja_baixado(proj: Path, link: str) -> Path | None:
    dados = ler_projeto(proj)
    v = Path(dados.get("video") or "")
    if dados.get("link") == link and v.name and v.is_file():
        return v
    return None


def criar_do_link(link: str, nome: str | None, cookies: str | None) -> Path:
    """`./topclip baixar <link>` sem projeto: cria um com o nome do vídeo, como o painel faria."""
    if not nome:
        nome = info(link, cookies)["titulo"]
    base = servidor.slug(nome)
    for n in range(1, 100):
        pasta = base if n == 1 else f"{base}-{n}"     # dois Reels do mesmo perfil: reel-de-x, reel-de-x-2
        proj = servidor.PROJETOS / pasta
        if ler_projeto(proj).get("link") == link:
            return proj                               # o mesmo link de novo: retoma, não duplica
        if not proj.exists():
            return servidor.PROJETOS / servidor.criar_projeto(nome, "", link=link, pasta=pasta)["slug"]
    raise ErroDownload(f"Já existem projetos demais chamados {base}. Dê outro nome com --nome \"...\".")


# ------------------------------------------------------------------ download
class Andamento:
    """Gancho do yt-dlp: anota o avanço no diário (a barra do painel) e, mais espaçado, no terminal."""

    def __init__(self, proj: Path, ident: str):
        self.proj, self.ident = proj, ident
        self.ultimo_painel = 0.0
        self.ultimo_pct_terminal: dict[str, int] = {}

    def __call__(self, d: dict) -> None:
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        feito = d.get("downloaded_bytes") or 0
        if not total:
            return
        pct = max(0, min(100, int(feito * 100 / total)))
        fmt = d.get("info_dict") or {}
        oque = "o áudio" if fmt.get("vcodec") == "none" else "o vídeo"
        msg = f"baixando {oque}: {_mb(feito)} de {_mb(total)} ({pct}%)"
        agora = time.monotonic()
        if agora - self.ultimo_painel >= INTERVALO_PAINEL_S:
            self.ultimo_painel = agora
            ATV.registrar(self.proj, msg, tipo="progresso", pct=pct, id=self.ident, **ANOTAR)
        marco = pct // INTERVALO_TERMINAL_PCT
        if self.ultimo_pct_terminal.get(oque) != marco:
            self.ultimo_pct_terminal[oque] = marco
            print(f"  {msg}", flush=True)


def _travar(arquivo, esperar: bool) -> bool:
    """Trava exclusiva no arquivo; sem `esperar`, False se outro processo já tem."""
    if fcntl:
        try:
            fcntl.flock(arquivo, fcntl.LOCK_EX | (0 if esperar else fcntl.LOCK_NB))
            return True
        except BlockingIOError:
            return False
    while True:          # Windows: o LK_LOCK desiste em 10 s, então a espera é aqui
        try:
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if not esperar:
                return False
            time.sleep(1)


def baixar(link: str, proj: Path, cookies: str | None = None) -> Path:
    """Baixa para `proj/video.mp4`. Dois pedidos para o mesmo projeto: o segundo espera o primeiro."""
    proj.mkdir(parents=True, exist_ok=True)
    with (proj / TRAVA).open("w") as trava:
        if not _travar(trava, esperar=False):
            print("Já tem um download deste projeto rodando (o painel começou). Esperando terminar…", flush=True)
            _travar(trava, esperar=True)
        pronto = ja_baixado(proj, link)
        if pronto:
            return pronto
        return _baixar_travado(link, proj, cookies)


def _baixar_travado(link: str, proj: Path, cookies: str | None) -> Path:
    ident = f"{os.getpid()}-{int(time.time())}"
    s = site(link)
    ATV.registrar(proj, f"baixando o vídeo do {s}", tipo="inicio", id=ident, pid=os.getpid(),
                  comando=f"baixar {link}"[:200], **ANOTAR)
    t0 = time.monotonic()
    try:
        import yt_dlp
    except ImportError:
        erro = ErroDownload("Falta o yt-dlp, que baixa vídeos de links. Rode ./topclip instalar.")
        ATV.registrar(proj, str(erro), tipo="erro", id=ident, codigo=1, **ANOTAR)
        raise erro from None
    if not shutil.which("ffmpeg"):
        erro = traduzir(Exception("ffmpeg not found"), link)
        ATV.registrar(proj, str(erro), tipo="erro", id=ident, codigo=1, **ANOTAR)
        raise erro

    o = opcoes(cookies)
    o.update(outtmpl=str(proj / "video.%(ext)s"), progress_hooks=[Andamento(proj, ident)],
             postprocessors=[{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}])
    try:
        with yt_dlp.YoutubeDL(o) as y:
            v = _video_unico(y.extract_info(link, download=False))
            titulo = titulo_do_video(v, s)
            dur = duracao_txt(v.get("duration"))
            print(f"{s}: {titulo}" + (f" ({dur})" if dur else ""), flush=True)
            leg = legenda_original(v) if s == "YouTube" else None
            ATV.registrar(proj, f"achei o vídeo: {titulo}", tipo="info", **ANOTAR)
            final = y.process_ie_result(v, download=True)
            caminho = Path(((final.get("requested_downloads") or [{}])[0]).get("filepath") or "")
            if not caminho.is_file():
                caminho = next(iter(sorted(proj.glob("video.mp4")) or sorted(proj.glob("video.*"))), Path())
            if not caminho.is_file():
                raise ErroDownload("O download terminou, mas o arquivo do vídeo não apareceu na pasta do projeto.")
            legenda = _baixar_legenda(y, leg, proj) if leg else None
    except Exception as e:
        erro = traduzir(e, link)
        ATV.registrar(proj, str(erro), tipo="erro", id=ident, codigo=1, **ANOTAR)
        raise erro from None

    duracao = v.get("duration") or duracao_do_arquivo(caminho)
    campos = {"video": str(caminho), "link": link, "titulo": titulo, "duracao": duracao}
    if legenda:
        campos["legenda"] = str(legenda)
    gravar_projeto(proj, **campos)
    seg = int(time.monotonic() - t0)
    ATV.registrar(proj, f"vídeo baixado — {duracao_txt(duracao)}, {_mb(caminho.stat().st_size)}, "
                        f"em {duracao_txt(seg)}", tipo="fim", id=ident, codigo=0, **ANOTAR)
    return caminho


def _baixar_legenda(y, leg: tuple[str, str], proj: Path) -> Path | None:
    """Bônus: sem ela a transcrição cai no Whisper. Falhar aqui nunca derruba o download."""
    chave, url = leg
    try:
        texto = y.urlopen(url).read().decode("utf-8", "replace")
    except Exception:
        return None
    if "-->" not in texto:
        return None
    destino = proj / f"legenda.{chave}.vtt"
    destino.write_text(texto, encoding="utf-8")
    ATV.registrar(proj, "legenda automática do YouTube baixada (tempo por palavra)", tipo="info", **ANOTAR)
    return destino


# ------------------------------------------------------------------ linha de comando
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="./topclip baixar", description="Baixa o vídeo de um link para o projeto.")
    ap.add_argument("alvos", nargs="+", metavar="link | projetos/<nome>")
    ap.add_argument("--nome", help="nome do projeto, ao criar (padrão: o título do vídeo)")
    ap.add_argument("--cookies-do-navegador", dest="cookies", choices=NAVEGADORES,
                    help="usa o login deste navegador (Instagram que pede login)")
    a = ap.parse_args(argv)

    links = [x for x in a.alvos if eh_link(x)]
    pastas = [x for x in a.alvos if not eh_link(x)]
    if len(links) > 1 or len(pastas) > 1:
        ap.error("um link e/ou uma pasta de projeto por vez")
    try:
        proj = pasta_do_projeto(pastas[0]) if pastas else None
        link = links[0] if links else ""
        if proj and not link:
            link = ler_projeto(proj).get("link", "")
            if not link:
                video = ler_projeto(proj).get("video", "")
                if video and Path(video).is_file():
                    print(f"VIDEO={video}")
                    return 0
                raise ErroDownload(f"{proj.name} não tem link para baixar. Passe o link: ./topclip baixar <link> projetos/{proj.name}")
        if not link:
            ap.error("passe o link do vídeo")
        if proj is None:
            proj = criar_do_link(link, a.nome, a.cookies)
        elif not (proj / "projeto.json").exists():
            servidor.criar_projeto(a.nome or proj.name.replace("-", " ").capitalize(), "", link=link, pasta=proj.name)
        video = baixar(link, proj, a.cookies)
    except ErroDownload as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDownload interrompido. Rode o mesmo comando para continuar de onde parou.", file=sys.stderr)
        return 130
    info_proj = ler_projeto(proj)
    print(f"PROJETO=projetos/{proj.name}")
    print(f"VIDEO={video}")
    if info_proj.get("legenda"):
        print(f"LEGENDA={info_proj['legenda']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
