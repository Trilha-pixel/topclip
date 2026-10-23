# TopClip

Vídeo longo → clipes verticais 9:16 com motion e legenda, e posts virais de imagem.
Cinco skills em `.claude/skills/`: `topclip` (fluxo completo), `topclip-corte`,
`topclip-motion`, `topclip-estilo` (criar o estilo da pessoa, remixar, exportar e
importar) e `topclip-post` (frase do vídeo em 2 ou 3 prints do rosto, feed ou stories,
post único ou carrossel, com a legenda pronta).

## Regras do repositório

- **Todo comando passa por `./topclip`**, rodado da raiz. Nunca `python3 script.py`
  direto: o `python3` do sistema no macOS é o 3.9 e o pacote exige 3.10+. Para um
  script avulso: `./topclip py <script.py>`.
- **Vídeos e runs do usuário vão em `projetos/<nome-do-video>/`** — fora do git.
  Nunca grave nada do usuário fora dessa pasta.
- **Vídeo por link** (YouTube, Instagram): `./topclip baixar <link>` cria o projeto e
  baixa; projeto do painel com `link` no `projeto.json`: `./topclip baixar projetos/<nome>`.
  Nunca peça para a pessoa baixar à mão (skill `topclip`, "Vídeo de link").
- Antes do primeiro projeto: `./topclip verificar`. Faltou algo: `./topclip instalar`.
- **Painel** (`./topclip painel`, código em `painel/`): o usuário escolhe momentos,
  cortes e o estilo do motion por lá. Quando ele disser que escolheu no painel, leia
  `projetos/<nome>/escolhas.json` (numa conversa nova, sem projeto dito: o atualizado
  por último). Corte com entrega já está pronto — siga só com os novos, na mesma run
  (skill `topclip`, "Voltando depois para fazer o resto"). O estilo é o `estilo` de
  `escolhas.json`, senão o de `minha-biblioteca/preferencias.json`, senão o Papel
  (skill `topclip`, seção do motion). A identidade visual do painel é a mesma do motion
  (TopClip Papel) — não troque fontes nem paleta.
- **Estilos de motion** (`./topclip estilo listar`): os oficiais em `biblioteca/estilos/`,
  os do usuário em `minha-biblioteca/estilos/`. O projeto escolhe com
  `./topclip motion novo <pasta> --estilo <id>` (padrão: `papel`) e congela o estilo em
  `estilo/resolvido.json`. Formato e plano: `docs/proposta-estilos.md`. As peças que os
  estilos compartilham ficam em `biblioteca/pecas/` (nunca cor ou fonte fixa: tudo vem
  do estilo). Mexeu num estilo ou numa peça: `./topclip estilo previa <id>` regera a galeria.
  Estilo da pessoa (remixar, ajustar, aprovar, exportar, importar, paleta, amostra no
  clipe): skill `topclip-estilo`. Estilo oficial nunca se edita — remixa.
- **Todo estilo segue o fluxo do Papel** (frase com objeto → objeto desenhado → registro →
  palavra); muda o lápis (`biblioteca/pecas/lapis.py`). Frase com objeto vira desenho,
  nunca texto (D0 da rubrica). Antes de desenhar: `./topclip objetos` (a biblioteca
  primeiro). Objeto novo oficial em `biblioteca/pecas/objetos.py`, só com o papel de cada
  forma (nunca cor): sai nos três lápis. Os do usuário em `minha-biblioteca/objetos.py`
  (molde em `.claude/skills/topclip-motion/exemplo/objetos_usuario.py`), conferidos com
  `./topclip objetos`; chegam sozinhos ao projeto a cada `./topclip py`.
- **Assets desenhados numa run vão para `minha-biblioteca/`**, fora do git: função em
  `minha-biblioteca/desenho.py` (molde em `.claude/skills/topclip-motion/exemplo/desenho_usuario.py`),
  PNG em `minha-biblioteca/assets/`, linha em `minha-biblioteca/MANIFESTO.md`. Nunca em
  `lib/desenho.py` nem em `biblioteca/`: são do repositório, e o próximo `git pull` do
  usuário daria conflito. Asset só vira oficial quando quem mantém o repositório pede.
- **Posts virais** (`./topclip post …`, skill `topclip-post`): o Claude só escolhe as frases
  e escreve as legendas (`projetos/<nome>/posts/frases.json`) e roda `./topclip post prints`;
  escolher, editar, post único ou carrossel, trocar print (ou subir foto), fonte, P&B,
  assinatura e baixar é no painel (aba Posts virais), sem voltar ao Claude. O painel grava
  em `posts/posts.json`. Código em `.claude/skills/topclip-post/lib/`.
- Depois de mexer em código: `./topclip testes` e `./topclip verificar`.
