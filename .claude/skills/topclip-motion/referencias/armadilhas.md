# Armadilhas

Cada uma custou pelo menos uma rodada de retrabalho. Confira antes de renderizar.

## Geometria

1. **Âncora sob rotação.** Fração medida no bitmap original não vale depois de
   `Image.rotate(expand=True)` — o referencial muda. Jogou um círculo manual para o
   centro do mostrador em vez do 12. Use `motor.rotate_anchor()`, verificado contra o
   PIL com erro < 1px. Vale para qualquer anotação presa a objeto rotacionado.

2. **Pan tem teto.** Push de N% dá apenas `N/2 %` da largura de folga lateral.
   Push 6% + pan 70px puxou borda preta para dentro do quadro. Calcule antes de
   prometer reframe: `pan_max = (escala − 1) × largura / 2`.

3. **Seta que volta.** Origem e destino na mesma coluna fazem a curva fechar um gancho
   sobre si mesma, sem direção legível. Alterne esquerda/direita.

4. **Polilinha sem spline vira ziguezague.** Traço manual não tem quina. Use Catmull-Rom.

## Recorte

5. **Sombra embutida.** Modelo de imagem sempre põe sombra de contato. Sombra é camada.
   Sinal que resolve: o objeto está de um lado do fundo em luminância e a sombra do
   outro, **lisa e neutra**. Deixe o fundo crescer só nessa faixa, com guarda de
   gradiente — aço escovado e tinta de gravura têm gradiente alto e ficam protegidos.

6. **A regra inverte para objeto escuro.** "Objeto é mais claro que o fundo" vale para
   papel e metal claro. Teclado charcoal (73) contra fundo cinza (144) seria comido
   inteiro. `dark_floor` troca o teto por uma faixa.

7. **Fundo transparente não existe.** Pedir "transparent background PNG" ao modelo
   devolve RGB sem alfa e um fundo cinza sólido. Testado.

8. **Fundo chroma custa spill.** Torna o matte trivial, mas contamina ~65% dos pixels de
   borda com a cor do fundo. Neste estilo a borda é a matéria. Prefira neutro escolhido
   pelo maior afastamento de luminância.

## Texto

9. **Máquina de escrever é template.** Revelar caractere a caractere em tipografia
   editorial é proibido. Bloco para editorial, write para marcador.

10. **Anchor "mm" usa a caixa da FONTE**, que inclui ascendente e descendente. Texto
    centrado nela escorrega para baixo e sai da faixa da fita. Use centro do *ink*.

11. **`text_width` subestima texto manual em até 20%** — soma avanços de fonte e ignora
    que o modo `hand` rotaciona e desloca cada caractere. Meça o desenho, não a fonte,
    ou o rótulo vaza para fora da etiqueta.

12. **A fita se dimensiona pela palavra**, nunca o contrário: `largura = texto / 0,62`.
    Com 41% de preenchimento a etiqueta lê como fita vazia com letras perdidas.

13. **Variação por caractere no marcador: ±1,4° e ±1,6% de baseline.** Com ±3,2° a
    palavra vira letras soltas. A bíblia pede "escrito de uma vez".

14. **Dois rótulos empilhados na mesma coluna viram um rótulo de duas linhas.**

## Acabamento

15. **Aberração cromática tem que ser radial**, nula no centro. Deslocamento horizontal
    uniforme franja toda letra de vermelho e ciano e lê como erro de render.

16. **Ruído de traço precisa de comprimento de correlação** (~26 pontos, interpolado),
    senão a linha vira corrente de contas em vez de traço de caneta.

17. **Grão aleatório por pixel e por frame é incompressível.** Sem correlação entre
    frames o x264 não prevê nada: 120 Mbps contra 4 Mbps do resto. Borre o campo
    (σ≈0,9 — grão de filme tem tamanho) e segure cada campo por 2 frames.

## Luz sem glow

18. A identidade proíbe neon, glow e bloom. Para "luz de tela chamativa":
    gere a foto com a tela como **única fonte**, pedindo explicitamente
    `no glow, no bloom, no halation, no volumetric rays`; meça o croma (numa foto real
    ele vem quase neutro, ~6); e **construa** a cor com mapa de gradiente sobre a
    luminância — sombras em carvão neutro, meios-tons na cor da paleta, núcleo da fonte
    quase branco. Nenhum pixel escuro é iluminado; só a curva muda.
    Normalize pelo percentil 2, não 0,4 — cortar mais baixo esmaga a silhueta.
    Borre o núcleo mais claro para matar interface legível.

19. **Foto escura sobre footage escuro precisa de cartão com margem branca grossa.**
    É a margem que separa. A proporção do corte tem que casar com a do cartão, senão
    a margem desaparece.

