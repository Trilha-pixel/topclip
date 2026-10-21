# 6. Regras de edição

## 6.1 Edição orientada a beats

A unidade de edição não é “um corte a cada X segundos”. É o beat semântico ou emocional.

Uma mudança visual é justificada quando ocorre:

- nova ideia;
- número importante;
- mudança de pessoa;
- contraste;
- prova;
- reação;
- virada;
- passagem de tempo;
- objeto citado;
- retomada após highlight.

## 6.2 Estrutura de abertura

O primeiro frame deve conter pelo menos uma âncora:

- rosto expressivo;
- objeto relevante;
- texto específico;
- consequência;
- número;
- ação já em andamento.

Evitar:

- fade-in;
- logo longo;
- silêncio não intencional;
- plano vazio;
- frase começando pela metade;
- texto abstrato como “VOCÊ PRECISA VER ISSO”.

## 6.3 Highlight e retorno no tempo

Quando o highlight vem depois:

```text
HIGHLIGHT
↓
CORTE CLARO DE RETORNO
↓
CONTEXTO MÍNIMO
↓
CONTINUAÇÃO APÓS O TRECHO JÁ USADO
↓
PAYOFF
```

O retorno precisa ser compreensível, mas não exige efeito chamativo. Pode usar corte seco, card breve ou mudança de enquadramento.

## 6.4 Remoção de pausas

Remover:

- silêncio técnico;
- hesitação sem função;
- repetição de palavra;
- respiração excessiva entre frases independentes.

Preservar:

- pausa antes da revelação;
- timing cômico;
- reação;
- emoção;
- mudança de decisão;
- respiração que evita corte artificial.

Default técnico: silêncios acima de 550 ms são candidatos, não remoção automática. Silêncios de 250–550 ms só devem ser tocados com razão editorial.

## 6.5 Jump cuts

Jump cut pode:

- remover tempo morto;
- condensar contexto;
- aumentar clareza;
- separar beats.

Não deve:

- fazer a pessoa parecer dizer algo que não disse;
- apagar qualificações importantes;
- transformar dúvida em certeza;
- destruir continuidade emocional.

## 6.6 Punch-ins

Defaults:

- escala 1.05–1.15;
- duração mínima de 1,2s;
- não alternar sem motivo;
- evitar zoom em toda frase;
- usar em número, confissão, reação, mudança de argumento ou prova.

## 6.7 Crop vertical

Ordem de preferência:

1. rosto/objeto principal rastreado;
2. composição de duas pessoas;
3. crop anchor definido por segmento;
4. centro como fallback.

O `scripts/autoframe.py` resolve 1 e 2 automaticamente: detecta rostos com YuNet,
identifica **quem está falando** por correlação entre o movimento da boca e a energia
do áudio, e grava `crop_anchor_x` + `zoom` por subsegmento. O renderer continua o mesmo.

Regra decisiva: **em plano aberto nunca escolha o maior rosto**. Quem está mais perto
da câmera tem o maior rosto e frequentemente não é quem fala. O critério é a
correlação audiovisual, não a área.

Quando não houver locutor detectável, cai para anchor de segmento e depois centro.

### Os dois layouts

| Layout | Quando usar |
| --- | --- |
| `cover` | uma pessoa, ou plano em que o locutor cabe sozinho no 9:16 |
| `split` | 2–3 pessoas no mesmo plano que não cabem lado a lado num crop estreito |

No `split`, a metade de cima é o **quadro inteiro sem crop** — contexto, todo mundo
na mesa — em altura natural do aspecto da fonte. Para 1920×1080 isso dá 608px em
cima e 1312px embaixo, que recebem o crop fechado em quem sustenta a fala.

A altura natural não é um detalhe estético: é o que garante que a metade de cima
não distorce e que nenhuma metade fica preta. `scripts/render.py` calcula a
geometria sozinho a partir das dimensões da fonte; o plano só declara `layout` e
`crop_anchor_x`. Fonte já vertical é recusada com erro explícito em vez de gerar um
split degenerado.

Nunca deixar metade do split preta ou vazia. Se não sobra conteúdo para cima,
repetir o mesmo plano mais aberto — nunca cor sólida.

### O crop pode precisar mudar dentro do mesmo plano

Ausência de corte de câmera **não** significa enquadramento estático: a câmera do
bruto pode zoomar durante o próprio clipe. Antes de decidir por um crop estático,
olhar o span horizontal por bucket de tempo. Variação acima de ~25% entre buckets
exige enquadramento por subsegmento — que é o que `autoframe` já produz.

Salto de enquadramento vai onde já existe corte de câmera ou fronteira de turno de
fala. **Nunca no meio de uma palavra.**

## 6.8 Cards e texto

Use card quando:

- nome ou entidade é indispensável;
- número precisa ser visto;
- pergunta organiza a fala;
- transição temporal precisa ficar clara;
- print ou gráfico é citado.

Não use card para repetir cada palavra da legenda.

## 6.9 B-roll

Prioridade:

1. imagens do próprio vídeo;
2. tela compartilhada existente;
3. objeto mostrado;
4. reação de quem realmente reagiu naquele momento;
5. asset fornecido pelo usuário.

B-roll externo não é inventado. O plano pode sugerir asset opcional, mas o rough cut deve funcionar sem ele.

## 6.10 Transições

Default: corte seco.

Use transição especial somente para:

- volta no tempo;
- passagem de lugar;
- mudança de capítulo;
- comparação antes/depois;
- mudança de fonte visual.

## 6.11 Ritmo por perfil

### Resposta rápida

- baixa tolerância a preâmbulo;
- texto direto;
- cortes em raciocínio concluído;
- demonstração cedo.

### História

- preservar microexpressões;
- permitir pausas com tensão;
- ritmo acelera em contexto e desacelera na virada.

### Humor

- proteger setup e reação;
- não colocar SFX que explique a piada;
- não antecipar punchline na legenda.

### Opinião

- manter qualificação relevante;
- mostrar razão e consequência;
- evitar transformar nuance em ataque absoluto.

## 6.12 Legenda aqui é decupagem, não queima

Esta skill entrega o vertical **limpo**. Os arquivos `captions.srt`/`.ass` são
gerados como dado de decupagem — timing por palavra — porque é deles que a skill
`topclip-motion` tira a âncora de cada evento de motion no frame da palavra dita.

Segmentar os chunks por sentido, não por contagem cega de palavras. A queima
acontece depois, na topclip-motion, junto com o motion, num passe só.

Para publicar um clipe sem motion, ligar `make_captioned_version` no config: aí
esta skill queima a legenda padrão do pacote.

## 6.13 Qualidade de imagem

Renderer default:

- 1080x1920;
- H.264;
- pixel format yuv420p;
- frame rate herdado ou normalizado conforme config;
- `faststart`;
- bitrate/CRF configurável.

Não aplicar saturação, HDR, sharpen ou glow automaticamente.
