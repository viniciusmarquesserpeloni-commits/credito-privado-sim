// =============================================================================================
// cpsim — motor em JavaScript (porte do núcleo Python em src/cpsim/)
//
// O Python é a REFERÊNCIA. Este arquivo replica as mesmas funções, com os mesmos nomes de
// conceitos, e é conferido contra resultados gerados pelo Python (offline/tests/fixtures.json).
// Qualquer mudança de fórmula deve ser feita nos dois lados, com fixture atualizada.
//
// Convenções: datas = número de dias desde 1970-01-01 (UTC); taxas em decimal (0.1437);
// em %CDI a taxa é a fração do CDI (1.045). Nada aqui acessa a página (DOM) nem a rede.
// =============================================================================================

// ------------------------------------------------------------------------------- datas
const DAY = 86400000;
export function D(y, m, d) { return Math.floor(Date.UTC(y, m - 1, d) / DAY); }
export function ymd(dn) { const t = new Date(dn * DAY); return [t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()]; }
export function isoDate(dn) { const [y, m, d] = ymd(dn); return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`; }
export function brDate(dn) { if (dn == null) return "—"; const [y, m, d] = ymd(dn); return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y}`; }
export function fromIso(s) { const [y, m, d] = s.slice(0, 10).split("-").map(Number); return D(y, m, d); }
function weekday(dn) { return (new Date(dn * DAY).getUTCDay() + 6) % 7; } // 0 = segunda
function monthLen(y, m) { return new Date(Date.UTC(y, m, 0)).getUTCDate(); }
export function todayDn() { const t = new Date(); return D(t.getFullYear(), t.getMonth() + 1, t.getDate()); }

// ------------------------------------------------------------------------------- normalização
export function stripAccents(s) { return String(s ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, ""); }
export function normHeader(s) { if (s == null) return ""; return stripAccents(String(s)).replace(/\s+/g, " ").trim().toLowerCase(); }
const NUM_GAPS = /(?<=[\d.,])\s+(?=[\d.,%])|(?<=\d)\s+(?=[.,])/g;
export function squashNumberGaps(s) { let prev = null; while (prev !== s) { prev = s; s = s.replace(NUM_GAPS, ""); } return s; }
function strictFloat(t) { if (t === "" || t == null) return null; const v = Number(t); return Number.isFinite(v) ? v : null; }

export function parseBrl(s) {
  if (s == null) return null;
  let t = String(s).trim();
  if (["", "-", "—"].includes(t)) return null;
  t = t.replace("R$", "").replace(/ /g, "").replace(/ /g, "");
  if (["", "-", "—"].includes(t)) return null;
  const neg = t.startsWith("-") || (t.startsWith("(") && t.endsWith(")"));
  t = t.replace(/^[-()]+|[-()]+$/g, "").replace(/\./g, "").replace(",", ".");
  const v = strictFloat(t);
  if (v == null) return null;
  return neg ? -v : v;
}

export function parseNumber(v) {
  if (v == null || typeof v === "boolean") return null;
  if (typeof v === "number") return v;
  if (typeof v === "object") return null;
  let t = String(v).trim().replace("R$", "").replace(/ /g, "").replace(/ /g, "");
  if (["", "-", "—"].includes(t)) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  return strictFloat(t);
}

export function parsePercent(v) {
  if (v == null || typeof v === "boolean") return [null, false];
  if (typeof v === "number") return [v, false];
  if (typeof v === "object") return [null, false];
  let t = squashNumberGaps(String(v).trim());
  const hasPct = t.includes("%");
  t = t.replace(/%/g, "").trim();
  if ((t.match(/,/g) || []).length === 1 && (t.match(/\./g) || []).length >= 1) t = t.replace(/\./g, "").replace(",", ".");
  else t = t.replace(/,/g, ".");
  return [strictFloat(t), hasPct];
}

export function parseDateBr(s) {
  if (s == null) return null;
  if (typeof s === "object" && "dn" in s) return s.dn;
  if (typeof s === "number") return null;
  const t = String(s).replace(/ /g, "").trim();
  const m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (mo < 1 || mo > 12 || d < 1 || d > monthLen(y, mo)) return null;
  return D(y, mo, d);
}

function brNum(x, casas) { return x.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }); }
export function fmtPct(x, casas = 2) { return x == null ? "—" : `${brNum(x * 100, casas)}%`; }
export function fmtBps(x, casas = 0) { return x == null ? "—" : `${brNum(x * 10000, casas)} bps`; }
export function fmtBrl(x) { return x == null ? "—" : `${x < 0 ? "-R$ " : "R$ "}${brNum(Math.abs(x), 2)}`; }
export function fmtNum(x, casas = 2) { return x == null || Number.isNaN(x) ? "—" : brNum(x, casas); }

