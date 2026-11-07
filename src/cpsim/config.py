"""Configuração dos nomes das colunas INTERNAS do Runflow.

Os nomes reais (que citam instituições e campos de receita da mesa) ficam só em
`config/runflow_columns.local.toml`, fora do git. O repositório traz
`config/runflow_columns.example.toml`, com nomes genéricos, que as amostras fictícias usam.

Ordem de busca: caminho explícito → arquivo local → exemplo.
No navegador (stlite) só o exemplo é publicado; o arquivo local entra por upload (Fase 3).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .normalize import norm_header

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
LOCAL = CONFIG_DIR / "runflow_columns.local.toml"
EXAMPLE = CONFIG_DIR / "runflow_columns.example.toml"

# Campos internos conhecidos (nomes neutros; o cabeçalho real vem da config).
INTERNAL_FIELD_NAMES = ("fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b")


@dataclass(frozen=True)
class InternalColumns:
    """cabeçalho normalizado -> campo interno, e campo -> rótulo de tela."""

    by_header: dict[str, str]
    labels: dict[str, str]
    source: str  # "local", "exemplo" ou caminho/descrição
    headers: dict[str, str] = field(default_factory=dict)  # campo -> cabeçalho original

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(self.labels)


def parse_internal_columns(text: str, source: str = "texto") -> InternalColumns:
    data = tomllib.loads(text)
    cols = data.get("colunas_internas", {})
    by_header: dict[str, str] = {}
    labels: dict[str, str] = {}
    headers: dict[str, str] = {}
    for campo, spec in cols.items():
        if isinstance(spec, str):
            cab, rot = spec, campo
        else:
            cab, rot = spec["cabecalho"], spec.get("rotulo", campo)
        by_header[norm_header(cab)] = campo
        labels[campo] = rot
        headers[campo] = cab
    return InternalColumns(by_header, labels, source, headers)


def load_internal_columns(path: str | Path | None = None) -> InternalColumns:
    if path is not None:
        p = Path(path)
        return parse_internal_columns(p.read_text(encoding="utf-8"), str(p))
    if LOCAL.is_file():
        return parse_internal_columns(LOCAL.read_text(encoding="utf-8"), "local")
    return parse_internal_columns(EXAMPLE.read_text(encoding="utf-8"), "exemplo")
