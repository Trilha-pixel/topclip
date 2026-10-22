"""
Legenda dos estilos que nao sao o Papel.

Reaproveita do `captions` o que e caro e ja foi medido: a divisao da fala em blocos, o
tempo de cada palavra, as janelas livres e a posicao pelo rosto. Troca so o desenho:
fonte, cor, destaque e animacao vem do `legenda.json` do estilo. O `captions.py` nao
muda: os limites do bloco sao ajustados nas constantes do modulo, em tempo de execucao.

Estilo de traco "mao" (o Papel, e quem herdar dele) continua com o `captions.draw`,
inclusive o boil "print" da tipografia.
"""
from PIL import Image, ImageDraw, ImageFilter

from .base import W, H, _contraste, abre_fonte, com_sombra, largura_texto, quebra, retangulo

LARGURA = int(W * 0.72)        # coluna da legenda: a fonte limpa e mais estreita que a do Papel


def para(estilo):
    """A legenda do estilo, ou None quando e a do Papel."""
    if estilo is None or estilo.r.get("traco") == "mao":
        return None
    return Legenda(estilo)


class Legenda:
    def __init__(self, estilo):
        self.e = estilo
        self.c = estilo.legenda

    def configura(self, cap):
        """Ajusta o tamanho do bloco no modulo captions. Chame antes do primeiro blocos()."""
        cap.MAXPAL = int(self.c["palavras_por_bloco"])
        alvo = self.c.get("duracao_alvo")
        if alvo:
            cap.ALVO = float(alvo)
            cap.MAXDUR = round(float(alvo) * 1.9, 3)   # a razao medida no Papel: 0,62 / 0,33
        return self

    def quadros_entrada(self, fps):
        """Quantos quadros a entrada do bloco dura (0 = corte seco)."""
        if self.c["animacao"] == "corte_seco":
            return 0
        return max(1, round(self.c.get("entrada_s", 0.13) * fps))

    def _fonte(self, enf, tamanho):
        caminho = self.c.get("fonte_enfase") if enf and self.c.get("fonte_enfase") else self.c["fonte"]
        return abre_fonte(str(self.e.raiz / caminho), int(tamanho), int(self.c.get("peso", 700)))

    def draw(self, bloco, k, fps, posicao):
        """O bloco no k-esimo quadro desde que entrou. `posicao` = captions.posicao()."""
        c = self.c
        enf = bool(bloco.get("enf"))
        destaque = enf and bool(bloco.get("cor"))
        texto = bloco["txt"].rstrip(",;:")              # virgula no fim do bloco so suja a caixa
        texto = texto.upper() if c["caixa_alta"] else texto
        tamanho = c["corpo"] * (c["enfase"] if enf else 1.0)
        fonte = self._fonte(enf, tamanho)
        maior = max(largura_texto(fonte, p) for p in texto.split())
        if maior > W * 0.84:                                  # palavra nunca quebra: encolhe
            tamanho *= W * 0.84 / maior
            fonte = self._fonte(enf, tamanho)
        linhas = quebra(fonte, texto, LARGURA)
        asc, desc = fonte.getmetrics()
        passo = int(fonte.size * 1.08)
        # Caixa atras do bloco: a pilula do acento no destaque; a `fundo` da legenda (a
        # etiqueta do Limpo) nos outros. Texto em caixa sai no maior contraste com ela.
        # Com destaque_modo "texto" (Impacto, Luxo) o destaque e a cor da palavra, sem caixa.
        pilula = destaque and c.get("destaque_modo", "pilula") == "pilula"
        caixa = c["destaque"] if pilula else c.get("fundo")
        cor = self.e.cor(c["destaque"] if destaque and not pilula else c["cor"])
        if pilula:
            cor = self.e.cor(max(("#FFFFFF", "#111111"), key=lambda h: _contraste(h, caixa)))

        tinta = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        total = passo * (len(linhas) - 1) + asc + desc
        cy, teto = posicao
        y = max(teto, cy - total / 2)
        if caixa:
            larg = max(largura_texto(fonte, l) for l in linhas)
            px, py = fonte.size * 0.36, fonte.size * 0.2
            alfa = 255 if pilula else int(255 * c.get("fundo_alfa", 0.94))
            cx = retangulo(larg + 2 * px, total + 2 * py, fonte.size * 0.32, self.e.cor(caixa, alfa))
            if not pilula:            # a etiqueta clara sobre camisa clara precisa de borda
                cx = com_sombra(cx, desfoque=14, opacidade=0.22, dy=4, margem=30)
                tinta.alpha_composite(cx, (int((W - cx.width) / 2), int(y - py - 30)))
            else:
                tinta.alpha_composite(cx, (int((W - cx.width) / 2), int(y - py)))
        d = ImageDraw.Draw(tinta)
        sd = c.get("sombra_dura")
        traco = dict(stroke_width=int(c["contorno"]), stroke_fill=(0, 0, 0, 255))
        for i, l in enumerate(linhas):
            x = (W - largura_texto(fonte, l)) / 2
            if sd:                    # sombra dura: o mesmo texto, preto e deslocado, por baixo
                d.text((x + sd[0], y + i * passo + sd[1]), l, font=fonte, fill=(0, 0, 0, 255), **traco)
            d.text((x, y + i * passo), l, font=fonte, fill=cor, **traco)

        if not caixa and not c["contorno"] and not sd:
            # sombra macia: a fonte limpa sem sombra some no pescoco iluminado
            a = tinta.getchannel("A").filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.55))
            sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sombra.putalpha(a)
            base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            base.alpha_composite(sombra, (0, 4))
            base.alpha_composite(tinta)
            tinta = base

        n = self.quadros_entrada(fps)
        if n and k < n:
            p = (k + 1) / (n + 1)
            if c["animacao"] == "pop":
                s = 0.86 + 0.14 * self.e.e_entrada(p)
                bb = tinta.getbbox()
                if bb:
                    rec = tinta.crop(bb)
                    rec = rec.resize((max(1, int(rec.width * s)), max(1, int(rec.height * s))),
                                     Image.LANCZOS)
                    tinta = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    cx, cyy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                    tinta.alpha_composite(rec, (int(cx - rec.width / 2), int(cyy - rec.height / 2)))
            tinta.putalpha(tinta.getchannel("A").point(lambda v: int(v * min(1.0, p * 1.15))))
        return tinta
