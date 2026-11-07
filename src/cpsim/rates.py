"""Conversões de taxas (base 252, capitalização composta).

Todas as taxas em decimal ao ano (0.1437 = 14,37% a.a.), salvo indicação.
Referências: metodologia 4.1 (base 252), 4.3 (spread multiplicativo), 4.7 (CDI + spread),
4.10 (inflação implícita), 4.12 (equalização tributária, em `taxes.gross_up_*`).
"""

from __future__ import annotations

from .models import Indexer, Rate

DU_ANO = 252


def annual_to_daily(r: float) -> float:
    return (1.0 + r) ** (1.0 / DU_ANO) - 1.0


def daily_to_annual(d: float) -> float:
    return (1.0 + d) ** DU_ANO - 1.0


def cdi_sgs_to_annual(pct_ao_dia: float) -> float:
    """Série SGS 12 vem em % ao dia (ex.: 0.050788) -> taxa anual decimal."""
    return daily_to_annual(pct_ao_dia / 100.0)


def compound(r: float, du: int) -> float:
    """Fator de capitalização em `du` dias úteis."""
    return (1.0 + r) ** (du / DU_ANO)


def pct_cdi_to_annual(p: float, cdi: float) -> float:
    """%CDI -> taxa anual equivalente: o percentual incide sobre a taxa DIÁRIA do CDI.
    Ex.: 104,5% de um CDI de 14,15% a.a."""
    return daily_to_annual(p * annual_to_daily(cdi))


def cdi_plus_to_annual(spread: float, cdi: float) -> float:
    """CDI + s (forma multiplicativa, metodologia 4.7: 1,13 × 1,015 − 1)."""
    return (1.0 + cdi) * (1.0 + spread) - 1.0


def ipca_plus_to_nominal(real: float, ipca: float) -> float:
    """IPCA + r -> nominal (Fisher): (1 + r)(1 + π) − 1."""
    return (1.0 + real) * (1.0 + ipca) - 1.0


def nominal_to_ipca_plus(nominal: float, ipca: float) -> float:
    return (1.0 + nominal) / (1.0 + ipca) - 1.0


def implied_inflation(nominal: float, real: float) -> float:
    """Inflação implícita (metodologia 4.10): (1 + nominal)/(1 + real) − 1."""
    return (1.0 + nominal) / (1.0 + real) - 1.0


def spread_over(r: float, base: float) -> float:
    """Spread multiplicativo (metodologia 4.3, padrão ANBIMA): (1 + r)/(1 + base) − 1.
    Ex.: IPCA + 7,80% sobre NTN-B a IPCA + 7,20% -> 0,56% (56 bps)."""
    return (1.0 + r) / (1.0 + base) - 1.0


def nominal_expected(rate: Rate, cdi: float, ipca: float) -> float:
    """Taxa nominal anual esperada de uma taxa em qualquer indexador, dado um cenário de CDI e
    IPCA médios no horizonte (metodologia 6, "três mundos de indexador"; prompt 6.4).
    O resultado DEPENDE do cenário: quem exibe deve dizer isso."""
    if rate.indexer is Indexer.PRE:
        return rate.value
    if rate.indexer is Indexer.IPCA:
        return ipca_plus_to_nominal(rate.value, ipca)
    if rate.indexer is Indexer.CDI_PCT:
        return pct_cdi_to_annual(rate.value, cdi)
    if rate.indexer is Indexer.CDI_SPREAD:
        return cdi_plus_to_annual(rate.value, cdi)
    raise ValueError(rate.indexer)


def rate_difference(a: Rate, b: Rate, cdi: float | None = None) -> float:
    """Diferença a − b no MESMO indexador, em taxa anual (prompt 6.3):
    IPCA: diferença de spread real; Pré: nominal; CDI+: de spread;
    %CDI: (p_a − p_b) × CDI esperado (exige `cdi`)."""
    if a.indexer is not b.indexer:
        raise ValueError("indexadores diferentes: use nominal_expected() no modo amplo")
    if a.indexer is Indexer.CDI_PCT:
        if cdi is None:
            raise ValueError("%CDI exige o CDI esperado no horizonte")
        return (a.value - b.value) * cdi
    return a.value - b.value
