// Enriquecimento, motor de troca e relatório — porte de src/cpsim/enrich.py, swap_engine.py e
// report.py. Python = referência. O fee e demais colunas internas NUNCA entram em cálculo ou
// ranking: `candidate.internal` só é lido em reportSwaps() no modo interno (regras 6 e 7).
import {
  stripAccents, Indexer, pctCdiToAnnual, cdiPlusToAnnual, rateDifference, nominalExpected, rateStr,
  buildSchedule, pricingFlows, price, brent, macaulayDuration, businessDays, taxPolicy, exitCost,
  paybackYears, spreadOverNtnb, ntnbReference, DEFAULT_BID_ASK, fmtBps, fmtPct, fmtBrl, fmtNum, brDate,
} from "./engine.mjs";
const fmtSigned = (x, c = 2) => (x >= 0 ? "+" : "") + fmtNum(x, c);
import { positionsOf } from "./parsers.mjs";

export const KIND = { DADO: "dado", ESTIMATIVA: "estimativa", APROXIMACAO: "aproximação" };
const DEFAULT_COUPON = "Semestral", DEFAULT_AMORTIZATION = "Bullet";
const SCOPE_TYPES = new Set(["DEB", "CRI", "CRA"]);
const LOT_DISPERSION_ALERT = 0.0010, DESK_SPREAD_REVIEW = 0.0150;
export const SRC = {
  OVERRIDE: "informado pelo usuário",
  IMPLIED_RUNFLOW: "estimada pelo PU Mercado (fluxo do Runflow)",
  IMPLIED_DEFAULT: "estimada pelo PU Mercado (fluxo padrão: juros semestrais, amortização no vencimento)",
  IMPLIED_USER: "estimada pelo PU Mercado (fluxo informado pelo usuário)",
  RUNFLOW_RATE: "Taxa de Compra do Runflow", RUNFLOW_DURATION: "Duration do Runflow",
  DURATION_CALC: "calculada com o fluxo da estimativa",
};
const sourced = (value, source, kind = KIND.DADO, note = "") => ({ value, source, kind, note });

export function issuerKey(name) {
  let t = stripAccents(name || "").toUpperCase();
  t = t.replace(/\b(S\.?\s?A\.?|S\/A|LTDA\.?|CIA\.?|COMPANHIA|EM RECUPERACAO JUDICIAL)(?=\s|$|[^A-Z0-9])/g, " ");
  t = t.replace(/[^A-Z0-9 ]/g, " ");
  return t.split(/\s+/).filter(Boolean).join(" ");
}
export function discountRate(idx, value, sc) {
  if (idx === Indexer.CDI_PCT) return pctCdiToAnnual(value, sc.cdi);
  if (idx === Indexer.CDI_SPREAD) return cdiPlusToAnnual(value, sc.cdi);
  return value;
}
export function impliedRate(puMarket, puCurve, purchaseRate, couponRate, valuation, maturity, couponText, amortText, sc) {
  const idx = purchaseRate.indexer;
  const sch = buildSchedule(valuation, maturity, couponText, amortText, discountRate(idx, couponRate, sc));
  if (!sch.ok) return null;
  const flows = pricingFlows(sch);
  const base = price(flows, discountRate(idx, purchaseRate.value, sc));
  const target = puMarket / puCurve;
  const g = (y) => price(flows, discountRate(idx, y, sc)) / base - target;
  const [lo, hi] = idx === Indexer.CDI_PCT ? [0.05, 5.0] : [-0.3, 1.5];
  let y;
  try { y = brent(g, lo, hi, 1e-10); } catch { return null; }
  return [y, macaulayDuration(flows, discountRate(idx, y, sc)), [...sch.warnings]];
}
function taxExempt(pos, cand, policy) {
  if (cand && cand.taxExempt != null) return sourced(policy.isExempt(pos.assetType, cand.taxExempt), "Runflow (Isento?)");
  if (policy.pfExemptProducts.has(pos.assetType || "")) return sourced(policy.isExempt(pos.assetType, null), "tipo do papel");
  if (pos.lots.some((l) => (l.income || 0) > 0) && pos.lots.every((l) => (l.ir || 0) === 0))
    return sourced(policy.isExempt(pos.assetType, true), "inferido: IR zero com rendimento", KIND.ESTIMATIVA);
  return sourced(policy.isExempt(pos.assetType, false), "inferido: IR no Mapa", KIND.ESTIMATIVA);
}

