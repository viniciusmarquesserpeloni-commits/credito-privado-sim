"""Fluxo de pagamentos APROXIMADO a partir dos textos de Cupom e Amortização do Runflow.

Exemplos aceitos (prompt 5.1):
  Cupom:       "Mai/Nov", "Mensal", "Jan/Abr/Jul/Out", "Semestral", "Trimestral", "Anual", "Bullet"
  Amortização: "Bullet", "Anual (Início 2037)", "Mar/Set (Início 2034)",
               "Semestral (Início Set 26)", "Mensal", "Mensal (Início 2027)"

Premissas (todas aproximações, por isso `Schedule.approximate = True`):
- dia de pagamento = dia do vencimento (limitado ao fim do mês), ajustado ao dia útil seguinte;
- o saldo ATUAL (= 1) é amortizado em parcelas iguais nas datas restantes a partir do início
  indicado ("amortizações iguais a partir do início"); parcelas já passadas são ignoradas;
- juros compostos base 252 sobre o saldo de cada trecho; o 1º cupom inclui os juros desde a
  data de cupom anterior (fluxo "sujo", como o PU);
- cupom "Bullet": juros só no vencimento, contados a partir da data de avaliação.
Texto não reconhecido -> fluxo vazio e alerta (o papel fica sem fluxo).
"""

from __future__ import annotations

import calendar as _cal
import datetime as dt
import re
from dataclasses import dataclass, field

from .calendar import business_days, following
from .normalize import strip_accents

MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8,
          "set": 9, "out": 10, "nov": 11, "dez": 12}
_STEP = {"mensal": 1, "bimestral": 2, "trimestral": 3, "quadrimestral": 4, "semestral": 6,
         "anual": 12}


@dataclass(frozen=True)
class CashFlow:
    date: dt.date  # data contratual
    pay_date: dt.date  # ajustada ao dia útil
    du: int  # dias úteis desde a avaliação
    interest: float
    amortization: float

    @property
    def t(self) -> float:
        return self.du / 252.0

    @property
    def total(self) -> float:
        return self.interest + self.amortization


@dataclass
class Schedule:
    flows: list[CashFlow]
    approximate: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.flows)

    def as_pricing_flows(self) -> list[tuple[float, float]]:
        return [(f.t, f.total) for f in self.flows]


# ----------------------------------------------------------------------------- textos
def _norm(text: str) -> str:
    return " ".join(strip_accents(text or "").lower().split())


