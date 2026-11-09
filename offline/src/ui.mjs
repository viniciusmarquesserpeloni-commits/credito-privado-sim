// Interface do HTML offline (visual do painel "Relatório de Fundos").
// Tudo roda neste navegador: arquivos lidos em memória, nada enviado, gravado ou registrado.
import * as E from "./engine.mjs";
import * as P from "./parsers.mjs";
import * as A from "./analysis.mjs";
import * as X from "./xlsx.mjs";

const DATA = JSON.parse(document.getElementById("cpsim-data").textContent);
const $ = (sel, root = document) => root.querySelector(sel);
const h = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const b64bytes = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const num = (v) => { if (v == null || String(v).trim() === "") return null; const n = Number(String(v).trim().replace(/\./g, "").replace(",", ".")); return Number.isFinite(n) ? n : null; };
const numPlain = (v) => { if (v == null || String(v).trim() === "") return null; const n = Number(String(v).trim().replace(",", ".")); return Number.isFinite(n) ? n : null; };

const DEFAULTS = {
  qualificado: false, investidor: "PF", horizonte: 1, cenario: "base", cdiUsuario: 14, ipcaUsuario: 4.5,
  bandaDuration: 1.5, toleranciaRating: 0, aceitarSemRating: false, modoAmplo: false, mesmaTributacao: true,
  incluirSemPreco: false, limiteEmissor: 20, limiteSetor: 40, classeLiquidez: "media",
  bAlta: 10, bMedia: 25, bBaixa: 50, recDelta: 30, recPayback: 1, margDelta: 10, margPayback: 2,
};
const S = { route: "dados", mode: "interno", useSamples: false, files: {}, params: { ...DEFAULTS }, overrides: {}, fixes: {},
  mapaRaw: null, runflowSheets: null, busy: "", error: "", filtro: "todas", version: 0, cache: {} };
const PUBLIC = P.publicFromPayloads(DATA.public);
const L = (t) => A.sanitize(t, S.mode);
const interno = () => S.mode === "interno";

// ------------------------------------------------------------------------------- pdf.js
let pdfjs = null;
const blobUrl = (id) => URL.createObjectURL(new Blob([b64bytes(document.getElementById(id).textContent)], { type: "text/javascript" }));
async function extractFragments(bytes) {
  if (!pdfjs) { pdfjs = await import(blobUrl("pdfjs-lib")); pdfjs.GlobalWorkerOptions.workerSrc = blobUrl("pdfjs-worker"); }
  const doc = await pdfjs.getDocument({ data: bytes.slice(), isEvalSupported: false }).promise;
  const frags = [];
  for (let p = 1; p <= doc.numPages; p++) {
    const tc = await (await doc.getPage(p)).getTextContent();
    for (const it of tc.items) { const t = (it.str || "").trim(); if (t) frags.push({ page: p, x: Math.round(it.transform[4] * 100) / 100, y: Math.round(it.transform[5] * 100) / 100, text: t }); }
  }
  return { frags, nPages: doc.numPages };
}

// ------------------------------------------------------------------------------- dados
function fileBytes(kind) {
  if (S.useSamples) return kind === "mapa" ? b64bytes(DATA.samples.mapa) : kind === "runflow" ? b64bytes(DATA.samples.runflow) : null;
  return S.files[kind]?.bytes || null;
}
async function loadFiles() {
  S.error = "";
  try {
    const pdf = fileBytes("mapa"), xlsx = fileBytes("runflow");
    S.busy = pdf || xlsx ? "Lendo arquivos…" : ""; render();
    if (pdf) { const t0 = performance.now(); const { frags, nPages } = await extractFragments(pdf); S.mapaRaw = P.parseMapaFragments(frags, nPages); S.mapaMs = performance.now() - t0; } else S.mapaRaw = null;
    S.runflowSheets = xlsx ? await X.readXlsx(xlsx) : null;
  } catch (e) { S.error = `Não foi possível ler os arquivos: ${e.message || e}`; }
  S.busy = ""; S.version++; render();
}
const internalCols = () => (S.useSamples || !S.files.cfg ? P.parseInternalColumns(DATA.exampleToml, S.useSamples ? "exemplo" : "exemplo (sem .toml carregado)") : P.parseInternalColumns(S.files.cfg.text, S.files.cfg.name));
function memo(key, fn) {
  const k = `${key}:${S.version}`;
  if (!(k in S.cache)) {
    for (const kk of Object.keys(S.cache)) if (!kk.endsWith(`:${S.version}`)) delete S.cache[kk];
    let v = null;
    try { v = fn(); } catch (e) { S.calcError = `${key}: ${e.message || e}`; console.error(e); }
    S.cache[k] = v; // atribuição DEPOIS de fn(): cálculos aninhados também gravam no cache
  }
  return S.cache[k];
}
function mapa() {
  return memo("mapa", () => {
    if (!S.mapaRaw) return null;
    const m = structuredClone(S.mapaRaw);
    for (const [i, fx] of Object.entries(S.fixes)) {
      const lot = m.lots[Number(i)]; if (!lot) continue;
      for (const [k, v] of Object.entries(fx)) { if (k === "rateText") { lot.rateText = v; lot.rate = P.parseRateText(v); } else lot[k] = v; }
      P.validateLot(lot);
    }
    return m;
  });
}
const runflow = () => memo("runflow", () => (S.runflowSheets ? P.readRunflowSheets(S.runflowSheets, internalCols()) : null));
const asOf = () => mapa()?.positionDate ?? E.todayDn();
function scenario() {
  const p = S.params;
  return memo("sc", () => (p.cenario === "usuario" ? P.userScenario(p.cdiUsuario / 100, p.ipcaUsuario / 100, p.horizonte) : P.baseScenario(PUBLIC, asOf(), p.horizonte)));
}
function swapParams() {
  const p = S.params;
  return A.swapParams({ qualifiedInvestor: p.qualificado, durationBand: p.bandaDuration, sameTax: p.mesmaTributacao, sameIndexer: !p.modoAmplo,
    ratingTolerance: p.toleranciaRating, acceptUnrated: p.aceitarSemRating, issuerLimit: p.limiteEmissor / 100, sectorLimit: p.limiteSetor / 100,
    liquidityClass: p.classeLiquidez, bidAskByClass: { alta: p.bAlta / 1e4, media: p.bMedia / 1e4, baixa: p.bBaixa / 1e4 },
    recMinDelta: p.recDelta / 1e4, recMaxPayback: p.recPayback, margMinDelta: p.margDelta / 1e4, margMaxPayback: p.margPayback, policy: E.taxPolicy(p.investidor) });
}
const enriched = () => memo("en", () => { const m = mapa(); if (!m || m.positionDate == null) return null; const rf = runflow(); return A.enrich(m, scenario(), rf ? rf.candidates : null, S.overrides, { includeWithoutMarketPrice: S.params.incluirSemPreco, policy: E.taxPolicy(S.params.investidor) }); });
const report = () => memo("rep", () => { const en = enriched(), rf = runflow(); if (!en || !rf) return null; return A.runSwaps(en, rf.candidates, scenario(), asOf(), swapParams(), P.ntnbQuotes(PUBLIC)[0]); });
function changed() { S.version++; render(); }