export function enrichPosition(pos, valuation, sc, cand = null, ov = null, { includeWithoutMarketPrice = false, policy = taxPolicy() } = {}) {
  ov = ov || {};
  const alerts = [];
  const idx = pos.indexer;
  const inScope = (SCOPE_TYPES.has(pos.assetType) && pos.hasMarketPrice) || (includeWithoutMarketPrice && pos.assetType != null);
  let note = "";
  if (!pos.hasMarketPrice) note = "sem PU Mercado" + (includeWithoutMarketPrice ? "" : " (fora por padrão)");
  else if (!SCOPE_TYPES.has(pos.assetType)) note = `tipo ${pos.assetType} fora do escopo`;
  let coupon, amort, flowDesc, srcImplied;
  if (ov.coupon || ov.amortization) {
    coupon = ov.coupon || (cand ? cand.coupon : DEFAULT_COUPON);
    amort = ov.amortization || (cand ? cand.amortization : DEFAULT_AMORTIZATION);
    flowDesc = `Cupom ${coupon}; Amortização ${amort}`; srcImplied = SRC.IMPLIED_USER;
  } else if (cand && cand.coupon && cand.amortization) {
    coupon = cand.coupon; amort = cand.amortization;
    flowDesc = `Cupom ${coupon}; Amortização ${amort} (Runflow)`; srcImplied = SRC.IMPLIED_RUNFLOW;
  } else {
    coupon = DEFAULT_COUPON; amort = DEFAULT_AMORTIZATION;
    flowDesc = "juros semestrais, amortização no vencimento (padrão)"; srcImplied = SRC.IMPLIED_DEFAULT;
  }
  const lotRates = []; let calcDur = null;
  for (const lot of pos.lots) {
    if (!(lot.puMarket && lot.puCurve && lot.rate && lot.maturity)) continue;
    const couponRate = (cand && cand.emissionRate != null ? cand.emissionRate : null)
      || (lot.titleRate && lot.titleRate.indexer === lot.rate.indexer ? lot.titleRate.value : null)
      || lot.rate.value;
    const res = impliedRate(lot.puMarket, lot.puCurve, lot.rate, couponRate, valuation, lot.maturity, coupon, amort, sc);
    if (res == null) continue;
    const [y, d, w] = res;
    lotRates.push([y, lot.quantity || 1]); calcDur = d;
    for (const x of w) if (!alerts.includes(x)) alerts.push(x);
  }
  let marketRate = null;
  if (ov.marketRate != null) marketRate = sourced(ov.marketRate, SRC.OVERRIDE);
  else if (lotRates.length) {
    const tot = lotRates.reduce((s, [, q]) => s + q, 0);
    marketRate = sourced(lotRates.reduce((s, [v, q]) => s + v * q, 0) / tot, srcImplied, KIND.ESTIMATIVA, "taxa estimada");
    const vs = lotRates.map(([v]) => v), disp = Math.max(...vs) - Math.min(...vs);
    if (disp > LOT_DISPERSION_ALERT) alerts.push(`lotes do mesmo código dão taxas diferentes (${(disp * 1e4).toFixed(0)} bps): verificar PU Curva/fluxo`);
    if (srcImplied === SRC.IMPLIED_DEFAULT) alerts.push("taxa estimada com fluxo padrão; se o papel amortiza antes do vencimento, informe a amortização (o erro cresce com a distância entre taxa de mercado e taxa de operação)");
    if (idx === Indexer.CDI_PCT || idx === Indexer.CDI_SPREAD) alerts.push("estimativa depende do cenário de CDI");
  } else if (cand && cand.rate && cand.indexer === idx) {
    marketRate = sourced(cand.rate.value, SRC.RUNFLOW_RATE, KIND.APROXIMACAO, "aproximação: taxa de venda da mesa, a recompra tende a ser pior");
    alerts.push(marketRate.note);
  } else alerts.push("sem taxa de mercado: sem recomendação");
  let duration = null;
  if (ov.duration != null) duration = sourced(ov.duration, SRC.OVERRIDE);
  else if (cand && cand.duration != null) duration = sourced(cand.duration, SRC.RUNFLOW_DURATION);
  else if (calcDur != null) duration = sourced(calcDur, SRC.DURATION_CALC, KIND.ESTIMATIVA, flowDesc);
  else if (pos.maturity != null) duration = sourced(businessDays(valuation, pos.maturity) / 252, "prazo até o vencimento", KIND.APROXIMACAO, "sem fluxo: duration = prazo (superestima se houver cupom)");
  const dmod = duration && marketRate && idx ? duration.value / (1 + discountRate(idx, marketRate.value, sc)) : null;
  let deskSpread = null;
  if (marketRate && marketRate.kind === KIND.ESTIMATIVA && cand && cand.rate && cand.indexer === idx && idx)
    deskSpread = rateDifference({ indexer: idx, value: marketRate.value }, cand.rate, sc.cdi);
  const rating = cand ? cand.rating : { raw: "", label: null, notch: null };
  if (rating.notch == null) alerts.push("sem rating" + (cand ? "" : " (papel fora do Runflow)"));
  const issuer = cand && cand.issuer ? cand.issuer : pos.first.issuer;
  const e = {
    position: pos, code: pos.code, candidate: cand, inScope, scopeNote: note, indexer: idx, marketRate, duration, dmod,
    flow: flowDesc, lotRates: lotRates.map(([v]) => v), rating, sector: cand ? cand.sector : "", issuerKey: issuerKey(issuer),
    taxExempt: taxExempt(pos, cand, policy), alerts, deskSpread, review: deskSpread != null && deskSpread > DESK_SPREAD_REVIEW,
  };
  e.netValue = pos.netValue || 0;
  e.mtmVsCurve = pos.grossMarket == null || pos.grossCurve == null ? null : pos.grossMarket - pos.grossCurve;
  e.rate = marketRate && idx ? { indexer: idx, value: marketRate.value } : null;
  return e;
}
export function enrich(mapa, sc, candidates = null, overrides = {}, opts = {}) {
  if (mapa.positionDate == null) throw new Error("Mapa sem data da posição");
  const by = new Map((candidates || []).map((c) => [c.code, c]));
  return positionsOf(mapa).map((p) => enrichPosition(p, mapa.positionDate, sc, by.get(p.code) || null, overrides[p.code] || null, opts));
}

