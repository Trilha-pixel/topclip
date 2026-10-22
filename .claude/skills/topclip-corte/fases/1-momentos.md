# Fase 1 — MOMENTOS

> **A entrega é uma lista, não um vídeo.** Nenhum frame é decodificado nesta
> fase. Termina com os momentos apresentados ao usuário e a run parada.

**Carregue:** `docs/05-regras-de-selecao.md`. Só isso, além do `REGRAS.md`.
Não abra `06-regras-de-edicao` (in/out), `12-erros-registrados` (render) nem
`config/` — são das fases 2 e 3.

**Subagentes desta fase:** `context-mapper` e `clip-hunter`. **Só esses dois.**
Os outros seis (`clip-builder`, `feed-psychologist`, `blind-reviewer`,
`clip-deduplicator`, `edit-director`, `quality-controller`) são de fases que
você ainda não abriu.

---

## 1. Preparação

```bash
./topclip corte preflight
./topclip corte init <VIDEO> [TRANSCRIPT] \
  --mode full --platform cross-platform \
  --workspace projetos/<nome-do-video>/runs
```

Leia o `RUN_DIR=` emitido. Depois:

```bash
./topclip corte prepare --run <run-dir>
```

`prepare` gera metadados, áudio de análise e transcript normalizado.

**O índice visual fica de fora, e isso é a regra, não uma otimização.**
`03-visual-index.json` é gravado como placeholder adiado. Gerá-lo decodifica o
vídeo inteiro duas vezes (frames periódicos + detecção de cena); num podcast de
3h isso trava a run antes de você sequer saber que trecho interessa. Índice
visual só na fase 2, e escopado às janelas dos candidatos.

## 2. Decupagem — o timing por palavra é pré-requisito

Transcrição com granularidade de 1 segundo **não serve**: erra nome, número e
palavra, e não diz onde a palavra começa. Três fontes, nesta ordem:

1. **Legenda automática do YouTube**, se o vídeo estiver lá (mesmo já publicado).
   O VTT traz `<00:26:48.520><c>carrinhos</c>` — timing por palavra de graça.
   Projeto que veio de link do YouTube (`./topclip baixar`) já tem: é o `legenda`
   do `projeto.json` — passe-o como `[TRANSCRIPT]` no `init`. Vídeo local que também
   está no YouTube:
   ```bash
   ./topclip py -m yt_dlp "ytsearch3:TITULO DO VIDEO" --print "%(id)s | %(duration)s | %(channel)s"
   # confirmar pela duração batendo com o arquivo local, depois:
   ./topclip py -m yt_dlp --js-runtimes node --write-auto-subs --sub-langs "pt-orig" --sub-format vtt \
     --skip-download -o "projetos/<nome>/legenda.%(ext)s" "https://youtube.com/watch?v=ID"
   ```
   Use a faixa `-orig` (a do idioma falado); as outras são tradução e perdem o
   tempo por palavra.
   `prepare` aceita o `.vtt` direto: o parser extrai o timestamp real de cada
   palavra, remove a duplicação da cue rolante e usa o `>>` como fronteira de
   troca de locutor.
2. **Whisper local** com `word_timestamps=True` — o que `prepare` roda sozinho
   quando não há transcript: mlx-whisper na GPU em Mac com Apple Silicon,
   faster-whisper na CPU nos outros (`transcription.backend`, ver
   `docs/13-transcricao.md`). O avanço aparece no painel enquanto roda.
3. Sem nenhum dos dois: **pare aqui** e entregue o diagnóstico de dependência.
   Não invente transcript.

Se o usuário já colou transcript com timestamps, use o dele e pule a geração.

## 3. Digest — o passo que decide o custo da run

```bash
./topclip corte digest --run <run-dir>
```

Gera `02-digest.md`: texto + timestamp por bloco de ~20s, quebrando na troca de
locutor. **É isto que os agentes leem. Ninguém lê `02-transcript.json`.**

Medido num podcast de 3h (6.057 segmentos, 40.363 palavras com timing):

| | tokens |
| --- | --- |
| `02-transcript.json` inteiro | **1.346.173** |
| `02-digest.md` | **62.758** |
| | **21,5x menos** |

O `words[]` é 9 em cada 10 tokens do artefato e o modelo **não usa nada dele**
para escolher trecho — timing por palavra é para os scripts (in/out, legenda,
autoframe). Ler o transcript cru para escolher assunto é pagar o episódio
inteiro por uma informação que não entra na decisão. Um agente sozinho não
caberia na janela.

