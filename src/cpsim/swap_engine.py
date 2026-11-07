"""Motor de troca: para cada posição, candidatos do Runflow elegíveis, economia e classificação.

Prompt 6.2–6.5; metodologia 10.2, 10.3 e 10.5 (etapas do motor de troca).

Regras inegociáveis aplicadas aqui:
- o fee/receita da mesa e demais colunas internas NUNCA são lidos (`Candidate.internal` não é
  acessado neste módulo); o ranking usa só a economia do cliente (regra 7);
- limiares de classificação são hipóteses não validadas por backtest (regra 9).

Cenário A: PU Mercado = preço executável (custo de saída 0).
Cenário B: PU Mercado = marcação; custo de saída = (b/2) × D_mod × V, b por classe de liquidez
(sem ANBIMA no MVP). A classificação final usa o cenário B.
A taxa de compra do Runflow já embute o custo de entrada (por isso só a saída é cobrada).
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field

from .calendar import business_days
from .enrich import EnrichedPosition, issuer_key
from .models import Candidate, Indexer, Rate
from .rates import nominal_expected, rate_difference
from .scenarios import Scenario
from .spreads import (DEFAULT_BID_ASK_BY_LIQUIDITY, NtnbQuote, exit_cost, ntnb_reference,
                      payback_years, spread_over_ntnb)
from .taxes import DEFAULT_POLICY, TaxPolicy

RECOMENDADA = "Troca recomendada"
MARGINAL = "Troca marginal"
MANTER = "Manter"
SEM_TAXA = "Sem taxa de mercado"
FORA = "Fora do escopo"


@dataclass(frozen=True)
class SwapParams:
    """Parâmetros da tela 2 (padrões = prompt 6.2–6.5; todos hipóteses ajustáveis)."""

    qualified_investor: bool = False
    duration_band: float = 1.5  # anos
    same_tax: bool = True
    same_indexer: bool = True  # False = modo amplo (compara taxa nominal esperada)
    rating_tolerance: int = 0  # degraus aceitos abaixo do rating atual
    accept_unrated: bool = False  # "sem rating em qualquer lado -> alerta e exige confirmação"
    issuer_limit: float = 0.20
    sector_limit: float = 0.40
    liquidity_class: str = "media"  # classe padrão das posições (alta, media, baixa)
    liquidity_by_code: dict[str, str] = field(default_factory=dict)
    bid_ask_by_class: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_BID_ASK_BY_LIQUIDITY))
    rec_min_delta: float = 0.0030  # 30 bps
    rec_max_payback: float = 1.0  # anos
    marg_min_delta: float = 0.0010  # 10 bps
    marg_max_payback: float = 2.0
    top_n: int = 3
    policy: TaxPolicy = DEFAULT_POLICY


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class PairResult:
    holding: EnrichedPosition
    candidate: Candidate
    checks: list[Check]
    delta_rate: float | None = None  # Δy no mesmo indexador (ou nominal, no modo amplo)
    delta_spread: float | None = None  # Δs sobre a NTN-B (IPCA)
    delta_metric: float | None = None  # o Δ usado na classificação
    delta_metric_name: str = ""
    delta_nominal: float | None = None  # Δ de taxa nominal esperada (ganho em R$)
    gain_annual: float | None = None  # R$/ano = V × Δ nominal
    exit_cost_b: float = 0.0  # R$
    tax_anticipated: float = 0.0  # R$ (IR antecipado + IOF)
    payback_a: float | None = None
    payback_b: float | None = None
    class_a: str = MANTER
    class_b: str = MANTER
    net_gain_b: float | None = None  # R$/ano: ganho − (saída + imposto)/horizonte (ranking)
    alerts: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def final_class(self) -> str:
        return self.class_b

    @property
    def diverges(self) -> bool:
        return self.class_a != self.class_b


@dataclass
class PositionResult:
    holding: EnrichedPosition
    best: list[PairResult]
    evaluated: int
    rejected_by: Counter
    status: str

    @property
    def top(self) -> PairResult | None:
        return self.best[0] if self.best else None


@dataclass
class PortfolioStats:
    total: float
    avg_nominal_rate: float | None
    avg_duration: float | None
    by_issuer: dict[str, float]
    by_sector: dict[str, float]


@dataclass
class SwapReport:
    scenario: Scenario
    params: SwapParams
    as_of: dt.date
    results: list[PositionResult]
    before: PortfolioStats
    after: PortfolioStats
    applied: list[PairResult]
    total_gain_annual: float
    alerts: list[str]


# ----------------------------------------------------------------------------- economia
def _delta_ntnb_spread(h: EnrichedPosition, c: Candidate, ntnb: list[NtnbQuote],
                       as_of: dt.date) -> float | None:
    if h.indexer is not Indexer.IPCA or c.indexer is not Indexer.IPCA or not ntnb:
        return None
    ref_h = ntnb_reference(ntnb, ref_year=h.candidate.ntnb_ref_year if h.candidate else None,
                           duration=h.duration.value if h.duration else None, as_of=as_of)
    ref_c = ntnb_reference(ntnb, ref_year=c.ntnb_ref_year, duration=c.duration, as_of=as_of)
    if ref_h is None or ref_c is None:
        return None
    s_h = spread_over_ntnb(h.market_rate.value, ref_h.value.rate)
    s_c = spread_over_ntnb(c.rate.value, ref_c.value.rate)
    return s_c - s_h


def _years_to(as_of: dt.date, d: dt.date | None) -> float:
    return max(business_days(as_of, d) / 252.0, 0.0) if d else 0.0


def anticipated_tax_position(h: EnrichedPosition, as_of: dt.date, scenario: Scenario) -> float:
    """IR antecipado + IOF da venda, a partir do IR e IOF que o Mapa informa por lote
    (prompt 6.6). IR: T ≈ IR_lote × [1 − (1 + r)^(−T_rest)] (metodologia 10.2), com r = taxa
    nominal esperada do papel e T_rest = prazo até o vencimento. IOF: devido integralmente."""
    r = nominal_expected(h.rate, scenario.cdi, scenario.ipca) if h.rate else 0.0
    t_rest = _years_to(as_of, h.position.maturity)
    total = 0.0
    for lot in h.position.lots:
        ir = lot.ir or 0.0
        if ir > 0 and t_rest > 0:
            total += ir * (1.0 - (1.0 + r) ** (-t_rest))
        total += lot.iof or 0.0
    return total


def classify(delta: float | None, payback: float | None, eligible: bool,
             p: SwapParams) -> str:
    """Prompt 6.5. Recomendada: Δ ≥ 30 bps e equilíbrio ≤ 1 ano. Marginal: 10 ≤ Δ < 30 bps
    ou 1 < equilíbrio ≤ 2 anos (com Δ ≥ 10 bps e equilíbrio ≤ 2 anos). Senão: manter."""
    if not eligible or delta is None or payback is None:
        return MANTER
    if delta >= p.rec_min_delta and payback <= p.rec_max_payback:
        return RECOMENDADA
    if delta >= p.marg_min_delta and payback <= p.marg_max_payback:
        return MARGINAL
    return MANTER


def evaluate_pair(h: EnrichedPosition, c: Candidate, ctx: _Context) -> PairResult:
    p, sc = ctx.params, ctx.scenario
    V = h.net_value
    checks: list[Check] = []
    alerts: list[str] = []

    # --- filtros (prompt 6.2)
    lastro_ok = c.active and c.lastro is not None and c.lastro >= V
    checks.append(Check("distribuição e lastro", lastro_ok,
                        f"distribuição {c.distribution or '—'}; lastro "
                        f"{'—' if c.lastro is None else f'{c.lastro:,.0f}'} vs saída {V:,.0f}"))
    perfil_ok = not (c.qualified_only and not p.qualified_investor)
    checks.append(Check("perfil do investidor", perfil_ok,
                        "exige investidor qualificado" if c.qualified_only else "público geral"))
    ex_h = h.tax_exempt.value
    ex_c = p.policy.is_exempt(c.product, c.tax_exempt)
    if p.same_tax:
        checks.append(Check("tributação", ex_h == ex_c,
                             f"atual {'isento' if ex_h else 'tributado'}; candidato "
                             f"{'isento' if ex_c else 'tributado'}"))
    same_idx = c.indexer is h.indexer
    if p.same_indexer:
        checks.append(Check("indexador", same_idx,
                             f"{h.indexer.value if h.indexer else '—'} → "
                             f"{c.indexer.value if c.indexer else '—'}"))
    if h.duration is None or c.duration is None:
        checks.append(Check("duration", False, "duration ausente"))
    else:
        dd = c.duration - h.duration.value
        checks.append(Check("duration", abs(dd) <= p.duration_band,
                             f"{h.duration.value:.2f} → {c.duration:.2f} anos (Δ {dd:+.2f}; "
                             f"banda ±{p.duration_band:.1f})"))
    if h.rating.has_rating and c.rating.has_rating:
        ok = c.rating.notch >= h.rating.notch - p.rating_tolerance
        checks.append(Check("rating", ok, f"{h.rating.label} → {c.rating.label}"))
    else:
        checks.append(Check("rating", p.accept_unrated,
                             f"sem rating ({h.rating.label or '—'} → {c.rating.label or '—'}); "
                             + ("aceito pelo usuário" if p.accept_unrated
                                else "exige confirmação")))
        alerts.append("rating ausente em um dos lados")
    # concentração após a troca
    tot = ctx.total
    ik, sk = issuer_key(c.issuer), (c.sector or "").strip().lower()
    exp_i = ctx.by_issuer.get(ik, 0.0) + V - (V if ik == h.issuer_key else 0.0)
    exp_s = ctx.by_sector.get(sk, 0.0) + V - (V if sk == (h.sector or "").strip().lower() else 0.0)
    if tot > 0:
        checks.append(Check("concentração por emissor", exp_i / tot <= p.issuer_limit,
                             f"{exp_i / tot:.1%} do total analisado (limite {p.issuer_limit:.0%})"))
        if sk:
            checks.append(Check("concentração por setor", exp_s / tot <= p.sector_limit,
                                 f"{exp_s / tot:.1%} (limite {p.sector_limit:.0%})"))

    res = PairResult(h, c, checks, alerts=alerts)
    if h.rate is None or c.rate is None:
        return res

    # --- economia (prompt 6.3)
    n_h = nominal_expected(h.rate, sc.cdi, sc.ipca)
    n_c = nominal_expected(c.rate, sc.cdi, sc.ipca)
    if ex_h != ex_c:  # só com o filtro de tributação desligado: compara líquido de IR
        ir_new = p.policy.ir_rate(int(round(sc.horizon_years * 365)))
        n_h = n_h if ex_h else n_h * (1 - ir_new)
        n_c = n_c if ex_c else n_c * (1 - ir_new)
        alerts.append("tributações diferentes: comparação líquida de IR (aproximação)")
    res.delta_nominal = n_c - n_h
    if same_idx:
        res.delta_rate = rate_difference(c.rate, h.rate, cdi=sc.cdi)
    else:
        res.delta_rate = res.delta_nominal
        alerts.append(f"indexadores diferentes: comparação pela taxa nominal esperada no cenário "
                      f"'{sc.name}' (CDI {sc.cdi:.2%}, IPCA {sc.ipca:.2%})")
    res.delta_spread = _delta_ntnb_spread(h, c, ctx.ntnb, ctx.as_of) if same_idx else None
    if res.delta_spread is not None:
        res.delta_metric, res.delta_metric_name = res.delta_spread, "Δ spread s/ NTN-B"
    else:
        res.delta_metric, res.delta_metric_name = res.delta_rate, "Δ taxa"
        if same_idx and h.indexer is Indexer.IPCA:
            alerts.append("sem NTN-B de referência: classificação pela diferença de taxa")
    res.gain_annual = V * res.delta_nominal

    cls = p.liquidity_by_code.get(h.code, p.liquidity_class)
    b = p.bid_ask_by_class.get(cls, p.bid_ask_by_class.get("media", 0.0025))
    res.exit_cost_b = exit_cost(b, h.dmod or 0.0) * V
    res.tax_anticipated = ctx.tax_by_code[h.code]
    if res.gain_annual > 0:
        res.payback_a = payback_years(res.tax_anticipated / V, res.delta_nominal) if V else None
        res.payback_b = payback_years((res.exit_cost_b + res.tax_anticipated) / V,
                                      res.delta_nominal) if V else None
    res.class_a = classify(res.delta_metric, res.payback_a, res.eligible, p)
    res.class_b = classify(res.delta_metric, res.payback_b, res.eligible, p)
    if res.diverges:
        res.alerts.append("depende do preço real de recompra (cenários A e B divergem)")
    if not ex_h and res.tax_anticipated > 0:
        res.alerts.append("a nova aplicação reinicia a tabela regressiva de IR")
    res.net_gain_b = res.gain_annual - (res.exit_cost_b + res.tax_anticipated) / sc.horizon_years
    return res


@dataclass
class _Context:
    params: SwapParams
    scenario: Scenario
    as_of: dt.date
    total: float
    by_issuer: dict[str, float]
    by_sector: dict[str, float]
    ntnb: list[NtnbQuote]
    tax_by_code: dict[str, float]


def _stats(items: list[tuple[float, float | None, float | None, str, str]]) -> PortfolioStats:
    """items: (valor, taxa nominal, duration, emissor, setor)."""
    tot = sum(v for v, *_ in items)
    with_r = [(v, r) for v, r, *_ in items if r is not None]
    with_d = [(v, d) for v, _, d, *_ in items if d is not None]
    by_i: dict[str, float] = {}
    by_s: dict[str, float] = {}
    for v, _, _, i, s in items:
        by_i[i] = by_i.get(i, 0.0) + v
        if s:
            by_s[s] = by_s.get(s, 0.0) + v
    wavg = (lambda xs: sum(v * x for v, x in xs) / sum(v for v, _ in xs) if xs else None)
    return PortfolioStats(tot, wavg(with_r), wavg(with_d),
                          {k: v / tot for k, v in by_i.items()} if tot else {},
                          {k: v / tot for k, v in by_s.items()} if tot else {})


def run_swaps(enriched: list[EnrichedPosition], candidates: list[Candidate], scenario: Scenario,
              as_of: dt.date, params: SwapParams | None = None,
              ntnb: list[NtnbQuote] | None = None) -> SwapReport:
    p = params or SwapParams()
    scope = [h for h in enriched if h.in_scope]
    total = sum(h.net_value for h in scope)
    by_issuer: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for h in scope:
        by_issuer[h.issuer_key] = by_issuer.get(h.issuer_key, 0.0) + h.net_value
        s = (h.sector or "").strip().lower()
        if s:
            by_sector[s] = by_sector.get(s, 0.0) + h.net_value
    ctx = _Context(p, scenario, as_of, total, by_issuer, by_sector, ntnb or [],
                   {h.code: anticipated_tax_position(h, as_of, scenario) for h in scope})

    results: list[PositionResult] = []
    for h in enriched:
        if not h.in_scope:
            results.append(PositionResult(h, [], 0, Counter(), FORA))
            continue
        if not h.has_market_rate:
            results.append(PositionResult(h, [], 0, Counter(), SEM_TAXA))
            continue
        pairs = [evaluate_pair(h, c, ctx) for c in candidates if c.code != h.code]
        rejected = Counter(ch.name for pr in pairs for ch in pr.checks if not ch.passed)
        ok = [pr for pr in pairs if pr.eligible and pr.net_gain_b is not None]
        ok.sort(key=lambda pr: pr.net_gain_b, reverse=True)  # só economia do cliente (regra 7)
        best = ok[: p.top_n]
        status = best[0].final_class if best else MANTER
        results.append(PositionResult(h, best, len(pairs), rejected, status))

    # carteira antes/depois: aplica a melhor troca RECOMENDADA de cada posição, respeitando lastro
    def item(h: EnrichedPosition):
        r = nominal_expected(h.rate, scenario.cdi, scenario.ipca) if h.rate else None
        return (h.net_value, r, h.duration.value if h.duration else None, h.issuer_key,
                (h.sector or "").strip().lower())

    before = _stats([item(h) for h in scope])
    lastro_left = {c.code: c.lastro or 0.0 for c in candidates}
    applied: list[PairResult] = []
    alerts: list[str] = []
    after_items = []
    swaps = sorted((r for r in results if r.top and r.top.final_class == RECOMENDADA),
                   key=lambda r: r.top.net_gain_b, reverse=True)
    swapped: dict[str, PairResult] = {}
    for r in swaps:
        pr = next((x for x in r.best if x.final_class == RECOMENDADA
                   and lastro_left[x.candidate.code] >= r.holding.net_value), None)
        if pr is None:
            alerts.append(f"{r.holding.code}: lastro esgotado pelas outras trocas")
            continue
        lastro_left[pr.candidate.code] -= r.holding.net_value
        swapped[r.holding.code] = pr
        applied.append(pr)
    for h in scope:
        pr = swapped.get(h.code)
        if pr is None:
            after_items.append(item(h))
        else:
            c = pr.candidate
            after_items.append((h.net_value, nominal_expected(c.rate, scenario.cdi, scenario.ipca),
                                c.duration, issuer_key(c.issuer), (c.sector or "").strip().lower()))
    after = _stats(after_items)
    return SwapReport(scenario, p, as_of, results, before, after, applied,
                      sum(pr.gain_annual or 0.0 for pr in applied), alerts)


