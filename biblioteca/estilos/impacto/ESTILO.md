# Impacto

Caixa alta pesada, contorno preto, **um acento só** (amarelo, ou verde na variação) e
entrada em **pop**. É o estilo que o leigo pede pelo nome ("legenda pulando", Hormozi,
MrBeast). Bom para vendas, negócios, motivação, fitness e finanças.

Num projeto Impacto, **este arquivo manda sobre a `IDENTIDADE.md`** (que é do Papel). As
regras universais e a rubrica do Diretor continuam valendo
(`docs/proposta-estilos.md`, seção 7) — inclusive as que seguram a energia.

## O que faz o Impacto ser o Impacto

1. **Tipografia que grita.** Archivo Black para tudo que se lê e Anton para número, sempre
   em caixa alta, com **contorno preto** (7% do corpo) e **sombra dura** para baixo. Isso
   vem da `tipografia` do `tokens.json`: toda peça escreve assim sozinha.
2. **Um acento por cena.** Amarelo `#FFE600` (ou verde `#22D65A`). O vermelho `alerta`
   existe para o "não" e aparece no máximo uma vez por clipe.
3. **Pop.** Perfil enérgico: a peça nasce pequena, passa do tamanho (~110%) e assenta, em
   4–7 quadros. Saída em 2–4 quadros. Nada desliza: o pop já é o gesto.
4. **Sobre o vídeo ou tela preta.** Frase e cartão vão por cima do vídeo, no terço de cima
   (o rosto fica livre). Número grande vai em tela cheia preta (`P.fundo`).
5. **Legenda de 1–2 palavras**, caixa alta, contorno de 8 px e sombra dura, entrando em
   pop. A palavra de destaque (até 3 por clipe) muda de cor para o acento — sem pílula.

## Cenas

As cenas-exemplo estão no `compose.py` do projeto. Toda cena do Impacto é **overlay**
(`cutaway=False` no SHOTS do render.py); o `motion novo` já deixa o exemplo assim.

## O que segura o Impacto

O Impacto é o estilo mais perto do "template genérico" que a pesquisa apontou (o padrão de
Opus, Submagic e CapCut). O que o diferencia é a âncora: **cada pop cai numa palavra do
transcript**. Por isso:

- nada entra "para dar dinâmica": evento sem palavra não entra;
- no máximo 3 flashes por segundo e nada de tremer a tela inteira (WCAG 2.3.1);
- um movimento expressivo de cada vez — pop em três coisas juntas vira barulho;
- sem emoji, sem neon, sem glow, sem gradiente.
