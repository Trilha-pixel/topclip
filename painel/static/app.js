/* TopClip — painel. Sem framework e sem build: abre e roda. */
"use strict";

const app = document.getElementById("app");
const ETAPAS = [
  { id: "momentos", nome: "Momentos" },
  { id: "cortes", nome: "Cortes" },
  { id: "vertical", nome: "Vertical" },
  { id: "motion", nome: "Motion" },
  { id: "entrega", nome: "Entrega" },
];
const ESTADO_TXT = { feito: "pronto", andamento: "em andamento", pendente: "a fazer" };

// O pipeline grava códigos (sem acento, às vezes em inglês). Na tela, português de gente.
const ROTULOS = {
  historia: "história", story: "história", contradicao: "contradição", contrarian: "contra a corrente",
  dinheiro: "dinheiro", money: "dinheiro", declaracao_forte: "declaração forte", opinion: "opinião",
  curiosidade: "curiosidade", revelacao: "revelação", revelation: "revelação", autoridade: "autoridade",
  authority: "autoridade", aprendizado: "aprendizado", tutorial: "tutorial", humor: "humor",
  transformacao: "transformação", transformation: "transformação", conflito: "conflito", conflict: "conflito",
  risco: "risco", demonstracao: "demonstração", fast_answer: "resposta rápida", long_clip: "clipe longo",
  medio: "médio", alto: "alto", baixo: "baixo",
  APPROVE: "aprovado", PASS: "aprovado", REBUILD: "refazer", DUPLICATE: "duplicado", REJECT: "reprovado", LONG_CLIP: "clipe longo",
  contexto_insuficiente: "falta contexto",
};
const rotulo = (v) => ROTULOS[v] || String(v ?? "").replace(/_/g, " ");

// ------------------------------------------------------------------ utilidades
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
    body: opcoes.body ? JSON.stringify(opcoes.body) : undefined,
  });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || `erro ${r.status}`);
  return dados;
}

