"""Núcleo: calendário, taxas, preço, impostos, spreads, fluxos e modelos."""

from __future__ import annotations

import datetime as dt

import pytest

from cpsim import calendar as cal
from cpsim import cashflows, pricing, rates, spreads, taxes
from cpsim.models import Indexer, Kind, Rate, parse_indexer, parse_rating
from cpsim.normalize import (fmt_bps, fmt_brl, fmt_pct, parse_number, parse_percent,
                             squash_number_gaps)

D = dt.date


# ============================================================== calendário
@pytest.mark.parametrize("year, easter", [(2024, D(2024, 3, 31)), (2025, D(2025, 4, 20)),
                                          (2026, D(2026, 4, 5)), (2027, D(2027, 3, 28))])
def test_pascoa(year, easter):
    assert cal.easter(year) == easter


def test_feriados_moveis_2026():
    h = cal.holidays(2026)
    assert {D(2026, 2, 16), D(2026, 2, 17), D(2026, 4, 3), D(2026, 6, 4)} <= h


def test_consciencia_negra_desde_2024():
    assert D(2024, 11, 20) in cal.holidays(2024)
    assert D(2023, 11, 20) not in cal.holidays(2023)


def test_dias_uteis_finados():
    # 30/10/2026 (sex) a 06/11/2026: 02/11 é feriado -> 30/10, 03, 04, 05
    assert cal.business_days(D(2026, 10, 30), D(2026, 11, 6)) == 4
    assert cal.business_days(D(2026, 11, 6), D(2026, 10, 30)) == -4
    assert cal.business_days_many(D(2026, 10, 30), [D(2026, 11, 3), D(2026, 11, 6)]) == [1, 4]
    assert cal.business_days_many(D(2026, 10, 30), []) == []


def test_dia_util_e_ajustes():
    assert not cal.is_business_day(D(2026, 11, 2))
    assert not cal.is_business_day(D(2026, 11, 7))  # sábado
    assert cal.following(D(2026, 11, 2)) == D(2026, 11, 3)
    assert cal.add_business_days(D(2026, 10, 30), 1) == D(2026, 11, 3)
    assert cal.year_fraction(D(2026, 10, 30), D(2026, 11, 6)) == pytest.approx(4 / 252)


def test_calendario_fora_do_intervalo():
    with pytest.raises(ValueError):
        cal.business_days(D(1980, 1, 1), D(2026, 1, 1))


# ============================================================== taxas
def test_conversoes_diarias():
    assert rates.daily_to_annual(rates.annual_to_daily(0.1415)) == pytest.approx(0.1415)
    # SGS 12 em 05/11/2026: 0,050788% a.d. ≈ 13,65% a.a.
    assert rates.cdi_sgs_to_annual(0.050788) == pytest.approx(0.1365, abs=0.0001)
    assert rates.compound(0.10, 252) == pytest.approx(1.10)


def test_pct_cdi_incide_na_taxa_diaria():
    assert rates.pct_cdi_to_annual(1.0, 0.14) == pytest.approx(0.14)
    r = rates.pct_cdi_to_annual(1.045, 0.14)
    assert 0.14 * 1.045 < r < 0.14 * 1.05  # composto diário: um pouco acima de 104,5% × CDI


def test_fisher_e_implicita():
    n = rates.ipca_plus_to_nominal(0.07, 0.045)
    assert rates.nominal_to_ipca_plus(n, 0.045) == pytest.approx(0.07)
    assert rates.implied_inflation(n, 0.07) == pytest.approx(0.045)


def test_nominal_esperado_e_diferenca():
    cdi, ipca = 0.14, 0.045
    assert rates.nominal_expected(Rate(Indexer.PRE, 0.13), cdi, ipca) == 0.13
    assert rates.nominal_expected(Rate(Indexer.IPCA, 0.07), cdi, ipca) == pytest.approx(
        1.07 * 1.045 - 1)
    assert rates.nominal_expected(Rate(Indexer.CDI_SPREAD, 0.01), cdi, ipca) == pytest.approx(
        1.14 * 1.01 - 1)
    assert rates.nominal_expected(Rate(Indexer.CDI_PCT, 1.0), cdi, ipca) == pytest.approx(cdi)
    a, b = Rate(Indexer.CDI_PCT, 1.05), Rate(Indexer.CDI_PCT, 1.00)
    assert rates.rate_difference(a, b, cdi=0.14) == pytest.approx(0.007)
    assert rates.rate_difference(Rate(Indexer.IPCA, 0.0738), Rate(Indexer.IPCA, 0.0712)) == \
        pytest.approx(0.0026)
    with pytest.raises(ValueError):
        rates.rate_difference(a, Rate(Indexer.PRE, 0.1))
    with pytest.raises(ValueError):
        rates.rate_difference(a, b)


