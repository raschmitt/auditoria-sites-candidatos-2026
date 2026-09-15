"""
Gera um resumo executivo em Markdown a partir do CSV processado, para
consulta rápida e para servir de base ao relatório final.

Saída: docs/RESUMO_EXECUTIVO.md
"""
from __future__ import annotations

import csv
import os

DIR = os.path.dirname(__file__)
CANDIDATOS = os.path.join(DIR, "..", "data", "raw", "candidatos_sites.csv")
ANALISE = os.path.join(DIR, "..", "data", "processed", "sites_analise.csv")
OUT = os.path.join(DIR, "..", "docs", "RESUMO_EXECUTIVO.md")


def ler_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    candidatos = ler_csv(CANDIDATOS)
    analise = ler_csv(ANALISE)

    total_candidatos = len(candidatos)
    com_algum_endereco = sum(1 for c in candidatos if c["sites_json"])
    total_sites_proprios = len(analise)

    fora_brasil = [r for r in analise if r["hospedado_no_brasil"] == "False"]
    dentro_brasil = [r for r in analise if r["hospedado_no_brasil"] == "True"]
    indeterminado_cdn = [r for r in analise if r["atras_de_cdn_proxy"]]
    com_erro = [r for r in analise if r["hospedagem_erro"]]

    linhas = [
        "# Resumo Executivo, Auditoria de Hospedagem de Sites de Candidatos 2026",
        "",
        f"- Candidaturas cobertas: **{total_candidatos}**",
        f"- Com pelo menos um endereço eletrônico declarado: **{com_algum_endereco}**",
        f"- Sites próprios identificados (domínio autônomo, excluindo redes sociais): **{total_sites_proprios}**",
        "",
        "## Hospedagem",
        f"- Hospedados no Brasil (confirmado): **{len(dentro_brasil)}**",
        f"- Hospedados fora do Brasil (confirmado, não atrás de CDN): **{len(fora_brasil)}**",
        f"- Atrás de CDN/proxy global (país indeterminável por este método): **{len(indeterminado_cdn)}**",
        f"- Erro na análise (DNS não resolveu, timeout etc.): **{len(com_erro)}**",
        "",
    ]

    if fora_brasil:
        linhas += ["## Detalhe, sites confirmados fora do Brasil", ""]
        for r in fora_brasil:
            linhas.append(f"- {r['nome_urna']} ({r['uf']}/{r['cargo_nome']}, {r['partido_sigla']}), "
                          f"{r['dominio']}, {r['pais']} (IP {r['ip']})")
        linhas.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"Relatório gerado em {OUT}")
    print("\n".join(linhas[:15]))


if __name__ == "__main__":
    main()
