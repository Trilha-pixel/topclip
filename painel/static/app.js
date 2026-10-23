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

// Preferência só deste navegador (uma dobra aberta, por exemplo). Sem armazenamento, vale o padrão.
function lerPref(chave, padrao) {
  try { const v = localStorage.getItem(`topclip:${chave}`); return v == null ? padrao : JSON.parse(v); } catch { return padrao; }
}
function gravarPref(chave, valor) {
  try { localStorage.setItem(`topclip:${chave}`, JSON.stringify(valor)); } catch { /* sem armazenamento: só não lembra */ }
}

// ------------------------------------------------------------------ NIET Clube
// Bilhetes pequenos no Papel, nada de pop-up nem chamada de rede: só um link que a pessoa
// abre se quiser. O utm_content diz qual lugar do painel trouxe a visita.
const NIET_URL = "https://www.nietclube.com.br/";
function linkNiet(lugar) {
  return NIET_URL + "?utm_source=topclip&utm_medium=painel&utm_content=" + lugar;
}

// As asas, na cor da tinta: o SVG pinta com currentColor.
const logoNiet = (largura) =>
  `<svg class="niet-logo" viewBox="0 0 1044 537" width="${largura}" height="${(largura * 537 / 1044).toFixed(1)}" aria-hidden="true"><use href="/static/marca/niet.svg#niet"/></svg>`;

// O "×" esconde o bilhete neste navegador; sem armazenamento, ele só volta a aparecer.
function bilheteNiet(chave, classe, miolo, acao) {
  if (lerPref(chave, false)) return "";
  return `
  <aside class="${classe} niet" data-niet="${esc(chave)}">
    <button type="button" class="niet-fechar" data-fechar-niet="${esc(chave)}" aria-label="Esconder este bilhete" title="Esconder">×</button>
    ${miolo}
    <div class="niet-pe">${acao}<span class="niet-assinatura">${logoNiet(28)}NIET Clube</span></div>
  </aside>`;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-fechar-niet]");
  if (!b) return;
  gravarPref(b.dataset.fecharNiet, true);
  document.querySelectorAll(`[data-niet="${CSS.escape(b.dataset.fecharNiet)}"]`).forEach((el) => el.remove());
});

// Lista longa em páginas. Os itens de todas as páginas já estão no HTML — a escolha marca
// item de qualquer página e "marcar todos" pega todos —, a página só mostra e esconde.
// Quando a tela redesenha sozinha (chegou coisa nova), volta para a mesma página.
const POR_PAGINA = 6;
const paginaAberta = {};

function paginas(chave, total, por = POR_PAGINA) {
  if (total <= por) return "";
  const n = Math.ceil(total / por);
  return `
  <nav class="paginas" data-paginas="${esc(chave)}" data-por="${por}" aria-label="Páginas">
    <button type="button" class="pag-seta" data-pag="-1" aria-label="Página anterior">‹</button>
    ${Array.from({ length: n }, (_, i) => `<button type="button" class="pag-num" data-pag-num="${i}">${i + 1}</button>`).join("")}
    <button type="button" class="pag-seta" data-pag="1" aria-label="Próxima página">›</button>
    <span class="pag-conta"></span>
  </nav>`;
}

function ligarPaginas(raiz = app) {
  raiz.querySelectorAll("[data-paginas]").forEach((nav) => {
    const chave = nav.dataset.paginas;
    const lista = [...raiz.querySelectorAll("[data-paginada]")].find((l) => l.dataset.paginada === chave);
    if (!lista) return;
    const itens = [...lista.children];
    const por = Number(nav.dataset.por) || POR_PAGINA;
    const n = Math.ceil(itens.length / por);
    const mostrar = (pg, rolar) => {
      pg = Math.max(0, Math.min(n - 1, pg));
      paginaAberta[chave] = pg;
      itens.forEach((el, i) => (el.hidden = Math.floor(i / por) !== pg));
      nav.querySelectorAll("[data-pag-num]").forEach((b) => b.setAttribute("aria-current", Number(b.dataset.pagNum) === pg ? "page" : "false"));
      nav.querySelector('[data-pag="-1"]').disabled = pg === 0;
      nav.querySelector('[data-pag="1"]').disabled = pg === n - 1;
      nav.querySelector(".pag-conta").textContent = `${pg * por + 1}–${Math.min(itens.length, (pg + 1) * por)} de ${itens.length}`;
      lista.querySelectorAll("video").forEach((v) => v.closest("[hidden]") && v.pause());
      if (rolar) lista.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    nav.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || b.disabled) return;
      mostrar(b.dataset.pagNum != null ? Number(b.dataset.pagNum) : (paginaAberta[chave] || 0) + Number(b.dataset.pag), true);
    });
    mostrar(paginaAberta[chave] || 0, false);
  });
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

// No computador fica embaixo dos botões, na sobra da coluna do polaroide; no celular as
// colunas empilham e ali empurraria os projetos, então vai para depois deles.
const bilheteInicio = (onde) => bilheteNiet("niet-inicio", `papel fita niet-inicio ${onde}`,
  `<span class="mao niet-rotulo">quem fez o TopClip</span>
   <p>Eu fiz o TopClip conversando com o Claude. Quer criar ferramentas como essa, para vender ou para usar na sua empresa? O primeiro passo é o curso de Lovable do NIET Clube.</p>`,
  `<a class="link" href="${linkNiet("inicio")}" target="_blank" rel="noopener">conhecer o NIET Clube →</a>`);

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
      ${bilheteInicio("no-heroi")}
    </div>
    <div class="heroi-arte">
      <a href="${linkNiet("heroi")}" target="_blank" rel="noopener" title="Montar uma agência de cortes com o NIET Clube">
        <img src="/static/img/heroi.jpg" alt="Isso é uma agência: três clipes verticais, de um podcaster, um médico e um advogado, com uma seta até a etiqueta de preço R$, todo mês. Abre o NIET Clube.">
      </a>
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
       </div>`}
  ${bilheteInicio("no-pe")}`;

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

