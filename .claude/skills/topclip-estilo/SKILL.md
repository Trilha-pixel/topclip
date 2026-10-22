---
name: topclip-estilo
description: Cria o estilo de motion da própria pessoa (cores, fontes, energia e legenda da marca dela) ou remixa um estilo oficial do TopClip (Papel, Limpo, Impacto, Luxo), e cuida dos estilos dela — ajustar, aprovar, exportar, importar e apagar. Use quando o pedido for "cria o meu estilo", "quero o motion com a cara da minha marca", "usa as cores do meu Instagram", "faz um estilo parecido com o Limpo mas laranja", "remixa o Impacto", "exporta meu estilo", "importa esse estilo que me mandaram" ou "qual estilo combina comigo". NÃO use para fazer o motion de um clipe (isso é topclip-motion, que já recebe o estilo pronto).
allowed-tools:
  - Read
  - Write
  - Glob
  - AskUserQuestion
  - Bash(./topclip *)
  - Bash(ffprobe *)
---

# Criar e cuidar do estilo da pessoa

> Parte do **TopClip**. Todo comando roda da raiz, pelo `./topclip`. Formato do pacote e
> regras dos estilos: `docs/proposta-estilos.md` (seções 5 a 10 e 16).

Um estilo é uma **pasta**: `estilo.json` (nome, energia, variações), `tokens.json` (cores,
fontes, movimento, tipografia), `legenda.json` e a galeria em `preview/`. Os oficiais
ficam em `biblioteca/estilos/` e **nunca são editados**. Os da pessoa ficam em
`minha-biblioteca/estilos/`, fora do git. Ela já tem 10 peças (contador, marca-texto,
troca de palavra, desfoque, cascata, antes e depois, cartão, Lottie, moldura e brilho),
que vestem qualquer estilo sozinhas. Criar um estilo é **escolher números**, não escrever
código.

Público leigo: fale de "cor de destaque", "fonte dos títulos" e "energia", nunca de
token ou JSON. Mostre imagem antes de pedir decisão.

## O fluxo (criar o estilo dela)

### 1. Insumos — todos opcionais

Peça o que a pessoa tiver, de uma vez:

- **prints** de 2 ou 3 posts dela, o **logo** ou fotos da marca (para a paleta);
- **um clipe dela** (o vertical de um projeto, ou o vídeo bruto), para as amostras;
- **3 adjetivos** da marca e **o que ela não quer** ("nada de dourado", "nada infantil").

Sem prints, a paleta sai das respostas. Sem clipe, use o de algum projeto em `projetos/`
(os verticais ficam em `projetos/<nome>/clipes-verticais/`).

### 2. Paleta — local e grátis

```bash
./topclip estilo paleta print1.png print2.png logo.png --para <id>
```

Sai a paleta dominante (k-means) com fundo, texto e acento sugeridos e o contraste de
cada um. O texto precisa de 4,5:1 contra o fundo; o acento, de preferência 3:1.

### 3. Até 5 perguntas — AskUserQuestion, com opções

1. **Energia:** calma (Limpo, Luxo), editorial (Papel) ou enérgica (Impacto)?
2. **Base:** qual oficial chega mais perto? Mostre `biblioteca/estilos/<id>/preview/capa.png`.
3. **Títulos:** fino e elegante, firme e limpo, ou pesado e em caixa alta?
4. **Legenda:** etiqueta discreta, texto grande com contorno, ou itálico com faixa?
5. **Fundo das telas cheias:** claro, escuro ou a cor da marca?

Pule a pergunta que os insumos já responderam.

### 4. Quatro direções, no clipe dela

Crie 4 rascunhos a partir das respostas. São quatro jeitos diferentes de ler a marca,
não quatro tons da mesma cor: mude a base, a energia ou o fundo.

```bash
./topclip estilo remixar limpo <id>-a --nome "Marca · A"
./topclip estilo ajustar <id>-a cor.fundo=#F4F1EA cor.texto=#111111 cor.acento=#FF5A1F
./topclip estilo remixar impacto <id>-b --nome "Marca · B"
./topclip estilo ajustar <id>-b cor.acento=#FF5A1F
# ...C e D
./topclip estilo amostra <id>-a <id>-b <id>-c <id>-d --video <clipe> --t <segundo com o rosto> \
    --texto "<uma frase dela>" --legenda "<outra frase>" --saida projetos/<nome>/estilo-direcoes.png
```

