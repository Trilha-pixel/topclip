"""
Os posts de um projeto: as frases (as do Claude e as da pessoa), os prints e o que ela
escolheu no painel — e, juntando tudo, a arte de cada post.

    projetos/<nome>/posts/
      frases.json     as frases que o Claude achou na transcrição (skill topclip-post)
      prints.json     os prints de cada frase e o banco do vídeo (./topclip post prints)
      prints/         os quadros (JPG) e as miniaturas — e as fotos que a pessoa subiu (f-0001)
      posts.json      o que a pessoa escolheu e editou no painel
      prontos/        os PNG finais (o painel grava ao baixar; ./topclip post render)
      prontos/carrossel/  os slides do carrossel, numerados na ordem, e a legenda.txt

O posts.json é do painel:

    {"formato": "feed", "prints": {"feed": 2, "stories": 3}, "fonte": "inter", "destaque": null,
     "modo": "unico", "pb": false, "assinatura": false,
     "escolhidas": ["frase-003", "minha-1"],                    (a ordem é a dos slides)
     "minhas": [{"id": "minha-1", "partes": {"2": ["…", "…"]}, "referencia": "Salmos 23:1"}],
     "edicoes": {"frase-003": {"partes": {"2": ["…", "…"]}, "prints": {"2": ["p-0004", "f-0001"]},
                               "ajustes": {"feed-2": [{"zoom": 1.2, "x": 0, "y": 0.05}, {}]},
                               "referencia": "", "legenda": null}},
     "capa": {"usar": null, "texto": null, "print": null, "ajuste": {"zoom": 1, "x": 0, "y": 0}},
     "legenda_carrossel": null}

A edição vale por número de prints (o texto dividido em 2 não é o dividido em 3); o
ajuste do recorte, por formato e número (o print de 1080×675 não é o de 1080×640).
`null` é "o que o Claude escreveu" (a legenda, o título da capa); `capa.usar` null liga a
capa quando o Claude escreveu um título. O carrossel é só no feed: escolher o carrossel
volta o formato para o feed, e escolher os stories volta para o post único.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import arte as A
import frases as F
import prints as P

RAIZ = Path(__file__).resolve().parents[4]
MARCA = RAIZ / "minha-biblioteca" / "marca"
RE_PRINT = re.compile(r"[pf]-\d{4,6}")              # p-: do vídeo; f-: foto que a pessoa subiu
RE_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
RE_ARROBA = re.compile(r"[A-Za-z0-9._]{1,30}")
MAX_MINHAS = 60
MODOS = {"unico": "Post único", "carrossel": "Carrossel"}
SLIDES_MAX = 20                  # o Instagram aceita até 20 fotos num carrossel


def pasta(proj: Path) -> Path:
    return Path(proj) / "posts"


def _ler(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def video_do_projeto(proj: Path) -> Path | None:
    v = (_ler(Path(proj) / "projeto.json", {}) or {}).get("video") or ""
    return Path(v).expanduser() if v else None


def achar_transcricao(proj: Path) -> Path | None:
    """A dos posts (./topclip post transcrever) ou a da run de cortes mais recente."""
    proj = Path(proj)
    propria = pasta(proj) / "transcricao.json"
    if propria.is_file():
        return propria
    runs = sorted(proj.glob("runs/*/02-transcript.json"), key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None


def ler_frases(proj: Path) -> tuple[list[dict], list[str], str | None]:
    """(frases, avisos, erro) do frases.json do Claude. Sem o arquivo: lista vazia."""
    arq = pasta(proj) / "frases.json"
    if not arq.is_file():
        return [], [], None
    doc = _ler(arq)
    if doc is None:
        return [], [], "o frases.json não é um JSON válido"
    try:
        frases, avisos = F.conferir(doc)
        return frases, avisos, None
    except F.ErroFrases as e:
        return [], [], str(e)


def ler_prints(proj: Path) -> dict:
    return P.ler(pasta(proj))


def ler_carrossel(proj: Path) -> dict:
    """O `carrossel` que o Claude escreveu no frases.json: {"capa": …, "legenda": …}."""
    return F.carrossel(_ler(pasta(proj) / "frases.json", {}))


def arroba() -> str | None:
    """O @ da marca da pessoa (Biblioteca → Minha marca), como "@perfil". Aceita o que ela
    digitou: "perfil", "@perfil" ou o link do Instagram."""
    bruto = str((_ler(MARCA / "marca.json", {}) or {}).get("arroba") or "").strip()
    bruto = bruto.rstrip("/").rsplit("/", 1)[-1].split("?")[0].lstrip("@").strip()
    return f"@{bruto}" if RE_ARROBA.fullmatch(bruto) else None


# ------------------------------------------------------------------ fontes
def fonte_da_marca() -> dict | None:
    """A fonte da marca da pessoa (Biblioteca → Minha marca), como família da arte."""
    m = _ler(MARCA / "marca.json", {}) or {}
    fontes = m.get("fontes") if isinstance(m.get("fontes"), dict) else {}
    valor = fontes.get("texto") or fontes.get("titulo")
    if not valor:
        return None
    do_kit = {v["nome"]: v for v in A.FONTES.values()}
    if valor in do_kit:
        fam = dict(do_kit[valor])
    else:
        arq = MARCA / str(valor)
        if not arq.is_file() or arq.suffix.lower() not in (".ttf", ".otf"):
            return None
        fam = {"arquivo": str(arq.resolve()), "regular": {"wght": 400}, "negrito": {"wght": 700}}
    fam["nome"] = f"Da minha marca ({valor})"
    return fam


def fontes() -> list[dict]:
    """As famílias para escolher. A da marca entra como opção própria só se não for uma da
    lista (marca em Inter = a Inter, com a etiqueta "da sua marca")."""
    lista = [{"id": k, "nome": v["nome"], "arquivo": v["arquivo"]} for k, v in A.fontes_disponiveis().items()]
    marca = fonte_da_marca()
    if marca:
        igual = next((f for f in lista if f["arquivo"] == marca["arquivo"]), None)
        if igual:
            igual["marca"] = True
        else:
            lista.append({"id": "marca", "nome": marca["nome"], "arquivo": marca["arquivo"], "marca": True})
    return lista


def familia(fonte_id: str):
    if fonte_id == "marca":
        return fonte_da_marca() or A.PADRAO["fonte"]
    return fonte_id


# ------------------------------------------------------------------ o estado do painel
def estado_padrao() -> dict:
    return {"formato": A.PADRAO["formato"], "prints": dict(A.PADRAO["prints"]), "fonte": A.PADRAO["fonte"],
            "destaque": None, "modo": "unico", "pb": False, "assinatura": False,
            "escolhidas": [], "minhas": [], "edicoes": {},
            "capa": {"usar": None, "texto": None, "print": None, "ajuste": _ajuste({})},
            "legenda_carrossel": None}


def ler_estado(proj: Path) -> dict:
    est = estado_padrao()
    salvo = _ler(pasta(proj) / "posts.json", {})
    if isinstance(salvo, dict):
        try:
            est = _validar(salvo, est)
        except ValueError:
            pass
    return est


def _texto(v, limite=300) -> str:
    return str(v or "").replace("\n", " ").strip()[:limite]


def _legenda(v) -> str | None:
    """A legenda como a pessoa escreveu (com as quebras de linha); None é "a do Claude"."""
    if v is None:
        return None
    t = str(v).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(t) > F.LEGENDA_MAX:
        raise ValueError(f"A legenda passou de {F.LEGENDA_MAX} letras, o limite do Instagram.")
    return t


def _partes(v) -> dict:
    saida = {}
    if isinstance(v, dict):
        for k, lista in v.items():
            if str(k) in ("1", "2", "3") and isinstance(lista, list) and len(lista) == int(k):
                saida[str(k)] = [_texto(p) for p in lista]
    return saida


def _validar(dados: dict, atual: dict) -> dict:
    """Mistura `dados` (o que o painel mandou) em `atual`, conferindo cada campo."""
    est = json.loads(json.dumps(atual))
    if dados.get("formato") == "stories" and dados.get("modo") == "carrossel":
        raise ValueError("O carrossel é só no feed.")
    if "formato" in dados:
        if dados["formato"] not in A.FORMATOS:
            raise ValueError("Formato precisa ser feed ou stories.")
        est["formato"] = dados["formato"]
        if est["formato"] == "stories":
            est["modo"] = "unico"                 # stories não tem carrossel
    if "modo" in dados:
        if dados["modo"] not in MODOS:
            raise ValueError("O modo precisa ser post único ou carrossel.")
        est["modo"] = dados["modo"]
        if est["modo"] == "carrossel":
            est["formato"] = "feed"
    for chave in ("pb", "assinatura"):
        if chave in dados:
            if not isinstance(dados[chave], bool):
                raise ValueError(f"{chave} precisa ser sim ou não.")
            est[chave] = dados[chave]
    if "capa" in dados:
        c = dados["capa"]
        if not isinstance(c, dict):
            raise ValueError("Capa inválida.")
        capa = est["capa"]
        if "usar" in c:
            if c["usar"] is not None and not isinstance(c["usar"], bool):
                raise ValueError("Capa inválida.")
            capa["usar"] = c["usar"]
        if "texto" in c:
            t = None if c["texto"] is None else _texto(c["texto"], 160)
            if t and t.count("**") % 2:
                raise ValueError("O negrito do título da capa ficou aberto.")
            capa["texto"] = t
        if "print" in c:
            if c["print"] is not None and not (isinstance(c["print"], str) and RE_PRINT.fullmatch(c["print"])):
                raise ValueError("Print da capa inválido.")
            if c["print"] != capa.get("print"):
                capa["ajuste"] = _ajuste({})      # print novo: o recorte do antigo não serve
            capa["print"] = c["print"]
        if "ajuste" in c:
            capa["ajuste"] = _ajuste(c["ajuste"])
    if "legenda_carrossel" in dados:
        est["legenda_carrossel"] = _legenda(dados["legenda_carrossel"])
    if "prints" in dados:
        p = dados["prints"]
        if isinstance(p, int):
            p = {est["formato"]: p}
        if not isinstance(p, dict):
            raise ValueError("Número de prints inválido.")
        for k, v in p.items():
            if k not in A.FORMATOS or v not in F.PRINTS:
                raise ValueError("O post tem 1, 2 ou 3 prints.")
            est["prints"][k] = int(v)
    if "fonte" in dados:
        validas = {f["id"] for f in fontes()}
        if dados["fonte"] not in validas:
            raise ValueError("Essa fonte não está disponível.")
        est["fonte"] = dados["fonte"]
    if "destaque" in dados:
        d = dados["destaque"]
        if d is not None and not (isinstance(d, str) and RE_HEX.fullmatch(d)):
            raise ValueError("A cor do destaque precisa ser #RRGGBB.")
        est["destaque"] = d.upper() if d else None
    if "escolhidas" in dados:
        if not isinstance(dados["escolhidas"], list):
            raise ValueError("Lista de frases inválida.")
        est["escolhidas"] = list(dict.fromkeys(str(x) for x in dados["escolhidas"] if F.RE_ID.fullmatch(str(x))))
    if "minhas" in dados:
        if not isinstance(dados["minhas"], list) or len(dados["minhas"]) > MAX_MINHAS:
            raise ValueError(f"Até {MAX_MINHAS} frases suas por projeto.")
        minhas = []
        for m in dados["minhas"]:
            if not isinstance(m, dict) or not re.fullmatch(r"minha-\d{1,4}", str(m.get("id", ""))):
                raise ValueError("Frase sua com id inválido.")
            minhas.append({"id": m["id"], "partes": _partes(m.get("partes")), "referencia": _texto(m.get("referencia"), 80)})
        est["minhas"] = minhas
    if "edicoes" in dados:
        if not isinstance(dados["edicoes"], dict):
            raise ValueError("Edição inválida.")
        for fid, ed in dados["edicoes"].items():
            if not F.RE_ID.fullmatch(str(fid)):
                continue
            if ed is None:
                est["edicoes"].pop(fid, None)
                continue
            if not isinstance(ed, dict):
                raise ValueError("Edição inválida.")
            limpa = {"partes": _partes(ed.get("partes")), "prints": {}, "ajustes": {},
                     "referencia": _texto(ed.get("referencia"), 80), "legenda": _legenda(ed.get("legenda"))}
            for k, lista in (ed.get("prints") or {}).items():
                if str(k) in ("1", "2", "3") and isinstance(lista, list) and len(lista) == int(k) \
                        and all(isinstance(x, str) and RE_PRINT.fullmatch(x) for x in lista):
                    limpa["prints"][str(k)] = lista
            for k, lista in (ed.get("ajustes") or {}).items():
                fmt, _, n = str(k).partition("-")
                if fmt in A.FORMATOS and n in ("1", "2", "3") and isinstance(lista, list) and len(lista) == int(n):
                    limpa["ajustes"][k] = [_ajuste(a) for a in lista]
            est["edicoes"][fid] = limpa
    return est


def _ajuste(a) -> dict:
    a = a if isinstance(a, dict) else {}
    num = lambda v, lo, hi, padrao: min(hi, max(lo, float(v))) if isinstance(v, (int, float)) else padrao
    return {"zoom": num(a.get("zoom"), 0.5, 3.0, 1.0), "x": num(a.get("x"), -1.0, 1.0, 0.0), "y": num(a.get("y"), -1.0, 1.0, 0.0)}


def salvar_estado(proj: Path, dados: dict) -> dict:
    est = _validar(dados if isinstance(dados, dict) else {}, ler_estado(proj))
    if est["assinatura"] and "assinatura" in (dados or {}) and not arroba():
        raise ValueError("Cadastre o seu @ em Biblioteca → Minha marca para assinar os posts.")
    est["atualizado"] = datetime.now().isoformat(timespec="seconds")
    pasta(proj).mkdir(parents=True, exist_ok=True)
    (pasta(proj) / "posts.json").write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    return est


# ------------------------------------------------------------------ montar a arte
def todas_as_frases(proj: Path, estado: dict | None = None) -> list[dict]:
    """As do Claude e, depois, as da pessoa (com "minha": True)."""
    estado = estado or ler_estado(proj)
    frases, _, _ = ler_frases(proj)
    return frases + [{**m, "minha": True} for m in estado["minhas"]]


def achar_frase(proj: Path, fid: str, estado: dict | None = None) -> dict | None:
    return next((f for f in todas_as_frases(proj, estado) if f["id"] == fid), None)


def prints_da_frase(doc: dict, frase: dict, n: int, estado: dict) -> list[str]:
    """Os prints que valem: os que a pessoa trocou, senão a escolha automática, senão o banco."""
    ed = estado["edicoes"].get(frase["id"]) or {}
    quadros = doc.get("quadros") or {}
    trocados = (ed.get("prints") or {}).get(str(n))
    if trocados and all(p in quadros for p in trocados):
        return trocados
    auto = (((doc.get("frases") or {}).get(frase["id"]) or {}).get("auto") or {}).get(str(n))
    if auto and all(p in quadros for p in auto):
        return auto
    minhas = [m["id"] for m in estado["minhas"]]
    pos = minhas.index(frase["id"]) if frase["id"] in minhas else len(frase["id"])
    return P.do_banco(doc, n, pos)


def montagem(proj: Path, frase: dict, estado: dict, doc: dict | None = None) -> dict:
    """Tudo o que a arte de uma frase precisa, no formato e número de prints do estado."""
    doc = doc if doc is not None else ler_prints(proj)
    fmt = estado["formato"]
    n = estado["prints"][fmt]
    ed = estado["edicoes"].get(frase["id"]) or {}
    partes = (ed.get("partes") or {}).get(str(n)) or F.partes_para(frase, n)
    pids = prints_da_frase(doc, frase, n, estado)
    ajustes = (ed.get("ajustes") or {}).get(f"{fmt}-{n}") or [{}] * n
    quadros = doc.get("quadros") or {}
    paineis = []
    for i in range(n):
        q = quadros.get(pids[i]) if i < len(pids) else None
        aj = ajustes[i] if i < len(ajustes) else {}
        paineis.append({"imagem": str(pasta(proj) / q["arquivo"]) if q else None, "rosto": q["rosto"] if q else None,
                        "texto": partes[i] if i < len(partes) else "", "print": pids[i] if i < len(pids) else None,
                        "zoom": aj.get("zoom", 1.0), "x": aj.get("x", 0.0), "y": aj.get("y", 0.0)})
    referencia = ed.get("referencia") if "referencia" in ed else frase.get("referencia", "")
    return {"formato": fmt, "n": n, "paineis": paineis, "partes": partes, "prints": pids,
            "referencia": referencia or "", **_visual(estado), "legenda": legenda_da_frase(frase, estado)}


def _visual(estado: dict) -> dict:
    """O que vale para todos os posts: fonte, destaque, P&B e a assinatura (o @ da marca)."""
    return {"fonte": estado["fonte"], "destaque": estado["destaque"], "pb": bool(estado.get("pb")),
            "assinatura": (arroba() or "") if estado.get("assinatura") else ""}


def legenda_da_frase(frase: dict, estado: dict) -> str:
    """A legenda do post: a que a pessoa editou, senão a que o Claude escreveu."""
    ed = estado["edicoes"].get(frase["id"]) or {}
    if ed.get("legenda") is not None:
        return ed["legenda"]
    return str(frase.get("legenda") or "").strip()


def _arte(m: dict, escala: float, capa=False):
    return A.montar(m["paineis"], formato=m["formato"], fonte=familia(m["fonte"]), destaque=m["destaque"],
                    referencia=m.get("referencia", ""), escala=escala, pb=m["pb"], assinatura=m["assinatura"], capa=capa)


def renderizar(proj: Path, frase: dict, estado: dict, escala: float = 1.0, doc: dict | None = None):
    return _arte(montagem(proj, frase, estado, doc), escala)


# ------------------------------------------------------------------ o carrossel
def carrossel_do_projeto(proj: Path, estado: dict, doc: dict | None = None) -> dict:
    """A capa e a legenda do carrossel, já resolvidas (o que a pessoa mudou, senão o do Claude)."""
    doc = doc if doc is not None else ler_prints(proj)
    claude = ler_carrossel(proj)
    capa = estado["capa"]
    quadros = doc.get("quadros") or {}
    texto = capa["texto"] if capa.get("texto") is not None else claude.get("capa", "")
    usar = capa["usar"] if capa.get("usar") is not None else bool(claude.get("capa"))
    pid = capa.get("print") if capa.get("print") in quadros else None
    if not pid:                                   # o melhor rosto do vídeo; sem banco, o 1º print do 1º slide
        banco = [p for p in doc.get("banco") or [] if p in quadros]
        todas = {f["id"]: f for f in todas_as_frases(proj, estado)}
        primeira = next((todas[i] for i in estado["escolhidas"] if i in todas), None)
        pid = banco[0] if banco else ((prints_da_frase(doc, primeira, 1, estado) or [None])[0] if primeira else None)
    legenda = estado["legenda_carrossel"]
    if legenda is None:
        legenda = claude.get("legenda", "")
    return {"usar": usar, "texto": texto, "print": pid, "ajuste": capa.get("ajuste") or _ajuste({}),
            "legenda": legenda, "capa_claude": claude.get("capa", ""), "legenda_claude": claude.get("legenda", "")}


def montagem_capa(proj: Path, estado: dict, doc: dict | None = None) -> dict:
    doc = doc if doc is not None else ler_prints(proj)
    c = carrossel_do_projeto(proj, estado, doc)
    q = (doc.get("quadros") or {}).get(c["print"]) if c["print"] else None
    aj = c["ajuste"]
    painel = {"imagem": str(pasta(proj) / q["arquivo"]) if q else None, "rosto": q["rosto"] if q else None,
              "texto": c["texto"], "print": c["print"], "zoom": aj["zoom"], "x": aj["x"], "y": aj["y"]}
    return {"formato": "feed", "n": 1, "paineis": [painel], **_visual(estado)}


def renderizar_capa(proj: Path, estado: dict, escala: float = 1.0, doc: dict | None = None):
    return _arte(montagem_capa(proj, estado, doc), escala, capa=True)


def nome_do_arquivo(frase: dict, estado: dict, ordem: int | None = None) -> str:
    texto = F.limpo(" ".join(F.partes_para(frase, 2)))
    import unicodedata
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40].rstrip("-") or frase["id"]
    pre = f"{ordem:02d}-" if ordem is not None else ""
    return f"{pre}{s}-{estado['formato']}.png"


def exportar(proj: Path, ids: list[str] | None = None, estado: dict | None = None) -> list[Path]:
    """Grava os PNG finais em posts/prontos/: os escolhidos no painel, ou os `ids` pedidos.
    As legendas vão juntas, em legendas.txt (o nome de cada PNG e a legenda dele)."""
    estado = estado or ler_estado(proj)
    doc = ler_prints(proj)
    todas = {f["id"]: f for f in todas_as_frases(proj, estado)}
    ids = [i for i in (ids or estado["escolhidas"]) if i in todas]
    saida = pasta(proj) / "prontos"
    saida.mkdir(parents=True, exist_ok=True)
    feitos, legendas = [], []
    for k, fid in enumerate(ids, 1):
        destino = saida / nome_do_arquivo(todas[fid], estado, k)
        renderizar(proj, todas[fid], estado, 1.0, doc).save(destino, optimize=True)
        feitos.append(destino)
        leg = legenda_da_frase(todas[fid], estado)
        if leg:
            legendas.append(f"{destino.name}\n\n{leg}")
    if legendas:
        (saida / "legendas.txt").write_text(("\n\n" + "-" * 40 + "\n\n").join(legendas) + "\n", encoding="utf-8")
    else:
        (saida / "legendas.txt").unlink(missing_ok=True)      # a de uma exportação anterior não vale mais
    return feitos


def exportar_carrossel(proj: Path, ids: list[str] | None = None, estado: dict | None = None) -> list[Path]:
    """Os slides do carrossel em posts/prontos/carrossel/, numerados na ordem: a capa (se
    ligada) e as frases na ordem escolhida. A legenda do carrossel vai em legenda.txt."""
    estado = estado or ler_estado(proj)
    estado = {**estado, "formato": "feed"}
    doc = ler_prints(proj)
    todas = {f["id"]: f for f in todas_as_frases(proj, estado)}
    ids = [i for i in (ids or estado["escolhidas"]) if i in todas]
    if not ids:
        raise ValueError("Escolha pelo menos uma frase para o carrossel.")
    saida = pasta(proj) / "prontos" / "carrossel"
    saida.mkdir(parents=True, exist_ok=True)
    for velho in [*saida.glob("*.png"), saida / "legenda.txt"]:   # a ordem mudou: os números antigos confundiriam
        velho.unlink(missing_ok=True)
    c = carrossel_do_projeto(proj, estado, doc)
    feitos = []
    if c["usar"]:
        destino = saida / "01-capa.png"
        renderizar_capa(proj, estado, 1.0, doc).save(destino, optimize=True)
        feitos.append(destino)
    for fid in ids:
        destino = saida / nome_do_arquivo(todas[fid], estado, len(feitos) + 1).replace("-feed.png", ".png")
        renderizar(proj, todas[fid], estado, 1.0, doc).save(destino, optimize=True)
        feitos.append(destino)
    if c["legenda"]:
        (saida / "legenda.txt").write_text(c["legenda"] + "\n", encoding="utf-8")
    return feitos
