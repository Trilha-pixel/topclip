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
const num = (n) => String(n).replace(".", ",");   // 7.5 -> "7,5"
const MOMENTOS_RECOMENDADOS = 5;   // escolher 14 para usar 2 custou ~1h a mais na fase de cortes

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
let rotaAtual = null, rotaAnterior = null;   // o "voltar" do estilo leva para onde a pessoa estava

async function rotear() {
  clearInterval(relogio);
  escolhaNaoSalva = false;
  [rotaAnterior, rotaAtual] = [rotaAtual, location.hash];
  const partes = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  window.scrollTo(0, 0);
  esconderBarra();
  try {
    if (partes[0] === "projeto" && partes[1]) { marcarNav("inicio"); return await telaProjeto(partes[1], partes[2]); }
    if (partes[0] === "biblioteca") { marcarNav("biblioteca"); return await telaBiblioteca(partes); }
    if (partes[0] === "instalacao") { marcarNav("instalacao"); return await telaInstalacao(); }
    marcarNav("inicio");
    return await telaInicio();
  } catch (err) {
    app.innerHTML = `<div class="vazio"><h2 class="titulo">Ops.</h2><p class="lead" style="margin:16px auto">${esc(err.message)}</p><a class="botao" href="#/">Voltar ao início</a></div>`;
  }
}
window.addEventListener("hashchange", rotear);

// ------------------------------------------------------------------ início
// "pronto", "a fazer" ou o % de quanto já foi
const estadoTxt = (estado, pct) => (estado === "andamento" && pct > 0 ? `${pct}%` : ESTADO_TXT[estado]);

function trilha(etapas, progresso = {}) {
  return `<div class="trilha">${ETAPAS.map((e, i) =>
    `${i ? `<i class="${etapas[e.id] === "feito" ? "feito" : ""}"></i>` : ""}<span class="${etapas[e.id]}" title="${e.nome}: ${estadoTxt(etapas[e.id], progresso[e.id])}"></span>`).join("")}</div>`;
}

