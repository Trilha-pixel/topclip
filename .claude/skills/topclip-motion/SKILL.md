---
name: topclip-motion
description: Insere motion graphics (no estilo TopClip Papel — colagem editorial, papel marfim, fita crepe, anotação à mão — ou em Limpo, Impacto, Luxo e nos estilos do usuário, com o mesmo fluxo e o desenho de cada um) e legenda queimada dentro de um clipe vertical ja cortado (podcast, entrevista, talking head). Use quando o pedido for adicionar motion, ilustrar palavras-chave, animar trechos, "colocar uns motions nesse corte", "ilustrar essa fala", queimar legenda no clipe, ou melhorar e estender motions ja feitos. Cobre o processo inteiro: escolher as frases pelo transcript, gerar e recortar assets PNG, compor as cenas em camadas com registros visuais variados, legendar, revisar com rubrica, e montar o master sem tocar no audio. NAO use para video gerado do zero por IA de video.
---

# Motion editorial sobre footage

> Parte do **TopClip**. Todo caminho aqui é relativo à raiz do repositório,
> e todo comando roda a partir dela, pelo lançador `./topclip`.

Insere cenas de motion dentro de um clipe vertical que **já existe**, no estilo
`TOPCLIP PAPEL` (o padrão) ou em outro estilo da biblioteca — o fluxo é o mesmo, muda o
desenho (ver "O mesmo fluxo em todo estilo"). O áudio é congelado: não dá para reescrever a fala, então tudo se ancora
no que foi dito e em quando foi dito.

## A identidade viaja junto

Esta skill é um **kit fechado**, não só um método. Ver `IDENTIDADE.md`.

| | |
| --- | --- |
| `fontes/` | as 5 fontes da identidade, licenças livres, com os arquivos de licença |
| `biblioteca/assets/` (raiz do repo) | os assets oficiais do Papel |
| `minha-biblioteca/assets/` (raiz do repo, fora do git) | os assets desenhados nas runs do usuário — cresce com o uso |
| `minha-biblioteca/objetos.py` (fora do git) | os objetos do usuário para os estilos com lápis — saem em todo lápis |
| `biblioteca/estilos/` | os estilos oficiais (`./topclip estilo listar`); o Papel é o padrão |
| `lib/` | o motor, o kit com as **receitas**, o recorte, o CRT, a legenda, a transcrição, os dois templates |
| `exemplo/` | o bloco de configuração de um clipe real, a galeria das receitas (`exemplo/receitas/`) e os moldes dos desenhos do usuário |
| `verificar.py` | checagem de instalação — rode antes do primeiro projeto |
| `referencias/` | identidade, registros, **receitas**, transições, legenda, armadilhas, rubricas, prompts |

Quem instalar reproduz **este** visual, não um parecido.

## Requisitos de máquina

| | | Se faltar |
| --- | --- | --- |
| Python 3.10+ (`.venv/`) + `Pillow`, `numpy`, `opencv-contrib-python` | composição e recorte | nada roda |
| `ffmpeg` | montagem do master | os frames saem, o vídeo não |
| `faster-whisper` | transcript palavra a palavra | sem ancoragem e sem legenda |
| gerador de imagem | **opcional** — só para quem quer objeto com cara de foto | o Claude desenha o asset em código (seção 3) |

**Antes do primeiro projeto:** `./topclip verificar`. Faltou algo: `./topclip instalar`.

**Transcript.** Insumo sem substituto — motion ancorado e legenda em corte seco dependem
de saber em que frame cada palavra foi dita. Gere com:

```bash
./topclip motion transcrever PROJETO/00_brief/fonte.mp4 PROJETO/00_brief/transcript_palavras.json
```

Formato: `[{"w": "palavra", "t": 12.28, "e": 12.54}, ...]`, em segundos **do clipe**.
Já tem transcript em outro formato? Converta para este — não reescreva o motor.

**`night_photo.py` e `crt.py` trazem constantes calibradas** para as fotos do kit
(recorte, curva de cor, quadrilátero da tela). Ao gerar fotografia nova, recalibre — os
dois scripts dizem onde.

## Regra-mãe

> **Mostrar uma prova, apontar o detalhe, concluir — nesta ordem.**
> Movimento acompanha raciocínio. Nada se mexe só para "dar dinâmica".

## O que NÃO usar

