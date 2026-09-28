# MeasureSoftGram — Dashboard de Gestão de Projeto

App **Streamlit** de gestão do projeto MeasureSoftGram (EPS 2026.2). Consolida três
fontes — **SonarCloud**, **Zenhub** e a **planilha do time** — e ainda a CI do GitHub,
com a identidade visual da documentação. Vale **20% da nota final** (DA-R1, DA-R2, DA-R3).

## Rodar

```bash
cd Analytics
pip install -r requirements.txt
streamlit run app.py
```

Sem configurar nada o painel já abre com os arquivos versionados em `data/` e as
abas publicadas da planilha. Para atualizar os dados:

```bash
python scripts/coleta_velocity.py   # Zenhub (ZENHUB_API_KEY no .env)
python scripts/coleta_sonar.py      # SonarCloud (SONAR_TOKEN opcional: projetos públicos)
python -m unittest discover -s tests -v
```

Tokens ficam em `Analytics/.env` (modelo em `.env.example`, fora do git) ou nos
secrets do GitHub. Nenhum token é lido pelo site publicado.

## Regra de origem dos dados

Cada informação vem da **fonte mais adequada**, e cada bloco da tela mostra a etiqueta
da fonte (`SONAR`, `ZENHUB`, `PLANILHA`, `GITHUB`, `CALCULADO`).

| Informação | Fonte | Como chega |
| --- | --- | --- |
| Cobertura, duplicação, LOC, testes, ratings | SonarCloud | `metrics.yml` de cada repositório → `data/*.json` |
| Bugs, vulnerabilidades, code smells, hotspots, dívida técnica, Quality Gate, severidade, histórico | SonarCloud | `scripts/coleta_sonar.py` → `data/sonar/` (workflow `sonar-coleta.yml`, diário) |
| Sprints, story points, velocity, backlog, pipelines, épicos, releases | Zenhub | `scripts/coleta_velocity.py` → `data/zenhub/velocity/` (workflow `zenhub-velocity.yml`, diário) |
| Custos, time por semana, horas, riscos, monitoramento, decisões | Planilha | abas publicadas no Google em CSV (`config.PLANILHAS`), sem cópia local |
| Execuções da CI | GitHub | `metrics.yml` → `GitHub_API-Runs-*.json` |

A planilha **não repete** nada que o Sonar ou o Zenhub têm, e não há cópia local em CSV:
aba sem URL ou que não responde aparece como indisponível. As regras do cálculo da velocity
(critério de feito, níveis pontuados, janela de planning) ficam em `config.PARAMETROS`. **Nenhum valor é
inventado:** métrica sem insumo aparece como *Indisponível*, com o motivo e o que
falta para calculá-la (ex.: *CPI indisponível: Actual Cost não foi fornecido*).

## Páginas

| Página | Pergunta que responde |
| --- | --- |
| **Visão Executiva** | Como está o projeto? Status geral, KPIs, situação por dimensão, planejado × realizado, pontos de atenção |
| **Agile EVM** | Estamos no prazo e no custo? PV, EV, AC, BAC, SV, CV, SPI, CPI, EAC, ETC, burndown |
| **Qualidade técnica (Sonar)** | A qualidade do código está evoluindo? Atual → anterior → variação, evolução, severidade, Quality Gate |
| **Gestão ágil (ZenHub)** | Como estão backlog, velocity, throughput, épicos e releases? |
| **Custos e riscos (Planilha)** | Custos (orçamento, planejado, realizado, por categoria e recurso), matriz de riscos P × I, decisões |
| **Integração contínua (GitHub)** | A CI é confiável como portão de qualidade? |
| **Metodologia e Fontes** | Metadados de cada coleta, fórmulas, metas, limitações e tratamento de dados ausentes |

Filtros globais na barra lateral: **release** (define o período e as metas),
**período**, **repositórios** e **branch**. Filtros específicos (severidade, Quality
Gate, linguagem, sprint, épico, situação, prioridade, responsável, categoria de
risco...) ficam na página e só aparecem quando o dado tem aquela dimensão.