function cartaoProjeto(p) {
  const iniciais = p.nome.split(/\s+/).slice(0, 2).map((s) => s[0] || "").join("").toUpperCase();
  const atual = ETAPAS.find((e) => e.id === p.etapa_atual);
  const pronto = Object.values(p.etapas).every((v) => v === "feito");
  // fez 2 de 14 e volta depois para o resto: "tudo pronto!" esconderia os outros 12
  const parcial = p.n_prontos > 0 && p.n_prontos < p.n_cortes;
  return `
  <a class="cartao papel fita" href="#/projeto/${esc(p.slug)}">
    ${p.demo ? `<span class="selo-demo">exemplo</span>` : ""}
    ${["rodando", "ativo"].includes(p.atividade) ? `<span class="ativo-selo"><i></i>trabalhando</span>`
      : ["sua_vez", "avisar_claude"].includes(p.atividade) ? `<span class="ativo-selo sua_vez"><i></i>sua vez</span>` : ""}
    <div class="capa">${p.capa ? `<img src="${p.capa}" alt="" loading="lazy">` : `<span class="iniciais">${esc(iniciais)}</span>`}</div>
    <h3>${esc(p.nome)}</h3>
    <div class="meta">${esc(p.video || (p.link ? `baixando de ${p.link}` : "sem vídeo definido"))}</div>
    ${trilha(p.etapas, p.progresso)}
    <div class="trilha-rotulo">${parcial ? `${p.n_prontos} de ${p.n_cortes} cortes prontos`
      : pronto ? "tudo pronto!" : atual && p.progresso && p.progresso[atual.id] > 0 && p.progresso[atual.id] < 100
      ? `agora: ${esc(atual.nome.toLowerCase())} · ${p.progresso[atual.id]}%`
      : `próximo: ${esc(atual ? atual.nome.toLowerCase() : "")}`}</div>
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
  const chave = (lista) => JSON.stringify(lista.map((p) => [p.slug, p.atividade, p.etapa_atual, p.n_prontos]));
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
      <div class="colar-link" data-colar-link>
        <label for="link" class="mao">ou cole o link do YouTube ou do Instagram</label>
        <input id="link" name="link" type="text" inputmode="url" spellcheck="false" placeholder="https://www.youtube.com/watch?v=…">
        <small data-link-estado hidden></small>
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
  const colarLink = form.querySelector("[data-colar-link]");
  let linkConferido = "";
  const definirVideo = (caminho) => {
    form.video.value = caminho;
    form.link.value = linkConferido = "";
    const arq = caminho.split("/").pop();
    escolhido.querySelector("[data-escolhido-nome]").textContent = arq;
    escolhido.querySelector("[data-escolhido-caminho]").textContent = caminho;
    escolhido.hidden = false;
    delete escolhido.dataset.tipo;
    soltar.hidden = colarLink.hidden = true;
    if (!nomeMexido || !form.nome.value.trim()) form.nome.value = nomeDoArquivo(arq);
    mostrarErro("");
  };
  form.querySelector("[data-trocar]").onclick = () => {
    escolhido.hidden = true; soltar.hidden = colarLink.hidden = false;
    form.video.value = form.link.value = linkConferido = "";
  };

  // Link do YouTube ou do Instagram: o servidor confere o vídeo (título, duração) na
  // hora e só baixa quando o projeto é criado — para dentro de projetos/<nome>/.
  const estadoLink = colarLink.querySelector("[data-link-estado]");
  let conferindo = null;
  const conferirLink = () => {
    const link = form.link.value.trim();
    if (!link) return Promise.resolve(false);
    if (link === linkConferido) return Promise.resolve(true);
    if (conferindo && conferindo.link === link) return conferindo.promessa;
    mostrarErro("");
    estadoLink.hidden = false;
    estadoLink.textContent = "procurando o vídeo…";
    const promessa = (async () => {
      try {
        const v = await api("/api/info-link", { method: "POST", body: { link } });
        if (v.erro) { mostrarErro(v.erro); return false; }
        form.video.value = "";
        linkConferido = v.link;
        escolhido.querySelector("[data-escolhido-nome]").textContent = v.titulo;
        escolhido.querySelector("[data-escolhido-caminho]").textContent =
          [v.site, v.duracao_txt, "baixa para o projeto quando você criar"].filter(Boolean).join(" · ");
        escolhido.hidden = false;
        escolhido.dataset.tipo = "link";
        soltar.hidden = colarLink.hidden = true;
        if (!nomeMexido || !form.nome.value.trim()) form.nome.value = v.titulo;
        return true;
      } catch (err) { mostrarErro(err.message); return false; }
      finally { estadoLink.hidden = true; conferindo = null; }
    })();
    conferindo = { link, promessa };
    return promessa;
  };
  form.link.addEventListener("paste", () => setTimeout(conferirLink, 0));
  form.link.addEventListener("change", conferirLink);
  form.link.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); conferirLink(); } });
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
    if (form.link.value.trim() && !(await conferirLink())) return;
    const link = linkConferido;
    try {
      const r = await api("/api/projetos", { method: "POST", body: { nome: form.nome.value, video: link ? "" : form.video.value, link } });
      form.innerHTML = `
        <h2 class="titulo">Agora é com o <span class="marca">Claude</span></h2>
        ${link ? `<p class="explica"><b>O vídeo já está baixando</b> para dentro do projeto — o andamento aparece na página dele. Não precisa esperar: o Claude espera o download terminar.</p>` : ""}
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
const VISTO_BRANCO = VISTO.replace('stroke="#2a292c"', 'stroke="#fff"');

// A cada volta do relógio: estado e % de cada etapa, sem redesenhar a tela
function atualizarTrilha(etapas) {
  if (!etapas) return;
  app.querySelectorAll(".etapa[data-etapa]").forEach((b) => {
    const e = etapas[b.dataset.etapa];
    if (!e) return;
    const era = ["feito", "andamento", "pendente"].find((c) => b.classList.contains(c));
    if (era !== e.estado) {
      b.classList.remove("feito", "andamento", "pendente");
      b.classList.add(e.estado);
      b.querySelector(".num").innerHTML = e.estado === "feito" ? VISTO_BRANCO : b.dataset.i;
    }
    b.querySelector(".barrinha i").style.width = `${e.pct}%`;
    b.querySelector(".estado").textContent = estadoTxt(e.estado, e.pct);
  });
}

function trilhaEtapas(p, ativa) {
  return `
  <div class="etapas">
    ${linhaAzul()}
    ${ETAPAS.map((e, i) => `
      <button class="etapa ${p.etapas[e.id]}" data-etapa="${e.id}" data-i="${i + 1}" aria-current="${e.id === ativa}">
        <span class="num">${p.etapas[e.id] === "feito" ? VISTO_BRANCO : i + 1}</span>
        ${e.id === ativa ? `<svg class="circulo" viewBox="0 0 82 76" aria-hidden="true"><path d="${circuloMao(82, 76, i * 13 + 5)}"/></svg>` : ""}
        <span class="nome">${e.nome}</span>
        <span class="barrinha" aria-hidden="true"><i style="width:${(p.progresso || {})[e.id] || 0}%"></i></span>
        <span class="estado">${estadoTxt(p.etapas[e.id], (p.progresso || {})[e.id])}</span>
      </button>`).join("")}
  </div>`;
}

async function telaProjeto(slug, etapa) {
  const p = await api(`/api/projetos/${encodeURIComponent(slug)}`);
  const ativa = ETAPAS.some((e) => e.id === etapa) ? etapa : p.etapa_atual;
  // o que já saiu (ou está saindo) não volta para a escolha: marcar de novo refaria o trabalho
  const feitos = new Set([...p.momentos, ...p.cortes].filter((x) => x.feito).map((x) => x.id));
  escolhas = {
    momentos: new Set((p.escolhas.momentos || []).filter((id) => !feitos.has(id))),
    cortes: new Set((p.escolhas.cortes || []).filter((id) => !feitos.has(id))),
  };
  // a etapa de motion mostra a escolha do estilo; sem a lista, o resto da etapa segue igual
  const estilos = ativa === "motion" ? await api("/api/estilos").catch(() => null) : null;
  const corpo = { momentos: blocoMomentos, cortes: blocoCortes, vertical: blocoVertical, motion: blocoMotion, entrega: blocoEntrega }[ativa](p, estilos);

  app.innerHTML = `
  <a class="voltar" href="#/">← todos os projetos</a>
  <div class="cabeca-projeto">
    <div>
      <h1 class="titulo">${esc(p.nome)}</h1>
      <div class="caminho">${p.video ? `🎬 ${esc(p.video)}` : p.link ? `🔗 baixando de ${esc(p.link)}` : "sem vídeo definido"}${p.run ? ` · run ${esc(p.run)}` : ""}</div>
    </div>
    <div class="cabeca-acoes">
      <button class="link apagar" data-acao="apagar">apagar projeto</button>
      <button class="botao claro pequeno" data-acao="abrir">Abrir pasta</button>
    </div>
  </div>
  ${trilhaEtapas(p, ativa)}
  <section class="atividade papel" id="atividade"><div class="mudo mono">carregando a atividade…</div></section>
  <section class="painel-etapa papel">${corpo}</section>`;

  app.querySelectorAll("[data-etapa]").forEach((b) => (b.onclick = () => (location.hash = `#/projeto/${slug}/${b.dataset.etapa}`)));
  app.querySelector('[data-acao="abrir"]').onclick = () => api(`/api/projetos/${slug}/abrir`, { method: "POST" }).catch((e) => aviso(esc(e.message)));
  app.querySelector('[data-acao="apagar"]').onclick = () => abrirApagarProjeto(p);
  ligarEscolhas(p, ativa);
  if (estilos) ligarEstilo(p, estilos);
  acompanharAtividade(slug, etapa, ativa);
}

// Vai para a Lixeira do computador, não some de vez: criou errado, é só apagar; apagou errado, dá para tirar de lá.
function abrirApagarProjeto(p) {
  const n = p.entregas.length;
  const itens = [
    n ? `Vão junto os <b>${n} ${n === 1 ? "clipe pronto" : "clipes prontos"}</b> da Entrega. Se quiser guardar, baixe antes.` : "",
    p.video_no_projeto ? "Vai junto o vídeo, que está dentro da pasta do projeto."
      : p.video ? `O vídeo original fica onde está: <span class="mono">${esc(p.video)}</span>` : "",
  ].filter(Boolean);
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `
  <div class="modal papel fita" role="dialog" aria-modal="true">
    <h2 class="titulo">Apagar este projeto?</h2>
    <p class="explica">A pasta de <b>${esc(p.nome)}</b> vai para a <b>Lixeira</b> do computador. Mudou de ideia? É só tirar de lá.</p>
    ${itens.length ? `<ul class="apagar-lista">${itens.map((i) => `<li>${i}</li>`).join("")}</ul>` : ""}
    ${p.atividade === "rodando" ? `<p class="erro">O TopClip está trabalhando neste projeto agora. Espere terminar (ou pare o Claude) e apague depois.</p>` : ""}
    <div class="erro" data-erro hidden></div>
    <div class="modal-acoes">
      <button type="button" class="botao claro" data-fechar>Cancelar</button>
      <button type="button" class="botao perigo" data-confirmar ${p.atividade === "rodando" ? "disabled" : ""}>Apagar projeto</button>
    </div>
  </div>`;
  document.body.appendChild(fundo);
  const fechar = () => fundo.remove();
  fundo.addEventListener("click", (e) => { if (e.target === fundo || e.target.closest("[data-fechar]")) fechar(); });
  const confirmar = fundo.querySelector("[data-confirmar]");
  confirmar.onclick = async () => {
    confirmar.disabled = true;
    confirmar.textContent = "Apagando…";
    try {
      await api(`/api/projetos/${encodeURIComponent(p.slug)}/apagar`, { method: "POST" });
      fechar();
      location.hash = "#/";
      aviso(`<b>Projeto apagado.</b> Está na Lixeira, se precisar.`);
    } catch (err) {
      const erro = fundo.querySelector("[data-erro]");
      erro.hidden = false;
      erro.textContent = err.message;
      confirmar.textContent = "Apagar projeto";
      confirmar.disabled = false;
    }
  };
}

const pedirAoClaude = (p) => `/topclip projetos/${p.slug}`;

function blocoMomentos(p) {
  if (!p.momentos.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Momentos</h2>
      <p class="explica">O Claude lê a transcrição inteira e separa os trechos que prendem quem cai ali sem contexto — com gancho, desenvolvimento e fechamento. Eles aparecem aqui para você escolher.</p></div></div>
    ${proximoPasso("comece pelo Claude:", pedirAoClaude(p))}`;
  }
  const comNota = p.momentos.some((m) => m.nota != null);
  const melhores = melhoresMomentos(p).length;
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.momentos.length} momentos encontrados</h2>
      <p class="explica">Marque <b>poucos — de 2 a ${MOMENTOS_RECOMENDADOS}</b>. Cada momento marcado vira corte, revisão e prévia: marcar demais deixa a próxima etapa bem mais lenta. O Claude só segue com os escolhidos.</p>
      ${comNota ? `<p class="explica">Em ordem de <b>nota estimada</b> — a mesma conta que decide no fim. Abaixo de ${num(p.gate)}, o corte tende a sair fraco.</p>` : ""}</div>
    <div style="display:flex;gap:16px">${comNota
      ? (melhores ? `<button class="link" data-melhores>marcar os ${melhores} melhores</button>` : "")
      : `<button class="link" data-todos="momentos">marcar todos</button>`}<button class="link" data-limpar="momentos">limpar</button></div>
  </div>
  <div class="lista">
    ${p.momentos.map((m) => `
      <article class="momento ${escolhas.momentos.has(m.id) ? "escolhido" : ""} ${m.feito || ""}" ${m.feito ? "" : `data-item="momentos" data-id="${esc(m.id)}" tabindex="0" role="checkbox" aria-checked="${escolhas.momentos.has(m.id)}"`}>
        <div class="momento-lado">
          <span class="tempo">${esc(m.inicio)} → ${esc(m.fim)}</span>
          ${m.nota != null ? `<span class="nota ${m.abaixo_do_gate.length ? "fraca" : ""}">${num(m.nota)}<small>/10</small><span class="nota-rotulo">nota estimada</span></span>` : ""}
        </div>
        <div>
          <p class="citacao">${esc(m.quote)}</p>
          <div class="tags">
            ${carimbo(m.feito, "tag")}
            ${m.abaixo_do_gate.length ? `<span class="tag risco">pode sair fraco</span>` : ""}
            ${m.trigger ? `<span class="tag forte">${esc(rotulo(m.trigger))}</span>` : ""}
            ${m.profile && rotulo(m.profile) !== rotulo(m.trigger) ? `<span class="tag">${esc(rotulo(m.profile))}</span>` : ""}
            ${m.confidence != null ? `<span class="tag">confiança ${Math.round(m.confidence * 100)}%</span>` : ""}
            ${m.risk_of_distortion && m.risk_of_distortion !== "baixo" ? `<span class="tag risco">risco de distorção: ${esc(rotulo(m.risk_of_distortion))}</span>` : ""}
          </div>
          ${m.abaixo_do_gate.length ? `<p class="detalhe"><b>Abaixo do mínimo:</b> ${m.abaixo_do_gate.map(esc).join(" · ")}</p>` : ""}
          ${m.context_needed ? `<p class="detalhe"><b>Contexto:</b> ${esc(m.context_needed)}</p>` : ""}
          ${m.payoff_candidate ? `<p class="detalhe"><b>Fecha com:</b> ${esc(m.payoff_candidate)}</p>` : ""}
        </div>
        <span class="marcar">${m.feito === "pronto" ? VISTO.replace('stroke="#2a292c"', 'stroke="#fff"') : VISTO}</span>
      </article>`).join("")}
  </div>
  <div data-depois-salvar hidden>${proximoPasso("agora diga ao Claude:", "escolhi no painel, pode seguir")}</div>`;
}

// Os que passariam no gate, melhor nota primeiro, no máximo o recomendado — fora os já feitos.
const melhoresMomentos = (p) =>
  p.momentos.filter((m) => m.nota != null && !m.abaixo_do_gate.length && !m.feito).slice(0, MOMENTOS_RECOMENDADOS);

// Corte (ou momento) que já saiu: o carimbo azul é o mesmo "feito" da trilha de etapas.
const CARIMBO = { pronto: "✓ pronto", andamento: "em produção" };
const carimbo = (feito, classe = "") => (feito ? `<span class="carimbo ${feito} ${classe}">${CARIMBO[feito]}</span>` : "");

function blocoCortes(p) {
  if (!p.cortes.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Cortes</h2>
      <p class="explica">Com os momentos escolhidos, o Claude crava o início e o fim de cada corte no timing das palavras e gera uma prévia para você assistir.</p></div></div>
    ${p.momentos.length ? proximoPasso("escolheu os momentos? diga ao Claude:", "escolhi no painel, pode seguir") : proximoPasso("comece pelo Claude:", pedirAoClaude(p))}`;
  }
  const prontos = p.cortes.filter((c) => c.feito === "pronto").length;
  const faltam = p.cortes.filter((c) => !c.feito).length;
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.cortes.length} cortes para assistir${prontos ? ` <span class="mudo">(${prontos} ${prontos === 1 ? "pronto" : "prontos"})</span>` : ""}</h2>
      <p class="explica">${prontos
        ? `Os marcados com <span class="carimbo pronto em-linha">✓ pronto</span> já estão na Entrega. Marque os próximos que viram vertical.`
        : "Assista e marque os que viram vertical. Os outros param aqui."}</p></div>
    ${faltam ? `<div style="display:flex;gap:16px"><button class="link" data-todos="cortes">${faltam < p.cortes.length ? "marcar os que faltam" : "marcar todos"}</button><button class="link" data-limpar="cortes">limpar</button></div>` : ""}
  </div>
  <div class="cortes">
    ${p.cortes.map((c) => `
      <article class="corte ${escolhas.cortes.has(c.id) ? "escolhido" : ""} ${c.feito || ""}" data-cartao="${esc(c.id)}">
        ${carimbo(c.feito)}
        ${c.preview ? `<video src="${c.preview}" controls preload="metadata" playsinline></video>`
                    : `<div class="sem-video">a prévia aparece aqui<br>quando o Claude cortar</div>`}
        <div class="corte-corpo">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
            <h4>${esc(c.titulo || c.id)}</h4>
            ${c.nota != null ? `<span class="nota ${c.abaixo_do_gate.length ? "fraca" : ""}">${num(c.nota)}<small>/10</small></span>` : ""}
          </div>
          <div class="tags">
            ${c.abaixo_do_gate.length ? `<span class="tag risco">pode sair fraco</span>` : ""}
            ${c.duracao ? `<span class="tag forte">${Math.round(c.duracao)}s</span>` : ""}
            ${c.perfil ? `<span class="tag">${esc(rotulo(c.perfil))}</span>` : ""}
            ${c.status ? `<span class="tag">${esc(rotulo(c.status))}</span>` : ""}
            ${c.falhas.map((f) => `<span class="tag risco">${esc(rotulo(f))}</span>`).join("")}
          </div>
          ${c.abaixo_do_gate.length ? `<p class="detalhe"><b>Abaixo do mínimo:</b> ${c.abaixo_do_gate.map(esc).join(" · ")}</p>` : ""}
          ${c.porque ? `<p class="detalhe"><b>Por que funciona:</b> ${esc(c.porque)}</p>` : ""}
          ${c.transcricao ? `<details class="detalhe"><summary>ler a fala do corte</summary><p>${esc(c.transcricao)}</p></details>` : ""}
          <div class="corte-rodape">
            ${c.feito === "pronto" ? `<a class="link" href="#/projeto/${esc(p.slug)}/entrega">já está na entrega →</a>`
              : c.feito ? `<span class="mudo mono">começado, ainda sem entrega</span>`
              : `<button class="alternar" data-item="cortes" data-id="${esc(c.id)}" role="checkbox" aria-checked="${escolhas.cortes.has(c.id)}">
              <span class="marcar">${VISTO}</span> vira vertical
            </button>`}
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
  ${proximoPasso("quer motion e legenda? diga ao Claude:", "coloca motion nos verticais aprovados")}
  <p class="explica" style="margin-top:14px"><a class="link" href="#/projeto/${esc(p.slug)}/motion">antes, escolha o estilo do motion →</a></p>`;
}

function blocoMotion(p, estilos) {
  if (!p.motion.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Motion</h2>
      <p class="explica">O Claude escolhe as frases que têm objeto, desenha os elementos em código e monta as cenas no estilo que você escolher aqui, cada uma presa à palavra exata da fala.</p></div></div>
    ${blocoEstilo(p, estilos)}
    ${proximoPasso("com os verticais prontos, peça:", "coloca motion nos verticais aprovados")}`;
  }
  return blocoEstilo(p, estilos) + p.motion.map((m) => `
    <div class="motion-bloco">
      <div class="secao-topo"><h2 class="subtitulo">${esc(m.nome)}</h2><span class="tags">${m.estilo ? `<span class="tag">estilo ${esc(m.estilo)}</span>` : ""}${m.master ? `<span class="tag forte">master pronto</span>` : `<span class="tag">em produção</span>`}</span></div>
      <div class="verticais">
        ${m.master ? `<div class="vertical"><video src="${m.master}" controls preload="metadata" playsinline></video><div class="rotulo">master final</div></div>`
          : m.rascunho ? `<div class="vertical"><video src="${m.rascunho}" controls preload="metadata" playsinline></video><div class="rotulo">rascunho (revisão)</div></div>` : ""}
        ${m.quadros.map((q) => `<div class="vertical"><img src="${q}" alt="" loading="lazy"><div class="rotulo">${esc(decodeURIComponent(q.split("/").pop()))}</div></div>`).join("")}
      </div>
    </div>`).join("");
}

// ------------------------------------------------------------------ estilo do motion (no projeto)
// 3 estilos à vista — o recomendado pelo Claude, o escolhido e o seu padrão vêm primeiro — e
// o resto em "ver todos". Clicar já salva em escolhas.json, como "estilo": {id, variacao}.
let estiloTodosAbertos = false;
let estiloDobraAberta = false;

function blocoEstilo(p, lista) {
  const validos = lista ? lista.estilos.filter((e) => e.valido) : [];
  if (!validos.length || !p.estilo) return "";
  const est = p.estilo;
  const porId = Object.fromEntries(validos.map((e) => [e.id, e]));
  const rec = est.recomendado && porId[est.recomendado.id];
  const ids = [...new Set([rec && rec.id, est.escolhido && est.escolhido.id, est.padrao.estilo, ...validos.map((e) => e.id)])]
    .filter((id) => porId[id]);
  const nomeVale = nomeEstilo(porId[est.vale.id], est.vale.variacao) || est.nome;
  const origem = est.escolhido ? "escolhido para este projeto" : est.padrao.salvo ? "o seu padrão" : "o padrão do TopClip";

  const cartao = (id) => {
    const e = porId[id];
    const vale = est.vale.id === id;
    const vid = vale ? est.vale.variacao : (rec && rec.id === id && est.recomendado.variacao) || (e.variacoes[0] || {}).id;
    const v = e.variacoes.find((x) => x.id === vid) || e.variacoes[0] || {};
    return `
    <article class="escolha-estilo ${vale ? "escolhido" : ""}" data-escolher="${esc(id)}" data-variacao="${esc(v.id || "")}" tabindex="0" role="radio" aria-checked="${vale}">
      ${rec && rec.id === id ? `<span class="selo-recomendado">recomendado</span>` : ""}
      <div class="escolha-capa">${v.capa ? `<img src="${v.capa}" alt="Prévia do estilo ${esc(e.nome)}" loading="lazy">` : ""}</div>
      <div class="escolha-corpo">
        <h4>${esc(e.nome)}</h4>
        <div class="mudo">${esc(energiaTxt(e.energia))}${e.bom_para.length ? ` · ${esc(e.bom_para.slice(0, 2).join(", "))}` : ""}</div>
        ${e.variacoes.length > 1 ? `<div class="escolha-variacoes">${e.variacoes.map((x) =>
          `<button type="button" class="chip ${vale && x.id === est.vale.variacao ? "ativo" : ""}" data-variacao="${esc(x.id)}" data-capa="${esc(x.capa || "")}">${bolinha(x)}${esc(x.nome)}</button>`).join("")}</div>` : ""}
        <span class="escolha-status">${vale ? "✓ vai sair neste" : "usar este"}</span>
      </div>
    </article>`;
  };
  const primeiros = ids.slice(0, 3), resto = ids.slice(3);
  const conteudo = `
    <p class="explica">Vale para os clipes que o Claude ainda vai fazer. Agora: <b>${esc(nomeVale)}</b> — ${origem}.
      ${est.escolhido ? `<button class="link" data-estilo-padrao>voltar ao meu padrão</button>` : ""}</p>
    ${rec && est.recomendado.porque ? `<p class="explica"><span class="mao">o Claude recomenda o estilo ${esc(rec.nome)}:</span> ${esc(est.recomendado.porque)}</p>` : ""}
    <div class="escolha-estilos">${primeiros.map(cartao).join("")}</div>
    ${resto.length ? `<div class="escolha-estilos" data-resto ${estiloTodosAbertos ? "" : "hidden"}>${resto.map(cartao).join("")}</div>` : ""}
    <div class="estilo-motion-acoes">
      ${resto.length ? `<button class="link" data-ver-todos>${estiloTodosAbertos ? "mostrar só 3" : `ver todos os estilos (${ids.length})`}</button>` : ""}
      <a class="link" href="#/biblioteca">comparar as peças de cada estilo na biblioteca</a>
    </div>`;
  // com clipe já no motion, a escolha vale para os próximos: fica dobrada para não tomar a tela
  if (p.motion.length) {
    return `<details class="estilo-motion dobra" id="estilo-motion" ${estiloDobraAberta ? "open" : ""}>
      <summary><span class="subtitulo">Estilo dos próximos clipes</span> <b>${esc(nomeVale)}</b> <span class="link">trocar</span></summary>${conteudo}</details>`;
  }
  return `<section class="estilo-motion" id="estilo-motion"><h3 class="subtitulo">Estilo do motion</h3>${conteudo}</section>`;
}

function ligarEstilo(p, lista) {
  const caixa = document.getElementById("estilo-motion");
  if (!caixa) return;
  const redesenhar = () => { caixa.outerHTML = blocoEstilo(p, lista); ligarEstilo(p, lista); };
  const salvar = async (estilo) => {
    const agora = p.estilo.escolhido;
    if (estilo && agora && agora.id === estilo.id && agora.variacao === estilo.variacao) return;
    try {
      const r = await api(`/api/projetos/${encodeURIComponent(p.slug)}/escolhas`, { method: "POST", body: { estilo } });
      p.estilo.escolhido = r.estilo || null;
      p.estilo.vale = r.estilo || { id: p.estilo.padrao.estilo, variacao: p.estilo.padrao.variacao };
      redesenhar();
      const e = lista.estilos.find((x) => x.id === p.estilo.vale.id);
      aviso(r.estilo ? `<b>Estilo salvo: ${esc(nomeEstilo(e, p.estilo.vale.variacao))}.</b> Agora diga ao Claude para seguir com o motion.`
        : `<b>Pronto:</b> o motion sai no seu padrão.`);
    } catch (err) {
      aviso(`<b>Não salvou:</b> ${esc(err.message)}`);
    }
  };
  caixa.querySelectorAll("[data-escolher]").forEach((c) => {
    const img = c.querySelector(".escolha-capa img");
    const capa = img && img.getAttribute("src");
    c.addEventListener("click", (ev) => {
      const chip = ev.target.closest("button.chip");
      salvar({ id: c.dataset.escolher, variacao: chip ? chip.dataset.variacao : c.dataset.variacao });
    });
    c.addEventListener("keydown", (ev) => {
      if (ev.target === c && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); salvar({ id: c.dataset.escolher, variacao: c.dataset.variacao }); }
    });
    // passar o mouse numa variação mostra a capa dela antes de escolher
    c.querySelectorAll("button.chip").forEach((b) => {
      b.addEventListener("mouseenter", () => { if (img && b.dataset.capa) img.src = b.dataset.capa; });
      b.addEventListener("mouseleave", () => { if (img) img.src = capa; });
    });
  });
  caixa.querySelector("[data-estilo-padrao]")?.addEventListener("click", () => salvar(null));
  caixa.querySelector("[data-ver-todos]")?.addEventListener("click", () => { estiloTodosAbertos = !estiloTodosAbertos; redesenhar(); });
  if (caixa.tagName === "DETAILS") caixa.addEventListener("toggle", () => (estiloDobraAberta = caixa.open));
}

function blocoEntrega(p) {
  if (!p.entregas.length) {
    return `
    <div class="secao-topo"><div><h2 class="subtitulo">Entrega</h2>
      <p class="explica">Os masters conferidos (duração, cadência e áudio idêntico ao original) chegam aqui, prontos para postar.</p></div></div>
    ${proximoPasso("quando o motion estiver pronto:", "pode entregar os clipes")}`;
  }
  const faltam = p.cortes.filter((c) => !c.feito).length;
  return `
  <div class="secao-topo"><div><h2 class="subtitulo">${p.entregas.length} clipes prontos para postar</h2>
    <p class="explica">Baixe ou abra a pasta. Bom post! 🎉</p>
    ${faltam ? `<p class="explica">Ainda tem ${faltam} ${faltam === 1 ? "corte que você não fez" : "cortes que você não fez"}. <a class="link" href="#/projeto/${esc(p.slug)}/cortes">escolher os próximos</a></p>` : ""}</div>
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
    const demais = tipo === "momentos" && n > MOMENTOS_RECOMENDADOS;
    barra.querySelector(".conta").innerHTML = `<b>${n}</b> ${n === 1 ? nomeItem[0] : nomeItem[1]}`
      + (demais ? `<span class="alerta">acima de ${MOMENTOS_RECOMENDADOS}, os cortes demoram bem mais</span>` : "");
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
    app.querySelectorAll(`[data-item="${tipo}"]`).forEach((el) => conjunto.add(el.dataset.id)); mudou = true; escolhaNaoSalva = true; atualizar();
  });
  app.querySelector("[data-melhores]")?.addEventListener("click", () => {
    conjunto.clear(); melhoresMomentos(p).forEach((m) => conjunto.add(m.id)); mudou = true; escolhaNaoSalva = true; atualizar();
  });
  app.querySelector(`[data-limpar="${tipo}"]`)?.addEventListener("click", () => { conjunto.clear(); mudou = true; escolhaNaoSalva = true; atualizar(); });

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
let logDeTodas = false;        // o log mostra só a etapa aberta; "todas as etapas" junta tudo

const barraPct = (pct, cls = "ativ-barra") =>
  pct != null ? `<span class="${cls}"><i style="width:${Math.max(0, Math.min(100, pct))}%"></i></span>` : "";

// O passo a passo da etapa aberta: barra de quanto já foi e cada passo marcado.
function blocoProgresso(nome, e) {
  if (!e) return "";
  const passo = (x) => `<li class="${x.feito ? "feito" : x.pct != null ? "andando" : ""}"><span class="marca">${x.feito ? VISTO_BRANCO : ""}</span>${esc(x.nome)}`
    + `${!x.feito && (x.detalhe || x.pct != null) ? ` <small>${esc([x.detalhe, x.pct != null ? `${x.pct}%` : ""].filter(Boolean).join(" · "))}</small>` : ""}</li>`;
  // o passo que está andando (tem %) vem antes do primeiro que falta
  const daVez = (lista) => lista.find((x) => !x.feito && x.pct != null) || lista.find((x) => !x.feito);
  const proximo = daVez([...(e.passos || []), ...(e.itens || []).flatMap((i) => i.passos)]);
  const clipes = e.itens && e.itens.length ? `
    <ul class="prog-clipes">${e.itens.map((i) => {
      const prox = daVez(i.passos);
      return `<li><b>${esc(i.nome)}</b>${barraPct(i.pct, "prog-barra")}<span class="prog-pct-mini">${i.pct}%</span>
        <small>${prox ? `agora: ${esc(prox.nome)}${prox.pct != null ? ` · ${prox.pct}%` : ""}` : "master pronto"}</small></li>`;
    }).join("")}</ul>` : "";
  const vazio = e.itens && !e.itens.length ? `<p class="ativ-vazio">Cada clipe aprovado vira um projeto de motion — o avanço de cada um aparece aqui.</p>` : "";
  return `
    <div class="prog-etapa">
      <div class="prog-cabeca">
        <span class="prog-nome">${esc(nome)}</span><span class="prog-pct">${e.pct}%</span>
        <span class="prog-agora">${e.estado === "feito" ? "etapa pronta" : !proximo ? ""
          : proximo.pct != null ? `agora: ${esc(proximo.nome)} · ${proximo.pct}%` : `próximo passo: ${esc(proximo.nome)}`}</span>
      </div>
      ${barraPct(e.pct, "prog-barra")}
      ${e.passos && e.passos.length ? `<ol class="prog-passos">${e.passos.map(passo).join("")}</ol>` : ""}
      ${clipes}${vazio}
    </div>`;
}

function desenharAtividade(slug, a, ativa) {
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
    // cada comando aberto com a barra dele (dois motions em paralelo: duas barras)
    const todos = a.rodando_todos && a.rodando_todos.length ? a.rodando_todos : [a.rodando];
    agora = todos.map((r) => `<div class="ativ-cmd">${esc(r.msg)}${r.progresso
      ? `<small class="ativ-progresso">${barraPct(r.pct)}${esc(r.progresso)}</small>` : ""}</div>`).join("")
      + `<small>começou ${ha(todos[0].ha_s)} · o painel atualiza sozinho</small>`;
  }
  else if (a.estado === "ativo") agora = `${esc(ultimo.msg)}<small>última notícia ${ha(a.ultima_ha_s)}</small>`;
  else if (a.estado === "sua_vez") agora = `${esc(a.sua_vez.msg)} <button class="link" data-ir-etapa="${a.sua_vez.etapa}">escolher agora</button>`;
  else if (a.estado === "avisar_claude") agora = `Você já escolheu. Agora diga ao Claude: ${comando("escolhi no painel, pode seguir")}`;
  else if (a.estado === "esperando_claude") agora = `Nada começou ainda. Cole no Claude Code, aberto na pasta do TopClip: ${comando(`/topclip projetos/${slug}`)}`;
  else agora = `${esc(ultimo ? ultimo.msg : "")}<small>última notícia ${ha(a.ultima_ha_s)} · se o Claude ainda estiver pensando, a próxima etapa aparece aqui sozinha</small>`;

  const nomeEtapa = (ETAPAS.find((e) => e.id === ativa) || ETAPAS[0]).nome;
  const daEtapa = logDeTodas ? a.eventos : a.eventos.filter((e) => e.etapa === ativa);
  const lista = atividadeAberta ? daEtapa : daEtapa.slice(0, 6);
  caixa.innerHTML = `
    <div class="ativ-topo">
      <span class="ativ-estado ${cls}"><i></i>${rotulo}</span>
      <div class="ativ-agora">${agora}</div>
    </div>
    ${blocoProgresso(nomeEtapa, (a.etapas || {})[ativa])}
    <div class="ativ-log-cabeca">
      <span>${logDeTodas ? "log de todas as etapas" : `log da etapa ${esc(nomeEtapa.toLowerCase())}`} (${daEtapa.length})</span>
      <span class="ativ-log-acoes">
        <button class="link" data-log-todas>${logDeTodas ? `só ${esc(nomeEtapa.toLowerCase())}` : "todas as etapas"}</button>
        ${daEtapa.length > 6 ? `<button class="link" data-ativ-alternar>${atividadeAberta ? "ver menos" : `ver tudo`}</button>` : ""}
      </span>
    </div>
    ${daEtapa.length ? `<ul class="ativ-lista">${lista.map((e) => `
      <li><time datetime="${esc(e.t)}">${horario(e.t)}</time><span class="ic ${e.tipo}">${ICONE_EVENTO[e.tipo] || "•"}</span><span>${esc(e.msg)}${logDeTodas && e.etapa ? ` <small class="ativ-etapa">${esc(e.etapa)}</small>` : ""}</span></li>`).join("")}</ul>`
      : `<p class="ativ-vazio">${a.eventos.length ? "Nada nesta etapa ainda — o que o TopClip fizer nela aparece aqui, ao vivo." : "O que o TopClip fizer neste projeto aparece aqui, ao vivo."}</p>`}`;
  caixa.querySelector("[data-ativ-alternar]")?.addEventListener("click", () => { atividadeAberta = !atividadeAberta; desenharAtividade(slug, a, ativa); });
  caixa.querySelector("[data-log-todas]")?.addEventListener("click", () => { logDeTodas = !logDeTodas; desenharAtividade(slug, a, ativa); });
  caixa.querySelector("[data-ir-etapa]")?.addEventListener("click", (e) => (location.hash = `#/projeto/${slug}/${e.target.dataset.irEtapa}`));
}

function acompanharAtividade(slug, etapa, ativa) {
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
    atualizarTrilha(a.etapas);
    const chave = JSON.stringify([a.estado, a.eventos.slice(0, 12), a.sua_vez, a.rodando_todos, a.etapas, atividadeAberta, logDeTodas]);
    if (chave !== chaveAnterior || ["rodando", "ativo", "parado"].includes(a.estado)) {
      desenharAtividade(slug, a, ativa);
      chaveAnterior = chave;
    }
  };
  passo();
  relogio = setInterval(passo, 3000);
}

