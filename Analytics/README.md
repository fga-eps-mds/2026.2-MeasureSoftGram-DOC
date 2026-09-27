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
| **Projeto** | Planilhas do time | Google Sheets publicado como CSV, ou `planilhas/*.csv` |

Produto e processo são **100% automáticos**. Projeto é manual por natureza:
horas trabalhadas e julgamento de risco não se coletam de repositório.

> **A regra que governa este app:** todo número exibido vem de um arquivo. Quando
> um dado não existe, o painel diz que não existe e explica por quê. Um indicador
> ausente e declarado é informação; um inventado é ruído — e reprodutibilidade é
> critério de avaliação.

## Estrutura

```
Analytics/
├── app.py              # entrada do Streamlit (visão geral + quatro dimensões)
├── config.py           # ÚNICO arquivo que o time edita: URLs das planilhas
├── src/
│   ├── loader.py       # descoberta e parse dos .json e das planilhas
│   ├── resumo.py       # indicadores e status da Visão geral
│   └── theme.py        # paleta validada, metas por release
├── planilhas/          # CSVs de apoio, usados quando não há planilha publicada
│   ├── evm.csv
│   ├── velocity.csv
│   ├── riscos.csv
│   └── decisoes.csv
├── data/               # ← o pipeline escreve aqui. Não editar à mão.
├── stlite/build.py     # empacota o app para o GitHub Pages
├── .streamlit/
│   └── config.toml
└── requirements.txt
```

`data/` é território do pipeline: os workflows dos oito repositórios commitam os
`.json` ali. Por isso as planilhas do time ficam em `planilhas/`, separadas — o
que é gerado nunca se mistura com o que é escrito.

O app também lê `../analytics-raw-data/` na raiz do repositório, porque dois
workflows ainda publicam lá.

## Modelo de gestão (DA-R1)

A aba **Projeto** calcula velocity, burndown e AgileEVM em `src/gestao.py`, a
partir de:

| Arquivo | O que é |
| --- | --- |
| `planilhas/sprints.csv` | Calendário oficial (o do Zenhub) e release de cada sprint |
| `planilhas/releases.csv` | Entrega e PRP de linha de base de cada release |
| `planilhas/parametros.csv` | Capacidade, custo/hora, critério de feito, níveis pontuados |
| `planilhas/horas.csv` | Horas reais por integrante e sprint (AC) |
| `data/zenhub/zenhub-sprints-*.json` | Snapshot do quadro (`scripts/coleta_zenhub.py`) |

Atualizar o Zenhub:

```bash
export ZENHUB_TOKEN=...   # Zenhub > Settings > API
python scripts/coleta_zenhub.py
```

O dicionário de cada indicador está em `docs/metricas/modelo-de-gestao.mdx`.

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
| **Projeto** | AgileEVM, velocity/burndown e custos (planilha Custos e AgileEVM) |
| **Riscos e decisões** | Matriz de riscos e registro de decisões (planilha Riscos e Decisões) |

A visão geral não calcula nada novo: lê os mesmos dados das outras abas e aplica
as mesmas metas (`theme.METAS`, SPI ≥ 0,95, CI ≥ 80%, conclusão ≥ 80%). O seletor
**Metas da release** na barra lateral começa na release em andamento.

## Planilhas do time

Editar CSV e commitar a cada atualização não funciona na prática: ninguém faz. A
equipe de 2026.1 resolveu lendo planilhas do Google direto, e mantivemos a
abordagem.

Publique a aba em **Arquivo → Compartilhar → Publicar na web**, formato CSV, e
cole a URL em `config.py`. O painel passa a refletir a planilha em até 5 minutos,
sem commit nenhum. Enquanto a URL estiver vazia, ele usa o CSV local — e mostra
na tela qual das duas fontes foi lida.

### Formato esperado

`evm` — layout **AgileEVM**, o mesmo da equipe de 2026.1: três linhas de
cabeçalho (a linha 3 é a dos nomes de coluna), uma linha por sprint, moeda em
formato brasileiro (`R$ 5.282,36`). O leitor procura as colunas pelo nome, então
acrescentar coluna no meio não quebra nada; renomear, sim. As colunas que o
painel usa:

```
Sprint (n) · Início da Sprint · Fim da sprint · Pontos planejados (PP)
Points Completed (PC) · Planned Value (PV) · Earned Value (EV) · Actual Cost (AC)
```

CPI, SPI e EAC são recalculados aqui a partir de PV/EV/AC — as colunas de índice
da planilha servem de conferência, não de fonte.

**O EVM exige horas reais individuais**: sem registro semanal não há linha de
base, e preencher retroativamente por estimativa descaracteriza o indicador.

`velocity` — cabeçalho na linha 2, uma linha por sprint:

```csv
Sprint,Pontos planejados (PP),Points Completed (PC),Velocity,Velocity mean
1,21,18,18,18
```

Se a aba não existir, o painel deriva a velocity de PP/PC do próprio EVM e diz
na tela que derivou.

`riscos` — probabilidade e impacto em `Baixa` / `Média` / `Alta`:

```csv
id,risco,probabilidade,impacto,resposta,responsavel,status
R01,Motor de calculo nao reproduzivel,Alta,Alto,Mitigar,,Aberto
```

`decisoes` — o registro que a R2 (≥3) e a R3 (≥5) cobram:

```csv
data,metrica,causa,decisao,resultado
2026-09-24,coverage,Cobertura em 82.7% contra meta de 85%,Priorizar testes em X,
```

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
