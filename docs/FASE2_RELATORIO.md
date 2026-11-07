# Fase 2 — Relatório do motor de troca

Data: 07/11/2026. **203 testes passando; cobertura do núcleo 98%.**

## O que foi feito

| Módulo | Conteúdo |
|---|---|
| `scripts/update_public_data.py` | Coleta BCB SGS (CDI 12, meta Selic 432, IPCA 433), Focus (Selic por reunião, IPCA anual e 12 meses) e Tesouro Direto (só IPCA+ e prefixados, últimas 5 datas-base). Cada JSON grava `fonte`, `url` e `coletado_em` (horário de Brasília). Se uma fonte falhar, o arquivo anterior fica e o erro vai para `_status.json`. Datas futuras da série 432 são cortadas. |
| `curves.py` | CDI esperado (CDI atual + trajetória da Selic do Focus, com datas de reunião **aproximadas**), IPCA esperado (12 meses e depois as medianas anuais), NTN-Bs do Tesouro Direto (**taxa de varejo**, média de compra e venda) com duration calculada. |
| `scenarios.py` | Cenário base (Focus, "mercado precificado", não previsão) e cenário do usuário. |
| `enrich.py` | Taxa de mercado e duration de cada posição pela regra nova (abaixo), escopo (DEB/CRI/CRA com PU Mercado), isenção (Runflow → tipo do papel → inferida pelo IR do Mapa), marcação vs curva e alertas. |
| `swap_engine.py` | Filtros parametrizáveis, economia nos cenários A e B, classificação, até 3 candidatos por posição com justificativa, carteira antes e depois. |
| `report.py` | Tabelas e export Excel em memória, nos modos **interno** e **cliente**. |

## Taxa de mercado e duration (regra definida por você)

1. Código no Runflow → fluxo (Cupom/Amortização) e duration do Runflow.
2. Fora do Runflow → fluxo padrão: juros semestrais e amortização no vencimento.
3. Nos dois casos, a taxa y resolve PU(y)/PU(taxa de operação) = PU Mercado/PU Curva, com o
   mesmo fluxo nos dois lados. O resultado sai marcado como *estimativa* ("taxa estimada"). Sem
   Runflow, a duration sai do mesmo cálculo.
4. `Override` permite informar cupom, amortização, duration ou a própria taxa (para a tela Carteira).

**Interpretação a confirmar:** no caso 1, a taxa também sai da razão de PUs, usando o fluxo do
Runflow. A Taxa de Compra do Runflow só entra se a equação não tiver solução, marcada como
*aproximação* ("taxa de venda da mesa; a recompra tende a ser pior").

**PU Curva = PU na taxa de operação:** conferido no Mapa real. Nos lotes sem pagamento desde a
compra, PU Curva / PU Operação bate com a correção pela taxa de operação (0,00% e +0,01% nos
prefixados; −0,3% a −0,4% nos IPCA, diferença explicada pela minha aproximação mensal do IPCA).
Nos demais, a diferença vem de juros e amortizações pagos no período. As amostras fictícias
agora geram PU Curva e PU Mercado com o fluxo de cada papel, e o motor recupera a taxa de
mercado usada com erro < 0,5 bp, inclusive pelo fluxo padrão.

## Teste-ouro da premissa "amortização no vencimento"

Sua especificação: erro < 10 bps se o papel amortiza nos últimos 3 anos, e < 30 bps se amortiza
nos últimos 8. **Ela vale para o papel típico, mas não em todo o domínio:** o erro ≈ Δy × (D_real /
D_estimada − 1), em que Δy é a distância entre a taxa de mercado e a de operação.

Pior erro (bps), em cupons de 5–12% e taxas de operação de 5–13%:

| Amortização | Prazo | Δy 50 bps | Δy 100 bps | Δy 150 bps | Δy 300 bps |
|---|---|---|---|---|---|
| últimos 3 anos | 5 anos | 12 | 24 | 36 | 73 |
| últimos 3 anos | 10 anos | 5 | 10 | 16 | 31 |
| últimos 3 anos | 15 anos | 3 | 6 | 9 | 18 |
| últimos 8 anos | 10 anos | 17 | 34 | 51 | 103 |
| últimos 8 anos | 15 anos | 10 | 20 | 29 | 59 |
| últimos 8 anos | 20 anos | 6 | 13 | 19 | 39 |