// ------------------------------------------------------------------ biblioteca
// Estilos de motion, as peças que eles vestem, a marca e os objetos desenhados. O visual de
// cada estilo só aparece dentro das prévias (imagens de `./topclip estilo previa`): o painel
// continua no Papel.
const ENERGIA = {
  calmo: ["calmo", "movimento lento e suave"],
  editorial: ["editorial", "ritmo de revista: entra rápido e assenta"],
  energico: ["enérgico", "rápido e com impacto"],
};
const PECAS = {
  contador: ["Contador", "o número conta até o valor dito"],
  marca_texto: ["Marca-texto", "destaca a palavra na frase"],
  troca_palavra: ["Troca de palavra", "a palavra muda no mesmo lugar"],
  desfoque: ["Desfoque", "o texto entra saindo do borrão"],
  cascata: ["Lista", "os itens entram um por um"],
  antes_depois: ["Antes e depois", "duas imagens e um divisor"],
  cartao: ["Cartão", "título e texto numa etiqueta"],
  moldura: ["Moldura", "filete que se desenha em volta da cena"],
  brilho: ["Brilho", "um reflexo de luz passa pelo título"],
  lottie: ["Ícone animado", "animação pronta, nas cores do estilo"],
};
// o que cada espaço do estilo pega da marca (MARCA_PARA_TOKEN do lib/estilo.py)
const SLOTS = { "cor.acento": "a cor primária", "cor.apoio": "a cor secundária", "cor.texto": "a cor do texto",
  "fonte.titulo": "a fonte do título", "fonte.apoio": "a fonte do texto", logo: "o logo" };
