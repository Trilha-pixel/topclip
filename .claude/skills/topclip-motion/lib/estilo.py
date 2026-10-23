#!/usr/bin/env python3
"""
Estilos de motion: o pacote, o validador e a resolucao estilo <- variacao <- marca.

Um estilo e uma pasta (formato em docs/proposta-estilos.md). Este modulo nao desenha
nada: le o pacote, confere e grava o `estilo/resolvido.json` do projeto, que o render
le para o acabamento e as pecas leem para cor, fonte e movimento.

    ./topclip estilo listar
    ./topclip estilo validar <id|pasta>
    ./topclip estilo previa <id|pasta> [--cena M1]
    ./topclip motion novo <pasta> --estilo <id> [--variacao <v>] [--sem-marca]

Os oficiais ficam em `biblioteca/estilos/` (no git); os do usuario, em
`minha-biblioteca/estilos/` (fora dele). A marca do usuario fica em
`minha-biblioteca/marca/` e so entra nos `slots_da_marca` que o estilo libera.

Vai copiado para todo projeto junto com o resto de `lib/`; ali so `acabamento()` e usado.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PADRAO = "papel"

# Os numeros de movimento que cada estilo herda (24fps). Vem dos guias de motion
# (Material 3, Carbon, Fluent, NN/g), aumentados para video. O estilo sobrescreve o que
# quiser em `tokens.movimento.ajustes` e grava a calibracao de producao no ESTILO.md.
PERFIS = {
    "calmo": {
        "curva_entrada": [0, 0, 0.38, 0.9], "curva_saida": [0.4, 0, 1, 1],
        "curva_movimento": [0.33, 0, 0.67, 1],
        "entrada_quadros": [12, 17], "saida_quadros": [7, 10], "overshoot": [0, 0],
        "stagger_quadros": 3, "coreografia_max_s": 0.9, "tela_min_s": 2.5,
        "eventos_por_10s": [1, 2], "simultaneos": 1, "transicao": "dissolve",
        "push_camera": [0, 0.02], "escala_entrada": 0, "deslocamento_entrada": 30,
    },
    "editorial": {
        "curva_entrada": [0.05, 0.7, 0.1, 1], "curva_saida": [0.3, 0, 0.8, 0.15],
        "curva_movimento": [0.2, 0, 0, 1],
        "entrada_quadros": [8, 12], "saida_quadros": [5, 6], "overshoot": [0, 0.02],
        "stagger_quadros": 2, "coreografia_max_s": 0.6, "tela_min_s": 1.5,
        "eventos_por_10s": [2, 4], "simultaneos": 2, "transicao": "corte_wipe",
        "push_camera": [0.03, 0.06], "escala_entrada": 0, "deslocamento_entrada": 26,
    },
    "energico": {
        "curva_entrada": [0.34, 1.56, 0.64, 1], "curva_saida": [0.7, 0, 0.84, 0],
        "curva_movimento": [0.2, 0, 0, 1],
        "entrada_quadros": [4, 7], "saida_quadros": [2, 4], "overshoot": [0.08, 0.12],
        "stagger_quadros": 1, "coreografia_max_s": 0.4, "tela_min_s": 0.8,
        "eventos_por_10s": [4, 7], "simultaneos": 3, "transicao": "corte_beat",
        "push_camera": [0.08, 0.15],
        # o "pop": a peca nasce pequena e passa do tamanho pela curva que passa de 1
        # (pico ~1,085 -> escala ~1,10); sem deslizar, porque o pop ja e o gesto
        "escala_entrada": 1.18, "deslocamento_entrada": 0,
    },
}
TRANSICOES = {"dissolve", "corte_wipe", "corte_beat"}

# As pecas (biblioteca/pecas/: 8 na fase 2, moldura e brilho na 3). O estilo declara quais usa.
PECAS = {"contador", "marca_texto", "troca_palavra", "desfoque", "cascata",
         "antes_depois", "cartao", "lottie", "moldura", "brilho", "objeto"}
# O lapis desenha os objetos (biblioteca/pecas/lapis.py). O Papel nao tem: desenha com o dele.
LAPIS = {"limpo", "impacto", "luxo"}
DESTAQUES = {"pilula", "texto"}

# Fontes que viajam com a skill: o estilo pode pedir pelo nome, sem trazer o arquivo.
FONTES_DO_KIT = {
    "Archivo Narrow": "ArchivoNarrow[wght].ttf",
    "Archivo Black": "ArchivoBlack-Regular.ttf",
    "Anton": "Anton-Regular.ttf",
    "Permanent Marker": "PermanentMarker-Regular.ttf",
    "IBM Plex Mono": "IBMPlexMono-Medium.ttf",
    "Fraunces": "Fraunces[SOFT,WONK,opsz,wght].ttf",
    "Fraunces Italic": "Fraunces-Italic[SOFT,WONK,opsz,wght].ttf",
    "Inter": "Inter[opsz,wght].ttf",
    "Playfair Display Italic": "PlayfairDisplay-Italic[wght].ttf",
}

# Como os campos da marca viram tokens. So entram os que o estilo pos em slots_da_marca.
MARCA_PARA_TOKEN = {
    ("cores", "primaria"): "cor.acento",
    ("cores", "secundaria"): "cor.apoio",
    ("cores", "texto"): "cor.texto",
    ("fontes", "titulo"): "fonte.titulo",
    ("fontes", "texto"): "fonte.apoio",
}

ORIGENS = {"oficial", "meu", "comunidade"}
# Como as cenas entram no render: "cutaway" (a mesa opaca do Papel, com saida slide/wipe/
# push) ou "overlay" (a cena desenha o proprio fundo e entra e sai sozinha, como no Limpo).
CENAS = {"cutaway", "overlay"}
ANIMACOES = {"corte_seco", "fade", "pop"}
POSICOES = {"rosto", "fixa"}
TRACOS = {"mao", "limpo"}
ARQUIVOS = ("estilo.json", "tokens.json", "legenda.json", "ESTILO.md")
EXECUTAVEIS = {".py", ".pyc", ".sh", ".bash", ".zsh", ".command", ".js", ".mjs", ".cjs",
               ".bat", ".cmd", ".ps1", ".exe", ".dylib", ".so", ".dll", ".app", ".jar"}
LICENCAS = ("SIL Open Font License", "Apache License", "Ubuntu Font Licence")
TAMANHO_MAX = 20 * 1024 * 1024
RE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
RE_VERSAO = re.compile(r"^\d+\.\d+\.\d+$")
RE_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ---------------------------------------------------------------- onde ficam

def pastas(raiz):
    raiz = Path(raiz)
    return [raiz / "biblioteca" / "estilos", raiz / "minha-biblioteca" / "estilos"]


def achar(alvo, raiz):
    """`alvo` e um id (procura nos oficiais, depois nos do usuario) ou uma pasta."""
    p = Path(alvo)
    if p.is_dir() and (p / "estilo.json").exists():
        return p.resolve()
    for base in pastas(raiz):
        if (base / alvo / "estilo.json").exists():
            return (base / alvo).resolve()
    disponiveis = sorted(e.name for e in todos(raiz))
    raise SystemExit(f"estilo '{alvo}' nao encontrado. Disponiveis: {', '.join(disponiveis) or 'nenhum'}")


def todos(raiz):
    vistos, out = set(), []
    for base in pastas(raiz):
        for p in sorted(base.glob("*/estilo.json")) if base.is_dir() else []:
            if p.parent.name not in vistos:
                vistos.add(p.parent.name)
                out.append(p.parent)
    return out


# ---------------------------------------------------------------- leitura

def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def carregar(pasta):
    pasta = Path(pasta)
    return {"estilo": _json(pasta / "estilo.json"), "tokens": _json(pasta / "tokens.json"),
            "legenda": _json(pasta / "legenda.json")}


def token(tokens, caminho):
    """'cor.acento' -> o $value. None se nao existir."""
    no = tokens
    for parte in caminho.split("."):
        if not isinstance(no, dict) or parte not in no:
            return None
        no = no[parte]
    return no.get("$value") if isinstance(no, dict) else None


def _tokens_folha(tokens, prefixo=""):
    for k, v in tokens.items():
        if k.startswith("$"):
            continue
        if isinstance(v, dict) and "$value" in v:
            yield prefixo + k, v
        elif isinstance(v, dict) and k != "movimento":
            yield from _tokens_folha(v, prefixo + k + ".")


def _poe_token(tokens, caminho, valor):
    no = tokens
    partes = caminho.split(".")
    for parte in partes[:-1]:
        no = no.setdefault(parte, {})
    folha = no.setdefault(partes[-1], {})
    folha["$value"] = valor


def extensoes(tokens):
    return (tokens.get("$extensions") or {}).get("topclip") or {}


# ---------------------------------------------------------------- cor

def _lum(hexa):
    def canal(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _neutra(hexa):
    """Cor sem croma (branco, preto, cinza): max - min dos canais abaixo de 12%."""
    h = hexa.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return max(rgb) - min(rgb) < 0.12 * 255


def contraste(a, b):
    """Razao de contraste WCAG 2.x entre duas cores hex (1 a 21)."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- validacao

