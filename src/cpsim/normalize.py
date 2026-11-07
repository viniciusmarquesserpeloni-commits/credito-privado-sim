"""Normalização de textos e números nos formatos dos arquivos de entrada, e formatação pt-BR."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

_SPACES = re.compile(r"\s+")
# O PDF real insere espaços de kerning dentro de números: "99 . 999,99", "9 .99%", "999, 99".
_NUM_GAPS = re.compile(r"(?<=[\d.,])\s+(?=[\d.,%])|(?<=\d)\s+(?=[.,])")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_header(s: object) -> str:
    """Normaliza um cabeçalho: sem acento, minúsculo, espaços simples, sem bordas.

    >>> norm_header("  Taxa de  Compra ")
    'taxa de compra'
    >>> norm_header("Δ A")
    'δ a'
    """
    if s is None:
        return ""
    return _SPACES.sub(" ", strip_accents(str(s))).strip().lower()


def squash_number_gaps(s: str) -> str:
    """'99 . 999,99' -> '99.999,99'; '9 .99%' -> '9.99%'; 'R$ 1.021,25' fica igual."""
    prev = None
    while prev != s:
        prev, s = s, _NUM_GAPS.sub("", s)
    return s


def parse_brl(s: str | None) -> float | None:
    """'R$ 1.021,25' -> 1021.25 ; '-' ou vazio -> None."""
    if s is None:
        return None
    t = str(s).strip()
    if t in {"", "-", "—"}:
        return None
    t = t.replace("R$", "").replace("\xa0", "").replace(" ", "")
    if t in {"", "-", "—"}:
        return None
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("-()")
    t = t.replace(".", "").replace(",", ".")
    v = float(t)
    return -v if neg else v


def parse_number(v: object) -> float | None:
    """Número de célula Excel: float/int, ou texto pt-BR ("3,88", "1.234,5", "R$ 1.000")."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace("R$", "").replace("\xa0", "").replace(" ", "")
    if t in {"", "-", "—"}:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def parse_percent(v: object) -> tuple[float | None, bool]:
    """Percentual -> (valor, veio_como_texto_com_%).

    7,05% / "7.05%" -> 7.05 (escala %), True ; 0.0705 (célula numérica) -> 0.0705, False.
    Quem chama decide a escala de números sem '%' (ver runflow_xlsx._rate_scale).
    """
    if v is None or isinstance(v, bool):
        return None, False
    if isinstance(v, (int, float)):
        return float(v), False
    t = squash_number_gaps(str(v).strip())
    has_pct = "%" in t
    t = t.replace("%", "").strip()
    if t.count(",") == 1 and t.count(".") >= 1:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return float(t), has_pct
    except ValueError:
        return None, has_pct


def parse_date_br(s: object) -> dt.date | None:
    """'dd/mm/aaaa' (ou date/datetime) -> date. Tolera espaços espúrios ("15/05/ 2032")."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s.date()
    if isinstance(s, dt.date):
        return s
    t = str(s).replace(" ", "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


# ----------------------------------------------------------------------------- exibição
def fmt_pct(x: float | None, casas: int = 2) -> str:
    """0.1437 -> '14,37%'."""
    if x is None:
        return "—"
    return f"{x * 100:,.{casas}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_bps(x: float | None, casas: int = 0) -> str:
    """0.0056 -> '56 bps'."""
    if x is None:
        return "—"
    return f"{x * 10_000:,.{casas}f} bps".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_brl(x: float | None) -> str:
    if x is None:
        return "—"
    s = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if x < 0 else "R$ ") + s
