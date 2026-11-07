"""Leitor do Mapa de Posições (PDF do banco) -> `MapaPositions` com `Lot`s tipados.

Estratégia: extrair cada fragmento de texto com sua posição (x, y) via pypdf e reconstruir a
tabela "Operações" pelas colunas do cabeçalho. Roda igual no Python local e no navegador.

Layout real (calibrado em 07/11/2026, só por estrutura): cada palavra é um fragmento; o
cabeçalho tem rótulos em 1–2 linhas ("PU Operação", "Taxa / Operação", "Valor Bruto / (curva)");
células alinhadas ao TOPO; o código do papel vem na última linha do Título, após " - "; o PDF
insere espaços de kerning dentro de números ("99 . 999,99") e até de códigos.
A amostra fictícia usa linhas inteiras e alinhamento ao MEIO; os dois casos são tratados.

Privacidade (regra 10): só os fragmentos abaixo do cabeçalho da tabela e fora do rodapé viram
dados. Título do relatório e linha do cliente (nome/agência/conta) são descartados aqui; da área
fora da tabela só a data da posição é aproveitada.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from ..models import Indexer, Lot, MapaPositions, Rate
from ..normalize import norm_header, parse_brl, parse_date_br, squash_number_gaps

COLUMNS = [
    "titulo", "emissao", "vencimento", "emissor", "operacao", "taxa_operacao", "quantidade",
    "pu_operacao", "pu_curva", "valor_bruto_curva", "pu_mercado", "valor_bruto_mercado",
    "ir", "iof", "valor_liquido", "rendimento",
]
_LABELS = {
    "titulo": "titulo", "emissao": "emissao", "vencimento": "vencimento", "emissor": "emissor",
    "operacao": "operacao", "taxa operacao": "taxa_operacao", "quantidade": "quantidade",
    "pu operacao": "pu_operacao", "pu curva": "pu_curva",
    "valor bruto (curva)": "valor_bruto_curva", "pu mercado": "pu_mercado",
    "valor bruto (mercado)": "valor_bruto_mercado", "ir": "ir", "iof": "iof",
    "valor liquido": "valor_liquido", "rendimento": "rendimento",
}
# Comparação sem espaços: o PDF quebra palavras ("Quantida de") e insere espaços ("T axa").
HEADER_MAP = {k.replace(" ", ""): v for k, v in _LABELS.items()}

ASSET_TYPES = {"DEB", "CRI", "CRA", "CDB", "CPR", "LCA", "LCI", "LF", "LIG", "CCB", "NC", "CDCA"}

_RE_DATA_POSICAO = re.compile(
    r"Data\s*(?:da\s*)?posi[cç][aã]o:?\s*(\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4})", re.I)
_RE_PAGINA = re.compile(r"^\s*\d+\s*de\s*\d+\s*$", re.I)
# Rodapé: "Data posição: ... x de y" e a nota "*O Valor líquido ... dedução de impostos (IR e IOF)".
_RE_RODAPE = re.compile(
    r"^\s*\*|Data\s*(?:da\s*)?posi[cç][aã]o|dedu[cç][aã]o\s*de\s*(?:IR|impostos)"
    r"|valor\s*l[ií]quido\s*(?:considera|[ée]\s*calculado)", re.I)
_RE_AGENCIA = re.compile(r"\bAg\.?\s*[\dX]{3,5}\s*/", re.I)
_RE_QTD = re.compile(r"^\d{1,3}(\.\d{3})+$|^\d+$")
_RE_DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_RE_TITULO_FIM = re.compile(r"(.+?\s-\s*[A-Z0-9]{4,})(?=\s|$)")
_RE_PCT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*%")
_NUM = r"(-?\d+(?:[.,]\d+)?)"
_RE_TAXA_OP = [
    (re.compile(rf"^(?:DI|CDI)\s*\+\s*{_NUM}\s*%?$", re.I), Indexer.CDI_SPREAD),
    (re.compile(rf"^{_NUM}\s*%?\s*\+\s*(?:DI|CDI)$", re.I), Indexer.CDI_SPREAD),
    (re.compile(rf"^{_NUM}\s*%\s*(?:do\s*)?(?:DI|CDI)$", re.I), Indexer.CDI_PCT),
    (re.compile(rf"^(?:DI|CDI)\s*{_NUM}\s*%$", re.I), Indexer.CDI_PCT),
    (re.compile(rf"^{_NUM}\s*%\s*IPCA$", re.I), Indexer.IPCA),
    (re.compile(rf"^IPCA\s*\+?\s*{_NUM}\s*%$", re.I), Indexer.IPCA),
    (re.compile(rf"^{_NUM}\s*%\s*PR[EÉ]$", re.I), Indexer.PRE),
    (re.compile(rf"^PR[EÉ]\s*{_NUM}\s*%$", re.I), Indexer.PRE),
]


@dataclass(frozen=True)
class Fragment:
    page: int
    x: float
    y: float
    text: str


# ----------------------------------------------------------------------------- extração
def extract_fragments(data: bytes) -> tuple[list[Fragment], int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    frags: list[Fragment] = []
    for pno, page in enumerate(reader.pages, start=1):
        def visitor(text, cm, tm, font_dict, font_size, _p=pno):
            t = (text or "").strip()
            if not t:
                return
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            for part in t.split("\n"):
                part = part.strip()
                if part:
                    frags.append(Fragment(_p, round(x, 2), round(y, 2), part))

        page.extract_text(visitor_text=visitor)
    return frags, len(reader.pages)


def _lines(frags: list[Fragment], tol: float = 1.0) -> list[list[Fragment]]:
    """Agrupa fragmentos da mesma página na mesma linha (y próximo), em ordem de leitura."""
    out: list[list[Fragment]] = []
    for f in sorted(frags, key=lambda f: (f.page, -f.y, f.x)):
        if out and out[-1][0].page == f.page and abs(out[-1][0].y - f.y) <= tol:
            out[-1].append(f)
        else:
            out.append([f])
    return [sorted(line, key=lambda f: f.x) for line in out]


def _line_text(line: list[Fragment]) -> str:
    return " ".join(f.text for f in line)


# ----------------------------------------------------------------------------- cabeçalho
def _is_prefix(key: str) -> bool:
    return any(k.startswith(key) for k in HEADER_MAP)


def _header_columns(band: list[Fragment], y_line1: float) -> list[tuple[float, str]]:
    """Monta as colunas do cabeçalho: palavras da 1ª linha agrupadas enquanto formam o começo
    de um rótulo conhecido; palavras da 2ª linha anexadas à coluna em que caem pelo x."""
    line1 = sorted([f for f in band if f.y >= y_line1 - 2.0], key=lambda f: f.x)
    line2 = sorted([f for f in band if f.y < y_line1 - 2.0], key=lambda f: (-f.y, f.x))
    groups: list[list[Fragment]] = []
    for f in line1:
        if groups:
            cur = "".join(norm_header(g.text) for g in groups[-1]).replace(" ", "")
            nxt = (cur + norm_header(f.text)).replace(" ", "")
            if _is_prefix(nxt):
                groups[-1].append(f)
                continue
        groups.append([f])
    starts = [min(g.x for g in grp) for grp in groups]
    labels = ["".join(norm_header(g.text) for g in grp).replace(" ", "") for grp in groups]
    for f in line2:
        i = max((k for k, x0 in enumerate(starts) if f.x + 1.0 >= x0), default=0)
        labels[i] += norm_header(f.text).replace(" ", "")
    return list(zip(starts, labels))


# ----------------------------------------------------------------------------- linhas
def _partition(frags: list[Fragment], anchors: list[float]) -> list[list[Fragment]] | None:
    """Divide as linhas de uma coluna (ordem de leitura) em grupos contíguos, um por linha
    da tabela, minimizando a distância de cada grupo à âncora da linha (centro ou topo).
    Usado quando as células são alinhadas ao meio e encostam umas nas outras."""
    n, r = len(frags), len(anchors)
    if n < r or r == 0:
        return None
    ys = [f.y for f in frags]
    inf = float("inf")

    def cost(i: int, j: int, k: int) -> float:
        top, bot = ys[i], ys[j - 1]
        return min(abs((top + bot) / 2 - anchors[k]), abs(top - anchors[k]))

    dp = [[inf] * (n + 1) for _ in range(r + 1)]
    back = [[0] * (n + 1) for _ in range(r + 1)]
    dp[0][0] = 0.0
    for k in range(1, r + 1):
        for j in range(k, n - (r - k) + 1):
            best, arg = inf, 0
            for i in range(k - 1, j):
                v = dp[k - 1][i] + cost(i, j, k - 1)
                if v < best:
                    best, arg = v, i
            dp[k][j], back[k][j] = best, arg
    groups: list[list[Fragment]] = []
    j = n
    for k in range(r, 0, -1):
        i = back[k][j]
        groups.append(frags[i:j])
        j = i
    return groups[::-1]


# ----------------------------------------------------------------------------- campos
def parse_rate_text(txt: str) -> Rate | None:
    t = " ".join(squash_number_gaps(txt).split())
    for rx, idx in _RE_TAXA_OP:
        m = rx.match(t)
        if m:
            return Rate(idx, float(m.group(1).replace(",", ".")) / 100.0)
    return None


@dataclass(frozen=True)
class TitleParts:
    asset_type: str | None
    issuer: str
    rate: Rate | None
    maturity_text: str | None
    code: str | None


def parse_title(title: str) -> TitleParts:
    """'<TIPO> <EMISSOR> <INDEXADOR> <taxa> <dd/mm/aaaa> - <CÓDIGO>' (ordem de indexador e
    taxa pode variar: 'CDI 100%', '104.50% CDI', 'CDI + 1.20%')."""
    t = " ".join(squash_number_gaps(title).split())
    code = None
    body = t
    if " - " in t or t.endswith(" -"):
        body, _, tail = t.rpartition(" -")
        code = tail.replace(" ", "").strip("-") or None
    toks = body.split(" ")
    asset = toks[0].upper() if toks and toks[0].upper() in ASSET_TYPES else None
    rest = toks[1:] if asset else toks
    idx_pos, idx = None, None
    for i, tok in enumerate(rest):
        u = tok.upper().strip(",;")
        if u in {"IPCA", "IPCA+"}:
            idx_pos, idx = i, Indexer.IPCA
        elif u in {"PRE", "PRÉ", "PREFIXADO"}:
            idx_pos, idx = i, Indexer.PRE
        elif u in {"CDI", "DI", "CDI+", "DI+"}:
            plus = u.endswith("+") or (i + 1 < len(rest) and rest[i + 1].startswith("+"))
            idx_pos, idx = i, (Indexer.CDI_SPREAD if plus else Indexer.CDI_PCT)
        if idx_pos is not None:
            break
    issuer = " ".join(rest[:idx_pos] if idx_pos is not None else rest)
    after = " ".join(rest[idx_pos:]) if idx_pos is not None else ""
    m = _RE_PCT.search(after)
    rate = Rate(idx, float(m.group(1).replace(",", ".")) / 100.0) if (idx and m) else None
    dates = _RE_DATE.findall(body)
    return TitleParts(asset, issuer.strip(), rate, dates[-1] if dates else None, code)


def _to_int(s: str) -> int | None:
    s = s.replace(" ", "").strip()
    if not s or s == "-":
        return None
    try:
        return int(s.replace(".", ""))
    except ValueError:
        return None


# ----------------------------------------------------------------------------- principal
def parse_mapa(data: bytes) -> MapaPositions:
    frags, n_pages = extract_fragments(data)
    warnings: list[str] = []

    # Rodapé e data da posição: por LINHA reconstruída (no PDF real cada palavra é um fragmento).
    excluded: set[Fragment] = set()
    data_pos = None
    for line in _lines(frags):
        txt = _line_text(line)
        if data_pos is None:
            m = _RE_DATA_POSICAO.search(txt)
            if m:
                data_pos = parse_date_br(m.group(1))
        if _RE_PAGINA.match(txt) or _RE_RODAPE.search(txt) or _RE_AGENCIA.search(txt):
            excluded.update(line)
    if data_pos is None:
        warnings.append("Data da posição não encontrada no rodapé.")

    lots: list[Lot] = []
    for pno in range(1, n_pages + 1):
        pf = [f for f in frags if f.page == pno and f not in excluded]
        head = [f for f in pf if norm_header(f.text) == "titulo"]
        if not head:
            continue
        y_head = head[0].y
        band = [f for f in pf if abs(f.y - y_head) <= 10]
        starts: list[tuple[float, str]] = []
        for x0, label in _header_columns(band, y_head):
            col = HEADER_MAP.get(label)
            if col is None:
                warnings.append(f"Página {pno}: cabeçalho não reconhecido '{label}'.")
                continue
            starts.append((x0, col))
        missing = [c for c in COLUMNS if c not in {c2 for _, c2 in starts}]
        if missing:
            warnings.append(f"Página {pno}: colunas ausentes {missing}; página ignorada.")
            continue
        starts.sort()
        y_body_top = min(f.y for f in band) - 1
        body = [f for f in pf if f.y < y_body_top]

        def col_of(f: Fragment) -> str:
            col = starts[0][1]
            for x0, c in starts:
                if f.x + 1.0 >= x0:
                    col = c
            return col

        by_col: dict[str, list[Fragment]] = {c: [] for c in COLUMNS}
        for f in body:
            by_col[col_of(f)].append(f)

        anchors = sorted({f.y for f in by_col["quantidade"]
                          if _RE_QTD.match(f.text.replace(" ", ""))}, reverse=True)
        if not anchors:
            continue

        # Alinhamento ao topo? (o Título começa exatamente na altura da Quantidade)
        tit_ys = [f.y for f in by_col["titulo"]]
        hits = sum(any(abs(a - y) < 0.6 for y in tit_ys) for a in anchors)
        # Ao meio, um Título de 3 linhas também "acerta" a âncora com a linha do meio; por isso
        # exige-se também que o topo da 1ª linha da tabela coincida com a 1ª âncora.
        top_aligned = (hits >= 0.8 * len(anchors) and bool(tit_ys)
                       and abs(max(tit_ys) - anchors[0]) < 0.6)

        cells: list[dict[str, list[Fragment]]] = [{c: [] for c in COLUMNS} for _ in anchors]
        titles: list[str] | None = None
        if not top_aligned:
            # Alinhado ao meio: o Título se separa melhor pelo marcador de fim " - CÓDIGO".
            joined = " ".join(_line_text(ln) for ln in _lines(by_col["titulo"]))
            found = [m.group(1).strip() for m in _RE_TITULO_FIM.finditer(joined)]
            if len(found) == len(anchors):
                titles = found
        for c in COLUMNS:
            if c == "titulo" and titles is not None:
                continue
            if top_aligned:
                for f in by_col[c]:
                    above = [i for i, a in enumerate(anchors) if a >= f.y - 0.6]
                    if above:
                        cells[above[-1]][c].append(f)
                continue
            lines_c = _lines(by_col[c])
            groups = _partition([ln[0] for ln in lines_c], anchors)
            if groups is None:  # menos linhas que âncoras: vai pelo mais próximo
                for ln in lines_c:
                    i = min(range(len(anchors)), key=lambda k: abs(anchors[k] - ln[0].y))
                    cells[i][c].extend(ln)
                continue
            line_of = {id(ln[0]): ln for ln in lines_c}
            for i, grp in enumerate(groups):
                for head_frag in grp:
                    cells[i][c].extend(line_of[id(head_frag)])

        for i, cell in enumerate(cells):
            lots.append(_to_lot(pno, cell, titles[i] if titles is not None else None))

    return MapaPositions(data_pos, lots, n_pages, warnings, n_fragments=len(frags))


def _join(frs: list[Fragment]) -> str:
    return " ".join(f.text for f in sorted(frs, key=lambda f: (-f.y, f.x))).strip()


def _to_lot(page: int, cell: dict[str, list[Fragment]], title_text: str | None = None) -> Lot:
    def txt(c: str) -> str:
        if c == "titulo" and title_text is not None:
            return title_text
        return _join(cell[c])

    def num(c: str) -> float | None:
        try:
            return parse_brl(squash_number_gaps(txt(c)))
        except ValueError:
            return None

    title = " ".join(txt("titulo").split())
    tp = parse_title(title)
    rate_txt = " ".join(squash_number_gaps(txt("taxa_operacao")).split())
    lot = Lot(
        page=page,
        code=tp.code,
        asset_type=tp.asset_type,
        title=title,
        issuer=txt("emissor"),
        emission=parse_date_br(txt("emissao")),
        maturity=parse_date_br(txt("vencimento")),
        purchase_date=parse_date_br(txt("operacao")),
        rate=parse_rate_text(rate_txt),
        rate_text=rate_txt,
        title_rate=tp.rate,
        quantity=_to_int(txt("quantidade")),
        pu_purchase=num("pu_operacao"),
        pu_curve=num("pu_curva"),
        gross_curve=num("valor_bruto_curva"),
        pu_market=num("pu_mercado"),
        gross_market=num("valor_bruto_mercado"),
        ir=num("ir"),
        iof=num("iof"),
        net_value=num("valor_liquido"),
        income=num("rendimento"),
    )
    validate_lot(lot, raw_dates={"Emissão": txt("emissao"), "Vencimento": txt("vencimento"),
                                 "Operação": txt("operacao")})
    return lot


def _tol(q: int, gross: float) -> float:
    """Tolerância de Qtd × PU ≈ Valor Bruto. O PU exibido tem 2 casas, mas o banco calcula o
    Valor Bruto com mais precisão: no Mapa real a diferença relativa chega a ~1e-5. Usamos o
    maior entre 1 centavo por unidade e 0,005% do valor (erros de leitura dão desvios enormes)."""
    return max(0.05, q * 0.01, abs(gross) * 5e-5)


def validate_lot(lot: Lot, raw_dates: dict[str, str] | None = None) -> None:
    """Validação por linha (prompt 5.2 / metodologia 10.5). Preenche `lot.errors`."""
    e = lot.errors
    e.clear()
    lot.warnings.clear()
    if not lot.code or not re.fullmatch(r"[A-Z0-9]{4,}", lot.code):
        e.append("código não encontrado no Título")
    if lot.asset_type is None:
        e.append("tipo do papel não reconhecido no Título")
    if lot.rate is None:
        e.append(f"Taxa Operação não reconhecida: '{lot.rate_text}'")
    for nome, d in (("Emissão", lot.emission), ("Vencimento", lot.maturity),
                    ("Operação", lot.purchase_date)):
        if d is None:
            raw = (raw_dates or {}).get(nome, "")
            e.append(f"data inválida em {nome}: '{raw}'")
    q = lot.quantity
    if q is None or q <= 0:
        e.append("quantidade ausente")
        return
    if lot.pu_curve is not None and lot.gross_curve is not None:
        if abs(q * lot.pu_curve - lot.gross_curve) > _tol(q, lot.gross_curve):
            e.append("Quantidade × PU Curva ≠ Valor Bruto (curva)")
    elif lot.gross_curve is None:
        e.append("Valor Bruto (curva) ausente")
    if lot.pu_market is not None and lot.gross_market is not None:
        if abs(q * lot.pu_market - lot.gross_market) > _tol(q, lot.gross_market):
            e.append("Quantidade × PU Mercado ≠ Valor Bruto (mercado)")
    elif (lot.pu_market is None) != (lot.gross_market is None):
        e.append("PU Mercado e Valor Bruto (mercado) inconsistentes")
    base = lot.gross_market if lot.gross_market is not None else lot.gross_curve
    if base is not None and lot.net_value is not None:
        ded = (lot.ir or 0.0) + (lot.iof or 0.0)
        if abs(base - ded - lot.net_value) > max(0.05, abs(base) * 5e-5):
            # Aviso, não erro: no Mapa real há CPR sem PU Mercado com Valor Líquido abaixo
            # do Bruto e IR/IOF zerados (critério do próprio banco).
            lot.warnings.append("Valor Líquido ≠ Valor Bruto − IR − IOF (critério do arquivo)")
