"""Tabelas de saída e export Excel nos modos INTERNO e CLIENTE (regra 6).

Modo cliente: sem colunas internas do Runflow (receita da mesa, comparativos, diferenças), sem
lastro disponível e sem qualquer menção ao Runflow interno (o texto é trocado por "oferta
disponível"). Modo interno: inclui essas colunas, com os rótulos do config de colunas internas.
Nenhuma coluna interna entra em cálculo ou ordenação (regra 7): aqui elas só são exibidas.
"""

from __future__ import annotations

import io
import re
from typing import Any

from .enrich import EnrichedPosition
from .models import Mode
from .normalize import fmt_bps, fmt_brl, fmt_pct
from .swap_engine import PairResult, SwapReport

AVISO = ("Ferramenta analítica: não constitui recomendação de investimento. Os limiares de "
         "classificação são hipóteses ainda não validadas por backtest.")
_RUNFLOW = re.compile(r"run\s*-?\s*flow", re.I)
_RUNFLOW_PREP = re.compile(r"\b([dn])o\s+(run\s*-?\s*flow)", re.I)
_LASTRO = re.compile(r"\s*(e\s+)?lastro(\s+dispon[ií]vel)?", re.I)
LASTRO_COL = "Lastro disponível"


def sanitize(text: Any, mode: Mode) -> Any:
    """Modo cliente: troca menções ao Runflow interno por "oferta disponível" e remove "lastro"."""
    if mode == "cliente" and isinstance(text, str):
        t = _RUNFLOW_PREP.sub(lambda m: f"{m.group(1)}a oferta disponível", text)
        t = _RUNFLOW.sub("oferta disponível", t)
        return _LASTRO.sub("", t)
    return text


def _clean_row(row: dict[str, Any], mode: Mode) -> dict[str, Any]:
    return {sanitize(k, mode): sanitize(v, mode) for k, v in row.items()}


def _rate_txt(indexer, value) -> str:
    if value is None or indexer is None:
        return "—"
    from .models import Rate

    return str(Rate(indexer, value))


def positions_table(enriched: list[EnrichedPosition], mode: Mode) -> list[dict[str, Any]]:
    rows = []
    for e in enriched:
        p = e.position
        mr, du = e.market_rate, e.duration
        rows.append(_clean_row({
            "Código": e.code,
            "Tipo": p.asset_type,
            "Emissor": p.issuer,
            "Indexador": e.indexer.value if e.indexer else "—",
            "Vencimento": p.maturity,
            "Valor líquido": p.net_value,
            "Taxa de mercado": _rate_txt(e.indexer, mr.value if mr else None),
            "Fonte da taxa": mr.source if mr else "—",
            "Natureza da taxa": mr.kind.value if mr else "—",
            "Duration (anos)": round(du.value, 2) if du else None,
            "Fonte da duration": du.source if du else "—",
            "Rating": e.rating.label or "—",
            "Isento": "sim" if e.tax_exempt.value else "não",
            "Marcação vs curva": e.mtm_vs_curve,
            "Na análise": "sim" if e.in_scope else f"não ({e.scope_note})",
            "Alertas": "; ".join(e.alerts),
        }, mode))
    return rows


def justification(pr: PairResult, mode: Mode) -> str:
    parts = []
    for ch in pr.checks:
        name, detail = ch.name, ch.detail
        if mode == "cliente" and ch.name == "distribuição e lastro":
            name = "disponibilidade"
            detail = "disponível" if ch.passed else "indisponível para o valor da posição"
        parts.append(f"{'✓' if ch.passed else '✗'} {name}: {detail}")
    if pr.delta_metric is not None:
        parts.append(f"{pr.delta_metric_name}: {fmt_bps(pr.delta_metric, 1)}")
    if pr.payback_b is not None:
        parts.append(f"equilíbrio A {pr.payback_a:.2f} / B {pr.payback_b:.2f} anos")
    parts += pr.alerts
    return sanitize(" | ".join(parts), mode)


