"""
A arte do post: prints empilhados, um por parte da frase, com o texto embaixo de cada um.

    from arte import montar
    img = montar([{"imagem": "p-0001.jpg", "rosto": [820, 210, 260, 300], "texto": "**Seja obcecado** pelo processo."},
                  {"imagem": "p-0007.jpg", "rosto": [...], "texto": "O resultado **vira consequência.**"}],
                 formato="feed", fonte="inter")
    img.save("post.png")

O visual é o dos posts de frase que viralizam: branco, centralizado, peso normal com as
palavras-chave em negrito, sobre um degradê escuro no pé de cada print. O degradê fica
mais forte quando o fundo atrás do texto é claro (parede branca, camisa clara).

Opções: `pb=True` deixa as fotos em preto e branco (o texto e o destaque continuam);
`assinatura="@perfil"` escreve o @ pequeno embaixo do texto do último print; `capa=True`
faz o slide de capa do carrossel (um print só, o título maior e "arraste para o lado").

Tamanhos (1080 de largura):
  feed 4:5    1080×1350 — 2 prints de 1080×675 (quase o quadro inteiro do vídeo) ou 3 de 1080×450
  stories     1080×1920 — 3 prints de 1080×556 ou 2 de 1080×835, acima de uma faixa escura de
              250 px no pé, onde o Instagram põe a caixa de resposta (o texto nunca cai ali)

Só Pillow: roda no painel (prévia ao vivo) e no `./topclip post render`.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

from frases import tokens

AQUI = Path(__file__).resolve().parent
PASTAS_FONTES = [AQUI.parent / "fontes", AQUI.parents[1] / "topclip-motion" / "fontes"]

FORMATOS = {
    "feed": {"nome": "Feed 4:5", "tamanho": (1080, 1350)},
    "stories": {"nome": "Stories 9:16", "tamanho": (1080, 1920)},
}
# DM Sans é a mais parecida com a dos posts de frase que viralizam (geométrica, compacta)
PADRAO = {"formato": "feed", "prints": {"feed": 2, "stories": 3}, "fonte": "dmsans"}

# Cada família: o arquivo e os eixos do peso normal e do negrito. As que faltarem no disco
# somem da lista (as da pasta fontes/ desta skill são opcionais).
FONTES = {
    "inter": {"nome": "Inter", "arquivo": "Inter[opsz,wght].ttf",
              "regular": {"opsz": 32, "wght": 400}, "negrito": {"opsz": 32, "wght": 700}},
    "jakarta": {"nome": "Plus Jakarta Sans", "arquivo": "PlusJakartaSans[wght].ttf",
                "regular": {"wght": 400}, "negrito": {"wght": 700}},
    "montserrat": {"nome": "Montserrat", "arquivo": "Montserrat[wght].ttf",
                   "regular": {"wght": 400}, "negrito": {"wght": 700}},
    "dmsans": {"nome": "DM Sans", "arquivo": "DMSans[opsz,wght].ttf",
               "regular": {"opsz": 32, "wght": 400}, "negrito": {"opsz": 32, "wght": 700}},
    "archivo": {"nome": "Archivo Narrow", "arquivo": "ArchivoNarrow[wght].ttf",
                "regular": {"wght": 400}, "negrito": {"wght": 700}, "escala": 1.12},
    "fraunces": {"nome": "Fraunces", "arquivo": "Fraunces[SOFT,WONK,opsz,wght].ttf",
                 "regular": {"opsz": 72, "wght": 400, "SOFT": 50, "WONK": 0},
                 "negrito": {"opsz": 72, "wght": 700, "SOFT": 50, "WONK": 0}},
    "playfair": {"nome": "Playfair Itálico", "arquivo": "PlayfairDisplay-Italic[wght].ttf",
                 "regular": {"wght": 400}, "negrito": {"wght": 800}, "escala": 1.06},
}
EIXOS = {b"Weight": "wght", b"Optical size": "opsz", b"Optical Size": "opsz", b"Softness": "SOFT", b"Wonky": "WONK"}

# o tamanho do texto e a altura do rosto (fração do print) por formato e número de prints
TEXTO = {("feed", 1): 60, ("feed", 2): 54, ("feed", 3): 46,
         ("stories", 1): 64, ("stories", 2): 60, ("stories", 3): 54}
TEXTO_CAPA = 78                # o título da capa do carrossel
DICA_CAPA = "arraste para o lado"
MARGEM_LADO = 72
RESPIRO_STORIES = 250          # px no pé dos stories: a caixa de resposta cobre essa faixa
BRANCO = (255, 255, 255)


# ------------------------------------------------------------------ fontes
def achar_fonte(arquivo: str) -> Path | None:
    p = Path(arquivo)
    if p.is_absolute():
        return p if p.is_file() else None
    return next((d / arquivo for d in PASTAS_FONTES if (d / arquivo).is_file()), None)


def fontes_disponiveis() -> dict:
    return {k: v for k, v in FONTES.items() if achar_fonte(v["arquivo"])}


def familia(fonte) -> dict:
    """O id de uma família da lista, ou a própria família (dict) — a fonte da marca da pessoa."""
    if isinstance(fonte, dict) and fonte.get("arquivo"):
        return fonte
    disp = fontes_disponiveis()
    return disp.get(fonte) or disp.get(PADRAO["fonte"]) or next(iter(disp.values()))


_cache_fontes: dict = {}


def carregar(arquivo: str, tamanho: int, eixos: dict | None) -> ImageFont.FreeTypeFont:
    chave = (arquivo, tamanho, tuple(sorted((eixos or {}).items())))
    if chave not in _cache_fontes:
        caminho = achar_fonte(arquivo)
        if not caminho:
            raise FileNotFoundError(f"fonte não encontrada: {arquivo}")
        f = ImageFont.truetype(str(caminho), tamanho)
        if eixos:
            try:
                ordem = f.get_variation_axes()
                f.set_variation_by_axes([eixos.get(EIXOS.get(a["name"], ""), a["default"]) for a in ordem])
            except (OSError, AttributeError):
                pass                                   # fonte estática: vale como está
        _cache_fontes[chave] = f
    return _cache_fontes[chave]


def par_de_fontes(fam: dict, tamanho: int):
    tamanho = max(8, int(round(tamanho * fam.get("escala", 1.0))))
    arq_n = fam.get("arquivo_negrito") or fam["arquivo"]
    return carregar(fam["arquivo"], tamanho, fam.get("regular")), carregar(arq_n, tamanho, fam.get("negrito"))


# ------------------------------------------------------------------ imagens
_cache_img: "OrderedDict[str, Image.Image]" = OrderedDict()


def abrir(imagem) -> Image.Image:
    """Caminho (com cache: editar o texto não relê o JPG) ou uma Image já aberta."""
    if isinstance(imagem, Image.Image):
        return imagem.convert("RGB")
    chave = str(imagem)
    if chave in _cache_img:
        _cache_img.move_to_end(chave)
        return _cache_img[chave]
    img = Image.open(chave)
    img.load()
    img = img.convert("RGB")
    _cache_img[chave] = img
    while len(_cache_img) > 32:
        _cache_img.popitem(last=False)
    return img


def recorte(fw, fh, pw, ph, rosto=None, zoom=1.0, dx=0.0, dy=0.0, livre=0.8):
    """O retângulo (x0, y0, x1, y1) do quadro que vira um print de pw×ph.

    Com rosto: aproxima até o rosto ocupar metade da altura do print (nos prints deitados,
    como nos posts de referência) ou ~26% (no print em pé, que mostra o tronco), sem ampliar
    o quadro mais que 1,35×. O rosto fica centrado na largura e inteiro acima do texto:
    `livre` é a fração do print acima dele (no último print dos stories o texto sobe, e o
    rosto sobe e diminui junto). `zoom` multiplica a aproximação automática; `dx`/`dy`
    empurram o recorte (fração dele)."""
    ar = pw / ph
    cw, ch = (fh * ar, fh) if fw / fh > ar else (fw, fw / ar)
    deitado = ar >= 1.2
    z_max = max(1.0, cw / (pw / 1.35))
    z = 1.0
    if rosto:
        alvo = min(0.50, livre * 0.68) if deitado else min(0.26, livre * 0.4)
        z = max(1.0, alvo * ch / max(1.0, rosto[3]))
    z = max(1.0, min(z * max(0.5, float(zoom or 1)), z_max * 1.15))
    cw, ch = cw / z, ch / z
    if rosto:
        cx, cy = rosto[0] + rosto[2] / 2, rosto[1] + rosto[3] / 2
        x0, y0 = cx - cw / 2, cy - min(0.40 if deitado else 0.33, livre * 0.5) * ch
    else:
        x0, y0 = (fw - cw) / 2, (fh - ch) * 0.4
    x0 += float(dx or 0) * cw
    y0 += float(dy or 0) * ch
    x0 = min(max(0.0, x0), fw - cw)
    y0 = min(max(0.0, y0), fh - ch)
    return (x0, y0, x0 + cw, y0 + ch)


# ------------------------------------------------------------------ texto
def _linhas(toks, fr, fn, largura, n_linhas):
    """Quebra as palavras em `n_linhas` linhas equilibradas (a mais larga o menor possível).
    Devolve (linhas, largura da mais larga) ou None se não couber."""
    lw = [(fn if b else fr).getlength(p) for p, b in toks]
    esp = fr.getlength(" ")
    if not toks:
        return [], 0

    def largura_de(a, b):
        return sum(lw[a:b]) + esp * max(0, b - a - 1)

    k = len(toks)
    if n_linhas == 1 or k == 1:
        w = largura_de(0, k)
        return ([toks], w) if w <= largura else None
    melhor = None
    if n_linhas == 2:
        opcoes = ([0, i, k] for i in range(1, k))
    else:
        opcoes = ([0, i, j, k] for i in range(1, k - 1) for j in range(i + 1, k))
    for lim in opcoes:
        ws = [largura_de(a, b) for a, b in zip(lim, lim[1:])]
        if max(ws) > largura:
            continue
        # a última linha um pouco mais curta que a primeira lê melhor que o contrário
        nota = max(ws) + (0.15 * (ws[-1] - ws[0]) if ws[-1] > ws[0] else 0)
        if melhor is None or nota < melhor[0]:
            melhor = (nota, lim, max(ws))
    if melhor is None:
        return None
    lim = melhor[1]
    return [toks[a:b] for a, b in zip(lim, lim[1:])], melhor[2]


def compor_texto(texto, fam, tamanho, largura, min_frac=0.72):
    """Escolhe o tamanho e a quebra: até 2 linhas, encolhendo até 72% do tamanho; não
    coube, aceita 3 linhas (e por fim quantas precisar, no menor tamanho)."""
    toks = tokens(texto)
    if not toks:
        return None
    menor = int(tamanho * min_frac)
    for max_l in (2, 3):
        t = tamanho
        while t >= menor:
            fr, fn = par_de_fontes(fam, t)
            for n in range(1, max_l + 1):
                r = _linhas(toks, fr, fn, largura, n)
                if r:
                    return {"linhas": r[0], "fr": fr, "fn": fn, "tamanho": t}
            t -= 2
    fr, fn = par_de_fontes(fam, menor)
    linhas, atual, w = [], [], 0
    esp = fr.getlength(" ")
    for p, b in toks:
        pw = (fn if b else fr).getlength(p)
        if atual and w + esp + pw > largura:
            linhas.append(atual)
            atual, w = [], 0
        w += (esp if atual else 0) + pw
        atual.append((p, b))
    linhas.append(atual)
    return {"linhas": linhas, "fr": fr, "fn": fn, "tamanho": menor}


def desenhar_texto(camada, bloco, base_y, largura_total, cor, cor_destaque):
    """Desenha as linhas centralizadas; `base_y` é a linha de base da ÚLTIMA linha."""
    d = ImageDraw.Draw(camada)
    fr, fn = bloco["fr"], bloco["fn"]
    entre = bloco["tamanho"] * 1.2
    esp = fr.getlength(" ")
    n = len(bloco["linhas"])
    for i, linha in enumerate(bloco["linhas"]):
        y = base_y - (n - 1 - i) * entre
        ws = [(fn if b else fr).getlength(p) for p, b in linha]
        x = (largura_total - (sum(ws) + esp * (len(linha) - 1))) / 2
        for (p, b), w in zip(linha, ws):
            d.text((x, y), p, font=fn if b else fr, fill=(cor_destaque if b else cor) + (255,), anchor="ls")
            x += w + esp


def _hex(c, padrao=None):
    if isinstance(c, str) and len(c) == 7 and c.startswith("#"):
        try:
            return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return padrao


# ------------------------------------------------------------------ o post
def preto_e_branco(img: Image.Image) -> Image.Image:
    """P&B com um pouco mais de contraste (o cinza puro do quadro de vídeo fica lavado)."""
    cinza = ImageOps.grayscale(img)
    forte = ImageOps.autocontrast(cinza, cutoff=(0.5, 0.5))
    return Image.blend(cinza, forte, 0.6).convert("RGB")


def _seta(d, x, y, tam, cor):
    """Uma seta → desenhada (nem toda fonte tem o caractere); `y` é a linha de base do texto."""
    meio = y - tam * 0.34
    w = max(1, round(tam * 0.09))
    d.line([(x, meio), (x + tam * 0.9, meio)], fill=cor, width=w)
    d.line([(x + tam * 0.9 - tam * 0.3, meio - tam * 0.26), (x + tam * 0.9, meio), (x + tam * 0.9 - tam * 0.3, meio + tam * 0.26)],
           fill=cor, width=w, joint="curve")


def alturas_dos_prints(n: int, H: int) -> list[int]:
    alt = [H // n] * n
    alt[-1] += H - sum(alt)
    return alt


def montar(paineis: list[dict], *, formato="feed", fonte="inter", destaque=None, referencia="",
           escala=1.0, pb=False, assinatura="", capa=False) -> Image.Image:
    """O post inteiro. Cada painel: {"imagem": caminho ou Image, "rosto": [x, y, w, h] ou None,
    "texto": "com **negrito**", "zoom": 1.0, "x": 0.0, "y": 0.0}. `escala` 0.5 é a prévia."""
    if formato not in FORMATOS:
        raise ValueError(f"formato desconhecido: {formato}")
    n = len(paineis)
    if n not in (1, 2, 3):
        raise ValueError("o post tem 1, 2 ou 3 prints")
    if capa and n != 1:
        raise ValueError("a capa do carrossel tem um print só")
    W, H = (round(v * escala) for v in FORMATOS[formato]["tamanho"])
    s = W / 1080
    fam = familia(fonte)
    cor_destaque = _hex(destaque, BRANCO)
    tela = Image.new("RGB", (W, H), (12, 12, 14))
    # nos stories o pé é da caixa de resposta do Instagram: os prints ficam acima dele e a
    # faixa de baixo é o fim escuro do degradê do último print (o texto nunca cai ali)
    rodape = round(RESPIRO_STORIES * s) if formato == "stories" else 0
    y_tela = 0
    tam_base = TEXTO_CAPA if capa else TEXTO[(formato, n)]
    for i, (pn, ph) in enumerate(zip(paineis, alturas_dos_prints(n, H - rodape))):
        ultimo = i == n - 1
        # o texto primeiro: onde ele fica decide até onde o rosto pode descer
        bloco = compor_texto(pn.get("texto", ""), fam, round(tam_base * s), W - 2 * MARGEM_LADO * s)
        ref = (DICA_CAPA if capa else str(referencia or "").strip()) if ultimo else ""
        sig = str(assinatura or "").strip() if ultimo else ""
        respiro = ph * 0.085
        tam = bloco["tamanho"] if bloco else round(tam_base * s)
        tam_ref = round(tam * (0.42 if capa else 0.52))
        tam_sig = max(round(15 * s), round(min(tam, 54 * s) * 0.42))
        alt_ref = tam_ref * 1.9 if ref else 0
        alt_sig = tam_sig * 1.75 if sig else 0
        desc = tam * 0.28                                      # o que desce abaixo da linha de base
        base = ph - respiro - desc - alt_ref - alt_sig
        n_l = len(bloco["linhas"]) if bloco else 0
        topo = base - tam * 0.95 - max(0, n_l - 1) * tam * 1.2
        livre = max(0.3, topo / ph - 0.03) if (bloco or ref or sig) else 0.9

        if pn.get("imagem") is not None:
            img = abrir(pn["imagem"])
            caixa = recorte(img.width, img.height, W, ph, pn.get("rosto"),
                            pn.get("zoom", 1.0), pn.get("x", 0.0), pn.get("y", 0.0), livre=livre)
            painel = img.resize((W, ph), Image.LANCZOS, box=caixa)
            painel = painel.filter(ImageFilter.UnsharpMask(radius=max(0.6, 1.3 * s), percent=50, threshold=3))
            if pb:
                painel = preto_e_branco(painel)
        else:
            painel = Image.new("RGB", (W, ph), (36, 36, 40))
        painel = painel.convert("RGBA")

        if bloco or ref or sig:
            fr_ref = par_de_fontes(fam, tam_ref)[0] if ref else None
            # degradê: nasce acima do texto e chega à força total na altura dele; mais forte
            # quando o fundo atrás do texto é claro (parede branca, camisa clara)
            faixa = painel.crop((0, max(0, int(topo)), W, ph)).convert("L")
            luz = ImageStat.Stat(faixa).mean[0] / 255 if faixa.height > 0 else 0.5
            forca = min(0.9, max(0.58, 0.5 + 0.55 * luz))
            ini = max(0.0, topo - 0.34 * ph * min(1.0, livre / 0.75))
            cheio = max(ini + 1, topo + 0.45 * (base - topo))
            grad = Image.new("L", (1, ph), 0)
            for y in range(ph):
                if y <= ini:
                    a = 0.0
                elif y < cheio:
                    t = (y - ini) / (cheio - ini)
                    a = forca * t * t * (3 - 2 * t)
                else:
                    a = min(0.96, forca + 0.08 * (y - cheio) / max(1.0, ph - cheio))
                grad.putpixel((0, y), int(255 * a))
            sombra_fundo = Image.new("RGBA", (W, ph), (0, 0, 0, 0))
            sombra_fundo.putalpha(grad.resize((W, ph)))
            painel = Image.alpha_composite(painel, sombra_fundo)

            camada = Image.new("RGBA", (W, ph), (0, 0, 0, 0))
            if bloco:
                desenhar_texto(camada, bloco, base, W, BRANCO, cor_destaque)
            d = ImageDraw.Draw(camada)
            if ref:
                y_ref = base + desc + alt_ref * 0.62
                if capa:                       # "arraste para o lado →", com a seta desenhada
                    w_seta = tam_ref * 1.25
                    x_ref = W / 2 - w_seta / 2
                    d.text((x_ref, y_ref), ref, font=fr_ref, fill=(255, 255, 255, 215), anchor="ms")
                    _seta(d, x_ref + fr_ref.getlength(ref) / 2 + tam_ref * 0.35, y_ref, tam_ref, (255, 255, 255, 215))
                else:
                    d.text((W / 2, y_ref), ref, font=fr_ref, fill=(255, 255, 255, 215), anchor="ms")
            if sig:
                fr_sig = par_de_fontes(fam, tam_sig)[0]
                d.text((W / 2, base + desc + alt_ref + alt_sig * 0.66), sig, font=fr_sig, fill=(255, 255, 255, 180), anchor="ms")
            # sombra macia do texto: segura a leitura quando o fundo é claro
            sombra = Image.new("RGBA", (W, ph), (0, 0, 0, 0))
            sombra.putalpha(camada.getchannel("A").filter(ImageFilter.GaussianBlur(max(2, 7 * s))).point(lambda a: int(a * 0.5)))
            painel = Image.alpha_composite(painel, sombra.transform(sombra.size, Image.AFFINE, (1, 0, 0, 0, 1, -2 * s)))
            painel = Image.alpha_composite(painel, camada)
        tela.paste(painel.convert("RGB"), (0, y_tela))
        y_tela += ph
    return tela