## Estrutura

```
Analytics/
├── app.py                  # tema, carga das fontes, filtros globais, cabeçalho, navegação
├── config.py               # ÚNICO arquivo que o time edita: URLs da planilha, projetos do Sonar, metas, datas
├── pages/                  # só desenho: uma função pagina() por tela
│   ├── visao_executiva.py  ├── sonar.py   ├── zenhub.py
│   ├── evm.py              ├── planilha.py ├── processo.py
│   └── metodologia.py
├── src/
│   ├── data/               # coleta e leitura das fontes
│   │   ├── contexto.py     # carrega tudo com cache e metadados; uma fonte com erro não derruba as outras
│   │   ├── sonar.py        # .json do pipeline + snapshot da API
│   │   ├── sonar_api.py    # cliente da Web API do SonarCloud (usado só pela coleta)
│   │   ├── github.py       # issues e execuções de CI
│   │   └── planilha.py     # abas publicadas da planilha e config.PARAMETROS
│   ├── zenhub/             # cliente GraphQL, queries, normalização e coleta do Zenhub
│   ├── metrics/            # cálculos puros, testados
│   │   ├── velocity.py  ├── evm.py  ├── agile.py (backlog, throughput, épicos, releases)
│   │   ├── qualidade.py ├── resumo.py (visão executiva) └── calculations.py (variação, status, formatação)
│   ├── components/         # kpi.py, charts.py, filters.py, tables.py, layout.py
│   └── theme.py            # IDV da documentação (cores, tipografia, CSS)
├── planilhas/              # planilhas-fonte (.xlsx); os CSVs são lidos direto da versão publicada
├── data/                   # ← TODOS os .json: pipeline (metrics.yml), sonar/ e zenhub/velocity/
├── scripts/                # coleta_velocity.py, coleta_sonar.py, diagnostico_zenhub.py
├── tests/                  # python -m unittest discover -s tests -v
└── stlite/build.py         # empacota o app para o GitHub Pages
```

## Identidade visual

As mesmas cores da documentação (`src/css/custom.css`): primária `#2B4D6F`,
secundária `#5F7EA3`, fundo `#F4F5F6`, sucesso `#04724D`, aviso `#DF8E16`, erro
`#D13310`; Roboto no texto e Quattrocento na marca. Cor só com significado: verde
conforme, amarelo atenção, vermelho crítico, cinza neutro/indisponível — sempre
acompanhada do rótulo em texto. Séries usam a primária, a secundária e um cinza,
com tracejado como segunda codificação; no máximo três séries por gráfico (com mais
categorias, o gráfico vira pequenos múltiplos ou tabela). Todo gráfico tem título,
unidade, período, tooltip e a tabela dos dados logo abaixo.

## Publicação (GitHub Pages)

O `deploy.yml` roda `python Analytics/stlite/build.py`, que copia `app.py`,
`config.py`, `pages/`, `src/` e `data/**/*.json` (e baixa as abas publicadas da planilha) para
`static/dashboard/` e gera um `index.html` com o [stlite](https://github.com/whitphx/stlite)
(Streamlit no navegador). É o mesmo `app.py`. `.env`, `scripts/` e `*.xlsx` nunca
entram no pacote. Testar localmente:

```bash
python Analytics/stlite/build.py && cd static/dashboard && python -m http.server 8000
```

## Limitações conhecidas

- O Zenhub só registra mudanças de escopo feitas depois do início da sprint. Issues que
  já estavam na sprint contam no concluído, mas o **planejado** (linha de base) só vê
  os eventos — daí sprints com planejado 0 SP.
- As queries do **backlog completo** (`PIPELINES`, `PIPELINE_ISSUES` em
  `src/zenhub/queries.py`) precisam ser conferidas contra o schema do Zenhub. Se
  falharem, a coleta segue e a página avisa que só as issues das sprints foram lidas.
- Sem horas registradas na aba Horas, o custo real (AC) e tudo que depende dele (CPI,
  CV, ETC, EAC) ficam indisponíveis — o custo planejado não substitui o real.
