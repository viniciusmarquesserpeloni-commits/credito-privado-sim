"""Spread de crédito, NTN-B de referência, risco de spread e custos de troca.

Referências: metodologia 3.1 (NTN-B de referência), 4.3 (spread sobre NTN-B), 4.6 (DTS),
4.8 (breakeven), 4.9 (PD implícita), 4.11 (custo de saída), 10.3 (prazo de equilíbrio).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass

from .models import Kind, Sourced
from .rates import spread_over


def spread_over_ntnb(r_ipca_plus: float, r_ntnb: float) -> float:
    """s = (1 + r_deb)/(1 + r_NTNB) − 1 (metodologia 4.3)."""
    return spread_over(r_ipca_plus, r_ntnb)


@dataclass(frozen=True)
class NtnbQuote:
    maturity: dt.date
    rate: float  # IPCA + rate (decimal)
    duration: float | None = None  # anos (se a fonte informar)


def ntnb_reference(
    quotes: Mapping[dt.date, NtnbQuote] | list[NtnbQuote],
    *,
    ref_year: int | None = None,
    duration: float | None = None,
    as_of: dt.date | None = None,
    source: str = "Tesouro Direto",
    kind: Kind = Kind.APROXIMACAO,
) -> Sourced | None:
    """Escolhe a NTN-B de referência.

    1. Se o Runflow indicar o ano ("B35"), usa a NTN-B que vence nesse ano.
    2. Senão, a de menor |duration − D| (regra ANBIMA, metodologia 3.1); sem duration da NTN-B,
       aproxima pela de vencimento mais próximo do prazo D (marcado como aproximação).
    Fonte Tesouro Direto = "taxa de varejo" (prompt 6.3); ANBIMA títulos públicos é dado."""
    qs = list(quotes.values()) if isinstance(quotes, Mapping) else list(quotes)
    if not qs:
        return None
    if ref_year is not None:
        same = [q for q in qs if q.maturity.year == ref_year]
        if same:
            return Sourced(same[0], source, kind, f"B{ref_year % 100:02d} indicada no Runflow")
    if duration is None:
        return None
    with_d = [q for q in qs if q.duration is not None]
    if with_d:
        best = min(with_d, key=lambda q: abs(q.duration - duration))
        return Sourced(best, source, kind, "menor diferença de duration (regra ANBIMA)")
    if as_of is None:
        return None
    best = min(qs, key=lambda q: abs((q.maturity - as_of).days / 365.25 - duration))
    return Sourced(best, source, Kind.APROXIMACAO,
                   "vencimento mais próximo da duration (sem duration da NTN-B)")


def dts(spread_duration: float, s: float) -> float:
    """DTS = D_s × s (metodologia 4.6)."""
    return spread_duration * s


def breakeven_spread_widening(s: float, h_years: float, spread_duration: float) -> float:
    """Δs* ≈ s × h / D_s (metodologia 4.8). Ex.: 56 bps, h = 1, D_s = 4,8 -> 11,7 bps."""
    return s * h_years / spread_duration


def implied_default_intensity(s: float, lgd: float) -> float:
    """λ ≈ s / LGD (metodologia 4.9). Superestima a PD real: uso só comparativo."""
    return s / lgd


def exit_cost(bid_ask: float, dmod: float) -> float:
    """Custo de saída ≈ (b/2) × D_mod, em fração do PU (metodologia 4.11; prompt 6.3 cenário B).
    b = taxa de venda − taxa de compra. Ex.: b = 20 bps, D = 4 -> 0,40%."""
    return bid_ask / 2.0 * dmod


# Classes de liquidez (prompt 6.3): b total (compra − venda) HIPOTÉTICO por classe.
DEFAULT_BID_ASK_BY_LIQUIDITY = {"alta": 0.0010, "media": 0.0025, "baixa": 0.0050}


def payback_years(total_cost_fraction: float, annual_gain_fraction: float) -> float | None:
    """Prazo de equilíbrio = custo total / ganho anual (prompt 6.3; metodologia 10.3).
    Ex. 10.3: 1,46% / 0,80% a.a. ≈ 1,8 ano. Sem ganho -> None."""
    if annual_gain_fraction <= 0:
        return None
    return total_cost_fraction / annual_gain_fraction
