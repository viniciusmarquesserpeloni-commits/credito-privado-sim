"""Casos-ouro da metodologia (docs/metodologia.md, seções 4 e 10.3).

Todos os números vêm do documento; tolerâncias refletem o arredondamento com que lá aparecem.
"""

from __future__ import annotations

import pytest

from cpsim import pricing, rates, spreads, taxes


# ------------------------------------------------------------------ 4.5 prefixado 3 anos
@pytest.fixture
def pre3():
    """Prefixado de 3 anos, cupom anual de 12%, taxa de 13% a.a., face 100."""
    return pricing.annual_flows(0.12, 3), 0.13


def test_45_pu_duration_convexidade_dv01(pre3):
    flows, y = pre3
    assert pricing.price(flows, y) == pytest.approx(97.64, abs=0.005)
    assert pricing.macaulay_duration(flows, y) == pytest.approx(2.69, abs=0.005)
    assert pricing.modified_duration(flows, y) == pytest.approx(2.38, abs=0.005)
    assert pricing.convexity(flows, y) == pytest.approx(8.09, abs=0.005)
    assert pricing.dv01(flows, y) == pytest.approx(0.0232, abs=0.00005)


@pytest.mark.parametrize(
    "dy, exata, so_dur, dur_conv",
    [(0.01, -0.0234, -0.0238, -0.0234), (-0.01, 0.0242, 0.0238, 0.0242),
     (0.03, -0.0678, -0.0713, -0.0677)],
)
def test_45_tabela_de_choques(pre3, dy, exata, so_dur, dur_conv):
    flows, y = pre3
    pu0 = pricing.price(flows, y)
    dmod, conv = pricing.modified_duration(flows, y), pricing.convexity(flows, y)
    assert pricing.price(flows, y + dy) / pu0 - 1 == pytest.approx(exata, abs=0.00005)
    assert -dmod * dy == pytest.approx(so_dur, abs=0.00005)
    assert pricing.price_change_approx(dmod, conv, dy) == pytest.approx(dur_conv, abs=0.00005)


def test_45_taxa_a_partir_do_pu(pre3):
    flows, y = pre3
    assert pricing.yield_from_price(flows, pricing.price(flows, y)) == pytest.approx(y, abs=1e-10)


# ------------------------------------------------------------------ 4.3 spread sobre NTN-B
def test_43_spread_ntnb_56_bps():
    s = spreads.spread_over_ntnb(0.078, 0.072)
    assert s == pytest.approx(0.0056, abs=0.00005)
    assert round(s * 10_000) == 56


# ------------------------------------------------------------------ 4.7 retorno CDI+ 12 meses
def test_47_retorno_cdi_mais_cenarios():
    # O documento arredonda para 2 casas (14,695% -> 14,70%): tolerância de meio ponto-base.
    tol = 0.00006
    carry = rates.cdi_plus_to_annual(0.015, 0.13)
    assert carry == pytest.approx(0.1470, abs=tol)
    otimista = pricing.expected_return_approx(carry, spread_duration=3.0, ds=-0.0030)
    base = pricing.expected_return_approx(carry, spread_duration=3.0)
    pessimista = pricing.expected_return_approx(carry, spread_duration=3.0, ds=0.0080)
    assert otimista == pytest.approx(0.1560, abs=tol)
    assert base == pytest.approx(0.1470, abs=tol)
    assert pessimista == pytest.approx(0.1230, abs=tol)


# ------------------------------------------------------------------ 4.8, 4.9, 4.11
def test_48_breakeven_de_spread():
    assert spreads.breakeven_spread_widening(0.0056, 1.0, 4.8) * 10_000 == pytest.approx(11.7,
                                                                                         abs=0.05)


def test_49_pd_implicita():
    assert spreads.implied_default_intensity(0.015, 0.60) == pytest.approx(0.025)


def test_411_custo_de_saida():
    assert spreads.exit_cost(0.0020, 4.0) == pytest.approx(0.0040)


# ------------------------------------------------------------------ 4.12 gross-up
def test_412_gross_up_ipca_isento():
    nominal = rates.ipca_plus_to_nominal(0.078, 0.04)
    assert nominal == pytest.approx(0.1211, abs=0.00005)
    assert taxes.gross_up_nominal(nominal, 0.15) == pytest.approx(0.1425, abs=0.00005)
    assert taxes.gross_up_ipca_spread(0.078, 0.04, 0.15) == pytest.approx(0.0986, abs=0.00005)


# ------------------------------------------------------------------ 10.3 exemplo de troca
def test_103_exemplo_de_troca():
    ganho_taxa = 0.0730 - 0.0650  # 0,80 p.p. a.a. (mesmo indexador IPCA)
    custo_tx = 2 * spreads.exit_cost(2 * 0.0010, 4.0)  # meio-spread 10 bps × D 4, cada lado
    assert custo_tx == pytest.approx(0.0080)
    r = rates.ipca_plus_to_nominal(0.065, 0.04)
    imposto = taxes.anticipated_tax(0.15, 15.0, r, 4.0)  # R$ por R$ 100 investidos
    assert imposto == pytest.approx(0.75, abs=0.005)
    imposto_pct = imposto / 115.0
    assert imposto_pct == pytest.approx(0.0066, abs=0.00005)
    custo_total = custo_tx + imposto_pct
    assert custo_total == pytest.approx(0.0146, abs=0.00005)
    assert spreads.payback_years(custo_total, ganho_taxa) == pytest.approx(1.8, abs=0.05)
    # Se fosse isento: custo 0,80% e equilíbrio ≈ 1 ano
    assert taxes.anticipated_tax(0.0, 15.0, r, 4.0) == 0.0
    assert spreads.payback_years(custo_tx, ganho_taxa) == pytest.approx(1.0)
