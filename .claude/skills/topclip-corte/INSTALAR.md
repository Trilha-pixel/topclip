# Instalação — topclip-corte

A instalação é a do repositório inteiro, na raiz:

```bash
./topclip instalar
./topclip verificar
```

O instalador põe `ffmpeg` e Python 3.10+ (Homebrew no macOS, apt no Linux), cria a
venv em `.venv/`, instala `requirements.txt` e baixa o modelo YuNet para `models/`.
Os 8 subagentes já vêm em `.claude/agents/` — nada para copiar.

O que segue são as armadilhas que justificam cada escolha do instalador.

## Sempre pelo lançador

```bash
./topclip corte <subcomando>
```

Nunca `python3 scripts/vch.py` direto. O `python3` do sistema no macOS é o **3.9**,
e o pacote exige 3.10+. Chamando direto, o preflight responde `Análise: AUSENTE` e
o pipeline morre depois de você já achar que instalou tudo.

## O pin do OpenCV não é capricho

```bash
opencv-contrib-python==4.10.0.84
```

Sem versão, o pip vai para o 5.0.0, que removeu `cv2.dnn.readNetFromCaffe` e não
empacota os haarcascades — quebra os detectores. Não instale `opencv-python` junto:
o contrib já inclui tudo e os dois pacotes brigam pelo mesmo módulo `cv2`.

`mediapipe` foi testado e **descartado**: a variante Tasks API trava com
`Check failed: service_ Service is unavailable` ao inicializar o `DrishtiMetalHelper`
no macOS, mesmo forçando `delegate=CPU`. Não insista.

## ffmpeg sem libass

O `ffmpeg` do Homebrew pode vir sem libass — `ffmpeg -filters` não lista `ass` nem
`subtitles`. Não afeta o padrão: esta skill entrega o vertical limpo e a
`topclip-motion` queima a legenda por outro caminho (Pillow + `overlay`). Só não
ligue `make_captioned_version` esperando que funcione. `./topclip verificar` avisa.

## Sem `jsonschema`, a validação passa vazia

E é ela que segura a qualidade do pipeline. Não trate como opcional.

## Testes

```bash
./topclip testes
```

Os testes de `autoframe` pulam sozinhos quando `cv2`/`numpy` não estão instalados.
