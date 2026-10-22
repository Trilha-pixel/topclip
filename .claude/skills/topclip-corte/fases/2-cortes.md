# Fase 2 — CORTES

> **A entrega é vídeo para assistir, com a nota do gate**, não o clipe final.
> Corte horizontal, do bruto, no in/out exato. Sem vertical, sem enquadramento,
> sem legenda. O usuário assiste e diz quais sobrevivem.

**Carregue:** `docs/06-regras-de-edicao.md` e `docs/12-erros-registrados.md`.
Não abra `config/` nem nada de enquadramento — é fase 3.

**Subagentes desta fase:** `clip-builder`, `feed-psychologist`,
`blind-reviewer`, `clip-deduplicator`. **Não** invoque `edit-director` nem
`quality-controller`: são da fase 3.

**Entrada:** os momentos que o usuário escolheu na fase 1. Só eles. Momento que
ele não escolheu não entra "porque estava bom" — ele já viu e decidiu. Se ele
escolheu mais de 5, diga uma vez que a fase demora proporcionalmente e siga: a
escolha é dele.

---

## A ordem, e por que é esta

```text
1  Clip Builder, só nos escolhidos, com autochecagem
2  auditoria técnica + dedupe temporal ............ scripts, segundos
3  prévias, todas em paralelo ..................... o usuário já pode assistir
4  revisão cega ∥ revisão de feed ∥ dedupe          mesma versão, ao mesmo tempo
5  UM rebuild, juntando as duas revisões
6  nova rodada só nos cortes que mudaram            volta ao 2, até o limite
7  nota de cada corte (a conta do gate) → PARE
```

Na run de teste (`aula-yt-teste`) a ordem antiga custou 41 minutos de cortes para
2 clipes, e cada desperdício tem aqui a sua correção:

| O que aconteceu | O que mudou |
| --- | --- |
| Clip Builder montou os 14 momentos (12 min); o usuário usou 2 | a fase 1 mostra a nota e recomenda 2–5; o Builder só monta os escolhidos |
| revisão cega reprovou os 14; o rebuild esperou a de feed (17 min), que foi jogada fora quando ele escolheu 2 | as duas revisões rodam juntas, sobre a mesma versão, e geram **um** rebuild |
| os 2 escolhidos foram refeitos e revisados de novo | a nova rodada é só dos cortes que mudaram |
| as prévias só foram cortadas depois da escolha: ele marcou corte sem ver vídeo | prévias logo depois do Builder, antes das revisões |
| a nota do gate só apareceu no `finalize`, 1h depois: os 2 escolhidos ficaram abaixo de 7,5 | `estimate` dá a nota aqui, com a mesma conta |

**Nenhum portão saiu.** Autochecagem, auditoria, revisão de feed, revisão cega,
dedupe, limite de rebuild e nota mínima continuam todos. O que mudou é que nenhum
espera outro sem motivo, e nenhum roda sobre corte que o usuário já descartou.

Anote cada passo no painel (`./topclip log projetos/<nome> "..."`), em português de
gente: "montando os 3 cortes", "prévias prontas — pode ir assistindo enquanto as
revisões rodam", "revisões pediram ajuste em 2; refazendo os dois de uma vez".

## 1. Clip Builder — só os escolhidos

Subagente `clip-builder`. Saída: `06-candidates.json`, validado em seguida.

Reconstrua cada candidato com intervalos reais. Destaque inicial pode vir do
meio ou do fim, mas remova o replay no corpo quando não houver função narrativa.
O agente traz a **autochecagem** dos seis motivos que mais derrubaram cortes na
revisão cega (gancho sem assunto em 3s, emenda que quebra frase, palavra solta,
final que pede continuação, referente perdido, número tardio no `money`): é
mais barato o Builder pegar isso do que uma volta de rebuild.

**Antes de cravar in/out, puxe o timing por palavra SÓ das janelas escolhidas:**

```bash
./topclip corte digest --run <run-dir> \
  --windows "1523-1615,4870-4940"
```

Gera `02-palavras-janelas.txt`. Medido: 2.974 tokens contra 1.346.173 do
transcript inteiro — **452x**. Abrir o transcript cheio para cortar 60s é o
mesmo erro do índice visual do vídeo inteiro: pagar o episódio para usar o
minuto.

### Regras de in/out contra o timing por palavra

**Começar na frase, não no conector.** Proibido abrir em `mas`, `então`, `aí`,
`e`, `porque`, `uhum`, `vocês viram`, `olha só`, `agora`, `cara`. Procurar 1–3s
à frente uma abertura autossuficiente.

**Não truncar palavra.** Início 0,2–0,3s antes da primeira palavra; fim 0,3–0,5s
depois da última sílaba.

**Não cortar o payoff.** Depois da frase forte, deixar a reação terminar. 1–2s a
mais fazem o corte parecer natural em vez de amputado.

