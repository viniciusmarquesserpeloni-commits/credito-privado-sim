# Fase 1 — Relatório do núcleo de cálculo

Data: 07/11/2026. **138 testes passando; cobertura do núcleo 97%** (meta: 80%).

## O que foi feito

| Módulo | Conteúdo | Metodologia |
|---|---|---|
| `models.py` | `Lot`, `Position`, `MapaPositions`, `Candidate`, `RunflowData`, `Rate`/`Indexer`, `Rating` (escala ordinal, grafias AAA/brAAA/AAAbr/AA+.br/Aa1/sf/exp), `Sourced`/`Kind` (dado, estimativa, aproximação) | 10.5 |
| `calendar.py` | Feriados nacionais por regra (fixos, Carnaval, Sexta-feira Santa, Corpus Christi, 20/11 desde 2024), dias úteis [d0, d1), du/252 | 4.1 |
| `rates.py` | Conversões diária/anual, %CDI sobre a taxa diária, CDI + s multiplicativo, Fisher, inflação implícita, spread multiplicativo, taxa nominal esperada por indexador, diferença de taxa no mesmo indexador | 4.3, 4.7, 4.10 |
| `pricing.py` | PU, duration de Macaulay e modificada, convexidade, DV01, aproximação por duration e convexidade, taxa a partir do PU (Brent em Python puro, sem scipy), decomposição do retorno no horizonte | 4.1, 4.5, 4.7 |
| `cashflows.py` | Fluxo **aproximado** a partir dos textos de Cupom e Amortização ("Mai/Nov", "Mensal", "Anual (Início 2037)", "Semestral (Início Set 26)"…); texto não reconhecido → sem fluxo + alerta | prompt 5.1 |
| `taxes.py` | IR e IOF regressivos e isenção como **parâmetros** ("confirmar vigência"), imposto antecipado, gross-up | 4.12, 10.2 |
| `spreads.py` | Spread sobre NTN-B, escolha da NTN-B de referência (B-ref do Runflow ou menor diferença de duration), DTS, breakeven, PD implícita, custo de saída, prazo de equilíbrio | 3.1, 4.3, 4.6, 4.8, 4.9, 4.11, 10.3 |
| `parsers/mapa_pdf.py` | Leitor tipado, **calibrado na estrutura do Mapa real** | 10.5 |
| `parsers/runflow_xlsx.py` | Leitor tipado; colunas internas vindas de `config/` | 10.5 |
| `config.py` | Nomes das colunas internas: arquivo local (fora do git) → exemplo | — |

**Casos-ouro** (`tests/test_golden.py`), todos batendo com o documento: prefixado de 3 anos
(PU 97,64; D_Mac 2,69; D_mod 2,38; C 8,09; DV01 0,0232 e a tabela de choques de ±100 e +300 bps);
spread de 56 bps sobre a NTN-B; retornos de CDI+ em 12 meses (14,70%, 15,60% e 12,30%);
breakeven de 11,7 bps; PD implícita de 2,5%; custo de saída de 0,40%; gross-up para IPCA + 9,86%;
exemplo de troca (custo total 1,46%, equilíbrio em 1,8 ano; se isento, 0,80% e 1 ano).

## Calibragem com o Mapa real

Lido localmente e **só por estrutura**: o texto foi mascarado (letras → A, dígitos → 9) antes de
aparecer em qualquer saída, e nada do arquivo foi para o repositório.

**Resultado:** 3 páginas, 24 lotes, 23 posições, **0 lotes com erro**, data da posição lida, sem
dado do cliente no resultado.

| Achado no PDF real | Tratamento |
|---|---|
| Cada palavra é um fragmento separado, inclusive nos cabeçalhos ("PU" + "Operação") | Colunas montadas casando as palavras com os rótulos conhecidos |
| Células alinhadas ao **topo**, com espaço entre linhas da tabela | Detecção automática do alinhamento; ao topo, linhas por faixa; ao meio (amostra antiga), partição ótima |
| Espaços de kerning dentro de números, taxas, datas e códigos ("9 . 99%", "99 . 999,99", código partido) | Normalização antes de converter |
| Rodapé "Data posição: … x de y" numa linha e nota iniciada por "*" | Rodapé por linha reconstruída; a nota não vaza mais para a última linha da página |
| O Valor Bruto difere de Qtd × PU em até ~0,001% (o banco usa o PU com mais casas do que exibe) | Tolerância = o maior entre 1 centavo por unidade e 0,005% do valor |
| Em CPRs sem PU Mercado, o Valor Líquido vem 4–5% abaixo do Bruto, com IR e IOF zerados | Vira **aviso**, não erro (é critério do arquivo; CPR sem preço fica fora da análise) |

A nova amostra fictícia `data/samples/mapa_posicoes_layout_real.pdf` reproduz essa estrutura, sem
dado real; os testes rodam nas duas amostras.

**Tempo:** o Mapa real de 3 páginas leva 2,3 s localmente, quase todo na extração do pypdf
(o código do simulador leva ~0,1 s). No navegador deve ser algumas vezes mais lento. Se a espera
incomodar na Fase 3, a alternativa é extrair o texto com pdf.js (o plano B da Fase 0).

## Ajuste de privacidade (pedido nesta fase)

- Os nomes reais das colunas internas do Runflow e dos nomes de instituição saíram do código, dos
  documentos e das amostras. Ficam em `config/runflow_columns.local.toml`, fora do git; já criei
  esse arquivo na sua máquina com os nomes do prompt.
- No repositório só fica `config/runflow_columns.example.toml`, com nomes genéricos. Ele é usado
  pelas amostras e é o único publicado no site; o `build_site` recusa `*.local.toml`.
- No navegador, a tela aceita o upload do `.toml` local, que fica só na memória.
- O CI de privacidade agora barra também o nome da instituição e os nomes das duas colunas internas
  pedidos (lista em `tests/test_privacy.py`), sem diferenciar acento nem maiúsculas. Na primeira
  rodada ele pegou uma descrição no CLAUDE.md e um trecho deste relatório, e os textos foram trocados.
- **O histórico do git ainda tem os nomes antigos**, nos 3 commits locais da Fase 0. Como nada foi
  enviado, a proposta é recriar o histórico limpo antes do primeiro push.

## Decisões e desvios para a Fase 2

1. **Taxa implícita de IPCA+ sem VNA (desvio do prompt 6.1, passo 2).** Por definição, o PU Curva é
   o fluxo descontado à taxa de aquisição (metodologia 10.1). A razão PU Mercado / PU Curva elimina
   a escala do VNA, então dá para achar a taxa implícita sem ele. O resultado sai marcado como
   *estimativa*. Os lotes do mesmo papel servem de checagem cruzada. Proposta: usar na Fase 2.
2. **Custo de entrada.** O exemplo 10.3 soma saída e entrada, mas o prompt 6.3 (cenário B) cobra
   só a saída, porque a taxa de compra do Runflow já embute a entrada. A Fase 2 segue o prompt; o
   caso-ouro 10.3 continua testado pelas funções básicas.
3. **ANBIMA e B3 ainda sem leitor:** faltam arquivos reais para confirmar o layout (prompt 5.3).
