# 1. Análise completa da Skill original

## 1.1 Veredito

A Skill original **funcionaria para encontrar clipes editorialmente defensáveis**, mas não funcionaria de forma consistente como um sistema autônomo de produção para TikTok e Instagram.

Ela resolve muito bem o problema “este trecho consegue existir fora do podcast?”. Ainda não resolve completamente o problema “este trecho consegue sobreviver ao comportamento de rolagem, entregar valor rápido, ser editado de modo coerente e sair como arquivo publicável?”.

Classificação da versão original:

| Dimensão | Avaliação | Observação |
|---|---:|---|
| Entendimento global do vídeo | 9/10 | Exige mapear contexto antes de cortar. |
| Reconstrução narrativa | 9/10 | Permite highlight fora de ordem e proíbe replay inútil. |
| Independência do clipe | 9/10 | O teste do espectador cego é excelente. |
| Deduplicação | 9/10 | Detecta contenção e sobreposição temporal. |
| Payoff | 9/10 | Não aceita frase forte sem resolução. |
| Psicologia de feed | 5/10 | Hook existe, mas velocidade de promessa e primeiro valor não são medidos. |
| Perfis de conteúdo | 4/10 | Usa uma estrutura geral para formatos com ritmos diferentes. |
| Métricas determinísticas | 3/10 | Solicita cálculos, mas não define ferramentas que os executem. |
| Edição e legenda | 2/10 | Audita elementos visuais, mas não cria um plano técnico completo. |
| Execução no Claude Code | 3/10 | Não possuía frontmatter, contratos de entrada, scripts, schemas ou pastas de estado. |

## 1.2 O que já estava muito correto

### Entender antes de caçar

A ordem Context Mapper antes de Clip Hunter impede um erro comum: escolher uma frase impactante cujo significado depende de algo dito vinte minutos antes.

### Distinguir frase viral de clipe viral

A Skill original não confunde “frase destacável” com “vídeo completo”. Ela exige hook, contexto, desenvolvimento e payoff. Isso é mais maduro do que a maioria dos prompts de clipping.

### Reconstruir sem replay

A permissão para usar uma revelação como highlight, voltar ao contexto e continuar depois do ponto já exibido é uma regra editorial forte. Ela elimina o padrão amador de repetir exatamente a mesma fala.

### Testar como conteúdo isolado

O Blind Reviewer é o mecanismo mais importante da versão original. Ele reduz o viés de quem conhece o episódio inteiro e, por isso, preenche mentalmente lacunas que o público não consegue preencher.

### Não maximizar quantidade

A regra de que um vídeo pode ter três, dez, vinte ou nenhum clipe excelente protege o sistema de gerar cortes artificiais para cumprir meta.

## 1.3 O que faltava para o feed

### A Skill perguntava “o primeiro segundo desperta curiosidade?”, mas não media a promessa

Curiosidade vaga não é suficiente. O espectador precisa perceber rapidamente pelo menos uma destas coisas:

- o que vai descobrir;
- qual transformação está em jogo;
- qual número ou consequência importa;
- qual crença será contrariada;
- qual pergunta receberá resposta;
- por que aquela pessoa tem autoridade para falar.

O harness adiciona `proposition_latency_seconds`: tempo até o espectador conseguir formular “este vídeo é sobre X e vale assistir porque Y”.

### A Skill não media o primeiro valor

Um hook pode prometer bem e ainda manter o público esperando demais. Por isso foi criado `first_value_latency_seconds`: tempo até a primeira informação que já recompensa parcialmente a permanência.

Exemplo ruim:

> “Você não vai acreditar no que aconteceu...”
> 18 segundos de preparação genérica.

Exemplo melhor:

> “A marca ofereceu quatro milhões — mas o momento em que ela fez a oferta mudou toda a negociação.”

A segunda versão abre uma lacuna específica e entrega valor parcial imediatamente.

### A Skill não media dívida de contexto

“Dívida de contexto” é o número de entidades, relações e acontecimentos que o espectador precisa entender antes de receber valor.

Um clipe pode ser autocontido no total e ainda ser lento no início. Se os primeiros oito segundos servem apenas para apresentar quatro pessoas e duas empresas, ele perde para conteúdos mais fáceis de processar.

### A Skill não diferenciava ritmos

Um tutorial, uma revelação e uma história não devem obedecer ao mesmo relógio.

- resposta rápida: pergunta ou resultado quase imediatamente;
- contradição: crença comum e quebra até o segundo 2–3;
- dinheiro: número ou escala cedo;
- história: consequência ou risco cedo, contexto depois;
- humor: setup curto, ruptura clara, reação preservada;
- long clip: valor acumulativo e capítulos internos.

### A Skill não exigia microprogressão

Um clipe de 60 segundos não pode depender de um único payoff no final. Ele precisa produzir beats: prova, contraste, número, mudança, mini-resposta, reação, nova pergunta ou implicação.

O harness mede:

- `semantic_beat_count`;
- `average_seconds_per_beat`;
- `maximum_seconds_without_new_value`.

### A Skill não distinguia curiosidade legítima de clickbait

O novo sistema verifica:

- a promessa é específica?
- o conteúdo realmente possui a resposta?
- a resposta é proporcional ao suspense?
- o highlight foi retirado de modo que distorce o significado?
- existe uma entrega parcial antes do payoff final?

## 1.4 O que faltava para execução

### Contrato de entrada

Era necessário especificar vídeo, transcript, modo análise, modo verificação e modo renderização.

### Estado persistente

Sem arquivos intermediários, o modelo poderia afirmar que realizou várias passagens dentro da mesma resposta, sem separação verificável. Agora cada passagem produz um JSON próprio.

### Matemática em código

Sobreposição, contenção, repetição, duração e validação não devem depender de estimativa do LLM.

### Revisão realmente cega

Na versão operacional, o Blind Reviewer não possui ferramentas de leitura e recebe somente o clipe reconstruído. Ele não vê justificativas nem scores anteriores.

### Saída de edição

A Skill original terminava em JSON editorial. O harness termina em plano de edição, SRT, ASS, vídeo limpo, vídeo legendado e organização por contexto.

## 1.5 Falhas que o novo sistema deve impedir

1. **Hook com contexto atrasado:** frase forte, mas sujeito desconhecido.
2. **Pergunta sem resposta rápida:** introdução longa antes de qualquer valor.
3. **Número sem mecanismo:** “ganhou 4 milhões”, sem explicar como ou por quê.
4. **História sem stakes:** cronologia correta, porém sem razão para continuar.
5. **Falso suspense:** ocultar informação óbvia que poderia ser dita no início.
6. **Replay do highlight:** mesma fala aparece duas vezes.
7. **Clipes irmãos:** três cortes contam a mesma história com pequenas diferenças.
8. **Legenda decorativa:** texto rápido demais, mal segmentado ou concorrendo com o rosto.
9. **Overediting:** zoom e transição sem relação com mudança de significado.
10. **Montagem enganosa:** combinação de falas reais que altera sentido ou causalidade.

## 1.6 Conclusão

A lógica original deve ser preservada como núcleo editorial. A evolução necessária não é substituir contexto por velocidade; é **comprimir o contexto até o mínimo suficiente, entregar valor antes e manter progressão sem falsificar a fala**.