// pseudo-aleatório com semente: o mesmo rabisco sempre que a tela redesenha
function aleatorio(semente) {
  let s = semente >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

/* Círculo feito à mão: elipse com tremor, que passa um pouco do ponto de partida —
   o mesmo gesto do hand_circle() do motor de motion. */
function circuloMao(w, h, semente = 7) {
  const r = aleatorio(semente);
  const cx = w / 2, cy = h / 2, rx = w / 2 - 4, ry = h / 2 - 4;
  const pts = [];
  const voltas = 1.18, n = 46, inicio = -2.2 + r() * 0.4;
  for (let i = 0; i <= n; i++) {
    const t = inicio + (i / n) * voltas * Math.PI * 2;
    const j = 1 + (r() - 0.5) * 0.07 + (i / n) * 0.05;
    pts.push([cx + Math.cos(t) * rx * j, cy + Math.sin(t) * ry * j]);
  }
  return "M" + pts.map((p) => p.map((v) => v.toFixed(1)).join(" ")).join(" L");
}

/* A linha azul de continuidade do motion, atravessando a trilha de etapas. */
function linhaAzul(w = 1000, h = 24, semente = 3) {
  const r = aleatorio(semente);
  let d = `M0 ${h / 2}`;
  for (let x = 40; x <= w; x += 40) d += ` Q${x - 20} ${h / 2 + (r() - 0.5) * 14} ${x} ${h / 2 + (r() - 0.5) * 6}`;
  return `<svg class="linha-azul" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" fill="none" stroke="#2e82f7" stroke-width="3" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}

const VISTO = `<svg viewBox="0 0 26 26" aria-hidden="true"><path d="M5 14 L10.5 19.5 L21.5 6.5" fill="none" stroke="#2a292c" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const SETA = `<svg viewBox="0 0 120 70" aria-hidden="true"><path d="M8 10 C 40 6, 80 20, 96 52" fill="none" stroke="#2a292c" stroke-width="2.6" stroke-linecap="round"/><path d="M84 46 L97 55 L101 39" fill="none" stroke="#2a292c" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function aviso(texto, ms = 3200) {
  const el = document.createElement("div");
  el.className = "papel fita direita aviso-flutuante";
  el.innerHTML = texto;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

async function copiar(texto, botao) {
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    const t = document.createElement("textarea");
    t.value = texto; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  if (botao) { const o = botao.textContent; botao.textContent = "Copiado!"; setTimeout(() => (botao.textContent = o), 1400); }
}

const comando = (texto) =>
  `<div class="comando"><code>${esc(texto)}</code><button class="botao claro pequeno" data-copiar="${esc(texto)}">Copiar</button></div>`;

function proximoPasso(titulo, texto) {
  return `<div class="proximo"><span class="mao">${esc(titulo)}</span>${comando(texto)}</div>`;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-copiar]");
  if (b) copiar(b.dataset.copiar, b);
});

// ------------------------------------------------------------------ rotas
function marcarNav(qual) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("ativo", a.dataset.nav === qual));
}

let relogio = null;            // atualização ao vivo da tela atual
let escolhaNaoSalva = false;   // não redesenhar por cima de uma escolha em andamento

async function rotear() {
  clearInterval(relogio);
  escolhaNaoSalva = false;
  const partes = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  window.scrollTo(0, 0);
  esconderBarra();
  try {
    if (partes[0] === "projeto" && partes[1]) { marcarNav("inicio"); return await telaProjeto(partes[1], partes[2]); }
    if (partes[0] === "biblioteca") { marcarNav("biblioteca"); return await telaBiblioteca(); }
    if (partes[0] === "instalacao") { marcarNav("instalacao"); return await telaInstalacao(); }
    marcarNav("inicio");
    return await telaInicio();
  } catch (err) {
    app.innerHTML = `<div class="vazio"><h2 class="titulo">Ops.</h2><p class="lead" style="margin:16px auto">${esc(err.message)}</p><a class="botao" href="#/">Voltar ao início</a></div>`;
  }
}
window.addEventListener("hashchange", rotear);

// ------------------------------------------------------------------ início
function trilha(etapas) {
  return `<div class="trilha">${ETAPAS.map((e, i) =>
    `${i ? `<i class="${etapas[e.id] === "feito" ? "feito" : ""}"></i>` : ""}<span class="${etapas[e.id]}" title="${e.nome}: ${ESTADO_TXT[etapas[e.id]]}"></span>`).join("")}</div>`;
}

function cartaoProjeto(p) {
  const iniciais = p.nome.split(/\s+/).slice(0, 2).map((s) => s[0] || "").join("").toUpperCase();
  const atual = ETAPAS.find((e) => e.id === p.etapa_atual);
  const pronto = Object.values(p.etapas).every((v) => v === "feito");
  return `
  <a class="cartao papel fita" href="#/projeto/${esc(p.slug)}">
    ${p.demo ? `<span class="selo-demo">exemplo</span>` : ""}
    ${["rodando", "ativo"].includes(p.atividade) ? `<span class="ativo-selo"><i></i>trabalhando</span>`
      : ["sua_vez", "avisar_claude"].includes(p.atividade) ? `<span class="ativo-selo sua_vez"><i></i>sua vez</span>` : ""}
    <div class="capa">${p.capa ? `<img src="${p.capa}" alt="" loading="lazy">` : `<span class="iniciais">${esc(iniciais)}</span>`}</div>
    <h3>${esc(p.nome)}</h3>
    <div class="meta">${esc(p.video || "sem vídeo definido")}</div>
    ${trilha(p.etapas)}
    <div class="trilha-rotulo">${pronto ? "tudo pronto!" : `próximo: ${esc(atual ? atual.nome.toLowerCase() : "")}`}</div>
  </a>`;
}

async function telaInicio() {
  const { projetos } = await api("/api/projetos");
  const temExemplo = projetos.some((p) => p.slug === "exemplo-podcast");
  app.innerHTML = `
  <section class="heroi">
    <div>
      <h1 class="manchete">Do podcast<br>ao <span class="marca">Short</span></h1>
      <p class="lead">Seus projetos de corte num lugar só. O Claude faz o trabalho pesado — você escolhe o que fica.</p>
      <div class="heroi-acoes">
        <button class="botao" data-acao="novo">+ Novo projeto</button>
        ${temExemplo ? "" : `<button class="botao claro" data-acao="demo">Ver um exemplo</button>`}
      </div>
    </div>
    <div class="heroi-arte">
      <img src="/static/img/heroi.jpg" alt="Cena de motion do TopClip: despertador sobre papel pontilhado com a palavra MVP na fita crepe">
      <div class="rabisco">desenhado pelo Claude, em código${SETA}</div>
    </div>
  </section>

  <div class="secao-topo">
    <h2 class="subtitulo">Seus projetos <span class="mudo">(${projetos.length})</span></h2>
  </div>
  ${projetos.length
    ? `<div class="grade">${projetos.map(cartaoProjeto).join("")}</div>`
    : `<div class="vazio papel">
         <h3 class="titulo">Nenhum projeto ainda</h3>
         <p class="lead" style="margin:14px auto 26px">Crie o primeiro: dê um nome, aponte o vídeo, e o painel te diz o que pedir ao Claude.</p>
         <button class="botao" data-acao="novo">+ Novo projeto</button>
       </div>`}`;

  app.querySelectorAll('[data-acao="novo"]').forEach((b) => (b.onclick = abrirNovoProjeto));
  const chave = (lista) => JSON.stringify(lista.map((p) => [p.slug, p.atividade, p.etapa_atual]));
  const antes = chave(projetos);
  relogio = setInterval(async () => {
    if (document.querySelector(".modal-fundo")) return;          // formulário aberto: não mexe
    const r = await api("/api/projetos").catch(() => null);
    if (r && chave(r.projetos) !== antes) { clearInterval(relogio); telaInicio(); }
  }, 5000);
  const demo = app.querySelector('[data-acao="demo"]');
  if (demo) demo.onclick = async () => { const r = await api("/api/demo", { method: "POST" }); location.hash = `#/projeto/${r.slug}`; };
}

function abrirNovoProjeto() {
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `
  <form class="modal papel fita" autocomplete="off">
    <h2 class="titulo">Novo projeto</h2>
    <p class="explica">Um vídeo, um projeto. Tudo que sair dele fica em <span class="mono">projetos/</span>.</p>
    <div class="campo">
      <label>O vídeo</label>
      <div class="soltar" data-soltar>
        <button type="button" class="botao" data-escolher>Escolher vídeo no computador</button>
        <span class="mao">ou arraste o arquivo para cá</span>
      </div>
      <div class="escolhido" data-escolhido hidden>
        <span class="escolhido-icone" aria-hidden="true">▶</span>
        <div><b data-escolhido-nome></b><small data-escolhido-caminho></small></div>
        <button type="button" class="link" data-trocar>trocar</button>
      </div>
      <details class="detalhe colar"><summary>prefiro colar o caminho</summary>
        <input id="video" name="video" placeholder="/Users/voce/Videos/podcast.mp4">
      </details>
    </div>
    <div class="campo">
      <label for="nome">Nome do projeto</label>
      <input id="nome" name="nome" placeholder="Podcast com a Ana — ep. 12" required>
      <small>Preenche sozinho com o nome do vídeo — mude se quiser.</small>
    </div>
    <div class="erro" hidden></div>
    <div class="modal-acoes">
      <button type="button" class="botao claro" data-fechar>Cancelar</button>
      <button type="submit" class="botao">Criar projeto</button>
    </div>
  </form>`;
  document.body.appendChild(fundo);
  const form = fundo.querySelector("form");
  const erro = form.querySelector(".erro");
  const fechar = () => fundo.remove();
  fundo.addEventListener("click", (e) => { if (e.target === fundo || e.target.closest("[data-fechar]")) fechar(); });

  const soltar = form.querySelector("[data-soltar]");
  const escolhido = form.querySelector("[data-escolhido]");
  let nomeMexido = false;
  form.nome.addEventListener("input", () => (nomeMexido = true));
  const mostrarErro = (msg) => { erro.hidden = !msg; erro.textContent = msg || ""; };

  // "podcast_ana-ep12.mp4" -> "Podcast ana ep12": um ponto de partida, não uma regra
  const nomeDoArquivo = (arq) => {
    const base = arq.replace(/\.[^.]+$/, "").replace(/[_\-.]+/g, " ").replace(/\s+/g, " ").trim();
    return base.charAt(0).toUpperCase() + base.slice(1);
  };
  const definirVideo = (caminho) => {
    form.video.value = caminho;
    const arq = caminho.split("/").pop();
    escolhido.querySelector("[data-escolhido-nome]").textContent = arq;
    escolhido.querySelector("[data-escolhido-caminho]").textContent = caminho;
    escolhido.hidden = false;
    soltar.hidden = true;
    if (!nomeMexido || !form.nome.value.trim()) form.nome.value = nomeDoArquivo(arq);
    mostrarErro("");
  };
  form.querySelector("[data-trocar]").onclick = () => { escolhido.hidden = true; soltar.hidden = false; form.video.value = ""; };
  form.video.addEventListener("change", () => { if (form.video.value.trim()) definirVideo(form.video.value.trim().replace(/^['"]|['"]$/g, "")); });

  const botaoEscolher = form.querySelector("[data-escolher]");
  botaoEscolher.onclick = async () => {
    const texto = botaoEscolher.textContent;
    botaoEscolher.textContent = /Mac/.test(navigator.platform) ? "Abrindo o Finder…" : "Abrindo a janela…";
    botaoEscolher.disabled = true;
    try {
      const r = await api("/api/escolher-video", { method: "POST" });
      if (r.caminho) definirVideo(r.caminho);
      else if (r.indisponivel) { mostrarErro("Não consegui abrir a janela de escolha neste sistema. Cole o caminho abaixo."); form.querySelector(".colar").open = true; }
      else if (r.erro) mostrarErro(r.erro);
    } catch (err) { mostrarErro(err.message); }
    botaoEscolher.textContent = texto;
    botaoEscolher.disabled = false;
  };

  ["dragenter", "dragover"].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.add("arrastando"); }));
  ["dragleave", "drop"].forEach((ev) => soltar.addEventListener(ev, () => soltar.classList.remove("arrastando")));
  soltar.addEventListener("drop", async (e) => {
    e.preventDefault();
    const arq = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!arq) return;
    mostrarErro("");
    soltar.querySelector(".mao").textContent = `procurando ${arq.name}…`;
    try {
      const r = await api("/api/localizar-video", { method: "POST", body: { nome: arq.name, tamanho: arq.size } });
      if (r.caminho) definirVideo(r.caminho);
      else mostrarErro(r.erro);
    } catch (err) { mostrarErro(err.message); }
    soltar.querySelector(".mao").textContent = "ou arraste o arquivo para cá";
  });
  // soltar o arquivo fora da área não pode fazer o navegador abrir o vídeo e perder o formulário
  fundo.addEventListener("dragover", (e) => e.preventDefault());
  fundo.addEventListener("drop", (e) => e.preventDefault());

  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api("/api/projetos", { method: "POST", body: { nome: form.nome.value, video: form.video.value } });
      form.innerHTML = `
        <h2 class="titulo">Agora é com o <span class="marca">Claude</span></h2>
        <p class="explica">Abra o Claude Code na pasta do TopClip e cole o comando abaixo. Ele começa pela transcrição e para quando tiver os momentos para você escolher — aqui no painel.</p>
        ${r.aviso ? `<p class="erro">${esc(r.aviso)}</p>` : ""}
        <div style="margin-top:22px">${comando(`/topclip projetos/${r.slug}`)}</div>
        <div class="modal-acoes">
          <a class="botao" href="#/projeto/${esc(r.slug)}" data-fechar>Ir para o projeto</a>
        </div>`;
    } catch (err) {
      erro.hidden = false;
      erro.textContent = err.message;
    }
  };
}

