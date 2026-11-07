"""Leitor do Runflow (Excel da mesa) -> `RunflowData` com `Candidate`s tipados.

Aba `Consolidado`, cabeçalho na linha 10, dados a partir da 11. As colunas são localizadas pelo
NOME normalizado do cabeçalho (sem acento, minúsculo), nunca pela letra: colunas extras ou em
outra ordem não quebram a leitura.

Colunas internas (receita da mesa, comparativos com outras plataformas) têm os nomes reais só
em `config/runflow_columns.local.toml` (fora do git); ver `cpsim.config`. Elas vão para
`Candidate.internal`, que só o modo interno exibe e que nenhum cálculo usa (regras 6 e 7).
"""

from __future__ import annotations

import io
import re
from typing import Any

from ..config import InternalColumns, load_internal_columns
from ..models import Candidate, Indexer, Rate, RunflowData, parse_indexer, parse_rating
from ..normalize import norm_header, parse_date_br, parse_number, parse_percent, strip_accents

SHEET = "Consolidado"
HEADER_ROW = 10

# Colunas públicas: cabeçalho normalizado -> campo.
PUBLIC_COLUMNS = {
    "codigo": "codigo",
    "empresa": "empresa",
    "produto": "produto",
    "taxa de compra": "taxa_compra",
    "indexador": "indexador",
    "distribuicao": "distribuicao",
    "lastro disponivel": "lastro_disponivel",
    "qtds disponiveis": "qtd_disponivel",
    "vencimento": "vencimento",
    "duration": "duration",
    "b ref.": "b_ref",
    "taxa de emissao": "taxa_emissao",
    "cupom": "cupom",
    "amortizacao": "amortizacao",
    "setor de atuacao": "setor",
    "rating": "rating",
    "agencia": "agencia",
    "investidor qualificado?": "investidor_qualificado",
    "isento?": "isento",
    "garantia na emissao": "garantia",
}
REQUIRED = ("codigo", "taxa_compra", "indexador", "vencimento")

# Campos que só o modo interno pode exibir (além das colunas internas da config).
INTERNAL_PUBLIC_FIELDS = {"lastro_disponivel"}


def _rate_scale(value: float, had_pct: bool, indexer: Indexer) -> float:
    """Converte para decimal. Texto com '%' sempre /100. Número de célula:
    %CDI entre 0,3 e 3 já é fração (0,995); acima disso está em pontos (99,5).
    Demais indexadores: acima de 0,5 está em pontos (7,05) — spread de 50% a.a. não existe."""
    if had_pct:
        return value / 100.0
    if indexer is Indexer.CDI_PCT:
        return value if value <= 3 else value / 100.0
    return value if abs(value) <= 0.5 else value / 100.0


def _yes(v: object) -> bool | None:
    if v is None or str(v).strip() == "":
        return None
    t = strip_accents(str(v)).strip().lower()
    if t in {"sim", "s", "yes", "y", "true", "1", "isento"}:
        return True
    if t in {"nao", "n", "no", "false", "0", "tributado"}:
        return False
    return None


def _qualified(v: object) -> bool | None:
    if v is None:
        return None
    t = strip_accents(str(v)).strip().lower()
    if t.startswith("qualif") or t.startswith("profis") or t == "sim":
        return True
    if t in {"geral", "nao", "não", "publico geral", "varejo"}:
        return False
    return None


def _bref_year(v: object) -> int | None:
    if v is None:
        return None
    m = re.fullmatch(r"\s*(?:NTN-?B\s*)?B?\s*(\d{2}|\d{4})\s*", str(v), re.I)
    if not m:
        return None
    y = int(m.group(1))
    return y if y > 1000 else 2000 + y


def _text(v: object) -> str:
    return "" if v is None else str(v).strip()