# ============================================================== preço
def test_brent_casos_de_borda():
    assert pricing.brent(lambda x: x - 1.0, 1.0, 2.0) == 1.0
    assert pricing.brent(lambda x: x - 2.0, 1.0, 2.0) == 2.0
    with pytest.raises(ValueError):
        pricing.brent(lambda x: x * x + 1, -1.0, 1.0)
    assert pricing.brent(lambda x: x ** 3 - 2 * x - 5, 2.0, 3.0) == pytest.approx(2.0945514815)


def test_yield_sem_fluxo_e_fluxos_invalidos():
    with pytest.raises(ValueError):
        pricing.yield_from_price([], 100.0)
    with pytest.raises(ValueError):
        pricing.annual_flows(0.1, 0)


# ============================================================== impostos
@pytest.mark.parametrize("dias, ir", [(0, 0.225), (180, 0.225), (181, 0.20), (360, 0.20),
                                      (361, 0.175), (720, 0.175), (721, 0.15), (5000, 0.15)])
def test_tabela_ir(dias, ir):
    assert taxes.DEFAULT_POLICY.ir_rate(dias) == ir


def test_tabela_iof_e_politica():
    p = taxes.DEFAULT_POLICY
    assert p.iof_rate(0) == 1.0 and p.iof_rate(1) == 0.96 and p.iof_rate(29) == 0.03
    assert p.iof_rate(30) == 0.0
    assert p.status == taxes.CONFIRMAR_VIGENCIA
    with pytest.raises(ValueError):
        p.ir_rate(-1)


def test_isencao():
    pf = taxes.DEFAULT_POLICY
    assert pf.is_exempt("CRI", None) and pf.is_exempt("CRA", None)
    assert not pf.is_exempt("DEB", None)
    assert pf.is_exempt("DEB", True)  # incentivada: a coluna "Isento?" manda
    assert not pf.is_exempt("CRI", False)
    pj = taxes.TaxPolicy(investor="PJ")
    assert not pj.is_exempt("CRI", True)


def test_imposto_antecipado_sem_ganho():
    assert taxes.anticipated_tax(0.15, -10.0, 0.1, 3) == 0.0
    assert taxes.net_of_ir(0.12, 0.15) == pytest.approx(0.102)


# ============================================================== spreads
def test_ntnb_referencia():
    qs = [spreads.NtnbQuote(D(2032, 8, 15), 0.0789), spreads.NtnbQuote(D(2035, 5, 15), 0.0791),
          spreads.NtnbQuote(D(2045, 5, 15), 0.0759)]
    r = spreads.ntnb_reference(qs, ref_year=2035)
    assert r.value.maturity.year == 2035 and r.kind is Kind.APROXIMACAO
    r = spreads.ntnb_reference(qs, duration=6.0, as_of=D(2026, 10, 30))
    assert r.value.maturity.year == 2032  # vencimento mais próximo de 6 anos
    assert spreads.ntnb_reference(qs, duration=6.0) is None  # sem data de referência
    qd = [spreads.NtnbQuote(D(2032, 8, 15), 0.0789, 4.6), spreads.NtnbQuote(D(2035, 5, 15),
                                                                            0.0791, 6.1)]
    r = spreads.ntnb_reference({q.maturity: q for q in qd}, duration=5.9, kind=Kind.DADO,
                               source="ANBIMA")
    assert r.value.maturity.year == 2035 and r.kind is Kind.DADO
    assert spreads.ntnb_reference([], duration=5) is None
    assert spreads.dts(4.0, 0.01) == pytest.approx(0.04)
    assert spreads.payback_years(0.01, 0.0) is None


# ============================================================== fluxos
MAT = D(2035, 9, 15)
VAL = D(2026, 10, 30)


@pytest.mark.parametrize("texto, meses", [
    ("Mai/Nov", [5, 11]), ("Mensal", list(range(1, 13))), ("Jan/Abr/Jul/Out", [1, 4, 7, 10]),
    ("Bullet", []), ("Semestral", [3, 9]), ("Anual", [9]), ("Trimestral", [3, 6, 9, 12]),
    ("mar e set", [3, 9]), ("qualquer coisa", None),
])
def test_meses_de_cupom(texto, meses):
    assert cashflows.parse_months(texto, MAT) == meses


@pytest.mark.parametrize("texto, esperado", [
    ("Bullet", ([], None)),
    ("Anual (Início 2037)", ([9], D(2037, 1, 1))),
    ("Mar/Set (Início 2034)", ([3, 9], D(2034, 1, 1))),
    ("Semestral (Início Set 26)", ([3, 9], D(2026, 9, 1))),
    ("Semestral (Início Dez 30)", ([6, 12], D(2030, 12, 1))),
    ("Mensal", (list(range(1, 13)), None)),
    ("Anual (Início depois)", None),
    ("??", None),
])
def test_amortizacao(texto, esperado):
    assert cashflows.parse_amortization(texto, MAT) == esperado