// ------------------------------------------------------------------------------- calendário
const FIXED = [[1, 1], [4, 21], [5, 1], [9, 7], [10, 12], [11, 2], [11, 15], [12, 25]];
const MIN_YEAR = 1990, MAX_YEAR = 2100;
export function easter(year) {
  const a = year % 19, b = Math.floor(year / 100), c = year % 100, d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return D(year, Math.floor(n / 31), (n % 31) + 1);
}
const _hol = new Map();
export function holidays(year) {
  if (_hol.has(year)) return _hol.get(year);
  const s = new Set(FIXED.map(([m, d]) => D(year, m, d)));
  if (year >= 2024) s.add(D(year, 11, 20));
  const p = easter(year);
  [p - 48, p - 47, p - 2, p + 60].forEach((x) => s.add(x));
  _hol.set(year, s);
  return s;
}
export function isBusinessDay(dn) { return weekday(dn) < 5 && !holidays(ymd(dn)[0]).has(dn); }
let _cum = null; const CAL0 = D(MIN_YEAR, 1, 1), CAL1 = D(MAX_YEAR, 12, 31) + 1;
function cum() {
  if (_cum) return _cum;
  _cum = new Int32Array(CAL1 - CAL0 + 1);
  for (let i = 0; i < CAL1 - CAL0; i++) _cum[i + 1] = _cum[i] + (isBusinessDay(CAL0 + i) ? 1 : 0);
  return _cum;
}
function check(dn) { if (dn < CAL0 || dn > CAL1) throw new Error(`data fora do calendário suportado (${MIN_YEAR}–${MAX_YEAR})`); }
/** Dias úteis em [d0, d1). */
export function businessDays(d0, d1) { check(d0); check(d1); const c = cum(); return c[d1 - CAL0] - c[d0 - CAL0]; }
export function following(dn) { while (!isBusinessDay(dn)) dn += 1; return dn; }

// ------------------------------------------------------------------------------- taxas
export const Indexer = { PRE: "PRE", IPCA: "IPCA", CDI_PCT: "%CDI", CDI_SPREAD: "CDI+" };
export const annualToDaily = (r) => (1 + r) ** (1 / 252) - 1;
export const dailyToAnnual = (d) => (1 + d) ** 252 - 1;
export const cdiSgsToAnnual = (pct) => dailyToAnnual(pct / 100);
export const compound = (r, du) => (1 + r) ** (du / 252);
export const pctCdiToAnnual = (p, cdi) => dailyToAnnual(p * annualToDaily(cdi));
export const cdiPlusToAnnual = (s, cdi) => (1 + cdi) * (1 + s) - 1;
export const ipcaPlusToNominal = (real, ipca) => (1 + real) * (1 + ipca) - 1;
export const spreadOver = (r, base) => (1 + r) / (1 + base) - 1;
export function nominalExpected(rate, cdi, ipca) {
  switch (rate.indexer) {
    case Indexer.PRE: return rate.value;
    case Indexer.IPCA: return ipcaPlusToNominal(rate.value, ipca);
    case Indexer.CDI_PCT: return pctCdiToAnnual(rate.value, cdi);
    case Indexer.CDI_SPREAD: return cdiPlusToAnnual(rate.value, cdi);
  }
  throw new Error(rate.indexer);
}
export function rateDifference(a, b, cdi = null) {
  if (a.indexer !== b.indexer) throw new Error("indexadores diferentes");
  if (a.indexer === Indexer.CDI_PCT) { if (cdi == null) throw new Error("%CDI exige o CDI"); return (a.value - b.value) * cdi; }
  return a.value - b.value;
}
export function rateStr(rate) {
  if (!rate) return "—";
  const v = brNum(rate.value * 100, 2);
  return { PRE: `${v}% a.a.`, IPCA: `IPCA + ${v}%`, "%CDI": `${v}% do CDI`, "CDI+": `CDI + ${v}%` }[rate.indexer];
}
const INDEXER_ALIASES = { pre: "PRE", "pré": "PRE", prefixado: "PRE", ipca: "IPCA", "ipca+": "IPCA", "%cdi": "%CDI", "% cdi": "%CDI", "cdi%": "%CDI", "+cdi": "CDI+", "cdi+": "CDI+", "cdi +": "CDI+", "di+": "CDI+", "+di": "CDI+" };
export function parseIndexer(text) {
  if (text == null) return null;
  const t = String(text).trim().toLowerCase().replace(/\s+/g, " ");
  return INDEXER_ALIASES[t] || INDEXER_ALIASES[stripAccents(t)] || null;
}

