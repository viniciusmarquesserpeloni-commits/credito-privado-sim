"""Gera offline/tests/fixtures.json: resultados do núcleo PYTHON (a referência) para conferir o
motor JavaScript do HTML offline. Rodar sempre que mudar fórmula, amostra ou dado público:

    python scripts/make_js_fixtures.py
    cd offline && npm test
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cpsim import calendar as cal  # noqa: E402
from cpsim import pricing, rates, report, spreads, taxes  # noqa: E402
from cpsim.cashflows import build_schedule  # noqa: E402
from cpsim.config import EXAMPLE, load_internal_columns  # noqa: E402
from cpsim.curves import expected_cdi, expected_ipca, load_public, ntnb_quotes  # noqa: E402
from cpsim.enrich import Override, enrich  # noqa: E402
from cpsim.parsers.mapa_pdf import parse_mapa  # noqa: E402
from cpsim.parsers.runflow_xlsx import read_runflow  # noqa: E402
from cpsim.scenarios import base_scenario, user_scenario  # noqa: E402
from cpsim.swap_engine import SwapParams, run_swaps  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
OUT = ROOT / "offline" / "tests" / "fixtures.json"


def iso(d):
    return d.isoformat() if d else None


def rate(r):
    return None if r is None else {"indexer": r.indexer.value, "value": r.value}


def lot_json(lot):
    return {"page": lot.page, "code": lot.code, "assetType": lot.asset_type, "title": lot.title,
            "issuer": lot.issuer, "emission": iso(lot.emission), "maturity": iso(lot.maturity),
            "purchaseDate": iso(lot.purchase_date), "rate": rate(lot.rate),
            "titleRate": rate(lot.title_rate), "quantity": lot.quantity, "puPurchase": lot.pu_purchase,
            "puCurve": lot.pu_curve, "grossCurve": lot.gross_curve, "puMarket": lot.pu_market,
            "grossMarket": lot.gross_market, "ir": lot.ir, "iof": lot.iof, "netValue": lot.net_value,
            "income": lot.income, "errors": lot.errors, "warnings": lot.warnings}


def cand_json(c):
    return {"code": c.code, "issuer": c.issuer, "product": c.product, "rate": rate(c.rate),
            "active": c.active, "lastro": c.lastro, "qtyAvailable": c.qty_available,
            "maturity": iso(c.maturity), "duration": c.duration, "ntnbRefYear": c.ntnb_ref_year,
            "emissionRate": c.emission_rate, "coupon": c.coupon, "amortization": c.amortization,
            "sector": c.sector, "rating": c.rating.label, "qualifiedOnly": c.qualified_only,
            "taxExempt": c.tax_exempt, "internal": c.internal, "warnings": c.warnings}


def enriched_json(e):
    return {"code": e.code, "inScope": e.in_scope, "scopeNote": e.scope_note,
            "indexer": e.indexer.value if e.indexer else None,
            "marketRate": None if e.market_rate is None else {
                "value": e.market_rate.value, "source": e.market_rate.source,
                "kind": e.market_rate.kind.value},
            "duration": None if e.duration is None else {"value": e.duration.value,
                                                         "source": e.duration.source},
            "dmod": e.dmod, "lotRates": e.lot_rates, "rating": e.rating.label,
            "taxExempt": e.tax_exempt.value, "taxExemptSource": e.tax_exempt.source,
            "alerts": e.alerts, "deskSpread": e.desk_spread, "review": e.review,
            "mtmVsCurve": e.mtm_vs_curve, "issuerKey": e.issuer_key}


def report_json(rep, mode, labels):
    res = []
    for r in rep.results:
        res.append({"code": r.holding.code, "status": r.status, "evaluated": r.evaluated,
                    "rejectedBy": dict(r.rejected_by),
                    "best": [{"code": p.candidate.code, "classA": p.class_a, "classB": p.class_b,
                              "deltaRate": p.delta_rate, "deltaSpread": p.delta_spread,
                              "deltaMetric": p.delta_metric, "deltaNominal": p.delta_nominal,
                              "gainAnnual": p.gain_annual, "exitCostB": p.exit_cost_b,
                              "taxAnticipated": p.tax_anticipated, "paybackA": p.payback_a,
                              "paybackB": p.payback_b, "netGainB": p.net_gain_b,
                              "alerts": p.alerts,
                              "justification": report.justification(p, mode)}
                             for p in r.best]})
    return {"results": res, "applied": [p.candidate.code for p in rep.applied],
            "totalGainAnnual": rep.total_gain_annual,
            "before": {"total": rep.before.total, "avgNominalRate": rep.before.avg_nominal_rate,
                       "avgDuration": rep.before.avg_duration},
            "after": {"total": rep.after.total, "avgNominalRate": rep.after.avg_nominal_rate,
                      "avgDuration": rep.after.avg_duration},
            "alerts": rep.alerts, "summary": report.summary_table(rep),
            "swapsTable": report.swaps_table(rep, mode, labels)}


def main() -> None:
    cfg = load_internal_columns(EXAMPLE)
    rf = read_runflow((SAMPLES / "runflow_exemplo.xlsx").read_bytes(), cfg)
    out: dict = {"generatedBy": "scripts/make_js_fixtures.py"}

    # calendário
    pares = [("2026-10-30", "2026-11-06"), ("2026-01-01", "2026-12-31"), ("2024-11-15", "2024-11-25"),
             ("2026-11-06", "2026-10-30"), ("2030-02-01", "2035-09-15")]
    out["businessDays"] = [[a, b, cal.business_days(dt.date.fromisoformat(a),
                                                     dt.date.fromisoformat(b))] for a, b in pares]
    out["holidays2026"] = sorted(d.isoformat() for d in cal.holidays(2026))

    # casos-ouro
    f = pricing.annual_flows(0.12, 3)
    out["golden"] = {
        "pu": pricing.price(f, 0.13), "dmac": pricing.macaulay_duration(f, 0.13),
        "dmod": pricing.modified_duration(f, 0.13), "conv": pricing.convexity(f, 0.13),
        "dv01": pricing.dv01(f, 0.13), "spread": spreads.spread_over_ntnb(0.078, 0.072),
        "grossup": taxes.gross_up_ipca_spread(0.078, 0.04, 0.15),
        "antecipado": taxes.anticipated_tax(0.15, 15.0, rates.ipca_plus_to_nominal(0.065, 0.04), 4.0),
        "pctcdi": rates.pct_cdi_to_annual(1.045, 0.14),
    }

    # fluxos
    casos = [("2026-10-30", "2035-09-15", "Mar/Set", "Mar/Set (Início 2034)", 0.071),
             ("2026-10-30", "2028-07-15", "Bullet", "Bullet", 0.12),
             ("2026-10-30", "2032-12-15", "Jun/Dez", "Semestral (Início Dez 30)", 0.074),
             ("2026-10-30", "2034-02-15", "Mensal", "Mensal", 0.068)]
    out["schedules"] = []
    for v, m, c, a, r in casos:
        s = build_schedule(dt.date.fromisoformat(v), dt.date.fromisoformat(m), c, a, r)
        out["schedules"].append({"args": [v, m, c, a, r], "warnings": s.warnings,
                                 "flows": [[iso(x.date), iso(x.pay_date), x.du, x.interest,
                                            x.amortization] for x in s.flows]})

    # leitores
    out["mapa"] = {}
    for nome in ("mapa_posicoes_exemplo.pdf", "mapa_posicoes_layout_real.pdf"):
        m = parse_mapa((SAMPLES / nome).read_bytes())
        out["mapa"][nome] = {"positionDate": iso(m.position_date), "nPages": m.n_pages,
                             "warnings": m.warnings, "lots": [lot_json(x) for x in m.lots]}
    out["runflow"] = {"missing": rf.missing, "extra": rf.extra,
                      "candidates": [cand_json(c) for c in rf.candidates]}

    # curvas (snapshot de data/public do repositório)
    pd = load_public()
    as_of = dt.date(2026, 10, 30)
    q, base = ntnb_quotes(pd)
    out["curves"] = {"asOf": iso(as_of),
                     "cdi": {str(h): expected_cdi(pd, as_of, h).value for h in (0.5, 1.0, 2.0, 3.0)},
                     "ipca": {str(h): expected_ipca(pd, as_of, h).value for h in (0.5, 1.0, 2.0, 3.0)},
                     "ntnb": [[iso(x.maturity), x.rate, x.duration] for x in q], "ntnbBase": iso(base)}

    # pipeline completo na amostra com estrutura do PDF real
    m = parse_mapa((SAMPLES / "mapa_posicoes_layout_real.pdf").read_bytes())
    runs = {
        "usuario": (user_scenario(0.14, 0.045), {}, SwapParams()),
        "base_focus": (base_scenario(pd, m.position_date, 1.0), {}, SwapParams()),
        "overrides_amplo": (user_scenario(0.14, 0.045),
                            {"XHOM36": Override(amortization="Anual (Início 2033)"),
                             "XALF12": Override(duration=3.9)},
                            SwapParams(same_indexer=False, issuer_limit=0.5, sector_limit=0.6,
                                       liquidity_class="baixa")),
    }
    out["pipeline"] = {}
    for nome, (sc, ovs, params) in runs.items():
        en = enrich(m, sc, rf.candidates, ovs)
        rep = run_swaps(en, rf.candidates, sc, m.position_date, params, q)
        out["pipeline"][nome] = {
            "scenario": {"cdi": sc.cdi, "ipca": sc.ipca, "name": sc.name},
            "overrides": {k: {"coupon": v.coupon, "amortization": v.amortization,
                              "duration": v.duration, "marketRate": v.market_rate}
                          for k, v in ovs.items()},
            "params": {"sameIndexer": params.same_indexer, "issuerLimit": params.issuer_limit,
                       "sectorLimit": params.sector_limit, "liquidityClass": params.liquidity_class},
            "enriched": [enriched_json(e) for e in en],
            "report": report_json(rep, "interno", rf.internal_labels),
            "reportCliente": report_json(rep, "cliente", rf.internal_labels)["swapsTable"],
            "positionsCliente": report.positions_table(en, "cliente"),
        }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n",
                   encoding="utf-8")
    print(f"gerado {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
