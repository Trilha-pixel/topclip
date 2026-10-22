# Luxo

Serifa de display **fina**, latão sobre preto, filete Art Deco e movimento **lento**. O
"luxo de coach" preto e dourado virou clichê; o que deixa este atual é o Deco (Neo Deco,
Pinterest Predicts 2026) e a contenção. Bom para mentoria, imóveis, estética, moda e alto
padrão. Três variações: **latão** (preto), **bordô** e **marfim** (claro).

Num projeto Luxo, **este arquivo manda sobre a `IDENTIDADE.md`** (que é do Papel). As
regras universais e a rubrica do Diretor continuam valendo
(`docs/proposta-estilos.md`, seção 7).

## O que faz o Luxo ser o Luxo

1. **Fraunces fina** (380 nos títulos, 300 nos números) para o que importa; Inter 400 no
   apoio; rótulo em Inter caixa alta com espaçamento largo (0,3 do corpo). Os pesos e o
   espaçamento vêm da `tipografia` do `tokens.json`: a peça pede 700, o estilo entrega fino.
2. **Latão como único acento**: filete, sublinhado, reflexo, número. Nunca dourado
   chapado em bloco grande — é linha e luz, não tinta.
3. **Movimento lento**: perfil calmo esticado (entrada de 16–22 quadros, saída de 10–13,
   stagger de 4), deslocamento curto (18 px). Sem pop, sem overshoot.
4. **Assinaturas**: a `moldura` (filete duplo que se desenha, com leques Deco nos cantos),
   o `brilho` (reflexo que passa uma vez no título) e as faixas de `cinema` (letterbox)
   quando a cena fica sobre o vídeo.
5. **Legenda** em Playfair Itálica, marfim, numa **faixa preta translúcida** (62%),
   entrando em fade de 0,25 s. O destaque fica na mesma faixa e muda a cor da palavra
   para o latão. Sem a faixa (só sombra macia), a itálica fina sumia na camisa branca do
   clip-010 — rascunho de 2026-10-22.

## Cenas

As cenas-exemplo estão no `compose.py` do projeto. Toda cena do Luxo é **overlay**
(`cutaway=False` no SHOTS); o `motion novo` já deixa o exemplo assim. Tela cheia usa
`P.fundo`; sobre o vídeo, `P.cinema` dá o tom de filme sem cobrir o rosto.

## O que não entra

- dourado metálico realista, brilho em loop, partícula, lens flare;
- serifa pesada (o Luxo é fino) e mais de uma moldura por cena;
- tudo que corre: se a cena precisa de pressa, o estilo é o Impacto.