def read_runflow(data: bytes, internal: InternalColumns | None = None) -> RunflowData:
    from openpyxl import load_workbook

    internal = internal or load_internal_columns()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    warnings: list[str] = []
    if SHEET in wb.sheetnames:
        ws = wb[SHEET]
    else:
        ws = wb[wb.sheetnames[0]]
        warnings.append(f"Aba '{SHEET}' não encontrada; usando a primeira aba.")

    it = ws.iter_rows(min_row=HEADER_ROW, values_only=True)
    header = next(it, None) or ()
    pub: dict[int, str] = {}
    intl: dict[int, str] = {}
    extra: list[str] = []
    for j, h in enumerate(header):
        key = norm_header(h)
        if not key:
            continue
        if key in PUBLIC_COLUMNS:
            pub[j] = PUBLIC_COLUMNS[key]
        elif key in internal.by_header:
            intl[j] = internal.by_header[key]
        else:
            extra.append(str(h))
    missing = [v for v in PUBLIC_COLUMNS.values() if v not in pub.values()]
    missing += [f"(interna) {internal.labels[f]}" for f in internal.fields
                if f not in intl.values()]
    if any(r in missing for r in REQUIRED):
        warnings.append("Colunas obrigatórias ausentes: "
                        + ", ".join(r for r in REQUIRED if r in missing))

    candidates: list[Candidate] = []
    for values in it:
        if values is None:
            continue
        rec: dict[str, Any] = {c: (values[j] if j < len(values) else None) for j, c in pub.items()}
        code = _text(rec.get("codigo"))
        if not code:
            continue
        candidates.append(_to_candidate(code, rec, {
            campo: (values[j] if j < len(values) else None) for j, campo in intl.items()
        }))
    wb.close()
    return RunflowData(candidates, missing, extra, dict(internal.labels), internal.source,
                       warnings)


def _to_candidate(code: str, rec: dict[str, Any], internal_values: dict[str, Any]) -> Candidate:
    w: list[str] = []
    idx = parse_indexer(rec.get("indexador"))
    rate = None
    if idx is None:
        w.append(f"indexador não reconhecido: {rec.get('indexador')!r}")
    else:
        val, had_pct = parse_percent(rec.get("taxa_compra"))
        if val is None:
            w.append(f"taxa de compra não reconhecida: {rec.get('taxa_compra')!r}")
        else:
            rate = Rate(idx, _rate_scale(val, had_pct, idx))
    em_val, em_pct = parse_percent(rec.get("taxa_emissao"))
    emission = None
    if em_val is not None and idx is not None:
        emission = _rate_scale(em_val, em_pct, idx)
    maturity = parse_date_br(rec.get("vencimento"))
    if maturity is None:
        w.append(f"vencimento inválido: {rec.get('vencimento')!r}")
    duration = parse_number(rec.get("duration"))
    if duration is None:
        w.append("sem duration")
    rating = parse_rating(rec.get("rating"))
    if not rating.has_rating:
        w.append("sem rating")
    qty = parse_number(rec.get("qtd_disponivel"))
    dist = _text(rec.get("distribuicao"))
    return Candidate(
        code=code,
        issuer=_text(rec.get("empresa")),
        product=_text(rec.get("produto")).upper() or None,
        rate=rate,
        active=strip_accents(dist).lower() == "ativa",
        distribution=dist,
        lastro=parse_number(rec.get("lastro_disponivel")),
        qty_available=None if qty is None else int(qty),
        maturity=maturity,
        duration=duration,
        ntnb_ref_year=_bref_year(rec.get("b_ref")),
        emission_rate=emission,
        coupon=_text(rec.get("cupom")),
        amortization=_text(rec.get("amortizacao")),
        sector=_text(rec.get("setor")),
        rating=rating,
        agency=_text(rec.get("agencia")),
        qualified_only=_qualified(rec.get("investidor_qualificado")),
        tax_exempt=_yes(rec.get("isento")),
        guarantee=_text(rec.get("garantia")),
        internal=internal_values,
        warnings=w,
    )
