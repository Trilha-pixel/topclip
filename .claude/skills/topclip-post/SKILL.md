---
name: topclip-post
description: Posts virais do TopClip — frases fortes tiradas da transcrição do vídeo, divididas em 2 ou 3 prints do rosto da pessoa, com o texto branco e as palavras-chave em negrito, para o feed do Instagram (4:5) ou os stories (9:16). Use quando o pedido for "faz os posts virais", "post de frase", "frases do vídeo com print", "posts com o rosto e a frase", "post estilo Alfredo Soares", "transforma o podcast em posts de frase", ou uma frase própria (um salmo, uma citação) com os prints do vídeo. NÃO faz vídeo (isso é topclip-corte e topclip-motion) e ainda não faz carrossel.
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash(./topclip *)
---

# TopClip — posts virais

Do vídeo longo saem também posts de imagem: a frase dividida em prints do rosto, um
print por parte, como os posts de frase que viralizam no Instagram.

```text
transcrição ──► o Claude escolhe 14 frases ──► ./topclip post prints ──► painel: a pessoa escolhe, edita e baixa
               (posts/frases.json)              (os melhores rostos)       (Projeto → Posts virais)
```

**A sua parte é só escolher as frases.** O resto — trocar print, editar o texto, pôr
negrito, trocar a fonte, o formato e o número de prints, baixar o PNG — a pessoa faz no
painel, na hora, sem voltar à conversa. Todo comando passa por `./topclip`, da raiz.

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
- **Varia.** Misture os tipos, espalhe pelo vídeo inteiro e não repita a mesma ideia.
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

## 3. O arquivo `projetos/<nome>/posts/frases.json`

```json
{"versao": 1, "frases": [
  {"id": "frase-001", "tipo": "contraste", "inicio": 300.7, "fim": 310.1,
   "original": "vocês não estão vendendo preço, (…) vocês não estão vendendo um site, vocês têm que vender uma solução",
   "partes": {"2": ["Você não está **vendendo um site.**", "Está vendendo **confiança e resultado.**"],
              "3": ["Você não está", "**vendendo um site.**", "Está vendendo **confiança e resultado.**"]},
   "porque": "troca o produto pelo valor — a virada que o público dele precisa ouvir"}
]}
```

- `tipo`: `contraste`, `provocacao`, `conselho`, `verdade_dura`, `pergunta`,
  `inspiracao`, `historia` ou `numero` (vira a etiqueta no painel).
- `inicio` e `fim`: os segundos do trecho original (o número entre parênteses do
  `texto`). É perto deles que os prints são procurados — errar aqui dá print de outro
  momento. Quando as partes vêm de momentos distantes, diga quando cada uma foi dita:
  `"tempos": {"3": [1514.5, 1517.0, 1536.8]}`.
- `porque`: uma linha, sem jargão — aparece para a pessoa no painel.
- Negrito entre `**…**`, dentro do texto da parte.

Depois:

```bash
./topclip post conferir projetos/<nome>        # formato, tamanho de cada parte, negrito
./topclip post prints projetos/<nome>          # ~30 s numa aula de 36 min, 1080p
```

O `prints` lê o vídeo em volta de cada frase, dá nota a cada quadro (rosto, nitidez, olho
aberto, sorriso) e escolhe os prints de cada post, todos diferentes entre si. Também
monta o **banco**: os melhores rostos do vídeo inteiro, para as frases da pessoa. Frase
nova no frases.json? Rode de novo: só as novas são lidas. `--refazer` começa do zero.

## 4. Conferir e entregar

Olhe duas ou três artes antes de chamar a pessoa:

```bash
./topclip post render projetos/<nome> --frase frase-001 --frase frase-007
```

O PNG sai em `posts/prontos/`: abra com o Read. Confira se o rosto aparece inteiro, se o
texto lê bem e se a divisão ficou natural. Frase sem rosto por perto (o `prints` avisa)
usa o banco — diga isso.

Então avise, em uma linha, e anote no painel: as frases estão no painel, em **Projeto →
Posts virais**. Lá a pessoa marca as que quer e ajusta tudo; os PNG baixam direto e
ficam também em `posts/prontos/`.

## Pedidos na conversa

- **Formato, prints, fonte:** `./topclip post render projetos/<nome> --frase <id>
  --formato stories --prints 3 --fonte fraunces` (`./topclip post fontes` lista as fontes).
  O padrão é o que a pessoa escolheu no painel (`posts/posts.json`); sem escolha, feed
  com 2 prints, stories com 3, Inter.
- **Uma frase dela** (um salmo, uma frase que ela tem): `./topclip post minha
  projetos/<nome> "O Senhor é o meu pastor; nada me faltará." --referencia "Salmos 23:1"`.
  Entra já escolhida, com prints do banco (sem banco, rode o `prints` antes).
- **Editar texto, negrito, trocar print, reposicionar a foto:** é no painel. Pela conversa,
  edite a frase no `frases.json` (o painel mostra a versão nova; o que a pessoa já editou
  lá continua valendo).

## O que nunca fazer

- Nunca inventar fala nem mudar o sentido do que a pessoa disse.
- Nunca usar foto que não seja do próprio vídeo (ou que ela mandou).
- Nunca prometer viralizar: é um formato que costuma ir bem, não uma garantia.
- Ainda não existe: carrossel, legenda pronta do post, P&B, assinatura @ (fase 2).
