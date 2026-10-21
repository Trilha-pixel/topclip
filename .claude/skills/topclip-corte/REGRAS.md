# Regras invioláveis

## A missão: timesteps primeiro, vídeo bruto por último

A skill **nunca começa analisando o vídeo bruto**. Ela sempre parte de
transcript e timestamps. A ordem é fixa e não é uma opção entre outras:

```text
TIMESTEPS/TRANSCRIPT  →  SELEÇÃO (hook, desenvolvimento, payoff)  →  CORTE do bruto
        ↑ nunca pula esta etapa                                          ↑ só chega aqui
        ↑ nunca abre o vídeo pra "entender" antes disso                  depois de já saber
                                                                          exatamente onde cortar
```

Concretamente:

- `prepare` nunca decodifica o vídeo pra análise (índice visual) por conta
  própria. Ele lê transcript e metadados; nada mais.
- Context Mapper e Clip Hunter trabalham **inteiramente sobre o texto**. Para
  cada trecho candidato eles precisam responder três perguntas antes de
  qualquer corte existir: o que é o **hook** (a frase/fato que prende sem
  contexto), o que é o **desenvolvimento** (o que sustenta entre o hook e o
  payoff — mecanismo, prova, virada) e o que é o **payoff** (o que fecha a
  promessa). Sem essas três respostas, o momento não está pronto pra virar
  candidato — ele volta pro texto, não pro vídeo.
- O vídeo bruto só é aberto depois: para o corte em si (segmentos reais de
  áudio/imagem) e, escopado às janelas já escolhidas, para conferir recurso
  visual (`vch visual-index --windows`) e decidir enquadramento.
- Rodar índice visual do vídeo inteiro antes da seleção existir é o erro que
  já travou uma run inteira (ver `docs/12-erros-registrados.md`, §12.6). Não
  é "às vezes evitável" — é sempre a ordem errada.

## Divisão de responsabilidade

- O **modelo** decide contexto, narrativa, relevância, curiosidade, payoff e editabilidade.
- Os **scripts** calculam duração, interseção temporal, repetição, silêncio, normalização, enquadramento, arquivos e render.
- Nunca estime manualmente um valor que um script do pacote calcula.

## As onze regras

1. Nunca invente palavras que não existam na fonte.
2. Nunca faça montagem que altere causalidade, intenção ou cronologia relevante.
3. Nunca aprove um clipe na primeira passagem.
4. Nunca use score médio para esconder hard fail.
5. Nunca repita highlight no corpo sem propósito documentado.
6. Nunca entregue clipes semanticamente duplicados para aumentar quantidade.
7. Nunca use corte, zoom ou efeito apenas para "estimular". Toda mudança serve a um novo beat, clareza, emoção ou prova.
8. Nunca corte um rosto na borda do crop, nem deixe metade de split vazia.
9. Nunca trate transcript sem timestamp como suficiente para render preciso.
10. Nunca declare "viral garantido". O sistema estima publicabilidade; desempenho real exige teste na plataforma.
11. Nunca comece analisando o vídeo bruto. A seleção — incluindo identificar hook, desenvolvimento e payoff de cada candidato — roda inteira sobre transcript e timestamps; o vídeo só é tocado no passo de corte, depois que já se sabe exatamente onde cortar.

## Fronteira com a topclip-motion

Esta skill entrega o **vertical limpo**. Legenda queimada e motion graphics são da
`topclip-motion`, que compõe as duas coisas no mesmo passe sobre este arquivo.

- Não queime legenda aqui quando o clipe for seguir para motion.
- Não gere, recorte nem componha asset de motion aqui.
- Gere sempre `captions.srt`/`.ass`: são **decupagem**, não legenda queimada. A
  topclip-motion depende desse timing por palavra para ancorar cada evento na fala.

## Artefatos intermediários obrigatórios

Cada run preserva:

```text
00-manifest.json          08-technical-audit.json
01-media.json             09-blind-review.json
02-transcript.json        10-deduplication.json
03-visual-index.json      11-edit-plans.json
04-context-map.json       12-quality-review.json
05-viral-moments.json     13-final-clips.json
06-candidates.json        14-rejected-clips.json
07-feed-review.json       15-run-report.md
```

Não pule arquivos silenciosamente. Quando uma etapa não se aplicar, registre
`skipped` e o motivo no manifest.

## Revisão cega

O Blind Reviewer recebe apenas: timeline reconstruída, transcript reconstruído,
duração estimada e descrição de elementos visuais que realmente aparecem.

Não forneça score anterior, justificativa, título promocional, status sugerido,
contexto completo do episódio nem o nome do agente que escolheu o clipe.

## Saída

`<workspace>/<run-id>/output/`, organizada por `primary_context`.
