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
MINHA = RAIZ / "minha-biblioteca"      # a do usuario: assets das runs, estilos, marca
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
    return {k: v["estado"] for k, v in progresso_etapas(proj, run).items()}


# ------------------------------------------------------------------ progresso de cada etapa
# Cada etapa é uma lista de passos: o nome em português, o peso (~ o tempo que costuma
# levar) e o sinal, nos arquivos, de que terminou. O passo cujo comando está rodando
# conta pelo que o comando anunciou — a barra da transcrição, das prévias, do render.
ORDEM = ["momentos", "cortes", "vertical", "motion", "entrega"]
TETO_SEM_TERMINAR = 95      # todos os passos com arquivo, mas a etapa não fechou: rodada nova em curso


def projetos_motion(proj: Path) -> list[Path]:
    return [p for p in sorted((proj / "motion").glob("*")) if (p / "compose.py").exists()]


def master_final(m: Path) -> Path | None:
    """O master de um projeto de motion — nunca o RASCUNHO, que é só para revisão."""
    finais = [p for p in sorted((m / "12_master").glob("*.mp4")) if not p.name.upper().startswith("RASCUNHO")]
    return finais[-1] if finais else None


def _verticais(run: Path | None) -> list[Path]:
    return sorted(run.glob("output/final-clips/*/*/clip-vertical.mp4")) if run else []


def progresso_etapas(proj: Path, run: Path | None, rodando=()) -> dict:
    """Quanto de cada etapa já foi (0 a 100), o estado e os passos — deduzido dos arquivos.

    `rodando`: os comandos abertos agora, cada um com `sub`, `clipe` e o `pct` que anunciou.
    Uma etapa só chega a 100 quando fecha de verdade (o mesmo "feito" de sempre: momentos
    no 05, cortes no portão, …); até lá para em 95, por mais que os arquivos digam que sim.
    """
    tem = lambda *ns: bool(run) and any((run / n).exists() for n in ns)
    doc = lambda n: (ler_json(run / n, {}) or {}) if tem(n) else {}
    escolhas = ler_json(proj / "escolhas.json", {}) or {}
    em_curso = {(r.get("sub"), r.get("clipe")): (r.get("pct") or 0) / 100 for r in rodando if r.get("sub")}

    def passo(nome, peso, feito, cmd=None, fracao=None, clipe=None, detalhe=None):
        if not feito and cmd and (cmd, clipe) in em_curso:
            fracao = max(fracao or 0, em_curso[(cmd, clipe)])
        return {"nome": nome, "peso": peso, "feito": bool(feito), "fracao": fracao, "detalhe": detalhe}

    # Momentos: a transcrição e os dois subagentes que leem o vídeo inteiro
    mom = doc("05-viral-moments.json")
    momentos = [
        passo("run criada", 2, tem("00-manifest.json"), "init"),
        passo("vídeo analisado", 3, tem("01-media.json")),
        passo("transcrição palavra a palavra", 33, tem("02-transcript.json"), "prepare"),
        passo("resumo para o Claude ler", 2, tem("02-digest.md"), "digest"),
        passo("mapa dos assuntos (Context Mapper)", 25, tem("04-context-map.json")),
        passo("momentos encontrados (Clip Hunter)", 30, tem("05-viral-moments.json")),
        passo("nota estimada de cada momento", 5, "estimate_gate" in mom, "estimate"),
    ]

    # Cortes: Clip Builder, prévias, as revisões em paralelo e a nota de cada corte
    cand = doc("06-candidates.json")
    clips = cand.get("clips") or []
    ids = [str(c.get("id", "")) for c in clips]
    previews = sorted(run.glob("preview/*.mp4")) if run else []
    n_prev = sum(1 for i in range(1, len(clips) + 1) if previa_do_corte(previews, ids, i))
    cortes = [
        passo("cortes montados (Clip Builder)", 30, tem("06-candidates.json")),
        passo("bordas e auditoria técnica", 5, tem("08-technical-audit.json"), "audit"),
        passo("prévias para você assistir", 10, clips and n_prev >= len(clips), "previews",
              n_prev / len(clips) if clips else None, detalhe=f"{n_prev} de {len(clips)}" if clips else None),
        passo("revisão de retenção (feed)", 20, tem("07-feed-review.json")),
        passo("revisão cega", 20, tem("09-blind-review.json")),
        passo("repetidos removidos", 5, tem("10-temporal-deduplication.json", "10-deduplication.json"), "dedupe"),
        passo("nota de cada corte", 10, clips and all(nota_estimada(c) is not None for c in clips), "estimate"),
    ]

    # Vertical: plano, enquadramento, revisão final e o render de cada aprovado
    verticais = _verticais(run)
    final = doc("13-final-clips.json")
    if final:
        esperados = sum(1 for c in final.get("clips", [])
                        if c.get("status") in ("APPROVED", "LONG_CLIP") or c.get("user_override"))
    else:
        esperados = len(escolhas.get("cortes") or [])
    sabido = bool(esperados)                       # sem 13 nem escolha, o total é chute: não mostra
    esperados = max(1, esperados or len(verticais))
    n_vert = min(len(verticais), esperados)
    estagios = doc("00-manifest.json").get("stages") or {}
    concluido = lambda nome: (estagios.get(nome) or {}).get("status") == "complete"
    vertical = [
        passo("plano de edição (Edit Director)", 20, tem("11-edit-plans.json")),
        passo("enquadramento seguindo quem fala", 15, concluido("autoframe"), "autoframe"),
        passo("controle de qualidade", 15, tem("12-quality-review.json")),
        passo("lista final fechada", 5, tem("13-final-clips.json"), "finalize"),
        passo("legenda palavra a palavra", 5, concluido("subtitles"), "subtitles"),
        passo("clipes renderizados", 40, n_vert >= esperados, "render", n_vert / esperados,
              detalhe=f"{n_vert} de {esperados}" if sabido else None),
    ]

    # Motion: um projeto por clipe aprovado, cada um com os seus passos
    clipes = []
    for m in projetos_motion(proj):
        b, master = m / "00_brief", master_final(m)
        quadros = any((m / "08_images" / "frames").glob("*.png")) or any((m / "08_images" / "frames").glob("*.jpg"))
        rascunho = any((m / "12_master").glob("RASCUNHO*.mp4"))
        ps = [
            passo("projeto de motion criado", 3, True),
            passo("clipe vertical copiado", 2, (b / "fonte.mp4").exists()),
            passo("transcrição do clipe", 10, (b / "transcript_palavras.json").exists(), "transcrever", clipe=m.name),
            passo("plano de motion (frases escolhidas)", 15, (b / "PLANO_MOTION.md").exists()),
            passo("cenas compostas", 30, quadros, "compose.py", clipe=m.name),
            passo("rascunho para revisão", 15, rascunho or master, "render.py:rascunho", clipe=m.name),
            passo("master final", 25, master, "render.py", clipe=m.name),
        ]
        clipes.append({"nome": m.name, "feito": bool(master), "passos": ps})

    # Entrega: um master conferido em entregas/ por projeto de motion
    n_ent = len(list((proj / "entregas").glob("*.mp4")))
    alvo = len(clipes) or n_ent or 1
    entrega = [passo("clipes entregues", 1, n_ent >= alvo, fracao=n_ent / alvo,
                     detalhe=f"{min(n_ent, alvo)} de {alvo}" if clipes else None)]

    feito = {
        "momentos": tem("05-viral-moments.json"),
        "cortes": bool(verticais) or cortes_no_portao(run),
        "vertical": bool(verticais) and len(verticais) >= esperados,
        "motion": bool(clipes) and all(c["feito"] for c in clipes),
        "entrega": n_ent > 0 and n_ent >= len(clipes),
    }
    # a vez do Claude depois de uma escolha sua: a etapa seguinte já começou, mesmo sem arquivo
    andando = {
        "momentos": bool(run),
        "cortes": feito["momentos"] and bool(escolhas.get("momentos")),
        "vertical": feito["cortes"] and bool(escolhas.get("cortes")),
        "motion": bool(clipes),
        "entrega": False,
    }

    def etapa(nome, passos, itens=None):
        if feito[nome]:
            pct = 100
        elif itens:
            pct = min(TETO_SEM_TERMINAR, round(sum(_somar(i["passos"]) if not i["feito"] else 100
                                                  for i in itens) / len(itens)))
        else:
            pct = min(TETO_SEM_TERMINAR, round(_somar(passos)))
        estado = "feito" if feito[nome] else ("andamento" if pct > 0 or andando[nome] else "pendente")
        saida = {"pct": pct, "estado": estado, "passos": _para_tela(passos, feito[nome])}
        if itens is not None:
            saida["itens"] = [{"nome": i["nome"], "pct": 100 if i["feito"] or feito[nome] else round(_somar(i["passos"])),
                               "passos": _para_tela(i["passos"], i["feito"] or feito[nome])} for i in itens]
        return saida

    return {
        "momentos": etapa("momentos", momentos),
        "cortes": etapa("cortes", cortes),
        "vertical": etapa("vertical", vertical),
        "motion": etapa("motion", [], clipes),
        "entrega": etapa("entrega", entrega),
    }


