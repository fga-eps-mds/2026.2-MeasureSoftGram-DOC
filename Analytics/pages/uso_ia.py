"""Uso de IA — retrospectiva crítica do uso de IA generativa no semestre e as evidências (pedido, onde, aceito ou
descartado e por quê). Combinados da equipe em docs/equipe/uso-de-ia.mdx; evidências em data/ia/evidencias.json."""

from __future__ import annotations

import streamlit as st

from src.components import layout, rastreio
from src.data import uso_ia

DOC = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC"
COMBINADOS = "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/equipe/uso-de-ia/"
GH = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-"


def _retrospectiva() -> None:
    layout.secao("O que a IA acertou", "Onde a IA poupou trabalho sem perder qualidade?")
    st.markdown(f"""
- **Reproduzir antes de corrigir.** Os bugs do login com GitHub ([Service#32]({GH}Service/pull/32)), do `state` do
  OAuth ([Front#46]({GH}Front/pull/46)) e do fechamento da release ([Service#78]({GH}Service/pull/78)) foram
  reproduzidos antes da correção, com teste RED falhando pelo motivo certo e o GREEN em commit separado.
- **Ler muito volume com evidência.** A triagem das 44 issues de bug herdadas de 2026.1
  ([DOC#38]({DOC}/issues/38)) deu um veredito por issue, com o comando executado ou o arquivo e a linha.
- **Achar o que ninguém tinha visto.** O `make test` do Service não coletava `accounts/tests.py` (187 testes no PR
  contra 315 na coleta do CI); o total de métricas zerado no seed ([Service#86]({GH}Service/pull/86)); o conflito de
  migrações `0018` entre duas branches.
- **Medir em vez de supor.** A complexidade cognitiva do Plugin e do Front foi medida com o `eslint-plugin-sonarjs`,
  que reproduziu os números do SonarCloud antes do refactor ([Plugin#12]({GH}Plugin/pull/12)).
""")

    layout.secao("O que a IA errou", "Que erros só apareceram porque alguém conferiu?")
    st.markdown("""
- **Conclusão apressada por leitura estática:** o bug do qualifier TRK/FIL foi dado como aberto e já estava corrigido.
- **Plano baseado numa suposição:** o redirecionamento para domínio externo no OAuth não acontece no Next 12; só o teste
  no navegador mostrou isso.
- **Números errados na análise de dados:** o filtro de bots excluía um integrante cujo login contém "bot"; a taxa de CI
  misturava o repositório de documentação (71,4% em vez de 82,8%); e a IA afirmou que todos lançaram horas quando os
  dados não mostram quem lançou.
- **Fatos trocados em texto:** o rascunho do MD-R2 atribuiu um componente à pessoa errada e chamou homologação de
  produção.
- **Escopo e regras:** propôs mudanças fora do pedido (um `console.error` que não reprovava o Sonar) e, numa sessão,
  digitou um comando proibido pelas regras do repositório (`gh api` sem argumentos, sem requisição feita).

Todos os erros acima foram pegos na revisão humana ou num teste que a própria IA rodou a pedido, antes de publicar.
""")

    layout.secao("O que exigiu julgamento humano", "O que não delegamos, e por quê?")
    st.markdown(f"""
- **Segurança:** não vincular contas no login OAuth (o allauth apagaria a senha local) e aceitar que a chave antiga
  vire o token da GitHub Action (não quebra integrações, mas não expira no logout).
- **Escopo e dependências:** não avançar os ponteiros dos submódulos do Platform (já estavam com outra pessoa) e adiar o
  upgrade do TypeScript do Front.
- **O que só uma pessoa faz:** login real no navegador, autorizar o App do GitHub, reiniciar o Docker e homologar com o
  PO.
- **Publicação:** push, PR, comentário, merge e fechamento de issue só com aval explícito, caso a caso. A IA não revisa
  nem aprova PR; as exceções de merge foram registradas no próprio PR.
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
    layout.titulo_pagina("Uso de IA", "Retrospectiva crítica do uso de IA generativa no semestre: o que acertou, o que "
                         "errou, o que exigiu julgamento humano e as evidências de cada caso.")
    _retrospectiva()
    _critica_ao_dashboard()
    _evidencias()
