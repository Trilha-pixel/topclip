# Identidade visual — TOPCLIP PAPEL

Este é o guia de estilo operacional da identidade. `IDENTIDADE.md` diz o que a define;
aqui estão os valores.

## Canvas

```yaml
canvas: 1080x1920
fps_timeline: 24          # o master pode sair em outra cadência
margens_laterais: 96px
exclusao_direita: 120px   # x > 960 — vale para TEXTO e herói, não para prop sangrando
exclusao_inferior: 260px  # y > 1660
espaco_negativo: 25-40% no registro research-desk
```

Fluxo vertical: 7–18% tema · 18–65% evidência · 55–78% anotação · 72–88% conclusão.

**Sobre espaço negativo:** a faixa 25–40% descreve a família *research desk* — mesa
coberta de papéis sobrepostos. No registro *clean editorial*, com 4 a 6 objetos
discretos, 20–33% de ocupação é o que sai, e as referências aprovadas do canal são
igualmente arejadas. Não persiga o número; persiga a distribuição.

## Paleta

```yaml
paper:      "#D9D8D1"    light:  "#F4F0E8"
ink:        "#373639"    charcoal: "#29292B"
yellow:     "#DBD653"    blue:   "#2E82F7"
red:        "#C94850"    green:  "#31C25B"
tape:       "#BFBBAE"
```

Proporção: **80% neutros · 15% massa escura · 5% acento**. Um acento principal por cena.

Cenas de papel tendem a ficar sem massa escura (medido: 1,4% e 4,8%). Uma **fotografia
noturna** resolve — ver `luz sem glow` em `armadilhas.md`.

## Tipografia

| Função | Fonte (macOS) | Corpo |
| --- | --- | --- |
| Manchete condensada | `DIN Condensed Bold` | 80–112px |
| Etiqueta manual | `Bradley Hand Bold` + stroke | 46–124px |
| Mono técnica | `Menlo` | 22–38px |
| Serif expressiva | `Georgia Bold` | 96–152px |

Máximo três famílias por quadro, quatro funções no projeto.

**Modo de entrada do texto:**

- editorial → **bloco** (opacidade 0→1 + subida de ~14px, 6–10 frames)
- marcador → **write** (frente de revelação esquerda→direita, ponta de caneta)
- **nunca caractere a caractere** em tipografia editorial: é máquina de escrever, efeito
  de template proibido

## Sombras — por classe de material

```yaml
papel:        dy 6   blur 14  opacidade 0.15
cartao:       dy 11  blur 24  opacidade 0.17
objeto_alto:  dy 20  blur 32  opacidade 0.20
fita:         dy 3   blur 9   opacidade 0.11
sobre_video:  dy 14  blur 26  opacidade 0.42   # precisa cravar mais, senão flutua
```

Nunca a mesma sombra em todas as camadas.

## Movimento

```yaml
entrada:        8-18 frames
overshoot:      2-4%
stagger:        2-4 frames entre objetos
camera_push:    100 -> 103-106%
hold_final:     8-18 frames
easing_pouso:   cubic-bezier(0.20, 0.80, 0.20, 1.00)
easing_traco:   velocidade quase constante — caneta não desacelera no fim
easing_saida:   aceleração (t^2.4)
```

Verbos permitidos: pousar, deslizar, revelar, desenhar, conectar, comparar, aproximar,
afastar, segurar.

Câmera e objeto são operações **separadas**: ou a câmera aproxima, ou o objeto cresce.
Nunca as duas.

## Proibições

neon · glow · bloom · HDR · gradiente decorativo · 3D plástico · dashboard SaaS ·
card arredondado sem função · partículas de "IA" · glitch como transição · impacto de
câmera em toda frase · tudo centralizado · movimento constante · texto repetindo a
narração · objeto flutuando sem contato · linha ou seta que não leva a nada