Não gere vídeo com IA de vídeo. A composição por camadas em PIL dá controle exato de
posição, tempo e grafia, e produz o mesmo resultado com custo muito menor. Os objetos
são **desenhados em código** (`lib/desenho.py`); IA de imagem é opcional, para quem
quer um objeto com cara de foto.

## Ordem de execução

Cada etapa tem uma trava. Não avance sem ela.

| # | Etapa | Saída | Trava |
| --- | --- | --- | --- |
| 1 | **Ancorar** | tabela palavra → frame | transcript palavra-a-palavra existe |
| 2 | **Escolher frases** | `PLANO_MOTION.md`: tabela entra/não-entra com motivo, objeto de cada cena | laudo D0 aprovado: frase com objeto vira desenho |
| 3 | **Assets** | PNG com alfa por objeto (Papel) ou objeto no lápis (os outros) | biblioteca primeiro; o que faltar, desenhado em `minha-biblioteca/desenho.py` (Papel) ou `minha-biblioteca/objetos.py` (lápis) |
| 4 | **Recortar** | PNG com alfa | só para asset de gerador de imagem; laudo D1 aprovado |
| 5 | **Compor** | 4 estados por cena + folha `<cena>_ESTADOS.png` | laudo D2/D3 aprovado |
| 6 | **Blueprint + transições** | um .md por cena + mapa | entrada e saída definidas |
| 7 | **Legenda** | sequência RGBA de duração total | `captions.check()` passa: nenhuma palavra dita fica de fora |
| 8 | **Render + mux** | `RASCUNHO.mp4` na revisão, master uma vez no fim | duração, cadência, quadros e MD5 do áudio batem (conferido sozinho) |

Leia `referencias/rubricas-diretor.md` antes da etapa 2 e aplique em 2 (o D0 é o plano), 3, 4, 5 e 7.
Escolha o registro de cada cena em `referencias/registros.md` **antes** de compor, e
procure a receita dele em `referencias/receitas.md` — o `compose.py` já vem com uma
cena-exemplo pronta por receita.
Legenda queimada: `referencias/legenda.md`. Saídas e transições: `referencias/transicoes.md`.
Boil (o objeto redesenhado a cada passo): `referencias/boil.md`.

---

## 1. Ancorar no transcript

Converta cada palavra para frame local do plano:

```
frame24 = (t_palavra − t_início_do_plano) × 24
```

**Todo evento visual se trava numa palavra**, com tolerância de ±3 frames. Um elemento
que entra fora da palavra vira enfeite: o espectador não liga uma coisa à outra.

Sem transcript com timestamp por palavra, pare e produza um antes (Whisper com
`word_timestamps`, ou legendas do YouTube).

## 2. Escolher as frases

Entra a frase que tem **objeto**. Não entra a que só tem conceito.

| Critério | Entra | Não entra |
| --- | --- | --- |
| tem substantivo concreto ou unidade de medida | ✓ | |
| é a instrução ou o payoff do clipe | ✓ | |
| número que o falante **se autocorrige** ou estima ("sei lá") | | ✗ em tipografia de dado |
| piada lateral, aparte | | ✗ |
| já ilustrado por outra cena | | ✗ |
| grandiloquência sem objeto ("primeira vez na história") | | ✗ |

**Registro de fato vs. opinião.** Número dito pelo entrevistado só vira gráfico limpo se
for verificável. Estimativa vira **marcador manual** ou não entra.

**Varie o REGISTRO, nao so o objeto.** Tres cenas seguidas de "mesa + objeto + fita"
leem como a mesma cena, por mais que os objetos mudem. Nunca repita registro em cenas
vizinhas — a tabela esta em `referencias/registros.md`.

**Densidade.** Mire em 30–40% do clipe coberto por motion. Abaixo de 20% o vídeo fica
parado; acima de 50% o rosto some. Deixe pelo menos 1,5s de rosto entre cenas.

**Escreva a tabela dos que ficaram de fora, com o motivo.** A decisão descartada é tão
útil quanto a adotada, e evita refazer a discussão depois.

**O plano** (`00_brief/PLANO_MOTION.md`) tem as duas tabelas. A das que entram traz, por
cena: janela, âncoras (palavra@s), registro, **objeto** e o que a cena mostra. A coluna
Objeto diz de onde ele vem — `relogio` (biblioteca), `xicara` (novo, desenhado agora) ou
`—` (cena de texto, com o motivo: a frase não tem objeto). O Diretor confere o plano no
**D0**, antes de desenhar qualquer coisa (`referencias/rubricas-diretor.md`).

