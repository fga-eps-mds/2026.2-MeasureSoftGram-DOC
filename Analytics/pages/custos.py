"""Custos — orçamento, gasto e premissas (fonte: planilha do time).

Ordem: cartões → dado bruto (premissas, custo do time por semana) → análise (custo por sprint,
custo por categoria) → aba original da planilha.

Como na literatura de EVM ágil, nenhuma hora é estimada nem apontada: o custo de uma semana é o custo
de quem está no time naquela semana (integrantes ativos da aba Planejamento × custo de um integrante por
semana + infraestrutura). Gasto = esse custo nas semanas que já começaram.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout, rastreio
from src.components.kpi import kpi
from src.data import planilha as pl
from src.metrics.calculations import brl, data_br, num, vazio


ESCOPO = {
    "release": "define o período padrão",
    "periodo": "semanas da aba Planejamento que começam no período",
}


def _menus(c):
    layout.menus([
        ("Custo de um integrante por semana", "quanto custa uma pessoa do time numa semana",
         "custo de cursar EPS por semana + energia + internet + depreciação do notebook", [rastreio.aba("custos")]),
        ("Custo do time na semana", "quanto o time custa numa semana",
         "integrantes ativos (aba Planejamento) × custo de um integrante por semana + infraestrutura",
         [rastreio.aba("planejamento"), rastreio.aba("custos")]),
        ("Orçamento (custo planejado)", "quanto o período deve custar", "Σ custo do time nas semanas do período",
         [rastreio.aba("planejamento"), rastreio.aba("custos")]),
        ("Gasto (custo real)", "quanto já foi gasto", "Σ custo do time nas semanas que já começaram — sem horas: "
         "na literatura de EVM ágil o custo é o do time, não o de horas apontadas",
         [rastreio.aba("planejamento"), rastreio.aba("custos")]),
        ("Custo por categoria", "de que é feito o orçamento", "valor semanal de cada componente × integrantes-semana "
         "planejados", [rastreio.aba("custos"), rastreio.aba("planejamento")]),
    ], [
        ("Custo de um integrante por semana", brl(c.get("custo_membro_semana")),
         "aba Custos · chave custo_membro_semana", pl.link_aba("custos")),
        ("Integrantes no time", num(c.get("integrantes")), "aba Custos · chave integrantes", pl.link_aba("custos")),
    ], fontes=["PLANILHA", "CALCULADO"])


def pagina(embutida: bool = False):
    """``embutida``: desenhada no fim da página Agile EVM (o painel enxuto juntou as duas)."""
    ctx, f = layout.estado()
    if embutida:
        st.divider()
        layout.secao("Custos", "Quanto o projeto deve custar, quanto já custou e de onde vem cada valor?",
                     ["PLANILHA"])
    else:
        layout.titulo_pagina("Custos", "Quanto o projeto deve custar, quanto já custou e de onde vem cada valor.",
                             ["PLANILHA"])
    c = ctx.custo
    if not embutida:
        _menus(c)
    if not c:
        layout.indisponivel("Aba Custos não lida", ctx.origem_planilha.get("custos", "não lida").replace("**", ""),
                            "publicar a aba Custos e colar o link em `config.PLANILHAS`.")
        return
    plano_todo = ctx.plano.dropna(subset=["custo"]) if not ctx.plano.empty else ctx.plano
    # ── recorte: período global + sprint (filtro da página) ──
    plano = filters.por_periodo(plano_todo, "semana", f["periodo"]) if not plano_todo.empty else plano_todo
    caixa = filters.da_pagina(f, ESCOPO, titulo="Filtros de custos", resumo=False) if embutida \
        else filters.da_pagina(f, ESCOPO)
    sprints = sorted(int(x) for x in plano["sprint"].dropna().unique()) if not plano.empty and "sprint" in plano \
        else []
    sel_s = caixa.multiselect("Sprint", sprints, key="custo_sprint", placeholder="Todas do período",
                              format_func=lambda x: f"S{x}")
    if sel_s:
        plano = plano[plano["sprint"].isin(sel_s)]
    st.caption(f"Recorte: {filters.resumo_ativos(f, ESCOPO)}" + (f" · sprints {', '.join(f'S{x}' for x in sel_s)}"
                                                                  if sel_s else "")
               + f" · orçamento do semestre inteiro: {brl(plano_todo['custo'].sum(), 0) if not plano_todo.empty else '—'}")
    passadas = plano[plano["semana"] <= ctx.hoje] if not plano.empty else plano
    gasto = float(passadas["custo"].sum()) if not passadas.empty else None
    semana_atual = plano_todo[plano_todo["semana"] <= ctx.hoje].tail(1) if not plano_todo.empty else plano_todo

    layout.secao("Resumo", "Quanto foi orçado e quanto foi gasto?", ["PLANILHA", "CALCULADO"])
    k = st.columns(4)
    with k[0]:
        kpi("Orçamento no período", brl(plano["custo"].sum(), 0) if not plano.empty else None, "PLANILHA",
            nota=f"{len(plano)} semanas planejadas", origem=[rastreio.aba("planejamento")])
    with k[1]:
        kpi("Gasto no período", brl(gasto, 0) if gasto is not None else None, "CALCULADO",
            nota=(f"custo do time em {len(passadas)} semana(s) já iniciada(s)" if gasto is not None else
                  "Nenhuma semana do período começou ainda."), origem=[rastreio.aba("planejamento")])
    with k[2]:
        kpi("Custo do time por semana", brl(semana_atual["custo"].iloc[0], 0) if not semana_atual.empty else None,
            "PLANILHA", nota=(f"{num(semana_atual['integrantes'].iloc[0])} integrantes ativos na semana atual"
                              if not semana_atual.empty and "integrantes" in semana_atual else "aba Planejamento"),
            origem=[rastreio.aba("planejamento")])
    with k[3]:
        kpi("Custo de um integrante por semana", brl(c.get("custo_membro_semana")), "PLANILHA",
            nota="premissa da aba Custos", origem=[rastreio.aba("custos")])

    layout.secao("Análise", "Quanto custa cada sprint, e do que o custo é feito?", ["CALCULADO"])
    e, d = st.columns(2)
    with e:
        if plano.empty or "sprint" not in plano:
            layout.indisponivel("Custo por sprint indisponível", "aba Planejamento sem sprint por semana.")
        else:
            pp = plano.assign(situacao=["Gasto" if x <= ctx.hoje else "A gastar" for x in plano["semana"]])
            dd = pp.groupby(["sprint", "situacao"])["custo"].sum().reset_index()
            dd["sprint"] = dd["sprint"].map(lambda x: f"S{int(x)}")
            ordem = [f"S{int(x)}" for x in sorted(plano["sprint"].dropna().unique())]
            dom = ["Gasto", "A gastar"]
            b = (alt.Chart(dd).mark_bar(size=24, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                 .encode(x=alt.X("sprint:N", sort=ordem, title="Sprint", axis=alt.Axis(labelAngle=0)),
                         y=alt.Y("custo:Q", title="R$", stack=True),
                         color=alt.Color("situacao:N", title=None, sort=dom,
                                         scale=alt.Scale(domain=dom, range=[theme.SERIES[0], theme.SERIES[2]])),
                         tooltip=[alt.Tooltip("sprint:N"), alt.Tooltip("situacao:N", title="Situação"),
                                  alt.Tooltip("custo:Q", title="R$", format=",.2f")]))
            charts.mostrar(b, "Custo do time por sprint", "R$ · integrantes ativos × custo por semana + infraestrutura",
                           altura=220, nota="Gasto = semanas que já começaram; a gastar = semanas futuras.")
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
                         x=alt.X("valor:Q", title="R$ no período"),
                         tooltip=[alt.Tooltip("categoria:N"), alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
            rot = b.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(text="texto:N")
            charts.mostrar(b + rot, "Orçamento por categoria", "R$ no período", altura=charts.altura_categorias(len(cat)))

    if layout.detalhes("custos", "Mostrar premissas e custo por semana"):
        layout.secao("Dado bruto", "De onde sai cada valor?", ["PLANILHA"])
        t1, t3 = st.tabs(["Premissas (aba Custos)", "Custo do time por semana (aba Planejamento)"])
        with t1:
            df = ctx.custos_df
            if df.empty:
                st.caption("Aba Custos vazia.")
            else:
                cols = [x for x in ("item", "valor", "unidade", "calculo", "fonte", "chave") if x in df]
                st.dataframe(df[cols].rename(columns={"item": "Item", "valor": "Valor", "unidade": "Unidade",
                                                      "calculo": "Como é calculado", "fonte": "Fonte", "chave": "Chave"}),
                             use_container_width=True, hide_index=True)
        with t3:
            if plano.empty:
                st.caption("Aba Planejamento sem custo por semana.")
            else:
                w = plano[["semana", "release", "sprint", "integrantes", "custo"]].copy()
                w["situacao"] = ["gasto" if x <= ctx.hoje else "a gastar" for x in w["semana"]]
                w["semana"] = w["semana"].map(data_br)
                layout.tabela_html(w, {"semana": "Semana de", "release": "Release", "sprint": "Sprint",
                                       "integrantes": "Integrantes ativos", "custo": "Custo do time (R$)",
                                       "situacao": "Situação"},
                                   numericas=("sprint", "integrantes", "custo"))
                st.caption("Se alguém entrar ou sair do time, atualize os integrantes da semana na aba Planejamento: o "
                           "gasto e o custo real do EVM mudam junto.")
        for chave in ("custos", "planejamento"):
            rastreio.aba_original(chave)
