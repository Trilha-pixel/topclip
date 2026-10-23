#!/usr/bin/env python3
"""
Diário de atividade de um projeto: `projetos/<nome>/atividade.jsonl`.

É o que o painel mostra em "Atividade" — para a pessoa saber se o TopClip está mesmo
trabalhando, e em que ponto de cada etapa. Quatro fontes escrevem aqui:

  * o lançador `./topclip`, sozinho, no início e no fim de cada comando de corte, de
    transcrição e de script de motion (`./topclip py projetos/...`), com duração, se deu
    erro e a etapa do painel em que o comando cai;
  * o Claude, narrando as etapas dele:
        ./topclip log projetos/<nome> --etapa cortes "Clip Builder montando os cortes"
  * o próprio painel, quando a pessoa cria o projeto ou salva escolhas;
  * os comandos longos (transcrição, prévias, enquadramento, render, render do motion),
    anotando o avanço com tipo "progresso" e `pct` — a barra do painel. Só o mais
    recente de cada comando vale. Use `Progresso` para isso.

Toda linha pode levar `etapa` (momentos, cortes, vertical, motion, entrega). Sem ela, o
painel herda a etapa da notícia anterior. Os posts virais (`./topclip post …`) correm por
fora da fila de etapas: a linha deles leva `etapa` "posts" e não puxa as outras.

Uso pelo lançador (não precisa chamar à mão):
    atividade.py registrar <projeto> <tipo> [--etapa X] <mensagem...>
    atividade.py inicio <projeto> <id> <pid> <comando...>
    atividade.py fim <projeto> <id> <codigo> <segundos> <comando...>
    atividade.py achar-projeto <args...>      imprime a pasta do projeto, se algum argumento apontar para uma

Registrar nunca pode derrubar o pipeline: qualquer erro aqui é engolido em silêncio.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROJETOS = RAIZ / "projetos"
ARQUIVO = "atividade.jsonl"
ETAPAS = ("momentos", "cortes", "vertical", "motion", "entrega", "posts")
ENV_ID = "TOPCLIP_ATIVIDADE"      # o lançador exporta o id do comando: o progresso casa com ele

# O que cada subcomando significa, em português de gente, e a etapa do painel em que cai.
# Etapa None: o comando roda em mais de uma (bordas, revisões…) — herda a da notícia anterior.
COMANDOS = {
    "preflight": ("conferindo a instalação", "momentos"),
    "init": ("criando a run do projeto", "momentos"),
    "prepare": ("preparando o vídeo e transcrevendo — em vídeo longo, leva vários minutos", "momentos"),
    "digest": ("resumindo a transcrição para o Claude ler", "momentos"),
    "visual-index": ("olhando os frames dos trechos escolhidos", "cortes"),
    "validate-artifact": ("conferindo um arquivo da run", None),
    "validate-project": ("conferindo o pacote", None),
    "estimate": ("dando a nota estimada de cada um", "momentos"),
    "previews": ("cortando as prévias para você assistir", "cortes"),
    "blind-packets": ("preparando a revisão cega", "cortes"),
    "audit": ("auditando os cortes", "cortes"),
    "dedupe": ("tirando cortes repetidos", "cortes"),
    "bordas": ("acertando as bordas dos cortes no respiro da fala", None),
    "revisoes": ("conferindo se as revisões são da versão atual", None),
    "autoframe": ("enquadrando em 9:16, seguindo quem fala", "vertical"),
    "finalize": ("fechando o relatório da run", "vertical"),
    "subtitles": ("gerando a legenda palavra a palavra", "vertical"),
    "render": ("renderizando os clipes", "vertical"),
    "verify-output": ("conferindo os clipes finais", "vertical"),
    "transcrever": ("transcrevendo o clipe palavra a palavra", "motion"),
    "compose.py": ("compondo as cenas do motion", "motion"),
    "render.py": ("montando o vídeo com motion", "motion"),
}
# ./topclip post <sub>: os posts virais, que correm por fora das etapas dos clipes
POSTS = {
    "texto": "lendo a transcrição para achar as frases dos posts",
    "transcrever": "transcrevendo o vídeo para os posts",
    "conferir": "conferindo as frases dos posts",
    "prints": "escolhendo os prints dos posts",
    "render": "gravando os posts prontos",
}


def classificar(comando: list[str]) -> dict:
    """['corte', 'prepare', '--run', ...] -> o que é, em português, e em que etapa cai.

    Devolve {"sub": "prepare", "msg": "preparando…", "etapa": "momentos", "clipe": None}.
    `clipe` é o clipe do motion (`.../motion/clip-005/render.py`), quando houver.
    """
    if comando and comando[0] == "post":
        nome = comando[1] if len(comando) > 1 else ""
        return {"sub": f"post:{nome}", "msg": POSTS.get(nome, "posts virais"), "etapa": "posts", "clipe": None}
    sub = msg = etapa = None
    for parte in comando:
        nome = Path(parte).name if parte.endswith(".py") else parte
        if nome in COMANDOS:
            sub = nome
            msg, etapa = COMANDOS[nome]
            break
    juntos = " ".join(comando)
    m = re.search(r"/motion/([^/\s]+)/", juntos)
    clipe = m.group(1) if m else None
    if sub == "estimate" and "--cortes" in comando:
        msg, etapa = "dando a nota estimada de cada corte", "cortes"
    elif sub == "digest" and "--windows" in comando:
        msg, etapa = "puxando o tempo de cada palavra dos trechos escolhidos", "cortes"
    elif sub == "validate-artifact":
        arq = next((m for p in comando if (m := re.match(r"(\d\d)-[\w-]+\.json$", Path(p).name))), None)
        n = int(arq.group(1)) if arq else -1
        etapa = "momentos" if 0 <= n <= 5 else "cortes" if 6 <= n <= 10 else "vertical" if n >= 11 else None
    elif sub == "render.py" and "--rascunho" in comando:
        sub, msg = "render.py:rascunho", "montando o rascunho do motion para revisão"
    elif sub == "compose.py" and "--check" in comando:
        msg = "conferindo as cenas do motion"
    elif sub is None:
        script = next((p for p in comando if p.endswith(".py")), None)
        msg = f"rodando {Path(script).name}" if script else (" ".join(comando[:2]) or "comando")
    if clipe:
        etapa = "motion"
        msg = f"{clipe}: {msg}"
    return {"sub": sub, "msg": msg, "etapa": etapa, "clipe": clipe}


def descrever(comando: list[str]) -> str:
    """['corte', 'prepare', '--run', ...] -> 'preparando o vídeo e transcrevendo…'"""
    return classificar(comando)["msg"]


def achar_projeto(args: list[str]) -> Path | None:
    """A pasta `projetos/<nome>` que algum argumento cita (relativo ou absoluto)."""
    for a in args:
        m = re.search(r"(?:^|/)projetos/([a-z0-9][a-z0-9-]*)", a)
        if m:
            p = PROJETOS / m.group(1)
            if p.is_dir():
                return p
    return None


def registrar(projeto: Path, msg: str, tipo: str = "info", **extra) -> None:
    try:
        projeto = Path(projeto)
        if not projeto.is_dir():
            return
        extra = {k: v for k, v in extra.items() if v is not None}
        linha = {"t": datetime.now().isoformat(timespec="milliseconds"), "tipo": tipo, "msg": str(msg)[:500], **extra}
        with (projeto / ARQUIVO).open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        pass


def ler(projeto: Path, ultimas: int = 5000) -> list[dict]:
    """As últimas linhas do diário. Dos "progresso", fica só o mais recente de cada
    comando — eles chegam a cada poucos segundos e afogariam o resto."""
    p = Path(projeto) / ARQUIVO
    if not p.exists():
        return []
    try:
        linhas = p.read_text(encoding="utf-8", errors="replace").splitlines()[-ultimas:]
    except Exception:
        return []
    out = []
    for l in linhas:
        try:
            out.append(json.loads(l))
        except Exception:
            continue
    vistos, enxuto = set(), []
    for e in reversed(out):
        if e.get("tipo") == "progresso":
            chave = e.get("id")
            if chave in vistos:
                continue
            vistos.add(chave)
        enxuto.append(e)
    return enxuto[::-1]


class Progresso:
    """
    A barra de um comando longo no painel. Cada chamada anota um "progresso" com `pct`
    no diário — no máximo um a cada `intervalo_s` (o primeiro e o de 100% sempre passam).

        prog = Progresso(run, "renderizando os clipes", etapa="vertical")
        for i, clipe in enumerate(clipes):
            prog(i, len(clipes), clipe_id)        # "renderizando os clipes: 1 de 3 · clip-007 (33%)"
            ...
        prog(len(clipes), len(clipes))

        prog.marcar(80, "juntando tudo no master")   # quando a conta não é "i de n"

    `onde` é qualquer caminho dentro de projetos/<nome>. Fora dele (run avulsa, testes),
    não anota nada. Nunca derruba quem chama.
    """

    def __init__(self, onde, rotulo: str, *, etapa: str | None = None, intervalo_s: float = 4.0,
                 relogio=time.monotonic):
        self.rotulo, self.etapa, self.intervalo_s, self.relogio = rotulo, etapa, float(intervalo_s), relogio
        self.ultimo = None
        self.id = os.environ.get(ENV_ID) or None
        try:
            self.projeto = achar_projeto([str(Path(onde).expanduser().resolve())])
        except Exception:
            self.projeto = None

    def __call__(self, feito, total, detalhe: str = "") -> None:
        try:
            pct = max(0, min(100, int(100 * feito / total))) if total else None
            msg = f"{self.rotulo}: {feito} de {total}" + (f" · {detalhe}" if detalhe else "")
            if pct is not None:
                msg += f" ({pct}%)"
            self.marcar(pct, msg, final=bool(total) and feito >= total)
        except Exception:
            pass

    def marcar(self, pct, msg: str, *, final: bool = False) -> None:
        try:
            agora = self.relogio()
            if not final and self.ultimo is not None and agora - self.ultimo < self.intervalo_s:
                return
            self.ultimo = agora
            if self.projeto:
                pct = None if pct is None else max(0, min(100, int(pct)))
                registrar(self.projeto, msg, tipo="progresso", pct=pct, etapa=self.etapa, id=self.id)
        except Exception:
            pass


def _tirar_opcao(resto: list[str], nome: str) -> tuple[list[str], str | None]:
    """['--etapa', 'cortes', 'msg'] -> (['msg'], 'cortes'). Sem a opção, nada muda."""
    if nome in resto:
        k = resto.index(nome)
        if k + 1 < len(resto):
            return resto[:k] + resto[k + 2:], resto[k + 1]
    return resto, None


def main(argv: list[str]) -> int:
    try:
        if not argv:
            return 0
        acao, resto = argv[0], argv[1:]
        if acao == "achar-projeto":
            p = achar_projeto(resto)
            if p:
                print(p)
            return 0
        if acao == "registrar" and len(resto) >= 3:
            alvo = achar_projeto([resto[0]]) or Path(resto[0])
            msg, etapa = _tirar_opcao(resto[2:], "--etapa")
            if msg:
                registrar(alvo, " ".join(msg), tipo=resto[1], etapa=etapa if etapa in ETAPAS else None)
        elif acao == "inicio" and len(resto) >= 3:
            projeto, ident, pid, comando = Path(resto[0]), resto[1], resto[2], resto[3:]
            c = classificar(comando)
            registrar(projeto, c["msg"], tipo="inicio", id=ident, pid=int(pid), comando=" ".join(comando)[:200],
                      sub=c["sub"], etapa=c["etapa"], clipe=c["clipe"])
        elif acao == "fim" and len(resto) >= 4:
            projeto, ident, codigo, segundos, comando = Path(resto[0]), resto[1], int(resto[2]), int(resto[3]), resto[4:]
            c = classificar(comando)
            desc, extra = c["msg"], {"id": ident, "sub": c["sub"], "etapa": c["etapa"], "clipe": c["clipe"]}
            if codigo == 0:
                registrar(projeto, f"{desc} — pronto em {_duracao(segundos)}", tipo="fim", codigo=0, **extra)
            else:
                registrar(projeto, f"{desc} — falhou (código {codigo}) depois de {_duracao(segundos)}",
                          tipo="erro", codigo=codigo, **extra)
    except Exception:
        pass
    return 0


def _duracao(s: int) -> str:
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}min {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}min"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
