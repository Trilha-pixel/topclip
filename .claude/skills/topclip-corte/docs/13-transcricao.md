# 13 — Transcrição: mlx-whisper × faster-whisper

`prepare` transcreve sozinho quando não há transcript. Quem escolhe o motor é
`transcription.backend` no `config/default.yaml`:

| backend | onde roda | quando o `auto` escolhe |
| --- | --- | --- |
| `mlx-whisper` | GPU do Mac (Apple Silicon, MLX) | macOS arm64 + pacote instalado + `device: auto` + modelo com versão MLX |
| `faster-whisper` | CPU (int8) ou CUDA | todo o resto, e de reserva se o mlx falhar no meio |

Os dois gravam o mesmo `02-transcript.json` (segmentos com `words[]` de
`start`/`end`/`probability`); só muda o campo `backend`. O teste
`tests/test_transcribe.py` trava essa igualdade contra o schema.

Diferenças de decodificação, sem remédio no mlx-whisper 0.4: decodificação gulosa
(não tem beam search; o faster-whisper usa `beam_size=5`) e nada de VAD (o
`vad_filter` só vale no faster-whisper). Nos dois, o espectrograma do áudio
inteiro é montado de uma vez — memória parecida para vídeo longo.

Enquanto transcreve, o avanço vai para o diário do projeto a cada
`progress_interval_seconds` (15 s): o painel mostra barra e "transcrevendo:
12:30 de 36:10 (35%) · faltam ~4 min" ao lado do comando rodando.

## Medição (Mac M2, 8 GB, 21/10/2026)

Vídeo de teste: aula em pt-BR, um locutor (`Aula 1.mov`). Uma rodada de cada,
modelo já em cache, `language: pt`, `word_timestamps`.

| áudio | faster-whisper small (CPU) | mlx-whisper small (GPU) | ganho |
| --- | --- | --- | --- |
| 5 min | 56 s | 28 s | 2,0x |
| 17 min | ~191 s (extrapolado¹) | 75 s | ~2,5x |

¹ A rodada de 17 min do faster-whisper foi interrompida: outra run pesada
começou no meio e a máquina entrou em swap. O valor vem do ritmo medido nos 5 min.
O mlx escala melhor que linear porque o custo fixo (carregar modelo, compilar o
DTW do numba) se dilui. Projeção para o vídeo de 36 min que levou ~13 min: uns
3 min no mlx com a máquina livre.

Referência de modelo grande, nos mesmos 5 min: large-v3-turbo levou 2min45s no
faster-whisper e 1min46s no mlx.

### Qualidade

Sem gabarito humano, a régua foi o large-v3-turbo nos dois motores. As duas
transcrições turbo discordam entre si em só 3% das palavras.

| contra | faster-whisper small | mlx-whisper small |
| --- | --- | --- |
| turbo (faster-whisper) — palavras divergentes | 11,2% | 9,5% |
| turbo (mlx) — palavras divergentes | 10,2% | 9,6% |
| início da palavra, p90 do erro (ref. turbo fw) | 280 ms | 170 ms |
| inícios com erro > 200 ms (ref. turbo fw) | 12,3% | 9,6% |

Nos inícios em que os dois small discordam por mais de 200 ms, o áudio entre os
dois instantes confirmou o mlx 33 vezes e o faster-whisper 25 (29 ambíguos).
Nos fins, 10 × 4. Timing equivalente, levemente a favor do mlx.

O perfil dos erros é diferente:

- **mlx small** limpa a fala: tira todo "né"/"tá" (0 contra 9 "né" no turbo) e
  os palavrões, e errou "Nietzsche" (6 no turbo, 0 aqui).
- **faster-whisper small** inventa "tá" (16 contra 2 no turbo) e erra palavra
  de conteúdo: "créditos de a" (é "de IA"), "de vende" (é "a gente vende"),
  "cópia" (é "copy").

Para achar e cortar momentos, dá na mesma. A legenda queimada não usa este
transcript: a topclip-motion transcreve o clipe de novo com o modelo dela.

**Decisão:** `auto` fica no mlx-whisper quando disponível. É 2 a 2,5x mais
rápido com qualidade equivalente. Para voltar ao comportamento antigo:
`backend: faster-whisper`.