| Regra | Valor |
| --- | --- |
| Duração alvo | 35–75s |
| Teto | 90s — acima disso, tentar versão curta antes de aceitar |
| Sobreposição entre dois cortes | < 30% |
| Sobreposição hook↔corpo no mesmo corte | 0%, salvo payoff narrativo declarado |

Se o hook é >50% do clipe, **não use hook — faça linear.**

### Bordas no vale de energia — script, não ouvido

O timing por palavra do Whisper erra 0,1–0,5s em palavras coladas: a borda que
cai na "fronteira" que ele deu pega a cauda da palavra anterior ou corta a
última sílaba. Logo depois do Clip Builder, sempre:

```bash
./topclip corte bordas --run <run-dir>
```

Para cada borda de segmento que é corte de verdade, mede a energia (RMS a 10ms)
e leva a borda ao vale: borda já em silêncio claro (< -50 dB) fica; senão vai
ao silêncio mais próximo em ±0,15s; sem silêncio, ao ponto mais baixo se passar
de -40 dB. Nunca atravessa palavra — a borda só cai no vão entre duas palavras,
e nenhuma palavra entra ou sai do corte por causa dela. Eventos, beats e duração
estimada do candidato são recalculados juntos.

Sem vale abaixo de -40 dB, a borda não se mexe e o clipe ganha `borda_fraca` em
`warnings`: é fala colada de verdade. Escolha outra borda numa pausa real e rode
de novo, ou deixe, se não houver pausa ali (o aviso viaja com o clipe até o QC).
**Não meça RMS à mão** — foi o que custou 13,5 min da fase 3 na run de `docs/12`
(12.7). O detalhe de cada borda fica em `iterations/bordas-06.json` e em
`edge_audio` no próprio segmento; rodar de novo não mexe no que já foi medido.

### Recursos visuais do próprio bruto

Antes de fechar in/out, olhar os frames. O bruto costuma já ter card de título,
print, transição P&B→cor, inserto, reação facial. **Nunca cortar imediatamente
antes de um desses** — são hook de graça.

O índice visual, escopado às janelas escolhidas, roda **em segundo plano, ao mesmo
tempo que o Builder** — na run de teste levou 14 min para 9 janelas, e ninguém
precisa esperá-lo de braços cruzados:

```bash
./topclip corte visual-index --run <run-dir> \
  --windows "1523-1615,4870-4940"
```

Para um instante pontual, o grab avulso serve:

```bash
ffmpeg -ss T -i BRUTO -frames:v 1 -vf scale=480:-2 f.jpg
```

E pense no primeiro frame: rosto em movimento > rosto neutro > objeto > vazio.

## 2. Auditoria técnica — antes de gastar revisor

```bash
./topclip corte audit --run <run-dir>
./topclip corte dedupe --run <run-dir>
```

A auditoria calcula **sem estimativa do modelo**: duração final, sobreposição,
contenção, repetição de highlight, intervalos inválidos, gaps, palavras por
segundo, silêncio. Leva segundos. Hard fail em `08-technical-audit.json` volta
**já** ao Clip Builder: não há por que um revisor ler um corte com intervalo
inválido. O `dedupe` é a sobreposição temporal entre cortes
(`10-temporal-deduplication.json`).

### Revisão vale para uma versão do corte

Cada entrada de `07`, `09` e `12` é carimbada pelo script com `segments_hash`, a
versão do corte que o revisor viu. Mudou o corte depois (rebuild, borda movida à
mão), a revisão daquele clipe fica velha — e só a dele. O ajuste do `bordas`
**não** conta como versão nova: não tira nem põe palavra.

```bash
./topclip corte revisoes --run <run-dir>
```

Sai `limpo: true` ou a lista do que refazer, com o subagente de cada item. Rode
antes das prévias (passo 3) e das revisões (passo 4). Não carimbe nada à mão: ao
reenviar um clipe ao revisor, a entrada nova vai sem `segments_hash`.

## 3. Prévias — já, todas em paralelo

```bash
./topclip corte previews --run <run-dir>
```

Corta a prévia de cada corte de `06-candidates.json` ao mesmo tempo, seguindo a
timeline do Builder — os mesmos segmentos, na mesma ordem, sem os
`remove_from_body` —, em 720p. É a mesma versão que os revisores vão ler, então o
usuário assiste ao que está sendo julgado. Saem em
`<run-dir>/preview/<NN>-<clip-id>-<titulo>.mp4`; o `<NN>` segue a ordem de
`06-candidates.json` e o painel casa cada prévia com o seu corte pelo id. A versão
anterior de um corte é apagada quando a nova é cortada.

Avise no painel que as prévias estão lá. Ele pode ir assistindo enquanto as
revisões rodam — é tempo que antes ficava parado.

## 4. Revisões em paralelo, na mesma versão

```bash
./topclip corte blind-packets --run <run-dir>
```

Se o `revisoes` acusou revisão de feed velha, ela entra nesta rodada. Depois,
**numa única mensagem**, dispare juntos:

