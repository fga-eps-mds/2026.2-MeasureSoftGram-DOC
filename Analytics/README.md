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
| Bugs, vulnerabilidades, code smells, hotspots, dívida técnica, Quality Gate, severidade, histórico | SonarCloud | `scripts/coleta_sonar.py` → `data/sonar/` (workflow `coleta-dados.yml`: diário e sob demanda) |
| Sprints, story points, velocity, backlog, pipelines, épicos, releases | Zenhub | `scripts/coleta_velocity.py` → `data/zenhub/velocity/` (workflow `coleta-dados.yml`: diário e sob demanda) |
| Custos, time por semana, horas, riscos, monitoramento, decisões | Planilha | abas publicadas no Google em CSV (`config.PLANILHAS`), sem cópia local |
| Execuções da CI | GitHub | `metrics.yml` → `GitHub_API-Runs-*.json` |

A planilha **não repete** nada que o Sonar ou o Zenhub têm, e não há cópia local em CSV:
aba sem URL ou que não responde aparece como indisponível. As regras do cálculo da velocity
(níveis pontuados, janela de planning) ficam em `config.PARAMETROS`; o critério de feito é fixo: **a issue só precisa estar fechada** para os story points contarem. **Nenhum valor é
inventado:** métrica sem insumo aparece como *Indisponível*, com o motivo e o que
falta para calculá-la (ex.: *CPI indisponível: Actual Cost não foi fornecido*).

## Páginas

| Página | Pergunta que responde |
| --- | --- |
| **Visão Executiva** | Como está o projeto? Status geral, KPIs, situação por dimensão, planejado × realizado, pontos de atenção |
| **Agile EVM** | Estamos no prazo e no custo? PV, EV, AC, BAC, SV, CV, SPI, CPI, EAC, ETC, burndown |
| **Qualidade (Q-Rapids)** | Quatro indicadores do plano, metas, pisos, portões e detalhe por arquivo/sprint |
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
└── tests/                  # python -m unittest discover -s tests -v
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

## Publicação (Streamlit Community Cloud)

O app publicado está em **https://20262-measuresoftgram-doc.streamlit.app/** — é o link **Dashboard** do topo da documentação.
O Streamlit Community Cloud roda `Analytics/app.py` da branch `main` e se atualiza
sozinho a cada push (inclusive os commits das coletas). Os dados vêm dos arquivos
de `Analytics/data/` e das abas publicadas da planilha, lidas ao vivo.

- Nenhum secret é configurado lá: o botão "Atualizar dados" do Zenhub fica
  desligado e as coletas continuam nos workflows do GitHub.
- Sem acesso por alguns dias o app dorme; ao abrir, clique em
  *Yes, get this app back up* e aguarde ~30 s.
- O endereço antigo `<site da doc>/dashboard/` redireciona para o app
  (`static/dashboard/index.html`).

## Limitações conhecidas

- O Zenhub só registra mudanças de escopo feitas depois do início da sprint. Issues que
  já estavam na sprint contam no concluído, mas o **planejado** (linha de base) só vê
  os eventos — daí sprints com planejado 0 SP.
- As queries do **backlog completo** (`PIPELINES`, `PIPELINE_ISSUES` em
  `src/zenhub/queries.py`) precisam ser conferidas contra o schema do Zenhub. Se
  falharem, a coleta segue e a página avisa que só as issues das sprints foram lidas.
- Sem horas registradas na aba Horas, o custo real (AC) e tudo que depende dele (CPI,
  CV, ETC, EAC) ficam indisponíveis — o custo planejado não substitui o real.

## Plano de qualidade da R3

A página **Qualidade (Q-Rapids)** compara R1, R2 e R3 até a data atual. Release e período
selecionados na barra lateral não alteram essa comparação fixa; repositórios e branch do Sonar são respeitados.
As janelas são 24/08–28/09, 29/09–26/10 e 27/10–30/11/2026. O Sonar usa o último snapshot **dentro**
da janela; sem coleta na janela, não reutiliza silenciosamente um dado de outra release.

