"""Coleta os dados PÚBLICOS usados pelo simulador e grava em data/public/*.json.

Fontes (regra 5: só fontes abertas, sem robô para ANBIMA/B3):
- BCB SGS: CDI diário (12), meta Selic (432), IPCA mensal (433)
- BCB Focus (Olinda): Selic por reunião do Copom, IPCA anual e IPCA 12 meses (suavizada)
- Tesouro Transparente: preços e taxas do Tesouro Direto (taxas de VAREJO)

Cada arquivo grava `fonte`, `url`, `coletado_em` (ISO, horário de Brasília) e `dados`.
Se uma coleta falhar, o arquivo anterior é mantido e o erro vai para `_status.json`.

Uso:  python scripts/update_public_data.py
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public"
BRT = dt.timezone(dt.timedelta(hours=-3), "BRT")  # Brasília, sem horário de verão desde 2019
UA = {"User-Agent": "credito-privado-sim (coleta de dados publicos)"}
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
TD_CSV = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-"
          "7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/"
          "precotaxatesourodireto.csv")
TD_DIAS = 5  # datas-base mais recentes guardadas do Tesouro Direto
# Só os títulos usados: NTN-B (referência de spread IPCA+) e prefixados (curva pré, futuro).
TD_TITULOS = {"Tesouro IPCA+ com Juros Semestrais", "Tesouro IPCA+", "Tesouro Prefixado",
              "Tesouro Prefixado com Juros Semestrais"}


def _get(url: str, timeout: int = 90) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _json(url: str):
    return json.loads(_get(url).decode("utf-8"))


def _br_date(s: str) -> str:
    d, m, y = s.split("/")
    return f"{y}-{m}-{d}"


def _num(s: str) -> float | None:
    s = (s or "").strip()
    return float(s.replace(".", "").replace(",", ".")) if s else None


# ----------------------------------------------------------------------------- coletas
def sgs(serie: int, hoje: dt.date, anos: int = 2) -> tuple[str, list[dict]]:
    ini = (hoje - dt.timedelta(days=365 * anos)).strftime("%d/%m/%Y")
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json"
           f"&dataInicial={ini}&dataFinal={hoje.strftime('%d/%m/%Y')}")
    rows = _json(url)
    # A meta Selic (432) vem preenchida até a próxima reunião: corta em hoje.
    dados = [{"data": _br_date(r["data"]), "valor": float(r["valor"])} for r in rows]
    dados = [r for r in dados if r["data"] <= hoje.isoformat()]
    if not dados:
        raise ValueError("série vazia")
    return url, dados


def focus_selic() -> tuple[str, dict]:
    url = (f"{OLINDA}/ExpectativasMercadoSelic?$top=200&$orderby=Data%20desc&$format=json"
           "&$filter=baseCalculo%20eq%200")
    vals = _json(url)["value"]
    ultima = vals[0]["Data"]
    reunioes = [{"reuniao": v["Reuniao"], "mediana": v["Mediana"]} for v in vals
                if v["Data"] == ultima]
    return url, {"data_referencia": ultima, "reunioes": _sort_reunioes(reunioes)}


def _sort_reunioes(rs: list[dict]) -> list[dict]:
    def key(r):
        num, ano = r["reuniao"][1:].split("/")
        return int(ano), int(num)
    return sorted(rs, key=key)


def focus_ipca() -> tuple[str, dict]:
    url_a = (f"{OLINDA}/ExpectativasMercadoAnuais?$top=40&$orderby=Data%20desc&$format=json"
             "&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200")
    url_12 = (f"{OLINDA}/ExpectativasMercadoInflacao12Meses?$top=1&$orderby=Data%20desc"
              "&$format=json&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200"
              "%20and%20Suavizada%20eq%20'S'")
    anuais = _json(url_a)["value"]
    ultima = anuais[0]["Data"]
    anos = sorted(({"ano": int(v["DataReferencia"]), "mediana": v["Mediana"]} for v in anuais
                   if v["Data"] == ultima), key=lambda r: r["ano"])
    m12 = _json(url_12)["value"][0]
    return f"{url_a} ; {url_12}", {
        "data_referencia": ultima, "anual": anos,
        "doze_meses": {"data_referencia": m12["Data"], "mediana": m12["Mediana"]},
    }


def tesouro_direto() -> tuple[str, list[dict]]:
    raw = _get(TD_CSV, timeout=180).decode("latin-1")
    rows = list(csv.DictReader(io.StringIO(raw), delimiter=";"))
    for r in rows:
        r["_base"] = _br_date(r["Data Base"])
    datas = sorted({r["_base"] for r in rows})[-TD_DIAS:]
    out = []
    for r in rows:
        if r["_base"] not in datas or r["Tipo Titulo"] not in TD_TITULOS:
            continue
        out.append({
            "titulo": r["Tipo Titulo"], "vencimento": _br_date(r["Data Vencimento"]),
            "data_base": r["_base"], "taxa_compra": _num(r["Taxa Compra Manha"]),
            "taxa_venda": _num(r["Taxa Venda Manha"]), "pu_compra": _num(r["PU Compra Manha"]),
            "pu_venda": _num(r["PU Venda Manha"]), "pu_base": _num(r["PU Base Manha"]),
        })
    out.sort(key=lambda r: (r["data_base"], r["titulo"], r["vencimento"]))
    return TD_CSV, out


# ----------------------------------------------------------------------------- gravação
def _write(nome: str, fonte: str, url: str, dados, agora: dt.datetime) -> None:
    payload = {"fonte": fonte, "url": url, "coletado_em": agora.isoformat(timespec="seconds"),
               "dados": dados}
    (OUT / nome).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    agora = dt.datetime.now(BRT)
    hoje = agora.date()
    jobs: list[tuple[str, str, Callable[[], tuple[str, object]]]] = [
        ("cdi.json", "BCB SGS 12 — CDI (% a.d.)", lambda: sgs(12, hoje)),
        ("selic_meta.json", "BCB SGS 432 — meta Selic (% a.a.)", lambda: sgs(432, hoje)),
        ("ipca_mensal.json", "BCB SGS 433 — IPCA (% a.m.)", lambda: sgs(433, hoje, anos=3)),
        ("focus_selic.json", "BCB Focus — Selic por reunião (mediana, % a.a.)", focus_selic),
        ("focus_ipca.json", "BCB Focus — IPCA anual e 12 meses (mediana, %)", focus_ipca),
        ("tesouro_direto.json",
         "Tesouro Transparente — Tesouro Direto (taxas de VAREJO, % a.a.)", tesouro_direto),
    ]
    status = {"executado_em": agora.isoformat(timespec="seconds"), "ok": [], "erros": {}}
    for nome, fonte, fn in jobs:
        try:
            url, dados = fn()
            _write(nome, fonte, url, dados, agora)
            status["ok"].append(nome)
            print(f"ok    {nome}")
        except Exception as e:  # noqa: BLE001 — mantém o arquivo anterior e registra
            status["erros"][nome] = f"{type(e).__name__}: {e}"
            print(f"ERRO  {nome}: {e}", file=sys.stderr)
    (OUT / "_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