// ------------------------------------------------------------------------------- componentes
const kpi = (label, value, hint = "") => `<div class="card kpi"><div class="label">${h(label)}</div><div class="value num">${value}</div>${hint ? `<div class="hint">${h(hint)}</div>` : ""}</div>`;
const pageHead = (title, desc, aside = "") => `<div class="page-head"><div><h2>${h(title)}</h2><p>${desc}</p></div>${aside ? `<div class="aside">${aside}</div>` : ""}</div>`;
const kindBadge = (k) => (k === A.KIND.ESTIMATIVA ? '<span class="badge est">estimativa</span>' : k === A.KIND.APROXIMACAO ? '<span class="badge apx">aproximação</span>' : '<span class="badge dado">dado</span>');
const CLS_BADGE = { [A.CLS.RECOMENDADA]: "rec", [A.CLS.MARGINAL]: "marg", [A.CLS.MANTER]: "manter", [A.CLS.SEM_TAXA]: "fora", [A.CLS.FORA]: "fora" };
const clsBadge = (c) => `<span class="badge ${CLS_BADGE[c] || "manter"}">${h(c)}</span>`;
const signed = (v) => (v == null ? "—" : `<span class="${v >= 0 ? "pos" : "neg"}">${h(E.fmtBrl(v))}</span>`);
const fmtYears = (v) => (v == null ? "—" : E.fmtNum(v, 2));
const needData = (what = "o Mapa de Posições e o Runflow") => `<div class="card empty"><h3>Sem dados carregados</h3><p>${h(L(`Carregue ${what} na aba Dados, ou use as amostras fictícias.`))}</p><p><a class="btn primary" href="#/dados">Ir para Dados</a></p></div>`;

