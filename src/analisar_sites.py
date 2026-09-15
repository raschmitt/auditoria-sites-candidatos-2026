"""
Etapa 2 do pipeline: lê data/raw/candidatos_sites.csv, classifica cada
endereço declarado, e para os que são "site_proprio" roda a análise de
hospedagem (art. 57-B da Lei 9.504/97).

Saída: data/processed/sites_analise.csv — um registro por
(candidato, site_proprio_declarado), com o resultado da análise de
hospedagem.

Resumível: domínios já analisados (presentes na saída) são pulados.

Nota: a análise de autoria provável (pessoa física x jurídica) que
existia nesta etapa foi removida do escopo atual do projeto — o módulo
`dev_signature.py` continua no repositório, mas não é mais chamado
daqui. Ver `docs/METODOLOGIA.md`.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))
from site_classifier import classificar_lista  # noqa: E402
from hosting_analysis import analisar_hospedagem  # noqa: E402

# Etapa é I/O-bound (DNS + HTTP de geolocalização) — paraleliza com
# threads. A taxa da API de geolocalização de IP é limitada globalmente
# em `hosting_analysis._aguardar_rate_limit`, então aumentar este número
# não estoura o limite dela — só reduz o tempo ocioso de cada thread
# esperando a vez na fila do rate limiter.
MAX_WORKERS = 12

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidatos_sites.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sites_analise.csv")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logs", "analisar_sites.log")

FIELDS = [
    "candidato_id", "numero", "nome_urna", "uf", "cargo_nome", "partido_sigla",
    "url_declarada", "dominio",
    "ip", "pais", "pais_codigo", "hospedado_no_brasil", "atras_de_cdn_proxy", "hospedagem_erro",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_done_keys() -> set[tuple[str, str]]:
    if not os.path.exists(OUT_PATH):
        return set()
    with open(OUT_PATH, encoding="utf-8") as f:
        return {(row["candidato_id"], row["dominio"]) for row in csv.DictReader(f)}


def ensure_header() -> None:
    if not os.path.exists(OUT_PATH):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


_write_lock = threading.Lock()


def append_row(row: dict) -> None:
    with _write_lock:
        with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow(row)


def _analisar_um(cand: dict, site: dict) -> dict:
    hosp = analisar_hospedagem(site["dominio"])
    return {
        "candidato_id": cand["id"],
        "numero": cand["numero"],
        "nome_urna": cand["nome_urna"],
        "uf": cand["uf"],
        "cargo_nome": cand["cargo_nome"],
        "partido_sigla": cand["partido_sigla"],
        "url_declarada": site["url"],
        "dominio": site["dominio"],
        "ip": hosp.get("ip"),
        "pais": hosp.get("pais"),
        "pais_codigo": hosp.get("pais_codigo"),
        "hospedado_no_brasil": hosp.get("hospedado_no_brasil"),
        "atras_de_cdn_proxy": hosp.get("atras_de_cdn_proxy"),
        "hospedagem_erro": hosp.get("erro"),
    }


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ensure_header()
    done = load_done_keys()
    log(f"{len(done)} (candidato, domínio) já analisados anteriormente.")

    with open(IN_PATH, encoding="utf-8") as f:
        candidatos = list(csv.DictReader(f))

    tarefas: list[tuple[dict, dict]] = []
    for cand in candidatos:
        if not cand["sites_json"]:
            continue
        sites = json.loads(cand["sites_json"])
        classificados = classificar_lista(sites)
        proprios = [c for c in classificados if c["categoria"] == "site_proprio"]
        for site in proprios:
            key = (cand["id"], site["dominio"])
            if key in done:
                continue
            tarefas.append((cand, site))

    log(f"{len(tarefas)} sites próprios pendentes de análise "
        f"(paralelizado em {MAX_WORKERS} threads).")

    total_ok = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(_analisar_um, cand, site): (cand, site) for cand, site in tarefas}
        for i, futuro in enumerate(as_completed(futuros), start=1):
            cand, site = futuros[futuro]
            try:
                row = futuro.result()
                append_row(row)
                total_ok += 1
            except Exception as e:
                log(f"ERRO analisando {cand['nome_urna']} -> {site['dominio']}: {e}")
            if i % 25 == 0 or i == len(tarefas):
                log(f"  ... {i}/{len(tarefas)} processados nesta execução.")

    log(f"Concluído. {total_ok} sites próprios novos analisados nesta execução.")


if __name__ == "__main__":
    main()