def _months_from_step(step: int, anchor_month: int) -> list[int]:
    return sorted({((anchor_month - 1 + k * step) % 12) + 1 for k in range(12 // step)})


def parse_months(text: str, maturity: dt.date) -> list[int] | None:
    """Meses de pagamento. [] = só no vencimento (bullet). None = não reconhecido."""
    t = _norm(re.sub(r"\(.*?\)", "", text or ""))
    if t in {"bullet", "no vencimento", "vencimento", "final"}:
        return []
    if t in _STEP:
        return _months_from_step(_STEP[t], maturity.month)
    parts = [p.strip()[:3] for p in re.split(r"\s*(?:[/,;-]|\be\b)\s*", t) if p.strip()]
    if parts and all(p in MONTHS for p in parts):
        return sorted({MONTHS[p] for p in parts})
    return None


def parse_amortization(text: str, maturity: dt.date) -> tuple[list[int], dt.date | None] | None:
    """(meses, início) da amortização. ([], None) = bullet. None = não reconhecido.
    "Anual (Início 2037)" -> mês do vencimento a partir de 2037;
    "Semestral (Início Set 26)" -> set e mar a partir de set/2026."""
    raw = text or ""
    months = parse_months(raw, maturity)
    if months is None:
        return None
    if months == []:
        return [], None
    start = None
    m = re.search(r"\(\s*in[ií]cio\s+([^)]*)\)", strip_accents(raw), re.I)
    if m:
        s = _norm(m.group(1))
        m_my = re.fullmatch(r"([a-z]{3})[a-z]*\s*/?\s*(\d{2}|\d{4})", s)
        m_y = re.fullmatch(r"(\d{4})", s)
        if m_my and m_my.group(1) in MONTHS:
            y = int(m_my.group(2))
            y = y if y > 1000 else 2000 + y
            start = dt.date(y, MONTHS[m_my.group(1)], 1)
            step = _STEP.get(_norm(re.sub(r"\(.*?\)", "", raw)))
            if step:  # frequência ancorada no mês de início, não no do vencimento
                months = _months_from_step(step, start.month)
        elif m_y:
            start = dt.date(int(m_y.group(1)), 1, 1)
        else:
            return None
    return months, start


# ----------------------------------------------------------------------------- datas
def _on_day(year: int, month: int, day: int) -> dt.date:
    return dt.date(year, month, min(day, _cal.monthrange(year, month)[1]))


def _dates_in_months(months: list[int], day: int, after: dt.date, until: dt.date,
                     start: dt.date | None = None) -> list[dt.date]:
    out = []
    for y in range(after.year, until.year + 1):
        for mth in months:
            d = _on_day(y, mth, day)
            if after < d <= until and (start is None or d >= start):
                out.append(d)
    return out


def _previous_coupon(months: list[int], day: int, valuation: dt.date) -> dt.date:
    cands = [_on_day(y, mth, day) for y in (valuation.year - 1, valuation.year) for mth in months]
    past = [d for d in cands if d <= valuation]
    return max(past) if past else valuation


# ----------------------------------------------------------------------------- fluxo
def build_schedule(valuation: dt.date, maturity: dt.date, coupon_text: str, amort_text: str,
                   coupon_rate: float) -> Schedule:
    """Fluxo por unidade de saldo atual (saldo = 1 na avaliação).

    `coupon_rate`: taxa anual do cupom — taxa de emissão (Pré), juro real (IPCA, fluxo REAL
    sobre o VNA) ou taxa nominal esperada (%CDI/CDI+, fluxo projetado com o CDI do cenário)."""
    w: list[str] = []
    if maturity <= valuation:
        return Schedule([], warnings=["papel vencido na data de avaliação"])
    cm = parse_months(coupon_text, maturity)
    am = parse_amortization(amort_text, maturity)
    if cm is None:
        w.append(f"cupom não reconhecido: {coupon_text!r}")
    if am is None:
        w.append(f"amortização não reconhecida: {amort_text!r}")
    if cm is None or am is None:
        return Schedule([], warnings=w)
    day = maturity.day
    coupon_dates = set(_dates_in_months(cm, day, valuation, maturity)) | {maturity}
    a_months, a_start = am
    amort_dates = set(_dates_in_months(a_months, day, valuation, maturity, a_start)) | {maturity}
    events = sorted(coupon_dates | amort_dates)
    n_amort = len(amort_dates)
    parcel = 1.0 / n_amort

    if cm:
        accr_start = _previous_coupon(cm, day, valuation)
    else:
        accr_start = valuation
        w.append("cupom bullet: juros contados a partir da data de avaliação")
    outstanding, accrued = 1.0, 0.0
    prev = accr_start
    flows: list[CashFlow] = []
    for d in events:
        pay = following(d)
        seg_du = business_days(following(prev) if prev < valuation else prev, pay)
        accrued += outstanding * ((1.0 + coupon_rate) ** (max(seg_du, 0) / 252.0) - 1.0)
        interest = 0.0
        if d in coupon_dates:
            interest, accrued = accrued, 0.0
        amort = parcel if d in amort_dates else 0.0
        if d == maturity:
            amort = outstanding  # fecha o saldo (evita resíduo de arredondamento)
        flows.append(CashFlow(d, pay, business_days(valuation, pay), interest, amort))
        outstanding -= amort
        prev = pay
    return Schedule(flows, approximate=True, warnings=w)
