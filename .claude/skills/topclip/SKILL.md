---
name: topclip
description: Fluxo completo do TopClip — de um vídeo longo (podcast, entrevista, live, aula) até clipes verticais 9:16 com motion editorial e legenda queimada, prontos para Shorts, Reels e TikTok. Use quando o pedido for o pacote inteiro ("faz os cortes com motion", "transforma esse podcast em clipes prontos", "/topclip video.mp4"), ou quando não estiver claro por qual etapa começar. Para só cortar, use topclip-corte; para só pôr motion num clipe que já existe, use topclip-motion.
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
  projeto.json     nome e caminho do vídeo (o painel cria)
  escolhas.json    o que o usuário marcou no painel (momentos, cortes)
  runs/            as runs da topclip-corte (--workspace aponta aqui)
  motion/<clipe>/  um projeto da topclip-motion por clipe aprovado
  entregas/        os masters finais, um .mp4 por clipe
```

**Chamado com uma pasta** (`/topclip projetos/<nome>`): o projeto já existe, criado
pelo painel. Leia `projeto.json` — o vídeo está em `video`. Chamado com um vídeo:
crie a pasta e o `projeto.json` (`{"nome", "video", "criado"}`) você mesmo, para o
projeto aparecer no painel.

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

### Narre o que está fazendo — o painel mostra ao vivo

O painel tem uma caixa **Atividade** que diz se o TopClip está trabalhando. Os comandos
`./topclip corte …` e `./topclip motion transcrever …` se registram sozinhos (início,
fim, duração, erro) quando um argumento aponta para `projetos/<nome>`. O que **você**
faz entre eles — subagente lendo, decisão, espera — só aparece se você anotar:

```bash
./topclip log projetos/<nome> "Clip Hunter procurando momentos que funcionam fora de contexto"
```

Anote ao começar cada etapa e cada subagente, e ao parar num portão ("momentos
prontos — esperando sua escolha"). Uma linha curta, em português de gente, sem jargão
de arquivo. Sem isso, a pessoa vê o painel parado enquanto você trabalha e acha que travou.

## 2. Cortes — skill `topclip-corte`

Invoque a skill `topclip-corte` com o vídeo e `--workspace projetos/<nome>/runs`.
Ela tem quatro portões (momentos, cortes, vertical, entrega). **Respeite cada um:**
pare, mostre, espere o usuário escolher. Só emende as fases quando ele pedir
("vai até o fim", "manda o pacote todo").

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

**Assets:** procure primeiro em `biblioteca/assets/`. O que não existir, o Claude
desenha em código (seção 3 da `topclip-motion`). Todo asset novo aprovado volta para
`biblioteca/assets/` com uma linha no `biblioteca/MANIFESTO.md` — é assim que o
próximo vídeo começa com mais coisa pronta.

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
