# Registros visuais

Tres cenas seguidas de "mesa + objeto + fita" leem como a mesma cena. **Alterne o
registro**, nao so o objeto. Cada registro tem um jeito proprio de compor, de anotar e
de animar.

| Registro | Quando usar | Heroi | Anotacao | Acento |
| --- | --- | --- | --- | --- |
| **Mesa de pesquisa** | objeto concreto sendo nomeado | objeto fotografado top-down | fita + marcador | amarelo |
| **Documentario retro** | "funcionando", "rodando", passagem de epoca | monitor CRT, aparelho antigo | nenhuma — a tela fala | fosforo ambar |
| **Foto em cartao** | pessoa, cena, prova de que alguem fez | copia impressa com margem branca | circulo manual | a cor da propria luz |
| **Dado a mao** | numero que o falante estima ou corrige | pizza/barra em hachura de marcador | o proprio numero, em marcador | amarelo da hachura |
| **Processo** | "de X para Y", transformacao | dois objetos + seta | seta longa | amarelo no fim |
| **Anotacao de campo** | faixa, ordem de grandeza, lembrete | cartao com escrita a mao | seta curta entre as palavras | nenhum |

Regra pratica: **nao repita registro em cenas vizinhas**. Se M2 e mesa de pesquisa,
M3 nao pode ser.

**Receitas prontas por registro** (`referencias/receitas.md`, exemplo de cada uma no
`compose.py` que todo projeto recebe):

| Registro | Receita | Funcao do kit |
| --- | --- | --- |
| Mesa de pesquisa | fita-etiqueta dimensionada pela palavra | `tape_label` |
| Dado a mao | barras em hachura com contorno em 2 passadas | `hatch_bar` |
| Dado a mao | conta montada a mao, item a item | `hand_tally`, `conta`, `sublinhado_duplo` |
| Processo | etiqueta de preco com barbante (destino da seta) | `price_tag` |
| Anotacao de campo | item escrito e riscado pela tinta | `ink_bbox`, `strike_ink` |
| Anotacao de campo (overlay) | tira de papel no topo, sobre o video | `bilhete`, `nota_topo` |
| todos | papel no tamanho de uso (pautado, quadriculado, kraft) | `scrap`, `fita` |

## Documentario retro — a tela

O conteudo da tela e desenhado por nos, **em blocos, nunca em texto**:

- a nota do editor costuma proibir interface falsa de aplicativo;
- escrever codigo na tela e inventar conteudo;
- no tamanho em que o aparelho aparece (~330px), nenhum caractere seria legivel.

Blocos de comprimento variavel, aparecendo linha a linha, com cursor piscando, leem
como "tem coisa rodando" sem afirmar nada. Some scanlines e vinheta do tubo.

O quadrilatero da tela precisa ser **medido** no recorte, nao estimado: o aparelho fica
em tres-quartos, a tela e um trapezio, e um paste reto denuncia. `cv2.approxPolyDP` no
contorno da regiao escura + `getPerspectiveTransform`. Ver `lib/crt.py`.

O registro retro e **tempero, nao idioma**. Uma cena por video.

## Dado a mao

Numero que o falante estima, arredonda ou corrige NAO vai em tipografia de dado limpo —
ganharia autoridade que a fala nao tem. Vai em **hachura de marcador**, com o numero
escrito a mao.

Ordem de desenho, que e a ordem da mao: contorno em duas passadas → raios → hachura.
Ver `motor.hand_pie()`.

Quando o falante se corrige ("90… 50%"), o numero que vale e o ULTIMO. Por o primeiro
na tela contradiz o audio.
