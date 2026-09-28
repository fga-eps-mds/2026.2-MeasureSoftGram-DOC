"""Visão Executiva — situação consolidada do projeto (todas as fontes)."""

from __future__ import annotations

import html

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.metrics import agile, resumo
from src.metrics import velocity as vel
from src.metrics.calculations import data_br, num, pct, release_atual

DIMENSOES = [("Qualidade", "Qualidade técnica", ["SONAR"]), ("Entrega", "Prazo e escopo", ["ZENHUB"]),
             ("Custo", "Custo", ["PLANILHA"]), ("Riscos", "Riscos e decisões", ["PLANILHA"]),
             ("Processo", "Integração contínua", ["GITHUB"])]


def _cartao_dimensao(titulo, fontes, itens: pd.DataFrame) -> None:
    s = theme.pior(list(itens["status"])) if not itens.empty else "unavailable"
    if not itens.empty and (itens["status"] == "unavailable").all():
        s = "unavailable"
    cor = theme.cor_status(s)
    linhas = "".join(
        f"<div style='margin-top:.35rem;font-size:.8rem;color:{theme.INK['secondary']}'>"
        f"<span style='color:{theme.cor_status(i.status)};font-weight:700'>{theme.ROTULO_STATUS[i.status]}</span> · "
        f"{html.escape(i.indicador)}: <b style='color:{theme.INK['primary']}'>"
        f"{html.escape(i.valor) if i.valor else 'indisponível'}</b></div>"
        for i in itens.itertuples())
    st.markdown(f"<div class='msg-status-geral' style='--kpi-cor:{cor}'><div class='rotulo'>{html.escape(titulo)} "
                f"{layout.etiquetas(fontes)}</div><div class='valor' style='color:{cor}'>{theme.ROTULO_STATUS[s]}</div>"
                f"{linhas}</div>", unsafe_allow_html=True)


