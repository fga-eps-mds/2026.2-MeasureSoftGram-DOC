"""Integração contínua — fonte GITHUB (execuções de workflow coletadas pelo metrics.yml)."""

from __future__ import annotations

import altair as alt
import streamlit as st

import config
from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.data.sonar import nome_curto
from src.metrics.calculations import num, status_taxa

CONCLUSOES = ["success", "failure", "cancelled", "skipped"]
ROT = {"success": "Sucesso", "failure": "Falha", "cancelled": "Cancelada", "skipped": "Ignorada"}
COR = alt.Scale(domain=[ROT[c] for c in CONCLUSOES],
                range=[theme.STATUS["good"], theme.STATUS["critical"], theme.NEUTRO, theme.NEUTRO_CLARO])


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Integração contínua", "Saúde dos pipelines de CI/CD dos repositórios (processo de "
                         "desenvolvimento).", ["GITHUB"])
    layout.metodologia([
        ("Execuções, sucesso, falhas", "GITHUB — Actions (`GitHub_API-Runs-*.json`, coletado pelo metrics.yml)",
         "taxa de sucesso = execuções com sucesso ÷ execuções concluídas com sucesso ou falha"),
        ("Tempo de feedback", "GITHUB", "atualização final − início de cada execução, em minutos (mediana)"),
        ("Meta", "time", f"sucesso da CI ≥ {num(config.META_CI_SUCESSO)}%"),
    ])
    runs = ctx.gh_runs
    if runs.empty:
        layout.indisponivel("Sem execuções de CI", "nenhum arquivo `GitHub_API-Runs-*.json` encontrado.",
                            "rodar o `metrics.yml` nos repositórios.")
        return
    r = filters.por_periodo(filters.por_repo(runs, f["repos"]), "criado_em", f["periodo"])
    conc = r[r["conclusao"].isin(["success", "failure"])]
    if conc.empty:
        layout.indisponivel("Sem execuções concluídas no período", "ajuste o período ou os repositórios.")
        return
    taxa = (conc["conclusao"] == "success").mean() * 100
    layout.secao("Indicadores", "A CI é confiável o bastante para servir de portão de qualidade?", ["GITHUB"])
    k = st.columns(4)
    with k[0]:
        kpi("Taxa de sucesso", f"{num(taxa)}%", "GITHUB",
            status=status_taxa(taxa, config.META_CI_SUCESSO, 60), nota=f"meta ≥ {num(config.META_CI_SUCESSO)}%")
    with k[1]:
        kpi("Execuções concluídas", num(len(conc)), "GITHUB", nota=f"{r['repositorio'].nunique()} repositórios")
    with k[2]:
        kpi("Falhas", num(int((conc["conclusao"] == "failure").sum())), "GITHUB")
    with k[3]:
        dur = conc["duracao_min"].dropna()
        kpi("Tempo mediano de feedback", f"{num(dur.median(), 1)} min" if not dur.empty else None, "GITHUB",
            nota=f"mais lenta: {num(dur.max(), 1)} min" if not dur.empty else "sem duração registrada")

    layout.secao("Resultado por repositório", "Onde a CI falha mais?", ["GITHUB"])
    pr = (r[r["conclusao"].isin(CONCLUSOES)].assign(repo=lambda x: x["repositorio"].map(nome_curto),
                                                      resultado=lambda x: x["conclusao"].map(ROT))
          .groupby(["repo", "resultado"], as_index=False).size().rename(columns={"size": "execucoes"}))
    b = (alt.Chart(pr).mark_bar(size=18, stroke=theme.INK["surface"], strokeWidth=2)
         .encode(y=alt.Y("repo:N", sort="-x", title=None), x=alt.X("execucoes:Q", title="Execuções", stack=True),
                 color=alt.Color("resultado:N", title="Resultado", scale=COR, sort=[ROT[c] for c in CONCLUSOES]),
                 tooltip=[alt.Tooltip("repo:N", title="Repositório"), alt.Tooltip("resultado:N", title="Resultado"),
                          alt.Tooltip("execucoes:Q", title="Execuções")]))
    charts.mostrar(b, "Execuções de CI por resultado", "quantidade de execuções no período", pr,
                   altura=max(160, 30 * pr["repo"].nunique()))

    layout.secao("Evolução", "A estabilidade da CI está melhorando?", ["GITHUB"])
    sem = conc.assign(semana=lambda x: x["criado_em"].dt.tz_convert(None).dt.to_period("W").dt.start_time)
    s = sem.groupby("semana").agg(execucoes=("conclusao", "size"),
                                  sucesso=("conclusao", lambda c: (c == "success").mean() * 100)).reset_index()
    g = (alt.Chart(s).mark_line(color=theme.SERIES[0], strokeWidth=2,
                                point=alt.OverlayMarkDef(size=60, filled=True, color=theme.SERIES[0]))
         .encode(x=alt.X("semana:T", title="Semana", axis=alt.Axis(format="%d/%m")),
                 y=alt.Y("sucesso:Q", title="Sucesso (%)", scale=alt.Scale(domain=[0, 100])),
                 tooltip=[alt.Tooltip("semana:T", title="Semana de", format="%d/%m/%Y"),
                          alt.Tooltip("sucesso:Q", title="Sucesso (%)", format=".0f"),
                          alt.Tooltip("execucoes:Q", title="Execuções")]))
    charts.mostrar(g + charts.regra_horizontal(config.META_CI_SUCESSO, f"meta {num(config.META_CI_SUCESSO)}%",
                                               theme.STATUS["critical"]),
                   "Taxa de sucesso da CI por semana", "% de execuções com sucesso · semanas com execução", s, altura=240)
