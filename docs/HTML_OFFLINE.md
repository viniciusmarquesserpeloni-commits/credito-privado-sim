# Versão offline (um único HTML) e novo visual

Data: 09/11/2026.

## Por quê

A empresa pode bloquear o endereço do GitHub Pages, e a versão Streamlit (stlite) baixa o Python
e os pacotes de CDNs (~30 MB) a cada abertura, o que também pode ser bloqueado. A versão offline
é **um único arquivo `.html` (~2,5 MB)** que abre com duplo clique no Edge ou no Chrome, **sem
internet e sem servidor**. Os arquivos do usuário são lidos só no navegador.

## Onde está

- **Gerar localmente:** `python scripts/build_offline.py` → `dist/simulador_credito_privado.html`
  (fora do git). Para embutir os dados públicos do dia, rode antes `python scripts/update_public_data.py`.
- **Site:** o workflow de dados públicos publica o arquivo em
  `…/credito-privado-sim/simulador_credito_privado.html`, atualizado todo dia útil, e o rodapé do
  app Streamlit tem o link para baixar.

## Como funciona

| Parte | Arquivo | Observação |
|---|---|---|
| Motor | `offline/src/engine.mjs`, `parsers.mjs`, `analysis.mjs` | Porte do núcleo Python, função por função. **O Python continua sendo a referência.** |
| Leitura do PDF | pdf.js 6.4.299 (`offline/vendor/pdfjs`, Apache-2.0) embutido | Mesmo resultado do pypdf no Mapa real (24 lotes, mesmos números e códigos), com o título e o emissor até mais limpos (sem espaços de kerning). |
| Leitura e escrita de Excel | `offline/src/xlsx.mjs` | Sem biblioteca: descompactação nativa do navegador e `.xlsx` gravado sem compressão. |
| Interface | `offline/src/ui.mjs`, `styles.css`, `index.template.html` | Visual do painel "Relatório de Fundos"; modos interno e cliente; export Excel. |
| Montagem | `scripts/build_offline.py` | Junta tudo num arquivo; embute os dados públicos, as amostras fictícias e o config de **exemplo**. Nunca embute `*.local.toml` nem arquivo real. |

Os dados públicos (CDI, Focus, Tesouro Direto) ficam **embutidos** no arquivo e envelhecem. A aba
Dados mostra a data da coleta e avisa acima de 3 dias úteis; dá para usar o cenário do usuário em
Parâmetros ou gerar o HTML de novo.

## Conferência JS × Python

`scripts/make_js_fixtures.py` grava os resultados do Python em `offline/tests/fixtures.json`, e
`cd offline && npm test` confere o motor JS contra eles. O CI faz os dois e falha se a referência
estiver desatualizada. A conferência cobre:

- calendário, casos-ouro da metodologia e fluxos aproximados;
- leitura das duas amostras do Mapa (pdf.js × pypdf) e do Runflow (leitor próprio × openpyxl);
- curvas (Focus, NTN-B);
- três cenários completos de troca: classificações, ganhos, custos, justificativas, resumo e
  colunas do modo cliente.

Ao portar, apareceram três textos do Python com ponto decimal no lugar da vírgula ("4.02",
"CDI 14.00%", "2,500,000"). Foram corrigidos nos dois motores.

**Verificado:**

- o HTML aberto direto do disco (`file://`) no Edge, sem servidor;
- com as amostras, os mesmos números do site publicado: 4 trocas recomendadas, 1 marginal, 6
  manter, ganho anual de R$ 6.971,58;
- o modo cliente sem colunas internas, lastro, spread da mesa ou menção ao Runflow, conferido
  pelo texto renderizado de todas as abas;
- sem rolagem horizontal em 1.280 px nem em 375 px.

## Regra de manutenção

Mudou fórmula, leitor ou texto de saída no Python? Mude o mesmo no `offline/src/`, rode
`python scripts/make_js_fixtures.py` e `cd offline && npm test`.

## Novo visual (as duas versões)

Cores, tipografia e componentes do painel "Relatório de Fundos": faixa petróleo com marca e
pílulas (posição, dados públicos, modo), abas com sublinhado verde-lima, cartões brancos de KPI,
chips e tabelas compactas.

- **HTML offline:** visual copiado do painel.
- **Streamlit:** aproximação via tema e CSS. A navegação foi para o topo, a barra lateral saiu e as
  métricas viraram cartões. As tabelas internas do Streamlit (canvas) não aceitam o mesmo estilo.
