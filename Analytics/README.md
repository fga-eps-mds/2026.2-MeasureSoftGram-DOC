# Dashboard Gerencial e Analítico

App **Streamlit** que consome os arquivos gerados automaticamente pelo pipeline
de CI/CD e apresenta as três dimensões exigidas pela disciplina: **produto**,
**projeto** e **processo**.

Vale **20% da nota final** e é avaliado nas três releases (DA-R1, DA-R2, DA-R3).

## Rodar

```bash
cd Analytics
pip install -r requirements.txt
streamlit run app.py
```

Não precisa configurar nada para ver produto e processo: se houver `.json` em
`data/`, o painel monta sozinho.

## De onde vem cada número

| Dimensão | Fonte | Como chega |
| --- | --- | --- |
| **Produto** | SonarCloud | `metrics.yml` de cada repositório → `Analytics/data/` |
| **Processo** | API do GitHub | o mesmo workflow → `GitHub_API-Issues-*` e `GitHub_API-Runs-*` |
| **Projeto — pontos** (sprints, velocity, AgileEVM, burndown) | API do Zenhub | `scripts/coleta_velocity.py` → `data/zenhub/velocity/` |
| **Projeto — custos e horas**, **riscos e decisões** | Planilha do time | abas publicadas como CSV (`config.py`), ou `planilhas/*.csv` |

A planilha só guarda o que o Zenhub não tem: **Custos**, **Planejamento** (quem
está no time em cada semana), **Horas**, **Riscos**, **Monitoramento** e
**Decisões**. Nenhum ponto é digitado na planilha.

> **A regra que governa este app:** todo número exibido vem de um arquivo. Quando
> um dado não existe, o painel diz que não existe e explica por quê. Um indicador
> ausente e declarado é informação; um inventado é ruído — e reprodutibilidade é
> critério de avaliação.

## Estrutura

```
Analytics/
├── app.py                  # entrada do Streamlit (visão geral + quatro dimensões)
├── config.py               # ÚNICO arquivo que o time edita: URLs das abas publicadas
├── src/
│   ├── loader.py           # .json do SonarCloud e do GitHub
│   ├── zenhub/             # cliente, queries, normalização e coleta do Zenhub
│   ├── velocity.py         # planejado, concluído, velocity, média
│   ├── evm.py              # AgileEVM e burndown (pontos do Zenhub + custos da planilha)
│   ├── velocity_dashboard.py
│   ├── planilhas.py        # leitura das abas da planilha
│   ├── gestao.py           # parâmetros (planilhas/parametros.csv)
│   ├── resumo.py           # indicadores e status da Visão geral
│   ├── qualidade.py        # modelo de qualidade (prévia da R2)
│   └── theme.py            # paleta validada, metas por release
├── planilhas/              # cópia local das 6 abas + parametros.csv (regras do time)
├── data/                   # ← o pipeline e a coleta do Zenhub escrevem aqui
├── scripts/                # coleta_velocity.py, diagnostico_zenhub.py, zenhub_post.mjs
├── tests/                  # python -m unittest discover -s tests -v
├── stlite/build.py         # empacota o app para o GitHub Pages
└── requirements.txt
```

## Modelo de gestão (DA-R1)

A aba **Projeto** tem três partes: **Velocity** (`src/velocity.py`), **AgileEVM e
burndown** (`src/evm.py`) e **Custos**. Pontos e sprints vêm do Zenhub; o custo
planejado de cada semana, as horas reais e o custo/hora vêm da planilha.
`planilhas/parametros.csv` guarda as regras do time (critério de feito, níveis
pontuados, janela de planning, sprints canceladas).

Atualizar o Zenhub (na pasta `Analytics/`):

```bash
python scripts/coleta_velocity.py          # ZENHUB_API_KEY no .env
```

O dicionário de cada indicador está em `docs/metricas/modelo-de-gestao.mdx` e
`docs/metricas/velocity-zenhub.mdx`.

## Publicação (URL exigida no Aprender 3)

