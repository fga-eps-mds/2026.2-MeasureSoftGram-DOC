"""Gestão ágil — fonte ZENHUB (backlog, sprints, velocity, throughput, épicos e releases)."""

from __future__ import annotations

import sys

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.data.sonar import nome_curto
from src.metrics import agile
from src.metrics import velocity as vel
from src.metrics.calculations import data_br, num, pct

SIT = [agile.CONCLUIDO, agile.ANDAMENTO, agile.PLANEJADO]
COR_SIT = alt.Scale(domain=SIT + [agile.NAO_CLASSIFICADO],
                    range=[theme.SERIES[0], theme.SERIES[1], theme.SERIES[2], theme.NEUTRO_CLARO])


def _sp(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{num(v)} SP"


def _botao_atualizar(ctx) -> None:
    """Coleta nova pela API (só rodando localmente com a chave no .env)."""
    if sys.platform == "emscripten":
        st.caption("Na versão publicada os dados do Zenhub são atualizados pelo workflow `coleta-dados.yml`.")
        return
    from src.zenhub.client import carregar_env, chave_do_ambiente
    from src.data.contexto import RAIZ
    carregar_env(RAIZ / ".env")
    pode = bool(chave_do_ambiente())
    if st.button("Atualizar dados do Zenhub", disabled=not pode, key="zh_atualizar",
                 help="Consulta a API do Zenhub agora e grava um snapshot novo." if pode
                 else "Defina ZENHUB_API_KEY em Analytics/.env."):
        from scripts.coleta_velocity import executar
        from src.zenhub.client import ZenhubError
        try:
            with st.spinner("Consultando o Zenhub (alguns minutos por causa do limite de complexidade)..."):
                executar(log=lambda _m: None)
        except ZenhubError as e:
            st.error(f"Não foi possível atualizar: {e}. O painel continua com o último snapshot.")
            return
        st.cache_data.clear()
        st.rerun()


def _filtros(ctx, f, df: pd.DataFrame) -> pd.DataFrame:
    """Filtros da página. Prioridade e responsável só aparecem se o snapshot tiver esses campos."""
    d = filters.por_repo(df, f["repos"])
    tem_prioridade = (d["prioridade"] != "Sem prioridade").any()
    tem_resp = (d["responsavel"] != "Sem responsável").any()
    campos = [("sprint", "Sprint"), ("release", "Release"), ("epico", "Épico"), ("situacao", "Situação"),
              ("tipo", "Tipo")]
    if tem_prioridade:
        campos.append(("prioridade", "Prioridade"))
    if tem_resp:
        campos.append(("responsavel", "Responsável"))
    cols = st.columns(len(campos))
    for col, (campo, rotulo) in zip(cols, campos):
        valores = sorted(d[campo].dropna().unique(), key=lambda v: (str(v).startswith("Sem "), str(v)))
        sel = col.multiselect(rotulo, valores, key=f"zh_f_{campo}", placeholder="Todos")
        if sel:
            d = d[d[campo].isin(sel)]
    if not tem_prioridade or not tem_resp:
        faltam = [n for n, t in (("prioridade", tem_prioridade), ("responsável", tem_resp)) if not t]
        st.caption(f"Filtros de {' e '.join(faltam)} não exibidos: o snapshot atual não tem esse campo "
                   "(ele vem da coleta do backlog completo).")
    return d


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Gestão ágil", "Backlog, sprints, velocity e entregas a partir do quadro do Zenhub.",
                         ["ZENHUB"])
    snap = ctx.zh_snap
    topo_e, topo_d = st.columns([3, 1])
    with topo_d:
        _botao_atualizar(ctx)
    with topo_e:
        if snap:
            fonte = ctx.fonte("ZENHUB")[0]
            st.caption(f"Snapshot `{ctx.zh_arquivo}` · coletado em **{data_br(fonte.ultima_atualizacao, True)}** · "
                       f"{snap.get('requisicoes', '?')} requisições · feito = issue fechada "
                       f"(em qualquer pipeline) · pontuam: {', '.join(sorted(ctx.zh_regras.tipos_pontuados))}.")
    layout.metodologia([
        ("Planejado / Em andamento / Concluído", "ZENHUB — pipeline da issue",
         "issue fechada = Concluído (só ela conta pontos); aberta = pela pipeline (mapa em `src/metrics/agile.py`; "
         "aberta no Done = Em andamento; pipeline fora do mapa = Não classificado)"),
        ("Story Points planejados", "ZENHUB — `Sprint.scopeChange`", "issues pontuáveis na sprint ao fim da janela de "
         f"planning ({ctx.zh_regras.janela_planning.total_seconds() / 3600:.0f} h), com a estimativa do momento da "
         "entrada; issues que já estavam na sprint no início (sem evento no histórico, que só registra mudanças "
         "depois do início) entram com a estimativa atual; congelado em `linhas-de-base.json`"),
        ("Velocity", "ZENHUB", "Story Points de issues pontuáveis fechadas dentro da sprint (issue sem estimativa "
         "conta 0 SP e aparece nas observações)"),
        ("Velocity média", "cálculo", f"média das sprints concluídas (≥ {ctx.zh_regras.min_sprints_media}); "
         "a sprint em andamento fica de fora"),
        ("Média móvel", "cálculo", "média das 3 últimas sprints concluídas; só existe a partir da 3ª"),
        ("Taxa de conclusão", "cálculo", "SP concluídos ÷ SP planejados; indisponível quando o planejado é 0"),
        ("Throughput", "ZENHUB", "issues pontuáveis concluídas por semana (segunda a domingo, horário de Brasília)"),
        ("Progresso do épico / release", "ZENHUB", "issues concluídas ÷ issues (filhas do épico ou ligadas à release)"),
    ])
    if not snap:
        layout.indisponivel("Sem dados do Zenhub", "ainda não há snapshot em `data/zenhub/velocity/`.",
                            "rodar `python scripts/coleta_velocity.py` com `ZENHUB_API_KEY` no `Analytics/.env`.")
        return
    for aviso in snap.get("avisos") or []:
        st.caption(f"Aviso da coleta: {aviso}")
    if not ctx.zh_backlog_completo:
        layout.indisponivel(
            "Backlog completo não coletado",
            "este snapshot só tem as issues que passaram por alguma sprint; itens que estão apenas no Product "
            "Backlog, Icebox ou New Issues não aparecem nas contagens abaixo.",
            "rodar a coleta novamente (`scripts/coleta_velocity.py`): a versão atual também percorre todos os "
            "pipelines do quadro.")

    todas = ctx.zh_issues
    d = _filtros(ctx, f, todas)

    # ── KPIs ──
    layout.secao("Indicadores", "Quanto foi planejado, quanto está em andamento e quanto foi entregue?", ["ZENHUB"])
    cont = d["situacao"].value_counts()
    total = len(d)
    sprints = filters.por_periodo(ctx.zh_iniciadas, "start_date", f["periodo"], "end_date")
    media = vel.calculate_average_velocity(sprints, ctx.zh_regras.min_sprints_media)
    concl = sprints[sprints["status"] == vel.STATUS_CONCLUIDA] if not sprints.empty else sprints
    planejado = concl["planned_story_points"].sum(min_count=1) if not concl.empty else None
    concluido = concl["completed_story_points"].sum(min_count=1) if not concl.empty else None
    taxa = vel.calculate_completion_rate(planejado, concluido)
    layout_kpis = st.columns(4)
    with layout_kpis[0]:
        kpi("Itens no filtro", num(total), "ZENHUB",
            nota=f"{int((d['pontos'].isna() & d['issue_type'].isin(ctx.zh_regras.tipos_pontuados)).sum())} "
                 "pontuáveis sem estimativa")
    with layout_kpis[1]:
        kpi("Planejados", num(cont.get(agile.PLANEJADO, 0)), "ZENHUB", nota="New Issues, Backlogs, DoR")
    with layout_kpis[2]:
        kpi("Em andamento", num(cont.get(agile.ANDAMENTO, 0)), "ZENHUB", nota="In Progress, Review/QA, DoD e Done ainda abertas")
    with layout_kpis[3]:
        kpi("Concluídos", num(cont.get(agile.CONCLUIDO, 0)), "ZENHUB",
            nota=f"{pct(cont.get(agile.CONCLUIDO, 0) / total) if total else '—'} dos itens do filtro")
    k2 = st.columns(4)
    with k2[0]:
        if media["valor"] is None:
            kpi("Velocity média", None, "ZENHUB", nota=f"Indisponível: {media['motivo']}.")
        else:
            kpi("Velocity média", _sp(media["valor"]), "ZENHUB", nota=f"{media['n']} sprints concluídas")
    with k2[1]:
        kpi("SP concluídos (sprints concluídas)", _sp(concluido) if concluido is not None else None, "ZENHUB",
            nota="nenhuma sprint concluída no período" if concluido is None else f"{len(concl)} sprint(s)")
    with k2[2]:
        if taxa is None:
            kpi("Taxa de conclusão", None, "ZENHUB",
                nota="Indisponível: o planejado das sprints concluídas é 0 SP ou não existe (issues sem estimativa "
                     "na planning).")
        else:
            kpi("Taxa de conclusão", f"{num(taxa)}%", "ZENHUB",
                status="good" if taxa >= 80 else ("warning" if taxa >= 60 else "critical"),
                nota="SP concluídos ÷ SP planejados · meta ≥ 80%")
    tp = agile.throughput_semanal(filters.por_periodo(d, "concluida_em", f["periodo"]), ctx.zh_regras.tipos_pontuados)
    with k2[3]:
        if tp.empty:
            kpi("Throughput médio", None, "ZENHUB", nota="Indisponível: nenhuma issue pontuável concluída no período.")
        else:
            kpi("Throughput médio", f"{num(tp['itens'].mean(), 1)} itens/sem.", "ZENHUB",
                nota=f"{len(tp)} semana(s) com entrega")

    # ── backlog ──
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

    # ── velocity ──
    layout.secao("Velocity por sprint", "Quanto o time planeja e quanto entrega a cada sprint?", ["ZENHUB"])
    if sprints.empty:
        layout.indisponivel("Sem sprints no período", "nenhuma sprint iniciada no período selecionado.")
    else:
        v = sprints.sort_values("start_date").copy()
        v["eixo"] = v["sprint_label"] + v["status"].map({vel.STATUS_ANDAMENTO: " (parcial)",
                                                          vel.STATUS_CANCELADA: " (cancelada)"}).fillna("")
        concl_v = v[v["status"] == vel.STATUS_CONCLUIDA]
        v["media_movel"] = agile.media_movel(concl_v["velocity"]).reindex(v.index)
        longo = pd.concat(ignore_index=True, objs=[v.assign(serie="Planejado", pontos=v["planned_story_points"]),
                           v.assign(serie="Concluído (velocity)", pontos=v["completed_story_points"])])
        longo = longo.dropna(subset=["pontos"])
        longo["parcial"] = longo["status"] != vel.STATUS_CONCLUIDA
        series = ["Planejado", "Concluído (velocity)"]
        ordem = list(v["eixo"])
        barras = (alt.Chart(longo).mark_bar(size=18, cornerRadiusTopLeft=3, cornerRadiusTopRight=3,
                                            stroke=theme.INK["surface"], strokeWidth=2)
                  .encode(x=alt.X("eixo:N", sort=ordem, title="Sprint", axis=alt.Axis(labelAngle=0)),
                          xOffset=alt.XOffset("serie:N", sort=series),
                          y=alt.Y("pontos:Q", title="Story Points"),
                          color=alt.Color("serie:N", title=None, sort=series,
                                          scale=alt.Scale(domain=series, range=[theme.SERIES[2], theme.SERIES[0]])),
                          opacity=alt.condition("datum.parcial", alt.value(0.45), alt.value(1)),
                          tooltip=[alt.Tooltip("sprint_name:N", title="Sprint"), alt.Tooltip("status:N", title="Situação"),
                                   alt.Tooltip("serie:N", title="Série"), alt.Tooltip("pontos:Q", title="SP", format=".0f")]))
        rot = barras.mark_text(dy=-7, fontSize=11).encode(text=alt.Text("pontos:Q", format=".0f"),
                                                          color=alt.value(theme.INK["secondary"]),
                                                          opacity=alt.value(1))
        camadas = barras + rot
        mm = v.dropna(subset=["media_movel"])
        if not mm.empty:
            camadas = camadas + (alt.Chart(mm).mark_line(color=theme.SERIES[1], strokeDash=[4, 3], strokeWidth=2,
                                                         point=alt.OverlayMarkDef(size=50, color=theme.SERIES[1]))
                                 .encode(x=alt.X("eixo:N", sort=ordem), y="media_movel:Q",
                                         tooltip=[alt.Tooltip("eixo:N", title="Sprint"),
                                                  alt.Tooltip("media_movel:Q", title="Média móvel (3)", format=".1f")]))
        if media["valor"] is not None:
            camadas = camadas + charts.regra_horizontal(media["valor"], f"velocity média {num(media['valor'])} SP",
                                                        theme.INK["primary"])
        notas = ["Barras claras = sprint em andamento (parcial) ou cancelada, fora da média."]
        notas.append("Média móvel (3 sprints) tracejada." if not mm.empty else
                     "Média móvel não exibida: exige 3 sprints concluídas.")
        if media["valor"] is None:
            notas.append(f"Velocity média não exibida: {media['motivo']}.")
        if (v["planned_story_points"].fillna(0) == 0).any():
            notas.append("Planejado = 0 SP significa que as issues da sprint não tinham estimativa ao fim da planning "
                         "(o painel não estima pontos).")
        tabela_v = v[["sprint_label", "sprint_name", "status", "release_name", "planned_story_points",
                      "completed_story_points", "completion_rate", "planned_issues", "completed_issues",
                      "completed_unplanned_story_points", "baseline_source", "notes"]].rename(columns={
            "sprint_label": "sprint", "sprint_name": "nome", "status": "situação", "release_name": "release",
            "planned_story_points": "SP planejados", "completed_story_points": "SP concluídos",
            "completion_rate": "taxa de conclusão (%)", "planned_issues": "issues planejadas",
            "completed_issues": "issues concluídas", "completed_unplanned_story_points": "SP fora do plano",
            "baseline_source": "linha de base", "notes": "observações"})
        charts.mostrar(camadas, "Story Points planejados × concluídos por sprint",
                       f"Story Points · sprints de {data_br(f['periodo'][0])} a {data_br(f['periodo'][1])}",
                       tabela_v, nota=" ".join(notas), altura=320)

    # ── throughput e evolução ──
    layout.secao("Evolução das entregas", "O time está entregando de forma contínua?", ["ZENHUB"])
    e, dd = st.columns(2)
    with e:
        if tp.empty:
            layout.indisponivel("Throughput indisponível", "nenhuma issue pontuável concluída no período.")
        else:
            b = (alt.Chart(tp).mark_bar(size=22, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=theme.SERIES[0])
                 .encode(x=alt.X("semana:T", title="Semana (início)", axis=alt.Axis(format="%d/%m")),
                         y=alt.Y("itens:Q", title="Issues concluídas"),
                         tooltip=[alt.Tooltip("semana:T", title="Semana de", format="%d/%m/%Y"),
                                  alt.Tooltip("itens:Q", title="Issues"), alt.Tooltip("pontos:Q", title="SP", format=".0f"),
                                  alt.Tooltip("sem_estimativa:Q", title="Sem estimativa")]))
            charts.mostrar(b, "Throughput semanal", "issues pontuáveis concluídas por semana", tp, altura=240)
    with dd:
        c = d[d["concluida_em"].notna()].sort_values("concluida_em")
        c = filters.por_periodo(c, "concluida_em", f["periodo"])
        if c.empty:
            layout.indisponivel("Evolução acumulada indisponível", "nenhuma issue concluída no período.")
        else:
            c = c.assign(dia=c["concluida_em"].dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize())
            acum = c.groupby("dia").size().cumsum().reset_index(name="acumulado")
            area = (alt.Chart(acum).mark_area(color=theme.SERIES[0], opacity=0.18, line={"color": theme.SERIES[0]},
                                              interpolate="step-after")
                    .encode(x=alt.X("dia:T", title="Data", axis=alt.Axis(format="%d/%m")),
                            y=alt.Y("acumulado:Q", title="Issues concluídas (acumulado)"),
                            tooltip=[alt.Tooltip("dia:T", title="Data", format="%d/%m/%Y"),
                                     alt.Tooltip("acumulado:Q", title="Acumulado")]))
            charts.mostrar(area + charts.marcos_release(acum["dia"].min(), acum["dia"].max()),
                           "Entregas acumuladas", "issues concluídas (todas as do filtro) · acumulado no período",
                           acum, altura=240)

    # ── releases e épicos ──
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
        st.dataframe(ep, use_container_width=True, hide_index=True, column_config={
            "epico": st.column_config.TextColumn("Épico", width="large"), "numero": "Nº", "repositorio": "Repositório",
            "situacao": "Situação", "filhas": "Filhas", "concluidas": "Concluídas", "em_andamento": "Em andamento",
            "pontos": st.column_config.NumberColumn("SP", format="%.0f"),
            "pontos_concluidos": st.column_config.NumberColumn("SP concluídos", format="%.0f"),
            "progresso": st.column_config.ProgressColumn("Progresso", min_value=0, max_value=100, format="%.0f%%")})
        st.caption("Épico sem filhas aparece sem progresso (não é 0%). SP = só Features, Tasks e Bugs sem filhas "
                   "(a mesma regra da velocity: uma US com Tasks não soma junto com as Tasks). Aqui entram todas as "
                   "issues fechadas do épico, inclusive as da sprint em andamento; a velocity só soma as fechadas "
                   "dentro de sprints concluídas. Releases e épicos usam todas as issues (só o filtro de repositório vale aqui).")

    # ── qualidade do cadastro no Zenhub ──
    alertas = agile.alertas_de_dados(filters.por_repo(todas, f["repos"]), ctx.zh_regras.tipos_pontuados)
    layout.secao("Consistência do cadastro no Zenhub", "Há issues cadastradas de um jeito que distorce os números?",
                 ["ZENHUB"])
    if alertas.empty:
        layout.alerta("good", "Nenhuma inconsistência de tipo ou estimativa encontrada.")
    else:
        graves = alertas[~alertas["problema"].str.startswith("sem estimativa")]
        for g in graves.itertuples():
            layout.alerta("warning", f"#{g.numero} {g.titulo} — {g.problema}", str(g.repositorio))
        st.dataframe(alertas, use_container_width=True, hide_index=True, column_config={
            "numero": "Nº", "titulo": st.column_config.TextColumn("Issue", width="large"), "repositorio": "Repositório",
            "tipo": "Tipo", "problema": st.column_config.TextColumn("O que corrigir", width="large"),
            "url": st.column_config.LinkColumn("Link", display_text="abrir")})
        st.caption("O painel não corrige o cadastro: o número só muda quando a issue for ajustada no Zenhub e a "
                   "próxima coleta rodar.")

    with st.expander(f"Ver as {len(d)} issues do filtro"):
        cols = {"number": "Nº", "title": "Título", "repositorio": "Repositório", "tipo": "Tipo", "pipeline": "Pipeline",
                "situacao": "Situação", "pontos": "SP", "sprint": "Sprint", "epico": "Épico", "release": "Release",
                "prioridade": "Prioridade", "responsavel": "Responsável", "url": "Link"}
        t = d[[c for c in cols if c in d]].rename(columns=cols)
        t["Repositório"] = t["Repositório"].map(nome_curto)
        st.dataframe(t, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir"),
                                    "SP": st.column_config.NumberColumn(format="%.0f")})
