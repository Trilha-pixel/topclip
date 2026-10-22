# Legenda — padrão TOPCLIP PAPEL v2

> **Estado: APROVADO** (clipe 06, 2026-08-29). Este é o padrão corrente da identidade.
> A v1 — cascata à esquerda, entrada animada em 4 frames, palavra-chave vermelha em toda
> frase, legenda no clipe inteiro — foi **reprovada**: lia como arrastada e competia com
> os motions. Não voltar a ela.

Tudo abaixo foi **medido frame a frame** numa referência do estilo (talking head vertical,
1492 frames a 30fps, 720x1280), não estimado a olho. Os números são o contrato.

| parâmetro | medido | como |
| --- | --- | --- |
| eixo horizontal | centro da linha em **359,5px de 360** (desvio mediano 1,0px) | bbox por linha, 54 blocos |
| entrada | **93% da massa no 1º frame**; deslocamento 0,7px; escala 0,0% | perfil de massa nos 6 primeiros frames |
| duração do bloco | mediana **10 frames a 30fps = 0,33s** (p25 0,20 / p75 0,53) | segmentação por IoU |
| cadência | **2,45 blocos/s** | 122 blocos em 49,7s |
| linhas por bloco | 1 na maioria (41 de 54) | perfil de linhas |
| corpo | glifo 38px@720 → **57px@1080** → corpo ~78px | altura de tinta |
| ênfase | **2,1×** o corpo | razão maior/menor linha dentro do bloco |
| cor | **94% branco**, 3,5% verde, 2,4% vermelho | classificação por pixel |
| vertical | centro do bloco em **0,696H** | bbox do bloco |
| largura de linha | p90 = **0,48W** | bbox por linha |

O **vertical** de 0,696H foi medido num podcast, com o queixo em y≈1102. Ele é o
padrão, não a regra: a legenda se posiciona pelo rosto (abaixo).

## As duas correções que mais mudam o resultado

**1. A fluidez não vem de easing, vem de ritmo.** A versão anterior animava a entrada
(subida + fade em 4 frames) porque "entrar duro" parecia bruto. Medido: a referência não
anima nada — é corte seco. O que dá fluidez é a CADÊNCIA: blocos curtos trocando ~2,45
vezes por segundo, cada um no tempo exato da palavra. Animar a entrada de um bloco que
dura 10 frames gasta metade da vida dele em transição, e é isso que lia como arrastado.

**2. A cor não é o dispositivo.** A versão anterior pintava a palavra-chave de vermelho
em toda frase. Na referência 94% das linhas são brancas. O acento só funciona porque é
raro — no clipe inteiro, duas palavras.

## Diagramação

- **Centrado**, nunca cascata alinhada à esquerda.
- Empilhamento **por tinta**, não pela métrica da fonte: mede-se a bbox real de cada
  linha e usa-se entrelinha `LEAD ≈ 0,96`. Só assim uma entrelinha menor que 1 fica
  previsível em vez de colidir. As linhas se tocando é a diagramação da referência.
- Dois registros: grotesco **black** para o corpo, **serifa itálica** de alto contraste
  para a ênfase. A palavra de ênfase aparece **sozinha** no bloco.
- Branco com **sombra projetada** (blur 7, offset y+5, alpha 0,62). Sem tarja e sem
  inversão de cor: a legibilidade vem da ALTURA (peito, sobre roupa escura), não de
  tratamento do fundo.
- Bloco de uma palavra só existe se ela **carrega sentido** — conjunção sozinha no meio
  da tela lê como erro de corte.

## Altura: abaixo do queixo mais baixo

Num vídeo selfie o rosto fica mais baixo que no podcast da referência. No clip-005 o
queixo desce até y≈1486 quando ele se inclina, e o padrão (CY 1330) cobria a boca — a
run corrigiu à mão para CY 1545 / TETO 1410, e ainda assim o pior frame ficou no limite.

Agora a altura sai do rosto. Com `video=` em `captions.configurar`, a primeira passada
de legenda amostra as janelas a 4 fps, detecta o rosto com o **YuNet** da skill de corte
(borda de baixo da caixa = queixo, ±20px, conferido nos dois clipes da run) e usa o
**pior frame** — o queixo mais baixo de todas as janelas (armadilha 38):

```text
TETO = max(1120, queixo + 12)          a tinta nunca sobe acima disto
CY   = max(1330, TETO + 48)            e o bloco desce só o necessário
CY  <= 1660 − 48                       nunca dentro da faixa de interface
```

