"""Fase 2: taxa de mercado/duration, curvas, cenários, motor de troca e relatório."""

from __future__ import annotations

import copy
import datetime as dt
import io
import json
import sys
from pathlib import Path

import pytest

from cpsim import report
from cpsim.cashflows import build_schedule
from cpsim.config import EXAMPLE, load_internal_columns
from cpsim.curves import (PublicData, copom_date, current_cdi, expected_cdi, expected_ipca,
                          load_public, ntnb_quotes)
from cpsim.enrich import (SRC_DURATION_CALC, SRC_IMPLIED_DEFAULT, SRC_IMPLIED_RUNFLOW,
                          SRC_IMPLIED_USER, SRC_OVERRIDE, SRC_RUNFLOW_DURATION, SRC_RUNFLOW_RATE,
                          EnrichedPosition, Override, enrich, enrich_position, implied_rate,
                          issuer_key)
from cpsim.models import (Candidate, Indexer, Kind, Lot, MapaPositions, Position, Rate, Sourced,
                          parse_rating)
from cpsim.parsers.mapa_pdf import parse_mapa
from cpsim.parsers.runflow_xlsx import read_runflow
from cpsim.pricing import brent, price
from cpsim.scenarios import base_scenario, user_scenario
from cpsim.spreads import NtnbQuote
from cpsim.swap_engine import (FORA, MANTER, MARGINAL, RECOMENDADA, SEM_TAXA, SwapParams,
                               anticipated_tax_position, classify, run_swaps)
from cpsim.taxes import TaxPolicy

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
sys.path.insert(0, str(ROOT / "scripts"))
from make_samples import SAMPLE_CDI, SAMPLE_IPCA, TAXA_MERCADO  # noqa: E402

D = dt.date
VAL = D(2026, 10, 30)
SC = user_scenario(SAMPLE_CDI, SAMPLE_IPCA)


# ============================================================ teste-ouro: premissa de amortização
def _erro_premissa_bullet(anos_amort: int, taxa_op: float, taxa_mercado: float,
                          venc: dt.date = D(2036, 9, 15), cupom: float = 0.07) -> float:
    """Papel real amortiza nos últimos `anos_amort` anos; a estimativa supõe pagamento no
    vencimento. Devolve o erro da taxa estimada em bps."""
    real = build_schedule(VAL, venc, "Mar/Set", f"Mar/Set (Início {venc.year - anos_amort + 1})",
                          cupom).as_pricing_flows()
    razao = price(real, taxa_mercado) / price(real, taxa_op)  # = PU Mercado / PU Curva
    res = implied_rate(razao, 1.0, Rate(Indexer.IPCA, taxa_op), cupom, VAL, venc, "Mar/Set",
                       "Bullet", SC)
    return (res[0] - taxa_mercado) * 1e4


@pytest.mark.parametrize("taxa_op, taxa_mercado", [(0.070, 0.078), (0.075, 0.0675),
                                                   (0.065, 0.073), (0.072, 0.072)])
def test_ouro_amortizacao_ultimos_3_anos_erro_menor_que_10bps(taxa_op, taxa_mercado):
    """Teste-ouro definido pelo usuário (papel de ~10 anos, |Δy| ≤ 80 bps)."""
    assert abs(_erro_premissa_bullet(3, taxa_op, taxa_mercado)) < 10


@pytest.mark.parametrize("taxa_op, taxa_mercado", [(0.070, 0.078), (0.075, 0.0675),
                                                   (0.065, 0.073), (0.072, 0.072)])
def test_ouro_amortizacao_ultimos_8_anos_erro_menor_que_30bps(taxa_op, taxa_mercado):
    assert abs(_erro_premissa_bullet(8, taxa_op, taxa_mercado)) < 30