def _somar(passos: list[dict]) -> float:
    total = sum(p["peso"] for p in passos) or 1
    return 100 * sum(p["peso"] * (1 if p["feito"] else (p["fracao"] or 0)) for p in passos) / total


def _para_tela(passos: list[dict], tudo_feito: bool) -> list[dict]:
    """Etapa fechada: todo passo conta como feito (run antiga sem algum arquivo novo)."""
    saida = []
    for p in passos:
        feito = tudo_feito or p["feito"]
        item = {"nome": p["nome"], "feito": feito}
        if not feito and p["fracao"]:
            item["pct"] = round(100 * p["fracao"])
        if not feito and p["detalhe"]:
            item["detalhe"] = p["detalhe"]
        saida.append(item)
    return saida


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


def tem_id(nome: str, clip_id: str) -> bool:
    """`clip-010` aparece como palavra inteira no nome? (`clip-0101` não conta)"""
    return bool(clip_id) and re.search(rf"(^|-){re.escape(clip_id)}(-|$)", nome) is not None


def andamento_dos_cortes(proj: Path, run: Path | None) -> dict:
    """Até onde cada corte já foi: "pronto" (tem entrega) ou "andamento" (vertical ou motion começados).

    A pessoa escolhe 2 de 14, posta, e volta depois para fazer o resto: o painel precisa
    saber quais já saíram. O que liga um corte ao que saiu dele é o id no nome —
    `entregas/clip-010-….mp4`, `motion/clip-010`, `final-clips/<contexto>/clip-010-…`.
    Entram também os entregues que não estão mais no 06 (refeito só com os novos).
    """
    entregas = [p.stem for p in (proj / "entregas").glob("*.mp4")]
    producao = [p.name for p in (proj / "motion").glob("*") if p.is_dir()]
    if run:
        producao += [p.parent.name for p in run.glob("output/final-clips/*/*/clip-vertical.mp4")]
    ids = [str(c.get("id", "")) for c in ((ler_json(run / "06-candidates.json", {}) or {}).get("clips", []) if run else [])]
    ids += [m.group(1) for n in entregas for m in [re.match(r"(clip-\d+)(-|$)", n)] if m and m.group(1) not in ids]
    estado = {}
    for i in ids:
        if any(tem_id(n, i) for n in entregas):
            estado[i] = "pronto"
        elif any(tem_id(n, i) for n in producao):
            estado[i] = "andamento"
        else:
            estado[i] = None
    return estado


