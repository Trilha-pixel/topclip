---
name: topclip-corte
description: Transforma vídeo longo bruto (podcast, entrevista, live, aula) em clipes verticais 9:16 prontos para Shorts, Reels e TikTok. Cobre as quatro etapas — decupagem com timing por palavra, identificação dos trechos que funcionam fora de contexto, corte com in/out preciso, e enquadramento vertical com locutor ativo. Use quando o pedido for cortar podcast, achar cortes, "o que vira Short disso", clipar entrevista, decupar vídeo longo, deixar vertical, enquadrar pro Reels, ou refazer cortes redundantes. NÃO queima legenda nem faz motion — isso é a skill topclip-motion, que recebe o vertical limpo desta.
effort: high
allowed-tools:
  - Agent
  - Read
  - Write
  - Grep
  - Glob
  - Bash(./topclip corte *)
  - Bash(./topclip verificar *)
  - Bash(ffprobe *)
  - Bash(ffmpeg *)
---

# Do bruto ao vertical

> Parte do **TopClip**. Todo caminho aqui é relativo à raiz do repositório,
> e todo comando roda a partir dela, pelo lançador `./topclip`.

Quatro entregas em sequência, **cada uma com um portão**. Você para no portão,
mostra o resultado e espera o usuário dizer o que segue. Só emende as quatro numa
run só quando ele pedir explicitamente ("vai até o fim", "manda o pacote todo").

| # | Entrega | O que sai | Você lê |
| --- | --- | --- | --- |
| **1** | **MOMENTOS** | a lista dos trechos que dariam corte, com timestamp e citação | `fases/1-momentos.md` |
| **2** | **CORTES** | os trechos já cortados, em vídeo, para assistir | `fases/2-cortes.md` |
| **3** | **VERTICAL** | 9:16 com o locutor rastreado e reenquadrado | `fases/3-vertical.md` |
| **4** | **ENTREGA** | pasta final verificada, pronta para a topclip-motion | `fases/4-entrega.md` |

> **Leia SÓ o arquivo da fase em que você está.** Carregar as quatro de uma vez
> era o que fazia esta skill custar ~6.800 palavras antes da primeira ação útil,
> a maior parte sobre render e enquadramento, num pedido que às vezes era só
> "quais são os bons momentos". A fase 1 sozinha precisa de ~1.200.

## A regra que decide o custo da run

**Nenhum agente lê `02-transcript.json`.** Medido num podcast de 3h: o artefato
cru custa **1.346.173 tokens** — não cabe numa janela — e 9 em cada 10 desses
tokens são `words[]`, timing por palavra que o modelo **não usa** para escolher
trecho. Timing por palavra é para os scripts.

| Quem precisa de quê | Comando | Custo |
| --- | --- | --- |
| escolher trecho (fases 1) | `vch digest --run <run>` | 62.758 tok — **21,5x menos** |
| cravar in/out (fase 2) | `vch digest --run <run> --windows "a-b,c-d"` | 2.974 tok — **452x menos** |
| in/out, legenda, autoframe | os scripts, direto no JSON | não passa por LLM |

E **você, no loop principal, não lê texto longo** — nem transcript, nem digest.
Você lê os artefatos JSON, que são compactos. Quem lê texto longo é subagente,
em contexto próprio, que morre no fim da passagem.

## A ordem é fixa

```text
TIMESTEPS  →  SELEÇÃO  →  CORTE  →  VERTICAL
    ↑ sempre        ↑ só texto      ↑ só aqui o bruto é aberto
    primeiro
```

**A skill nunca começa analisando o vídeo bruto**, e os timesteps são
pré-requisito de tudo: sem transcript com timing **por palavra**, a fase 1 não
começa — ver a decupagem em `fases/1-momentos.md`. Isso não é um modo entre
outros; é a única ordem. O que varia é **até que fase** ir.

## Sempre carregado

Só `REGRAS.md` (nesta pasta) — as 11 regras invioláveis e a
missão. Tudo mais é carregado pela fase que precisa:

| Fase | Carrega além do REGRAS.md |
| --- | --- |
| 1 | `docs/05-regras-de-selecao.md` |
| 2 | `docs/06-regras-de-edicao.md`, `docs/12-erros-registrados.md` |
| 3 | `config/default.yaml`, `config/platforms/<platform>.yaml` |
| 4 | nada |

## O kit viaja junto

| | |
| --- | --- |
| `fases/` | as quatro fases — leia uma por vez |
| `scripts/` | o motor: transcrição, métricas, enquadramento, render, QC |
| `docs/` | seleção, edição, psicologia de feed, erros já cometidos |
| `config/` | default + 3 plataformas + 12 perfis narrativos |
| `schemas/` | os 15 contratos JSON de cada artefato |
| `models/` | YuNet, detecção facial do enquadramento automático — baixado pelo `./topclip instalar` |
| `verificar.py` | checagem de instalação — rode antes do primeiro projeto |
| `../../agents/` | os 8 subagentes, em `.claude/agents/` — o Claude Code os registra sozinho |

Use sempre `./topclip corte <subcomando>`, nunca `python3 scripts/vch.py`. O
`python3` do sistema no macOS é o 3.9 e o pacote exige 3.10+; o lançador usa a
venv do repositório (`.venv/`).

**Nem todo subagente roda em toda fase.** São 8 no total, mas a fase 1 usa 2. Não
invoque agente de fase que você ainda não abriu.

## Antes do primeiro projeto

```bash
./topclip verificar
```

Se acusar dependência faltando, rode `./topclip instalar`. Não comece
com instalação incompleta: o pipeline quebra no meio, depois de já ter gasto a
transcrição.

## Argumentos

Aceite vídeo com transcrição opcional; só transcrição, para análise sem render;
`--run <run-dir>` para continuar; `--max-clips N` **como teto, nunca como meta**;
`--platform cross-platform`, `tiktok` ou `instagram-reels`.

Não peça confirmação quando caminho e plataforma puderem ser inferidos — o
portão de cada fase já é o ponto de conversa.

## Onde a run mora

**`--workspace` é obrigatório no `init`.** Use `projetos/<nome-do-video>/runs` —
a pasta `projetos/` fica fora do git. Sem `--workspace` a run é gravada dentro
da skill e some da vista.

## Fronteira com a topclip-motion

Esta skill entrega `clip-vertical.mp4` **limpo** — sem legenda queimada e sem
motion. Quem queima legenda e insere motion é a `topclip-motion`, no mesmo passe.

Os `captions.srt`/`.ass` são gerados sempre: são **decupagem**, não legenda
queimada. É o timing por palavra que a topclip-motion usa para ancorar cada evento
na fala. Não pule, e não queime legenda aqui antes de mandar — seriam duas.
