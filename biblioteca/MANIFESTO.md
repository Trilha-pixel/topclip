# Biblioteca de assets

Todo asset aprovado num vídeo volta para cá e fica disponível para o próximo.
`./topclip motion novo` copia esta pasta inteira para dentro de cada projeto.

## Regras para entrar

- PNG com canal alfa, sem texto embutido, sem sombra embutida — sombra é camada.
- Passou no laudo D1 de `.claude/skills/topclip-motion/referencias/rubricas-diretor.md`.
- Nome em MAIÚSCULAS com sublinhado, dizendo o objeto: `RELOGIO_PAREDE.png`.
- Uma linha na tabela abaixo.

`BG_PAPER.png` é especial: é o fundo de mesa (papel marfim pontilhado) e vai para
`07_assets/raw/` do projeto, não para `cutout/`.

**Papel grande não vem daqui.** Os retalhos do `A10_SCRAPS` têm ~360px por peça e
borram quando ampliados. Papel acima de ~450px (folha de caderno, quadriculado de
gráfico, etiqueta kraft) sai de `kit.scrap()`, que desenha o retalho no tamanho de uso
com o mesmo código, e a fita de etiqueta de `kit.fita()`. Esses ficam no cache do
projeto (`07_assets/cutout/_uso/`), não na biblioteca.

## Assets

| Arquivo | Objeto | Origem | Registro |
| --- | --- | --- | --- |
| `BG_PAPER.png` | papel marfim pontilhado, 1080×1920 | `desenho.py` | fundo de mesa |
| `A02_CLOCK.png` | despertador de duas campainhas, mostrador sem números | `desenho.py` | objeto |
| `A03_TAPE.png` | 4 tiras de fita crepe (a 1ª é a de etiqueta) | `desenho.py` | prop |
| `A04_CLIPS.png` | 3 clipes de papel | `desenho.py` | prop |
| `A05_CARD.png` | cartão de cópia impressa, em pé, margem branca (para `kit.photo_card`) | `desenho.py` | foto em cartão |
| `A05_SHEET.png` | folha alta de algodão frio que cruza a lente na saída `wipe` | `desenho.py` | transição |
| `A10_SCRAPS.png` | 4 retalhos: kraft, pautado, quadriculado, cartão | `desenho.py` | prop |
