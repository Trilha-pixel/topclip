# 12. Erros já cometidos nesta pipeline

Registro de falhas reais, com o sintoma e a correção. Ler antes de fechar cortes.
Não são hipóteses — cada linha custou um retrabalho.

## 12.1 Seleção e corte

| Erro | Onde apareceu | Correção |
| --- | --- | --- |
| Excluir bloco inteiro sem procurar janela apertada dentro | insight "produto é uma merda" | procurar a janela de 25s antes de descartar 55s |
| Deixar 4–6s de preâmbulo antes do número | "R$ 4 milhões" | abrir **no** número |
| Tese antes do loop de curiosidade | "terceiro carrinho" | pergunta primeiro; a moral vira payoff |
| Hook ocupando 73% do clipe | "quando você fala eu acredito" | virou linear |
| Truncar a última palavra | "vai ser muito gran—" | verificar borda com `silencedetect` |
| Abrir em "Uhum" | "R$ 200 milhões" | mover o in para a imagem forte |
| Publicar dois cortes, um contido no outro | "R$ 4 milhões" / "momento certo" | checar contenção antes de cortar |
| Cortar na fronteira de palavra que o Whisper deu | 113,58s, "Mas\|você" | `./topclip corte bordas` leva ao vale de energia (12.7) |

A checagem de borda de áudio foi o que pegou o corte truncando "grande". Ela é
barata e não é opcional:

```bash
ffmpeg -i CLIPE -af "silencedetect=noise=-35dB:d=0.1" -f null -
```

## 12.2 Enquadramento vertical

### Movimento de boca sozinho escolhe a pessoa errada

Dois problemas reais, nesta ordem:

**Bug de forma.** `cv2` devolve a caixa do rosto com jitter de 1–2px frame a frame.
Comparar o ROI da boca por igualdade de shape antes do diff faz a comparação falhar
quase sempre, e o motion fica `0.00` justamente para o rosto que mais aparece — o
locutor principal. Sintoma: motion média exatamente 0.00 num track com centenas de
detecções. **Redimensione o ROI para um tamanho fixo antes de comparar.**

**Motion engana mesmo corrigido.** Num clipe 100% monólogo (zero trocas de turno na
transcrição), o ouvinte passivo mostrou motion médio **maior** que quem falava o
tempo inteiro (17,5 vs 16,2) — ajeitou a mão perto do rosto, mastigou, reagiu.
Motion puro teria centralizado o crop na pessoa errada.

O que `scripts/active_speaker.py` faz em vez disso: **correlação entre movimento de
boca e energia do áudio**, com histerese para não ficar pingando. Correlação separa
locutor real de ouvinte inquieto; motion sozinho não.

### Nunca escolher pelo maior rosto

Em plano aberto, quem está mais perto da câmera tem o maior rosto e frequentemente
não é quem fala. O critério é a correlação audiovisual, nunca a área.

### A câmera do bruto zooma dentro do próprio corte

Detectado num clipe: um punch-in contínuo fez o grupo crescer de ~810px para
~1400px de largura ao longo de 39s. Crop fixo, mesmo bem centrado, cortava gente na
borda na segunda metade.

**Antes de decidir se o crop pode ser estático, olhe o span por bucket de tempo.**
Se a largura necessária varia mais de ~25% entre buckets, faça o enquadramento em
subsegmentos — que é exatamente o que `autoframe` produz.

### Rosto pequeno não detecta em passe único

Num plano aberto 1920px com 2–3 pessoas, cada rosto vira ~12px depois do resize
interno do detector — confiança abaixo de 0.2, erra quase tudo. O YuNet do pacote
já trabalha em resolução própria, mas quando for necessário cair para um detector
SSD, fatie o frame em tiras verticais sobrepostas e amplie 2× antes de detectar,
somando as coordenadas de volta e removendo duplicata por proximidade de centro.

### Amostrar, não processar frame a frame

2–5 fps já captura movimento de câmera e de pessoa num corte de 30–90s. Processar
todo frame é caro e não muda a decisão de crop.

### Close parado não precisa de 5 fps

Sugestão de comentarista, adotada com uma ressalva. Antes, todo plano passava
pela análise densa (5 fps de YuNet + boca × áudio), inclusive o close parado,
em que o resultado já era um crop estático na mediana. Agora `_plan_single_shot`
detecta primeiro em 3 frames (início, meio, fim) e só paga a densa quando a
amostra não basta (ver `fases/3-vertical.md`). Não economiza token, porque a
detecção já rodava em Python local. Economiza processamento.

