# CLAUDE.md — credito-privado-sim

## Objetivo
Aplicação web que lê o **Mapa de Posições** (PDF) de um cliente e o **Runflow** da mesa (Excel com
papéis de crédito privado à venda) e indica, posição a posição, se vale trocar o ativo por um do
Runflow, considerando taxa, duration, rating, tributação, liquidez, estoque e custos.

## Regras inegociáveis
1. **Nenhum dado real no repositório.** O repositório é público. Mapa e Runflow reais
   entram só por upload na hora do uso, ficam na memória do navegador e nunca são gravados em
   disco, enviados a servidor ou logados.
2. Só existem no repositório **dados fictícios** em `data/samples/`, gerados por
   `scripts/make_samples.py`, no mesmo layout dos reais (emissores e códigos fictícios; nenhum
   nome de cliente, agência ou conta).
3. `.gitignore` bloqueia `*.pdf, *.xlsx, *.xls, *.csv, *.txt` fora de `data/samples/` e `data/public/`.
4. **CI de privacidade** (`tests/test_privacy.py` + workflow `tests.yml`): falha se houver arquivo
   de dados fora das pastas permitidas, ou se qualquer arquivo versionado contiver as frases de
   marcação de confidencialidade, nomes de colunas internas do Runflow ou nome de instituição
   (lista exata em `tests/test_privacy.py`; sem diferenciar acento), ou um padrão de
   agência/conta do tipo "Ag" + 4 dígitos + "/" + dígitos.
5. **Sem robôs de coleta** para ANBIMA e B3 (termos de uso proíbem). Automatizar apenas fontes
   abertas: BCB SGS, BCB Focus (Olinda) e Tesouro Transparente.
6. **Dois modos de saída:** *interno* (pode mostrar as colunas internas do Runflow — receita
   estimada da mesa, ganho máximo de taxa, comparativos com outras plataformas e suas diferenças — e o
   lastro disponível) e *cliente* (remove essas colunas e qualquer menção ao Runflow interno).
   Teste automatizado garante que o export em modo cliente não tem colunas internas.
   **Os nomes reais dessas colunas e qualquer nome de instituição ficam só em
   `config/runflow_columns.local.toml` (fora do git).** No repositório, só
   `config/runflow_columns.example.toml`, com nomes genéricos, usado pelas amostras.
7. **O fee da mesa nunca entra no ranking nem na classificação.** Ordenar só pela economia do cliente.
8. Telemetria do Streamlit desligada (`gatherUsageStats = false` em `.streamlit/config.toml` e no
   `streamlitConfig` do stlite em `web/index.html`).
9. A tela de Metodologia e o README avisam: ferramenta analítica, não constitui recomendação de
   investimento; limiares de classificação são hipóteses ainda não validadas por backtest.
10. Ao ler o Mapa, **descartar nome do cliente, agência e conta** logo no parser; esses campos não
    existem no modelo de dados.

Outras preferências do dono do projeto: interface, docs e commits em português do Brasil; **nunca
dar `git push` sem perguntar**; não usar marca/logo de banco na interface (os rótulos de tela das
colunas internas também vêm do config local).

## Escopo do MVP (decisões do dono, 07/11/2026)
- **ANBIMA e B3 fora do MVP: sem leitores.** Entradas: Mapa (PDF) e Runflow (XLSX).
- **Taxa de mercado e duration das posições** (`enrich.py`):
  1. código no Runflow → duration e fluxo (Cupom/Amortização) do Runflow;
  2. senão → fluxo padrão (juros semestrais, amortização no vencimento);
  3. nos dois casos a taxa y resolve PU(y)/PU(taxa_op) = PU Mercado/PU Curva com o mesmo fluxo
     (VNA se cancela; o PU Curva é o PU na taxa de operação — conferido no Mapa real) e sai
     marcada "taxa estimada"; sem Runflow a duration sai do mesmo cálculo;
  4. o usuário pode sobrescrever cupom, amortização, duration ou taxa (`Override`, tela Carteira);
  5. Taxa de Compra do Runflow só como fallback, marcada "aproximação";
  6. lotes do mesmo código devem dar a mesma taxa: divergência > 10 bps -> alerta
     "verificar PU Curva/fluxo";
  7. modo interno: spread estimado da mesa = taxa estimada − Taxa de Compra; > 150 bps marca a
     posição para revisão (nunca no modo cliente, nunca no ranking).
- **Dados públicos:** `update-data.yml` (dias úteis 20h BRT + manual + chamado pelo `pages.yml`)
  coleta e publica os JSON enxutos JUNTO com o site, **sem commit na main**; `data/public/` no
  repositório é só a reserva. O app mostra a data da coleta e alerta se > 3 dias úteis.
- Premissa "amortização no vencimento" tem erro conhecido (ver `docs/FASE2_RELATORIO.md`).

## Stack
- Python ≥ 3.12 (CI testa 3.12 e 3.13). Núcleo em `src/cpsim` com funções puras, sem Streamlit,
  tipado (dataclasses), testado com pytest.
- Interface Streamlit em `app/`, rodando no navegador via **stlite** (Pyodide), publicada no
  GitHub Pages a partir de `web/index.html` (montado em `_site/` por `scripts/build_site.py`).
  O mesmo app roda localmente com `streamlit run app/app.py`.
- Dependências compatíveis com Pyodide: numpy, pandas, openpyxl, pypdf. **Sem scipy** (decisão
  aprovada na Fase 0: acrescenta ~10–20 s ao carregamento); raízes (taxa implícita no PU) com
  Brent/Newton em Python puro.
- stlite **1.12.0** fixado (Pyodide 314, Python 3.14, pandas 3) — decisão aprovada na Fase 0, por
  corrigir travamento de apps multipágina. Código compatível com Python ≥ 3.12. Versões locais fixas
  em `pyproject.toml`; no navegador valem as versões da distribuição Pyodide da versão do stlite
  fixada em `web/index.html` (a tela da Fase 0 mostra as duas).
- `fpdf2` só para gerar amostras (não roda no navegador).

## Comandos
```bash
python -m pip install -e ".[dev]"          # ambiente local
pytest                                       # testes (inclui privacidade)
streamlit run app/app.py                     # app local
python scripts/make_samples.py               # regenera data/samples/
python scripts/build_site.py                 # monta _site/ (o que vai para o Pages)
python scripts/build_site.py --serve         # monta e serve: http://localhost:8790 (testa o stlite)
```
Para testar outra versão do stlite sem editar nada: `http://localhost:8790/?stlite=1.11.0`.

## Convenções
- Dias úteis base 252, calendário de feriados nacionais por regra (`calendar.py`).
- Taxas em **decimal** internamente (0.1437); exibição em % com vírgula ("14,37%").
- Separar sempre **dado**, **estimativa** e **aproximação** (ex.: `fluxo_aproximado=True`,
  "taxa de varejo" para Tesouro Direto).
- Colunas do Runflow localizadas **pelo nome normalizado** do cabeçalho, nunca pela letra.
- Mapa real (calibrado por estrutura em 07/11/2026): cada palavra é um fragmento, células
  alinhadas ao topo, espaços de kerning em números/códigos. `data/samples/mapa_posicoes_layout_real.pdf`
  reproduz essa estrutura com dados fictícios; os testes usam as duas amostras.
- Toda fórmula segue `docs/metodologia.md` (citar a seção no docstring). Desvio só com justificativa.
- Trabalho por fases: ao fim de cada fase, testes + commit local + resumo, e parar para aprovação.