def resumo(proj: Path) -> dict:
    info = ler_json(proj / "projeto.json", {}) or {}
    run = run_mais_recente(proj)
    feitos = andamento_dos_cortes(proj, run)
    ativ = atividade(proj)          # já traz o estado e o % de cada etapa, com o que está rodando
    et = {k: v["estado"] for k, v in ativ["etapas"].items()}
    # quando é a vez da pessoa escolher, a etapa da escolha é a atual — não a seguinte
    atual = ativ["sua_vez"]["etapa"] if ativ["sua_vez"] else next((k for k in ORDEM if et[k] != "feito"), "entrega")
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
        "link": info.get("link", ""),
        "criado": info.get("criado", ""),
        "etapas": et,
        "progresso": {k: v["pct"] for k, v in ativ["etapas"].items()},
        "etapa_atual": atual,
        "n_momentos": len((momentos or {}).get("moments", [])),
        "n_cortes": len(feitos),
        "n_prontos": sum(1 for e in feitos.values() if e == "pronto"),
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
    doc_cortes = (ler_json(run / "06-candidates.json", {}) or {}) if run else {}
    feitos = andamento_dos_cortes(proj, run)
    # momento -> até onde o corte dele foi; o 13 guarda o momento dos clipes que já saíram
    do_momento: dict[str, str] = {}
    for doc in (doc_cortes, (ler_json(run / "13-final-clips.json", {}) or {}) if run else {}):
        for c in doc.get("clips", []):
            e, mid = feitos.get(str(c.get("id", ""))), c.get("moment_id")
            if e and mid and do_momento.get(mid) != "pronto":
                do_momento[mid] = e
    momentos = []
    for m in doc_momentos.get("moments", []):
        momentos.append({**m, "inicio": mmss(m.get("start")), "fim": mmss(m.get("end")),
                         "nota": nota_estimada(m), "abaixo_do_gate": m.get("estimate_below_gate") or [],
                         "feito": do_momento.get(m.get("id"))})
    # a pergunta da pessoa é "quais prestam": melhor nota primeiro; sem nota, na ordem do Clip Hunter
    momentos.sort(key=lambda m: -m["nota"] if m["nota"] is not None else float("inf"))

    cortes = []
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
            "preview": url_midia(prev) if prev else None, "feito": feitos.get(str(c.get("id", ""))),
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
        master = master_final(m)
        rascunhos = sorted((m / "12_master").glob("RASCUNHO*.mp4"))
        motion.append({"nome": m.name, "quadros": [url_midia(q) for q in quadros[:12]],
                       "master": url_midia(master) if master else None,
                       "rascunho": url_midia(rascunhos[-1]) if rascunhos and not master else None,
                       "estilo": estilo_do_motion(m)})

    entregas = [{"nome": e.stem, "video": url_midia(e), "mb": round(e.stat().st_size / 1e6, 1)}
                for e in sorted((proj / "entregas").glob("*.mp4"))]

    return {**base, "run": run.name if run else None, "momentos": momentos, "cortes": cortes,
            "gate": doc_cortes.get("estimate_gate") or doc_momentos.get("estimate_gate") or 7.5,
            "verticais": verticais, "motion": motion, "entregas": entregas, "escolhas": escolhas,
            "estilo": estilo_do_projeto(proj, escolhas),
            # baixado pelo link, o vídeo mora na pasta do projeto: apagar leva ele junto
            "video_no_projeto": bool(base["video"]) and dentro(Path(base["video"]).expanduser(), proj)}


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
    tem = tem_id
    achado = next((p for p in previews if tem(p.stem, ids[posicao - 1])), None)
    if achado:
        return achado
    sem_id = lambda stem: not re.search(r"(^|-)clip-\d+(-|$)", stem) and not any(tem(stem, i) for i in ids)
    return next((p for p in previews if p.stem.startswith(f"{posicao:02d}-") and sem_id(p.stem)), None)


def biblioteca() -> dict:
    """Os assets oficiais e os que o usuario desenhou nas runs (minha-biblioteca/), cada
    um com a linha do MANIFESTO da sua pasta."""
    itens = []
    for base, dono in ((BIBLIOTECA, "oficial"), (MINHA, "seu")):
        linhas = {}
        manifesto = base / "MANIFESTO.md"
        if manifesto.exists():
            for l in manifesto.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", l)
                if m:
                    linhas[m.group(1)] = {"objeto": m.group(2).strip(), "origem": m.group(3).strip(),
                                          "registro": m.group(4).strip()}
        for p in sorted((base / "assets").glob("*.png")):
            itens.append({"arquivo": p.name, "url": url_midia(p), "dono": dono,
                          **linhas.get(p.name, {})})
    return {"assets": itens, "objetos": objetos_dos_estilos()}


def objetos_dos_estilos() -> dict:
    """Os objetos dos estilos com lápis (Limpo, Impacto, Luxo): os oficiais e os do usuário,
    lidos do código sem executar (lib/meus_objetos.py), e a folha dos seus, que o
    `./topclip objetos` grava."""
    mod = modulo_meus_objetos()
    try:
        seus, erro = mod.lista(MINHA / "objetos.py"), None
    except ValueError as e:
        seus, erro = [], str(e)
    return {"oficiais": mod.lista(BIBLIOTECA / "pecas" / "objetos.py"), "seus": seus, "erro": erro,
            "folha": _url_se_existe(MINHA / "objetos.png") if seus else None}


# ------------------------------------------------------------------ estilos, marca e preferências
# Os pacotes de estilo (docs/proposta-estilos.md): os oficiais em biblioteca/estilos/, os do
# usuário em minha-biblioteca/estilos/. Quem confere o pacote e mede o contraste é o
# lib/estilo.py da skill de motion — o painel só lê. O visual de cada estilo aparece só
# nas prévias (preview/*.png, de `./topclip estilo previa`): nada é desenhado aqui.
ESTILO_PY = RAIZ / ".claude" / "skills" / "topclip-motion" / "lib" / "estilo.py"
RE_ESTILO = re.compile(r"[a-z0-9][a-z0-9-]{1,30}")
CONTRASTE_MIN = 4.5                 # o mesmo mínimo do resolver para a cor de texto da marca
LOGO_MAX = 5_000_000                # bytes do PNG; em base64 o pedido chega ~1/3 maior
MARCA_CORES = {"primaria": "primária", "secundaria": "secundária", "texto": "do texto"}
MARCA_FONTES = {"titulo": "do título", "texto": "do texto"}
_estilo_mod = None