const hex = (c, reserva = "#d9d4c8") => (/^#[0-9a-f]{6}$/i.test(c || "") ? c : reserva);
const energiaTxt = (e) => (ENERGIA[e] || [rotulo(e)])[0];
const listaFalada = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} e ${xs[xs.length - 1]}`);
const marcaNoEstilo = (e) => listaFalada(e.slots_da_marca.map((s) => SLOTS[s]).filter(Boolean));
const nomeEstilo = (e, vid) => (e ? [e.nome, (e.variacoes.find((v) => v.id === vid) || {}).nome].filter(Boolean).join(" · ") : "");

// a bolinha de uma variação: o fundo e o acento dela
const bolinha = (v, ativa = false) =>
  `<span class="bolinha${ativa ? " ativa" : ""}" style="--fundo:${hex(v.fundo)};--acento:${hex(v.acento)}" title="${esc(v.nome || "")}"></span>`;

let estiloDasPecas = null;     // o estilo cujas peças a Biblioteca mostra — troca com um clique

function cartaoEstilo(e, padrao, selecionado) {
  const ehPadrao = padrao.estilo === e.id;
  const capa = (ehPadrao && (e.variacoes.find((v) => v.id === padrao.variacao) || {}).capa) || e.capa;
  return `
  <article class="estilo-cartao papel ${selecionado ? "selecionado" : ""}" data-estilo="${esc(e.id)}" tabindex="0" role="button" aria-pressed="${selecionado}">
    ${ehPadrao ? `<span class="selo-padrao">seu padrão</span>` : ""}
    <div class="estilo-capa">${capa ? `<img src="${capa}" alt="Prévia do estilo ${esc(e.nome)}" loading="lazy">` : `<span>sem prévia ainda</span>`}</div>
    <div class="estilo-nome"><h3>${esc(e.nome)}</h3>${e.dono === "seu" ? `<span class="selo-seu">seu</span>` : ""}</div>
    <div class="estilo-energia"><b>${esc(energiaTxt(e.energia))}</b>${e.bom_para.length ? ` · bom para ${esc(e.bom_para.slice(0, 3).join(", "))}` : ""}</div>
    ${e.valido ? "" : `<p class="estilo-erro">Este estilo tem um problema e não pode ser usado agora.</p>`}
    <div class="estilo-rodape">
      <span class="bolinhas" title="${e.variacoes.length} ${e.variacoes.length === 1 ? "variação" : "variações"}">${e.variacoes.map((v) => bolinha(v, ehPadrao && v.id === padrao.variacao)).join("")}</span>
      <a class="link" href="#/biblioteca/estilo/${esc(e.id)}">ver o estilo</a>
    </div>
  </article>`;
}

// As peças de um estilo, sempre na mesma ordem: trocar de estilo troca só as imagens.
function gradePecas(e, ordem = e.pecas.map((p) => p.id)) {
  if (!e.pecas.length) {
    return `<div class="vazio-pecas">O ${esc(e.nome)} não usa estas peças: tudo nele, texto e objeto, é desenhado à mão no kit do papel, uma cena para cada fala.</div>`;
  }
  const dele = Object.fromEntries(e.pecas.map((p) => [p.id, p]));
  return `<div class="pecas">${ordem.map((id) => {
    const p = dele[id];
    const [nome, txt] = PECAS[id] || [rotulo(id), ""];
    return `<figure class="peca ${p ? "" : "ausente"}">
      <div class="peca-quadro">${p && p.imagem ? `<img src="${p.imagem}" alt="${esc(nome)} no estilo ${esc(e.nome)}" loading="lazy">`
        : `<span>${p ? "sem prévia ainda" : `o estilo ${esc(e.nome)} não usa`}</span>`}</div>
      <figcaption><b>${esc(nome)}</b>${esc(txt)}</figcaption>
    </figure>`;
  }).join("")}</div>`;
}

function prateleiraPecas(lista, sel) {
  // a ordem de PECAS, e no fim as que o painel ainda não conhece: igual em todo estilo
  const existem = new Set(lista.flatMap((e) => e.pecas.map((p) => p.id)));
  const ordem = [...new Set([...Object.keys(PECAS), ...existem])].filter((id) => existem.has(id));
  return `
  <div class="secao-topo"><div><h2 class="subtitulo">Peças <span class="mudo">no estilo ${esc(sel.nome)}</span></h2>
    <p class="explica">As mesmas animações vestem a cara de cada estilo. Troque o estilo e veja.</p></div></div>
  <div class="chips" role="tablist" aria-label="Ver as peças no estilo">${lista.map((e) =>
    `<button class="chip ${e.id === sel.id ? "ativo" : ""}" data-estilo="${esc(e.id)}" role="tab" aria-selected="${e.id === sel.id}">${bolinha(e.variacoes[0] || {})}${esc(e.nome)}</button>`).join("")}</div>
  ${gradePecas(sel, ordem)}`;
}

function cartaoMarca(m) {
  const c = m.marca.cores;
  return `
  <a class="marca-cartao papel fita" href="#/biblioteca/marca">
    <span class="marca-amostras">${["primaria", "secundaria", "texto"].map((k) =>
      c[k] ? `<span style="background:${hex(c[k])}"></span>` : `<span class="vazia"></span>`).join("")}</span>
    ${m.logo ? `<img class="marca-logo" src="${m.logo}" alt="seu logo">` : ""}
    <span>
      <b>${m.existe && m.marca.nome ? esc(m.marca.nome) : "Minha marca"}</b>
      <span>${m.existe ? "Suas cores, fontes e logo. Entram só onde cada estilo deixa." : "Coloque suas cores, fontes e logo. Eles entram nos estilos que aceitam marca."}</span>
      <span class="link">${m.existe ? "editar minha marca" : "configurar minha marca"} →</span>
    </span>
  </a>`;
}

async function telaBiblioteca(partes = []) {
  if (partes[1] === "estilo" && partes[2]) return telaEstilo(partes[2]);
  if (partes[1] === "marca") return telaMarca();
  const [{ estilos, padrao }, { assets }, m] = await Promise.all([api("/api/estilos"), api("/api/biblioteca"), api("/api/marca")]);
  // as peças começam no estilo escolhido antes, senão no seu padrão, senão no primeiro que tem peças
  let sel = estilos.find((e) => e.id === estiloDasPecas) || estilos.find((e) => e.id === padrao.estilo && e.pecas.length)
    || estilos.find((e) => e.pecas.length) || estilos[0];
  const oficiais = estilos.filter((e) => e.dono === "oficial");
  const seus = estilos.filter((e) => e.dono !== "oficial");
  const grade = (lista) => `<div class="estilos">${lista.map((e) => cartaoEstilo(e, padrao, sel && e.id === sel.id)).join("")}</div>`;
  app.innerHTML = `
  <section style="margin-bottom:40px">
    <h1 class="manchete">A <span class="marca">biblioteca</span></h1>
    <p class="lead">Os estilos do motion, as peças que eles animam, a sua marca e tudo que já foi desenhado. Cada projeto escolhe o estilo na etapa Motion.</p>
  </section>

  <section class="prateleira">
    <div class="secao-topo"><div><h2 class="subtitulo">Estilos</h2>
      <p class="explica">Clique num estilo para ver as peças nele. O seu padrão vale quando o projeto não escolhe outro.</p></div></div>
    ${estilos.length ? grade(oficiais) : `<div class="vazio papel"><p class="lead" style="margin:0 auto">Nenhum estilo encontrado.</p></div>`}
    <h3 class="prateleira-sub">Seus estilos</h3>
    ${seus.length ? grade(seus) : `<p class="explica">Peça ao Claude <i>“cria o meu estilo”</i>: ele tira a paleta dos seus posts, mostra quatro caminhos num quadro do seu vídeo e monta o estilo com a sua cara. Ou abra um estilo acima e use <i>Fazer o meu a partir deste</i>.</p>`}
    <label class="importar-estilo papel" tabindex="0">
      <input type="file" accept=".topclip-estilo" hidden>
      <b>Recebeu um estilo?</b> Arraste o arquivo <code>.topclip-estilo</code> aqui ou <span class="link">escolha no computador</span>.
    </label>
  </section>

  ${sel ? `<section class="prateleira papel painel-etapa" id="pecas">${prateleiraPecas(estilos, sel)}</section>` : ""}

  <section class="prateleira">
    <div class="secao-topo"><h2 class="subtitulo">Minha marca</h2></div>
    ${cartaoMarca(m)}
  </section>

  <section class="prateleira">
    <div class="secao-topo"><div><h2 class="subtitulo">Objetos desenhados</h2>
      <p class="explica">Todo objeto desenhado num vídeo fica aqui para o próximo. Quanto mais você usa, mais coisa já vem pronta.</p></div></div>
    ${assets.length ? `<div class="assets">${assets.map((a, i) => `
      <figure class="asset papel ${i % 3 === 1 ? "fita" : ""}" style="margin:0">
        <div class="vitrine ${a.arquivo.startsWith("BG_") ? "fundo" : ""}"><img src="${a.url}" alt="${esc(a.objeto || a.arquivo)}" loading="lazy"></div>
        <h4>${esc(a.arquivo)}${a.dono === "seu" ? ` <span class="selo-seu">seu</span>` : ""}</h4>
        <p>${esc(a.objeto || "")}</p>
      </figure>`).join("")}</div>`
    : `<div class="vazio papel"><h3 class="titulo">Nada desenhado ainda</h3><p class="lead" style="margin:14px auto">O primeiro vídeo com motion já começa a encher.</p></div>`}
  </section>`;

  const trocar = (id) => {
    const e = estilos.find((x) => x.id === id);
    if (!e || !sel || e.id === sel.id) return;
    sel = e;
    estiloDasPecas = id;
    app.querySelectorAll(".estilo-cartao").forEach((c) => {
      const sim = c.dataset.estilo === id;
      c.classList.toggle("selecionado", sim);
      c.setAttribute("aria-pressed", sim);
    });
    document.getElementById("pecas").innerHTML = prateleiraPecas(estilos, sel);
    ligarChips();
  };
  ligarImportar(app.querySelector(".importar-estilo"));
  const ligarChips = () => document.querySelectorAll("#pecas .chip").forEach((b) => (b.onclick = () => trocar(b.dataset.estilo)));
  app.querySelectorAll(".estilo-cartao").forEach((c) => {
    c.addEventListener("click", (ev) => { if (!ev.target.closest("a")) trocar(c.dataset.estilo); });
    c.addEventListener("keydown", (ev) => {
      if (ev.target === c && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); trocar(c.dataset.estilo); }
    });
  });
  ligarChips();
}

// ------------------------------------------------------------------ detalhe do estilo
async function telaEstilo(id) {
  const e = await api(`/api/estilos/${encodeURIComponent(id)}`);
  const { padrao } = e;
  const [energia, energiaExplica] = ENERGIA[e.energia] || [rotulo(e.energia), ""];
  const veioDoProjeto = rotaAnterior && rotaAnterior.startsWith("#/projeto/");
  const rascunho = e.dono === "seu" && String(e.versao || "").startsWith("0.");
  app.innerHTML = `
  <a class="voltar" href="${veioDoProjeto ? esc(rotaAnterior) : "#/biblioteca"}">← ${veioDoProjeto ? "voltar ao projeto" : "biblioteca"}</a>
  <div class="cabeca-projeto">
    <div>
      <h1 class="titulo">${esc(e.nome)}${e.dono === "seu" ? ` <span class="selo-seu">${e.origem === "comunidade" ? "importado" : "seu"}</span>` : ""}${rascunho ? ` <span class="selo-rascunho">rascunho</span>` : ""}</h1>
      ${e.descricao ? `<p class="lead">${esc(e.descricao)}</p>` : ""}
      ${rascunho ? `<p class="explica">Ainda é rascunho: peça ao Claude <i>“aprova o estilo ${esc(e.nome)}”</i> para gerar a galeria e fechar a versão 1.0.</p>` : ""}
    </div>
  </div>
  <div class="acoes-estilo">
    <button class="botao claro pequeno" data-acao="remixar">Fazer o meu a partir deste</button>
    ${e.valido ? `<a class="botao claro pequeno" href="/api/estilos/${encodeURIComponent(e.id)}/exportar" download>Exportar para compartilhar</a>` : ""}
    ${e.dono === "seu" ? `<button class="botao pequeno perigo" data-acao="apagar">Apagar este estilo</button>` : ""}
  </div>
  <form class="remixar papel" hidden>
    <label>Nome do seu estilo <input name="nome" maxlength="60" placeholder="${esc(e.nome)} da minha marca" required></label>
    <button class="botao pequeno" type="submit">Criar</button>
    <p class="explica">Vira uma cópia sua, em rascunho. Depois peça ao Claude para trocar as cores, as fontes ou a energia — por exemplo, <i>“deixa o meu estilo com o laranja da minha marca”</i>.</p>
  </form>
  <div class="estilo-fatos">
    <div><span class="rotulo-fato">energia</span><b>${esc(energia)}</b><small>${esc(energiaExplica)}</small></div>
    <div><span class="rotulo-fato">bom para</span><b>${esc(e.bom_para.join(", ") || "—")}</b></div>
    <div><span class="rotulo-fato">sua marca</span>
      <b>${e.slots_da_marca.length ? "entra" : "não entra"}</b>
      <small>${e.slots_da_marca.length ? `usa ${esc(marcaNoEstilo(e))}.` : "As cores e as fontes deste estilo são fixas."}
        <a class="link" href="#/biblioteca/marca">minha marca</a></small></div>
  </div>
  ${e.valido ? "" : `<div class="estilo-problema papel"><b>Este estilo tem um problema e não pode ser usado agora.</b>
    <ul>${e.erros.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`}

  <section class="papel painel-etapa prateleira">
    <div class="secao-topo"><div><h2 class="subtitulo">${e.variacoes.length === 1 ? "Variação" : `${e.variacoes.length} variações`}</h2>
      <p class="explica">O mesmo jeito de mexer, com outra paleta. A que você usar como padrão vale para os vídeos novos, até o projeto escolher outra.</p></div></div>
    <div class="variacoes-grade">${e.variacoes.map((v) => {
      const ehPadrao = padrao.estilo === e.id && padrao.variacao === v.id;
      return `<figure class="variacao-cartao ${ehPadrao ? "padrao" : ""}">
        <div class="variacao-capa">${v.capa ? `<img src="${v.capa}" alt="${esc(nomeEstilo(e, v.id))}">` : `<span>sem prévia ainda</span>`}</div>
        <figcaption>${bolinha(v)}<b>${esc(v.nome)}</b>
          ${ehPadrao ? `<span class="selo-padrao">✓ seu padrão</span>`
            : e.valido ? `<button class="botao claro pequeno" data-padrao="${esc(v.id)}">Usar como padrão</button>` : ""}</figcaption>
      </figure>`;
    }).join("")}</div>
    ${e.demo ? `<video class="estilo-demo" src="${e.demo}" controls muted loop playsinline preload="metadata"></video>` : ""}
  </section>

  ${e.objetos ? `<section class="papel painel-etapa prateleira">
    <div class="secao-topo"><div><h2 class="subtitulo">O desenho</h2>
      <p class="explica">Os objetos que o Claude desenha nas cenas, no traço do ${esc(e.nome)}. Cada fala ganha o seu, preso à palavra: o mesmo relógio sai diferente em cada estilo.</p></div></div>
    <img class="estilo-objetos" src="${e.objetos}" alt="Os objetos desenhados no estilo ${esc(e.nome)}" loading="lazy">
  </section>` : ""}

  <section class="papel painel-etapa prateleira">
    <div class="secao-topo"><div><h2 class="subtitulo">Peças</h2>
      <p class="explica">As animações de texto e de dado que o Claude junta ao desenho, presas à palavra da fala.</p></div></div>
    ${gradePecas(e)}
  </section>`;

  app.querySelectorAll("[data-padrao]").forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await api("/api/preferencias", { method: "POST", body: { estilo: e.id, variacao: b.dataset.padrao } });
      await telaEstilo(id);
      aviso(`<b>Pronto:</b> os vídeos novos saem no ${esc(nomeEstilo(e, r.variacao))}, a menos que o projeto escolha outro.`);
    } catch (err) {
      b.disabled = false;
      aviso(`<b>Não salvou:</b> ${esc(err.message)}`);
    }
  }));

  const form = app.querySelector("form.remixar");
  app.querySelector('[data-acao="remixar"]').onclick = () => {
    form.hidden = !form.hidden;
    if (!form.hidden) form.querySelector("input").focus();
  };
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const botao = form.querySelector("button");
    botao.disabled = true;
    try {
      const novo = await api("/api/estilos/remixar", { method: "POST", body: { base: e.id, nome: form.nome.value } });
      location.hash = `#/biblioteca/estilo/${encodeURIComponent(novo.id)}`;
      aviso(`<b>Criado:</b> ${esc(novo.nome)} é seu. Peça ao Claude para ajustar as cores, as fontes ou a energia.`);
    } catch (err) {
      botao.disabled = false;
      aviso(`<b>Não criou:</b> ${esc(err.message)}`);
    }
  };
  const apagar = app.querySelector('[data-acao="apagar"]');
  if (apagar) apagar.onclick = async () => {
    if (!confirm(`Apagar o estilo ${e.nome}? Os vídeos que já usaram ele continuam como estão.`)) return;
    apagar.disabled = true;
    try {
      await api(`/api/estilos/${encodeURIComponent(e.id)}/apagar`, { method: "POST", body: {} });
      location.hash = "#/biblioteca";
      aviso(`<b>Apagado:</b> ${esc(e.nome)}.`);
    } catch (err) {
      apagar.disabled = false;
      aviso(`<b>Não apagou:</b> ${esc(err.message)}`);
    }
  };
}

