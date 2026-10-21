# 11. Operação no Claude Code

## Onde a skill mora

```text
<repo>/.claude/skills/topclip-corte/   a skill
<repo>/.claude/agents/                 os 8 subagentes — o Claude Code os lê daqui
<repo>/.venv/                          o Python do pacote, criado por ./topclip instalar
<repo>/projetos/                       os vídeos e as runs (fora do git)
```

Abra o Claude Code **na raiz do repositório**. É isso que faz a skill e os
subagentes aparecerem: não há nada para copiar para `~/.claude/`.

## Como chamar

A skill é invocável pelo modelo — "corta esse podcast", "o que vira Short disso",
"deixa vertical". Diretamente:

```text
/topclip-corte ~/Videos/podcast.mp4 --mode full
```

Ou o fluxo completo, do bruto ao clipe com motion: `/topclip ~/Videos/podcast.mp4`.

## Onde as runs ficam

Sempre em `projetos/`, nunca dentro da skill:

```bash
./topclip corte init VIDEO.mp4 LEGENDA.vtt \
  --mode full --workspace projetos/meu-podcast/runs
```

Sem `--workspace`, a run cai em `.claude/skills/topclip-corte/workspace/runs/` e
some da vista.

## Modos

| Modo | Faz |
| --- | --- |
| `analyze` | decupagem + seleção, sem render |
| `verify` | acrescenta auditoria técnica e revisão cega |
| `render` | corta e renderiza o vertical |
| `full` | tudo |

## O lançador

Todo comando passa por `./topclip corte`. Ele usa a venv do repositório
(Python 3.10+) — o `python3` do sistema no macOS é o 3.9 e não roda o pacote.

## Retomar uma run

```bash
./topclip corte init --run <run-dir>
```

Os artefatos numerados `00`–`16` dizem onde parou. Não recomece do zero: a
transcrição e o índice visual são a parte cara.
