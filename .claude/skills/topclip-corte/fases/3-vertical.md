# Fase 3 — VERTICAL

> **A entrega é o 9:16 com o locutor rastreado.** Só para os clipes que o
> usuário aprovou assistindo os previews da fase 2.

**Carregue:** `config/default.yaml` e `config/platforms/<platform>.yaml`. Os
perfis em `config/profiles/` só do perfil de cada candidato — não a pasta toda.

**Subagentes desta fase:** `edit-director` e `quality-controller`.

---

## 1. Direção de edição

Subagente `edit-director`, **só para os aprovados**. Produz `11-edit-plans.json`
com ordem real dos segmentos, layout e crop anchor, punch-ins motivados, cortes
e pausas removíveis, cards, chunks de legenda, mix de áudio, categoria e nome de
saída.

### Os dois layouts

| Layout | Quando | O que faz |
| --- | --- | --- |
| `cover` | uma pessoa, ou plano em que o locutor cabe sozinho | crop único 9:16 seguindo o locutor, com punch-in opcional |
| `split` | 2–3 pessoas no mesmo plano que não cabem lado a lado | quadro inteiro em cima (contexto), crop fechado embaixo (leitura) |

No `split` a metade de cima é o frame **inteiro sem crop**, em altura natural do
aspecto da fonte — 608px para uma fonte 1920×1080. É isso que garante que
nenhuma metade fica preta e nada distorce. Os 1312px restantes recebem o crop
fechado. Fonte já vertical **não aceita** `split`: o render recusa, e recusar é
melhor que entregar torto.

Ordem de preferência do enquadramento:

1. locutor ativo rastreado (`autoframe`);
2. composição de duas/três pessoas (`split`);
3. `crop_anchor_x` definido à mão por segmento;
4. centro, como último recurso.

## 2. Enquadramento automático por locutor ativo

```bash
./topclip corte autoframe --run <run-dir>
```

Reescreve `timeline` de cada plano com `crop_anchor_x` e `zoom` por subsegmento.
Detecta rostos com YuNet e decide **quem está falando** por correlação entre
movimento de boca e energia do áudio.

> **Em plano aberto nunca escolha o maior rosto.** Quem está mais perto da
> câmera tem o maior rosto e frequentemente não é quem fala. O critério é a
> correlação audiovisual, não a área. Movimento de boca sozinho já errou de
> forma confirmável: num monólogo, o ouvinte passivo pontuou mais que o locutor.

Requer `opencv-contrib-python` e `numpy` (opcionais — ver `INSTALAR.md`). Sem
eles, caia para anchor por segmento e **declare** no plano que o enquadramento é
manual. Não declare `autoframe` num plano que foi ancorado à mão.

Valide antes de renderizar:

```bash
./topclip corte validate-artifact --run <run-dir> --file 11-edit-plans.json
```

Não peça B-roll externo como se já existisse. Asset ausente é `optional`.

## 3. Decupagem do respiro

A `timeline` de cada clipe é uma **lista de segmentos que o render concatena**
(`_concat_segments`). É assim que o ar morto sai: o Edit Director emite dois
segmentos que pulam a pausa, em vez de um só que a contém.

**Respiro sai por padrão; `preserve_pause` é a exceção.** Corta hesitação, "é…",
ar entre frases, gagueira e retomada. Preserva a pausa antes do payoff, a espera
da reação depois da punchline, o riso do outro, e a respiração curta dentro da
frase — cortar essa vira locução de robô.

Ponto de partida a calibrar: silêncio sem função acima de ~0,4s colapsa para
~0,15–0,2s. **Não zere.**

Cada segmento obedece à mesma regra de borda do Clip Builder: 0,2–0,3s antes da
primeira palavra, 0,3–0,5s depois da última sílaba. Vale por segmento, não só
nas pontas do clipe.

Se a soma do que saiu passar de ~15% da duração, o problema provavelmente é o
in/out — devolva ao Clip Builder em vez de costurar aqui.

> **A legenda acompanha sozinha.** `map_transcript_to_timeline` remapeia o
> timing por palavra com offset acumulado por segmento, então o `.srt` sai
> correto contra o clipe renderizado e a `topclip-motion` continua ancorando motion
> no frame exato da palavra. Verificado no motor — não é suposição.

## 4. Quality Controller pré-render

Subagente `quality-controller` → `12-quality-review.json`. O revisor deve tentar
**derrubar** a seleção, não confirmar o trabalho anterior. Valide, depois:

```bash
./topclip corte finalize --run <run-dir>
```

Gera `13-final-clips.json`, `14-rejected-clips.json`, `15-run-report.md` e
`output/context-index.md`.

## 5. Render

```bash
./topclip corte subtitles --run <run-dir>
./topclip corte render --run <run-dir>
```

`subtitles` roda **mesmo sem queimar legenda**: os `.srt`/`.ass` são a decupagem
por clipe, com timing por palavra, e é o que a `topclip-motion` usa depois para
ancorar cada evento de motion no frame exato da palavra dita. Não pule.

Passe para a fase 4 para verificar e empacotar. Não declare sucesso aqui — o
render existir não é o mesmo que o render estar certo.
