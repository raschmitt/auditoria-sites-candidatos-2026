"""
Orquestrador do pipeline (escopo atual: só hospedagem — ver
docs/METODOLOGIA.md sobre a etapa de autoria/doação, fora de escopo).

Roda as duas etapas em sequência, cada uma via o supervisor (reinício
automático em caso de travamento do navegador). Pode ser interrompido a
qualquer momento (Ctrl+C) e retomado depois — cada etapa é resumível
via checkpoint em CSV.

Uso:
    DISPLAY=:0 python run_pipeline.py [--etapa {1,2,all}]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).parent
SUPERVISOR = DIR / "scripts" / "supervisor.sh"

ETAPAS = {
    1: ("src/discover_candidatos.py", 180, 40),
    2: ("src/analisar_sites.py", 300, 20),
}


def rodar_etapa(n: int) -> bool:
    script, timeout_s, tentativas = ETAPAS[n]
    print(f"\n{'=' * 60}\nEtapa {n}: {script}\n{'=' * 60}")
    result = subprocess.run(
        ["bash", str(SUPERVISOR), script, str(timeout_s), str(tentativas)],
        cwd=DIR,
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--etapa", choices=["1", "2", "all"], default="all")
    args = parser.parse_args()

    etapas_a_rodar = [1, 2] if args.etapa == "all" else [int(args.etapa)]
    for n in etapas_a_rodar:
        ok = rodar_etapa(n)
        if not ok:
            print(f"\nEtapa {n} não concluiu limpo após o máximo de tentativas. "
                  f"Rode novamente mais tarde — o progresso já feito fica salvo.")
            sys.exit(1)

    print("\nPipeline concluído.")


if __name__ == "__main__":
    main()
