"""Integração contínua — fonte GITHUB (execuções de workflow coletadas pelo metrics.yml)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import charts, filters, layout, rastreio
from src.components.kpi import kpi
from src.data.sonar import nome_curto
from src.metrics.calculations import data_br, num, status_taxa

CONCLUSOES = ["success", "failure", "cancelled", "skipped"]
ROT = {"success": "Sucesso", "failure": "Falha", "cancelled": "Cancelada", "skipped": "Ignorada"}
COR = alt.Scale(domain=[ROT[c] for c in CONCLUSOES],
                range=[theme.STATUS["good"], theme.STATUS["critical"], theme.NEUTRO, theme.NEUTRO_CLARO])


def _tabela_repos(todas, r, f) -> None:
    """Uma linha por repositório: contagem por resultado, até quando há dado e de onde veio, com link."""
    linhas = []
    for repo in config.GITHUB_REPOS:
        if f["repos"] and nome_curto(repo) not in f["repos"]:
            continue
        x = r[r["repositorio"] == repo]
        tudo = todas[todas["repositorio"] == repo]
        cont = x["conclusao"].fillna("em andamento").value_counts()
        ok, falha = int(cont.get("success", 0)), int(cont.get("failure", 0))
        origem = ", ".join(sorted(tudo["origem"].dropna().unique())) if not tudo.empty else "sem dados"
        ate = (tudo["coletado_em"].max() if (tudo["origem"] == "coleta do dashboard").any()
               else tudo["atualizado_em"].max()) if not tudo.empty else None
        falhas_r = x[x["conclusao"] == "failure"].sort_values("criado_em")
        ult_falha = falhas_r.iloc[-1] if not falhas_r.empty else None
        linhas.append({
            "repo": [(nome_curto(repo), rastreio.actions(repo))],
            "ult_falha": [(data_br(ult_falha["criado_em"], True) + f" · {ult_falha['workflow']}",
                           ult_falha.get("url") if isinstance(ult_falha.get("url"), str) else None)]
            if ult_falha is not None else [],
            "total": len(x), "sucesso": ok, "falha": falha,
            "outras": len(x) - ok - falha,
            "taxa": f"{num(ok / (ok + falha) * 100)}%" if ok + falha else "—",
            "ate": pd.Timestamp(ate).tz_convert("America/Sao_Paulo").strftime("%d/%m %H:%M") if ate is not None
            and not pd.isna(ate) else "—",
            "origem": origem})
    tab = pd.DataFrame(linhas)
    layout.tabela_html(tab, {"repo": "Repositório", "total": "Execuções no período", "sucesso": "Sucesso",
                             "falha": "Falha", "outras": "Canceladas / ignoradas / em andamento",
                             "taxa": "Taxa de sucesso", "ult_falha": "Última falha", "ate": "Dados até",
                             "origem": "Origem do dado"},
                       links=("repo", "ult_falha"), numericas=("total", "sucesso", "falha", "outras"), altura=None)
    st.caption("Para conferir no GitHub: abra o repositório (link), aba Actions, e compare com as execuções criadas "
               "no período da barra lateral. 'Dados até' é o momento da última coleta: execuções depois disso só "
               "aparecem na próxima. Origem 'metrics.yml' = arquivo enviado pelo pipeline do próprio repositório, "
               "que só atualiza quando ele roda; 'coleta do dashboard' = `scripts/coleta_github.py`, 3 vezes por "
               "dia, com todas as execuções do semestre.")


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Integração contínua", "Saúde dos pipelines de CI/CD dos repositórios (processo de "
                         "desenvolvimento).", ["GITHUB"])
    layout.menus([
        ("Execução", "uma rodada de um workflow do GitHub Actions (testes, lint, deploy...)",
         "cada item de `actions/runs` criado no período", []),
        ("Taxa de sucesso", "quanto da CI passa", "execuções com sucesso ÷ execuções que terminaram em sucesso ou "
         "falha (canceladas e ignoradas ficam de fora)", []),
        ("Tempo de feedback", "quanto a CI demora para responder", "fim − início de cada execução (mediana)", []),
        ("Dados até", "até quando há execuções coletadas", "hora da última coleta daquele repositório", []),
    ], [
        ("Meta de sucesso da CI", f"≥ {num(config.META_CI_SUCESSO)}%", "config.py · META_CI_SUCESSO",
         rastreio.codigo()),
        ("Abaixo disso é crítico", f"< {num(config.LIMITE_CI_CRITICO)}%", "config.py · LIMITE_CI_CRITICO",
         rastreio.codigo()),
        ("Repositórios coletados", ", ".join(nome_curto(r) for r in config.GITHUB_REPOS), "config.py · GITHUB_REPOS",
         rastreio.codigo()),
        ("Execuções desde", data_br(pd.Timestamp(config.INICIO_SEMESTRE)), "config.py · INICIO_SEMESTRE",
         rastreio.codigo()),
        ("Período analisado", f"{data_br(f['periodo'][0])} a {data_br(f['periodo'][1])}", "barra lateral", None),
    ], fontes=["GITHUB", "CALCULADO"])
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
    layout.secao("Resumo", "A CI é confiável o bastante para servir de portão de qualidade?", ["GITHUB"])
    k = st.columns(4)
    with k[0]:
        kpi("Taxa de sucesso", f"{num(taxa)}%", "GITHUB",
            status=status_taxa(taxa, config.META_CI_SUCESSO, config.LIMITE_CI_CRITICO), nota=f"meta ≥ {num(config.META_CI_SUCESSO)}%")
    with k[1]:
        outras = len(r) - len(conc)
        kpi("Execuções no período", num(len(r)), "GITHUB",
            nota=f"{num(len(conc))} com sucesso ou falha (base da taxa) · {num(outras)} canceladas, ignoradas ou "
                 f"em andamento · {r['repositorio'].nunique()} repositórios")
    with k[2]:
        kpi("Falhas", num(int((conc["conclusao"] == "failure").sum())), "GITHUB")
    with k[3]:
        ult = r.sort_values("criado_em").iloc[-1]
        dur = conc["duracao_min"].dropna()
        kpi("Última execução", data_br(ult["criado_em"], True), "GITHUB",
            nota=f"{nome_curto(ult['repositorio'])} · {ult['workflow']} · {ult['conclusao'] or 'em andamento'}"
                 + (f" · feedback mediano {num(dur.median(), 1)} min" if not dur.empty else ""),
            origem=[("abrir a execução", ult.get("url"))] if isinstance(ult.get("url"), str) else None)

    layout.secao("Dado bruto", "Os números batem com a aba Actions de cada repositório?", ["GITHUB"])
    _tabela_repos(runs, r, f)

    layout.secao("Análise", "A estabilidade da CI está melhorando?", ["GITHUB"])
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