// ------------------------------------------------------------------------------- telas
function viewDados() {
  const m = mapa(), rf = runflow();
  const drop = (kind, title, accept, req) => {
    const f = S.useSamples ? (kind === "cfg" ? null : { name: "amostra fictícia" }) : S.files[kind];
    return `<label class="drop" data-drop="${kind}"><div class="title">${h(L(title))}</div><div class="small muted">${req ? "obrigatório" : "opcional"} · arraste aqui ou</div>
      <span class="btn" style="margin-top:8px">Escolher arquivo</span><input type="file" accept="${accept}" data-file="${kind}" ${S.useSamples ? "disabled" : ""}>
      <div class="file">${f ? `✓ ${h(f.name)}` : "nenhum arquivo"}</div></label>`;
  };
  const col = P.oldestCollection(PUBLIC);
  const fresh = P.freshness(PUBLIC, E.todayDn());
  const stale = fresh.filter((f) => f.stale).map((f) => f.name);
  const [cdi0] = PUBLIC.cdiDaily.length ? P.currentCdi(PUBLIC) : [null];
  const [ntnb, ntnbBase] = P.ntnbQuotes(PUBLIC);
  let erros = "";
  if (m && m.lots.some((l) => l.errors.length)) {
    const rows = m.lots.map((l, i) => [l, i]).filter(([l]) => l.errors.length).map(([l, i]) => `<tr data-lot="${i}"><td class="l">${i + 1}</td><td class="l wrap small">${h(l.errors.join("; "))}</td>
      <td><input class="input" data-fix="code" value="${h(l.code ?? "")}"></td><td><input class="input" data-fix="rateText" value="${h(l.rateText ?? "")}"></td>
      ${["quantity", "puCurve", "grossCurve", "puMarket", "grossMarket", "ir", "iof", "netValue"].map((k) => `<td><input class="input n" data-fix="${k}" value="${l[k] == null ? "" : h(E.fmtNum(l[k], k === "quantity" ? 0 : 2))}"></td>`).join("")}</tr>`).join("");
    erros = `<div class="section-title">Linhas com erro — corrija e aplique</div><div class="card"><div class="card-b"><p class="small muted">Confira no PDF e corrija. Linhas com erro ficam fora da análise.</p></div>
      <div class="table-wrap"><table class="data"><thead><tr><th class="l">Linha</th><th class="l">Erros</th><th>Código</th><th>Taxa Operação</th><th>Qtd</th><th>PU Curva</th><th>VB curva</th><th>PU Mercado</th><th>VB mercado</th><th>IR</th><th>IOF</th><th>V. líquido</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="card-b"><button class="btn primary" data-action="aplicar-fixes">Aplicar correções</button></div></div>`;
  } else if (m) erros = `<div class="ok-note" style="margin-top:16px">Todas as linhas do Mapa passaram na validação (Quantidade × PU ≈ Valor Bruto).</div>`;
  return pageHead("Dados", h(L("Envie o Mapa de Posições (PDF) e o Runflow (XLSX). Os arquivos são lidos neste navegador: nada é enviado, gravado ou registrado. Ao fechar a página, tudo some.")),
    `Versão offline · gerada em ${h(DATA.build.date)}`) +
    `<div class="card"><div class="card-b"><div class="grid g-3">${drop("mapa", "Mapa de Posições (PDF)", ".pdf,application/pdf", true)}${drop("runflow", "Runflow (XLSX)", ".xlsx", true)}${drop("cfg", "Colunas internas (.toml)", ".toml,text/plain", false)}</div>
      <div class="toolbar" style="margin-top:14px"><button class="chip" aria-pressed="${S.useSamples}" data-action="amostras">Usar amostras fictícias</button>
      ${!S.useSamples && Object.keys(S.files).length ? '<button class="btn ghost" data-action="descartar">Descartar arquivos</button>' : ""}
      <span class="small muted">${h(L("O .toml traz os nomes reais das colunas internas do Runflow (config/runflow_columns.local.toml). Fica só na memória."))}</span></div>
      ${S.busy ? `<div class="warn-note" style="margin-top:12px">${h(S.busy)}</div>` : ""}${S.error ? `<div class="warn-note" style="margin-top:12px">${h(S.error)}</div>` : ""}</div></div>
    <div class="section-title">Situação dos arquivos</div><div class="grid g-3">
      <div class="card"><div class="card-h"><h3>Mapa de Posições</h3><span class="sub">${m ? (S.useSamples ? "amostra fictícia" : h(S.files.mapa?.name || "")) : "não carregado"}</span></div><div class="card-b">
        ${m ? `<dl class="kv"><dt>Data da posição</dt><dd>${E.brDate(m.positionDate)}</dd><dt>Páginas</dt><dd>${m.nPages}</dd><dt>Lotes</dt><dd>${m.lots.length}</dd><dt>Posições</dt><dd>${P.positionsOf(m).length}</dd><dt>Lotes com erro</dt><dd>${m.lots.filter((l) => l.errors.length).length}</dd><dt>Leitura</dt><dd>${S.mapaMs ? `${E.fmtNum(S.mapaMs / 1000, 1)} s` : "—"}</dd></dl>${m.warnings.map((w) => `<div class="warn-note" style="margin-top:8px">${h(w)}</div>`).join("")}` : '<p class="muted">Envie o PDF do Mapa de Posições.</p>'}</div></div>
      <div class="card"><div class="card-h"><h3>${h(L("Runflow"))}</h3><span class="sub">${rf ? (S.useSamples ? "amostra fictícia" : h(S.files.runflow?.name || "")) : "não carregado"}</span></div><div class="card-b">
        ${rf ? `<dl class="kv"><dt>Papéis</dt><dd>${rf.candidates.length}</dd><dt>Distribuição ativa</dt><dd>${rf.candidates.filter((c) => c.active).length}</dd><dt>Colunas não encontradas</dt><dd>${rf.missing.length ? h(rf.missing.join(", ")) : "nenhuma"}</dd>
          ${interno() ? `<dt>Colunas ignoradas</dt><dd>${rf.extra.length ? h(rf.extra.join(", ")) : "nenhuma"}</dd><dt>Nomes das colunas internas</dt><dd>${h(rf.columnsSource)}</dd>` : ""}</dl>${rf.warnings.map((w) => `<div class="warn-note" style="margin-top:8px">${h(w)}</div>`).join("")}` : `<p class="muted">${h(L("Envie a planilha do Runflow."))}</p>`}</div></div>
      <div class="card"><div class="card-h"><h3>Dados públicos</h3><span class="sub">embutidos neste arquivo</span></div><div class="card-b">
        <dl class="kv"><dt>Coletados em</dt><dd>${col != null ? E.brDate(col) : "—"}</dd><dt>CDI atual (SGS 12)</dt><dd>${E.fmtPct(cdi0)}</dd><dt>Focus Selic / IPCA</dt><dd>${E.brDate(PUBLIC.focusSelicDate)} / ${E.brDate(PUBLIC.focusIpcaDate)}</dd><dt>NTN-B (Tesouro Direto)</dt><dd>${ntnb.length} vencimentos · ${E.brDate(ntnbBase)}</dd></dl>
        ${stale.length ? `<div class="warn-note" style="margin-top:8px">Dados com mais de ${P.MAX_IDADE_DIAS_UTEIS} dias úteis: ${h(stale.join(", "))}. Gere o HTML de novo para atualizar, ou use o cenário do usuário em Parâmetros.</div>` : ""}
        <p class="small muted" style="margin-top:8px">Tesouro Direto = taxas de varejo (referência de NTN-B).</p></div></div>
    </div>${erros}`;
}