def _fonte_ok(valor, pasta):
    if valor in FONTES_DO_KIT:
        return True
    return isinstance(valor, str) and (pasta / valor).is_file()


def validar(pasta, exigir_previa=True):
    """Confere o pacote inteiro. Devolve (erros, avisos): pacote com erro nao instala.
    `exigir_previa=False` so para o `previa`, que e quem gera a capa."""
    pasta = Path(pasta)
    erros, avisos = [], []
    for nome in ARQUIVOS:
        if not (pasta / nome).is_file():
            erros.append(f"falta {nome}")
    if erros:
        return erros, avisos
    try:
        d = carregar(pasta)
    except json.JSONDecodeError as e:
        return [f"JSON invalido: {e}"], avisos
    est, tok, leg = d["estilo"], d["tokens"], d["legenda"]

    # estilo.json
    eid = est.get("id")
    if not isinstance(eid, str) or not RE_ID.match(eid):
        erros.append(f"id '{eid}' invalido: minusculas, numeros e hifen, 2 a 31 caracteres")
    elif eid != pasta.name:
        erros.append(f"id '{eid}' diferente do nome da pasta '{pasta.name}'")
    if not isinstance(est.get("nome"), str) or not est["nome"].strip():
        erros.append("falta nome")
    if not RE_VERSAO.match(str(est.get("versao", ""))):
        erros.append(f"versao '{est.get('versao')}' fora do formato 1.0.0")
    if est.get("origem") not in ORIGENS:
        erros.append(f"origem '{est.get('origem')}' deve ser uma de {sorted(ORIGENS)}")
    if est.get("energia") not in PERFIS:
        erros.append(f"energia '{est.get('energia')}' deve ser uma de {sorted(PERFIS)}")
    if not isinstance(est.get("licenca"), str) or not est["licenca"].strip():
        erros.append("falta licenca")
    if not (isinstance(est.get("bom_para"), list) and est["bom_para"]
            and all(isinstance(x, str) for x in est["bom_para"])):
        erros.append("bom_para deve ser uma lista de nichos")
    pecas = est.get("pecas")
    if not isinstance(pecas, list):
        erros.append("pecas deve ser uma lista (pode ser vazia)")
    else:
        for x in pecas:
            if x not in PECAS:
                erros.append(f"peca desconhecida: '{x}' (existem: {', '.join(sorted(PECAS))})")
    var = est.get("variacoes")
    if not isinstance(var, dict) or not var:
        erros.append("variacoes deve ter pelo menos uma (a padrao, com tokens {})")
    else:
        for vid, v in var.items():
            if not isinstance(v, dict) or not isinstance(v.get("nome"), str):
                erros.append(f"variacao '{vid}' sem nome")
                continue
            for caminho, valor in (v.get("tokens") or {}).items():
                if token(tok, caminho) is None:
                    erros.append(f"variacao '{vid}' troca '{caminho}', que nao existe em tokens.json")
                elif caminho.startswith("cor.") and not RE_HEX.match(str(valor)):
                    erros.append(f"variacao '{vid}': '{caminho}' = '{valor}' nao e cor #RRGGBB")
    slots = est.get("slots_da_marca")
    if not isinstance(slots, list):
        erros.append("slots_da_marca deve ser uma lista (pode ser vazia)")
    else:
        for s in slots:
            if s != "logo" and token(tok, s) is None:
                erros.append(f"slot da marca '{s}' nao existe em tokens.json")
    codigo = est.get("codigo")
    if not isinstance(codigo, bool):
        erros.append("codigo deve ser true ou false")
    if est.get("origem") == "comunidade" and codigo:
        erros.append("pacote da comunidade nao pode ter codigo")
    if est.get("cenas", "cutaway") not in CENAS:
        erros.append(f"cenas '{est.get('cenas')}' deve ser uma de {sorted(CENAS)}")
    if isinstance(var, dict):
        for vid, v in var.items():
            t = dict(fundo=token(tok, "cor.fundo"), texto=token(tok, "cor.texto"))
            t.update({k.split(".", 1)[1]: x for k, x in ((v or {}).get("tokens") or {}).items()
                      if k in ("cor.fundo", "cor.texto")})
            if all(isinstance(x, str) and RE_HEX.match(x) for x in t.values()):
                r = contraste(t["fundo"], t["texto"])
                if r < 4.5:
                    avisos.append(f"variacao '{vid}': contraste texto/fundo {r:.1f}:1, abaixo de 4,5:1")

    # tokens.json
    for c in ("cor.fundo", "cor.texto", "cor.acento", "fonte.titulo", "fonte.apoio"):
        if token(tok, c) is None:
            erros.append(f"tokens.json sem '{c}'")
    for caminho, folha in _tokens_folha(tok):
        valor = folha["$value"]
        if folha.get("$type") == "color" and not RE_HEX.match(str(valor)):
            erros.append(f"'{caminho}' = '{valor}' nao e cor #RRGGBB")
        if folha.get("$type") == "fontFamily" and not _fonte_ok(valor, pasta):
            erros.append(f"fonte '{caminho}' = '{valor}': nem fonte do kit nem arquivo do pacote")
    mov = tok.get("movimento") or {}
    perfil = mov.get("perfil", est.get("energia"))
    if perfil not in PERFIS:
        erros.append(f"movimento.perfil '{perfil}' deve ser um de {sorted(PERFIS)}")
    for k, v in (mov.get("ajustes") or {}).items():
        if k not in PERFIS["calmo"]:
            erros.append(f"ajuste de movimento desconhecido: '{k}'")
        elif k == "transicao" and v not in TRANSICOES:
            erros.append(f"transicao '{v}' deve ser uma de {sorted(TRANSICOES)}")
    ext = extensoes(tok)
    if ext.get("traco") not in TRACOS:
        erros.append(f"$extensions.topclip.traco deve ser um de {sorted(TRACOS)}")
    ac = ext.get("acabamento") or {}
    for k, (lo, hi) in {"grao": (0, 0.2), "vinheta": (0, 0.5), "aberracao": (0, 3),
                        "saturacao": (0, 2)}.items():
        if not isinstance(ac.get(k), (int, float)) or not lo <= ac[k] <= hi:
            erros.append(f"acabamento.{k} deve ser numero entre {lo} e {hi}")
    boil = ext.get("boil", None)
    if boil is not None and (not isinstance(boil, (int, float)) or not 0 <= boil <= 2):
        erros.append("boil deve ser null (sem boil) ou numero entre 0 e 2")
    erros += _erros_tipografia(ext.get("tipografia"), tok)
    if ext.get("lapis") is not None and ext["lapis"] not in LAPIS:
        erros.append(f"$extensions.topclip.lapis deve ser um de {sorted(LAPIS)}")
    if "objeto" in (est.get("pecas") or []) and not ext.get("lapis"):
        erros.append("a peca objeto precisa de $extensions.topclip.lapis (o jeito de desenhar)")

    # legenda.json
    for k, tipo in {"corpo": int, "palavras_por_bloco": int, "destaques_por_clipe": int,
                    "contorno": int, "caixa_alta": bool}.items():
        if not isinstance(leg.get(k), tipo) or (tipo is int and isinstance(leg.get(k), bool)):
            erros.append(f"legenda.{k} deve ser {tipo.__name__}")
    if isinstance(leg.get("corpo"), int) and not 30 <= leg["corpo"] <= 200:
        erros.append("legenda.corpo fora de 30 a 200 px")
    if not isinstance(leg.get("enfase"), (int, float)) or not 1 <= leg["enfase"] <= 3:
        erros.append("legenda.enfase deve ser numero entre 1 e 3")
    if leg.get("animacao") not in ANIMACOES:
        erros.append(f"legenda.animacao deve ser uma de {sorted(ANIMACOES)}")
    if leg.get("posicao") not in POSICOES:
        erros.append(f"legenda.posicao deve ser uma de {sorted(POSICOES)}")
    if "peso" in leg and (not isinstance(leg["peso"], int) or not 100 <= leg["peso"] <= 900):
        erros.append("legenda.peso deve ser inteiro entre 100 e 900")
    if "duracao_alvo" in leg and (not isinstance(leg["duracao_alvo"], (int, float))
                                  or not 0.2 <= leg["duracao_alvo"] <= 2.0):
        erros.append("legenda.duracao_alvo deve ser numero entre 0,2 e 2 segundos")
    if leg.get("destaque_modo", "pilula") not in DESTAQUES:
        erros.append(f"legenda.destaque_modo deve ser um de {sorted(DESTAQUES)}")
    sd = leg.get("sombra_dura")
    if sd is not None and not (isinstance(sd, list) and len(sd) == 2
                               and all(isinstance(v, int) and -20 <= v <= 20 for v in sd)):
        erros.append("legenda.sombra_dura deve ser [dx, dy] em px inteiros entre -20 e 20")
    if "entrada_s" in leg and (not isinstance(leg["entrada_s"], (int, float))
                               or not 0.05 <= leg["entrada_s"] <= 0.6):
        erros.append("legenda.entrada_s deve ser numero entre 0,05 e 0,6 segundos")
    for k in ("fonte", "fonte_enfase"):
        if k in leg and _ref(leg[k], tok, pasta) is None:
            erros.append(f"legenda.{k} '{leg[k]}' nao resolve (token, fonte do kit ou arquivo)")
    for k in ("cor", "destaque") + (("fundo",) if leg.get("fundo") is not None else ()):
        v = _ref(leg.get(k), tok, pasta)
        if not (isinstance(v, str) and RE_HEX.match(v)):
            erros.append(f"legenda.{k} '{leg.get(k)}' nao resolve para cor #RRGGBB")
    if "fundo_alfa" in leg and (not isinstance(leg["fundo_alfa"], (int, float))
                                or not 0 < leg["fundo_alfa"] <= 1):
        erros.append("legenda.fundo_alfa deve ser numero entre 0 e 1")

    # arquivos
    total = 0
    for f in pasta.rglob("*"):
        if not f.is_file():
            continue
        total += f.stat().st_size
        rel = f.relative_to(pasta)
        if not codigo and (f.suffix.lower() in EXECUTAVEIS or f.stat().st_mode & 0o111):
            erros.append(f"arquivo executavel num pacote sem codigo: {rel}")
    if total > TAMANHO_MAX:
        erros.append(f"pacote com {total / 1e6:.1f} MB (maximo 20 MB)")
    fontes = list((pasta / "fontes").glob("*.[to]tf")) if (pasta / "fontes").is_dir() else []
    if fontes:
        textos = [f.read_text(encoding="utf-8", errors="ignore")
                  for f in (pasta / "fontes").iterdir() if f.suffix.lower() in (".txt", ".md", "")]
        if not any(lic in t for t in textos for lic in LICENCAS):
            erros.append("fontes/ sem arquivo de licenca (OFL, Apache ou UFL)")
    for png in (pasta / "assets").glob("*.png") if (pasta / "assets").is_dir() else []:
        if not _tem_alfa(png):
            erros.append(f"asset sem canal alfa: assets/{png.name}")
    lot = pasta / "lottie"
    if lot.is_dir():
        if not any(f.suffix.lower() in (".txt", ".md") for f in lot.iterdir()):
            erros.append("lottie/ sem o arquivo de licenca")
        for f in lot.glob("*.json"):
            try:
                if _tem_expression(_json(f)):
                    erros.append(f"lottie/{f.name} usa expressions, que o renderizador nao roda")
            except json.JSONDecodeError:
                erros.append(f"lottie/{f.name} nao e JSON valido")
    if exigir_previa and not (pasta / "preview" / "capa.png").is_file():
        erros.append(f"falta preview/capa.png (gere com ./topclip estilo previa {pasta.name})")
    if not (pasta / "preview" / "demo.mp4").is_file():
        avisos.append("sem preview/demo.mp4 (a galeria mostra so a capa)")
    return erros, avisos


