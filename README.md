# Auditoria de Sites de Candidatos — Eleições Gerais 2026

Projeto de auditoria técnica que verifica, para **todos os candidatos das
Eleições Gerais 2026 no Brasil** (Presidente, Governador, Senador,
Deputado Federal, Deputado Estadual/Distrital e suplentes), se os sites
próprios declarados à Justiça Eleitoral (art. 57-B da Lei nº 9.504/1997)
cumprem a exigência de hospedagem em servidor no Brasil.

> **Escopo atual:** o projeto ficou restrito a essa verificação de
> hospedagem. A análise de autoria provável (pessoa física x jurídica) e
> o cruzamento com prestação de contas (`donation_disclosure.py`) foram
> deixados de lado por decisão do autor — os scripts continuam no
> repositório (e algumas colunas de autoria ainda aparecem no CSV de
> saída, como resíduo de execução anterior), mas não fazem parte do
> escopo/entrega atual do projeto.

> Este é um projeto de análise exploratória/triagem, não uma auditoria
> jurídica conclusiva. Toda constatação apontada aqui precisa ser
> confirmada manualmente na prestação de contas oficial antes de qualquer
> comunicação formal ao TSE. Ver limitações detalhadas em
> [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md).

## Pipeline

```
1. discover_candidatos.py   → data/raw/candidatos_sites.csv
   Percorre todas as UFs e cargos da eleição 2026 e extrai, para cada
   candidato, os endereços eletrônicos que ele declarou à Justiça
   Eleitoral.

2. analisar_sites.py        → data/processed/sites_analise.csv
   Filtra os endereços que são efetivamente "sites próprios" (exclui
   redes sociais, agregadores de link e plataformas de financiamento
   coletivo) e, para cada um, verifica o país de hospedagem via
   DNS + geolocalização de IP.
```

> `donation_disclosure.py` (cruzamento com prestação de contas) e a
> análise de autoria em `dev_signature.py` continuam no repositório mas
> **fora do escopo atual** — não fazem parte do pipeline ativo.

## Por que via navegador real (Playwright headed), e não `requests`?

O WAF do TSE bloqueia com HTTP 403 qualquer requisição que não venha de
um navegador de verdade renderizando a página — inclusive `curl`,
`requests` e até Playwright/Selenium em **modo headless**. A única
configuração que funcionou nos testes foi Chromium real, com interface
gráfica (`headless=False`), acessando a API pública via `fetch()` de
dentro da própria página carregada. Ver `src/tse_client.py` e a seção
correspondente em `docs/METODOLOGIA.md`.

Isso significa que os scripts deste projeto **precisam rodar numa
máquina com ambiente gráfico disponível** (`$DISPLAY` configurado) — não
funcionam em um servidor puramente headless/CI sem um display virtual.

> **TODO (execução recorrente/agendada):** para rodar via cron/systemd
> sem depender de uma sessão gráfica de usuário logada, a solução é usar
> `Xvfb` (display X virtual em memória) — o Chromium continua abrindo em
> modo "headed" (não é detectado pelo WAF), só que renderiza num buffer
> invisível em vez de uma janela real. Requer `sudo apt-get install
> xvfb`, ainda não instalado neste ambiente. Depois de instalado, basta
> envolver os comandos com `xvfb-run -a` (ex.:
> `xvfb-run -a scripts/supervisor.sh src/discover_candidatos.py 180 40`)
> em vez de fixar `DISPLAY=:0`.

## Como rodar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # baixa o binário do Chromium (sem --with-deps, ver nota abaixo)

# Cada etapa é resumível — pode ser interrompida (Ctrl+C) e rodada de
# novo; ela pula o que já está salvo no CSV de saída.
DISPLAY=:0 python src/discover_candidatos.py
python src/analisar_sites.py   # não usa navegador, roda sem DISPLAY

# Ou, com reinício automático em caso de travamento:
scripts/supervisor.sh src/discover_candidatos.py 180 40
```

> Nota sobre `playwright install`: em ambientes sem acesso a `sudo`
> interativo, use `playwright install chromium` (sem `--with-deps`) — as
> bibliotecas de sistema do Chrome já presentes numa máquina desktop
> normal costumam ser suficientes.

## Estrutura de dados

| Arquivo | Granularidade | Descrição |
|---|---|---|
| `data/raw/candidatos_sites.csv` | 1 linha por candidato | Todos os candidatos 2026, com a lista bruta de sites/redes declarados |
| `data/processed/sites_analise.csv` | 1 linha por (candidato, site próprio) | Análise de hospedagem (colunas de autoria ficam presentes mas fora do escopo atual) |

Documentação completa do método, das limitações e das decisões de
projeto em [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md).