// ============================================================================ motor de troca
export const CLS = { RECOMENDADA: "Troca recomendada", MARGINAL: "Troca marginal", MANTER: "Manter", SEM_TAXA: "Sem taxa de mercado", FORA: "Fora do escopo" };
export function swapParams(o = {}) {
  return { qualifiedInvestor: false, durationBand: 1.5, sameTax: true, sameIndexer: true, ratingTolerance: 0, acceptUnrated: false,
    issuerLimit: 0.20, sectorLimit: 0.40, liquidityClass: "media", liquidityByCode: {}, bidAskByClass: { ...DEFAULT_BID_ASK },
    recMinDelta: 0.0030, recMaxPayback: 1.0, margMinDelta: 0.0010, margMaxPayback: 2.0, topN: 3, policy: taxPolicy(), ...o };
}
export function classify(delta, payback, eligible, p) {
  if (!eligible || delta == null || payback == null) return CLS.MANTER;
  if (delta >= p.recMinDelta && payback <= p.recMaxPayback) return CLS.RECOMENDADA;
  if (delta >= p.margMinDelta && payback <= p.margMaxPayback) return CLS.MARGINAL;
  return CLS.MANTER;
}
const yearsTo = (asOf, d) => (d != null ? Math.max(businessDays(asOf, d) / 252, 0) : 0);
export function anticipatedTaxPosition(h, asOf, sc) {
  const r = h.rate ? nominalExpected(h.rate, sc.cdi, sc.ipca) : 0;
  const tRest = yearsTo(asOf, h.position.maturity);
  let total = 0;
  for (const lot of h.position.lots) {
    const ir = lot.ir || 0;
    if (ir > 0 && tRest > 0) total += ir * (1 - (1 + r) ** -tRest);
    total += lot.iof || 0;
  }
  return total;
}
function deltaNtnbSpread(h, c, ntnb, asOf) {
  if (h.indexer !== Indexer.IPCA || c.indexer !== Indexer.IPCA || !ntnb.length) return null;
  const rh = ntnbReference(ntnb, { refYear: h.candidate ? h.candidate.ntnbRefYear : null, duration: h.duration ? h.duration.value : null, asOf });
  const rc = ntnbReference(ntnb, { refYear: c.ntnbRefYear, duration: c.duration, asOf });
  if (!rh || !rc) return null;
  return spreadOverNtnb(c.rate.value, rc.rate) - spreadOverNtnb(h.marketRate.value, rh.rate);
}
function evaluatePair(h, c, ctx) {
  const { params: p, scenario: sc } = ctx;
  const V = h.netValue, checks = [], alerts = [];
  const lastroOk = c.active && c.lastro != null && c.lastro >= V;
  checks.push({ name: "distribuição e lastro", passed: lastroOk, detail: `distribuição ${c.distribution || "—"}; lastro ${c.lastro == null ? "—" : fmtNum(c.lastro, 0)} vs saída ${fmtNum(V, 0)}` });
  checks.push({ name: "perfil do investidor", passed: !(c.qualifiedOnly && !p.qualifiedInvestor), detail: c.qualifiedOnly ? "exige investidor qualificado" : "público geral" });
  const exH = h.taxExempt.value, exC = p.policy.isExempt(c.product, c.taxExempt);
  if (p.sameTax) checks.push({ name: "tributação", passed: exH === exC, detail: `atual ${exH ? "isento" : "tributado"}; candidato ${exC ? "isento" : "tributado"}` });
  const sameIdx = c.indexer === h.indexer;
  if (p.sameIndexer) checks.push({ name: "indexador", passed: sameIdx, detail: `${h.indexer || "—"} → ${c.indexer || "—"}` });
  if (h.duration == null || c.duration == null) checks.push({ name: "duration", passed: false, detail: "duration ausente" });
  else {
    const dd = c.duration - h.duration.value;
    checks.push({ name: "duration", passed: Math.abs(dd) <= p.durationBand, detail: `${fmtNum(h.duration.value)} → ${fmtNum(c.duration)} anos (Δ ${fmtSigned(dd)}; banda ±${fmtNum(p.durationBand, 1)})` });
  }
  if (h.rating.notch != null && c.rating.notch != null) checks.push({ name: "rating", passed: c.rating.notch >= h.rating.notch - p.ratingTolerance, detail: `${h.rating.label} → ${c.rating.label}` });
  else {
    checks.push({ name: "rating", passed: p.acceptUnrated, detail: `sem rating (${h.rating.label || "—"} → ${c.rating.label || "—"}); ${p.acceptUnrated ? "aceito pelo usuário" : "exige confirmação"}` });
    alerts.push("rating ausente em um dos lados");
  }
  const tot = ctx.total, ik = issuerKey(c.issuer), sk = (c.sector || "").trim().toLowerCase();
  const expI = (ctx.byIssuer[ik] || 0) + V - (ik === h.issuerKey ? V : 0);
  const expS = (ctx.bySector[sk] || 0) + V - (sk === (h.sector || "").trim().toLowerCase() ? V : 0);
  if (tot > 0) {
    checks.push({ name: "concentração por emissor", passed: expI / tot <= p.issuerLimit, detail: `${fmtPct(expI / tot, 1)} do total analisado (limite ${fmtPct(p.issuerLimit, 0)})` });
    if (sk) checks.push({ name: "concentração por setor", passed: expS / tot <= p.sectorLimit, detail: `${fmtPct(expS / tot, 1)} (limite ${fmtPct(p.sectorLimit, 0)})` });
  }
  const res = { holding: h, candidate: c, checks, deltaRate: null, deltaSpread: null, deltaMetric: null, deltaMetricName: "", deltaNominal: null,
    gainAnnual: null, exitCostB: 0, taxAnticipated: 0, paybackA: null, paybackB: null, classA: CLS.MANTER, classB: CLS.MANTER, netGainB: null, alerts };
  res.eligible = checks.every((x) => x.passed);
  if (!h.rate || !c.rate) return res;
  let nH = nominalExpected(h.rate, sc.cdi, sc.ipca), nC = nominalExpected(c.rate, sc.cdi, sc.ipca);
  if (exH !== exC) {
    const irNew = p.policy.irRate(Math.round(sc.horizonYears * 365));
    nH = exH ? nH : nH * (1 - irNew); nC = exC ? nC : nC * (1 - irNew);
    alerts.push("tributações diferentes: comparação líquida de IR (aproximação)");
  }
  res.deltaNominal = nC - nH;
  if (sameIdx) res.deltaRate = rateDifference(c.rate, h.rate, sc.cdi);
  else { res.deltaRate = res.deltaNominal; alerts.push(`indexadores diferentes: comparação pela taxa nominal esperada no cenário '${sc.name}' (CDI ${fmtPct(sc.cdi)}, IPCA ${fmtPct(sc.ipca)})`); }
  res.deltaSpread = sameIdx ? deltaNtnbSpread(h, c, ctx.ntnb, ctx.asOf) : null;
  if (res.deltaSpread != null) { res.deltaMetric = res.deltaSpread; res.deltaMetricName = "Δ spread s/ NTN-B"; }
  else { res.deltaMetric = res.deltaRate; res.deltaMetricName = "Δ taxa"; if (sameIdx && h.indexer === Indexer.IPCA) alerts.push("sem NTN-B de referência: classificação pela diferença de taxa"); }
  res.gainAnnual = V * res.deltaNominal;
  const cls = p.liquidityByCode[h.code] || p.liquidityClass;
  const b = p.bidAskByClass[cls] ?? p.bidAskByClass.media ?? 0.0025;
  res.exitCostB = exitCost(b, h.dmod || 0) * V;
  res.taxAnticipated = ctx.taxByCode[h.code];
  if (res.gainAnnual > 0 && V) {
    res.paybackA = paybackYears(res.taxAnticipated / V, res.deltaNominal);
    res.paybackB = paybackYears((res.exitCostB + res.taxAnticipated) / V, res.deltaNominal);
  }
  res.classA = classify(res.deltaMetric, res.paybackA, res.eligible, p);
  res.classB = classify(res.deltaMetric, res.paybackB, res.eligible, p);
  if (res.classA !== res.classB) alerts.push("depende do preço real de recompra (cenários A e B divergem)");
  if (!exH && res.taxAnticipated > 0) alerts.push("a nova aplicação reinicia a tabela regressiva de IR");
  res.netGainB = res.gainAnnual - (res.exitCostB + res.taxAnticipated) / sc.horizonYears;
  return res;
}
function stats(items) {
  const tot = items.reduce((s, it) => s + it[0], 0);
  const wavg = (xs) => (xs.length ? xs.reduce((s, [v, x]) => s + v * x, 0) / xs.reduce((s, [v]) => s + v, 0) : null);
  const byI = {}, byS = {};
  for (const [v, , , i, s] of items) { byI[i] = (byI[i] || 0) + v; if (s) byS[s] = (byS[s] || 0) + v; }
  const share = (o) => (tot ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v / tot])) : {});
  return { total: tot, avgNominalRate: wavg(items.filter((x) => x[1] != null).map((x) => [x[0], x[1]])),
    avgDuration: wavg(items.filter((x) => x[2] != null).map((x) => [x[0], x[2]])), byIssuer: share(byI), bySector: share(byS) };
}
export function runSwaps(enriched, candidates, sc, asOf, params = swapParams(), ntnb = []) {
  const p = params;
  const scope = enriched.filter((h) => h.inScope);
  const total = scope.reduce((s, h) => s + h.netValue, 0);
  const byIssuer = {}, bySector = {};
  for (const h of scope) {
    byIssuer[h.issuerKey] = (byIssuer[h.issuerKey] || 0) + h.netValue;
    const s = (h.sector || "").trim().toLowerCase(); if (s) bySector[s] = (bySector[s] || 0) + h.netValue;
  }
  const ctx = { params: p, scenario: sc, asOf, total, byIssuer, bySector, ntnb, taxByCode: Object.fromEntries(scope.map((h) => [h.code, anticipatedTaxPosition(h, asOf, sc)])) };
  const results = [];
  for (const h of enriched) {
    if (!h.inScope) { results.push({ holding: h, best: [], evaluated: 0, rejectedBy: {}, status: CLS.FORA }); continue; }
    if (!h.marketRate) { results.push({ holding: h, best: [], evaluated: 0, rejectedBy: {}, status: CLS.SEM_TAXA }); continue; }
    const pairs = candidates.filter((c) => c.code !== h.code).map((c) => evaluatePair(h, c, ctx));
    const rejectedBy = {};
    for (const pr of pairs) for (const ch of pr.checks) if (!ch.passed) rejectedBy[ch.name] = (rejectedBy[ch.name] || 0) + 1;
    const ok = pairs.filter((pr) => pr.eligible && pr.netGainB != null).sort((a, b) => b.netGainB - a.netGainB);
    const best = ok.slice(0, p.topN);
    results.push({ holding: h, best, evaluated: pairs.length, rejectedBy, status: best.length ? best[0].classB : CLS.MANTER });
  }
  const item = (h) => [h.netValue, h.rate ? nominalExpected(h.rate, sc.cdi, sc.ipca) : null, h.duration ? h.duration.value : null, h.issuerKey, (h.sector || "").trim().toLowerCase()];
  const before = stats(scope.map(item));
  const lastroLeft = Object.fromEntries(candidates.map((c) => [c.code, c.lastro || 0]));
  const applied = [], alerts = [], swapped = new Map();
  const swaps = results.filter((r) => r.best[0] && r.best[0].classB === CLS.RECOMENDADA).sort((a, b) => b.best[0].netGainB - a.best[0].netGainB);
  for (const r of swaps) {
    const pr = r.best.find((x) => x.classB === CLS.RECOMENDADA && lastroLeft[x.candidate.code] >= r.holding.netValue);
    if (!pr) { alerts.push(`${r.holding.code}: lastro esgotado pelas outras trocas`); continue; }
    lastroLeft[pr.candidate.code] -= r.holding.netValue;
    swapped.set(r.holding.code, pr); applied.push(pr);
  }
  const after = stats(scope.map((h) => {
    const pr = swapped.get(h.code);
    if (!pr) return item(h);
    const c = pr.candidate;
    return [h.netValue, nominalExpected(c.rate, sc.cdi, sc.ipca), c.duration, issuerKey(c.issuer), (c.sector || "").trim().toLowerCase()];
  }));
  return { scenario: sc, params: p, asOf, results, before, after, applied, totalGainAnnual: applied.reduce((s, pr) => s + (pr.gainAnnual || 0), 0), alerts };
}