// ------------------------------------------------------------------ projeto
let escolhas = { momentos: new Set(), cortes: new Set() };

function trilhaEtapas(p, ativa) {
  return `
  <div class="etapas">
    ${linhaAzul()}
    ${ETAPAS.map((e, i) => `
      <button class="etapa ${p.etapas[e.id]}" data-etapa="${e.id}" aria-current="${e.id === ativa}">
        <span class="num">${p.etapas[e.id] === "feito" ? VISTO.replace('stroke="#2a292c"', 'stroke="#fff"') : i + 1}</span>
        ${e.id === ativa ? `<svg class="circulo" viewBox="0 0 82 76" aria-hidden="true"><path d="${circuloMao(82, 76, i * 13 + 5)}"/></svg>` : ""}
        <span class="nome">${e.nome}</span>
        <span class="estado">${ESTADO_TXT[p.etapas[e.id]]}</span>
      </button>`).join("")}
  </div>`;
}

async function telaProjeto(slug, etapa) {
  const p = await api(`/api/projetos/${encodeURIComponent(slug)}`);
  const ativa = ETAPAS.some((e) => e.id === etapa) ? etapa : p.etapa_atual;
  escolhas = {
    momentos: new Set(p.escolhas.momentos || []),
    cortes: new Set(p.escolhas.cortes || []),
  };
  const corpo = { momentos: blocoMomentos, cortes: blocoCortes, vertical: blocoVertical, motion: blocoMotion, entrega: blocoEntrega }[ativa](p);

  app.innerHTML = `
  <a class="voltar" href="#/">← todos os projetos</a>
  <div class="cabeca-projeto">
    <div>
      <h1 class="titulo">${esc(p.nome)}</h1>
      <div class="caminho">${p.video ? `🎬 ${esc(p.video)}` : "sem vídeo definido"}${p.run ? ` · run ${esc(p.run)}` : ""}</div>
    </div>
    <button class="botao claro pequeno" data-acao="abrir">Abrir pasta</button>
  </div>
  ${trilhaEtapas(p, ativa)}
  <section class="atividade papel" id="atividade"><div class="mudo mono">carregando a atividade…</div></section>
  <section class="painel-etapa papel">${corpo}</section>`;

  app.querySelectorAll("[data-etapa]").forEach((b) => (b.onclick = () => (location.hash = `#/projeto/${slug}/${b.dataset.etapa}`)));
  app.querySelector('[data-acao="abrir"]').onclick = () => api(`/api/projetos/${slug}/abrir`, { method: "POST" }).catch((e) => aviso(esc(e.message)));
  ligarEscolhas(p, ativa);
  acompanharAtividade(slug, etapa);
}

