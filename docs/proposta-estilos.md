# Proposta: estilos de motion e a nova Biblioteca

> **Estado: APROVADA. Fases 1, 2 e 3 implementadas** em 2026-10-22.
> Fase 1: `lib/estilo.py`, `biblioteca/estilos/papel/`, `./topclip estilo listar|validar`,
> `motion novo --estilo`, `minha-biblioteca/` e a regressão do Papel (`tests/test_estilo.py`).
> Fase 2: as 8 peças em `biblioteca/pecas/`, a legenda por estilo, o estilo Limpo (claro e
> escuro), `./topclip estilo previa` e o rascunho do clip-010 no Limpo (`tests/test_pecas.py`).
> Fase 3: tipografia e pop por estilo, as peças `moldura` e `brilho`, o `cinema`, os estilos
> Impacto (amarelo, verde) e Luxo (latão, bordô, marfim), e o clip-010 nos três estilos com
> as MESMAS cenas. Fase 4: a aba Biblioteca, o detalhe do estilo, a escolha do estilo na
> etapa Motion e Minha marca no painel. As fases 5 e v2 ainda são proposta.
> O que mudou no caminho está na seção 16.
> Base: a pesquisa de 2026-10-22 (bibliotecas web de motion, caminhos de renderização,
> tendências de 2026, guias de motion, concorrentes) e o teste do Lottie sobre o clip-010.

## 1. O que muda para quem usa

Hoje todo vídeo do TopClip sai no TOPCLIP PAPEL. Com esta proposta, na etapa de motion a
pessoa escolhe um **estilo** e uma **variação** de cor, aplica a **marca** dela por cima e,
se quiser, cria o próprio estilo com o Claude ou instala um da comunidade. A aba
Biblioteca do painel deixa de ser a grade de PNGs do Papel e vira a estante onde tudo isso
aparece.

No lançamento:

| Prateleira | No lançamento | Depois |
| --- | --- | --- |
| Estilos | Papel, Limpo, Impacto, Luxo | Revista, Calmo, Tech |
| Variações | cerca de 10 visuais (2 ou 3 por estilo) | crescem com cada estilo |
| Peças | 8, entre elas o Lottie | as que a comunidade pedir |
| Minha marca | ✓ | |
| Meus estilos | criar com o Claude, exportar e importar | |
| Comunidade | troca por arquivo | vitrine com índice e checagem automática |

## 2. O que esta proposta não quebra

1. **O motor não muda.** `motor.py`, `kit.py`, `desenho.py` e `captions.py` ficam como
   estão. O que é novo mora fora deles e só **usa** as funções deles.
2. **O Papel sai idêntico.** Um teste de regressão renderiza o exemplo do Papel e compara o
   MD5 de cada quadro com o de hoje.
3. **Nada do usuário fica no git.** Hoje isso não é verdade (ver 4.3).
4. **Os estilos oficiais não pedem instalação.** A única dependência nova é o
   `thorvg-python` (~1 MB, pip), para o Lottie.
5. **Pacote da comunidade não tem código.** Só dados, então instalar é seguro.

## 3. Conceitos

| Termo | O que é | Exemplo |
| --- | --- | --- |
| **Estilo** | identidade visual completa: cores, fontes, ritmo, acabamento, legenda e regras | Papel, Limpo |
| **Variação** | troca de paleta dentro do estilo; o jeito de mexer continua o mesmo | Papel kraft, Limpo escuro |
| **Peça** | componente animado escrito uma vez, que veste o estilo ativo | contador, marca-texto |
| **Perfil de energia** | os números de movimento que o estilo herda | calmo, editorial, enérgico |
| **Função de movimento** | o que a cena pede; o perfil traduz em números | `entrada.destaque` |
| **Marca** | logo, cores e fontes do usuário, que entram só onde o estilo permite | `marca.json` |
| **Pacote** | a pasta de um estilo, que se exporta, importa e publica | `limpo/` |

## 4. Pastas

### 4.1 Oficial: no git, só leitura para o usuário

```
biblioteca/
  MANIFESTO.md            índice: estilos oficiais e assets do Papel
  assets/                 os assets do Papel, onde já estão (não mudam de lugar)
  estilos/
    papel/                estilo.json + tokens.json apontando para o que já existe
    limpo/
    impacto/
    luxo/
  pecas/                  as peças compartilhadas (Python, oficial, com testes)
    CREDITOS.md           crédito das bibliotecas MIT de onde veio cada ideia
  comunidade/
    indice.json           (v2) pacotes aprovados da comunidade
```