A ressalva é a de "A câmera do bruto zooma dentro do próprio corte": 3 frames
fixos num plano de 39s não veem a câmera zoomando nem a pessoa saindo do lugar
no meio. Por isso o plano com mais de 20s amostra 1 frame a cada ~5s, e uma
largura de rosto que varia mais de 25% entre amostras manda para a densa. Em
plano aberto com várias pessoas a amostra não decide nada, e ele vai direto
para a densa.

A amostra para no primeiro frame que já decide pela densa. Numa mesa, o primeiro
frame mostra dois rostos e os outros nem são decodificados. Sem isso, o pior
caso abaixo ficava 39–49% mais lento, em vez de 15%.

Caso simulado: vídeo sintético 1080p30 H.264 a 6 Mb/s, 60s em 4 planos, GOP de
2s. Decodificação, YuNet e envelope de áudio são reais; só a resposta do
detector é simulada. Cada célula é o tempo de parede antes → depois, com as
duas variantes intercaladas:

| Cenário | Só enquadramento | Cortes + enquadramento | Caminhos |
| --- | --- | --- | --- |
| podcast típico: 3 closes + 1 mesa | 5,8s → 3,6s (−39%) | 7,8s → 5,8s (−26%) | amostrado ×3, denso ×1 |
| entrevista só de closes | 5,6s → 2,4s (−57%) | 7,6s → 4,6s (−39%) | amostrado ×4 |
| mesa o tempo todo (pior caso) | 6,0s → 6,9s (+15%) | 8,0s → 9,1s (+14%) | denso ×4, 1 amostra cada |

Com GOP de ~8s, o total fica em −26%, −34% e +15%. A medição rodou numa
máquina carregada (load 4–10, OBS aberto), e uma segunda rodada deu −20% no
enquadramento do caso típico. Trate como faixa, não como ponto: **~20–40% a
menos no podcast típico, ~35–60% em entrevista só de closes, ~10–15% a mais
quando é mesa o tempo todo.** O tipo decidido (`close`/`aberto`) foi o mesmo
antes e depois em todos os planos.

O que custa: cada frame amostrado em 1080p leva ~150ms (GOP 2s) a ~220ms
(GOP 8s). Quase tudo é decodificação desde o keyframe anterior; o spawn do
ffmpeg é ~30ms. `-threads 1` e `-hwaccel videotoolbox` são **mais lentos** para
um frame só. Amostrar no próprio keyframe cortaria esse custo; ainda não foi
feito.

### PySceneDetect: decodificar pelo ffmpeg, não pelo OpenCV

O caminho do manual (`open_video` + `SceneManager`) usa o `VideoCapture` do
OpenCV, que converte cada frame 1080p numa thread só: 4,5s por minuto de vídeo
contra 2,0s do filtro `scene` do ffmpeg. `_cuts_pyscenedetect` deixa o ffmpeg
decodificar (multithread, já em 256×144, que é a mesma resolução que o
`SceneManager` usaria) e passa os frames ao `AdaptiveDetector.process_frame`:
2,2s por minuto, com os mesmos cortes. No vídeo sintético ele achou um corte
(35s) que o limite fixo de 0,35 do ffmpeg perdeu. Sem esse corte, a mesa e o
close seguinte virariam um plano só de 40s.

Armadilha, caso alguém volte ao `SceneManager`: `detect_scenes(video, end_time=6)`
para no **frame 6**, não em 6s. `int` é número de frame para o PySceneDetect.
Pego no teste com vídeo sintético: `(0, 6)` não achava cortes; `(1.0, 6.0)`
achava. O teste `TestVideoSintetico.test_pyscenedetect_acha_os_cortes` passa
inteiros de propósito.

### Por que não YOLO (nota, sem dependência)

Detector de rosto/pessoa da família YOLO via Ultralytics é mais robusto a perfil
e oclusão que o YuNet, e seria a comparação natural. Fica de fora: o Ultralytics
é **AGPL-3.0**, e o TopClip é MIT. Puxar AGPL como dependência do pipeline
obrigaria o projeto inteiro a seguir a AGPL para quem o distribui ou serve. Se
for comparar, faça fora do repositório e traga só o número. Um detector com
pesos de licença permissiva também serve. O `mediapipe` já foi descartado por
outro motivo (12.3).