// Clipes (o vídeo cortado, etapa por etapa) ou posts virais (frase + prints): o mesmo vídeo, dois produtos.
const ICONE_CLIPES = `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="2.5" width="12" height="19" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.5 9 L14.5 12 L10.5 15 Z" fill="currentColor"/></svg>`;
const ICONE_POSTS = `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="2.5" width="16" height="19" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M4 12 H20" stroke="currentColor" stroke-width="2"/><path d="M8 9 H16 M8 18.5 H16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;

function cabecaProjeto(p, modo) {
  return `
  <a class="voltar" href="#/">← todos os projetos</a>
  <div class="cabeca-projeto">
    <div>
      <h1 class="titulo">${esc(p.nome)}</h1>
      <div class="caminho">${p.video ? `🎬 ${esc(p.video)}` : p.link ? `🔗 baixando de ${esc(p.link)}` : "sem vídeo definido"}${p.run && modo === "clipes" ? ` · run ${esc(p.run)}` : ""}</div>
    </div>
    <div class="cabeca-acoes">
      <button class="link apagar" data-acao="apagar">apagar projeto</button>
      <button class="botao claro pequeno" data-acao="abrir">Abrir pasta</button>
    </div>
  </div>
  <nav class="modos" aria-label="O que fazer com este vídeo">
    <a class="modo ${modo === "clipes" ? "ativo" : ""}" href="#/projeto/${esc(p.slug)}" ${modo === "clipes" ? 'aria-current="page"' : ""}>${ICONE_CLIPES}<span><b>Clipes</b><small>vídeos 9:16 com motion</small></span></a>
    <a class="modo ${modo === "posts" ? "ativo" : ""}" href="#/projeto/${esc(p.slug)}/posts" ${modo === "posts" ? 'aria-current="page"' : ""}>${ICONE_POSTS}<span><b>Posts virais</b><small>frase + prints do vídeo</small></span></a>
  </nav>`;
}

function ligarCabeca(p) {
  app.querySelector('[data-acao="abrir"]').onclick = () => api(`/api/projetos/${p.slug}/abrir`, { method: "POST" }).catch((e) => aviso(esc(e.message)));
  app.querySelector('[data-acao="apagar"]').onclick = () => abrirApagarProjeto(p);
}

async function telaProjeto(slug, etapa) {
  if (etapa === "posts") return telaPosts(slug);
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
  ${cabecaProjeto(p, "clipes")}
  ${trilhaEtapas(p, ativa)}
  <section class="atividade papel" id="atividade"><div class="mudo mono">carregando a atividade…</div></section>
  <section class="painel-etapa papel">${corpo}</section>`;

  app.querySelectorAll("[data-etapa]").forEach((b) => (b.onclick = () => (location.hash = `#/projeto/${slug}/${b.dataset.etapa}`)));
  ligarCabeca(p);
  ligarEscolhas(p, ativa);
  ligarPaginas();
  ligarMotion();
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
  const abertos = p.momentos.filter((m) => !m.feito);
  const feitos = p.momentos.filter((m) => m.feito);
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.momentos.length} momentos encontrados${feitos.length ? ` <span class="mudo">(${abertos.length} para escolher)</span>` : ""}</h2>
      <p class="explica">Marque <b>poucos — de 2 a ${MOMENTOS_RECOMENDADOS}</b>. Cada momento marcado vira corte, revisão e prévia: marcar demais deixa a próxima etapa bem mais lenta. O Claude só segue com os escolhidos.</p>
      ${comNota ? `<p class="explica">Em ordem de <b>nota estimada</b> — a mesma conta que decide no fim. Abaixo de ${num(p.gate)}, o corte tende a sair fraco.</p>` : ""}</div>
    ${abertos.length ? `<div class="acoes-lista">${comNota
      ? (melhores ? `<button class="link" data-melhores>marcar os ${melhores} melhores</button>` : "")
      : `<button class="link" data-todos="momentos">marcar todos</button>`}<button class="link" data-limpar="momentos">limpar</button></div>` : ""}
  </div>
  ${abertos.length ? `<div class="lista" data-paginada="${esc(p.slug)}:momentos">${abertos.map(cartaoMomento).join("")}</div>
  ${paginas(`${p.slug}:momentos`, abertos.length)}`
    : `<p class="explica">Todos os momentos já viraram clipe ou estão em produção.</p>`}
  <div data-depois-salvar hidden>${proximoPasso("agora diga ao Claude:", "escolhi no painel, pode seguir")}</div>
  ${grupoFeitos(feitos, ["momento", "momentos"], `<div class="lista">${feitos.map(cartaoMomento).join("")}</div>`)}`;
}

function cartaoMomento(m) {
  const sim = escolhas.momentos.has(m.id);
  return `
  <article class="momento ${sim ? "escolhido" : ""} ${m.feito || ""}" ${m.feito ? "" : `data-item="momentos" data-id="${esc(m.id)}" tabindex="0" role="checkbox" aria-checked="${sim}"`}>
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
      ${m.context_needed || m.payoff_candidate ? `<details class="detalhe mais"><summary>contexto e fechamento</summary>
        ${m.context_needed ? `<p><b>Contexto:</b> ${esc(m.context_needed)}</p>` : ""}
        ${m.payoff_candidate ? `<p><b>Fecha com:</b> ${esc(m.payoff_candidate)}</p>` : ""}</details>` : ""}
    </div>
    <span class="marcar">${m.feito === "pronto" ? VISTO_BRANCO : VISTO}</span>
  </article>`;
}

// O que já saiu (ou está saindo) não volta para a escolha: fica embaixo, dobrado.
function grupoFeitos(lista, [um, varios], conteudo) {
  const n = lista.length;
  if (!n) return "";
  const prontos = lista.every((x) => x.feito === "pronto");
  const texto = `${n === 1 ? um : varios} ${!prontos ? "já feitos ou em produção" : n === 1 ? "já virou clipe" : "já viraram clipe"}`;
  return `<details class="grupo-feitos"><summary><span class="carimbo pronto em-linha">✓ ${n}</span> ${esc(texto)} <span class="link">ver</span></summary>${conteudo}</details>`;
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
  const abertos = p.cortes.filter((c) => !c.feito);
  const feitos = p.cortes.filter((c) => c.feito);
  const cartao = (c) => cartaoCorte(p, c);
  return `
  <div class="secao-topo">
    <div><h2 class="subtitulo">${p.cortes.length} cortes para assistir${feitos.length ? ` <span class="mudo">(${abertos.length} para escolher)</span>` : ""}</h2>
      <p class="explica">${feitos.length
        ? "Os que já saíram estão lá embaixo, dobrados. Marque os próximos que viram vertical."
        : "Assista e marque os que viram vertical. Os outros param aqui."}</p></div>
    ${abertos.length ? `<div class="acoes-lista"><button class="link" data-todos="cortes">${feitos.length ? "marcar os que faltam" : "marcar todos"}</button><button class="link" data-limpar="cortes">limpar</button></div>` : ""}
  </div>
  ${abertos.length ? `<div class="cortes" data-paginada="${esc(p.slug)}:cortes">${abertos.map(cartao).join("")}</div>
  ${paginas(`${p.slug}:cortes`, abertos.length)}`
    : `<p class="explica">Todos os cortes já viraram clipe ou estão em produção.</p>`}
  <div data-depois-salvar hidden>${proximoPasso("agora diga ao Claude:", "escolhi no painel, pode seguir")}</div>
  ${grupoFeitos(feitos, ["corte", "cortes"], `<div class="cortes">${feitos.map(cartao).join("")}</div>`)}`;
}

function cartaoCorte(p, c) {
  const sim = escolhas.cortes.has(c.id);
  return `
  <article class="corte ${sim ? "escolhido" : ""} ${c.feito || ""} ${c.preview ? "" : "sem-previa"}" data-cartao="${esc(c.id)}">
    ${carimbo(c.feito)}
    ${c.preview ? `<video src="${c.preview}" controls preload="metadata" playsinline></video>`
                : `<div class="sem-video">a prévia aparece aqui quando o Claude cortar</div>`}
    <div class="corte-corpo">
      <div class="corte-cabeca">
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
          : `<button class="alternar" data-item="cortes" data-id="${esc(c.id)}" role="checkbox" aria-checked="${sim}">
          <span class="marcar">${VISTO}</span> vira vertical
        </button>`}
      </div>
    </div>
  </article>`;
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
    ${p.verticais.map((v) => `<div class="vertical"><video src="${v.video}" controls preload="metadata" playsinline></video>${rotuloClipe(p, v.nome)}</div>`).join("")}
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
  // um cartão por clipe: clip-010, clip-010-limpo e clip-010-luxo são versões do mesmo corte
  const grupos = new Map();
  p.motion.forEach((m) => {
    const base = baseDoClipe(m.nome);
    grupos.set(base, [...(grupos.get(base) || []), m]);
  });
  const n = grupos.size;
  return blocoEstilo(p, estilos) + `
  <div class="secao-topo"><div><h2 class="subtitulo">${n} ${n === 1 ? "clipe" : "clipes"} no motion</h2>
    <p class="explica">Cada versão é o mesmo corte num estilo. O <b>master</b> é o final; o <b>rascunho</b> é só para revisar.</p></div></div>
  <div class="motion-clipes">${[...grupos].map(([base, versoes]) => cartaoMotion(p, base, versoes)).join("")}</div>`;
}

// "clip-010-quanto-mais-barato" e "clip-010-limpo" -> "clip-010"
const baseDoClipe = (nome) => (String(nome).match(/^clip-\d+/) || [nome])[0];
const tituloDoClipe = (p, nome) => (p.cortes.find((c) => c.id === baseDoClipe(nome)) || {}).titulo || "";
const rotuloClipe = (p, nome, extra = "") => {
  const titulo = tituloDoClipe(p, nome);
  return `<div class="rotulo">${titulo ? `<b>${esc(titulo)}</b>` : ""}<span>${esc(titulo ? baseDoClipe(nome) : nome)}${extra}</span></div>`;
};

function cartaoMotion(p, base, versoes) {
  // o master primeiro: é o que vale. Sem estilo congelado, o clipe é de antes dos estilos — Papel.
  const ordem = [...versoes].sort((a, b) => !!b.master - !!a.master);
  const naEntrega = p.entregas.some((e) => baseDoClipe(e.nome) === base);
  const situacao = (m) => (m.master ? "master" : m.rascunho ? "rascunho" : "em produção");
  const video = (m) => (m.master || m.rascunho
    ? `<video src="${m.master || m.rascunho}" controls preload="metadata" playsinline></video>`
    : `<div class="sem-video">o vídeo aparece aqui quando o Claude montar o rascunho</div>`);
  const nomeQuadro = (q) => decodeURIComponent(q.split("/").pop()).replace(/\.\w+$/, "");
  return `
  <article class="motion-clipe" data-motion="${esc(base)}">
    <div class="motion-cabeca">
      <div><span class="motion-id">${esc(base)}</span><h3>${esc(tituloDoClipe(p, base) || base)}</h3></div>
      ${naEntrega ? `<a class="carimbo pronto" href="#/projeto/${esc(p.slug)}/entrega">✓ na entrega</a>` : ""}
    </div>
    ${ordem.length > 1 ? `<div class="motion-versoes" role="tablist" aria-label="Versões">${ordem.map((m, i) => `
      <button type="button" class="chip ${i ? "" : "ativo"}" role="tab" aria-selected="${!i}" data-versao="${i}">${esc(m.estilo || "Papel")}<small>${situacao(m)}</small></button>`).join("")}</div>` : ""}
    ${ordem.map((m, i) => `
    <div class="motion-versao" data-versao-painel="${i}" ${i ? "hidden" : ""}>
      <div class="motion-tela">${video(m)}</div>
      <div class="motion-info">
        <p class="motion-situacao"><b>${ordem.length > 1 ? "" : `${esc(m.estilo || "Papel")} · `}${m.master ? "Master pronto" : m.rascunho ? "Rascunho para revisão" : "Em produção"}</b>
          ${m.master ? "" : m.rascunho ? "— o master sai depois que a revisão for aprovada." : "— as cenas aparecem aqui conforme o Claude compõe."}</p>
        ${m.quadros.length ? `
        <div class="motion-quadros-cabeca">quadros das cenas (${m.quadros.length})</div>
        <div class="motion-quadros">${m.quadros.map((q) => `<a href="${q}" target="_blank" rel="noopener" title="${esc(nomeQuadro(q))}"><img src="${q}" alt="${esc(nomeQuadro(q))}" loading="lazy"></a>`).join("")}</div>` : ""}
      </div>
    </div>`).join("")}
  </article>`;
}

function ligarMotion() {
  app.querySelectorAll("[data-motion]").forEach((cartao) => {
    cartao.querySelectorAll("[data-versao]").forEach((b) => b.addEventListener("click", () => {
      cartao.querySelectorAll("[data-versao]").forEach((x) => { x.classList.toggle("ativo", x === b); x.setAttribute("aria-selected", x === b); });
      cartao.querySelectorAll("[data-versao-painel]").forEach((painel) => {
        painel.hidden = painel.dataset.versaoPainel !== b.dataset.versao;
        if (painel.hidden) painel.querySelectorAll("video").forEach((v) => v.pause());
      });
    }));
  });
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
      ${rotuloClipe(p, e.nome, ` · ${num(e.mb)} MB · <a href="${e.video}" download>baixar</a>`)}</div>`).join("")}
  </div>
  ${bilheteNiet(`niet-entrega-${p.slug}`, "papel fita niet-entrega",
    `<h3 class="subtitulo">Você acabou de fazer o trabalho de uma agência</h3>
     <p class="explica">Tem podcaster, médico, advogado e empresário pagando todo mês para alguém fazer exatamente isso. No NIET Clube eu te ensino a sair do zero aos R$30 mil por mês com uma agência de cortes, do jeito que eu montei a minha.</p>`,
    `<a class="botao" href="${linkNiet("entrega")}" target="_blank" rel="noopener">Quero montar minha agência →</a>`)}`;
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
// O passo a passo e o log ficam dobrados: a faixa de cima já diz o estado e o %.
// Abrir ou fechar fica lembrado neste navegador (sem armazenamento, começa dobrado).
let atividadeDetalhe = lerPref("atividade-detalhe", false);

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
  const prog = (a.etapas || {})[ativa];
  caixa.innerHTML = `
    <div class="ativ-topo">
      <span class="ativ-estado ${cls}"><i></i>${rotulo}</span>
      <div class="ativ-agora">${agora}</div>
      <button class="ativ-resumo" data-ativ-detalhe aria-expanded="${atividadeDetalhe}">
        ${prog ? `<span class="ativ-resumo-nome">${esc(nomeEtapa)}</span><b>${prog.pct}%</b>${barraPct(prog.pct, "ativ-resumo-barra")}` : ""}
        <span class="link">${atividadeDetalhe ? "esconder detalhes" : "passo a passo e log"}</span>
      </button>
    </div>
    <div class="ativ-detalhe" ${atividadeDetalhe ? "" : "hidden"}>
    ${blocoProgresso(nomeEtapa, prog)}
    <div class="ativ-log-cabeca">
      <span>${logDeTodas ? "log de todas as etapas" : `log da etapa ${esc(nomeEtapa.toLowerCase())}`} (${daEtapa.length})</span>
      <span class="ativ-log-acoes">
        <button class="link" data-log-todas>${logDeTodas ? `só ${esc(nomeEtapa.toLowerCase())}` : "todas as etapas"}</button>
        ${daEtapa.length > 6 ? `<button class="link" data-ativ-alternar>${atividadeAberta ? "ver menos" : `ver tudo`}</button>` : ""}
      </span>
    </div>
    ${daEtapa.length ? `<ul class="ativ-lista">${lista.map((e) => `
      <li><time datetime="${esc(e.t)}">${horario(e.t)}</time><span class="ic ${e.tipo}">${ICONE_EVENTO[e.tipo] || "•"}</span><span>${esc(e.msg)}${logDeTodas && e.etapa ? ` <small class="ativ-etapa">${esc(e.etapa)}</small>` : ""}</span></li>`).join("")}</ul>`
      : `<p class="ativ-vazio">${a.eventos.length ? "Nada nesta etapa ainda — o que o TopClip fizer nela aparece aqui, ao vivo." : "O que o TopClip fizer neste projeto aparece aqui, ao vivo."}</p>`}
    </div>`;
  caixa.querySelector("[data-ativ-detalhe]").addEventListener("click", () => {
    atividadeDetalhe = !atividadeDetalhe;
    gravarPref("atividade-detalhe", atividadeDetalhe);
    desenharAtividade(slug, a, ativa);
  });
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

// ------------------------------------------------------------------ posts virais
// A frase dividida em prints do rosto, para o feed (4:5) ou os stories (9:16). O Claude acha as
// frases (posts/frases.json) e o `./topclip post prints` escolhe os quadros; daqui para a frente é
// tudo no painel e na hora: escolher, editar, trocar print e fonte, baixar. Cada mudança é salva em
// posts/posts.json e a prévia é refeita pelo servidor (a mesma arte que sai no PNG).
const LEGENDA_MAX = 2200;         // o limite do Instagram
const DESTAQUES = [
  { cor: null, nome: "Só negrito" },
  { cor: "#FFD43B", nome: "Amarelo" },
  { cor: "#7DF29B", nome: "Verde" },
];
let posts = null;                 // o que o servidor mandou da última vez
let postsSlug = null;
let postsVersao = Date.now();     // vai na URL da prévia: muda, a imagem recarrega
let trocandoPrint = null;         // {fid, i}: a faixa de prints aberta ({fid: "capa"}: a da capa)
let pediuPrintsEm = 0;            // o comando leva um instante para aparecer no diário
const salvarDepois = {};          // fid -> timer da edição esperando para salvar
const fontesPost = new Set();

const urlPosts = (resto = "") => `/api/projetos/${encodeURIComponent(postsSlug)}/posts${resto}`;
const nPrints = () => posts.estado.prints[posts.estado.formato];
const negritoHTML = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
const tokensDe = (t) => {
  const saida = [];
  String(t || "").split("**").forEach((pedaco, i) => pedaco.split(/\s+/).filter(Boolean).forEach((w) => saida.push([w, i % 2 === 1])));
  return saida;
};
const marcarTokens = (toks) => {
  const partes = [];
  for (let i = 0; i < toks.length;) {
    if (toks[i][1]) {
      let j = i;
      while (j < toks.length && toks[j][1]) j++;
      partes.push(`**${toks.slice(i, j).map((t) => t[0]).join(" ")}**`);
      i = j;
    } else { partes.push(toks[i][0]); i++; }
  }
  return partes.join(" ");
};
const semNegrito = (t) => tokensDe(t).map((x) => x[0]).join(" ");

// texto novo digitado: as palavras que continuam no lugar (ou que já estavam em negrito) mantêm o negrito
function retokenizar(antigo, digitado) {
  const velhos = tokensDe(antigo);
  const negritas = new Set(velhos.filter((t) => t[1]).map((t) => t[0]));
  return marcarTokens(digitado.split(/\s+/).filter(Boolean).map((w, i) =>
    [w, velhos[i] && velhos[i][0] === w ? velhos[i][1] : negritas.has(w)]));
}

function carregarFontesPost(lista) {
  const novas = lista.filter((f) => f.url && !fontesPost.has(f.id));
  if (!novas.length) return;
  const css = novas.map((f) => `@font-face{font-family:"post-${f.id}";src:url("${f.url}") format("truetype");font-weight:100 900;font-display:swap}`).join("");
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
  novas.forEach((f) => fontesPost.add(f.id));
}

async function telaPosts(slug) {
  postsSlug = slug;
  const [p, dados] = await Promise.all([api(`/api/projetos/${encodeURIComponent(slug)}`), api(`/api/projetos/${encodeURIComponent(slug)}/posts`)]);
  posts = dados;
  carregarFontesPost(posts.fontes);
  app.innerHTML = `${cabecaProjeto(p, "posts")}<section class="painel-etapa papel posts-tela" id="posts"></section>`;
  ligarCabeca(p);
  desenharPosts();
  acompanharPrints();
}

function desenharPosts() {
  const caixa = document.getElementById("posts");
  if (!caixa) return;
  caixa.innerHTML = blocoPosts();
  ligarPosts(caixa);
  barraPosts();
}

function blocoPosts() {
  const d = posts, e = d.estado, n = nPrints();
  const carrossel = e.modo === "carrossel";
  const claude = d.frases.filter((f) => !f.minha);
  const escolhidas = e.escolhidas.map((id) => d.frases.find((f) => f.id === id)).filter(Boolean);
  const pedido = `faz os posts virais de projetos/${postsSlug}`;
  const seg = (atual, valor, rotulo, attr, extra = "") => `<button type="button" class="seg ${atual === valor ? "ativo" : ""}" data-${attr}="${esc(valor)}" aria-pressed="${atual === valor}" ${extra}>${rotulo}</button>`;
  const icone = (k) => `<svg viewBox="0 0 16 20" aria-hidden="true">${Array.from({ length: k }, (_, i) =>
    `<rect x="1" y="${1 + i * (18 / k)}" width="14" height="${18 / k - 1.5}" rx="1.2"/>`).join("")}</svg>`;
  const destaques = [...DESTAQUES, ...(d.cor_da_marca ? [{ cor: d.cor_da_marca, nome: "Cor da marca" }] : [])];

  const status = [];
  if (d.erro_frases) status.push(`<div class="posts-aviso erro"><b>As frases do Claude têm um problema.</b> ${esc(d.erro_frases)}</div>`);
  if (d.gerando) {
    status.push(`<div class="posts-aviso andando"><span class="giro"></span><div><b>Escolhendo os melhores prints do vídeo…</b>
      <span class="mudo">${esc(d.gerando.msg || "")}</span>${barraPct(d.gerando.pct || 0)}</div></div>`);
  } else if (d.tem_video && (!d.tem_prints || d.faltam_prints.length)) {
    const txt = !d.tem_prints
      ? (claude.length ? "As frases estão prontas, mas os prints ainda não foram escolhidos." : "Para escrever as suas frases, o painel precisa antes escolher os melhores rostos do vídeo.")
      : `${d.faltam_prints.length} ${d.faltam_prints.length === 1 ? "frase nova ainda não tem prints" : "frases novas ainda não têm prints"}.`;
    status.push(`<div class="posts-aviso"><div><b>${esc(txt)}</b> <span class="mudo">Leva cerca de meio minuto num vídeo de meia hora.</span></div>
      <button class="botao pequeno" data-gerar-prints>Escolher os prints agora</button></div>`);
  } else if (!d.tem_video) {
    status.push(`<div class="posts-aviso"><b>Não achei o vídeo deste projeto.</b> <span class="mudo">Sem ele não dá para tirar os prints — confira o caminho em projeto.json ou espere o download terminar.</span></div>`);
  }

  return `
  <div class="secao-topo"><div>
    <h2 class="subtitulo">Posts virais</h2>
    <p class="explica">A frase dividida em prints do rosto, como os posts de frase que viralizam. Escolha as frases, ajuste o texto e baixe — tudo aqui, na hora.</p>
  </div></div>

  <div class="posts-ajustes">
    <div class="ajuste"><span class="ajuste-rotulo">Tipo</span>
      <div class="segmentado tipo">${Object.entries(d.modos).map(([k, nome]) => seg(e.modo, k, `${ICONE_MODO[k] || ""}<span>${esc(nome)}</span>`, "modo")).join("")}</div></div>
    <div class="ajuste"><span class="ajuste-rotulo">Formato</span>
      <div class="segmentado">${Object.entries(d.formatos).map(([k, f]) => seg(e.formato, k, `${esc(f.nome)}<small>${f.largura}×${f.altura}</small>`, "formato",
        carrossel && k === "stories" ? 'title="O carrossel é só no feed: escolher os stories volta para o post único."' : "")).join("")}</div></div>
    <div class="ajuste"><span class="ajuste-rotulo">Prints</span>
      <div class="segmentado prints">${[1, 2, 3].map((k) => seg(n, k, `${icone(k)}<span>${k}</span>`, "prints")).join("")}</div></div>
    <div class="ajuste larga"><span class="ajuste-rotulo">Fonte</span>
      <div class="chips-post">${d.fontes.map((f) => `<button type="button" class="chip fonte ${e.fonte === f.id ? "ativo" : ""}" data-fonte="${esc(f.id)}" style="font-family:'post-${esc(f.id)}',var(--texto)"><span class="aa">Aa</span>${esc(f.nome)}${f.marca ? `<small>da sua marca</small>` : ""}</button>`).join("")}</div></div>
    <div class="ajuste"><span class="ajuste-rotulo">Palavras em destaque</span>
      <div class="chips-post">${destaques.map((x) => `<button type="button" class="chip ${(e.destaque || null) === x.cor ? "ativo" : ""}" data-destaque="${esc(x.cor || "")}"><span class="bolinha" style="background:${x.cor || "#fff"}"></span>${esc(x.nome)}</button>`).join("")}</div></div>
    <div class="ajuste"><span class="ajuste-rotulo">Fotos</span>
      <div class="segmentado">${seg(e.pb ? "pb" : "cor", "cor", "Coloridas", "pb")}${seg(e.pb ? "pb" : "cor", "pb", "P&amp;B", "pb")}</div></div>
    <div class="ajuste"><span class="ajuste-rotulo">Assinatura</span>
      <div class="segmentado assinatura">${seg(e.assinatura && d.arroba ? "sim" : "nao", "nao", "Sem", "assinatura")}${seg(e.assinatura && d.arroba ? "sim" : "nao", "sim", esc(d.arroba || "seu @"), "assinatura", d.arroba ? "" : "disabled")}</div>
      ${d.arroba ? "" : `<a class="link dica-arroba" href="#/biblioteca/marca">cadastrar o seu @ na sua marca</a>`}</div>
  </div>
  ${carrossel ? `<p class="explica dica-ajuste">No carrossel, cada frase vira um slide do feed (1080×1350), na ordem de “Seu carrossel”. O Instagram aceita até ${d.slides_max} slides.</p>` : ""}
  ${e.formato === "feed" && n === 3 ? `<p class="explica dica-ajuste">3 prints no feed ficam baixinhos (1080×450): funciona melhor com o rosto bem de perto.</p>` : ""}
  ${e.formato === "stories" ? `<p class="explica dica-ajuste">Nos stories, o texto do último print sobe sozinho para não ficar embaixo da caixa de resposta.</p>` : ""}

  ${status.join("")}

  <div class="posts-passo">
    <h3 class="subtitulo"><span class="passo-num">1</span> Escolha as frases ${claude.length ? `<span class="mudo">(${claude.length} do vídeo)</span>` : ""}</h3>
    ${claude.length ? `<p class="explica">O Claude separou as frases que funcionam sozinhas, já divididas em ${n} ${n === 1 ? "parte" : "partes"}. Marque as que viram ${carrossel ? "slide" : "post"}.</p>` : ""}
  </div>
  ${!claude.length && !d.erro_frases ? `<div class="posts-vazio">
      <p class="explica">${d.tem_transcricao ? "A transcrição já existe: falta o Claude escolher as frases." : "O Claude transcreve o vídeo e escolhe as frases mais fortes."} Peça a ele:</p>
      ${comando(pedido)}
      <p class="explica">Ou escreva a sua frase agora — um salmo, uma frase sua — e use os prints do vídeo.</p></div>` : ""}
  <div class="frases-grade">
    ${d.frases.map(cartaoFrase).join("")}
    <button type="button" class="frase-nova" data-nova-frase><span class="mais">+</span><b>Escrever minha frase</b><span class="mudo">um salmo, uma frase sua, uma citação</span></button>
  </div>

  <div class="posts-passo" id="seus-posts">
    <h3 class="subtitulo"><span class="passo-num">2</span> ${carrossel ? "Seu carrossel" : "Seus posts"} ${escolhidas.length ? `<span class="mudo">(${escolhidas.length})</span>` : ""}</h3>
    ${escolhidas.length ? `<p class="explica">Clique numa palavra para pôr ou tirar o negrito. Arraste a foto da prévia para reposicionar; troque o print — ou suba uma foto sua — clicando na miniatura. As setas mudam a ordem.</p>`
      : `<p class="explica">Marque uma frase acima e o ${carrossel ? "slide" : "post"} aparece aqui.</p>`}
  </div>
  ${carrossel && escolhidas.length ? blocoCarrossel(escolhidas) : ""}
  <div class="posts-lista">${escolhidas.map(editorPost).join("")}</div>`;
}

const ICONE_MODO = {
  unico: `<svg viewBox="0 0 16 20" aria-hidden="true"><rect x="2" y="1" width="12" height="18" rx="1.5"/></svg>`,
  carrossel: `<svg viewBox="0 0 24 20" aria-hidden="true"><rect x="1" y="1" width="12" height="18" rx="1.5"/><rect x="15" y="3.5" width="3.4" height="13" rx="1"/><rect x="20" y="6" width="2.6" height="8" rx="1"/></svg>`,
};

const palavrasHTML = (t) => tokensDe(t).map(([w, b], k) => `<button type="button" class="palavra ${b ? "negrito" : ""}" data-w="${k}">${esc(w)}</button>`).join("");
const contaLegenda = (t) => `${String(t || "").length}/${LEGENDA_MAX}`;

function cartaoFrase(f) {
  const sim = posts.estado.escolhidas.includes(f.id);
  return `
  <article class="frase-cartao ${sim ? "escolhida" : ""} ${f.minha ? "minha" : ""}" data-frase="${esc(f.id)}" role="checkbox" aria-checked="${sim}" tabindex="0">
    <div class="frase-topo">
      ${f.minha ? `<span class="tag forte">sua frase</span>` : f.tipo_nome ? `<span class="tag forte">${esc(f.tipo_nome)}</span>` : ""}
      ${f.inicio ? `<span class="tempo">${esc(f.inicio)}</span>` : ""}
      ${f.editada ? `<span class="tag">editada</span>` : ""}
      <span class="marcar">${VISTO}</span>
    </div>
    <ol class="frase-partes">${f.partes.map((t) => `<li><span>${negritoHTML(t)}</span></li>`).join("")}</ol>
    ${f.original && !f.minha ? `<details class="detalhe"><summary>o que foi dito</summary><p>${esc(f.original)}</p>${f.porque ? `<p class="mudo">por que funciona: ${esc(f.porque)}</p>` : ""}</details>` : ""}
  </article>`;
}

// o número do post (ou do slide: a capa é o 1) na ordem em que vai sair
function posicao(fid) {
  const e = posts.estado, k = e.escolhidas.indexOf(fid) + 1;
  return e.modo === "carrossel" && posts.carrossel.usar ? k + 1 : k;
}

function setasOrdem(fid) {
  const lista = posts.estado.escolhidas, k = lista.indexOf(fid);
  return `<button type="button" class="ordem-btn" data-mover="-1" ${k <= 0 ? "disabled" : ""} title="mover para antes" aria-label="mover para antes">↑</button>
    <button type="button" class="ordem-btn" data-mover="1" ${k >= lista.length - 1 ? "disabled" : ""} title="mover para depois" aria-label="mover para depois">↓</button>`;
}

function editorPost(f) {
  const d = posts, e = d.estado, fmt = d.formatos[e.formato];
  const carrossel = e.modo === "carrossel";
  const q = (pid) => d.quadros[pid];
  const legendaEditada = e.edicoes[f.id]?.legenda != null;
  return `
  <article class="post-editor" data-post="${esc(f.id)}">
    <div class="post-previa" style="aspect-ratio:${fmt.largura}/${fmt.altura}" title="arraste para reposicionar a foto">
      <img src="${urlPosts(`/previa/${f.id}.jpg?v=${postsVersao}`)}" alt="Prévia do post" draggable="false">
    </div>
    <div class="post-campos">
      <div class="post-cabeca">
        <div class="post-ordem"><span class="ordem-num">${carrossel ? "slide" : "post"} ${posicao(f.id)}</span>${setasOrdem(f.id)}
          ${f.minha ? `<span class="tag forte">sua frase</span>` : f.tipo_nome ? `<span class="tag forte">${esc(f.tipo_nome)}</span>` : ""} ${f.inicio ? `<span class="tempo">${esc(f.inicio)}</span>` : ""}</div>
        <button class="botao pequeno" data-baixar="${esc(f.id)}">Baixar PNG</button>
      </div>
      ${f.partes.map((t, i) => `
      <div class="post-parte" data-parte="${i}">
        <button type="button" class="post-mini ${trocandoPrint && trocandoPrint.fid === f.id && trocandoPrint.i === i ? "aberto" : ""}" data-trocar="${i}" title="trocar o print">
          ${q(f.prints[i]) ? `<img src="${q(f.prints[i]).mini}" alt="">` : `<span>sem print</span>`}<small>trocar</small></button>
        <div class="post-texto">
          <label class="ajuste-rotulo" for="t-${esc(f.id)}-${i}">Print ${i + 1}</label>
          <input id="t-${esc(f.id)}-${i}" type="text" value="${esc(semNegrito(t))}" data-texto="${i}" autocomplete="off" spellcheck="true">
          <div class="palavras" data-palavras="${i}">${palavrasHTML(t)}</div>
        </div>
        <div class="post-zoom" role="group" aria-label="Zoom do print ${i + 1}">
          <button type="button" data-zoom="1" data-i="${i}" title="aproximar">+</button>
          <button type="button" data-zoom="-1" data-i="${i}" title="afastar">−</button>
        </div>
      </div>
      ${trocandoPrint && trocandoPrint.fid === f.id && trocandoPrint.i === i ? faixaPrints(f.prints[i], f.candidatos) : ""}`).join("")}
      <div class="campo post-ref">
        <label for="r-${esc(f.id)}">Referência <small class="mudo">(opcional — aparece pequena no último print)</small></label>
        <input id="r-${esc(f.id)}" type="text" value="${esc(f.referencia)}" data-referencia placeholder="ex.: Salmos 23:1" maxlength="80">
      </div>
      ${carrossel ? "" : `
      <div class="campo post-legenda">
        <div class="legenda-topo"><label for="l-${esc(f.id)}">Legenda do post <small class="mudo">(para colar no Instagram)</small></label>
          <button type="button" class="botao pequeno claro" data-copiar-legenda>Copiar legenda</button></div>
        <textarea id="l-${esc(f.id)}" rows="5" maxlength="${LEGENDA_MAX}" data-legenda placeholder="Escreva a legenda que vai junto do post no Instagram.">${esc(f.legenda)}</textarea>
        <div class="legenda-pe"><span class="mudo" data-conta>${contaLegenda(f.legenda)}</span>${legendaEditada && f.legenda_claude ? `<button type="button" class="link" data-legenda-claude>voltar à legenda do Claude</button>` : ""}</div>
      </div>`}
      <div class="post-rodape">
        ${f.editada ? `<button class="link" data-restaurar>voltar ao ${f.minha ? "texto que você escreveu" : "texto do Claude"}</button>` : "<span></span>"}
        ${f.minha ? `<button class="link apagar" data-apagar-minha>apagar esta frase</button>` : `<button class="link" data-tirar>tirar ${carrossel ? "do carrossel" : "dos posts"}</button>`}
      </div>
    </div>
  </article>`;
}

// O carrossel: a fita com os slides na ordem, a capa e a legenda (uma só para o carrossel).
function blocoCarrossel(escolhidas) {
  const c = posts.carrossel;
  const slide = (f, k) => `
    <div class="slide" data-slide="${esc(f.id)}">
      <button type="button" class="slide-ir" data-ir="${esc(f.id)}" title="editar este slide"><img src="${urlPosts(`/previa/${f.id}.jpg?v=${postsVersao}`)}" alt="Slide ${k}" loading="lazy"></button>
      <div class="slide-pe"><button type="button" data-mover-slide="-1" data-fid="${esc(f.id)}" ${k === (c.usar ? 2 : 1) ? "disabled" : ""} aria-label="mover para antes">‹</button><b>${k}</b><button type="button" data-mover-slide="1" data-fid="${esc(f.id)}" ${f.id === escolhidas[escolhidas.length - 1].id ? "disabled" : ""} aria-label="mover para depois">›</button></div>
    </div>`;
  const legendaEditada = posts.estado.legenda_carrossel != null;
  return `
  <div class="carrossel-caixa">
    <div class="carrossel-fita">
      ${c.usar ? `<div class="slide capa"><button type="button" class="slide-ir" data-ir="capa" title="editar a capa"><img src="${urlPosts(`/capa.jpg?v=${postsVersao}`)}" alt="Capa"></button><div class="slide-pe"><b>1 · capa</b></div></div>` : ""}
      ${escolhidas.map((f, k) => slide(f, k + 1 + (c.usar ? 1 : 0))).join("")}
    </div>
    <div class="campo post-legenda legenda-carrossel">
      <div class="legenda-topo"><label for="legenda-carrossel">Legenda do carrossel <small class="mudo">(uma só para todos os slides)</small></label>
        <button type="button" class="botao pequeno claro" data-copiar-legenda>Copiar legenda</button></div>
      <textarea id="legenda-carrossel" rows="6" maxlength="${LEGENDA_MAX}" data-legenda-carrossel placeholder="Escreva a legenda que vai junto do carrossel no Instagram.">${esc(c.legenda)}</textarea>
      <div class="legenda-pe"><span class="mudo" data-conta>${contaLegenda(c.legenda)}</span>${legendaEditada && c.legenda_claude ? `<button type="button" class="link" data-legenda-carrossel-claude>voltar à legenda do Claude</button>` : ""}</div>
    </div>
  </div>
  ${editorCapa()}`;
}

function editorCapa() {
  const d = posts, c = d.carrossel;
  if (!c.usar) {
    return `<div class="capa-desligada" data-capa><div><b>Sem capa.</b> <span class="mudo">O carrossel começa direto na primeira frase.</span></div>
      <button type="button" class="botao pequeno" data-capa-usar="1">Pôr uma capa</button></div>`;
  }
  const q = d.quadros[c.print];
  const aberto = trocandoPrint && trocandoPrint.fid === "capa";
  return `
  <article class="post-editor capa-editor" data-capa>
    <div class="post-previa" style="aspect-ratio:1080/1350" title="arraste para reposicionar a foto">
      <img src="${urlPosts(`/capa.jpg?v=${postsVersao}`)}" alt="Prévia da capa" draggable="false">
    </div>
    <div class="post-campos">
      <div class="post-cabeca">
        <div class="post-ordem"><span class="ordem-num">slide 1</span><span class="tag forte">capa</span></div>
        <button type="button" class="link" data-capa-usar="0">tirar a capa</button>
      </div>
      <p class="explica capa-explica">A capa abre o carrossel: um print só, o título grande e “arraste para o lado”.</p>
      <div class="post-parte">
        <button type="button" class="post-mini ${aberto ? "aberto" : ""}" data-trocar-capa title="trocar o print">
          ${q ? `<img src="${q.mini}" alt="">` : `<span>sem print</span>`}<small>trocar</small></button>
        <div class="post-texto">
          <label class="ajuste-rotulo" for="capa-texto">Título da capa</label>
          <input id="capa-texto" type="text" maxlength="160" value="${esc(semNegrito(c.texto))}" data-capa-texto placeholder="ex.: 5 verdades sobre cobrar caro" autocomplete="off" spellcheck="true">
          <div class="palavras" data-capa-palavras>${palavrasHTML(c.texto)}</div>
        </div>
        <div class="post-zoom" role="group" aria-label="Zoom da capa">
          <button type="button" data-capa-zoom="1" title="aproximar">+</button>
          <button type="button" data-capa-zoom="-1" title="afastar">−</button>
        </div>
      </div>
      ${aberto ? faixaPrints(c.print, []) : ""}
      ${c.capa_claude && d.estado.capa.texto != null && d.estado.capa.texto !== c.capa_claude
        ? `<div class="post-rodape"><button type="button" class="link" data-capa-claude>voltar ao título do Claude</button><span></span></div>` : ""}
    </div>
  </article>`;
}

function faixaPrints(usado, candidatos) {
  const d = posts;
  const mini = (pid) => d.quadros[pid] ? `<button type="button" class="faixa-print ${pid === usado ? "ativo" : ""}" data-usar="${esc(pid)}" title="${esc(d.quadros[pid].t)}${d.quadros[pid].sorrindo ? " · sorrindo" : ""}"><img src="${d.quadros[pid].mini}" alt="" loading="lazy"><small>${esc(d.quadros[pid].t)}</small></button>` : "";
  const perto = candidatos.filter((p) => d.quadros[p]);
  const banco = d.banco.filter((p) => !perto.includes(p) && d.quadros[p]);
  const proprias = d.proprias.filter((p) => d.quadros[p]);
  return `
  <div class="faixa" data-faixa>
    ${perto.length ? `<div class="faixa-rotulo">perto da frase</div><div class="faixa-linha">${perto.map(mini).join("")}</div>` : ""}
    ${banco.length ? `<div class="faixa-rotulo">do vídeo todo</div><div class="faixa-linha">${banco.map(mini).join("")}</div>` : ""}
    <div class="faixa-rotulo">suas fotos</div>
    <div class="faixa-linha">
      <label class="faixa-print subir" title="subir uma foto sua (JPG ou PNG)"><input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" data-subir-foto hidden><span class="mais">+</span><small>subir foto</small></label>
      ${proprias.map((p) => `<div class="faixa-item">${mini(p)}<button type="button" class="faixa-tirar" data-tirar-foto="${esc(p)}" title="tirar esta foto" aria-label="tirar esta foto">×</button></div>`).join("")}
    </div>
  </div>`;
}

// a edição de uma frase como o servidor guarda: só o que a pessoa mudou
function edicaoDe(fid) {
  const ed = posts.estado.edicoes[fid];
  return { partes: { ...(ed?.partes || {}) }, prints: { ...(ed?.prints || {}) }, ajustes: { ...(ed?.ajustes || {}) },
           referencia: ed?.referencia ?? null, legenda: ed?.legenda ?? null };
}

async function salvarPosts(dados, redesenhar = true) {
  try {
    const r = await api(urlPosts(), { method: "POST", body: dados });
    posts = r;
    postsVersao = Date.now();
    if (redesenhar) desenharPosts();
    return true;
  } catch (err) {
    aviso(`<b>Não salvou:</b> ${esc(err.message)}`);
    return false;
  }
}

// salva a edição de uma frase sem redesenhar a tela (o cursor fica onde está) e recarrega a prévia
function salvarEdicao(fid, ed, imediato = false) {
  clearTimeout(salvarDepois[fid]);
  posts.estado.edicoes[fid] = ed;
  const enviar = async () => {
    delete salvarDepois[fid];
    const ref = ed.referencia;
    const ok = await salvarPosts({ edicoes: { [fid]: { ...ed, referencia: ref ?? (posts.frases.find((f) => f.id === fid) || {}).referencia ?? "" } } }, false);
    if (!ok) return;
    const el = app.querySelector(`[data-post="${CSS.escape(fid)}"]`);
    const f = posts.frases.find((x) => x.id === fid);
    if (!el || !f) return;
    const src = urlPosts(`/previa/${fid}.jpg?v=${postsVersao}`);
    el.querySelector(".post-previa > img").src = src;
    app.querySelectorAll(`[data-slide="${CSS.escape(fid)}"] img`).forEach((img) => (img.src = src));
    el.querySelector(".post-rodape").outerHTML = editorPost(f).match(/<div class="post-rodape">[\s\S]*?<\/div>/)[0];
    ligarRodape(el, f);
    const cartao = app.querySelector(`[data-frase="${CSS.escape(fid)}"]`);
    if (cartao) { cartao.outerHTML = cartaoFrase(f); ligarCartoes(); }
  };
  if (imediato) return enviar();
  salvarDepois[fid] = setTimeout(enviar, 450);
}

// a capa e a legenda do carrossel também esperam a pessoa parar de digitar
const pendente = { capa: null, capaDados: {}, legenda: null };

function salvarCapa(mudanca, imediato = false) {
  clearTimeout(pendente.capa);
  Object.assign(pendente.capaDados, mudanca);
  Object.assign(posts.estado.capa, mudanca);
  const enviar = async () => {
    pendente.capa = null;
    const dados = pendente.capaDados;
    pendente.capaDados = {};
    if (!(await salvarPosts({ capa: dados }, false))) return;
    const src = urlPosts(`/capa.jpg?v=${postsVersao}`);
    app.querySelectorAll("[data-capa] .post-previa > img, .slide.capa img").forEach((img) => (img.src = src));
  };
  if (imediato) return enviar();
  pendente.capa = setTimeout(enviar, 450);
}

function salvarLegendaCarrossel(texto, imediato = false) {
  clearTimeout(pendente.legenda);
  posts.estado.legenda_carrossel = texto;
  const enviar = () => { pendente.legenda = null; return salvarPosts({ legenda_carrossel: texto }, false); };
  if (imediato) return enviar();
  pendente.legenda = setTimeout(enviar, 600);
}

async function terminarSalvamentos() {
  for (const fid of Object.keys(salvarDepois)) {
    clearTimeout(salvarDepois[fid]);
    await salvarEdicao(fid, posts.estado.edicoes[fid], true);
  }
  if (pendente.capa) await salvarCapa({}, true);
  if (pendente.legenda) await salvarLegendaCarrossel(posts.estado.legenda_carrossel, true);
}

const salvando = () => Object.keys(salvarDepois).length || pendente.capa || pendente.legenda;

function ligarCartoes() {
  app.querySelectorAll("[data-frase]").forEach((c) => {
    const alternar = () => {
      const lista = [...posts.estado.escolhidas];
      const i = lista.indexOf(c.dataset.frase);
      if (i >= 0) lista.splice(i, 1); else lista.push(c.dataset.frase);
      salvarPosts({ escolhidas: lista }).then((ok) => {
        if (ok && i < 0) aviso(posts.estado.modo === "carrossel" ? `<b>Slide criado.</b> Ajuste lá embaixo, em “Seu carrossel”.` : `<b>Post criado.</b> Ajuste lá embaixo, em “Seus posts”.`, 2200);
      });
    };
    c.onclick = (ev) => { if (!ev.target.closest("details, a")) alternar(); };
    c.onkeydown = (ev) => { if (ev.target === c && (ev.key === " " || ev.key === "Enter")) { ev.preventDefault(); alternar(); } };
  });
}

function ligarRodape(el, f) {
  // voltar ao texto do Claude não apaga a legenda que a pessoa escreveu
  el.querySelector("[data-restaurar]")?.addEventListener("click", () => {
    const leg = posts.estado.edicoes[f.id]?.legenda;
    salvarPosts({ edicoes: { [f.id]: leg != null ? { legenda: leg } : null } });
  });
  el.querySelector("[data-tirar]")?.addEventListener("click", () => salvarPosts({ escolhidas: posts.estado.escolhidas.filter((x) => x !== f.id) }));
  el.querySelector("[data-apagar-minha]")?.addEventListener("click", () => {
    if (!confirm("Apagar esta frase sua?")) return;
    salvarPosts({ minhas: posts.estado.minhas.filter((m) => m.id !== f.id),
                  escolhidas: posts.estado.escolhidas.filter((x) => x !== f.id), edicoes: { [f.id]: null } });
  });
}

async function moverPost(fid, passo) {
  await terminarSalvamentos();
  const lista = [...posts.estado.escolhidas];
  const i = lista.indexOf(fid), j = i + passo;
  if (i < 0 || j < 0 || j >= lista.length) return;
  [lista[i], lista[j]] = [lista[j], lista[i]];
  if (await salvarPosts({ escolhidas: lista })) app.querySelector(`[data-post="${CSS.escape(fid)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// a foto que a pessoa sobe: o navegador reduz (até 2560 px) e manda em JPG, já em pé
async function fotoParaJpeg(arq) {
  try {
    const bmp = await createImageBitmap(arq, { imageOrientation: "from-image" });
    const k = Math.min(1, 2560 / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * k);
    c.height = Math.round(bmp.height * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    return c.toDataURL("image/jpeg", 0.92);
  } catch {
    // o navegador não abre (HEIC fora do Safari): vai como veio e o servidor diz se dá
    return new Promise((ok, erro) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = erro; r.readAsDataURL(arq); });
  }
}

async function subirFoto(arq) {
  try {
    const r = await api(urlPosts("/foto"), { method: "POST", body: { conteudo: await fotoParaJpeg(arq) } });
    posts = r;
    aviso(r.quadros[r.nova]?.sem_rosto
      ? "<b>Foto adicionada.</b> Não achei um rosto nela: arraste a prévia para enquadrar."
      : "<b>Foto adicionada.</b> Ela fica em “suas fotos” para os outros posts também.", 3600);
    return r.nova;
  } catch (err) {
    aviso(`<b>A foto não subiu:</b> ${esc(err.message)}`, 5200);
    return null;
  }
}

// a faixa de prints (de uma parte ou da capa): escolher, subir uma foto, tirar uma foto sua
function ligarFaixa(caixa, usar) {
  const faixa = caixa.querySelector("[data-faixa]");
  if (!faixa) return;
  faixa.querySelectorAll("[data-usar]").forEach((b) => (b.onclick = () => usar(b.dataset.usar)));
  faixa.querySelector("[data-subir-foto]")?.addEventListener("change", async (ev) => {
    const arq = ev.target.files[0];
    if (!arq) return;
    const rotulo = ev.target.closest("label");
    rotulo.classList.add("subindo");
    rotulo.querySelector("small").textContent = "subindo…";
    const pid = await subirFoto(arq);
    if (pid) usar(pid);
    else desenharPosts();
  });
  faixa.querySelectorAll("[data-tirar-foto]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Tirar esta foto dos prints? A original continua no seu computador.")) return;
    try {
      posts = await api(urlPosts("/foto/apagar"), { method: "POST", body: { id: b.dataset.tirarFoto } });
      postsVersao = Date.now();
      desenharPosts();
    } catch (err) { aviso(`<b>Não deu:</b> ${esc(err.message)}`); }
  }));
}

