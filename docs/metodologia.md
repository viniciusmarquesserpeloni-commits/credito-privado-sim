# Simulador de Oportunidades em Crédito Privado — Etapa 1: Pesquisa

*Documento de pesquisa — versão pública para o repositório. Nenhum dado real de clientes ou de instituições. Base da pesquisa: 29/10/2026; atualizado em 07/11/2026.*

## 1. Resumo executivo

**Conclusão central:** não existe na literatura um modelo único e validado que diga "compre" ou "venda" um título de crédito privado. Existe, porém, um arcabouço teoricamente sólido e implementável: **decompor o retorno esperado do título em seus componentes, ajustá-lo por perda esperada, liquidez e impostos, e compará-lo com alternativas sob cenários explícitos.** É isso que o simulador deve fazer.

Principais achados:

1. **Retorno esperado, não taxa.** O retorno de um título no horizonte *h* se decompõe em carrego + rolldown + variação da curva base + variação do spread − perda de crédito − custos. Essa identidade é contábil (não é hipótese), e é a espinha dorsal recomendada.
2. **Spread não é só risco de default.** A literatura internacional mostra que boa parte do spread corporativo remunera liquidez, impostos e prêmio de risco sistemático, não perda esperada ([Elton et al., 2001](https://ideas.repec.org/a/bla/jfinan/v56y2001i1p247-277.html); [Huang & Huang, 2012](https://ideas.repec.org/a/oup/rasset/v2y2012i2p153-202..html); [Longstaff et al., 2005](https://www.nber.org/papers/w10418)). No Brasil, a isenção de IR das incentivadas, CRIs e CRAs adiciona uma distorção tributária que precisa ser neutralizada antes de comparar papéis.
3. **Valor relativo tem evidência, mas fora do Brasil.** Medidas de spread "barato" em relação ao risco geram retorno excedente em crédito americano ([Correia, Richardson & Tuna, 2012](https://ideas.repec.org/a/spr/reaccs/v17y2012i3d10.1007_s11142-012-9191-x.html); [Israel, Palhares & Richardson, 2018](https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/Common-Factors-in-Corporate-Bond-Returns.pdf); [Houweling & van Zundert, 2017](https://papers.ssrn.com/abstract=2516322)). Não encontrei estudo equivalente publicado para debêntures brasileiras: **a eficácia aqui é hipótese a testar, não fato.**
4. **A decisão de venda é prospectiva.** O retorno futuro de manter um título é aproximadamente a taxa de mercado atual (mais efeitos de curva e spread), e não a taxa de aquisição. O lucro acumulado é irrelevante para a decisão, exceto pelo imposto que a venda antecipa.
5. **ANBIMA é a espinha dorsal de dados.** Taxas indicativas, curvas de crédito e ETTJ são públicas no dia, mas o histórico profundo é pago (ANBIMA Feed). BCB, Tesouro e CVM são gratuitos. Ratings e dados granulares de CRI/CRA são restritos.
6. **Classificação por regras, não por pontuação.** A recomendação é classificar com base em quantidades mensuráveis (excesso de retorno ajustado, spread residual vs. pares, spread de equilíbrio), com limiares calibrados e validados por backtest. Até a validação, o simulador deve se apresentar como ferramenta analítica, não de recomendação.

**Principal risco do projeto:** a taxa indicativa da ANBIMA é, em boa parte, resultado de uma pesquisa de cotações, não de negócios executados. Um backtest feito sobre ela mede o modelo contra a ANBIMA, não contra preços em que se consegue de fato comprar ou vender.

## 2. Revisão da literatura acadêmica

A literatura sustenta três blocos do simulador (curva, spread e liquidez) e dá evidência empírica, quase toda nos EUA, de que medidas de valor relativo e carrego têm algum poder de explicar retornos futuros. A coluna "Tipo" separa **teoria** (modelo derivado de hipóteses econômicas), **empírica** (teste estatístico em dados) e **heurística** (prática de mercado sem teste formal).

### 2.1 Estrutura a termo dos juros

| Referência | Achado | Tipo | Implicação para o simulador |
| --- | --- | --- | --- |
| [Nelson & Siegel (1987)](https://www.nber.org/papers/w1594) | Curva inteira descrita por 3 fatores (nível, inclinação, curvatura) com uma forma funcional parcimoniosa | Teoria/estatística | Base para interpolar curvas e spreads com poucos parâmetros |
| [Svensson (1994)](https://www.nber.org/system/files/working_papers/w4871/w4871.pdf) | Acrescenta uma segunda curvatura ao Nelson-Siegel, melhor ajuste em vencimentos longos | Teoria/estatística | É o modelo da ETTJ ANBIMA (seção 3) |
| [Litterman & Scheinkman (1991)](https://www.gpif.go.jp/investment/20220301_workingpaper_en.pdf) | Três componentes principais explicam quase toda a variação dos retornos de títulos | Empírica | Cenários de curva devem mover nível, inclinação e curvatura, não só choque paralelo *(link: documento que replica e cita o estudo; original no Journal of Fixed Income, não acessado)* |
| [Diebold & Li (2006)](https://www.nber.org/papers/w10048) | Fatores Nelson-Siegel modelados como AR(1) geram previsões razoáveis em horizontes longos | Empírica | Opcional para cenário-base de curva; nunca como previsão pontual |
| [Cochrane & Piazzesi (2005)](https://www.nber.org/papers/w9178) | Combinação de taxas a termo prevê retornos excedentes de títulos; o prêmio de prazo varia no tempo | Empírica | **A curva a termo não é a expectativa pura dos juros futuros**; contém prêmio de prazo |
| [Caldeira, Moura & Santos (2013)](https://papers.ssrn.com/abstract=2311733) | No DI futuro brasileiro, combinações de previsões (AR, Nelson-Siegel, Svensson) superam modelos isolados em vários casos | Empírica (Brasil) | Se houver previsão de curva, usar combinação e avaliar pelo critério econômico |
| [Vicente & Graminho (2014), BCB TD 359](https://www.bcb.gov.br/pec/wps/port/TD359.pdf) | Inflação implícita = expectativa + convexidade + prêmio de risco − prêmio de liquidez; expectativa explica cerca de 60% da variação | Empírica (Brasil) | Inflação implícita não é previsão de IPCA; comparar sempre com Focus |
| [Araujo & Vicente (2017), BCB TD 460](https://www.bcb.gov.br/pec/wps/port/TD460.pdf) | Inflação implícita de curto prazo é competitiva com o Focus como previsor | Empírica (Brasil) | Inflação implícita curta é insumo válido para cenários de IPCA |

### 2.2 Spread de crédito: o que ele remunera

| Referência | Achado | Tipo | Implicação |
| --- | --- | --- | --- |
| [Merton (1974)](https://dspace.mit.edu/handle/1721.1/1874) | Dívida como ativo livre de risco menos uma opção de venda sobre os ativos da firma; spread depende de alavancagem e volatilidade | Teoria (modelo estrutural) | Justifica usar alavancagem e volatilidade do emissor como explicativas do spread |
| [Duffie & Singleton (1999)](https://ideas.repec.org/a/oup/rfinst/v12y1999i4p687-720.html) | Spread = intensidade de default × perda dado default, descontado como taxa ajustada | Teoria (forma reduzida) | Fundamenta a relação spread ≈ PD × LGD (seção 4) |
| [Elton, Gruber, Agrawal & Mann (2001)](https://ideas.repec.org/a/bla/jfinan/v56y2001i1p247-277.html) | Default esperado explica parcela surpreendentemente pequena do spread; impostos e prêmio de risco sistemático explicam o resto | Empírica (EUA) | Spread alto não implica perda esperada alta, nem o inverso |
| [Huang & Huang (2012)](https://ideas.repec.org/a/oup/rasset/v2y2012i2p153-202..html) | Modelos estruturais calibrados explicam só parte do spread em ratings altos ("credit spread puzzle") | Teoria + empírica | Em AAA/AA, o spread é dominado por fatores não ligados a default |
| [Collin-Dufresne, Goldstein & Martin (2001)](https://ideas.repec.org/a/bla/jfinan/v56y2001i6p2177-2207.html) | Variáveis de crédito explicam pouco das variações mensais de spread; um fator comum de oferta e demanda domina os resíduos | Empírica (EUA) | Spreads de papéis diferentes se movem juntos; o cenário de spread precisa de um fator de mercado |
| [Longstaff, Mithal & Neis (2005)](https://www.nber.org/papers/w10418) | Pelo CDS, a maior parte do spread é default; o componente não-default varia com a liquidez | Empírica (EUA) | Separar componente de liquidez quando possível |
| [Gilchrist & Zakrajšek (2012)](https://www.nber.org/papers/w17021) | O "excess bond premium" (spread além do default esperado) antecipa atividade econômica | Empírica (EUA) | Spread médio de mercado elevado sinaliza apetite a risco baixo, não necessariamente barganha |
| [Christensen (2008), FRBSF](https://www.frbsf.org/research-and-insights/publications/economic-letter/2008/03/corporate-bond-credit-spread/) | Resumo do "credit spread puzzle": mais da metade da variação dos spreads não se liga à saúde do emissor | Revisão | Reforça o uso de comparação entre pares em vez de modelo absoluto |
| [Sheng & Saito (2005)](https://pesquisa-eaesp.fgv.br/sites/gvpesquisa.fgv.br/files/arquivos/sheng_-_determinantes_da_spread_da_debentures.pdf) | Em 138 debêntures (1999–2002), rating afeta o spread; setor e volume são controles relevantes | Empírica (Brasil) | Pares devem ser definidos por rating, setor e tamanho; amostra antiga |

### 2.3 Liquidez

| Referência | Achado | Tipo | Implicação |
| --- | --- | --- | --- |
| [Amihud (2002)](https://archive.nyu.edu/handle/2451/27420) | Iliquidez medida como retorno absoluto dividido pelo volume; iliquidez é precificada | Empírica (ações) | Adaptável a debêntures com dados de negócios da B3 |
| [Bao, Pan & Wang (2011)](https://dspace.mit.edu/handle/1721.1/75381) | Iliquidez medida pela autocovariância negativa dos preços explica parte relevante dos spreads | Empírica (EUA) | Exige série de negócios diários; aplicável só aos papéis mais negociados |
| [Dick-Nielsen, Feldhütter & Lando (2012)](https://research-api.cbs.dk/ws/files/58847171/corporate_bon_liquidity_david_lando.pdf) | Componente de liquidez do spread aumentou muito na crise de 2008, mais em ratings baixos | Empírica (EUA) | Custo de liquidez deve ser dependente do regime (estresse) |
| [Giacomoni & Sheng (2013)](https://eaesp.fgv.br/sites/default/files/legacy/pesquisa-eaesp-files/arquivos/sheng_-_o_impacto_da_liquidez.pdf) | Em 101 debêntures (2006–2009), prêmio de liquidez significativo em 3 de 7 medidas, mas pequeno | Empírica (Brasil) | No Brasil, a evidência de prêmio de liquidez é fraca e antiga; tratar como custo de saída, não como fonte de retorno |

### 2.4 Valor relativo, carrego e fatores em crédito

| Referência | Achado | Tipo | Implicação |
| --- | --- | --- | --- |
| [Correia, Richardson & Tuna (2012)](https://ideas.repec.org/a/spr/reaccs/v17y2012i3d10.1007_s11142-012-9191-x.html) | Comparar spread de mercado com risco de default estimado por fundamentos gera retornos excedentes | Empírica (EUA) | Base teórica do "spread residual" do módulo B |
| [Israel, Palhares & Richardson (2018)](https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/Common-Factors-in-Corporate-Bond-Returns.pdf) | 1997–2015, EUA: value (Sharpe 1,80), defensivo (1,21), momentum (1,12) e carry (0,19) em carteiras long-short | Empírica (EUA) | Value é o fator mais forte; carry isolado é fraco. Long-short não é replicável por PF no Brasil |
| [Houweling & van Zundert (2017)](https://papers.ssrn.com/abstract=2516322) | Fatores tamanho, baixo risco, valor e momentum têm alfa em crédito, mesmo com custos | Empírica (EUA/Europa) | Reforça valor e baixo risco como critérios |
| [Koijen, Moskowitz, Pedersen & Vrugt (2018)](https://econbiz.de/Record/carry-koijen-ralph/10011968803) | Carrego prevê retornos em várias classes, inclusive títulos, mas com risco de queda em crises | Empírica (multiclasse) | Carrego é componente, não sinal suficiente |
| [Ben Dor et al. (2007), DTS](https://robeco.com/en-us/insights/2024/09/duration-times-spread-measuring-credit-risk) | Variações de spread são proporcionais ao nível; risco medido por duration × spread | Empírica (gestora/Lehman) | Cenários de spread em termos relativos (%), não em bps fixos *(fonte: resumo da Robeco; artigo original não acessado)* |

### 2.5 Livros-texto de referência (fundamentação das fórmulas)

- Fabozzi, *Bond Markets, Analysis, and Strategies* e *The Handbook of Fixed Income Securities*: preço, yield, duration, convexidade, spreads (Z-spread, OAS).
- Tuckman & Serrat, *Fixed Income Securities*: DV01, carry e rolldown, valor relativo em curva.
- [Martellini, Priaulet & Priaulet, *Fixed-Income Securities*](https://www.wiley-vch.de/en/areas-interest/finance-economics-law/fixed-income-securities-978-0-470-85277-4): modelagem da curva (Nelson-Siegel/Svensson), estratégias e cenários de curva.
- Hull, *Options, Futures, and Other Derivatives* e *Risk Management and Financial Institutions*: PD implícita no spread, risco de crédito, VaR.
- [Ilmanen, *Expected Returns* (Wiley, 2011)](https://www.oreilly.com/library/view/expected-returns-an/9781119990772/): prêmio de prazo, prêmio de crédito e por que yield ≠ retorno esperado.

### 2.6 O que a literatura **não** responde

- Não há estudo publicado que encontrei testando estratégias de valor relativo em debêntures, CRIs e CRAs brasileiros no mercado secundário, com custos reais.
- Os estudos brasileiros de spread e liquidez cobrem períodos anteriores a 2010, antes do crescimento das incentivadas e da precificação diária em larga escala pela ANBIMA.

## 3. Metodologias utilizadas pelo mercado

No Brasil, a referência de preço justo do crédito privado é a taxa indicativa da ANBIMA, e a referência de spread é a curva de crédito ANBIMA por rating. Gestores constroem sobre elas análises de valor relativo, carrego e cenários. As regras abaixo foram lidas nos documentos oficiais; versões indicadas.

### 3.1 Taxa indicativa ANBIMA (debêntures, CRI, CRA)

Fonte: [Metodologias ANBIMA de Precificação de CRA e CRI, nov/2025](https://www.anbima.com.br/data/files/11/C7/38/7D/16FBC91067D089C9BA2BA2A8/Metodologias_ANBIMA_de_Precificacao_CRA_CRI.pdf) e [Metodologias ANBIMA de Precificação, mai/2021](https://www.anbima.com.br/data/files/5D/92/EC/E7/E82F971013C70F976B2BA2A8/Metodologias-ANBIMA-de-precificacao.pdf).

- **Insumos:** cotações enviadas diariamente por instituições contribuidoras (até 18h30), negócios registrados no REUNE e *calls* de corretoras. Divulgação até 20h.
- **Forma de cotação por indexador:** DI como % do DI ou spread sobre DI; IPCA como pontos sobre a NTN-B de duration mais próxima, convertidos em taxa pelo método multiplicativo; prefixado como taxa nominal.
- **NTN-B de referência:** a de menor diferença absoluta de duration. Não há interpolação entre NTN-Bs. Troca de referência por movimento de taxa exige teste de 5 dias.
- **Ponderação (CRI/CRA, nov/2025):** Taxa indicativa = 0,50 × média de coleta + 0,35 × negócios d0 + 0,10 × negócios d−1 + 0,05 × negócios d−2. Sem negócios válidos, todo o peso vai para a coleta.
- **Negócios válidos:** fora do mesmo conglomerado, e (i) 3 ou mais negócios acima de R$ 500 mil, ou (ii) 1 a 2 negócios acima de R$ 950 mil dentro do filtro estatístico.
- **Filtros de outliers:** box plot (Q1 − 1,5×IQR; Q3 + 1,5×IQR) e teste t a 1%; mínimo de 3 observações após filtros.
- **Elegibilidade (CRI/CRA, nov/2025):** negócios em pelo menos 4 dias no mês, em 2 de 3 meses, tickets a partir de R$ 100 mil, vencimento acima de 1 ano, lastro de devedor único, indicação de 5 instituições.

**Implicação:** só uma fração do estoque é precificada (a ANBIMA noticia [mais de 600 debêntures acompanhadas por dia](https://www.anbima.com.br/pt_br/noticias/precificacao-de-debentures-ultrapassa-a-marca-de-600-ativos-acompanhados-por-dia.htm)). Papéis ilíquidos ficam fora, e a taxa de papéis pouco negociados reflete sobretudo cotações, não negócios.

### 3.2 Curvas de crédito ANBIMA

Fonte: [Credit curves – Methodology, out/2021](https://www.anbima.com.br/data/files/EC/77/C1/4F/67CFD71028DFACD76B2BA2A8/Metodologia_Curva%20de%20Credito_out21_ingles.pdf).

- Curvas de spread para AAA, AA e A, com rating atribuído pelo Comitê de Precificação da ANBIMA (não há padronização entre agências).
- Insumos: debêntures DI e IPCA precificadas diariamente; exclui papéis com opções de resgate ou amortização antecipada e vencimentos até 21 dias úteis.
- Modelo: Nelson-Siegel sem curvatura para o spread, com nível próprio por rating e inclinação comum; estimação por mínimos quadrados ponderados por 1/duration.
- Aviso no [site da ANBIMA (17/03/2026)](https://www.anbima.com.br/pt_br/informar/precos-e-indices/curvas/curvas-de-credito.htm): as curvas passam a ficar exclusivamente no ANBIMA Data.

### 3.3 ETTJ ANBIMA (curvas soberanas nominal, real e inflação implícita)

Fonte: [ETTJ – Metodologia, ago/2021](https://www.anbima.com.br/data/files/9A/F4/E3/1F/4805B710B0F024B7882BA2A8/est-termo_metodologia_v2021.pdf).

- Modelo de Svensson (6 parâmetros) estimado diariamente sobre títulos públicos, minimizando erros de preço ponderados por 1/duration; otimização por algoritmo genético seguido de refinamento.
- Curvas: prefixada, real (IPCA) e inflação implícita pela identidade de Fisher. O próprio documento alerta que a inflação implícita mistura expectativa e prêmios de risco e liquidez.

### 3.4 Índices de debêntures (IDA)

A família [IDA](https://www.anbima.com.br/informacoes/ida/default.asp) (IDA-DI, IDA-IPCA, IDA-IPCA Infraestrutura, entre outros; [metodologia dez/2023](https://www.anbima.com.br:443/data/files/55/F0/37/0A/9EEFC8104606BDC8B82BA2A8/Metodologia_IDA_dez23.pdf)) mede o retorno de carteiras teóricas marcadas pelas taxas indicativas. Uso no simulador: **benchmark** do backtest e referência de retorno médio do mercado. Há também o [IDA LIQ (metodologia mar/2026)](https://www.anbima.com.br/data/files/AC/50/22/3B/15FBC91067D089C9BA2BA2A8/Metodologia_IDA_LIQ_mar26.pdf), restrito aos papéis mais negociados.

### 3.5 Práticas de gestores e bancos (heurísticas consolidadas)

| Prática | O que faz | Status |
| --- | --- | --- |
| Spread sobre NTN-B / DI de duration equivalente | Isola o prêmio de crédito e liquidez da parte soberana | Padrão de mercado; base da ANBIMA |
| Z-spread | Spread constante sobre a curva zero que reprecifica o fluxo | Padrão internacional (Fabozzi); mais correto que spread sobre um único título |
| Gráfico spread × duration por rating/setor | Identifica papéis acima ou abaixo da curva de pares | Heurística; formalizada aqui como "spread residual" |
| Carrego + rolldown | Retorno no horizonte com curva e spread constantes | Identidade contábil; evidência mista como sinal |
| DTS (duration × spread) | Mede risco de spread de forma comparável entre ratings | Empírico (Ben Dor et al., 2007) |
| Breakeven de spread | Quanto o spread pode abrir antes de anular o carrego extra | Identidade; muito usado em mesas |
| Análise de crédito fundamentalista | Alavancagem, cobertura, liquidez, covenants, garantias | Padrão; sem modelo universal de PD para o Brasil |

**Provedores globais (Bloomberg, MSCI, J.P. Morgan):** usam OAS, spread duration e modelos de risco multifatoriais. Suas metodologias são proprietárias e não foram verificadas nesta pesquisa; o simulador não deve depender delas.

## 4. Modelos matemáticos recomendados

Os modelos abaixo são padrão de livro-texto (Fabozzi; Tuckman & Serrat; Martellini et al.; Hull) ou da metodologia ANBIMA. **Todos os números dos exemplos são hipotéticos**, escolhidos para ilustrar o cálculo, e foram conferidos em Python.

### 4.1 Preço e taxa (convenção brasileira, base 252)

O PU é o valor presente dos fluxos descontados pela taxa do título, com prazo em dias úteis:

```latex
PU = \sum_{i=1}^{n} \frac{FC_i}{(1+r)^{du_i/252}}
```

- FC: fluxo projetado (juros e amortizações). Em IPCA+, os fluxos são reais sobre o VNA; em CDI+, os juros futuros são projetados pela curva DI.
- Variáveis: escritura (fluxo, datas, indexador), VNA, calendário de feriados, curva DI e projeções de IPCA (ANBIMA).

### 4.2 Curva base: Svensson (ETTJ ANBIMA)

```latex
r(t) = \beta_1 + \beta_2\frac{1-e^{-t/\tau_1}}{t/\tau_1} + \beta_3\left(\frac{1-e^{-t/\tau_1}}{t/\tau_1} - e^{-t/\tau_1}\right) + \beta_4\left(\frac{1-e^{-t/\tau_2}}{t/\tau_2} - e^{-t/\tau_2}\right)
```

β1 é o nível de longo prazo, β2 a inclinação, β3 e β4 as curvaturas. **Recomendação:** não reestimar; consumir os parâmetros publicados pela ANBIMA, e usar a curva DI da B3 para o mercado CDI.

### 4.3 Spread de crédito

**Spread sobre a NTN-B de referência (padrão ANBIMA, multiplicativo):**

```latex
s = \frac{1 + r_{deb}}{1 + r_{NTNB}} - 1
```

Exemplo: debênture a IPCA + 7,80%, NTN-B de duration próxima a IPCA + 7,20% → s = 1,078/1,072 − 1 = **0,56% (56 bps)**.

**Z-spread (mais correto, usa a curva inteira):** o spread constante z que iguala o preço de mercado ao fluxo descontado pela curva zero (real para IPCA+, DI para CDI+):

```latex
PU_{mercado} = \sum_{i} \frac{FC_i}{\left[(1+r_{zero}(t_i))(1+z)\right]^{t_i}}
```

É o mesmo desconto da curva de crédito ANBIMA (fator 1/\[(1+REAL)(1+S)\]). Para CDI+ e %CDI, o spread é direto (CDI + s) ou convertido (%CDI → spread equivalente pela curva DI no prazo do título).

### 4.4 Spread residual vs. pares (valor relativo)

Ajusta-se, a cada data, uma curva de spread por grupo de pares *g* (indexador × faixa de rating × opcionalmente setor e tratamento tributário), na forma da curva de crédito ANBIMA:

```latex
S_g(\tau) = \beta_{0,g} + \beta_{1}\frac{1-e^{-\lambda\tau}}{\lambda\tau}
```

```latex
z_j = \frac{s_j - \hat{S}_{g}(D_j)}{\hat{\sigma}_{g}}
```

- s\_j: Z-spread do papel j; D\_j: duration; σ̂\_g: desvio-padrão dos resíduos do grupo.
- Leitura: z\_j > 0 → papel paga mais que pares de mesmo prazo ("barato"); z\_j < 0 → "caro".
- **Cuidado:** resíduo positivo pode ser risco não capturado pelo rating (evento, setor, garantia fraca), e não barganha. Por isso ele não decide sozinho (seção 9).
- Variação recomendada: z-score do próprio spread do papel vs. seu histórico (por exemplo, 252 dias úteis), para a pergunta "o spread do emissor está comprimido?".

### 4.5 Duration, convexidade e DV01

```latex
D_{Mac} = \frac{1}{PU}\sum_i t_i \frac{FC_i}{(1+y)^{t_i}} \qquad D_{mod} = \frac{D_{Mac}}{1+y} \qquad DV01 = D_{mod}\times PU \times 0{,}0001
```

```latex
C = \frac{1}{PU(1+y)^2}\sum_i t_i(t_i+1)\frac{FC_i}{(1+y)^{t_i}} \qquad \frac{\Delta PU}{PU} \approx -D_{mod}\,\Delta y + \tfrac{1}{2}\,C\,(\Delta y)^2
```

Exemplo: prefixado de 3 anos, cupom anual de 12%, taxa de 13% a.a. → PU = 97,64; D\_Mac = 2,69; D\_mod = 2,38; C = 8,09; DV01 = 0,0232 por 100 de face.

| Choque na taxa | Variação exata do PU | Só duration | Duration + convexidade |
| --- | --- | --- | --- |
| +100 bps | −2,34% | −2,38% | −2,34% |
| −100 bps | +2,42% | +2,38% | +2,42% |
| +300 bps | −6,78% | −7,13% | −6,77% |

Títulos CDI+ têm duration de juros próxima de zero (o cupom acompanha o CDI), mas **spread duration** igual ao prazo médio: o risco deles está no spread, não na curva.

### 4.6 Risco de spread: spread duration e DTS

```latex
\frac{\Delta PU}{PU} \approx -D_{s}\,\Delta s \qquad DTS = D_{s} \times s \qquad \frac{\Delta PU}{PU} \approx -DTS \times \frac{\Delta s}{s}
```

A forma relativa (Δs/s) segue a evidência de que spreads altos oscilam mais em bps ([Ben Dor et al., 2007](https://robeco.com/en-us/insights/2024/09/duration-times-spread-measuring-credit-risk)). Permite usar um único choque percentual de spread para papéis de ratings diferentes.

### 4.7 Retorno total esperado no horizonte h (núcleo do simulador)

```latex
E[R_h] \approx \underbrace{y\,h}_{carrego} + \underbrace{D_{mod}\,[\,y(T) - y(T-h)\,]}_{rolldown} - \underbrace{D_{mod}\,\Delta r}_{curva\ base} - \underbrace{D_{s}\,\Delta s}_{spread} + \underbrace{\tfrac{1}{2}C\,(\Delta y)^2}_{convexidade} - \underbrace{PD_h \times LGD}_{perda\ esperada} - \underbrace{c}_{custos}
```

- Carrego: a taxa do próprio título (para CDI+, CDI esperado pela curva DI + spread).
- Rolldown: ganho de o título "descer" a curva de spread e a curva base com a passagem do tempo, se as curvas não mudarem.
- Δr e Δs vêm dos cenários (seção 9), não de previsão pontual.

Exemplo (CDI+, h = 12 meses): CDI esperado de 13,0% pela curva DI, spread de 1,50%, spread duration de 3,0. Carrego = 1,13 × 1,015 − 1 = **14,70%**. Cenário otimista (spread fecha 30 bps): **15,60%**. Base (spread estável): **14,70%**. Pessimista (spread abre 80 bps): **12,30%**. Antes de perda esperada e custos.

### 4.8 Spread de equilíbrio (breakeven)

Quanto o spread pode abrir no horizonte antes de o papel render menos que o título público de mesma duration:

```latex
\Delta s^{*} \approx \frac{s \times h}{D_{s}}
```

Exemplo: spread de 56 bps sobre a NTN-B e spread duration de 4,8 → Δs\* ≈ **11,7 bps em 12 meses**. Se a volatilidade histórica anual do spread desse grupo for maior que isso, o prêmio é "fino": uma abertura comum anula o ganho sobre a NTN-B.

### 4.9 Perda esperada e PD implícita

```latex
EL_h = PD_h \times LGD \qquad \lambda_{implícita} \approx \frac{s}{LGD}
```

Exemplo: spread de 1,50% e LGD de 60% → intensidade de default implícita ≈ 2,5% a.a. Como o spread também remunera liquidez e prêmio de risco (seção 2.2), a PD implícita **superestima** a PD real. Uso recomendado: só comparativo. Para PD real, não há base pública brasileira de defaults de debêntures por rating; as agências publicam estudos de default que precisam ser verificados (pergunta aberta na seção 14).

### 4.10 Inflação implícita e decisão IPCA+ vs. prefixado

```latex
\pi^{impl} = \frac{1 + r_{nominal}(T)}{1 + r_{real}(T)} - 1
```

Se a inflação esperada (Focus) no prazo for maior que a implícita, o IPCA+ tende a render mais que o prefixado equivalente, e vice-versa. A implícita contém prêmio de risco inflacionário ([BCB TD 359](https://www.bcb.gov.br/pec/wps/port/TD359.pdf)), então a comparação é um indicador, não uma previsão.

### 4.11 Liquidez e custo de saída

```latex
Roll = 2\sqrt{-\mathrm{Cov}(\Delta P_t, \Delta P_{t-1})} \qquad Amihud = \frac{1}{N}\sum_t \frac{|R_t|}{Vol_t} \qquad c_{saída} \approx \frac{b}{2} \times D_{mod}
```

b: diferença entre taxa de compra e de venda (em taxa). Exemplo: b = 20 bps e D\_mod = 4 → custo de saída ≈ 0,40% do PU. Na falta de negócios, usar como proxy de b a diferença entre taxas de compra e venda divulgadas pela ANBIMA, ou a dispersão das cotações.

### 4.12 Equalização tributária (gross-up)

Para comparar um isento com um tributado, equalizar sobre o **retorno nominal** (o IR incide sobre o ganho nominal, inclusive a correção pelo IPCA):

```latex
r_{bruto\ equivalente} = \frac{r_{nominal\ isento}}{1 - IR}
```

Exemplo: incentivada a IPCA + 7,80% com IPCA de 4,0% → nominal 12,11%. Com IR de 15%, o tributado equivalente é 14,25% nominal, ou cerca de **IPCA + 9,86%**. A diferença cresce com a inflação. A alíquota relevante depende do prazo de permanência (tabela regressiva) e do investidor (PF, PJ, fundo).

## 5. Comparação entre metodologias

Nenhum método isolado basta: os de maior fundamentação (retorno total, duration) descrevem o título mas não dizem se ele está barato; os que tentam dizer isso (valor relativo, carrego) têm evidência empírica, mas fora do Brasil. A tabela orienta qual peso cada um deve ter na decisão.

| Metodologia | Natureza | Evidência de eficácia | Dados no Brasil | Implementação | Papel no simulador |
| --- | --- | --- | --- | --- | --- |
| Decomposição do retorno total (4.7) | Identidade contábil | Não se aplica (é exata dado o cenário) | Bom | Simples | **Espinha dorsal** |
| Duration, convexidade, DV01 (4.5) | Teoria (matemática de preço) | Aproximação com erro conhecido | Bom | Simples | Sensibilidade e cenários |
| Curva Svensson / ETTJ (4.2) | Estatística parcimoniosa | Padrão de bancos centrais e ANBIMA | Bom (gratuito no dia) | Consumir pronto | Curva base |
| Spread sobre NTN-B / Z-spread (4.3) | Definição de mercado | Não se aplica | Bom para precificados ANBIMA | Média (fluxos) | Medida de prêmio |
| Spread residual vs. pares (4.4) | Valor relativo | Positiva nos EUA (Correia et al.; Israel et al.); **não testada no Brasil** | Médio (amostra pequena por grupo) | Média | Sinal principal, se validado |
| Z-score histórico do spread do emissor | Heurística (reversão à média) | Fraca/indireta; spreads têm regimes | Exige histórico pago | Simples | Contexto, não sinal |
| Carrego + rolldown | Identidade + hipótese de curva estável | Carry em bonds: positiva mas com quedas em crises (Koijen et al.); carry em crédito fraco (Israel et al.) | Bom | Simples | Componente do retorno |
| Breakeven de spread (4.8) | Identidade | Não se aplica | Bom | Simples | Margem de segurança |
| DTS (4.6) | Empírica | Robusta em EUA/Europa (Ben Dor et al.) | Bom | Simples | Escala dos choques de spread |
| Modelo estrutural de Merton (2.2) | Teoria | Explica mal o nível do spread (credit spread puzzle) | Ruim (exige valor de mercado dos ativos) | Complexa | Não recomendado no MVP |
| PD implícita no spread (4.9) | Teoria (forma reduzida) | Superestima PD real | Bom | Simples | Só comparativo |
| Score de crédito fundamentalista (Altman e similares) | Empírica (estatística) | Validado em outros mercados; recalibração necessária | Bom para companhias abertas (CVM); ruim para fechadas e CRI/CRA | Média | Alerta de risco (bandeiras) |
| Medidas de liquidez (Roll, Amihud, bid-ask) | Empírica | Prêmio de liquidez pequeno no Brasil (Giacomoni & Sheng) | Ruim/médio (poucos negócios) | Média | Custo de saída e filtro |
| Previsão de curva (Diebold-Li, combinações) | Econométrica | Ganho modesto e instável | Bom | Média | Opcional; não no MVP |
| Fatores multifatoriais (value, momentum, low risk) | Empírica | Forte nos EUA; long-short | Histórico pago | Alta | Fase de pesquisa (backtest) |

**Leitura:** o simulador deve combinar a espinha dorsal (retorno esperado sob cenários) com **um** sinal de valor relativo e **filtros** de risco e liquidez. Empilhar muitos indicadores aumenta o risco de sobreajuste sem evidência de ganho.

## 6. Aplicabilidade ao mercado brasileiro

Os modelos são aplicáveis, mas sete particularidades locais mudam a forma de calcular e comparar. Ignorá-las gera conclusões erradas mesmo com fórmulas corretas.

| Particularidade | Por que importa | Tratamento proposto |
| --- | --- | --- |
| **Três mundos de indexador** (CDI+/%CDI, IPCA+, prefixado) | Riscos diferentes: CDI+ quase só tem risco de spread; IPCA+ e pré têm forte risco de juros | Comparar dentro do indexador; entre indexadores, converter tudo para retorno esperado em CDI equivalente no horizonte, sob o mesmo cenário |
| **Isenção de IR** (incentivadas Lei 12.431, CRI, CRA para PF) | Isentos negociam com spread menor; spread bruto não é comparável ao de tributados | Grupos de pares separados por tratamento tributário e gross-up (4.12) para comparar entre grupos |
| **Tabela regressiva de IR** (22,5% a 15% conforme o prazo) | Vender e recomprar antecipa imposto e pode reiniciar a alíquota | Incluir IR na decisão de venda/troca (seção 10) |
| **Taxa indicativa = cotação, não negócio** | Pode haver distorção entre indicativa e preço executável, sobretudo em papéis ilíquidos | Mostrar sempre a "taxa de mesa" informada pelo usuário ao lado da indicativa; custo de saída explícito |
| **Iliquidez e baixa frequência de negócios** | Muitos papéis não têm negócios diários; medidas de liquidez ficam ruidosas | Classes de liquidez (alta, média, baixa) com custo de saída por classe, calibrado em dados de negócios |
| **Opções embutidas** (resgate antecipado facultativo, amortização extraordinária) | Limitam valorização: emissor tende a resgatar quando o spread comprime | Sinalizar e calcular yield/spread até a data de resgate (yield-to-worst) quando houver cláusula com prêmio definido |
| **CRI/CRA são estruturas** | Risco depende do devedor, do lastro, de garantias, de subordinação e da securitizadora | Módulo de crédito com campos de estrutura; regras do lastro mudaram com a [Res. CMN 5.118/2024](https://normativos.bcb.gov.br/Votos/CMN/20248/Voto_do_CMN_8_2024.pdf) e alterações posteriores |

### Contexto regulatório e tributário (verificado em 29/10/2026)

- A **MP 1.303/2025** propunha IR de 5% sobre novas emissões de LCI, LCA, CRI, CRA e debêntures incentivadas. A Câmara retirou-a de pauta em outubro de 2025 e ela perdeu a validade; nenhuma das mudanças entrou em vigor ([InfoMoney](https://www.infomoney.com.br/politica/governo-estuda-aplicar-iof-sobre-lci-lca-cri-cra-e-debentures-diz-jornal/); [Banco Fibra, mar/2026](https://bancofibra.com.br/blog/debentures-incentivadas/)).
- Em **28/10/2026**, a imprensa noticiou que o governo estuda cobrar **IOF** sobre investimentos isentos, inclusive CRI, CRA e debêntures. Não há proposta formal, alíquota nem definição sobre estoque ([Seu Dinheiro](https://www.seudinheiro.com/2026/renda-fixa/lcis-lcas-e-outros-isentos-voltam-a-mira-do-governo-e-podem-passar-a-ter-iof-diz-jornal-mlim/); [Economic News Brasil](https://economicnewsbrasil.com.br/2026/10/28/iof-em-investimentos-isentos/)).
- **Implicação:** o tratamento tributário deve ser **parâmetro configurável**, não regra fixa no código. Risco regulatório sobre isentos é um cenário relevante para spreads de incentivadas. Não confirmei em fonte oficial (Receita/Planalto) a tabela regressiva vigente; a confirmação fica para a fase de especificação.

### O que funciona bem no Brasil

- Curvas soberanas de alta qualidade e gratuitas (DI futuro, ETTJ ANBIMA), o que torna confiáveis o carrego, o rolldown da curva base e os cenários de juros.
- Precificação diária padronizada (ANBIMA) com metodologia pública, o que permite spreads comparáveis entre papéis.
- Demonstrações financeiras padronizadas das companhias abertas (CVM), o que permite indicadores de crédito automatizados para emissores abertos.

## 7. Fontes de dados disponíveis

O simulador consegue rodar o dia corrente com fontes gratuitas, mas um backtest sério de crédito privado exige histórico pago da ANBIMA (ou acesso institucional, como o do seu banco). "Não verificado" indica que a pesquisa não confirmou o item em fonte primária.

| Fonte | Dados | Frequência | Histórico | Acesso | Custo e restrições |
| --- | --- | --- | --- | --- | --- |
| [ANBIMA site / ANBIMA Data](https://www.anbima.com.br/pt_br/informar/precos-e-indices/precos/taxas-debentures.htm) | Taxas indicativas, PU, duration de debêntures, CRI, CRA; ETTJ; curvas de crédito; IDA | Diária (até 20h) | Curto no gratuito: Z-spread de debêntures só dos últimos 5 dias úteis ([notícia, out/2025](https://legismap.com.br/conteudos/artigos-e-noticias/spread-do-mercado-secundario-de-debentures-agora-e-divulgado-no-anbima-data)) | Download no site | Gratuito; termos de uso para coleta automatizada não verificados |
| [ANBIMA Feed (API)](https://developers.anbima.com.br/en/?p=1116) | Mesmos dados via REST (debêntures, CRI/CRA, títulos públicos, curvas, IDA, projeções IPCA/IGP-M) | Diária; alguns intradiários | Histórico para assinantes | OAuth2 (token de 1h); sandbox gratuito | Pago. Tabela no site (valores mensais para usuário final): debêntures R$ 1.144,16; CRI/CRA R$ 778,03; títulos públicos R$ 686,50 ([fonte](https://feed.anbima.com.br/en/?p=1198)). Página com rodapé de 2021: **valores podem estar desatualizados** |
| B3: [taxas referenciais](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-derivativos/precos-referenciais/taxas-referenciais-bm-fbovespa/) e Boletim Diário | Ajustes de DI futuro, curvas de swap (DI x Pré, DI x IPCA), negócios de renda fixa | Diária | Longo | Consulta/download no site | Gratuito para consulta; a página de taxas referenciais **veda coleta automatizada, inclusive por IA**. Página de dados públicos descontinuada em 31/03/2026, migrada ao Boletim Diário ([CE 001/2026](https://www.b3.com.br/data/files/24/92/1D/71/773CB9109B5E99B9AC094EA8/CE%20001-2026-VTEC_NOVA%20DATA%20PARA%20DESCONTINUACAO%20DA%20PAGINA%20DE%20DADOS%20PUBLICOS_PT.pdf)) |
| B3 serviços pagos (UP2DATA, preços referenciais de debêntures) | Feeds de mercado; [preços de debêntures](https://www.b3.com.br/data/files/94/17/6F/CD/606C1710EB0EEB17AC094EA8/OC%20053-2020%20PRE%20Servi%C3%A7os%20de%20Dados%20%20%20Lan%C3%A7amento%20do%20Novo%20Canal%20de%20Dados%20de%20Precifica%C3%A7%C3%A3o%20de%20Deb%C3%AAntures%20no%20UP2DATA.pdf) | Diária | Longo | Contrato | Pago; preço não verificado |
| [BCB SGS](https://dadosabertos.bcb.gov.br/dataset/1178-taxa-de-juros---selic-anualizada-base-252/resource/e7fe6edb-d6c3-49b1-a7ef-6e0e98b63270) | Selic, CDI, IPCA e milhares de séries | Diária/mensal | Décadas | API JSON aberta | Gratuito; há limite de janela por consulta em séries diárias (confirmar regra vigente) |
| [BCB Focus (Olinda)](https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado/resource/1a5fdbb7-c8bd-49ec-9f90-ba3585044636) | Expectativas de IPCA, Selic, PIB, câmbio por horizonte | Semanal (com atualização diária das bases) | Desde 2001 aprox. (não verificado) | API OData | Gratuito |
| [Tesouro Transparente](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1?inner_span=True) | Preços e taxas do Tesouro Direto | Diária | Desde 2002 aprox. (não verificado) | CSV aberto | Gratuito; são taxas de varejo, não mercado secundário |
| IBGE (SIDRA) | IPCA oficial e números-índice | Mensal | Longo | API aberta | Gratuito (não verificado nesta pesquisa) |
| [CVM Dados Abertos](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp) | DFP e ITR de companhias abertas, cadastro | Trimestral/anual | Mais de uma década | CSV aberto | Gratuito; não cobre emissores fechados nem devedores de CRI/CRA |
| Agências de rating (S&P, Fitch, Moody's) | Rating e perspectiva por emissão | Por evento | Variável | Consulta individual nos sites | Uso em base de dados normalmente restrito por licença; feeds pagos (não verificado) |
| Uqbar, terminais (Bloomberg, LSEG) | Dados detalhados de CRI/CRA, fluxos, eventos; preços | Diária | Longo | Assinatura | Pagos; LSEG distribui dados ANBIMA ([LSEG](https://www.lseg.com/en/data-analytics/financial-data/pricing-and-market-data/fixed-income-pricing-data/anbima)) |
| Escrituras e relatórios (fundos.net / FNET, sites de agentes fiduciários) | Fluxos, garantias, covenants, opções de resgate | Por evento | Longo | PDF (não estruturado) | Gratuito; exige extração manual ou semiautomática |

**Verificação adicional da base pública ANBIMA:** a [página de mercado secundário de debêntures](https://www.anbima.com.br/informacoes/merc-sec-debentures/default.asp) permite baixar arquivos diários (XLS e TXT) com taxas de compra, venda e indicativa e PU, mas só dos **últimos 5 dias úteis**. Os [termos de uso do site](https://www.anbima.com.br/pt_br/termos-de-uso.htm) (atualizados em 01/07/2026) proíbem expressamente robôs de coleta e mineração de dados (seção 2.4). Não encontrei licença gratuita de redistribuição pública; no ANBIMA Feed, o plano de usuário final proíbe compartilhar, e a redistribuição exige plano pago específico. Isto não é parecer jurídico; a confirmação definitiva é com a ANBIMA.

### 7.1 Alternativas à ANBIMA para taxas e preços de crédito privado

Quase todas as fontes "alternativas" gratuitas republicam dados da ANBIMA. As fontes independentes são três: os **negócios registrados na B3** (preço, não taxa), a **CALC da B3** (preços referenciais, paga acima de 10 cálculos por dia) e a **taxa da mesa do banco**. Provedores pagos cobrem o histórico. Verificado em 30/10/2026.

| Fonte | O que entrega | Independente da ANBIMA? | Acesso e custo | Uso no simulador |
| --- | --- | --- | --- | --- |
| [B3 – Negociação Consolidada (Boletim Diário, renda fixa)](https://b3.com.br/data/files/C2/11/CB/7F/6F07781064456178AC094EA8/Glossario_Registrosconsolidados.pdf) | Por papel e dia: preço mínimo, médio, máximo e último, quantidade, número de negócios, volume, ISIN, emissor; cobre DEB, CRI e CRA | Sim (negócios reais) | CSV diário gratuito, download manual; [coleta automatizada vedada](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/) | **Upload diário.** Taxa calculada pelo simulador a partir do PU e do fluxo; medidas de liquidez (frequência, volume, dispersão) |
| [B3 – Negócios no Puma (balcão)](https://www.b3.com.br/data/files/2F/05/AA/A5/D3B0D910F37907C9AC094EA8/Negocios%20de%20VM%20de%20renda%20fixa%20realizados%20no%20Puma%20-%20Balcao_.pdf) | Preços e melhores ofertas de compra e venda de debêntures, CRI e CRA negociados na tela | Sim | CSV diário; glossário marcado como informação interna, acesso público não confirmado | Proxy de bid-ask, se acessível |
| [B3 – Calculadora de Renda Fixa (CALC)](https://www.b3.com.br/pt_br/solucoes/plataformas/interface-de-negociacao/calc/sobre-a-calc/) | PU e taxas referenciais, fluxo projetado, VNA, duration; cerca de 1,3 mil debêntures, principais CRAs e CRIs | Sim (equipe própria da B3) | 10 cálculos/dia grátis; planos a partir de R$ 454,02/mês (debêntures), R$ 480,65 (CRA), R$ 506,97 (CRI); API disponível | Fonte de **fluxos de pagamento** e checagem de PU; opcional |
| Run de compra da instituição (arquivo do usuário) | Taxa de compra, duration, prazo, tipo, rating | Sim | Interno; upload pelo usuário | **Upload.** Taxa principal da análise; nunca no repositório |
| [debentures.com.br (SND)](https://www.debentures.com.br/) | Características de debêntures e preços mínimos/médios/máximos negociados | Não (site da ANBIMA) | Gratuito; aviso de descontinuação e migração ao ANBIMA Data | Consulta de características, enquanto existir |
| [Clube dos Poupadores](https://clubedospoupadores.com/renda-fixa/cotacao.html), [Mais Retorno](https://maisretorno.com/termos-de-uso) | Preços de negócios (REUNE, até R$ 100 mil); cadastro de debêntures | Não (ANBIMA/CVM) | Gratuito; cópia proibida (Clube); raspagem e redistribuição proibidas (Mais Retorno) | Não usar como fonte de dados |
| [Boletim de Debêntures Incentivadas](https://www.gov.br/fazenda/pt-br/central-de-conteudo/publicacoes/boletim-de-debentures-incentivadas) | Emissões, prazos, indexadores, volume secundário, IDA (agregados) | Não (ANBIMA desde 2024; Fazenda 2013–2022) | Gratuito, mensal, dashboard | Contexto de mercado primário |
| Quantum Finance, Economatica, Bloomberg, LSEG | Taxas e preços históricos de crédito privado ([InfoMoney usa Quantum](https://www.infomoney.com.br/onde-investir/quanto-pagam-as-debentures-cris-e-cras-mais-negociados/)) | Parcialmente (agregam ANBIMA, B3 e próprios) | Pagos; licença restringe redistribuição (não verificado caso a caso) | **Melhor caminho para o histórico do backtest**, se o banco já tiver acesso |
| [PYield (Python, MIT)](https://pypi.org/project/PYield) | Curvas e títulos públicos, DI futuro, Selic, IPCA | Não se aplica (só soberano) | Gratuito; termos das fontes continuam valendo | Opcional para a curva base, após checar como acessa as fontes |

**Conclusão:** para o dia a dia, o simulador combina três uploads (taxa da mesa, arquivo ANBIMA e CSV de negócios da B3), sem robô e sem salvar dados no repositório. Para histórico, a saída viável é (a) acumular os arquivos diários a partir de agora, para uso pessoal, ou (b) usar um terminal ou provedor pago que o banco já contrate.

**Lacunas críticas:** (1) histórico longo de taxas indicativas sem custo; (2) base estruturada de fluxos de pagamento de todos os papéis; (3) ratings em base de dados; (4) histórico público de defaults de debêntures e CRI/CRA para calibrar PD e LGD.

**Regra de exibição:** cada número do simulador mostra fonte, data de referência e horário da última atualização; dado vencido (por exemplo, indicativa de D−2) aparece sinalizado.

## 8. Arquitetura quantitativa recomendada

A arquitetura separa o que é medido (módulos A–E) do que é suposto (cenários) e do que é decidido (regras de compra e venda), para que cada premissa fique visível e testável.

Fluxo da arquitetura:

1. **Dados** (fonte, data e hora em cada número): ANBIMA, B3, BCB/IBGE, CVM e arquivos do usuário.
2. **Módulos analíticos** A (juros), B (spread), C (retorno), D (crédito) e E (liquidez).
3. **Motor de cenários**: base (taxas a termo), otimista e pessimista (percentis históricos), estresse e cenário do usuário.
4. **Decisões**: compra (ERA, spread residual, margem de segurança) e venda/troca (manter × vender × trocar).
5. **Painel** com classificação, cenários, alternativas e data/hora dos dados.
6. **Backtest**, que calibra periodicamente os limiares das decisões.

Os módulos calculam métricas na data da consulta; o motor de cenários projeta curva e spread no horizonte; as duas decisões usam a mesma decomposição de retorno (4.7). O backtest não roda a cada consulta: ele calibra os limiares das regras de forma periódica e decide se a classificação pode ser exibida como recomendação.

| Módulo | Pergunta que responde | Principais saídas |
| --- | --- | --- |
| A · Juros e macro | Em que ponto do ciclo estamos e o que a curva já precifica? | Curva DI, ETTJ nominal e real, inflação implícita vs. Focus, inclinação (ex.: 10 anos − 1 ano) |
| B · Spread e preço | O papel paga mais ou menos que pares e que o próprio histórico? | Z-spread, spread vs. indicativa, spread residual z\_j, z-score histórico |
| C · Sensibilidade e retorno | Quanto ganho ou perco em cada cenário? | Duration, convexidade, DV01, DTS, carrego, rolldown, retorno total por cenário |
| D · Crédito | O spread compensa o risco do emissor? | Rating, bandeiras (alavancagem, cobertura, vencimentos), PD implícita relativa, estrutura/garantias |
| E · Liquidez | Quanto custa sair e com que facilidade? | Frequência de negócios, diferença compra/venda, classe de liquidez, custo de saída |

## 9. Metodologia de compra

A compra é avaliada por uma pergunta objetiva: **no horizonte escolhido, o retorno esperado do papel, depois de perda esperada, custo de saída e impostos, supera o do título soberano equivalente e o dos pares, com margem suficiente para absorver uma abertura normal de spread?**

### 9.1 Entradas

| Grupo | Campos | Origem |
| --- | --- | --- |
| Identificação | Código do ativo, emissor, setor, tipo (debênture, CRI, CRA), incentivada/isento | Usuário + ANBIMA |
| Remuneração | Indexador, taxa de aquisição (taxa de mesa), PU, vencimento | Usuário |
| Fluxo | Datas de juros e amortização, opções de resgate | Escritura / ANBIMA |
| Risco de crédito | Rating e perspectiva, indicadores do emissor, garantias | Usuário + CVM |
| Liquidez | Frequência de negócios, diferença compra/venda | B3 / ANBIMA |
| Investidor | Horizonte (padrão 12 meses), tipo (PF, PJ), alíquota de IR aplicável | Usuário |

### 9.2 Cálculos, em ordem

1. **Preço e sensibilidades:** PU à taxa informada, duration, convexidade, DV01, spread duration (4.1, 4.5, 4.6).
2. **Prêmio:** Z-spread na taxa de mesa e na taxa indicativa ANBIMA; diferença entre as duas ("estou pagando acima ou abaixo da indicativa?").
3. **Valor relativo:** spread residual z\_j contra a curva do grupo de pares (4.4) e z-score do spread do próprio emissor no histórico.
4. **Cenários** no horizonte h, para curva base e spread:
   - **Base:** curva segue as taxas a termo; spread constante. (Ressalva: a taxa a termo contém prêmio de prazo; Cochrane & Piazzesi, 2005.)
   - **Otimista e pessimista:** percentis 90 e 10 da distribuição histórica de variações em h dos fatores de curva (nível, inclinação) e do spread relativo do grupo (Δs/s, coerente com DTS), estimados com janela móvel.
   - **Estresse:** choque histórico nomeado (por exemplo, a abertura de spreads de março–abril de 2020, registrada pela ANBIMA, ou a de 2023 após eventos de crédito relevantes), aplicado como cenário à parte.
   - **Do usuário:** Selic, IPCA e spread definidos manualmente (por exemplo, a partir do Focus).
5. **Retorno total esperado** por cenário (4.7), descontando perda esperada (4.9) e custo de saída (4.11), líquido de IR conforme o investidor.
6. **Benchmark no mesmo cenário:** NTN-B (IPCA+), LTN/NTN-F ou curva pré (prefixado) e CDI (pós), de mesma duration, líquidos de IR.
7. **Margem de segurança:** spread de equilíbrio Δs\* (4.8) dividido pelo desvio-padrão histórico de Δs no horizonte para o grupo ("quantos desvios o prêmio aguenta").
8. **Bandeiras de risco:** rebaixamento ou perspectiva negativa, alavancagem (dívida líquida/EBITDA) e cobertura de juros (EBITDA/despesa financeira) fora de faixas setoriais, concentração de vencimentos de dívida em 24 meses, liquidez baixa, opção de resgate próxima.

### 9.3 Métricas de decisão

```latex
ERA = E[R_h^{papel}]_{base} - E[R_h^{soberano}]_{base} \qquad MS = \frac{\Delta s^{*}}{\sigma(\Delta s_h)_{grupo}} \qquad z_j = \frac{s_j - \hat{S}_g(D_j)}{\hat{\sigma}_g}
```

ERA: excesso de retorno ajustado (já líquido de perda esperada, custos e IR). MS: margem de segurança. z\_j: valor relativo vs. pares.

### 9.4 Regras de classificação

Regras transparentes sobre as três métricas e as bandeiras. **Os limiares abaixo são hipóteses iniciais**, a serem calibradas e validadas no backtest (seção 11); não têm validação empírica ainda.

| Classificação | Regra (todas as condições) |
| --- | --- |
| Oportunidade atrativa | ERA > 0; z\_j ≥ +1,0; MS ≥ 1,0; nenhuma bandeira crítica |
| Oportunidade moderada | ERA > 0; z\_j ≥ +0,5 ou MS ≥ 0,5; nenhuma bandeira crítica |
| Precificado adequadamente | ERA ≥ 0; z\_j entre −0,5 e +0,5 |
| Pouco atrativo | z\_j ≤ −0,5, ou ERA próximo de zero com MS < 0,5 |
| Risco-retorno desfavorável | ERA < 0 no cenário base, ou bandeira crítica, ou perda no cenário pessimista acima da tolerância do usuário |

### 9.5 Saídas

- Classificação com a **justificativa decomposta** (quais condições passaram ou falharam).
- Taxa vs. indicativa ANBIMA, vs. curva de pares e vs. soberano; prêmio em bps.
- Adequação do prazo: retorno por unidade de duration comparado aos pares; inclinação da curva de spread do grupo (se prêmios crescem pouco com o prazo, estender duration não compensa).
- Retorno até o vencimento (carregando) e no horizonte, por cenário; ganho/perda de marcação a mercado.
- Principais riscos (bandeiras) e top 5 alternativas do mesmo indexador e tratamento tributário, ordenadas por ERA.

## 10. Metodologia de venda

**Princípio:** manter um título equivale a recomprá-lo hoje pelo preço de venda, sem pagar custos de transação. Logo, a decisão de manter usa a **taxa de mercado atual**, não a taxa de aquisição. O lucro acumulado só entra na decisão pelo imposto que a venda antecipa.

### 10.1 Diagnóstico da posição (olhando para trás)

| Pergunta | Cálculo |
| --- | --- |
| Retorno acumulado | TIR da posição (fluxos recebidos + valor de mercado atual vs. preço de compra), em % a.a., % do CDI e vs. NTN-B/IDA no período |
| Quanto valorizou ou desvalorizou | PU de mercado − PU "na curva" (PU calculado à taxa de aquisição na data de hoje) = ganho ou perda de marcação; o resto do retorno é carrego realizado |
| A taxa está comprimida? | Spread atual vs. spread na compra; z-score do spread do emissor no histórico; spread residual vs. pares (z\_j negativo = papel caro) |

### 10.2 Decisão (olhando para frente)

Três alternativas no mesmo horizonte h e no mesmo cenário:

1. **Manter:** retorno esperado com o papel marcado à taxa atual de venda (4.7), menos perda esperada.
2. **Vender e ficar no soberano/CDI:** retorno do benchmark, menos custo de saída e imposto antecipado.
3. **Trocar por outro papel:** retorno esperado da alternativa, menos custo de saída, custo de entrada, imposto antecipado e diferença de perda esperada.

```latex
V_{troca} = \left(E[R_h^{alt}] - E[R_h^{manter}]\right) - c_{saída} - c_{entrada} - T_{antecipado} - \Delta EL
```

```latex
T_{antecipado} \approx IR \times G \times \left[1 - (1+r)^{-T_{rest}}\right]
```

- G: ganho tributável realizado na venda; T\_rest: prazo até quando o imposto seria pago se o papel fosse mantido; r: taxa de desconto nominal. Isentos têm T = 0.
- Além da antecipação, a nova aplicação reinicia a tabela regressiva (alíquota maior se resgatada em menos de 2 anos).
- **Regra:** vender/trocar se V\_troca > margem mínima definida pelo usuário (histerese, para evitar giro excessivo por diferenças dentro do erro de estimativa) **e** a alternativa tiver risco de crédito, duration e liquidez comparáveis ou melhores.
- Vender para o soberano se o ERA de manter (9.3) ficar negativo: o prêmio restante não paga o risco.

### 10.3 Exemplo numérico (hipotético)

Debênture IPCA+ tributada comprada há 2 anos a IPCA + 8,00%; hoje negocia a IPCA + 6,50% (comprimiu); duration modificada remanescente de 4,0; posição vale R$ 115 para cada R$ 100 investidos. Alternativa de mesmo rating, setor e duration a IPCA + 7,30%.

| Item | Valor |
| --- | --- |
| Ganho de taxa da troca | 0,80 p.p. a.a. |
| Custo de saída + entrada (10 bps de meio-spread × duration 4, cada lado) | 0,80% |
| Imposto antecipado (IR 15% sobre ganho de R$ 15, pago 4 anos antes, desconto a IPCA + 6,5% com IPCA de 4%) | R$ 0,75, ou 0,66% da posição |
| Custo total da troca | ≈ 1,46% |
| Tempo para o ganho de taxa pagar a troca | ≈ 1,8 ano |

**Leitura:** com 4 anos de duration remanescente, a troca tende a compensar se a alternativa tiver de fato risco equivalente. A taxa de aquisição (8,00%) não entrou em nenhuma conta: o que importa é que manter rende cerca de IPCA + 6,50% daqui para frente. Se o papel fosse isento, o custo cairia para 0,80% e o prazo de equilíbrio para cerca de 1 ano.

### 10.4 Potencial adicional de valorização

- Rolldown restante na curva de spread e na curva base (4.7).
- Convergência para a curva de pares: se z\_j < 0 (já está caro), o viés esperado é de **devolução**, não de ganho adicional, se a reversão à média for validada no backtest.
- Teto por opção de resgate antecipado: com spread comprimido, o emissor tem incentivo a resgatar, limitando a alta de preço.

### 10.5 Aplicação: Mapa de Posições × run de compra da instituição

O fluxo principal do simulador: o usuário carrega o **Mapa de Posições** do cliente e o **run de compra** da instituição (planilha com os papéis disponíveis e suas taxas), e o simulador lista, para cada ativo da carteira, se existe no run um substituto que melhore a relação risco-retorno depois de custos e impostos. Os arquivos reais nunca entram no repositório; os testes usam arquivos fictícios no mesmo layout.

**Campos disponíveis em cada arquivo**

| Arquivo | Formato recebido | Campos | O que falta |
| --- | --- | --- | --- |
| Mapa de Posições | PDF gerado pelo banco, uma linha por lote de compra | Título (tipo, emissor, indexador, taxa de emissão, vencimento, código), Emissão, Vencimento, Emissor, data da Operação, Taxa Operação, Quantidade, PU Operação, PU Curva, Valor Bruto (curva), PU Mercado, Valor Bruto (mercado), IR, IOF, Valor Líquido, Rendimento | Duration, fluxo de pagamentos, rating, setor, garantia e **taxa de mercado atual** de cada ativo |
| Run de compra | Planilha Excel com cabeçalho fixo | Código, Empresa, Produto (DEB, CRI, CRA, CPR), Taxa de Compra, Indexador (Pré, %CDI, IPCA, +CDI), Distribuição, Lastro Disponível, Quantidades disponíveis, Vencimento, Duration, NTN-B de referência, Taxa de Emissão, Cupom, Amortização, Setor, Rating, Agência, Investidor Qualificado, Isento, Garantia; campos internos da instituição (exibidos só no modo interno, nunca usados no ranking) | Taxa de **recompra** (preço de saída); papéis fora do estoque |

**Lacuna central:** o Mapa não traz a taxa de mercado atual dos ativos da carteira, e essa taxa é o retorno de "manter" (seção 10.2). Ordem de prioridade proposta para obtê-la:

1. Taxa indicativa ANBIMA do mesmo código, pelo upload opcional. Aqui a ANBIMA deixa de ser acessória: ela também fornece a duration dos ativos da carteira e as taxas de compra e venda de referência, usadas para estimar o custo de saída.
2. Taxa implícita no PU Mercado do Mapa, calculada com o fluxo do papel (run de compra, quando o papel está lá; senão, escritura ou CALC da B3).
3. Taxa de Compra do mesmo código no run de compra, sinalizada como aproximação (a recompra tende a ser pior que a venda).

Não há run de venda (recompra) disponível. Ativos sem nenhuma das três fontes ficam marcados como "sem taxa de mercado" e não recebem recomendação.

**Etapas do motor de troca**

1. **Leitura e limpeza:** extrair código, tipo e indexador do campo Título; agregar lotes do mesmo código mantendo os lotes para IR e IOF; descartar nome, agência e conta do cliente na leitura.
2. **Escopo:** analisar debêntures, CRIs e CRAs com PU Mercado. CDBs e CPRs sem preço de mercado ficam fora por padrão (configurável).
3. **Enriquecimento:** para cada ativo da carteira, obter taxa de mercado, duration, rating e setor (run de compra, ANBIMA ou entrada manual), registrando a fonte de cada campo.
4. **Filtros de elegibilidade dos candidatos** (padrões ajustáveis): distribuição ativa e lastro suficiente para o valor de saída; compatível com o perfil do cliente (investidor qualificado ou não); mesmo tratamento tributário (isento para isento); mesmo indexador (modo amplo permite trocar entre indexadores, comparando no mesmo cenário); diferença de duration de até 1,5 ano, salvo se o usuário aceitar alongar; rating igual ou melhor; concentração por emissor e setor abaixo de limites definidos pelo usuário.
5. **Economia de cada par (ativo atual → candidato):** diferença de taxa; diferença de spread sobre a NTN-B de referência de cada um (corrige diferenças de prazo); IR e IOF da venda pelo lote; ganho estimado em R$ por ano sobre o valor de saída; prazo de equilíbrio; efeito na duration e na concentração da carteira; resultado nos cenários da seção 9.
6. **Classificação do par:** "troca recomendada", "troca marginal" ou "manter", com limiares de ganho de spread e de prazo de equilíbrio calibráveis (valores iniciais propostos: 30 bps e 10 bps de ganho de spread; hipóteses a validar).
7. **Saída:** para cada ativo da carteira, os até 3 melhores candidatos com a justificativa de cada filtro e cálculo; resumo da carteira antes e depois (taxa média, duration, concentração, ganho total estimado).

**Regra de custo: dois cenários lado a lado** (decisão do usuário, já que não se sabe se o PU Mercado é preço de recompra):

| Cenário | Hipótese sobre o PU Mercado | Cálculo do ganho da troca |
| --- | --- | --- |
| A · Preço executável | É o preço que a mesa paga na recompra | Diferença de taxa direta: custos de saída e entrada já embutidos (antes de IR, IOF e risco) |
| B · Marcação de referência | É só marcação (por exemplo, ANBIMA) | Diferença de taxa menos custo de saída = meio spread de compra/venda × duration. Padrão: meio spread das taxas de compra e venda ANBIMA do papel; sem ANBIMA, parâmetro do usuário por classe de liquidez |

A classificação final usa o **cenário B (conservador)**; quando os dois divergem (por exemplo, "recomendada" em A e "marginal" em B), o resultado mostra o alerta. **Teste automático:** se o arquivo ANBIMA for carregado e o PU Mercado do Mapa coincidir com o PU indicativo ANBIMA, o simulador informa que o PU Mercado é marcação de referência, e o cenário B passa a ser o realista.

**Leitura do Mapa em PDF** (não há export em Excel): parser do layout atual com validação linha a linha (Quantidade × PU deve bater com o Valor Bruto; código extraído do Título deve existir). Linhas que falham aparecem numa tabela editável para correção manual antes da análise. Mudança de layout do PDF exige ajuste do parser.

**Governança dos dados:**

- O run de compra é material restrito da instituição. O simulador terá dois modos de saída: **interno** (inclui campos internos) e **cliente** (mostra só taxas e métricas que o cliente pode ver).
- A ordenação das trocas usa apenas a economia do cliente. A receita da instituição na operação não entra no ranking, para evitar conflito de interesse e giro excessivo.
- Processamento 100% no navegador do usuário, sem envio dos arquivos a servidor. Isso favorece uma página estática no GitHub Pages; hospedar em serviço com servidor enviaria os arquivos a terceiros.

## 11. Estratégia de backtesting

O backtest deve responder a uma pergunta falsificável: **papéis classificados como "atrativos" na data t renderam mais, no horizonte seguinte, do que papéis "precificados adequadamente" e do que o índice IDA correspondente, depois de custos?** Se não, o sinal de valor relativo não entra no produto como recomendação.

### 11.1 Desenho

1. **Base:** painel diário de taxas indicativas, PU, duration e características de todos os papéis precificados pela ANBIMA (debêntures DI e IPCA primeiro; CRI/CRA depois), mais curvas soberanas e negócios da B3. Período desejado: o mais longo disponível, cobrindo ciclos de alta e queda da Selic e episódios de estresse (2020; 2023).
2. **Datas de formação:** mensais (fim de mês). Em cada data, calcular métricas e classificação **usando apenas informação disponível até aquela data**.
3. **Retorno realizado:** retorno total de cada papel no horizonte h (1, 3, 6 e 12 meses), pelo PU ANBIMA, incluindo cupons e amortizações.
4. **Testes:**
   - Carteiras por quintil de z\_j e de ERA, dentro de cada grupo (indexador × rating × tratamento tributário); diferença de retorno entre extremos.
   - Regressões cross-section (Fama-MacBeth) do retorno excedente futuro sobre z\_j, ERA e MS, com erros-padrão robustos (Newey-West).
   - Taxa de acerto: % de "atrativos" que superam o benchmark; % de "vender" que de fato rendem menos que a alternativa depois.
   - Erro de previsão do modelo de retorno esperado: comparação entre E\[R\_h\] do cenário base e o retorno realizado (viés e erro quadrático médio).
5. **Custos:** descontar meio-spread de entrada e saída por classe de liquidez; testar sensibilidade com custos dobrados.
6. **Execução realista:** sinal formado em t, execução em t+1 (ou t+2) à taxa daquele dia; excluir papéis sem negócio no mês ou aplicar penalidade de iliquidez.

### 11.2 Vieses a evitar

| Viés | Como aparece aqui | Controle |
| --- | --- | --- |
| Look-ahead | Usar rating, balanço ou curva de pares revisados depois da data t | Base "point-in-time": balanço só após a data de divulgação na CVM; rating só após a data da ação de rating |
| Sobrevivência | Papéis que deram default ou saíram da precificação ANBIMA somem da base | Manter papéis excluídos até o fim do horizonte, com preço de saída ou de recuperação estimado; reportar quantos saíram e por quê |
| Seleção pela elegibilidade | Só papéis negociados entram na precificação | Declarar o universo testado; não extrapolar para papéis ilíquidos |
| Preço não executável | Indicativa é cotação | Teste paralelo só com papéis com negócios REUNE/B3 no dia da formação |
| Sobreajuste e testes múltiplos | Testar muitos limiares e escolher o melhor | Fixar hipóteses antes; separar período de calibração e de validação (walk-forward); exigir t > 3 ([Harvey, Liu & Zhu, 2016](https://www.nber.org/papers/w20592)); reportar Sharpe deflacionado ([Bailey & López de Prado, 2014](https://papers.ssrn.com/abstract=2460551)) |
| Regime | Resultado vale só num ciclo de juros | Reportar por subperíodo: alta de Selic, queda, estresse |
| Fluxo técnico | Compressão de spreads por fluxo para fundos incentivados, não por qualidade | Testar incentivadas e não incentivadas separadamente |

### 11.3 Critério de aprovação (proposta)

O sinal só vira "recomendação" se, fora da amostra de calibração: (a) o quintil de maior z\_j/ERA superar o de menor depois de custos, com significância; (b) o resultado se mantiver em pelo menos dois regimes de juros; (c) a perda no estresse não for desproporcional ao ganho médio. Caso contrário, o simulador exibe as métricas como diagnóstico, sem classificação de compra/venda.

## 12. Limitações e riscos do projeto

Os maiores riscos não são de fórmula, e sim de dado e de interpretação: o modelo pode estar matematicamente certo e economicamente enganoso.

| Risco | Quando as conclusões falham | Mitigação |
| --- | --- | --- |
| Spread "barato" que é risco escondido | Emissor em deterioração ainda não refletida no rating (casos de evento de crédito súbito) | Bandeiras fundamentalistas; nunca classificar como atrativo com bandeira crítica; exibir a notícia/evento mais recente como lembrete manual |
| Indicativa diferente do preço executável | Papéis ilíquidos, mercado estressado | Taxa de mesa como entrada principal; custo de saída explícito |
| Amostra pequena por grupo de pares | Poucos papéis AA de um setor em certa duration | Agrupar por rating e indexador primeiro; setor só com N mínimo (ex.: 8 papéis) |
| Cenários mal calibrados | Mudança de regime (fiscal, política monetária) fora do histórico | Cenários do usuário e de estresse ao lado dos estatísticos |
| Taxa a termo tratada como previsão | Prêmio de prazo elevado (curva inclinada por risco, não por expectativa) | Rotular o cenário base como "mercado precificado", não "previsão"; comparar com Focus |
| Mudança tributária | IOF ou IR sobre isentos (estudo noticiado em 28/10/2026) | Tributação parametrizável; cenário regulatório |
| Dados pagos ou com uso restrito | Histórico ANBIMA pago; B3 veda coleta automatizada em páginas | Validar licenças antes de publicar no GitHub; dados proprietários fora do repositório público |
| Uso como recomendação | Cliente ou colega interpreta classificação como ordem | Aviso explícito; classificação só após validação (11.3); verificar com compliance do banco o uso com clientes |
| Opções e estruturas complexas | Resgate antecipado, CRIs com subordinação, pré-pagamento | MVP limitado a papéis bullet ou com fluxo conhecido; sinalizar o resto como "fora do escopo do modelo" |
| Evidência empírica importada | Fatores de crédito validados nos EUA podem não funcionar no Brasil | Backtest local obrigatório |

**Fatos, hipóteses e estimativas neste documento:** fórmulas e regras ANBIMA são fatos documentados; a eficácia do valor relativo no Brasil é hipótese; limiares de classificação, custos de saída e exemplos numéricos são estimativas ilustrativas.

## 13. Roadmap de desenvolvimento

O desenvolvimento avança em fases com portões de aprovação; o portão decisivo é o do backtest, que separa ferramenta analítica de ferramenta de recomendação.

| Fase | Conteúdo | Portão para avançar |
| --- | --- | --- |
| 0 · Especificação e teste técnico | Premissas, licenças de dados, casos de teste | Premissas aprovadas |
| 1 · Núcleo de cálculo | PU, duration, convexidade, spreads, carrego, rolldown, retorno por cenário | PU e taxa batem com calculadoras de referência |
| 2 · MVP do painel | Compra e troca com dados do dia; métricas sem rótulo de recomendação | Uso real por algumas semanas |
| 3 · Base histórica e backtest | Painel point-in-time, curvas de pares, quintis, walk-forward | **Critério da seção 11.3 atendido** |
| 4 · Classificação e expansão | Rótulos calibrados, CRI/CRA, prefixados, busca de alternativas | — |

As fases 1 e 2 não dependem de dados pagos. A fase 3 depende de acesso a histórico de taxas.

## 14. Referências e links

Apenas documentos efetivamente localizados nesta pesquisa. Itens marcados "resumo" foram verificados só pelo resumo ou por fonte secundária.

**Metodologias e dados (Brasil)**

- ANBIMA. [Metodologias ANBIMA de Precificação](https://www.anbima.com.br/data/files/5D/92/EC/E7/E82F971013C70F976B2BA2A8/Metodologias-ANBIMA-de-precificacao.pdf), mai/2021.
- ANBIMA. [Metodologias ANBIMA de Precificação de CRA e CRI](https://www.anbima.com.br/data/files/11/C7/38/7D/16FBC91067D089C9BA2BA2A8/Metodologias_ANBIMA_de_Precificacao_CRA_CRI.pdf), nov/2025.
- ANBIMA. [Metodologia Intervalo Indicativo](https://www.anbima.com.br/data/files/79/F1/76/70/8FEFC8104606BDC8B82BA2A8/Metodologia%20ANBIMA%20Intervalo%20Indicativo.pdf), dez/2023.
- ANBIMA. [Credit curves – Methodology](https://www.anbima.com.br/data/files/EC/77/C1/4F/67CFD71028DFACD76B2BA2A8/Metodologia_Curva%20de%20Credito_out21_ingles.pdf), out/2021; [página das curvas de crédito](https://www.anbima.com.br/pt_br/informar/precos-e-indices/curvas/curvas-de-credito.htm).
- ANBIMA. [Estrutura a Termo das Taxas de Juros Estimada – Metodologia](https://www.anbima.com.br/data/files/9A/F4/E3/1F/4805B710B0F024B7882BA2A8/est-termo_metodologia_v2021.pdf), ago/2021.
- ANBIMA. [Metodologia IDA](https://www.anbima.com.br:443/data/files/55/F0/37/0A/9EEFC8104606BDC8B82BA2A8/Metodologia_IDA_dez23.pdf), dez/2023; [Metodologia IDA LIQ](https://www.anbima.com.br/data/files/AC/50/22/3B/15FBC91067D089C9BA2BA2A8/Metodologia_IDA_LIQ_mar26.pdf), mar/2026.
- ANBIMA. [Developers – APIs de preços e índices](https://developers.anbima.com.br/en/?p=1116); [ANBIMA Feed – planos](https://feed.anbima.com.br/en/?p=1198).
- B3. [Taxas referenciais](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-derivativos/precos-referenciais/taxas-referenciais-bm-fbovespa/); [CE 001/2026-VTEC](https://www.b3.com.br/data/files/24/92/1D/71/773CB9109B5E99B9AC094EA8/CE%20001-2026-VTEC_NOVA%20DATA%20PARA%20DESCONTINUACAO%20DA%20PAGINA%20DE%20DADOS%20PUBLICOS_PT.pdf); [CE 002/2026-VPC](https://www.b3.com.br/data/files/D7/94/8A/F8/D300C91076A8EEB9AC094EA8/CE%20002-2026-VPC%20COMPROMISSADAS%20DE%20DEBENTURES%20NO%20BOLETIM%20DIARIO%20DO%20MERCADO_PT.pdf).
- BCB. [Dados abertos – Expectativas de mercado (Focus)](https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado/resource/1a5fdbb7-c8bd-49ec-9f90-ba3585044636); [SGS](https://dadosabertos.bcb.gov.br/dataset/1178-taxa-de-juros---selic-anualizada-base-252/resource/e7fe6edb-d6c3-49b1-a7ef-6e0e98b63270).
- CVM. [Dados abertos – DFP](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp). Tesouro Nacional. [Taxas do Tesouro Direto](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1?inner_span=True).
- CMN. [Voto 8/2024 (Res. 5.118, lastro de CRI/CRA)](https://normativos.bcb.gov.br/Votos/CMN/20248/Voto_do_CMN_8_2024.pdf).

**Estrutura a termo**

- Nelson, C.; Siegel, A. (1987). Parsimonious Modeling of Yield Curves. *Journal of Business*. [NBER WP 1594](https://www.nber.org/papers/w1594).
- Svensson, L. (1994). [Estimating and Interpreting Forward Interest Rates: Sweden 1992–1994](https://www.nber.org/system/files/working_papers/w4871/w4871.pdf). NBER WP 4871.
- Litterman, R.; Scheinkman, J. (1991). Common Factors Affecting Bond Returns. *Journal of Fixed Income* (citado via [GPIF, 2022](https://www.gpif.go.jp/investment/20220301_workingpaper_en.pdf); resumo).
- Diebold, F.; Li, C. (2006). [Forecasting the Term Structure of Government Bond Yields](https://www.nber.org/papers/w10048). *Journal of Econometrics*.
- Cochrane, J.; Piazzesi, M. (2005). [Bond Risk Premia](https://www.nber.org/papers/w9178). *American Economic Review*.
- Caldeira, J.; Moura, G.; Santos, A. (2013). [Predicting the Yield Curve Using Forecast Combinations](https://papers.ssrn.com/abstract=2311733). SSRN (resumo).
- Vicente, J.; Graminho, F. (2014). [Decompondo a Inflação Implícita](https://www.bcb.gov.br/pec/wps/port/TD359.pdf). BCB TD 359.
- Araujo, G.; Vicente, J. (2017). [Estimação da Inflação Implícita de Curto Prazo](https://www.bcb.gov.br/pec/wps/port/TD460.pdf). BCB TD 460.

**Risco de crédito e spreads**

- Merton, R. (1974). [On the Pricing of Corporate Debt](https://dspace.mit.edu/handle/1721.1/1874). *Journal of Finance*.
- Altman, E. (1968). Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy. *Journal of Finance* 23(4) ([edição](https://afajof.org/issue/volume-23-issue-4/)).
- Duffie, D.; Singleton, K. (1999). [Modeling Term Structures of Defaultable Bonds](https://ideas.repec.org/a/oup/rfinst/v12y1999i4p687-720.html). *Review of Financial Studies*.
- Elton, E. et al. (2001). [Explaining the Rate Spread on Corporate Bonds](https://ideas.repec.org/a/bla/jfinan/v56y2001i1p247-277.html). *Journal of Finance* (resumo).
- Collin-Dufresne, P.; Goldstein, R.; Martin, J. S. (2001). [The Determinants of Credit Spread Changes](https://ideas.repec.org/a/bla/jfinan/v56y2001i6p2177-2207.html). *Journal of Finance* (resumo).
- Longstaff, F.; Mithal, S.; Neis, E. (2005). [Corporate Yield Spreads: Default Risk or Liquidity?](https://www.nber.org/papers/w10418). *Journal of Finance* (resumo).
- Huang, J.; Huang, M. (2012). [How Much of the Corporate-Treasury Yield Spread Is Due to Credit Risk?](https://ideas.repec.org/a/oup/rasset/v2y2012i2p153-202..html). *Review of Asset Pricing Studies* (resumo).
- Gilchrist, S.; Zakrajšek, E. (2012). [Credit Spreads and Business Cycle Fluctuations](https://www.nber.org/papers/w17021). *American Economic Review*.
- Christensen, J. (2008). [The Corporate Bond Credit Spread Puzzle](https://www.frbsf.org/research-and-insights/publications/economic-letter/2008/03/corporate-bond-credit-spread/). FRBSF Economic Letter.
- Sheng, H.; Saito, R. (2005). [Determinantes de spread das debêntures no mercado brasileiro](https://pesquisa-eaesp.fgv.br/sites/gvpesquisa.fgv.br/files/arquivos/sheng_-_determinantes_da_spread_da_debentures.pdf). *R.Adm.*

**Liquidez**

- Amihud, Y. (2002). [Illiquidity and Stock Returns](https://archive.nyu.edu/handle/2451/27420). *Journal of Financial Markets*.
- Bao, J.; Pan, J.; Wang, J. (2011). [The Illiquidity of Corporate Bonds](https://dspace.mit.edu/handle/1721.1/75381). *Journal of Finance*.
- Dick-Nielsen, J.; Feldhütter, P.; Lando, D. (2012). [Corporate Bond Liquidity Before and After the Onset of the Subprime Crisis](https://research-api.cbs.dk/ws/files/58847171/corporate_bon_liquidity_david_lando.pdf). *Journal of Financial Economics*.
- Giacomoni, B.; Sheng, H. (2013). [O impacto da liquidez nos retornos esperados das debêntures brasileiras](https://eaesp.fgv.br/sites/default/files/legacy/pesquisa-eaesp-files/arquivos/sheng_-_o_impacto_da_liquidez.pdf). *RAUSP*.

**Valor relativo, fatores e backtesting**

- Correia, M.; Richardson, S.; Tuna, I. (2012). [Value Investing in Credit Markets](https://ideas.repec.org/a/spr/reaccs/v17y2012i3d10.1007_s11142-012-9191-x.html). *Review of Accounting Studies* (resumo).
- Israel, R.; Palhares, D.; Richardson, S. (2018). [Common Factors in Corporate Bond Returns](https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/Common-Factors-in-Corporate-Bond-Returns.pdf). *Journal of Investment Management*.
- Houweling, P.; van Zundert, J. (2017). [Factor Investing in the Corporate Bond Market](https://papers.ssrn.com/abstract=2516322). *Financial Analysts Journal* (resumo).
- Koijen, R.; Moskowitz, T.; Pedersen, L.; Vrugt, E. (2018). [Carry](https://econbiz.de/Record/carry-koijen-ralph/10011968803). *Journal of Financial Economics* (resumo).
- Ben Dor, A. et al. (2007). DTS (Duration Times Spread). *Journal of Portfolio Management* 33(2) (via [Robeco](https://robeco.com/en-us/insights/2024/09/duration-times-spread-measuring-credit-risk); resumo).
- Harvey, C.; Liu, Y.; Zhu, H. (2016). […and the Cross-Section of Expected Returns](https://www.nber.org/papers/w20592). *Review of Financial Studies*.
- Bailey, D.; López de Prado, M. (2014). [The Deflated Sharpe Ratio](https://papers.ssrn.com/abstract=2460551). *Journal of Portfolio Management*.

**Livros**

- Fabozzi, F. *Bond Markets, Analysis, and Strategies*; *The Handbook of Fixed Income Securities*.
- Tuckman, B.; Serrat, A. *Fixed Income Securities*. Wiley.
- Martellini, L.; Priaulet, P.; Priaulet, S. [*Fixed-Income Securities: Valuation, Risk Management and Portfolio Strategies*](https://www.wiley-vch.de/en/areas-interest/finance-economics-law/fixed-income-securities-978-0-470-85277-4). Wiley, 2003.
- Hull, J. *Options, Futures, and Other Derivatives*; *Risk Management and Financial Institutions*.
- Ilmanen, A. [*Expected Returns*](https://www.oreilly.com/library/view/expected-returns-an/9781119990772/). Wiley, 2011.

**Tributação (notícias)**

- [InfoMoney, 28/10/2026](https://www.infomoney.com.br/politica/governo-estuda-aplicar-iof-sobre-lci-lca-cri-cra-e-debentures-diz-jornal/); [Seu Dinheiro, 28/10/2026](https://www.seudinheiro.com/2026/renda-fixa/lcis-lcas-e-outros-isentos-voltam-a-mira-do-governo-e-podem-passar-a-ter-iof-diz-jornal-mlim/); [Economic News Brasil, 28/10/2026](https://economicnewsbrasil.com.br/2026/10/28/iof-em-investimentos-isentos/); [Banco Fibra, 03/03/2026](https://bancofibra.com.br/blog/debentures-incentivadas/); [InfoMoney, 01/10/2025](https://www.infomoney.com.br/politica/congresso-adia-votacao-de-mp-alternativa-ao-iof-para-vespera-do-prazo-de-validade/).
