"""
A base das pecas: o estilo do projeto, curvas, texto e formas.

Toda peca tem a mesma interface:

    camada = peca.quadro(f, inicio, fim, estilo, **dados)    # PIL RGBA 1080x1920

- `f`: o quadro na timeline de 24fps da cena (aceita fracao), como nas receitas do kit;
- `inicio` e `fim`: quando a peca comeca a entrar e quando termina de sair, em quadros,
  travados na palavra do transcript;
- `estilo`: o `Estilo` do projeto (`pecas.carregar(ROOT)`), com cor, fonte e movimento
  ja resolvidos (estilo <- variacao <- marca).

Fora de [inicio, fim] a camada sai vazia. Nenhuma peca le cor ou fonte fixa: tudo vem do
estilo, e por isso a mesma peca veste o Limpo, o Impacto ou o estilo de quem criou o seu.
"""
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SS = 3          # supersampling das formas: borda suave sem depender do antialias do PIL


# ---------------------------------------------------------------- tempo

def bezier(x1, y1, x2, y2):
    """cubic-bezier(x1, y1, x2, y2) como funcao t -> progresso. y pode passar de 1
    (overshoot): quem anima opacidade ou cor corta em 1 (regra universal 4)."""
    def bx(s):
        return 3 * x1 * s * (1 - s) ** 2 + 3 * x2 * s * s * (1 - s) + s ** 3

    def by(s):
        return 3 * y1 * s * (1 - s) ** 2 + 3 * y2 * s * s * (1 - s) + s ** 3

    def curva(t):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(28):
            mid = (lo + hi) / 2
            if bx(mid) < t:
                lo = mid
            else:
                hi = mid
        return by((lo + hi) / 2)
    return curva


def lin(f, a, b):
    """Progresso linear de 0 (em a) a 1 (em b)."""
    if f <= a:
        return 0.0
    if f >= b:
        return 1.0
    return (f - a) / (b - a)


# ---------------------------------------------------------------- o estilo

