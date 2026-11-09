// Leitores (Mapa, Runflow, config de colunas internas), curvas e cenários — porte de
// src/cpsim/parsers/*.py, config.py, curves.py e scenarios.py. Python = referência.
import {
  D, ymd, fromIso, normHeader, squashNumberGaps, parseBrl, parseDateBr, parseNumber, parsePercent,
  stripAccents, Indexer, parseIndexer, parseRating, businessDays, following, compound, cdiSgsToAnnual,
  buildSchedule, pricingFlows, macaulayDuration,
} from "./engine.mjs";

// ============================================================================ Mapa (PDF)
const COLUMNS = ["titulo", "emissao", "vencimento", "emissor", "operacao", "taxa_operacao", "quantidade",
  "pu_operacao", "pu_curva", "valor_bruto_curva", "pu_mercado", "valor_bruto_mercado", "ir", "iof",
  "valor_liquido", "rendimento"];
const LABELS = { titulo: "titulo", emissao: "emissao", vencimento: "vencimento", emissor: "emissor",
  operacao: "operacao", "taxa operacao": "taxa_operacao", quantidade: "quantidade", "pu operacao": "pu_operacao",
  "pu curva": "pu_curva", "valor bruto (curva)": "valor_bruto_curva", "pu mercado": "pu_mercado",
  "valor bruto (mercado)": "valor_bruto_mercado", ir: "ir", iof: "iof", "valor liquido": "valor_liquido",
  rendimento: "rendimento" };
const HEADER_MAP = Object.fromEntries(Object.entries(LABELS).map(([k, v]) => [k.replace(/ /g, ""), v]));
const HEADER_KEYS = Object.keys(HEADER_MAP);
const ASSET_TYPES = new Set(["DEB", "CRI", "CRA", "CDB", "CPR", "LCA", "LCI", "LF", "LIG", "CCB", "NC", "CDCA"]);
const RE_DATA_POSICAO = /Data\s*(?:da\s*)?posi[cç][aã]o:?\s*(\d{1,2}\s*\/\s*\d{1,2}\s*\/\s*\d{4})/i;
const RE_PAGINA = /^\s*\d+\s*de\s*\d+\s*$/i;
const RE_RODAPE = /^\s*\*|Data\s*(?:da\s*)?posi[cç][aã]o|dedu[cç][aã]o\s*de\s*(?:IR|impostos)|valor\s*l[ií]quido\s*(?:considera|[ée]\s*calculado)/i;
const RE_AGENCIA = /\bAg\.?\s*[\dX]{3,5}\s*\//i;
const RE_QTD = /^\d{1,3}(\.\d{3})+$|^\d+$/;
const RE_DATE = /\d{1,2}\/\d{1,2}\/\d{4}/g;
const RE_TITULO_FIM = /(.+?\s-\s*[A-Z0-9]{4,})(?=\s|$)/g;
const RE_PCT = /(-?\d+(?:[.,]\d+)?)\s*%/;
const NUM = "(-?\\d+(?:[.,]\\d+)?)";
const RE_TAXA_OP = [
  [new RegExp(`^(?:DI|CDI)\\s*\\+\\s*${NUM}\\s*%?$`, "i"), Indexer.CDI_SPREAD],
  [new RegExp(`^${NUM}\\s*%?\\s*\\+\\s*(?:DI|CDI)$`, "i"), Indexer.CDI_SPREAD],
  [new RegExp(`^${NUM}\\s*%\\s*(?:do\\s*)?(?:DI|CDI)$`, "i"), Indexer.CDI_PCT],
  [new RegExp(`^(?:DI|CDI)\\s*${NUM}\\s*%$`, "i"), Indexer.CDI_PCT],
  [new RegExp(`^${NUM}\\s*%\\s*IPCA$`, "i"), Indexer.IPCA],
  [new RegExp(`^IPCA\\s*\\+?\\s*${NUM}\\s*%$`, "i"), Indexer.IPCA],
  [new RegExp(`^${NUM}\\s*%\\s*PR[EÉ]$`, "i"), Indexer.PRE],
  [new RegExp(`^PR[EÉ]\\s*${NUM}\\s*%$`, "i"), Indexer.PRE],
];
const ws = (s) => s.split(/\s+/).filter(Boolean).join(" ");