// ------------------------------------------------------------------------------- rating
const SCALE = ["D", "C", "CC", "CCC-", "CCC", "CCC+", "B-", "B", "B+", "BB-", "BB", "BB+", "BBB-", "BBB", "BBB+", "A-", "A", "A+", "AA-", "AA", "AA+", "AAA"];
export const NOTCH = Object.fromEntries(SCALE.map((l, i) => [l, i]));
const MOODYS = { AAA: "AAA", AA1: "AA+", AA2: "AA", AA3: "AA-", A1: "A+", A2: "A", A3: "A-", BAA1: "BBB+", BAA2: "BBB", BAA3: "BBB-", BA1: "BB+", BA2: "BB", BA3: "BB-", B1: "B+", B2: "B", B3: "B-", CAA1: "CCC+", CAA2: "CCC", CAA3: "CCC-", CA: "CC" };
export function parseRating(text) {
  const raw = text == null ? "" : String(text).trim();
  if (["", "0", "-", "—", "NR", "nr", "n/a", "N/A", "SR", "sem rating"].includes(raw)) return { raw, label: null, notch: null };
  let t = raw.toUpperCase().replace(/ /g, "");
  t = t.replace(/\((BRA|BR|EXP|SF|P)\)/g, "").replace(/\.(BR|SF)\b/g, "").replace(/SF$/, "").replace(/^BR(?=[ABCD])/, "").replace(/BR$/, "").replace(/^\.+|\.+$/g, "");
  if (MOODYS[t]) t = MOODYS[t];
  if (t in NOTCH) return { raw, label: t, notch: NOTCH[t] };
  return { raw, label: null, notch: null };
}

// ------------------------------------------------------------------------------- preço
export const price = (flows, y) => flows.reduce((s, [t, fc]) => s + fc / (1 + y) ** t, 0);
export function macaulayDuration(flows, y) { return flows.reduce((s, [t, fc]) => s + (t * fc) / (1 + y) ** t, 0) / price(flows, y); }
export const modifiedDuration = (flows, y) => macaulayDuration(flows, y) / (1 + y);
export function convexity(flows, y) { return flows.reduce((s, [t, fc]) => s + (t * (t + 1) * fc) / (1 + y) ** t, 0) / (price(flows, y) * (1 + y) ** 2); }
export const dv01 = (flows, y) => modifiedDuration(flows, y) * price(flows, y) * 1e-4;
export const priceChangeApprox = (dmod, conv, dy) => -dmod * dy + 0.5 * conv * dy * dy;
export function annualFlows(coupon, years, face = 100) { const out = []; for (let t = 1; t <= years; t++) out.push([t, face * coupon + (t === years ? face : 0)]); return out; }

export function brent(f, a, b, tol = 1e-12, maxiter = 200) {
  let fa = f(a), fb = f(b);
  if (fa === 0) return a;
  if (fb === 0) return b;
  if (fa * fb > 0) throw new Error("a raiz não está no intervalo");
  if (Math.abs(fa) < Math.abs(fb)) { [a, b] = [b, a]; [fa, fb] = [fb, fa]; }
  let c = a, fc = fa, mflag = true, d = 0;
  for (let it = 0; it < maxiter; it++) {
    let s;
    if (fa !== fc && fb !== fc) s = (a * fb * fc) / ((fa - fb) * (fa - fc)) + (b * fa * fc) / ((fb - fa) * (fb - fc)) + (c * fa * fb) / ((fc - fa) * (fc - fb));
    else s = b - (fb * (b - a)) / (fb - fa);
    const lo = (3 * a + b) / 4;
    const cond = !((lo < s && s < b) || (b < s && s < lo))
      || (mflag && Math.abs(s - b) >= Math.abs(b - c) / 2)
      || (!mflag && Math.abs(s - b) >= Math.abs(c - d) / 2)
      || (mflag && Math.abs(b - c) < tol)
      || (!mflag && Math.abs(c - d) < tol);
    if (cond) { s = (a + b) / 2; mflag = true; } else mflag = false;
    const fs = f(s);
    d = c; c = b; fc = fb;
    if (fa * fs < 0) { b = s; fb = fs; } else { a = s; fa = fs; }
    if (Math.abs(fa) < Math.abs(fb)) { [a, b] = [b, a]; [fa, fb] = [fb, fa]; }
    if (fb === 0 || Math.abs(b - a) < tol) return b;
  }
  return b;
}
export function yieldFromPrice(flows, pu, lo = -0.5, hi = 5.0) { if (!flows.length) throw new Error("sem fluxos"); return brent((y) => price(flows, y) - pu, lo, hi); }
export function expectedReturnApprox(carry, o = {}) {
  const { dmod = 0, rolldownDy = 0, dr = 0, spreadDuration = 0, ds = 0, conv = 0, dy = 0, expectedLoss = 0, costs = 0 } = o;
  return carry + dmod * rolldownDy - dmod * dr - spreadDuration * ds + 0.5 * conv * dy * dy - expectedLoss - costs;
}

