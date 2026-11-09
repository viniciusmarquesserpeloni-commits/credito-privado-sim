"""Tela 1 — Dados: uploads, situação dos arquivos, dados públicos e correção de linhas."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import ui  # noqa: E402
from cpsim.curves import MAX_IDADE_DIAS_UTEIS, freshness, oldest_collection  # noqa: E402

ss = st.session_state
st.title("Dados")
st.caption("Os arquivos ficam só na memória desta aba: nada é gravado, enviado a servidor ou "
           "registrado. Ao fechar a aba, tudo some.")

st.toggle("Usar arquivos de amostra (fictícios)", key=ui.bind("usar_amostra"),
          help=ui.L("Mapa e Runflow fictícios do repositório, no mesmo layout dos reais."))
ui.store("usar_amostra")

# ---------------------------------------------------------------- uploads
c1, c2, c3 = st.columns(3)
with c1:
    up = st.file_uploader("Mapa de Posições (PDF) — obrigatório", type=["pdf"],
                          disabled=ui.use_samples())
    if up is not None and up.getvalue() != ss.get("mapa_bytes"):
        ss["mapa_bytes"], ss["mapa_nome"] = up.getvalue(), up.name
        ss["lot_fixes"], ss["overrides"] = {}, {}
with c2:
    up = st.file_uploader(ui.L("Runflow (XLSX) — obrigatório"), type=["xlsx"],
                          disabled=ui.use_samples())
    if up is not None and up.getvalue() != ss.get("runflow_bytes"):
        ss["runflow_bytes"], ss["runflow_nome"] = up.getvalue(), up.name
with c3:
    up = st.file_uploader("Colunas internas (.toml) — opcional", type=["toml"],
                          disabled=ui.use_samples(),
                          help="config/runflow_columns.local.toml, com os nomes reais das "
                               "colunas internas. Fica só na memória.")
    if up is not None:
        ss["cfg_text"], ss["cfg_nome"] = up.getvalue().decode("utf-8"), up.name

if not ui.use_samples() and (ss.get("mapa_bytes") or ss.get("runflow_bytes")):
    if st.button("Descartar arquivos carregados"):
        for k in ("mapa_bytes", "mapa_nome", "runflow_bytes", "runflow_nome", "cfg_text",
                  "cfg_nome", "lot_fixes", "overrides", "_memo"):
            ss.pop(k, None)
        st.rerun()

# ---------------------------------------------------------------- situação
st.subheader("Situação dos arquivos")
m, rf = ui.mapa(), ui.runflow()
a, b, c = st.columns(3)
with a:
    st.markdown("**Mapa de Posições**")
    if m is None:
        st.write("não carregado")
    else:
        nome = "amostra fictícia" if ui.use_samples() else ss.get("mapa_nome", "")
        st.write(f"{nome} · posição de "
                 f"**{m.position_date.strftime('%d/%m/%Y') if m.position_date else '—'}**")
        st.write(f"{m.n_pages} páginas · {len(m.lots)} lotes · {len(m.positions())} posições · "
                 f"{len(m.invalid_lots)} lote(s) com erro")
        for w in m.warnings:
            st.warning(w)
with b:
    st.markdown(f"**{ui.L('Runflow')}**")
    if rf is None:
        st.write("não carregado")
    else:
        nome = "amostra fictícia" if ui.use_samples() else ss.get("runflow_nome", "")
        st.write(f"{nome} · {len(rf.candidates)} papéis · "
                 f"{sum(c.active for c in rf.candidates)} com distribuição ativa")
        if rf.missing:
            st.warning("Colunas não encontradas: " + ", ".join(rf.missing))
        if rf.extra and ui.interno():
            st.caption("Colunas ignoradas: " + ", ".join(rf.extra))
        for w in rf.warnings:
            st.warning(w)
        if ui.interno():
            st.caption(f"Nomes das colunas internas: config {rf.columns_source}.")
with c:
    st.markdown("**Dados públicos**")
    pd_ = ui.public()
    col = oldest_collection(pd_)
    st.write("BCB SGS (CDI, Selic, IPCA), Focus e Tesouro Direto — coletados em "
             f"**{col.strftime('%d/%m/%Y') if col else '—'}**")
    venc = [f.name for f in freshness(pd_, dt.date.today()) if f.stale]
    if venc:
        st.warning(f"Mais de {MAX_IDADE_DIAS_UTEIS} dias úteis (ou ausentes): "
                   + ", ".join(venc))
    st.caption("Tesouro Direto = taxas de varejo (referência de NTN-B).")

# ---------------------------------------------------------------- correção de linhas
if m is not None and m.invalid_lots:
    st.subheader("Linhas com erro — corrija e aplique")
    st.caption("Confira no PDF e corrija os campos. Linhas com erro ficam fora da análise.")
    raw = ui.mapa_raw()
    idx = [i for i, lot in enumerate(m.lots) if not lot.valid]
    df = pd.DataFrame([{
        "linha": i, "erros": "; ".join(m.lots[i].errors),
        **{f: getattr(m.lots[i], f) for f in ui.LOT_FIELDS},
    } for i in idx])
    edited = st.data_editor(df, hide_index=True, disabled=["linha", "erros"], key="editor_lotes",
                            width="stretch")
    if st.button("Aplicar correções"):
        fixes = dict(ss.get("lot_fixes", {}))
        for _, row in edited.iterrows():
            i = int(row["linha"])
            orig = raw.lots[i]
            ch = {f: row[f] for f in ui.LOT_FIELDS
                  if not (pd.isna(row[f]) and getattr(orig, f) is None)
                  and row[f] != getattr(orig, f)}
            for f in ("quantity",):
                if f in ch and ch[f] is not None and not pd.isna(ch[f]):
                    ch[f] = int(ch[f])
            if ch:
                fixes[i] = ch
        ss["lot_fixes"] = fixes
        st.rerun()
elif m is not None:
    st.success("Todas as linhas do Mapa passaram na validação (Quantidade × PU ≈ Valor Bruto).")
if ss.get("lot_fixes"):
    st.caption(f"{len(ss['lot_fixes'])} linha(s) corrigida(s) manualmente nesta sessão.")
