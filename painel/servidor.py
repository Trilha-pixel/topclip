#!/usr/bin/env python3
"""
Painel do TopClip — servidor local.

    ./topclip painel                 abre em http://127.0.0.1:7777
    ./topclip painel --porta 8080 --sem-abrir

So a biblioteca padrao do Python: nada para instalar alem do que o TopClip ja tem.
Escuta apenas em 127.0.0.1 — o painel nunca fica visivel na rede.

O painel NAO substitui o Claude Code: quem escolhe momento, corta e compoe e o Claude.
O painel mostra o que a run produziu e grava as escolhas da pessoa em
`projetos/<nome>/escolhas.json`, que as skills leem em cada portao.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import threading
import unicodedata
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

RAIZ = Path(__file__).resolve().parent.parent
ESTATICO = Path(__file__).resolve().parent / "static"
PROJETOS = RAIZ / "projetos"
BIBLIOTECA = RAIZ / "biblioteca"
FONTES = RAIZ / ".claude" / "skills" / "topclip-motion" / "fontes"
DEMO = Path(__file__).resolve().parent / "demo"

VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("image/svg+xml", ".svg")


# ------------------------------------------------------------------ utilidades
def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:48] or "projeto"


def ler_json(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def dentro(p: Path, *raizes: Path) -> bool:
    """O caminho resolvido mora dentro de uma das raizes permitidas?"""
    try:
        r = p.resolve()
    except Exception:
        return False
    return any(r == b.resolve() or b.resolve() in r.parents for b in raizes)


def url_midia(p: Path) -> str:
    return "/midia/" + quote(str(p.resolve().relative_to(RAIZ.resolve())))


def mmss(seg) -> str:
    try:
        s = float(seg)
    except Exception:
        return "--:--"
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


# ------------------------------------------------------------------ leitura dos projetos
def run_mais_recente(proj: Path) -> Path | None:
    runs = sorted((proj / "runs").glob("*/00-manifest.json"), key=lambda p: p.stat().st_mtime)
    return runs[-1].parent if runs else None


def etapas(proj: Path, run: Path | None) -> dict:
    """Em que ponto o projeto esta, deduzido so dos arquivos que existem."""
    tem = lambda *ps: any((run / p).exists() for p in ps) if run else False
    verticais = list(run.glob("output/final-clips/*/*/clip-vertical.mp4")) if run else []
    motion = [p for p in (proj / "motion").glob("*") if (p / "compose.py").exists()]
    entregas = list((proj / "entregas").glob("*.mp4"))
    previews = list(run.glob("preview/*.mp4")) if run else []
    return {
        "momentos": "feito" if tem("05-viral-moments.json") else ("andamento" if run else "pendente"),
        "cortes": "feito" if (verticais or cortes_no_portao(run))
                  else ("andamento" if (previews or tem("06-candidates.json")) else "pendente"),
        "vertical": "feito" if verticais else "pendente",
        "motion": "feito" if any(any((m / "12_master").glob("*.mp4")) for m in motion)
                  else ("andamento" if motion else "pendente"),
        "entrega": "feito" if entregas else "pendente",
    }


# o que a fase 2 grava antes da nota dos cortes, o último passo antes do portão
ANTES_DA_NOTA = ("07-feed-review.json", "08-technical-audit.json", "09-blind-review.json",
                 "10-temporal-deduplication.json", "10-deduplication.json")


def cortes_no_portao(run: Path | None) -> bool:
    """A fase 2 parou no portão: é a vez da pessoa assistir e escolher os cortes.

    O 06 e as prévias saem logo depois do Clip Builder, e as revisões (subagentes, que
    não aparecem como processo) ainda levam minutos. O sinal é o último passo da fase,
    `./topclip corte estimate --cortes`: a nota em todo corte do 06, e o 06 mais novo que
    tudo o que a fase grava antes dela. Auditoria ou revisão mais nova que o 06 é rodada
    nova em andamento — o rebuild regrava o 06 copiando a nota velha.
    """
    cand = run / "06-candidates.json" if run else None
    if not cand or not cand.exists():
        return False
    doc = ler_json(cand, {}) or {}
    if "estimate_gate" not in doc and "estimate_gate" not in (ler_json(run / "05-viral-moments.json", {}) or {}):
        # run de antes do `estimate`: fica como era, o 06 basta. A nota nunca vai chegar, e
        # exigir as revisões tiraria o aviso para sempre de quem não as tem — a cópia antiga
        # do projeto de exemplo não tem 07 nem 09, e em aula-yt-teste o 09 é mais velho que o 06.
        return True
    cortes = doc.get("clips") or []
    if not cortes or any(nota_estimada(c) is None for c in cortes):
        return False
    nota = cand.stat().st_mtime_ns
    return all(p.stat().st_mtime_ns <= nota for p in (run / n for n in ANTES_DA_NOTA) if p.exists())


def resumo(proj: Path) -> dict:
    info = ler_json(proj / "projeto.json", {}) or {}
    run = run_mais_recente(proj)
    et = etapas(proj, run)
    ordem = ["momentos", "cortes", "vertical", "motion", "entrega"]
    ativ = atividade(proj)
    # quando é a vez da pessoa escolher, a etapa da escolha é a atual — não a seguinte
    atual = ativ["sua_vez"]["etapa"] if ativ["sua_vez"] else next((k for k in ordem if et[k] != "feito"), "entrega")
    capa = None
    for padrao in ("motion/*/08_images/frames/*_END.png", "motion/*/08_images/frames/*.png",
                   "motion/*/08_images/frames/*.jpg"):
        achados = sorted(proj.glob(padrao))
        if achados:
            capa = url_midia(achados[0])
            break
    momentos = ler_json(run / "05-viral-moments.json", {}) if run else {}
    return {
        "slug": proj.name,
        "nome": info.get("nome") or proj.name.replace("-", " ").title(),
        "video": info.get("video", ""),
        "criado": info.get("criado", ""),
        "etapas": et,
        "etapa_atual": atual,
        "n_momentos": len((momentos or {}).get("moments", [])),
        "capa": capa,
        "demo": bool(info.get("demo")),
        "atividade": ativ["estado"],
    }


ESTADOS = ["START", "MID", "END", "EXIT"]


def ordem_do_quadro(p: Path):
    """M1_START, M1_MID, M1_END, M1_EXIT — na ordem da cena, não na alfabética."""
    cena, _, estado = p.stem.rpartition("_")
    return (cena, ESTADOS.index(estado) if estado in ESTADOS else len(ESTADOS), p.name)


def detalhe(proj: Path) -> dict:
    base = resumo(proj)
    run = run_mais_recente(proj)
    escolhas = ler_json(proj / "escolhas.json", {}) or {}

    # A nota é a mesma conta do gate do finalize (`./topclip corte estimate`), antecipada:
    # nos momentos, sobre o que o Clip Hunter estimou; nos cortes, Builder + revisão de feed.
    doc_momentos = (ler_json(run / "05-viral-moments.json", {}) or {}) if run else {}
    momentos = []
    for m in doc_momentos.get("moments", []):
        momentos.append({**m, "inicio": mmss(m.get("start")), "fim": mmss(m.get("end")),
                         "nota": nota_estimada(m), "abaixo_do_gate": m.get("estimate_below_gate") or []})
    # a pergunta da pessoa é "quais prestam": melhor nota primeiro; sem nota, na ordem do Clip Hunter
    momentos.sort(key=lambda m: -m["nota"] if m["nota"] is not None else float("inf"))

    cortes = []
    doc_cortes = (ler_json(run / "06-candidates.json", {}) or {}) if run else {}
    previews = sorted(run.glob("preview/*.mp4")) if run else []
    ids = [str(c.get("id", "")) for c in doc_cortes.get("clips", [])]
    for i, c in enumerate(doc_cortes.get("clips", []), 1):
        prev = previa_do_corte(previews, ids, i)
        nota = nota_estimada(c)
        if nota is None and c.get("scores"):            # run antiga, sem `estimate --cortes`
            scores = c["scores"]
            nota = round(sum(scores.values()) / len(scores), 1)
        cortes.append({
            "id": c.get("id"), "titulo": c.get("title"), "status": c.get("status"),
            "perfil": c.get("profile"), "duracao": c.get("estimated_final_duration_seconds"),
            "transcricao": c.get("reconstructed_transcript"), "porque": c.get("why_it_can_work"),
            "nota": nota, "nota_do_gate": nota_estimada(c) is not None,
            "abaixo_do_gate": c.get("estimate_below_gate") or [], "falhas": c.get("hard_fails") or [],
            "preview": url_midia(prev) if prev else None,
        })

    verticais = []
    if run:
        for v in sorted(run.glob("output/final-clips/*/*/clip-vertical.mp4")):
            verticais.append({"nome": v.parent.name, "contexto": v.parent.parent.name, "video": url_midia(v)})

    motion = []
    for m in sorted((proj / "motion").glob("*")):
        if not (m / "compose.py").exists():
            continue
        quadros = sorted(list((m / "08_images" / "frames").glob("*.png")) +
                         list((m / "08_images" / "frames").glob("*.jpg")), key=ordem_do_quadro)
        masters = sorted((m / "12_master").glob("*.mp4"))
        motion.append({"nome": m.name, "quadros": [url_midia(q) for q in quadros[:12]],
                       "master": url_midia(masters[-1]) if masters else None})

    entregas = [{"nome": e.stem, "video": url_midia(e), "mb": round(e.stat().st_size / 1e6, 1)}
                for e in sorted((proj / "entregas").glob("*.mp4"))]

    return {**base, "run": run.name if run else None, "momentos": momentos, "cortes": cortes,
            "gate": doc_cortes.get("estimate_gate") or doc_momentos.get("estimate_gate") or 7.5,
            "verticais": verticais, "motion": motion, "entregas": entregas, "escolhas": escolhas}


def nota_estimada(item: dict):
    try:
        return round(float(item["publishability_estimate"]), 1)
    except (KeyError, TypeError, ValueError):
        return None


def previa_do_corte(previews: list[Path], ids: list[str], posicao: int) -> Path | None:
    """O arquivo `<NN>-<clip-id>-<titulo>.mp4` do corte na `posicao` (1, 2, …) de 06-candidates.json.

    Casa pelo id: o NN muda quando 06-candidates.json é refeito com menos cortes, e aí
    apontaria a prévia de outro — inclusive a de uma rodada velha. Só uma prévia sem id
    nenhum no nome (cortada à mão, `<NN>-<slug>.mp4`) casa pela posição.
    """
    def tem(stem: str, clip_id: str) -> bool:
        return bool(clip_id) and re.search(rf"(^|-){re.escape(clip_id)}(-|$)", stem) is not None

    achado = next((p for p in previews if tem(p.stem, ids[posicao - 1])), None)
    if achado:
        return achado
    sem_id = lambda stem: not re.search(r"(^|-)clip-\d+(-|$)", stem) and not any(tem(stem, i) for i in ids)
    return next((p for p in previews if p.stem.startswith(f"{posicao:02d}-") and sem_id(p.stem)), None)


def biblioteca() -> dict:
    linhas = {}
    manifesto = BIBLIOTECA / "MANIFESTO.md"
    if manifesto.exists():
        for l in manifesto.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", l)
            if m:
                linhas[m.group(1)] = {"objeto": m.group(2).strip(), "origem": m.group(3).strip(),
                                      "registro": m.group(4).strip()}
    itens = []
    for p in sorted((BIBLIOTECA / "assets").glob("*.png")):
        itens.append({"arquivo": p.name, "url": url_midia(p), **linhas.get(p.name, {})})
    return {"assets": itens}


_saude_cache: dict = {}


def saude(forcar=False) -> dict:
    if _saude_cache and not forcar:
        return _saude_cache
    try:
        proc = subprocess.run([str(RAIZ / "topclip"), "verificar"], capture_output=True, text=True,
                              timeout=180, cwd=str(RAIZ))
        saida = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
        ok = proc.returncode == 0
    except Exception as e:  # pragma: no cover
        saida, ok = f"nao consegui rodar ./topclip verificar: {e}", False
    itens = []
    for l in saida.splitlines():
        m = re.match(r"\s*\[\s*(ok|FALTA|aviso)\s*\]\s*(.+)", l) or re.match(r"\s*(ok|FALTA|aviso)\s{2,}(.+)", l)
        if m:
            itens.append({"estado": m.group(1).lower(), "texto": m.group(2).strip()})
    _saude_cache.clear()
    _saude_cache.update({"ok": ok, "itens": itens, "saida": saida,
                         "quando": datetime.now().strftime("%H:%M")})
    return _saude_cache


def criar_projeto(nome: str, video: str) -> dict:
    nome = (nome or "").strip()
    video = (video or "").strip().strip("'\"")
    if not nome:
        raise ValueError("Dê um nome para o projeto.")
    s = slug(nome)
    proj = PROJETOS / s
    if proj.exists():
        raise ValueError(f"Já existe um projeto chamado “{s}”.")
    aviso = None
    if video:
        pv = Path(video).expanduser()
        if not pv.exists():
            aviso = "Não achei esse arquivo de vídeo. Confira o caminho — o projeto foi criado mesmo assim."
        video = str(pv)
    for sub in ("runs", "motion", "entregas"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    (proj / "projeto.json").write_text(json.dumps({
        "nome": nome, "video": video, "criado": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    ATV.registrar(proj, "projeto criado no painel — esperando o Claude começar", tipo="projeto")
    return {"slug": s, "aviso": aviso}


def salvar_escolhas(proj: Path, dados: dict) -> dict:
    atual = ler_json(proj / "escolhas.json", {}) or {}
    for chave in ("momentos", "cortes", "motion"):
        if chave in dados and isinstance(dados[chave], list):
            atual[chave] = [str(x) for x in dados[chave]]
    if "observacao" in dados:
        atual["observacao"] = str(dados["observacao"])[:2000]
    atual["atualizado"] = datetime.now().isoformat(timespec="seconds")
    (proj / "escolhas.json").write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    for chave, nomes in (("momentos", ("momento", "momentos")), ("cortes", ("corte", "cortes"))):
        if chave in dados and isinstance(dados[chave], list):
            n = len(dados[chave])
            ATV.registrar(proj, f"você escolheu {n} {nomes[0] if n == 1 else nomes[1]} no painel", tipo="voce")
    return atual


# ------------------------------------------------------------------ atividade
import atividade as ATV  # noqa: E402  — o diário que o lançador e o Claude escrevem

ARTEFATOS = {
    "00-manifest.json": "run criada",
    "01-media.json": "vídeo analisado (duração, imagem e áudio)",
    "02-transcript.json": "transcrição pronta, palavra a palavra",
    "02-digest.md": "resumo da transcrição pronto para o Claude ler",
    "04-context-map.json": "o Claude mapeou os assuntos do vídeo",
    "05-viral-moments.json": "momentos encontrados",
    "06-candidates.json": "cortes montados",
    "07-feed-review.json": "revisão de retenção feita",
    "09-blind-review.json": "revisão cega feita",
    "10-deduplication.json": "cortes repetidos removidos",
    "11-edit-plans.json": "plano de edição do vertical pronto",
    "12-quality-review.json": "controle de qualidade feito",
    "13-final-clips.json": "lista final de clipes fechada",
    "15-run-report.md": "relatório da run pronto",
    "16-output-verification.json": "clipes finais conferidos",
}
JANELA_ATIVO_S = 10 * 60      # notícia do Claude mais nova que isso = ainda trabalhando


def _nascimento(p: Path) -> float:
    st = p.stat()
    return getattr(st, "st_birthtime", st.st_mtime)


def _evento_arquivo(p: Path, msg: str, quando=None) -> dict:
    ts = quando if quando is not None else _nascimento(p)
    return {"ts": ts, "t": datetime.fromtimestamp(ts).isoformat(timespec="seconds"), "tipo": "arquivo", "msg": msg}


def eventos_de_arquivos(proj: Path, run: Path | None) -> list[dict]:
    ev = []
    if run:
        for nome, rotulo in ARTEFATOS.items():
            p = run / nome
            if not p.exists():
                continue
            if nome == "05-viral-moments.json":
                n = len((ler_json(p, {}) or {}).get("moments", []))
                rotulo = f"{n} momento{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}"
            elif nome == "06-candidates.json":
                n = len((ler_json(p, {}) or {}).get("clips", []))
                rotulo = f"{n} corte{'s' if n != 1 else ''} montado{'s' if n != 1 else ''}"
            ev.append(_evento_arquivo(p, rotulo))
        for p in run.glob("preview/*.mp4"):
            ev.append(_evento_arquivo(p, f"prévia pronta: {p.stem}"))
        for p in run.glob("output/final-clips/*/*/clip-vertical.mp4"):
            ev.append(_evento_arquivo(p, f"vertical pronto: {p.parent.name}"))
    for m in (proj / "motion").glob("*"):
        if not (m / "compose.py").exists():
            continue
        quadros = list((m / "08_images" / "frames").glob("*.png")) + list((m / "08_images" / "frames").glob("*.jpg"))
        if quadros:
            ultimo = max(quadros, key=lambda q: q.stat().st_mtime)
            ev.append(_evento_arquivo(ultimo, f"motion {m.name}: {len(quadros)} quadro{'s' if len(quadros) != 1 else ''} composto{'s' if len(quadros) != 1 else ''}",
                                      ultimo.stat().st_mtime))
        for p in (m / "12_master").glob("*.mp4"):
            ev.append(_evento_arquivo(p, f"master com motion pronto: {m.name}"))
    for p in (proj / "entregas").glob("*.mp4"):
        ev.append(_evento_arquivo(p, f"entregue: {p.stem}"))
    return ev


def _pid_vivo(pid) -> bool:
    import os
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def atividade(proj: Path) -> dict:
    diario = ATV.ler(proj)
    abertos: dict[str, dict] = {}
    eventos = []
    for i, e in enumerate(diario):
        try:
            # + i microssegundos: eventos do mesmo segundo mantêm a ordem em que aconteceram
            ts = datetime.fromisoformat(e["t"]).timestamp() + i * 1e-6
        except Exception:
            continue
        e = {**e, "ts": ts}
        if e.get("tipo") == "inicio":
            abertos[e.get("id", "")] = e
        elif e.get("tipo") in ("fim", "erro"):
            abertos.pop(e.get("id", ""), None)
        eventos.append(e)

    rodando = None
    for e in abertos.values():
        if _pid_vivo(e.get("pid")):
            if not rodando or e["ts"] > rodando["ts"]:
                rodando = e
        else:   # começou e o processo sumiu sem anotar o fim: travou ou foi interrompido
            eventos.append({**e, "tipo": "erro", "msg": f"{e['msg']} — interrompido", "ts": e["ts"] + 0.001})

    run = run_mais_recente(proj)
    eventos += eventos_de_arquivos(proj, run)
    eventos.sort(key=lambda e: e["ts"], reverse=True)
    agora = datetime.now().timestamp()
    ultima = eventos[0]["ts"] if eventos else None

    sua_vez = None
    if not rodando:
        esc = ler_json(proj / "escolhas.json", {}) or {}
        mom = run / "05-viral-moments.json" if run else None
        cand = run / "06-candidates.json" if run else None
        if mom and mom.exists() and not esc.get("momentos") and not (cand and cand.exists()):
            sua_vez = {"etapa": "momentos", "msg": "Os momentos estão prontos. Escolha quais viram corte."}
        elif cortes_no_portao(run) and not esc.get("cortes") and not list(run.glob("output/final-clips/*/*/clip-vertical.mp4")):
            sua_vez = {"etapa": "cortes", "msg": "Os cortes estão prontos. Assista e escolha quais viram vertical."}

    reais = [e for e in eventos if e.get("tipo") != "projeto"]
    if rodando:
        estado = "rodando"
    elif eventos and eventos[0].get("tipo") == "voce":
        estado = "avisar_claude"
    elif sua_vez:
        estado = "sua_vez"
    elif not reais:
        estado = "esperando_claude"
    elif ultima and agora - ultima < JANELA_ATIVO_S and eventos[0].get("tipo") in ("info", "inicio"):
        estado = "ativo"
    else:
        estado = "parado"

    return {
        "estado": estado,
        "rodando": {"msg": rodando["msg"], "desde": rodando["t"], "ha_s": int(agora - rodando["ts"])} if rodando else None,
        "sua_vez": sua_vez,
        "ultima_ha_s": int(agora - ultima) if ultima else None,
        "eventos": [{k: e.get(k) for k in ("t", "tipo", "msg")} for e in eventos[:80]],
        "assinatura": _assinatura(proj, run),
    }


def _assinatura(proj: Path, run: Path | None) -> str:
    """Muda quando aparece arquivo novo que mude o que a tela mostra — aí o painel redesenha."""
    partes = [str(p.relative_to(proj)) for p in sorted(proj.glob("runs/*/0[0-9]-*.json"))]
    partes += [str(p.relative_to(proj)) for p in sorted(proj.glob("runs/*/1[0-9]-*.json"))]
    if run:
        partes += [p.name for p in run.glob("preview/*.mp4")] + [p.parent.name for p in run.glob("output/final-clips/*/*/clip-vertical.mp4")]
        # arquivos que são REESCRITOS no lugar: a nota estimada entra depois do momento,
        # o rebuild refaz o corte e a prévia com o mesmo nome
        for p in [run / "05-viral-moments.json", run / "06-candidates.json", *run.glob("preview/*.mp4")]:
            if p.exists():
                partes.append(f"{p.name}@{p.stat().st_mtime_ns}")
    partes += [str(p.relative_to(proj)) for p in proj.glob("motion/*/08_images/frames/*")]
    partes += [str(p.relative_to(proj)) for p in proj.glob("motion/*/12_master/*.mp4")]
    partes += [p.name for p in proj.glob("entregas/*.mp4")]
    import hashlib
    return hashlib.sha1("|".join(sorted(partes)).encode()).hexdigest()[:12]


# ------------------------------------------------------------------ escolher o vídeo
# O navegador não entrega o caminho de um arquivo à página (segurança). Mas o servidor
# roda no computador da pessoa: quem abre o seletor nativo é ele. Nada é copiado nem
# enviado — o painel só fica sabendo ONDE o vídeo está.
_dialogo = threading.Lock()

ESCOLHER_MAC = [
    "activate",
    'set f to choose file with prompt "Escolha o vídeo para o TopClip" '
    'of type {"public.movie", "public.audiovisual-content"}',
    "POSIX path of f",
]


def escolher_video() -> dict:
    if not _dialogo.acquire(blocking=False):
        return {"erro": "Já tem uma janela de escolha aberta — olhe atrás do navegador."}
    try:
        if sys.platform == "darwin":
            cmd = ["osascript"] + [arg for linha in ESCOLHER_MAC for arg in ("-e", linha)]
        else:
            import shutil
            zenity = shutil.which("zenity")
            if not zenity:
                return {"indisponivel": True}
            cmd = [zenity, "--file-selection", "--title=Escolha o vídeo para o TopClip",
                   "--file-filter=Vídeos | *.mp4 *.mov *.m4v *.mkv *.webm *.MP4 *.MOV"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        caminho = proc.stdout.strip()
        if proc.returncode == 0 and caminho:
            return {"caminho": caminho}
        if "-128" in proc.stderr or proc.returncode == 1:
            return {"cancelado": True}
        return {"erro": "Não consegui abrir a janela de escolha. Cole o caminho no campo abaixo."}
    except subprocess.TimeoutExpired:
        return {"cancelado": True}
    finally:
        _dialogo.release()


PASTAS_COMUNS = ["Movies", "Videos", "Downloads", "Desktop", "Documents"]


def _varrer(pastas, nome: str, profundidade=4, orcamento_s=3.0):
    """Procura um arquivo pelo nome nas pastas dadas, sem descer em pastas ocultas."""
    import os
    import time
    fim = time.monotonic() + orcamento_s
    for base in pastas:
        base = Path(base)
        if not base.is_dir():
            continue
        nivel0 = len(base.parts)
        for raiz, dirs, arquivos in os.walk(base):
            if time.monotonic() > fim:
                return
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "Library"
                       and len(Path(raiz, d).parts) - nivel0 <= profundidade]
            if nome in arquivos:
                yield Path(raiz) / nome


def localizar_video(nome: str, tamanho, pastas=None) -> dict:
    """
    O vídeo foi ARRASTADO para a página: o navegador só conta o nome e o tamanho.
    Acha o original no disco por esses dois dados — Spotlight no Mac, varredura das
    pastas de costume no Linux (ou nas `pastas` dadas, nos testes).
    """
    nome = Path(str(nome or "")).name
    if not nome or Path(nome).suffix.lower() not in VIDEO:
        return {"erro": "Isso não parece um arquivo de vídeo (mp4, mov, m4v, mkv ou webm)."}
    try:
        tamanho = int(tamanho)
    except (TypeError, ValueError):
        tamanho = -1

    candidatos: list[Path] = []
    if pastas is None and sys.platform == "darwin":
        try:
            proc = subprocess.run(["mdfind", "-name", nome], capture_output=True, text=True, timeout=10)
            candidatos = [Path(l) for l in proc.stdout.splitlines() if Path(l).name == nome]
        except Exception:
            candidatos = []
    else:
        base = pastas if pastas is not None else [Path.home() / p for p in PASTAS_COMUNS]
        candidatos = list(_varrer(base, nome))

    def mesmo_tamanho(p: Path) -> bool:
        try:
            return tamanho < 0 or p.stat().st_size == tamanho
        except OSError:
            return False

    certos = [p for p in candidatos if mesmo_tamanho(p)]
    if not certos and len(candidatos) == 1:
        certos = candidatos              # sem permissão para medir, mas o nome é único
    if not certos:
        return {"erro": "Não achei esse vídeo sozinho. Use o botão “Escolher vídeo”."}
    try:
        certos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        pass
    return {"caminho": str(certos[0])}


def carregar_demo() -> dict:
    """Copia o projeto de exemplo para projetos/ — para ver o painel antes da 1a run."""
    import shutil
    destino = PROJETOS / "exemplo-podcast"
    if destino.exists():
        return {"slug": destino.name}
    shutil.copytree(DEMO / "exemplo-podcast", destino)
    return {"slug": destino.name}


# ------------------------------------------------------------------ HTTP
class Painel(BaseHTTPRequestHandler):
    server_version = "TopClipPainel/1"

    def log_message(self, fmt, *args):  # silencioso: o terminal e da pessoa
        pass

    # -- respostas
    def _json(self, dados, status=HTTPStatus.OK):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, msg, status=HTTPStatus.BAD_REQUEST):
        self._json({"erro": msg}, status)

    def _arquivo(self, p: Path, cache=False):
        if not p.is_file():
            return self._erro("arquivo não encontrado", HTTPStatus.NOT_FOUND)
        tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        tamanho = p.stat().st_size
        inicio, fim = 0, tamanho - 1
        faixa = self.headers.get("Range")
        parcial = False
        if faixa:
            m = re.match(r"bytes=(\d*)-(\d*)", faixa)
            if m:
                if m.group(1):
                    inicio = int(m.group(1))
                    if m.group(2):
                        fim = min(int(m.group(2)), tamanho - 1)
                elif m.group(2):  # sufixo: ultimos N bytes
                    inicio = max(0, tamanho - int(m.group(2)))
                parcial = True
        if inicio > fim or inicio >= tamanho:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{tamanho}")
            self.end_headers()
            return
        self.send_response(HTTPStatus.PARTIAL_CONTENT if parcial else HTTPStatus.OK)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - inicio + 1))
        if parcial:
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-cache")
        self.end_headers()
        with p.open("rb") as f:
            f.seek(inicio)
            falta = fim - inicio + 1
            while falta > 0:
                bloco = f.read(min(1 << 20, falta))
                if not bloco:
                    break
                try:
                    self.wfile.write(bloco)
                except (BrokenPipeError, ConnectionResetError):
                    return
                falta -= len(bloco)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("pedido grande demais")
        return json.loads(self.rfile.read(n) or b"{}")

    def _projeto(self, s: str) -> Path | None:
        p = PROJETOS / s
        return p if re.fullmatch(r"[a-z0-9-]+", s) and p.is_dir() else None

    def _host_ok(self) -> bool:
        """Só responde a pedidos endereçados ao próprio painel. Um site que tente se
        passar por 127.0.0.1 via DNS (rebinding) chega com outro Host e para aqui."""
        porta = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{porta}", f"localhost:{porta}")

    # -- rotas
    def do_GET(self):
        if not self._host_ok():
            return self._erro("host não permitido", HTTPStatus.FORBIDDEN)
        rota = unquote(urlparse(self.path).path)
        if rota in ("/", "/index.html"):
            return self._arquivo(ESTATICO / "index.html")
        if rota.startswith("/static/"):
            p = ESTATICO / rota[len("/static/"):]
            return self._arquivo(p, cache=False) if dentro(p, ESTATICO) else self._erro("proibido", HTTPStatus.FORBIDDEN)
        if rota.startswith("/fontes/"):
            p = FONTES / rota[len("/fontes/"):]
            if dentro(p, FONTES) and p.suffix == ".ttf":
                return self._arquivo(p, cache=True)
            return self._erro("proibido", HTTPStatus.FORBIDDEN)
        if rota.startswith("/midia/"):
            p = RAIZ / rota[len("/midia/"):]
            if dentro(p, PROJETOS, BIBLIOTECA) and p.suffix.lower() in VIDEO | IMAGEM:
                return self._arquivo(p)
            return self._erro("proibido", HTTPStatus.FORBIDDEN)
        if rota == "/api/projetos":
            PROJETOS.mkdir(exist_ok=True)
            lista = [resumo(p) for p in PROJETOS.iterdir() if p.is_dir() and not p.name.startswith(".")]
            lista.sort(key=lambda r: r.get("criado") or "", reverse=True)
            return self._json({"projetos": lista})
        m = re.fullmatch(r"/api/projetos/([^/]+)/atividade", rota)
        if m:
            p = self._projeto(m.group(1))
            return self._json(atividade(p)) if p else self._erro("projeto não encontrado", HTTPStatus.NOT_FOUND)
        m = re.fullmatch(r"/api/projetos/([^/]+)", rota)
        if m:
            p = self._projeto(m.group(1))
            return self._json(detalhe(p)) if p else self._erro("projeto não encontrado", HTTPStatus.NOT_FOUND)
        if rota == "/api/biblioteca":
            return self._json(biblioteca())
        if rota == "/api/saude":
            return self._json(saude("forcar" in (urlparse(self.path).query or "")))
        return self._erro("rota não encontrada", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        rota = urlparse(self.path).path
        # So aceita pedido vindo do proprio painel: outro site aberto no navegador
        # nao consegue criar projeto nem gravar escolha por aqui.
        origem = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if not self._host_ok() or (origem and urlparse(origem).netloc != host):
            return self._erro("origem não permitida", HTTPStatus.FORBIDDEN)
        try:
            corpo = self._corpo()
            if rota == "/api/projetos":
                return self._json(criar_projeto(corpo.get("nome", ""), corpo.get("video", "")))
            if rota == "/api/escolher-video":
                return self._json(escolher_video())
            if rota == "/api/localizar-video":
                return self._json(localizar_video(corpo.get("nome", ""), corpo.get("tamanho")))
            if rota == "/api/demo":
                return self._json(carregar_demo())
            m = re.fullmatch(r"/api/projetos/([^/]+)/escolhas", rota)
            if m:
                p = self._projeto(m.group(1))
                if not p:
                    return self._erro("projeto não encontrado", HTTPStatus.NOT_FOUND)
                return self._json(salvar_escolhas(p, corpo))
            m = re.fullmatch(r"/api/projetos/([^/]+)/abrir", rota)
            if m:
                p = self._projeto(m.group(1))
                if not p:
                    return self._erro("projeto não encontrado", HTTPStatus.NOT_FOUND)
                abridor = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([abridor, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return self._json({"ok": True})
        except ValueError as e:
            return self._erro(str(e))
        except Exception as e:  # pragma: no cover
            return self._erro(f"erro inesperado: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)
        return self._erro("rota não encontrada", HTTPStatus.NOT_FOUND)


def main() -> int:
    ap = argparse.ArgumentParser(description="Painel local do TopClip")
    ap.add_argument("--porta", type=int, default=7777)
    ap.add_argument("--sem-abrir", action="store_true", help="não abre o navegador")
    a = ap.parse_args()
    PROJETOS.mkdir(exist_ok=True)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.porta), Painel)
    except OSError:
        print(f"A porta {a.porta} está ocupada. Tente: ./topclip painel --porta {a.porta + 1}")
        return 1
    url = f"http://127.0.0.1:{a.porta}"
    print(f"\n  TopClip — painel rodando em {url}\n  Ctrl+C para fechar.\n")
    if not a.sem_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    threading.Thread(target=saude, daemon=True).start()   # aquece o "verificar"
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Painel fechado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