function ligarPosts(caixa) {
  const e = posts.estado;
  caixa.querySelectorAll("[data-modo]").forEach((b) => (b.onclick = () => b.dataset.modo !== e.modo && salvarPosts({ modo: b.dataset.modo })));
  caixa.querySelectorAll("[data-formato]").forEach((b) => (b.onclick = () => {
    if (b.dataset.formato === e.formato) return;
    salvarPosts({ formato: b.dataset.formato }).then((ok) => {
      if (ok && e.modo === "carrossel" && b.dataset.formato === "stories") aviso("<b>Stories não têm carrossel:</b> voltou para o post único.", 3600);
    });
  }));
  caixa.querySelectorAll("[data-prints]").forEach((b) => (b.onclick = () => Number(b.dataset.prints) !== nPrints() && salvarPosts({ prints: { [e.formato]: Number(b.dataset.prints) } })));
  caixa.querySelectorAll("[data-fonte]").forEach((b) => (b.onclick = () => b.dataset.fonte !== e.fonte && salvarPosts({ fonte: b.dataset.fonte })));
  caixa.querySelectorAll("[data-destaque]").forEach((b) => (b.onclick = () => salvarPosts({ destaque: b.dataset.destaque || null })));
  caixa.querySelectorAll("[data-pb]").forEach((b) => (b.onclick = () => (b.dataset.pb === "pb") !== e.pb && salvarPosts({ pb: b.dataset.pb === "pb" })));
  caixa.querySelectorAll("[data-assinatura]").forEach((b) => (b.onclick = () => (b.dataset.assinatura === "sim") !== e.assinatura && salvarPosts({ assinatura: b.dataset.assinatura === "sim" })));
  caixa.querySelector("[data-gerar-prints]")?.addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    ev.target.textContent = "Começando…";
    try {
      await api(urlPosts("/gerar-prints"), { method: "POST" });
      pediuPrintsEm = Date.now();
      posts.gerando = { msg: "começando…", pct: 0 };
      desenharPosts();
    } catch (err) {
      aviso(`<b>Não deu para começar:</b> ${esc(err.message)}`);
      ev.target.disabled = false;
      ev.target.textContent = "Escolher os prints agora";
    }
  });
  caixa.querySelector("[data-nova-frase]")?.addEventListener("click", abrirNovaFrase);
  ligarCartoes();
  ligarCarrossel(caixa);

  caixa.querySelectorAll("[data-post]").forEach((el) => {
    const fid = el.dataset.post;
    const f = () => posts.frases.find((x) => x.id === fid);
    const n = nPrints(), chaveAj = `${e.formato}-${n}`;
    const partesAgora = () => [...f().partes];

    el.querySelectorAll("[data-texto]").forEach((inp) => inp.addEventListener("input", () => {
      const i = Number(inp.dataset.texto);
      const partes = partesAgora();
      partes[i] = retokenizar(partes[i], inp.value);
      f().partes = partes;
      const ed = edicaoDe(fid);
      ed.partes[String(n)] = partes;
      el.querySelector(`[data-palavras="${i}"]`).innerHTML = palavrasHTML(partes[i]);
      salvarEdicao(fid, ed);
    }));
    el.querySelectorAll("[data-palavras]").forEach((box) => box.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-w]");
      if (!b) return;
      const i = Number(box.dataset.palavras), k = Number(b.dataset.w);
      const partes = partesAgora();
      const toks = tokensDe(partes[i]);
      toks[k][1] = !toks[k][1];
      partes[i] = marcarTokens(toks);
      f().partes = partes;
      b.classList.toggle("negrito", toks[k][1]);
      const ed = edicaoDe(fid);
      ed.partes[String(n)] = partes;
      salvarEdicao(fid, ed);
    }));
    el.querySelector("[data-referencia]").addEventListener("input", (ev) => {
      const ed = edicaoDe(fid);
      ed.referencia = ev.target.value;
      f().referencia = ev.target.value;
      salvarEdicao(fid, ed);
    });
    el.querySelector("[data-legenda]")?.addEventListener("input", (ev) => {
      const ed = edicaoDe(fid);
      ed.legenda = ev.target.value;
      f().legenda = ev.target.value;
      el.querySelector(".post-legenda [data-conta]").textContent = contaLegenda(ev.target.value);
      salvarEdicao(fid, ed);
    });
    el.querySelector(".post-legenda [data-copiar-legenda]")?.addEventListener("click", (ev) => {
      const t = el.querySelector("[data-legenda]").value.trim();
      if (!t) return aviso("A legenda está vazia.");
      copiar(t, ev.currentTarget);
    });
    el.querySelector("[data-legenda-claude]")?.addEventListener("click", () => {
      const ed = edicaoDe(fid);
      ed.legenda = null;
      posts.estado.edicoes[fid] = ed;
      salvarPosts({ edicoes: { [fid]: { ...ed, referencia: ed.referencia ?? f().referencia ?? "" } } });
    });
    el.querySelectorAll("[data-mover]").forEach((b) => (b.onclick = () => moverPost(fid, Number(b.dataset.mover))));
    el.querySelectorAll("[data-zoom]").forEach((b) => (b.onclick = () => {
      const i = Number(b.dataset.i);
      const ed = edicaoDe(fid);
      const aj = (ed.ajustes[chaveAj] || f().ajustes).map((a) => ({ ...a }));
      aj[i].zoom = Math.max(0.6, Math.min(2.5, Math.round((aj[i].zoom * (Number(b.dataset.zoom) > 0 ? 1.12 : 1 / 1.12)) * 100) / 100));
      ed.ajustes[chaveAj] = aj;
      f().ajustes = aj;
      salvarEdicao(fid, ed, true);
    }));
    el.querySelectorAll("[data-trocar]").forEach((b) => (b.onclick = () => {
      const i = Number(b.dataset.trocar);
      trocandoPrint = trocandoPrint && trocandoPrint.fid === fid && trocandoPrint.i === i ? null : { fid, i };
      desenharPosts();
      app.querySelector(`[data-post="${CSS.escape(fid)}"] [data-faixa]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }));
    ligarFaixa(el, async (pid) => {
      const i = trocandoPrint.i;
      const ed = edicaoDe(fid);
      const pr = [...f().prints];
      pr[i] = pid;
      ed.prints[String(n)] = pr;
      // print novo: o zoom e a posição do antigo não servem mais
      if (ed.ajustes[chaveAj]) { ed.ajustes[chaveAj] = ed.ajustes[chaveAj].map((a, k) => (k === i ? { zoom: 1, x: 0, y: 0 } : a)); }
      posts.estado.edicoes[fid] = ed;
      await salvarPosts({ edicoes: { [fid]: { ...ed, referencia: ed.referencia ?? f().referencia ?? "" } } });
    });
    el.querySelector("[data-baixar]").onclick = async () => {
      await terminarSalvamentos();
      location.href = urlPosts(`/baixar/${fid}.png`);
    };
    ligarRodape(el, f());
    ligarArrastar(el, n, () => (edicaoDe(fid).ajustes[chaveAj] || f().ajustes), (aj) => {
      const ed = edicaoDe(fid);
      ed.ajustes[chaveAj] = aj;
      f().ajustes = aj;
      return salvarEdicao(fid, ed, true);
    });
  });
}

function ligarCarrossel(caixa) {
  caixa.querySelectorAll("[data-ir]").forEach((b) => (b.onclick = () => {
    const alvo = b.dataset.ir === "capa" ? caixa.querySelector("[data-capa]") : caixa.querySelector(`[data-post="${CSS.escape(b.dataset.ir)}"]`);
    alvo?.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  caixa.querySelectorAll("[data-mover-slide]").forEach((b) => (b.onclick = () => moverPost(b.dataset.fid, Number(b.dataset.moverSlide))));
  const leg = caixa.querySelector("[data-legenda-carrossel]");
  if (leg) {
    const caixaLeg = leg.closest(".post-legenda");
    leg.addEventListener("input", () => {
      caixaLeg.querySelector("[data-conta]").textContent = contaLegenda(leg.value);
      salvarLegendaCarrossel(leg.value);
    });
    caixaLeg.querySelector("[data-copiar-legenda]").onclick = (ev) => {
      if (!leg.value.trim()) return aviso("A legenda está vazia.");
      copiar(leg.value.trim(), ev.currentTarget);
    };
    caixaLeg.querySelector("[data-legenda-carrossel-claude]")?.addEventListener("click", () => salvarPosts({ legenda_carrossel: null }));
  }

  const el = caixa.querySelector("[data-capa]");
  if (!el) return;
  el.querySelectorAll("[data-capa-usar]").forEach((b) => (b.onclick = () => salvarPosts({ capa: { usar: b.dataset.capaUsar === "1" } })));
  if (!el.matches(".capa-editor")) return;
  const texto = () => posts.carrossel.texto || "";
  const mudarTexto = (t) => {
    posts.carrossel.texto = t;
    salvarCapa({ texto: t });
  };
  el.querySelector("[data-capa-texto]").addEventListener("input", (ev) => {
    const t = retokenizar(texto(), ev.target.value);
    el.querySelector("[data-capa-palavras]").innerHTML = palavrasHTML(t);
    mudarTexto(t);
  });
  el.querySelector("[data-capa-palavras]").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-w]");
    if (!b) return;
    const toks = tokensDe(texto());
    toks[Number(b.dataset.w)][1] = !toks[Number(b.dataset.w)][1];
    b.classList.toggle("negrito", toks[Number(b.dataset.w)][1]);
    mudarTexto(marcarTokens(toks));
  });
  el.querySelector("[data-capa-claude]")?.addEventListener("click", () => salvarPosts({ capa: { texto: null } }));
  el.querySelectorAll("[data-capa-zoom]").forEach((b) => (b.onclick = () => {
    const aj = { ...posts.carrossel.ajuste };
    aj.zoom = Math.max(0.6, Math.min(2.5, Math.round((aj.zoom * (Number(b.dataset.capaZoom) > 0 ? 1.12 : 1 / 1.12)) * 100) / 100));
    posts.carrossel.ajuste = aj;
    salvarCapa({ ajuste: aj }, true);
  }));
  el.querySelector("[data-trocar-capa]").onclick = () => {
    trocandoPrint = trocandoPrint && trocandoPrint.fid === "capa" ? null : { fid: "capa", i: 0 };
    desenharPosts();
    app.querySelector("[data-capa] [data-faixa]")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  ligarFaixa(el, (pid) => salvarPosts({ capa: { print: pid } }));
  ligarArrastar(el, 1, () => [posts.carrossel.ajuste], (aj) => {
    posts.carrossel.ajuste = aj[0];
    return salvarCapa({ ajuste: aj[0] }, true);
  });
}

// arrastar a foto na prévia: o print sob o mouse anda junto (a prévia é refeita ao soltar)
function ligarArrastar(el, n, lerAjustes, gravar) {
  const caixa = el.querySelector(".post-previa");
  const img = caixa.querySelector("img");
  let ini = null;
  caixa.addEventListener("pointerdown", (ev) => {
    if (ev.button > 0) return;
    const r = caixa.getBoundingClientRect();
    const i = Math.min(n - 1, Math.floor(((ev.clientY - r.top) / r.height) * n));
    // uma janela só do print arrastado, com uma cópia da prévia dentro: os outros prints ficam parados
    const janela = document.createElement("div");
    janela.className = "post-arraste";
    janela.style.cssText = `top:${(i * 100) / n}%;height:${100 / n}%`;
    const copia = img.cloneNode();
    copia.style.cssText = `top:${-i * 100}%;height:${n * 100}%`;
    janela.appendChild(copia);
    caixa.appendChild(janela);
    ini = { x: ev.clientX, y: ev.clientY, i, w: r.width, h: r.height / n, janela, copia };
    caixa.setPointerCapture(ev.pointerId);
    caixa.classList.add("arrastando");
  });
  caixa.addEventListener("pointermove", (ev) => {
    if (ini) ini.copia.style.transform = `translate(${ev.clientX - ini.x}px, ${ev.clientY - ini.y}px)`;
  });
  const soltar = (ev) => {
    if (!ini) return;
    const dx = (ev.clientX - ini.x) / ini.w, dy = (ev.clientY - ini.y) / ini.h;
    const { i, janela } = ini;
    ini = null;
    caixa.classList.remove("arrastando");
    if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) { janela.remove(); return; }
    const aj = lerAjustes().map((a) => ({ ...a }));
    // a foto anda com o mouse: o recorte anda ao contrário
    aj[i].x = Math.max(-0.8, Math.min(0.8, aj[i].x - dx));
    aj[i].y = Math.max(-0.8, Math.min(0.8, aj[i].y - dy));
    img.addEventListener("load", () => janela.remove(), { once: true });
    setTimeout(() => janela.remove(), 4000);
    gravar(aj);
  };
  caixa.addEventListener("pointerup", soltar);
  caixa.addEventListener("pointercancel", soltar);
}

function barraPosts() {
  esconderBarra();
  const e = posts.estado, n = e.escolhidas.length;
  if (!n) return;
  const carrossel = e.modo === "carrossel";
  const slides = n + (carrossel && posts.carrossel.usar ? 1 : 0);
  const barra = document.createElement("div");
  barra.className = "barra-acao visivel";
  barra.innerHTML = carrossel
    ? `<span class="conta"><b>${slides}</b> ${slides === 1 ? "slide" : "slides"} · Carrossel${slides > posts.slides_max ? `<span class="alerta">O Instagram aceita até ${posts.slides_max} slides: tire ${slides - posts.slides_max}.</span>` : ""}</span>
      <button class="botao pequeno" data-zip>Baixar o carrossel (ZIP)</button>`
    : `<span class="conta"><b>${n}</b> ${n === 1 ? "post" : "posts"} · ${esc(posts.formatos[e.formato].nome)}</span>
      <button class="botao pequeno" data-zip>Baixar ${n === 1 ? "o post" : `os ${n}`} (PNG)</button>`;
  document.body.appendChild(barra);
  barra.querySelector("[data-zip]").onclick = async () => {
    await terminarSalvamentos();
    if (carrossel) {
      location.href = urlPosts("/baixar.zip");
      aviso(`<b>Baixando o carrossel.</b> Os slides vêm numerados na ordem, com a legenda junto. Ficam também em <span class="mono">projetos/${esc(postsSlug)}/posts/prontos/carrossel/</span>.`, 5200);
      return;
    }
    location.href = n === 1 ? urlPosts(`/baixar/${e.escolhidas[0]}.png`) : urlPosts("/baixar.zip");
    aviso(`<b>Baixando.</b> Os PNG também ficam em <span class="mono">projetos/${esc(postsSlug)}/posts/prontos/</span>.`, 4200);
  };
}

function abrirNovaFrase() {
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `
  <div class="modal papel fita" role="dialog" aria-modal="true" aria-labelledby="nova-frase-titulo">
    <h2 class="titulo" id="nova-frase-titulo">Sua frase</h2>
    <p class="explica">Escreva inteira: o painel divide em ${nPrints()} ${nPrints() === 1 ? "parte" : "partes"} e usa os melhores rostos do vídeo. Depois dá para ajustar tudo.</p>
    <div class="campo"><label for="nf-texto">Frase</label>
      <textarea id="nf-texto" rows="3" maxlength="280" placeholder="O Senhor é o meu pastor; nada me faltará."></textarea></div>
    <div class="campo"><label for="nf-ref">Referência <small class="mudo">(opcional)</small></label>
      <input id="nf-ref" type="text" maxlength="80" placeholder="Salmos 23:1"></div>
    <div class="erro" data-erro hidden></div>
    <div class="modal-acoes">
      <button type="button" class="botao claro" data-fechar>Cancelar</button>
      <button type="button" class="botao" data-criar>Criar post</button>
    </div>
  </div>`;
  document.body.appendChild(fundo);
  const fechar = () => fundo.remove();
  fundo.addEventListener("click", (ev) => { if (ev.target === fundo || ev.target.closest("[data-fechar]")) fechar(); });
  const texto = fundo.querySelector("#nf-texto");
  texto.focus();
  fundo.querySelector("[data-criar]").onclick = async () => {
    const t = texto.value.replace(/\s+/g, " ").trim();
    if (!t) { const er = fundo.querySelector("[data-erro]"); er.hidden = false; er.textContent = "Escreva a frase."; return; }
    const usados = posts.estado.minhas.map((m) => Number(m.id.split("-")[1]) || 0);
    const id = `minha-${Math.max(0, ...usados) + 1}`;
    const ref = fundo.querySelector("#nf-ref").value.trim();
    const ok = await salvarPosts({
      minhas: [...posts.estado.minhas, { id, partes: { 1: [t] } }],
      escolhidas: [...posts.estado.escolhidas, id],
      edicoes: { [id]: { partes: {}, prints: {}, ajustes: {}, referencia: ref } },
    });
    if (ok) {
      fechar();
      app.querySelector(`[data-post="${CSS.escape(id)}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };
}

// A tela acompanha sozinha o que chega de fora: os prints sendo escolhidos (pelo botão ou pelo
// Claude no terminal) e as frases novas que o Claude grava. Redesenha só quando muda o que se
// vê — e nunca no meio de uma edição.
const assinaturaPosts = (d) => JSON.stringify([d.frases.map((f) => [f.id, f.legenda_claude]), d.tem_prints, d.faltam_prints, !!d.gerando,
  d.banco.length, d.proprias.length, d.erro_frases, d.arroba, d.carrossel.capa_claude, d.carrossel.legenda_claude]);

function acompanharPrints() {
  clearInterval(relogio);
  relogio = setInterval(async () => {
    if (!posts || document.querySelector(".modal-fundo")) return;
    const r = await api(urlPosts()).catch(() => null);
    if (!r || !posts) return;
    if (!r.gerando && posts.gerando && Date.now() - pediuPrintsEm < 8000 && (!r.tem_prints || r.faltam_prints.length)) r.gerando = posts.gerando;
    const editando = salvando() || document.activeElement?.closest?.("#posts input, #posts textarea");
    if (assinaturaPosts(r) !== assinaturaPosts(posts)) {
      if (editando) return;                          // espera a pessoa sair do campo
      const terminou = posts.gerando && !r.gerando;
      posts = r;
      postsVersao = Date.now();
      desenharPosts();
      if (terminou) aviso("<b>Prints prontos.</b>");
      return;
    }
    if (r.gerando) {
      posts.gerando = r.gerando;
      const caixa = app.querySelector(".posts-aviso.andando");
      if (caixa) {
        caixa.querySelector(".mudo").textContent = r.gerando.msg || "";
        const barra = caixa.querySelector(".ativ-barra i");
        if (barra) barra.style.width = `${r.gerando.pct || 0}%`;
      }
    }
  }, 3000);
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

// Os objetos do Limpo, do Impacto e do Luxo: os mesmos para os três, no traço de cada um.
function secaoObjetos(o) {
  if (!o) return "";
  const seus = o.seus || [];
  return `
    <h3 class="prateleira-sub">No Limpo, no Impacto e no Luxo</h3>
    <p class="explica">${o.oficiais.length} objetos prontos, que saem no traço de cada estilo (abra um estilo e veja em “O desenho”)${seus.length ? `, e ${seus.length === 1 ? "um desenhado" : `${seus.length} desenhados`} para os seus vídeos:` : "."}</p>
    ${o.erro ? `<p class="estilo-erro">O arquivo dos seus objetos tem um erro: ${esc(o.erro)}. Peça ao Claude para conferir.</p>` : ""}
    ${seus.length ? `${o.folha ? `<img class="objetos-folha" src="${o.folha}" alt="Os seus objetos no Limpo, no Impacto e no Luxo" loading="lazy">` : ""}
      <ul class="objetos-seus">${seus.map((x) => `<li><b>${esc(x.nome.replace(/_/g, " "))}</b>${esc(x.descricao)}</li>`).join("")}</ul>`
    : `<p class="explica">Quando a fala pede um objeto que não está na lista, o Claude desenha, e ele aparece aqui para os próximos vídeos.</p>`}`;
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
  const [{ estilos, padrao }, { assets, objetos }, m] = await Promise.all([api("/api/estilos"), api("/api/biblioteca"), api("/api/marca")]);
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
    <h3 class="prateleira-sub">No Papel</h3>
    ${assets.length ? `<div class="assets">${assets.map((a, i) => `
      <figure class="asset papel ${i % 3 === 1 ? "fita" : ""}" style="margin:0">
        <div class="vitrine ${a.arquivo.startsWith("BG_") ? "fundo" : ""}"><img src="${a.url}" alt="${esc(a.objeto || a.arquivo)}" loading="lazy"></div>
        <h4>${esc(a.arquivo)}${a.dono === "seu" ? ` <span class="selo-seu">seu</span>` : ""}</h4>
        <p>${esc(a.objeto || "")}</p>
      </figure>`).join("")}</div>`
    : `<div class="vazio papel"><h3 class="titulo">Nada desenhado ainda</h3><p class="lead" style="margin:14px auto">O primeiro vídeo com motion já começa a encher.</p></div>`}
    ${secaoObjetos(objetos)}
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
  const veioDoProjeto = rotaAnterior && rotaAnterior.startsWith("#/projeto/");   // ex.: o @ da assinatura dos posts

  app.innerHTML = `
  <a class="voltar" href="${veioDoProjeto ? esc(rotaAnterior) : "#/biblioteca"}">← ${veioDoProjeto ? "voltar ao projeto" : "biblioteca"}</a>
  <div class="cabeca-projeto"><div>
    <h1 class="titulo">Minha <span class="marca">marca</span></h1>
    <p class="lead">Suas cores, fontes e logo. Cada estilo diz onde a marca pode entrar: assim ela aparece sem estragar o estilo.</p>
  </div></div>
  <div class="marca-tela">
    <form class="papel painel-etapa marca-form" autocomplete="off">
      <div class="campo-duplo">
        <div class="campo"><label for="m-nome">Nome da marca</label><input id="m-nome" name="nome" value="${esc(m.marca.nome)}" placeholder="Sua marca"></div>
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
  </div>
  ${bilheteNiet("niet-instalacao", "papel niet-instalacao",
    `<h2 class="subtitulo">Quer mudar alguma coisa?</h2>
     <p class="explica">O TopClip é código aberto: dá para mudar uma tela, criar um recurso ou fazer outra ferramenta do zero. Quer aprender a fazer isso começando do zero? O primeiro passo é o curso de Lovable do NIET Clube.</p>`,
    `<a class="link" href="${linkNiet("instalacao")}" target="_blank" rel="noopener">começar pelo Lovable →</a>`)}`;
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
