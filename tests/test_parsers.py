"""Leitores do Mapa (duas amostras fictícias) e do Runflow (colunas por nome, config interna)."""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pytest

from cpsim.config import EXAMPLE, load_internal_columns, parse_internal_columns
from cpsim.models import Indexer
from cpsim.parsers.mapa_pdf import parse_mapa, parse_rate_text, parse_title, validate_lot
from cpsim.parsers.runflow_xlsx import PUBLIC_COLUMNS, read_runflow

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
D = dt.date


@pytest.fixture(scope="module")
def mapa_simples():
    return parse_mapa((SAMPLES / "mapa_posicoes_exemplo.pdf").read_bytes())


@pytest.fixture(scope="module")
def mapa_real():
    """Amostra fictícia com a ESTRUTURA do PDF real (palavras soltas, topo, kerning)."""
    return parse_mapa((SAMPLES / "mapa_posicoes_layout_real.pdf").read_bytes())


@pytest.fixture(scope="module")
def runflow():
    return read_runflow((SAMPLES / "runflow_exemplo.xlsx").read_bytes(),
                        load_internal_columns(EXAMPLE))


# ===================================================================== Mapa — as duas amostras
@pytest.mark.parametrize("fx, n_lotes", [("mapa_simples", 28), ("mapa_real", 15)])
def test_mapa_le_tudo_sem_erro(request, fx, n_lotes):
    m = request.getfixturevalue(fx)
    assert m.n_pages >= 2
    assert m.position_date == D(2026, 10, 30)
    assert len(m.lots) == n_lotes
    assert not m.warnings
    assert m.invalid_lots == []
    assert {lot.page for lot in m.lots} >= {1, 2}


@pytest.mark.parametrize("fx", ["mapa_simples", "mapa_real"])
def test_mapa_descarta_cliente_e_rodape(request, fx):
    m = request.getfixturevalue(fx)
    blob = repr([lot.__dict__ for lot in m.lots]).upper()
    for proibido in ("CLIENTE", "EXEMPLO", "AG XXXX", "XXXXXX", "DATA POSIÇÃO", "DEDUÇÃO",
                     "GERADO EM", "MAPA DE POSI"):
        assert proibido not in blob


@pytest.mark.parametrize("fx", ["mapa_simples", "mapa_real"])
def test_mapa_campos(request, fx):
    m = request.getfixturevalue(fx)
    by = {}
    for lot in m.lots:
        by.setdefault(lot.code, lot)  # primeiro lote de cada código
    alf = by["XALF12"]
    assert alf.title == "DEB ENERGIA ALFA IPCA 6.50% 15/05/2032 - XALF12"
    assert alf.asset_type == "DEB" and alf.issuer == "ENERGIA ALFA S.A."
    assert alf.maturity == D(2032, 5, 15) and alf.emission == D(2022, 5, 15)
    assert alf.title_rate.indexer is Indexer.IPCA and alf.title_rate.value == pytest.approx(0.065)
    assert by["XGAM13"].rate.indexer is Indexer.PRE
    assert by["XDEL14"].rate.indexer is Indexer.CDI_PCT
    assert by["XDEL14"].rate.value == pytest.approx(1.045)
    assert by["XEPS11"].rate.indexer is Indexer.CDI_SPREAD
    assert by["XEPS11"].rate.value == pytest.approx(0.012)
    assert by["CDBX0001"].pu_market is None and not by["CDBX0001"].has_market_price
    assert by["CPRX0001"].gross_market is None
    assert by["XCRI26A01"].asset_type == "CRI" and by["XCRA25B02"].asset_type == "CRA"


def test_mapa_real_kerning_e_codigo_quebrado(mapa_real):
    codes = [lot.code for lot in mapa_real.lots]
    assert "CDBX0001" in codes  # código escrito como "CDBX00 01" no PDF
    lot = mapa_real.lots[0]
    assert lot.pu_curve == pytest.approx(1312.77) and lot.quantity == 120


def test_mapa_lotes_agregados(mapa_simples):
    pos = {p.code: p for p in mapa_simples.positions()}
    alf = pos["XALF12"]
    assert len(alf.lots) == 4 and alf.quantity == 120 + 60 + 67 + 37
    assert alf.indexer is Indexer.IPCA and alf.has_market_price
    assert alf.gross_market == pytest.approx(sum(lot.gross_market for lot in alf.lots))
    assert alf.net_value == pytest.approx(sum(lot.net_value for lot in alf.lots))
    assert alf.ir == 0.0 and alf.iof == 0.0
    assert 0.0662 < alf.purchase_rate_avg < 0.0705
    assert alf.issuer == "ENERGIA ALFA S.A." and alf.maturity == D(2032, 5, 15)
    assert alf.asset_type == "DEB"
    assert not pos["CDBX0001"].has_market_price and pos["CDBX0001"].gross_market is None
    assert pos["XGAM13"].ir > 0  # tributada, com ganho


