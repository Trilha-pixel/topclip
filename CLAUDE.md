# TopClip

Vídeo longo → clipes verticais 9:16 com motion e legenda. Três skills em
`.claude/skills/`: `topclip` (fluxo completo), `topclip-corte`, `topclip-motion`.

## Regras do repositório

- **Todo comando passa por `./topclip`**, rodado da raiz. Nunca `python3 script.py`
  direto: o `python3` do sistema no macOS é o 3.9 e o pacote exige 3.10+. Para um
  script avulso: `./topclip py <script.py>`.
- **Vídeos e runs do usuário vão em `projetos/<nome-do-video>/`** — fora do git.
  Nunca grave nada do usuário fora dessa pasta.
- Antes do primeiro projeto: `./topclip verificar`. Faltou algo: `./topclip instalar`.
- Assets novos de motion: desenhe em `.claude/skills/topclip-motion/lib/desenho.py`,
  gere em `biblioteca/assets/` e registre em `biblioteca/MANIFESTO.md`.
- Depois de mexer em código: `./topclip testes` e `./topclip verificar`.