def test_limite_documentado_da_premissa():
    """Fora desse domínio o erro passa dos limites (ver docs/FASE2_RELATORIO.md): papel curto
    e taxa longe da de operação. Este teste registra o limite para ninguém confiar às cegas."""
    assert abs(_erro_premissa_bullet(3, 0.09, 0.12, venc=D(2031, 9, 15), cupom=0.05)) > 30
    assert abs(_erro_premissa_bullet(8, 0.070, 0.080)) > 30  # Δy de 100 bps já estoura


def test_sem_amortizacao_antecipada_erro_zero():
    assert abs(_erro_premissa_bullet(0, 0.07, 0.08)) < 0.01


# ============================================================ enriquecimento nas amostras
@pytest.fixture(scope="module")
def runflow():
    return read_runflow((SAMPLES / "runflow_exemplo.xlsx").read_bytes(),
                        load_internal_columns(EXAMPLE))


@pytest.fixture(scope="module", params=["mapa_posicoes_exemplo.pdf",
                                        "mapa_posicoes_layout_real.pdf"])
def mapa(request):
    return parse_mapa((SAMPLES / request.param).read_bytes())


@pytest.fixture(scope="module")
def enriched(mapa, runflow):
    return {e.code: e for e in enrich(mapa, SC, runflow.candidates)}


def test_taxa_de_mercado_recuperada_nas_amostras(enriched):
    for code, alvo in TAXA_MERCADO.items():
        e = enriched[code]
        assert e.in_scope and e.market_rate.kind is Kind.ESTIMATIVA
        assert e.market_rate.note == "taxa estimada"
        assert e.market_rate.value == pytest.approx(alvo, abs=0.00005), code  # < 0,5 bp


def test_fontes_runflow_e_padrao(enriched, runflow):
    alf = enriched["XALF12"]
    assert alf.market_rate.source == SRC_IMPLIED_RUNFLOW
    assert alf.duration.source == SRC_RUNFLOW_DURATION
    assert alf.duration.value == runflow.by_code()["XALF12"].duration
    assert "(Runflow)" in alf.flow
    assert len(alf.lot_rates) == len(alf.position.lots)  # uma estimativa por lote
    hom = enriched["XHOM36"]  # fora do Runflow
    assert hom.candidate is None and hom.market_rate.source == SRC_IMPLIED_DEFAULT
    assert hom.duration.source == SRC_DURATION_CALC and hom.duration.kind is Kind.ESTIMATIVA
    assert 6.0 < hom.duration.value < 8.0
    assert any("fluxo padrão" in a for a in hom.alerts)
    assert any("sem rating" in a for a in hom.alerts)
    assert hom.dmod == pytest.approx(hom.duration.value / (1 + hom.market_rate.value))


def test_escopo_e_isencao(enriched):
    assert not enriched["CDBX0001"].in_scope and "PU Mercado" in enriched["CDBX0001"].scope_note
    assert not enriched["CPRX0001"].in_scope
    assert enriched["CDBX0001"].market_rate is None
    assert enriched["XALF12"].tax_exempt.value is True  # coluna Isento? do Runflow
    assert enriched["XGAM13"].tax_exempt.value is False
    assert enriched["XHOM36"].tax_exempt.kind is Kind.ESTIMATIVA  # inferido do IR no Mapa
    assert enriched["XDEL14"].alerts and "cenário de CDI" in " ".join(enriched["XDEL14"].alerts)
    assert enriched["XALF12"].mtm_vs_curve < 0  # mercado abaixo da curva (taxa subiu)


def test_overrides_do_usuario(mapa, runflow):
    ovs = {"XHOM36": Override(amortization="Anual (Início 2033)"),
           "XALF12": Override(duration=3.9, market_rate=0.0701)}
    en = {e.code: e for e in enrich(mapa, SC, runflow.candidates, ovs)}
    padrao = {e.code: e for e in enrich(mapa, SC, runflow.candidates)}
    assert en["XHOM36"].market_rate.source == SRC_IMPLIED_USER
    # amortização antecipada encurta a duration em relação à premissa "no vencimento"
    assert en["XHOM36"].duration.value < padrao["XHOM36"].duration.value - 0.5
    assert en["XALF12"].market_rate.source == SRC_OVERRIDE
    assert en["XALF12"].market_rate.value == 0.0701
    assert en["XALF12"].duration.value == 3.9 and en["XALF12"].duration.source == SRC_OVERRIDE