def modulo_estilo():
    """O lib/estilo.py da skill, carregado pelo caminho: não mora num pacote do painel."""
    global _estilo_mod
    if _estilo_mod is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("topclip_estilo", ESTILO_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _estilo_mod = mod
    return _estilo_mod


def pastas_de_estilos() -> list[tuple[Path, str]]:
    return [(BIBLIOTECA / "estilos", "oficial"), (MINHA / "estilos", "seu")]


def achar_estilo(eid) -> Path | None:
    """Oficial primeiro, como o `estilo.achar`: um estilo seu com o mesmo id não o esconde."""
    if not isinstance(eid, str) or not RE_ESTILO.fullmatch(eid):
        return None
    for base, _ in pastas_de_estilos():
        if (base / eid / "estilo.json").is_file():
            return base / eid
    return None


def _url_se_existe(p: Path):
    # ?v=: a prévia regerada no mesmo nome não fica presa no cache do navegador
    return f"{url_midia(p)}?v={p.stat().st_mtime_ns}" if p.is_file() else None


def _ler_dict(p: Path) -> dict:
    """JSON de um pacote que pode ter sido escrito à mão: o que não for objeto vira {}."""
    d = ler_json(p, {})
    return d if isinstance(d, dict) else {}


def _lista(v) -> list:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _variacoes(est: dict) -> dict:
    v = est.get("variacoes")
    return {k: x for k, x in v.items() if isinstance(x, dict)} if isinstance(v, dict) else {}


def resumo_estilo(pasta: Path, dono: str) -> dict:
    mod = modulo_estilo()
    est = _ler_dict(pasta / "estilo.json")
    tok = _ler_dict(pasta / "tokens.json")
    try:
        erros, avisos = mod.validar(pasta)
    except Exception as e:              # pacote quebrado não derruba a aba
        erros, avisos = [f"não consegui conferir o pacote: {e}"], []
    variacoes = []
    for i, (vid, v) in enumerate(_variacoes(est).items()):
        troca = v.get("tokens") if isinstance(v.get("tokens"), dict) else {}
        cor = lambda c: troca.get(f"cor.{c}") or mod.token(tok, f"cor.{c}")
        # a capa da 1a variação é a capa.png; as outras, capa-<variação>.png (`estilo previa`)
        capa = pasta / "preview" / ("capa.png" if i == 0 else f"capa-{vid}.png")
        variacoes.append({"id": vid, "nome": v.get("nome") or vid, "capa": _url_se_existe(capa),
                          "fundo": cor("fundo"), "acento": cor("acento"), "texto": cor("texto")})
    pecas = [{"id": x, "imagem": _url_se_existe(pasta / "preview" / "pecas" / f"{x}.png")}
             for x in _lista(est.get("pecas")) if RE_ESTILO.fullmatch(x.replace("_", "-"))]
    return {
        "id": pasta.name, "nome": str(est.get("nome") or pasta.name), "descricao": str(est.get("descricao") or ""),
        "energia": est.get("energia"), "bom_para": _lista(est.get("bom_para")), "versao": est.get("versao"),
        "origem": est.get("origem"), "dono": dono, "variacoes": variacoes,
        "capa": variacoes[0]["capa"] if variacoes else None, "pecas": pecas,
        "slots_da_marca": _lista(est.get("slots_da_marca")),
        "demo": _url_se_existe(pasta / "preview" / "demo.mp4"),
        # o desenho do estilo: os objetos no lapis dele (`estilo previa`); o Papel nao tem
        "objetos": _url_se_existe(pasta / "preview" / "objetos.png"),
        "valido": not erros, "erros": erros, "avisos": avisos,
    }


def estilos() -> dict:
    """Oficiais e os seus, o padrão (o Papel) na frente; um id repetido vale o oficial."""
    padrao = getattr(modulo_estilo(), "PADRAO", "papel")
    vistos, lista = set(), []
    for base, dono in pastas_de_estilos():
        for p in sorted(base.glob("*/estilo.json")) if base.is_dir() else []:
            if p.parent.name not in vistos:
                vistos.add(p.parent.name)
                lista.append(resumo_estilo(p.parent, dono))
    lista.sort(key=lambda e: (e["dono"] != "oficial", e["id"] != padrao))
    return {"estilos": lista, "padrao": preferencias()}


def estilo_detalhe(eid: str) -> dict | None:
    pasta = achar_estilo(eid)
    if not pasta:
        return None
    dono = "oficial" if pasta.parent == BIBLIOTECA / "estilos" else "seu"
    return {**resumo_estilo(pasta, dono), "padrao": preferencias()}


def conferir_escolha(eid, variacao=None) -> dict:
    """{"id", "variacao"} de um estilo que existe e passa no validador. Sem variação, a primeira."""
    pasta = achar_estilo(eid)
    if not pasta:
        raise ValueError("Esse estilo não está na biblioteca.")
    erros, _ = modulo_estilo().validar(pasta)
    if erros:
        raise ValueError(f"O estilo {pasta.name} tem um problema e não pode ser usado: {erros[0]}")
    existem = list(_variacoes(_ler_dict(pasta / "estilo.json")))
    variacao = variacao or (existem[0] if existem else None)
    if variacao not in existem:
        raise ValueError(f"O estilo {pasta.name} não tem a variação “{variacao}”.")
    return {"id": pasta.name, "variacao": variacao}


def nome_do_estilo(eid, variacao=None, pasta: Path | None = None) -> str:
    """'Limpo · Escuro' — o nome que a pessoa vê, não o id."""
    est = _ler_dict((pasta or achar_estilo(eid) or Path("-")) / "estilo.json")
    var = _variacoes(est).get(variacao) or {}
    return " · ".join(x for x in (est.get("nome") or eid, var.get("nome")) if x)


def preferencias() -> dict:
    """O estilo padrão da pessoa (minha-biblioteca/preferencias.json); sem ele, o Papel."""
    salvo = ler_json(MINHA / "preferencias.json", {})
    salvo = salvo if isinstance(salvo, dict) else {}
    eid, pasta = salvo.get("estilo"), achar_estilo(salvo.get("estilo"))
    if not pasta:
        eid = getattr(modulo_estilo(), "PADRAO", "papel")
        pasta = achar_estilo(eid)
    existem = list(_variacoes(_ler_dict(pasta / "estilo.json"))) if pasta else []
    variacao = salvo.get("variacao") if salvo.get("estilo") == eid and salvo.get("variacao") in existem \
        else (existem[0] if existem else None)
    return {"estilo": eid, "variacao": variacao, "salvo": salvo.get("estilo") == eid}


def salvar_preferencias(dados: dict) -> dict:
    escolha = conferir_escolha(dados.get("estilo"), dados.get("variacao"))
    atual = ler_json(MINHA / "preferencias.json", {})
    atual = atual if isinstance(atual, dict) else {}      # outras preferências futuras ficam
    atual.update(estilo=escolha["id"], variacao=escolha["variacao"])
    MINHA.mkdir(parents=True, exist_ok=True)
    (MINHA / "preferencias.json").write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    return preferencias()


def estilo_do_projeto(proj: Path, escolhas: dict) -> dict:
    """O que a etapa de motion vai usar: a escolha do projeto, senão o padrão da pessoa.
    `estilo_recomendado` no projeto.json é o que o Claude sugeriu pelo transcript."""
    rec = (ler_json(proj / "projeto.json", {}) or {}).get("estilo_recomendado")
    rec = {"id": rec} if isinstance(rec, str) else rec
    rec = ({k: str(rec[k]) for k in ("id", "variacao", "porque") if rec.get(k)}
           if isinstance(rec, dict) and achar_estilo(rec.get("id")) else None)
    esc = escolhas.get("estilo")
    esc = {"id": esc["id"], "variacao": esc.get("variacao")} if isinstance(esc, dict) and achar_estilo(esc.get("id")) else None
    padrao = preferencias()
    vale = esc or {"id": padrao["estilo"], "variacao": padrao["variacao"]}
    return {"escolhido": esc, "recomendado": rec, "padrao": padrao, "vale": vale,
            "nome": nome_do_estilo(vale["id"], vale["variacao"])}


def estilo_do_motion(m: Path) -> str | None:
    """O estilo que um projeto de motion congelou (estilo/resolvido.json), para a etiqueta."""
    r = ler_json(m / "estilo" / "resolvido.json", None)
    if not isinstance(r, dict) or not r.get("id"):
        return None
    return nome_do_estilo(r["id"], r.get("variacao"), m / "estilo")


def _png(dados: bytes) -> dict | None:
    """Largura, altura e transparência de um PNG, lendo só o cabeçalho (sem PIL no painel)."""
    if len(dados) < 33 or dados[:8] != b"\x89PNG\r\n\x1a\n" or dados[12:16] != b"IHDR":
        return None
    tipo = dados[25]                     # 4 e 6: cinza e cor com alfa; nos outros, o bloco tRNS
    return {"largura": int.from_bytes(dados[16:20], "big"), "altura": int.from_bytes(dados[20:24], "big"),
            "transparente": tipo in (4, 6) or b"tRNS" in dados[:dados.find(b"IDAT")]}


def _contraste_txt(r: float) -> str:
    return f"{r:.1f}".replace(".", ",")


def avisos_da_marca(m: dict) -> list[str]:
    """A cor de texto precisa de 4,5:1 (a conta é o `estilo.contraste`): sobre a cor primária,
    e sobre o fundo de cada estilo que deixa a marca trocar a cor do texto — ali, abaixo do
    mínimo, o resolver fica com a cor do estilo."""
    mod = modulo_estilo()
    cores = m.get("cores") if isinstance(m.get("cores"), dict) else {}
    hexa = lambda c: isinstance(c, str) and bool(mod.RE_HEX.match(c))
    texto, avisos = cores.get("texto"), []
    if not hexa(texto):
        return avisos
    if hexa(cores.get("primaria")):
        r = mod.contraste(texto, cores["primaria"])
        if r < CONTRASTE_MIN:
            avisos.append(f"O texto sobre a cor primária fica com contraste {_contraste_txt(r)}:1. "
                          f"Para ler bem no celular, o mínimo é 4,5:1.")
    for base, _ in pastas_de_estilos():
        for p in sorted(base.glob("*/estilo.json")) if base.is_dir() else []:
            est = _ler_dict(p)
            if "cor.texto" not in _lista(est.get("slots_da_marca")):
                continue
            tok = _ler_dict(p.parent / "tokens.json")
            ruins = []
            for vid, v in _variacoes(est).items():
                troca = v.get("tokens") if isinstance(v.get("tokens"), dict) else {}
                fundo = troca.get("cor.fundo") or mod.token(tok, "cor.fundo")
                if hexa(fundo) and mod.contraste(texto, fundo) < CONTRASTE_MIN:
                    ruins.append(v.get("nome") or vid)
            if ruins:
                avisos.append(f"No {est.get('nome') or p.parent.name} ({', '.join(ruins)}), o texto ficaria "
                              f"difícil de ler sobre o fundo: ali o vídeo usa a cor de texto do estilo.")
    return avisos


def marca() -> dict:
    pasta = MINHA / "marca"
    m = ler_json(pasta / "marca.json", None)
    existe = isinstance(m, dict)
    m = m if existe else {}
    cores = m.get("cores") if isinstance(m.get("cores"), dict) else {}
    fontes = m.get("fontes") if isinstance(m.get("fontes"), dict) else {}
    logo = pasta / m["logo"] if isinstance(m.get("logo"), str) and m["logo"] else None
    logo = logo if logo and dentro(logo, pasta) and logo.is_file() else None
    info = _png(logo.read_bytes()) if logo else None
    return {
        "existe": existe,
        "marca": {"nome": m.get("nome") or "", "arroba": m.get("arroba") or "",
                  "cores": {c: cores.get(c) for c in MARCA_CORES},
                  "fontes": {f: fontes.get(f) for f in MARCA_FONTES}},
        "logo": _url_se_existe(logo) if logo else None, "logo_info": info,
        "fontes_do_kit": [{"nome": n, "url": "/fontes/" + quote(a)}
                          for n, a in modulo_estilo().FONTES_DO_KIT.items()],
        "avisos": avisos_da_marca(m),
        "aviso_logo": "O logo não tem fundo transparente: no vídeo ele aparece dentro de um retângulo."
                      if info and not info["transparente"] else None,
    }


def salvar_marca(dados: dict) -> dict:
    """Grava minha-biblioteca/marca/marca.json (formato da seção 9) e o logo.png. Confere
    tudo antes de gravar qualquer coisa; campos que o formulário não mandou ficam como estão."""
    import base64
    mod = modulo_estilo()
    pasta = MINHA / "marca"
    atual = ler_json(pasta / "marca.json", {})
    atual = atual if isinstance(atual, dict) else {}
    for campo in ("nome", "arroba"):
        if campo in dados:
            atual[campo] = str(dados[campo] or "").strip()[:80]
    cores = dict(atual.get("cores") if isinstance(atual.get("cores"), dict) else {})
    for c, nome in MARCA_CORES.items():
        v = str((dados.get("cores") or {}).get(c) or "").strip()
        if not v:
            continue
        if not mod.RE_HEX.match(v):
            raise ValueError(f"A cor {nome} precisa estar no formato #RRGGBB (por exemplo, #2E82F7).")
        cores[c] = v.upper()
    fontes = dict(atual.get("fontes") if isinstance(atual.get("fontes"), dict) else {})
    for f, nome in MARCA_FONTES.items():
        v = str((dados.get("fontes") or {}).get(f) or "").strip()
        if not v:
            continue
        # do kit, ou a fonte própria que já estava no marca.json (arquivo em marca/)
        if v not in mod.FONTES_DO_KIT and not (v == fontes.get(f) and dentro(pasta / v, pasta)
                                               and (pasta / v).is_file()):
            raise ValueError(f"A fonte {nome} precisa ser uma das fontes do TopClip.")
        fontes[f] = v
    png = None
    if dados.get("logo"):
        try:
            png = base64.b64decode(str(dados["logo"]).split(",", 1)[-1], validate=True)
        except ValueError:
            raise ValueError("Não consegui ler o logo. Envie um arquivo PNG.")
        if len(png) > LOGO_MAX:
            raise ValueError("O logo passou de 5 MB. Use um PNG menor.")
        if not _png(png):
            raise ValueError("O logo precisa ser um arquivo PNG.")
    atual["cores"], atual["fontes"] = cores, fontes
    if png:
        atual["logo"] = "logo.png"
    elif dados.get("remover_logo"):
        atual.pop("logo", None)          # tira do marca.json; o arquivo fica onde está
    pasta.mkdir(parents=True, exist_ok=True)
    if png:
        (pasta / "logo.png").write_bytes(png)
    (pasta / "marca.json").write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    return marca()


# ------------------------------------------------------------------ o estilo da pessoa
# Remixar, importar, exportar e apagar (fase 5). Quem faz é o lib/meu_estilo.py da skill;
# o painel só chama, apontando para a minha-biblioteca dele (que os testes trocam).
# Criar e ajustar um estilo é conversa com o Claude (skill topclip-estilo), não formulário.
IMPORTAR_MAX = 25 * 1024 * 1024     # o mesmo teto do pacote; em base64 o pedido chega ~1/3 maior


def modulo_meus_objetos():
    lib = str(ESTILO_PY.parent)
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import meus_objetos
    return meus_objetos


def modulo_meu_estilo():
    lib = str(ESTILO_PY.parent)
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import meu_estilo
    meu_estilo.MINHA = MINHA
    return meu_estilo


def _chama(fn, *args, **kw):
    """Erro de uso do meu_estilo vira a mensagem que a tela mostra."""
    mod = modulo_meu_estilo()
    try:
        return fn(mod)(*args, **kw)
    except mod.ErroEstilo as e:
        raise ValueError(str(e).replace("\n  ", " · ")) from None


def remixar_estilo(dados: dict) -> dict:
    nome = str(dados.get("nome") or "").strip()[:60]
    novo = str(dados.get("id") or "").strip() or slug(nome)[:31]
    if not nome:
        raise ValueError("Dê um nome para o seu estilo.")
    p = _chama(lambda m: m.remixar, RAIZ, str(dados.get("base") or ""), novo, nome)
    return estilo_detalhe(p.name)


def importar_estilo(dados: dict) -> dict:
    import base64
    import tempfile
    try:
        bruto = base64.b64decode(str(dados.get("conteudo") or "").split(",", 1)[-1], validate=True)
    except ValueError:
        raise ValueError("Não consegui ler o arquivo. Envie um .topclip-estilo.") from None
    if not bruto:
        raise ValueError("O arquivo veio vazio.")
    if len(bruto) > IMPORTAR_MAX:
        raise ValueError("O arquivo passou de 25 MB.")
    with tempfile.TemporaryDirectory(prefix="topclip-importar-") as d:
        arq = Path(d) / "estilo.topclip-estilo"
        arq.write_bytes(bruto)
        p = _chama(lambda m: m.importar, RAIZ, arq, bool(dados.get("substituir")))
    return estilo_detalhe(p.name)


def apagar_estilo(eid: str) -> dict:
    nome = _chama(lambda m: m.apagar, RAIZ, eid)
    return {"ok": True, "apagado": nome, "padrao": preferencias()}


def exportar_estilo(eid: str) -> Path:
    """O .topclip-estilo numa pasta temporária: quem serve apaga a pasta depois."""
    import tempfile
    pasta = Path(tempfile.mkdtemp(prefix="topclip-exportar-"))
    try:
        return _chama(lambda m: m.exportar, RAIZ, eid, pasta)
    except ValueError:
        import shutil
        shutil.rmtree(pasta, ignore_errors=True)
        raise


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


def criar_projeto(nome: str, video: str, link: str = "", pasta: str | None = None) -> dict:
    """Com `link` (YouTube, Instagram) o vídeo ainda não existe: `iniciar_download` o baixa.
    `pasta` é o nome já decidido por quem chama (`./topclip baixar <link> projetos/<nome>`)."""
    import baixar   # aqui e não no topo: baixar importa este módulo
    nome = (nome or "").strip()
    video = (video or "").strip().strip("'\"")
    link = (link or "").strip()
    if not nome:
        raise ValueError("Dê um nome para o projeto.")
    if link and not baixar.eh_link(link):
        raise ValueError("Isso não parece um link. Cole o endereço completo, começando com https://")
    s = pasta or slug(nome)
    proj = PROJETOS / s
    if (proj / "projeto.json").exists() or (proj.exists() and not pasta):
        raise ValueError(f"Já existe um projeto chamado “{s}”.")
    aviso = None
    if video and not link:
        pv = Path(video).expanduser()
        if not pv.exists():
            aviso = "Não achei esse arquivo de vídeo. Confira o caminho — o projeto foi criado mesmo assim."
        video = str(pv)
    for sub in ("runs", "motion", "entregas"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    dados = {"nome": nome, "video": "" if link else video, "criado": datetime.now().isoformat(timespec="seconds")}
    if link:
        dados["link"] = link
    (proj / "projeto.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    ATV.registrar(proj, f"projeto criado a partir de um link do {baixar.site(link)}" if link
                  else "projeto criado no painel — esperando o Claude começar", tipo="projeto")
    return {"slug": s, "aviso": aviso}


def iniciar_download(proj: Path) -> None:
    """Baixa o link do projeto em segundo plano, numa sessão própria: fechar o painel não
    interrompe. O avanço vai para o diário (Atividade); a saída crua, para baixar.log."""
    with (proj / "baixar.log").open("ab") as log:
        subprocess.Popen([str(RAIZ / "topclip"), "baixar", str(proj)], cwd=str(RAIZ), stdin=subprocess.DEVNULL,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def info_do_link(link: str) -> dict:
    """Título e duração do vídeo do link, para a pessoa confirmar antes de criar o projeto."""
    import baixar
    try:
        return baixar.info(link)
    except baixar.ErroDownload as e:
        return {"erro": str(e)}


def salvar_escolhas(proj: Path, dados: dict) -> dict:
    atual = ler_json(proj / "escolhas.json", {}) or {}
    for chave in ("momentos", "cortes", "motion"):
        if chave in dados and isinstance(dados[chave], list):
            atual[chave] = [str(x) for x in dados[chave]]
    if "observacao" in dados:
        atual["observacao"] = str(dados["observacao"])[:2000]
    # o estilo do motion: {"id", "variacao"} conferido antes de gravar; null volta ao padrão
    if "estilo" in dados:
        e = dados["estilo"]
        if e is None:
            atual.pop("estilo", None)
        else:
            e = e if isinstance(e, dict) else {"id": e}
            atual["estilo"] = conferir_escolha(e.get("id"), e.get("variacao"))
    atual["atualizado"] = datetime.now().isoformat(timespec="seconds")
    (proj / "escolhas.json").write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    for chave, nomes in (("momentos", ("momento", "momentos")), ("cortes", ("corte", "cortes"))):
        if chave in dados and isinstance(dados[chave], list):
            n = len(dados[chave])
            ATV.registrar(proj, f"você escolheu {n} {nomes[0] if n == 1 else nomes[1]} no painel", tipo="voce",
                          etapa=chave)
    if "estilo" in dados:
        e = atual.get("estilo")
        ATV.registrar(proj, f"você escolheu o estilo {nome_do_estilo(e['id'], e['variacao'])} para o motion" if e
                      else "você voltou para o seu estilo padrão no motion", tipo="voce", etapa="motion")
    return atual


def apagar_projeto(proj: Path) -> dict:
    """Manda a pasta do projeto para a Lixeira — nunca apaga de vez: criou errado ou
    apagou o projeto errado, é só tirar de lá. O vídeo original fora da pasta não é mexido."""
    if atividade(proj)["estado"] == "rodando":
        raise ValueError("O TopClip está trabalhando neste projeto agora. "
                         "Espere terminar (ou pare o Claude) e apague depois.")
    para_lixeira(proj)
    if proj.exists():
        raise ValueError(f"A pasta não saiu do lugar. Apague pelo Finder: {proj}")
    return {"ok": True}


def para_lixeira(p: Path) -> None:
    """Lixeira do sistema: `trash` do macOS 15+ (com "Devolver" no Finder), o Finder nos
    Macs mais antigos, `gio trash` ou `trash-put` no Linux."""
    import shutil
    if sys.platform == "darwin":
        cmd = (["trash", str(p)] if shutil.which("trash") else
               ["osascript", "-e", "on run argv", "-e",
                'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)',
                "-e", "end run", str(p)])
    elif shutil.which("gio"):
        cmd = ["gio", "trash", str(p)]
    elif shutil.which("trash-put"):
        cmd = ["trash-put", str(p)]
    else:
        raise ValueError(f"Não achei a Lixeira deste sistema. Apague a pasta pelo gerenciador de arquivos: {p}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        raise ValueError(f"Não consegui mandar para a Lixeira: {e}")
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout).strip().splitlines()
        raise ValueError("Não consegui mandar para a Lixeira" + (f": {detalhe[-1]}" if detalhe else "."))


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
MAX_EVENTOS = 600             # o log de cada etapa sai daqui: não pode cortar as antigas cedo
SEGUINTE = dict(zip(ORDEM, ORDEM[1:]))


def _nascimento(p: Path) -> float:
    st = p.stat()
    return getattr(st, "st_birthtime", st.st_mtime)


def _evento_arquivo(p: Path, msg: str, quando=None, etapa: str | None = None) -> dict:
    ts = quando if quando is not None else _nascimento(p)
    return {"ts": ts, "t": datetime.fromtimestamp(ts).isoformat(timespec="seconds"), "tipo": "arquivo", "msg": msg,
            "etapa": etapa}


def _etapa_do_artefato(nome: str) -> str:
    """00–05 são dos momentos, 06–10 dos cortes, 11 em diante do vertical."""
    n = int(nome[:2])
    return "momentos" if n <= 5 else "cortes" if n <= 10 else "vertical"


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
            # o manifesto é reescrito a cada etapa: a run nasceu quando a pasta nasceu
            quando = _nascimento(run) if nome == "00-manifest.json" else None
            ev.append(_evento_arquivo(p, rotulo, quando, etapa=_etapa_do_artefato(nome)))
        for p in run.glob("preview/*.mp4"):
            ev.append(_evento_arquivo(p, f"prévia pronta: {p.stem}", etapa="cortes"))
        for p in run.glob("output/final-clips/*/*/clip-vertical.mp4"):
            ev.append(_evento_arquivo(p, f"vertical pronto: {p.parent.name}", etapa="vertical"))
    for m in projetos_motion(proj):
        passos = [("compose.py", "projeto de motion criado"),
                  ("00_brief/fonte.mp4", "clipe vertical copiado para o motion"),
                  ("00_brief/transcript_palavras.json", "transcrição do clipe pronta"),
                  ("00_brief/PLANO_MOTION.md", "plano de motion pronto (frases escolhidas e recusadas)")]
        for rel, rotulo in passos:
            if (m / rel).exists():
                ev.append(_evento_arquivo(m / rel, f"{m.name}: {rotulo}", etapa="motion"))
        quadros = list((m / "08_images" / "frames").glob("*.png")) + list((m / "08_images" / "frames").glob("*.jpg"))
        if quadros:
            ultimo = max(quadros, key=lambda q: q.stat().st_mtime)
            ev.append(_evento_arquivo(ultimo, f"{m.name}: {len(quadros)} quadro{'s' if len(quadros) != 1 else ''} composto{'s' if len(quadros) != 1 else ''}",
                                      ultimo.stat().st_mtime, etapa="motion"))
        for p in (m / "12_master").glob("RASCUNHO*.mp4"):       # remontado no lugar: vale a última vez
            ev.append(_evento_arquivo(p, f"{m.name}: rascunho pronto para revisão", p.stat().st_mtime, etapa="motion"))
        master = master_final(m)
        if master:
            ev.append(_evento_arquivo(master, f"master com motion pronto: {m.name}", etapa="motion"))
    for p in (proj / "entregas").glob("*.mp4"):
        ev.append(_evento_arquivo(p, f"entregue: {p.stem}", etapa="entrega"))
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

    vivos = []
    for e in abertos.values():
        if _pid_vivo(e.get("pid")):
            vivos.append(e)
        else:   # começou e o processo sumiu sem anotar o fim: travou ou foi interrompido
            eventos.append({**e, "tipo": "erro", "msg": f"{e['msg']} — interrompido", "ts": e["ts"] + 0.001})
    vivos.sort(key=lambda e: e["ts"], reverse=True)

    run = run_mais_recente(proj)
    eventos += eventos_de_arquivos(proj, run)
    eventos.sort(key=lambda e: e["ts"], reverse=True)
    _etiquetar(eventos)

    # Progresso (os comandos longos anotam a cada poucos segundos): só o mais recente de
    # cada comando vale, casado pelo id. Sem id (diário antigo), é do comando aberto mais
    # recente antes dele. Com o comando rodando, vai para a manchete; sem comando, o mais
    # novo fica no topo da lista enquanto nada mais novo acontecer.
    progressos = [e for e in eventos if e.get("tipo") == "progresso"]
    eventos = [e for e in eventos if e.get("tipo") != "progresso"]
    agora = datetime.now().timestamp()

    def progresso_de(r):
        return (next((p for p in progressos if p.get("id") and p.get("id") == r.get("id")), None)
                or next((p for p in progressos if not p.get("id") and p["ts"] > r["ts"]), None))

    rodando_todos = []
    for r in vivos:
        p = progresso_de(r)
        rodando_todos.append({"msg": r["msg"], "desde": r["t"], "ha_s": int(agora - r["ts"]),
                              "progresso": p["msg"] if p else None, "pct": p.get("pct") if p else None,
                              "etapa": r.get("etapa"), "sub": r.get("sub"), "clipe": r.get("clipe")})
    rodando = vivos[0] if vivos else None
    if not rodando and progressos and (not eventos or progressos[0]["ts"] > eventos[0]["ts"]):
        eventos.insert(0, progressos[0])
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

    # o download do link é preparação: vídeo baixado ainda é "esperando o Claude" (o erro conta)
    reais = [e for e in eventos if e.get("tipo") != "projeto"
             and not (e.get("origem") == "baixar" and e.get("tipo") != "erro")]
    if rodando:
        estado = "rodando"
    elif eventos and eventos[0].get("tipo") == "voce":
        estado = "avisar_claude"
    elif sua_vez:
        estado = "sua_vez"
    elif not reais:
        estado = "esperando_claude"
    elif ultima and agora - ultima < JANELA_ATIVO_S and eventos[0].get("tipo") in ("info", "inicio", "progresso"):
        estado = "ativo"
    else:
        estado = "parado"

    return {
        "estado": estado,
        "rodando": rodando_todos[0] if rodando_todos else None,
        "rodando_todos": rodando_todos,
        "sua_vez": sua_vez,
        "ultima_ha_s": int(agora - ultima) if ultima else None,
        "eventos": [{k: e.get(k) for k in ("t", "tipo", "msg", "etapa")} for e in eventos[:MAX_EVENTOS]],
        "etapas": progresso_etapas(proj, run, rodando_todos),
        "assinatura": _assinatura(proj, run),
    }


def _etiquetar(eventos: list[dict]) -> None:
    """Dá a cada notícia (mais nova primeiro) a etapa em que aconteceu — é o que separa o
    log por etapa no painel. Quem não diz (o Claude narrando sem --etapa, um comando que
    serve a duas etapas) herda a da notícia anterior. Depois de uma escolha sua, a etapa
    seguinte já começou: é o Claude trabalhando nela."""
    atual, do_comando = "momentos", {}
    for e in reversed(eventos):
        etapa = e.get("etapa") if e.get("etapa") in ORDEM else None
        if not etapa and e.get("tipo") in ("inicio", "fim", "erro") and e.get("id"):
            # diário de antes da etapa nos comandos: o início diz o comando, o fim casa pelo id
            if e.get("tipo") == "inicio" and e.get("comando"):
                do_comando[e["id"]] = ATV.classificar(str(e["comando"]).split())["etapa"]
            etapa = do_comando.get(e["id"])
        if not etapa and e.get("tipo") == "voce":          # diário de antes da etapa nas escolhas
            etapa = "cortes" if "corte" in str(e.get("msg", "")) else "momentos"
        if etapa:
            e["etapa"] = etapa
            # a hora de um arquivo engana (o manifesto e o 06 são reescritos no lugar): ele
            # tem etapa, mas não arrasta as notícias seguintes para ela
            if e.get("tipo") != "arquivo":
                atual = SEGUINTE.get(etapa, etapa) if e.get("tipo") == "voce" else etapa
        else:
            e["etapa"] = atual


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
    partes += [p.name for p in proj.glob("video.mp4")]   # o download do link terminou: sai o "baixando de…"
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

    def _baixar(self, p: Path):
        """Um arquivo para o navegador salvar (não abrir): o .topclip-estilo exportado."""
        dados = p.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{quote(p.name)}"')
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self, limite=1_000_000) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limite:
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
            if dentro(p, PROJETOS, BIBLIOTECA, MINHA) and p.suffix.lower() in VIDEO | IMAGEM:
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
        if rota == "/api/estilos":
            return self._json(estilos())
        m = re.fullmatch(r"/api/estilos/([^/]+)/exportar", rota)
        if m:
            try:
                arq = exportar_estilo(m.group(1))
            except ValueError as e:
                return self._erro(str(e))
            try:
                return self._baixar(arq)
            finally:
                import shutil
                shutil.rmtree(arq.parent, ignore_errors=True)
        m = re.fullmatch(r"/api/estilos/([^/]+)", rota)
        if m:
            d = estilo_detalhe(m.group(1))
            return self._json(d) if d else self._erro("estilo não encontrado", HTTPStatus.NOT_FOUND)
        if rota == "/api/marca":
            return self._json(marca())
        if rota == "/api/preferencias":
            return self._json(preferencias())
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
            # o logo da marca chega em base64 dentro do JSON: o servidor é só biblioteca padrão
            limite = {"/api/marca": LOGO_MAX * 4 // 3 + 100_000,
                      "/api/estilos/importar": IMPORTAR_MAX * 4 // 3 + 100_000}.get(rota, 1_000_000)
            corpo = self._corpo(limite)
            if rota == "/api/marca":
                return self._json(salvar_marca(corpo))
            if rota == "/api/estilos/remixar":
                return self._json(remixar_estilo(corpo))
            if rota == "/api/estilos/importar":
                return self._json(importar_estilo(corpo))
            m = re.fullmatch(r"/api/estilos/([^/]+)/apagar", rota)
            if m:
                return self._json(apagar_estilo(m.group(1)))
            if rota == "/api/marca/conferir":          # o aviso de contraste enquanto a pessoa mexe
                return self._json({"avisos": avisos_da_marca({"cores": corpo.get("cores") or {}})})
            if rota == "/api/preferencias":
                return self._json(salvar_preferencias(corpo))
            if rota == "/api/projetos":
                r = criar_projeto(corpo.get("nome", ""), corpo.get("video", ""), corpo.get("link", ""))
                if corpo.get("link"):
                    iniciar_download(PROJETOS / r["slug"])
                return self._json(r)
            if rota == "/api/info-link":
                return self._json(info_do_link(corpo.get("link", "")))
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
            m = re.fullmatch(r"/api/projetos/([^/]+)/apagar", rota)
            if m:
                p = self._projeto(m.group(1))
                if not p:
                    return self._erro("projeto não encontrado", HTTPStatus.NOT_FOUND)
                return self._json(apagar_projeto(p))
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
