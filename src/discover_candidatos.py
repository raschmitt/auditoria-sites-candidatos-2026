"""
Crawler 1: descobre todos os candidatos das Eleições Gerais 2026 (Brasil
inteiro, todos os cargos) e extrai os sites/redes declarados por cada um
(art. 57-B da Lei nº 9.504/1997 — endereços eletrônicos comunicados à
Justiça Eleitoral).

Saída: data/raw/candidatos_sites.csv, um registro por candidato, com uma
coluna `sites_json` contendo a lista bruta de endereços declarados.

É resumível: se o CSV de saída já existir, os IDs de candidato já
presentes são pulados, permitindo interromper e retomar a execução.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from tse_client import TSEClient  # noqa: E402

ELEICAO_ID = 20322002026
ANO = 2026
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidatos_sites.csv")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logs", "discover_candidatos.log")

FIELDS = [
    "id", "numero", "nome_urna", "nome_completo", "cpf",
    "uf", "cargo_codigo", "cargo_nome", "partido_sigla", "partido_numero",
    "situacao", "totalizacao", "sites_json",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_done_ids() -> set[str]:
    if not os.path.exists(OUT_PATH):
        return set()
    with open(OUT_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["id"] for row in reader}


def ensure_csv_header() -> None:
    is_new = not os.path.exists(OUT_PATH)
    if is_new:
        with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def append_rows(rows: list[dict]) -> None:
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        for r in rows:
            writer.writerow(r)


def main(concurrency: int = 15) -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ensure_csv_header()
    done_ids = load_done_ids()
    log(f"Retomando execução: {len(done_ids)} candidatos já processados.")

    with TSEClient(headless=False) as client:
        estrutura = client.get_json(f"eleicao/eleicao-atual?idEleicao={ELEICAO_ID}")
        if not estrutura:
            log("ERRO: não foi possível obter a estrutura nacional da eleição.")
            sys.exit(1)  # força o supervisor a tratar como falha e tentar de novo

        # Monta lista de (uf, cargo_codigo, cargo_nome) a percorrer
        alvo: list[tuple[str, int, str]] = []
        for ue in estrutura["ues"]:
            uf = ue["sigla"]
            for cargo in ue["cargos"]:
                alvo.append((uf, cargo["codigo"], cargo["nome"]))
        log(f"{len(alvo)} combinações UF/cargo a percorrer "
            f"({sum(c['contagem'] for ue in estrutura['ues'] for c in ue['cargos'])} candidaturas no total).")

        total_novos = 0
        for uf, cargo_cod, cargo_nome in alvo:
            listagem = client.get_json(
                f"candidatura/listar/{ANO}/{uf}/{ELEICAO_ID}/{cargo_cod}/candidatos"
            )
            if not listagem or not listagem.get("candidatos"):
                continue
            candidatos = listagem["candidatos"]
            pendentes = [c for c in candidatos if str(c["id"]) not in done_ids]
            if not pendentes:
                log(f"{uf}/{cargo_nome}: {len(candidatos)} candidatos, todos já processados.")
                continue
            log(f"{uf}/{cargo_nome}: {len(candidatos)} candidatos, {len(pendentes)} pendentes.")

            # Processa em sub-lotes pequenos e grava no CSV a cada sub-lote
            # concluído — assim, se o processo for interrompido/travar no
            # meio de uma UF/cargo grande (ex.: RJ tem 1188 candidatos a
            # deputado estadual), o progresso já feito não se perde: a
            # retomada pula direto para os sub-lotes ainda não gravados.
            SUBLOTE = 100
            for j in range(0, len(pendentes), SUBLOTE):
                subpendentes = pendentes[j : j + SUBLOTE]
                paths = [
                    f"candidatura/buscar/{ANO}/{uf}/{ELEICAO_ID}/candidato/{c['id']}"
                    for c in subpendentes
                ]
                detalhes = client.get_json_many(paths, concurrency=concurrency)

                rows = []
                for cand, det in zip(subpendentes, detalhes):
                    sites = det.get("sites") if det else None
                    rows.append({
                        "id": cand["id"],
                        "numero": cand["numero"],
                        "nome_urna": cand.get("nomeUrna"),
                        "nome_completo": (det or {}).get("nomeCompleto") or cand.get("nomeCompleto"),
                        "cpf": (det or {}).get("cpf"),
                        "uf": uf,
                        "cargo_codigo": cargo_cod,
                        "cargo_nome": cargo_nome,
                        "partido_sigla": (det or {}).get("partido", {}).get("sigla") if det else None,
                        "partido_numero": (det or {}).get("partido", {}).get("numero") if det else None,
                        "situacao": cand.get("descricaoSituacao"),
                        "totalizacao": cand.get("descricaoTotalizacao"),
                        "sites_json": json.dumps(sites, ensure_ascii=False) if sites else "",
                    })
                    done_ids.add(str(cand["id"]))
                append_rows(rows)
                total_novos += len(rows)
                log(f"  ... {uf}/{cargo_nome}: sub-lote {j + len(subpendentes)}/{len(pendentes)} salvo.")

        log(f"Concluído. {total_novos} novos candidatos salvos nesta execução. "
            f"Total acumulado: {len(done_ids)}.")


if __name__ == "__main__":
    main()
