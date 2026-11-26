"""Uso de IA — retrospectiva crítica do uso de IA generativa no semestre e as evidências (pedido, onde, aceito ou
descartado e por quê). Combinados da equipe em docs/equipe/uso-de-ia.mdx; evidências em data/ia/evidencias.json."""

from __future__ import annotations

import streamlit as st

from src.components import layout, rastreio
from src.data import uso_ia

DOC = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC"
COMBINADOS = "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/equipe/uso-de-ia/"
GH = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-"


def _como_o_time_usou() -> None:
    layout.secao("Como o time usou IA", "Em que frentes a IA entrou no trabalho do semestre?")
    st.markdown(f"""
O time usou principalmente o **Claude** (Claude Code e o chat) e, numa parte do dashboard, o **Gemini**
(Antigravity), em quatro frentes: **planejamento e gestão** (rascunho de épicos, tasks e critérios de aceite; análise
de dependências; propostas de reestruturação), **código** (correções com TDD, refactors guiados pelo Sonar, páginas do
dashboard), **documentação** (reestruturação do site, arquitetura, modelo de dados) e **análise de dados do
dashboard** (números das apresentações de release).

Esta análise consolida o que está registrado em PRs, commits com coautoria de IA e conversas do grupo do time. As
evidências abaixo são do grupo, sem identificar integrantes; o registro individual de cada pessoa fica no seu
`MD_Template.md` ([combinado da equipe]({COMBINADOS})).
""")


def _retrospectiva() -> None:
    layout.secao("O que a IA acertou", "Onde a IA poupou trabalho sem perder qualidade?")
    st.markdown(f"""
- **Rascunho para começar, não para entregar.** Épicos, tasks, cenários e critérios de aceite rascunhados com IA
  deram ao time uma visão do trabalho da release logo no início; o escopo foi validado com o PO antes de virar
  compromisso.
- **Reproduzir antes de corrigir.** Os bugs do login com GitHub ([Service#32]({GH}Service/pull/32)), do `state` do
  OAuth ([Front#46]({GH}Front/pull/46)) e do fechamento da release ([Service#78]({GH}Service/pull/78)) foram
  reproduzidos antes da correção, com teste falhando pelo motivo certo e a correção em commit separado.
- **Volume com evidência.** A triagem das 44 issues de bug herdadas de 2026.1 ([DOC#38]({DOC}/issues/38)) deu um
  veredito por issue com a fonte para conferir, e a reestruturação do site de documentação (13 commits) foi feita com
  apoio de IA e integrada ao site.
- **Medir em vez de supor.** A complexidade do Plugin foi medida com a mesma regra do SonarCloud antes do refactor
  ([Plugin#12]({GH}Plugin/pull/12)), e a queda do dashboard no Streamlit Cloud foi resolvida medindo a memória de cada
  fonte de dados antes de mexer ([DOC#383]({DOC}/pull/383)).
- **Vários modelos se conferindo.** Na página Canvas Analytics ([DOC#368]({DOC}/pull/368)) um modelo escreveu a
  especificação, outro o código e um terceiro conferiu o diff contra os critérios de aceite.
""")

    layout.secao("O que a IA errou", "Que erros só apareceram porque alguém conferiu?")
    st.markdown("""
- **Números errados na análise de dados:** o filtro de bots excluía um integrante cujo login contém "bot"; a taxa de
  CI misturava o repositório de documentação (71,4% em vez de 82,8%); e a IA afirmou que todos lançaram horas quando os
  dados não mostram quem lançou.
- **Conclusões por leitura estática ou suposição:** um bug foi dado como aberto e já estava corrigido; um plano de
  correção previa um problema que o framework usado nem permitia.
- **Detalhes que parecem certos e não são:** um teste esperava "1,00" para 0,995, que em ponto flutuante vira "0,99";
  um link fixo entre páginas; um estilo de wireframe genérico.
- **Propostas difíceis de usar:** uma proposta de extensão do modelo matemático saiu técnica demais para ser entendida
  sem explicação e não foi adotada.
- **Texto com "cara de IA":** texto gerado chegou a ser passado para outra pessoa do time conferir se não estava
  "com cara de IA" antes de publicar.
- **Escopo:** sugestões de mudanças fora do que foi pedido, cortadas na revisão.
""")

    layout.secao("O que exigiu julgamento humano", "O que o time não delegou, e por quê?")
    st.markdown(f"""
- **Validação com o PO e com o professor:** critérios de aceite, escopo das issues e qualquer mudança no modelo
  matemático do Core passaram pelo PO ou pelo professor antes de entrar.
- **Segurança:** não vincular contas no login OAuth (a biblioteca de login apagaria a senha local).
- **Escopo e dependências:** o que entra em cada PR, quem toca em cada parte (por exemplo, os submódulos do Platform)
  e quando atualizar dependências grandes.
- **O que só uma pessoa faz:** login real no navegador, autorizações de conta e homologação com o PO.
- **Revisão e publicação:** a IA não revisa nem aprova PR; push, merge e fechamento de issue são decisões do time.
- **O que nunca passa pela IA** ([combinado da equipe]({COMBINADOS})): atas com o PO, decisões gerenciais,
  autoavaliação e defesa oral.
""")