// ------------------------------------------------------------------------------- fluxos
const MONTHS = { jan: 1, fev: 2, mar: 3, abr: 4, mai: 5, jun: 6, jul: 7, ago: 8, set: 9, out: 10, nov: 11, dez: 12 };
const STEP = { mensal: 1, bimestral: 2, trimestral: 3, quadrimestral: 4, semestral: 6, anual: 12 };
const normTxt = (t) => stripAccents(t || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
function monthsFromStep(step, anchor) { const s = new Set(); for (let k = 0; k < 12 / step; k++) s.add(((anchor - 1 + k * step) % 12) + 1); return [...s].sort((a, b) => a - b); }
export function parseMonths(text, maturity) {
  const t = normTxt(String(text || "").replace(/\(.*?\)/g, ""));
  if (["bullet", "no vencimento", "vencimento", "final"].includes(t)) return [];
  if (t in STEP) return monthsFromStep(STEP[t], ymd(maturity)[1]);
  const parts = t.split(/\s*(?:[/,;-]|\be\b)\s*/).map((p) => p.trim().slice(0, 3)).filter(Boolean);
  if (parts.length && parts.every((p) => p in MONTHS)) return [...new Set(parts.map((p) => MONTHS[p]))].sort((a, b) => a - b);
  return null;
}
export function parseAmortization(text, maturity) {
  const raw = text || "";
  let months = parseMonths(raw, maturity);
  if (months == null) return null;
  if (months.length === 0) return [[], null];
  let start = null;
  const m = stripAccents(raw).match(/\(\s*in[ií]cio\s+([^)]*)\)/i);
  if (m) {
    const s = normTxt(m[1]);
    const mmy = s.match(/^([a-z]{3})[a-z]*\s*\/?\s*(\d{2}|\d{4})$/);
    const my = s.match(/^(\d{4})$/);
    if (mmy && mmy[1] in MONTHS) {
      let y = Number(mmy[2]); y = y > 1000 ? y : 2000 + y;
      start = D(y, MONTHS[mmy[1]], 1);
      const step = STEP[normTxt(raw.replace(/\(.*?\)/g, ""))];
      if (step) months = monthsFromStep(step, MONTHS[mmy[1]]);
    } else if (my) start = D(Number(my[1]), 1, 1);
    else return null;
  }
  return [months, start];
}
const onDay = (y, m, day) => D(y, m, Math.min(day, monthLen(y, m)));
function datesInMonths(months, day, after, until, start = null) {
  const out = [];
  for (let y = ymd(after)[0]; y <= ymd(until)[0]; y++) for (const mo of months) { const d = onDay(y, mo, day); if (after < d && d <= until && (start == null || d >= start)) out.push(d); }
  return out;
}
function previousCoupon(months, day, valuation) {
  const y = ymd(valuation)[0];
  const past = [y - 1, y].flatMap((yy) => months.map((mo) => onDay(yy, mo, day))).filter((d) => d <= valuation);
  return past.length ? Math.max(...past) : valuation;
}
/** Fluxo por unidade de saldo atual (saldo = 1 na avaliação). Ver src/cpsim/cashflows.py. */
export function buildSchedule(valuation, maturity, couponText, amortText, couponRate) {
  const w = [];
  if (maturity <= valuation) return { flows: [], warnings: ["papel vencido na data de avaliação"], ok: false };
  const cm = parseMonths(couponText, maturity), am = parseAmortization(amortText, maturity);
  if (cm == null) w.push(`cupom não reconhecido: '${couponText}'`);
  if (am == null) w.push(`amortização não reconhecida: '${amortText}'`);
  if (cm == null || am == null) return { flows: [], warnings: w, ok: false };
  const day = ymd(maturity)[2];
  const couponDates = new Set([...datesInMonths(cm, day, valuation, maturity), maturity]);
  const [aMonths, aStart] = am;
  const amortDates = new Set([...datesInMonths(aMonths, day, valuation, maturity, aStart), maturity]);
  const events = [...new Set([...couponDates, ...amortDates])].sort((a, b) => a - b);
  const parcel = 1 / amortDates.size;
  let accrStart;
  if (cm.length) accrStart = previousCoupon(cm, day, valuation);
  else { accrStart = valuation; w.push("cupom bullet: juros contados a partir da data de avaliação"); }
  let outstanding = 1, accrued = 0, prev = accrStart;
  const flows = [];
  for (const d of events) {
    const pay = following(d);
    const segDu = businessDays(prev < valuation ? following(prev) : prev, pay);
    accrued += outstanding * ((1 + couponRate) ** (Math.max(segDu, 0) / 252) - 1);
    let interest = 0;
    if (couponDates.has(d)) { interest = accrued; accrued = 0; }
    let amort = amortDates.has(d) ? parcel : 0;
    if (d === maturity) amort = outstanding;
    const du = businessDays(valuation, pay);
    flows.push({ date: d, payDate: pay, du, t: du / 252, interest, amortization: amort, total: interest + amort });
    outstanding -= amort;
    prev = pay;
  }
  return { flows, warnings: w, ok: flows.length > 0, approximate: true };
}
export const pricingFlows = (sch) => sch.flows.map((f) => [f.t, f.total]);

