# Relatório Técnico, Auditoria de Hospedagem de Sites de Candidatos, Eleições Gerais 2026

> Este documento é destinado a eventual encaminhamento ao Tribunal
> Superior Eleitoral como subsídio técnico, não como denúncia formal
> ou parecer jurídico. Todo achado aqui é indício de triagem
> automatizada, nenhuma conclusão deve ser tomada como prova sem
> verificação manual complementar (ver seção 4).

## 1. Apresentação

Este relatório resume os resultados de uma auditoria técnica
independente sobre o cumprimento da exigência legal de hospedagem em
servidor localizado no Brasil para sites de campanha nas Eleições
Gerais 2026 (art. 57-B, I, da Lei nº 9.504/1997, c/c Resolução TSE
nº 23.610/2019).

O escopo cobre **as 20.965 candidaturas registradas nacionalmente**
(Presidente, Governador, Senador, Deputado Federal e Deputado
Estadual/Distrital, nas 27 Unidades da Federação), com base
exclusivamente em dados públicos do próprio painel oficial do TSE
(`divulgacandcontas.tse.jus.br`). Coleta realizada em 15/09/2026.

A metodologia completa, incluindo limitações técnicas, está documentada
em [`METODOLOGIA.md`](METODOLOGIA.md) e não é repetida aqui.

## 2. Números gerais

| Métrica | Valor | % |
|---|---|---|
| Candidaturas cobertas | 20.965 | - |
| Com ao menos um endereço eletrônico declarado | 17.469 | 83,3% |
| Sites próprios identificados (domínio autônomo, excl. redes sociais) | 5.418 | - |
| **Hospedados no Brasil (confirmado)** | **1.978** | **36,5%** |
| **Hospedados fora do Brasil (confirmado)** | **930** | **17,2%** |
| Atrás de CDN/proxy global (indeterminável por este método) | 1.574 | 29,0% |
| Erro na análise (DNS não resolveu, site fora do ar etc.) | 936 | 17,3% |

Ou seja, dos sites próprios que puderam ser efetivamente verificados
(hospedagem confirmada, excluindo CDN-indeterminado e erro, base de
2.908), **cerca de 32% estão hospedados fora do Brasil**.

## 3. Achados que sugerem verificação manual

### 3.1. Sites confirmados fora do Brasil

Lista completa no CSV `data/processed/sites_analise.csv` (coluna
`hospedado_no_brasil=False`, 930 registros).
Alguns padrões notáveis observados:

- **Flávio Bolsonaro** (candidato à Presidência, PL), rede de ~12
  domínios próprios (`fbtv22.net`, `fbtv22.com`, `fbtv22.com.br`,
  `tvflavio.net`, `tvflavio.com`, `22tv.com.br`, `tvfb22.*` etc.),
  a maioria concentrada no mesmo bloco de IP geolocalizado na
  **Lituânia** (`2.57.91.91`), com outro grupo nos EUA
  (`185.230.63.186`). Vários desses domínios usam TLD `.com.br`, o que
  demonstra que o sufixo brasileiro não garante hospedagem no Brasil.
- Diversos candidatos a governador/deputado com domínio `.com.br`
  individual resolvendo para provedores de hospedagem genéricos nos
  EUA, Austrália ou outros países (ex.: `davidalmeida.com.br`,
  `robertocidade.com.br`, `serafimcorrea.com.br`, `zelopesac.com.br`).

### 3.2. Ressalva sobre o grupo "atrás de CDN" (1.574 casos)

Esse grupo **não deve ser interpretado como "em conformidade"** nem
como "violação confirmada", é literalmente indeterminado com os dados
públicos disponíveis (ver seção 5.2 de [`METODOLOGIA.md`](METODOLOGIA.md)). Uma checagem
manual adicional (ex.: histórico de DNS anterior à ativação do
CDN/proxy) seria necessária para qualquer conclusão sobre esses casos.

## 4. Ressalvas antes de qualquer uso oficial

- Todos os achados são **indícios de triagem automatizada**, não
  conclusões jurídicas. Antes de qualquer comunicação formal ao TSE,
  cada caso relevante precisa ser verificado manualmente e, idealmente,
  revisado por profissional de Direito Eleitoral.
- A coleta foi feita em 15/09/2026, um retrato pontual no tempo, sites
  continuam sendo criados, alterados e desativados ao longo da campanha
  (936 casos de "erro" já refletem isso: muitos domínios declarados
  simplesmente não resolvem mais).
- Geolocalização de IP tem limitações conhecidas (CDNs, ver seção 3.2).
  Antes de qualquer afirmação pública sobre um candidato específico,
  reconfirmar manualmente o achado.
- Ver seção 6 de [`METODOLOGIA.md`](METODOLOGIA.md) para a lista completa de limitações.

## 5. Reprodutibilidade

Código-fonte completo, dados brutos e processados disponíveis no
repositório público no GitHub
(`raschmitt/auditoria-sites-candidatos-2026`).