def test_sem_runflow_e_sem_preco(mapa):
    en = {e.code: e for e in enrich(mapa, SC, None, include_without_market_price=True)}
    assert en["XALF12"].market_rate.source == SRC_IMPLIED_DEFAULT
    assert en["CDBX0001"].in_scope  # incluído por parâmetro, mas sem taxa
    assert en["CDBX0001"].market_rate is None
    assert any("sem taxa de mercado" in a for a in en["CDBX0001"].alerts)
    assert en["CDBX0001"].duration.kind is Kind.APROXIMACAO  # = prazo


def test_fallback_para_taxa_do_runflow(mapa, runflow):
    pos = next(p for p in mapa.positions() if p.code == "XGAM13")
    pos = copy.deepcopy(pos)
    for lot in pos.lots:
        lot.pu_market = lot.pu_curve * 50  # sem solução possível
    e = enrich_position(pos, VAL, SC, runflow.by_code()["XGAM13"])
    assert e.market_rate.source == SRC_RUNFLOW_RATE and e.market_rate.kind is Kind.APROXIMACAO
    assert "recompra tende a ser pior" in e.market_rate.note


def test_dispersao_entre_lotes(mapa, runflow):
    pos = copy.deepcopy(next(p for p in mapa.positions() if p.code == "XALF12"))
    pos.lots[0].pu_curve *= 1.02
    e = enrich_position(pos, VAL, SC, runflow.by_code()["XALF12"])
    assert any("lotes do mesmo papel" in a for a in e.alerts)


def test_enrich_exige_data():
    with pytest.raises(ValueError):
        enrich(MapaPositions(None, [], 0), SC)


def test_issuer_key():
    assert issuer_key("ENERGIA ALFA S.A.") == issuer_key("Energia Alfa S.A.") == "ENERGIA ALFA"
    assert issuer_key("Logística Gama Participações S/A") == "LOGISTICA GAMA PARTICIPACOES"


# ============================================================ curvas e cenários
def _payloads(cdi_dia=0.05, meta=13.75, focus=((("R8/2026"), 13.75),), ipca12=4.5,
              anual=((2027, 4.0), (2028, 3.5)), td=()):
    return {
        "cdi": {"dados": [{"data": "2026-11-05", "valor": cdi_dia}]},
        "selic_meta": {"dados": [{"data": "2026-11-05", "valor": meta}]},
        "focus_selic": {"dados": {"data_referencia": "2026-10-30",
                                  "reunioes": [{"reuniao": r, "mediana": v} for r, v in focus]}},
        "focus_ipca": {"dados": {"data_referencia": "2026-10-30",
                                 "anual": [{"ano": a, "mediana": v} for a, v in anual],
                                 "doze_meses": {"data_referencia": "2026-10-30",
                                                "mediana": ipca12}}},
        "tesouro_direto": {"dados": list(td)},
    }


def test_cdi_esperado_constante_e_com_cortes():
    pd = PublicData.from_payloads(_payloads())
    cdi0, _ = current_cdi(pd)
    gap = 0.1375 - cdi0
    assert expected_cdi(pd, D(2026, 11, 6), 1.0).value == pytest.approx(cdi0, abs=1e-6)
    pd2 = PublicData.from_payloads(_payloads(focus=(("R8/2026", 13.75), ("R1/2027", 12.75))))
    e = expected_cdi(pd2, D(2026, 11, 6), 1.0)
    assert 0.1275 - gap < e.value < cdi0 and e.kind is Kind.ESTIMATIVA
    assert copom_date("R6/2028") == D(2028, 9, 16)
    with pytest.raises(ValueError):
        current_cdi(PublicData.from_payloads({}))