Medido nos dois clipes da run: clip-005 → CY 1546 / TETO 1498; clip-010 → CY 1487 /
TETO 1439. Sem o modelo, cascata Haar do OpenCV (p90, corrigida para a caixa mais
curta). Sem rosto detectado ou sem `video`: posição fixa 1330/1120, **com aviso** —
confira num frame. O resultado fica em `00_brief/legenda_rosto.json` e só é refeito se
o vídeo ou as janelas mudarem. Para fixar à mão: `configurar(..., posicao=(cy, teto))`.

## Ênfase longa: o corpo desce até caber

A ênfase a 168px (2,1× o corpo) estoura em palavra longa: "MENSALIDADE," media 946px,
de x=67 a 1014 — dentro dos 120px da direita. Palavra nunca quebra, então o **corpo
dessa palavra** desce até ela caber em `LARGURA_MAX` (780px, 150px de cada lado); as
curtas continuam a 168. "MENSALIDADE," sai a 135px, o mesmo que a run escolheu à mão
(136). `LARGURA` (560) continua sendo só a quebra das linhas de corpo — usada como teto
da ênfase, ela levaria a palavra a 1,24× o corpo e mataria o dispositivo.

## Onde a legenda entra

A referência é talking head puro e legenda o vídeo inteiro. Com motion graphics o caso
muda: cutaway que já tem tipografia própria não pode receber legenda por cima — duas
tipografias no mesmo quadro brigam. Então a legenda **corre nas janelas livres e cala sob
os motions**. Janela menor que 2s fica de fora: legenda que pisca entre dois motions lê
como defeito.

Bloco **nunca atravessa um corte** do próprio clipe: junta o fim de uma frase com o começo
de outra e lê como erro de decupagem. Corte conhecido entra em `CORTES`.

### Cole o início da janela no fim da cena

As janelas são o **complemento exato** das cenas: começam onde uma cena termina e
terminam onde a próxima começa — `janelas=captions.janelas_livres(SHOTS, DUR)`. **Não
recue as bordas.** O recuo de 0,15s que se usava apagava a palavra que cai no vão: no
clip-005 sumiu o "Não" de "Não é difícil fazer" (a tela dizia "é difícil fazer", o
contrário do áudio). Somado à regra antiga (só entrava a palavra *inteira* dentro da
janela), o recuo levou ainda "isso", "Se", "para", "consegue", "serviço" e "Você" nos
dois clipes da run. O bloco não invade a cena porque é **preso à janela** — a sobra
depois da última palavra é cortada na borda.

Cada palavra é da janela ou da cena onde cai o **meio** dela: a palavra que atravessa a
borda fica com quem tem a maior parte dela.

### Cada palavra na tela enquanto é dita

O teto de duração do bloco (`MAXDUR`, 0,62s) existe para o bloco não ficar pendurado
depois da fala — não para cortar a fala. Ele cortava: no clip-010 "mas também para"
saía em 38,12s e o "para" (38,14s) ia à tela **antes** de ser dito e sumia justo quando
era dito; no clip-005, "de você ter um" mostrava "ter um" adiantado. Agora o bloco
nunca sai antes de a última palavra dele terminar, e o bloco que fica longo porque a
fala é lenta se **divide** na fronteira de palavra mais perto do meio — só onde os dois
lados têm palavra de conteúdo (nunca "de um" sozinho). O `check()` para com erro se
qualquer palavra não estiver na tela enquanto é dita.

`captions.check()` roda **antes** do render e para com erro se alguma palavra é dita
com o rosto na tela e fica sem legenda — fora de toda janela e fora de toda cena —,
com destaque para negação ("não", "nunca", "nem", "nada"…). Janela curta (< 2s) entre
duas cenas gera aviso: se a legenda piscar ali, estique uma das cenas sobre o vão em
vez de tirar a janela.

## A tipografia também é impressa

**Decisão revertida.** A frase de impacto ficava sem boil, com o argumento de que seria
"tipografia limpa contra um mundo que treme". Errado: na referência a tipografia é
impressa em papel áspero — a borda da letra é **erodida**.

Mas não é o boil dos objetos. O preset `ink` tem ruído grosso e deformaria a FORMA da
letra. Para tipografia existe **`print`**: ruído fino (`size 22`, `amount 3.0`) que erode
a BORDA sem desmanchar o desenho. `print` **não escala** com `BOIL_SCALE` — é textura de
impressão, não intensidade de tremor.

`boil_ctx(None)` continua obrigatório antes da passada de legenda: sem ele o texto
herdaria o campo congelado do último frame da última cena.

## Sincronia

Exige transcrição **palavra a palavra** (faster-whisper com `word_timestamps=True`).
Sem ela não há corte seco possível — o corte seco só funciona porque cai no tempo exato
da palavra. Blocos não podem se sobrepor no tempo: com sobreposição o render escolhe o
primeiro que casa e o bloco seguinte entra atrasado, destruindo justamente a sincronia.
