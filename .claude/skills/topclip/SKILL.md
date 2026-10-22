---
name: topclip
description: Fluxo completo do TopClip — de um vídeo longo (podcast, entrevista, live, aula), arquivo no computador ou link do YouTube/Instagram, até clipes verticais 9:16 com motion editorial e legenda queimada, prontos para Shorts, Reels e TikTok. Use quando o pedido for o pacote inteiro ("faz os cortes com motion", "transforma esse podcast em clipes prontos", "/topclip video.mp4", "/topclip https://youtube.com/..."), ou quando não estiver claro por qual etapa começar. Para só cortar, use topclip-corte; para só pôr motion num clipe que já existe, use topclip-motion.
allowed-tools:
  - Agent
  - Read
  - Write
  - Grep
  - Glob
  - Bash(./topclip *)
  - Bash(ffprobe *)
  - Bash(ffmpeg *)
---

# TopClip — do vídeo longo ao clipe pronto

Duas skills em sequência, cada uma com seus portões:

```text
vídeo longo ──► topclip-corte ──► clip-vertical.mp4 limpo + timing por palavra ──► topclip-motion ──► master final
                 momentos → cortes → vertical → entrega        ancorar → assets → compor → legenda → render
```

Todo caminho é relativo à raiz do repositório e todo comando passa por `./topclip`.

## 0. Antes de tudo

```bash
./topclip verificar
```

Se acusar falta, rode `./topclip instalar` e verifique de novo. Não comece com
instalação incompleta: o pipeline quebra no meio, depois de já ter gasto a transcrição.

## 1. Projeto

Um vídeo, uma pasta: `projetos/<nome-do-video>/` (minúsculas, hífen, sem acento).
A pasta `projetos/` fica fora do git — nada do usuário sobe para o repositório.

```text
projetos/<nome>/
  projeto.json     nome e caminho do vídeo (o painel cria); veio de link: `link` e `legenda`
  video.mp4        o vídeo baixado, quando o projeto veio de um link
  legenda.*.vtt    a legenda automática do YouTube, com tempo por palavra (quando havia)
  escolhas.json    o que o usuário marcou no painel (momentos, cortes)
  runs/            as runs da topclip-corte (--workspace aponta aqui)
  motion/<clipe>/  um projeto da topclip-motion por clipe aprovado
  entregas/        os masters finais, um .mp4 por clipe
```

**Chamado com uma pasta** (`/topclip projetos/<nome>`): o projeto já existe, criado
pelo painel. Leia `projeto.json` — o vídeo está em `video`. Chamado com um vídeo:
crie a pasta e o `projeto.json` (`{"nome", "video", "criado"}`) você mesmo, para o
projeto aparecer no painel.

**Vídeo de link (YouTube, Instagram).** Nunca peça para a pessoa baixar à mão:

```bash
./topclip baixar <link>                    # cria projetos/<título-do-vídeo>/ e baixa
./topclip baixar projetos/<nome>           # projeto criado no painel com link (tem `link`, `video` vazio)
```

O segundo também serve quando o painel já começou o download: ele espera terminar
em vez de baixar de novo, e com o vídeo já baixado só confirma. A saída termina em
`PROJETO=`, `VIDEO=` e, no YouTube, `LEGENDA=` — use esses caminhos. Vai até 1080p
(H.264 quando o site oferece), que é a fonte para a qual o enquadramento foi
calibrado. Em vídeo longo leva alguns minutos: rode em segundo plano e anote no
painel; o avanço do download aparece sozinho na Atividade.

Com `LEGENDA=` (legenda automática do YouTube no idioma do vídeo), passe-a como
transcript no `init` da topclip-corte: o timing por palavra vem pronto e a
transcrição pelo Whisper, a etapa mais lenta da fase 1, é pulada
(`fases/1-momentos.md`, seção 2).

Se falhar, a mensagem já diz o que fazer. A comum no Instagram e no "confirme que
não é um robô" do YouTube é pedir login: rode de novo com
`--cookies-do-navegador chrome` (ou `safari`, `firefox`) — **só com o ok da pessoa**,
porque o yt-dlp lê os cookies do navegador dela e o macOS pede a senha do chaveiro.

## O painel

