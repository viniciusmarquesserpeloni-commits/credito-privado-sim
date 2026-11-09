"""Tela 3 — Carteira: taxa de mercado e duration com fonte, marcação vs curva e sobrescritas."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import ui  # noqa: E402
from cpsim import report  # noqa: E402
from cpsim.enrich import Override  # noqa: E402
from cpsim.normalize import fmt_brl  # noqa: E402

ss = st.session_state
st.title("Carteira")

m = ui.mapa()
if m is None:
    st.info("Carregue o Mapa de Posições na tela **Dados** (ou use as amostras).")
    st.stop()
en = ui.enriched()
if en is None:
    st.error("O Mapa não tem data da posição; não é possível estimar taxas.")
    st.stop()
if ui.runflow() is None:
    st.warning(ui.L("Sem Runflow: todas as taxas saem pelo fluxo padrão (juros semestrais, "
                    "amortização no vencimento) e não há candidatos de troca."))

escopo = [e for e in en if e.in_scope]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valor líquido total", fmt_brl(sum(e.net_value for e in en)))
c2.metric("Posições na análise", f"{len(escopo)} de {len(en)}")
c3.metric("Com taxa de mercado", sum(1 for e in escopo if e.has_market_rate))
if ui.interno():
    c4.metric("Marcadas para revisão", sum(e.review for e in en),
              help="Spread estimado da mesa (taxa estimada − Taxa de Compra) acima de 150 bps.")
else:
    c4.metric("Com alerta", sum(1 for e in escopo if e.alerts))

st.caption("Taxa **estimada** = resolvida pela razão PU Mercado / PU Curva com o fluxo do papel; "
           "**aproximação** = premissa simplificadora; **dado** = informado. Fora da análise por "
           "padrão: papéis sem PU Mercado (CDB, CPR).")

rows = report.positions_table(en, ui.mode())
st.dataframe(ui.display(rows, money=("Valor líquido", "Marcação vs curva"),
                        years=("Duration (anos)",)), hide_index=True, width="stretch")

# ---------------------------------------------------------------- sobrescritas
st.subheader("Informar fluxo, duration ou taxa")
st.caption(ui.L("Campos vazios = usa a estimativa. Amortização e cupom no formato do Runflow "
                "(ex.: \"Anual (Início 2033)\", \"Mar/Set\", \"Bullet\"). Taxa em % — para "
                "%CDI, em % do CDI (ex.: 104,5)."))
ovs = ui.overrides()
base = pd.DataFrame([{
    "Código": e.code,
    "Fluxo em uso": ui.L(e.flow),
    "Cupom": ovs[e.code].coupon if e.code in ovs else None,
    "Amortização": ovs[e.code].amortization if e.code in ovs else None,
    "Duration (anos)": ovs[e.code].duration if e.code in ovs else None,
    "Taxa (%)": (ovs[e.code].market_rate * 100
                 if e.code in ovs and ovs[e.code].market_rate is not None else None),
} for e in escopo])
if base.empty:
    st.write("Nenhuma posição na análise.")
else:
    base = base.astype({"Cupom": "object", "Amortização": "object",
                        "Duration (anos)": "float64", "Taxa (%)": "float64"})
    edited = st.data_editor(base, hide_index=True, disabled=["Código", "Fluxo em uso"],
                            key="editor_overrides", width="stretch",
                            column_config={
                                "Duration (anos)": st.column_config.NumberColumn(min_value=0.0),
                                "Taxa (%)": st.column_config.NumberColumn(format="%.4f"),
                            })
    b1, b2 = st.columns([1, 4])
    if b1.button("Aplicar"):
        new: dict[str, Override] = {}

        def val(x):
            if x is None or (isinstance(x, float) and math.isnan(x)):
                return None
            if isinstance(x, str):
                return x.strip() or None
            return x

        for _, r in edited.iterrows():
            o = Override(coupon=val(r["Cupom"]), amortization=val(r["Amortização"]),
                         duration=val(r["Duration (anos)"]),
                         market_rate=(val(r["Taxa (%)"]) / 100 if val(r["Taxa (%)"]) is not None
                                      else None))
            if any(v is not None for v in (o.coupon, o.amortization, o.duration, o.market_rate)):
                new[r["Código"]] = o
        ss["overrides"] = new
        st.rerun()
    if ovs and b2.button("Limpar sobrescritas"):
        ss["overrides"] = {}
        st.rerun()
