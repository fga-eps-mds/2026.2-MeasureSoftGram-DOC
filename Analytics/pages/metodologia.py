"""Metodologia e Fontes — de onde vem cada número, fórmulas, limitações e estado das coletas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src.components import filters, layout
from src.metrics.calculations import data_br

STATUS_COLETA = {"ok": "Coletado", "parcial": "Parcial", "sem dados": "Sem dados", "erro": "Erro na leitura"}


def pagina():
    ctx, f = layout.estado()
    filters.da_pagina(f, {}, tem_filtros=False)
    layout.titulo_pagina("Metodologia e Fontes", "Origem e atualização dos dados, regras que diferem das "
                         "ferramentas, limitações e o tratamento de dados ausentes.")

    layout.secao("Metadados e atualização dos dados", "De onde veio cada número e quando foi atualizado?")
    linhas = []
    for fo in ctx.fontes:
        periodo = (f"{data_br(fo.periodo[0])} a {data_br(fo.periodo[1])}"
                   if fo.periodo and fo.periodo[0] is not None else "—")
        linhas.append({"Fonte": fo.fonte, "Entrada": fo.entrada,
                       "Última atualização": data_br(fo.ultima_atualizacao, True),
                       "Período dos dados": periodo, "Registros": fo.registros,
                       "Status da coleta": STATUS_COLETA.get(fo.status, fo.status), "Observação": fo.mensagem})
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True,
                 column_config={"Observação": st.column_config.TextColumn(width="large")})
    st.caption(f"Período analisado nas páginas: {data_br(f['periodo'][0])} a {data_br(f['periodo'][1])} "
               f"(filtro global). Situação calculada em {data_br(ctx.hoje)}.")

    if ctx.repos_ignorados:
        st.caption("Repositórios ignorados por não serem do semestre 2026.2 (`config.PREFIXO_REPOS_PROJETO`): "
                   + " · ".join(f"{fonte}: {', '.join(sorted(r))}" for fonte, r in ctx.repos_ignorados.items())
                   + ". Os `.json` dos repositórios centrais chegam em `data/` pelo `metrics.yml` deles, e as issues "
                     "deles aparecem no Zenhub, mas nada disso entra em nenhuma métrica do painel.")

    layout.secao("Como os filtros funcionam", "Onde cada filtro da barra lateral vale?")
    st.markdown("""
Todos os filtros ficam na **barra lateral**. Em cima, os **filtros globais**, iguais em todas as páginas; embaixo,
em **Filtros desta página**, os filtros próprios da página aberta e o resumo *Como os filtros globais valem aqui*.

| Página | Release | Período | Repositórios | Branch | Filtros da página |
|---|---|---|---|---|---|
| Visão Executiva | metas e release em foco | situação no fim do período | Sonar, Zenhub, SPI, CI | Sonar | — |
| Gestão ágil | período padrão | sprints que terminam no período | stories do repositório | — | sprint, épico, pessoa, issue, sprint do burndown |
| Agile EVM | release analisada | sprint concluída até o fim do período | prazo (SPI); custo é do time | — | release (só com *Semestre inteiro*), sprint |
| Custos | período padrão | semanas e horas do período | não se aplica (custo do time) | — | sprint, integrante |
| Riscos | período padrão | identificados até o fim; revisões no período | não se aplica | — | status, nível, categoria, responsável |
| Decisões | meta da release | tabela no período; meta acumulada até o fim | não se aplica | — | tipo, status, indicador |
| Qualidade técnica | metas | situação no fim do período; evolução no período | repositórios | coletas do pipeline | Quality Gate, linguagem, métrica do gráfico |
| Qualidade (Q-Rapids) | comparação entre releases | nota na última coleta até o fim do período; métricas de processo no período | repositórios avaliados | coletas do pipeline | repositório do detalhamento |
| Integração contínua | período padrão | execuções criadas no período | repositórios | — | workflow, branch da execução |

**Situação no fim do período**: com a R1 escolhida, a página mostra o valor de cada métrica na última coleta até
28/09 — é assim que dá para comparar R1 × R2 sem misturar coletas. O Quality Gate e os problemas por severidade só
existem no snapshot mais recente da API (sem histórico): num período que termina antes dele, ficam de fora.
""")

    layout.secao("Fontes e responsabilidades", "Por que cada informação vem de onde vem?")
    st.markdown(f"""