| Subagente | Quantos | Lê | Saída |
| --- | --- | --- | --- |
| `feed-psychologist` | 1, para os cortes da rodada | `06-candidates.json` + o perfil de cada corte | `07-feed-review.json` |
| `blind-reviewer` | 1 por corte | **só** o pacote do corte em `blind-packets/`, inline | você junta em `09-blind-review.json` |
| `clip-deduplicator` | 1, só na 1ª rodada e só com 2+ cortes | os cortes + `10-temporal-deduplication.json` | `10-deduplication.json` |

Todos olham para o mesmo `06-candidates.json`, recém-auditado. Em cada revisão,
grave `rebuild_attempt_reviewed` com o `rebuild_attempt` do corte revisado — o
revisor cego não sabe disso (nem deve); quem anota é você, ao juntar o `09`. Não
comece rebuild nenhum antes de todas voltarem: rebuild com meia revisão é o que
obrigava a refazer depois.

**Revisão de feed.** Avalie separadamente: captura no primeiro segundo; clareza da
proposta até 3s; tempo até primeiro valor; dívida de contexto; gap de
curiosidade; densidade de beats; progressão; integridade promessa–payoff;
compartilhamento; fadiga. "Dopamina" não é métrica. Use os proxies definidos no
projeto.

**Revisão cega.** Para cada corte, leia **somente** seu arquivo em
`blind-packets/` e envie o conteúdo inline ao subagente `blind-reviewer`. Esse
agente não tem ferramenta local de leitura, busca ou execução — a única declarada
não é local e deve permanecer sem uso. Não envie título promocional, contexto
completo, score nem justificativa anterior, nem o resultado da revisão de feed.

```bash
./topclip corte validate-artifact --run <run-dir> --file 07-feed-review.json
./topclip corte validate-artifact --run <run-dir> --file 09-blind-review.json
```

## 5. Um rebuild, juntando as duas revisões

Para cada corte, leia junto: hard fail da auditoria, `status` e `problems` do
feed, `decision`, `problems` e `rebuild_instructions` da cega, e o dedupe.

| Situação do corte | O que fazer |
| --- | --- |
| PASS nas duas, sem hard fail | pronto — não mexa |
| perdedor no dedupe | sai, com o motivo (`DUPLICATE`) |
| `REJECT` em qualquer revisão | sai, com o motivo (`REJECTED`) |
| `REBUILD` em uma ou nas duas | entra na lista do rebuild |

Monte **uma** lista por corte com o que as duas pediram, sem repetir o que as duas
disseram com outras palavras. Invoque o `clip-builder` **uma vez**, só com os
cortes da lista. Quando as revisões pedem coisas opostas, vale fidelidade > se
sustentar sozinho > velocidade, e o Builder registra a escolha em `warnings`. Ele
soma 1 ao `rebuild_attempt` de cada corte que refez.

## 6. Nova rodada — só nos que mudaram

Rode o `bordas` nos cortes refeitos e volte ao passo 2:

```bash
./topclip corte bordas --run <run-dir>
./topclip corte audit --run <run-dir>
./topclip corte previews --run <run-dir> --clips clip-002,clip-005
./topclip corte blind-packets --run <run-dir>
```

e, de novo numa única mensagem, feed e cega **só desses cortes**. Ao gravar `07` e
`09`, troque só as entradas deles — a revisão dos que já passaram continua valendo,
porque o corte deles não mudou. O `clip-deduplicator` só roda de novo se um
rebuild mudou a promessa ou o payoff de algum corte.

Repita até passar ou até `max_rebuild_attempts` (3, em `config/default.yaml`).
Depois do limite, `REJECTED` com motivo explícito.

## 7. Nota de cada corte e PARE

```bash
./topclip corte estimate --run <run-dir> --cortes
```

A **mesma conta do `finalize`**: as notas do Builder com as da revisão de feed por
cima. Grava `publishability_estimate` e `estimate_below_gate` em cada corte de
`06-candidates.json`; o painel mostra a nota em cada prévia. Rode depois da última
rodada — a nota de um corte sem revisão de feed é só a do Builder, e o comando
avisa quais estão assim.

Entregue os arquivos ao usuário e **pare**. Por corte, uma linha: a nota (e, abaixo
de 7,5, por quê), a duração, o hook em citação literal, e o que as revisões
apontaram (se apontaram). Corte abaixo do gate: diga com todas as letras que, se
ele escolher, chega ao fim marcado como fraco (`WEAK`) — ou reprovado, se o motivo
for fidelidade abaixo de 9. A escolha é dele, mas feita sabendo.

Os previews em `<run-dir>/preview/` aparecem no painel (`./topclip painel`, etapa
Cortes) para ele assistir e marcar; se escolher por lá, os ids estão em
`projetos/<nome>/escolhas.json` → `cortes`.

A fase 3 só começa depois que ele disser quais viram vertical. Renderizar
vertical de 20 clipes para descobrir que 12 não prestam é o custo que este
portão existe para evitar.
