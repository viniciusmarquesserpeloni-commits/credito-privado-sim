"""Calendário de dias úteis (feriados nacionais por regra) e contagem base 252.

Feriados: fixos (1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 25/12), 20/11 (Consciência Negra,
nacional desde 2024 — Lei 14.759/2023), Carnaval (segunda e terça), Sexta-feira Santa e
Corpus Christi (móveis, a partir da Páscoa). É a regra usada pelo mercado (ANBIMA).

Contagem de dias úteis: `business_days(d0, d1)` conta os dias úteis em [d0, d1) — o número
de dias úteis "corridos" entre as duas datas, como em du/252 (metodologia 4.1).
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

import numpy as np

FIXED = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)]
_MIN_YEAR, _MAX_YEAR = 1990, 2100


def easter(year: int) -> dt.date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


@lru_cache(maxsize=None)
def holidays(year: int) -> frozenset[dt.date]:
    out = {dt.date(year, m, d) for m, d in FIXED}
    if year >= 2024:
        out.add(dt.date(year, 11, 20))
    p = easter(year)
    out |= {
        p - dt.timedelta(days=48),  # segunda de Carnaval
        p - dt.timedelta(days=47),  # terça de Carnaval
        p - dt.timedelta(days=2),  # Sexta-feira Santa
        p + dt.timedelta(days=60),  # Corpus Christi
    }
    return frozenset(out)


@lru_cache(maxsize=1)
def _np_holidays() -> np.ndarray:
    days = sorted(d for y in range(_MIN_YEAR, _MAX_YEAR + 1) for d in holidays(y))
    return np.array(days, dtype="datetime64[D]")


def _check(d: dt.date) -> None:
    if not (_MIN_YEAR <= d.year <= _MAX_YEAR):
        raise ValueError(f"data fora do calendário suportado ({_MIN_YEAR}–{_MAX_YEAR}): {d}")


def is_business_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def business_days(d0: dt.date, d1: dt.date) -> int:
    """Dias úteis em [d0, d1). Negativo se d1 < d0."""
    _check(d0)
    _check(d1)
    return int(np.busday_count(np.datetime64(d0, "D"), np.datetime64(d1, "D"),
                               holidays=_np_holidays()))


def business_days_many(d0: dt.date, ds: list[dt.date]) -> list[int]:
    """Versão vetorizada de `business_days(d0, d)` para várias datas."""
    if not ds:
        return []
    _check(d0)
    for d in ds:
        _check(d)
    ends = np.array(ds, dtype="datetime64[D]")
    return np.busday_count(np.datetime64(d0, "D"), ends, holidays=_np_holidays()).tolist()


def year_fraction(d0: dt.date, d1: dt.date) -> float:
    """du/252."""
    return business_days(d0, d1) / 252.0


def following(d: dt.date) -> dt.date:
    """Próximo dia útil (o próprio dia, se útil)."""
    while not is_business_day(d):
        d += dt.timedelta(days=1)
    return d


def add_business_days(d: dt.date, n: int) -> dt.date:
    _check(d)
    r = np.busday_offset(np.datetime64(d, "D"), n, roll="forward", holidays=_np_holidays())
    return r.astype(dt.date)