function lines(frags, tol = 1.0) {
  const out = [];
  const sorted = [...frags].sort((a, b) => a.page - b.page || b.y - a.y || a.x - b.x);
  for (const f of sorted) {
    const last = out.at(-1);
    if (last && last[0].page === f.page && Math.abs(last[0].y - f.y) <= tol) last.push(f);
    else out.push([f]);
  }
  return out.map((l) => [...l].sort((a, b) => a.x - b.x));
}
const lineText = (l) => l.map((f) => f.text).join(" ");
const isPrefix = (key) => HEADER_KEYS.some((k) => k.startsWith(key));

function headerColumns(band, yLine1) {
  const line1 = band.filter((f) => f.y >= yLine1 - 2).sort((a, b) => a.x - b.x);
  const line2 = band.filter((f) => f.y < yLine1 - 2).sort((a, b) => b.y - a.y || a.x - b.x);
  const groups = [];
  for (const f of line1) {
    if (groups.length) {
      const cur = groups.at(-1).map((g) => normHeader(g.text)).join("").replace(/ /g, "");
      const nxt = (cur + normHeader(f.text)).replace(/ /g, "");
      if (isPrefix(nxt)) { groups.at(-1).push(f); continue; }
    }
    groups.push([f]);
  }
  const starts = groups.map((g) => Math.min(...g.map((x) => x.x)));
  const labels = groups.map((g) => g.map((x) => normHeader(x.text)).join("").replace(/ /g, ""));
  for (const f of line2) {
    let i = 0;
    starts.forEach((x0, k) => { if (f.x + 1 >= x0) i = k; });
    labels[i] += normHeader(f.text).replace(/ /g, "");
  }
  return starts.map((s, i) => [s, labels[i]]);
}

function partition(frags, anchors) {
  const n = frags.length, r = anchors.length;
  if (n < r || r === 0) return null;
  const ys = frags.map((f) => f.y);
  const cost = (i, j, k) => { const top = ys[i], bot = ys[j - 1]; return Math.min(Math.abs((top + bot) / 2 - anchors[k]), Math.abs(top - anchors[k])); };
  const dp = Array.from({ length: r + 1 }, () => new Array(n + 1).fill(Infinity));
  const back = Array.from({ length: r + 1 }, () => new Array(n + 1).fill(0));
  dp[0][0] = 0;
  for (let k = 1; k <= r; k++) for (let j = k; j <= n - (r - k); j++) {
    let best = Infinity, arg = 0;
    for (let i = k - 1; i < j; i++) { const v = dp[k - 1][i] + cost(i, j, k - 1); if (v < best) { best = v; arg = i; } }
    dp[k][j] = best; back[k][j] = arg;
  }
  const groups = []; let j = n;
  for (let k = r; k > 0; k--) { const i = back[k][j]; groups.push(frags.slice(i, j)); j = i; }
  return groups.reverse();
}

export function parseRateText(txt) {
  const t = ws(squashNumberGaps(txt || ""));
  for (const [rx, idx] of RE_TAXA_OP) { const m = t.match(rx); if (m) return { indexer: idx, value: Number(m[1].replace(",", ".")) / 100 }; }
  return null;
}

