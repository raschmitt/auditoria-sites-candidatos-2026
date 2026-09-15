# Metodologia — Auditoria de Sites de Candidatos, Eleições Gerais 2026

**Última atualização:** conforme data do commit no controle de versão.
**Autor:** análise conduzida com apoio de assistente de IA (Claude), a
pedido do responsável pelo repositório.

## 1. Objetivo

Verificar, para o universo de candidaturas registradas nas Eleições
Gerais 2026, dois pontos de conformidade relacionados ao uso de sites de
campanha na internet:

1. **Hospedagem em território brasileiro** dos sites próprios declarados
   à Justiça Eleitoral.
2. **Registro contábil adequado** de sites que aparentam ter sido
   desenvolvidos por pessoa jurídica, cruzando indícios técnicos de
   autoria com a prestação de contas pública de cada candidato.

## 2. Base legal considerada

- **Lei nº 9.504/1997 (Lei das Eleições)**
  - **Art. 57-B, inciso I**: a propaganda eleitoral na internet pode ser
    realizada em sítio do candidato, desde que o endereço eletrônico seja
    comunicado à Justiça Eleitoral.
  - **Art. 23** e **§ 7º**: doações de pessoa física podem incluir bens
    ou serviços estimáveis em dinheiro; a exceção ao limite de 10% dos
    rendimentos do doador, para uso de bem próprio ou prestação de
    serviço próprio, tem teto de R$ 40 mil.
- **Resolução TSE nº 23.610/2019** (dispõe sobre propaganda eleitoral) —
  regulamenta a exigência de hospedagem/veiculação de sites de campanha
  em conformidade com a legislação brasileira.
- **Resolução TSE nº 23.607/2019** (dispõe sobre a arrecadação e
  prestação de contas) — normatiza o Sistema de Prestação de Contas
  Eleitorais (SPCE): todo bem ou serviço estimável recebido precisa ser
  lançado com recibo eleitoral e comprovação de valor de mercado.
- **Vedação a doação por pessoa jurídica**: empresas (CNPJ) estão
  proibidas de doar recursos financeiros ou estimáveis em dinheiro a
  campanhas — logo, o desenvolvimento de um site não pode ser doado por
  uma agência/empresa; se doado, precisa vir do CPF do profissional que
  o desenvolveu.

> Este documento reproduz o entendimento da legislação tal como
> apresentado ao autor do projeto (inclusive via uma busca com resposta
> de IA, usada como ponto de partida). **Não substitui parecer jurídico
> formal** — antes de qualquer comunicação oficial ao TSE, recomenda-se
> validação por profissional do Direito Eleitoral quanto à redação exata
> vigente de cada dispositivo.

## 3. Fonte de dados

Toda a coleta usa exclusivamente a **API pública do painel
"Divulgação de Candidaturas e Contas Eleitorais"**
(`https://divulgacandcontas.tse.jus.br/divulga/`), a mesma que alimenta
o site oficial de consulta do TSE. Não há uso de nenhuma base paga,
vazada ou não pública.

Endpoints usados (descobertos por engenharia reversa das chamadas de
rede feitas pela própria SPA oficial do TSE, navegando manualmente pela
interface):

| Endpoint | Uso |
|---|---|
| `GET /rest/v1/eleicao/eleicao-atual?idEleicao={id}` | Estrutura nacional: todas as UFs, cargos e contagem de candidatos |
| `GET /rest/v1/candidatura/listar/{ano}/{uf}/{id}/{cargo}/candidatos` | Lista de candidatos de um cargo/UF |
| `GET /rest/v1/candidatura/buscar/{ano}/{uf}/{id}/candidato/{idCandidato}` | Detalhe do candidato, incl. campo `sites` (endereços declarados) |
| `GET /rest/v1/prestador/consulta/{id}/{ano}/{uf}/{cargo}/{partido}/{numero}/{idCandidato}` | Dados consolidados de prestação de contas, incl. `rankingDoadores` e `rankingFornecedores` |

### 3.1. Obstáculo técnico: bloqueio de automação pelo WAF do TSE

