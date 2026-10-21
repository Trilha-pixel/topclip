# Instalação — topclip-motion

A instalação é a do repositório inteiro, na raiz:

```bash
./topclip instalar
./topclip verificar
```

O instalador põe `ffmpeg` e Python 3.10+, cria a venv em `.venv/` e instala Pillow,
numpy, OpenCV e faster-whisper. A verificação desta skill checa as 9 fontes, o motor
(mede tipo, aplica o boil, confirma que a legenda exige configuração) e a biblioteca
de assets.

## Usar

No Claude Code, aberto na raiz do repositório: peça motion sobre um clipe vertical que
já existe — *"coloca uns motions nesse corte"*, *"ilustra essa fala"* — ou rode o fluxo
completo com `/topclip`.

Para montar um projeto à mão:

```bash
./topclip motion novo projetos/meu-clipe/motion
cp clipe-vertical.mp4 projetos/meu-clipe/motion/00_brief/fonte.mp4
./topclip motion transcrever projetos/meu-clipe/motion/00_brief/fonte.mp4 \
    projetos/meu-clipe/motion/00_brief/transcript_palavras.json
```

O modelo de transcrição baixa ~1,5 GB na primeira vez. **Transcript por palavra é
insumo sem substituto**: motion ancorado e legenda em corte seco dependem de saber em
que frame cada palavra foi dita.

`exemplo/clipe06_config.py` tem o bloco `CLIPE` de um clipe real preenchido, com o
motivo de cada escolha.

## O que a skill NÃO faz

Não gera vídeo com IA de vídeo. A composição por camadas em PIL dá controle exato de
posição, tempo e grafia — e produz o mesmo resultado com custo muito menor.

## Recalibrar ao trocar de fotografia

`night_photo.py` e `crt.py` trazem constantes medidas para fotografias específicas
(recorte, curva de cor, quadrilátero da tela). Fotografia nova pede recalibração — os
dois scripts dizem onde.

## Licenças

As 9 fontes são de licença livre (OFL/Apache), com os arquivos de licença em `fontes/`.
Fontes de sistema não podem ser redistribuídas — por isso a identidade foi construída
só sobre fontes abertas.