def pagina():
    ctx, f = layout.estado()
    ind = resumo.indicadores(ctx, f)
    status, frase = resumo.situacao_geral(ind)
    rel_nome, entrega = release_atual(ctx.hoje)
    dias = (entrega - ctx.hoje).days
    alvo, feitas = resumo.release_em_foco(ctx, f["release"])

    layout.titulo_pagina("Visão Executiva", "Situação do projeto em uma tela: prazo, escopo, qualidade, custo e riscos, "
                         "com os pontos que pedem atenção.", ["SONAR", "ZENHUB", "PLANILHA"])

    # ── situação geral ──
    cor = theme.cor_status(status)
    e, d = st.columns([1.3, 2])
    with e:
        st.markdown(f"<div class='msg-status-geral' style='--kpi-cor:{cor}'><div class='rotulo'>Status geral do projeto"
                    f"</div><div class='valor' style='color:{cor}'>{theme.ROTULO_STATUS[status]}</div>"
                    f"<div style='font-size:.85rem;color:{theme.INK['secondary']}'>{html.escape(frase)}</div>"
                    f"<div style='font-size:.78rem;color:{theme.INK['muted']};margin-top:.4rem'>Metas da "
                    f"{f['release_metas']} · status = pior indicador com meta</div></div>", unsafe_allow_html=True)
    with d:
        c = st.columns(3)
        with c[0]:
            kpi("Release em andamento", rel_nome, "ZENHUB",
                nota=f"entrega {data_br(entrega)} · " + ("hoje" if dias == 0 else f"faltam {dias} dia(s)" if dias > 0
                                                         else f"entregue há {-dias} dia(s)"))
        cal = ctx.calendario
        atual = cal[(cal["inicio"] <= ctx.hoje) & (cal["fim"] >= ctx.hoje)] if not cal.empty else cal
        with c[1]:
            if atual is None or atual.empty:
                kpi("Sprint atual", None, "ZENHUB", nota="nenhuma sprint do Zenhub cobre hoje")
            else:
                a = atual.iloc[0]
                kpi("Sprint atual", a["sprint"], "ZENHUB", nota=f"{data_br(a['inicio'])} a {data_br(a['fim'])}")
        with c[2]:
            if feitas.empty:
                kpi("Progresso da release", None, "ZENHUB", nota="sem sprints iniciadas")
            else:
                u = feitas.iloc[-1]
                kpi(f"Progresso da {alvo}", pct(u["APC"]), "ZENHUB",
                    status=next(iter(ind.loc[ind["indicador"] == f"Progresso da {alvo}", "status"]), None),
                    nota=f"{num(u['RPC'])} de {num(u['PRP'])} SP · planejado {pct(u['PPC'])}")

    # ── KPIs ──
    layout.secao("Principais indicadores", "Como estamos em entrega, qualidade, custo e risco?")
    iss = filters.por_repo(ctx.zh_issues, f["repos"])
    cont = iss["situacao"].value_counts() if iss is not None and not iss.empty else pd.Series(dtype=int)
    media = vel.calculate_average_velocity(ctx.zh_iniciadas, ctx.zh_regras.min_sprints_media)

    def ind_(nome_parcial):
        m = ind[ind["indicador"].str.startswith(nome_parcial)]
        return m.iloc[0] if not m.empty else None

    k = st.columns(4)
    with k[0]:
        kpi("Itens concluídos (fechados)", num(cont.get(agile.CONCLUIDO, 0)) if not cont.empty else None, "ZENHUB",
            nota=f"de {num(len(iss))} itens" + ("" if ctx.zh_backlog_completo else " (só os que passaram por sprints)")
            if not cont.empty else "sem snapshot do Zenhub")
    with k[1]:
        kpi("Itens em andamento", num(cont.get(agile.ANDAMENTO, 0)) if not cont.empty else None, "ZENHUB",
            nota="abertas em In Progress, Review/QA, DoD ou Done")
    with k[2]:
        kpi("Itens planejados", num(cont.get(agile.PLANEJADO, 0)) if not cont.empty else None, "ZENHUB",
            nota="Backlogs e DoR")
    with k[3]:
        kpi("Velocity média", f"{num(media['valor'])} SP" if media["valor"] is not None else None, "ZENHUB",
            nota=f"{media['n']} sprints concluídas" if media["valor"] is not None
            else f"Indisponível: {media['motivo']}.")
    k = st.columns(4)
    for col, (prefixo, rot, fonte) in zip(k, [("SPI", "SPI (prazo)", "CALCULADO"), ("CPI", "CPI (custo)", "CALCULADO"),
                                              ("Cobertura", "Cobertura média", "SONAR"),
                                              ("Riscos com", "Riscos elevados", "PLANILHA")]):
        with col:
            i = ind_(prefixo)
            if i is None or i["valor"] is None:
                kpi(rot, None, fonte, nota=("Indisponível: " + i["leitura"] + ".") if i is not None else None)
            else:
                kpi(rot, i["valor"], fonte, status=i["status"], nota=i["leitura"])

    # ── situação por dimensão ──
    layout.secao("Situação por dimensão", "Qual área concentra os problemas?")
    cols = st.columns(len(DIMENSOES))
    for col, (dim, titulo, fontes) in zip(cols, DIMENSOES):
        with col:
            _cartao_dimensao(titulo, fontes, ind[ind["dimensao"] == dim])

    # ── evolução das entregas ──
    layout.secao("Evolução das entregas", "Estamos entregando conforme o planejado?", ["ZENHUB", "CALCULADO"])
    if feitas.empty:
        layout.indisponivel("Sem dados de entrega", "nenhuma sprint iniciada no Zenhub para a release.")
    else:
        prog = feitas.melt(id_vars=["sprint"], value_vars=["PPC", "APC"], var_name="serie", value_name="valor")
        prog["nome"] = prog["serie"].map({"PPC": "Planejado (% do prazo)", "APC": "Realizado (% do escopo)"})
        dom = ["Planejado (% do prazo)", "Realizado (% do escopo)"]
        g = (alt.Chart(prog).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
             .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                     y=alt.Y("valor:Q", title="% da release", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                     color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[theme.SERIES[2],
                                                                                           theme.SERIES[0]])),
                     strokeDash=alt.StrokeDash("nome:N", legend=None, scale=alt.Scale(domain=dom, range=[[6, 4], [1, 0]])),
                     tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Série"),
                              alt.Tooltip("valor:Q", title="%", format=".0%")]))
        e, d = st.columns([1.2, 1])
        with e:
            charts.mostrar(g, f"Planejado × realizado — {alvo}", "% da release por sprint iniciada (Agile EVM)",
                           feitas[["sprint", "status", "PPC", "APC", "PRP", "RPC"]], altura=230)
        with d:
            if cal is None or cal.empty:
                st.caption("Sem calendário de sprints.")
            else:
                c2 = cal.assign(fim_barra=cal["fim"] + pd.Timedelta(days=1),
                                encerrada=cal["fim"] < ctx.hoje, release=cal["release"].fillna("sem release"))
                barras = (alt.Chart(c2).mark_bar(height=18, cornerRadius=3, stroke=theme.INK["surface"], strokeWidth=2)
                          .encode(x=alt.X("inicio:T", title=None, axis=alt.Axis(format="%d/%m")), x2="fim_barra:T",
                                  y=alt.Y("release:N", title=None, sort=list(dict.fromkeys(c2["release"]))),
                                  color=alt.condition("datum.encerrada", alt.value(theme.NEUTRO), alt.value(theme.SERIES[0])),
                                  tooltip=[alt.Tooltip("sprint:N", title="Sprint"), alt.Tooltip("release:N"),
                                           alt.Tooltip("status:N", title="Situação"),
                                           alt.Tooltip("inicio:T", title="Início", format="%d/%m"),
                                           alt.Tooltip("fim:T", title="Fim", format="%d/%m")]))
                rot = (alt.Chart(c2.assign(meio=c2["inicio"] + (c2["fim_barra"] - c2["inicio"]) / 2))
                       .mark_text(fontSize=10, color="#FFFFFF", fontWeight=600)
                       .encode(x="meio:T", y=alt.Y("release:N", sort=list(dict.fromkeys(c2["release"]))),
                               text="sprint:N"))
                hoje = alt.Chart(pd.DataFrame({"d": [ctx.hoje]})).mark_rule(color=theme.STATUS["critical"],
                                                                           strokeWidth=1.5).encode(x="d:T")
                charts.mostrar(barras + rot + hoje, "Calendário de sprints", "sprints do Zenhub por release · cinza = "
                               "encerrada · linha vermelha = hoje", cal, altura=120)

    # ── pontos de atenção ──
    layout.secao("Pontos de atenção", "Quais indicadores precisam de ação?")
    at = resumo.pontos_de_atencao(ind)
    if at.empty:
        layout.alerta("good", "Nenhum indicador crítico, em atenção ou sem dado.")
    else:
        for i in at.itertuples():
            valor = f": {i.valor}" if i.valor else ""
            layout.alerta(i.status, f"{i.indicador}{valor} — {i.leitura}", f"{i.fonte} · detalhe em {i.onde}")
    layout.tabela(ind.assign(status=ind["status"].map(theme.ROTULO_STATUS)).rename(columns={
        "dimensao": "dimensão", "onde": "página"}), "Ver todos os indicadores desta visão")
