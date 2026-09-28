"""Blocos de apoio da página Gestão ágil: backlog atual e confiabilidade dos dados do Zenhub.

Ficam separados para a página principal seguir a ordem de análise (filtros → KPIs →
planejado → realizado → velocity → burndown → análises → issues).
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout
from src.metrics import agile
from src.metrics import velocity as vel
from src.metrics.calculations import num

SIT = [agile.CONCLUIDO, agile.ANDAMENTO, agile.PLANEJADO]
COR_SIT = alt.Scale(domain=SIT + [agile.NAO_CLASSIFICADO],
                    range=[theme.SERIES[0], theme.SERIES[1], theme.SERIES[2], theme.NEUTRO_CLARO])


def backlog(ctx, f, snap, todas, d):
    layout.secao("Backlog", "Como está distribuído o trabalho no quadro?", ["ZENHUB"])
    conhecidos = list(agile.SITUACAO_PIPELINE)
    ordem_pipe = sorted(todas["pipeline"].dropna().unique(),
                        key=lambda p: (conhecidos.index(p) if p in conhecidos else len(conhecidos), p))
    por_pipe = agile.distribuicao(d, "pipeline")
    if por_pipe.empty:
        st.caption("Sem issues para os filtros selecionados.")
    else:
        barras = (alt.Chart(por_pipe).mark_bar(cornerRadiusEnd=3, stroke=theme.INK["surface"], strokeWidth=1)
                  .encode(y=alt.Y("pipeline:N", sort=ordem_pipe, title=None),
                          x=alt.X("itens:Q", title="Issues"),
                          color=alt.Color("situacao:N", title="Situação", scale=COR_SIT,
                                          sort=SIT + [agile.NAO_CLASSIFICADO]),
                          tooltip=[alt.Tooltip("pipeline:N", title="Pipeline"), alt.Tooltip("situacao:N", title="Situação"),
                                   alt.Tooltip("itens:Q", title="Issues"), alt.Tooltip("pontos:Q", title="SP", format=".0f")]))
        charts.mostrar(barras, "Issues por pipeline", "quantidade de issues · situação atual no quadro",
                       por_pipe, altura=charts.altura_categorias(por_pipe["pipeline"].nunique()))
        e, dd = st.columns(2)
        for alvo, campo, titulo in ((e, "epico", "Issues por épico"), (dd, "release", "Issues por release")):
            with alvo:
                dist = agile.distribuicao(d, campo)
                ordem = (dist.groupby(campo)["itens"].sum().sort_values(ascending=False).index.tolist())
                b = (alt.Chart(dist).mark_bar(stroke=theme.INK["surface"], strokeWidth=1)
                     .encode(y=alt.Y(f"{campo}:N", sort=ordem, title=None,
                                     axis=alt.Axis(labelLimit=260)),
                             x=alt.X("itens:Q", title="Issues"),
                             color=alt.Color("situacao:N", title="Situação", scale=COR_SIT,
                                             sort=SIT + [agile.NAO_CLASSIFICADO]),
                             tooltip=[alt.Tooltip(f"{campo}:N", title=titulo.split()[-1].capitalize()),
                                      alt.Tooltip("situacao:N", title="Situação"), alt.Tooltip("itens:Q", title="Issues")]))
                charts.mostrar(b, titulo, "quantidade de issues por situação", dist,
                               altura=charts.altura_categorias(dist[campo].nunique()))
        e, dd = st.columns(2)
        campos_extra = [("tipo", "Issues por tipo")]
        if (d["prioridade"] != "Sem prioridade").any():
            campos_extra.append(("prioridade", "Issues por prioridade"))
        for alvo, (campo, titulo) in zip((e, dd), campos_extra):
            with alvo:
                dist = agile.distribuicao(d, campo)
                b = (alt.Chart(dist).mark_bar(stroke=theme.INK["surface"], strokeWidth=1)
                     .encode(y=alt.Y(f"{campo}:N", sort="-x", title=None), x=alt.X("itens:Q", title="Issues"),
                             color=alt.Color("situacao:N", title="Situação", scale=COR_SIT,
                                             sort=SIT + [agile.NAO_CLASSIFICADO]),
                             tooltip=[alt.Tooltip(f"{campo}:N"), alt.Tooltip("situacao:N"), alt.Tooltip("itens:Q")]))
                charts.mostrar(b, titulo, "quantidade de issues por situação", dist,
                               altura=charts.altura_categorias(dist[campo].nunique()))
        if len(campos_extra) == 1:
            with dd:
                layout.indisponivel("Distribuição por prioridade indisponível",
                                    "o snapshot atual não traz a prioridade das issues.",
                                    "coletar o backlog completo (campo `pipelineIssue.priority`).")


def releases_e_epicos(ctx, f, snap, todas, d):
    layout.secao("Releases e épicos", "Quanto de cada entrega planejada já foi concluído?", ["ZENHUB"])
    rel = agile.progresso_releases(snap, filters.por_repo(todas, f["repos"]))
    if rel.empty:
        layout.indisponivel("Sem releases no Zenhub", "o workspace não tem Release Reports com issues.")
    else:
        rel = rel.assign(progresso=rel["progresso"] * 100)
        st.dataframe(rel, use_container_width=True, hide_index=True, column_config={
            "release": "Release", "estado": "Estado", "inicio": "Início", "fim": "Fim", "issues": "Issues",
            "concluidas": "Concluídas", "pontos": st.column_config.NumberColumn("SP", format="%.0f"),
            "pontos_concluidos": st.column_config.NumberColumn("SP concluídos", format="%.0f"),
            "progresso": st.column_config.ProgressColumn("Progresso", min_value=0, max_value=100, format="%.0f%%"),
            "issues_no_zenhub": st.column_config.NumberColumn("Issues segundo o Zenhub", format="%d")})
        st.caption("'Issues segundo o Zenhub' inclui pull requests e issues fora do snapshot; o progresso usa só as "
                   "issues presentes no snapshot, sem PRs.")
    ep = agile.progresso_epicos(filters.por_repo(todas, f["repos"]))
    if not ep.empty:
        ep = ep.assign(progresso=ep["progresso"] * 100)
        for col in ("pontos", "pontos_concluidos"):
            ep[col] = ep[col].map(lambda v: "—" if pd.isna(v) else num(v))
        if "url" in ep:
            ep["epico"] = [layout.link_celula(u, x) for x, u in zip(ep["epico"], ep["url"])]
            ep = ep.drop(columns="url")
        st.dataframe(ep, use_container_width=True, hide_index=True, column_config={
            "epico": layout.coluna_link("Épico", width="large", help="clique para abrir o épico"), "numero": "Nº", "repositorio": "Repositório",
            "situacao": "Situação", "filhas": "Filhas", "concluidas": "Concluídas", "em_andamento": "Em andamento",
            "pontos": "SP", "pontos_concluidos": "SP concluídos",
            "progresso": st.column_config.ProgressColumn("Progresso", min_value=0, max_value=100, format="%.0f%%")})
        st.caption("— = nenhuma filha pontuável com estimativa. Épico sem filhas aparece sem progresso (não é 0%). SP = só Features, Tasks e Bugs sem filhas "
                   "(a mesma regra da velocity: uma US com Tasks não soma junto com as Tasks). Aqui entram todas as "
                   "issues fechadas do épico, inclusive as da sprint em andamento; a velocity só soma as fechadas "
                   "dentro de sprints concluídas. Releases e épicos usam todas as issues (só o filtro de repositório vale aqui).")


def conferencia(ctx, f, snap, todas, d):
    layout.secao("Conferência dos story points", "Os SP fechados batem entre velocity, sprint atual e épicos?",
                 ["ZENHUB", "CALCULADO"])
    conc = agile.conciliacao_sp(filters.por_repo(todas, f["repos"]), ctx.zh_iniciadas)
    if conc["total"] is None:
        layout.indisponivel("Conferência indisponível", "não há issues no snapshot.")
    else:
        layout.alerta("good" if conc["fecha"] else "critical", agile.frase_conciliacao(conc))
        tab = pd.concat([conc["linhas"].drop(columns="curto"), conc["epicos"]], ignore_index=True)
        tab.insert(0, "visao", ["Por sprint"] * len(conc["linhas"]) + ["Por épico"] * len(conc["epicos"]))
        st.dataframe(tab, use_container_width=True, hide_index=True, column_config={
            "visao": "Visão", "parcela": st.column_config.TextColumn("Parcela", width="large"),
            "sp": st.column_config.NumberColumn("SP", format="%.0f"), "issues": "Issues pontuáveis"})
        if not conc["fora"].empty:
            fora = conc["fora"].copy()
            if "url" in fora:
                fora["title"] = [layout.link_celula(u, x) for x, u in zip(fora["title"], fora["url"])]
                fora = fora.drop(columns="url")
            st.dataframe(fora, use_container_width=True, hide_index=True, column_config={
                "title": layout.coluna_link("Issue", width="large")})
        st.caption("Calculado a cada carga (`agile.conciliacao_sp`): total = issues Feature/Task/Bug sem filhas "
                   "pontuáveis e fechadas. 'Itens concluídos' nos indicadores conta issues de todos os tipos, por "
                   "isso não é comparável com SP. Fechada entre o fim de uma sprint e o início da próxima conta na "
                   "próxima. Só o filtro de repositório vale aqui.")


def comparacao_zenhub(ctx, f, snap, todas, d):
    layout.secao("Comparação com o Zenhub", "Por que o concluído do painel difere do Zenhub?", ["ZENHUB", "CALCULADO"])
    comp, difs = vel.comparar_com_zenhub(snap, ctx.zh_iniciadas, ctx.zh_regras, ctx.agora_utc)
    if comp.empty:
        layout.indisponivel("Comparação indisponível", "nenhuma sprint iniciada no snapshot.")
    else:
        for frase, r in zip(vel.frase_comparacao(comp, difs), comp.itertuples()):
            layout.alerta("good" if r.reproduz else "critical", frase)
        st.dataframe(comp, use_container_width=True, hide_index=True, column_config={
            "sprint": "Sprint", "status": "Situação",
            "zenhub_api": st.column_config.NumberColumn("Zenhub (API)", format="%.0f"),
            "zenhub_reproduzido": st.column_config.NumberColumn("Zenhub reproduzido", format="%.0f"),
            "reproduz": st.column_config.CheckboxColumn("Bate?"),
            "painel": st.column_config.NumberColumn("Painel", format="%.0f"),
            "diferenca": st.column_config.NumberColumn("Painel − Zenhub", format="%+.0f")})
        if not difs.empty:
            dd = difs.drop(columns=["fechada_em"]).copy()
            dd["issue"] = [layout.link_celula(u, x.split("-")[-1]) for x, u in zip(dd["issue"], dd["url"])]
            dd["titulo"] = [layout.link_celula(u, x) for x, u in zip(dd["titulo"], dd["url"])]
            st.dataframe(dd.drop(columns="url"), use_container_width=True, hide_index=True, column_config={
                "sprint": "Sprint", "issue": layout.coluna_link("Issue"),
                "titulo": layout.coluna_link("Título", width="large"),
                "sp": st.column_config.NumberColumn("SP", format="%.0f"), "efeito": "No painel",
                "motivo": st.column_config.TextColumn("Motivo", width="large")})
        st.caption("'Zenhub (API)' é o `completedPoints` de cada sprint, só com estimativas reais. 'Zenhub reproduzido' "
                   "recalcula esse número a partir das issues do snapshot com a regra do Zenhub (issue ou PR na sprint, "
                   "fechada entre o início e o fim, com estimativa): se não bater, o painel avisa em vermelho. "
                   "O relatório Team Velocity com 'assumed estimates' soma estimativas presumidas para issues sem "
                   "estimativa, que o painel não usa: por isso ele não é comparável. Regras que diferem de propósito: "
                   "página Metodologia.")


def consistencia(ctx, f, snap, todas, d):
    alertas = agile.alertas_de_dados(filters.por_repo(todas, f["repos"]), ctx.zh_regras.tipos_pontuados)
    layout.secao("Consistência do cadastro no Zenhub", "Há issues cadastradas de um jeito que distorce os números?",
                 ["ZENHUB"])
    if alertas.empty:
        layout.alerta("good", "Nenhuma inconsistência de tipo ou estimativa encontrada.")
    else:
        graves = alertas[~alertas["problema"].str.startswith("sem estimativa")]
        for g in graves.itertuples():
            layout.alerta("warning", f"#{g.numero} {g.titulo} — {g.problema}", str(g.repositorio),
                          link=(f"#{g.numero} {g.titulo}", g.url))
        al = alertas.copy()
        al["titulo"] = [layout.link_celula(u, x) for x, u in zip(al["titulo"], al["url"])]
        st.dataframe(al.drop(columns="url"), use_container_width=True, hide_index=True, column_config={
            "numero": "Nº", "titulo": layout.coluna_link("Issue", width="large"), "repositorio": "Repositório",
            "tipo": "Tipo", "problema": st.column_config.TextColumn("O que corrigir", width="large")})
        st.caption("O painel não corrige o cadastro: o número só muda quando a issue for ajustada no Zenhub e a "
                   "próxima coleta rodar.")
