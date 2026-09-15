"""
Crawler 2: para candidatos cujo site foi classificado (etapa anterior)
como provavelmente desenvolvido por PESSOA JURÍDICA, verifica se há
algum registro correspondente na prestação de contas — seja como
DESPESA paga a um fornecedor (cenário regular: contratação de serviço)
ou como DOAÇÃO recebida (cenário vedado, se o doador for CNPJ; ou
irregular por omissão, se não constar registro nenhum).

Fonte de dados: mesmo endpoint público `prestador/consulta` do TSE já
usado no restante do projeto, especificamente os campos
`rankingDoadores` (maiores doadores declarados) e `rankingFornecedores`
(maiores fornecedores pagos).

⚠️ LIMITAÇÃO METODOLÓGICA IMPORTANTE (documentar isso é obrigatório
em qualquer uso destes resultados):
O painel público do TSE expõe apenas um RANKING dos maiores doadores e
fornecedores por candidato — não a lista itemizada completa de receitas
com descrição de cada item (esse detalhe só existe no arquivo oficial
de prestação de contas, público após o fim do processamento eleitoral).
Portanto, este cruzamento é um indício (triagem), não uma prova
definitiva de irregularidade. Um resultado "sem_registro_encontrado"
pode significar (a) omissão real, ou (b) que o registro existe mas está
fora do recorte do "ranking" (ex.: fornecedor pequeno, fora do top-N
exibido publicamente). Toda constatação relevante deve ser confirmada
manualmente na prestação de contas completa antes de qualquer
comunicação ao TSE.
"""
from __future__ import annotations

import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from tse_client import TSEClient  # noqa: E402

ELEICAO_ID = 20322002026
ANO = 2026

IN_ANALISE = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sites_analise.csv")
IN_CANDIDATOS = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidatos_sites.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "verificacao_doacao_site.csv")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logs", "donation_disclosure.log")

FIELDS = [
    "candidato_id", "nome_urna", "uf", "cargo_nome", "partido_sigla",
    "dominio_site", "whois_org_site",
    "doador_cnpj_encontrado", "doadores_cnpj_lista",
    "fornecedor_correspondente_encontrado", "fornecedores_top",
    "status_verificacao",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def carregar_candidatos_por_id() -> dict[str, dict]:
    with open(IN_CANDIDATOS, encoding="utf-8") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def carregar_alvos_pj() -> list[dict]:
    with open(IN_ANALISE, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["autoria_provavel"] == "pessoa_juridica"]
    return rows


def load_done_ids() -> set[str]:
    if not os.path.exists(OUT_PATH):
        return set()
    with open(OUT_PATH, encoding="utf-8") as f:
        return {r["candidato_id"] for r in csv.DictReader(f)}


def ensure_header() -> None:
    if not os.path.exists(OUT_PATH):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def append_row(row: dict) -> None:
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)


def _nome_bate(a: str, b: str) -> bool:
    """Comparação tolerante: normaliza espaços/maiúsculas e verifica
    se um nome está contido no outro (para lidar com razão social
    completa vs. nome fantasia abreviado)."""
    if not a or not b:
        return False
    a_n = " ".join(a.upper().split())
    b_n = " ".join(b.upper().split())
    return a_n in b_n or b_n in a_n


def main(concurrency: int = 10) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ensure_header()
    candidatos_por_id = carregar_candidatos_por_id()
    alvos = carregar_alvos_pj()
    done = load_done_ids()
    pendentes = [a for a in alvos if a["candidato_id"] not in done]
    log(f"{len(alvos)} sites classificados como pessoa_juridica; "
        f"{len(pendentes)} candidatos pendentes de verificação de contas.")

    if not pendentes:
        log("Nada a fazer.")
        return

    with TSEClient(headless=False) as client:
        paths = []
        for a in pendentes:
            cand = candidatos_por_id.get(a["candidato_id"])
            if not cand:
                continue
            paths.append((
                a,
                f"prestador/consulta/{ELEICAO_ID}/{ANO}/{cand['uf']}/{cand['cargo_codigo']}/"
                f"{cand['partido_numero']}/{cand['numero']}/{cand['id']}",
            ))

        for i in range(0, len(paths), concurrency):
            batch = paths[i : i + concurrency]
            respostas = client.get_json_many([p for _, p in batch], concurrency=concurrency)
            for (alvo, _), resp in zip(batch, respostas):
                cand = candidatos_por_id[alvo["candidato_id"]]
                if resp is None:
                    status = "erro_consulta"
                    doadores_cnpj, fornecedores = [], []
                    fornecedor_ok = False
                else:
                    doadores = resp.get("rankingDoadores") or []
                    fornecedores_raw = resp.get("rankingFornecedores") or []
                    doadores_cnpj = [d for d in doadores if d.get("cpfCnpj") and len(d["cpfCnpj"]) == 14]
                    fornecedores = [f.get("nome") for f in fornecedores_raw if f.get("nome")]

                    whois_org = alvo.get("whois_org") or ""
                    fornecedor_ok = any(_nome_bate(whois_org, nome) for nome in fornecedores) if whois_org else False

                    if doadores_cnpj:
                        status = "ALERTA_doacao_de_cnpj_encontrada"
                    elif fornecedor_ok:
                        status = "ok_pago_como_fornecedor"
                    else:
                        status = "sem_registro_encontrado"

                append_row({
                    "candidato_id": alvo["candidato_id"],
                    "nome_urna": alvo["nome_urna"],
                    "uf": alvo["uf"],
                    "cargo_nome": alvo["cargo_nome"],
                    "partido_sigla": alvo["partido_sigla"],
                    "dominio_site": alvo["dominio"],
                    "whois_org_site": alvo.get("whois_org", ""),
                    "doador_cnpj_encontrado": bool(doadores_cnpj),
                    "doadores_cnpj_lista": "; ".join(f"{d.get('nome')} (R$ {d.get('valor')})" for d in doadores_cnpj),
                    "fornecedor_correspondente_encontrado": fornecedor_ok,
                    "fornecedores_top": "; ".join(fornecedores[:5]),
                    "status_verificacao": status,
                })
                log(f"{alvo['nome_urna']} ({alvo['uf']}) -> {status}")

    log("Concluído.")


if __name__ == "__main__":
    main()