function field(key, label, help = "", step = "any") {
  return `<div class="f-row"><label for="p-${key}">${h(label)}${help ? `<div class="help">${h(help)}</div>` : ""}</label><input class="input" id="p-${key}" data-param="${key}" inputmode="decimal" value="${h(String(S.params[key]).replace(".", ","))}"></div>`;
}
const check = (key, label, help = "") => `<label class="f-check"><input type="checkbox" data-param="${key}" ${S.params[key] ? "checked" : ""}>${h(label)}</label>${help ? `<div class="help">${h(help)}</div>` : ""}`;
const seg = (key, opts) => `<div class="seg">${opts.map(([v, t]) => `<button data-seg="${key}" data-value="${v}" aria-pressed="${S.params[key] === v}">${h(t)}</button>`).join("")}</div>`;
function viewParametros() {
  const sc = scenario();
  return pageHead("Parâmetros", "Limiares e custos são hipóteses ainda não validadas por backtest. As mudanças valem na hora para Carteira e Trocas.", `<button class="btn" data-action="padroes">Restaurar padrões</button>`) +
    `<div class="grid g-2">
     <div class="card"><div class="card-h"><h3>Investidor e saída</h3></div><div class="card-b">
       <div class="f-group"><span class="f-label">Modo de saída</span><div class="seg"><button data-action="modo" data-value="interno" aria-pressed="${interno()}">Interno</button><button data-action="modo" data-value="cliente" aria-pressed="${!interno()}">Cliente</button></div><div class="help">${h(L("Cliente: sem colunas internas, sem estoque da mesa e sem menção ao Runflow interno."))}</div></div>
       <div class="f-group"><span class="f-label">Tipo</span>${seg("investidor", [["PF", "Pessoa física"], ["PJ", "Pessoa jurídica"]])}<div class="help">PJ não tem isenção de IR.</div></div>
       <div class="f-group">${check("qualificado", "Investidor qualificado")}${field("horizonte", "Horizonte (anos)")}</div></div></div>
     <div class="card"><div class="card-h"><h3>Cenário de CDI e IPCA</h3></div><div class="card-b">
       <div class="f-group">${seg("cenario", [["base", "Base (Focus)"], ["usuario", "Do usuário"]])}</div>
       ${S.params.cenario === "usuario" ? `<div class="f-group">${field("cdiUsuario", "CDI médio no horizonte (% a.a.)")}${field("ipcaUsuario", "IPCA médio no horizonte (% a.a.)")}</div>` : ""}
       <div class="f-group small">Em uso: <b>${h(sc.name)}</b> — CDI ${E.fmtPct(sc.cdi)}, IPCA ${E.fmtPct(sc.ipca)}<div class="help">${h(sc.cdiSource)}. ${h(sc.note)}</div></div></div></div>
     <div class="card"><div class="card-h"><h3>Filtros de elegibilidade</h3></div><div class="card-b">
       <div class="f-group">${field("bandaDuration", "Banda de duration (± anos)")}${field("toleranciaRating", "Tolerância de rating (degraus abaixo)")}</div>
       <div class="f-group">${check("aceitarSemRating", "Aceitar papéis sem rating", "Sem rating em qualquer lado: só passa se você confirmar aqui.")}${check("mesmaTributacao", "Exigir mesma tributação (isento → isento)")}${check("modoAmplo", "Modo amplo: permitir outro indexador", "Compara pela taxa nominal esperada no cenário.")}${check("incluirSemPreco", "Incluir posições sem PU Mercado (CDB, CPR…)")}</div>
       <div class="f-group">${field("limiteEmissor", "Limite por emissor após a troca (% do total)")}${field("limiteSetor", "Limite por setor após a troca (% do total)")}</div></div></div>
     <div class="card"><div class="card-h"><h3>Custos e classificação</h3></div><div class="card-b">
       <div class="f-group"><span class="f-label">Custo de saída (cenário B)</span><div class="help" style="margin-bottom:8px">b = taxa de venda − taxa de compra; custo ≈ b/2 × duration modificada × valor (padrões hipotéticos).</div>
         ${seg("classeLiquidez", [["alta", "Liquidez alta"], ["media", "Média"], ["baixa", "Baixa"]])}${field("bAlta", "b — alta (bps)")}${field("bMedia", "b — média (bps)")}${field("bBaixa", "b — baixa (bps)")}</div>
       <div class="f-group"><span class="f-label">Limiares (cenário B)</span>${field("recDelta", "Recomendada: Δ mínimo (bps)")}${field("recPayback", "Recomendada: equilíbrio máx. (anos)")}${field("margDelta", "Marginal: Δ mínimo (bps)")}${field("margPayback", "Marginal: equilíbrio máx. (anos)")}</div></div></div>
    </div>`;
}