export function parseTitle(title) {
  const t = ws(squashNumberGaps(title || ""));
  let code = null, body = t;
  if (t.includes(" - ") || t.endsWith(" -")) {
    const i = t.lastIndexOf(" -");
    body = t.slice(0, i);
    code = t.slice(i + 2).replace(/ /g, "").replace(/^-+|-+$/g, "") || null;
  }
  const toks = body.split(" ");
  const asset = toks.length && ASSET_TYPES.has(toks[0].toUpperCase()) ? toks[0].toUpperCase() : null;
  const rest = asset ? toks.slice(1) : toks;
  let idxPos = null, idx = null;
  for (let i = 0; i < rest.length; i++) {
    const u = rest[i].toUpperCase().replace(/^[,;]+|[,;]+$/g, "");
    if (u === "IPCA" || u === "IPCA+") { idxPos = i; idx = Indexer.IPCA; }
    else if (["PRE", "PRÉ", "PREFIXADO"].includes(u)) { idxPos = i; idx = Indexer.PRE; }
    else if (["CDI", "DI", "CDI+", "DI+"].includes(u)) {
      const plus = u.endsWith("+") || (i + 1 < rest.length && rest[i + 1].startsWith("+"));
      idxPos = i; idx = plus ? Indexer.CDI_SPREAD : Indexer.CDI_PCT;
    }
    if (idxPos != null) break;
  }
  const issuer = (idxPos != null ? rest.slice(0, idxPos) : rest).join(" ").trim();
  const after = idxPos != null ? rest.slice(idxPos).join(" ") : "";
  const m = after.match(RE_PCT);
  const rate = idx && m ? { indexer: idx, value: Number(m[1].replace(",", ".")) / 100 } : null;
  const dates = body.match(RE_DATE) || [];
  return { assetType: asset, issuer, rate, maturityText: dates.at(-1) ?? null, code };
}

function toInt(s) {
  s = s.replace(/ /g, "").trim();
  if (!s || s === "-") return null;
  const t = s.replace(/\./g, "");
  return /^-?\d+$/.test(t) ? Number(t) : null;
}

function tol(q, gross) { return Math.max(0.05, q * 0.01, Math.abs(gross) * 5e-5); }

export function validateLot(lot, rawDates = {}) {
  const e = (lot.errors = []);
  lot.warnings = [];
  if (!lot.code || !/^[A-Z0-9]{4,}$/.test(lot.code)) e.push("código não encontrado no Título");
  if (lot.assetType == null) e.push("tipo do papel não reconhecido no Título");
  if (lot.rate == null) e.push(`Taxa Operação não reconhecida: '${lot.rateText}'`);
  for (const [nome, d] of [["Emissão", lot.emission], ["Vencimento", lot.maturity], ["Operação", lot.purchaseDate]]) {
    if (d == null) e.push(`data inválida em ${nome}: '${rawDates[nome] ?? ""}'`);
  }
  const q = lot.quantity;
  if (q == null || q <= 0) { e.push("quantidade ausente"); return; }
  if (lot.puCurve != null && lot.grossCurve != null) {
    if (Math.abs(q * lot.puCurve - lot.grossCurve) > tol(q, lot.grossCurve)) e.push("Quantidade × PU Curva ≠ Valor Bruto (curva)");
  } else if (lot.grossCurve == null) e.push("Valor Bruto (curva) ausente");
  if (lot.puMarket != null && lot.grossMarket != null) {
    if (Math.abs(q * lot.puMarket - lot.grossMarket) > tol(q, lot.grossMarket)) e.push("Quantidade × PU Mercado ≠ Valor Bruto (mercado)");
  } else if ((lot.puMarket == null) !== (lot.grossMarket == null)) e.push("PU Mercado e Valor Bruto (mercado) inconsistentes");
  const base = lot.grossMarket != null ? lot.grossMarket : lot.grossCurve;
  if (base != null && lot.netValue != null) {
    const ded = (lot.ir || 0) + (lot.iof || 0);
    if (Math.abs(base - ded - lot.netValue) > Math.max(0.05, Math.abs(base) * 5e-5)) lot.warnings.push("Valor Líquido ≠ Valor Bruto − IR − IOF (critério do arquivo)");
  }
}

const joinFrags = (frs) => [...frs].sort((a, b) => b.y - a.y || a.x - b.x).map((f) => f.text).join(" ").trim();