class Estilo:
    """O `estilo/resolvido.json` do projeto, com as fontes ja abertas e as curvas prontas."""

    def __init__(self, resolvido, raiz):
        self.r = resolvido
        self.raiz = Path(raiz)
        m = resolvido["movimento"]
        self.mov = m
        self.e_entrada = bezier(*m["curva_entrada"])
        self.e_saida = bezier(*m["curva_saida"])
        self.e_mov = bezier(*m["curva_movimento"])
        # a duracao padrao e o meio da faixa do perfil (calmo: 12-17 -> 14,5 quadros)
        self.q_entrada = sum(m["entrada_quadros"]) / 2
        self.q_saida = sum(m["saida_quadros"]) / 2
        self.stagger = m["stagger_quadros"]
        self.desloca = m.get("deslocamento_entrada", 30)
        # tipografia do estilo (em fracao do corpo): caixa alta, contorno e sombra dura do
        # Impacto, peso e espacamento por papel de fonte do Luxo. Sem nada, texto limpo.
        t = resolvido.get("tipografia") or {}
        self.tipo = dict(caixa_alta=bool(t.get("caixa_alta")), contorno=float(t.get("contorno", 0)),
                         cor_contorno=t.get("cor_contorno", "#000000"),
                         sombra_dura=list(t.get("sombra_dura") or [0, 0]),
                         peso=dict(t.get("peso") or {}), tracking=dict(t.get("tracking") or {}))

    @property
    def id(self):
        return self.r["id"]

    @property
    def legenda(self):
        return self.r["legenda"]

    def hexa(self, nome):
        """Cor do estilo pelo nome (ou um #RRGGBB direto). O estilo so e obrigado a ter
        fundo, texto e acento: as outras que as pecas usam caem numa vizinha."""
        if isinstance(nome, str) and nome.startswith("#"):
            return nome
        cores = self.r["cor"]
        if nome in cores:
            return cores[nome]
        if nome == "sobre_acento":
            return max(("#FFFFFF", "#111111"), key=lambda c: _contraste(c, cores["acento"]))
        vizinha = {"superficie": "fundo", "linha": "apoio", "apoio": "texto"}
        while nome not in cores and nome in vizinha:
            nome = vizinha[nome]
        return cores[nome]

    def cor(self, nome, alfa=255):
        h = self.hexa(nome)
        return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), int(alfa))

    @property
    def escuro(self):
        """Fundo escuro pede borda em vez de sombra nos cartoes."""
        r, g, b, _ = self.cor("fundo")
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.35

    def caminho_fonte(self, nome):
        """Fonte do estilo pelo nome; as que faltam caem em `apoio` (obrigatoria)."""
        fontes = self.r["fonte"]
        return str(self.raiz / fontes.get(nome, fontes["apoio"]))

    def fonte(self, nome, tamanho, peso=None):
        """A fonte do papel `nome`. O peso que o estilo fixa para o papel vence o da peca
        (o Luxo pede titulo fino onde a peca pediria 700)."""
        peso = self.tipo["peso"].get(nome, peso)
        return abre_fonte(self.caminho_fonte(nome), int(tamanho), peso)

    # --- texto com a tipografia do estilo
    def caixa(self, texto):
        """O texto como o estilo escreve (caixa alta no Impacto). Aplique ANTES de medir."""
        return texto.upper() if self.tipo["caixa_alta"] else texto

    def tracking(self, nome, tamanho, padrao=0.0):
        """Espacamento entre letras do papel `nome`, em px (o estilo da em fracao do corpo)."""
        return self.tipo["tracking"].get(nome, padrao) * tamanho

    def efeitos(self, fonte, cor=None):
        """Contorno e sombra dura em px para esta fonte (o estilo da em fracao do corpo).
        Letra que ja e da cor do contorno (preto sobre o amarelo) vai sem efeito: contorno
        preto em letra preta vira borrao."""
        s = fonte.size
        dx, dy = self.tipo["sombra_dura"]
        cc = self.tipo["cor_contorno"]
        if cor is not None and _contraste("#%02X%02X%02X" % tuple(cor[:3]), cc) < 2.5:
            return dict(contorno=0, cor_contorno=self.cor(cc), sombra=(0, 0))
        return dict(contorno=int(round(self.tipo["contorno"] * s)), cor_contorno=self.cor(cc),
                    sombra=(int(round(dx * s)), int(round(dy * s))))

    def pad(self, fonte, cor=None):
        """Margem que `linha` deixa em volta do texto (para quem mede palavra no bloco)."""
        e = self.efeitos(fonte, cor)
        return 2 + e["contorno"] + max(abs(e["sombra"][0]), abs(e["sombra"][1]))

    def linha(self, texto, fonte, cor, tracking=0):
        return linha(texto, fonte, cor, tracking, **self.efeitos(fonte, cor))

    def bloco(self, linhas, fonte, cor, entrelinha=1.12, alinha="centro", tracking=0):
        return bloco(linhas, fonte, cor, entrelinha, alinha, tracking, **self.efeitos(fonte, cor))

    # --- movimento
    def escala(self, ent):
        """Escala da entrada: 1 nos perfis calmo e editorial; no energico a peca nasce
        pequena e passa do tamanho (o 'pop'), pela curva de entrada que passa de 1."""
        amp = self.mov.get("escala_entrada", 0)
        return 1.0 if not amp else max(0.0, 1 - amp * (1 - ent))

    def entrada(self, f, inicio, dur=None):
        """0 -> 1 ao longo da entrada que comeca em `inicio` (curva do perfil)."""
        return self.e_entrada(lin(f, inicio, inicio + (dur or self.q_entrada)))

    def saida(self, f, fim, dur=None):
        """0 -> 1 ao longo da saida que TERMINA em `fim`."""
        d = dur or self.q_saida
        return self.e_saida(lin(f, fim - d, fim))

    def envelope(self, f, inicio, fim):
        """(entrada, saida) da peca inteira. Opacidade = min(1, entrada) * (1 - saida)."""
        return self.entrada(f, inicio), self.saida(f, fim)


