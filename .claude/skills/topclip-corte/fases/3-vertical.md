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

Logo depois do Edit Director, as bordas dele — inclusive as dos cortes de
respiro, que são novas — vão para o vale de energia:

```bash
./topclip corte bordas --run <run-dir>
```

É o mesmo comando da fase 2; com `11-edit-plans.json` presente ele trabalha no
plano e não toca no 06 (então as revisões 07/09 continuam valendo). Ao mover uma
borda, **recalcula sozinho todos os tempos de clipe do plano** pela posição na
fonte: `clip_start`/`clip_end` da timeline, `captions.chunks`, `cards`,
`motion_anchors`, `punch_ins`, `breath_cut_before` e `breath_decupage`. Coisa
grudada num corte (punch-in que entra no corte) acompanha o corte; coisa no meio
de um segmento acompanha a fala.

Ordem de preferência do enquadramento:

1. locutor ativo rastreado (`autoframe`);
2. composição de duas/três pessoas (`split`);
3. `crop_anchor_x` definido à mão por segmento;
4. centro, como último recurso.

## 2. Enquadramento automático por locutor ativo

```bash
./topclip corte autoframe --run <run-dir>
```

Reescreve `timeline` de cada plano com `crop_anchor_x` e `zoom` por subsegmento,
e recalcula os tempos de clipe de cada subsegmento (eles herdavam o
`clip_start`/`clip_end` do segmento inteiro).
Detecta rostos com YuNet e decide **quem está falando** por correlação entre
movimento de boca e energia do áudio.

> **Em plano aberto nunca escolha o maior rosto.** Quem está mais perto da
> câmera tem o maior rosto e frequentemente não é quem fala. O critério é a
> correlação audiovisual, não a área. Movimento de boca sozinho já errou de
> forma confirmável: num monólogo, o ouvinte passivo pontuou mais que o locutor.

### Como ele decide, plano a plano

1. **Cortes de câmera** com PySceneDetect (`AdaptiveDetector`, sobre frames que
   o ffmpeg decodifica). Ele compara cada frame com a média dos vizinhos, então
   pan e zoom de câmera não viram corte. Sem o pacote `scenedetect`, cai no
   limite fixo do ffmpeg (`scene > 0.35`).
2. **Amostra esparsa.** YuNet em só 3 frames do plano: início, meio e fim. Plano
   com mais de 20s ganha 1 frame a cada ~5s, porque 3 fixos não veem a pessoa
   sair do lugar no meio, nem a câmera zoomando dentro do corte (docs/12). A
   amostra para no primeiro frame que já manda para a densa.
3. **Um rosto só, parado e do mesmo tamanho em todas as amostras** → crop
   estático na mediana. "Parado" é variar menos que o `DEADZONE` (55px na
   fonte); "mesmo tamanho" é a largura do rosto variar até 25%. A análise
   densa nem roda.
4. **Qualquer outra coisa → análise densa** (5 fps + correlação boca × áudio,
   com histerese): vários rostos, rosto que anda, zoom, rosto ausente em alguma
   amostra, nenhum rosto, frame que não decodificou. Na dúvida, é densa: errar
   o crop custa mais que alguns segundos de processamento.

| Plano | Caminho | Por quê |
| --- | --- | --- |
| close parado, uma pessoa | `amostrado` | a amostra já basta para o crop |
| mesa com 2+ pessoas | `denso` | precisa da correlação para achar quem fala |
| uma pessoa que anda / câmera que zooma | `denso` | o crop estático cortaria gente |
| B-roll, tela, sem rosto | `denso` | confere em 5 fps antes de centralizar |

Rosto em zona de `--exclude-zones` (TV do cenário) não conta nem na amostra.

**Diagnóstico.** Cada plano sai no relatório com `caminho` (`amostrado` ou
`denso`), `amostras`, `motivo` (por que a amostra não bastou, ex.: `"3 rostos na
amostra"`, `"rosto andou 320px (deadzone 55px)"`) e `detector_cortes`
(`pyscenedetect` ou `ffmpeg`), e cada segmento ganha a contagem `caminhos`. O
relatório sai com `./topclip py .claude/skills/topclip-corte/scripts/autoframe.py
--video <v> --segments <segs.json> --out <rel.json>`; o `./topclip corte autoframe
--run` só grava a timeline.

