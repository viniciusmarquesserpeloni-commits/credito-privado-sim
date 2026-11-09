"""Monta o HTML ÚNICO e OFFLINE do simulador: dist/simulador_credito_privado.html.

Um só arquivo (~2,5 MB) com tudo dentro: CSS, motor JavaScript (offline/src/*.mjs, conferido
contra o Python), interface, leitor de PDF (pdf.js, Apache-2.0), dados públicos de data/public/,
amostras fictícias e o config de EXEMPLO das colunas internas. Abre com duplo clique, sem
internet e sem servidor. Os arquivos do usuário são lidos só no navegador.

Nunca embute config/*.local.toml nem arquivo real: só o que já está versionado.

Uso:
    python scripts/update_public_data.py     # opcional: dados públicos do dia
    python scripts/build_offline.py [--out caminho.html]
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "offline" / "src"
VENDOR = ROOT / "offline" / "vendor" / "pdfjs"
OUT = ROOT / "dist" / "simulador_credito_privado.html"
MODULES = ["engine.mjs", "parsers.mjs", "analysis.mjs", "xlsx.mjs", "ui.mjs"]
PUBLIC = ["cdi", "selic_meta", "ipca_mensal", "focus_selic", "focus_ipca", "tesouro_direto"]
BRT = dt.timezone(dt.timedelta(hours=-3))


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("ascii")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip() or "local"
    except (OSError, subprocess.CalledProcessError):
        return "local"


def _safe_script_text(text: str, what: str) -> str:
    """Conteúdo de <script>: não pode fechar a tag nem abrir comentário HTML."""
    if re.search(r"</script|<!--", text, re.I):
        raise SystemExit(f"{what} contém '</script' ou '<!--': ajuste o código-fonte")
    return text


def build(out: Path = OUT) -> Path:
    data = {
        "public": {n: json.loads((ROOT / "data" / "public" / f"{n}.json").read_text("utf-8"))
                   for n in PUBLIC},
        "exampleToml": (ROOT / "config" / "runflow_columns.example.toml").read_text("utf-8"),
        "samples": {"mapa": _b64(ROOT / "data" / "samples" / "mapa_posicoes_layout_real.pdf"),
                    "runflow": _b64(ROOT / "data" / "samples" / "runflow_exemplo.xlsx")},
        "metodologia": (ROOT / "docs" / "metodologia.md").read_text("utf-8"),
        "build": {"date": dt.datetime.now(BRT).strftime("%d/%m/%Y %H:%M"), "commit": _commit()},
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/").replace("<!--", "<\\!--")
    modules = "\n".join(
        f'<script type="text/plain" data-mod="{m}">'
        f'{_safe_script_text((SRC / m).read_text("utf-8"), m)}</script>' for m in MODULES)
    html = (SRC / "index.template.html").read_text("utf-8")
    for key, val in {"/*__CSS__*/": (SRC / "styles.css").read_text("utf-8"),
                     "/*__DATA__*/": data_json,
                     "/*__PDFJS_LIB__*/": _b64(VENDOR / "pdf.min.mjs"),
                     "/*__PDFJS_WORKER__*/": _b64(VENDOR / "pdf.worker.min.mjs"),
                     "<!--__MODULES__-->": modules}.items():
        if key not in html:
            raise SystemExit(f"marcador {key} ausente no modelo")
        html = html.replace(key, val, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    dest = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT
    p = build(dest)
    print(f"gerado {p} ({p.stat().st_size / 1e6:.2f} MB)")
