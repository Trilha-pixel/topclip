"""
Pecas: os componentes animados que todo estilo compartilha. Ver `base.py` para a
interface e docs/proposta-estilos.md (secao 8) para o plano.

    import pecas as P
    ESTILO = P.carregar(ROOT)
    c = P.fundo(frame, 0, 90, ESTILO)
    c.alpha_composite(P.contador.quadro(frame, 4, 90, ESTILO, valor=3000, prefixo="R$ "))

O `./topclip motion novo` copia esta pasta para `<projeto>/pecas/`: o projeto congela a
versao das pecas junto com a do estilo.
"""
from . import (antes_depois, cartao, cascata, contador, desfoque, lottie, marca_texto,
               troca_palavra)
from .base import Estilo, W, H, carregar, cola, fundo, lin, vazio

TODAS = {"contador": contador, "marca_texto": marca_texto, "troca_palavra": troca_palavra,
         "desfoque": desfoque, "cascata": cascata, "antes_depois": antes_depois,
         "cartao": cartao, "lottie": lottie}