def _erros_tipografia(t, tok):
    """`$extensions.topclip.tipografia`, opcional. Medidas em fracao do corpo da fonte."""
    if t is None:
        return []
    if not isinstance(t, dict):
        return ["tipografia deve ser um objeto"]
    erros = []
    if "caixa_alta" in t and not isinstance(t["caixa_alta"], bool):
        erros.append("tipografia.caixa_alta deve ser true ou false")
    if "contorno" in t and (not isinstance(t["contorno"], (int, float)) or not 0 <= t["contorno"] <= 0.2):
        erros.append("tipografia.contorno deve ser fracao do corpo entre 0 e 0,2")
    if "cor_contorno" in t and not RE_HEX.match(str(t["cor_contorno"])):
        erros.append("tipografia.cor_contorno deve ser #RRGGBB")
    sd = t.get("sombra_dura")
    if sd is not None and not (isinstance(sd, list) and len(sd) == 2 and
                               all(isinstance(v, (int, float)) and -0.2 <= v <= 0.2 for v in sd)):
        erros.append("tipografia.sombra_dura deve ser [dx, dy] em fracao do corpo, entre -0,2 e 0,2")
    for papel, v in (t.get("peso") or {}).items():
        if token(tok, f"fonte.{papel}") is None:
            erros.append(f"tipografia.peso: papel de fonte '{papel}' nao existe em tokens.json")
        elif not isinstance(v, int) or not 100 <= v <= 900:
            erros.append(f"tipografia.peso.{papel} deve ser inteiro entre 100 e 900")
    for papel, v in (t.get("tracking") or {}).items():
        if not isinstance(v, (int, float)) or not -0.1 <= v <= 0.5:
            erros.append(f"tipografia.tracking.{papel} deve ser fracao do corpo entre -0,1 e 0,5")
    return erros


