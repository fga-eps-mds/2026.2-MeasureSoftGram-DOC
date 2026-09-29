"""Custos — orçamento, gasto e premissas (fonte: planilha do time).

Ordem: cartões → dado bruto (premissas, horas, planejamento semanal) → análise
(planejado × real por sprint, custo por categoria) → aba original da planilha.
Sem horas registradas o custo real fica indisponível: nunca é trocado pelo planejado.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, layout, rastreio
from src.components.kpi import kpi
from src.data import planilha as pl
from src.metrics.calculations import brl, data_br, num, vazio


def _menus(c):
    layout.menus([
        ("Custo de um integrante por semana", "quanto custa uma pessoa do time numa semana",
         "custo de cursar EPS por semana + energia + internet + depreciação do notebook", [rastreio.aba("custos")]),
        ("Custo por hora", "converte horas trabalhadas em reais", "custo de um integrante por semana ÷ horas por "
         "semana", [rastreio.aba("custos")]),
        ("Orçamento (custo planejado)", "quanto o semestre deve custar", "Σ semanas (integrantes ativos × custo de um "
         "integrante + infraestrutura)", [rastreio.aba("planejamento"), rastreio.aba("custos")]),
        ("Gasto (custo real)", "quanto já foi gasto", "horas registradas × custo por hora; sprint sem horas não entra",
         [rastreio.aba("horas"), rastreio.aba("custos")]),
        ("Custo por categoria", "de que é feito o orçamento", "valor semanal de cada componente × integrantes-semana "
         "planejados", [rastreio.aba("custos"), rastreio.aba("planejamento")]),
    ], [
        ("Custo por hora", brl(c.get("custo_hora")), "aba Custos · chave custo_hora", pl.link_aba("custos")),
        ("Custo de um integrante por semana", brl(c.get("custo_membro_semana")),
         "aba Custos · chave custo_membro_semana", pl.link_aba("custos")),
        ("Horas por integrante por semana", f"{num(c.get('horas_semana_total'))} h",
         "aba Custos · chave horas_semana_total", pl.link_aba("custos")),
        ("Integrantes no time", num(c.get("integrantes")), "aba Custos · chave integrantes", pl.link_aba("custos")),
    ], fontes=["PLANILHA", "CALCULADO"])


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Custos", "Quanto o projeto deve custar, quanto já custou e de onde vem cada valor.",
                         ["PLANILHA"])
    c = ctx.custo
    _menus(c)
    if not c:
        layout.indisponivel("Aba Custos não lida", ctx.origem_planilha.get("custos", "não lida").replace("**", ""),
                            "publicar a aba Custos e colar o link em `config.PLANILHAS`.")
        return
    plano = ctx.plano.dropna(subset=["custo"]) if not ctx.plano.empty else ctx.plano
    horas = ctx.horas.dropna(subset=["horas"]) if not ctx.horas.empty and "horas" in ctx.horas else pd.DataFrame()
    horas = horas[horas["horas"] > 0] if not horas.empty else horas
    custo_hora = c.get("custo_hora")
    gasto = float(horas["horas"].sum() * custo_hora) if not horas.empty and custo_hora else None

    layout.secao("Resumo", "Quanto foi orçado e quanto foi gasto?", ["PLANILHA", "CALCULADO"])
    k = st.columns(4)
    with k[0]:
        kpi("Orçamento do semestre", brl(plano["custo"].sum(), 0) if not plano.empty else None, "PLANILHA",
            nota=f"{len(plano)} semanas planejadas", origem=[rastreio.aba("planejamento")])
    with k[1]:
        ate = plano[plano["semana"] <= ctx.hoje]["custo"].sum() if not plano.empty else None
        kpi("Gasto até agora", brl(gasto, 0) if gasto is not None else None, "CALCULADO",
            nota=(f"planejado até hoje: {brl(ate, 0)}" if gasto is not None else
                  "Indisponível: nenhuma hora registrada na aba Horas."), origem=[rastreio.aba("horas")])
    with k[2]:
        kpi("Custo por hora", brl(custo_hora), "PLANILHA", nota=f"{num(c.get('horas_semana_total'))} h por semana",
            origem=[rastreio.aba("custos")])
    with k[3]:
        kpi("Horas registradas", f"{num(horas['horas'].sum())} h" if not horas.empty else None, "PLANILHA",
            nota=(f"sprints {', '.join(str(int(s)) for s in sorted(horas['sprint'].dropna().unique()))}"
                  if not horas.empty else "Indisponível: aba Horas vazia."), origem=[rastreio.aba("horas")])

    layout.secao("Dado bruto", "De onde sai cada valor?", ["PLANILHA"])
    t1, t2, t3 = st.tabs(["Premissas (aba Custos)", "Horas por integrante e sprint (aba Horas)",
                          "Custo planejado por semana (aba Planejamento)"])
    with t1:
        df = ctx.custos_df
        if df.empty:
            st.caption("Aba Custos vazia.")
        else:
            cols = [x for x in ("item", "valor", "unidade", "calculo", "fonte", "chave") if x in df]
            st.dataframe(df[cols].rename(columns={"item": "Item", "valor": "Valor", "unidade": "Unidade",
                                                  "calculo": "Como é calculado", "fonte": "Fonte", "chave": "Chave"}),
                         use_container_width=True, hide_index=True)
    with t2:
        if horas.empty:
            layout.indisponivel("Sem horas registradas", "a aba Horas não tem horas lançadas.")
        else:
            piv = horas.pivot_table(index="integrante", columns="sprint", values="horas", aggfunc="sum")
            piv.columns = [f"S{int(x)}" for x in piv.columns]
            piv["Total"] = piv.sum(axis=1)
            st.dataframe(piv.reset_index().rename(columns={"integrante": "Integrante"}), use_container_width=True,
                         hide_index=True)
            st.caption(f"{horas['integrante'].nunique()} integrantes com horas · custo real = horas × "
                       f"{brl(custo_hora)} por hora.")
    with t3:
        if plano.empty:
            st.caption("Aba Planejamento sem custo por semana.")
        else:
            w = plano[["semana", "release", "sprint", "integrantes", "custo"]].copy()
            w["semana"] = w["semana"].map(data_br)
            layout.tabela_html(w, {"semana": "Semana de", "release": "Release", "sprint": "Sprint",
                                   "integrantes": "Integrantes ativos", "custo": "Custo planejado (R$)"},
                               numericas=("sprint", "integrantes", "custo"))

    layout.secao("Análise", "O gasto está de acordo com o planejado, e do que ele é feito?", ["CALCULADO"])
    e, d = st.columns(2)
    with e:
        if plano.empty or "sprint" not in plano:
            layout.indisponivel("Planejado × real indisponível", "aba Planejamento sem sprint por semana.")
        else:
            plan = plano.groupby("sprint")["custo"].sum()
            real = horas.groupby("sprint")["horas"].sum() * custo_hora if not horas.empty and custo_hora else \
                pd.Series(dtype=float)
            linhas = [{"sprint": f"S{int(s)}", "serie": "Planejado", "valor": v} for s, v in plan.items()]
            linhas += [{"sprint": f"S{int(s)}", "serie": "Real", "valor": v} for s, v in real.items()]
            dd = pd.DataFrame(linhas)
            ordem = [f"S{int(s)}" for s in sorted(plan.index)]
            dom = ["Planejado", "Real"]
            b = (alt.Chart(dd).mark_bar(size=14, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                 .encode(x=alt.X("sprint:N", sort=ordem, title="Sprint", axis=alt.Axis(labelAngle=0)),
                         xOffset=alt.XOffset("serie:N", sort=dom), y=alt.Y("valor:Q", title="R$"),
                         color=alt.Color("serie:N", title=None, sort=dom,
                                         scale=alt.Scale(domain=dom, range=[theme.SERIES[2], theme.SERIES[0]])),
                         tooltip=[alt.Tooltip("sprint:N"), alt.Tooltip("serie:N"),
                                  alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
            charts.mostrar(b, "Custo planejado × real por sprint", "R$ · real = horas registradas × custo por hora",
                           altura=220, nota=None if not real.empty else "Real não aparece: nenhuma hora registrada.")
    with d:
        pessoas_semana = plano["integrantes"].sum() if not plano.empty else 0
        cat = pd.DataFrame([{"categoria": rot, "valor": c.get(k) * pessoas_semana}
                            for k, rot in pl.COMPONENTES_CUSTO.items() if not vazio(c.get(k))])
        if c.get("infra_semana") is not None and not plano.empty:
            cat = pd.concat([cat, pd.DataFrame([{"categoria": "Infraestrutura (deploy, domínio)",
                                                 "valor": c.get("infra_semana") * len(plano)}])], ignore_index=True)
        if cat.empty:
            layout.indisponivel("Custo por categoria indisponível", "aba Custos sem os componentes semanais.")
        else:
            cat["texto"] = cat["valor"].map(lambda v: brl(v, 0))
            b = (alt.Chart(cat).mark_bar(cornerRadiusEnd=3, color=theme.SERIES[0])
                 .encode(y=alt.Y("categoria:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                         x=alt.X("valor:Q", title="R$ no semestre"),
                         tooltip=[alt.Tooltip("categoria:N"), alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
            rot = b.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(text="texto:N")
            charts.mostrar(b + rot, "Orçamento por categoria", "R$ no semestre", altura=charts.altura_categorias(len(cat)))

    for chave in ("custos", "horas", "planejamento"):
        rastreio.aba_original(chave)