O pacote `papel/` não copia nada: aponta para `IDENTIDADE.md`, `referencias/`, `fontes/` e
`biblioteca/assets/`, que continuam onde estão.

### 4.2 Do usuário: fora do git

```
minha-biblioteca/         entra no .gitignore
  marca/
    marca.json
    logo.png
    fontes/
  estilos/<id>/           criados com o Claude, remixes e instalados
  assets/                 assets desenhados nas runs
  MANIFESTO.md            a tabela dos seus assets (mesmo formato do oficial)
  desenho.py              as funções desenha_* criadas nas runs
                          (molde: .claude/skills/topclip-motion/exemplo/desenho_usuario.py)
```

### 4.3 O conserto que vem junto

Hoje a skill manda escrever `desenha_<NOME>` em `lib/desenho.py` e gerar o PNG em
`biblioteca/assets/`. Os dois são arquivos versionados. Depois que o usuário faz um vídeo,
o primeiro `git pull` de uma atualização sua dá conflito.

Regra nova: **a run do usuário escreve em `minha-biblioteca/`**. Um asset só vai para
`biblioteca/` e `lib/desenho.py` quando quem mantém o repositório decide torná-lo oficial,
pelo mesmo fluxo de hoje. O `CLAUDE.md` e a skill passam a dizer isso.

### 4.4 Dentro do projeto

```bash
./topclip motion novo <pasta> --estilo limpo --variacao escuro
```

O lançador copia o pacote para `<projeto>/estilo/`, junto com a marca e um
`resolvido.json`, que guarda os tokens já combinados (estilo ← variação ← marca). É o que
já acontece com o `lib/*.py`: **o projeto congela a versão do estilo**, e atualizar um
estilo não muda vídeo antigo. Sem `--estilo`, sai o Papel, exatamente como hoje.

## 5. O pacote de estilo

### 5.1 Arquivos

| Arquivo | Obrigatório | Conteúdo |
| --- | --- | --- |
| `estilo.json` | sim | metadados, variações, peças, espaços liberados para a marca |
| `tokens.json` | sim | cores, fontes, movimento, acabamento |
| `ESTILO.md` | sim | o que faz o estilo ser ele, regras e reprovações (formato da `IDENTIDADE.md`) |
| `legenda.json` | sim | como a legenda se comporta |
| `rubrica.md` | não | critérios do Diretor além das regras universais (seção 7) |
| `fontes/` | se usar fonte fora do kit | TTF/OTF + arquivo de licença (OFL, Apache ou UFL) |
| `assets/` | não | PNG com alfa + `MANIFESTO.md` |
| `lottie/` | não | `.json` + licença, sem expressions |
| `preview/` | sim | `capa.png`, `demo.mp4` (3–6 s), `pecas/<peca>.png` |
| `compose.py` | só nos oficiais e nos "meus" | cenas-exemplo e receitas próprias |

### 5.2 `estilo.json`

```json
{
  "id": "luxo",
  "nome": "Luxo",
  "versao": "1.0.0",
  "topclip": ">=1.0",
  "origem": "oficial",
  "autor": "Felipe Top",
  "licenca": "MIT",
  "descricao": "Preto, marfim e latão. Movimento lento, filete Art Deco.",
  "bom_para": ["mentoria", "imóveis", "estética", "moda"],
  "energia": "calmo",
  "variacoes": {
    "latao": {"nome": "Latão", "tokens": {}},
    "bordo": {"nome": "Bordô", "tokens": {"cor.acento": "#5A1A22"}}
  },
  "pecas": ["contador", "marca_texto", "troca_palavra", "cascata", "cartao", "lottie"],
  "slots_da_marca": ["cor.acento", "fonte.titulo", "logo"],
  "codigo": false
}
```

- `origem`: `oficial`, `meu` ou `comunidade`.
- `slots_da_marca`: o que a marca pode trocar. **Quem cria o estilo decide.** É isso que
  impede uma marca de estragar o estilo, o mesmo modelo dos templates do After Effects
  (MOGRT) e dos slots do Lottie.
- `codigo`: `true` só em oficial e em "meu". O validador recusa pacote da comunidade com
  qualquer arquivo executável.