function viewCarteira() {
  const m = mapa();
  if (!m) return pageHead("Carteira", "Taxa de mercado e duration de cada posição, com a fonte de cada número.") + needData("o Mapa de Posições");
  const en = enriched();
  if (!en) return pageHead("Carteira", "") + `<div class="warn-note">O Mapa não tem data da posição; não é possível estimar taxas.</div>`;
  const esc = en.filter((e) => e.inScope);
  const rows = en.map((e) => {
    const p = e.position, mr = e.marketRate, du = e.duration;
    return `<tr><td class="l"><div class="name">${h(e.code)}</div><div class="meta">${h(p.assetType || "")} · ${h(p.issuer)}</div></td><td class="l">${h(e.indexer || "—")}</td><td>${E.brDate(p.maturity)}</td>
      <td class="num">${h(E.fmtBrl(p.netValue))}</td><td class="num">${h(mr ? E.rateStr({ indexer: e.indexer, value: mr.value }) : "—")}<div class="meta">${mr ? kindBadge(mr.kind) : ""}</div></td>
      <td class="l wrap small">${h(mr ? L(mr.source) : "—")}</td><td class="num">${du ? E.fmtNum(du.value, 2) : "—"}<div class="meta">${h(du ? L(du.source) : "")}</div></td>
      <td>${h(e.rating.label || "—")}</td><td>${e.taxExempt.value ? '<span class="badge isento">isento</span>' : "tributado"}</td><td class="num">${signed(e.mtmVsCurve)}</td>
      ${interno() ? `<td class="num">${e.deskSpread == null ? "—" : E.fmtNum(e.deskSpread * 1e4, 1) + " bps"}${e.review ? ' <span class="badge rev">revisar</span>' : ""}</td>` : ""}
      <td class="l">${e.inScope ? "sim" : `<span class="muted">não</span><div class="meta">${h(e.scopeNote)}</div>`}</td>
      <td class="l wrap small">${e.alerts.length ? e.alerts.map((a) => `• ${h(L(a))}`).join("<br>") : "—"}</td></tr>`;
  }).join("");
  const ovRows = esc.map((e) => {
    const o = S.overrides[e.code] || {};
    return `<tr data-ov="${h(e.code)}"><td class="l"><div class="name">${h(e.code)}</div><div class="meta">${h(L(e.flow))}</div></td>
      <td><input class="input" data-ovf="coupon" placeholder="ex.: Mar/Set" value="${h(o.coupon ?? "")}"></td><td><input class="input" data-ovf="amortization" placeholder="ex.: Anual (Início 2033)" value="${h(o.amortization ?? "")}"></td>
      <td><input class="input n" data-ovf="duration" inputmode="decimal" value="${o.duration == null ? "" : E.fmtNum(o.duration, 2)}"></td><td><input class="input n" data-ovf="marketRate" inputmode="decimal" value="${o.marketRate == null ? "" : E.fmtNum(o.marketRate * 100, 4)}"></td></tr>`;
  }).join("");
  return pageHead("Carteira", "Taxa de mercado estimada pela razão PU Mercado / PU Curva com o fluxo do papel, duration e marcação a mercado. Papéis sem PU Mercado (CDB, CPR) ficam fora por padrão.", `Posição de ${E.brDate(m.positionDate)}`) +
    (!runflow() ? `<div class="warn-note">${h(L("Sem Runflow: todas as taxas saem pelo fluxo padrão (juros semestrais, amortização no vencimento) e não há candidatos de troca."))}</div>` : "") +
    `<div class="grid g-4">${kpi("Valor líquido total", h(E.fmtBrl(en.reduce((s, e) => s + e.netValue, 0))), "Soma do Mapa (já líquido de IR/IOF)")}${kpi("Posições na análise", `${esc.length} <span class="small muted">de ${en.length}</span>`, "DEB, CRI e CRA com PU Mercado")}
      ${kpi("Com taxa de mercado", String(esc.filter((e) => e.marketRate).length), "estimada, informada ou aproximada")}
      ${interno() ? kpi("Marcadas para revisão", String(en.filter((e) => e.review).length), "spread estimado da mesa > 150 bps") : kpi("Com alerta", String(esc.filter((e) => e.alerts.length).length), "veja a coluna Alertas")}</div>
    <div class="section-title">Posições</div><div class="card"><div class="table-wrap"><table class="data"><thead><tr><th class="l">Papel</th><th class="l">Indexador</th><th>Vencimento</th><th>Valor líquido</th><th>Taxa de mercado</th><th class="l">Fonte da taxa</th><th>Duration</th><th>Rating</th><th>Tributação</th><th>Marcação vs curva</th>${interno() ? "<th>Spread da mesa</th>" : ""}<th class="l">Na análise</th><th class="l">Alertas</th></tr></thead><tbody>${rows}</tbody></table></div></div>
    <div class="section-title">Informar fluxo, duration ou taxa</div><div class="card"><div class="card-b"><p class="small muted">${h(L("Campos vazios = usa a estimativa. Cupom e amortização no formato do Runflow (\"Mar/Set\", \"Anual (Início 2033)\", \"Bullet\"). Taxa em % — para %CDI, em % do CDI (ex.: 104,5)."))}</p></div>
      ${esc.length ? `<div class="table-wrap"><table class="data"><thead><tr><th class="l">Papel / fluxo em uso</th><th>Cupom</th><th>Amortização</th><th>Duration (anos)</th><th>Taxa (%)</th></tr></thead><tbody>${ovRows}</tbody></table></div>
      <div class="card-b toolbar"><button class="btn primary" data-action="aplicar-ov">Aplicar</button>${Object.keys(S.overrides).length ? '<button class="btn ghost" data-action="limpar-ov">Limpar sobrescritas</button>' : ""}</div>` : '<div class="card-b muted">Nenhuma posição na análise.</div>'}</div>`;
}