## 3. Conseguir os assets

**Estilo com lápis** (Limpo, Impacto, Luxo e os remixes deles — o `estilo/resolvido.json`
tem `"lapis"`): o objeto não é PNG, é geometria desenhada pelo lápis do estilo. Veja
"O mesmo fluxo em todo estilo", no fim, e pule as etapas 3 e 4 daqui. O que segue é o
Papel.

Nesta ordem — pare no primeiro que resolver:

1. **Biblioteca.** `biblioteca/assets/` (oficiais, lista em `biblioteca/MANIFESTO.md`) e
   `minha-biblioteca/assets/` (os desenhados nas runs, lista em
   `minha-biblioteca/MANIFESTO.md`). O `./topclip motion novo` já copiou os dois para
   `07_assets/` do projeto.
2. **Desenhar em código — o padrão.** Escreva `desenha_<NOME>(seed)` em
   `minha-biblioteca/desenho.py`, registre em `ASSETS` e gere. Na primeira vez, copie o
   molde (ele importa as ferramentas de `lib/desenho.py`):

   ```bash
   mkdir -p minha-biblioteca && cp .claude/skills/topclip-motion/exemplo/desenho_usuario.py minha-biblioteca/desenho.py
   ./topclip py minha-biblioteca/desenho.py minha-biblioteca/assets --so <NOME>
   ```

   **Nunca em `lib/desenho.py` nem em `biblioteca/`**: são do repositório, e o próximo
   `git pull` do usuário daria conflito. Asset só vira oficial quando quem mantém o
   repositório pede.

   **Papel grande** (folha de caderno, quadriculado, kraft acima de ~450px) não se
   amplia do `A10_SCRAPS`, que borra: `kit.scrap("pautado", w, h)` desenha o retalho no
   tamanho de uso, com pauta e grade em escala de caderno real.

   O PNG já sai com alfa — pula a etapa 4. Regras: textura de papel ou material
   (`textura()`), borda nunca vetorial perfeita (`contorno()`), **nenhuma sombra
   embutida** (sombra é camada, `kit.SH_*`), nenhum texto (texto é sempre PIL na cena).
   Desenhe em partes separáveis quando a parte for animar — ponteiro, tecla, barra.
   **Olhe o resultado** dentro de uma cena antes de aprovar: asset solto engana.
   Aprovado no laudo D1, ele fica em `minha-biblioteca/assets/` com uma linha no
   `minha-biblioteca/MANIFESTO.md` (mesma tabela do `biblioteca/MANIFESTO.md`).
3. **Gerador de imagem — opcional**, para quem quer cara de foto (Higgsfield, Gemini,
   ou o modo manual: o usuário gera no Google Flow e solta o PNG em `07_assets/raw/`).
   Aí vale o que segue, e o asset passa pelo recorte (etapa 4).

### 3b. Prompt para gerador de imagem

Um prompt por objeto. Templates completos em `referencias/prompts-asset.md`.

**Fundo: escolha pelo maior afastamento de LUMINÂNCIA do objeto.**

| Objeto | Fundo |
| --- | --- |
| papel, cartão, objeto claro | cinza médio `#8A8A8A` |
| objeto escuro (teclado, metal escuro) | cinza claro `#D8D8D8` |
| objeto de luminância média E neutro | último recurso: chroma |

Testado: **pedir "fundo transparente" não funciona** — o modelo devolve RGB sem canal
alfa, e o pedido produz um fundo cinza sólido. **Fundo chroma** torna o recorte trivial
mas contamina ~65% dos pixels de borda com spill da cor, o que estraga justamente a
borda — que neste estilo é a matéria (fibra de papel rasgado, metal fosco).

Sempre no prompt, sem exceção:

- `no cast shadow on the backdrop` — sombra é camada, não pixel do asset
- `no text, no letters, no numbers, no logo, no brand`
- `no glow, no bloom, no neon, no gradients, no HDR, no AI-polished look`
- objeto isolado, top-down, luz difusa uniforme

**Relógio e qualquer mostrador:** peça **sem números, só tracinhos**, e redesenhe os
ponteiros em PIL. Assim a hora vira dado controlado e animável, e não sobra texto de IA.

## 4. Recortar

Use `lib/cutout.py`. Três passes, e a ordem importa:

