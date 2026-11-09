"""Visual do painel "Relatório de Fundos" aplicado ao Streamlit (mesmas cores e componentes do
HTML offline): faixa petróleo com marca e pílulas, navegação no topo com sublinhado lima,
cartões brancos para métricas e contêineres."""

from __future__ import annotations

import html

import streamlit as st

CSS = """
<style>
:root { --ink:#0e2a33; --ink-2:#1c3f4a; --ink-3:#2e5562; --lime:#a8cf38; --lime-soft:#eef6d6;
  --bg:#f4f5f2; --surface:#ffffff; --surface-2:#f8f9f6; --line:#e2e6e0; --text:#0e2a33;
  --text-2:#4b5f66; --muted:#7d8f95;
  --font:"Inter","Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif; }
.stApp, .stApp p, .stApp label, .stApp li { font-family: var(--font); }
.stApp { background: var(--bg); }
/* cabeçalho do Streamlit (onde fica a navegação no topo) no tom petróleo */
header[data-testid="stHeader"] { background: var(--ink); }
header[data-testid="stHeader"] a, header[data-testid="stHeader"] span,
header[data-testid="stHeader"] button, header[data-testid="stHeader"] svg { color: #b9c9cd !important; }
header[data-testid="stHeader"] a[aria-current="page"], header[data-testid="stHeader"] a:hover,
header[data-testid="stHeader"] a[aria-current="page"] span { color: #fff !important; }
header[data-testid="stHeader"] a[aria-current="page"] { box-shadow: inset 0 -3px 0 var(--lime); border-radius: 0; background: transparent !important; }
/* faixa de marca */
[data-testid="stMainBlockContainer"] { padding-top: 3.75rem; }
.cp-topbar { background: var(--ink); color: #fff; margin: 0 0 1.25rem; padding: 14px 24px 18px;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px 24px;
  border-radius: 0 0 10px 10px; border-top: 1px solid rgba(255,255,255,.08); }
.cp-brand { display: flex; align-items: center; gap: 14px; }
.cp-mark { position: relative; width: 34px; height: 34px; flex: none; }
.cp-mark::before { content: ""; position: absolute; left: 3px; top: 4px; width: 26px; height: 5px; background: var(--lime); transform: rotate(-12deg); border-radius: 1px; }
.cp-mark::after { content: ""; position: absolute; left: 12px; top: 13px; width: 6px; height: 19px; background: #fff; border-radius: 1px; }
.cp-brand h1 { margin: 0 !important; padding: 0 !important; font-size: 18px !important; font-weight: 600 !important; color: #fff !important; letter-spacing: -.01em; }
.cp-brand p { margin: 2px 0 0 !important; font-size: 12.5px; color: #b9c9cd !important; }
.cp-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.cp-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,.08); color: #dfe8ea; font-size: 12px; white-space: nowrap; }
.cp-pill b { color: #fff; font-weight: 600; }
.cp-pill i { width: 6px; height: 6px; border-radius: 50%; background: var(--lime); display: inline-block; }
.cp-pill.stale i { background: #f0b429; }
.cp-pill.lime { background: var(--lime); color: var(--ink); font-weight: 600; }
/* títulos e cartões */
.stApp h1 { font-size: 22px !important; font-weight: 600 !important; letter-spacing: -.015em; color: var(--text); }
.stApp h2, .stApp h3 { font-size: 14.5px !important; font-weight: 600 !important; color: var(--text); text-transform: none; }
[data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 14px 18px; box-shadow: 0 1px 2px rgba(14,42,51,.06), 0 1px 1px rgba(14,42,51,.04); }
[data-testid="stMetricLabel"] p { color: var(--text-2) !important; font-size: 12px !important; font-weight: 500; }
[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 600 !important; letter-spacing: -.02em; color: var(--text); }
[data-testid="stExpander"] details, [data-testid="stVerticalBlockBorderWrapper"] { background: var(--surface); border-color: var(--line) !important; border-radius: 10px !important; }
.stButton > button, .stDownloadButton > button { border-radius: 8px; }
[data-testid="stDownloadButton"] button, .stButton > button[kind="primary"] { background: var(--ink) !important; color: #fff !important; border-color: var(--ink) !important; }
[data-testid="stDownloadButton"] button p { color: #fff !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; }
[data-testid="stSidebar"] { display: none; }
[data-testid="stCaptionContainer"] { color: var(--muted); }
</style>
"""


def apply() -> None:
    st.html(CSS)


def topbar(pills: list[tuple[str, str, str]], subtitle: str = "Simulador de trocas de títulos") -> None:
    """pills: (rótulo, valor, classe extra: '', 'stale' ou 'lime')."""
    items = "".join(
        f'<span class="cp-pill {cls}">{"" if cls == "lime" else "<i></i>"}{html.escape(lbl)}'
        f'{f" <b>{html.escape(val)}</b>" if val else ""}</span>' for lbl, val, cls in pills)
    st.html(f'<div class="cp-topbar"><div class="cp-brand"><span class="cp-mark"></span><div>'
            f'<h1>Crédito Privado</h1><p>{html.escape(subtitle)}</p></div></div>'
            f'<div class="cp-meta">{items}</div></div>')