def _ref(valor, tokens, pasta):
    """Campo da legenda: referencia a token ('cor.acento'), fonte do kit, arquivo ou hex."""
    if not isinstance(valor, str):
        return None
    if valor.startswith(("cor.", "fonte.")):
        return token(tokens, valor)
    if RE_HEX.match(valor) or _fonte_ok(valor, pasta):
        return valor
    return None


def _tem_alfa(png):
    from PIL import Image
    with Image.open(png) as im:
        return im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info


def _tem_expression(no):
    """No Lottie, expression e uma string na chave 'x' de uma propriedade."""
    if isinstance(no, dict):
        if isinstance(no.get("x"), str):
            return True
        return any(_tem_expression(v) for v in no.values())
    if isinstance(no, list):
        return any(_tem_expression(v) for v in no)
    return False


# ---------------------------------------------------------------- resolucao

def _caminho_fonte(valor, origem):
    """Fonte do kit -> fontes/ do projeto; arquivo do pacote ou da marca -> dentro de estilo/."""
    if valor in FONTES_DO_KIT:
        return f"fontes/{FONTES_DO_KIT[valor]}"
    return f"{origem}/{valor}"


def resolver(pasta, variacao=None, marca=None):
    """
    Combina estilo <- variacao <- marca num dicionario so, com caminhos relativos a raiz
    do projeto. `marca` e a pasta da marca (com marca.json) ou None.
    """
    pasta = Path(pasta)
    d = carregar(pasta)
    est, tok, leg = d["estilo"], json.loads(json.dumps(d["tokens"])), dict(d["legenda"])
    vid = variacao or next(iter(est["variacoes"]))
    if vid not in est["variacoes"]:
        raise SystemExit(f"variacao '{vid}' nao existe em {est['id']}. "
                         f"Existem: {', '.join(est['variacoes'])}")
    for caminho, valor in (est["variacoes"][vid].get("tokens") or {}).items():
        _poe_token(tok, caminho, valor)

    origem_fonte = {}
    aplicado, recusado, logo = [], [], None
    if marca and (Path(marca) / "marca.json").is_file():
        m = _json(Path(marca) / "marca.json")
        slots = set(est.get("slots_da_marca") or [])
        for (grupo, campo), caminho in MARCA_PARA_TOKEN.items():
            valor = (m.get(grupo) or {}).get(campo)
            if valor is None or caminho not in slots:
                continue
            if caminho.startswith("cor."):
                if not RE_HEX.match(str(valor)):
                    recusado.append({"slot": caminho, "motivo": f"'{valor}' nao e cor #RRGGBB"})
                    continue
                if caminho == "cor.acento" and _neutra(valor):
                    # branco, preto ou cinza nao destacam nada: o estilo fica com o acento
                    # dele (a mesma regra da paleta tirada dos posts)
                    recusado.append({"slot": caminho, "motivo": f"'{valor}' e cor neutra (branco, "
                                     "preto ou cinza) e nao serve de destaque"})
                    continue
                if caminho == "cor.texto":
                    r = contraste(valor, token(tok, "cor.fundo"))
                    if r < 4.5:
                        recusado.append({"slot": caminho,
                                         "motivo": f"contraste {r:.1f}:1 com o fundo, abaixo de 4,5:1"})
                        continue
            else:
                if valor not in FONTES_DO_KIT and not (Path(marca) / valor).is_file():
                    recusado.append({"slot": caminho, "motivo": f"fonte '{valor}' nao encontrada"})
                    continue
                if valor not in FONTES_DO_KIT:
                    origem_fonte[caminho] = "estilo/marca"
            _poe_token(tok, caminho, valor)
            aplicado.append(caminho)
        if "logo" in slots and m.get("logo") and (Path(marca) / m["logo"]).is_file():
            logo = f"estilo/marca/{m['logo']}"
            aplicado.append("logo")

    cores = {k.split(".", 1)[1]: f["$value"] for k, f in _tokens_folha(tok) if k.startswith("cor.")}
    fontes = {k.split(".", 1)[1]: _caminho_fonte(f["$value"], origem_fonte.get(k, "estilo"))
              for k, f in _tokens_folha(tok) if k.startswith("fonte.")}
    mov = tok.get("movimento") or {}
    perfil = mov.get("perfil", est["energia"])
    movimento = dict(PERFIS[perfil], perfil=perfil, **(mov.get("ajustes") or {}))
    ext = extensoes(tok)

    def leg_valor(k, v):
        if isinstance(v, str) and v.startswith("cor."):
            return token(tok, v)
        if k in ("fonte", "fonte_enfase"):
            return fontes[v.split(".", 1)[1]] if v.startswith("fonte.") else _caminho_fonte(v, "estilo")
        return v
    legenda = {k: leg_valor(k, v) for k, v in leg.items()}

    return {
        "id": est["id"], "nome": est["nome"], "versao": est["versao"],
        "origem": est["origem"], "variacao": vid, "energia": est["energia"],
        "cenas": est.get("cenas", "cutaway"),
        "cor": cores, "fonte": fontes, "movimento": movimento,
        "acabamento": ext["acabamento"], "boil": ext.get("boil"), "traco": ext["traco"],
        "tipografia": ext.get("tipografia") or {}, "lapis": ext.get("lapis"),
        "legenda": legenda,
        "marca": {"aplicado": aplicado, "recusado": recusado, "logo": logo},
    }


