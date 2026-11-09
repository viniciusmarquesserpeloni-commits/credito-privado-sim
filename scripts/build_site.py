"""Monta _site/ (o que é publicado no GitHub Pages) a partir do repositório.

_site/
  index.html          <- web/index.html (carrega o stlite e monta o app)
  manifest.json       <- lista de arquivos Python/dados que o stlite copia para o navegador
  app/..., src/cpsim/..., data/samples/..., data/public/*.json

Só entram código, amostras fictícias e dados públicos. Nenhum arquivo de usuário passa por aqui.

Uso:  python scripts/build_site.py            (só monta)
      python scripts/build_site.py --serve    (monta e serve em http://localhost:8790)
"""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"

INCLUDE = ["app/**/*.py", "src/cpsim/**/*.py", "data/samples/*", "data/public/*.json",
           "config/*.example.toml", "docs/metodologia.md", ".streamlit/config.toml"]
# Nunca publicar (defesa extra além do INCLUDE): config local com nomes reais.
NEVER = (".local.toml",)

# Pacotes instalados no navegador. Sem versão = a que vem na distribuição Pyodide do stlite;
# com versão = baixado do PyPI pelo micropip (só Python puro).
STLITE_REQUIREMENTS = ["pandas", "openpyxl", "pypdf==6.21.4"]

ENTRYPOINT = "app/app.py"
READY_MARKER = "Simulador de trocas"  # texto que indica que o app desenhou a 1ª tela


def _clean(d: Path) -> None:
    """Esvazia _site/ arquivo a arquivo. Em pasta sincronizada (OneDrive), apagar diretórios
    pode falhar por bloqueio momentâneo; pastas vazias que sobrarem não fazem mal."""
    d.mkdir(exist_ok=True)
    for p in sorted(d.rglob("*"), key=lambda p: -len(p.parts)):
        try:
            p.unlink() if p.is_file() else p.rmdir()
        except OSError:
            if p.is_file():
                raise


def main() -> None:
    _clean(SITE)
    files: list[str] = []
    for pattern in INCLUDE:
        for p in sorted(ROOT.glob(pattern)):
            if not p.is_file() or "__pycache__" in p.parts or p.name.endswith(NEVER):
                continue
            rel = p.relative_to(ROOT).as_posix()
            dest = SITE / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            files.append(rel)
    shutil.copy2(ROOT / "web" / "index.html", SITE / "index.html")
    # GitHub Pages serve 404.html para caminhos desconhecidos: recarregar em /trocas, /carteira…
    # abre o próprio app (que lê o caminho e mostra a tela certa) em vez do erro do GitHub.
    shutil.copy2(ROOT / "web" / "index.html", SITE / "404.html")
    (SITE / ".nojekyll").touch()
    # Versão offline (um único HTML), gerada com os mesmos dados públicos deste build.
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_offline import build as build_offline

    build_offline(SITE / "simulador_credito_privado.html")
    manifest = {
        "entrypoint": ENTRYPOINT,
        "requirements": STLITE_REQUIREMENTS,
        "files": files,
        "readyMarker": READY_MARKER,
    }
    (SITE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"_site/ montado com {len(files)} arquivos")


def serve(port: int = 8790) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"servindo _site/ em http://localhost:{port}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
    if "--serve" in sys.argv:
        i = sys.argv.index("--serve")
        arg = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        serve(int(arg) if arg.isdigit() else 8790)