def carregar(raiz, opcional=False):
    """O estilo do projeto em `raiz` (le estilo/resolvido.json, gravado pelo motion novo)."""
    f = Path(raiz) / "estilo" / "resolvido.json"
    if not f.is_file():
        if opcional:
            return None
        raise FileNotFoundError(
            f"{f} nao existe. Crie o projeto com ./topclip motion novo <pasta> --estilo <id>.")
    return Estilo(json.loads(f.read_text(encoding="utf-8")), raiz)


def _contraste(a, b):
    def lum(h):
        def c(v):
            v = v / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * c(int(h[1:3], 16)) + 0.7152 * c(int(h[3:5], 16)) + 0.0722 * c(int(h[5:7], 16))
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


@lru_cache(maxsize=256)
def abre_fonte(caminho, tamanho, peso=None):
    """Fonte com o peso travado. Fonte variavel sem eixo travado abre na instancia padrao
    (a Inter abriria Regular onde se pediu 700)."""
    f = ImageFont.truetype(caminho, tamanho)
    try:
        eixos = f.get_variation_axes()
    except (OSError, AttributeError):
        return f
    vals = []
    for ax in eixos:
        nome = ax["name"].decode() if isinstance(ax["name"], bytes) else str(ax["name"])
        v = ax["default"]
        if nome == "Weight" and peso:
            v = peso
        elif nome == "Optical size":
            v = tamanho / 2.4                  # corpo grande pede o desenho de display
        vals.append(max(ax["minimum"], min(ax["maximum"], v)))
    f.set_variation_by_axes(vals)
    return f


# ---------------------------------------------------------------- camadas

def vazio():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def opaco(camada, k):
    """Multiplica a opacidade da camada por k (0..1)."""
    k = max(0.0, min(1.0, k))
    if k >= 1:
        return camada
    out = camada.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * k)))
    return out


def cola(tela, camada, centro, k=1.0, dy=0.0, dx=0.0, escala=1.0):
    """Cola `camada` com o centro em `centro`, deslocada, escalada e com opacidade k."""
    if k <= 0 or escala <= 0.02:
        return tela
    if abs(escala - 1.0) > 1e-3:
        camada = camada.resize((max(1, int(camada.width * escala)),
                                max(1, int(camada.height * escala))), Image.LANCZOS)
    x = int(round(centro[0] - camada.width / 2 + dx))
    y = int(round(centro[1] - camada.height / 2 + dy))
    tela.alpha_composite(opaco(camada, k), (x, y))
    return tela


def sombra(camada, desfoque=26, opacidade=0.16, dy=12, margem=60):
    """A sombra difusa de uma camada, ja com margem: devolve (sombra, deslocamento)."""
    w, h = camada.width + 2 * margem, camada.height + 2 * margem
    a = Image.new("L", (w, h), 0)
    a.paste(camada.getchannel("A"), (margem, margem + dy))
    a = a.filter(ImageFilter.GaussianBlur(desfoque)).point(lambda v: int(v * opacidade))
    s = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s.putalpha(a)
    return s


def com_sombra(camada, **kw):
    """A camada sobre a propria sombra, numa camada maior (margem dos dois lados)."""
    margem = kw.get("margem", 60)
    s = sombra(camada, **kw)
    s.alpha_composite(camada, (margem, margem))
    return s


# ---------------------------------------------------------------- formas

def retangulo(w, h, raio, cor, borda=None):
    """Retangulo arredondado com borda suave. `borda` = (largura, cor) opcional."""
    w, h = max(1, int(w)), max(1, int(h))
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=int(raio * SS), fill=cor)
    if borda:
        lb, cb = borda
        d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=int(raio * SS),
                            outline=cb, width=max(1, int(lb * SS)))
    return big.resize((w, h), Image.LANCZOS)