function toLot(page, cell, titleText) {
  const txt = (c) => (c === "titulo" && titleText != null ? titleText : joinFrags(cell[c]));
  const num = (c) => parseBrl(squashNumberGaps(txt(c)));
  const title = ws(txt("titulo"));
  const tp = parseTitle(title);
  const rateTxt = ws(squashNumberGaps(txt("taxa_operacao")));
  const lot = {
    page, code: tp.code, assetType: tp.assetType, title, issuer: txt("emissor"),
    emission: parseDateBr(txt("emissao")), maturity: parseDateBr(txt("vencimento")), purchaseDate: parseDateBr(txt("operacao")),
    rate: parseRateText(rateTxt), rateText: rateTxt, titleRate: tp.rate, quantity: toInt(txt("quantidade")),
    puPurchase: num("pu_operacao"), puCurve: num("pu_curva"), grossCurve: num("valor_bruto_curva"),
    puMarket: num("pu_mercado"), grossMarket: num("valor_bruto_mercado"), ir: num("ir"), iof: num("iof"),
    netValue: num("valor_liquido"), income: num("rendimento"), errors: [], warnings: [],
  };
  validateLot(lot, { "Emissão": txt("emissao"), "Vencimento": txt("vencimento"), "Operação": txt("operacao") });
  return lot;
}

/** frags: [{page, x, y, text}] (coordenadas do PDF). Ver src/cpsim/parsers/mapa_pdf.py. */
export function parseMapaFragments(frags, nPages) {
  const warnings = [];
  const excluded = new Set();
  let dataPos = null;
  for (const line of lines(frags)) {
    const t = lineText(line);
    if (dataPos == null) { const m = t.match(RE_DATA_POSICAO); if (m) dataPos = parseDateBr(m[1]); }
    if (RE_PAGINA.test(t) || RE_RODAPE.test(t) || RE_AGENCIA.test(t)) line.forEach((f) => excluded.add(f));
  }
  if (dataPos == null) warnings.push("Data da posição não encontrada no rodapé.");
  const lots = [];
  for (let pno = 1; pno <= nPages; pno++) {
    const pf = frags.filter((f) => f.page === pno && !excluded.has(f));
    const head = pf.filter((f) => normHeader(f.text) === "titulo");
    if (!head.length) continue;
    const yHead = head[0].y;
    const band = pf.filter((f) => Math.abs(f.y - yHead) <= 10);
    let starts = [];
    for (const [x0, label] of headerColumns(band, yHead)) {
      const col = HEADER_MAP[label.replace(/ /g, "")];
      if (col == null) { warnings.push(`Página ${pno}: cabeçalho não reconhecido '${label}'.`); continue; }
      starts.push([x0, col]);
    }
    const found = new Set(starts.map(([, c]) => c));
    const missing = COLUMNS.filter((c) => !found.has(c));
    if (missing.length) { warnings.push(`Página ${pno}: colunas ausentes [${missing.join(", ")}]; página ignorada.`); continue; }
    starts.sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : 1));
    const yBodyTop = Math.min(...band.map((f) => f.y)) - 1;
    const body = pf.filter((f) => f.y < yBodyTop);
    const colOf = (f) => { let col = starts[0][1]; for (const [x0, c] of starts) if (f.x + 1 >= x0) col = c; return col; };
    const byCol = Object.fromEntries(COLUMNS.map((c) => [c, []]));
    for (const f of body) byCol[colOf(f)].push(f);
    const anchors = [...new Set(byCol.quantidade.filter((f) => RE_QTD.test(f.text.replace(/ /g, ""))).map((f) => f.y))].sort((a, b) => b - a);
    if (!anchors.length) continue;
    const titYs = byCol.titulo.map((f) => f.y);
    const hits = anchors.filter((a) => titYs.some((y) => Math.abs(a - y) < 0.6)).length;
    const topAligned = hits >= 0.8 * anchors.length && titYs.length > 0 && Math.abs(Math.max(...titYs) - anchors[0]) < 0.6;
    const cells = anchors.map(() => Object.fromEntries(COLUMNS.map((c) => [c, []])));
    let titles = null;
    if (!topAligned) {
      const joined = lines(byCol.titulo).map(lineText).join(" ");
      const fnd = [...joined.matchAll(RE_TITULO_FIM)].map((m) => m[1].trim());
      if (fnd.length === anchors.length) titles = fnd;
    }
    for (const c of COLUMNS) {
      if (c === "titulo" && titles != null) continue;
      if (topAligned) {
        for (const f of byCol[c]) {
          let last = -1;
          anchors.forEach((a, i) => { if (a >= f.y - 0.6) last = i; });
          if (last >= 0) cells[last][c].push(f);
        }
        continue;
      }
      const linesC = lines(byCol[c]);
      const groups = partition(linesC.map((ln) => ln[0]), anchors);
      if (groups == null) {
        for (const ln of linesC) {
          let best = 0;
          anchors.forEach((a, k) => { if (Math.abs(a - ln[0].y) < Math.abs(anchors[best] - ln[0].y)) best = k; });
          cells[best][c].push(...ln);
        }
        continue;
      }
      const lineOf = new Map(linesC.map((ln) => [ln[0], ln]));
      groups.forEach((grp, i) => grp.forEach((h) => cells[i][c].push(...lineOf.get(h))));
    }
    cells.forEach((cell, i) => lots.push(toLot(pno, cell, titles ? titles[i] : null)));
  }
  return { positionDate: dataPos, lots, nPages, warnings, nFragments: frags.length };
}