def test_ipca_esperado():
    pd = PublicData.from_payloads(_payloads())
    assert expected_ipca(pd, D(2026, 11, 6), 1.0).value == pytest.approx(0.045)
    v2 = expected_ipca(pd, D(2026, 11, 6), 2.0).value
    assert v2 == pytest.approx((1.045 * 1.04) ** 0.5 - 1)
    v4 = expected_ipca(pd, D(2026, 11, 6), 4.0).value  # anos sem Focus repetem o último
    assert v4 == pytest.approx((1.045 * 1.04 * 1.035 * 1.035) ** 0.25 - 1)
    sem12 = PublicData.from_payloads({k: v for k, v in _payloads().items()})
    sem12.focus_ipca_12m = None
    assert expected_ipca(sem12, D(2026, 11, 6), 1.0).value == pytest.approx(0.04)
    vazio = PublicData.from_payloads({})
    with pytest.raises(ValueError):
        expected_ipca(vazio, D(2026, 11, 6), 1.0)


def test_ntnb_do_tesouro_direto():
    td = [{"titulo": "Tesouro IPCA+ com Juros Semestrais", "vencimento": "2035-05-15",
           "data_base": "2026-11-05", "taxa_compra": 7.91, "taxa_venda": 8.03},
          {"titulo": "Tesouro IPCA+ com Juros Semestrais", "vencimento": "2032-08-15",
           "data_base": "2026-11-04", "taxa_compra": 7.0, "taxa_venda": 7.1},
          {"titulo": "Tesouro IPCA+", "vencimento": "2029-05-15", "data_base": "2026-11-05",
           "taxa_compra": 8.0, "taxa_venda": 8.1}]
    q, base = ntnb_quotes(PublicData.from_payloads(_payloads(td=td)))
    assert base == D(2026, 11, 5) and len(q) == 1
    assert q[0].rate == pytest.approx(0.0797) and 6.0 < q[0].duration < 7.0
    assert ntnb_quotes(PublicData.from_payloads({})) == ([], None)


def test_dados_publicos_do_repositorio_carregam():
    pd = load_public()
    s = base_scenario(pd, D(2026, 11, 6), 1.0)
    assert 0.05 < s.cdi < 0.30 and 0.0 < s.ipca < 0.20
    assert "Focus" in s.cdi_source
    q, _ = ntnb_quotes(pd)
    assert q and all(x.duration for x in q)


# ============================================================ motor de troca: carteiras sintéticas
def _lot(code, ir=0.0, iof=0.0, qty=100, net=100_000.0, mat=D(2032, 5, 15), typ="DEB"):
    return Lot(page=1, code=code, asset_type=typ, title=f"{typ} X - {code}", issuer="EMISSOR H",
               emission=D(2022, 1, 1), maturity=mat, purchase_date=D(2024, 1, 1),
               rate=Rate(Indexer.IPCA, 0.07), rate_text="7% IPCA", title_rate=None,
               quantity=qty, pu_purchase=900.0, pu_curve=1000.0, gross_curve=net, pu_market=1000.0,
               gross_market=net + ir + iof, ir=ir, iof=iof, net_value=net, income=10_000.0)


def _holding(code="HOLD11", idx=Indexer.IPCA, rate=0.065, dur=4.0, net=100_000.0,
             rating="AA", issuer="Emissor H", sector="Energia", exempt=True, ir=0.0, iof=0.0,
             in_scope=True, market=True) -> EnrichedPosition:
    pos = Position(code, [_lot(code, ir=ir, iof=iof, net=net)])
    return EnrichedPosition(
        position=pos, candidate=None, in_scope=in_scope, scope_note="", indexer=idx,
        market_rate=Sourced(rate, "teste", Kind.ESTIMATIVA) if market else None,
        duration=Sourced(dur, "teste"), dmod=dur / (1 + rate), flow="teste", lot_rates=[rate],
        rating=parse_rating(rating), sector=sector, issuer_key=issuer_key(issuer),
        tax_exempt=Sourced(exempt, "teste"))