O domínio `divulgacandcontas.tse.jus.br` (e também `www.tse.jus.br` e
`dadosabertos.tse.jus.br`) está atrás de um WAF que retorna
**HTTP 403 "Access Denied"** para qualquer cliente que não seja um
navegador real renderizando a página — isso inclui `curl`, a biblioteca
`requests` do Python, **e também o Playwright/Selenium rodando em modo
headless** (mesmo com IP residencial brasileiro, mesmo mascarando
`navigator.webdriver`).

Testes realizados (ver histórico do projeto) mostraram que:
- `curl` com headers de navegador → 403
- Playwright Chromium `headless=True`, com e sem flags anti-detecção →
  403
- Playwright Chromium `headless=False` (janela real, mesmo processo,
  mesma máquina, mesmo IP) → **200, funciona normalmente**

Conclusão prática: o bloqueio não é por IP/rede, é por alguma
característica de fingerprinting específica do modo headless do
Chromium (comum em soluções de bot management como Akamai/Cloudflare
Bot Manager). A solução adotada foi rodar um Chromium **com interface
gráfica** (`headless=False`) e fazer as chamadas de API via `fetch()`
dentro da própria página carregada, replicando exatamente o
comportamento de um usuário navegando pelo site. Ver `src/tse_client.py`.

Essa exigência tem uma implicação prática importante: os crawlers deste
projeto **não podem rodar num servidor CI/CD puramente headless** sem um
display virtual (Xvfb ou equivalente) — precisam de um ambiente com
sessão gráfica disponível.

## 4. Etapa 1 — Descoberta de candidatos e sites declarados

Script: `src/discover_candidatos.py`

1. Busca a estrutura nacional da eleição 2026 (28 "UEs": as 27
   Unidades da Federação + "BR" para a chapa presidencial).
2. Para cada combinação UF × cargo (governador, vice, senador, 1º e 2º
   suplentes, deputado federal, deputado estadual/distrital — e
   presidente/vice para "BR"), lista todos os candidatos.
3. Para cada candidato, busca o detalhe completo e extrai o campo
   `sites` — a lista de endereços eletrônicos que o próprio candidato
   comunicou à Justiça Eleitoral (nos termos do art. 57-B, I).
4. Salva incrementalmente em `data/raw/candidatos_sites.csv`, um
   registro por candidato. Execução é **resumível**: candidatos já
   presentes no CSV de saída são pulados numa nova execução.

Universo coberto: **20.965 candidaturas** nacionais nas Eleições Gerais
2026 (contagem obtida diretamente da API do TSE em [preencher data da
coleta]).

## 5. Etapa 2 — Classificação e análise dos sites

Script: `src/analisar_sites.py` (usa `site_classifier.py`,
`hosting_analysis.py`, `dev_signature.py`)

### 5.1. Classificação (site próprio vs. rede social vs. outros)

O campo `sites` do TSE é um campo de texto livre por candidato — mistura
links de redes sociais (Instagram, Facebook, X/Twitter, TikTok, YouTube,
Kwai, Threads, LinkedIn, Telegram, WhatsApp, Discord), agregadores de
link (Linktree e similares), plataformas de financiamento coletivo
(QueroApoiar, Vakinha etc.) e, eventualmente, um domínio próprio do
candidato.

A regra de hospedagem no Brasil (art. 57-B) diz respeito ao **"sítio do
candidato"** — um domínio sobre o qual o candidato tem controle/escolha
de hospedagem — não aos perfis hospedados por terceiros (Meta, Google,
X etc.), cuja infraestrutura não é decisão do candidato. Por isso a
etapa de classificação (`site_classifier.py`) separa essas categorias
antes de aplicar a análise de hospedagem, evitando falsos positivos
("Instagram não hospedado no Brasil" não é uma violação imputável ao
candidato).

### 5.2. Verificação de hospedagem no Brasil

Para cada "site próprio":
1. Resolve o domínio via DNS para um endereço IP.
2. Geolocaliza o IP via API pública gratuita (`ip-api.com`), obtendo
   país, ISP/organização e ASN.
3. Marca `hospedado_no_brasil = True` se o código de país for `BR`.

**Limitação**: geolocalização de IP não é 100% infalível — CDNs globais
(Cloudflare, AWS CloudFront etc.) podem servir conteúdo de múltiplos
países a partir de um único IP "âncora" registrado em outro país, ou
vice-versa. Casos limítrofes (ex.: um provedor de hospedagem
internacional com operação legal no Brasil) precisam de checagem manual
antes de qualquer conclusão.

