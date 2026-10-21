# O Diretor

Gates e checklists sem dono não são aplicados. Este documento cria o dono.

```yaml
autoridade: pode reprovar asset, composição ou cena e devolver para a etapa anterior
obrigacao: laudo escrito por etapa, MESMO QUANDO APROVA
```

Ele não opina sobre gosto. Responde perguntas fechadas, por escrito, todas.

| Momento | Alvo | Laudo |
| --- | --- | --- |
| D1 | cada PNG isolado | `LAUDO_D1_ASSETS.md` |
| D2 | cada frame composto, parado | `LAUDO_D2_FRAMES.md` |
| D3 | os 4 estados lidos em sequência | `LAUDO_D3_ESTADOS.md` |
| D4 | o motion sobre o vídeo, no tempo real | `LAUDO_D4_PLATE.md` |
| D5 | o master | `LAUDO_D5_MASTER.md` |

## D1 — asset isolado

1. Borda física irregular, ou vetorial digital? → vetorial = **BLOCKER**
2. Tem sombra embutida na imagem? → sim = **BLOCKER** (sombra é camada)
3. Material reconhecível, ou "renderizado"? → renderizado = **HIGH**
4. Tem brilho, glow, gradiente ou 3D plástico? → sim = **BLOCKER**
5. Recortável sem fundir com o fundo? → não = **BLOCKER**
6. Tem texto gerado por IA? → sim = **BLOCKER**
7. Saturação contida e pretos foscos? → não = **MEDIUM**

## D2 — frame composto, parado

As dez regras do guia de estilo:

1. Entendo a ideia em menos de 1 segundo?
2. Existe uma evidência dominante?
3. A anotação aponta algo específico?
4. O vazio ajuda a leitura?
5. Os materiais parecem físicos?
6. A cor de destaque tem função?
7. Poderia existir na mesma mesa das outras cenas?
8. Há profundidade por sobreposição e sombra de contato?
9. **Legível a 300px de largura?** — renderize e olhe, não estime
10. Tirar qualquer elemento pioraria a explicação?

"Não" em 1, 2 ou 10 reprova. "Não" nas outras exige correção localizada, nunca redesenho.

Três específicas de footage:

11. Cobre rosto, olhos ou boca? → sim = **BLOCKER**
12. Invade os 120px da direita ou os 260px inferiores? → sim = **BLOCKER** (prop
    sangrando de propósito não conta)
13. Em overlay: parece colado no vídeo, ou flutuando? → flutuando = **HIGH**

## D3 — os quatro estados

1. Dá para narrar o que aconteceu só olhando os quatro? → não = **BLOCKER**
2. Cada estado tem exatamente uma novidade? → não = **HIGH**
3. Algum objeto se move sem motivo narrativo? → sim = **HIGH**
4. O `END` cai **depois** do último evento? → não = **HIGH** (mostra texto pela metade)
5. Existe hold de 8–18 frames? → não = **MEDIUM**

## D4 — sobre o vídeo, no tempo real

1. Palavra-âncora e entrada do elemento coincidem (±3 frames)?
2. O corte de entrada cai depois da consoante, não antes?
3. O retorno ao rosto acontece antes da próxima frase?
4. A energia do falante cai durante o motion?
5. Sem áudio, o motion ainda faz sentido?
6. **Existe trecho parado acima de 1,5s?** — meça, não estime

## D5 — master

Contra a fonte: duração · cadência · contagem de frames · **MD5 do áudio**.
Bitrate **por trecho**, não do arquivo inteiro — é assim que se acha um plano
explodindo sozinho.

## Formato

```yaml
laudo: D#
alvo: <arquivo>
veredito: APROVADO | APROVADO_COM_CORRECAO | REPROVADO
achados:
  - severidade: BLOCKER|HIGH|MEDIUM|LOW
    item: <número da rubrica>
    observacao: <o que está errado>
    correcao: <uma alteração, específica>
proxima_etapa: <estado>
```

## Proibido ao Diretor

- Aprovar porque "ficou bonito"
- Pedir redesenho geral quando o defeito é localizado
- **Escrever número que não mediu** — laudo que existe para verificar não pode conter
  valor não verificado
- Aprovar frame sem responder a rubrica inteira
