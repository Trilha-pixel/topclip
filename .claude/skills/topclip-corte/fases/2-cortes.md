# Fase 2 — CORTES

> **A entrega é vídeo para assistir**, não o clipe final. Corte horizontal, do
> bruto, no in/out exato. Sem vertical, sem enquadramento, sem legenda. O
> usuário assiste e diz quais sobrevivem.

**Carregue:** `docs/06-regras-de-edicao.md` e `docs/12-erros-registrados.md`.
Não abra `config/` nem nada de enquadramento — é fase 3.

**Subagentes desta fase:** `clip-builder`, `feed-psychologist`,
`blind-reviewer`, `clip-deduplicator`. **Não** invoque `edit-director` nem
`quality-controller`: são da fase 3.

**Entrada:** os momentos que o usuário aprovou na fase 1. Só eles. Momento que
ele não escolheu não entra "porque estava bom" — ele já viu e decidiu.

---

## 1. Clip Builder

Subagente `clip-builder`. Saída: `06-candidates.json`, validado em seguida.

Reconstrua cada candidato com intervalos reais. Destaque inicial pode vir do
meio ou do fim, mas remova o replay no corpo quando não houver função narrativa.

**Antes de cravar in/out, puxe o timing por palavra SÓ das janelas aprovadas:**

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

### Recursos visuais do próprio bruto

Antes de fechar in/out, olhar os frames. O bruto costuma já ter card de título,
print, transição P&B→cor, inserto, reação facial. **Nunca cortar imediatamente
antes de um desses** — são hook de graça.

**Agora sim o índice visual**, escopado às janelas dos candidatos aprovados:

```bash
./topclip corte visual-index --run <run-dir> \
  --windows "1523-1615,4870-4940"
```

Decodifica segundos, não horas. Para um instante pontual, o grab avulso serve:

```bash
ffmpeg -ss T -i BRUTO -frames:v 1 -vf scale=480:-2 f.jpg
```

E pense no primeiro frame: rosto em movimento > rosto neutro > objeto > vazio.

## 2. Feed Psychology Review

Subagente `feed-psychologist`. Saída: `07-feed-review.json`.

Avalie separadamente: captura no primeiro segundo; clareza da proposta até 3s;
tempo até primeiro valor; dívida de contexto; gap de curiosidade; densidade de
beats; progressão; integridade promessa–payoff; compartilhamento; fadiga.

"Dopamina" não é métrica. Use os proxies definidos no projeto.

## 3. Auditoria técnica

```bash
./topclip corte audit --run <run-dir>
```

Calcula **sem estimativa do modelo**: duração final, sobreposição, contenção,
repetição de highlight, intervalos inválidos, gaps, palavras por segundo,
silêncio. Leia `08-technical-audit.json` e devolva todo hard fail ao Clip
Builder.

Para status `REBUILD`: `Clip Builder → Feed Psychology → Auditoria`, até
`max_rebuild_attempts`. Depois do limite, `REJECTED` com motivo explícito.

## 4. Blind Reviewer

```bash
./topclip corte blind-packets --run <run-dir>
```

Para cada sobrevivente, leia **somente** seu arquivo em `blind-packets/` e envie
o conteúdo inline ao subagente `blind-reviewer`. Esse agente não tem ferramenta
local de leitura, busca ou execução — a única declarada não é local e deve
permanecer sem uso. Não envie título promocional, contexto completo, score nem
justificativa anterior. Saída: `09-blind-review.json`.

Falha relevante volta para `REBUILD`.

## 5. Deduplicação

```bash
./topclip corte dedupe --run <run-dir>
```

Depois o subagente `clip-deduplicator` compara equivalência semântica entre
clipes com baixa sobreposição temporal. Saída: `10-deduplication.json`. Mantenha
a versão com melhor combinação de independência, velocidade, payoff e
editabilidade.

## 6. Corte de preview e PARE

Corte cada sobrevivente do bruto, **horizontal, como está**. Sem reenquadrar,
sem legenda, sem normalizar. É material de aprovação, não entregável:

```bash
ffmpeg -y -ss <IN> -to <OUT> -i <BRUTO> \
  -c:v libx264 -preset veryfast -crf 23 -c:a aac \
  <run-dir>/preview/<NN>-<slug>.mp4
```

`-ss` antes do `-i` é rápido mas corta no keyframe anterior; como aqui o in/out
é o dado que está sendo aprovado, use `-ss` **depois** do `-i` (mais lento,
exato) ou aceite a imprecisão e diga que é preview.

Entregue os arquivos ao usuário e **pare**. Por clipe, uma linha: duração, o
hook em citação literal, e o que a auditoria apontou (se apontou).

A fase 3 só começa depois que ele disser quais viram vertical. Renderizar
vertical de 20 clipes para descobrir que 12 não prestam é o custo que este
portão existe para evitar.
