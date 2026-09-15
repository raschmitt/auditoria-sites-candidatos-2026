"""
Etapa 2 do pipeline: lê data/raw/candidatos_sites.csv, classifica cada
endereço declarado, e para os que são "site_proprio" roda a análise de
hospedagem (art. 57-B da Lei 9.504/97) e de autoria provável
(pessoa física x jurídica).

Saída: data/processed/sites_analise.csv — um registro por
(candidato, site_proprio_declarado), com o resultado das duas análises.

Resumível: domínios já analisados (presentes na saída) são pulados.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from site_classifier import classificar_lista  # noqa: E402
from hosting_analysis import analisar_hospedagem  # noqa: E402
from dev_signature import analisar_autoria  # noqa: E402

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidatos_sites.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sites_analise.csv")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logs", "analisar_sites.log")

FIELDS = [
    "candidato_id", "nome_urna", "uf", "cargo_nome", "partido_sigla",
    "url_declarada", "dominio",
    "ip", "pais", "pais_codigo", "hospedado_no_brasil", "atras_de_cdn_proxy", "hospedagem_erro",
    "meta_generator", "autoria_provavel", "pontos_pj", "pontos_pf",
    "whois_org", "evidencias_autoria",
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


def append_row(row: dict) -> None:
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ensure_header()
    done = load_done_keys()
    log(f"{len(done)} (candidato, domínio) já analisados anteriormente.")

    with open(IN_PATH, encoding="utf-8") as f:
        candidatos = list(csv.DictReader(f))

    total_sites_proprios = 0
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
            total_sites_proprios += 1
            log(f"Analisando {cand['nome_urna']} ({cand['uf']}/{cand['cargo_nome']}) -> {site['dominio']}")

            hosp = analisar_hospedagem(site["dominio"])
            autoria = analisar_autoria(site["url"] if "://" in site["url"] else "https://" + site["url"])

            row = {
                "candidato_id": cand["id"],
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
                "meta_generator": autoria.get("meta_generator"),
                "autoria_provavel": autoria.get("autoria_provavel"),
                "pontos_pj": autoria.get("pontos_pessoa_juridica"),
                "pontos_pf": autoria.get("pontos_pessoa_fisica"),
                "whois_org": autoria.get("whois_org"),
                "evidencias_autoria": " | ".join(autoria.get("evidencias", [])),
            }
            append_row(row)
            done.add(key)

    log(f"Concluído. {total_sites_proprios} sites próprios novos analisados nesta execução.")


if __name__ == "__main__":
    main()
