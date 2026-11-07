"""Tela 4 — Trocas: candidatos por posição (cenários A e B), justificativa e carteira antes/depois."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

import ui  # noqa: E402
from cpsim import report  # noqa: E402
from cpsim.normalize import fmt_brl  # noqa: E402
from cpsim.swap_engine import FORA, MANTER, MARGINAL, RECOMENDADA, SEM_TAXA  # noqa: E402

st.title("4 · Trocas")
if ui.need_data():
    st.stop()
rep, en, rf = ui.swap_report(), ui.enriched(), ui.runflow()
if rep is None:
    st.error("Não foi possível rodar o motor de troca (Mapa sem data da posição?).")
    st.stop()

st.caption(f"{report.AVISO} Classificação pelo cenário B (PU Mercado = marcação); o ranking "
           "usa só a economia do cliente"
           + ("; o fee da mesa não entra no ranking nem na classificação." if ui.interno()
              else "."))
cont = Counter(r.status for r in rep.results)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Troca recomendada", cont[RECOMENDADA])
c2.metric("Troca marginal", cont[MARGINAL])
c3.metric("Manter", cont[MANTER])
c4.metric("Sem taxa / fora", cont[SEM_TAXA] + cont[FORA])
c5.metric("Ganho anual estimado", fmt_brl(rep.total_gain_annual),
          help="Soma das trocas recomendadas aplicadas na carteira 'depois'.")

st.subheader("Carteira antes e depois")
st.caption(f"Cenário {rep.scenario.name}: CDI {ui.fmt_pct(rep.scenario.cdi)}, IPCA "
           f"{ui.fmt_pct(rep.scenario.ipca)}. Comparações entre indexadores dependem dele.")
st.dataframe(ui.display(report.summary_table(rep)), hide_index=True, width="stretch")
for a in rep.alerts:
    st.warning(a)

# ---------------------------------------------------------------- export
labels = rf.internal_labels if rf else {}
xlsx = report.to_excel(rep, en, ui.mode(), labels)
st.download_button(f"Exportar Excel (modo {ui.mode()})", data=xlsx,
                   file_name=f"trocas_{ui.mode()}_{rep.as_of:%Y-%m-%d}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   help="Gerado no navegador; o arquivo vai direto para a sua máquina.")

# ---------------------------------------------------------------- por posição
st.subheader("Por posição")
ordem = {RECOMENDADA: 0, MARGINAL: 1, MANTER: 2, SEM_TAXA: 3, FORA: 4}
so_trocas = st.toggle("Mostrar só posições com troca recomendada ou marginal", value=False)
rows_all = report.swaps_table(rep, ui.mode(), labels)
cols = ["Rank", "Candidato", "Emissor candidato", "Taxa candidato", "Duration candidato",
        "Rating candidato", "Δ usado", "Medida do Δ", "Ganho anual (R$)",
        "Custo de saída B (R$)", "Imposto antecipado (R$)", "Equilíbrio A (anos)",
        "Equilíbrio B (anos)", "Classificação (A)", "Classificação (B)"]
for r in sorted(rep.results, key=lambda r: (ordem.get(r.status, 9), -r.holding.net_value)):
    if so_trocas and r.status not in (RECOMENDADA, MARGINAL):
        continue
    h = r.holding
    extra = " · revisar" if (ui.interno() and h.review) else ""
    titulo = (f"{h.code} · {h.position.issuer} · {fmt_brl(h.net_value)} · "
              f"taxa {ui.fmt_rate(h.indexer, h.market_rate.value if h.market_rate else None)}"
              f" — **{r.status}**{extra}")
    with st.expander(titulo, expanded=r.status == RECOMENDADA):
        if r.status == FORA:
            st.write(f"Fora da análise: {h.scope_note}.")
            continue
        if r.status == SEM_TAXA:
            st.write("Sem taxa de mercado: informe a taxa ou o fluxo na tela **Carteira**.")
            continue
        if h.alerts:
            st.caption("Alertas da posição: " + ui.L("; ".join(h.alerts)))
        if not r.best:
            motivos = ", ".join(f"{k} ({v})" for k, v in r.rejected_by.most_common())
            st.write(f"Nenhum candidato elegível entre {r.evaluated} avaliados. "
                     f"Reprovações por filtro: {ui.L(motivos) or '—'}.")
            continue
        sub = [row for row in rows_all if row["Posição"] == h.code]
        keep = cols + [k for k in sub[0] if k not in cols and k not in (
            "Posição", "Emissor atual", "Valor de saída", "Taxa atual", "Situação",
            "Justificativa")]
        st.dataframe(ui.display([{k: row.get(k) for k in keep} for row in sub],
                                money=("Ganho anual (R$)", "Custo de saída B (R$)",
                                       "Imposto antecipado (R$)", report.LASTRO_COL),
                                years=("Duration candidato", "Equilíbrio A (anos)",
                                       "Equilíbrio B (anos)")),
                     hide_index=True, width="stretch")
        for row in sub:
            with st.popover(f"Justificativa — {row['Candidato']}"):
                for part in row["Justificativa"].split(" | "):
                    st.markdown(f"- {part}")
        st.caption(f"{r.evaluated} candidatos avaliados; reprovações por filtro: "
                   + ui.L(", ".join(f"{k} ({v})" for k, v in r.rejected_by.most_common())))
