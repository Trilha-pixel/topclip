# Limpo

Fundo chapado, tipografia sem serifa, **um acento só** e movimento calmo. Lê como uma
aula bem diagramada, não como anúncio. Bom para educação, saúde, produtividade, B2B e
tecnologia. Duas variações: **claro** (off-white quente) e **escuro** (quase preto).

Num projeto Limpo, **este arquivo manda sobre a `IDENTIDADE.md`** (que é do Papel). As
regras universais e a rubrica do Diretor continuam valendo
(`docs/proposta-estilos.md`, seção 7).

## O que faz o Limpo ser o Limpo

1. **Fundo chapado**, sem textura, sem grão, sem vinheta, sem boil. A cor vem de
   `cor.fundo` (claro `#F0EEE9`, escuro `#0A0A0B`).
2. **Um acento por cena** (`cor.acento`, azul `#2F6BFF` no claro e `#5B8CFF` no escuro).
   O resto é texto e cinza. Dois acentos na mesma cena viram slide de Canva.
3. **Inter** em tudo que se lê: títulos e números a 700, texto de apoio a 500–600, em
   sentence case. Caixa alta só no rótulo pequeno (IBM Plex Mono, com tracking).
4. **Cartões** na `cor.superficie`, cantos de 28–40 px. No claro, sombra difusa leve; no
   escuro, borda fina na `cor.linha` (sombra some no preto).
5. **Movimento do perfil calmo**: entrada de 12–17 quadros que desacelera, sem overshoot;
   saída mais curta que a entrada; um protagonista por vez; cascata com no máximo 0,9 s.
6. **Entra e sai sem corte seco.** Toda cena é overlay: o fundo entra em fade, e a cena
   sai em fade. Nunca slide, wipe ou push (são do Papel).

## O desenho (lápis `limpo`)

O mesmo fluxo do Papel — a frase tem objeto, o objeto é desenhado e entra na palavra —
com o desenho do Limpo: **ícone de produto**. Chapado, sem contorno; o corpo no acento, o
detalhe num tom claro do próprio acento, a face na `cor.superficie`; uma sombra macia do
objeto inteiro. Entra pelo perfil calmo, como as peças. Os objetos prontos, neste
desenho, estão em `preview/objetos.png`.

## Cenas

As cenas-exemplo estão no `compose.py` do projeto: M1 a M3 são os registros com objeto
(objeto em destaque, processo e dado, de `pecas/receitas.py`); de M4 em diante, uma por
peça. Duas formas:

- **Tela cheia**: `P.fundo(...)` mais a peça. É o padrão.
- **Sobre o vídeo**: só a peça, sem fundo, no terço de cima (centro em y≈520), para o
  rosto ficar livre. É o caso do cartão (M7).

No `render.py`, **toda cena do Limpo vai com `cutaway=False`** no SHOTS. O `motion novo`
já deixa o exemplo assim. Com `True`, o acabamento do render tiraria a transparência e a
cena entraria em corte seco.

## Legenda

**Etiqueta**: Inter 700 na cor do texto, numa caixa da `cor.superficie` (94% opaca, cantos
arredondados, sombra curta). Blocos de até 4 palavras e ~0,55 s; entrada em fade curto
(~4 quadros). A palavra de destaque (no máximo 2 por clipe, configuradas no `destaque`
do `CAP.configurar`) troca a caixa pela pílula do acento.

**Por que caixa, e não texto branco com sombra** (rascunho do clip-010, 2026-10-22): a
camisa do falante era branca, e o texto branco com sombra sumia nela. A caixa lê sobre
qualquer roupa e repete o cartão das cenas. A vírgula do fim do bloco sai da caixa.

## O que não entra

Escolhas que puxam o Limpo para o "template de SaaS" que a pesquisa apontou:

- gradiente roxo→azul, borda brilhante (border beam), glow, glassmorphism;
- emoji, ícone 3D, partícula, fundo animado atrás do rosto;
- efeito em loop que não está preso a uma palavra;
- texto de apoio abaixo de 45 px, ou qualquer texto abaixo de 30 px.

## Calibração

Os números do perfil calmo são o ponto de partida dos guias de motion. O que for
calibrado em produção (aprovado ou reprovado pelo Diretor) entra aqui, com o porquê,
como o Papel fez na `IDENTIDADE.md`.