function viewTrocas() {
  if (!mapa() || !runflow()) return pageHead("Trocas", "") + needData();
  const rep = report(), rf = runflow();
  if (!rep) return pageHead("Trocas", "") + `<div class="warn-note">Não foi possível rodar o motor${S.calcError ? `: ${h(S.calcError)}` : " (Mapa sem data da posição?)"}.</div>`;
  const cont = {}; for (const r of rep.results) cont[r.status] = (cont[r.status] || 0) + 1;
  const sum = A.summaryTable(rep);
  const ordem = { [A.CLS.RECOMENDADA]: 0, [A.CLS.MARGINAL]: 1, [A.CLS.MANTER]: 2, [A.CLS.SEM_TAXA]: 3, [A.CLS.FORA]: 4 };
  const filtros = [["todas", "Todas"], ["rec", "Recomendadas"], ["marg", "Marginais"], ["manter", "Manter"], ["fora", "Sem taxa / fora"]];
  const passa = (st) => S.filtro === "todas" || CLS_BADGE[st] === S.filtro;
  const labels = rf.internalLabels;
  const blocks = [...rep.results].sort((a, b) => (ordem[a.status] - ordem[b.status]) || (b.holding.netValue - a.holding.netValue)).filter((r) => passa(r.status)).map((r) => {
    const hd = r.holding;
    let body;
    if (r.status === A.CLS.FORA) body = `<p class="muted">Fora da análise: ${h(hd.scopeNote)}.</p>`;
    else if (r.status === A.CLS.SEM_TAXA) body = `<p class="muted">Sem taxa de mercado: informe a taxa ou o fluxo na aba Carteira.</p>`;
    else if (!r.best.length) body = `<p class="muted">Nenhum candidato elegível entre ${r.evaluated} avaliados. Reprovações por filtro: ${h(L(Object.entries(r.rejectedBy).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} (${v})`).join(", ")) || "—")}.</p>`;
    else {
      const table = `<div class="table-wrap inline"><table class="compact"><thead><tr><th class="l">#</th><th class="l">Candidato</th><th>Taxa</th><th>Duration</th><th>Rating</th><th>Δ usado</th><th>Ganho anual</th><th>Saída (B)</th><th>Imposto</th><th>Equilíbrio A / B</th><th>A</th><th>B</th>${interno() ? `<th>${h(A.LASTRO_COL)}</th>${Object.values(labels).map((l) => `<th>${h(l)}</th>`).join("")}` : ""}</tr></thead><tbody>
        ${r.best.map((b, k) => { const c = b.candidate; return `<tr><td class="l">${k + 1}</td><td class="l"><b>${h(c.code)}</b><div class="small muted">${h(c.issuer)}</div></td><td>${h(E.rateStr(c.rate))}</td><td>${fmtYears(c.duration)}</td><td>${h(c.rating.label || "—")}</td>
          <td>${h(E.fmtBps(b.deltaMetric, 1))}<div class="small muted">${h(b.deltaMetricName)}</div></td><td>${signed(b.gainAnnual)}</td><td>${h(E.fmtBrl(b.exitCostB))}</td><td>${h(E.fmtBrl(b.taxAnticipated))}</td><td>${fmtYears(b.paybackA)} / ${fmtYears(b.paybackB)}</td><td>${clsBadge(b.classA)}</td><td>${clsBadge(b.classB)}</td>
          ${interno() ? `<td>${h(E.fmtBrl(c.lastro))}</td>${Object.keys(labels).map((f) => `<td>${h(fmtInternal(c.internal?.[f]))}</td>`).join("")}` : ""}</tr>`; }).join("")}</tbody></table></div>`;
      const just = r.best.map((b) => `<div class="cand"><h4>Justificativa — ${h(b.candidate.code)}</h4><ul class="qc-list">${A.justification(b, S.mode).split(" | ").map((part) => {
        const icon = part.startsWith("✓") ? '<span class="ok">✓</span>' : part.startsWith("✗") ? '<span class="ko">✗</span>' : '<span class="nt">•</span>';
        return `<li>${icon}<span>${h(part.replace(/^[✓✗]\s*/, ""))}</span></li>`; }).join("")}</ul></div>`).join("");
      body = table + (hd.alerts.length ? `<p class="small muted" style="margin-top:10px">Alertas da posição: ${h(L(hd.alerts.join("; ")))}</p>` : "") + just +
        `<p class="small muted" style="margin-top:10px">${r.evaluated} candidatos avaliados; reprovações por filtro: ${h(L(Object.entries(r.rejectedBy).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} (${v})`).join(", ")))}</p>`;
    }
    return `<details class="pos" ${r.status === A.CLS.RECOMENDADA ? "open" : ""}><summary><span class="code">${h(hd.code)}</span><span class="meta">${h(hd.position.issuer)} · ${h(E.fmtBrl(hd.netValue))} · taxa ${h(hd.marketRate ? E.rateStr({ indexer: hd.indexer, value: hd.marketRate.value }) : "—")}</span>
      <span class="right">${interno() && hd.review ? '<span class="badge rev">revisar</span> ' : ""}${clsBadge(r.status)}</span></summary><div class="body">${body}</div></details>`;
  }).join("");
  return pageHead("Trocas", `${h(A.AVISO)} Classificação pelo cenário B (PU Mercado = marcação); o ranking usa só a economia do cliente${interno() ? "; o fee da mesa não entra no ranking nem na classificação" : ""}.`,
    `Cenário ${h(rep.scenario.name)} · CDI ${E.fmtPct(rep.scenario.cdi)} · IPCA ${E.fmtPct(rep.scenario.ipca)}`) +
    `<div class="card kpi-strip">${[["Troca recomendada", cont[A.CLS.RECOMENDADA] || 0], ["Troca marginal", cont[A.CLS.MARGINAL] || 0], ["Manter", cont[A.CLS.MANTER] || 0], ["Sem taxa / fora", (cont[A.CLS.SEM_TAXA] || 0) + (cont[A.CLS.FORA] || 0)]].map(([l, v]) => `<div class="kpi"><div class="label">${l}</div><div class="value num">${v}</div></div>`).join("")}
      <div class="kpi"><div class="label">Ganho anual estimado</div><div class="value num">${h(E.fmtBrl(rep.totalGainAnnual))}</div><div class="hint">trocas recomendadas aplicadas</div></div></div>
    <div class="grid g-2" style="margin-top:16px"><div class="card"><div class="card-h"><h3>Carteira antes e depois</h3><span class="sub">comparações entre indexadores dependem do cenário</span></div><div class="card-b"><div class="table-wrap inline"><table class="compact"><thead><tr><th>Item</th><th class="l">Antes</th><th class="l">Depois</th></tr></thead><tbody>
      ${sum.map((s) => `<tr><td>${h(s.Item)}</td><td class="l">${h(s.Antes)}</td><td class="l">${h(s.Depois)}</td></tr>`).join("")}</tbody></table></div>${rep.alerts.map((a) => `<div class="warn-note" style="margin-top:8px">${h(a)}</div>`).join("")}</div></div>
      <div class="card"><div class="card-h"><h3>Exportar</h3><span class="sub">modo ${h(S.mode)}</span></div><div class="card-b"><p class="small muted">Planilha com Carteira, Trocas, Resumo e Premissas. ${interno() ? "Inclui colunas internas: não envie ao cliente." : "Sem colunas internas: pode ser enviada ao cliente."}</p>
      <button class="btn primary" data-action="exportar">Exportar Excel (modo ${h(S.mode)})</button><p class="small muted" style="margin-top:8px">Gerado neste navegador; o arquivo vai direto para a sua máquina.</p></div></div></div>
    <div class="toolbar" style="margin:22px 0 12px"><span class="section-title" style="margin:0">Por posição</span><div class="chips">${filtros.map(([v, t]) => `<button class="chip" data-filtro="${v}" aria-pressed="${S.filtro === v}">${t}</button>`).join("")}</div></div>
    ${blocks || '<div class="card empty"><h3>Nenhuma posição neste filtro</h3></div>'}`;
}
function fmtInternal(v) { if (v == null || v === "") return "—"; if (typeof v === "number") return Math.abs(v) < 1 ? E.fmtPct(v) : E.fmtNum(v, 2); return String(v); }

