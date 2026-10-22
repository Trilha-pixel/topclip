#!/usr/bin/env python3
"""
Diário de atividade de um projeto: `projetos/<nome>/atividade.jsonl`.

É o que o painel mostra em "Atividade" — para a pessoa saber se o TopClip está mesmo
trabalhando. Quatro fontes escrevem aqui:

  * o lançador `./topclip`, sozinho, no início e no fim de cada comando de corte ou
    transcrição (com duração e se deu erro);
  * o Claude, narrando as etapas dele:  ./topclip log projetos/<nome> "procurando momentos"
  * o próprio painel, quando a pessoa cria o projeto ou salva escolhas;
  * a transcrição do `corte prepare` (scripts/transcribe.py), anotando o avanço algumas
    vezes por minuto com tipo "progresso" — o painel mostra só o mais recente.

Uso pelo lançador (não precisa chamar à mão):
    atividade.py registrar <projeto> <tipo> <mensagem...>
    atividade.py inicio <projeto> <id> <pid> <comando...>
    atividade.py fim <projeto> <id> <codigo> <segundos> <comando...>
    atividade.py achar-projeto <args...>      imprime a pasta do projeto, se algum argumento apontar para uma

Registrar nunca pode derrubar o pipeline: qualquer erro aqui é engolido em silêncio.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROJETOS = RAIZ / "projetos"
ARQUIVO = "atividade.jsonl"

# O que cada subcomando de corte significa, em português de gente.
COMANDOS = {
    "preflight": "conferindo a instalação",
    "init": "criando a run do projeto",
    "prepare": "preparando o vídeo e transcrevendo — em vídeo longo, leva vários minutos",
    "digest": "resumindo a transcrição para o Claude ler",
    "visual-index": "olhando os frames dos trechos escolhidos",
    "validate-artifact": "conferindo um arquivo da run",
    "validate-project": "conferindo o pacote",
    "blind-packets": "preparando a revisão cega",
    "audit": "auditando os cortes",
    "dedupe": "tirando cortes repetidos",
    "autoframe": "enquadrando em 9:16, seguindo quem fala",
    "finalize": "fechando o relatório da run",
    "subtitles": "gerando a legenda palavra a palavra",
    "render": "renderizando os clipes",
    "verify-output": "conferindo os clipes finais",
    "transcrever": "transcrevendo o clipe palavra a palavra",
}


def descrever(comando: list[str]) -> str:
    """['corte', 'prepare', '--run', ...] -> 'preparando o vídeo e transcrevendo…'"""
    for parte in comando:
        if parte in COMANDOS:
            return COMANDOS[parte]
    return " ".join(comando[:2]) or "comando"


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
        linha = {"t": datetime.now().isoformat(timespec="milliseconds"), "tipo": tipo, "msg": str(msg)[:500], **extra}
        with (projeto / ARQUIVO).open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        pass


def ler(projeto: Path, ultimas: int = 300) -> list[dict]:
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
    return out


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
            registrar(alvo, " ".join(resto[2:]), tipo=resto[1])
        elif acao == "inicio" and len(resto) >= 3:
            projeto, ident, pid, comando = Path(resto[0]), resto[1], resto[2], resto[3:]
            registrar(projeto, descrever(comando), tipo="inicio", id=ident, pid=int(pid),
                      comando=" ".join(comando)[:200])
        elif acao == "fim" and len(resto) >= 4:
            projeto, ident, codigo, segundos, comando = Path(resto[0]), resto[1], int(resto[2]), int(resto[3]), resto[4:]
            desc = descrever(comando)
            if codigo == 0:
                registrar(projeto, f"{desc} — pronto em {_duracao(segundos)}", tipo="fim", id=ident, codigo=0)
            else:
                registrar(projeto, f"{desc} — falhou (código {codigo}) depois de {_duracao(segundos)}",
                          tipo="erro", id=ident, codigo=codigo)
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