### Tracks fragmentados competem consigo mesmos

O tracker por vizinho mais próximo cria um track novo toda vez que perde e
reencontra um rosto (oclusão, ângulo). Agrupe tracks cujo `cx` médio fique a menos
de ~220px um do outro **antes** de qualquer scoring, senão a mesma pessoa disputa
contra si mesma e o score se dilui.

## 12.3 Ambiente

| Erro | Sintoma | Correção |
| --- | --- | --- |
| `pip install opencv-contrib-python` sem versão | trava no 5.0.0, sem `readNetFromCaffe` e sem haarcascades | pinar `==4.10.0.84` |
| `pip install scenedetect` sem teto | o 0.7 exige `opencv-python` e puxa o 5.0.0 junto do contrib, os dois brigando pelo mesmo `cv2` | `scenedetect>=0.6.4,<0.7,!=0.6.7.1`, sem extra `[opencv]` (o contrib já serve) |
| `scenedetect==0.6.7.1` | rebaixa `click` para 8.2.1 e o `huggingface-hub` do faster-whisper (exige `>=8.4.2`) quebra no `pip check` | excluir o 0.6.7.1; o 0.6.7 não tem esse teto |
| `pip install mlx-whisper` com dependências | puxa o `torch` (~400 MB) só para `mlx_whisper/torch_whisper.py`, um módulo de teste que nunca é importado | `--no-deps` + as dependências reais à mão (`instalar.sh`). O `pip check` passa a acusar "mlx-whisper requires torch" — esperado, não corrija instalando o torch |
| Insistir em `mediapipe` | `Check failed: service_ Service is unavailable` no `DrishtiMetalHelper`, mesmo com `delegate=CPU` | usar o detector do OpenCV |
| Testar substring `"ass"` nos filtros do ffmpeg | casa com `lowpass`, `highpass`, `bass`, `allpass`, `bandpass` — falso positivo | casar por palavra inteira (já corrigido em `preflight.py`) |
| `-c copy` para cortar | corta no keyframe errado, in/out não bate com o transcript | sempre recodificar |
| Rodar `init` sem `--workspace` | a run vai parar dentro da skill e some da vista | `--workspace projetos/<nome>/runs` |

## 12.4 Bugs corrigidos na fusão das skills

Encontrados ao unificar `viral-clip-harness`, `cortes-virais` e `vertical-reframe`:

| Bug | Efeito | Correção |
| --- | --- | --- |
| `cmd_autoframe` chamava `resolve_run()` e `read_json()`, que não existem | `NameError` — o comando `autoframe` nunca rodou | usa `ensure_run_dir()` e `load_json()` |
| `cmd_autoframe` lia `manifest["inputs"]["video"]` | a chave gravada é `video_path`; erro "Run sem vídeo" mesmo com vídeo | lê `video_path` |
| `autoframe` sem `11-edit-plans.json` | estourava com traceback cru | erro explícito mandando rodar o Edit Director antes |
| `framing.py` importava `active_speaker` sem pacote | quebrava conforme o diretório de execução | import de pacote com fallback |
| `autoframe` reescrevia `plan["timeline"]` inteira | apagava `layout` e `framing_reason` do Edit Director — o `split` virava `cover` silenciosamente | herda todo campo editorial do segmento de origem |
| VTT do YouTube caía no parser genérico de SRT | **timing por palavra perdido** e texto triplicado pela cue rolante | parser dedicado: palavra por palavra, dedupe por sufixo, `>>` como troca de locutor |
| Piso de duração mínima da cue (`max(start+0.2, ...)`) | vencia a regra de não sobrepor; `verify-output` reprovava com `srt_entries_overlap_or_out_of_order` | não sobrepor tem prioridade; cue curta é aceitável |
| Texto de cabeça de cue sem timestamp próprio | várias palavras no mesmo instante → legenda sobreposta adiante | distribuído no intervalo até a primeira palavra cronometrada |

Os quatro últimos só apareceram rodando o pipeline de verdade sobre 120s de
um podcast real. Os testes em `tests/test_vtt_e_legenda.py` e `tests/test_split_layout.py`
existem para que não voltem.

## 12.5 Ambiente macOS, medido

| Fato | Consequência |
| --- | --- |
| o `python3` do sistema no macOS é o 3.9; o pacote exige 3.10+ | por isso existe o lanchador `./topclip`, que usa a venv do repositório |
| o `ffmpeg` do Homebrew **não tem libass** | queimar legenda com o filtro `ass` é impossível; `make_captioned_version` fica desligado, e a topclip-motion queima por conta própria via Pillow + `overlay` |

