"""Simulador de trocas em crédito privado — ponto de entrada (navegação entre as 5 telas).

Roda igual no navegador (stlite/Pyodide, GitHub Pages) e localmente (`streamlit run app/app.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import theme  # noqa: E402
import ui  # noqa: E402

st.set_page_config(page_title="Simulador de trocas — crédito privado", page_icon="📊",
                   layout="wide", initial_sidebar_state="collapsed")
theme.apply()

paginas = [
    st.Page("pages/1_dados.py", title="Dados", default=True),
    st.Page("pages/2_parametros.py", title="Parâmetros"),
    st.Page("pages/3_carteira.py", title="Carteira"),
    st.Page("pages/4_trocas.py", title="Trocas"),
    st.Page("pages/5_metodologia.py", title="Metodologia e fontes"),
]
nav = st.navigation(paginas, position="top")
ui.header()
nav.run()
ui.footer()
