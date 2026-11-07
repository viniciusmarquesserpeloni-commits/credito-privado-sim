"""Tela 5 — Metodologia: resumo dos cálculos, limitações e aviso de não recomendação."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

import ui  # noqa: E402
from cpsim import report  # noqa: E402

st.title("5 · Metodologia")
st.warning(report.AVISO)

st.markdown(ui.L("""
**O que a ferramenta faz.** Para cada posição do Mapa, estima a taxa de mercado e a duration,
procura no Runflow papéis elegíveis para a troca e calcula a economia do cliente depois de custos
e impostos.

**Taxa de mercado das posições.** É a taxa *y* que faz PU(y) / PU(taxa de operação) igualar
PU Mercado / PU Curva, com o mesmo fluxo nos dois lados. O VNA se cancela, porque o PU Curva é o
PU na taxa de operação. O fluxo vem do Runflow quando o papel está lá; senão, a premissa padrão
é de juros semestrais e amortização no vencimento. O resultado é uma **estimativa**. Lotes do
mesmo papel que divergem mais de 10 bps geram alerta. Na tela Carteira dá para informar o fluxo,
a duration ou a taxa.

**Elegibilidade do candidato.** Distribuição ativa e estoque suficiente; perfil do investidor;
mesma tributação e mesmo indexador (o modo amplo compara a taxa nominal esperada); diferença de
duration até 1,5 ano; rating igual ou melhor; concentração por emissor e setor dentro dos
limites.

**Economia.** Ganho anual = valor de saída × diferença de taxa nominal esperada no cenário.
O cenário **A** trata o PU Mercado como preço executável, sem custo de saída. O cenário **B**
trata o PU Mercado como marcação, com custo de saída ≈ b/2 × duration modificada × valor.
Imposto antecipado ≈ IR × [1 − (1 + r)^(−prazo restante)], mais o IOF do Mapa. Prazo de
equilíbrio = custos ÷ ganho anual. Nos papéis IPCA+, o Δ usado é o spread sobre a NTN-B de
referência (Tesouro Direto, taxa de varejo).

**Classificação (cenário B, hipóteses).** *Recomendada*: Δ ≥ 30 bps e equilíbrio ≤ 1 ano.
*Marginal*: Δ ≥ 10 bps e equilíbrio ≤ 2 anos. *Manter*: os demais casos. Quando os cenários A e
B divergem, a tela avisa. O ranking usa só a economia do cliente.

**Limitações.**
- A premissa de amortização no vencimento erra mais quanto maior a distância entre a taxa de
  mercado e a de operação e quanto mais cedo o papel amortiza. A duration fica superestimada.
- CDI e IPCA esperados vêm do Focus, que é expectativa de mercado e não previsão; as datas das
  reuniões do Copom são aproximadas.
- O Tesouro Direto é taxa de varejo, não de mercado secundário.
- Tabelas de IR e IOF e isenções são parâmetros: confirmar a vigência.
- Os limiares de classificação não foram validados por backtest.
"""))

doc = ui.ROOT / "docs" / "metodologia.md"
# O documento de pesquisa descreve o run interno da instituição: só no modo interno.
if doc.is_file() and ui.interno():
    with st.expander("Documento de pesquisa completo (docs/metodologia.md)"):
        st.markdown(doc.read_text(encoding="utf-8"))
