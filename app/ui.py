"""Estado e utilidades compartilhadas pelas telas do app.

Tudo fica em `st.session_state` (memória da aba). Nada é gravado em disco, enviado a servidor
ou registrado em log (regra 1). Os widgets do Streamlit perdem o valor ao trocar de tela; por
isso cada parâmetro tem uma cópia persistente (`p_*`), e os arquivos ficam guardados como bytes.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

APP = Path(__file__).resolve().parent
ROOT = APP.parent
for _p in (str(APP), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from cpsim import report  # noqa: E402
from cpsim.config import EXAMPLE, load_internal_columns, parse_internal_columns  # noqa: E402
from cpsim.curves import (PublicData, freshness, load_public, ntnb_quotes,  # noqa: E402
                          oldest_collection)
from cpsim.enrich import EnrichedPosition, Override, enrich  # noqa: E402
from cpsim.models import Indexer, MapaPositions, RunflowData  # noqa: E402
from cpsim.normalize import fmt_brl, fmt_pct  # noqa: E402
from cpsim.parsers.mapa_pdf import parse_mapa, parse_rate_text, validate_lot  # noqa: E402
from cpsim.parsers.runflow_xlsx import read_runflow  # noqa: E402
from cpsim.scenarios import Scenario, base_scenario, user_scenario  # noqa: E402
from cpsim.spreads import DEFAULT_BID_ASK_BY_LIQUIDITY  # noqa: E402
from cpsim.swap_engine import SwapParams, SwapReport, run_swaps  # noqa: E402
from cpsim.taxes import TaxPolicy  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
SAMPLE_MAPA = SAMPLES / "mapa_posicoes_layout_real.pdf"
SAMPLE_RUNFLOW = SAMPLES / "runflow_exemplo.xlsx"
APP_TITLE = "Simulador de trocas"
ss = st.session_state

# Parâmetros (tela 2) e seus padrões — prompt 6.2–6.5; todos hipóteses ajustáveis.
DEFAULTS: dict[str, Any] = {
    "usar_amostra": False,
    "modo": "interno",
    "qualificado": False,
    "investidor": "PF",
    "horizonte": 1.0,
    "cenario": "Base (Focus)",
    "cdi_usuario": 14.0,
    "ipca_usuario": 4.5,
    "banda_duration": 1.5,
    "tolerancia_rating": 0,
    "aceitar_sem_rating": False,
    "modo_amplo": False,
    "mesma_tributacao": True,
    "limite_emissor": 20.0,
    "limite_setor": 40.0,
    "classe_liquidez": "media",
    "b_alta": DEFAULT_BID_ASK_BY_LIQUIDITY["alta"] * 1e4,
    "b_media": DEFAULT_BID_ASK_BY_LIQUIDITY["media"] * 1e4,
    "b_baixa": DEFAULT_BID_ASK_BY_LIQUIDITY["baixa"] * 1e4,
    "rec_delta": 30.0,
    "rec_payback": 1.0,
    "marg_delta": 10.0,
    "marg_payback": 2.0,
    "incluir_sem_preco": False,
}


# ----------------------------------------------------------------------------- parâmetros
def param(name: str) -> Any:
    return ss.get(f"p_{name}", DEFAULTS[name])


def bind(name: str) -> str:
    """Prepara a chave de um widget ligado ao parâmetro persistente `name`."""
    w = f"w_{name}"
    if f"p_{name}" not in ss:
        ss[f"p_{name}"] = DEFAULTS[name]
    if w not in ss:
        ss[w] = ss[f"p_{name}"]
    return w


def store(name: str) -> None:
    ss[f"p_{name}"] = ss[f"w_{name}"]


def mode() -> str:
    return param("modo")


def interno() -> bool:
    return mode() == "interno"


def L(text: str) -> str:
    """Texto de tela no modo ativo (modo cliente: sem menção ao Runflow)."""
    return report.sanitize(text, mode())


# ----------------------------------------------------------------------------- arquivos
def use_samples() -> bool:
    return bool(param("usar_amostra"))


def files() -> tuple[bytes | None, bytes | None, str | None]:
    if use_samples():
        return SAMPLE_MAPA.read_bytes(), SAMPLE_RUNFLOW.read_bytes(), None
    return ss.get("mapa_bytes"), ss.get("runflow_bytes"), ss.get("cfg_text")


def _h(*parts: Any) -> str:
    m = hashlib.sha256()
    for p in parts:
        m.update(p if isinstance(p, bytes) else repr(p).encode())
    return m.hexdigest()


def _memo(name: str, key: str, fn: Callable[[], Any]) -> Any:
    store_ = ss.setdefault("_memo", {})
    hit = store_.get(name)
    if hit and hit[0] == key:
        return hit[1]
    val = fn()
    store_[name] = (key, val)
    return val


def internal_columns():
    _, _, cfg = files()
    if use_samples():
        return load_internal_columns(EXAMPLE)
    if cfg:
        return parse_internal_columns(cfg, "upload")
    return load_internal_columns()


def mapa_raw() -> MapaPositions | None:
    pdf, _, _ = files()
    if not pdf:
        return None
    return _memo("mapa_raw", _h(pdf), lambda: parse_mapa(pdf))


LOT_FIELDS = ["code", "rate_text", "quantity", "pu_curve", "gross_curve", "pu_market",
              "gross_market", "ir", "iof", "net_value"]


def mapa() -> MapaPositions | None:
    """Mapa com as correções manuais da tela 1 aplicadas e revalidadas."""
    raw = mapa_raw()
    if raw is None:
        return None
    fixes = ss.get("lot_fixes", {})

    def build():
        m = copy.deepcopy(raw)
        for i, fx in fixes.items():
            if i >= len(m.lots):
                continue
            lot = m.lots[i]
            for k, v in fx.items():
                if k == "rate_text":
                    lot.rate_text = str(v)
                    lot.rate = parse_rate_text(str(v))
                else:
                    setattr(lot, k, v)
            validate_lot(lot)
        return m

    return _memo("mapa", _h(_h(files()[0] or b""), sorted(fixes.items())), build)


def runflow() -> RunflowData | None:
    _, xlsx, cfg = files()
    if not xlsx:
        return None
    cols = internal_columns()
    return _memo("runflow", _h(xlsx, cfg, use_samples()), lambda: read_runflow(xlsx, cols))


def public() -> PublicData:
    return _memo("public", "1", load_public)


def as_of() -> dt.date:
    m = mapa()
    return m.position_date if m and m.position_date else dt.date.today()


def scenario() -> Scenario:
    h = float(param("horizonte"))
    if param("cenario") == "Do usuário":
        return user_scenario(param("cdi_usuario") / 100, param("ipca_usuario") / 100, h)
    return base_scenario(public(), as_of(), h)


def params() -> SwapParams:
    return SwapParams(
        qualified_investor=param("qualificado"),
        duration_band=float(param("banda_duration")),
        same_tax=param("mesma_tributacao"),
        same_indexer=not param("modo_amplo"),
        rating_tolerance=int(param("tolerancia_rating")),
        accept_unrated=param("aceitar_sem_rating"),
        issuer_limit=param("limite_emissor") / 100,
        sector_limit=param("limite_setor") / 100,
        liquidity_class=param("classe_liquidez"),
        bid_ask_by_class={"alta": param("b_alta") / 1e4, "media": param("b_media") / 1e4,
                          "baixa": param("b_baixa") / 1e4},
        rec_min_delta=param("rec_delta") / 1e4,
        rec_max_payback=float(param("rec_payback")),
        marg_min_delta=param("marg_delta") / 1e4,
        marg_max_payback=float(param("marg_payback")),
        policy=TaxPolicy(investor=param("investidor")),
    )


def overrides() -> dict[str, Override]:
    return ss.get("overrides", {})


def enriched() -> list[EnrichedPosition] | None:
    m, rf = mapa(), runflow()
    if m is None or m.position_date is None:
        return None
    sc, ovs, p = scenario(), overrides(), params()
    key = _h(id(m), id(rf), sc, sorted((k, repr(v)) for k, v in ovs.items()),
             param("incluir_sem_preco"), p.policy)
    return _memo("enriched", key, lambda: enrich(
        m, sc, rf.candidates if rf else None, ovs,
        include_without_market_price=param("incluir_sem_preco"), policy=p.policy))


def swap_report() -> SwapReport | None:
    en, rf = enriched(), runflow()
    if en is None or rf is None:
        return None
    sc, p = scenario(), params()
    ntnb, _ = ntnb_quotes(public())
    key = _h(id(en), id(rf), sc, repr(p))
    return _memo("report", key, lambda: run_swaps(en, rf.candidates, sc, as_of(), p, ntnb))


# ----------------------------------------------------------------------------- exibição
OFFLINE_URL = ("https://viniciusmarquesserpeloni-commits.github.io/credito-privado-sim/"
               "simulador_credito_privado.html")


def header() -> None:
    """Faixa de marca no topo (visual do painel), com posição, dados públicos e modo."""
    from theme import topbar

    m = mapa()
    col = oldest_collection(public())
    stale = any(f.stale for f in freshness(public(), dt.date.today()))
    pills = [("Posição", m.position_date.strftime("%d/%m/%Y") if m and m.position_date else "—", ""),
             ("Dados públicos", col.strftime("%d/%m/%Y") if col else "—", "stale" if stale else ""),
             (f"Modo {mode()}", "", "lime")]
    if use_samples():
        pills.insert(2, ("Amostra fictícia", "", ""))
    topbar(pills)


def footer() -> None:
    st.divider()
    st.caption(f"{report.AVISO} Fontes públicas: BCB SGS (CDI, Selic, IPCA), BCB Focus e Tesouro "
               f"Transparente. Arquivos do usuário ficam só na memória desta aba. "
               f"[Versão offline (um único HTML, abre sem internet)]({OFFLINE_URL})")


def need_data() -> bool:
    """Mostra o aviso e devolve True se faltar Mapa ou Runflow."""
    pdf, xlsx, _ = files()
    if pdf and xlsx:
        return False
    st.info(L("Carregue o Mapa de Posições e o Runflow na aba **Dados** (ou use as amostras)."))
    return True


def fmt_rate(indexer: Indexer | None, value: float | None) -> str:
    if value is None or indexer is None:
        return "—"
    from cpsim.models import Rate

    return str(Rate(indexer, value))


def display(rows: list[dict[str, Any]], money: tuple[str, ...] = (),
            years: tuple[str, ...] = ()) -> pd.DataFrame:
    """Tabela para a TELA (texto pt-BR). O Excel exportado mantém os números crus."""
    df = pd.DataFrame(rows)
    for c in df.columns:
        if c in money:
            df[c] = df[c].map(lambda v: fmt_brl(v) if isinstance(v, (int, float)) else "—")
        elif c in years:
            df[c] = df[c].map(lambda v: f"{v:.2f}".replace(".", ",")
                              if isinstance(v, (int, float)) and v == v else "—")
        elif df[c].map(lambda v: isinstance(v, dt.date)).any():
            df[c] = df[c].map(lambda v: v.strftime("%d/%m/%Y") if isinstance(v, dt.date) else v)
    return df.astype(str).replace({"None": "—", "nan": "—"})