## Objeto vence palavra

26. **Ideia escrita a mao nao e o mesmo que ideia mostrada.** "CENTENAS -> MILHARES" em
    marcador estava certo de conteudo e errado de registro: o guia de estilo pede
    evidencia antes de estetica. Poucas notas -> maco de notas diz a mesma coisa sem uma
    letra. Antes de escrever uma palavra, pergunte que OBJETO diria aquilo.

27. **Cedula, documento e produto de marca: peca a impressao ILEGIVEL.** "printed design
    is an indistinct engraved pattern only, no readable numbers, no denomination, no
    portraits, no seals — not any real currency". Resolve a regra de nada-de-texto-de-IA
    e evita reproduzir dinheiro real. Gere variantes: uma das tres voltou com texto de
    IA visivel na nota e foi reprovada.

28. **Legenda que troca de cor precisa trocar na hora certa.** A decisao claro/escuro
    nao pode usar a janela inteira da cena: durante a SAIDA o papel ja foi embora e o
    video ocupa o quadro. Tinta escura sobre video escuro deixa so o halo claro visivel
    e a legenda le como copia dupla fantasmada. O ponto de troca depende do tipo de
    saida — `push` 0%, `wipe` 30%, `slide` 50% da duracao da saida.

## Boil

32. **Boil no quadro inteiro nao e boil.** Aplicado ao comp, o fundo ondula e vira
    distorcao de lente. No AE o Turbulent Displace vai em CADA layer — aqui tambem.

33. **Campo unico para o quadro todo le como tremor de camera.** Cada elemento precisa
    da propria semente, estavel entre frames. Semear por ordem de desenho quebra quando
    um objeto condicional aparece ou some — semeie pela linha que chamou.

34. **Elemento fisicamente unico precisa de campo unico.** Fita e a palavra escrita sobre
    ela sao um objeto so; com campos separados a etiqueta descola do papel.

35. **Objeto fotografado aguenta metade do que a tinta aguenta.** amount 6 no marcador
    le como redesenho; os mesmos 6 num relogio leem como derretimento, proibido pela
    §13. Mede antes: `obj 3 · paper 4 · type 2 · ink 6`.

36. **Estado implicito vaza entre passadas.** `_BOIL["frame"]` fica setado depois que a
    cena termina. Qualquer passada seguinte que desenhe texto herda o campo CONGELADO do
    ultimo frame — deformado e parado, o pior dos dois mundos. Zere no inicio de cada
    passada que nao deve boilar.

## Frase de impacto

37. **Legenda corrida briga com o motion.** Cena que ja tem uma palavra na tela nao
    aguenta uma segunda tipografia por cima. Frase de impacto entra so em janela SEM
    motion — e ha um `check()` que falha se colidir.

38. **Medir a posicao no frame do meio erra.** A pessoa se mexe durante a frase: o que
    estava livre no meio pode estar ocupado no fim. Meca o PIOR frame da janela.

39. **Energia de borda nao distingue paleto de microfone desfocado.** Os dois dao
    "calmo". Renderize a frase no inicio E no fim da janela e decida no olho.

40. **"Faixa mais calma" pode ser o rosto.** Energia de borda baixa nao significa
    espaco livre — pele lisa em close da o menor ruido do quadro. Detecte a face e
    coloque o texto abaixo do queixo mais baixo da janela.

41. **Inversao falha em tom medio.** Negativo de ~128 e ~128. Serve sobre escuro; sobre
    pele, piora. Quando nao ha area escura nem faixa livre, use tarja.

42. **Tipografia pede ruido FINO, objeto pede ruido grosso.** O mesmo preset nos dois
    erra: ruido grosso na letra deforma a forma; ruido fino no objeto nao aparece. Para
    texto use `size` pequeno (~22) — erode a borda como tinta em papel aspero.

43. **Textura nao deve escalar junto com intensidade.** `BOIL_SCALE` regula tremor;
    baixar o tremor dos objetos nao pode apagar a erosao de impressao da tipografia.

44. **Medir a referencia, nao imitar a impressao dela.** "Entrada animada parece mais
    fluida" estava errado por 4 frames de easing; a medicao mostrou corte seco puro e a
    fluidez vindo da cadencia. Antes de reproduzir um estilo, extraia os frames e meca:
    massa de tinta por frame, deslocamento, escala, bbox, cor.

45. **Acento raro e acento.** Pintar a palavra-chave em toda frase mata o dispositivo.
    Medido na referencia: 94% das linhas em branco puro.

46. **Blocos de legenda nao podem se sobrepor no tempo.** O render escolhe o primeiro
    que casa e o seguinte entra atrasado — perde a sincronia que faz o corte seco
    funcionar. Trunque `e` no `t` do proximo.

