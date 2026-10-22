"""
Troca de palavra: uma palavra que troca no mesmo lugar, abaixo de uma frase fixa.
Ideia do Word Rotate do Magic UI (MIT).

    troca_palavra.quadro(f, inicio, fim, estilo, prefixo="Cliente barato é",
                         palavras=["exigente", "lento", "caro"], trocas=[30, 52])

`trocas`: o quadro em que cada palavra depois da primeira entra — trave cada uma na
palavra do transcript. Sem `trocas`, ficam espacadas por igual. A palavra rola dentro de
uma janela da altura da linha: a que sai sobe e some na borda, a nova sobe de baixo.
"""
from PIL import Image

from .base import cola, opaco, vazio

EXEMPLO = dict(inicio=0, fim=110, f=52, dados=dict(
    prefixo="Cliente barato é", palavras=["exigente", "lento", "caro"], trocas=[30, 60]))


def quadro(f, inicio, fim, estilo, palavras, trocas=None, prefixo=None, centro=(540, 860),
           tamanho=128, peso=700, cor="acento"):
    tela = vazio()
    if not inicio <= f <= fim or not palavras:
        return tela
    ent, sai = estilo.envelope(f, inicio, fim)
    k = min(1.0, ent) * (1 - sai)
    if trocas is None:
        passo = (fim - estilo.q_saida - inicio) / len(palavras)
        trocas = [inicio + passo * (i + 1) for i in range(len(palavras) - 1)]
    if len(trocas) != len(palavras) - 1:
        raise ValueError("trocas precisa de uma entrada a menos que palavras")
    dy0 = (1 - ent) * estilo.desloca - sai * 18
    s = estilo.escala(ent)

    fp = estilo.fonte("titulo", tamanho, peso)
    lays = [estilo.linha(estilo.caixa(p), fp, estilo.cor(cor)) for p in palavras]
    janela = Image.new("RGBA", (max(l.width for l in lays), lays[0].height), (0, 0, 0, 0))
    i = sum(1 for t in trocas if f >= t)
    dur = estilo.q_entrada * 0.9
    h = janela.height
    if i > 0 and f < trocas[i - 1] + dur:
        a = estilo.e_entrada(min(1.0, (f - trocas[i - 1]) / dur))
        b = estilo.e_saida(min(1.0, (f - trocas[i - 1]) / dur))
        # a que sai apaga nos primeiros 60% da troca, enquanto sobe: com a curva de saida
        # (que acelera no fim) ela ainda aparecia como fantasma na borda da janela
        t = min(1.0, (f - trocas[i - 1]) / dur)
        velha, nova = opaco(lays[i - 1], 1 - t / 0.6), opaco(lays[i], min(1.0, a))
        janela.alpha_composite(velha, ((janela.width - velha.width) // 2, int(-h * b)))
        janela.alpha_composite(nova, ((janela.width - nova.width) // 2, int(h * (1 - min(1.0, a)))))
    else:
        janela.alpha_composite(lays[i], ((janela.width - lays[i].width) // 2, 0))

    if not prefixo:
        cola(tela, janela, centro, k, dy0, escala=s)
        return tela
    # prefixo em cima, janela embaixo, o par centrado em `centro`
    pre = estilo.linha(estilo.caixa(prefixo), estilo.fonte("titulo", int(tamanho * 0.5), 600),
                       estilo.cor("texto"))
    gap = tamanho * 0.04
    topo = centro[1] - (pre.height + gap + h) / 2
    cola(tela, pre, (centro[0], topo + pre.height / 2), k, dy0, escala=s)
    cola(tela, janela, (centro[0], topo + pre.height + gap + h / 2), k, dy0, escala=s)
    return tela