A configuração fica em `config.py`: catálogo das 44 métricas, fontes, fórmulas, justificativas,
mapa indicador/fatores, metas agregadas e por repositório e os cinco portões. As 10 incluídas
são M1, M2, M3, M5, M6, M7, M8, M9, M10 e DT; há 8 monitoradas, 8 habilitáveis e 18 excluídas.
Monitoradas aparecem com valor e sem peso; habilitáveis mostram a condição necessária para entrar.
O catálogo completo e os cinco critérios de seleção também aparecem em **Metodologia e Fontes**.

- Fator: média das métricas incluídas calculáveis na escala 0–1.
- Indicador: média dos fatores disponíveis; falta de dado nunca recebe zero.
- Pesos: `QRAPIDS["plano"]["pesos_fatores"]`, por indicador. `None` usa `1/n`; um dicionário
  informa um peso não negativo para cada fator. Os pesos são normalizados entre os fatores disponíveis,
  e as metas dos indicadores usam a mesma fórmula, com truncamento em duas casas.
- M8: mediana de `test.yml`, fora da média; até 5 minutos por repositório e teto crítico de 10 minutos.
- M9: conclusão por sprint; DT: Tasks/Sub-tasks concluídas no escopo da release. DT/Readiness em curso é parcial.
- Pisos: M5 ≥ 0,80 e M10 ≥ 0,90 por repositório. São restrições das métricas, sem criar um sexto portão.
- Atingido: exige meta atingida, portões comprovados e pisos atendidos. Dados ausentes impedem a comprovação;
  o painel identifica os repositórios ausentes. Ao selecionar repositórios, os portões usam esse escopo
  (por exemplo, relatório 1/1 no Core); sem seleção, são os oito repositórios do produto.

M1, M2 e M6 têm detalhe separado por Python/TypeScript. As tabelas mostram repositório, linguagem,
arquivo/sprint, fórmula, fonte e links estáveis para o plano. Os pesos do notebook são mantidos somente
para compatibilidade da implementação por arquivo e dos testes de referência; não agregam os indicadores.

As metas por repositório registram os números publicados no plano de 07/11, base `43c22d6`; não são
recalibradas automaticamente quando chegam coletas novas. Mudanças de pesos ou metas requerem atualizar
o plano e suas evidências. A implementação não equivale ao aceite do professor nem ao registro de D6–D9.

### Ambiente e verificação

```bash
# Na raiz do repositório; Node >= 20 e Python >= 3.11
python3 -m venv .venv
.venv/bin/python -m pip install -r Analytics/requirements.txt
npm ci
.venv/bin/python -m unittest discover -s Analytics/tests -v
npm run typecheck
npm run build
.venv/bin/python -m streamlit run Analytics/app.py
```

Os testes históricos precisam do commit `43c22d6` no histórico Git (clones rasos pulam essa verificação).
Dois testes do cliente Zenhub abrem um servidor HTTP em localhost: um sandbox que proíbe sockets
precisa liberar a execução local desses testes. Nenhum token é necessário para os testes nem para consultar
os snapshots versionados; atualizar Zenhub/Sonar/GitHub depende das credenciais de coleta correspondentes.

Os arquivos de `data/` são gerados pelos coletores e não devem ser corrigidos manualmente. Na base histórica de 07/11 faltavam
relatórios em AI/Plugin. Em 10/11, os pipelines públicos da `develop` desses dois repositórios já
geram e declaram os relatórios de testes; confirmar sua importação depende de nova análise e coleta
do Sonar. Não foram necessárias alterações adicionais nesses dois repositórios. A habilitação de cobertura de ramos muda a base de comparação: depois dela, coletar
novamente antes de interpretar a evolução de M5. O coletor da API passa a pedir `line_coverage` e
`branch_coverage` separadamente, sem preencher dados ausentes nem reescrever snapshots antigos. O Dev Container instala as dependências de
`Analytics/requirements.txt` e do lockfile npm e abre o Streamlit com as proteções padrão.