const sumOrNull = (vals) => (vals.some((v) => v == null) ? null : vals.reduce((a, b) => a + b, 0));
export function positionsOf(mapa) {
  const by = new Map();
  for (const lot of mapa.lots) if (lot.code) { if (!by.has(lot.code)) by.set(lot.code, []); by.get(lot.code).push(lot); }
  return [...by.entries()].map(([code, lots]) => makePosition(code, lots));
}
export function makePosition(code, lots) {
  const first = lots[0];
  const r = first.rate || first.titleRate;
  const q = sumOrNull(lots.map((l) => l.quantity));
  const pairs = lots.filter((l) => l.rate && l.quantity).map((l) => [l.rate.value, l.quantity]);
  const tq = pairs.reduce((s, [, x]) => s + x, 0);
  return {
    code, lots, first, assetType: first.assetType, issuer: first.issuer, maturity: first.maturity,
    indexer: r ? r.indexer : null, hasMarketPrice: lots.every((l) => l.puMarket != null),
    quantity: q, grossMarket: sumOrNull(lots.map((l) => l.grossMarket)), grossCurve: sumOrNull(lots.map((l) => l.grossCurve)),
    netValue: sumOrNull(lots.map((l) => l.netValue)), ir: sumOrNull(lots.map((l) => l.ir)), iof: sumOrNull(lots.map((l) => l.iof)),
    purchaseRateAvg: tq ? pairs.reduce((s, [v, x]) => s + v * x, 0) / tq : null,
  };
}

// ============================================================================ config (TOML)
export const INTERNAL_FIELDS = ["fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b"];
function tomlString(s) { const m = s.match(/^"((?:[^"\\]|\\.)*)"/); return m ? m[1].replace(/\\"/g, '"').replace(/\\\\/g, "\\") : null; }
/** Leitor mínimo do formato de config/runflow_columns.*.toml (seção [colunas_internas]). */
export function parseInternalColumns(text, source = "texto") {
  const byHeader = {}, labels = {}, headers = {};
  let sec = null;
  for (let line of String(text).split(/\r?\n/)) {
    line = line.replace(/^\s+/, "");
    if (!line || line.startsWith("#")) continue;
    const s = line.match(/^\[([^\]]+)\]/);
    if (s) { sec = s[1].trim(); continue; }
    if (sec !== "colunas_internas") continue;
    const kv = line.match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/);
    if (!kv) continue;
    const campo = kv[1], val = kv[2].trim();
    let cab = null, rot = campo;
    if (val.startsWith("{")) {
      const mc = val.match(/cabecalho\s*=\s*("(?:[^"\\]|\\.)*")/), mr = val.match(/rotulo\s*=\s*("(?:[^"\\]|\\.)*")/);
      cab = mc ? tomlString(mc[1]) : null; if (mr) rot = tomlString(mr[1]);
    } else cab = tomlString(val);
    if (cab == null) continue;
    byHeader[normHeader(cab)] = campo; labels[campo] = rot; headers[campo] = cab;
  }
  return { byHeader, labels, headers, source, fields: Object.keys(labels) };
}

