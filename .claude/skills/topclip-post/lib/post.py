#!/usr/bin/env python3
"""
Posts virais — frase + prints do vídeo, para o feed (4:5) e os stories (9:16).

    ./topclip post texto projetos/<nome> [--de 10:00] [--ate 25:00]
        a transcrição em linhas com o tempo, para o Claude escolher as frases
    ./topclip post transcrever projetos/<nome>
        transcreve o vídeo do projeto (só quando ainda não há transcrição)
    ./topclip post conferir projetos/<nome>
        confere o posts/frases.json que o Claude escreveu
    ./topclip post prints projetos/<nome> [--refazer] [--sem-banco]
        escolhe os prints de cada frase e o banco de rostos do vídeo
    ./topclip post render projetos/<nome> [--frase <id> ...] [--formato feed|stories]
                          [--prints 1|2|3] [--fonte <id>] [--pb | --cor]
                          [--assinatura | --sem-assinatura] [--carrossel | --unico]
                          [--capa "título com **negrito**" | --sem-capa]
        grava os PNG em posts/prontos/ (sem --frase: as escolhidas no painel, senão todas);
        o carrossel sai em posts/prontos/carrossel/, um slide por frase, na ordem pedida
    ./topclip post minha projetos/<nome> "a frase" [--referencia "Salmos 23:1"]
        uma frase da pessoa (fora da transcrição), já escolhida para virar post
    ./topclip post fontes
        as fontes disponíveis para os posts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import frases as F  # noqa: E402
import projeto as PJ  # noqa: E402

RAIZ = PJ.RAIZ


def _projeto(caminho: str) -> Path:
    p = Path(caminho).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not (p / "projeto.json").is_file():
        raise SystemExit(f"ERRO: {caminho} não é um projeto do TopClip (falta projeto.json)")
    return p


def _seg(v: str | None) -> float | None:
    if not v:
        return None
    partes = [float(x) for x in v.split(":")]
    s = 0.0
    for x in partes:
        s = s * 60 + x
    return s


def _mmss(s: float) -> str:
    return f"{int(s // 60):02d}:{s % 60:04.1f}"


def _atividade():
    sys.path.insert(0, str(RAIZ / "painel"))
    import atividade
    return atividade


# ------------------------------------------------------------------ texto
def linhas_da_transcricao(doc) -> list[tuple[float, float, str]]:
    """(início, fim, texto) por frase falada — do formato da run (segments) ou do motion (palavras)."""
    if isinstance(doc, dict) and isinstance(doc.get("segments"), list):
        return [(float(s["start"]), float(s["end"]), str(s.get("text", "")).strip())
                for s in doc["segments"] if str(s.get("text", "")).strip()]
    if isinstance(doc, list):                       # [{"w", "t", "e"}]: junta até a pontuação ou a pausa
        saida, atual, ini, fim_ant = [], [], None, None
        for p in doc:
            w, t, e = str(p.get("w", "")).strip(), float(p.get("t", 0)), float(p.get("e", 0))
            if atual and fim_ant is not None and t - fim_ant > 1.0:
                saida.append((ini, fim_ant, " ".join(atual)))
                atual, ini = [], None
            if ini is None:
                ini = t
            atual.append(w)
            fim_ant = e
            if w.endswith((".", "?", "!")) and len(atual) >= 4:
                saida.append((ini, e, " ".join(atual)))
                atual, ini = [], None
        if atual:
            saida.append((ini, fim_ant, " ".join(atual)))
        return saida
    return []


def cmd_texto(a) -> int:
    proj = _projeto(a.projeto)
    arq = PJ.achar_transcricao(proj)
    if not arq:
        print("Ainda não há transcrição neste projeto. Rode:\n"
              f"  ./topclip post transcrever {a.projeto}", file=sys.stderr)
        return 2
    de, ate = _seg(a.de), _seg(a.ate)
    linhas = linhas_da_transcricao(json.loads(arq.read_text(encoding="utf-8")))
    print(f"# transcrição: {arq.relative_to(RAIZ) if arq.is_relative_to(RAIZ) else arq}")
    print("# [início–fim] fala   (use os segundos no inicio/fim do frases.json)")
    for ini, fim, txt in linhas:
        if (de is not None and fim < de) or (ate is not None and ini > ate):
            continue
        print(f"[{_mmss(ini)}–{_mmss(fim)}] ({ini:.1f}–{fim:.1f}) {txt}")
    return 0


# ------------------------------------------------------------------ transcrever
def cmd_transcrever(a) -> int:
    proj = _projeto(a.projeto)
    destino = PJ.pasta(proj) / "transcricao.json"
    existente = PJ.achar_transcricao(proj)
    if existente and not a.refazer:
        print(f"Já há transcrição: {existente}\n(use --refazer para transcrever de novo)")
        return 0
    corte = RAIZ / ".claude" / "skills" / "topclip-corte"
    sys.path.insert(0, str(corte))
    info = json.loads((proj / "projeto.json").read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    legenda = info.get("legenda")
    if legenda and Path(legenda).expanduser().is_file():
        from scripts.normalize_transcript import normalize_transcript
        normalize_transcript(str(Path(legenda).expanduser()), destino)
        print(f"Transcrição tirada da legenda do YouTube: {destino}")
        return 0
    video = PJ.video_do_projeto(proj)
    if not video or not video.is_file():
        raise SystemExit(f"ERRO: não achei o vídeo do projeto ({video}). Baixou? ./topclip baixar {a.projeto}")
    from scripts.transcribe import ProgressoTranscricao, transcribe
    transcribe(video, destino, model_name="small", language="pt",
               progress=ProgressoTranscricao(destino, intervalo_s=15))
    print(f"Transcrição pronta: {destino}")
    return 0


# ------------------------------------------------------------------ conferir
def cmd_conferir(a) -> int:
    proj = _projeto(a.projeto)
    frases, avisos, erro = PJ.ler_frases(proj)
    if erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    if not frases:
        print(f"Sem frases ainda: escreva {PJ.pasta(proj) / 'frases.json'}", file=sys.stderr)
        return 1
    tipos = {}
    for f in frases:
        tipos[f.get("tipo", "?")] = tipos.get(f.get("tipo", "?"), 0) + 1
    print(f"ok  {len(frases)} frases · " + ", ".join(f"{n} {F.TIPOS.get(t, t)}" for t, n in sorted(tipos.items(), key=lambda x: -x[1])))
    for av in avisos:
        print(f"aviso  {av}")
    return 0


# ------------------------------------------------------------------ prints
def cmd_prints(a) -> int:
    import prints as P
    proj = _projeto(a.projeto)
    frases, avisos, erro = PJ.ler_frases(proj)
    if erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    video = PJ.video_do_projeto(proj)
    if not video or not video.is_file():
        raise SystemExit(f"ERRO: não achei o vídeo do projeto ({video}).")
    ATV = _atividade()
    prog = ATV.Progresso(proj, "escolhendo os prints dos posts", etapa="posts")
    try:
        doc = P.gerar(video, PJ.pasta(proj), frases, refazer=a.refazer, banco=not a.sem_banco, progresso=prog,
                      avisar=lambda m: print(f"aviso  {m}"))
    except P.ErroPrints as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    sem = [k for k, v in doc["frases"].items() if not v.get("candidatos")]
    print(f"ok  {len(doc['quadros'])} prints · {len(doc['frases'])} frases · banco com {len(doc.get('banco', []))} rostos")
    if sem:
        print(f"aviso  sem rosto perto da frase (usa o banco): {', '.join(sem)}")
    ATV.registrar(proj, f"prints dos posts prontos: {len(doc['frases'])} frases e {len(doc.get('banco', []))} rostos no banco",
                  tipo="info", etapa="posts")
    return 0


# ------------------------------------------------------------------ render
def cmd_render(a) -> int:
    proj = _projeto(a.projeto)
    estado = PJ.ler_estado(proj)
    muda = {}
    if a.formato:
        muda["formato"] = a.formato
    if a.prints:
        alvo = a.formato or ("feed" if a.modo == "carrossel" else estado["formato"])   # carrossel é só no feed
        muda["prints"] = {alvo: a.prints}
    if a.fonte:
        muda["fonte"] = a.fonte
    if a.pb is not None:
        muda["pb"] = a.pb
    if a.assinatura is not None:
        if a.assinatura and not PJ.arroba():
            raise SystemExit("ERRO: a marca não tem @. Cadastre no painel: Biblioteca → Minha marca → Seu @")
        muda["assinatura"] = a.assinatura
    if a.modo:
        muda["modo"] = a.modo
    if a.capa is not None or a.sem_capa:
        muda["capa"] = {"usar": False} if a.sem_capa else {"usar": True, "texto": a.capa or None}
    try:
        estado = PJ._validar(muda, estado)
    except ValueError as e:
        raise SystemExit(f"ERRO: {e}")
    ids = a.frase or estado["escolhidas"] or [f["id"] for f in PJ.todas_as_frases(proj, estado)]
    try:
        if estado["modo"] == "carrossel":
            feitos = PJ.exportar_carrossel(proj, ids, estado)
            if len(feitos) > PJ.SLIDES_MAX:
                print(f"aviso  {len(feitos)} slides: o Instagram aceita até {PJ.SLIDES_MAX} por carrossel", file=sys.stderr)
        else:
            feitos = PJ.exportar(proj, ids, estado)
    except ValueError as e:
        raise SystemExit(f"ERRO: {e}")
    for p in feitos:
        print(p)
    if not feitos:
        print("nenhuma frase para renderizar", file=sys.stderr)
        return 1
    return 0


def cmd_minha(a) -> int:
    proj = _projeto(a.projeto)
    texto = " ".join(a.texto.split())
    if not texto:
        raise SystemExit("ERRO: escreva a frase")
    estado = PJ.ler_estado(proj)
    n = max([int(m["id"].split("-")[1]) for m in estado["minhas"]] or [0]) + 1
    fid = f"minha-{n}"
    PJ.salvar_estado(proj, {
        "minhas": estado["minhas"] + [{"id": fid, "partes": {"1": [texto]}}],
        "escolhidas": estado["escolhidas"] + [fid],
        "edicoes": {fid: {"referencia": a.referencia or ""}},
    })
    print(f"ok  {fid}: {texto}" + (f"  ({a.referencia})" if a.referencia else ""))
    return 0


def cmd_fontes(_a) -> int:
    for f in PJ.fontes():
        print(f"{f['id']:<12} {f['nome']}")
    return 0


def main(argv=None) -> int:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)      # `| head` sem traceback
    ap = argparse.ArgumentParser(prog="./topclip post", description="Posts virais: frase + prints do vídeo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("texto", help="a transcrição em linhas com o tempo")
    s.add_argument("projeto"); s.add_argument("--de"); s.add_argument("--ate")
    s = sub.add_parser("transcrever", help="transcreve o vídeo do projeto")
    s.add_argument("projeto"); s.add_argument("--refazer", action="store_true")
    s = sub.add_parser("conferir", help="confere o posts/frases.json")
    s.add_argument("projeto")
    s = sub.add_parser("prints", help="escolhe os prints das frases e o banco de rostos")
    s.add_argument("projeto"); s.add_argument("--refazer", action="store_true"); s.add_argument("--sem-banco", action="store_true")
    s = sub.add_parser("render", help="grava os PNG em posts/prontos/")
    s.add_argument("projeto"); s.add_argument("--frase", action="append")
    s.add_argument("--formato", choices=["feed", "stories"]); s.add_argument("--prints", type=int, choices=[1, 2, 3])
    s.add_argument("--fonte")
    s.add_argument("--pb", dest="pb", action="store_true", default=None, help="fotos em preto e branco")
    s.add_argument("--cor", dest="pb", action="store_false", help="fotos coloridas")
    s.add_argument("--assinatura", dest="assinatura", action="store_true", default=None, help="o @ da marca no último print")
    s.add_argument("--sem-assinatura", dest="assinatura", action="store_false")
    s.add_argument("--carrossel", dest="modo", action="store_const", const="carrossel", help="um slide por frase, na ordem")
    s.add_argument("--unico", dest="modo", action="store_const", const="unico", help="um post por frase")
    s.add_argument("--capa", help='o título da capa do carrossel ("" usa o do frases.json)')
    s.add_argument("--sem-capa", action="store_true", help="carrossel sem slide de capa")
    s = sub.add_parser("minha", help="uma frase da pessoa, fora da transcrição")
    s.add_argument("projeto"); s.add_argument("texto"); s.add_argument("--referencia")
    sub.add_parser("fontes", help="as fontes disponíveis")
    a = ap.parse_args(argv)
    return {"texto": cmd_texto, "transcrever": cmd_transcrever, "conferir": cmd_conferir, "prints": cmd_prints,
            "render": cmd_render, "minha": cmd_minha, "fontes": cmd_fontes}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