def swaps_table(report: SwapReport, mode: Mode,
                internal_labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
    labels = internal_labels or {}
    rows = []
    for r in report.results:
        h = r.holding
        base = {"Posição": h.code, "Emissor atual": h.position.issuer,
                "Valor de saída": h.net_value,
                "Taxa atual": _rate_txt(h.indexer, h.market_rate.value if h.market_rate else None),
                "Situação": r.status}
        if not r.best:
            rows.append(_clean_row({**base, "Rank": None, "Candidato": "—",
                                    "Classificação (B)": r.status}, mode))
            continue
        for k, pr in enumerate(r.best, start=1):
            c = pr.candidate
            row = {
                **base, "Rank": k, "Candidato": c.code, "Emissor candidato": c.issuer,
                "Taxa candidato": str(c.rate) if c.rate else "—",
                "Duration candidato": c.duration, "Rating candidato": c.rating.label or "—",
                "Δ usado": fmt_bps(pr.delta_metric, 1), "Medida do Δ": pr.delta_metric_name,
                "Ganho anual (R$)": pr.gain_annual, "Custo de saída B (R$)": pr.exit_cost_b,
                "Imposto antecipado (R$)": pr.tax_anticipated,
                "Equilíbrio A (anos)": pr.payback_a, "Equilíbrio B (anos)": pr.payback_b,
                "Classificação (A)": pr.class_a, "Classificação (B)": pr.class_b,
                "Justificativa": justification(pr, mode),
            }
            if mode == "interno":
                row[LASTRO_COL] = c.lastro
                for campo, valor in c.internal.items():
                    row[labels.get(campo, campo)] = valor
            rows.append(_clean_row(row, mode))
    return rows


def summary_table(report: SwapReport) -> list[dict[str, Any]]:
    b, a = report.before, report.after

    def top(d: dict[str, float]) -> str:
        return ", ".join(f"{k} {v:.0%}" for k, v in sorted(d.items(), key=lambda x: -x[1])[:3])

    return [
        {"Item": "Valor analisado", "Antes": fmt_brl(b.total), "Depois": fmt_brl(a.total)},
        {"Item": "Taxa nominal esperada média", "Antes": fmt_pct(b.avg_nominal_rate),
         "Depois": fmt_pct(a.avg_nominal_rate)},
        {"Item": "Duration média (anos)",
         "Antes": f"{b.avg_duration:.2f}" if b.avg_duration is not None else "—",
         "Depois": f"{a.avg_duration:.2f}" if a.avg_duration is not None else "—"},
        {"Item": "Maiores emissores", "Antes": top(b.by_issuer), "Depois": top(a.by_issuer)},
        {"Item": "Maiores setores", "Antes": top(b.by_sector), "Depois": top(a.by_sector)},
        {"Item": "Trocas recomendadas aplicadas", "Antes": "", "Depois": str(len(report.applied))},
        {"Item": "Ganho anual estimado", "Antes": "", "Depois": fmt_brl(report.total_gain_annual)},
    ]


def assumptions_table(report: SwapReport) -> list[dict[str, Any]]:
    s, p = report.scenario, report.params
    return [
        {"Premissa": "Aviso", "Valor": AVISO},
        {"Premissa": "Data da posição", "Valor": report.as_of.strftime("%d/%m/%Y")},
        {"Premissa": "Cenário", "Valor": f"{s.name}: CDI {fmt_pct(s.cdi)}, IPCA {fmt_pct(s.ipca)} "
                                          f"(horizonte {s.horizon_years:g} ano)"},
        {"Premissa": "Fontes do cenário", "Valor": f"{s.cdi_source}; {s.ipca_source}"},
        {"Premissa": "Classificação", "Valor": "pelo cenário B (PU Mercado = marcação)"},
        {"Premissa": "Limiares (hipóteses)",
         "Valor": f"recomendada Δ ≥ {fmt_bps(p.rec_min_delta)} e equilíbrio ≤ "
                  f"{p.rec_max_payback:g} ano; marginal Δ ≥ {fmt_bps(p.marg_min_delta)} e "
                  f"equilíbrio ≤ {p.marg_max_payback:g} anos"},
        {"Premissa": "Custo de saída (b por classe, hipótese)",
         "Valor": ", ".join(f"{k} {fmt_bps(v)}" for k, v in p.bid_ask_by_class.items())},
        {"Premissa": "Tributação", "Valor": f"investidor {p.policy.investor}; tabelas: "
                                             f"{p.policy.status}"},
    ]


def to_excel(report: SwapReport, enriched: list[EnrichedPosition], mode: Mode,
             internal_labels: dict[str, str] | None = None) -> bytes:
    """Excel em memória (nada é gravado em disco)."""
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(positions_table(enriched, mode)).to_excel(xw, sheet_name="Carteira", index=False)
        pd.DataFrame(swaps_table(report, mode, internal_labels)).to_excel(xw, sheet_name="Trocas",
                                                                           index=False)
        pd.DataFrame(summary_table(report)).to_excel(xw, sheet_name="Resumo", index=False)
        pd.DataFrame(assumptions_table(report)).to_excel(xw, sheet_name="Premissas", index=False)
    return buf.getvalue()