def test_fluxo_semestral_com_amortizacao():
    s = cashflows.build_schedule(VAL, MAT, "Mar/Set", "Mar/Set (Início 2034)", 0.071)
    assert s.ok and s.approximate
    assert len(s.flows) == 18
    assert sum(f.amortization for f in s.flows) == pytest.approx(1.0)
    amort = [f for f in s.flows if f.amortization > 0]
    assert [f.date for f in amort] == [D(2034, 3, 15), D(2034, 9, 15), D(2035, 3, 15), MAT]
    assert all(f.amortization == pytest.approx(0.25) for f in amort)
    assert s.flows[0].pay_date == D(2027, 3, 15)
    # Descontado à própria taxa do cupom, o PU = 1 corrigido desde o último cupom (15/09/2026).
    du_acc = cal.business_days(D(2026, 9, 15), VAL)
    assert pricing.price(s.as_pricing_flows(), 0.071) == pytest.approx(1.071 ** (du_acc / 252))


def test_fluxo_bullet_e_dia_ajustado():
    s = cashflows.build_schedule(VAL, D(2028, 7, 15), "Bullet", "Bullet", 0.12)
    assert len(s.flows) == 1 and s.warnings  # aviso: juros contados desde a avaliação
    assert pricing.price(s.as_pricing_flows(), 0.12) == pytest.approx(1.0)
    m = cashflows.build_schedule(VAL, D(2027, 11, 15), "Mai/Nov", "Bullet", 0.10)
    assert m.flows[-1].pay_date == D(2027, 11, 16)  # 15/11 é feriado


def test_fluxo_nao_reconhecido_ou_vencido():
    s = cashflows.build_schedule(VAL, MAT, "Toda lua cheia", "Bullet", 0.07)
    assert not s.ok and "cupom" in s.warnings[0]
    s = cashflows.build_schedule(VAL, MAT, "Mar/Set", "Quando der", 0.07)
    assert not s.ok and "amortiza" in s.warnings[0]
    assert not cashflows.build_schedule(VAL, D(2026, 1, 1), "Bullet", "Bullet", 0.1).ok


def test_duration_do_fluxo_aproximado_coerente():
    s = cashflows.build_schedule(VAL, MAT, "Mar/Set", "Mar/Set (Início 2034)", 0.071)
    d = pricing.macaulay_duration(s.as_pricing_flows(), 0.0755)
    assert 5.5 < d < 7.0  # o Runflow fictício informa 6,02


# ============================================================== modelos e normalização
@pytest.mark.parametrize("raw, label", [
    ("AAA", "AAA"), ("brAAA", "AAA"), ("AAAbr", "AAA"), ("AAA(bra)", "AAA"), ("AA+.br", "AA+"),
    ("Aa1.br", "AA+"), ("brAA+", "AA+"), ("AA-", "AA-"), ("A+(exp)sf(bra)", "A+"),
    ("Baa3", "BBB-"), ("0", None), ("-", None), ("", None), (None, None), ("XYZ", None),
])
def test_rating(raw, label):
    r = parse_rating(raw)
    assert r.label == label
    assert r.has_rating is (label is not None)


def test_rating_ordinal():
    assert parse_rating("AAA").notch > parse_rating("AA+").notch > parse_rating("brAA").notch
    assert parse_rating("A").notch > parse_rating("BBB+").notch


@pytest.mark.parametrize("raw, idx", [("Pré", Indexer.PRE), ("PRE", Indexer.PRE),
                                      ("%CDI", Indexer.CDI_PCT), ("IPCA", Indexer.IPCA),
                                      ("+CDI", Indexer.CDI_SPREAD), ("CDI+", Indexer.CDI_SPREAD),
                                      ("IGP-M", None), (None, None)])
def test_indexador(raw, idx):
    assert parse_indexer(raw) is idx


def test_rate_str():
    assert str(Rate(Indexer.IPCA, 0.0705)) == "IPCA + 7,05%"
    assert str(Rate(Indexer.CDI_PCT, 0.995)) == "99,50% do CDI"
    assert str(Rate(Indexer.CDI_SPREAD, 0.0115)) == "CDI + 1,15%"
    assert str(Rate(Indexer.PRE, 0.1437)) == "14,37% a.a."


def test_normalizacao_e_formatos():
    assert squash_number_gaps("99 . 999,99") == "99.999,99"
    assert squash_number_gaps("9 .99%") == "9.99%"
    assert squash_number_gaps("R$ 1.021,25") == "R$ 1.021,25"
    assert parse_number("3,88") == 3.88 and parse_number(2) == 2.0
    assert parse_number("R$ 1.200.000,00") == 1_200_000.0
    assert parse_number("-") is None and parse_number(True) is None and parse_number("x") is None
    assert parse_percent("7,55%") == (7.55, True)
    assert parse_percent("1.234,5%") == (1234.5, True)
    assert parse_percent(0.0712) == (0.0712, False)
    assert parse_percent("abc") == (None, False) and parse_percent(None) == (None, False)
    assert fmt_pct(0.1437) == "14,37%" and fmt_pct(None) == "—"
    assert fmt_bps(0.0056) == "56 bps" and fmt_bps(None) == "—"
    assert fmt_brl(1021.25) == "R$ 1.021,25" and fmt_brl(-5) == "-R$ 5,00" and fmt_brl(None) == "—"
