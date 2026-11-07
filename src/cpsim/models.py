"""Modelo de dados do simulador (dataclasses puras, sem I/O).

Convenções: taxas em DECIMAL (0.0705 = 7,05%). Em %CDI, `value` é a fração do CDI
(1.045 = 104,50% do CDI). Datas como `datetime.date`.

Privacidade (regra 10): nenhum modelo tem campo para nome do cliente, agência ou conta.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from .normalize import strip_accents


# ----------------------------------------------------------------------------- procedência
class Kind(StrEnum):
    """Natureza de um número: separa o que é lido do que é estimado ou aproximado."""

    DADO = "dado"  # lido de arquivo ou fonte pública
    ESTIMATIVA = "estimativa"  # calculado por modelo a partir de dados (ex.: taxa implícita)
    APROXIMACAO = "aproximação"  # premissa simplificadora (ex.: fluxo aproximado, taxa de varejo)


@dataclass(frozen=True)
class Sourced:
    """Valor com fonte e natureza, para exibir "de onde veio" cada número."""

    value: Any
    source: str
    kind: Kind = Kind.DADO
    note: str = ""


# ----------------------------------------------------------------------------- indexador
class Indexer(StrEnum):
    PRE = "PRE"
    IPCA = "IPCA"
    CDI_PCT = "%CDI"
    CDI_SPREAD = "CDI+"


_INDEXER_ALIASES = {
    "pre": Indexer.PRE, "pré": Indexer.PRE, "prefixado": Indexer.PRE,
    "ipca": Indexer.IPCA, "ipca+": Indexer.IPCA,
    "%cdi": Indexer.CDI_PCT, "% cdi": Indexer.CDI_PCT, "cdi%": Indexer.CDI_PCT,
    "+cdi": Indexer.CDI_SPREAD, "cdi+": Indexer.CDI_SPREAD, "cdi +": Indexer.CDI_SPREAD,
    "di+": Indexer.CDI_SPREAD, "+di": Indexer.CDI_SPREAD,
}


def parse_indexer(text: object) -> Indexer | None:
    if text is None:
        return None
    t = " ".join(str(text).strip().lower().split())
    return _INDEXER_ALIASES.get(t) or _INDEXER_ALIASES.get(strip_accents(t))


@dataclass(frozen=True)
class Rate:
    indexer: Indexer
    value: float

    def __str__(self) -> str:
        v = f"{self.value * 100:.2f}".replace(".", ",")
        return {
            Indexer.PRE: f"{v}% a.a.",
            Indexer.IPCA: f"IPCA + {v}%",
            Indexer.CDI_PCT: f"{v}% do CDI",
            Indexer.CDI_SPREAD: f"CDI + {v}%",
        }[self.indexer]


# ----------------------------------------------------------------------------- rating
# Escala ordinal: maior = melhor. AAA = 21 ... D = 0. Agências nacionais e Moody's.
_SCALE = ["D", "C", "CC", "CCC-", "CCC", "CCC+", "B-", "B", "B+", "BB-", "BB", "BB+",
          "BBB-", "BBB", "BBB+", "A-", "A", "A+", "AA-", "AA", "AA+", "AAA"]
NOTCH = {lbl: i for i, lbl in enumerate(_SCALE)}
_MOODYS = {"AAA": "AAA", "AA1": "AA+", "AA2": "AA", "AA3": "AA-", "A1": "A+", "A2": "A",
           "A3": "A-", "BAA1": "BBB+", "BAA2": "BBB", "BAA3": "BBB-", "BA1": "BB+", "BA2": "BB",
           "BA3": "BB-", "B1": "B+", "B2": "B", "B3": "B-", "CAA1": "CCC+", "CAA2": "CCC",
           "CAA3": "CCC-", "CA": "CC"}


@dataclass(frozen=True)
class Rating:
    raw: str
    label: str | None  # forma canônica ("AA+") ou None se sem rating
    notch: int | None  # ordinal; None = sem rating

    @property
    def has_rating(self) -> bool:
        return self.notch is not None


def parse_rating(text: object) -> Rating:
    """Normaliza grafias: AAA, brAAA, AAAbr, AAA(bra), AA+.br, Aa1.br ... '0', '-', vazio = sem."""
    raw = "" if text is None else str(text).strip()
    if raw in {"", "0", "-", "—", "NR", "nr", "n/a", "N/A", "SR", "sem rating"}:
        return Rating(raw, None, None)
    t = raw.upper().replace(" ", "")
    t = re.sub(r"\((BRA|BR|EXP|SF|P)\)", "", t)  # AAA(bra), AA(exp)
    t = re.sub(r"\.(BR|SF)\b", "", t)  # AA+.br
    t = re.sub(r"SF$", "", t)  # AAAsf
    t = re.sub(r"^BR(?=[ABCD])", "", t)  # brAAA
    t = re.sub(r"BR$", "", t)  # AAAbr
    t = t.strip(".")
    if t in _MOODYS:
        t = _MOODYS[t]
    if t in NOTCH:
        return Rating(raw, t, NOTCH[t])
    return Rating(raw, None, None)


# ----------------------------------------------------------------------------- Mapa
@dataclass
class Lot:
    """Uma linha do Mapa de Posições (um lote de compra)."""

    page: int
    code: str | None
    asset_type: str | None  # DEB, CRI, CRA, CDB, CPR...
    title: str
    issuer: str
    emission: dt.date | None
    maturity: dt.date | None
    purchase_date: dt.date | None
    rate: Rate | None  # Taxa Operação (taxa de aquisição do lote)
    rate_text: str
    title_rate: Rate | None  # taxa que aparece no Título (em geral a de emissão)
    quantity: int | None
    pu_purchase: float | None
    pu_curve: float | None
    gross_curve: float | None
    pu_market: float | None
    gross_market: float | None
    ir: float | None
    iof: float | None
    net_value: float | None
    income: float | None
    errors: list[str] = field(default_factory=list)  # bloqueiam a análise (tabela editável)
    warnings: list[str] = field(default_factory=list)  # só informativos

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def has_market_price(self) -> bool:
        return self.pu_market is not None


@dataclass
class Position:
    """Lotes do mesmo código agregados (os lotes ficam para IR/IOF por lote)."""

    code: str
    lots: list[Lot]

    @property
    def first(self) -> Lot:
        return self.lots[0]

    @property
    def asset_type(self) -> str | None:
        return self.first.asset_type

    @property
    def issuer(self) -> str:
        return self.first.issuer

    @property
    def maturity(self) -> dt.date | None:
        return self.first.maturity

    @property
    def indexer(self) -> Indexer | None:
        r = self.first.rate or self.first.title_rate
        return r.indexer if r else None

    @property
    def has_market_price(self) -> bool:
        return all(lot.has_market_price for lot in self.lots)

    def _sum(self, attr: str) -> float | None:
        vals = [getattr(lot, attr) for lot in self.lots]
        return None if any(v is None for v in vals) else sum(vals)

    @property
    def quantity(self) -> int | None:
        q = self._sum("quantity")
        return None if q is None else int(q)

    @property
    def gross_market(self) -> float | None:
        return self._sum("gross_market")

    @property
    def gross_curve(self) -> float | None:
        return self._sum("gross_curve")

    @property
    def net_value(self) -> float | None:
        return self._sum("net_value")

    @property
    def ir(self) -> float | None:
        return self._sum("ir")

    @property
    def iof(self) -> float | None:
        return self._sum("iof")

    @property
    def purchase_rate_avg(self) -> float | None:
        """Taxa de aquisição média ponderada pela quantidade (só informativa: não decide nada)."""
        pairs = [(lot.rate.value, lot.quantity) for lot in self.lots if lot.rate and lot.quantity]
        tot = sum(q for _, q in pairs)
        return sum(v * q for v, q in pairs) / tot if tot else None


@dataclass
class MapaPositions:
    position_date: dt.date | None
    lots: list[Lot]
    n_pages: int
    warnings: list[str] = field(default_factory=list)
    n_fragments: int = 0

    @property
    def invalid_lots(self) -> list[Lot]:
        return [lot for lot in self.lots if not lot.valid]

    def positions(self) -> list[Position]:
        """Agrega por código, na ordem da primeira aparição. Lotes sem código ficam de fora."""
        by: dict[str, list[Lot]] = {}
        for lot in self.lots:
            if lot.code:
                by.setdefault(lot.code, []).append(lot)
        return [Position(code, lots) for code, lots in by.items()]


# ----------------------------------------------------------------------------- Runflow
@dataclass
class Candidate:
    """Uma linha do Runflow (papel disponível para compra)."""

    code: str
    issuer: str
    product: str | None  # DEB, CRI, CRA, CPR
    rate: Rate | None  # Taxa de Compra
    active: bool  # Distribuição = Ativa
    distribution: str
    lastro: float | None  # Lastro Disponível (R$)
    qty_available: int | None
    maturity: dt.date | None
    duration: float | None  # anos
    ntnb_ref_year: int | None  # "B35" -> 2035
    emission_rate: float | None  # Taxa de Emissão (decimal)
    coupon: str
    amortization: str
    sector: str
    rating: Rating
    agency: str
    qualified_only: bool | None  # Investidor Qualificado? = Qualificado
    tax_exempt: bool | None  # Isento? = Sim
    guarantee: str
    internal: dict[str, Any] = field(default_factory=dict)  # só modo interno (regra 6)
    warnings: list[str] = field(default_factory=list)

    @property
    def indexer(self) -> Indexer | None:
        return self.rate.indexer if self.rate else None


@dataclass
class RunflowData:
    candidates: list[Candidate]
    missing: list[str]  # colunas esperadas não encontradas
    extra: list[str]  # colunas da planilha que não são reconhecidas
    internal_labels: dict[str, str]  # campo interno -> rótulo de tela
    columns_source: str  # "local" ou "exemplo"
    warnings: list[str] = field(default_factory=list)

    def by_code(self) -> dict[str, Candidate]:
        return {c.code: c for c in self.candidates}


Mode = Literal["interno", "cliente"]