const pedirAoClaude = (p) => `/topclip projetos/${p.slug}`;

function blocoMomentos(p) {
  if (!p.momentos.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Momentos</h2>
      <p class="explica">O Claude lê a transcrição inteira e separa os trechos que prendem quem cai ali sem contexto — com gancho, desenvolvimento e fechamento. Eles aparecem aqui para você escolher.</p></div></div>
    ${proximoPasso("comece pelo Claude:", pedirAoClaude(p))}`;
  }
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.momentos.length} momentos encontrados</h2>
      <p class="explica">Marque os que você quer transformar em corte. O Claude só segue com os escolhidos.</p></div>
    <div style="display:flex;gap:16px"><button class="link" data-todos="momentos">marcar todos</button><button class="link" data-limpar="momentos">limpar</button></div>
  </div>
  <div class="lista">
    ${p.momentos.map((m) => `
      <article class="momento ${escolhas.momentos.has(m.id) ? "escolhido" : ""}" data-item="momentos" data-id="${esc(m.id)}" tabindex="0" role="checkbox" aria-checked="${escolhas.momentos.has(m.id)}">
        <span class="tempo">${esc(m.inicio)} → ${esc(m.fim)}</span>
        <div>
          <p class="citacao">${esc(m.quote)}</p>
          <div class="tags">
            ${m.trigger ? `<span class="tag forte">${esc(rotulo(m.trigger))}</span>` : ""}
            ${m.profile && rotulo(m.profile) !== rotulo(m.trigger) ? `<span class="tag">${esc(rotulo(m.profile))}</span>` : ""}
            ${m.confidence != null ? `<span class="tag">confiança ${Math.round(m.confidence * 100)}%</span>` : ""}
            ${m.risk_of_distortion && m.risk_of_distortion !== "baixo" ? `<span class="tag risco">risco de distorção: ${esc(rotulo(m.risk_of_distortion))}</span>` : ""}
          </div>
          ${m.context_needed ? `<p class="detalhe"><b>Contexto:</b> ${esc(m.context_needed)}</p>` : ""}
          ${m.payoff_candidate ? `<p class="detalhe"><b>Fecha com:</b> ${esc(m.payoff_candidate)}</p>` : ""}
        </div>
        <span class="marcar">${VISTO}</span>
      </article>`).join("")}
  </div>
  <div data-depois-salvar hidden>${proximoPasso("agora diga ao Claude:", "escolhi no painel, pode seguir")}</div>`;
}

function blocoCortes(p) {
  if (!p.cortes.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Cortes</h2>
      <p class="explica">Com os momentos escolhidos, o Claude crava o início e o fim de cada corte no timing das palavras e gera uma prévia para você assistir.</p></div></div>
    ${p.momentos.length ? proximoPasso("escolheu os momentos? diga ao Claude:", "escolhi no painel, pode seguir") : proximoPasso("comece pelo Claude:", pedirAoClaude(p))}`;
  }
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.cortes.length} cortes para assistir</h2>
      <p class="explica">Assista e marque os que viram vertical. Os outros param aqui.</p></div>
    <div style="display:flex;gap:16px"><button class="link" data-todos="cortes">marcar todos</button><button class="link" data-limpar="cortes">limpar</button></div>
  </div>
  <div class="cortes">
    ${p.cortes.map((c) => `
      <article class="corte ${escolhas.cortes.has(c.id) ? "escolhido" : ""}" data-cartao="${esc(c.id)}">
        ${c.preview ? `<video src="${c.preview}" controls preload="metadata" playsinline></video>`
                    : `<div class="sem-video">a prévia aparece aqui<br>quando o Claude cortar</div>`}
        <div class="corte-corpo">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
            <h4>${esc(c.titulo || c.id)}</h4>
            ${c.nota != null ? `<span class="nota">${c.nota}<small>/10</small></span>` : ""}
          </div>
          <div class="tags">
            ${c.duracao ? `<span class="tag forte">${Math.round(c.duracao)}s</span>` : ""}
            ${c.perfil ? `<span class="tag">${esc(rotulo(c.perfil))}</span>` : ""}
            ${c.status ? `<span class="tag">${esc(rotulo(c.status))}</span>` : ""}
            ${c.falhas.map((f) => `<span class="tag risco">${esc(rotulo(f))}</span>`).join("")}
          </div>
          ${c.porque ? `<p class="detalhe"><b>Por que funciona:</b> ${esc(c.porque)}</p>` : ""}
          ${c.transcricao ? `<details class="detalhe"><summary>ler a fala do corte</summary><p>${esc(c.transcricao)}</p></details>` : ""}
          <div class="corte-rodape">
            <button class="alternar" data-item="cortes" data-id="${esc(c.id)}" role="checkbox" aria-checked="${escolhas.cortes.has(c.id)}">
              <span class="marcar">${VISTO}</span> vira vertical
            </button>
          </div>
        </div>
      </article>`).join("")}
  </div>
  <div data-depois-salvar hidden>${proximoPasso("agora diga ao Claude:", "escolhi no painel, pode seguir")}</div>`;
}

function blocoVertical(p) {
  if (!p.verticais.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Vertical</h2>
      <p class="explica">Os cortes aprovados viram 9:16, com o enquadramento seguindo quem está falando — não o maior rosto.</p></div></div>
    ${proximoPasso("aprovou os cortes? diga ao Claude:", "escolhi no painel, pode seguir")}`;
  }
  return `
  <div class="secao-topo"><div><h2 class="subtitulo">${p.verticais.length} clipes verticais</h2>
    <p class="explica">Limpos, sem legenda e sem motion — prontos para a próxima etapa.</p></div></div>
  <div class="verticais">
    ${p.verticais.map((v) => `<div class="vertical"><video src="${v.video}" controls preload="metadata" playsinline></video><div class="rotulo">${esc(v.nome)}</div></div>`).join("")}
  </div>
  ${proximoPasso("quer motion e legenda? diga ao Claude:", "coloca motion nos verticais aprovados")}`;
}

function blocoMotion(p) {
  if (!p.motion.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Motion</h2>
      <p class="explica">O Claude escolhe as frases que têm objeto, desenha os elementos em código e monta as cenas no estilo TopClip Papel, cada uma presa à palavra exata da fala.</p></div></div>
    ${proximoPasso("com os verticais prontos, peça:", "coloca motion nos verticais aprovados")}`;
  }
  return p.motion.map((m) => `
    <div class="motion-bloco">
      <div class="secao-topo"><h2 class="subtitulo">${esc(m.nome)}</h2>${m.master ? `<span class="tag forte">master pronto</span>` : `<span class="tag">em produção</span>`}</div>
      <div class="verticais">
        ${m.master ? `<div class="vertical"><video src="${m.master}" controls preload="metadata" playsinline></video><div class="rotulo">master final</div></div>` : ""}
        ${m.quadros.map((q) => `<div class="vertical"><img src="${q}" alt="" loading="lazy"><div class="rotulo">${esc(decodeURIComponent(q.split("/").pop()))}</div></div>`).join("")}
      </div>
    </div>`).join("");
}

function blocoEntrega(p) {
  if (!p.entregas.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Entrega</h2>
      <p class="explica">Os masters conferidos (duração, cadência e áudio idêntico ao original) chegam aqui, prontos para postar.</p></div></div>
    ${proximoPasso("quando o motion estiver pronto:", "pode entregar os clipes")}`;
  }
  return `
  <div class="secao-topo"><div><h2 class="subtitulo">${p.entregas.length} clipes prontos para postar</h2>
    <p class="explica">Baixe ou abra a pasta. Bom post! 🎉</p></div>
    <button class="botao pequeno" data-acao="abrir-entregas">Abrir pasta</button></div>
  <div class="verticais">
    ${p.entregas.map((e) => `<div class="vertical"><video src="${e.video}" controls preload="metadata" playsinline></video>
      <div class="rotulo">${esc(e.nome)} · ${e.mb} MB · <a href="${e.video}" download>baixar</a></div></div>`).join("")}
  </div>`;
}

// ------------------------------------------------------------------ escolhas
function esconderBarra() { document.querySelector(".barra-acao")?.remove(); }

function ligarEscolhas(p, ativa) {
  const abrirEntregas = app.querySelector('[data-acao="abrir-entregas"]');
  if (abrirEntregas) abrirEntregas.onclick = () => api(`/api/projetos/${p.slug}/abrir`, { method: "POST" });
  if (!["momentos", "cortes"].includes(ativa)) return;
  const tipo = ativa;
  const conjunto = escolhas[tipo];
  const nomeItem = tipo === "momentos" ? ["momento escolhido", "momentos escolhidos"] : ["corte aprovado", "cortes aprovados"];

  const barra = document.createElement("div");
  barra.className = "barra-acao";
  barra.innerHTML = `<span class="conta"></span><button class="botao pequeno">Salvar escolhas</button>`;
  document.body.appendChild(barra);
  let mudou = false;

  const atualizar = () => {
    const n = conjunto.size;
    barra.querySelector(".conta").innerHTML = `<b>${n}</b> ${n === 1 ? nomeItem[0] : nomeItem[1]}`;
    barra.classList.toggle("visivel", mudou || n > 0);
    app.querySelectorAll(`[data-item="${tipo}"]`).forEach((el) => {
      const sim = conjunto.has(el.dataset.id);
      el.setAttribute("aria-checked", sim);
      (el.closest("[data-cartao]") || el).classList.toggle("escolhido", sim);
    });
  };
  const alternar = (id) => { conjunto.has(id) ? conjunto.delete(id) : conjunto.add(id); mudou = true; escolhaNaoSalva = true; atualizar(); };

  app.querySelectorAll(`[data-item="${tipo}"]`).forEach((el) => {
    el.addEventListener("click", (e) => { if (e.target.closest("video, details, a")) return; alternar(el.dataset.id); });
    el.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); alternar(el.dataset.id); } });
  });
  app.querySelector(`[data-todos="${tipo}"]`)?.addEventListener("click", () => {
    app.querySelectorAll(`[data-item="${tipo}"]`).forEach((el) => conjunto.add(el.dataset.id)); mudou = true; atualizar();
  });
  app.querySelector(`[data-limpar="${tipo}"]`)?.addEventListener("click", () => { conjunto.clear(); mudou = true; atualizar(); });

  barra.querySelector("button").onclick = async () => {
    try {
      await api(`/api/projetos/${p.slug}/escolhas`, { method: "POST", body: { [tipo]: [...conjunto] } });
      mudou = false;
      escolhaNaoSalva = false;
      atualizar();
      barra.classList.add("visivel");
      app.querySelector("[data-depois-salvar]")?.removeAttribute("hidden");
      app.querySelector("[data-depois-salvar]")?.scrollIntoView({ behavior: "smooth", block: "center" });
      aviso(`<b>Escolhas salvas.</b> Volte ao Claude e diga que escolheu no painel.`);
    } catch (err) {
      aviso(`<b>Não salvou:</b> ${esc(err.message)}`);
    }
  };
  atualizar();
}

// ------------------------------------------------------------------ atividade ao vivo
function ha(s) {
  if (s == null) return "";
  if (s < 10) return "agora";
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} dia${s >= 172800 ? "s" : ""}`;
}

function horario(iso) {
  const d = new Date(iso);
  const hoje = new Date().toDateString() === d.toDateString();
  const hh = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: hoje ? "2-digit" : undefined });
  return hoje ? hh : `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${hh}`;
}

const ICONE_EVENTO = { inicio: "▶", fim: "✓", arquivo: "✓", erro: "✕", info: "•", progresso: "…", voce: "★", projeto: "+" };
let atividadeAberta = false;

function desenharAtividade(slug, a) {
  const caixa = document.getElementById("atividade");
  if (!caixa) return;
  const ultimo = a.eventos[0];
  const falhou = ultimo && ultimo.tipo === "erro" && a.estado !== "rodando";
  const cls = falhou ? "erro" : a.estado;
  const rotulo = falhou ? "Algo falhou" : {
    rodando: "Trabalhando", ativo: "Trabalhando", sua_vez: "Sua vez", avisar_claude: "Sua vez",
    esperando_claude: "Esperando o Claude", parado: "Parado",
  }[a.estado];

  let agora;
  if (falhou) agora = `${esc(ultimo.msg)}<small>Veja a conversa com o Claude para o detalhe do erro.</small>`;
  else if (a.estado === "rodando") {
    // progresso: hoje só a transcrição anota ("transcrevendo: 12:30 de 36:10 (35%)")
    const r = a.rodando;
    const barra = r.pct != null ? `<span class="ativ-barra"><i style="width:${Math.max(0, Math.min(100, r.pct))}%"></i></span>` : "";
    const progresso = r.progresso ? `<small class="ativ-progresso">${barra}${esc(r.progresso)}</small>` : "";
    agora = `${esc(r.msg)}${progresso}<small>começou ${ha(r.ha_s)} · o painel atualiza sozinho</small>`;
  }
  else if (a.estado === "ativo") agora = `${esc(ultimo.msg)}<small>última notícia ${ha(a.ultima_ha_s)}</small>`;
  else if (a.estado === "sua_vez") agora = `${esc(a.sua_vez.msg)} <button class="link" data-ir-etapa="${a.sua_vez.etapa}">escolher agora</button>`;
  else if (a.estado === "avisar_claude") agora = `Você já escolheu. Agora diga ao Claude: ${comando("escolhi no painel, pode seguir")}`;
  else if (a.estado === "esperando_claude") agora = `Nada começou ainda. Cole no Claude Code, aberto na pasta do TopClip: ${comando(`/topclip projetos/${slug}`)}`;
  else agora = `${esc(ultimo ? ultimo.msg : "")}<small>última notícia ${ha(a.ultima_ha_s)} · se o Claude ainda estiver pensando, a próxima etapa aparece aqui sozinha</small>`;

  const lista = atividadeAberta ? a.eventos : a.eventos.slice(0, 6);
  caixa.innerHTML = `
    <div class="ativ-topo">
      <span class="ativ-estado ${cls}"><i></i>${rotulo}</span>
      <div class="ativ-agora">${agora}</div>
      ${a.eventos.length > 6 ? `<button class="link" data-ativ-alternar>${atividadeAberta ? "ver menos" : `ver tudo (${a.eventos.length})`}</button>` : ""}
    </div>
    ${a.eventos.length ? `<ul class="ativ-lista">${lista.map((e) => `
      <li><time datetime="${esc(e.t)}">${horario(e.t)}</time><span class="ic ${e.tipo}">${ICONE_EVENTO[e.tipo] || "•"}</span><span>${esc(e.msg)}</span></li>`).join("")}</ul>`
      : `<p class="ativ-vazio">O que o TopClip fizer neste projeto aparece aqui, ao vivo.</p>`}`;
  caixa.querySelector("[data-ativ-alternar]")?.addEventListener("click", () => { atividadeAberta = !atividadeAberta; desenharAtividade(slug, a); });
  caixa.querySelector("[data-ir-etapa]")?.addEventListener("click", (e) => (location.hash = `#/projeto/${slug}/${e.target.dataset.irEtapa}`));
}

function acompanharAtividade(slug, etapa) {
  let assinatura = null, chaveAnterior = null;
  const rota = location.hash;
  const passo = async () => {
    if (location.hash !== rota) return clearInterval(relogio);
    const a = await api(`/api/projetos/${encodeURIComponent(slug)}/atividade`).catch(() => null);
    if (!a) return;
    if (assinatura && a.assinatura !== assinatura && !escolhaNaoSalva) {
      // apareceu coisa nova (momentos, prévias, clipes): redesenha mantendo a rolagem
      clearInterval(relogio);
      const y = window.scrollY;
      await telaProjeto(slug, etapa);
      window.scrollTo(0, y);
      return;
    }
    assinatura = a.assinatura;
    const chave = JSON.stringify([a.estado, a.eventos.slice(0, 12), a.sua_vez, a.rodando && a.rodando.msg, atividadeAberta]);
    if (chave !== chaveAnterior || ["rodando", "ativo", "parado"].includes(a.estado)) {
      desenharAtividade(slug, a);
      chaveAnterior = chave;
    }
  };
  passo();
  relogio = setInterval(passo, 3000);
}

// ------------------------------------------------------------------ biblioteca
async function telaBiblioteca() {
  const { assets } = await api("/api/biblioteca");
  app.innerHTML = `
  <section style="margin-bottom:40px">
    <h1 class="manchete">A <span class="marca">biblioteca</span></h1>
    <p class="lead">Todo objeto desenhado num vídeo fica aqui para o próximo. Quanto mais você usa, mais coisa já vem pronta.</p>
  </section>
  ${assets.length ? `<div class="assets">${assets.map((a, i) => `
    <figure class="asset papel ${i % 3 === 1 ? "fita" : ""}" style="margin:0">
      <div class="vitrine ${a.arquivo.startsWith("BG_") ? "fundo" : ""}"><img src="${a.url}" alt="${esc(a.objeto || a.arquivo)}" loading="lazy"></div>
      <h4>${esc(a.arquivo)}</h4>
      <p>${esc(a.objeto || "")}</p>
    </figure>`).join("")}</div>`
  : `<div class="vazio papel"><h3 class="titulo">Biblioteca vazia</h3><p class="lead" style="margin:14px auto">O primeiro vídeo com motion já começa a encher.</p></div>`}`;
}

// ------------------------------------------------------------------ instalação
async function telaInstalacao() {
  app.innerHTML = `
  <section style="margin-bottom:40px">
    <h1 class="manchete">Tudo <span class="marca">pronto?</span></h1>
    <p class="lead">O passo a passo para instalar e o que o seu computador já tem.</p>
  </section>
  <div class="duas-colunas">
    <section class="papel fita painel-etapa">
      <h2 class="subtitulo" style="margin-bottom:22px">Como instalar</h2>
      <ol class="passos">
        <li><div><h4>Instale o Claude Code</h4><p class="explica">É ele que faz os cortes. Precisa de um plano pago do Claude (Pro ou Max). <a class="link" href="https://claude.com/claude-code" target="_blank" rel="noopener">claude.com/claude-code</a></p></div></li>
        <li><div><h4>Baixe o TopClip</h4>${comando("git clone https://github.com/Trilha-pixel/topclip.git && cd topclip")}</div></li>
        <li><div><h4>Rode o instalador</h4><p class="explica">Coloca o ffmpeg, o Python e o resto. Só uma vez.</p>${comando("./topclip instalar")}</div></li>
        <li><div><h4>Abra o painel</h4>${comando("./topclip painel")}</div></li>
      </ol>
    </section>
    <section class="papel painel-etapa" id="saude"><div class="carregando">verificando…</div></section>
  </div>`;
  await mostrarSaude(false);
}

async function mostrarSaude(forcar) {
  const caixa = document.getElementById("saude");
  if (!caixa) return;
  caixa.innerHTML = `<div class="carregando">verificando…</div>`;
  const s = await api(`/api/saude${forcar ? "?forcar" : ""}`);
  const faltas = s.itens.filter((i) => i.estado === "falta").length;
  const avisos = s.itens.filter((i) => i.estado === "aviso").length;
  const icone = { ok: "✓", aviso: "!", falta: "✕" };
  caixa.innerHTML = `
    <h2 class="subtitulo" style="margin-bottom:18px">Seu computador</h2>
    <div class="estado-geral">
      <span class="icone ${s.ok ? "ok" : "falta"}" style="width:40px;height:40px;font-size:20px;border-radius:50%;display:grid;place-items:center;color:#fff">${s.ok ? "✓" : "✕"}</span>
      <div><div class="grande">${s.ok ? "Tudo pronto" : "Falta algo"}</div>
      <div class="mudo mono">${faltas} faltando · ${avisos} avisos · conferido às ${esc(s.quando)}</div></div>
    </div>
    ${(() => {
      const item = (i) => `<li><span class="icone ${i.estado}">${icone[i.estado]}</span><span>${esc(i.texto)}</span></li>`;
      const problemas = s.itens.filter((i) => i.estado !== "ok");
      const oks = s.itens.filter((i) => i.estado === "ok");
      return `
        ${problemas.length ? `<ul class="checklist">${problemas.map(item).join("")}</ul>`
                           : `<p class="explica">Nada faltando. Pode abrir o Claude Code e começar um projeto.</p>`}
        ${oks.length ? `<details class="detalhe" style="margin-top:14px"><summary>ver os ${oks.length} itens conferidos</summary>
          <ul class="checklist">${oks.map(item).join("")}</ul></details>` : ""}`;
    })()}
    <div style="margin-top:22px;display:flex;gap:12px;flex-wrap:wrap">
      <button class="botao pequeno" id="reverificar">Verificar de novo</button>
      ${s.ok ? "" : comando("./topclip instalar")}
    </div>`;
  document.getElementById("reverificar").onclick = () => mostrarSaude(true);
}

rotear();