// ------------------------------------------------------------------------------- impostos
export const IR_PADRAO = [[180, 0.225], [360, 0.20], [720, 0.175], [null, 0.15]];
export const IOF_PADRAO = [0.96, 0.93, 0.90, 0.86, 0.83, 0.80, 0.76, 0.73, 0.70, 0.66, 0.63, 0.60, 0.56, 0.53, 0.50, 0.46, 0.43, 0.40, 0.36, 0.33, 0.30, 0.26, 0.23, 0.20, 0.16, 0.13, 0.10, 0.06, 0.03];
export function taxPolicy(investor = "PF") {
  return {
    investor, irTable: IR_PADRAO, iofTable: IOF_PADRAO, status: "confirmar vigência",
    pfExemptProducts: new Set(["CRI", "CRA", "CPR", "LCI", "LCA"]),
    irRate(days) { if (days < 0) throw new Error("prazo negativo"); for (const [lim, r] of this.irTable) if (lim == null || days <= lim) return r; return this.irTable.at(-1)[1]; },
    iofRate(days) { if (days <= 0) return 1; if (days > this.iofTable.length) return 0; return this.iofTable[days - 1]; },
    isExempt(product, flagged) { if (this.investor.toUpperCase() !== "PF") return false; if (flagged != null) return flagged; return this.pfExemptProducts.has((product || "").toUpperCase()); },
  };
}
export function anticipatedTax(ir, gain, r, tRest) { if (gain <= 0 || ir <= 0) return 0; return ir * gain * (1 - (1 + r) ** -tRest); }
export const grossUpNominal = (n, ir) => n / (1 - ir);
export const grossUpIpcaSpread = (real, ipca, ir) => (1 + grossUpNominal((1 + real) * (1 + ipca) - 1, ir)) / (1 + ipca) - 1;

// ------------------------------------------------------------------------------- spreads
export const spreadOverNtnb = spreadOver;
export const DEFAULT_BID_ASK = { alta: 0.0010, media: 0.0025, baixa: 0.0050 };
export const exitCost = (b, dmod) => (b / 2) * dmod;
export const breakevenSpreadWidening = (s, h, ds) => (s * h) / ds;
export const impliedDefaultIntensity = (s, lgd) => s / lgd;
export const paybackYears = (cost, gain) => (gain <= 0 ? null : cost / gain);
export function ntnbReference(quotes, { refYear = null, duration = null, asOf = null } = {}) {
  if (!quotes.length) return null;
  if (refYear != null) { const same = quotes.filter((q) => ymd(q.maturity)[0] === refYear); if (same.length) return same[0]; }
  if (duration == null) return null;
  const withD = quotes.filter((q) => q.duration != null);
  if (withD.length) return withD.reduce((b, q) => (Math.abs(q.duration - duration) < Math.abs(b.duration - duration) ? q : b));
  if (asOf == null) return null;
  return quotes.reduce((b, q) => (Math.abs((q.maturity - asOf) / 365.25 - duration) < Math.abs((b.maturity - asOf) / 365.25 - duration) ? q : b));
}
