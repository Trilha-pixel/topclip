"""
As frases dos posts: o formato de `posts/frases.json`, o negrito e a divisão em partes.

Cada frase vem dividida numa parte por print. O negrito vai no próprio texto, entre
asteriscos duplos — `"O resultado **vira consequência.**"` —, o mesmo formato que o Claude
escreve no frases.json e que o painel grava quando a pessoa clica numa palavra.

    {"id": "frase-001", "tipo": "contraste",
     "original": "o trecho literal da transcrição",
     "inicio": 612.4, "fim": 619.8,
     "partes": {"2": ["**Seja obcecado** pelo processo.", "O resultado **vira consequência.**"],
                "3": ["**Seja obcecado**", "pelo processo.", "O resultado **vira consequência.**"]},
     "porque": "contraste processo × resultado; fecha sozinha",
     "legenda": "A legenda pronta do post no Instagram (com até 5 hashtags no fim)."}

O frases.json ainda pode trazer o `carrossel`: o título da capa e a legenda do carrossel
(as frases escolhidas, uma por slide) — `{"capa": "5 verdades sobre **cobrar caro**",
"legenda": "…"}`.

Falta a divisão de um número de prints (a pessoa escolheu 3 e a frase só tem a de 2, ou
a frase é dela): `partes_para` divide de novo, pela pontuação e pelo tamanho.
"""
from __future__ import annotations

import re

TIPOS = {
    "contraste": "contraste",
    "provocacao": "provocação",
    "conselho": "conselho",
    "verdade_dura": "verdade dura",
    "pergunta": "pergunta",
    "inspiracao": "inspiração",
    "historia": "história",
    "numero": "número",
}
PRINTS = (1, 2, 3)
# acima disso a parte não cabe em duas linhas no print (Inter a ~56 px em 1080 de largura)
LIMITE_PARTE = {1: 120, 2: 64, 3: 46}
RE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
PONTUACAO = (",", ".", ";", ":", "!", "?", "—", "…")
LEGENDA_MAX = 2200            # o limite do Instagram
HASHTAGS_MAX = 5              # o Instagram passou a limitar as hashtags por post
CAPA_MAX = 90
RE_HASHTAG = re.compile(r"(?<![\w#])#\w+")


class ErroFrases(ValueError):
    pass


# ------------------------------------------------------------------ negrito
def tokens(texto: str) -> list[tuple[str, bool]]:
    """'O resultado **vira consequência.**' -> [('O', F), ('resultado', F), ('vira', T), ('consequência.', T)]"""
    saida, negrito = [], False
    for i, pedaco in enumerate(str(texto or "").split("**")):
        if i:
            negrito = not negrito
        saida += [(p, negrito) for p in pedaco.split()]
    return saida


def marcar(toks: list[tuple[str, bool]]) -> str:
    """O caminho de volta de `tokens`: cada sequência em negrito vira um só **…**."""
    partes, i = [], 0
    while i < len(toks):
        if toks[i][1]:
            j = i
            while j < len(toks) and toks[j][1]:
                j += 1
            partes.append("**" + " ".join(p for p, _ in toks[i:j]) + "**")
            i = j
        else:
            partes.append(toks[i][0])
            i += 1
    return " ".join(partes)


def limpo(texto: str) -> str:
    return " ".join(p for p, _ in tokens(texto))


# ------------------------------------------------------------------ divisão
def dividir(texto: str, n: int) -> list[str]:
    """Divide uma frase (com negrito) em `n` partes: perto da pontuação e com tamanhos
    parecidos. Com menos palavras que partes, as que sobram ficam vazias."""
    toks = tokens(texto)
    if n <= 1 or len(toks) <= 1:
        return [marcar(toks)] + [""] * (n - 1)
    if len(toks) < n:
        return [marcar([t]) for t in toks] + [""] * (n - len(toks))
    tam = [len(p) + 1 for p, _ in toks]
    total = sum(tam)

    def custo(cortes):
        limites = [0, *cortes, len(toks)]
        pedacos = [sum(tam[a:b]) for a, b in zip(limites, limites[1:])]
        c = sum(abs(p - total / n) for p in pedacos) / total
        # quebrar depois de pontuação é natural; antes de "e", "que", "de"… também serve
        for k in cortes:
            if toks[k - 1][0].endswith(PONTUACAO):
                c -= 0.22
        return c

    if n == 2:
        cortes = min(([k] for k in range(1, len(toks))), key=custo)
    else:
        cortes = min(([a, b] for a in range(1, len(toks) - 1) for b in range(a + 1, len(toks))), key=custo)
    limites = [0, *cortes, len(toks)]
    return [marcar(toks[a:b]) for a, b in zip(limites, limites[1:])]


def partes_para(frase: dict, n: int) -> list[str]:
    """As `n` partes da frase: as que ela traz para esse número de prints, senão a divisão
    de outra (a de 2 primeiro) feita de novo."""
    partes = frase.get("partes") or {}
    proprias = partes.get(str(n))
    if isinstance(proprias, list) and len(proprias) == n and any(str(p).strip() for p in proprias):
        return [str(p) for p in proprias]
    for k in ("2", "3", "1"):
        outra = partes.get(k)
        if isinstance(outra, list) and any(str(p).strip() for p in outra):
            return dividir(" ".join(str(p) for p in outra if str(p).strip()), n)
    return dividir(str(frase.get("texto") or ""), n)


