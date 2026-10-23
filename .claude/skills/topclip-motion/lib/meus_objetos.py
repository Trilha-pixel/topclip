#!/usr/bin/env python3
"""
Os objetos dos estilos com lapis (Limpo, Impacto, Luxo): os oficiais
(`biblioteca/pecas/objetos.py`) e os do usuario (`minha-biblioteca/objetos.py`).

    ./topclip objetos            a lista inteira; confere os seus nos tres lapis e grava a
                                 folha minha-biblioteca/objetos.png (o painel mostra)
    ./topclip objetos --json     a lista, para quem le de programa

A biblioteca vem primeiro: antes de desenhar um objeto, procure aqui. O que faltar, o
Claude desenha em minha-biblioteca/objetos.py e roda este comando — objeto com erro nao
entra na folha, e o comando diz por que. Cada `./topclip py` de um projeto de motion leva
a versao atual do arquivo para o projeto (objetos_meus.py).

A lista sai da leitura do codigo (ast), sem executar: o painel usa a mesma funcao.
"""
import argparse
import ast
import importlib.util
import json
import math
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parent
SKILL = LIB.parent
PAPEIS = {"corpo", "face", "detalhe", "destaque", "traco", "vazado"}
LAPIS_DOS_OFICIAIS = (("limpo", "limpo"), ("impacto", "impacto"), ("luxo", "luxo"))
CEL = 200                   # px de cada celula da folha (a folha tem 3 de largura)


def lista(arquivo):
    """[{nome, funcao, descricao}] do dicionario OBJETOS de `arquivo`, na ordem dele, com a
    primeira frase da docstring de cada funcao. Arquivo que nao existe: []. Com erro de
    sintaxe: ValueError."""
    arquivo = Path(arquivo)
    if not arquivo.is_file():
        return []
    try:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    except SyntaxError as e:
        raise ValueError(f"{arquivo.name}, linha {e.lineno}: {e.msg}") from None
    docs = {n.name: ast.get_docstring(n) or "" for n in arvore.body if isinstance(n, ast.FunctionDef)}
    pares = []                             # OBJETOS = {...} e OBJETOS["nome"] = funcao
    for n in arvore.body:
        alvo = n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else None
        if isinstance(alvo, ast.Name) and alvo.id == "OBJETOS" and isinstance(n.value, ast.Dict):
            pares += list(zip(n.value.keys, n.value.values))
        elif (isinstance(alvo, ast.Subscript) and isinstance(alvo.value, ast.Name)
              and alvo.value.id == "OBJETOS"):
            pares.append((alvo.slice, n.value))
    out = {}
    for k, v in pares:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            fn = v.id if isinstance(v, ast.Name) else ""
            doc = " ".join(docs.get(fn, "").split())
            out[k.value] = {"nome": k.value, "funcao": fn, "descricao": doc.split(". ")[0].rstrip(".")}
    return list(out.values())


def _carrega(arquivo):
    spec = importlib.util.spec_from_file_location("objetos_meus", arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    objetos = getattr(mod, "OBJETOS", None)
    if not isinstance(objetos, dict):
        raise ValueError("o arquivo precisa de um dicionario OBJETOS = {\"nome\": funcao}")
    return objetos


def _confere(nome, fn, estilos, desenha):
    """Erros de um objeto: o que ele devolve, os papeis, os pontos, e se sai nos tres lapis."""
    for p in (0.0, 0.5, 1.0):
        try:
            r = fn(p=p)
        except Exception as e:
            return [f"falhou com p={p}: {e}"]
        if not (isinstance(r, tuple) and len(r) == 3):
            return ["devolva (formas, altura, ancoras)"]
        formas, altura, ancoras = r
        if not isinstance(altura, (int, float)) or not 0 < altura <= 4:
            return [f"altura {altura!r}: use um numero entre 0 e 4 (em larguras)"]
        if not isinstance(ancoras, dict):
            return ["ancoras precisa ser um dicionario ({} se nao tiver)"]
        for f in formas:
            if f.get("papel") not in PAPEIS:
                return [f"papel '{f.get('papel')}': use {', '.join(sorted(PAPEIS))}"]
            if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in f["pts"]):
                return ["ponto que nao e numero (nan ou infinito)"]
    formas, altura, _ = fn(p=1.0)
    if not formas:
        return ["com p=1 o objeto nao tem nenhuma forma"]
    for (nome_estilo, lapis), est in zip(LAPIS_DOS_OFICIAIS, estilos):
        if desenha(formas, 200, altura, est, lapis, 1.0).getbbox() is None:
            return [f"sai vazio no lapis {lapis}"]
    return []