### 5.3 `tokens.json`

Segue a estrutura do W3C Design Tokens (`$type`, `$value`, `$extensions`) em versão
simplificada: cor em hex, fonte como caminho dentro do pacote ou nome de uma fonte do kit.

```json
{
  "cor": {
    "fundo":  {"$type": "color", "$value": "#0A0A0A"},
    "texto":  {"$type": "color", "$value": "#F2EDE4"},
    "acento": {"$type": "color", "$value": "#C9A45C"},
    "apoio":  {"$type": "color", "$value": "#5A1A22"}
  },
  "fonte": {
    "titulo": {"$type": "fontFamily", "$value": "fontes/CormorantGaramond-Italic.ttf"},
    "apoio":  {"$type": "fontFamily", "$value": "Inter"},
    "numero": {"$type": "fontFamily", "$value": "fontes/CormorantGaramond-Italic.ttf"}
  },
  "movimento": {"perfil": "calmo", "ajustes": {"push_camera": [0, 0.02]}},
  "$extensions": {"topclip": {
    "traco": "limpo",
    "acabamento": {"grao": 0.02, "vinheta": 0.08, "aberracao": 0, "saturacao": 1.0},
    "boil": null
  }}
}
```

- `traco: "mao"` desenha com tremido e boil, como o Papel. `traco: "limpo"` desenha com
  borda nítida.
- `acabamento` vira os argumentos do `finish()` que já existe. No Papel, são exatamente os
  valores de hoje (`grain=0.050, vignette=0.06, chroma=1.0, sat=0.92`).
- `movimento.ajustes` sobrescreve qualquer número do perfil (seção 6), inclusive o push
  de câmera. `boil: null` zera o boil dos objetos.
- A legenda e as variações apontam para tokens por caminho (`"fonte.impacto"`,
  `"cor.destaque"`); o `resolvido.json` já traz o valor final.

### 5.4 `legenda.json`

```json
{
  "fonte": "fonte.apoio",
  "corpo": 78,
  "enfase": 1.6,
  "caixa_alta": false,
  "cor": "cor.texto",
  "destaque": "cor.acento",
  "destaques_por_clipe": 2,
  "contorno": 0,
  "palavras_por_bloco": 4,
  "animacao": "fade",
  "posicao": "rosto"
}
```

- `animacao` pode ser `corte_seco` (o Papel), `fade` ou `pop`.
- A legenda do Papel continua sendo o `captions.draw` de hoje.
- Os outros estilos reaproveitam o `captions.blocos()`, que é a parte cara e já medida: a
  divisão da fala e o tempo de cada palavra. `palavras_por_bloco` e os outros limites são
  ajustados nas constantes do módulo em tempo de execução, sem editar o arquivo. O desenho
  fica em `biblioteca/pecas/legenda.py`.

## 6. Perfis de energia

Cada estilo herda um perfil e pode sobrescrever qualquer número dele. As cenas pedem uma
**função**, e o perfil responde com os números. É o modelo do Material 3 e do IBM Carbon.

| Função / parâmetro | Calmo | Editorial | Enérgico |
| --- | --- | --- | --- |
| `entrada` (curva) | `(0, 0, 0.38, 0.9)` | `(0.05, 0.7, 0.1, 1)` | `(0.34, 1.56, 0.64, 1)` |
| `saida` (curva) | `(0.4, 0, 1, 1)` | `(0.3, 0, 0.8, 0.15)` | `(0.7, 0, 0.84, 0)` |
| `movimento` (curva) | `(0.33, 0, 0.67, 1)` | `(0.2, 0, 0, 1)` | `(0.2, 0, 0, 1)` |
| duração da entrada | 12–17 quadros | 8–12 | 4–7 |
| duração da saída | 7–10 quadros | 5–6 | 2–4 |
| overshoot (só posição e escala) | 0 | 0–2% | 8–12% |
| stagger / total da coreografia | 3 quadros / ≤ 0,9 s | 2 / ≤ 0,6 s | 1 / ≤ 0,4 s |
| tempo mínimo do elemento na tela | 2,5 s | 1,5 s | 0,8 s |
| eventos visuais a cada 10 s | 1–2 | 2–4 | 4–7 |
| movimentos simultâneos | 1 | até 2 | até 3 |
| `transicao` | dissolve 300–500 ms | corte seco, wipe | corte no beat, zoom |
| push de câmera | 0–2%, lento | 3–6% | 8–15%, no máximo 1 a cada 3 s |