def test_validacao_detecta_e_aceita_correcao(mapa_simples):
    lot = mapa_simples.lots[0]
    original = lot.gross_curve
    lot.gross_curve = original * 1.5
    validate_lot(lot)
    assert "Quantidade × PU Curva ≠ Valor Bruto (curva)" in lot.errors
    lot.gross_curve = original  # "correção manual" na tabela editável
    validate_lot(lot)
    assert lot.valid


def test_validacao_outros_erros(mapa_simples):
    import copy

    lot = copy.deepcopy(mapa_simples.lots[2])
    lot.code, lot.rate, lot.maturity, lot.quantity = None, None, None, None
    validate_lot(lot, {"Vencimento": "31/02/2030"})
    txt = " | ".join(lot.errors)
    assert "código" in txt and "Taxa Operação" in txt and "31/02/2030" in txt
    assert "quantidade ausente" in txt
    lot2 = copy.deepcopy(mapa_simples.lots[2])
    lot2.gross_market = None
    validate_lot(lot2)
    assert any("inconsistentes" in e for e in lot2.errors)
    lot3 = copy.deepcopy(mapa_simples.lots[2])
    lot3.net_value += 100
    validate_lot(lot3)
    assert lot3.valid and lot3.warnings  # Valor Líquido divergente é só aviso


@pytest.mark.parametrize("txt, idx, v", [
    ("13.07% PRE", Indexer.PRE, 0.1307), ("5.98% IPCA", Indexer.IPCA, 0.0598),
    ("94.00% CDI", Indexer.CDI_PCT, 0.94), ("104.50% CDI", Indexer.CDI_PCT, 1.045),
    ("CDI + 1.20%", Indexer.CDI_SPREAD, 0.012), ("9 . 99% IPCA", Indexer.IPCA, 0.0999),
    ("IPCA + 6,5%", Indexer.IPCA, 0.065), ("CDI 100%", Indexer.CDI_PCT, 1.0),
    ("1,10% + CDI", Indexer.CDI_SPREAD, 0.011),
])
def test_taxa_operacao(txt, idx, v):
    r = parse_rate_text(txt)
    assert r.indexer is idx and r.value == pytest.approx(v)


def test_taxa_operacao_invalida():
    assert parse_rate_text("12% IGPM") is None


@pytest.mark.parametrize("titulo, tipo, emissor, idx, taxa, cod", [
    ("DEB ENERGIA ALFA IPCA 6.50% 15/05/2032 - XALF12", "DEB", "ENERGIA ALFA", Indexer.IPCA,
     0.065, "XALF12"),
    ("CRI IMOB ZETA CDI 100% 15/02/2034 - 24E1234567", "CRI", "IMOB ZETA", Indexer.CDI_PCT, 1.0,
     "24E1234567"),
    ("DEB VAREJO CDI + 1.20% 15/12/2028 - XEPS11", "DEB", "VAREJO", Indexer.CDI_SPREAD, 0.012,
     "XEPS11"),
    ("CDB BANCO X PRE 12. 50% 28/04/2027 - CDBX00 01", "CDB", "BANCO X", Indexer.PRE, 0.125,
     "CDBX0001"),
    ("CPR AGRO S.A. IPCA 9 . 99% 30/06/2027 -", "CPR", "AGRO S.A.", Indexer.IPCA, 0.0999, None),
])
def test_titulo(titulo, tipo, emissor, idx, taxa, cod):
    t = parse_title(titulo)
    assert (t.asset_type, t.issuer, t.code) == (tipo, emissor, cod)
    assert t.rate.indexer is idx and t.rate.value == pytest.approx(taxa)


def test_titulo_sem_tipo_conhecido():
    t = parse_title("XYZ ALGO 15/01/2030 - ABCD12")
    assert t.asset_type is None and t.rate is None and t.code == "ABCD12"


def test_pdf_sem_tabela():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "Documento qualquer")
    m = parse_mapa(bytes(pdf.output()))
    assert m.lots == [] and m.position_date is None and m.warnings


# ===================================================================== Runflow
def test_runflow_colunas_por_nome(runflow):
    assert len(runflow.candidates) == 24
    assert runflow.missing == []
    assert runflow.extra == ["Observação"]
    assert runflow.columns_source.endswith("runflow_columns.example.toml")
    assert set(runflow.internal_labels) == {"fee", "melhora", "comp_a", "comp_b", "delta_a",
                                            "delta_b"}


