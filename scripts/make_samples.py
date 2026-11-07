"""Gera os arquivos de AMOSTRA (100% fictícios) em data/samples/.

- mapa_posicoes_exemplo.pdf  -> mesmo layout descrito para o Mapa de Posições do banco
- runflow_exemplo.xlsx       -> mesmo layout descrito para o Runflow da mesa (aba Consolidado)

Nada aqui vem de arquivo real: emissores ("Energia Alfa S.A."...), códigos (prefixo X...),
quantidades e preços são inventados e determinísticos (sem aleatoriedade), para que o
arquivo gerado seja sempre igual e os testes possam depender dele.

Casos difíceis cobertos de propósito (o parser precisa lidar com eles):
- Título quebrado em várias linhas dentro da célula;
- o mesmo código em dois lotes (datas e taxas diferentes);
- CDB e CPR com PU Mercado "-";
- taxa "CDI + x%" além de "x% CDI", "x% IPCA" e "x% PRE";
- tabela que continua em várias páginas, com cabeçalho repetido;
- linha do cliente (fictícia) e rodapé com data da posição e "x de y";
- no Runflow: bloco de busca nas linhas 3–5, cabeçalho na linha 10, uma coluna extra
  ("Observação"), rating "0" e "-", grafias variadas de rating, taxa como texto em algumas linhas.

Uso:  python scripts/make_samples.py
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # usa o próprio núcleo para gerar PUs coerentes
OUT = ROOT / "data" / "samples"

DATA_POSICAO = dt.date(2026, 10, 30)


# --------------------------------------------------------------------------------------
# Formatação no padrão brasileiro
# --------------------------------------------------------------------------------------
def brl(v: float) -> str:
    s = f"{v:,.2f}"  # 1,234.56
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def num_br(v: float, casas: int = 2) -> str:
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def d(s: str) -> dt.date:
    dia, mes, ano = map(int, s.split("/"))
    return dt.date(ano, mes, dia)


def fmt_d(x: dt.date) -> str:
    return x.strftime("%d/%m/%Y")


# --------------------------------------------------------------------------------------
# Mapa de Posições (PDF)
# --------------------------------------------------------------------------------------
@dataclass
class Lote:
    tipo: str  # DEB, CRI, CRA, CDB, CPR
    emissor_titulo: str  # como aparece no Título
    emissor: str  # coluna Emissor
    indexador_titulo: str  # IPCA, PRE, CDI, "CDI +"
    taxa_titulo: str  # "6.50%"
    vencimento: str
    codigo: str
    emissao: str
    operacao: str  # data da compra
    taxa_operacao: str  # "6.62% IPCA", "104.50% CDI", "CDI + 1.20%"
    quantidade: int
    pu_operacao: float
    pu_curva: float
    pu_mercado: float | None  # None -> "-"
    isento: bool

    @property
    def titulo(self) -> str:
        if self.indexador_titulo == "CDI +":
            idx = f"CDI + {self.taxa_titulo}"
        else:
            idx = f"{self.indexador_titulo} {self.taxa_titulo}"
        return f"{self.tipo} {self.emissor_titulo} {idx} {self.vencimento} - {self.codigo}"


def _aliquota_ir(dias: int) -> float:
    if dias <= 180:
        return 0.225
    if dias <= 360:
        return 0.20
    if dias <= 720:
        return 0.175
    return 0.15


LOTES: list[Lote] = [
    Lote("DEB", "ENERGIA ALFA", "ENERGIA ALFA S.A.", "IPCA", "6.50%", "15/05/2032", "XALF12",
         "15/05/2022", "12/03/2024", "6.62% IPCA", 120, 1180.40, 1312.77, 1298.15, True),
    Lote("DEB", "ENERGIA ALFA", "ENERGIA ALFA S.A.", "IPCA", "6.50%", "15/05/2032", "XALF12",
         "15/05/2022", "08/08/2025", "7.05% IPCA", 60, 1265.10, 1309.42, 1298.15, True),
    Lote("DEB", "SANEAMENTO BETA", "SANEAMENTO BETA S.A.", "IPCA", "7.10%", "15/09/2035",
         "XBET21", "15/09/2023", "20/10/2023", "7.10% IPCA", 200, 1003.55, 1121.08, 1089.64, True),
    Lote("DEB", "LOGISTICA GAMA", "LOGÍSTICA GAMA PARTICIPAÇÕES S.A.", "PRE", "13.07%",
         "15/03/2029", "XGAM13", "15/03/2024", "02/04/2024", "13.07% PRE", 150, 998.20,
         1062.31, 1071.90, False),
    Lote("DEB", "TELECOM DELTA", "TELECOM DELTA S.A.", "CDI", "104.50%", "15/06/2030", "XDEL14",
         "15/06/2023", "15/01/2025", "104.50% CDI", 90, 1012.00, 1046.88, 1044.10, False),
    Lote("DEB", "VAREJO EPSILON", "VAREJO EPSILON COMÉRCIO S.A.", "CDI +", "1.20%",
         "15/12/2028", "XEPS11", "15/12/2023", "05/06/2026", "CDI + 1.20%", 80, 1001.30, 1035.60,
         1028.45, False),
    Lote("CRI", "IMOBILIARIA ZETA", "ZETA SECURITIZADORA S.A.", "IPCA", "6.80%", "15/02/2034",
         "XCRI26A01", "15/02/2024", "10/04/2024", "6.95% IPCA", 300, 1011.25, 1098.44, 1080.02,
         True),
    Lote("CRA", "AGRO ETA", "ETA SECURITIZADORA DE CRÉDITOS DO AGRONEGÓCIO S.A.", "CDI",
         "94.00%", "15/07/2028", "XCRA25B02", "15/07/2025", "22/07/2025", "94.00% CDI", 250,
         1000.00, 1091.37, 1088.70, True),
    Lote("DEB", "RODOVIAS KAPPA", "RODOVIAS KAPPA CONCESSIONÁRIA S.A.", "IPCA", "5.98%",
         "15/10/2031", "XKAP31", "15/10/2021", "18/11/2022", "5.98% IPCA", 110, 1102.70,
         1357.90, 1342.22, True),
    Lote("CDB", "BANCO FICTICIO THETA", "BANCO FICTÍCIO THETA S.A.", "PRE", "12.50%",
         "28/04/2027", "CDBX0001", "28/04/2025", "28/04/2025", "12.50% PRE", 50, 1000.00,
         1182.04, None, False),
    Lote("CPR", "AGRO IOTA", "AGRO IOTA LTDA.", "CDI", "110.00%", "30/06/2027", "CPRX0001",
         "30/06/2025", "30/06/2025", "110.00% CDI", 40, 1000.00, 1158.93, None, True),
    Lote("DEB", "SANEAMENTO BETA", "SANEAMENTO BETA S.A.", "IPCA", "7.10%", "15/09/2035",
         "XBET21", "15/09/2023", "03/02/2026", "7.42% IPCA", 75, 1068.80, 1118.31, 1089.64, True),
    Lote("DEB", "PAPEL LAMBDA", "PAPEL LAMBDA INDÚSTRIA S.A.", "CDI +", "0.95%", "15/09/2029",
         "XLAM12", "15/09/2024", "30/09/2024", "CDI + 0.95%", 130, 1000.40, 1072.15, 1069.88,
         False),
    Lote("CRA", "USINA MI", "MI SECURITIZADORA S.A.", "IPCA", "7.35%", "15/04/2033",
         "XCRA24C07", "15/04/2024", "06/05/2024", "7.35% IPCA", 180, 1004.10, 1099.76, 1071.53,
         True),
    # Papel FORA do Runflow: a taxa de mercado sai pelo fluxo padrão (semestral, bullet).
    Lote("DEB", "HIDRO OMEGA", "HIDRO ÔMEGA GERAÇÃO S.A.", "IPCA", "6.20%", "15/04/2036",
         "XHOM36", "15/04/2026", "20/04/2026", "6.40% IPCA", 90, 1001.50, 1043.20, 1030.00,
         True),
]

# Taxa de MERCADO "verdadeira" de cada papel (mesma unidade da taxa; %CDI em fração).
# O PU Mercado da amostra é gerado com ela; os testes conferem que o motor a recupera.
TAXA_MERCADO = {
    "XALF12": 0.0690, "XBET21": 0.0745, "XGAM13": 0.1380, "XDEL14": 1.0380, "XEPS11": 0.0140,
    "XCRI26A01": 0.0735, "XCRA25B02": 0.9600, "XKAP31": 0.0670, "XLAM12": 0.0105,
    "XCRA24C07": 0.0770, "XHOM36": 0.0720,
}
# Cenário usado para projetar os fluxos de papéis CDI na amostra (os testes usam o mesmo).
SAMPLE_CDI, SAMPLE_IPCA = 0.14, 0.045


@lru_cache(maxsize=None)
def _pus(codigo: str, taxa_op_txt: str, pu_curva_ref: float, tem_mercado: bool,
         venc: str, taxa_titulo: str) -> tuple[float, float | None]:
    """PU Curva = PU na taxa de operação; PU Mercado = PU na taxa de mercado, com o MESMO fluxo
    (Runflow do papel, ou padrão semestral/bullet). O VNA é a escala que reproduz o PU Curva de
    referência, e se cancela na razão PU Mercado / PU Curva (como no Mapa real)."""
    from cpsim.cashflows import build_schedule
    from cpsim.enrich import discount_rate
    from cpsim.parsers.mapa_pdf import parse_rate_text
    from cpsim.pricing import price
    from cpsim.scenarios import user_scenario

    sc = user_scenario(SAMPLE_CDI, SAMPLE_IPCA)
    op = parse_rate_text(taxa_op_txt)
    rf = next((r for r in RUNFLOW if r[0] == codigo), None)
    if rf:
        cupom, amort, cupom_taxa = rf[11], rf[12], rf[10]
    else:
        cupom, amort = "Semestral", "Bullet"
        cupom_taxa = parse_rate_text(taxa_titulo).value if parse_rate_text(taxa_titulo) else op.value
    sch = build_schedule(DATA_POSICAO, d(venc), cupom, amort,
                         discount_rate(op.indexer, cupom_taxa, sc))
    flows = sch.as_pricing_flows()
    pv_op = price(flows, discount_rate(op.indexer, op.value, sc))
    escala = pu_curva_ref / pv_op
    if not tem_mercado:
        return pu_curva_ref, None
    pv_m = price(flows, discount_rate(op.indexer, TAXA_MERCADO[codigo], sc))
    return pu_curva_ref, escala * pv_m

COLUNAS_MAPA = [
    ("Título", 32), ("Emissão", 15), ("Vencimento", 15), ("Emissor", 22),
    ("Operação", 15), ("Taxa Operação", 16), ("Quantidade", 13), ("PU Operação", 17),
    ("PU Curva", 17), ("Valor Bruto (curva)", 20), ("PU Mercado", 17),
    ("Valor Bruto (mercado)", 20), ("IR", 16), ("IOF", 13), ("Valor Líquido", 20),
    ("Rendimento", 19),
]


def linha_mapa(l: Lote) -> list[str]:
    idx_txt = "CDI" if l.indexador_titulo.startswith("CDI") and "+" not in l.indexador_titulo         else l.indexador_titulo
    titulo_taxa = (f"CDI + {l.taxa_titulo}" if l.indexador_titulo == "CDI +"
                   else f"{l.taxa_titulo} {idx_txt}")
    pu_curva, pu_merc = _pus(l.codigo, l.taxa_operacao, l.pu_curva, l.pu_mercado is not None,
                             l.vencimento, titulo_taxa)
    l = Lote(**{**l.__dict__, "pu_curva": pu_curva,
                "pu_mercado": None if pu_merc is None else round(pu_merc, 2)})
    # Como no Mapa real: PU exibido com 2 casas, Valor Bruto calculado com o PU completo.
    vb_curva = round(l.quantidade * pu_curva, 2)
    custo = round(l.quantidade * l.pu_operacao, 2)
    if pu_merc is None:
        vb_merc = None
        base = vb_curva
    else:
        vb_merc = round(l.quantidade * pu_merc, 2)
        base = vb_merc
    rendimento = round(base - custo, 2)
    dias = (DATA_POSICAO - d(l.operacao)).days
    ir = 0.0 if (l.isento or rendimento <= 0) else round(rendimento * _aliquota_ir(dias), 2)
    iof = 0.0
    liquido = round(base - ir - iof, 2)
    return [
        l.titulo, l.emissao, l.vencimento, l.emissor, l.operacao, l.taxa_operacao,
        str(l.quantidade), brl(l.pu_operacao), brl(l.pu_curva), brl(vb_curva),
        "-" if l.pu_mercado is None else brl(l.pu_mercado),
        "-" if vb_merc is None else brl(vb_merc),
        brl(ir), brl(iof), brl(liquido), brl(rendimento),
    ]


def make_mapa_pdf(path: Path) -> None:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    class MapaPDF(FPDF):
        def header(self) -> None:
            self.set_font("Helvetica", "B", 12)
            self.cell(0, 7, "Mapa de Posição", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 8)
            # Linha do cliente: FICTÍCIA e sem dígitos (o CI de privacidade bloqueia
            # padrões reais de agência/conta). O parser deve descartá-la.
            self.cell(0, 5, "CLIENTE EXEMPLO FICTÍCIO     Ag XXXX / XXXXXX",
                      new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "B", 9)
            self.cell(0, 6, "Operações", new_x="LMARGIN", new_y="NEXT")

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "", 6.5)
            self.cell(0, 3.5, f"Data posição: {fmt_d(DATA_POSICAO)} - Valores sujeitos a "
                      "confirmação.", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 3.5, "O Valor Líquido considera a dedução de IR e IOF sobre o "
                      "rendimento, quando aplicável.", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 3.5, f"{self.page_no()} de {{nb}}", align="R")

    pdf = MapaPDF(orientation="L", unit="mm", format="A4")
    pdf.set_creator("credito-privado-sim make_samples.py (dados fictícios)")
    pdf.set_creation_date(dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.timezone.utc))
    pdf.set_margins(5, 5, 5)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages("{nb}")
    pdf.add_page()
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_line_width(0.1)
    widths = tuple(w for _, w in COLUNAS_MAPA)
    head_style = FontFace(emphasis="BOLD", fill_color=(225, 225, 225))
    with pdf.table(
        col_widths=widths,
        width=sum(widths),
        align="LEFT",
        text_align="LEFT",
        line_height=3.0,
        headings_style=head_style,
        repeat_headings=1,
        v_align="MIDDLE",
    ) as table:
        table.row([c for c, _ in COLUNAS_MAPA])
        # Repete a carteira para a tabela passar de uma página (tabela multi-página);
        # a segunda volta usa quantidades diferentes para não duplicar lotes.
        for rodada in range(2):
            for l in LOTES:
                if rodada == 1:
                    if l.tipo in {"CDB", "CPR"}:
                        continue
                    l = Lote(**{**l.__dict__, "quantidade": l.quantidade // 2 + 7,
                                "operacao": "14/07/2026", "pu_operacao": round(l.pu_curva * 0.985, 2)})
                table.row(linha_mapa(l))
    pdf.output(str(path))


def make_mapa_pdf_layout_real(path: Path) -> None:
    """Mesmos lotes fictícios, mas com a ESTRUTURA observada no Mapa real (sem dado real):
    cada palavra é um texto separado, células alinhadas ao topo, cabeçalho em duas linhas,
    código do papel na última linha do Título, espaços de kerning dentro de números e códigos,
    rodapé "Data posição ... x de y" numa linha e nota iniciada por "*"."""
    from fpdf import FPDF

    W, H = 841.89, 595.28
    starts = [34.0, 93.95, 136.96, 179.96, 232.96, 275.95, 315.95, 355.94, 405.94, 455.94,
              505.94, 555.93, 605.93, 655.93, 705.93, 755.93]
    widths = [b - a - 4 for a, b in zip(starts, starts[1:] + [W - 20])]
    head1 = ["Título", "Emissão", "Vencimento", "Emissor", "Operação", "Taxa", "Quantidade",
             "PU Operação", "PU Curva", "Valor Bruto", "PU Mercado", "Valor Bruto", "IR", "IOF",
             "Valor Líquido", "Rendimento"]
    head2 = {5: "Operação", 9: "(curva)", 11: "(mercado)"}
    LS, GAP, FS = 8.36, 13.87, 6.5  # entrelinha, distância entre linhas da tabela, fonte

    pdf = FPDF(orientation="L", unit="pt", format="A4")
    pdf.set_creator("credito-privado-sim make_samples.py (dados fictícios)")
    pdf.set_creation_date(dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.timezone.utc))
    pdf.set_auto_page_break(False)
    pdf.alias_nb_pages("{nb}")
    pdf.set_font("Helvetica", "", FS)

    def words(x: float, y: float, text: str, kern_at: int | None = None) -> None:
        """Escreve palavra por palavra (como o PDF real). `kern_at` parte uma palavra em duas
        com folga extra, simulando o espaço de kerning que o pypdf enxerga."""
        for k, wd in enumerate(text.split(" ")):
            if kern_at is not None and k == kern_at and len(wd) > 3:
                a, b = wd[:-3], wd[-3:]
                pdf.text(x, y, a)
                pdf.text(x + pdf.get_string_width(a) + 1.6, y, b)
            else:
                pdf.text(x, y, wd)
            x += pdf.get_string_width(wd + " ")

    def wrap(text: str, width: float) -> list[str]:
        lines, cur = [], ""
        for wd in text.split(" "):
            cand = (cur + " " + wd).strip()
            if cur and pdf.get_string_width(cand) > width:
                lines.append(cur)
                cur = wd
            else:
                cur = cand
        return lines + ([cur] if cur else [])

    def new_page() -> float:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        words(30, 22.5, "Mapa de Posição")
        pdf.set_font("Helvetica", "", 7)
        # Linha do cliente FICTÍCIA e sem dígitos; o parser a descarta.
        words(30, 35.7, "Cliente: EXEMPLO FICTÍCIO Ag XXXX / XXXXXXX / XXXXXX")
        pdf.set_font("Helvetica", "B", 7)
        words(30, 69.4, "Operações")
        pdf.set_font("Helvetica", "B", FS)
        y1 = H - 513.92
        for i, lbl in enumerate(head1):
            words(starts[i], y1, lbl)
        for i, lbl in head2.items():
            words(starts[i], y1 + LS, lbl)
        pdf.set_font("Helvetica", "", FS)
        return H - 483.92

    def footer() -> None:
        pdf.set_font("Helvetica", "", 6)
        words(30, H - 23.74, f"Data posição: {fmt_d(DATA_POSICAO)}. Gerado em 30 de outubro "
              f"de 2026, 18:00:00 {pdf.page_no()} de {{nb}}")
        words(30, H - 16.02, "*O Valor líquido considera a dedução de impostos (IR e IOF). "
              "Para títulos isentos, o valor líquido é calculado sem IR.")
        pdf.set_font("Helvetica", "", FS)

    y = new_page()
    for n, l in enumerate(LOTES):
        vals = linha_mapa(l)
        # Título com o código sozinho na última linha, como no real; CDB com código "quebrado".
        cod = l.codigo if l.tipo != "CDB" else l.codigo[:-2] + " " + l.codigo[-2:]
        vals[0] = l.titulo.rsplit(" - ", 1)[0] + " - " + cod
        cells = [wrap(v, widths[i]) for i, v in enumerate(vals)]
        nlines = max(len(c) for c in cells)
        if y + (nlines - 1) * LS > H - 40:
            footer()
            y = new_page()
        for i, lines in enumerate(cells):
            for k, line in enumerate(lines):
                x = starts[i]
                if line == "-":
                    x += 15  # traço deslocado, como no real
                kern = 1 if (n % 3 == 0 and i >= 7 and line.startswith("R$")) else None
                words(x, y + k * LS, line, kern_at=kern)
        y += (nlines - 1) * LS + GAP
    footer()
    pdf.output(str(path))


# --------------------------------------------------------------------------------------
# Runflow (XLSX)
# --------------------------------------------------------------------------------------
def _internas_exemplo() -> dict[str, str]:
    import tomllib

    cfg = tomllib.loads((ROOT / "config" / "runflow_columns.example.toml").read_text("utf-8"))
    return {campo: spec["cabecalho"] for campo, spec in cfg["colunas_internas"].items()}


_INTERNAS = _internas_exemplo()

CABECALHO_RUNFLOW = [
    "Código", "Empresa", "Produto", "Taxa de Compra", "Indexador", "Distribuição",
    "Lastro Disponível", "QTDs disponíveis", "Vencimento", "Duration", "B Ref.",
    "Taxa de Emissão", "Cupom", "Amortização", "Setor de Atuação",
    "Observação",  # coluna EXTRA de propósito: o parser localiza colunas pelo nome
    "Rating", "Agência", "Investidor Qualificado?", "Isento?", "Garantia na Emissão",
    # Colunas internas: nomes GENÉRICOS do config de exemplo (os reais ficam no config local).
    *[_INTERNAS[c] for c in ("fee", "melhora", "comp_a", "comp_b", "delta_a", "delta_b")],
]

# (código, empresa, produto, taxa, indexador, distrib., lastro, venc, duration, bref,
#  taxa_emissao, cupom, amortização, setor, rating, agência, qualif., isento, garantia)
RUNFLOW = [
    ("XALF12", "Energia Alfa S.A.", "DEB", 0.0712, "IPCA", "Ativa", 2_500_000, "15/05/2032", 4.31, "B32", 0.0650, "Mai/Nov", "Bullet", "Energia Elétrica", "brAAA", "S&P", "Geral", "Sim", "Quirografária"),
    ("XALF23", "Energia Alfa S.A.", "DEB", 0.0738, "IPCA", "Ativa", 4_000_000, "15/11/2033", 5.12, "B33", 0.0720, "Mai/Nov", "Anual (Início 2031)", "Energia Elétrica", "AAA", "Fitch", "Geral", "Sim", "Quirografária"),
    ("XOME11", "Transmissora Ômega S.A.", "DEB", 0.0772, "IPCA", "Ativa", 6_000_000, "15/06/2034", 5.44, "B35", 0.0745, "Jun/Dez", "Bullet", "Energia Elétrica", "AAAbr", "Moody's", "Geral", "Sim", "Real"),
    ("XBET21", "Saneamento Beta S.A.", "DEB", 0.0755, "IPCA", "Ativa", 1_200_000, "15/09/2035", 6.02, "B35", 0.0710, "Mar/Set", "Mar/Set (Início 2034)", "Saneamento", "brAA+", "S&P", "Geral", "Sim", "Quirografária"),
    ("XSIG32", "Saneamento Sigma S.A.", "DEB", 0.0805, "IPCA", "Ativa", 3_500_000, "15/03/2036", 6.35, "B37", 0.0790, "Mar/Set", "Anual (Início 2034)", "Saneamento", "AA", "Fitch", "Geral", "Sim", "Real"),
    ("XKAP31", "Rodovias Kappa Concessionária S.A.", "DEB", 0.0681, "IPCA", "Ativa", 900_000, "15/10/2031", 3.88, "B30", 0.0598, "Abr/Out", "Anual (Início 2029)", "Rodovias", "brAA", "S&P", "Geral", "Sim", "Real"),
    ("XRHO27", "Rodovias Rho S.A.", "DEB", 0.0742, "IPCA", "Ativa", 5_000_000, "15/12/2032", 4.60, "B32", 0.0740, "Jun/Dez", "Semestral (Início Dez 30)", "Rodovias", "AA+", "Fitch", "Geral", "Sim", "Real"),
    ("XCRI26A01", "Zeta Securitizadora S.A.", "CRI", 0.0745, "IPCA", "Ativa", 700_000, "15/02/2034", 5.05, "B33", 0.0680, "Mensal", "Mensal", "Imobiliário", "brAA", "S&P", "Geral", "Sim", "Alienação fiduciária"),
    ("XCRI26B04", "Pi Securitizadora S.A.", "CRI", 0.0798, "IPCA", "Ativa", 2_000_000, "15/08/2034", 5.31, "B35", 0.0795, "Mensal", "Mensal", "Imobiliário", "AA-", "Fitch", "Qualificado", "Sim", "Alienação fiduciária"),
    ("XCRA24C07", "Mi Securitizadora S.A.", "CRA", 0.0779, "IPCA", "Ativa", 1_500_000, "15/04/2033", 4.85, "B33", 0.0735, "Abr/Out", "Anual (Início 2031)", "Agronegócio", "brAA+", "S&P", "Geral", "Sim", "Cessão fiduciária"),
    ("XCRA26A03", "Tau Securitizadora S.A.", "CRA", 0.0830, "IPCA", "Ativa", 3_000_000, "15/05/2033", 4.95, "B33", 0.0825, "Mai/Nov", "Bullet", "Agronegócio", "A+", "Fitch", "Geral", "Sim", "Aval"),
    ("XGAM13", "Logística Gama Participações S.A.", "DEB", 0.1395, "Pré", "Ativa", 800_000, "15/03/2029", 2.05, None, 0.1307, "Mar/Set", "Bullet", "Logística", "AA", "Fitch", "Geral", "Não", "Quirografária"),
    ("XUPS14", "Logística Upsilon S.A.", "DEB", 0.1437, "Pré", "Ativa", 2_200_000, "15/06/2029", 2.21, None, 0.1420, "Jun/Dez", "Bullet", "Logística", "AA", "S&P", "Geral", "Não", "Quirografária"),
    ("XPHI12", "Construtora Phi S.A.", "DEB", 0.1510, "Pré", "Encerrada", 0, "15/09/2029", 2.38, None, 0.1500, "Mar/Set", "Bullet", "Construção", "A", "Fitch", "Geral", "Não", "Quirografária"),
    ("XDEL14", "Telecom Delta S.A.", "DEB", 1.0420, "%CDI", "Ativa", 1_000_000, "15/06/2030", 3.10, None, 1.0450, "Jun/Dez", "Anual (Início 2028)", "Telecomunicações", "brAA+", "S&P", "Geral", "Não", "Quirografária"),
    ("XCHI15", "Telecom Chi S.A.", "DEB", 1.0650, "%CDI", "Ativa", 2_800_000, "15/08/2030", 3.25, None, 1.0600, "Fev/Ago", "Bullet", "Telecomunicações", "AA", "Fitch", "Geral", "Não", "Quirografária"),
    ("XCRA25B02", "Eta Securitizadora de Créditos do Agronegócio S.A.", "CRA", 0.9550, "%CDI", "Ativa", 1_100_000, "15/07/2028", 1.65, None, 0.9400, "Jan/Abr/Jul/Out", "Bullet", "Agronegócio", "AAA", "Fitch", "Geral", "Sim", "Cessão fiduciária"),
    ("XCRA26C05", "Psi Securitizadora S.A.", "CRA", 0.9750, "%CDI", "Ativa", 1_900_000, "15/09/2028", 1.80, None, 0.9750, "Mensal", "Bullet", "Agronegócio", "AA", "S&P", "Geral", "Sim", "Penhor"),
    ("XEPS11", "Varejo Epsilon Comércio S.A.", "DEB", 0.0135, "+CDI", "Ativa", 600_000, "15/12/2028", 1.95, None, 0.0120, "Jun/Dez", "Bullet", "Varejo", "A+", "Fitch", "Geral", "Não", "Quirografária"),
    ("XOMI16", "Varejo Ômicron S.A.", "DEB", 0.0160, "+CDI", "Ativa", 2_400_000, "15/02/2029", 2.10, None, 0.0155, "Fev/Ago", "Bullet", "Varejo", "AA-", "S&P", "Geral", "Não", "Quirografária"),
    ("XLAM12", "Papel Lambda Indústria S.A.", "DEB", 0.0102, "+CDI", "Ativa", 500_000, "15/09/2029", 2.45, None, 0.0095, "Mar/Set", "Anual (Início 2027)", "Papel e Celulose", "brAAA", "S&P", "Geral", "Não", "Quirografária"),
    ("XNU17", "Celulose Nu S.A.", "DEB", 0.0118, "+CDI", "Ativa", 3_100_000, "15/03/2030", 2.70, None, 0.0115, "Mar/Set", "Bullet", "Papel e Celulose", "AAA", "Fitch", "Geral", "Não", "Quirografária"),
    ("XXI18", "Holding Xi S.A.", "DEB", 0.0210, "+CDI", "Ativa", 1_000_000, "15/05/2030", 2.90, None, 0.0200, "Mai/Nov", "Bullet", "Holding", "0", None, "Qualificado", "Não", "Quirografária"),
    ("XCPR001", "Fazenda Exemplo Ltda.", "CPR", 0.1480, "Pré", "Ativa", 400_000, "30/06/2028", 1.50, None, 0.1480, "Bullet", "Bullet", "Agronegócio", "-", None, "Qualificado", "Sim", "Penhor de safra"),
]


def make_runflow_xlsx(path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Consolidado"
    ws["A1"] = "Runflow — Crédito Privado (ARQUIVO FICTÍCIO DE EXEMPLO)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Atualizado em {fmt_d(DATA_POSICAO)}"
    # Bloco de busca (linhas 3–5) que o parser deve ignorar
    ws["B3"] = "Buscar código:"
    ws["C3"] = "XALF12"
    ws["B4"] = "Taxa:"
    ws["C4"] = 0.0712
    ws["C4"].number_format = "0.00%"
    ws["B5"] = "Vencimento:"
    ws["C5"] = "15/05/2032"
    ws["A8"] = "Taxas indicativas sujeitas a alteração sem aviso prévio."

    header_row = 10
    fill = PatternFill("solid", fgColor="DDDDDD")
    for j, nome in enumerate(CABECALHO_RUNFLOW, start=1):
        c = ws.cell(row=header_row, column=j, value=nome)
        c.font = Font(bold=True)
        c.fill = fill

    col = {nome: j for j, nome in enumerate(CABECALHO_RUNFLOW, start=1)}
    for i, r in enumerate(RUNFLOW):
        (cod, emp, prod, taxa, idx, dist, lastro, venc, dur, bref, tx_em, cupom, amort,
         setor, rating, agencia, qualif, isento, garantia) = r
        row = header_row + 1 + i
        pu_ref = 1000.0

        def put(nome, valor, fmt=None):
            c = ws.cell(row=row, column=col[nome], value=valor)
            if fmt:
                c.number_format = fmt
            return c

        put("Código", cod)
        put("Empresa", emp)
        put("Produto", prod)
        # Duas linhas trazem a taxa como TEXTO com vírgula, para testar os dois formatos.
        if i in (3, 14):
            put("Taxa de Compra", num_br(taxa * 100, 2) + "%")
        else:
            put("Taxa de Compra", taxa, "0.00%")
        put("Indexador", idx)
        put("Distribuição", dist)
        put("Lastro Disponível", lastro, '"R$" #,##0.00')
        put("QTDs disponíveis", int(lastro // pu_ref))
        put("Vencimento", d(venc), "dd/mm/yyyy")
        # Uma linha com duration como texto "3,88" (vírgula decimal)
        put("Duration", num_br(dur, 2) if i == 5 else dur, None if i == 5 else "0.00")
        put("B Ref.", bref)
        put("Taxa de Emissão", tx_em, "0.00%")
        put("Cupom", cupom)
        put("Amortização", amort)
        put("Setor de Atuação", setor)
        put("Observação", "Oferta 476" if i % 5 == 0 else None)
        put("Rating", rating)
        put("Agência", agencia)
        put("Investidor Qualificado?", qualif)
        put("Isento?", isento)
        put("Garantia na Emissão", garantia)
        put(_INTERNAS["fee"], round(0.004 + 0.0005 * (i % 6), 4), "0.00%")
        put(_INTERNAS["melhora"], round(0.0005 + 0.0002 * (i % 4), 4), "0.00%")
        put(_INTERNAS["comp_a"], round(-0.0010 + 0.0004 * (i % 5), 4), "0.00%")
        put(_INTERNAS["comp_b"], round(-0.0008 + 0.0003 * (i % 6), 4), "0.00%")
        put(_INTERNAS["delta_a"], round(-10 + 4 * (i % 5), 1))
        put(_INTERNAS["delta_b"], round(-8 + 3 * (i % 6), 1))

    for j in range(1, len(CABECALHO_RUNFLOW) + 1):
        ws.column_dimensions[ws.cell(row=header_row, column=j).column_letter].width = 16
    ws.freeze_panes = ws.cell(row=header_row + 1, column=2)
    wb.properties.creator = "credito-privado-sim make_samples.py (dados fictícios)"
    wb.properties.created = wb.properties.modified = dt.datetime(2026, 10, 30, 12, 0)
    wb.save(str(path))
    _zip_deterministico(path)


def _zip_deterministico(path: Path) -> None:
    """Regrava o .xlsx com data fixa nos membros do zip (arquivo idêntico a cada geração)."""
    import zipfile

    with zipfile.ZipFile(path) as zin:
        items = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in items:
            if name == "docProps/core.xml":  # openpyxl grava "modificado em = agora"
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>2026-10-30T12:00:00Z", data)
            zi = zipfile.ZipInfo(name, date_time=(2026, 10, 30, 12, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_mapa_pdf(OUT / "mapa_posicoes_exemplo.pdf")
    make_mapa_pdf_layout_real(OUT / "mapa_posicoes_layout_real.pdf")
    make_runflow_xlsx(OUT / "runflow_exemplo.xlsx")
    for p in sorted(OUT.iterdir()):
        print(f"gerado: {p.relative_to(ROOT)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