`./topclip painel` abre uma interface local (http://127.0.0.1:7777) onde o usuário
vê os momentos, assiste os cortes e **marca o que quer** — sem digitar horário no
chat. Em cada portão, diga as duas opções: escolher aqui na conversa ou no painel.

Quando ele disser que escolheu no painel, leia `projetos/<nome>/escolhas.json`:

```json
{"momentos": ["moment-001", "moment-004"], "cortes": ["clip-002"], "atualizado": "..."}
```

Os ids são os de `05-viral-moments.json` e `06-candidates.json`. Confirme em uma
linha o que vai seguir ("seguindo com 2 momentos: …") e continue só com eles. Lista
vazia ou arquivo ausente: pergunte, não presuma.

**Voltando depois para fazer o resto.** É comum fazer 2 de 14 cortes, postar e
voltar outro dia — numa conversa nova, só com "escolhi no painel, pode seguir". Sem
projeto dito, é o de `escolhas.json` atualizado por último em `projetos/*/`. O painel
marca como **pronto** o corte que já tem entrega (`entregas/<clip-id>-….mp4`) e não
deixa marcá-lo de novo: `cortes` traz só os novos. Siga com eles na **mesma run**, a
partir da fase 3 (vertical) — os cortes e as prévias já existem. Não refaça nem
sobrescreva o que está em `entregas/`.

### Narre o que está fazendo — o painel mostra ao vivo

O painel tem uma caixa **Atividade** que diz se o TopClip está trabalhando, com uma
barra de % por etapa (momentos, cortes, vertical, motion, entrega) e o log de cada uma.
Os comandos `./topclip corte …`, `./topclip motion transcrever …` e os scripts do motion
rodados por `./topclip py projetos/<nome>/motion/<clipe>/render.py` se registram sozinhos
(início, fim, duração, erro) e os longos enchem a barra (transcrição, prévias,
enquadramento, render, render do motion). O % da etapa sai dos arquivos que cada passo
grava. O que **você** faz entre os comandos — subagente lendo, decisão, espera — só
aparece se você anotar, dizendo a etapa:

```bash
./topclip log projetos/<nome> --etapa momentos "Clip Hunter procurando momentos que funcionam fora de contexto"
```

Anote ao começar cada etapa e cada subagente, e ao parar num portão ("momentos
prontos — esperando sua escolha"). Uma linha curta, em português de gente, sem jargão
de arquivo. Sem `--etapa`, a linha herda a etapa da anterior — e a primeira notícia de
uma etapa nova cai no log da velha. Sem anotar, a pessoa vê o painel parado enquanto
você trabalha e acha que travou.

## 2. Cortes — skill `topclip-corte`

Invoque a skill `topclip-corte` com o vídeo e `--workspace projetos/<nome>/runs`.
Ela tem quatro portões (momentos, cortes, vertical, entrega). **Respeite cada um:**
pare, mostre, espere o usuário escolher. Só emende as fases quando ele pedir
("vai até o fim", "manda o pacote todo").

O que mais pesa no tempo é **quantos momentos ele escolhe**. Cada momento mostra
uma nota estimada, a mesma conta do gate final (mínimo 7,5), e o painel lista em
ordem de nota: recomende escolher **de 2 a 5**. Na run de teste ele marcou 14 para
usar 2 — a fase de cortes levou 41 min, e a nota baixa dos 2 escolhidos só apareceu
no fim. Na fase de cortes, o Clip Builder monta só os escolhidos, as prévias
saem logo depois para ele já assistir, e a revisão cega e a de feed rodam juntas,
gerando um único rebuild (`topclip-corte`, `fases/2-cortes.md`).

Saída por clipe: `clip-vertical.mp4` limpo (sem legenda, sem motion) e
`captions.srt`/`.ass` com o timing por palavra.

## 3. Motion — skill `topclip-motion`

Para cada clipe que o usuário aprovou na entrega dos cortes:

```bash
./topclip motion novo projetos/<nome>/motion/<clipe>
cp <run>/output/.../clip-vertical.mp4 projetos/<nome>/motion/<clipe>/00_brief/fonte.mp4
```

Depois invoque a skill `topclip-motion` sobre esse projeto. A transcrição do motion
é **do clipe**, não do episódio: gere com `./topclip motion transcrever`.

**Estilo:** sem pedido do usuário, é o Papel. Pedido outro: `--estilo <id>` no
`motion novo` (`./topclip estilo listar` mostra os disponíveis).

**Assets:** procure primeiro em `biblioteca/assets/` e `minha-biblioteca/assets/`. O
que não existir, o Claude desenha em código (seção 3 da `topclip-motion`). Todo asset
novo aprovado vai para `minha-biblioteca/assets/` com uma linha no
`minha-biblioteca/MANIFESTO.md` — é assim que o próximo vídeo começa com mais coisa
pronta, sem mexer em arquivo do repositório.

Mostre o plano de motion (frases escolhidas e recusadas) antes de compor. É o portão
desta etapa.

Para ganhar tempo: comece cada cena pela receita do registro dela
(`topclip-motion/referencias/receitas.md` — o `compose.py` já traz um exemplo pronto de
cada), revise pelos `<cena>_ESTADOS.png` e pelo `render.py --rascunho`, e monte o master
final (`render.py`, x264 slow) **uma vez**, depois da revisão aprovada.

## 4. Entrega

Copie cada master verificado (`12_master/MASTER_v01.mp4` — nunca o `RASCUNHO.mp4`,
que é só para revisão) para `projetos/<nome>/entregas/<clipe>.mp4` e mostre a
lista ao usuário com duração e o caminho de cada um. Não declare sucesso sem a
verificação do master (duração, cadência e MD5 do áudio contra a fonte).

## O que nunca fazer

- Nunca prometer "viral garantido". O sistema estima publicabilidade; desempenho real
  exige teste na plataforma.
- Nunca inventar fala nem alterar o sentido do que foi dito.
- Nunca gerar vídeo com IA de vídeo. O motion é composição em camadas.