Mostre a folha das amostras (o quadro do clipe dela em cada direção, lado a lado) e
pergunte qual. **Apague as que ela não quis** (`./topclip estilo apagar <id>-c`) e renomeie
a escolhida com um remix limpo, se ela quiser um nome definitivo.

### 5. Ajuste fino

A pessoa fala em palavras e você traduz em `ajustar`:

| Ela diz | Chave |
| --- | --- |
| "o laranja mais escuro" | `cor.acento=#E04A10` |
| "título mais fino" | `tipografia.peso.titulo=400` |
| "tudo em maiúscula" | `tipografia.caixa_alta=true` |
| "contorno preto nas letras" | `tipografia.contorno=0.07 tipografia.cor_contorno=#000000` |
| "mais calmo" / "mais agitado" | `energia=calmo` / `energia=energico` |
| "entrar mais devagar" | `movimento.entrada_quadros=[18,24]` |
| "legenda maior" | `legenda.corpo=76` |
| "palavra destacada sem caixa" | `legenda.destaque_modo=texto` |
| "uma versão escura" | `variacao.escuro.nome=Escuro variacao.escuro.cor.fundo=#0A0A0A ...` |
| "nome / para quem é" | `nome="Felipe Top"` `bom_para=marketing,vendas` |

Fontes: só as do kit (`Archivo Narrow`, `Archivo Black`, `Anton`, `Permanent Marker`,
`IBM Plex Mono`, `Fraunces`, `Fraunces Italic`, `Inter`, `Playfair Display Italic`) ou um
arquivo `.ttf` livre (OFL, Apache ou UFL) dentro de `fontes/` do pacote, **com o arquivo de
licença ao lado**. Fonte comercial da pessoa nunca entra num pacote. Ela pode usar a fonte
dela pela marca (`minha-biblioteca/marca/`), que fica no computador dela.

Depois de cada rodada de ajustes, gere a amostra de novo e mostre.

### 6. Aprovar

```bash
./topclip estilo aprovar <id>
```

Valida tudo (contraste, fontes, licenças), renderiza todas as peças em todas as variações
na galeria (`preview/`) e fecha a versão: rascunho `0.x` vira `1.0.0`. Olhe a galeria antes
de dizer que ficou pronto: `minha-biblioteca/estilos/<id>/preview/`.

### 7. Usar

- **No próximo clipe:** `./topclip motion novo <pasta> --estilo <id>`. A skill
  `topclip-motion` lê o `estilo/ESTILO.md` do projeto.
- **Como padrão:** no painel, aba Biblioteca → o estilo → "usar como padrão". Isso grava
  `minha-biblioteca/preferencias.json`.
- **A marca** (logo e cores) entra por cima de qualquer estilo, nos espaços que ele libera
  (`slots_da_marca`). Ela é editada no painel, em Minha marca.

Escreva no `ESTILO.md` do estilo dela o que faz ele ser ele, em 5 linhas: base, acento,
fontes, energia e o que não entra. É o que o Diretor cobra quando ela fizer motion.

## Remixar um oficial

É o mesmo fluxo começando dos passos 5 e 6:

```bash
./topclip estilo remixar luxo luxo-da-clinica --nome "Luxo da Clínica"
```

## Compartilhar

```bash
./topclip estilo exportar <id>               # gera <id>.topclip-estilo (sem código, sem a marca)
./topclip estilo importar arquivo.topclip-estilo [--substituir]
```

O que se importa entra como "comunidade". A importação recusa:

- código;
- caminho estranho dentro do zip;
- mais de 25 MB;
- nome de estilo oficial;
- pacote inválido.

Estilo importado sem cenas próprias recebe as cenas-modelo das peças. No painel, dá para
importar arrastando o arquivo.

## O que nunca fazer

- Editar um estilo oficial (`biblioteca/estilos/`): remixe.
- Gravar estilo ou marca da pessoa fora de `minha-biblioteca/`.
- Pôr fonte sem licença livre num pacote, ou código num pacote para compartilhar.
- Aprovar sem olhar a galeria e uma amostra sobre roupa clara: legenda branca some em
  camisa branca, e já aconteceu duas vezes (`docs/proposta-estilos.md`, seção 16).