O digest marca com `»` os blocos com sinal determinístico de clipe (número,
contradição, confissão, risco, história) — 107 de 1.243 no episódio medido.
**A marca é ordem de leitura, não seleção.** Momento bom sem palavra-chave
existe; leia os marcados primeiro e depois varra o resto.

> **Você, no loop principal, não lê nem o transcript nem o digest inteiro.**
> Você lê os artefatos JSON, que são compactos. Quem lê texto longo é subagente,
> em contexto próprio, que morre no fim da passagem.

## 4. Context Mapper

Subagente `context-mapper`. Entrada: **`02-digest.md`** e `01-media.json`. **Sem `03-visual-index.json`** — nesta fase ele
não existe, e isso é esperado: o mapeamento roda inteiro a partir do transcript.
`visual_events` aqui vem do que a fala descreve (print citado, reação
mencionada), não de frame extraído.

Saída: `04-context-map.json`.

```bash
./topclip corte validate-artifact --run <run-dir> --file 04-context-map.json
```

Não gere clipes nesta passagem.

## 5. Clip Hunter

Subagente `clip-hunter`. Saída: `05-viral-moments.json`, com a nota estimada de
cada momento (abaixo).

Encontre todos os momentos defensáveis, **sem forçar quantidade**. Cada momento
precisa de citação literal, timestamps e perfil provável.

**Critério de escolha:** não é a importância do trecho dentro do episódio. É a
chance de alguém cair nele **sem contexto nenhum** e continuar assistindo.

### As três perguntas, respondidas pelo TEXTO

- **Hook** — que frase/fato específico prende sem nenhum contexto anterior?
  (`trigger`)
- **Desenvolvimento** — o que sustenta entre o hook e o payoff: mecanismo,
  prova, virada, contra-argumento? Se não há nada sustentando, o momento é raso
  — vira observação, não candidato.
- **Payoff** — o que fecha a promessa do hook? (`payoff_candidate`)

Se as três respostas não existem no texto, o momento **não está pronto**. Ele
volta pra leitura do transcript, não pro vídeo, e não é adiável pra fase 2.

### A nota estimada

O Clip Hunter também grava, por momento, `estimated_scores`: as notas que ele
prevê para o corte montado (as regras de calibração estão no próprio agente).
Depois dele, no lugar do `validate-artifact`:

```bash
./topclip corte estimate --run <run-dir>
```

Valida o `05-viral-moments.json` e aplica a **mesma conta do gate do `finalize`**
(`docs/05-regras-de-selecao.md` §5.6, mínimo 7,5) sobre essas notas. Grava em cada
momento `publishability_estimate` e `estimate_below_gate` (por que cairia; vazio =
passaria). Sai com código 3 se algum momento ficou sem nota completa — devolva ao
Clip Hunter os que ele listar.

Na run de teste a nota só apareceu no `finalize`, uma hora depois da escolha: os
dois cortes escolhidos saíram abaixo de 7,5 quando já não dava para trocar — e três
que ele deixou de lado tinham nota maior. A nota é estimativa — a de verdade sai das revisões
da fase 2 —, mas é ela que deixa o usuário escolher sabendo.

## 6. Apresente e PARE

Mostre ao usuário, por momento:

| | |
| --- | --- |
| nota estimada | `publishability_estimate`; abaixo de 7,5, diga por quê (`estimate_below_gate`) |
| timestamp | `in`–`out` aproximados, em `mm:ss` |
| citação | o trecho **literal**, não paráfrase |
| hook / desenvolvimento / payoff | uma linha cada |
| perfil | o perfil narrativo provável |
| duração | estimada |

Ordene pela nota estimada, não por ordem cronológica — a pergunta dele é "quais
prestam", não "o que acontece no episódio". O painel mostra na mesma ordem.

**Recomende escolher poucos: de 2 a 5.** Cada momento escolhido vira montagem,
revisão cega, revisão de feed e prévia na fase 2. Na run de teste ele marcou 14
para usar 2, e a fase de cortes levou 41 minutos. Diga isso em uma linha, aponte os
que você escolheria (os de nota mais alta que não caem no gate) e deixe a decisão
com ele.

Diga quantos momentos você descartou e por quê, em uma linha. Momento
descartado com motivo evita refazer a discussão depois.

**Pare aqui.** Diga que ele pode escolher na conversa ou no painel
(`./topclip painel`, etapa Momentos — lá tem a nota e o botão "marcar os melhores").
Se ele responder que escolheu no painel, os ids estão em
`projetos/<nome>/escolhas.json` → `momentos`. Não rode `visual-index`, não invoque
`clip-builder`, não corte nada. A fase 2 só começa depois que o usuário disser
quais momentos viram corte — e ele pode cortar metade da sua lista, que é
justamente por isso que o corte não foi feito antes.
