"""Qualidade técnica — fonte SONAR (SonarCloud)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.data import sonar as sn
from src.metrics import qualidade
from src.metrics.calculations import data_br, num, status_meta, variacao

SEM_API = ("o metrics.yml não traz esta métrica e a coleta da API do SonarCloud ainda não rodou",
           "rodar o workflow \"Coleta de dados do dashboard\" no GitHub Actions (ou "
           "`python scripts/coleta_sonar.py`), que grava `Analytics/data/sonar/`")

DESTAQUES = [  # (métrica, rótulo)
    ("coverage", "Cobertura"),
    ("bugs", "Bugs"),
    ("vulnerabilities", "Vulnerabilidades"),
    ("code_smells", "Code smells"),
    ("security_hotspots", "Security hotspots"),
    ("sqale_index", "Dívida técnica"),
    ("duplicated_lines_density", "Duplicação"),
    ("ncloc", "Linhas de código"),
]
RATINGS = [("reliability_rating", "Confiabilidade"), ("security_rating", "Segurança"),
           ("sqale_rating", "Manutenibilidade")]


def _repos_completos(ctx, curtos: list[str]) -> list[str]:
    todos = set(ctx.sonar_atual["repositorio"]) if not ctx.sonar_atual.empty else set()
    if not ctx.sonar_serie.empty:
        todos |= set(ctx.sonar_serie["repositorio"])
    return sorted(r for r in todos if not curtos or sn.nome_curto(r) in curtos)


def _kpi_metrica(serie, metrica, rotulo, repos, release):
    nome, unidade, maior_melhor = sn.METRICAS[metrica]
    a = sn.atual_e_anterior(serie, metrica, repos)
    if a["atual"] is None:
        kpi(rotulo, None, "SONAR", nota=f"{nome}: {SEM_API[0]}.")
        return
    agreg = {"mean": "média simples", "sum": "soma", "max": "pior"}[sn.agregacao(metrica)]
    kpi(rotulo, sn.formatar(metrica, a["atual"]), "SONAR",
        status=status_meta(metrica, a["atual"], release, maior_melhor) if metrica in ("coverage",
                                                                                      "duplicated_lines_density")
        else None,
        delta=variacao(a["atual"], a["anterior"], unidade, maior_melhor),
        nota=f"{agreg} de {a['n_repos']} repositório(s) · {data_br(a['data_atual'])}")


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Qualidade técnica", "Métricas de qualidade do código medidas pelo SonarCloud, por "
                         "repositório e ao longo do tempo.", ["SONAR"])
    api = ctx.sonar_api or {}
    layout.metodologia([
        ("Cobertura, duplicação, LOC, testes, ratings de confiabilidade e segurança",
         "SONAR — pipeline `metrics.yml` → `data/*.json` e API (`data/sonar/`)",
         "valor da última coleta de cada repositório; no cartão, média simples (%) ou soma (contagens) "
         "dos repositórios filtrados; ratings: o pior (A = 1 … E = 5)"),
        ("Bugs, vulnerabilidades, code smells, security hotspots, dívida técnica, Quality Gate, "
         "rating de manutenibilidade, problemas por severidade", "SONAR — API do SonarCloud (`scripts/coleta_sonar.py`)",
         "`api/measures/component`, `api/qualitygates/project_status`, `api/issues/search` (facetas)"),
        ("Dívida técnica", "SONAR — `sqale_index`", "minutos de esforço estimados pelo SonarCloud, exibidos em horas"),
        ("Atual → anterior → variação", "cálculo", "atual = último dia com coleta; anterior = o dia com coleta "
         "imediatamente antes; em % a variação é em pontos percentuais (p.p.)"),
        ("Evolução", "SONAR — cada execução do pipeline + histórico da API", "um ponto por dia; em cada dia, cada "
         "repositório entra com o último valor conhecido (sem interpolar)"),
        ("Metas", "plano de ensino (`config.METAS`)", "cobertura ≥ 85% (R1/R2) e ≥ 90% (R3); duplicação ≤ 5% / ≤ 3%"),
    ])

    if ctx.sonar_serie.empty and ctx.sonar_atual.empty:
        layout.indisponivel("Nenhuma métrica do SonarCloud encontrada",
                            "não há arquivos do pipeline em `Analytics/data/` nem snapshot em `Analytics/data/sonar/`.",
                            "rodar o workflow `metrics.yml` em cada repositório ou `scripts/coleta_sonar.py`.")
        return

    # ── filtros da página ──
    serie = ctx.sonar_serie
    atual = ctx.sonar_atual
    if f["branch"]:
        serie = serie[(serie["branch"] == f["branch"]) | (serie["origem"] == "api")]
    serie = filters.por_periodo(serie, "coleta", f["periodo"])
    qg = api.get("quality_gate", pd.DataFrame())
    sev = api.get("severidades", pd.DataFrame())
    lang = api.get("linguagens", pd.DataFrame())
    cols = st.columns(3)
    repos = _repos_completos(ctx, f["repos"])
    if not qg.empty:
        estados = sorted(qg["status"].unique())
        sel_qg = cols[0].multiselect("Quality Gate", estados, key="sonar_qg", placeholder="Todos")
        if sel_qg:
            repos = [r for r in repos if r in set(qg.loc[qg["status"].isin(sel_qg), "repositorio"])]
    if not lang.empty:
        sel_l = cols[1].multiselect("Linguagem", sorted(lang["linguagem"].unique()), key="sonar_lang",
                                    placeholder="Todas")
        if sel_l:
            repos = [r for r in repos if r in set(lang.loc[lang["linguagem"].isin(sel_l), "repositorio"])]
    sel_sev = []
    if not sev.empty:
        sel_sev = cols[2].multiselect("Severidade", [s for s in sn.SEVERIDADES if s in set(sev["severidade"])],
                                      format_func=lambda s: sn.SEVERIDADE_PT.get(s, s), key="sonar_sev",
                                      placeholder="Todas")
    if not repos:
        st.info("Nenhum repositório com métricas do Sonar para os filtros selecionados.")
        return

    if not ctx.sonar_erros.empty:
        sem = sorted({sn.nome_curto(r) for r in ctx.sonar_erros["repositorio"]} - {sn.nome_curto(r) for r in repos})
        if sem:
            layout.indisponivel(f"Sem métricas: {', '.join(sem)}",
                                "o pipeline roda nesses repositórios, mas a API do SonarCloud responde erro "
                                "(projeto não encontrado). Não é ausência de valor: é ausência de projeto.",
                                "criar o projeto no SonarCloud e rodar o `metrics.yml`.")

    # ── KPIs ──
    layout.secao("Indicadores atuais", "Como está a qualidade técnica agora, e mudou desde a última coleta?",
                 ["SONAR"])
    rel = f["release_metas"]
    linha1, linha2 = st.columns(4), st.columns(4)
    for col, (m, rot) in zip(list(linha1) + list(linha2), DESTAQUES):
        with col:
            _kpi_metrica(serie, m, rot, repos, rel)
    c = st.columns(4)
    with c[0]:
        if qg.empty:
            kpi("Quality Gate", None, "SONAR", nota="Situação do Quality Gate: " + SEM_API[0] + ".")
        else:
            q = qg[qg["repositorio"].isin(repos)]
            ok = int((q["status"] == "OK").sum())
            kpi("Quality Gate aprovado", f"{ok} de {len(q)}", "SONAR",
                status="good" if ok == len(q) else ("warning" if ok >= len(q) / 2 else "critical"),
                nota="repositórios com Quality Gate OK")
    for col, (m, rot) in zip(c[1:], RATINGS):
        with col:
            a = sn.atual_e_anterior(serie, m, repos)
            if a["atual"] is None:
                kpi(f"Rating de {rot.lower()}", None, "SONAR", nota=SEM_API[0] + ".")
            else:
                letra = sn.formatar(m, a["atual"])
                kpi(f"Rating de {rot.lower()}", letra, "SONAR",
                    status="good" if letra == "A" else ("warning" if letra in "BC" else "critical"),
                    delta=variacao(a["atual"], a["anterior"], "", False),
                    nota=f"pior entre {a['n_repos']} repositório(s) (A melhor, E pior)")

    # ── evolução ──
    layout.secao("Evolução das métricas", "A qualidade do código está melhorando ao longo do tempo?", ["SONAR"])
    disponiveis = [m for m in sn.METRICAS if m in set(serie["metrica"])]
    if not disponiveis:
        layout.indisponivel("Sem série temporal no período", "nenhuma coleta do Sonar no período selecionado.")
    else:
        padrao = "coverage" if "coverage" in disponiveis else disponiveis[0]
        metrica = st.selectbox("Métrica", disponiveis, index=disponiveis.index(padrao), key="sonar_metrica",
                               format_func=lambda m: sn.METRICAS[m][0])
        nome, unidade, _ = sn.METRICAS[metrica]
        ag = sn.serie_agregada(serie, metrica, repos)
        agreg = {"mean": "média simples", "sum": "soma", "max": "pior valor"}[sn.agregacao(metrica)]
        y_tit = f"{nome} ({unidade})" if unidade else nome
        if metrica == "sqale_index":
            ag = ag.assign(valor=ag["valor"] / 60)
            y_tit = "Dívida técnica (horas)"
        linha = (alt.Chart(ag).mark_line(color=theme.SERIES[0], strokeWidth=2,
                                         point=alt.OverlayMarkDef(size=60, filled=True, color=theme.SERIES[0]))
                 .encode(x=alt.X("dia:T", title="Data da coleta", axis=alt.Axis(format="%d/%m")),
                         y=alt.Y("valor:Q", title=y_tit),
                         tooltip=[alt.Tooltip("dia:T", title="Data", format="%d/%m/%Y"),
                                  alt.Tooltip("valor:Q", title=nome, format=",.1f"),
                                  alt.Tooltip("repos:Q", title="Repositórios")]))
        camadas = linha
        meta = config.METAS.get(metrica, {}).get(rel)
        if meta is not None:
            camadas = camadas + charts.regra_horizontal(meta, f"meta {rel}: {num(meta)}%", theme.STATUS["critical"])
        if not ag.empty:
            camadas = camadas + charts.marcos_release(ag["dia"].min(), ag["dia"].max())
        charts.mostrar(camadas, f"{nome} — {agreg} dos repositórios selecionados",
                       f"{y_tit} · {data_br(f['periodo'][0])} a {data_br(f['periodo'][1])} · um ponto por dia de coleta",
                       ag.rename(columns={"dia": "data", "repos": "repositórios"}),
                       nota="Linhas pontilhadas verticais: entregas das releases." if meta is None else
                       "Linha tracejada vermelha: meta da release. Pontilhadas verticais: entregas das releases.",
                       altura=280)

        por_repo = serie[(serie["metrica"] == metrica) & serie["repositorio"].isin(repos)].copy()
        if metrica == "sqale_index":
            por_repo["valor"] = por_repo["valor"] / 60
        if por_repo["repositorio"].nunique() > 1:
            por_repo["repo"] = por_repo["repositorio"].map(sn.nome_curto)
            multiplos = (alt.Chart(por_repo).mark_line(color=theme.SERIES[0], strokeWidth=1.5,
                                                       point=alt.OverlayMarkDef(size=30, filled=True,
                                                                                color=theme.SERIES[0]))
                         .encode(x=alt.X("dia:T", title=None, axis=alt.Axis(format="%d/%m", tickCount=4)),
                                 y=alt.Y("valor:Q", title=None),
                                 tooltip=[alt.Tooltip("repo:N", title="Repositório"),
                                          alt.Tooltip("dia:T", title="Data", format="%d/%m/%Y"),
                                          alt.Tooltip("valor:Q", title=nome, format=",.1f")])
                         .properties(width=210, height=110)
                         .facet(facet=alt.Facet("repo:N", title=None,
                                                header=alt.Header(labelColor=theme.INK["secondary"],
                                                                  labelFontSize=11, labelFontWeight=500)),
                                columns=4))
            st.altair_chart(charts.finalizar(multiplos, f"{nome} por repositório",
                                             f"{y_tit} · mesma escala vertical em todos os painéis"),
                            use_container_width=False, theme=None)

    # ── severidade e tipos ──
    layout.secao("Problemas abertos", "Onde estão os problemas e qual a gravidade deles?", ["SONAR"])
    if sev.empty:
        layout.indisponivel("Distribuição por severidade indisponível", SEM_API[0] + ".", SEM_API[1] + ".")
    else:
        s = sev[sev["repositorio"].isin(repos)]
        if sel_sev:
            s = s[s["severidade"].isin(sel_sev)]
        tot = (s.groupby("severidade", as_index=False)["quantidade"].sum()
               .assign(nome=lambda d: d["severidade"].map(sn.SEVERIDADE_PT)))
        ordem = [sn.SEVERIDADE_PT[x] for x in sn.SEVERIDADES]
        e, d = st.columns(2)
        with e:
            barras = (alt.Chart(tot).mark_bar(cornerRadiusEnd=4)
                      .encode(y=alt.Y("nome:N", sort=ordem, title=None), x=alt.X("quantidade:Q", title="Problemas"),
                              color=alt.Color("nome:N", sort=ordem, legend=None,
                                              scale=alt.Scale(domain=ordem, range=theme.SEQUENCIAL[6:1:-1])),
                              tooltip=[alt.Tooltip("nome:N", title="Severidade"),
                                       alt.Tooltip("quantidade:Q", title="Problemas")]))
            rot = barras.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(
                text="quantidade:Q", color=alt.value(theme.INK["secondary"]))
            charts.mostrar(barras + rot, "Problemas abertos por severidade", "quantidade · coleta atual da API",
                           tot[["nome", "quantidade"]].rename(columns={"nome": "severidade"}), altura=charts.altura_categorias(len(tot)))
        with d:
            tp = api.get("tipos", pd.DataFrame())
            tp = tp[tp["repositorio"].isin(repos)] if not tp.empty else tp
            if tp.empty:
                st.caption("Sem distribuição por tipo.")
            else:
                nomes_t = {"BUG": "Bug", "VULNERABILITY": "Vulnerabilidade", "CODE_SMELL": "Code smell",
                           "SECURITY_HOTSPOT": "Security hotspot"}
                pr = (tp.assign(repo=tp["repositorio"].map(sn.nome_curto), nome=tp["tipo"].map(nomes_t))
                      .groupby(["repo", "nome"], as_index=False)["quantidade"].sum())
                ordem_t = [v for v in nomes_t.values() if v in set(pr["nome"])]
                barras = (alt.Chart(pr).mark_bar(stroke=theme.INK["surface"], strokeWidth=2)
                          .encode(y=alt.Y("repo:N", title=None, sort="-x"),
                                  x=alt.X("quantidade:Q", title="Problemas abertos", stack=True),
                                  color=alt.Color("nome:N", title="Tipo", sort=ordem_t,
                                                  scale=charts.escala_series(ordem_t[:3])
                                                  if len(ordem_t) <= 3 else alt.Scale(range=theme.SEQUENCIAL[2:])),
                                  tooltip=[alt.Tooltip("repo:N", title="Repositório"),
                                           alt.Tooltip("nome:N", title="Tipo"),
                                           alt.Tooltip("quantidade:Q", title="Problemas")]))
                charts.mostrar(barras, "Composição dos problemas por repositório", "quantidade · coleta atual da API",
                               pr, altura=charts.altura_categorias(pr["repo"].nunique()))

    # ── placar por repositório ──
    layout.secao("Situação por repositório", "Quais repositórios precisam de atenção?", ["SONAR"])
    a = atual[atual["repositorio"].isin(repos)]
    if a.empty:
        st.caption("Sem métricas atuais.")
    else:
        pivo = a.pivot_table(index="repositorio", columns="metrica", values="valor", aggfunc="last")
        placar = pd.DataFrame(index=pivo.index)
        for m in ["coverage", "duplicated_lines_density", "bugs", "vulnerabilities", "code_smells",
                  "security_hotspots", "sqale_index", "reliability_rating", "security_rating", "sqale_rating",
                  "tests", "ncloc"]:
            placar[sn.METRICAS[m][0]] = pivo[m].map(lambda v, m=m: sn.formatar(m, v)) if m in pivo else "indisponível"
        if not qg.empty:
            placar["Quality Gate"] = qg.set_index("repositorio")["status"].reindex(placar.index).fillna("indisponível")
        placar["Última coleta"] = a.groupby("repositorio")["coleta"].max().map(lambda d: data_br(d, True))
        placar.index = placar.index.map(sn.nome_curto)
        st.dataframe(placar.reset_index().rename(columns={"repositorio": "Repositório"}),
                     use_container_width=True, hide_index=True)
        cond = api.get("condicoes", pd.DataFrame())
        if not cond.empty:
            falhas = cond[(cond["status"] == "ERROR") & cond["repositorio"].isin(repos)]
            if not falhas.empty:
                layout.tabela(falhas.assign(repositorio=falhas["repositorio"].map(sn.nome_curto)),
                              f"Condições do Quality Gate que falharam ({len(falhas)})")

    # ── cobertura por componente ──
    comp = ctx.sonar_componentes
    if not comp.empty:
        comp = comp[comp["repositorio"].isin(repos)]
        if f["branch"]:
            comp = comp[comp["branch"] == f["branch"]]
        cob = (comp[comp["metrica"] == "coverage"].sort_values("coleta")
               .drop_duplicates(["repositorio", "componente"], keep="last"))
        if not cob.empty:
            layout.secao("Cobertura por componente", "Onde o esforço de teste rende mais?", ["SONAR"])
            cob = cob.nsmallest(15, "valor").assign(repo=lambda d: d["repositorio"].map(sn.nome_curto))
            barras = (alt.Chart(cob).mark_bar(cornerRadiusEnd=4, color=theme.SERIES[0])
                      .encode(y=alt.Y("componente:N", sort="x", title=None),
                              x=alt.X("valor:Q", title="Cobertura (%)", scale=alt.Scale(domain=[0, 100])),
                              tooltip=[alt.Tooltip("repo:N", title="Repositório"),
                                       alt.Tooltip("componente:N", title="Componente"),
                                       alt.Tooltip("valor:Q", title="Cobertura (%)", format=".1f")]))
            rot = barras.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(
                text=alt.Text("valor:Q", format=".0f"))
            charts.mostrar(barras + rot, "Os 15 componentes com menor cobertura",
                           "cobertura de testes (%) · última coleta do pipeline",
                           cob[["repo", "componente", "valor"]].rename(columns={"valor": "cobertura (%)"}),
                           altura=charts.altura_categorias(len(cob), 24))

        # ── modelo de qualidade (prévia DA-R2) ──
        pipeline = ctx.sonar_pipeline[ctx.sonar_pipeline["repositorio"].isin(repos)]
        mq = qualidade.calcular(comp, pipeline)
        if not mq.empty:
            layout.secao("Modelo de qualidade agregado (prévia DA-R2)",
                         "Considerando todas as métricas juntas, qual a nota de cada repositório?",
                         ["SONAR", "CALCULADO"])
            st.caption("Cada métrica vira a proporção de arquivos dentro de um limiar (0 a 1), ponderada em "
                       "Manutenibilidade e Confiabilidade; total = 0,5 × M + 0,5 × C. Limiares e pesos herdados "
                       "de 2026.1 (`src/metrics/qualidade.py`) — a R2 pede que o time os valide e justifique.")
            ult = mq.sort_values("coleta").groupby("repositorio").tail(1).copy()
            ult["nota"] = ult["total"].map(qualidade.nota)
            ult["repositorio"] = ult["repositorio"].map(sn.nome_curto)
            st.dataframe(ult[["repositorio", "nota", "total", "manutenibilidade", "confiabilidade", "coleta"]]
                         .round({"total": 2, "manutenibilidade": 2, "confiabilidade": 2}), use_container_width=True, hide_index=True,
                         column_config={"total": st.column_config.ProgressColumn("Total (0 a 1)", min_value=0,
                                                                                 max_value=1, format="%.2f"),
                                        "coleta": st.column_config.DatetimeColumn("Coleta", format="DD/MM/YYYY")})