// ============================================================================ Runflow (XLSX)
const PUBLIC_COLUMNS = { codigo: "codigo", empresa: "empresa", produto: "produto", "taxa de compra": "taxa_compra",
  indexador: "indexador", distribuicao: "distribuicao", "lastro disponivel": "lastro_disponivel", "qtds disponiveis": "qtd_disponivel",
  vencimento: "vencimento", duration: "duration", "b ref.": "b_ref", "taxa de emissao": "taxa_emissao", cupom: "cupom",
  amortizacao: "amortizacao", "setor de atuacao": "setor", rating: "rating", agencia: "agencia",
  "investidor qualificado?": "investidor_qualificado", "isento?": "isento", "garantia na emissao": "garantia" };
const REQUIRED = ["codigo", "taxa_compra", "indexador", "vencimento"];
const HEADER_ROW = 10;
function rateScale(v, hadPct, idx) { if (hadPct) return v / 100; if (idx === Indexer.CDI_PCT) return v <= 3 ? v : v / 100; return Math.abs(v) <= 0.5 ? v : v / 100; }
function yes(v) {
  if (v == null || String(v).trim() === "") return null;
  const t = stripAccents(String(v)).trim().toLowerCase();
  if (["sim", "s", "yes", "y", "true", "1", "isento"].includes(t)) return true;
  if (["nao", "n", "no", "false", "0", "tributado"].includes(t)) return false;
  return null;
}
function qualified(v) {
  if (v == null) return null;
  const t = stripAccents(String(v)).trim().toLowerCase();
  if (t.startsWith("qualif") || t.startsWith("profis") || t === "sim") return true;
  if (["geral", "nao", "publico geral", "varejo"].includes(t)) return false;
  return null;
}
function brefYear(v) { if (v == null) return null; const m = String(v).match(/^\s*(?:NTN-?B\s*)?B?\s*(\d{2}|\d{4})\s*$/i); if (!m) return null; const y = Number(m[1]); return y > 1000 ? y : 2000 + y; }
const text = (v) => (v == null ? "" : typeof v === "object" ? "" : String(v).trim());

/** sheets: [{name, rows: [[valor,...], ...]}] (linha 1 = rows[0]). Ver runflow_xlsx.py. */
export function readRunflowSheets(sheets, internal) {
  const warnings = [];
  let sh = sheets.find((s) => s.name === "Consolidado");
  if (!sh) { sh = sheets[0]; warnings.push("Aba 'Consolidado' não encontrada; usando a primeira aba."); }
  const header = sh.rows[HEADER_ROW - 1] || [];
  const pub = {}, intl = {}, extra = [];
  header.forEach((h, j) => {
    const key = normHeader(h);
    if (!key) return;
    if (key in PUBLIC_COLUMNS) pub[j] = PUBLIC_COLUMNS[key];
    else if (key in internal.byHeader) intl[j] = internal.byHeader[key];
    else extra.push(String(h));
  });
  const pubVals = new Set(Object.values(pub)), intlVals = new Set(Object.values(intl));
  const missing = Object.values(PUBLIC_COLUMNS).filter((v) => !pubVals.has(v));
  for (const f of internal.fields) if (!intlVals.has(f)) missing.push(`(interna) ${internal.labels[f]}`);
  if (REQUIRED.some((r) => missing.includes(r))) warnings.push("Colunas obrigatórias ausentes: " + REQUIRED.filter((r) => missing.includes(r)).join(", "));
  const candidates = [];
  for (const values of sh.rows.slice(HEADER_ROW)) {
    if (!values) continue;
    const rec = {}; for (const [j, c] of Object.entries(pub)) rec[c] = values[j] ?? null;
    const code = text(rec.codigo);
    if (!code) continue;
    const iv = {}; for (const [j, c] of Object.entries(intl)) iv[c] = values[j] ?? null;
    candidates.push(toCandidate(code, rec, iv));
  }
  return { candidates, missing, extra, internalLabels: { ...internal.labels }, columnsSource: internal.source, warnings };
}

