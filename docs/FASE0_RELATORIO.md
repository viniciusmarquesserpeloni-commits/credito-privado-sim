# Fase 0 — Relatório do teste técnico

Data: 07/11/2026. Ambiente: Windows 11, Python 3.13 local; navegador do app Claude (Chromium).

## Resumo

| Item | Resultado |
|---|---|
| App mínimo em stlite (Streamlit no navegador) | ✅ funciona localmente (`scripts/build_site.py --serve`). **Publicação no GitHub Pages pendente**: precisa criar o repositório e dar push (aguardando aprovação). |
| Leitura do **PDF** de amostra dentro do navegador (pypdf) | ✅ 26 linhas, 2 páginas, 0 erros, data da posição lida. Via upload real (campo de upload), não só arquivo embutido. |
| Leitura do **XLSX** de amostra dentro do navegador (openpyxl) | ✅ 24 papéis, colunas localizadas por nome, coluna extra ignorada. |
| Plano B (pdf.js) | **Não necessário.** |
| Tempo de carregamento | ver tabela abaixo (≈ 25–35 s na primeira tela; números de aba em segundo plano). |
| Endpoints públicos | ✅ BCB SGS (12, 432, 433), BCB Focus/Olinda (Selic por reunião, IPCA anual e 12 meses), Tesouro Transparente (CSV do Tesouro Direto). `scripts/check_endpoints.py` repete a checagem. |
| `make_samples.py` | ✅ Mapa PDF e Runflow XLSX fictícios, determinísticos (mesmo arquivo a cada geração). |
| Privacidade | ✅ `.gitignore` + `tests/test_privacy.py` + workflow `tests.yml`. Nenhuma requisição de envio de dados observada na rede durante o upload. |
| Arquivo **real** (Mapa/Runflow/ANBIMA) | ⏳ não testado — depende de você (ver "Próximos passos"). |

## Versões no navegador

| stlite | Pyodide | Python | Streamlit | pandas | numpy | openpyxl | pypdf | scipy |
|---|---|---|---|---|---|---|---|---|
| **1.12.0** (fixado) | 314.0.3 | 3.14.2 | 1.65.0 | 3.0.2 | 2.4.3 | 3.1.5 | 6.21.4 | 1.18.0 |
| 1.11.0 (comparação) | 0.29.3 | 3.13.2 | 1.65.0 | 2.3.3 | 2.2.5 | 3.1.5 | 6.21.4 | — |

As versões locais em `pyproject.toml` foram fixadas iguais às do stlite 1.12.0.

## Tempo de carregamento (até a primeira tela desenhada)

Medido pelo próprio `index.html` (`window.__cpsimLoad`, também no console como `[cpsim] app pronto em …`).
**Atenção:** o painel do navegador estava oculto (aba em segundo plano, que o Chromium desacelera),
então trate como teto, não como média.

| Cenário | Tempo |
|---|---|
| stlite 1.12.0, primeira visita (cache vazio) | 24,1 s |
| stlite 1.12.0, recarregando (2 medições) | 35,4 s / 35,7 s |
| stlite 1.11.0, primeira visita | 28,9 s |
| stlite 1.12.0 **+ scipy** | 46,6 s |

Leitura dentro do navegador, já carregado: PDF 0,3 s (2,1 s na primeira vez, que inclui importar o
pypdf); XLSX 1,1 s.

## Decisões e desvios

> **Aprovadas em 07/11/2026:** itens 1 (stlite 1.12.0) e 2 (sem scipy; já removido do
> `pyproject.toml` e do app). Itens 3–5 seguem como descrito.

1. **Python 3.12 não existe no navegador.** Nenhuma versão atual do stlite roda 3.12: a 1.11.0 usa
   3.13 e a 1.12.0 usa 3.14. O código mira Python ≥ 3.12 e o CI testa 3.12 e 3.13.
   **Fixei o stlite 1.12.0** porque ele corrige um travamento de apps com várias páginas (o nosso
   terá 5) e traz o pyarrow oficial. O custo é usar o pandas 3, fixado também localmente.
   Alternativa: 1.11.0 (pandas 2.3, Python 3.13), mas sem essa correção.