47. **Bloco de legenda nunca atravessa um corte do clipe.** Junta o fim de uma frase com
    o comeco de outra e le como erro de decupagem.

## Run aula-yt-teste (clip-005 e clip-010)

Cada uma custou uma remontagem de ~2 min (ou um laudo reprovado). Todas já estão
resolvidas no kit; ficam aqui para não voltar.

48. **Recuar a janela da legenda apaga a palavra do vão.** O recuo de 0,15s das bordas
    das cenas tirou o "Não" de "Não é difícil fazer" — a tela dizia o contrário do áudio.
    Cole a janela na cena (`janelas_livres`); o bloco é preso à janela, não invade.
    `captions.check()` para com erro em palavra sem legenda e sem cena.

49. **"Palavra inteira dentro da janela" perde a palavra da borda.** "consegue" em
    4,26–4,62 com a cena entrando em 4,55 não estava inteira em lugar nenhum. Reparta
    pelo **meio** da palavra.

50. **Altura de legenda medida num podcast não vale para selfie.** O rosto fica mais
    baixo e o CY padrão cobriu a boca. Posicione pelo queixo detectado no pior frame
    (`configurar(video=...)`).

51. **Ênfase de 168px estoura em palavra longa.** "MENSALIDADE," foi de x=67 a 1014.
    O corpo daquela palavra desce até caber (`LARGURA_MAX`); as curtas ficam em 168.

52. **A fonte desenha errado sem avisar.** No Permanent Marker "ª" sai como "A" ("1ª"
    lê "1A") e "≈" aponta para um "i". `text_layer` avisa; o "≈" sai desenhado à caneta.

53. **Asset que o template pede e a biblioteca não tem.** A saída `wipe` lia
    `A05_CARD.png`, que não existia: o render quebrava no meio da cena. Agora é
    `A05_SHEET` (desenhado), o kit desenha qualquer asset de `desenho.ASSETS` que faltar
    no projeto, e o render confere as saídas antes do primeiro quadro.

54. **Retalho ampliado borra.** Peça do A10 de ~360px levada a 850px perde a fibra e
    engrossa a pauta. Papel grande sai de `kit.scrap()`, no tamanho de uso; `piece()`
    avisa quando amplia mais de 1,25×.

55. **Revisar com o master final é caro.** `-preset slow` levava ~2 min por montagem e a
    run remontou 3 vezes por clipe. Revise com `render.py --rascunho` (veryfast) e
    monte o final uma vez.

56. **Teto de duração cortando a fala.** `MAXDUR` truncava o bloco antes da última
    palavra: o "para" aparecia adiantado e sumia quando era dito. Conferir só o TEXTO
    ("todas as palavras estão na tela") não pega — confira o TEMPO (`fora_de_hora`).

## Empacotar identidade

29. **Fonte de sistema trava a identidade numa maquina.** As do macOS nao podem ser
    redistribuidas. Use fontes de licenca livre e coloque-as DENTRO da skill, com os
    arquivos de licenca. Ao trocar, meca: Archivo Narrow e 1,35x mais larga que DIN
    Condensed, e o mesmo corpo estoura a composicao.

30. **Fonte variavel abre no peso padrao.** `ImageFont.truetype` de um `[wght].ttf` da
    Regular, nao o peso que a identidade pede. Trave o eixo com `set_variation_by_axes`.
    `getname()` continua reportando o nome base — nao serve de verificacao; mede densidade
    de tinta.

31. **Teste de instalacao limpa e obrigatorio.** Monte um diretorio vazio so com o que a
    skill entrega e renderize um frame. No clipe 06 isso pegou tres defeitos invisiveis
    na leitura: constante fora do modulo compartilhado, `__all__` definido antes das
    funcoes existirem, e nome de arquivo divergindo entre o kit e o codigo.

## Estado e processo

20. **`END` amostrado antes do último evento** mostra texto pela metade. Confira
    programaticamente: `END >= max(fim de evento)`.

21. **`EXIT` além do fim do plano** sugere um estado que nunca vai ao ar.

22. **`str.replace()` falha em silêncio.** Confirme cada patch por `grep -cF`.

23. **Métrica global engana.** Um rótulo de 270×90px num quadro 1080×1920 move menos de
    0,2% dos pixels: aparece como "parado" numa média global. Meça **dentro da caixa do
    elemento**.

24. **Objeto parado por segundos morre em cena.** Relógio congelado nega a própria ideia
    de tempo correndo. Dê ao menos um movimento lento e contínuo.

25. **Mostrador às 6h vira linha reta**, indistinguível de 12h em tela de celular.
    Prefira uma hora que forme L.