Os números são de 24 fps e vêm dos guias de motion (Material 3, Carbon, Fluent, NN/g),
aumentados para vídeo. São o ponto de partida. Cada estilo calibra os seus em produção e
grava no `ESTILO.md`, como o Papel fez.

| Estilo | Perfil |
| --- | --- |
| Papel, Revista | editorial |
| Limpo, Luxo, Calmo | calmo |
| Impacto | enérgico |

## 7. Regras universais (a rubrica de qualquer estilo)

O Diretor cobra estas regras em todo estilo. A `rubrica.md` de cada estilo só acrescenta.

1. A entrada desacelera e a saída acelera. Curva linear só em movimento contínuo.
2. A saída dura no máximo 70% da entrada.
3. A duração cresce com a distância percorrida.
4. Overshoot só em posição, escala e rotação. Cor e opacidade nunca passam do alvo.
5. Um protagonista em movimento por vez.
6. O que é estável entra primeiro, e o mais importante entra por último.
7. Dentro de um estilo, uma família só de curvas.
8. O movimento expressivo é exceção, mesmo no perfil enérgico.
9. **Texto de motion** (o que não é a fala) fica na tela pelo menos o maior entre 0,83 s e
   0,3 s × número de palavras. A legenda da fala não segue esta regra: o áudio já carrega a
   frase, e o Papel mediu e aprovou blocos de 0,33 s.
10. Contraste de pelo menos 4,5:1, medido contra o pior trecho do fundo real.
11. No máximo 3 flashes por segundo, e nada de zoom ou rotação contínuos em tela cheia.
12. O motion nunca carrega a ideia sozinho: ela precisa estar na fala.
13. Tamanhos mínimos: linha da legenda com 75 px ou mais, texto secundário com 45 px ou
    mais, e nada abaixo de 30 px.
14. Fica fora das faixas da interface. Os números ainda **precisam ser medidos**: a Meta
    pede 35% livres embaixo, mas isso é para anúncio, e a nossa legenda fica centrada em
    y≈1330. Medir num Reels, num Short e num TikTok de verdade antes de virar regra.

## 8. Peças da v1

| Peça | O que faz | Recebe | Ideia de (licença) |
| --- | --- | --- | --- |
| `contador` | número que conta até o valor dito | valor, prefixo, sufixo | Magic UI Number Ticker (MIT) |
| `marca_texto` | marca-texto, sublinhado ou círculo na palavra | texto, tipo | rough-notation (MIT) |
| `troca_palavra` | palavra que troca no mesmo lugar | lista de palavras | Magic UI Word Rotate (MIT) |
| `desfoque` | texto que entra desfocando, palavra a palavra | texto | Motion Primitives Text Effect (MIT) |
| `cascata` | itens entrando um por um | lista | Magic UI Animated List (MIT) |
| `antes_depois` | duas imagens com um divisor que corre | 2 imagens | Motion Primitives Image Comparison (MIT) |
| `cartao` | cartão ou etiqueta com título e texto | título, texto | — |
| `lottie` | toca um Lottie no trecho, com as cores da marca | arquivo, trecho | thorvg-python (LGPL, dependência) |

Todas têm a mesma interface:

```python
camada = peca.quadro(f, inicio, fim, estilo, **dados)   # PIL RGBA 1080x1920
```

- `estilo` traz os tokens resolvidos (estilo ← variação ← marca) e o perfil de energia.
- `inicio` e `fim` são quadros travados na palavra, como nas receitas de hoje.
- Com `traco: "mao"`, a peça usa `motor.hand_stroke` e o boil. Com `"limpo"`, desenha
  nítido em PIL.

**Licença.** O código só pode vir de fonte MIT ou Apache, e cada uma ganha crédito em
`CREDITOS.md`. **React Bits, Animate UI, Aceternity e Skiper não podem ser copiados nem
portados**: a licença do React Bits proíbe até a "ported version". Servem só como
referência visual, reescritas do zero.

**Lottie, pelo que o teste mediu:**
- Renderizar com `Colorspace.ABGR8888S`. O padrão é pré-multiplicado, e o `get_pillow()`
  não converte, o que escurece as bordas (RGB 119 onde deveria ser 255).
- Converter o tempo com `set_frame(t × fps_do_arquivo)`. Arquivo a 60 fps funciona sem
  ajuste.