def conferir(raiz):
    """Confere os objetos do usuario e grava a folha. Devolve (oficiais, seus, erros, folha)."""
    raiz = Path(raiz)
    sys.path.insert(0, str(raiz / "biblioteca"))
    sys.path.insert(0, str(LIB))
    import estilo as E
    import pecas as P
    from pecas.lapis import desenha
    from pecas.objetos import OBJETOS

    oficiais = lista(raiz / "biblioteca" / "pecas" / "objetos.py")
    arquivo = raiz / "minha-biblioteca" / "objetos.py"
    try:
        seus = lista(arquivo)
    except ValueError as e:
        return oficiais, [], {"objetos.py": [str(e)]}, None
    if not seus:
        return oficiais, [], {}, None
    try:
        meus = _carrega(arquivo)
    except Exception as e:
        return oficiais, seus, {"objetos.py": [f"nao carregou: {e}"]}, None

    estilos = [P.Estilo(E.resolver(raiz / "biblioteca" / "estilos" / nome), SKILL)
               for nome, _ in LAPIS_DOS_OFICIAIS]
    nomes_oficiais = {o["nome"] for o in oficiais}
    erros, bons = {}, []
    for nome, fn in meus.items():
        if nome in nomes_oficiais:
            erros[nome] = ["ja existe um objeto oficial com esse nome: use o oficial ou outro nome"]
            continue
        e = _confere(nome, fn, estilos, desenha)
        if e:
            erros[nome] = e
        else:
            bons.append(nome)

    folha = None
    if bons:
        # uma linha por objeto, os tres lapis lado a lado (cada um no fundo do seu estilo)
        from PIL import Image
        OBJETOS.update({n: meus[n] for n in bons})
        try:
            linhas = [[P.objeto.folha(est, [n], cel=CEL, cols=1, lapis=lapis)
                       for (_, lapis), est in zip(LAPIS_DOS_OFICIAIS, estilos)] for n in bons]
        finally:
            for n in bons:
                OBJETOS.pop(n, None)
        alt = linhas[0][0].height
        out = Image.new("RGB", (CEL * 3, alt * len(linhas)))
        for i, linha in enumerate(linhas):
            for j, cel in enumerate(linha):
                out.paste(cel.convert("RGB"), (j * CEL, i * alt))
        folha = raiz / "minha-biblioteca" / "objetos.png"
        out.save(folha, optimize=True)
    return oficiais, seus, erros, folha


def main(argv=None):
    ap = argparse.ArgumentParser(prog="./topclip objetos", description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", default=str(SKILL.parents[2]))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    raiz = Path(a.raiz)

    if a.json:
        try:
            seus = lista(raiz / "minha-biblioteca" / "objetos.py")
        except ValueError as e:
            seus = [{"erro": str(e)}]
        print(json.dumps({"oficiais": lista(raiz / "biblioteca" / "pecas" / "objetos.py"),
                          "seus": seus}, ensure_ascii=False, indent=1))
        return 0

    oficiais, seus, erros, folha = conferir(raiz)
    largura = max(len(o["nome"]) for o in oficiais + seus) + 2
    print(f"Oficiais ({len(oficiais)}) — biblioteca/pecas/objetos.py")
    for o in oficiais:
        print(f"  {o['nome']:<{largura}}{o['descricao']}")
    print(f"\nSeus ({len(seus)}) — minha-biblioteca/objetos.py")
    if not seus and not erros:
        print("  nenhum ainda. Molde: .claude/skills/topclip-motion/exemplo/objetos_usuario.py")
    for o in seus:
        marca = "ERRO" if o["nome"] in erros else "ok"
        print(f"  {marca:<5}{o['nome']:<{largura}}{o['descricao']}")
    for nome, es in erros.items():
        for e in es:
            print(f"  ERRO {nome}: {e}")
    if folha:
        print(f"\nFolha nos tres lapis: {folha.relative_to(raiz)}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
