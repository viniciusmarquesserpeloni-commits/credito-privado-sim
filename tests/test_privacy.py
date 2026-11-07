"""Regra 4 — CI de privacidade.

Falha se:
- existir arquivo de dados (pdf, xlsx, xls, xlsm, csv, txt) fora de data/samples/ e data/public/;
- qualquer arquivo versionado (ou prestes a ser) contiver frases de marcação de confidencialidade,
  nomes de colunas internas do Runflow, nome de instituição, ou um padrão de agência/conta
  ("Ag 1234 / 56789"). A comparação ignora acentos e maiúsculas.

PDFs e XLSX de amostra são inspecionados pelo TEXTO extraído (o binário é comprimido).
Este arquivo é o único excluído da varredura de frases, porque precisa listá-las.
"""

from __future__ import annotations

import io
import re
import subprocess
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THIS = Path(__file__).resolve()

DATA_EXT = {".pdf", ".xlsx", ".xls", ".xlsm", ".csv", ".txt"}
ALLOWED_DATA_DIRS = ("data/samples/", "data/public/")

# Comparados SEM acento e em maiúsculas (ver `scan`).
FORBIDDEN_PHRASES = [
    "MATERIAL INTERNO",
    "USO EXCLUSIVAMENTE INTERNO",
    "NAO COMPARTILHAR",
    # Colunas internas do Runflow e instituição: só em config/*.local.toml (fora do git).
    "FEE ESTIMADO",
    "MELHORA MAX",
]
FORBIDDEN_WORDS = re.compile(r"(?<![A-Z])ITAU(?![A-Z])")
AGENCIA_CONTA = re.compile(r"\bAg\.?\s*\d{4}\s*/\s*\d+", re.IGNORECASE)

SKIP_DIRS = {".git", ".venv", "venv", "_site", "__pycache__", ".pytest_cache", "node_modules"}
LOCAL_ONLY = re.compile(r"\.local\.toml$")


def repo_files() -> list[str]:
    """Arquivos versionados + novos não ignorados (o que entraria num commit)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout.decode("utf-8")
        files = [f for f in out.split("\0") if f]
        if files:
            return [f for f in files if (ROOT / f).is_file()]
    except (OSError, subprocess.CalledProcessError):
        pass
    found = []
    for p in ROOT.rglob("*"):
        if (p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)
                and not LOCAL_ONLY.search(p.name)):
            found.append(p.relative_to(ROOT).as_posix())
    return found


def extract_text(path: Path) -> str:
    suf = path.suffix.lower()
    data = path.read_bytes()
    if suf == ".pdf":
        from pypdf import PdfReader

        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    if suf in {".xlsx", ".xlsm"}:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                parts.extend(str(v) for v in row if v is not None)
        wb.close()
        return "\n".join(parts)
    return data.decode("utf-8", errors="ignore")


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c)).upper()


def scan(text: str) -> list[str]:
    hits = []
    upper = _fold(text)
    for ph in FORBIDDEN_PHRASES:
        if ph in upper:
            hits.append(ph)
    m = FORBIDDEN_WORDS.search(upper)
    if m:
        hits.append(m.group(0))
    m = AGENCIA_CONTA.search(text)
    if m:
        hits.append(f"agência/conta: {m.group(0)!r}")
    return hits


# ----------------------------------------------------------------------------- testes
def test_no_data_files_outside_allowed_dirs():
    bad = [
        f for f in repo_files()
        if Path(f).suffix.lower() in DATA_EXT and not f.startswith(ALLOWED_DATA_DIRS)
    ]
    assert not bad, f"Arquivos de dados fora de data/samples|public: {bad}"


def test_no_internal_markers_or_account_patterns():
    problems = {}
    for f in repo_files():
        p = ROOT / f
        if p.resolve() == THIS:
            continue
        try:
            hits = scan(extract_text(p))
        except Exception as e:  # noqa: BLE001 — arquivo ilegível também é problema
            hits = [f"não foi possível ler: {e}"]
        if hits:
            problems[f] = hits
    assert not problems, f"Conteúdo proibido encontrado: {problems}"


def test_samples_exist():
    assert (ROOT / "data/samples/mapa_posicoes_exemplo.pdf").is_file()
    assert (ROOT / "data/samples/runflow_exemplo.xlsx").is_file()


@pytest.mark.parametrize(
    "text, should_hit",
    [
        ("Cliente FULANO  Ag 1234 / 567890", True),
        ("ag 0001/12", True),
        ("Ag XXXX / XXXXXX", False),
        ("material interno — não divulgar", True),
        ("Não compartilhar", True),
        ("Taxa de Compra 7,05%", False),
        ("Fee Estimado", True),
        ("melhora máx.", True),
        ("banco itaú", True),
        ("ITAU", True),
        ("Limitações e riscos", False),  # "ita" + "ç" não é instituição
        ("capitaução", False),
        ("Comparativo Plataforma A", False),
    ],
)
def test_scanner_detects_patterns(text, should_hit):
    assert bool(scan(text)) is should_hit


def test_local_config_is_ignored():
    out = subprocess.run(["git", "check-ignore", "config/runflow_columns.local.toml"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode == 128:
        pytest.skip("git indisponível")
    assert out.stdout.strip() == "config/runflow_columns.local.toml"
    assert "config/runflow_columns.local.toml" not in repo_files()


def test_gitignore_blocks_data_files():
    """Um arquivo de dados criado fora das pastas permitidas precisa ser ignorado pelo git."""
    probe_dir = ROOT / "tests"
    names = ["_probe.pdf", "_probe.xlsx", "_probe.csv", "_probe.txt"]
    try:
        for n in names:
            (probe_dir / n).write_bytes(b"x")
        out = subprocess.run(
            ["git", "check-ignore", *[f"tests/{n}" for n in names]],
            cwd=ROOT, capture_output=True, text=True,
        )
        if out.returncode == 128:
            pytest.skip("git indisponível")
        ignored = set(out.stdout.split())
        assert ignored == {f"tests/{n}" for n in names}
    finally:
        for n in names:
            (probe_dir / n).unlink(missing_ok=True)