- Cores da marca entram por slot (`gen_slot` + `apply_slot`).
- A importação recusa arquivo com expressions. Elas **não rodam** no wheel do pip: nem
  `time*90` executou.
- Custa de 1,4 a 6 ms por quadro em 1080x1920, e o mesmo quadro sai idêntico.
- **Falta testar** com arquivos reais do LottieFiles.

## 9. Marca

```json
{
  "nome": "Felipe Top",
  "arroba": "@realfelipetop",
  "cores": {"primaria": "#2E82F7", "secundaria": "#DBD653", "texto": "#111111"},
  "fontes": {"titulo": "fontes/MinhaFonte-Bold.ttf", "texto": "Inter"},
  "logo": "logo.png"
}
```

- Ordem de resolução: **estilo → variação → marca**, e a marca só entra nos
  `slots_da_marca` do estilo.
- Campo da marca → token: `cores.primaria` → `cor.acento`, `cores.secundaria` →
  `cor.apoio`, `cores.texto` → `cor.texto`, `fontes.titulo` → `fonte.titulo`,
  `fontes.texto` → `fonte.apoio`, `logo` → `logo`. `motion novo --sem-marca` ignora a marca.
- Se a cor da marca deixar a legenda com contraste abaixo de 4,5:1, fica a cor do estilo e
  o painel avisa.
- Fonte da marca só entra com licença que permita embutir. Fonte comercial fica no
  computador do usuário e nunca vai para um pacote exportado.

## 10. Criar meu estilo com o Claude

1. **Insumos, todos opcionais:** @ do Instagram ou site, 3 prints de posts, logo, PDF de
   marca, 2 vídeos de referência, 3 adjetivos e o que a pessoa **não** quer.
2. **Extração local e grátis:** a paleta sai por k-means nas imagens. As fontes do site
   viram equivalentes do Google Fonts, por causa da licença.
3. **Até 5 perguntas:** energia, peso da legenda, quanto motion, textura e público.
4. **4 direções**, cada uma num quadro do clipe da própria pessoa. Ela escolhe uma e ajusta
   cor, fonte e energia.
5. **Validação:** contraste, tamanhos, licença das fontes, render de todas as peças e a
   rubrica.
6. **Aprovado, vira `minha-biblioteca/estilos/<id>/` na versão 1.0.0.** Cada clipe grava a
   versão que usou.

Remixar um oficial é o mesmo fluxo começando de uma cópia dele.

## 11. Comunidade

**v1, troca por arquivo:**
- `./topclip estilo exportar <id>` gera `<id>.topclip-estilo`, um zip sem a marca.
- `importar` valida e instala em `minha-biblioteca/estilos/`. O painel faz o mesmo
  arrastando o arquivo.

**v2, vitrine:**
- `biblioteca/comunidade/indice.json` lista os pacotes aprovados: id, nome, autor,
  repositório, **commit fixado**, licença, energia e "bom para".
- O pacote entra por PR. O CI roda `./topclip estilo validar`, que confere:
  - o formato do pacote;
  - que não há código;
  - as licenças das fontes;
  - PNG com alfa;
  - Lottie sem expressions;
  - tamanho de no máximo 20 MB;
  - o render de todas as peças com o clipe de exemplo, que gera a capa.
- Depois do CI, você revisa e aprova.
- No painel, "Instalar" baixa o zip do commit fixado, valida de novo e instala.

**Por que a vitrine fica para a v2:** se o formato do pacote mudar depois que as pessoas
publicarem, os pacotes delas quebram. Primeiro o formato se estabiliza com os 4 oficiais.

## 12. Painel

O painel continua com a cara do Papel. **O visual de cada estilo só aparece dentro das
prévias**, que são imagens e vídeos curtos gerados por `./topclip estilo previa <id>`; nada
renderiza no navegador.

**Aba Biblioteca:**
- prateleiras de Estilos oficiais, Meus estilos e Comunidade (v2);
- uma seção de Peças, que troca de cara conforme o estilo selecionado e usa
  `preview/pecas/`;
- o cartão Minha marca.

**Detalhe do estilo:**
- capa e demo, variações, peças, legenda de exemplo e "bom para";
- ações: usar como padrão, remixar, exportar.

