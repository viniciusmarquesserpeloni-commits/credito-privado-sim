"""Fase 0 — confere se as fontes públicas automatizáveis respondem (regra 5: só fontes abertas).

Não grava nada. Uso:  python scripts/check_endpoints.py
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request

UA = {"User-Agent": "credito-privado-sim/0.0 (verificacao de endpoints)"}
HOJE = dt.date.today()
INI = (HOJE - dt.timedelta(days=30)).strftime("%d/%m/%Y")
FIM = HOJE.strftime("%d/%m/%Y")
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"

ENDPOINTS = {
    "SGS 12 — CDI diário (% a.d.)":
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial={INI}&dataFinal={FIM}",
    "SGS 432 — meta Selic (% a.a.)":
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/5?formato=json",
    "SGS 433 — IPCA mensal (%)":
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/3?formato=json",
    "Focus — Selic por reunião":
        f"{OLINDA}/ExpectativasMercadoSelic?$top=5&$orderby=Data%20desc&$format=json"
        "&$filter=baseCalculo%20eq%200",
    "Focus — IPCA anual":
        f"{OLINDA}/ExpectativasMercadoAnuais?$top=5&$orderby=Data%20desc&$format=json"
        "&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200",
    "Focus — IPCA 12 meses (suavizada)":
        f"{OLINDA}/ExpectativasMercadoInflacao12Meses?$top=2&$orderby=Data%20desc&$format=json"
        "&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200%20and%20Suavizada%20eq%20'S'",
    "Tesouro Transparente — CKAN (Tesouro Direto)":
        "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show"
        "?id=taxas-dos-titulos-ofertados-pelo-tesouro-direto",
}


def main() -> None:
    for nome, url in ENDPOINTS.items():
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                body = json.loads(r.read().decode("utf-8"))
            dt_s = time.perf_counter() - t0
            if isinstance(body, list):
                info = f"{len(body)} pontos; último {body[-1]}"
            elif "value" in body:
                info = f"{len(body['value'])} linhas; mais recente Data={body['value'][0].get('Data')}"
            else:
                res = [x for x in body["result"]["resources"] if x["url"].endswith(".csv")]
                info = f"CSV: {res[0]['url']} (atualizado {res[0].get('last_modified')})"
            print(f"OK   {nome} [{dt_s:.1f}s] — {info}")
        except Exception as e:  # noqa: BLE001
            print(f"FALHA {nome}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
