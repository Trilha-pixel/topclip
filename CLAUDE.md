# TopClip

Vídeo longo → clipes verticais 9:16 com motion e legenda. Três skills em
`.claude/skills/`: `topclip` (fluxo completo), `topclip-corte`, `topclip-motion`.

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
- **Assets desenhados numa run vão para `minha-biblioteca/`**, fora do git: função em
  `minha-biblioteca/desenho.py` (molde em `.claude/skills/topclip-motion/exemplo/desenho_usuario.py`),
  PNG em `minha-biblioteca/assets/`, linha em `minha-biblioteca/MANIFESTO.md`. Nunca em
  `lib/desenho.py` nem em `biblioteca/`: são do repositório, e o próximo `git pull` do
  usuário daria conflito. Asset só vira oficial quando quem mantém o repositório pede.
- Depois de mexer em código: `./topclip testes` e `./topclip verificar`.