**Escolha na etapa de motion:**
- 3 cards recomendados (o Claude recomenda pelo transcript) e o botão "ver todos";
- cada card mostra um quadro do clipe do próprio usuário no estilo. Renderizar um quadro
  por estilo leva segundos;
- a escolha vai para `projetos/<nome>/escolhas.json` como
  `"estilo": {"id": "limpo", "variacao": "escuro"}`.

**Minha marca:** cores, fontes e logo, gravados em `minha-biblioteca/marca/`.

**API:**

| Rota | Função |
| --- | --- |
| `GET /api/estilos` | lista oficiais, meus e instalados |
| `GET /api/estilos/<id>` | detalhe e prévias |
| `POST /api/estilos/importar` | instala um `.topclip-estilo` |
| `GET` e `POST /api/marca` | lê e grava a marca |
| `GET /api/comunidade` | (v2) lê o índice |

O `servidor.py` continua só com a biblioteca padrão do Python: `zipfile` e `json` bastam.

## 13. O que muda em cada arquivo

| Arquivo | Muda? | O quê |
| --- | --- | --- |
| `motor.py`, `kit.py`, `desenho.py`, `captions.py` | **não** | |
| `compose_template.py` | não | continua sendo o compose do Papel |
| `render_template.py` | pouco | lê o acabamento de `estilo/resolvido.json` quando existe; sem ele, usa os valores de hoje. A regressão garante o Papel idêntico |
| `topclip` (lançador) | sim | `motion novo --estilo --variacao`; `estilo listar`, `validar`, `previa`, `exportar`, `importar` |
| `biblioteca/` | sim | `estilos/`, `pecas/`, `comunidade/` (v2) |
| `.gitignore` | sim | `minha-biblioteca/` |
| `requirements.txt` | sim | `thorvg-python` |
| `CLAUDE.md`, skills `topclip` e `topclip-motion` | sim | assets do usuário em `minha-biblioteca/`; ler o `ESTILO.md` do estilo do projeto |
| `painel/` | sim | telas e rotas da seção 12 |
| testes | sim | regressão do Papel, validador, cada peça renderizando em cada estilo |

## 14. Ordem de implementação

Cada fase termina com `./topclip testes` e `./topclip verificar` passando.

| Fase | Entrega | Tamanho |
| --- | --- | --- |
| 1. Fundação ✓ | formato do pacote, validador, `minha-biblioteca/`, `motion novo --estilo`, Papel como pacote, teste de regressão | feito em 2026-10-22 |
| 2. Peças + Limpo ✓ | as 8 peças em `traco: "limpo"`, o estilo Limpo completo (com legenda), um clipe real no Limpo | feito em 2026-10-22 |
| 3. Impacto + Luxo ✓ | os dois estilos, a legenda `pop`, as variações | feito em 2026-10-22 |
| 4. Painel ✓ | Biblioteca, detalhe, escolha na etapa de motion, Minha marca | feito em 2026-10-22 |
| 5. Meu estilo | criar com o Claude, remixar, exportar e importar | médio |
| v2 | vitrine da comunidade com CI | médio |

As fases 3 e 4 podem rodar em paralelo, porque não mexem nos mesmos arquivos. O Limpo vem
primeiro porque é o mais diferente do Papel: se o formato servir para ele, serve para os
outros.

## 15. Decisões tomadas

1. **Formato do pacote** como nas seções 4 e 5, com os ajustes da seção 16.
2. **Pasta `minha-biblioteca/`** para tudo do usuário.
3. **`thorvg-python==1.1.3` obrigatório** (no `requirements.txt`; o `verificar` só avisa se
   faltar, porque só a peça `lottie` depende dele).
4. **Ordem dos estilos: Limpo (feito), Impacto e Luxo.**

## 16. O que mudou na implementação

Decidido no caminho, com o motivo:

- **`estilo.json` ganhou `cenas`** (`cutaway` ou `overlay`). No `overlay` (Limpo) a cena
  desenha o próprio fundo (`P.fundo`) e entra e sai em fade, então o render a trata como
  overlay e o acabamento não tira a transparência. O `motion novo` já acerta o exemplo do
  SHOTS. Não precisou mexer nas saídas do render (slide, wipe, push continuam do Papel).
- **Estilo oficial com `compose.py`** (`codigo: true`) troca o compose do projeto recém-
  -criado pelo dele. Reinstalar um estilo num projeto com cenas escritas **não**
  sobrescreve o compose (isso apagou as cenas do clip-010 uma vez durante o teste).
