"""Tributação: IR regressivo, IOF regressivo, isenção, imposto antecipado e gross-up.

Tabelas e isenções são PARÂMETROS editáveis (metodologia 6, "Contexto regulatório"): há estudo do
governo noticiado em 28/10/2026 sobre IOF em investimentos isentos. Os padrões abaixo estão
marcados como "confirmar vigência" — não foram conferidos em fonte oficial nesta fase.

Na venda, o simulador usa o IR e o IOF que o próprio Mapa informa por lote (prompt 6.6);
estas tabelas servem para simular a NOVA aplicação e o imposto antecipado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CONFIRMAR_VIGENCIA = "confirmar vigência"

# (até N dias corridos, alíquota). Última faixa sem limite.
IR_PADRAO: tuple[tuple[int | None, float], ...] = ((180, 0.225), (360, 0.20), (720, 0.175),
                                                   (None, 0.15))
# IOF regressivo: % do rendimento por dia corrido (1 a 29); a partir do 30º dia, zero.
IOF_PADRAO: tuple[float, ...] = (
    0.96, 0.93, 0.90, 0.86, 0.83, 0.80, 0.76, 0.73, 0.70, 0.66, 0.63, 0.60, 0.56, 0.53, 0.50,
    0.46, 0.43, 0.40, 0.36, 0.33, 0.30, 0.26, 0.23, 0.20, 0.16, 0.13, 0.10, 0.06, 0.03,
)


@dataclass(frozen=True)
class TaxPolicy:
    """Parâmetros tributários (todos editáveis na tela de Parâmetros)."""

    ir_table: tuple[tuple[int | None, float], ...] = IR_PADRAO
    iof_table: tuple[float, ...] = IOF_PADRAO
    investor: str = "PF"  # "PF" ou "PJ"
    # Isenção de IR para PF (incentivadas Lei 12.431, CRI, CRA, CPR...). Parâmetro: pode mudar.
    pf_exempt_products: frozenset[str] = field(
        default_factory=lambda: frozenset({"CRI", "CRA", "CPR", "LCI", "LCA"}))
    status: str = CONFIRMAR_VIGENCIA

    def ir_rate(self, days_held: int) -> float:
        if days_held < 0:
            raise ValueError("prazo negativo")
        for limit, rate in self.ir_table:
            if limit is None or days_held <= limit:
                return rate
        return self.ir_table[-1][1]

    def iof_rate(self, days_held: int) -> float:
        """Fração do RENDIMENTO devida de IOF. Dia 0 (mesmo dia) = 100%."""
        if days_held <= 0:
            return 1.0
        if days_held > len(self.iof_table):
            return 0.0
        return self.iof_table[days_held - 1]

    def is_exempt(self, product: str | None, flagged_exempt: bool | None) -> bool:
        """Isenção para o investidor. A coluna "Isento?" do Runflow manda quando existe
        (debênture incentivada é DEB e só a planilha sabe); senão, pelo produto.
        PJ nunca é isenta nesta regra."""
        if self.investor.upper() != "PF":
            return False
        if flagged_exempt is not None:
            return flagged_exempt
        return (product or "").upper() in self.pf_exempt_products


DEFAULT_POLICY = TaxPolicy()


def anticipated_tax(ir: float, gain: float, r: float, t_rest: float) -> float:
    """Imposto antecipado pela venda (metodologia 10.2):
    T ≈ IR × G × [1 − (1 + r)^(−T_rest)].
    G = ganho tributável realizado; T_rest = anos até quando o imposto seria pago mantendo o
    papel; r = taxa de desconto nominal. Isento: chamar com ir = 0 (T = 0).
    Ex. 10.3: 0,15 × 15 × [1 − 1,1076^−4] ≈ R$ 0,75."""
    if gain <= 0 or ir <= 0:
        return 0.0
    return ir * gain * (1.0 - (1.0 + r) ** (-t_rest))


def gross_up_nominal(nominal_exempt: float, ir: float) -> float:
    """Taxa bruta tributada equivalente a um isento (metodologia 4.12): r / (1 − IR).
    O IR incide sobre o ganho NOMINAL, inclusive a correção pelo IPCA."""
    return nominal_exempt / (1.0 - ir)


def gross_up_ipca_spread(real_exempt: float, ipca: float, ir: float) -> float:
    """Spread real tributado equivalente a um IPCA+ isento (metodologia 4.12).
    Ex.: IPCA + 7,80% isento, IPCA 4%, IR 15% -> ≈ IPCA + 9,86%."""
    nominal = (1.0 + real_exempt) * (1.0 + ipca) - 1.0
    return (1.0 + gross_up_nominal(nominal, ir)) / (1.0 + ipca) - 1.0


def net_of_ir(nominal: float, ir: float) -> float:
    """Retorno nominal líquido de IR (aproximação: IR sobre o ganho do período)."""
    return nominal * (1.0 - ir)
