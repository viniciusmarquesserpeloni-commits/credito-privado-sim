"""Curvas e projeções a partir dos dados PÚBLICOS (data/public/*.json).

- CDI esperado no horizonte: CDI atual (SGS 12) e trajetória da Selic pela mediana do Focus por
  reunião, com o CDI = Selic − (diferença atual entre meta e CDI). As datas das reuniões são
  APROXIMADAS (mês típico do calendário do Copom), porque o Focus só informa "R6/2028".
- IPCA esperado: Focus 12 meses para o 1º ano, medianas anuais depois.
- NTN-B: Tesouro Direto (Tesouro IPCA+ com Juros Semestrais) — TAXA DE VAREJO, média de compra e
  venda; duration calculada com cupom de 6% a.a. em semestres (aproximação).

Tudo aqui depende de premissas: quem exibe deve mostrar a fonte e a data (metodologia 7,
"Regra de exibição").
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .calendar import business_days, following
from .cashflows import build_schedule
from .models import Kind, Sourced
from .pricing import macaulay_duration
from .rates import cdi_sgs_to_annual, compound
from .spreads import NtnbQuote

PUBLIC_DIR = Path(__file__).resolve().parents[2] / "data" / "public"
FILES = ("cdi.json", "selic_meta.json", "ipca_mensal.json", "focus_selic.json",
         "focus_ipca.json", "tesouro_direto.json")

# Mês e dia típicos das 8 reuniões do Copom (aproximação para datar "R1".."R8").
COPOM_MES_DIA = {1: (1, 28), 2: (3, 18), 3: (5, 6), 4: (6, 17), 5: (7, 29), 6: (9, 16),
                 7: (11, 4), 8: (12, 9)}
NTNB_TITULO = "Tesouro IPCA+ com Juros Semestrais"
NTNB_CUPOM = 0.06


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


@dataclass
class PublicData:
    cdi_daily: list[tuple[dt.date, float]]  # % a.d. (como no SGS)
    selic_meta: list[tuple[dt.date, float]]  # % a.a.
    focus_selic: list[tuple[str, float]]  # ("R7/2026", mediana % a.a.)
    focus_selic_date: dt.date | None
    focus_ipca_annual: dict[int, float]  # ano -> mediana %
    focus_ipca_12m: float | None  # %
    focus_ipca_date: dt.date | None
    tesouro: list[dict]
    collected_at: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_payloads(payloads: dict[str, dict]) -> PublicData:
        def series(name):
            p = payloads.get(name)
            return [(_d(r["data"]), float(r["valor"])) for r in p["dados"]] if p else []

        fs = payloads.get("focus_selic", {}).get("dados", {})
        fi = payloads.get("focus_ipca", {}).get("dados", {})
        return PublicData(
            cdi_daily=series("cdi"),
            selic_meta=series("selic_meta"),
            focus_selic=[(r["reuniao"], float(r["mediana"])) for r in fs.get("reunioes", [])],
            focus_selic_date=_d(fs["data_referencia"]) if fs.get("data_referencia") else None,
            focus_ipca_annual={int(r["ano"]): float(r["mediana"]) for r in fi.get("anual", [])},
            focus_ipca_12m=(float(fi["doze_meses"]["mediana"]) if fi.get("doze_meses") else None),
            focus_ipca_date=_d(fi["data_referencia"]) if fi.get("data_referencia") else None,
            tesouro=payloads.get("tesouro_direto", {}).get("dados", []),
            collected_at={k: v.get("coletado_em", "") for k, v in payloads.items()},
        )


def load_public(directory: str | Path = PUBLIC_DIR) -> PublicData:
    d = Path(directory)
    payloads = {}
    for f in FILES:
        p = d / f
        if p.is_file():
            payloads[f.removesuffix(".json")] = json.loads(p.read_text(encoding="utf-8"))
    return PublicData.from_payloads(payloads)


# ----------------------------------------------------------------------------- atualidade
MAX_IDADE_DIAS_UTEIS = 3


@dataclass(frozen=True)
class Freshness:
    name: str
    collected: dt.date | None
    age_business_days: int | None
    stale: bool


def freshness(pd: PublicData, today: dt.date,
              max_business_days: int = MAX_IDADE_DIAS_UTEIS) -> list[Freshness]:
    """Idade de cada arquivo público em dias úteis desde a coleta. Acima do limite -> vencido
    (o app alerta). Arquivo sem data de coleta conta como vencido."""
    out = []
    for name in (f.removesuffix(".json") for f in FILES):
        raw = pd.collected_at.get(name, "")
        d = _d(raw) if raw else None
        age = business_days(d, today) if d else None
        out.append(Freshness(name, d, age, age is None or age > max_business_days))
    return out


def oldest_collection(pd: PublicData) -> dt.date | None:
    ds = [_d(v) for v in pd.collected_at.values() if v]
    return min(ds) if ds else None


# ----------------------------------------------------------------------------- CDI
def copom_date(label: str) -> dt.date:
    """'R6/2028' -> data APROXIMADA da reunião (ver COPOM_MES_DIA)."""
    num, ano = label.strip().upper().lstrip("R").split("/")
    m, d = COPOM_MES_DIA[int(num)]
    return dt.date(int(ano), m, d)


def current_cdi(pd: PublicData) -> tuple[float, dt.date]:
    if not pd.cdi_daily:
        raise ValueError("sem série de CDI")
    d, v = pd.cdi_daily[-1]
    return cdi_sgs_to_annual(v), d


def cdi_path(pd: PublicData, as_of: dt.date) -> list[tuple[dt.date, float]]:
    """Trechos (início, CDI anual) a partir de `as_of`."""
    cdi0, _ = current_cdi(pd)
    gap = (pd.selic_meta[-1][1] / 100.0 - cdi0) if pd.selic_meta else 0.001
    path = [(as_of, cdi0)]
    for label, selic in pd.focus_selic:
        d = copom_date(label) + dt.timedelta(days=1)  # nova meta vale do dia seguinte
        if d > as_of:
            path.append((d, selic / 100.0 - gap))
    return path


def expected_cdi(pd: PublicData, as_of: dt.date, horizon_years: float) -> Sourced:
    """CDI médio anual (composto) entre `as_of` e `as_of + h`. Estimativa (Focus)."""
    end = as_of + dt.timedelta(days=round(365.25 * horizon_years))
    path = cdi_path(pd, as_of)
    fator, du_tot = 1.0, 0
    for i, (ini, cdi) in enumerate(path):
        fim = path[i + 1][0] if i + 1 < len(path) else end
        fim = min(fim, end)
        if fim <= ini:
            continue
        du = business_days(following(ini), following(fim))
        fator *= compound(cdi, du)
        du_tot += du
    media = fator ** (252 / du_tot) - 1 if du_tot else path[0][1]
    return Sourced(media, f"BCB SGS 12 + Focus Selic de {pd.focus_selic_date}", Kind.ESTIMATIVA,
                   "datas das reuniões do Copom aproximadas; CDI = Selic − diferença atual")


def expected_ipca(pd: PublicData, as_of: dt.date, horizon_years: float) -> Sourced:
    """IPCA médio anual no horizonte: 12 meses (Focus) no 1º ano, medianas anuais depois."""
    if pd.focus_ipca_12m is None and not pd.focus_ipca_annual:
        raise ValueError("sem expectativa de IPCA")
    first = (pd.focus_ipca_12m if pd.focus_ipca_12m is not None
             else pd.focus_ipca_annual[min(pd.focus_ipca_annual)]) / 100.0
    fator, anos = 1.0, 0.0
    h = horizon_years
    take = min(1.0, h)
    fator *= (1 + first) ** take
    anos += take
    y = as_of.year + 1
    last = first
    while anos < h - 1e-9:
        v = pd.focus_ipca_annual.get(y)
        last = v / 100.0 if v is not None else last
        take = min(1.0, h - anos)
        fator *= (1 + last) ** take
        anos += take
        y += 1
    return Sourced(fator ** (1 / anos) - 1, f"Focus IPCA de {pd.focus_ipca_date}",
                   Kind.ESTIMATIVA, "12 meses no 1º ano; medianas anuais depois")


# ----------------------------------------------------------------------------- NTN-B
def ntnb_quotes(pd: PublicData) -> tuple[list[NtnbQuote], dt.date | None]:
    """NTN-Bs da data-base mais recente do Tesouro Direto (taxa de varejo, média compra/venda),
    com duration de Macaulay calculada (cupom 6% a.a., pagamentos semestrais)."""
    rows = [r for r in pd.tesouro if r.get("titulo") == NTNB_TITULO]
    if not rows:
        return [], None
    base = max(r["data_base"] for r in rows)
    out = []
    as_of = _d(base)
    for r in rows:
        if r["data_base"] != base:
            continue
        taxas = [t for t in (r.get("taxa_compra"), r.get("taxa_venda")) if t is not None]
        if not taxas:
            continue
        rate = sum(taxas) / len(taxas) / 100.0
        mat = _d(r["vencimento"])
        months = "Mai/Nov" if mat.month == 5 else "Fev/Ago"
        sch = build_schedule(as_of, mat, months, "Bullet", NTNB_CUPOM)
        dur = macaulay_duration(sch.as_pricing_flows(), rate) if sch.ok else None
        out.append(NtnbQuote(mat, rate, dur))
    out.sort(key=lambda q: q.maturity)
    return out, as_of