## 12.6 `prepare` indexava o vídeo inteiro antes de qualquer seleção

Sintoma real: pedido de "só selecione os melhores momentos" (usuário já tinha
colado transcript com timestamps) rodou `vch prepare` num podcast de 3h15 e
travou — `_prepare_media` chamava `extract_visual_index()` incondicionalmente,
que decodifica o vídeo **inteiro duas vezes** (frames periódicos a cada 5s +
detecção de cena) antes mesmo do Context Mapper ou Clip Hunter rodarem. Nada
disso é necessário para seleção: ela roda inteira em cima do transcript.

Correção: `_prepare_media` não gera mais índice visual por padrão — grava
`03-visual-index.json` como placeholder adiado com aviso explícito.
`extract_visual_index()` ganhou `start_seconds`/`duration_seconds` (seek via
`-ss` antes do `-i`, sem decodificar o resto do arquivo) e um novo comando
`vch visual-index --run <dir> --windows "start-end,..."` gera o índice **só
nas janelas dos candidatos já escolhidos**, depois da seleção. `vch prepare
--visual-index` mantém o comportamento antigo (vídeo inteiro) para quem
precisar dele de propósito. Medido num podcast de 3h15 (11734s): `prepare` novo
(transcript + probe, sem índice) caiu de indeterminado/travado para ~8s.

Lição geral: **nenhum script do pacote deve decodificar o vídeo inteiro antes
da fase de seleção.** Se um novo passo do pipeline for tentado adicionar antes
do Clip Hunter e ele tocar no arquivo de vídeo (não só no transcript), isso é
sinal de que a ordem está errada de novo.

## 12.7 Fase 3 refazendo checagem: 25 min para 2 clipes, 13,5 em retrabalho

Run `aula-yt-teste` (21/10/2026), 2 clipes. A fase 3 levou 25 min, e 13,5 deles
foram checagem refeita, em cascata:

1. **Borda no meio de palavra colada.** O timing por palavra do Whisper erra
   0,1–0,5s quando as palavras são coladas. O início em 113,58s (a fronteira
   "Mas|você" pelo Whisper) pegava o fim do "Mas": a energia mostrava o "Mas"
   até 113,70 e o "você" só a partir de 114,17 — o intervalo que o Whisper deu
   ao "você" engolia a pausa e a cauda do "Mas". Outro fim cortava a cauda de
   "fazer", que o Whisper esticou até 2126,34s por cima da pausa (0,96s para
   duas sílabas). Corrigido à mão, medindo RMS a 10ms.
2. **Plano desatualizado.** Mover essas bordas no `11-edit-plans.json` deixou
   `clip_start`/`clip_end`, chunks de legenda, cards, `motion_anchors`,
   `punch_ins` e `breath_decupage` apontando para a versão anterior. O Quality
   Controller reprovou, o recálculo foi feito com script avulso, e o QC rodou
   de novo.
3. **Revisão de versão velha descoberta tarde.** O `finalize` consolidou um
   `07-feed-review.json` feito sobre a versão anterior do corte e deu REBUILD
   indevido. A revisão de feed foi refeita depois do QC.
4. **Override fora do pipeline.** Os dois ficaram `WEAK` (gate 7,5) e o usuário
   mandou seguir, mas o `render` só aceitava `APPROVED`/`LONG_CLIP`: os clipes
   foram renderizados chamando `render_clip` direto.

