"""Cenários de CDI e IPCA no horizonte (prompt 6.4; metodologia 9.2, item 4).

MVP: cenário BASE ("mercado precificado"/Focus, não previsão) e cenário DO USUÁRIO. Cenários
históricos (percentis, estresse) ficam para depois do MVP (Fase 4).
Toda comparação entre indexadores depende do cenário escolhido — a tela deve dizer isso.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .curves import PublicData, expected_cdi, expected_ipca


@dataclass(frozen=True)
class Scenario:
    name: str
    horizon_years: float
    cdi: float  # média anual esperada no horizonte (decimal)
    ipca: float
    cdi_source: str
    ipca_source: str
    note: str = ""


def base_scenario(pd: PublicData, as_of: dt.date, horizon_years: float = 1.0) -> Scenario:
    c = expected_cdi(pd, as_of, horizon_years)
    i = expected_ipca(pd, as_of, horizon_years)
    return Scenario("Base (Focus)", horizon_years, c.value, i.value, c.source, i.source,
                    "Expectativa de mercado (Focus), não previsão; " + c.note)


def user_scenario(cdi: float, ipca: float, horizon_years: float = 1.0) -> Scenario:
    return Scenario("Do usuário", horizon_years, cdi, ipca, "informado pelo usuário",
                    "informado pelo usuário")
