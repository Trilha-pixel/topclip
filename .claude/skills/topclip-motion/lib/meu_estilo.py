#!/usr/bin/env python3
"""
O estilo do usuario: remixar, ajustar, aprovar, exportar, importar e apagar, mais as
duas ferramentas da criacao com o Claude — a paleta tirada de imagens e a amostra num
quadro do clipe da propria pessoa. Tudo grava em `minha-biblioteca/estilos/` (fora do
git); estilo oficial nunca e editado.

    ./topclip estilo remixar limpo meu-estilo --nome "Meu estilo"
    ./topclip estilo ajustar meu-estilo cor.acento=#FF5A1F fonte.titulo="Archivo Black"
    ./topclip estilo paleta print1.png print2.png
    ./topclip estilo amostra limpo impacto meu-estilo --video clipe.mp4 --t 12.5
    ./topclip estilo aprovar meu-estilo
    ./topclip estilo exportar meu-estilo
    ./topclip estilo importar meu-estilo.topclip-estilo
    ./topclip estilo apagar meu-estilo

Ciclo de versao: o remix nasce rascunho (0.1.0); cada `ajustar` sobe o ultimo numero; o
`aprovar` valida, renderiza todas as pecas na galeria e leva a 1.0.0 (depois, 1.1.0,
1.2.0...). Cada clipe grava no `estilo/resolvido.json` a versao que usou.
"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import estilo as E


class ErroEstilo(ValueError):
    """Erro de uso que a pessoa resolve (id repetido, chave errada, pacote invalido)."""


EXTENSAO = ".topclip-estilo"
# o que um pacote compartilhado pode trazer: dados, imagem, fonte, video da demo. Codigo nao.
PERMITIDOS = {".json", ".md", ".txt", ".png", ".jpg", ".jpeg", ".ttf", ".otf", ".mp4"}
MAX_ARQUIVOS = 400
MAX_BYTES = 25 * 1024 * 1024


# ---------------------------------------------------------------- onde

# A pasta do usuario. None = <raiz>/minha-biblioteca; o painel aponta para a dele (que
# os testes do painel trocam por uma temporaria).
MINHA = None


def minha_biblioteca(raiz):
    return Path(MINHA) if MINHA else Path(raiz) / "minha-biblioteca"


def minha(raiz):
    return minha_biblioteca(raiz) / "estilos"


def oficiais(raiz):
    return Path(raiz) / "biblioteca" / "estilos"


def acha(alvo, raiz):
    """Id (oficial primeiro, depois os seus) ou pasta de um pacote. Sem derrubar o
    processo, como o `estilo.achar` faria: o painel chama daqui."""
    p = Path(alvo)
    if p.is_dir() and (p / "estilo.json").is_file():
        return p.resolve()
    for base in (oficiais(raiz), minha(raiz)):
        if E.RE_ID.match(str(alvo)) and (base / alvo / "estilo.json").is_file():
            return (base / alvo).resolve()
    raise ErroEstilo(f"estilo '{alvo}' não encontrado (./topclip estilo listar)")


def _do_usuario(alvo, raiz):
    p = acha(alvo, raiz)
    if minha(raiz).resolve() not in p.resolve().parents:
        raise ErroEstilo(f"'{p.name}' é um estilo oficial: faça o seu a partir dele "
                         f"(./topclip estilo remixar {p.name} <novo-id>)")
    return p


def _le(pasta):
    return {n: json.loads((pasta / f"{n}.json").read_text(encoding="utf-8"))
            for n in ("estilo", "tokens", "legenda")}


def _grava(pasta, d):
    for n, v in d.items():
        (pasta / f"{n}.json").write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")


def _versao(v, parte):
    a, b, c = (int(x) for x in v.split("."))
    return {"patch": f"{a}.{b}.{c + 1}", "minor": f"{a}.{b + 1}.0", "major": f"{a + 1}.0.0"}[parte]


# ---------------------------------------------------------------- remixar

def remixar(raiz, base, novo_id, nome=None, autor=None):
    """Copia `base` (oficial ou seu) para minha-biblioteca/estilos/<novo_id>, como rascunho."""
    origem = acha(base, raiz)
    if not E.RE_ID.match(novo_id or ""):
        raise ErroEstilo(f"nome curto '{novo_id}' inválido: use minúsculas, números e hífen, de 2 a 31 letras")
    if (oficiais(raiz) / novo_id).exists():
        raise ErroEstilo(f"'{novo_id}' é o nome de um estilo oficial: escolha outro")
    dest = minha(raiz) / novo_id
    if dest.exists():
        raise ErroEstilo(f"você já tem um estilo '{novo_id}'")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(origem, dest, ignore=shutil.ignore_patterns("__pycache__", ".*"))
    d = _le(dest)
    est = d["estilo"]
    base_id, base_nome, base_versao = est["id"], est["nome"], est["versao"]
    est.update(id=novo_id, nome=nome or f"{base_nome} (meu)", origem="meu", versao="0.1.0",
               autor=autor or "você", remix_de=f"{base_id}@{base_versao}",
               descricao=f"Remix do {base_nome}. {est.get('descricao', '')}".strip())
    _grava(dest, d)
    return dest


# ---------------------------------------------------------------- ajustar

def _valor(txt):
    """'#FF5A1F' fica texto; '380', 'true', 'null', '[0, 0.07]' viram o que sao em JSON."""
    if not isinstance(txt, str):
        return txt
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return txt


def _lista(v):
    return v if isinstance(v, list) else [x.strip() for x in str(v).split(",") if x.strip()]


def _aplica(d, chave, valor):
    est, tok, leg = d["estilo"], d["tokens"], d["legenda"]
    ext = tok.setdefault("$extensions", {}).setdefault("topclip", {})
    if chave.startswith(("cor.", "fonte.")):
        grupo, nome = chave.split(".", 1)
        folha = tok.setdefault(grupo, {}).setdefault(nome, {})
        folha["$type"] = "color" if grupo == "cor" else "fontFamily"
        if valor is None:
            tok[grupo].pop(nome)
        else:
            folha["$value"] = valor
    elif chave in ("energia", "movimento.perfil"):
        est["energia"] = valor
        tok.setdefault("movimento", {})["perfil"] = valor
    elif chave.startswith("movimento."):
        ajustes = tok.setdefault("movimento", {}).setdefault("ajustes", {})
        if valor is None:
            ajustes.pop(chave[10:], None)
        else:
            ajustes[chave[10:]] = valor
    elif chave.startswith("tipografia."):
        no = ext.setdefault("tipografia", {})
        *caminho, ultimo = chave.split(".")[1:]
        for p in caminho:
            no = no.setdefault(p, {})
        if valor is None:
            no.pop(ultimo, None)
        else:
            no[ultimo] = valor
    elif chave.startswith("acabamento."):
        ext.setdefault("acabamento", {})[chave[11:]] = valor
    elif chave in ("traco", "boil"):
        ext[chave] = valor
    elif chave.startswith("legenda."):
        if valor is None:
            leg.pop(chave[8:], None)
        else:
            leg[chave[8:]] = valor
    elif chave.startswith("variacao."):
        partes = chave.split(".", 2)
        if len(partes) == 2:                       # variacao.<v>=null apaga a variacao
            if valor is not None:
                raise ErroEstilo("use variacao.<id>.nome=... ou variacao.<id>.cor.<nome>=#RRGGBB")
            est["variacoes"].pop(partes[1], None)
            return
        _, vid, resto = partes
        var = est["variacoes"].setdefault(vid, {"nome": vid.capitalize(), "tokens": {}})
        if resto == "nome":
            var["nome"] = str(valor)
        elif valor is None:
            var.setdefault("tokens", {}).pop(resto, None)
        else:
            var.setdefault("tokens", {})[resto] = valor
    elif chave in ("nome", "descricao", "licenca", "autor"):
        est[chave] = str(valor)
    elif chave in ("bom_para", "slots_da_marca", "pecas"):
        est[chave] = _lista(valor)
    elif chave == "cenas":
        est["cenas"] = valor
    else:
        raise ErroEstilo(f"chave desconhecida: '{chave}'. Use cor.*, fonte.*, energia, "
                         "movimento.*, tipografia.*, acabamento.*, traco, boil, legenda.*, "
                         "variacao.*, nome, descricao, bom_para, slots_da_marca ou pecas")


def ajustar(raiz, alvo, pares):
    """
    Aplica `pares` ("chave=valor" ou dict) no seu estilo, valida e grava. Com qualquer erro
    nada muda. Sobe o ultimo numero da versao. Devolve (versao, avisos).
    """
    pasta = _do_usuario(alvo, raiz)
    if isinstance(pares, dict):
        itens = list(pares.items())
    else:
        itens = []
        for p in pares:
            if "=" not in p:
                raise ErroEstilo(f"'{p}': use chave=valor")
            k, v = p.split("=", 1)
            itens.append((k.strip(), _valor(v.strip())))
    original = _le(pasta)
    d = json.loads(json.dumps(original))
    for k, v in itens:
        _aplica(d, k, v)
    d["estilo"]["versao"] = _versao(d["estilo"]["versao"], "patch")
    _grava(pasta, d)
    erros, avisos = E.validar(pasta, exigir_previa=False)
    if erros:
        _grava(pasta, original)
        raise ErroEstilo("nada mudou:\n  " + "\n  ".join(erros))
    return d["estilo"]["versao"], avisos


# ---------------------------------------------------------------- aprovar

def aprovar(raiz, alvo, cena=None):
    """Valida, renderiza a galeria (todas as pecas, todas as variacoes) e fecha a versao:
    rascunho 0.x vira 1.0.0; estilo ja aprovado sobe o numero do meio."""
    pasta = _do_usuario(alvo, raiz)
    erros, _ = E.validar(pasta, exigir_previa=False)
    if erros:
        raise ErroEstilo("corrija antes de aprovar:\n  " + "\n  ".join(erros))
    E.previa(pasta, raiz, cena)
    erros, avisos = E.validar(pasta)
    if erros:
        raise ErroEstilo("a galeria saiu, mas o pacote ainda tem erro:\n  " + "\n  ".join(erros))
    d = _le(pasta)
    v = d["estilo"]["versao"]
    d["estilo"]["versao"] = "1.0.0" if v.startswith("0.") else _versao(v, "minor")
    _grava(pasta, d)
    return d["estilo"]["versao"], avisos


# ---------------------------------------------------------------- exportar e importar

def exportar(raiz, alvo, destino=None):
    """
    `<id>.topclip-estilo`: um zip com o pacote SEM codigo e sem a marca (a marca nunca fica
    no pacote). Cenas de estilo overlay continuam: quem importa recebe o compose modelo
    das pecas. Devolve o caminho do arquivo.
    """
    pasta = acha(alvo, raiz)
    erros, _ = E.validar(pasta)
    if erros:
        raise ErroEstilo("o estilo tem um problema e não sai assim:\n  " + "\n  ".join(erros)
                         + f"\n(aprove primeiro: ./topclip estilo aprovar {pasta.name})")
    destino = Path(destino) if destino else Path.cwd()
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{pasta.name}{EXTENSAO}"
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pasta.rglob("*")):
            rel = f.relative_to(pasta)
            if (not f.is_file() or any(p.startswith(".") or p == "__pycache__" for p in rel.parts)
                    or f.suffix.lower() not in PERMITIDOS):
                continue
            if rel.as_posix() == "estilo.json":
                est = json.loads(f.read_text(encoding="utf-8"))
                est.update(codigo=False, origem="comunidade")
                z.writestr(f"{pasta.name}/estilo.json",
                           json.dumps(est, ensure_ascii=False, indent=2) + "\n")
            else:
                z.write(f, f"{pasta.name}/{rel.as_posix()}")
    return arquivo


def _confere_zip(z):
    infos = z.infolist()
    if len(infos) > MAX_ARQUIVOS:
        raise ErroEstilo(f"o arquivo tem {len(infos)} itens (máximo {MAX_ARQUIVOS})")
    if sum(i.file_size for i in infos) > MAX_BYTES:
        raise ErroEstilo("o arquivo descompactado passa de 25 MB")
    topos = set()
    for i in infos:
        nome = i.filename
        partes = nome.split("/")
        if nome.startswith("/") or "\\" in nome or ".." in partes or ":" in partes[0]:
            raise ErroEstilo(f"caminho perigoso dentro do arquivo: {nome}")
        if (i.external_attr >> 16) & 0o170000 == 0o120000:
            raise ErroEstilo(f"atalho (link) dentro do arquivo: {nome}")
        topos.add(partes[0])
        if not nome.endswith("/") and Path(nome).suffix.lower() not in PERMITIDOS:
            raise ErroEstilo(f"'{nome}' não pode entrar: estilo compartilhado só traz dados, "
                             f"imagens e fontes (nada de código)")
    if len(topos) != 1:
        raise ErroEstilo("o arquivo precisa ter uma pasta só, com o nome do estilo")
    return topos.pop()


def importar(raiz, arquivo, substituir=False):
    """Confere e instala um `.topclip-estilo` em minha-biblioteca/estilos/. O estilo entra
    como "comunidade": sem codigo, validado como qualquer pacote. Devolve a pasta."""
    arquivo = Path(arquivo)
    try:
        z = zipfile.ZipFile(arquivo)
    except zipfile.BadZipFile:
        raise ErroEstilo(f"{arquivo.name} não é um estilo do TopClip (zip inválido)") from None
    with z, tempfile.TemporaryDirectory(prefix="topclip-importar-") as tmp:
        eid = _confere_zip(z)
        for i in z.infolist():
            if i.filename.endswith("/"):
                continue
            alvo = Path(tmp) / i.filename
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(i))
        pasta = Path(tmp) / eid
        if not (pasta / "estilo.json").is_file():
            raise ErroEstilo("o arquivo não tem o estilo.json na pasta do estilo")
        d = _le(pasta)
        d["estilo"].update(origem="comunidade", codigo=False)
        _grava(pasta, d)
        erros, _ = E.validar(pasta)
        if erros:
            raise ErroEstilo("estilo com problema:\n  " + "\n  ".join(erros))
        if (oficiais(raiz) / eid).exists():
            raise ErroEstilo(f"'{eid}' tem o nome de um estilo oficial e não pode entrar")
        dest = minha(raiz) / eid
        if dest.exists():
            if not substituir:
                raise ErroEstilo(f"você já tem um estilo '{eid}' (use --substituir para trocar)")
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(pasta, dest)
    return dest


def apagar(raiz, alvo):
    """Apaga um estilo seu. Se era o seu padrao, o padrao volta a ser o Papel."""
    pasta = _do_usuario(alvo, raiz)
    shutil.rmtree(pasta)
    pref = minha_biblioteca(raiz) / "preferencias.json"
    if pref.is_file():
        try:
            p = json.loads(pref.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            p = {}
        if p.get("estilo") == pasta.name:
            pref.unlink()
    return pasta.name


# ---------------------------------------------------------------- paleta

def paleta(imagens, n=6):
    """
    As cores dominantes de prints, logo ou fotos da marca (k-means em Lab, local e gratis)
    e uma sugestao de fundo, texto e acento com contraste conferido.
    """
    import cv2
    import numpy as np
    amostras = []
    for f in imagens:
        im = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if im is None:
            raise ErroEstilo(f"não consegui abrir {f}")
        k = 160 / max(im.shape[:2])
        if k < 1:
            im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        amostras.append(cv2.cvtColor(im, cv2.COLOR_BGR2LAB).reshape(-1, 3))
    dados = np.concatenate(amostras).astype(np.float32)
    n = max(2, min(n, len(dados)))
    criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(7)
    _, rotulos, centros = cv2.kmeans(dados, n, None, criterio, 4, cv2.KMEANS_PP_CENTERS)
    contagem = np.bincount(rotulos.ravel(), minlength=n)
    bgr = cv2.cvtColor(centros.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3)
    cores = []
    for i in np.argsort(-contagem):
        b, g, r = (int(x) for x in bgr[i])
        cores.append(("#%02X%02X%02X" % (r, g, b), round(100 * contagem[i] / contagem.sum(), 1)))

    def croma(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return max(r, g, b) - min(r, g, b)

    fundo = cores[0][0]
    texto = max(["#111111", "#FFFFFF"] + [c for c, _ in cores], key=lambda c: E.contraste(c, fundo))
    # acento e a cor VIVA da marca (preto e cinza nao sao acento), de preferencia com 3:1
    # contra o fundo; sem nenhuma que chegue la, a mais viva mesmo, e o contraste avisa
    resto = [c for c, _ in cores[1:] if c != texto]
    vivas = [c for c in resto if croma(c) >= 0.25] or resto
    boas = [c for c in vivas if E.contraste(c, fundo) >= 3]
    acento = max(boas or vivas or [texto], key=croma)
    return {"cores": cores, "sugestao": {"fundo": fundo, "texto": texto, "acento": acento},
            "contraste": {"texto": round(E.contraste(texto, fundo), 1),
                          "acento": round(E.contraste(acento, fundo), 1)}}


# ---------------------------------------------------------------- amostra no clipe

def amostra(raiz, alvos, video, t, saida, texto=None, legenda=None):
    """
    Um quadro do clipe da propria pessoa em cada estilo de `alvos` ("id" ou "id:variacao"):
    o video no instante `t`, uma frase sobre ele (no terco de cima) e a legenda do estilo.
    Com varios alvos, sai uma folha lado a lado — as "direcoes" da criacao com o Claude.
    """
    from PIL import Image, ImageDraw, ImageFont
    raiz, video, saida = Path(raiz), Path(video).resolve(), Path(saida)
    quadros = []
    with tempfile.TemporaryDirectory(prefix="topclip-amostra-") as tmp:
        for i, alvo in enumerate(alvos):
            eid, _, vid = alvo.partition(":")
            pasta = acha(eid, raiz)
            vid = vid or next(iter(json.loads((pasta / "estilo.json").read_text())["variacoes"]))
            proj = Path(tmp) / f"p{i}"
            E._projeto_temporario(raiz, pasta, proj, vid)
            png = Path(tmp) / f"q{i}.png"
            cmd = [sys.executable, "-m", "pecas.amostra", "--video", str(video), "--t", str(t),
                   "--saida", str(png)]
            if texto:
                cmd += ["--texto", texto]
            if legenda:
                cmd += ["--legenda", legenda]
            r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True)
            if r.returncode:
                raise ErroEstilo(f"amostra de {alvo} falhou:\n{r.stdout}{r.stderr}")
            nome = json.loads((pasta / "estilo.json").read_text())["nome"]
            quadros.append((f"{nome} · {vid}", Image.open(png).convert("RGB")))
    saida.parent.mkdir(parents=True, exist_ok=True)
    if len(quadros) == 1:
        quadros[0][1].save(saida)
        return saida
    w, h, topo, gap = 540, 960, 56, 16
    folha = Image.new("RGB", (len(quadros) * (w + gap) + gap, h + topo + gap), (32, 31, 33))
    dr = ImageDraw.Draw(folha)
    fonte = ImageFont.truetype(str(raiz / ".claude" / "skills" / "topclip-motion" / "fontes"
                                   / "IBMPlexMono-Medium.ttf"), 28)
    for k, (rot, im) in enumerate(quadros):
        x = gap + k * (w + gap)
        folha.paste(im.resize((w, h), Image.LANCZOS), (x, topo))
        dr.text((x + 4, 14), f"{k + 1}. {rot}", font=fonte, fill=(219, 214, 83))
    folha.save(saida)
    return saida


# ---------------------------------------------------------------- linha de comando

def comandos(sub):
    """Os subcomandos de `./topclip estilo` que vivem aqui."""
    r = sub.add_parser("remixar", help="copia um estilo para os seus, como rascunho")
    r.add_argument("base")
    r.add_argument("novo_id")
    r.add_argument("--nome")
    r.add_argument("--autor")
    a = sub.add_parser("ajustar", help="muda cor, fonte, energia... de um estilo seu")
    a.add_argument("alvo")
    a.add_argument("pares", nargs="+", help="chave=valor (ex.: cor.acento=#FF5A1F)")
    ap = sub.add_parser("aprovar", help="valida, gera a galeria e fecha a versao")
    ap.add_argument("alvo")
    ap.add_argument("--cena")
    e = sub.add_parser("exportar", help=f"gera <id>{EXTENSAO} para compartilhar")
    e.add_argument("alvo")
    e.add_argument("--destino", help="pasta de saida (padrao: a atual)")
    i = sub.add_parser("importar", help=f"instala um {EXTENSAO} nos seus estilos")
    i.add_argument("arquivo")
    i.add_argument("--substituir", action="store_true")
    x = sub.add_parser("apagar", help="apaga um estilo seu")
    x.add_argument("alvo")
    p = sub.add_parser("paleta", help="cores dominantes de imagens da marca")
    p.add_argument("imagens", nargs="+")
    p.add_argument("--cores", type=int, default=6)
    p.add_argument("--para", help="id do seu estilo, para imprimir o comando de ajuste")
    m = sub.add_parser("amostra", help="um quadro do clipe em cada estilo, lado a lado")
    m.add_argument("alvos", nargs="+", help="id ou id:variacao")
    m.add_argument("--video", required=True)
    m.add_argument("--t", type=float, default=3.0)
    m.add_argument("--saida", default="amostra-estilos.png")
    m.add_argument("--texto")
    m.add_argument("--legenda")
    return {"remixar", "ajustar", "aprovar", "exportar", "importar", "apagar", "paleta", "amostra"}


def roda(a):
    """Executa um subcomando de `comandos`. Erro de uso vira mensagem, nao traceback."""
    try:
        if a.cmd == "remixar":
            p = remixar(a.raiz, a.base, a.novo_id, a.nome, a.autor)
            print(f"  criado: {p} (rascunho 0.1.0)")
            print(f"  ajuste:  ./topclip estilo ajustar {p.name} cor.acento=#RRGGBB ...")
            print(f"  aprove:  ./topclip estilo aprovar {p.name}")
        elif a.cmd == "ajustar":
            v, avisos = ajustar(a.raiz, a.alvo, a.pares)
            print(f"  ok    {a.alvo} {v}")
            for x in avisos:
                print(f"  aviso {x}")
        elif a.cmd == "aprovar":
            v, avisos = aprovar(a.raiz, a.alvo, a.cena)
            print(f"  aprovado: {a.alvo} {v} (galeria regerada)")
            for x in avisos:
                print(f"  aviso {x}")
        elif a.cmd == "exportar":
            print(f"  {exportar(a.raiz, a.alvo, a.destino)}")
        elif a.cmd == "importar":
            p = importar(a.raiz, a.arquivo, a.substituir)
            print(f"  instalado: {p}")
        elif a.cmd == "apagar":
            print(f"  apagado: {apagar(a.raiz, a.alvo)}")
        elif a.cmd == "paleta":
            r = paleta(a.imagens, a.cores)
            for c, pct in r["cores"]:
                print(f"  {c}  {pct:5.1f}%")
            s = r["sugestao"]
            print(f"  sugestao: fundo {s['fundo']} · texto {s['texto']} "
                  f"({r['contraste']['texto']}:1) · acento {s['acento']} ({r['contraste']['acento']}:1)")
            if a.para:
                print(f"  ./topclip estilo ajustar {a.para} cor.fundo={s['fundo']} "
                      f"cor.texto={s['texto']} cor.acento={s['acento']}")
        elif a.cmd == "amostra":
            print(f"  {amostra(a.raiz, a.alvos, a.video, a.t, a.saida, a.texto, a.legenda)}")
    except ErroEstilo as e:
        print(f"  ERRO  {e}", file=sys.stderr)
        return 1
    return 0