- **`legenda.json` ganhou `peso`, `duracao_alvo`, `fundo` e `fundo_alfa`.** A legenda do
  Limpo virou **etiqueta** (texto escuro em caixa clara): texto branco com sombra sumia na
  camisa branca do clip-010. `duracao_alvo` ajusta o `ALVO` do captions, e o `MAXDUR`
  segue a mesma razão medida no Papel (1,9×).
- **`pecas/estados.py`** é a máquina de estados de revisão (START/MID/END/EXIT e a folha)
  para o compose dos estilos; o do Papel continua com a dele.
- **`./topclip estilo previa <id> [--cena M1]`** gera `capa.png`, `capa-<variação>.png` e
  `pecas/<peça>.png` dentro do pacote, num projeto temporário, sem a marca do usuário.
- **Cores e fontes de reserva:** o estilo só é obrigado a ter `fundo`, `texto` e `acento`.
  `superficie`, `linha`, `apoio` e `sobre_acento` caem numa vizinha (ou no maior contraste),
  e fonte que falta cai em `apoio`. Assim um estilo criado pelo usuário serve a toda peça.
- **O Limpo tem uma animação Lottie própria** (`lottie/check.json`, MIT, cor no slot
  `acento`), feita à mão no formato Lottie — nenhum arquivo de terceiros no repositório.

Fase 3:

- **`$extensions.topclip.tipografia`** (opcional): `caixa_alta`, `contorno` e `sombra_dura`
  em fração do corpo, `cor_contorno`, `peso` por papel de fonte e `tracking` por papel.
  As peças escrevem por `Estilo.linha/bloco/caixa` e herdam tudo: o Impacto ganha caixa
  alta com contorno sem uma linha nas peças, o Luxo ganha títulos finos (380) onde a peça
  pede 700. **Texto da cor do contorno vai sem efeito** (preto sobre o amarelo virava
  borrão com contorno preto).
- **Perfis ganharam `escala_entrada` e `deslocamento_entrada`.** No enérgico, a peça nasce
  pequena e passa do tamanho (~110%) pela curva que passa de 1 — o "pop" —, sem deslizar.
  Calmo e editorial seguem deslizando, sem escala.
- **Peças novas:** `moldura` (filete duplo que se desenha, com leques Art Deco) e `brilho`
  (reflexo que passa uma vez no título). Helper novo: `P.cinema` (faixas de letterbox).
- **`legenda.json` ganhou `destaque_modo`** (`pilula` ou `texto`), **`sombra_dura`** (px) e
  **`entrada_s`**. Com `destaque_modo: "texto"` a palavra muda de cor e fica na caixa da
  legenda, se houver (Luxo), ou solta com contorno (Impacto).
- **A legenda do Luxo ganhou faixa preta translúcida**: a itálica fina marfim sumia na
  camisa branca do clip-010, como o branco do Limpo antes da etiqueta. Toda legenda nova
  precisa ser vista sobre roupa clara antes de aprovar.
- **A fonte Anton ganhou o `OFL-Anton.txt`** (copyright lido da própria fonte): ela viajava
  no kit sem o arquivo de licença.
- **Prova da arquitetura:** o clip-010 saiu no Limpo, no Impacto e no Luxo com o mesmo
  `compose.py`, sem mudar uma linha — só o `--estilo` do `motion novo`.

Fase 4 (painel):

- **O padrão do usuário mora em `minha-biblioteca/preferencias.json`**
  (`{"estilo", "variacao"}`). A escolha do projeto vale primeiro, depois a preferência, e
  por último o Papel.
- **O selo "recomendado" lê `estilo_recomendado` do `projeto.json`**, que a skill `topclip`
  passa a gravar.
- **Rota extra `POST /api/marca/conferir`**, para o aviso de contraste ao vivo. O contraste
  é medido contra a cor primária e contra o fundo de cada estilo que deixa a marca trocar a
  cor do texto.
- **"Seus assets" virou "Objetos desenhados"** na tela, porque "assets" é jargão.
- **Ficou para depois:**
  - o quadro do clipe do próprio usuário em cada estilo (por enquanto, a prévia do pacote);
  - as prévias das peças por variação (hoje, só a da primeira);
  - a legenda de exemplo e a demo em vídeo no detalhe;
  - fonte própria da marca no formulário (só as fontes do kit).