def _critica_ao_dashboard() -> None:
    layout.secao("Crítica aos outputs automáticos do dashboard",
                 "Onde um texto ou status gerado pelo painel pode levar a uma leitura errada?")
    st.markdown(f"""
| Output automático | Onde | Risco de leitura | Como ler |
|---|---|---|---|
| **Pontos de atenção** ordenados por gravidade | Visão Executiva | "Sem dado" aparece ao lado de "crítico" e pode parecer desempenho ruim | Ausência de dado não vale zero: ler o motivo e corrigir a coleta antes de agir no indicador |
| **Velocity** e pontos entregues | Gestão ágil | Conta a issue só por estar fechada: issue fechada sem aceite conta, e trabalho pronto em issue aberta não conta | Cruzar com o pipeline de validação dos critérios de aceite |
| **CPI e custo real** do Agile EVM | Agile EVM e custos | O custo real é o custo do time por sprint, não horas apontadas; o CPI não mede esforço extra | Usar o CPI como tendência de custo do calendário, não como produtividade |
| **Taxa de sucesso da CI** | Integração contínua | Muda com o recorte de repositórios (71,4% com o DOC, 82,8% sem ele na R2) | Conferir o filtro de repositórios antes de citar o número |
| **Cobertura global** | Qualidade técnica | Repositório bem coberto na média pode ter arquivos pouco testados | Olhar a cobertura por arquivo (M1 do Q-Rapids) |
| **Tendência R1 → R2 → R3** | Canvas e Q-Rapids | Três pontos, e a R3 só fecha em 30/11 | Tratar como direção, não como tendência estatística |

Esses pontos vieram de erros reais de leitura no semestre (registrados nas evidências abaixo) e da seção de limitações
de [Metodologia e Fontes]({rastreio.pagina('Metodologia')}).
""")


def _evidencias() -> None:
    layout.secao("Evidências de uso de IA", "O que pedimos à IA, onde, e o que aceitamos ou descartamos?")
    try:
        df = uso_ia.evidencias()
    except (OSError, ValueError) as e:
        layout.indisponivel("Evidências indisponíveis", str(e), "corrigir data/ia/evidencias.json")
        return
    c1, c2 = st.columns(2)
    areas = c1.multiselect("Área", uso_ia.AREAS, placeholder="Todas", key="ia_area")
    resultados = c2.multiselect("Resultado", uso_ia.RESULTADOS, placeholder="Todos", key="ia_resultado")
    if areas:
        df = df[df["area"].isin(areas)]
    if resultados:
        df = df[df["resultado"].isin(resultados)]
    st.caption(f"{len(df)} evidência(s): {int((df['resultado'] == 'aceito').sum())} aceita(s), "
               f"{int((df['resultado'] == 'descartado').sum())} descartada(s). O pedido é o resumo do prompt, "
               "registrado no MD_Template.md de quem usou a IA.")
    st.dataframe(
        df.rename(columns={"data": "Data", "area": "Área", "pedido": "Pedido à IA (resumo do prompt)",
                           "onde": "Onde", "link": "Link", "resultado": "Resultado", "motivo": "Motivo"}),
        use_container_width=True, hide_index=True,
        column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                       "Link": st.column_config.LinkColumn(display_text="abrir"),
                       "Pedido à IA (resumo do prompt)": st.column_config.TextColumn(width="large"),
                       "Motivo": st.column_config.TextColumn(width="large")},
    )


def pagina():
    layout.titulo_pagina("Uso de IA", "Retrospectiva crítica do time sobre o uso de IA generativa no semestre: o que "
                         "acertou, o que errou, o que exigiu julgamento humano e as evidências de cada caso.")
    _como_o_time_usou()
    _retrospectiva()
    _critica_ao_dashboard()
    _evidencias()