O teste-ouro implementado (`tests/test_phase2.py`) usa um papel de 10 anos com cupom de 7% e
|Δy| ≤ 80 bps. Dá 7–10 bps com amortização nos últimos 3 anos e 24–26 bps nos últimos 8, dentro
dos dois limites. Um segundo teste registra onde a premissa estoura (papel de 5 anos com Δy de
300 bps; 8 anos de amortização com Δy de 100 bps).

**A duration erra mais do que a taxa.** Com amortização nos últimos 8 anos, a premissa dá 7,2
anos, contra 4,9 do papel real. Só isso já tira o papel da banda de ±1,5 ano do filtro de
duration. Por isso o alerta da posição pede que se informe a amortização.

**No Mapa real (sem Runflow, tudo pelo fluxo padrão):** as 18 posições na análise saíram com
taxa estimada. A checagem cruzada funcionou: os dois lotes de uma debênture IPCA divergem 17
bps, o que indica que o fluxo verdadeiro não é o padrão. Os três papéis em %CDI (CRIs e um CRA)
deram distâncias de 5,7 a 30,6 pontos de %CDI. Esses papéis costumam amortizar mensalmente, e
com o fluxo padrão **a estimativa deles não é confiável**: precisam do fluxo do Runflow ou da
amortização informada.

## Motor de troca — regras implementadas

- **Filtros** (todos com parâmetro): distribuição ativa e lastro ≥ valor de saída; perfil do
  investidor; mesma tributação; mesmo indexador (o modo amplo compara a taxa nominal esperada);
  |ΔD| ≤ 1,5 ano; rating igual ou melhor (sem rating → reprova, salvo confirmação); concentração
  por emissor e por setor depois da troca ≤ 20% e 40% do total analisado.
- **Economia:** V = Valor Líquido do Mapa. O Δ usado na classificação é o Δs sobre a NTN-B nos
  papéis IPCA (B-ref do Runflow ou duration mais próxima) e o Δy nos demais; em %CDI,
  Δy = (p_c − p_h) × CDI esperado. O ganho em R$ é V × Δ da taxa nominal esperada no cenário.
- **Custos:**
  - Cenário A: sem custo de saída.
  - Cenário B: (b/2) × D_mod × V, com b por classe de liquidez (padrões hipotéticos de 10, 25 e
    50 bps; sem ANBIMA no MVP).
  - Imposto antecipado: IR de cada lote, como informado no Mapa, × [1 − (1+r)^−T_rest], com
    T_rest = prazo até o vencimento, mais o IOF integral.
  - A entrada não é cobrada, porque a taxa do Runflow já a embute.
- **Classificação (cenário B):**
  - recomendada: Δ ≥ 30 bps e equilíbrio ≤ 1 ano;
  - marginal: Δ ≥ 10 bps e equilíbrio ≤ 2 anos (**interpretação** do "10 ≤ Δ < 30 bps ou
    1 < equilíbrio ≤ 2" do prompt);
  - manter: o resto.
  
  Quando A e B divergem, aparece o alerta "depende do preço real de recompra".
- **Ranking:** só pela economia do cliente no cenário B (ganho anual − custos / horizonte). O motor
  nunca lê as colunas internas; um teste muda o fee e confere que ranking e classificação não mudam.
- **Antes e depois:** aplica a melhor troca recomendada de cada posição. Se duas posições
  disputam o mesmo papel, o lastro vai primeiro para a de maior ganho, e a outra recebe um alerta.

## Modos de saída

- **Cliente:**
  - sem colunas internas e sem lastro;
  - "Runflow" vira "oferta disponível";
  - o filtro de lastro aparece como "disponibilidade".
  
  Um teste lê o Excel exportado célula a célula e confere que não sobrou nada disso.
- **Interno:** inclui lastro e as colunas internas, com os rótulos do config.

## Pendências

1. **Workflow `update-data.yml`** (coleta agendada, dias úteis às 20h, que faz commit e push dos
   dados públicos na `main` pelo GitHub Actions). A gravação dele foi interrompida na sua mudança
   de escopo, e não recriei sem confirmar com você.
2. Interface (Fase 3): telas, campos de sobrescrita na Carteira e export.