function mdToHtml(md) {
  const inline = (s) => h(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const out = []; const lines = md.split(/\r?\n/); let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) { const buf = []; i++; while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]); i++; out.push(`<pre>${h(buf.join("\n"))}</pre>`); continue; }
    const hm = l.match(/^(#{1,4})\s+(.*)$/); if (hm) { const lv = Math.min(4, hm[1].length + 1); out.push(`<h${lv}>${inline(hm[2])}</h${lv}>`); i++; continue; }
    if (l.startsWith("|")) { const rows = []; while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]); const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = rows.filter((r, k) => !(k === 1 && /^\|?\s*:?-{3,}/.test(r))); out.push(`<div class="table-wrap inline"><table>${body.map((r, k) => `<tr>${cells(r).map((c) => (k === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join("")}</tr>`).join("")}</table></div>`); continue; }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) { const items = []; while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "")); out.push(`<ul>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ul>`); continue; }
    if (l.startsWith(">")) { out.push(`<div class="disclaimer">${inline(l.replace(/^>\s?/, ""))}</div>`); i++; continue; }
    if (!l.trim()) { i++; continue; }
    const buf = [l]; i++; while (i < lines.length && lines[i].trim() && !/^(#|\||```|>|\s*([-*]|\d+\.)\s)/.test(lines[i])) buf.push(lines[i++]); out.push(`<p>${inline(buf.join(" "))}</p>`);
  }
  return out.join("\n");
}
function viewMetodologia() {
  return pageHead("Metodologia e fontes", "Como os números são calculados, de onde vêm os dados e o que a ferramenta não faz.") +
    `<div class="disclaimer" style="margin-bottom:16px">${h(A.AVISO)}</div><div class="card"><div class="card-b prose">
    <h3>O que a ferramenta faz</h3><p>${h(L("Para cada posição do Mapa, estima a taxa de mercado e a duration, procura no Runflow papéis elegíveis para a troca e calcula a economia do cliente depois de custos e impostos."))}</p>
    <h3>Taxa de mercado das posições</h3><p>É a taxa <i>y</i> que faz PU(y) / PU(taxa de operação) igualar PU Mercado / PU Curva, com o mesmo fluxo nos dois lados. O VNA se cancela, porque o PU Curva é o PU na taxa de operação. ${h(L("O fluxo vem do Runflow quando o papel está lá; senão, a premissa padrão é de juros semestrais e amortização no vencimento."))} O resultado é uma <b>estimativa</b>. Lotes do mesmo papel que divergem mais de 10 bps geram alerta. Na aba Carteira dá para informar o fluxo, a duration ou a taxa.</p>
    <span class="formula">PU(y) / PU(taxa_op) = PU_Mercado / PU_Curva        PU = Σ FC_i / (1 + y)^(du_i/252)</span>
    <h3>Elegibilidade do candidato</h3><ul><li>Distribuição ativa e estoque suficiente; perfil do investidor.</li><li>Mesma tributação e mesmo indexador (o modo amplo compara a taxa nominal esperada).</li><li>Diferença de duration até 1,5 ano; rating igual ou melhor.</li><li>Concentração por emissor e setor dentro dos limites.</li></ul>
    <h3>Economia</h3><p>Ganho anual = valor de saída × diferença de taxa nominal esperada no cenário. O cenário <b>A</b> trata o PU Mercado como preço executável, sem custo de saída. O cenário <b>B</b> trata o PU Mercado como marcação.</p>
    <span class="formula">custo de saída (B) ≈ b/2 × D_mod × V      imposto antecipado ≈ IR × [1 − (1 + r)^(−prazo)] + IOF      equilíbrio = custos ÷ ganho anual</span>
    <p>Nos papéis IPCA+, o Δ usado é o spread sobre a NTN-B de referência: s = (1 + r)/(1 + r_NTN-B) − 1, com a NTN-B do Tesouro Direto (taxa de varejo).</p>
    <h3>Classificação (cenário B, hipóteses)</h3><ul><li><b>Recomendada</b>: Δ ≥ 30 bps e equilíbrio ≤ 1 ano.</li><li><b>Marginal</b>: Δ ≥ 10 bps e equilíbrio ≤ 2 anos.</li><li><b>Manter</b>: os demais casos. Quando os cenários A e B divergem, a tela avisa.</li></ul><p>O ranking usa só a economia do cliente.</p>
    <h3>Limitações</h3><ul><li>A premissa de amortização no vencimento erra mais quanto maior a distância entre a taxa de mercado e a de operação e quanto mais cedo o papel amortiza; a duration fica superestimada.</li>
      <li>CDI e IPCA esperados vêm do Focus, que é expectativa de mercado e não previsão; as datas das reuniões do Copom são aproximadas.</li><li>O Tesouro Direto é taxa de varejo, não de mercado secundário.</li><li>Tabelas de IR e IOF e isenções são parâmetros: confirmar a vigência.</li><li>Os dados públicos estão embutidos neste arquivo e envelhecem: veja a data na aba Dados.</li></ul>
    <h3>Fontes</h3><p>BCB SGS (CDI 12, meta Selic 432, IPCA 433), BCB Focus (Olinda) e Tesouro Transparente (Tesouro Direto). Arquivos do usuário: Mapa de Posições (PDF) e ${h(L("Runflow"))} (XLSX), lidos só neste navegador.</p>
    </div></div>` +
    (interno() && DATA.metodologia ? `<details class="pos" style="margin-top:16px"><summary><span class="code">Documento de pesquisa completo</span><span class="meta">docs/metodologia.md · só no modo interno</span></summary><div class="body prose">${mdToHtml(DATA.metodologia)}</div></details>` : "");
}