def circulo(diam, cor):
    d = max(1, int(diam))
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse([0, 0, d * SS - 1, d * SS - 1], fill=cor)
    return big.resize((d, d), Image.LANCZOS)


def traco(w, h, pontos, largura, cor, progresso=1.0):
    """Polilinha com pontas redondas, desenhada ate `progresso` do comprimento."""
    import math
    big = Image.new("RGBA", (int(w) * SS, int(h) * SS), (0, 0, 0, 0))
    if progresso <= 0 or len(pontos) < 2:
        return big.resize((int(w), int(h)), Image.LANCZOS)
    segs = [(pontos[i], pontos[i + 1]) for i in range(len(pontos) - 1)]
    total = sum(math.dist(a, b) for a, b in segs)
    falta = total * min(1.0, progresso)
    pts = [pontos[0]]
    for a, b in segs:
        L = math.dist(a, b)
        if falta >= L:
            pts.append(b)
            falta -= L
        else:
            k = falta / L if L else 0
            pts.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            break
    d = ImageDraw.Draw(big)
    lw = max(1, int(largura * SS))
    sp = [(x * SS, y * SS) for x, y in pts]
    d.line(sp, fill=cor, width=lw, joint="curve")
    for x, y in (sp[0], sp[-1]):
        d.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=cor)
    return big.resize((int(w), int(h)), Image.LANCZOS)


def arco(w, h, largura, cor, progresso=1.0, inicio=-100):
    """Elipse desenhada como traco, de `inicio` graus ate progresso x 360."""
    big = Image.new("RGBA", (int(w) * SS, int(h) * SS), (0, 0, 0, 0))
    if progresso > 0:
        m = largura * SS / 2
        ImageDraw.Draw(big).arc([m, m, w * SS - m, h * SS - m], start=inicio,
                                end=inicio + 360 * min(1.0, progresso), fill=cor,
                                width=max(1, int(largura * SS)))
    return big.resize((int(w), int(h)), Image.LANCZOS)


# ---------------------------------------------------------------- texto

def largura_texto(fonte, texto, tracking=0):
    return fonte.getlength(texto) + tracking * max(0, len(texto) - 1)


def quebra(fonte, texto, largura, tracking=0, equilibra=True):
    """Linhas que cabem em `largura`. Palavra sozinha nunca quebra; '\\n' forca linha.
    `equilibra`: com o mesmo numero de linhas, a menor largura que ainda cabe — sem
    palavra orfa ("CLIENTE QUE COMPRA DE / NOVO" vira "CLIENTE QUE / COMPRA DE NOVO")."""
    out = _quebra(fonte, texto, largura, tracking)
    if equilibra and len(out) > 1 and "\n" not in texto:
        lo, hi = largura * 0.4, float(largura)
        for _ in range(10):
            meio = (lo + hi) / 2
            if len(_quebra(fonte, texto, meio, tracking)) == len(out):
                hi = meio
            else:
                lo = meio
        out = _quebra(fonte, texto, hi, tracking)
    return out


def _quebra(fonte, texto, largura, tracking=0):
    out = []
    for paragrafo in texto.split("\n"):
        cur = []
        for p in paragrafo.split():
            if cur and largura_texto(fonte, " ".join(cur + [p]), tracking) > largura:
                out.append(" ".join(cur))
                cur = [p]
            else:
                cur.append(p)
        out.append(" ".join(cur))
    return out