| Problema | Correção |
| --- | --- |
| borda no meio de palavra colada | `./topclip corte bordas --run` depois do Clip Builder e depois do Edit Director: mede RMS a 10ms e leva cada borda de corte ao vale — fica se já está em silêncio claro (< -50 dB), vai ao silêncio mais próximo em ±0,15s, ou ao ponto mais baixo abaixo de -40 dB; sem vale, `borda_fraca` em `warnings`. Nunca atravessa palavra: só cai no vão entre os corpos das palavras vizinhas (corpo = onde ela soa de fato dentro do intervalo do Whisper). Rodado sobre uma cópia da mesma run: 113,58 → 113,74s (-30,7 → -51,5 dB); 2125,85 → 2125,93s (-29,1 → -54,8 dB, o valor exato da correção manual); 2104,80s sai `borda_fraca` (-37 dB, fala colada sem pausa) |
| tempos do plano desatualizados | `bordas` e `autoframe` recalculam todo tempo de clipe pela posição na fonte (`scripts/tempos.py`): o que está grudado num corte acompanha o corte, o que está no meio acompanha a fala. Cada segmento guarda `synced_source`, então até borda editada à mão é recuperada; o `validate-artifact` do 11 acusa `tempo_de_clipe_desatualizado` |
| revisão de versão velha | cada entrada de 07, 09 e 12 é carimbada pelo script com `segments_hash` (versão do corte). `./topclip corte revisoes` lista o que refazer e roda **antes** do QC; o `finalize` para em vez de consolidar status errado. O ajuste do `bordas` e a emenda do `autoframe` não contam como versão nova |
| usuário quer seguir com WEAK | `finalize --seguir <ids> --motivo "..."`: `user_override` no 13, o render aceita, o relatório mantém `WEAK` numa seção própria. Vale enquanto o corte for o mesmo; hard fail não se força |

Lições:

- **Palavra do Whisper não é borda de corte.** Em palavra colada, o intervalo
  engole a pausa e a cauda da vizinha, e o meio do intervalo mente (o meio do
  "fazer" esticado caía antes do fim real da palavra). A borda se decide na
  energia; o Whisper só diz de que lado cada palavra está.
- **Todo número derivado precisa de quem o recalcule a partir da fonte.** Tempo
  de clipe é derivado de `source_start`/`source_end`; recalculá-lo à mão é o
  mesmo erro de estimar no modelo o que um script calcula.
- **Revisão vale para uma versão.** Descobrir revisão velha só no `finalize`
  custa o QC de novo. O portão é antes do QC.

Os testes `tests/test_bordas.py` (áudio sintético que reproduz "Mas|você" e o
"fazer" esticado), `tests/test_tempos.py` e `tests/test_versoes_e_override.py`
existem para que isso não volte.

## 12.8 Autoframe apagava o punch-in e podia abrir buraco na fonte

Achados rodando o `autoframe` sobre a run `aula-yt-teste` (21/10/2026), lida sem
gravar nada nela.

1. **Punch-in sobrescrito.** O Edit Director pôs `zoom: 1.08` em dois segmentos,
   motivado por número (clip-005, seg 3) e por virada de argumento (clip-010,
   seg 4) — a troca de zoom era o que disfarçava o jump cut. O `autoframe`
   tratava `zoom` como campo só dele e gravava o zoom do rosto: os dois saíam
   1.0, sem aviso. O `framing_reason` continuava dizendo "punch-in 1.08".
2. **Buraco na cobertura.** `plan_segments` descartava o trecho entre duas
   keyframes a menos de 0,15s uma da outra (`continue`), e nenhum vizinho
   cobria esse pedaço. Acontece na janela final de 0,1s antes de um corte de
   câmera, ou quando o plano do início é curto demais (< 0,3s) e a primeira
   keyframe vem depois do início do segmento. O render concatena os
   subsegmentos: aquele áudio sumia do clipe. E a cobertura entra no
   `segments_hash` (12.7): o buraco virava versão nova do corte e tornava velha
   a revisão do QC. Na run de teste, só closes (um subsegmento por segmento),
   não houve buraco; o defeito estava latente.

| Problema | Correção |
| --- | --- |
| punch-in do Edit Director virava 1.0 | o zoom do segmento é punch-in **relativo**: zoom final = zoom do rosto × zoom pedido, teto 2.0 (o do schema). Na mesma run: 1.08 → 1.08 nos dois. Com `max()` o punch-in sumiria num plano aberto em que o rosto já pede 1.3 |
| trecho < 0,15s descartado | os subsegmentos cobrem a faixa do segmento inteira: o trecho curto fica com o vizinho de trás (ou o da frente, no início), e a primeira keyframe vale desde o início do segmento. Mesmo `segments_hash` antes e depois do autoframe |

Lição: **etapa mecânica não reescreve decisão editorial calada.** O autoframe já
herdava `layout` e `framing_reason` (12.4) e continuava apagando o zoom, que
também é decisão do Edit Director. E **todo passo que subdivide segmento tem de
devolver a mesma faixa na fonte**: piscada de enquadramento se resolve no
enquadramento, nunca tirando áudio.

Os testes `TestZoomDoEditDirector` e `TestCoberturaDaFonte`, em
`tests/test_autoframe.py`, simulam o `plan_range` e existem para que isso não volte.