def test_runflow_tipos(runflow):
    by = runflow.by_code()
    c = by["XALF12"]
    assert c.indexer is Indexer.IPCA and c.rate.value == pytest.approx(0.0712)
    assert c.maturity == D(2032, 5, 15) and c.duration == pytest.approx(4.31)
    assert c.ntnb_ref_year == 2032 and c.emission_rate == pytest.approx(0.065)
    assert c.active and c.lastro == 2_500_000 and c.qty_available == 2500
    assert c.rating.label == "AAA" and c.tax_exempt is True and c.qualified_only is False
    assert c.product == "DEB" and c.coupon == "Mai/Nov" and c.amortization == "Bullet"
    assert by["XBET21"].rate.value == pytest.approx(0.0755)  # texto "7,55%"
    assert by["XKAP31"].duration == pytest.approx(3.88)  # texto "3,88"
    assert by["XDEL14"].rate.indexer is Indexer.CDI_PCT and by["XDEL14"].rate.value == 1.042
    assert by["XEPS11"].rate.indexer is Indexer.CDI_SPREAD
    assert by["XGAM13"].rate.indexer is Indexer.PRE and by["XGAM13"].tax_exempt is False
    assert not by["XPHI12"].active
    assert by["XCRI26B04"].qualified_only is True
    assert not by["XXI18"].rating.has_rating and "sem rating" in by["XXI18"].warnings
    assert by["XGAM13"].ntnb_ref_year is None


def test_runflow_colunas_internas_vao_para_internal(runflow):
    c = runflow.by_code()["XALF12"]
    assert set(c.internal) == {"fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b"}
    assert c.internal["fee"] == pytest.approx(0.004)
    # nenhum campo interno vaza para os atributos públicos
    assert not any(k in c.__dict__ for k in ("fee", "melhora", "comp_a"))


def _workbook(headers: list[str], rows: list[list]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Consolidado"
    for j, h in enumerate(headers, start=1):
        ws.cell(row=10, column=j, value=h)
    for i, row in enumerate(rows, start=11):
        for j, v in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_runflow_config_local_com_outros_nomes_e_ordem_diferente():
    cfg = parse_internal_columns(
        '[colunas_internas]\nfee = { cabecalho = "Coluna Secreta X", rotulo = "X" }\n'
        'comp_a = "Outra Coluna"\n', "teste")
    headers = ["Taxa de Compra", "Indexador", "Código", "Vencimento", "Coluna Secreta X",
               "Outra Coluna", "Coluna Nova"]
    data = _workbook(headers, [[0.995, "%CDI", "ZZZ11", "15/01/2030", 0.01, 2, "x"],
                               [99.5, "%CDI", "ZZZ12", dt.datetime(2030, 1, 15), None, None, None],
                               [None, None, None, None, None, None, None]])
    rf = read_runflow(data, cfg)
    assert [c.code for c in rf.candidates] == ["ZZZ11", "ZZZ12"]
    a, b = rf.candidates
    assert a.rate.value == pytest.approx(0.995) and b.rate.value == pytest.approx(0.995)
    assert a.internal == {"fee": 0.01, "comp_a": 2}
    assert rf.internal_labels == {"fee": "X", "comp_a": "comp_a"}
    assert rf.extra == ["Coluna Nova"]
    assert "empresa" in rf.missing and not rf.warnings  # obrigatórias presentes


def test_runflow_sem_aba_e_sem_obrigatorias():
    data = _workbook(["Código", "Empresa"], [["AAA11", "Empresa"]])
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data))
    wb["Consolidado"].title = "Outra"
    buf = io.BytesIO()
    wb.save(buf)
    rf = read_runflow(buf.getvalue(), load_internal_columns(EXAMPLE))
    assert any("Aba" in w for w in rf.warnings)
    assert any("obrigatórias" in w for w in rf.warnings)
    c = rf.candidates[0]
    assert c.rate is None and any("indexador" in w for w in c.warnings)


def test_runflow_valores_estranhos():
    headers = ["Código", "Taxa de Compra", "Indexador", "Vencimento", "Isento?",
               "Investidor Qualificado?", "B Ref.", "Rating"]
    rows = [["A1", "abc", "IPCA", "xx", "talvez", "Profissional", "NTN-B 2035", "brAA"],
            ["A2", 7.05, "IPCA", "15/05/2030", "Não", "Geral", "B40", None]]
    rf = read_runflow(_workbook(headers, rows), load_internal_columns(EXAMPLE))
    a, b = rf.candidates
    assert a.rate is None and any("taxa de compra" in w for w in a.warnings)
    assert a.maturity is None and a.tax_exempt is None and a.qualified_only is True
    assert a.ntnb_ref_year == 2035
    assert b.rate.value == pytest.approx(0.0705) and b.tax_exempt is False
    assert b.ntnb_ref_year == 2040


def test_config_carrega_exemplo_e_caminho():
    ex = load_internal_columns(EXAMPLE)
    assert ex.fields == ("fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b")
    assert ex.headers["fee"] == "Receita Estimada"
    assert load_internal_columns().fields  # local (se existir) ou exemplo
    assert set(PUBLIC_COLUMNS.values()) & set(ex.fields) == set()