1. **Flood** `FIXED_RANGE` semeado nas bordas. A tolerância sai de uma **varredura**
   (`python3 cutout.py --sweep NOME`): escolha o **platô**, o ponto a partir do qual
   aumentar a tolerância não remove mais nada.
2. **Sombra.** O fundo cresce, restrito à faixa onde a sombra mora: pixel neutro, liso,
   e do lado certo em luminância. `dark_floor` inverte a regra para objeto escuro.
3. **Fundo encapsulado.** Miolo de clipe de papel tem cor de fundo mas o flood não chega.

Tolerância relativa ao vizinho foi testada e **reprovada**: escorre por gradiente liso e
come o interior de objetos chapados.

## 5. Compor

**Divisão de trabalho — não negociável:**

| Camada | Origem | Motivo |
| --- | --- | --- |
| fundo, objetos físicos | `lib/desenho.py` (padrão) ou IA de imagem | materialidade controlada |
| **todo texto** | PIL, fonte local | grafia garantida |
| **toda anotação** (círculo, seta, sublinhado, linha) | PIL procedural | precisa ser desenhável em progresso |
| sombra de contato, grão, vinheta | PIL | intensidade por camada |

Anotação procedural não é economia: é o que permite renderizar "seta 40% desenhada"
sem regerar imagem.

**Uma timeline por cena, quatro estados amostrados dela:** `START` (frame 0),
`MID` (beat DIRECT), `END` (último evento concluído), `EXIT` (fim do plano). Os estados
são coerentes por construção — nenhum pode contradizer outro sem que o código esteja
errado.

Confira que `END` cai **depois** do último evento, senão o estado mostra texto pela metade
(`./topclip py compose.py --check`).

`./topclip py compose.py` renderiza os estados de todas as cenas **em paralelo** e monta
`08_images/frames/<cena>_ESTADOS.png`, os quatro lado a lado a 360px: revise essa folha.
Overlay é julgado sobre o vídeo: com `<CENA>_T0` no compose, o plate de cada estado sai
sozinho do `fonte.mp4`.

**Comece pelas receitas** (`referencias/receitas.md`): fita-etiqueta, barras em
hachura, item riscado pela tinta, etiqueta de preço com barbante, tira de papel no topo
do vídeo, conta montada à mão. Cada uma é função do kit com cena-exemplo no
`compose.py`. Texto com caractere que a fonte não tem gera aviso; o "≈" sai desenhado.

Detalhes de paleta, tipografia, safe zones e sombras: `referencias/identidade.md`.
Erros que já custaram retrabalho: `referencias/armadilhas.md` — **leia antes de compor**.

## 6. Entrada, saída e transição

| Tipo | Entrada | Saída |
| --- | --- | --- |
| **cutaway** (cobre o vídeo) | corte seco, herói **já em voo no frame 0** — o corte é a revelação | **três tipos alternados** — `slide`, `wipe`, `push`. Corte seco sozinho lê como tranco, e repetir a mesma saída vira tique. Ver `referencias/transicoes.md` |
| **overlay** (sobre o vídeo) | animada, com trajetória | volta por onde entrou, com fitas e anotação **presas ao objeto** |

Hold de 8–18 frames antes de qualquer saída. Melhor ponto de corte é o **silêncio** entre
palavras.

Continuidade honesta: dois elementos separados por dezenas de segundos não formam match
cut. Registre como **motivo recorrente**. O que amarra de verdade é **objeto herdado** —
o mesmo prop voltando com outro estado.

## 7. Render e montagem

Use o `render.py` do projeto (vem de `lib/render_template.py`). **Montagem por sobreposição, nunca por corte-e-concatenação.**

```bash
./topclip py projetos/<nome>/motion/<clipe>/render.py --rascunho      # revisão: veryfast, RASCUNHO.mp4
./topclip py projetos/<nome>/motion/<clipe>/render.py M2 --rascunho   # refez só a M2
./topclip py projetos/<nome>/motion/<clipe>/render.py                 # o master final, UMA vez
```

O render confere a legenda e as saídas **antes** do primeiro quadro (erro em segundos,
não depois de minutos), renderiza os quadros em vários processos e, depois de montar,
confere sozinho duração, cadência, quadros e MD5 do áudio contra a fonte. Rodado pelo
caminho do projeto, como acima, ele aparece no painel com a barra de % (quadros,
legenda e montagem) e o motion do clipe avança sozinho na etapa Motion.