def _cand(code="CAND11", idx=Indexer.IPCA, rate=0.075, dur=4.2, rating="AA", issuer="Emissor C",
          sector="Saneamento", exempt=True, active=True, lastro=5_000_000.0, qualified=False,
          product="DEB", fee=0.01, ntnb_year=None) -> Candidate:
    return Candidate(code=code, issuer=issuer, product=product, rate=Rate(idx, rate),
                     active=active, distribution="Ativa" if active else "Encerrada",
                     lastro=lastro, qty_available=1000, maturity=D(2032, 1, 1), duration=dur,
                     ntnb_ref_year=ntnb_year, emission_rate=rate, coupon="Semestral",
                     amortization="Bullet", sector=sector, rating=parse_rating(rating),
                     agency="X", qualified_only=qualified, tax_exempt=exempt, guarantee="",
                     internal={"fee": fee})


def _run(holdings, cands, params=None, ntnb=None):
    return run_swaps(holdings, cands, SC, VAL, params or SwapParams(issuer_limit=1.0,
                                                                     sector_limit=1.0), ntnb)


def _pair(h, c, params=None, extra=()):
    rep = _run([h, *extra], [c], params)
    pairs = rep.results[0]
    return rep, pairs


def test_troca_recomendada_basica():
    rep, r = _pair(_holding(), _cand())
    pr = r.best[0]
    assert pr.eligible and pr.final_class == RECOMENDADA and r.status == RECOMENDADA
    assert pr.delta_rate == pytest.approx(0.01)
    assert pr.delta_nominal == pytest.approx(0.01 * (1 + SAMPLE_IPCA))
    assert pr.gain_annual == pytest.approx(100_000 * 0.01 * 1.045)
    assert pr.payback_a == 0.0  # isento, sem IOF: nada a antecipar no cenário A
    assert pr.exit_cost_b == pytest.approx(0.0025 / 2 * (4 / 1.065) * 100_000)
    assert rep.applied == [pr] and rep.total_gain_annual == pytest.approx(pr.gain_annual)
    assert rep.after.avg_duration == pytest.approx(4.2)


@pytest.mark.parametrize("kwargs, filtro", [
    ({"active": False}, "distribuição e lastro"),
    ({"lastro": 50_000.0}, "distribuição e lastro"),
    ({"lastro": None}, "distribuição e lastro"),
    ({"qualified": True}, "perfil do investidor"),
    ({"exempt": False}, "tributação"),
    ({"idx": Indexer.PRE, "rate": 0.14}, "indexador"),
    ({"dur": 6.0}, "duration"),
    ({"dur": None}, "duration"),
    ({"rating": "A+"}, "rating"),
    ({"rating": "0"}, "rating"),
])
def test_cada_filtro_reprova(kwargs, filtro):
    rep, r = _pair(_holding(), _cand(**kwargs))
    assert r.best == [] and r.status == MANTER
    assert filtro in r.rejected_by


def test_filtros_parametrizaveis():
    p = SwapParams(issuer_limit=1, sector_limit=1, qualified_investor=True, accept_unrated=True,
                   rating_tolerance=1, duration_band=3.0)
    for kw in ({"qualified": True}, {"rating": "0"}, {"rating": "AA-"}, {"dur": 6.5}):
        _, r = _pair(_holding(), _cand(**kw), p)
        assert r.best, kw


