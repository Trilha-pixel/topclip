# 3. Arquitetura do harness

## 3.1 Princípio arquitetural

O sistema separa julgamento probabilístico de cálculo determinístico.

```text
MODELO
├── entende significado
├── identifica histórias
├── avalia curiosidade
├── reconstrói narrativa
├── identifica payoff
└── planeja edição

CÓDIGO
├── lê mídia
├── normaliza timestamps
├── calcula duração
├── mede sobreposição
├── mede repetição
├── detecta silêncio
├── valida JSON
├── cria legendas
└── renderiza FFmpeg
```

Nenhum dos lados deve substituir o outro.

## 3.2 Componentes

### Skill principal

`.claude/skills/topclip-corte/SKILL.md`

É o orquestrador. Define ordem, arquivos obrigatórios, loops e condição de conclusão.

### Subagentes

- `context-mapper`: entende o episódio.
- `clip-hunter`: encontra momentos candidatos.
- `clip-builder`: monta timelines publicáveis.
- `feed-psychologist`: testa velocidade, curiosidade e progressão.
- `blind-reviewer`: avalia sem conhecer a seleção.
- `clip-deduplicator`: remove equivalência semântica.
- `edit-director`: cria o plano técnico.
- `quality-controller`: última barreira.

### Scripts

O CLI `scripts/vch.py` centraliza operações. Ele chama módulos para mídia, transcript, métricas, schema, legenda e render.

### Schemas

Cada etapa possui contrato. Um arquivo incompleto não deve ser aceito apenas porque “parece correto”.

### Configuração

`config/default.yaml` contém limites globais. `config/profiles/` ajusta o relógio por tipo de clipe.

## 3.3 Fluxo

```text
INPUT
  │
  ▼
PRE-FLIGHT ── dependências, caminhos, permissões
  │
  ▼
INGESTION ── ffprobe, áudio, transcript, frames
  │
  ▼
CONTEXT MAPPER
  │
  ▼
CLIP HUNTER
  │
  ▼
CLIP BUILDER
  │
  ▼
FEED PSYCHOLOGY REVIEW
  │
  ▼
TECHNICAL AUDIT
  │
  ├── REBUILD ───────────────┐
  │                          │
  ▼                          │
BLIND REVIEWER               │
  │                          │
  ├── REBUILD ───────────────┘
  │
  ▼
TEMPORAL + SEMANTIC DEDUPE
  │
  ▼
EDIT DIRECTOR
  │
  ▼
QUALITY CONTROLLER
  │
  ▼
SUBTITLES + RENDER
  │
  ▼
OUTPUT VERIFICATION
```

## 3.4 Por que preservar arquivos intermediários

Arquivos intermediários permitem:

- auditar por que um clipe foi escolhido;
- comparar versões de rebuild;
- executar apenas uma fase novamente;
- testar outro modelo no mesmo contexto;
- criar evals;
- impedir que o modelo finja ter realizado uma passagem;
- recuperar execução interrompida.

## 3.5 Isolamento do Blind Reviewer

O revisor não recebe acesso ao workspace. O agente tem `tools: []` e recebe o objeto do clipe inline. Isso evita que leia scores, contexto ou justificativas.

A revisão cega avalia somente o produto, não a intenção do seletor.

## 3.6 Modelo de confiança

Cada campo deve registrar origem:

```json
{
  "value": 7.8,
  "source": "model",
  "agent": "feed-psychologist",
  "confidence": 0.82
}
```

ou:

```json
{
  "value": 32.41,
  "source": "deterministic",
  "script": "compute_metrics.py"
}
```

Isso impede misturar inferência com medição.

## 3.7 Modos de execução

### `analyze`

Produz contexto, candidatos, auditorias e relatórios. Não renderiza.

### `verify`

Recebe candidatos já existentes e executa feed review, auditoria técnica, blind review e dedupe.

### `render`

Recebe `13-final-clips.json` e gera legendas e vídeos.

### `full`

Executa tudo.

## 3.8 Falha controlada

O sistema deve falhar com diagnóstico em vez de improvisar.

Exemplos:

- sem FFmpeg: análise pode continuar com transcript, render não;
- sem transcript: transcrever ou interromper fase semântica;
- transcript sem timestamps: análise possível, render preciso bloqueado;
- vídeo corrompido: registrar erro de ingestão;
- schema inválido: impedir avanço;
- nenhum clipe aprovado: gerar relatório vazio, não inventar clipes.


## Output Quality Gate

Depois do render, `scripts/output_qc.py` verifica mídia, legendas e bordas do arquivo. Esse gate é separado do `quality-controller`: o agente revisa significado e plano antes do render; o script confere o que realmente foi exportado. O relatório final é `16-output-verification.json`.