**Legenda:** `janelas=captions.janelas_livres(SHOTS, DUR)` — coladas nas cenas, sem
recuo — e `video=SRC`, que põe a legenda abaixo do queixo mais baixo das janelas
(`referencias/legenda.md`).

- cutaway = frames opacos; overlay = RGBA, e o plate nunca é reprocessado
- a timeline pode ser 24fps mesmo com o clipe em 29,97: avalie cada frame de saída no
  tempo real (`frame24 = t × 24`, com fração). Converter cadência depois gera judder.
- grão: campo **borrado** (σ≈0,9) e **"on twos"**. Ruído branco por pixel e por frame é
  incompressível e leva o bitrate a 120 Mbps.

**Verificação obrigatória do master**, contra a fonte: duração, cadência, contagem de
frames e **MD5 do áudio** (`ffmpeg -i x.mp4 -map 0:a -f md5 -`). O `render.py` faz isso
sozinho no fim de cada montagem e para com erro se qualquer um diferir.

---

## Começar um projeto

```bash
./topclip motion novo projetos/<nome-do-video>/motion
cp <clipe-vertical.mp4> projetos/<nome-do-video>/motion/00_brief/fonte.mp4
```

O comando cria as pastas, copia o motor (`lib/*.py`), as fontes, `compose.py` e
`render.py`, e traz tudo que já existe em `biblioteca/assets/` e
`minha-biblioteca/assets/`. Nunca sobrescreve um projeto que já tem `compose.py`. Rode
os scripts do projeto com `./topclip py projetos/<nome>/motion/render.py`.

**Estilo.** `--estilo <id>` (e `--variacao <v>`) escolhe o estilo; sem ele, sai o Papel.
O projeto congela o estilo em `estilo/` com o `estilo/resolvido.json`: cores, fontes,
movimento, acabamento e legenda já combinados (estilo ← variação ← marca do usuário).
O `render.py` e o `compose.py` leem o acabamento dali. Estilo que não for o Papel: leia o
`estilo/ESTILO.md` do projeto antes de compor — ele manda sobre a `IDENTIDADE.md`.
`./topclip estilo listar` mostra os disponíveis.

### O mesmo fluxo em todo estilo

Limpo, Impacto e Luxo seguem **o fluxo do Papel, etapa por etapa**: ancorar no
transcript, escolher as frases que têm objeto, escolher o registro de cada cena, desenhar
o objeto, travar cada evento na palavra, revisar com a rubrica, render. O que muda é o
**lápis** — o jeito de desenhar do estilo:

| Estilo | Lápis | O mesmo relógio sai |
| --- | --- | --- |
| Papel | `lib/desenho.py` + `lib/kit.py` | recortado em papel, com textura, mão e boil |
| Limpo | `limpo` | ícone chapado em dois tons do acento, sombra macia |
| Impacto | `impacto` | adesivo: contorno preto grosso, borda branca, sombra dura |
| Luxo | `luxo` | gravura em latão que **se desenha** na entrada |

**Desenho primeiro.** Frase com objeto concreto vira **desenho** — objeto em destaque,
processo ou dado —, nunca peça de texto só porque a peça está pronta. Cena de texto é
para a frase que entrou sem objeto (a instrução, o payoff, a virada de argumento), e o
plano diz o motivo na coluna Objeto. O Papel nunca teve esse risco porque nele tudo é
desenho; nos outros estilos, as peças de texto estão a uma linha de distância.

**Objeto: a biblioteca primeiro, o desenho novo depois.** Para cada frase com objeto:

1. **Procure.** `./topclip objetos` lista os oficiais e os do usuário, com uma frase sobre
   cada um. Use o que é **o objeto da fala**, não um parecido: "café" pede xícara, e um
   relógio no lugar dela é enfeite.
2. **Faltou: desenhe.** Em `minha-biblioteca/objetos.py` — formas com **papel** (`corpo`,
   `face`, `detalhe`, `destaque`, `traco`, `vazado`), nunca cor; a primeira frase da
   docstring é a descrição que aparece na lista e no painel. Na primeira vez, copie o
   molde:

   ```bash
   mkdir -p minha-biblioteca && cp .claude/skills/topclip-motion/exemplo/objetos_usuario.py minha-biblioteca/objetos.py
   ```