### 5.3. Estimativa de autoria (pessoa física vs. pessoa jurídica)

Como não existe uma forma de obter isso com certeza absoluta a partir de
fora, o projeto usa um conjunto de **sinais técnicos observáveis e
auditáveis** (nunca uma classificação "caixa-preta"):

| Sinal | Peso | Direção |
|---|---|---|
| Tag `<meta name="generator">` de ferramenta de autoatendimento (Wix, Canva, Webnode, Google Sites, Carrd) | +2 pessoa física | Indica ferramenta de "monte seu site" sem necessidade de agência |
| Texto no rodapé tipo "Desenvolvido por / Criado por / Powered by [Nome]" | +1 a +2 pessoa jurídica | Mais forte se o nome contém termos como "agência", "estúdio", "marketing digital" |
| CNPJ visível no HTML | +1 pessoa jurídica | Indício de que uma empresa está envolvida |
| Organização registrante no WHOIS do domínio contendo razão social (Ltda, EIRELI, S.A., ME) | +2 pessoa jurídica | Registro formal do domínio em nome de empresa |

Cada evidência encontrada é registrada individualmente na coluna
`evidencias_autoria` do CSV de saída — a classificação final
(`autoria_provavel`) é apenas a soma desses sinais, nunca um veredito
automatizado a ser tomado como prova.

## 6. Etapa 3 — Cruzamento com a prestação de contas

Script: `src/donation_disclosure.py`

Para os sites classificados como prováveis de autoria por pessoa
jurídica na etapa 2, busca-se na prestação de contas pública do
candidato (`rankingDoadores` e `rankingFornecedores`, do endpoint
`prestador/consulta`):

- Se algum **doador com CNPJ** (14 dígitos) aparece no ranking de
  doadores → **alerta**: doação de pessoa jurídica é vedada por lei,
  independentemente de estar relacionada ao site.
- Se o nome da organização identificada por WHOIS aparece no ranking de
  **fornecedores pagos** → cenário regular (serviço contratado e pago,
  não doado).
- Caso contrário → `sem_registro_encontrado`: não foi possível localizar,
  nos dados públicos disponíveis, nenhum registro correspondente.

### 6.1. Limitação metodológica central desta etapa

O painel público do TSE expõe apenas um **ranking dos maiores** doadores
e fornecedores por candidato — não a lista itemizada completa de
receitas/despesas com descrição de cada lançamento (essa granularidade
só existe no arquivo oficial de prestação de contas, publicado
integralmente após o processamento eleitoral, e em bases como
Base dos Dados/dadosabertos.tse.jus.br, ainda não disponíveis para o
pleito de 2026 no momento desta coleta).

Portanto, **`sem_registro_encontrado` é um indício de triagem, não uma
prova de omissão**. Pode significar:
(a) omissão real de receita/despesa (Caixa 2), **ou**
(b) o registro existe, mas o valor é pequeno o suficiente para não
    aparecer no recorte de "maiores" doadores/fornecedores exibido
    publicamente, **ou**
(c) a correspondência de nomes falhou (razão social divergente do nome
    fantasia, erro de digitação etc.).

Qualquer achado relevante desta etapa deve ser **verificado manualmente**
na prestação de contas completa do candidato antes de ser levado
adiante.

## 7. Limitações gerais do projeto

- Cobertura depende da qualidade do que o próprio candidato preencheu no
  cadastro (campo `sites` é de texto livre, sujeito a erros de digitação
  que podem impedir a extração correta do domínio).
- A análise de hospedagem e autoria foi feita em um único momento no
  tempo — um site pode trocar de hospedagem ou ser retirado do ar depois
  da coleta.
- As heurísticas de autoria são probabilísticas; sites bem feitos por um
  voluntário técnico (pessoa física com conhecimento avançado) podem
  gerar falsos positivos de "pessoa jurídica", e vice-versa.
- O projeto não verifica o conteúdo político/eleitoral dos sites, apenas
  aspectos técnicos de hospedagem e indícios de autoria.

## 8. Reprodutibilidade

Todo o código está neste repositório. Os dados brutos e processados
(CSV) ficam versionados em `data/`, permitindo auditoria externa de cada
etapa. Ver `README.md` para instruções de execução.