def instalar(pasta, projeto, variacao=None, marca=None, exigir_previa=True):
    """
    Copia o pacote para `<projeto>/estilo/` (o projeto congela a versao que usou), a marca
    para `estilo/marca/`, os assets do pacote para `07_assets/cutout/`, e grava o
    `resolvido.json`. Valida antes: pacote com erro nao entra.

    Estilo com cenas proprias (`codigo: true` + `compose.py`) troca o compose.py do projeto
    pelo dele; estilo de cenas "overlay" acerta o exemplo do SHOTS do render.py.
    """
    pasta, projeto = Path(pasta), Path(projeto)
    erros, _ = validar(pasta, exigir_previa)
    if erros:
        raise SystemExit(f"estilo {pasta.name} invalido:\n  " + "\n  ".join(erros))
    est = carregar(pasta)["estilo"]
    alvo, molde = projeto / "compose.py", projeto / "compose_template.py"
    intocado = not alvo.exists() or (molde.exists() and alvo.read_bytes() == molde.read_bytes())
    modelo = projeto / "pecas" / "compose_modelo.py"
    if est.get("codigo") and (pasta / "compose.py").is_file() and intocado:
        # so troca o compose recem-criado: num projeto com cenas escritas, nunca sobrescreve
        shutil.copy2(pasta / "compose.py", alvo)
    elif est.get("cenas") == "overlay" and intocado and modelo.is_file():
        # estilo de pecas sem compose proprio (o importado, que chega sem codigo): as
        # cenas-exemplo genericas das pecas, que vestem qualquer estilo
        shutil.copy2(modelo, alvo)
    render = projeto / "render.py"
    if est.get("cenas") == "overlay" and render.is_file():
        t = render.read_text(encoding="utf-8")
        render.write_text(t.replace("77, True),   # exemplo", "77, False),  # exemplo"),
                          encoding="utf-8")
    r = resolver(pasta, variacao, marca)
    dest = projeto / "estilo"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(pasta, dest, ignore=shutil.ignore_patterns("preview", ".*"))
    if marca and r["marca"]["aplicado"]:
        shutil.copytree(marca, dest / "marca", ignore=shutil.ignore_patterns(".*"))
    cutout = projeto / "07_assets" / "cutout"
    for png in sorted((pasta / "assets").glob("*.png")) if (pasta / "assets").is_dir() else []:
        cutout.mkdir(parents=True, exist_ok=True)
        shutil.copy2(png, cutout / png.name)
    (dest / "resolvido.json").write_text(json.dumps(r, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return r


# ---------------------------------------------------------------- no projeto

def resolvido(raiz_projeto):
    f = Path(raiz_projeto) / "estilo" / "resolvido.json"
    return _json(f) if f.is_file() else None


def acabamento(raiz_projeto, fx, boil):
    """
    O acabamento e o boil do estilo do projeto, para o `finish()` e o `BOIL_SCALE`. Sem
    `estilo/resolvido.json` (projeto antigo) volta o que recebeu. O Papel resolve para os
    mesmos valores do template: o teste de regressao confere quadro a quadro.
    Estilo sem boil (`null`) zera a escala do boil dos objetos.
    """
    r = resolvido(raiz_projeto)
    if r is None:
        return fx, boil
    a = r["acabamento"]
    fx = dict(grain=a["grao"], vignette=a["vinheta"], chroma=a["aberracao"], sat=a["saturacao"])
    return fx, (0.0 if r.get("boil") is None else r["boil"])


# ---------------------------------------------------------------- previas

def _projeto_temporario(raiz, pasta, destino, variacao):
    """O minimo de um projeto de motion para renderizar previas (o que o motion novo faz,
    sem os assets do usuario e sem a marca: a previa mostra o estilo puro)."""
    skill = Path(raiz) / ".claude" / "skills" / "topclip-motion"
    destino.mkdir(parents=True)
    for f in (skill / "lib").glob("*.py"):
        shutil.copy2(f, destino)
    shutil.copy2(skill / "lib" / "compose_template.py", destino / "compose.py")
    shutil.copy2(skill / "lib" / "render_template.py", destino / "render.py")
    shutil.copytree(skill / "fontes", destino / "fontes")
    shutil.copytree(Path(raiz) / "biblioteca" / "pecas", destino / "pecas",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("cutout", "raw"):
        (destino / "07_assets" / sub).mkdir(parents=True)
    for png in (Path(raiz) / "biblioteca" / "assets").glob("*.png"):
        sub = "raw" if png.name == "BG_PAPER.png" else "cutout"
        shutil.copy2(png, destino / "07_assets" / sub / png.name)
    instalar(pasta, destino, variacao, None, exigir_previa=False)


def previa(pasta, raiz, cena=None):
    """
    Gera as previas que a galeria mostra, dentro do proprio pacote:
      preview/capa.png              a cena `cena` (padrao: a primeira) no END, variacao padrao
      preview/capa-<variacao>.png   a mesma cena nas outras variacoes
      preview/pecas/<peca>.png      cada peca declarada, no EXEMPLO dela
    """
    import subprocess
    import tempfile
    pasta = Path(pasta)
    est = _json(pasta / "estilo.json")
    destino = pasta / "preview"
    (destino / "pecas").mkdir(parents=True, exist_ok=True)
    gerados = []
    with tempfile.TemporaryDirectory(prefix="topclip-previa-") as tmp:
        for i, vid in enumerate(est["variacoes"]):
            proj = Path(tmp) / vid
            _projeto_temporario(raiz, pasta, proj, vid)
            capa = "capa.png" if i == 0 else f"capa-{vid}.png"
            cmd = [sys.executable, "-m", "pecas.previa", str(destino), "--capa", capa]
            if i == 0:
                cmd.append("--pecas")
            if cena:
                cmd += ["--cena", cena]
            r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True)
            if r.returncode:
                raise SystemExit(f"previa de {pasta.name} ({vid}) falhou:\n{r.stdout}{r.stderr}")
            gerados += [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return gerados


# ---------------------------------------------------------------- linha de comando

def _listar(raiz):
    itens = todos(raiz)
    if not itens:
        print("nenhum estilo encontrado")
        return 0
    for p in itens:
        try:
            e = _json(p / "estilo.json")
            erros, _ = validar(p)
            marca = "ok " if not erros else "ERRO"
            var = ", ".join(e.get("variacoes") or {})
            print(f"  {marca} {e.get('id', p.name):12s} {e.get('nome', ''):14s} "
                  f"{e.get('origem', '?'):10s} {e.get('energia', '?'):9s} variacoes: {var}")
        except (OSError, json.JSONDecodeError) as ex:
            print(f"  ERRO {p.name:12s} {ex}")
    return 0


def _validar(alvo, raiz, quieto=False, variacao=None):
    p = achar(alvo, raiz)
    erros, avisos = validar(p)
    if variacao and not erros:
        existem = _json(p / "estilo.json")["variacoes"]
        if variacao not in existem:
            erros.append(f"variacao '{variacao}' nao existe em {p.name}. Existem: {', '.join(existem)}")
    if not quieto or erros:
        for a in avisos:
            print(f"  aviso {a}")
        for e in erros:
            print(f"  ERRO  {e}")
        if not erros:
            print(f"  ok    {p.name} valido")
    return 1 if erros else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="./topclip estilo", description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", default=str(Path(__file__).resolve().parents[4]))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar", help="estilos oficiais e os seus")
    v = sub.add_parser("validar", help="confere um pacote")
    v.add_argument("alvo", help="id do estilo ou pasta do pacote")
    v.add_argument("--quieto", action="store_true", help="so fala se houver erro")
    v.add_argument("--variacao", help="confere tambem que a variacao existe")
    i = sub.add_parser("instalar", help="poe o estilo num projeto de motion")
    i.add_argument("alvo")
    i.add_argument("projeto")
    i.add_argument("--variacao")
    i.add_argument("--sem-marca", action="store_true")
    pv = sub.add_parser("previa", help="gera preview/ (capa e pecas) dentro do pacote")
    pv.add_argument("alvo")
    pv.add_argument("--cena", help="cena do compose.py para a capa (padrao: a primeira)")
    import meu_estilo                       # remixar, ajustar, aprovar, exportar, importar...
    do_usuario = meu_estilo.comandos(sub)
    a = ap.parse_args(argv)
    if a.cmd in do_usuario:
        return meu_estilo.roda(a)
    if a.cmd == "listar":
        return _listar(a.raiz)
    if a.cmd == "validar":
        return _validar(a.alvo, a.raiz, a.quieto, a.variacao)
    if a.cmd == "previa":
        for linha in previa(achar(a.alvo, a.raiz), a.raiz, a.cena):
            print(f"  {linha}")
        return 0
    marca = None if a.sem_marca else Path(a.raiz) / "minha-biblioteca" / "marca"
    r = instalar(achar(a.alvo, a.raiz), a.projeto, a.variacao, marca)
    print(f"  estilo {r['nome']} ({r['variacao']}), versao {r['versao']}")
    if r["marca"]["aplicado"]:
        print(f"  marca aplicada em: {', '.join(r['marca']['aplicado'])}")
    for x in r["marca"]["recusado"]:
        print(f"  aviso: marca nao entrou em {x['slot']}: {x['motivo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