O dashboard é publicado **no GitHub Pages, junto com a documentação**, em
`<site da doc>/dashboard/` (link **Dashboard** na barra do topo). Como o Pages só
serve arquivos estáticos, usamos o [stlite](https://github.com/whitphx/stlite): o
próprio Streamlit roda dentro do navegador, com Python em WebAssembly (Pyodide).
É o mesmo `app.py` — não existe uma segunda versão do painel.

Como funciona:

1. o workflow `.github/workflows/deploy.yml` roda `python Analytics/stlite/build.py`
   antes do build do Docusaurus;
2. o script copia `app.py`, `config.py`, `src/`, `planilhas/*.csv`, `data/**/*.json`
   e `../analytics-raw-data/*.json` para `static/dashboard/` e gera um `index.html`
   que monta esses arquivos no navegador e executa `Analytics/app.py`;
3. o Docusaurus publica `static/dashboard/` em `/dashboard/`.

Cada push na `main` — inclusive os commits que o pipeline de métricas faz em
`data/` — republica o painel com os dados novos. `.env`, `scripts/` e `*.xlsx`
nunca entram no pacote.

Testar localmente a versão do Pages:

```bash
python Analytics/stlite/build.py        # gera static/dashboard/ (ignorado pelo git)
cd static/dashboard && python -m http.server 8000
# abrir http://localhost:8000
```

A primeira abertura leva de 20 a 40 s (o navegador baixa o Pyodide e os pacotes);
depois fica em cache. Se uma versão nova do stlite quebrar algo, fixe a versão na
constante `STLITE` de `stlite/build.py`.

## Organização das abas

| Aba | Pergunta que responde |
| --- | --- |
| **Visão geral** | Como estamos? Release e sprint atuais, linha do tempo do semestre, pontos de atenção em ordem de gravidade, situação de cada dimensão e placar por repositório (`src/resumo.py`) |
| **Produto** | A qualidade do código está na meta? (SonarCloud) |
| **Processo** | A CI é confiável e as issues fluem? (GitHub) |
| **Projeto** | Velocity, AgileEVM e burndown (Zenhub) e custos (planilha) |
| **Riscos e decisões** | Matriz de riscos e registro de decisões (planilha Riscos e Decisões) |

A visão geral não calcula nada novo: lê os mesmos dados das outras abas e aplica
as mesmas metas (`theme.METAS`, SPI ≥ 0,95, CI ≥ 80%, conclusão ≥ 80%). O seletor
**Metas da release** na barra lateral começa na release em andamento.

## Planilhas do time

Da planilha "MeasureSoftGram" o painel lê seis abas. Publique cada uma em
**Arquivo → Compartilhar → Publicar na web**, escolhendo a aba e o formato
**CSV**, e cole a URL na chave correspondente de `config.py`:

| Chave em `config.py` | Aba | Para quê |
| --- | --- | --- |
| `custos` | Custos | custo/hora e custo de um integrante por semana |
| `planejamento` | Planejamento | quem está ativo em cada semana → BAC e PV |
| `horas` | Horas | horas reais → AC e CPI |
| `riscos` | Riscos | plano de riscos |
| `monitoramento` | Monitoramento | evolução da exposição por sprint |
| `decisoes` | Decisões | decisões baseadas em dados (R2 ≥ 3, R3 ≥ 5) |

Com a URL preenchida, o painel local reflete a planilha em até 5 minutos. No
GitHub Pages, o deploy baixa as abas publicadas e empacota junto do app (o
navegador não lê a planilha direto). Sem URL, vale o CSV local e a tela diz isso.
As abas EVM - Velocity, EVM - Valor Agregado, EVM - Índices e Burndown, Sumário
EVM e Matriz **não são mais lidas**: o painel calcula tudo com os pontos do Zenhub.

## Formato dos arquivos do pipeline

**SonarCloud** — `fga-eps-mds-<repo>-MM-DD-YYYY-HH-MM-SS-<branch>.json`

```
baseComponent.measures[]  → agregado do repositório (coverage, ncloc, tests...)
components[].measures[]   → o mesmo, por diretório e arquivo
```

A data sai do nome do arquivo: é ela que monta a série temporal. Cada execução do
workflow vira um ponto no gráfico.

**GitHub** — `GitHub_API-Issues-<org>-<repo>.json` (lista de issues) e
`GitHub_API-Runs-<org>-<repo>-<data>.json` (`{total_count, workflow_runs[]}`).

## Acessibilidade

A paleta categórica foi validada para deuteranopia, protanopia e tritanopia.
Cores de status nunca aparecem sozinhas — sempre com ícone e rótulo. Todo gráfico
tem visão em tabela no expansor logo abaixo.

## Evolução por release

| Release | O que acrescenta |
| --- | --- |
| **DA-R1** (28/09) | Indicadores de processo e projeto: velocity, burndown, EVM-Ágil, matriz de riscos |
| **DA-R2** (26/10) | Métricas de qualidade normalizadas, ponderadas e agregadas; comparação R1 × R2; ≥3 decisões |
| **DA-R3** (30/11) | Canvas Analytics, planejado × realizado, ≥5 decisões, retrospectiva do uso de IA |

## Referência

O dashboard de 2026.1 (`2026.1-MeasureSoftGram-DOC/Analytics/dashboard.py`) é a
referência anterior: 1272 linhas com Gantt, velocity e o modelo **Q-Rapids**. Vale
consultar para os gráficos de processo que ainda faltam aqui.

## Velocity pela API do Zenhub

A aba **Projeto → Velocity (Zenhub)** usa dados reais da API GraphQL do Zenhub,
em camadas separadas:

```
src/zenhub/client.py        # única camada que fala com a API (paginação, retries, rate limit)
src/zenhub/queries.py       # queries, validadas contra o schema público
src/zenhub/normalizacao.py  # nós GraphQL -> registros planos
src/zenhub/coleta.py        # snapshot em data/zenhub/velocity/
src/velocity.py             # calculate_velocity / calculate_average_velocity / calculate_completion_rate
src/velocity_dashboard.py   # render_filters / render_metrics / render_velocity_chart / render_table
scripts/coleta_velocity.py  # coleta pela linha de comando (e pelo botão "Atualizar dados")
tests/                      # python -m unittest discover -s tests -v
```

Chave em `Analytics/.env` (`ZENHUB_API_KEY`, ver `.env.example`) ou no secret do
GitHub; nunca no código nem no site publicado. Regras, campos usados e limitações
do planejado: `docs/metricas/velocity-zenhub.mdx`.