| Fonte | Cor | Usada para | Como chega ao painel | Atualização |
|---|---|---|---|---|
| **SonarCloud** | {layout.etiqueta('SONAR')} | qualidade técnica: cobertura, duplicação, bugs, vulnerabilidades, code smells, hotspots, dívida técnica, ratings, Quality Gate, testes; medidas por arquivo (complexidade, comentários, duplicação, cobertura, violações bloqueantes/críticas) para o modelo Q-Rapids | `metrics.yml` de cada repositório → `data/*.json`; API do SonarCloud → `scripts/coleta_sonar.py` → `data/sonar/` | a cada execução do pipeline; API diária (workflow `coleta-dados.yml`) |
| **Zenhub** | {layout.etiqueta('ZENHUB')} | gestão ágil: sprints, story points, velocity, backlog, pipelines, épicos, releases, throughput | API GraphQL → `scripts/coleta_velocity.py` → `data/zenhub/velocity/` | diária (workflow `coleta-dados.yml`) ou botão na página do Zenhub |
| **Planilha** | {layout.etiqueta('PLANILHA')} | só o que não existe nas outras: custos, time por semana, horas, riscos, monitoramento, decisões | abas publicadas no Google em CSV (`config.PLANILHAS`); sem cópia local | a cada {config.CACHE_PLANILHAS_S // 60} min (local) ou a cada deploy (GitHub Pages) |
| **GitHub** | {layout.etiqueta('GITHUB')} | processo: execuções e resultado da CI; issues (labels, descrição, milestone) e commits com arquivos alterados para o modelo Q-Rapids | API do GitHub → `scripts/coleta_github.py` → `data/github/` (`runs-`, `issues-`, `commits-`); `metrics.yml` → `GitHub_API-Runs-*.json` | 3 vezes por dia (workflow `coleta-dados.yml`) e a cada execução do pipeline |
| **Calculado** | {layout.etiqueta('CALCULADO')} | indicadores derivados (EVM, variações, status) | `src/metrics/` — funções puras, com testes em `tests/` | a cada abertura do painel |
""", unsafe_allow_html=True)
    st.markdown("A planilha **não repete** nenhum dado do Sonar ou do Zenhub: nenhum ponto, sprint ou métrica de "
                "código é digitado nela. As abas antigas de EVM da planilha não são lidas — o EVM é calculado com os "
                "pontos do Zenhub.")

    st.caption("Fórmulas, siglas e parâmetros de cada indicador ficam nos menus **Legenda e fórmulas** e "
               "**Parâmetros usados** no topo de cada página.")

    layout.secao("Diferenças de propósito em relação ao Zenhub",
                 "Onde o painel conta diferente do Zenhub, e por quê?", ["ZENHUB"])
    regras = ctx.zh_regras
    st.dataframe(pd.DataFrame([
        {"Regra": "Quem pontua", "Zenhub (completedPoints)": "toda issue ou PR com estimativa",
         "Painel": f"só {', '.join(sorted(regras.tipos_pontuados))} sem filhas pontuáveis",
         "Por quê": "PR, Épico e pai de Tasks repetem o trabalho das filhas: somar os dois conta duas vezes"},
        {"Regra": "Até quando conta na sprint", "Zenhub (completedPoints)": "fechada até o fim da sprint",
         "Painel": (f"fechada até {regras.prazo_fechamento} (Brasília) do dia seguinte ao último dia"
                    if regras.prazo_fechamento else "fechada até o fim da sprint"),
         "Por quê": "combinado do time (config.PARAMETROS · prazo_fechamento_dia_seguinte)"},
        {"Regra": "Sprint da issue", "Zenhub (completedPoints)": "sprint atual da issue",
         "Painel": "sprint em que ela estava quando fechou (histórico de escopo)",
         "Por quê": "o Zenhub leva as abertas para a sprint seguinte e a sprint antiga perde o histórico"},
        {"Regra": "Estimativa ausente", "Zenhub (completedPoints)": "0 SP (o Team Velocity com assumed estimates presume)",
         "Painel": "0 SP e a issue aparece em 'Consistência do cadastro'",
         "Por quê": "nenhum número é inventado"},
        {"Regra": "Velocity média", "Zenhub (completedPoints)": "média das sprints do relatório",
         "Painel": f"média das sprints concluídas (≥ {regras.min_sprints_media}), sem a em andamento",
         "Por quê": "sprint em andamento tem valor parcial"},
    ]), use_container_width=True, hide_index=True)
    st.caption("A página ZenHub reproduz o número do Zenhub a partir do snapshot e lista, issue por issue, cada "
               "diferença com o motivo; se a reprodução não bater com a API, o bloco fica vermelho.")

    layout.secao("Tratamento de dados ausentes", "O que o painel faz quando um dado não existe?")
    st.markdown("""
- **Nenhum valor é inventado, estimado ou trocado por outra métrica.** Um indicador sem insumo aparece como
  *Indisponível*, com o motivo e o que seria preciso para calculá-lo (ex.: *CPI indisponível: Actual Cost não foi
  fornecido*).
- **Custo real (AC) só com horas registradas de todo o time.** Sem horas na aba Horas, ou com horas de só parte dos
  integrantes ativos da aba Planejamento, AC, CPI, CV, ETC e EAC ficam indisponíveis — o custo planejado não substitui
  o real e um AC parcial deixaria o CPI melhor do que é.
- **Planejado da sprint só pelo histórico do Zenhub.** Sem histórico de escopo, o planejado fica indisponível; issue
  sem estimativa conta 0 SP e é listada nas observações.
- **Fonte fora do ar não derruba o painel:** ela aparece como *Erro* ou *Sem dados* na tabela acima e as páginas que
  dependem dela avisam.
- Filtros só aparecem onde a dimensão existe (ex.: prioridade e responsável só com o backlog completo do Zenhub).
""")

    layout.secao("Limitações conhecidas", "O que os números ainda não capturam?")
    st.markdown("""
- O Zenhub só registra mudanças de escopo feitas **depois** do início da sprint. Issues que já estavam na sprint no
  início (sem evento) entram no planejado com a **estimativa atual**, não com a do dia da planning.
- O relatório *Team Velocity* do Zenhub com *assumed estimates* soma estimativas presumidas para issues sem estimativa;
  esse número não é reproduzível com dados reais. O comparável é o `completedPoints` da API (bloco *Comparação com o
  Zenhub* na página ZenHub).
- A coleta do **backlog completo** (todos os pipelines, prioridade e responsável) usa queries novas que precisam ser
  conferidas com `python scripts/diagnostico_zenhub.py`; se falharem, a coleta segue e o painel usa só as issues das
  sprints, avisando.
- Métricas do SonarCloud que o `metrics.yml` não pede (bugs, vulnerabilidades, code smells, hotspots, dívida,
  Quality Gate) dependem do snapshot da API (`scripts/coleta_sonar.py`).
- Repositórios sem projeto no SonarCloud (ex.: AI) não têm métrica de qualidade.
- Médias entre repositórios são simples (não ponderadas por linhas de código).
""")