def test_concentracao_emissor_e_setor():
    h, outro = _holding(net=100_000), _holding("OUTR11", net=100_000, issuer="Emissor C",
                                                  sector="Saneamento")
    # Total analisado 200 mil; a troca leva o emissor C (e o setor saneamento) a 100%.
    _, r = _pair(h, _cand(), SwapParams(issuer_limit=1.0, sector_limit=1.0), extra=[outro])
    assert r.best
    p2 = SwapParams(issuer_limit=0.90, sector_limit=1.0)
    _, r2 = _pair(h, _cand(), p2, extra=[outro])
    assert "concentração por emissor" in r2.rejected_by
    p3 = SwapParams(issuer_limit=1.0, sector_limit=0.90)
    _, r3 = _pair(h, _cand(), p3, extra=[outro])
    assert "concentração por setor" in r3.rejected_by


def test_concentracao_mesmo_emissor_nao_conta_duas_vezes():
    h = _holding(issuer="Emissor C")
    _, r = _pair(h, _cand(), SwapParams(issuer_limit=1.0, sector_limit=1.0))
    assert r.best


@pytest.mark.parametrize("delta, payback, cls", [
    (0.0030, 1.0, RECOMENDADA), (0.0040, 0.5, RECOMENDADA), (0.0029, 0.5, MARGINAL),
    (0.0010, 2.0, MARGINAL), (0.0050, 1.5, MARGINAL), (0.0009, 0.1, MANTER),
    (0.0050, 2.1, MANTER), (None, 1.0, MANTER), (0.01, None, MANTER),
])
def test_limiares_de_classificacao(delta, payback, cls):
    assert classify(delta, payback, True, SwapParams()) == cls
    assert classify(0.01, 0.1, False, SwapParams()) == MANTER


def test_divergencia_entre_cenarios_a_e_b():
    # Δ de 35 bps: em A (sem custo) é recomendada; em B o custo de saída alonga o equilíbrio.
    p = SwapParams(issuer_limit=1, sector_limit=1, liquidity_class="baixa")
    _, r = _pair(_holding(dur=8.0), _cand(rate=0.0685, dur=8.0), p)
    pr = r.best[0]
    assert pr.class_a == RECOMENDADA and pr.class_b != RECOMENDADA
    assert pr.diverges and any("recompra" in a for a in pr.alerts)
    assert r.status == pr.class_b  # a final é a do cenário B


def test_fee_nao_muda_ranking_nem_classificacao():
    h = _holding()
    cs = [_cand("C1", rate=0.072, fee=0.0001), _cand("C2", rate=0.075, fee=0.05),
          _cand("C3", rate=0.073, fee=0.03)]
    r1 = _run([h], cs).results[0]
    cs2 = [copy.deepcopy(c) for c in cs]
    for c, f in zip(cs2, (0.09, 0.0, 0.5)):
        c.internal["fee"] = f
    r2 = _run([h], cs2).results[0]
    assert [p.candidate.code for p in r1.best] == [p.candidate.code for p in r2.best] == \
        ["C2", "C3", "C1"]
    assert [p.final_class for p in r1.best] == [p.final_class for p in r2.best]


def test_imposto_antecipado_tributado():
    h = _holding(exempt=False, ir=1_500.0, iof=0.0)
    t = anticipated_tax_position(h, VAL, SC)
    r = (1.065) * (1 + SAMPLE_IPCA) - 1
    from cpsim.calendar import business_days
    t_rest = business_days(VAL, D(2032, 5, 15)) / 252
    assert t == pytest.approx(1_500 * (1 - (1 + r) ** (-t_rest)))
    _, res = _pair(h, _cand(exempt=False))
    pr = res.best[0]
    assert pr.tax_anticipated == pytest.approx(t)
    assert pr.payback_a == pytest.approx(t / 100_000 / pr.delta_nominal)
    assert any("tabela regressiva" in a for a in pr.alerts)
    h2 = _holding(iof=200.0)
    assert anticipated_tax_position(h2, VAL, SC) == pytest.approx(200.0)


def test_modo_amplo_entre_indexadores():
    p = SwapParams(issuer_limit=1, sector_limit=1, same_indexer=False)
    _, r = _pair(_holding(), _cand(idx=Indexer.PRE, rate=0.14), p)
    pr = r.best[0]
    nom_h = 1.065 * 1.045 - 1
    assert pr.delta_rate == pytest.approx(0.14 - nom_h)
    assert any("cenário" in a for a in pr.alerts)


