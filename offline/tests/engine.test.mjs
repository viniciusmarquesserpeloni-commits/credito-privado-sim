// Motor JavaScript × núcleo Python (referência). Fixture: scripts/make_js_fixtures.py.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as E from "../src/engine.mjs";
import * as P from "../src/parsers.mjs";
import * as A from "../src/analysis.mjs";
import * as X from "../src/xlsx.mjs";
import { extractFragments } from "./pdf_node.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(here, "..", "..");
const FX = JSON.parse(fs.readFileSync(path.join(here, "fixtures.json"), "utf8"));
const iso = (dn) => (dn == null ? null : E.isoDate(dn));
const close = (a, b, tol = 1e-9, msg = "") => {
  if (a == null || b == null) return assert.equal(a, b, msg);
  assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${msg}: ${a} ≠ ${b}`);
};
const rateEq = (a, b, msg) => { if (!a || !b) return assert.equal(a, b, msg); assert.equal(a.indexer, b.indexer, msg); close(a.value, b.value, 1e-12, msg); };

async function loadInputs() {
  const cfg = P.parseInternalColumns(fs.readFileSync(path.join(ROOT, "config", "runflow_columns.example.toml"), "utf8"), "exemplo");
  const rf = P.readRunflowSheets(await X.readXlsx(fs.readFileSync(path.join(ROOT, "data", "samples", "runflow_exemplo.xlsx"))), cfg);
  const payloads = Object.fromEntries(P.PUBLIC_FILES.map((n) => [n, JSON.parse(fs.readFileSync(path.join(ROOT, "data", "public", `${n}.json`), "utf8"))]));
  return { rf, pd: P.publicFromPayloads(payloads) };
}
async function mapaOf(nome) {
  const { frags, nPages } = await extractFragments(fs.readFileSync(path.join(ROOT, "data", "samples", nome)));
  return P.parseMapaFragments(frags, nPages);
}

test("calendário: dias úteis e feriados iguais ao Python", () => {
  for (const [a, b, n] of FX.businessDays) assert.equal(E.businessDays(E.fromIso(a), E.fromIso(b)), n, `${a}→${b}`);
  assert.deepEqual([...E.holidays(2026)].map(E.isoDate).sort(), FX.holidays2026);
});

test("casos-ouro da metodologia", () => {
  const f = E.annualFlows(0.12, 3), g = FX.golden;
  close(E.price(f, 0.13), g.pu); close(E.macaulayDuration(f, 0.13), g.dmac); close(E.modifiedDuration(f, 0.13), g.dmod);
  close(E.convexity(f, 0.13), g.conv); close(E.dv01(f, 0.13), g.dv01); close(E.spreadOverNtnb(0.078, 0.072), g.spread);
  close(E.grossUpIpcaSpread(0.078, 0.04, 0.15), g.grossup);
  close(E.anticipatedTax(0.15, 15, E.ipcaPlusToNominal(0.065, 0.04), 4), g.antecipado);
  close(E.pctCdiToAnnual(1.045, 0.14), g.pctcdi);
  assert.ok(Math.abs(E.yieldFromPrice(f, g.pu) - 0.13) < 1e-10);
});

test("fluxos aproximados iguais ao Python", () => {
  for (const s of FX.schedules) {
    const [v, m, c, a, r] = s.args;
    const js = E.buildSchedule(E.fromIso(v), E.fromIso(m), c, a, r);
    assert.deepEqual(js.warnings, s.warnings);
    assert.equal(js.flows.length, s.flows.length, s.args.join(" "));
    js.flows.forEach((f, i) => {
      const [d, pay, du, int, am] = s.flows[i];
      assert.equal(iso(f.date), d); assert.equal(iso(f.payDate), pay); assert.equal(f.du, du);
      close(f.interest, int, 1e-12); close(f.amortization, am, 1e-12);
    });
  }
});

for (const nome of ["mapa_posicoes_exemplo.pdf", "mapa_posicoes_layout_real.pdf"]) {
  test(`Mapa (pdf.js) igual ao Python (pypdf): ${nome}`, async () => {
    const m = await mapaOf(nome), ref = FX.mapa[nome];
    assert.equal(iso(m.positionDate), ref.positionDate);
    assert.deepEqual(m.warnings, ref.warnings);
    assert.equal(m.lots.length, ref.lots.length);
    m.lots.forEach((l, i) => {
      const r = ref.lots[i], tag = `${nome} lote ${i} ${r.code}`;
      for (const k of ["page", "code", "assetType", "title", "issuer", "quantity", "puPurchase", "puCurve", "grossCurve", "puMarket", "grossMarket", "ir", "iof", "netValue", "income", "errors", "warnings"])
        assert.deepEqual(l[k], r[k], `${tag} ${k}`);
      for (const k of ["emission", "maturity", "purchaseDate"]) assert.equal(iso(l[k]), r[k], `${tag} ${k}`);
      rateEq(l.rate, r.rate, `${tag} rate`); rateEq(l.titleRate, r.titleRate, `${tag} titleRate`);
    });
  });
}

test("Runflow (leitor xlsx próprio) igual ao Python (openpyxl)", async () => {
  const { rf } = await loadInputs(), ref = FX.runflow;
  assert.deepEqual(rf.missing, ref.missing); assert.deepEqual(rf.extra, ref.extra);
  assert.equal(rf.candidates.length, ref.candidates.length);
  rf.candidates.forEach((c, i) => {
    const r = ref.candidates[i];
    for (const k of ["code", "issuer", "product", "active", "lastro", "qtyAvailable", "duration", "ntnbRefYear", "coupon", "amortization", "sector", "qualifiedOnly", "taxExempt", "internal", "warnings"])
      assert.deepEqual(c[k], r[k], `${r.code} ${k}`);
    assert.equal(iso(c.maturity), r.maturity); assert.equal(c.rating.label, r.rating);
    rateEq(c.rate, r.rate, r.code); close(c.emissionRate, r.emissionRate, 1e-12, `${r.code} emissão`);
  });
});

test("curvas (Focus, Tesouro Direto) iguais ao Python", async () => {
  const { pd } = await loadInputs(), ref = FX.curves, asOf = E.fromIso(ref.asOf);
  for (const [h, v] of Object.entries(ref.cdi)) close(P.expectedCdi(pd, asOf, Number(h)).value, v, 1e-12, `CDI ${h}`);
  for (const [h, v] of Object.entries(ref.ipca)) close(P.expectedIpca(pd, asOf, Number(h)).value, v, 1e-12, `IPCA ${h}`);
  const [q, base] = P.ntnbQuotes(pd);
  assert.equal(iso(base), ref.ntnbBase);
  q.forEach((x, i) => { assert.equal(iso(x.maturity), ref.ntnb[i][0]); close(x.rate, ref.ntnb[i][1]); close(x.duration, ref.ntnb[i][2], 1e-10); });
});

for (const nome of ["usuario", "base_focus", "overrides_amplo"]) {
  test(`pipeline completo igual ao Python: ${nome}`, async () => {
    const { rf, pd } = await loadInputs(), ref = FX.pipeline[nome];
    const m = await mapaOf("mapa_posicoes_layout_real.pdf");
    const sc = nome === "base_focus" ? P.baseScenario(pd, m.positionDate, 1) : P.userScenario(0.14, 0.045);
    close(sc.cdi, ref.scenario.cdi, 1e-12); close(sc.ipca, ref.scenario.ipca, 1e-12);
    const ovs = Object.fromEntries(Object.entries(ref.overrides).map(([k, v]) => [k, v]));
    const en = A.enrich(m, sc, rf.candidates, ovs);
    assert.equal(en.length, ref.enriched.length);
    en.forEach((e, i) => {
      const r = ref.enriched[i], t = `${nome} ${r.code}`;
      for (const k of ["code", "inScope", "scopeNote", "indexer", "alerts", "review", "issuerKey"]) assert.deepEqual(e[k], r[k], `${t} ${k}`);
      assert.equal(e.rating.label, r.rating, `${t} rating`); assert.equal(e.taxExempt.value, r.taxExempt); assert.equal(e.taxExempt.source, r.taxExemptSource);
      if (r.marketRate) { close(e.marketRate.value, r.marketRate.value, 1e-8, `${t} taxa`); assert.equal(e.marketRate.source, r.marketRate.source); assert.equal(e.marketRate.kind, r.marketRate.kind); }
      else assert.equal(e.marketRate, null, t);
      if (r.duration) { close(e.duration.value, r.duration.value, 1e-8, `${t} duration`); assert.equal(e.duration.source, r.duration.source); }
      close(e.dmod, r.dmod, 1e-8, `${t} dmod`); close(e.deskSpread, r.deskSpread, 1e-8, `${t} spread mesa`); close(e.mtmVsCurve, r.mtmVsCurve, 1e-9, `${t} mtm`);
    });
    const [q] = P.ntnbQuotes(pd);
    const p = A.swapParams({ sameIndexer: ref.params.sameIndexer, issuerLimit: ref.params.issuerLimit, sectorLimit: ref.params.sectorLimit, liquidityClass: ref.params.liquidityClass });
    const rep = A.runSwaps(en, rf.candidates, sc, m.positionDate, p, q), rr = ref.report;
    rep.results.forEach((r, i) => {
      const x = rr.results[i], t = `${nome} ${x.code}`;
      assert.equal(r.holding.code, x.code); assert.equal(r.status, x.status, `${t} status`); assert.equal(r.evaluated, x.evaluated);
      assert.deepEqual(r.rejectedBy, x.rejectedBy, `${t} reprovações`);
      assert.deepEqual(r.best.map((b) => b.candidate.code), x.best.map((b) => b.code), `${t} candidatos`);
      r.best.forEach((b, k) => {
        const y = x.best[k];
        assert.equal(b.classA, y.classA, `${t} A`); assert.equal(b.classB, y.classB, `${t} B`);
        for (const f of ["deltaRate", "deltaSpread", "deltaMetric", "deltaNominal", "gainAnnual", "exitCostB", "taxAnticipated", "paybackA", "paybackB", "netGainB"]) close(b[f], y[f], 1e-7, `${t} ${f}`);
        assert.deepEqual(b.alerts, y.alerts, `${t} alertas`);
        assert.equal(A.justification(b, "interno"), y.justification, `${t} justificativa`);
      });
    });
    assert.deepEqual(rep.applied.map((p) => p.candidate.code), rr.applied);
    close(rep.totalGainAnnual, rr.totalGainAnnual, 1e-7); assert.deepEqual(rep.alerts, rr.alerts);
    for (const k of ["total", "avgNominalRate", "avgDuration"]) { close(rep.before[k], rr.before[k], 1e-9, k); close(rep.after[k], rr.after[k], 1e-9, k); }
    assert.deepEqual(A.summaryTable(rep), rr.summary);
    // modo cliente: mesmas colunas e textos que o Python (sem colunas internas nem Runflow)
    const jsCli = A.swapsTable(rep, "cliente", rf.internalLabels);
    assert.deepEqual(jsCli.map((r) => Object.keys(r)), ref.reportCliente.map((r) => Object.keys(r)));
    jsCli.forEach((r, i) => assert.equal(r["Justificativa"], ref.reportCliente[i]["Justificativa"]));
    const blob = JSON.stringify(jsCli).toLowerCase() + JSON.stringify(A.positionsTable(en, "cliente")).toLowerCase();
    for (const w of ["runflow", "lastro", "spread estimado da mesa", ...Object.values(rf.internalLabels).map((s) => s.toLowerCase())]) assert.ok(!blob.includes(w), `modo cliente contém '${w}'`);
  });
}

test("export Excel: abre de volta com o próprio leitor", async () => {
  const bytes = X.writeXlsx([{ name: "Trocas", rows: [["Código", "Ganho"], ["XALF12", 1234.5], ["Ação & <teste>", null]] }]);
  const back = await X.readXlsx(bytes);
  assert.equal(back[0].name, "Trocas");
  assert.deepEqual(back[0].rows[1], ["XALF12", 1234.5]);
  assert.equal(back[0].rows[2][0], "Ação & <teste>");
});

test("config TOML: exemplo e formato curto", () => {
  const ex = P.parseInternalColumns(fs.readFileSync(path.join(ROOT, "config", "runflow_columns.example.toml"), "utf8"));
  assert.deepEqual(ex.fields, ["fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b"]);
  assert.equal(ex.headers.fee, "Receita Estimada");
  const curto = P.parseInternalColumns('[outra]\nx = "y"\n[colunas_internas]\n# comentário\ncomp_a = "Coluna \\"A\\""\n');
  assert.deepEqual(curto.headers, { comp_a: 'Coluna "A"' });
});
