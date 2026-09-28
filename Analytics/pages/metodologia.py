"""Metodologia e Fontes — de onde vem cada número, fórmulas, limitações e estado das coletas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import layout
from src.metrics.calculations import data_br, num

STATUS_COLETA = {"ok": "Coletado", "parcial": "Parcial", "sem dados": "Sem dados", "erro": "Erro na leitura"}


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Metodologia e Fontes", "Origem dos dados, periodicidade, fórmulas, limitações e o "
                         "tratamento de dados ausentes.")

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

    layout.secao("Fontes e responsabilidades", "Por que cada informação vem de onde vem?")
    st.markdown(f"""
| Fonte | Etiqueta | Usada para | Como chega ao painel | Atualização |
|---|---|---|---|---|
| **SonarCloud** | {layout.etiqueta('SONAR')} | qualidade técnica: cobertura, duplicação, bugs, vulnerabilidades, code smells, hotspots, dívida técnica, ratings, Quality Gate, testes | `metrics.yml` de cada repositório → `data/*.json`; API do SonarCloud → `scripts/coleta_sonar.py` → `data/sonar/` | a cada execução do pipeline; API diária (workflow `coleta-dados.yml`) |
| **Zenhub** | {layout.etiqueta('ZENHUB')} | gestão ágil: sprints, story points, velocity, backlog, pipelines, épicos, releases, throughput | API GraphQL → `scripts/coleta_velocity.py` → `data/zenhub/velocity/` | diária (workflow `coleta-dados.yml`) ou botão na página do Zenhub |
| **Planilha** | {layout.etiqueta('PLANILHA')} | só o que não existe nas outras: custos, time por semana, horas, riscos, monitoramento, decisões | abas publicadas no Google em CSV (`config.PLANILHAS`); sem cópia local | a cada {config.CACHE_PLANILHAS_S // 60} min (local) ou a cada deploy (GitHub Pages) |
| **GitHub** | {layout.etiqueta('GITHUB')} | processo: execuções e resultado da CI | `metrics.yml` → `GitHub_API-Runs-*.json` | a cada execução do pipeline |
| **Calculado** | {layout.etiqueta('CALCULADO')} | indicadores derivados (EVM, variações, status) | `src/metrics/` — funções puras, com testes em `tests/` | a cada abertura do painel |
""", unsafe_allow_html=True)
    st.markdown("A planilha **não repete** nenhum dado do Sonar ou do Zenhub: nenhum ponto, sprint ou métrica de "
                "código é digitado nela. As abas antigas de EVM da planilha não são lidas — o EVM é calculado com os "
                "pontos do Zenhub.")

    layout.secao("Fórmulas dos indicadores", "Como cada número derivado é calculado?")
    st.markdown(f"""
**Agile EVM** (Sulaiman, Barton & Blackburn, 2006), por release, a cada sprint *n*:

| Indicador | Fórmula | Insumos |
|---|---|---|
| PPC — % planejado | semanas decorridas ÷ semanas da release | datas das sprints (Zenhub) |
| APC — % realizado | RPC ÷ PRP | SP concluídos e escopo da release (Zenhub) |
| BAC | Σ custo planejado das semanas da release | abas Custos e Planejamento |
| PV | PPC × BAC | |
| EV | APC × BAC | |
| AC | Σ horas registradas × custo/hora | abas Horas e Custos |
| SV | EV − PV | |
| CV | EV − AC | |
| SPI | EV ÷ PV | |
| CPI | EV ÷ AC | |
| ETC | (BAC − EV) ÷ CPI | |
| EAC | AC + ETC | |

**Gestão ágil:** critério de feito = issue **fechada** (em qualquer pipeline; aberta não conta) · velocity = SP das issues pontuáveis ({', '.join(sorted(ctx.zh_regras.tipos_pontuados))}) fechadas
dentro da sprint · velocity média = média das sprints concluídas (≥ {ctx.zh_regras.min_sprints_media}) · média móvel
= média das 3 últimas sprints concluídas · taxa de conclusão = SP concluídos ÷ SP planejados · throughput = issues
pontuáveis concluídas por semana.

**Qualidade:** atual → anterior → variação entre os dois últimos dias com coleta; percentuais em pontos percentuais
(p.p.). Entre repositórios: média simples para percentuais, soma para contagens, pior valor para ratings. Modelo de
qualidade agregado (prévia DA-R2): proporção de arquivos dentro de limiares, ponderada em Manutenibilidade e
Confiabilidade (`src/metrics/qualidade.py`).

**Riscos:** exposição = probabilidade × impacto (1 a 5 cada) · baixo 1–5, médio 6–12, elevado 15–25.
""")

    layout.secao("Metas e status", "Quando um indicador é conforme, de atenção ou crítico?")
    metas = pd.DataFrame([
        {"Indicador": "Cobertura de testes", "Conforme": " / ".join(f"{k} ≥ {num(v)}%" for k, v in config.METAS["coverage"].items()),
         "Atenção": "até 10% abaixo da meta", "Crítico": "mais de 10% abaixo"},
        {"Indicador": "Duplicação", "Conforme": " / ".join(f"{k} ≤ {num(v)}%" for k, v in
                                                          config.METAS["duplicated_lines_density"].items()),
         "Atenção": "até 1,5 × a meta", "Crítico": "acima de 1,5 × a meta"},
        {"Indicador": "SPI e CPI", "Conforme": f"≥ {num(config.META_INDICE_EVM, 2)}", "Atenção": f"{num(config.LIMITE_INDICE_CRITICO, 2)} a {num(config.META_INDICE_EVM, 2)}",
         "Crítico": f"< {num(config.LIMITE_INDICE_CRITICO, 2)}"},
        {"Indicador": "Taxa de conclusão das sprints", "Conforme": f"≥ {num(config.META_TAXA_CONCLUSAO)}%",
         "Atenção": f"{num(config.LIMITE_TAXA_CRITICO)}% a {num(config.META_TAXA_CONCLUSAO)}%",
         "Crítico": f"< {num(config.LIMITE_TAXA_CRITICO)}%"},
        {"Indicador": "Sucesso da CI", "Conforme": f"≥ {num(config.META_CI_SUCESSO)}%",
         "Atenção": f"{num(config.LIMITE_CI_CRITICO)}% a {num(config.META_CI_SUCESSO)}%",
         "Crítico": f"< {num(config.LIMITE_CI_CRITICO)}%"},
        {"Indicador": "Riscos elevados abertos", "Conforme": "0", "Atenção": "1 ou 2", "Crítico": "3 ou mais"},
    ])
    st.dataframe(metas, use_container_width=True, hide_index=True)
    st.markdown(f"Cores: <b style='color:{theme.STATUS['good']}'>verde = conforme</b> · "
                f"<b style='color:{theme.STATUS['warning']}'>amarelo = atenção</b> · "
                f"<b style='color:{theme.STATUS['critical']}'>vermelho = crítico</b> · "
                f"<b style='color:{theme.STATUS['neutral']}'>cinza = informativo ou indisponível</b>. "
                "O status sempre aparece também em texto.", unsafe_allow_html=True)

    layout.secao("Tratamento de dados ausentes", "O que o painel faz quando um dado não existe?")
    st.markdown("""
- **Nenhum valor é inventado, estimado ou trocado por outra métrica.** Um indicador sem insumo aparece como
  *Indisponível*, com o motivo e o que seria preciso para calculá-lo (ex.: *CPI indisponível: Actual Cost não foi
  fornecido*).
- **Custo real (AC) só com horas registradas.** Sem horas na aba Horas, AC, CPI, CV, ETC e EAC ficam indisponíveis —
  o custo planejado não substitui o real.
- **Planejado da sprint só pelo histórico do Zenhub.** Sem histórico de escopo, o planejado fica indisponível; issue
  sem estimativa conta 0 SP e é listada nas observações.
- **Fonte fora do ar não derruba o painel:** ela aparece como *Erro* ou *Sem dados* na tabela acima e as páginas que
  dependem dela avisam.
- Filtros só aparecem onde a dimensão existe (ex.: prioridade e responsável só com o backlog completo do Zenhub).
""")

    layout.secao("Limitações conhecidas", "O que os números ainda não capturam?")
    st.markdown("""
- O Zenhub só registra mudanças de escopo feitas **depois** do início da sprint; issues que já estavam na sprint no
  início não têm evento. Elas contam no concluído, mas o **planejado** (linha de base) só enxerga os eventos — por isso
  sprints aparecem com planejado 0 SP quando nada foi estimado ou movido depois da planning.
- A coleta do **backlog completo** (todos os pipelines, prioridade e responsável) usa queries novas que precisam ser
  conferidas com `python scripts/diagnostico_zenhub.py`; se falharem, a coleta segue e o painel usa só as issues das
  sprints, avisando.
- Métricas do SonarCloud que o `metrics.yml` não pede (bugs, vulnerabilidades, code smells, hotspots, dívida,
  Quality Gate) dependem do snapshot da API (`scripts/coleta_sonar.py`).
- Repositórios sem projeto no SonarCloud (ex.: AI) não têm métrica de qualidade.
- Médias entre repositórios são simples (não ponderadas por linhas de código).
""")
