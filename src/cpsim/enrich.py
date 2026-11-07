"""Enriquecimento da carteira: taxa de mercado e duration de cada posição (metodologia 10.5).

Regra definida pelo usuário em 07/11/2026 (ANBIMA e B3 fora do MVP):

1. Código no Runflow -> duration e fluxo (Cupom/Amortização) do Runflow.
2. Fora do Runflow -> fluxo PADRÃO: juros semestrais e amortização no vencimento.
   Nos dois casos, a taxa de mercado y resolve
        PU(y) / PU(taxa de operação) = PU Mercado / PU Curva,
   com o mesmo fluxo aproximado nos dois lados (o VNA se cancela; o PU Curva do Mapa é o PU na
   taxa de operação — conferido no Mapa real em 07/11/2026). Resultado marcado "taxa estimada".
   Sem Runflow, a duration sai do mesmo cálculo.
3. O usuário pode sobrescrever cupom, amortização, duration ou a própria taxa (`Override`).
Se a equação não tiver solução e o papel estiver no Runflow, usa a Taxa de Compra dele como
APROXIMAÇÃO (taxa de venda da mesa; a recompra tende a ser pior). Sem nada disso: sem taxa.

Limite conhecido da premissa "amortização no vencimento": o erro da taxa cresce com a distância
entre taxa de mercado e taxa de operação e com o peso da amortização antecipada; a duration
fica superestimada (ver docs/FASE2_RELATORIO.md).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .calendar import business_days
from .cashflows import build_schedule
from .models import Candidate, Indexer, Kind, MapaPositions, Position, Rate, Rating, Sourced
from .normalize import strip_accents
from .pricing import brent, macaulay_duration, price
from .rates import cdi_plus_to_annual, pct_cdi_to_annual
from .scenarios import Scenario
from .taxes import DEFAULT_POLICY, TaxPolicy

DEFAULT_COUPON = "Semestral"
DEFAULT_AMORTIZATION = "Bullet"
SCOPE_TYPES = {"DEB", "CRI", "CRA"}
LOT_DISPERSION_ALERT = 0.0005  # 5 bps

SRC_OVERRIDE = "informado pelo usuário"
SRC_IMPLIED_RUNFLOW = "estimada pelo PU Mercado (fluxo do Runflow)"
SRC_IMPLIED_DEFAULT = "estimada pelo PU Mercado (fluxo padrão: juros semestrais, amortização no vencimento)"
SRC_IMPLIED_USER = "estimada pelo PU Mercado (fluxo informado pelo usuário)"
SRC_RUNFLOW_RATE = "Taxa de Compra do Runflow"
SRC_RUNFLOW_DURATION = "Duration do Runflow"
SRC_DURATION_CALC = "calculada com o fluxo da estimativa"


@dataclass
class Override:
    """Campos opcionais da tela Carteira para sobrescrever a estimativa."""

    coupon: str | None = None
    amortization: str | None = None
    duration: float | None = None  # anos (Macaulay)
    market_rate: float | None = None  # mesma unidade da taxa do papel (decimal; %CDI em fração)


@dataclass
class EnrichedPosition:
    position: Position
    candidate: Candidate | None  # mesmo código no Runflow
    in_scope: bool
    scope_note: str
    indexer: Indexer | None
    market_rate: Sourced | None  # value: float (decimal; %CDI em fração do CDI)
    duration: Sourced | None  # value: anos (Macaulay)
    dmod: float | None
    flow: str  # descrição do fluxo usado
    lot_rates: list[float]
    rating: Rating
    sector: str
    issuer_key: str
    tax_exempt: Sourced  # value: bool
    alerts: list[str] = field(default_factory=list)

    @property
    def code(self) -> str:
        return self.position.code

    @property
    def net_value(self) -> float:
        return self.position.net_value or 0.0

    @property
    def mtm_vs_curve(self) -> float | None:
        """Ganho/perda de marcação: Valor Bruto (mercado) − Valor Bruto (curva)."""
        gm, gc = self.position.gross_market, self.position.gross_curve
        return None if gm is None or gc is None else gm - gc

    @property
    def rate(self) -> Rate | None:
        if self.market_rate is None or self.indexer is None:
            return None
        return Rate(self.indexer, self.market_rate.value)

    @property
    def has_market_rate(self) -> bool:
        return self.market_rate is not None


# ----------------------------------------------------------------------------- utilidades
def issuer_key(name: str) -> str:
    """Nome de emissor comparável entre Mapa e Runflow ("ENERGIA ALFA S.A." ~ "Energia Alfa S.A.")."""
    t = strip_accents(name or "").upper()
    t = re.sub(r"\b(S\.?\s?A\.?|S/A|LTDA\.?|CIA\.?|COMPANHIA|EM RECUPERACAO JUDICIAL)\b", " ", t)
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    return " ".join(t.split())


def discount_rate(indexer: Indexer, value: float, scenario: Scenario) -> float:
    """Taxa de desconto anual do fluxo: Pré nominal, IPCA real (fluxo real), CDI em nominal
    pelo cenário de CDI (fluxo projetado)."""
    if indexer is Indexer.CDI_PCT:
        return pct_cdi_to_annual(value, scenario.cdi)
    if indexer is Indexer.CDI_SPREAD:
        return cdi_plus_to_annual(value, scenario.cdi)
    return value


def implied_rate(pu_market: float, pu_curve: float, purchase_rate: Rate, coupon_rate: float,
                 valuation: dt.date, maturity: dt.date, coupon_text: str, amort_text: str,
                 scenario: Scenario) -> tuple[float, float, list[str]] | None:
    """Resolve y em PU(y)/PU(taxa_op) = PU Mercado/PU Curva. Retorna (y, duration Macaulay em
    anos, alertas) ou None se não houver fluxo ou solução."""
    idx = purchase_rate.indexer
    sch = build_schedule(valuation, maturity, coupon_text, amort_text,
                         discount_rate(idx, coupon_rate, scenario))
    if not sch.ok:
        return None
    flows = sch.as_pricing_flows()
    base = price(flows, discount_rate(idx, purchase_rate.value, scenario))
    target = pu_market / pu_curve

    def g(y: float) -> float:
        return price(flows, discount_rate(idx, y, scenario)) / base - target

    lo, hi = (0.05, 5.0) if idx is Indexer.CDI_PCT else (-0.3, 1.5)
    try:
        y = brent(g, lo, hi, tol=1e-10)
    except ValueError:
        return None
    dur = macaulay_duration(flows, discount_rate(idx, y, scenario))
    return y, dur, list(sch.warnings)


def _tax_exempt(pos: Position, cand: Candidate | None, policy: TaxPolicy) -> Sourced:
    if cand is not None and cand.tax_exempt is not None:
        return Sourced(policy.is_exempt(pos.asset_type, cand.tax_exempt), "Runflow (Isento?)")
    if (pos.asset_type or "") in policy.pf_exempt_products:
        return Sourced(policy.is_exempt(pos.asset_type, None), "tipo do papel")
    lots = pos.lots
    if any((lot.income or 0) > 0 for lot in lots) and all((lot.ir or 0) == 0 for lot in lots):
        return Sourced(policy.is_exempt(pos.asset_type, True), "inferido: IR zero com rendimento",
                       Kind.ESTIMATIVA)
    return Sourced(policy.is_exempt(pos.asset_type, False), "inferido: IR no Mapa", Kind.ESTIMATIVA)


# ----------------------------------------------------------------------------- principal
def enrich_position(pos: Position, valuation: dt.date, scenario: Scenario,
                    candidate: Candidate | None = None, override: Override | None = None, *,
                    include_without_market_price: bool = False,
                    policy: TaxPolicy = DEFAULT_POLICY) -> EnrichedPosition:
    ov = override or Override()
    alerts: list[str] = []
    first = pos.first
    idx = pos.indexer
    in_scope = (pos.asset_type in SCOPE_TYPES and pos.has_market_price) or (
        include_without_market_price and pos.asset_type is not None)
    if not pos.has_market_price:
        note = "sem PU Mercado" + ("" if include_without_market_price else " (fora por padrão)")
    elif pos.asset_type not in SCOPE_TYPES:
        note = f"tipo {pos.asset_type} fora do escopo"
    else:
        note = ""

    # fluxo: usuário > Runflow > padrão
    if ov.coupon or ov.amortization:
        coupon = ov.coupon or (candidate.coupon if candidate else DEFAULT_COUPON)
        amort = ov.amortization or (candidate.amortization if candidate else DEFAULT_AMORTIZATION)
        flow_desc, src_implied = f"Cupom {coupon}; Amortização {amort}", SRC_IMPLIED_USER
    elif candidate is not None and candidate.coupon and candidate.amortization:
        coupon, amort = candidate.coupon, candidate.amortization
        flow_desc, src_implied = f"Cupom {coupon}; Amortização {amort} (Runflow)", SRC_IMPLIED_RUNFLOW
    else:
        coupon, amort = DEFAULT_COUPON, DEFAULT_AMORTIZATION
        flow_desc, src_implied = ("juros semestrais, amortização no vencimento (padrão)",
                                  SRC_IMPLIED_DEFAULT)

    # taxa implícita por lote
    lot_rates: list[tuple[float, int]] = []
    calc_dur: float | None = None
    for lot in pos.lots:
        if not (lot.pu_market and lot.pu_curve and lot.rate and lot.maturity):
            continue
        coupon_rate = ((candidate.emission_rate if candidate and candidate.emission_rate
                        is not None else None)
                       or (lot.title_rate.value if lot.title_rate
                           and lot.title_rate.indexer is lot.rate.indexer else None)
                       or lot.rate.value)
        res = implied_rate(lot.pu_market, lot.pu_curve, lot.rate, coupon_rate, valuation,
                           lot.maturity, coupon, amort, scenario)
        if res is None:
            continue
        y, d, w = res
        lot_rates.append((y, lot.quantity or 1))
        calc_dur = d
        for x in w:
            if x not in alerts:
                alerts.append(x)

    market_rate: Sourced | None = None
    if ov.market_rate is not None:
        market_rate = Sourced(ov.market_rate, SRC_OVERRIDE)
    elif lot_rates:
        tot = sum(q for _, q in lot_rates)
        y = sum(v * q for v, q in lot_rates) / tot
        market_rate = Sourced(y, src_implied, Kind.ESTIMATIVA, "taxa estimada")
        disp = max(v for v, _ in lot_rates) - min(v for v, _ in lot_rates)
        if disp > LOT_DISPERSION_ALERT:
            alerts.append(f"lotes do mesmo papel dão taxas diferentes ({disp * 1e4:.0f} bps): "
                          "o fluxo usado pode não ser o do papel")
        if src_implied == SRC_IMPLIED_DEFAULT:
            alerts.append("taxa estimada com fluxo padrão; se o papel amortiza antes do "
                          "vencimento, informe a amortização (o erro cresce com a distância "
                          "entre taxa de mercado e taxa de operação)")
        if idx in (Indexer.CDI_PCT, Indexer.CDI_SPREAD):
            alerts.append("estimativa depende do cenário de CDI")
    elif candidate is not None and candidate.rate is not None and candidate.indexer is idx:
        market_rate = Sourced(candidate.rate.value, SRC_RUNFLOW_RATE, Kind.APROXIMACAO,
                              "aproximação: taxa de venda da mesa, a recompra tende a ser pior")
        alerts.append(market_rate.note)
    else:
        alerts.append("sem taxa de mercado: sem recomendação")

    duration: Sourced | None = None
    if ov.duration is not None:
        duration = Sourced(ov.duration, SRC_OVERRIDE)
    elif candidate is not None and candidate.duration is not None:
        duration = Sourced(candidate.duration, SRC_RUNFLOW_DURATION)
    elif calc_dur is not None:
        duration = Sourced(calc_dur, SRC_DURATION_CALC, Kind.ESTIMATIVA, flow_desc)
    elif pos.maturity is not None:
        dur = business_days(valuation, pos.maturity) / 252.0
        duration = Sourced(dur, "prazo até o vencimento", Kind.APROXIMACAO,
                           "sem fluxo: duration = prazo (superestima se houver cupom)")

    dmod = None
    if duration is not None and market_rate is not None and idx is not None:
        dmod = duration.value / (1 + discount_rate(idx, market_rate.value, scenario))

    rating = candidate.rating if candidate else Rating("", None, None)
    if not rating.has_rating:
        alerts.append("sem rating" + ("" if candidate else " (papel fora do Runflow)"))
    issuer = candidate.issuer if candidate and candidate.issuer else first.issuer
    return EnrichedPosition(
        position=pos, candidate=candidate, in_scope=in_scope, scope_note=note, indexer=idx,
        market_rate=market_rate, duration=duration, dmod=dmod, flow=flow_desc,
        lot_rates=[v for v, _ in lot_rates], rating=rating,
        sector=candidate.sector if candidate else "", issuer_key=issuer_key(issuer),
        tax_exempt=_tax_exempt(pos, candidate, policy), alerts=alerts,
    )


def enrich(mapa: MapaPositions, scenario: Scenario, candidates: list[Candidate] | None = None,
           overrides: dict[str, Override] | None = None, *,
           include_without_market_price: bool = False,
           policy: TaxPolicy = DEFAULT_POLICY) -> list[EnrichedPosition]:
    if mapa.position_date is None:
        raise ValueError("Mapa sem data da posição")
    by_code = {c.code: c for c in (candidates or [])}
    ov = overrides or {}
    return [enrich_position(p, mapa.position_date, scenario, by_code.get(p.code), ov.get(p.code),
                            include_without_market_price=include_without_market_price,
                            policy=policy)
            for p in mapa.positions()]
