---
name: topclip-post
description: Posts virais do TopClip — frases fortes tiradas da transcrição do vídeo, divididas em 2 ou 3 prints do rosto da pessoa, com o texto branco e as palavras-chave em negrito, para o feed do Instagram (4:5) ou os stories (9:16), em post único ou carrossel, com a legenda do post pronta para copiar. Use quando o pedido for "faz os posts virais", "post de frase", "frases do vídeo com print", "posts com o rosto e a frase", "post estilo Alfredo Soares", "carrossel de frases", "escreve as legendas dos posts", "transforma o podcast em posts de frase", ou uma frase própria (um salmo, uma citação) com os prints do vídeo. NÃO faz vídeo (isso é topclip-corte e topclip-motion).
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash(./topclip *)
---

# TopClip — posts virais

Do vídeo longo saem também posts de imagem: a frase dividida em prints do rosto, um
print por parte, como os posts de frase que viralizam no Instagram — um post por frase
ou um carrossel com uma frase por slide.

```text
transcrição ──► o Claude escolhe 14 frases ──► ./topclip post prints ──► painel: a pessoa escolhe, edita e baixa
               e escreve as legendas            (os melhores rostos)       (Projeto → Posts virais)
               (posts/frases.json)
```

**A sua parte é escolher as frases e escrever as legendas.** O resto — post único ou
carrossel, a ordem dos slides, a capa, trocar print (ou subir uma foto dela), editar o
texto e a legenda, pôr negrito, trocar a fonte, o formato, o número de prints, P&B, a
assinatura com o @, baixar o PNG ou o ZIP — a pessoa faz no painel, na hora, sem voltar à
conversa. Todo comando passa por `./topclip`, da raiz.

## 1. A transcrição

```bash
./topclip post texto projetos/<nome>            # a transcrição em linhas: [mm:ss–mm:ss] (segundos) fala
./topclip post texto projetos/<nome> --de 10:00 --ate 20:00
```

Usa a transcrição da run de cortes (`runs/*/02-transcript.json`) quando ela existe: com
os cortes já feitos, não transcreva de novo. Sem nenhuma, transcreva antes — em vídeo
longo leva minutos, então rode em segundo plano e anote no painel:

```bash
./topclip post transcrever projetos/<nome>
./topclip log projetos/<nome> --etapa posts "transcrevendo o vídeo para achar as frases dos posts"
```

Vídeo de link ainda não baixado: `./topclip baixar projetos/<nome>` primeiro (skill
`topclip`, "Vídeo de link").

## 2. Escolher as 14 frases

Leia a transcrição **inteira** — frase boa aparece no meio de explicação comprida — e
escolha **14**. Anote no painel ao começar (`--etapa posts`).

**O que faz uma frase de post:**

- **Funciona sozinha.** Quem rola o feed não viu o vídeo: nada de "isso", "ele",
  "essa parte", "como eu disse".
- **Cabe em 2 ou 3 prints.** Cerca de 8 a 22 palavras no total. Em 2 prints, cada parte
  com até ~64 letras; em 3, até ~46 — o `conferir` avisa quando passa.
