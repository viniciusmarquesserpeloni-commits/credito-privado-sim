"""App Streamlit — tela de DIAGNÓSTICO de leitura (Fases 0–1).

Prova que o app roda no navegador (stlite/Pyodide) e localmente, e mostra como o Mapa (PDF) e o
Runflow (XLSX) foram lidos — só em memória. As telas definitivas (Dados, Parâmetros, Carteira,
Trocas, Metodologia) chegam na Fase 3.
"""

from __future__ import annotations

import sys
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from cpsim.config import EXAMPLE, load_internal_columns, parse_internal_columns  # noqa: E402
from cpsim.normalize import fmt_brl, fmt_pct  # noqa: E402
from cpsim.parsers.mapa_pdf import parse_mapa  # noqa: E402
from cpsim.parsers.runflow_xlsx import read_runflow  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
NO_NAVEGADOR = sys.platform == "emscripten"

st.set_page_config(page_title="Crédito Privado — diagnóstico", page_icon="📄", layout="wide")
st.title("Diagnóstico de leitura")
st.caption(
    "Ferramenta analítica em construção; não constitui recomendação de investimento. "
    "Arquivos enviados ficam só na memória desta aba e não são gravados nem enviados a servidor."
)

with st.expander("Ambiente"):
    versoes = {}
    for p in ["streamlit", "pandas", "numpy", "openpyxl", "pypdf"]:
        try:
            versoes[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versoes[p] = "não instalado"
    st.write(f"**Execução:** {'navegador (Pyodide/stlite)' if NO_NAVEGADOR else 'Python local'} "
             f"· **Python** {sys.version.split()[0]}")
    st.write(" · ".join(f"{k} {v}" for k, v in versoes.items()))

# ---------------------------------------------------------------- entradas
st.subheader("Arquivos")
amostra = st.selectbox(
    "Fonte",
    ["Enviar arquivos", "Amostra fictícia (layout do PDF real)", "Amostra fictícia (tabela simples)"],
)
c1, c2, c3 = st.columns(3)
enviar = amostra == "Enviar arquivos"
up_pdf = c1.file_uploader("Mapa de Posições (PDF)", type=["pdf"], disabled=not enviar)
up_xlsx = c2.file_uploader("Runflow (XLSX)", type=["xlsx"], disabled=not enviar)
up_cfg = c3.file_uploader("Colunas internas (.toml, opcional)", type=["toml"],
                          help="config/runflow_columns.local.toml — fica só na memória.")

if enviar:
    pdf_bytes = up_pdf.getvalue() if up_pdf else None
    xlsx_bytes = up_xlsx.getvalue() if up_xlsx else None
else:
    nome = ("mapa_posicoes_layout_real.pdf" if "real" in amostra else "mapa_posicoes_exemplo.pdf")
    pdf_bytes = (SAMPLES / nome).read_bytes()
    xlsx_bytes = (SAMPLES / "runflow_exemplo.xlsx").read_bytes()

# Amostras usam sempre os nomes genéricos do config de exemplo.
if up_cfg:
    internas = parse_internal_columns(up_cfg.getvalue().decode("utf-8"), "upload")
elif enviar:
    internas = load_internal_columns()
else:
    internas = load_internal_columns(EXAMPLE)

# ---------------------------------------------------------------- Mapa
if pdf_bytes:
    st.subheader("Mapa de Posições")
    t0 = time.perf_counter()
    try:
        mapa = parse_mapa(pdf_bytes)
    except Exception as e:  # noqa: BLE001 — diagnóstico: mostrar o erro é o resultado
        st.error(f"Falha ao ler o PDF: {type(e).__name__}: {e}")
        mapa = None
    dt_ms = (time.perf_counter() - t0) * 1000
    if mapa:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Data da posição", mapa.position_date.strftime("%d/%m/%Y")
                  if mapa.position_date else "—")
        m2.metric("Páginas / posições", f"{mapa.n_pages} / {len(mapa.positions())}")
        m3.metric("Lotes lidos", len(mapa.lots), f"{len(mapa.invalid_lots)} com erro",
                  delta_color="off")
        m4.metric("Tempo de leitura", f"{dt_ms:,.0f} ms".replace(",", "."))
        for w in mapa.warnings:
            st.warning(w)
        df = pd.DataFrame([{
            "pág.": lot.page, "código": lot.code, "tipo": lot.asset_type, "emissor": lot.issuer,
            "vencimento": lot.maturity, "compra": lot.purchase_date,
            "taxa compra": str(lot.rate) if lot.rate else lot.rate_text,
            "qtd": lot.quantity, "PU curva": fmt_brl(lot.pu_curve),
            "PU mercado": fmt_brl(lot.pu_market), "valor líquido": fmt_brl(lot.net_value),
            "erros": "; ".join(lot.errors), "avisos": "; ".join(lot.warnings),
        } for lot in mapa.lots])
        st.dataframe(df, hide_index=True, width="stretch")

# ---------------------------------------------------------------- Runflow
if xlsx_bytes:
    st.subheader("Runflow")
    t0 = time.perf_counter()
    try:
        rf = read_runflow(xlsx_bytes, internas)
    except Exception as e:  # noqa: BLE001
        st.error(f"Falha ao ler o XLSX: {type(e).__name__}: {e}")
        rf = None
    dt_ms = (time.perf_counter() - t0) * 1000
    if rf:
        m1, m2, m3 = st.columns(3)
        m1.metric("Papéis lidos", len(rf.candidates))
        m2.metric("Colunas ausentes", len(rf.missing))
        m3.metric("Tempo de leitura", f"{dt_ms:,.0f} ms".replace(",", "."))
        st.caption(f"Nomes das colunas internas: config **{rf.columns_source}**.")
        if rf.missing:
            st.warning("Colunas esperadas não encontradas: " + ", ".join(rf.missing))
        if rf.extra:
            st.info("Colunas não reconhecidas (ignoradas): " + ", ".join(rf.extra))
        for w in rf.warnings:
            st.warning(w)
        # Diagnóstico mostra só colunas públicas (modo cliente/interno completo: Fase 3).
        df = pd.DataFrame([{
            "código": c.code, "empresa": c.issuer, "produto": c.product,
            "taxa": str(c.rate) if c.rate else "—", "ativa": c.active,
            "vencimento": c.maturity, "duration": c.duration,
            "NTN-B ref.": c.ntnb_ref_year, "emissão": fmt_pct(c.emission_rate),
            "cupom": c.coupon, "amortização": c.amortization, "rating": c.rating.label or "—",
            "qualificado": c.qualified_only, "isento": c.tax_exempt,
            "alertas": "; ".join(c.warnings),
        } for c in rf.candidates])
        st.dataframe(df.astype(str), hide_index=True, width="stretch")

if not (pdf_bytes or xlsx_bytes):
    st.info("Envie os arquivos ou escolha uma amostra para testar a leitura.")