3. **Confira.** `./topclip objetos` desenha cada objeto seu nos três lápis, diz o que
   estiver errado e grava a folha em `minha-biblioteca/objetos.png`, que o painel mostra
   na Biblioteca. **Olhe a folha** antes de compor: o objeto se reconhece em 1 segundo,
   nos três?
4. **Use.** O objeto chega sozinho ao projeto: todo `./topclip py` de um script do
   projeto leva a versão atual do arquivo (`objetos_meus.py`). Fica para os próximos
   vídeos também.

**Nunca** em `pecas/objetos.py` nem em `biblioteca/`: são do repositório. Objeto só vira
oficial quando quem mantém o repositório pede. Os oficiais, desenhados em cada lápis,
estão em `biblioteca/estilos/<id>/preview/objetos.png`.

**Cena.** As receitas de `pecas/receitas.py` montam a cena do registro, já travada nas
palavras:

| Registro | A frase | Receita |
| --- | --- | --- |
| Objeto em destaque | nomeia uma coisa concreta | `R.objeto_em_destaque(f, 0, FIM, ESTILO, "relogio", titulo=..., etiqueta=..., objeto_em=..., anima_em=..., de=(0, 0), ate=(3, 0))` |
| Processo | "de X para Y", causa e efeito | `R.processo(f, 0, FIM, ESTILO, "etiqueta_preco", "pessoas", de_em=..., seta_em=..., para_em=..., rotulos=(..., ...))` |
| Dado | número, crescimento, proporção | `R.dado(f, 0, FIM, ESTILO, "grafico_barras", titulo=..., grafico_em=..., dur=..., rotulos=[...])` |

Os registros de texto são as **peças** direto: `contador` (número), `marca_texto` (frase
marcada), `troca_palavra`, `desfoque`, `cascata` (lista), `antes_depois`, `cartao` (sobre
o vídeo), `lottie`, `moldura`, `brilho`. Objeto solto, sem receita:
`P.objeto.quadro(f, inicio, fim, ESTILO, "<nome>", centro=..., largura=..., anima_em=..., dur=...)`.
`anima_em`/`dur` é a animação própria do objeto (ponteiro andando, barra crescendo) e
segue a fala, não a curva do estilo: a barra chega na palavra em qualquer estilo.

As regras do Papel continuam valendo: **nunca repita o registro em cenas vizinhas**,
número estimado não vira gráfico limpo, densidade de 30–40%. O `compose.py --check`
conta quantas cenas desenham objeto: confira com o plano. O `compose.py` do projeto
já vem com uma cena-exemplo por registro (M1 a M3) e por peça (M4 em diante).

**Tudo vem do estilo.** Toda peça e todo objeto vestem o `estilo/resolvido.json`: cor,
fonte, peso, caixa alta, contorno, sombra dura, pop, ritmo e lápis. Nunca escreva cor,
fonte ou efeito fixo numa cena dessas: **a mesma cena troca de cara quando o projeto
troca de estilo**. Cenas desses estilos são **overlay** (`cutaway=False` no SHOTS): tela
cheia desenha o próprio fundo com `P.fundo(...)`; sobre o vídeo, `P.cinema(...)` põe as
faixas de filme do Luxo. A legenda também é a do estilo (`pecas/legenda.py`), com os
mesmos blocos e tempos do `captions`.

`fontes/` tem que ficar ao lado de `motor.py` — a identidade depende dela e o motor
falha com mensagem clara se não achar.

```
PROJETO/
  00_brief/PLANO_MOTION.md      frases escolhidas e recusadas, com motivo
  05_motion/M#_motion.md        blueprint por cena
  06_transitions/TRANSITION_MAP.md
  07_assets/{raw,cutout}/
  08_images/frames/             os 4 estados por cena
  09_plates/                    frames do vídeo para as cenas de overlay
  10_sequences/                 PNG por frame, por cena
  11_qa/LAUDO_*.md              laudos do Diretor
  12_master/
  motor.py cutout.py compose.py render.py    (copiados de lib/ pelo `motion novo`)
```

O `bg_paper()` do template lê `07_assets/raw/BG_PAPER.png`; os demais assets saem de
`07_assets/cutout/`. Escreva as cenas a partir de `compose_template.py`.

## Ao editar em lote

`str.replace()` devolve a string **intacta** quando o padrão não casa — patch silencioso.
Depois de qualquer rodada de patches, confirme por `grep -cF` que cada padrão crítico
entrou. Para edição que depende do contexto ao redor, use a ferramenta Edit, que **erra**
se não casar.