// ------------------------------------------------------------------------------- render
const VIEWS = { dados: viewDados, parametros: viewParametros, carteira: viewCarteira, trocas: viewTrocas, metodologia: viewMetodologia };
function render() {
  const m = mapa(), col = P.oldestCollection(PUBLIC), stale = P.freshness(PUBLIC, E.todayDn()).some((f) => f.stale);
  $("#pill-pos").innerHTML = `<span class="dot"></span>Posição <b>${m ? E.brDate(m.positionDate) : "—"}</b>`;
  $("#pill-dados").className = `pill${stale ? " stale" : ""}`;
  $("#pill-dados").innerHTML = `<span class="dot"></span>Dados públicos <b>${col != null ? E.brDate(col) : "—"}</b>`;
  $("#pill-dados").title = stale ? `Mais de ${P.MAX_IDADE_DIAS_UTEIS} dias úteis: gere o HTML de novo para atualizar.` : "BCB SGS, Focus e Tesouro Direto";
  for (const b of document.querySelectorAll(".mode-switch button")) b.setAttribute("aria-pressed", String(b.dataset.value === S.mode));
  for (const t of document.querySelectorAll(".tab")) { if (t.dataset.route === S.route) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current"); }
  const rep = mapa() && runflow() ? report() : null;
  const nRec = rep ? rep.results.filter((r) => r.status === A.CLS.RECOMENDADA).length : 0;
  $("#tab-count").textContent = String(nRec); $("#tab-count").classList.toggle("hidden", !nRec);
  try { $("#view").innerHTML = (VIEWS[S.route] || viewDados)(); }
  catch (e) { $("#view").innerHTML = `<div class="warn-note">Erro ao montar a tela: ${h(e.message || e)}</div>`; console.error(e); }
  document.body.dataset.ready = S.busy ? "0" : "1";
}

// ------------------------------------------------------------------------------- eventos
function route() { const r = (location.hash.match(/^#\/([a-z]+)/) || [])[1]; S.route = r in VIEWS ? r : "dados"; render(); window.scrollTo(0, 0); }
window.addEventListener("hashchange", route);
async function takeFile(kind, file) {
  if (!file) return;
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (kind === "cfg") S.files.cfg = { name: file.name, text: new TextDecoder().decode(bytes) };
  else { S.files[kind] = { name: file.name, bytes }; if (kind === "mapa") { S.fixes = {}; S.overrides = {}; } }
  S.useSamples = false;
  if (kind === "cfg") changed(); else await loadFiles();
}
document.addEventListener("change", async (ev) => {
  const t = ev.target;
  if (t.dataset.file) { await takeFile(t.dataset.file, t.files[0]); t.value = ""; return; }
  if (t.dataset.param) {
    const k = t.dataset.param;
    if (t.type === "checkbox") S.params[k] = t.checked;
    else { const v = numPlain(t.value); if (v == null) { t.value = String(S.params[k]).replace(".", ","); return; } S.params[k] = k === "toleranciaRating" ? Math.max(0, Math.round(v)) : v; }
    changed();
  }
});
document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, a");
  if (!t) return;
  if (t.dataset.seg) { S.params[t.dataset.seg] = t.dataset.value; changed(); return; }
  if (t.dataset.filtro) { S.filtro = t.dataset.filtro; render(); return; }
  const a = t.dataset.action;
  if (a === "modo") { S.mode = t.dataset.value; changed(); }
  else if (a === "print") window.print();
  else if (a === "amostras") { S.useSamples = !S.useSamples; S.fixes = {}; S.overrides = {}; await loadFiles(); }
  else if (a === "descartar") { S.files = {}; S.fixes = {}; S.overrides = {}; S.mapaRaw = null; S.runflowSheets = null; changed(); }
  else if (a === "padroes") { S.params = { ...DEFAULTS }; changed(); }
  else if (a === "aplicar-fixes") {
    const fixes = { ...S.fixes };
    for (const tr of document.querySelectorAll("tr[data-lot]")) {
      const i = Number(tr.dataset.lot), fx = {};
      for (const inp of tr.querySelectorAll("input[data-fix]")) {
        const k = inp.dataset.fix, v = inp.value.trim();
        fx[k] = k === "code" ? (v.replace(/\s+/g, "") || null) : k === "rateText" ? v : k === "quantity" ? (num(v) == null ? null : Math.round(num(v))) : num(v);
      }
      fixes[i] = fx;
    }
    S.fixes = fixes; changed();
  } else if (a === "aplicar-ov" || a === "limpar-ov") {
    const ovs = {};
    if (a === "aplicar-ov") for (const tr of document.querySelectorAll("tr[data-ov]")) {
      const o = {};
      for (const inp of tr.querySelectorAll("input[data-ovf]")) { const k = inp.dataset.ovf, v = inp.value.trim(); if (!v) continue; o[k] = k === "duration" ? numPlain(v) : k === "marketRate" ? (numPlain(v) == null ? null : numPlain(v) / 100) : v; }
      if (Object.values(o).some((v) => v != null)) ovs[tr.dataset.ov] = o;
    }
    S.overrides = ovs; changed();
  } else if (a === "exportar") exportar();
});
for (const evn of ["dragover", "dragleave", "drop"]) document.addEventListener(evn, async (ev) => {
  const zone = ev.target.closest?.("[data-drop]");
  if (!zone) return;
  ev.preventDefault();
  zone.classList.toggle("over", evn === "dragover");
  if (evn === "drop" && !S.useSamples) await takeFile(zone.dataset.drop, ev.dataTransfer.files[0]);
});
function exportar() {
  const rep = report(), en = enriched(), rf = runflow();
  if (!rep) return;
  const sheets = [
    { name: "Carteira", rows: X.rowsFromObjects(A.positionsTable(en, S.mode)) },
    { name: "Trocas", rows: X.rowsFromObjects(A.swapsTable(rep, S.mode, rf.internalLabels)) },
    { name: "Resumo", rows: X.rowsFromObjects(A.summaryTable(rep)) },
    { name: "Premissas", rows: X.rowsFromObjects(A.assumptionsTable(rep)) },
  ];
  const blob = new Blob([X.writeXlsx(sheets)], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob); link.download = `trocas_${S.mode}_${E.isoDate(rep.asOf)}.xlsx`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 4000);
}

// ------------------------------------------------------------------------------- início
document.getElementById("footer").innerHTML = `<div class="src"><span><b>Fontes públicas:</b> BCB SGS (CDI, Selic, IPCA) · BCB Focus · Tesouro Transparente</span><span><b>Coleta:</b> ${P.oldestCollection(PUBLIC) != null ? E.brDate(P.oldestCollection(PUBLIC)) : "—"}</span><span><b>Versão:</b> ${h(DATA.build.date)} · ${h(DATA.build.commit)}</span></div><div>${h(A.AVISO)} Arquivos do usuário são lidos só neste navegador; nada é enviado, gravado ou registrado.</div>`;
const qs = new URLSearchParams(location.search);
if (qs.get("amostra") === "1") S.useSamples = true;
if (qs.get("modo") === "cliente") S.mode = "cliente";
route();
if (S.useSamples) loadFiles();
window.__cpsim = { S, report, enriched, mapa, runflow };