// ------------------------------------------------------------------ importar um estilo
// O arquivo .topclip-estilo vai em base64 no JSON (o servidor é só biblioteca padrão).
function lerComoBase64(arquivo) {
  return new Promise((ok, falha) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => falha(new Error("não consegui ler o arquivo"));
    r.readAsDataURL(arquivo);
  });
}

async function importarEstilo(arquivo) {
  if (!/\.topclip-estilo$/i.test(arquivo.name)) {
    aviso("<b>Não é um estilo:</b> o arquivo precisa terminar em .topclip-estilo.");
    return;
  }
  const conteudo = await lerComoBase64(arquivo);
  let corpo = { nome: arquivo.name, conteudo };
  for (;;) {
    try {
      const e = await api("/api/estilos/importar", { method: "POST", body: corpo });
      location.hash = `#/biblioteca/estilo/${encodeURIComponent(e.id)}`;
      aviso(`<b>Importado:</b> ${esc(e.nome)} já está nos seus estilos.`);
      return;
    } catch (err) {
      if (!corpo.substituir && /já tem um estilo/.test(err.message)
          && confirm(`${err.message.replace(/ \(use.*\)$/, "")}. Trocar pelo do arquivo?`)) {
        corpo = { ...corpo, substituir: true };
        continue;
      }
      aviso(`<b>Não importou:</b> ${esc(err.message)}`);
      return;
    }
  }
}