def test_tributacoes_diferentes_com_filtro_desligado():
    p = SwapParams(issuer_limit=1, sector_limit=1, same_tax=False)
    _, r = _pair(_holding(exempt=True), _cand(exempt=False, rate=0.09), p)
    assert any("líquida de IR" in a for a in r.best[0].alerts)


def test_pct_cdi_e_spread_ntnb():
    _, r = _pair(_holding(idx=Indexer.CDI_PCT, rate=1.00, dur=2.0),
                 _cand(idx=Indexer.CDI_PCT, rate=1.04, dur=2.0))
    assert r.best[0].delta_rate == pytest.approx(0.04 * SAMPLE_CDI)
    ntnb = [NtnbQuote(D(2030, 8, 15), 0.079, 3.4), NtnbQuote(D(2032, 8, 15), 0.0795, 4.8)]
    rep = _run([_holding()], [_cand(ntnb_year=2032)], ntnb=ntnb)
    pr = rep.results[0].best[0]
    # posição (D 4,0): NTN-B de duration mais próxima = 2030 (3,4); candidato: B32 indicada
    assert pr.delta_metric_name == "Δ spread s/ NTN-B"
    assert pr.delta_spread == pytest.approx((1.075 / 1.0795 - 1) - (1.065 / 1.079 - 1))


def test_sem_taxa_fora_do_escopo_e_lastro_compartilhado():
    h1, h2 = _holding("H1", net=100_000), _holding("H2", net=100_000)
    sem = _holding("H3", market=False)
    fora = _holding("H4", in_scope=False)
    c = _cand(lastro=150_000.0)  # só cabe uma das duas trocas
    rep = _run([h1, h2, sem, fora], [c])
    st = {r.holding.code: r.status for r in rep.results}
    assert st["H3"] == SEM_TAXA and st["H4"] == FORA
    assert st["H1"] == RECOMENDADA and st["H2"] == RECOMENDADA
    assert len(rep.applied) == 1 and any("lastro esgotado" in a for a in rep.alerts)


# ============================================================ relatório e modos
@pytest.fixture(scope="module")
def full_run(runflow):
    m = parse_mapa((SAMPLES / "mapa_posicoes_layout_real.pdf").read_bytes())
    en = enrich(m, SC, runflow.candidates)
    q, _ = ntnb_quotes(load_public())
    return en, run_swaps(en, runflow.candidates, SC, m.position_date, ntnb=q), runflow


def _cells(xlsx: bytes) -> list[str]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(xlsx), read_only=True)
    out = [str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True)
           for v in row if v is not None]
    wb.close()
    return out


def test_export_cliente_sem_colunas_internas(full_run):
    en, rep, rf = full_run
    labels = rf.internal_labels
    cells = _cells(report.to_excel(rep, en, "cliente", labels))
    blob = " | ".join(cells).lower()
    for rot in labels.values():
        assert rot.lower() not in blob
    for cab in load_internal_columns(EXAMPLE).headers.values():
        assert cab.lower() not in blob
    assert "runflow" not in blob and "lastro" not in blob
    assert "não constitui recomendação" in blob


def test_export_interno_tem_colunas_internas(full_run):
    en, rep, rf = full_run
    cells = _cells(report.to_excel(rep, en, "interno", rf.internal_labels))
    blob = " | ".join(cells)
    assert report.LASTRO_COL in blob
    assert any(rot in blob for rot in rf.internal_labels.values())
    assert "Runflow" in blob  # interno pode citar a fonte