function toCandidate(code, rec, internalValues) {
  const w = [];
  const idx = parseIndexer(rec.indexador);
  let rate = null;
  if (idx == null) w.push(`indexador não reconhecido: '${rec.indexador}'`);
  else {
    const [v, pct] = parsePercent(rec.taxa_compra);
    if (v == null) w.push(`taxa de compra não reconhecida: '${rec.taxa_compra}'`);
    else rate = { indexer: idx, value: rateScale(v, pct, idx) };
  }
  const [ev, epct] = parsePercent(rec.taxa_emissao);
  const emission = ev != null && idx != null ? rateScale(ev, epct, idx) : null;
  const maturity = parseDateBr(rec.vencimento);
  if (maturity == null) w.push(`vencimento inválido: '${text(rec.vencimento)}'`);
  const duration = parseNumber(rec.duration);
  if (duration == null) w.push("sem duration");
  const rating = parseRating(rec.rating);
  if (rating.notch == null) w.push("sem rating");
  const qty = parseNumber(rec.qtd_disponivel);
  const dist = text(rec.distribuicao);
  return {
    code, issuer: text(rec.empresa), product: text(rec.produto).toUpperCase() || null, rate, indexer: rate ? rate.indexer : null,
    active: stripAccents(dist).toLowerCase() === "ativa", distribution: dist, lastro: parseNumber(rec.lastro_disponivel),
    qtyAvailable: qty == null ? null : Math.trunc(qty), maturity, duration, ntnbRefYear: brefYear(rec.b_ref), emissionRate: emission,
    coupon: text(rec.cupom), amortization: text(rec.amortizacao), sector: text(rec.setor), rating, agency: text(rec.agencia),
    qualifiedOnly: qualified(rec.investidor_qualificado), taxExempt: yes(rec.isento), guarantee: text(rec.garantia),
    internal: internalValues, warnings: w,
  };
}

