# Simulador de Trocas em Crédito Privado

Aplicação web que lê o **Mapa de Posições** de um cliente (PDF) e o **Runflow** da mesa (Excel com
os papéis de crédito privado disponíveis) e indica, para cada ativo da carteira, se vale trocá-lo
por um papel do Runflow — considerando taxa, prazo/duration, rating, tributação, liquidez, estoque
e custos.

> **Aviso.** Ferramenta analítica. **Não constitui recomendação de investimento.** Os limiares de
> classificação ("troca recomendada", "marginal", "manter") são hipóteses ainda **não validadas por
> backtest**.

## Privacidade

- O app roda **inteiro no seu navegador** (Python via [stlite](https://github.com/whitphx/stlite)/Pyodide).
  Os arquivos que você envia ficam só na memória da aba: não são gravados em disco, enviados a
  servidor nem registrados em log.
- O repositório é público e contém **apenas dados fictícios** (`data/samples/`, gerados por
  `scripts/make_samples.py`) e dados públicos (`data/public/`: BCB e Tesouro Transparente).
- Um teste de privacidade no CI bloqueia arquivos de dados fora dessas pastas e marcações de
  confidencialidade ou números de agência/conta.
- Telemetria do Streamlit desligada.

## Estado

**Fase 2 (motor de troca)** concluída — relatórios em [`docs/`](docs/) (`FASE0_` a `FASE2_RELATORIO.md`).
Próxima: interface completa (Fase 3).

## Rodar localmente

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
pytest
streamlit run app/app.py
```

Versão do navegador, localmente:

```bash
python scripts/build_site.py --serve                # http://localhost:8790
```

## Metodologia

As fórmulas seguem [`docs/metodologia.md`](docs/metodologia.md).

## Licença

MIT.
