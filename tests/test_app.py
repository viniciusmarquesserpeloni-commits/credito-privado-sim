"""Fase 3: o app sobe com as amostras, produz a tela 4 sem erro e respeita o modo cliente."""

from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = ["1_dados.py", "2_parametros.py", "3_carteira.py", "4_trocas.py", "5_metodologia.py"]


def run(page: str | None = None, **state) -> AppTest:
    path = APP / "app.py" if page is None else APP / "pages" / page
    at = AppTest.from_file(str(path), default_timeout=180)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at: AppTest) -> str:
    parts: list[str] = []
    for kind in ("title", "header", "subheader", "markdown", "caption", "info", "warning",
                 "success", "error", "metric", "expander", "button", "toggle"):
        for el in getattr(at, kind, []):
            for attr in ("value", "label", "body"):
                v = getattr(el, attr, None)
                if isinstance(v, str):
                    parts.append(v)
    for df in at.dataframe:
        parts.append(df.value.to_csv())
    return "\n".join(parts)


def test_navegacao_sobe_na_tela_dados():
    at = run()
    assert any("1 · Dados" in t.value for t in at.title)


@pytest.mark.parametrize("page", PAGES)
def test_cada_tela_sem_erro_com_amostras(page):
    run(page, p_usar_amostra=True)


@pytest.mark.parametrize("page", PAGES)
def test_cada_tela_sem_dados_nao_quebra(page):
    run(page)


def test_tela_4_produz_trocas_e_export():
    at = run("4_trocas.py", p_usar_amostra=True)
    metr = {m.label: m.value for m in at.metric}
    assert int(metr["Troca recomendada"]) >= 1
    assert len(at.expander) >= 10
    assert any("Exportar Excel" in str(getattr(b, "label", "")) for b in at.get("download_button"))
    texto = all_text(at)
    assert "Troca recomendada" in texto and "Carteira antes e depois" in texto


def test_dados_mostra_situacao_e_coleta_publica():
    at = run("1_dados.py", p_usar_amostra=True)
    texto = all_text(at)
    assert "posição de **30/10/2026**" in texto
    assert "coletados em" in texto
    assert "Todas as linhas do Mapa passaram na validação" in texto


@pytest.mark.parametrize("page", ["3_carteira.py", "4_trocas.py", "5_metodologia.py"])
def test_modo_cliente_sem_colunas_internas_nem_runflow(page):
    at = run(page, p_usar_amostra=True, p_modo="cliente")
    texto = all_text(at).lower()
    from cpsim.config import EXAMPLE, load_internal_columns

    cfg = load_internal_columns(EXAMPLE)
    for rot in list(cfg.labels.values()) + list(cfg.headers.values()):
        assert rot.lower() not in texto, rot
    for proibido in ("runflow", "lastro", "spread estimado da mesa", "revisar"):
        assert proibido not in texto, proibido


def test_modo_interno_mostra_colunas_internas():
    at = run("4_trocas.py", p_usar_amostra=True, p_modo="interno")
    texto = all_text(at)
    assert "Lastro disponível" in texto
    from cpsim.config import EXAMPLE, load_internal_columns

    assert any(r in texto for r in load_internal_columns(EXAMPLE).labels.values())
    at3 = run("3_carteira.py", p_usar_amostra=True, p_modo="interno")
    assert "Spread estimado da mesa" in all_text(at3)


def test_parametro_persiste_e_muda_resultado():
    at = run("2_parametros.py", p_usar_amostra=True)
    at.number_input(key="w_banda_duration").set_value(0.0).run()
    assert at.session_state["p_banda_duration"] == 0.0
    t4 = run("4_trocas.py", p_usar_amostra=True, p_banda_duration=0.0)
    metr = {m.label: m.value for m in t4.metric}
    assert int(metr["Troca recomendada"]) == 0  # banda zero: nenhum candidato com mesma duration


def test_cenario_do_usuario():
    at = run("2_parametros.py", p_usar_amostra=True, p_cenario="Do usuário", p_cdi_usuario=10.0)
    assert "CDI 10,00%" in all_text(at)


def test_sobrescrita_na_carteira():
    from cpsim.enrich import Override

    at = run("3_carteira.py", p_usar_amostra=True,
             overrides={"XALF12": Override(duration=3.33, market_rate=0.0701)})
    df = at.dataframe[0].value
    linha = df[df["Código"] == "XALF12"].iloc[0]
    assert linha["Fonte da taxa"] == "informado pelo usuário"
    assert linha["Duration (anos)"] == "3,33"