function ligarImportar(zona) {
  if (!zona) return;
  const input = zona.querySelector("input[type=file]");
  input.onchange = () => input.files[0] && importarEstilo(input.files[0]);
  zona.addEventListener("dragover", (ev) => { ev.preventDefault(); zona.classList.add("arrastando"); });
  zona.addEventListener("dragleave", () => zona.classList.remove("arrastando"));
  zona.addEventListener("drop", (ev) => {
    ev.preventDefault();
    zona.classList.remove("arrastando");
    const f = ev.dataTransfer.files[0];
    if (f) importarEstilo(f);
  });
}

// ------------------------------------------------------------------ minha marca
const MARCA_COR = { primaria: "Primária", secundaria: "Secundária", texto: "Texto" };
const MARCA_COR_INICIAL = { primaria: "#2E82F7", secundaria: "#DBD653", texto: "#111111" };
const fontesDaMarca = {};

// cada fonte numa família à parte ("marca Inter"): a amostra nunca troca a fonte do painel
function carregarFonteDaMarca(f) {
  const familia = `marca ${f.nome}`;
  if (!fontesDaMarca[familia]) {
    fontesDaMarca[familia] = new FontFace(familia, `url("${f.url}")`, { weight: "100 900" }).load()
      .then((ff) => { document.fonts.add(ff); return familia; }).catch(() => null);
  }
  return fontesDaMarca[familia];
}