// ============================================================================ relatório
export const AVISO = "Ferramenta analítica: não constitui recomendação de investimento. Os limiares de classificação são hipóteses ainda não validadas por backtest.";
export const LASTRO_COL = "Lastro disponível", DESK_SPREAD_COL = "Spread estimado da mesa (bps)", REVIEW_COL = "Revisar (spread > 150 bps)";
export function sanitize(text, mode) {
  if (mode !== "cliente" || typeof text !== "string") return text;
  return text.replace(/\b([dn])o\s+(run\s*-?\s*flow)/gi, (_, p) => `${p}a oferta disponível`)
    .replace(/run\s*-?\s*flow/gi, "oferta disponível").replace(/\s*(e\s+)?lastro(\s+dispon[ií]vel)?/gi, "");
}
const clean = (row, mode) => Object.fromEntries(Object.entries(row).map(([k, v]) => [sanitize(k, mode), sanitize(v, mode)]));
const rateOf = (idx, v) => (v == null || idx == null ? "—" : rateStr({ indexer: idx, value: v }));
export function positionsTable(enriched, mode) {
  return enriched.map((e) => {
    const p = e.position, mr = e.marketRate, du = e.duration;
    const row = { "Código": e.code, "Tipo": p.assetType, "Emissor": p.issuer, "Indexador": e.indexer || "—", "Vencimento": p.maturity == null ? null : brDate(p.maturity),
      "Valor líquido": p.netValue, "Taxa de mercado": rateOf(e.indexer, mr ? mr.value : null), "Fonte da taxa": mr ? mr.source : "—",
      "Natureza da taxa": mr ? mr.kind : "—", "Duration (anos)": du ? Math.round(du.value * 100) / 100 : null, "Fonte da duration": du ? du.source : "—",
      "Rating": e.rating.label || "—", "Isento": e.taxExempt.value ? "sim" : "não", "Marcação vs curva": e.mtmVsCurve,
      "Na análise": e.inScope ? "sim" : `não (${e.scopeNote})`, "Alertas": e.alerts.join("; ") };
    if (mode === "interno") { row[DESK_SPREAD_COL] = e.deskSpread != null ? Math.round(e.deskSpread * 1e5) / 10 : null; row[REVIEW_COL] = e.review ? "sim" : ""; }
    return clean(row, mode);
  });
}
export function justification(pr, mode) {
  const parts = pr.checks.map((ch) => {
    let name = ch.name, detail = ch.detail;
    if (mode === "cliente" && ch.name === "distribuição e lastro") { name = "disponibilidade"; detail = ch.passed ? "disponível" : "indisponível para o valor da posição"; }
    return `${ch.passed ? "✓" : "✗"} ${name}: ${detail}`;
  });
  if (pr.deltaMetric != null) parts.push(`${pr.deltaMetricName}: ${fmtBps(pr.deltaMetric, 1)}`);
  if (pr.paybackB != null) parts.push(`equilíbrio A ${fmtNum(pr.paybackA)} / B ${fmtNum(pr.paybackB)} anos`);
  parts.push(...pr.alerts);
  return sanitize(parts.join(" | "), mode);
}
export function swapsTable(rep, mode, labels = {}) {
  const rows = [];
  for (const r of rep.results) {
    const h = r.holding;
    const base = { "Posição": h.code, "Emissor atual": h.position.issuer, "Valor de saída": h.netValue, "Taxa atual": rateOf(h.indexer, h.marketRate ? h.marketRate.value : null), "Situação": r.status };
    if (!r.best.length) { rows.push(clean({ ...base, "Rank": null, "Candidato": "—", "Classificação (B)": r.status }, mode)); continue; }
    r.best.forEach((pr, k) => {
      const c = pr.candidate;
      const row = { ...base, "Rank": k + 1, "Candidato": c.code, "Emissor candidato": c.issuer, "Taxa candidato": c.rate ? rateStr(c.rate) : "—",
        "Duration candidato": c.duration, "Rating candidato": c.rating.label || "—", "Δ usado": fmtBps(pr.deltaMetric, 1), "Medida do Δ": pr.deltaMetricName,
        "Ganho anual (R$)": pr.gainAnnual, "Custo de saída B (R$)": pr.exitCostB, "Imposto antecipado (R$)": pr.taxAnticipated,
        "Equilíbrio A (anos)": pr.paybackA, "Equilíbrio B (anos)": pr.paybackB, "Classificação (A)": pr.classA, "Classificação (B)": pr.classB,
        "Justificativa": justification(pr, mode) };
      if (mode === "interno") { row[LASTRO_COL] = c.lastro; for (const [f, v] of Object.entries(c.internal || {})) row[labels[f] || f] = v; }
      rows.push(clean(row, mode));
    });
  }
  return rows;
}
export function summaryTable(rep) {
  const b = rep.before, a = rep.after;
  const top = (d) => Object.entries(d).sort((x, y) => y[1] - x[1]).slice(0, 3).map(([k, v]) => `${k} ${fmtPct(v, 0)}`).join(", ");
  const dur = (x) => (x == null ? "—" : fmtNum(x));
  return [
    { "Item": "Valor analisado", "Antes": fmtBrl(b.total), "Depois": fmtBrl(a.total) },
    { "Item": "Taxa nominal esperada média", "Antes": fmtPct(b.avgNominalRate), "Depois": fmtPct(a.avgNominalRate) },
    { "Item": "Duration média (anos)", "Antes": dur(b.avgDuration), "Depois": dur(a.avgDuration) },
    { "Item": "Maiores emissores", "Antes": top(b.byIssuer), "Depois": top(a.byIssuer) },
    { "Item": "Maiores setores", "Antes": top(b.bySector), "Depois": top(a.bySector) },
    { "Item": "Trocas recomendadas aplicadas", "Antes": "", "Depois": String(rep.applied.length) },
    { "Item": "Ganho anual estimado", "Antes": "", "Depois": fmtBrl(rep.totalGainAnnual) },
  ];
}
export function assumptionsTable(rep) {
  const s = rep.scenario, p = rep.params;
  return [
    { "Premissa": "Aviso", "Valor": AVISO },
    { "Premissa": "Data da posição", "Valor": brDate(rep.asOf) },
    { "Premissa": "Cenário", "Valor": `${s.name}: CDI ${fmtPct(s.cdi)}, IPCA ${fmtPct(s.ipca)} (horizonte ${s.horizonYears} ano)` },
    { "Premissa": "Fontes do cenário", "Valor": `${s.cdiSource}; ${s.ipcaSource}` },
    { "Premissa": "Classificação", "Valor": "pelo cenário B (PU Mercado = marcação)" },
    { "Premissa": "Limiares (hipóteses)", "Valor": `recomendada Δ ≥ ${fmtBps(p.recMinDelta)} e equilíbrio ≤ ${p.recMaxPayback} ano; marginal Δ ≥ ${fmtBps(p.margMinDelta)} e equilíbrio ≤ ${p.margMaxPayback} anos` },
    { "Premissa": "Custo de saída (b por classe, hipótese)", "Valor": Object.entries(p.bidAskByClass).map(([k, v]) => `${k} ${fmtBps(v)}`).join(", ") },
    { "Premissa": "Tributação", "Valor": `investidor ${p.policy.investor}; tabelas: ${p.policy.status}` },
  ];
}