// ============================================================================ curvas
export const PUBLIC_FILES = ["cdi", "selic_meta", "ipca_mensal", "focus_selic", "focus_ipca", "tesouro_direto"];
const COPOM = { 1: [1, 28], 2: [3, 18], 3: [5, 6], 4: [6, 17], 5: [7, 29], 6: [9, 16], 7: [11, 4], 8: [12, 9] };
export function publicFromPayloads(p) {
  const series = (n) => (p[n] ? p[n].dados.map((r) => [fromIso(r.data), Number(r.valor)]) : []);
  const fs = p.focus_selic?.dados || {}, fi = p.focus_ipca?.dados || {};
  return {
    cdiDaily: series("cdi"), selicMeta: series("selic_meta"),
    focusSelic: (fs.reunioes || []).map((r) => [r.reuniao, Number(r.mediana)]),
    focusSelicDate: fs.data_referencia ? fromIso(fs.data_referencia) : null,
    focusIpcaAnnual: Object.fromEntries((fi.anual || []).map((r) => [Number(r.ano), Number(r.mediana)])),
    focusIpca12m: fi.doze_meses ? Number(fi.doze_meses.mediana) : null,
    focusIpcaDate: fi.data_referencia ? fromIso(fi.data_referencia) : null,
    tesouro: p.tesouro_direto?.dados || [],
    collectedAt: Object.fromEntries(Object.entries(p).map(([k, v]) => [k, v.coletado_em || ""])),
  };
}
export function copomDate(label) { const [num, ano] = label.trim().toUpperCase().replace(/^R/, "").split("/"); const [m, d] = COPOM[Number(num)]; return D(Number(ano), m, d); }
export function currentCdi(pd) { if (!pd.cdiDaily.length) throw new Error("sem série de CDI"); const [d, v] = pd.cdiDaily.at(-1); return [cdiSgsToAnnual(v), d]; }
export function cdiPath(pd, asOf) {
  const [cdi0] = currentCdi(pd);
  const gap = pd.selicMeta.length ? pd.selicMeta.at(-1)[1] / 100 - cdi0 : 0.001;
  const path = [[asOf, cdi0]];
  for (const [label, selic] of pd.focusSelic) { const d = copomDate(label) + 1; if (d > asOf) path.push([d, selic / 100 - gap]); }
  return path;
}
export function expectedCdi(pd, asOf, h) {
  const end = asOf + Math.round(365.25 * h);
  const path = cdiPath(pd, asOf);
  let fator = 1, duTot = 0;
  path.forEach(([ini, cdi], i) => {
    let fim = i + 1 < path.length ? path[i + 1][0] : end;
    fim = Math.min(fim, end);
    if (fim <= ini) return;
    const du = businessDays(following(ini), following(fim));
    fator *= compound(cdi, du); duTot += du;
  });
  return { value: duTot ? fator ** (252 / duTot) - 1 : path[0][1], source: `BCB SGS 12 + Focus Selic de ${pd.focusSelicDate != null ? isoOf(pd.focusSelicDate) : "—"}`,
    note: "datas das reuniões do Copom aproximadas; CDI = Selic − diferença atual" };
}
const isoOf = (dn) => { const [y, m, d] = ymd(dn); return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`; };
export function expectedIpca(pd, asOf, h) {
  const years = Object.keys(pd.focusIpcaAnnual).map(Number);
  if (pd.focusIpca12m == null && !years.length) throw new Error("sem expectativa de IPCA");
  const first = (pd.focusIpca12m != null ? pd.focusIpca12m : pd.focusIpcaAnnual[Math.min(...years)]) / 100;
  let fator = 1, anos = 0, take = Math.min(1, h);
  fator *= (1 + first) ** take; anos += take;
  let y = ymd(asOf)[0] + 1, last = first;
  while (anos < h - 1e-9) {
    const v = pd.focusIpcaAnnual[y];
    last = v != null ? v / 100 : last;
    take = Math.min(1, h - anos);
    fator *= (1 + last) ** take; anos += take; y += 1;
  }
  return { value: fator ** (1 / anos) - 1, source: `Focus IPCA de ${pd.focusIpcaDate != null ? isoOf(pd.focusIpcaDate) : "—"}` };
}
export function ntnbQuotes(pd) {
  const rows = pd.tesouro.filter((r) => r.titulo === "Tesouro IPCA+ com Juros Semestrais");
  if (!rows.length) return [[], null];
  const base = rows.map((r) => r.data_base).sort().at(-1);
  const asOf = fromIso(base);
  const out = [];
  for (const r of rows) {
    if (r.data_base !== base) continue;
    const taxas = [r.taxa_compra, r.taxa_venda].filter((t) => t != null);
    if (!taxas.length) continue;
    const rate = taxas.reduce((a, b) => a + b, 0) / taxas.length / 100;
    const mat = fromIso(r.vencimento);
    const sch = buildSchedule(asOf, mat, ymd(mat)[1] === 5 ? "Mai/Nov" : "Fev/Ago", "Bullet", 0.06);
    out.push({ maturity: mat, rate, duration: sch.ok ? macaulayDuration(pricingFlows(sch), rate) : null });
  }
  out.sort((a, b) => a.maturity - b.maturity);
  return [out, asOf];
}
export const MAX_IDADE_DIAS_UTEIS = 3;
export function freshness(pd, today, maxBd = MAX_IDADE_DIAS_UTEIS) {
  return PUBLIC_FILES.map((name) => {
    const raw = pd.collectedAt[name] || "";
    const d = raw ? fromIso(raw) : null;
    const age = d != null ? businessDays(d, today) : null;
    return { name, collected: d, age, stale: age == null || age > maxBd };
  });
}
export function oldestCollection(pd) { const ds = Object.values(pd.collectedAt).filter(Boolean).map(fromIso); return ds.length ? Math.min(...ds) : null; }

// ============================================================================ cenários
export function baseScenario(pd, asOf, h = 1) {
  const c = expectedCdi(pd, asOf, h), i = expectedIpca(pd, asOf, h);
  return { name: "Base (Focus)", horizonYears: h, cdi: c.value, ipca: i.value, cdiSource: c.source, ipcaSource: i.source,
    note: "Expectativa de mercado (Focus), não previsão; " + c.note };
}
export function userScenario(cdi, ipca, h = 1) {
  return { name: "Do usuário", horizonYears: h, cdi, ipca, cdiSource: "informado pelo usuário", ipcaSource: "informado pelo usuário", note: "" };
}