def linha(texto, fonte, cor, tracking=0, contorno=0, cor_contorno=(0, 0, 0, 255), sombra=(0, 0)):
    """Uma linha num layer justo na METRICA da fonte (ascendente a descendente), para
    que linhas com e sem acento tenham a mesma altura e alinhem pela linha de base.
    `contorno` e `sombra` (dura, deslocada) em px; sem eles, o layer e o de sempre."""
    asc, desc = fonte.getmetrics()
    extra = contorno + max(abs(sombra[0]), abs(sombra[1]))
    p = 2 + extra
    w = int(largura_texto(fonte, texto, tracking)) + 2 * p
    lay = Image.new("RGBA", (max(4, w), asc + desc + 2 * extra), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def escreve(x, y, cor_txt):
        kw = dict(stroke_width=contorno, stroke_fill=cor_contorno) if contorno else {}
        if tracking:
            for c in texto:
                d.text((x, y), c, font=fonte, fill=cor_txt, **kw)
                x += fonte.getlength(c) + tracking
        else:
            d.text((x, y), texto, font=fonte, fill=cor_txt, **kw)

    if sombra != (0, 0):
        escreve(p + sombra[0], extra + sombra[1], cor_contorno)
    escreve(p, extra, cor)
    return lay


def bloco(linhas, fonte, cor, entrelinha=1.12, alinha="centro", tracking=0, **efeitos):
    """Varias linhas empilhadas. Devolve (layer, caixas): `caixas[i]` = (x, y, w, h) de
    cada linha no layer, para quem precisa marcar uma palavra."""
    lays = [linha(l, fonte, cor, tracking, **efeitos) for l in linhas]
    passo = int(fonte.size * entrelinha)
    w = max(l.width for l in lays)
    h = passo * (len(lays) - 1) + lays[-1].height
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    caixas = []
    for i, l in enumerate(lays):
        x = {"centro": (w - l.width) // 2, "esquerda": 0, "direita": w - l.width}[alinha]
        out.alpha_composite(l, (x, i * passo))
        caixas.append((x, i * passo, l.width, l.height))
    return out, caixas


def acha_palavra(linhas, caixas, fonte, palavra, tracking=0, pad=2):
    """Caixa (x0, y0, x1, y1) da primeira ocorrencia de `palavra` no bloco, ou None.
    `pad` e a margem da `linha` (Estilo.pad: muda com contorno e sombra)."""
    alvo = palavra.lower().strip(".,!?;:\"'()")
    asc, desc = fonte.getmetrics()
    for l, (x, y, _, _) in zip(linhas, caixas):
        pos = 0
        for p in l.split(" "):
            if p.lower().strip(".,!?;:\"'()") == alvo or p.lower() == palavra.lower():
                limpa = p.rstrip(".,!?;:\"')")
                x0 = x + pad + largura_texto(fonte, l[:pos], tracking) + (tracking if pos else 0)
                x1 = x0 + largura_texto(fonte, limpa, tracking)
                y0 = y + pad - 2
                return (x0, y0, x1, y0 + asc + desc)
            pos += len(p) + 1
    return None


def mascara_retangulo(tamanho, caixa):
    m = Image.new("L", tamanho, 0)
    ImageDraw.Draw(m).rectangle(caixa, fill=255)
    return m


def recorta(camada, mascara):
    """A camada so onde a mascara deixa (multiplica o alfa)."""
    out = camada.copy()
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mascara))
    return out


def cinema(f, inicio, fim, estilo, altura=0.1, cor="#000000"):
    """Faixas de cinema (letterbox) que crescem de cima e de baixo e voltam na saida. Sobre
    o video, dao o tom de filme do Luxo sem cobrir o rosto."""
    if not (inicio <= f <= fim):
        return vazio()
    ent, sai = estilo.envelope(f, inicio, fim)
    h = int(H * altura * min(1.0, ent) * (1 - sai))
    tela = vazio()
    if h > 0:
        d = ImageDraw.Draw(tela)
        d.rectangle([0, 0, W, h], fill=estilo.cor(cor))
        d.rectangle([0, H - h, W, H], fill=estilo.cor(cor))
    return tela


def fundo(f, inicio, fim, estilo, cor="fundo"):
    """Tela cheia na cor do estilo, entrando e saindo em fade pelo perfil. E o que faz uma
    cena de overlay (cutaway=False no SHOTS) virar 'tela cheia' sem corte seco."""
    if not (inicio <= f <= fim):
        return vazio()
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    return Image.new("RGBA", (W, H), estilo.cor(cor, 255 * k))