**Custo.** A amostra para no primeiro frame que já decide pela densa: numa mesa,
1 frame por plano. No caso simulado de `docs/12` (60s em 1080p, 4 planos), o
tempo total de cortes + enquadramento caiu ~20–40% num podcast típico (três
closes e uma mesa) e ~35–60% numa entrevista só de closes. Num programa que é
mesa o tempo todo, todo plano cai na densa e a amostra vira custo a mais,
~10–15%.

**O limite da amostra.** O que acontece entre duas amostras e desfaz antes da
seguinte não aparece: alguém que entra e sai do quadro em menos de ~5s num
close parado. Num close isso não muda o crop certo. Se mudar, use
`--exclude-zones` ou ancore o segmento à mão.

Requer `opencv-contrib-python` e `numpy` (opcionais — ver `INSTALAR.md`); o
`scenedetect` também é opcional. Sem `cv2`, caia para anchor por segmento e
**declare** no plano que o enquadramento é manual. Não declare `autoframe` num
plano que foi ancorado à mão.

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

> **O plano também.** Mudou uma borda no 11 — por pedido do usuário, à mão —
> **não recalcule nada à mão**: rode `./topclip corte bordas --run <run-dir>`. Cada
> segmento guarda em `synced_source` a fonte com que os tempos de clipe dele foram
> calculados, e é por ele que o script sabe o que mudou. O
> `validate-artifact` do 11 acusa `tempo_de_clipe_desatualizado` se alguém
> esquecer. Na run de `docs/12` (12.7), recalcular à mão custou duas rodadas de QC.

## 4. Quality Controller pré-render

**Antes** de chamar o QC, o portão das revisões:

```bash
./topclip corte revisoes --run <run-dir>
```

Confere os clipes do 11: nenhuma revisão (07, 09) feita sobre versão anterior do
corte e nenhum plano com tempo de clipe velho. Se não sair `limpo: true`, refaça
o que ele lista **agora** — revisão de feed velha descoberta só no `finalize`
foi o que fez a run de `docs/12` rodar o QC duas vezes.

Subagente `quality-controller` → `12-quality-review.json`. O revisor deve tentar
**derrubar** a seleção, não confirmar o trabalho anterior. Valide, depois:

```bash
./topclip corte finalize --run <run-dir>
```

Gera `13-final-clips.json`, `14-rejected-clips.json`, `15-run-report.md` e
`output/context-index.md`. Se alguma revisão dos clipes do 11 for de versão
velha do corte, o `finalize` **para** e diz o que refazer, em vez de consolidar
status errado.

### Quando o usuário manda seguir mesmo assim

Clipe abaixo do gate (`WEAK`) ou que a revisão mandou refazer (`REBUILD`) só vai
para render se o **usuário** disser que quer seguir. Aí:

```bash
./topclip corte finalize --run <run-dir> --seguir clip-005,clip-010 \
  --motivo "usuário quer publicar mesmo com nota 6,9"
```

O clipe entra no `13-final-clips.json` com `user_override` (quem, quando, o que
ele disse) e o render aceita. O status **não muda**: continua `WEAK` no
relatório, numa seção própria. A decisão fica no manifesto e vale para os
próximos `finalize` — enquanto o corte for o mesmo; mudou o corte, pergunte de
novo. `REJECTED` (hard fail) e `DUPLICATE` não se forçam. Para desfazer:
`--nao-seguir clip-005`. Nunca chame `render_clip` direto para contornar o
gate.

## 5. Render

```bash
./topclip corte subtitles --run <run-dir>
./topclip corte render --run <run-dir>
```

O `render` faz os `APPROVED`, os `LONG_CLIP` e os que têm `user_override`.
`subtitles` roda **mesmo sem queimar legenda**: os `.srt`/`.ass` são a decupagem
por clipe, com timing por palavra, e é o que a `topclip-motion` usa depois para
ancorar cada evento de motion no frame exato da palavra dita. Não pule.

Passe para a fase 4 para verificar e empacotar. Não declare sucesso aqui — o
render existir não é o mesmo que o render estar certo.
