# Saída dos cutaways

Corte seco de uma composição cheia direto para o rosto lê como tranco. E **repetir a
mesma saída** em todas as cenas vira tique. Três tipos, alternados, nunca dois iguais
seguidos:

| Tipo | O que acontece | Quando |
| --- | --- | --- |
| `slide` | a mesa é puxada para fora do quadro e o vídeo aparece atrás | padrão |
| `wipe` | uma folha atravessa a lente; atrás dela o vídeo já está lá | quando se quer o "clarão" |
| `push` | a câmera acelera para dentro e o corte cai na velocidade | fecho de ideia |

13 frames a 29,97fps (~0,43s), com aceleração (`ease_in`, t^2.4).

## Por que não flash branco nem whip pan

O guia de estilo lista os dois entre o que **mata o estilo**, junto com glitch e
"transições de template". Quando pedirem flash, entregue o `wipe`: dá o mesmo clarão,
mas **material** — é o "papel que cruza a lente" que o pack indica
(`09_TRANSITION_MAP §2`). Quando pedirem efeito de câmera, entregue o `push`, que é o
"zoom na prova" do mesmo documento.

Vale dizer isso ao diretor uma vez, e seguir. É o tipo de conflito que se resolve com
um equivalente, não com recusa.

## Implementação

Os cutaways renderizam em **RGBA**: a área que a mesa liberou fica transparente e o
`overlay` do ffmpeg deixa o vídeo original passar por baixo. O `push` é a exceção — o
quadro segue opaco e quem esconde o corte é a aceleração.

A folha do `wipe` usa um papel **diferente** do fundo da mesa (cartão de algodão frio
contra marfim), senão a passagem não lê.