- **Tem forma de post viral.** Contraste ("Seja obcecado pelo processo. / O resultado vira
  consequência."), virada (a parte 1 abre a tensão, a última fecha), verdade dura,
  conselho direto, número concreto, pergunta que incomoda, inspiração. Prefira as que
  se dividem sozinhas em duas metades espelhadas.
- **Varia.** Misture os tipos, espalhe pelo vídeo inteiro e não repita a mesma ideia —
  elas também viram os slides de um carrossel, e juntas contam o assunto.
- **Fica de fora:** propaganda e merchan (links, cupom, "entra no clube"), frase que só
  faz sentido com a imagem do vídeo, palavrão, ataque a terceiros.

**Lapidar sem mudar o sentido.** Fala não sai pronta: tire muleta ("então", "tipo",
"né", "cara"), troque "vocês" por "você", acerte a concordância, encurte. Corrija o que a
transcrição errou (nome de marca, termo técnico) pelo contexto. **Nunca invente ideia nem
troque o sentido** — o trecho literal vai em `original`, para a pessoa conferir.

**Dividir.** Escreva a divisão em 2 e em 3 partes. Cada parte é uma oração inteira
sempre que der; nunca corte nome, número ou expressão ("dor de cabeça") ao meio.

**Negrito.** Uma a quatro palavras por parte, as que carregam o sentido: o contraste, o
verbo forte, o número ("Quanto **mais barato** você vende, / **piores** são os seus
clientes."). Quase nunca a parte inteira.

**A legenda de cada frase.** O texto que vai embaixo do post no Instagram, pronto para
copiar (no painel, um clique copia):

- **Não repete a frase do post** — complementa. A primeira linha é o gancho (é o que
  aparece antes do "mais"); depois, uma ou duas frases curtas com a ideia do vídeo.
- **Na voz da pessoa**, "você" para quem lê; história dela em primeira pessoa.
- **Fecha com uma chamada** simples: salvar, mandar para alguém, comentar uma palavra.
- **Até 5 hashtags**, no fim (o Instagram limita); 3 de nicho costumam bastar.
- Curta: 2 a 4 parágrafos, cerca de 300 a 600 letras (o teto é 2.200).
- Nunca prometer resultado, inventar número ou pôr link (legenda do Instagram não tem
  link clicável).

**O carrossel.** Escreva também o bloco `carrossel`. Quem escolhe as frases e a ordem
dos slides é a pessoa, então os dois textos precisam servir para qualquer seleção:

- `capa`: o título do slide de capa, curto (até ~60 letras), com **negrito** na palavra
  que promete. Sem número ("5 verdades…"): ela pode escolher 3 ou 8 frases.
  Ex.: "O que ninguém te conta sobre **cobrar caro**".
- `legenda`: a legenda do carrossel, sobre o assunto do vídeo, com "arrasta para o lado"
  ou "salva para ler depois" e uma pergunta no fim. As mesmas regras da legenda acima.

## 3. O arquivo `projetos/<nome>/posts/frases.json`

```json
{"versao": 1,
 "carrossel": {"capa": "O que ninguém te conta sobre **cobrar caro**",
               "legenda": "Preço não é só número: (…)\n\nArrasta para o lado e salva.\n\n#precificacao #freelancer"},
 "frases": [
  {"id": "frase-001", "tipo": "contraste", "inicio": 300.7, "fim": 310.1,
   "original": "vocês não estão vendendo preço, (…) vocês não estão vendendo um site, vocês têm que vender uma solução",
   "partes": {"2": ["Você não está **vendendo um site.**", "Está vendendo **confiança e resultado.**"],
              "3": ["Você não está", "**vendendo um site.**", "Está vendendo **confiança e resultado.**"]},
   "porque": "troca o produto pelo valor — a virada que o público dele precisa ouvir",
   "legenda": "Ninguém acorda querendo “um site”.\n\nA pessoa quer mais clientes, mais confiança, mais resultado. O site é só o caminho.\n\nMuda o discurso e o seu orçamento muda junto.\n\n#vendas #criacaodesites #freelancer"}
]}
```

- `tipo`: `contraste`, `provocacao`, `conselho`, `verdade_dura`, `pergunta`,
  `inspiracao`, `historia` ou `numero` (vira a etiqueta no painel).
- `inicio` e `fim`: os segundos do trecho original (o número entre parênteses do
  `texto`). É perto deles que os prints são procurados — errar aqui dá print de outro
  momento. Quando as partes vêm de momentos distantes, diga quando cada uma foi dita:
  `"tempos": {"3": [1514.5, 1517.0, 1536.8]}`.
- `porque`: uma linha, sem jargão — aparece para a pessoa no painel.
- `legenda`: texto com `\n` entre os parágrafos.
- Negrito entre `**…**`, dentro do texto da parte e do título da capa.

Depois:

```bash
./topclip post conferir projetos/<nome>        # formato, tamanho das partes, negrito, legendas e hashtags
./topclip post prints projetos/<nome>          # ~30 s numa aula de 36 min, 1080p
```

O `prints` lê o vídeo em volta de cada frase, dá nota a cada quadro (rosto, nitidez, olho
aberto, sorriso) e escolhe os prints de cada post, todos diferentes entre si. Também
monta o **banco**: os melhores rostos do vídeo inteiro, para as frases da pessoa e para a
capa do carrossel. Frase nova no frases.json? Rode de novo: só as novas são lidas.
`--refazer` começa do zero. As fotos que a pessoa subiu pelo painel nunca são apagadas.

Projeto que já tem as frases e só falta a legenda ("escreve as legendas dos posts"):
acrescente `legenda` em cada frase e o bloco `carrossel` no mesmo frases.json, sem mexer
no resto, e rode o `conferir`. O painel mostra sozinho; a legenda que a pessoa já editou
lá continua valendo.

## 4. Conferir e entregar

Olhe duas ou três artes antes de chamar a pessoa:

```bash
./topclip post render projetos/<nome> --frase frase-001 --frase frase-007
```

O PNG sai em `posts/prontos/`: abra com o Read. Confira se o rosto aparece inteiro, se o
texto lê bem e se a divisão ficou natural. Frase sem rosto por perto (o `prints` avisa)
usa o banco — diga isso.

Então avise, em uma linha, e anote no painel: as frases estão no painel, em **Projeto →
Posts virais**. Lá a pessoa marca as que quer, escolhe post único ou carrossel e ajusta
tudo; os PNG (ou o ZIP do carrossel, numerado na ordem dos slides e com a legenda junto)
baixam direto e ficam também em `posts/prontos/`.

## Pedidos na conversa

O padrão de tudo é o que a pessoa escolheu no painel (`posts/posts.json`); sem escolha,
post único no feed com 2 prints (stories com 3), DM Sans, fotos coloridas, sem assinatura.
As opções do `render` valem só para aquela vez:

- **Formato, prints, fonte:** `./topclip post render projetos/<nome> --frase <id>
  --formato stories --prints 3 --fonte fraunces` (`./topclip post fontes` lista as fontes).
- **Carrossel:** `./topclip post render projetos/<nome> --carrossel --frase frase-003
  --frase frase-001 --frase frase-009` — um slide por frase, na ordem pedida (sem
  `--frase`: as escolhidas no painel, na ordem de lá). Sai em `posts/prontos/carrossel/`
  (`01-capa.png`, `02-…` e a `legenda.txt`). A capa usa o título do frases.json;
  `--capa "Outro **título**"` troca, `--sem-capa` tira. Só no feed (1080×1350); o
  Instagram aceita até 20 slides.
- **P&B:** `--pb` (as fotos em preto e branco; o texto e o destaque continuam) ou `--cor`.
- **Assinatura:** `--assinatura` põe o @ da marca dela, pequeno, embaixo do texto do
  último print. O @ vem de Biblioteca → Minha marca (`minha-biblioteca/marca/marca.json`,
  campo `arroba`); sem @ cadastrado, peça para ela preencher lá.
- **Uma frase dela** (um salmo, uma frase que ela tem): `./topclip post minha
  projetos/<nome> "O Senhor é o meu pastor; nada me faltará." --referencia "Salmos 23:1"`.
  Entra já escolhida, com prints do banco (sem banco, rode o `prints` antes).
- **Uma foto dela** no lugar de um print: é no painel — clicar na miniatura do print,
  "subir foto". A foto fica em `posts/prints/` do projeto (f-0001…), o rosto é detectado
  como nos outros, e ela aparece em "suas fotos" para todos os posts.
- **Editar texto, legenda, negrito, ordem, trocar print, reposicionar a foto:** é no
  painel. Pela conversa, edite a frase no `frases.json` (o painel mostra a versão nova; o
  que a pessoa já editou lá continua valendo).

## O que nunca fazer

- Nunca inventar fala nem mudar o sentido do que a pessoa disse.
- Nunca usar foto que não seja do próprio vídeo (ou que ela mandou).
- Nunca prometer viralizar: é um formato que costuma ir bem, não uma garantia — nem na
  conversa, nem na legenda.
- Nunca mais de 5 hashtags numa legenda.