def tempos_para(frase: dict, n: int) -> list[float]:
    """Quando cada parte foi dita: os `tempos` da frase, senão a janela [inicio, fim]
    repartida pelo tamanho de cada parte (fala literal anda mais ou menos no ritmo do texto)."""
    dados = (frase.get("tempos") or {}).get(str(n))
    if isinstance(dados, list) and len(dados) == n and all(isinstance(t, (int, float)) for t in dados):
        return [float(t) for t in dados]
    ini, fim = frase.get("inicio"), frase.get("fim")
    if not isinstance(ini, (int, float)) or not isinstance(fim, (int, float)) or fim <= ini:
        return []
    tam = [max(1, len(limpo(p))) for p in partes_para(frase, n)]
    total, acc, saida = sum(tam), 0, []
    for t in tam:
        saida.append(ini + (fim - ini) * (acc + t / 2) / total)
        acc += t
    return saida


# ------------------------------------------------------------------ legenda e carrossel
def _avisos_legenda(onde: str, legenda) -> list[str]:
    if not isinstance(legenda, str) or not legenda.strip():
        return []
    avisos = []
    if len(legenda) > LEGENDA_MAX:
        avisos.append(f"{onde}: a legenda passa de {LEGENDA_MAX} letras (o Instagram corta)")
    n = len(RE_HASHTAG.findall(legenda))
    if n > HASHTAGS_MAX:
        avisos.append(f"{onde}: {n} hashtags na legenda — use até {HASHTAGS_MAX}")
    return avisos


def carrossel(doc) -> dict:
    """O `carrossel` do frases.json: {"capa": título com **negrito**, "legenda": texto}, só
    com o que veio (texto vazio fica de fora)."""
    c = doc.get("carrossel") if isinstance(doc, dict) else None
    if not isinstance(c, dict):
        return {}
    saida = {}
    if isinstance(c.get("capa"), str) and c["capa"].strip():
        saida["capa"] = " ".join(c["capa"].split())
    if isinstance(c.get("legenda"), str) and c["legenda"].strip():
        saida["legenda"] = c["legenda"].strip()
    return saida


# ------------------------------------------------------------------ conferir o frases.json
def conferir(doc) -> tuple[list[dict], list[str]]:
    """Confere o frases.json do Claude. Devolve (frases, avisos); erro de formato levanta
    ErroFrases com todos os problemas juntos."""
    if not isinstance(doc, dict) or not isinstance(doc.get("frases"), list):
        raise ErroFrases('o frases.json precisa ser {"frases": [ … ]}')
    erros, avisos, vistos, frases = [], [], set(), []
    for i, f in enumerate(doc["frases"], 1):
        onde = f"frase {i}"
        if not isinstance(f, dict):
            erros.append(f"{onde}: precisa ser um objeto")
            continue
        fid = str(f.get("id") or "")
        onde = fid or onde
        if not RE_ID.fullmatch(fid):
            erros.append(f"{onde}: id precisa ser minúsculas, números e hífen (ex.: frase-001)")
        elif fid in vistos:
            erros.append(f"{onde}: id repetido")
        vistos.add(fid)
        partes = f.get("partes")
        if not isinstance(partes, dict) or not isinstance(partes.get("2"), list):
            erros.append(f'{onde}: falta "partes": {{"2": [parte 1, parte 2]}}')
            continue
        for k, lista in partes.items():
            if k not in ("1", "2", "3"):
                erros.append(f"{onde}: partes só para 1, 2 ou 3 prints (veio {k!r})")
                continue
            if not isinstance(lista, list) or len(lista) != int(k) or not all(isinstance(p, str) and p.strip() for p in lista):
                erros.append(f"{onde}: partes[{k!r}] precisa ter {k} textos não vazios")
                continue
            for p in lista:
                if p.count("**") % 2:
                    erros.append(f"{onde}: negrito sem fechar em {p!r}")
                elif len(limpo(p)) > LIMITE_PARTE[int(k)]:
                    avisos.append(f"{onde}: a parte {limpo(p)!r} é longa para {k} prints (mais de {LIMITE_PARTE[int(k)]} letras)")
            if not any("**" in p for p in lista):
                avisos.append(f"{onde}: partes[{k!r}] sem nenhuma palavra em negrito")
        if "3" not in partes:
            avisos.append(f"{onde}: sem a divisão em 3 — o painel divide sozinho se a pessoa escolher 3 prints")
        ini, fim = f.get("inicio"), f.get("fim")
        if not isinstance(ini, (int, float)) or not isinstance(fim, (int, float)) or fim <= ini:
            erros.append(f"{onde}: inicio e fim (segundos no vídeo) são obrigatórios, com fim depois do inicio")
        if f.get("tipo") and f["tipo"] not in TIPOS:
            avisos.append(f"{onde}: tipo {f['tipo']!r} fora da lista ({', '.join(TIPOS)})")
        if not str(f.get("original") or "").strip():
            avisos.append(f"{onde}: sem o trecho original da transcrição")
        leg = f.get("legenda")
        if leg is not None and not isinstance(leg, str):
            erros.append(f"{onde}: a legenda precisa ser um texto")
        elif not str(leg or "").strip():
            avisos.append(f"{onde}: sem legenda — o painel mostra a caixa vazia para a pessoa escrever")
        avisos += _avisos_legenda(onde, leg)
        frases.append(f)
    c = doc.get("carrossel")
    if c is not None:
        if not isinstance(c, dict) or any(k in c and not isinstance(c[k], str) for k in ("capa", "legenda")):
            erros.append('carrossel: precisa ser {"capa": "título", "legenda": "texto"}')
        else:
            capa = c.get("capa") or ""
            if capa.count("**") % 2:
                erros.append(f"carrossel: negrito sem fechar na capa {capa!r}")
            elif len(limpo(capa)) > CAPA_MAX:
                avisos.append(f"carrossel: o título da capa é longo (mais de {CAPA_MAX} letras)")
            avisos += _avisos_legenda("carrossel", c.get("legenda"))
    if erros:
        raise ErroFrases("\n  ".join(["o frases.json tem problemas:", *erros]))
    return frases, avisos
