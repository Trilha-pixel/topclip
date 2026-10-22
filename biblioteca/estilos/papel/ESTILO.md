# Papel

O estilo original do TopClip: colagem editorial sobre papel marfim, com fita crepe,
clipe, retalhos e anotação à mão.

**A identidade completa não mora aqui.** Ela está em
`.claude/skills/topclip-motion/IDENTIDADE.md`, as regras em `referencias/` (registros,
receitas, legenda, transições, boil, armadilhas, rubricas) e os assets em
`biblioteca/assets/`. O motor e o kit já desenham o Papel por padrão.

Este pacote só registra os valores do Papel no formato dos estilos (`tokens.json`,
`legenda.json`). Eles são **os mesmos do motor**, e um teste confere que não se separam:

- cores: as constantes de `motor.py` (`PAPER`, `INK`, `YELLOW`, `BLUE`, `RED`…);
- acabamento: o `FX_DESK` de `kit.py` e do `render_template.py`, com boil a 0,5;
- legenda: as constantes de `captions.py` (Archivo Black 80, ênfase em Playfair Itálica
  a 2,1×, corte seco, 3 palavras por bloco).

Mudar o visual do Papel continua sendo pelo caminho da `IDENTIDADE.md`: laudo, nova
versão, e aí este pacote acompanha.