2. **scipy acrescenta ~10–20 s ao carregamento.** Proposta: não usar scipy no app. O único uso
   previsto é achar raiz (taxa implícita no PU), que dá para fazer em Python puro (Brent/Newton) em
   poucas linhas. Ele fica fora dos pacotes do navegador; se você concordar, sai também do `pyproject`.
3. **`docs/metodologia.md` ainda não existe** (há um marcador). Preciso dele antes da Fase 1 para
   conferir as fórmulas e os casos-ouro.
4. **Colunas internas do Runflow:** os nomes reais (receita da mesa, comparativos com outras
   plataformas) foram movidos para `config/runflow_columns.local.toml`, fora do git (ajuste pedido
   na Fase 1). O repositório só tem `config/runflow_columns.example.toml`, com nomes genéricos.
5. **pypdf vem do PyPI na hora do carregamento** (os demais pacotes vêm da CDN do Pyodide). Na
   Fase 3 dá para servir o arquivo do pacote pelo próprio Pages e tirar essa dependência.

## O que o teste revelou sobre a leitura do PDF

- Um leitor "por linhas de texto" não basta: células altas (Título, Emissor com 3 a 6 linhas) **encostam
  nas vizinhas sem espaço entre elas**. O leitor usa a posição (x, y) de cada fragmento, as colunas
  do cabeçalho e uma partição ótima das linhas de cada coluna por linha da tabela (funciona com
  alinhamento ao meio ou ao topo). O Título usa o marcador de fim " - CÓDIGO".
- Cabeçalho com palavra quebrada ("Quantida" / "de") e com duas linhas ("Valor Bruto" / "(curva)")
  já é tratado.
- Limitação conhecida: quando o PDF quebra **dentro** de uma palavra ("SECURITIZADOR" / "A"), o texto
  sai com um espaço a mais. Não afeta código, taxa nem valores; o emissor também pode vir do Título
  e do Runflow.
- **Tudo isso foi calibrado só na amostra fictícia.** O layout real pode ter alinhamento diferente
  (números à direita, por exemplo). É o principal risco que falta eliminar.

## Observações sobre as fontes públicas

- **SGS 12 (CDI):** exige `dataInicial`/`dataFinal` com janela de no máximo 10 anos (sem datas → HTTP 406).
- **SGS 432 (meta Selic):** a série vem preenchida até a próxima reunião do Copom (hoje mostra
  datas de dez/2026). A coleta precisa cortar em "hoje".
- **Focus (Olinda):** OK; filtrar `baseCalculo eq 0`. A última data hoje é 30/10/2026 (publicação semanal).
- **Tesouro Transparente:** CSV único de 14,6 MB com todo o histórico (`;`, vírgula decimal, latin-1,
  data-base D-1). A coleta vai guardar só os dias recentes em `data/public/`.

## Próximos passos

1. **Você:** testar os arquivos **reais** na versão local do navegador — nada sai da sua máquina:
   rode `python scripts/build_site.py --serve`, abra http://localhost:8790 e envie o Mapa e o Runflow.
   Me diga só o que a tela mostrar (contagens, avisos, colunas ausentes), **sem** colar dados.
   Se preferir, autorize que eu leia o PDF real localmente apenas para calibrar o layout, sem copiar
   nada para o repositório.
2. **Você:** criar o repositório público `credito-privado-sim` no GitHub (vazio) e ativar Pages com
   origem "GitHub Actions"; com o seu OK eu faço o push e confiro o site publicado.
3. **Você:** exportar o documento de pesquisa para `docs/metodologia.md` e me mandar um arquivo ANBIMA
   real (debêntures e CRI/CRA) para confirmar o layout.
4. **Eu, na Fase 1:** `models, calendar, rates, pricing, cashflows, taxes, spreads` + leitores tipados,
   com testes e casos-ouro.
