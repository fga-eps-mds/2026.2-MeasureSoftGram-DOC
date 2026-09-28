"""Gestão complementar — fonte PLANILHA (custos, riscos e decisões).

Só entra aqui o que nem o Sonar nem o Zenhub têm.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.data import planilha as pl
from src.metrics.calculations import brl, data_br, num, vazio
from src.metrics import resumo

NIVEIS = ["Elevado", "Médio", "Baixo"]
COR_NIVEL = alt.Scale(domain=NIVEIS, range=[theme.RISCO["Elevado"], theme.RISCO["Médio"], theme.RISCO["Baixo"]])


def _nivel(exposicao) -> str | None:
    if vazio(exposicao):
        return None
    return "Elevado" if exposicao >= 15 else ("Médio" if exposicao >= 6 else "Baixo")


def _origem(ctx, chave):
    return ctx.origem_planilha.get(chave, "não lida").replace("**", "")


# ───────────────────────── custos ─────────────────────────

def _custos(ctx, f):
    layout.metodologia([
        ("Custo semanal de um integrante", "PLANILHA — aba Custos", "custo de cursar EPS por semana + energia + "
         "internet + depreciação do notebook"),
        ("Custo planejado da semana", "PLANILHA — aba Planejamento", "integrantes ativos na semana × custo semanal "
         "de um integrante + infraestrutura"),
        ("Orçamento (BAC)", "PLANILHA", "soma do custo planejado das semanas"),
        ("Custo realizado", "PLANILHA — aba Horas × custo/hora da aba Custos", "horas registradas × custo por hora; "
         "semana/sprint sem horas registradas = custo realizado indisponível (não é zero nem o planejado)"),
        ("Custo por categoria", "PLANILHA", "componente semanal × integrantes-semana planejados"),
        ("Variação", "cálculo", "custo realizado − custo planejado das sprints com horas registradas"),
    ], "Metodologia — custos")
    st.caption(f"Fontes: {_origem(ctx, 'custos')} · {_origem(ctx, 'planejamento')} · {_origem(ctx, 'horas')}.")
    c = ctx.custo
    if not c:
        layout.indisponivel("Aba Custos não encontrada", _origem(ctx, "custos"),
                            "publicar a aba Custos em CSV e colar o link em `config.py` (chave `custos`).")
        return
    plano = ctx.plano.dropna(subset=["custo"]) if not ctx.plano.empty else ctx.plano
    plano_p = filters.por_periodo(plano, "semana", f["periodo"]) if not plano.empty else plano
    ate_hoje = plano[plano["semana"] <= ctx.hoje] if not plano.empty else plano
    horas = ctx.horas.dropna(subset=["horas"]) if not ctx.horas.empty and "horas" in ctx.horas else pd.DataFrame()
    custo_hora = c.get("custo_hora")
    realizado = float(horas["horas"].sum() * custo_hora) if not horas.empty and custo_hora else None

    layout.secao("Orçamento e custo", "Quanto foi orçado, quanto já deveria ter sido gasto e quanto foi gasto?",
                 ["PLANILHA"])
    k = st.columns(4)
    with k[0]:
        kpi("Orçamento do semestre", brl(plano["custo"].sum()) if not plano.empty else None, "PLANILHA",
            nota=f"{len(plano)} semanas planejadas" if not plano.empty else "aba Planejamento vazia")
    with k[1]:
        kpi("Custo planejado no período", brl(plano_p["custo"].sum()) if not plano_p.empty else None, "PLANILHA",
            nota=f"{data_br(f['periodo'][0])} a {data_br(f['periodo'][1])}")
    with k[2]:
        kpi("Custo planejado até hoje", brl(ate_hoje["custo"].sum()) if not ate_hoje.empty else None, "PLANILHA",
            nota=f"semanas iniciadas até {data_br(ctx.hoje)}")
    with k[3]:
        kpi("Custo realizado", brl(realizado) if realizado is not None else None, "PLANILHA",
            nota="horas registradas × custo/hora" if realizado is not None else
            "Indisponível: nenhuma hora registrada na aba Horas (o custo real não é estimado).")
    k = st.columns(4)
    with k[0]:
        kpi("Custo por hora", brl(custo_hora), "PLANILHA", nota=f"{num(c.get('horas_semana_total'))} h por semana")
    with k[1]:
        kpi("Custo semanal de um integrante", brl(c.get("custo_membro_semana")), "PLANILHA")
    with k[2]:
        kpi("Integrantes", num(c.get("integrantes")), "PLANILHA")
    with k[3]:
        if realizado is None:
            kpi("Variação planejado × realizado", None, "CALCULADO",
                nota="Indisponível: sem custo realizado para comparar.")
        else:
            sprints_com = set(horas["sprint"].dropna())
            base = plano[plano["sprint"].isin(sprints_com)]["custo"].sum() if "sprint" in plano else None
            dif = realizado - base if base else None
            kpi("Variação planejado × realizado", brl(dif) if dif is not None else None, "CALCULADO",
                status=None if dif is None else ("good" if dif <= 0 else "critical"),
                nota=f"realizado − planejado das sprints {', '.join(str(int(s)) for s in sorted(sprints_com))}")

    if not plano.empty:
        layout.secao("Custo por período", "Como o custo planejado se distribui no semestre?", ["PLANILHA"])
        e, d = st.columns(2)
        with e:
            b = (alt.Chart(plano_p).mark_bar(size=16, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=theme.SERIES[0])
                 .encode(x=alt.X("semana:T", title="Semana", axis=alt.Axis(format="%d/%m")),
                         y=alt.Y("custo:Q", title="R$"),
                         tooltip=[alt.Tooltip("semana:T", title="Semana de", format="%d/%m/%Y"),
                                  alt.Tooltip("release:N", title="Release"), alt.Tooltip("sprint:Q", title="Sprint"),
                                  alt.Tooltip("integrantes:Q", title="Integrantes"),
                                  alt.Tooltip("custo:Q", title="R$", format=",.2f")]))
            charts.mostrar(b, "Custo planejado por semana", "R$ por semana · aba Planejamento", plano_p, altura=240)
        with d:
            ac = plano.sort_values("semana").assign(planejado=lambda x: x["custo"].cumsum())
            series = [ac[["semana", "planejado"]].rename(columns={"planejado": "valor"}).assign(serie="Planejado")]
            if realizado is not None and "sprint" in plano:
                por_sprint = horas.groupby("sprint")["horas"].sum() * custo_hora
                fim_sprint = plano.groupby("sprint")["semana"].max()
                r = pd.DataFrame({"semana": fim_sprint.reindex(por_sprint.index).values,
                                  "valor": por_sprint.cumsum().values}).dropna()
                series.append(r.assign(serie="Realizado"))
            longo = pd.concat(series, ignore_index=True)
            dom = list(dict.fromkeys(longo["serie"]))
            g = (alt.Chart(longo).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40, filled=True))
                 .encode(x=alt.X("semana:T", title="Semana", axis=alt.Axis(format="%d/%m")),
                         y=alt.Y("valor:Q", title="R$ acumulado"),
                         color=alt.Color("serie:N", title=None, scale=alt.Scale(domain=dom, range=[theme.SERIES[2],
                                                                                              theme.SERIES[0]][:len(dom)])),
                         strokeDash=alt.StrokeDash("serie:N", legend=None,
                                                   scale=alt.Scale(domain=dom, range=[[6, 4], [1, 0]][:len(dom)])),
                         tooltip=[alt.Tooltip("semana:T", format="%d/%m/%Y"), alt.Tooltip("serie:N", title="Série"),
                                  alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
            hoje = pd.DataFrame({"d": [ctx.hoje]})
            regra = alt.Chart(hoje).mark_rule(color=theme.INK["secondary"], strokeWidth=1).encode(x="d:T")
            charts.mostrar(g + regra, "Custo acumulado planejado × realizado", "R$ acumulado no semestre · linha vertical = hoje",
                           longo, nota=None if realizado is not None else
                           "Realizado não aparece: nenhuma hora registrada na aba Horas.", altura=240)

        layout.secao("Custo por categoria e por recurso", "Do que é feito o custo e como ele se divide no time?",
                     ["PLANILHA"])
        e, d = st.columns(2)
        pessoas_semana = plano["integrantes"].sum()
        with e:
            cat = pd.DataFrame([{"categoria": rot, "valor": c.get(k) * pessoas_semana}
                                for k, rot in pl.COMPONENTES_CUSTO.items() if not vazio(c.get(k))])
            if c.get("infra_semana") is not None:
                cat = pd.concat([cat, pd.DataFrame([{"categoria": "Infraestrutura (deploy, domínio)",
                                                     "valor": c.get("infra_semana") * len(plano)}])], ignore_index=True)
            cat["texto"] = cat["valor"].map(brl)
            b = (alt.Chart(cat).mark_bar(cornerRadiusEnd=3, color=theme.SERIES[0])
                 .encode(y=alt.Y("categoria:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                         x=alt.X("valor:Q", title="R$ no semestre"),
                         tooltip=[alt.Tooltip("categoria:N", title="Categoria"), alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
            rot = b.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(text="texto:N")
            charts.mostrar(b + rot, "Custo planejado por categoria", "R$ no semestre", cat[["categoria", "valor"]],
                           nota="Infraestrutura é zero: deploy no LAPPIS e documentação no GitHub Pages.", altura=charts.altura_categorias(len(cat)))
        with d:
            rec = pl.custo_por_recurso(ctx.plano_bruto, c.get("custo_membro_semana"))
            if rec.empty:
                layout.indisponivel("Custo por recurso indisponível", "aba Planejamento sem integrantes.")
            else:
                por = rec.groupby("integrante", as_index=False).agg(planejado=("custo", "sum"), semanas=("ativo", "sum"))
                if not horas.empty and custo_hora and "integrante" in horas:
                    hr = horas.groupby("integrante")["horas"].sum() * custo_hora
                    por["realizado"] = por["integrante"].map(hr)
                b = (alt.Chart(por).mark_bar(cornerRadiusEnd=2, color=theme.SERIES[0])
                     .encode(y=alt.Y("integrante:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
                             x=alt.X("planejado:Q", title="R$ planejado no semestre"),
                             tooltip=[alt.Tooltip("integrante:N"), alt.Tooltip("semanas:Q", title="Semanas ativas"),
                                      alt.Tooltip("planejado:Q", title="R$", format=",.2f")]))
                charts.mostrar(b, "Custo planejado por integrante", "R$ no semestre · semanas ativas × custo semanal",
                               por, nota=None if "realizado" in por else
                               "Custo realizado por integrante indisponível: nenhuma hora registrada.",
                               altura=charts.altura_categorias(len(por), 18))

    if not ctx.custos_df.empty:
        layout.tabela(ctx.custos_df.drop(columns=["chave"], errors="ignore"), "Ver as premissas de custo (aba Custos)")


# ───────────────────────── riscos ─────────────────────────

def _riscos(ctx, f):
    layout.metodologia([
        ("Risco, categoria, causa, resposta, responsável, status", "PLANILHA — aba Riscos", "registro do time"),
        ("Probabilidade e impacto", "PLANILHA — aba Monitoramento", "escala de 1 a 5; vale a avaliação mais recente"),
        ("Exposição e nível", "cálculo", "P × I: 1 a 5 baixo, 6 a 12 médio, 15 a 25 elevado"),
        ("Matriz", "PLANILHA", "riscos não encerrados em cada combinação de P e I"),
        ("Evolução", "PLANILHA — aba Monitoramento", "exposição de cada risco em cada sprint avaliada"),
    ], "Metodologia — riscos")
    st.caption(f"Fontes: {_origem(ctx, 'riscos')} · {_origem(ctx, 'monitoramento')}.")
    r = ctx.riscos
    if r.empty:
        layout.indisponivel("Aba Riscos não encontrada", _origem(ctx, "riscos"),
                            "publicar a aba Riscos em CSV e colar o link em `config.py` (chave `riscos`).")
        return
    r = r.copy()
    r["nivel_calc"] = r["exposicao_atual"].map(_nivel)
    r["status"] = r["status"].astype(str).str.strip()
    cols = st.columns(4)
    filtros_r = [("categoria", "Categoria"), ("status", "Status"), ("nivel_calc", "Nível"), ("responsavel", "Responsável")]
    for col, (campo, rot) in zip(cols, filtros_r):
        if campo in r:
            sel = col.multiselect(rot, sorted(v for v in r[campo].dropna().unique() if str(v).strip()),
                                  key=f"risco_{campo}", placeholder="Todos")
            if sel:
                r = r[r[campo].isin(sel)]
    baixo = r["status"].str.lower()
    ativos = r[~baixo.str.startswith(("encerr", "mitigad", "fechad"))]

    layout.secao("Situação dos riscos", "Quantos riscos estão abertos e quão graves eles são?", ["PLANILHA"])
    k = st.columns(5)
    with k[0]:
        kpi("Não encerrados", num(len(ativos)), "PLANILHA",
            nota=f"{resumo.contagem_riscos(r)['frase'] or 'nenhum'} · {len(r)} registrados")
    with k[1]:
        kpi("Mitigados / encerrados", num(int(baixo.str.startswith(("encerr", "mitigad", "fechad")).sum())), "PLANILHA")
    with k[2]:
        n = int((ativos["exposicao_atual"] >= 15).sum())
        kpi("Exposição elevada", num(n), "PLANILHA", status="critical" if n >= 3 else ("warning" if n else "good"),
            nota="P × I entre 15 e 25")
    with k[3]:
        kpi("Materializados", num(int(baixo.str.startswith("materializ").sum())), "PLANILHA")
    with k[4]:
        s = int((ativos["responsavel"].astype(str).str.strip() == "").sum()) if "responsavel" in ativos else None
        kpi("Sem responsável", num(s) if s is not None else None, "PLANILHA",
            status=None if s is None else ("good" if s == 0 else "warning"))

    for rid in resumo.riscos_fora_da_aba(ctx.riscos, ctx.monitoramento):
        layout.alerta("warning", f"{rid} tem avaliação na aba Monitoramento, mas não existe na aba Riscos: "
                                 "o painel não o conta até ser cadastrado lá.", "PLANILHA")

    layout.secao("Matriz de probabilidade × impacto", "Quais riscos têm maior impacto?", ["PLANILHA"])
    e, d = st.columns([1.1, 1])
    with e:
        grade = pd.DataFrame([(p, i) for p in range(1, 6) for i in range(1, 6)], columns=["p", "i"])
        grade["exposicao"] = grade["p"] * grade["i"]
        grade["nivel"] = grade["exposicao"].map(_nivel)
        cont = (ativos.dropna(subset=["probabilidade_atual", "impacto_atual"])
                .assign(p=lambda x: x["probabilidade_atual"].astype(int), i=lambda x: x["impacto_atual"].astype(int))
                .groupby(["p", "i"]).agg(ids=("id", lambda x: ", ".join(map(str, x))), n=("id", "count")).reset_index())
        grade = grade.merge(cont, on=["p", "i"], how="left").fillna({"ids": "", "n": 0})
        fundo = (alt.Chart(grade).mark_rect(stroke=theme.INK["surface"], strokeWidth=2)
                 .encode(x=alt.X("p:O", title="Probabilidade (1 a 5)", axis=alt.Axis(labelAngle=0)),
                         y=alt.Y("i:O", title="Impacto (1 a 5)", sort="descending"),
                         color=alt.Color("nivel:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                         tooltip=[alt.Tooltip("p:O", title="Probabilidade"), alt.Tooltip("i:O", title="Impacto"),
                                  alt.Tooltip("exposicao:Q", title="P × I"), alt.Tooltip("nivel:N", title="Nível"),
                                  alt.Tooltip("ids:N", title="Riscos")]))
        txt = (alt.Chart(grade[grade["ids"] != ""]).mark_text(fontSize=11, fontWeight=600, color=theme.INK["primary"],
                                                             lineBreak=", ")
               .encode(x="p:O", y=alt.Y("i:O", sort="descending"), text="ids:N"))
        charts.mostrar(fundo + txt, "Riscos abertos na matriz P × I", "IDs dos riscos em cada célula · avaliação mais recente",
                       grade[grade["n"] > 0][["p", "i", "exposicao", "nivel", "ids"]], altura=330)
    with d:
        top = ativos.sort_values("exposicao_atual", ascending=False).head(5)
        st.markdown("**Maiores exposições**")
        for t in top.itertuples():
            lv = _nivel(t.exposicao_atual) or "—"
            st_ = {"Elevado": "critical", "Médio": "warning", "Baixo": "good"}.get(lv, "neutral")
            layout.alerta(st_, f"{t.id} · {t.risco}", f"P×I {num(t.exposicao_atual)} · {t.responsavel or 'sem responsável'}")

    layout.secao("Distribuição dos riscos", "Onde os riscos se concentram?", ["PLANILHA"])
    e, d = st.columns(2)
    with e:
        pn = ativos.groupby("nivel_calc", as_index=False).size().rename(columns={"size": "riscos"})
        b = (alt.Chart(pn).mark_bar(cornerRadiusEnd=3, stroke=theme.INK["axis"], strokeWidth=1)
             .encode(y=alt.Y("nivel_calc:N", sort=NIVEIS, title=None), x=alt.X("riscos:Q", title="Riscos abertos"),
                     color=alt.Color("nivel_calc:N", scale=COR_NIVEL, legend=None),
                     tooltip=[alt.Tooltip("nivel_calc:N", title="Nível"), alt.Tooltip("riscos:Q", title="Riscos")]))
        rot = b.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(
            text="riscos:Q", color=alt.value(theme.INK["secondary"]))
        charts.mostrar(b + rot, "Riscos abertos por severidade", "quantidade · nível pela exposição P × I", pn, altura=charts.altura_categorias(len(pn), 34))
    with d:
        pc = ativos.groupby(["categoria", "nivel_calc"], as_index=False).size().rename(columns={"size": "riscos"})
        b = (alt.Chart(pc).mark_bar(stroke=theme.INK["surface"], strokeWidth=2)
             .encode(y=alt.Y("categoria:N", sort="-x", title=None), x=alt.X("riscos:Q", title="Riscos abertos", stack=True),
                     color=alt.Color("nivel_calc:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                     order=alt.Order("nivel_calc:N", sort="ascending"),
                     tooltip=[alt.Tooltip("categoria:N", title="Categoria"), alt.Tooltip("nivel_calc:N", title="Nível"),
                              alt.Tooltip("riscos:Q", title="Riscos")]))
        charts.mostrar(b, "Riscos abertos por categoria", "quantidade · categorias da EAR", pc,
                       altura=charts.altura_categorias(pc["categoria"].nunique(), 30))

    layout.secao("Evolução dos riscos", "Estamos acumulando riscos ou reduzindo a exposição?", ["PLANILHA"])
    m = ctx.monitoramento
    if m.empty or m["sprint"].dropna().empty:
        layout.indisponivel("Evolução indisponível", "a aba Monitoramento não tem avaliações.")
    else:
        m = m.dropna(subset=["exposicao"]).assign(nivel=lambda x: x["exposicao"].map(_nivel))
        m = m[m["id_do_risco"].isin(r["id"])]
        por = m.groupby(["sprint", "nivel"], as_index=False).size().rename(columns={"size": "riscos"})
        b = (alt.Chart(por).mark_bar(stroke=theme.INK["surface"], strokeWidth=2)
             .encode(x=alt.X("sprint:O", title="Sprint avaliada", axis=alt.Axis(labelAngle=0)),
                     y=alt.Y("riscos:Q", title="Riscos avaliados", stack=True),
                     color=alt.Color("nivel:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                     order=alt.Order("nivel:N", sort="ascending"),
                     tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nivel:N", title="Nível"), alt.Tooltip("riscos:Q")]))
        tot = m.groupby("sprint", as_index=False)["exposicao"].sum()
        nota = ("Só há avaliação de uma sprint; cada nova revisão de riscos na planning vira uma coluna."
                if m["sprint"].nunique() < 2 else None)
        e, d = st.columns(2)
        with e:
            charts.mostrar(b, "Riscos por nível em cada revisão", "quantidade · aba Monitoramento", por, nota=nota,
                           altura=230)
        with d:
            heat = (alt.Chart(m).mark_rect(stroke=theme.INK["surface"], strokeWidth=2)
                    .encode(x=alt.X("sprint:O", title="Sprint avaliada", axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("id_do_risco:N", title=None),
                            color=alt.Color("nivel:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                            tooltip=[alt.Tooltip("id_do_risco:N", title="Risco"), alt.Tooltip("sprint:O"),
                                     alt.Tooltip("probabilidade:Q", title="P"), alt.Tooltip("impacto:Q", title="I"),
                                     alt.Tooltip("exposicao:Q", title="P × I"), alt.Tooltip("status:N")]))
            txt = heat.mark_text(fontSize=10).encode(text="exposicao:Q", color=alt.value(theme.INK["primary"]))
            charts.mostrar(heat + txt, "Exposição de cada risco por revisão", "P × I", tot.rename(
                columns={"exposicao": "exposição total"}), altura=max(200, 20 * m["id_do_risco"].nunique()))

    layout.secao("Matriz de riscos", "Qual é o plano de resposta de cada risco?", ["PLANILHA"])
    colunas = {"id": "ID", "risco": "Descrição", "categoria": "Categoria", "probabilidade_atual": "Probabilidade",
               "impacto_atual": "Impacto", "exposicao_atual": "P × I", "nivel_calc": "Nível", "responsavel": "Responsável",
               "resposta": "Estratégia de resposta", "status": "Status", "identificado_em": "Identificado em",
               "prazo": "Prazo", "acao_preventiva": "Mitigação", "contingencia": "Contingência"}
    t = r.sort_values("exposicao_atual", ascending=False)
    t = t[[c for c in colunas if c in t]].rename(columns=colunas)
    st.dataframe(t, use_container_width=True, hide_index=True, column_config={
        "Descrição": st.column_config.TextColumn(width="large"),
        "Identificado em": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "P × I": st.column_config.NumberColumn(format="%d")})
    if "prazo" not in r:
        st.caption("Prazo: a aba Riscos não tem essa coluna — o dado não está disponível. Para exibi-lo, acrescente a "
                   "coluna **Prazo** na planilha.")


# ───────────────────────── decisões ─────────────────────────

def _decisoes(ctx, f):
    st.caption(f"Fonte: {_origem(ctx, 'decisoes')}. Meta da disciplina: ≥ 3 decisões na R2 e ≥ 5 na R3.")
    dec = ctx.decisoes
    if dec.empty:
        layout.indisponivel("Nenhuma decisão registrada", "a aba Decisões está vazia.")
        return
    k = st.columns(3)
    medidas = int((dec.get("resultado", pd.Series(dtype=str)).astype(str).str.strip() != "").sum())
    meta = {"R2": 3, "R3": 5}.get(f["release_metas"])
    with k[0]:
        kpi("Decisões registradas", num(len(dec)), "PLANILHA",
            status=None if not meta else ("good" if len(dec) >= meta else "warning"),
            nota=f"meta da {f['release_metas']}: {meta}" if meta else "metas: 3 na R2, 5 na R3")
    with k[1]:
        kpi("Com resultado medido", num(medidas), "PLANILHA")
    with k[2]:
        kpi("Vigentes", num(int((dec.get("status", pd.Series(dtype=str)) == "Vigente").sum())), "PLANILHA")
    for _, d in dec.iterrows():
        with st.container(border=True):
            st.markdown(f"**{d.get('data', '')} · sprint {d.get('sprint', '')} · {d.get('indicador', '')}** · "
                        f"{d.get('tipo', '')} · _{d.get('status', '')}_")
            st.markdown(f"**Contexto e dado:** {d.get('contexto_e_dado', '')}\n\n**Decisão:** {d.get('decisao', '')}\n\n"
                        f"**Evidência:** {d.get('evidencia', '')}\n\n**Critério de sucesso:** "
                        f"{d.get('criterio_de_sucesso', '')}\n\n**Resultado:** {d.get('resultado', '') or '_em observação_'}")


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Custos e riscos", "Informações gerenciais que não existem no Sonar nem no Zenhub: custos, "
                         "riscos e decisões registrados na planilha do time.", ["PLANILHA"])
    aba_c, aba_r, aba_d = st.tabs(["Custos", "Riscos", "Decisões"])
    with aba_c:
        _custos(ctx, f)
    with aba_r:
        _riscos(ctx, f)
    with aba_d:
        _decisoes(ctx, f)
