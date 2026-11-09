"""Tela 2 — Parâmetros (todos são hipóteses ajustáveis; padrões do prompt 6.2–6.5)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

import ui  # noqa: E402
from cpsim.normalize import fmt_pct  # noqa: E402

st.title("Parâmetros")
st.caption("Limiares e custos são hipóteses ainda não validadas por backtest.")


def radio(name, label, options, **kw):
    st.radio(label, options, key=ui.bind(name), horizontal=True, **kw)
    ui.store(name)


def toggle(name, label, **kw):
    st.toggle(label, key=ui.bind(name), **kw)
    ui.store(name)


def number(name, label, **kw):
    st.number_input(label, key=ui.bind(name), **kw)
    ui.store(name)


def select(name, label, options, **kw):
    st.selectbox(label, options, key=ui.bind(name), **kw)
    ui.store(name)


st.subheader("Saída")
radio("modo", "Modo", ["interno", "cliente"],
      help=ui.L("Cliente: sem colunas internas, sem estoque da mesa e sem menção ao Runflow "
                "interno."))

st.subheader("Investidor")
c1, c2, c3 = st.columns(3)
with c1:
    radio("investidor", "Tipo", ["PF", "PJ"], help="PJ não tem isenção de IR.")
with c2:
    toggle("qualificado", "Investidor qualificado")
with c3:
    number("horizonte", "Horizonte (anos)", min_value=0.25, max_value=10.0, step=0.25)

st.subheader("Cenário de CDI e IPCA")
radio("cenario", "Cenário", ["Base (Focus)", "Do usuário"])
if ui.param("cenario") == "Do usuário":
    c1, c2 = st.columns(2)
    with c1:
        number("cdi_usuario", "CDI médio no horizonte (% a.a.)", min_value=0.0, step=0.25)
    with c2:
        number("ipca_usuario", "IPCA médio no horizonte (% a.a.)", min_value=-5.0, step=0.25)
sc = ui.scenario()
st.caption(f"Em uso: **{sc.name}** — CDI {fmt_pct(sc.cdi)}, IPCA {fmt_pct(sc.ipca)} "
           f"({sc.cdi_source}). {sc.note}")

st.subheader("Filtros de elegibilidade")
c1, c2, c3 = st.columns(3)
with c1:
    number("banda_duration", "Banda de duration (± anos)", min_value=0.0, step=0.25)
    number("tolerancia_rating", "Tolerância de rating (degraus abaixo)", min_value=0,
           max_value=6, step=1)
with c2:
    toggle("aceitar_sem_rating", "Aceitar papéis sem rating",
           help="Sem rating em qualquer lado: só passa se você confirmar aqui.")
    toggle("mesma_tributacao", "Exigir mesma tributação (isento → isento)")
with c3:
    toggle("modo_amplo", "Modo amplo: permitir outro indexador",
           help="Compara pela taxa nominal esperada no cenário escolhido.")
    toggle("incluir_sem_preco", "Incluir posições sem PU Mercado (CDB, CPR…)")
c1, c2 = st.columns(2)
with c1:
    number("limite_emissor", "Limite por emissor após a troca (% do total)", min_value=1.0,
           max_value=100.0, step=5.0)
with c2:
    number("limite_setor", "Limite por setor após a troca (% do total)", min_value=1.0,
           max_value=100.0, step=5.0)

st.subheader("Custo de saída (cenário B)")
st.caption("b = diferença entre taxa de venda e de compra; custo ≈ b/2 × duration modificada × "
           "valor. Sem ANBIMA no MVP: b por classe de liquidez (padrões hipotéticos).")
c1, c2, c3, c4 = st.columns(4)
with c1:
    select("classe_liquidez", "Classe padrão das posições", ["alta", "media", "baixa"])
with c2:
    number("b_alta", "b — alta (bps)", min_value=0.0, step=5.0)
with c3:
    number("b_media", "b — média (bps)", min_value=0.0, step=5.0)
with c4:
    number("b_baixa", "b — baixa (bps)", min_value=0.0, step=5.0)

st.subheader("Limiares de classificação (cenário B)")
c1, c2, c3, c4 = st.columns(4)
with c1:
    number("rec_delta", "Recomendada: Δ mínimo (bps)", min_value=0.0, step=5.0)
with c2:
    number("rec_payback", "Recomendada: equilíbrio máx. (anos)", min_value=0.0, step=0.25)
with c3:
    number("marg_delta", "Marginal: Δ mínimo (bps)", min_value=0.0, step=5.0)
with c4:
    number("marg_payback", "Marginal: equilíbrio máx. (anos)", min_value=0.0, step=0.25)

if st.button("Restaurar padrões"):
    for k in list(st.session_state.keys()):
        if k.startswith(("p_", "w_")):
            del st.session_state[k]
    st.rerun()