def test_tabelas_e_resumo(full_run):
    en, rep, _ = full_run
    rows = report.positions_table(en, "interno")
    assert {r["Código"] for r in rows} >= set(TAXA_MERCADO)
    swaps = report.swaps_table(rep, "cliente")
    assert any(r["Classificação (B)"] in (RECOMENDADA, MARGINAL) for r in swaps)
    assert all("✓" in r.get("Justificativa", "") or r["Candidato"] == "—" for r in swaps)
    assert all("lastro" not in r.get("Justificativa", "").lower() for r in swaps)
    summ = {r["Item"]: r for r in report.summary_table(rep)}
    assert summ["Trocas recomendadas aplicadas"]["Depois"] == str(len(rep.applied))
    prem = report.assumptions_table(rep)
    assert prem[0]["Valor"] == report.AVISO
    assert report.sanitize("Taxa do Runflow", "cliente") == "Taxa da oferta disponível"
    assert report.sanitize("fora do runflow; Runflow", "cliente") ==         "fora da oferta disponível; oferta disponível"
    assert report.sanitize("Taxa do Runflow", "interno") == "Taxa do Runflow"
    assert report.sanitize(3, "cliente") == 3


# ============================================================ coleta de dados públicos
def test_coleta_mantem_arquivo_anterior_em_falha(tmp_path, monkeypatch):
    import update_public_data as up

    monkeypatch.setattr(up, "OUT", tmp_path)
    (tmp_path / "cdi.json").write_text('{"anterior": true}', encoding="utf-8")

    def falha(*a, **k):
        raise OSError("sem rede")

    monkeypatch.setattr(up, "_get", falha)
    assert up.main() == 1
    assert json.loads((tmp_path / "cdi.json").read_text("utf-8")) == {"anterior": True}
    st = json.loads((tmp_path / "_status.json").read_text("utf-8"))
    assert st["ok"] == [] and "cdi.json" in st["erros"]


def test_coleta_grava_fonte_url_e_horario(tmp_path, monkeypatch):
    import update_public_data as up

    monkeypatch.setattr(up, "OUT", tmp_path)
    resp = {"sgs": [{"data": "05/11/2026", "valor": "0.05"}, {"data": "09/12/2099",
                                                              "valor": "1"}]}

    def fake_json(url):
        if "bcdata.sgs" in url:
            return resp["sgs"]
        if "Selic" in url:
            return {"value": [{"Data": "2026-10-30", "Reuniao": "R1/2027", "Mediana": 13.5},
                              {"Data": "2026-10-30", "Reuniao": "R8/2026", "Mediana": 13.75}]}
        if "Anuais" in url:
            return {"value": [{"Data": "2026-10-30", "DataReferencia": "2027", "Mediana": 4.0}]}
        return {"value": [{"Data": "2026-10-30", "Mediana": 4.5}]}

    csv = ("Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
           "PU Compra Manha;PU Venda Manha;PU Base Manha\n"
           "Tesouro IPCA+ com Juros Semestrais;15/05/2035;05/11/2026;7,91;8,03;4381,57;4348,72;"
           "4348,72\nTesouro Selic;01/03/2029;05/11/2026;0,06;0,07;1;1;1\n")
    monkeypatch.setattr(up, "_json", fake_json)
    monkeypatch.setattr(up, "_get", lambda url, timeout=90: csv.encode("latin-1"))
    assert up.main() == 0
    cdi = json.loads((tmp_path / "cdi.json").read_text("utf-8"))
    assert set(cdi) == {"fonte", "url", "coletado_em", "dados"}
    assert cdi["coletado_em"].endswith("-03:00")
    assert all(r["data"] <= "2026-12-31" for r in cdi["dados"])  # corta datas futuras (432)
    fs = json.loads((tmp_path / "focus_selic.json").read_text("utf-8"))["dados"]
    assert [r["reuniao"] for r in fs["reunioes"]] == ["R8/2026", "R1/2027"]
    td = json.loads((tmp_path / "tesouro_direto.json").read_text("utf-8"))["dados"]
    assert len(td) == 1 and td[0]["taxa_compra"] == 7.91