async function telaMarca() {
  const [m, { estilos }] = await Promise.all([api("/api/marca"), api("/api/estilos")]);
  const cores = { ...MARCA_COR_INICIAL };
  Object.entries(m.marca.cores).forEach(([k, v]) => { if (v) cores[k] = v; });
  const fontes = { titulo: m.marca.fontes.titulo || "Archivo Black", texto: m.marca.fontes.texto || "Inter" };
  const kit = m.fontes_do_kit.map((f) => f.nome);
  const opcoes = (atual) => (atual && !kit.includes(atual) ? `<option value="${esc(atual)}" selected>${esc(atual.split("/").pop())} (sua)</option>` : "")
    + kit.map((n) => `<option value="${esc(n)}" ${n === atual ? "selected" : ""}>${esc(n)}</option>`).join("");
  let logoNovo = null, tirarLogo = false;

  app.innerHTML = `
  <a class="voltar" href="#/biblioteca">← biblioteca</a>
  <div class="cabeca-projeto"><div>
    <h1 class="titulo">Minha <span class="marca">marca</span></h1>
    <p class="lead">Suas cores, fontes e logo. Cada estilo diz onde a marca pode entrar: assim ela aparece sem estragar o estilo.</p>
  </div></div>
  <div class="marca-tela">
    <form class="papel painel-etapa marca-form" autocomplete="off">
      <div class="campo-duplo">
        <div class="campo"><label for="m-nome">Nome da marca</label><input id="m-nome" name="nome" value="${esc(m.marca.nome)}" placeholder="Felipe Top"></div>
        <div class="campo"><label for="m-arroba">Seu @</label><input id="m-arroba" name="arroba" value="${esc(m.marca.arroba)}" placeholder="@seuperfil"></div>
      </div>
      <fieldset class="campo"><legend>Cores</legend>
        ${Object.entries(MARCA_COR).map(([k, nome]) => `
        <div class="cor-linha">
          <input type="color" data-cor="${k}" value="${hex(cores[k]).toLowerCase()}" aria-label="Cor: ${nome}">
          <span>${nome}</span>
          <input class="hex" data-hex="${k}" value="${esc(cores[k])}" maxlength="7" spellcheck="false" aria-label="Código da cor: ${nome}">
        </div>`).join("")}
      </fieldset>
      <div class="campo-duplo">
        <div class="campo"><label for="m-titulo">Fonte do título</label><select id="m-titulo" data-fonte="titulo">${opcoes(fontes.titulo)}</select></div>
        <div class="campo"><label for="m-texto">Fonte do texto</label><select id="m-texto" data-fonte="texto">${opcoes(fontes.texto)}</select></div>
      </div>
      <div class="campo"><label>Logo</label>
        <div class="logo-linha">
          <div class="logo-caixa" data-logo-caixa></div>
          <div class="logo-acoes">
            <label class="botao claro pequeno">Escolher PNG<input type="file" accept="image/png" data-logo hidden></label>
            <button type="button" class="link" data-tirar-logo hidden>tirar o logo</button>
            <small>PNG com fundo transparente, até 5 MB.</small>
          </div>
        </div>
      </div>
      <div class="avisos-marca" data-avisos aria-live="polite"></div>
      <div class="erro" data-erro hidden></div>
      <div class="modal-acoes"><button class="botao" type="submit">Salvar minha marca</button></div>
    </form>
    <aside class="marca-lado">
      <div class="papel painel-etapa">
        <h3 class="subtitulo">Como fica</h3>
        <div class="amostra" data-amostra>
          <img class="amostra-logo" alt="" hidden>
          <div class="amostra-titulo"></div>
          <div class="amostra-texto"></div>
          <span class="amostra-faixa"></span>
        </div>
        <small class="mudo">Seu texto sobre a cor primária, com a secundária na faixa. É só uma amostra: no vídeo, cada estilo usa a marca do jeito dele.</small>
      </div>
      <div class="papel painel-etapa onde-entra">
        <h3 class="subtitulo">Onde ela entra</h3>
        <ul>${estilos.map((e) => `<li><a href="#/biblioteca/estilo/${esc(e.id)}">${esc(e.nome)}</a>
          ${e.slots_da_marca.length ? `usa ${esc(marcaNoEstilo(e))}` : `<span class="mudo">não usa: cores e fontes fixas</span>`}</li>`).join("")}</ul>
      </div>
    </aside>
  </div>`;

  const form = app.querySelector(".marca-form");
  const amostra = app.querySelector("[data-amostra]");
  const caixaAvisos = form.querySelector("[data-avisos]");
  const erro = form.querySelector("[data-erro]");
  const mostrarErro = (msg) => { erro.hidden = !msg; erro.textContent = msg || ""; };

  const pintar = () => {
    amostra.style.background = hex(cores.primaria);
    amostra.style.color = hex(cores.texto);
    amostra.querySelector(".amostra-faixa").style.background = hex(cores.secundaria);
    amostra.querySelector(".amostra-titulo").textContent = form.nome.value.trim() || "Sua marca";
    amostra.querySelector(".amostra-texto").textContent = form.arroba.value.trim() || "o texto do vídeo fica assim";
  };
  const mostrarLogo = (url) => {
    form.querySelector("[data-logo-caixa]").innerHTML = url ? `<img src="${esc(url)}" alt="seu logo">` : `<span>sem logo</span>`;
    const img = amostra.querySelector(".amostra-logo");
    img.hidden = !url;
    if (url) img.src = url;
    form.querySelector("[data-tirar-logo]").hidden = !url;
  };
  // o aviso de contraste vem do servidor (a conta do lib/estilo.py), enquanto a pessoa mexe
  const mostrarAvisos = (avisos) => {
    caixaAvisos.innerHTML = (avisos.length ? avisos.map((a) => `<p>${esc(a)}</p>`).join("")
      : `<p class="ok">Contraste bom: o texto se lê bem sobre a cor primária.</p>`)
      + (m.aviso_logo && !logoNovo && !tirarLogo ? `<p>${esc(m.aviso_logo)}</p>` : "");
  };
  let espera = null;
  const reconferir = () => {
    clearTimeout(espera);
    espera = setTimeout(async () => {
      const r = await api("/api/marca/conferir", { method: "POST", body: { cores } }).catch(() => null);
      if (r) mostrarAvisos(r.avisos);
    }, 250);
  };
  const aplicarFonte = async (qual, alvo) => {
    const f = m.fontes_do_kit.find((x) => x.nome === fontes[qual]);
    alvo.style.fontFamily = "";
    const familia = f && (await carregarFonteDaMarca(f));
    if (familia && fontes[qual] === f.nome) alvo.style.fontFamily = `"${familia}", var(--texto)`;
  };

  form.querySelectorAll("[data-cor]").forEach((inp) => inp.addEventListener("input", () => {
    cores[inp.dataset.cor] = inp.value.toUpperCase();
    form.querySelector(`[data-hex="${inp.dataset.cor}"]`).value = cores[inp.dataset.cor];
    pintar(); reconferir();
  }));
  form.querySelectorAll("[data-hex]").forEach((inp) => inp.addEventListener("input", () => {
    const v = (inp.value.trim().startsWith("#") ? "" : "#") + inp.value.trim();
    if (!/^#[0-9a-f]{6}$/i.test(v)) return;
    cores[inp.dataset.hex] = v.toUpperCase();
    form.querySelector(`[data-cor="${inp.dataset.hex}"]`).value = v.toLowerCase();
    pintar(); reconferir();
  }));
  form.nome.addEventListener("input", pintar);
  form.arroba.addEventListener("input", pintar);
  form.querySelectorAll("[data-fonte]").forEach((s) => s.addEventListener("change", () => {
    fontes[s.dataset.fonte] = s.value;
    aplicarFonte(s.dataset.fonte, amostra.querySelector(s.dataset.fonte === "titulo" ? ".amostra-titulo" : ".amostra-texto"));
  }));
  form.querySelector("[data-logo]").addEventListener("change", (ev) => {
    const arq = ev.target.files[0];
    if (!arq) return;
    if (arq.type !== "image/png") return mostrarErro("O logo precisa ser um arquivo PNG.");
    if (arq.size > 5_000_000) return mostrarErro("O logo passou de 5 MB. Use um PNG menor.");
    const leitor = new FileReader();
    leitor.onload = () => { logoNovo = leitor.result; tirarLogo = false; mostrarLogo(logoNovo); mostrarErro(""); reconferir(); };
    leitor.readAsDataURL(arq);
  });
  form.querySelector("[data-tirar-logo]").onclick = () => { logoNovo = null; tirarLogo = true; mostrarLogo(null); reconferir(); };

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const botao = form.querySelector('[type="submit"]');
    botao.disabled = true;
    const corpo = { nome: form.nome.value, arroba: form.arroba.value, cores, fontes };
    if (logoNovo) corpo.logo = logoNovo;
    else if (tirarLogo) corpo.remover_logo = true;
    try {
      await api("/api/marca", { method: "POST", body: corpo });
      await telaMarca();
      aviso(`<b>Marca salva.</b> Ela entra nos próximos vídeos, nos estilos que aceitam marca.`);
    } catch (err) {
      mostrarErro(err.message);
      botao.disabled = false;
    }
  };

  pintar();
  mostrarLogo(m.logo);
  if (m.existe) mostrarAvisos(m.avisos);
  else reconferir();                       // as cores de partida também passam pela conta
  aplicarFonte("titulo", amostra.querySelector(".amostra-titulo"));
  aplicarFonte("texto", amostra.querySelector(".amostra-texto"));
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
