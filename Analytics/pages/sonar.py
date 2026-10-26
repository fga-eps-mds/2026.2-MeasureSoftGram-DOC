"""Qualidade técnica — fonte SONAR (SonarCloud)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import charts, filters, layout, rastreio
from src.components.kpi import kpi
from src.data import sonar as sn

from src.metrics.calculations import data_br, num, status_meta, variacao

SEM_API = ("o metrics.yml não traz esta métrica e a coleta da API do SonarCloud ainda não rodou",
           "rodar o workflow \"Coleta de dados do dashboard\" no GitHub Actions (ou "
           "`python scripts/coleta_sonar.py`), que grava `Analytics/data/sonar/`")

ESCOPO = {
    "release": "metas de cobertura e duplicação da release",
    "periodo": "situação no fim do período (última coleta até lá); o gráfico de evolução mostra as coletas do "
               "período",
    "repos": "repositórios analisados",
    "branch": "coletas do pipeline desta branch (o snapshot da API é sempre da develop)",
}


def _menus(f):
    rel = f["release_metas"]
    metas = config.METAS
    layout.menus([
        ("Cobertura de testes", "% das linhas exercitadas pelos testes", "valor do SonarCloud por repositório; o cartão "
         "mostra o pior repositório e a média", [("SonarCloud", config.SONAR_URL + "/organizations/"
                                                  + config.SONAR_ORGANIZACAO + "/projects")]),
        ("Quality Gate", "portão de qualidade do SonarCloud: aprovado ou reprovado", "status do projeto na API",
         []),
        ("Bugs · vulnerabilidades", "problemas de confiabilidade e de segurança abertos", "soma dos repositórios", []),
        ("Dívida técnica", "tempo estimado para corrigir os code smells", "`sqale_index` em minutos, mostrado em horas",
         []),
        ("Duplicação", "% de linhas duplicadas", "valor do SonarCloud por repositório", []),
        ("Ratings (A a E)", "notas de confiabilidade, segurança e manutenibilidade", "A = melhor, E = pior; o painel "
         "mostra o pior repositório (não existe média de letra)", []),
        ("Variação", "mudança desde a coleta anterior", "atual − anterior; em % é em pontos percentuais (p.p.)", []),
    ], [
        *[(f"Cobertura mínima na {k}", f"{num(v)}%", "config.py · METAS['coverage']", rastreio.codigo())
          for k, v in metas["coverage"].items()],
        *[(f"Duplicação máxima na {k}", f"{num(v)}%", "config.py · METAS['duplicated_lines_density']",
           rastreio.codigo()) for k, v in metas["duplicated_lines_density"].items()],
        ("Metas usadas agora", rel, "release da barra lateral", None),
        ("Branch analisada", config.SONAR_BRANCH, "config.py · SONAR_BRANCH", rastreio.codigo()),
        ("Atenção / crítico", "até 10% abaixo da meta = atenção; mais = crítico", "calculations.status_meta",
         rastreio.codigo("src/metrics/calculations.py")),
    ], fontes=["SONAR", "CALCULADO"])


def _resumo(atual, serie, repos, qg, rel):
    atual = atual[atual["repositorio"].isin(repos)]
    k = st.columns(5)
    with k[0]:
        cob = atual[atual["metrica"] == "coverage"]
        if cob.empty:
            kpi("Cobertura (pior repositório)", None, "SONAR", nota=SEM_API[0] + ".")
        else:
            pior = cob.loc[cob["valor"].idxmin()]
            meta = config.METAS["coverage"].get(rel)
            abaixo = cob[cob["valor"] < meta] if meta is not None else cob.iloc[0:0]
            kpi("Cobertura (pior repositório)", f"{num(pior['valor'], 1)}%", "SONAR",
                status=status_meta("coverage", pior["valor"], rel, True),
                nota=f"{sn.nome_curto(pior['repositorio'])} · média {num(cob['valor'].mean(), 1)}% · "
                     f"{len(abaixo)} de {len(cob)} abaixo de {num(meta)}%",
                origem=[(sn.nome_curto(pior["repositorio"]), rastreio.sonar(pior["repositorio"]))])
    with k[1]:
        if qg.empty:
            kpi("Quality Gate", None, "SONAR", nota=SEM_API[0] + ".")
        else:
            q = qg[qg["repositorio"].isin(repos)]
            reprov = q[q["status"] != "OK"]
            kpi("Quality Gate aprovado", f"{len(q) - len(reprov)} de {len(q)}", "SONAR",
                status="good" if reprov.empty else ("warning" if len(reprov) <= len(q) / 2 else "critical"),
                nota="reprovados: " + ", ".join(sn.nome_curto(r) for r in reprov["repositorio"]) if len(reprov)
                else "todos aprovados",
                origem=[(sn.nome_curto(r), rastreio.sonar(r)) for r in reprov["repositorio"]] or None)
    for col, (m, rot) in zip(k[2:], [("bugs", "Bugs"), ("vulnerabilities", "Vulnerabilidades"),
                                     ("sqale_index", "Dívida técnica")]):
        with col:
            a = sn.atual_e_anterior(serie, m, repos)
            if a["atual"] is None:
                kpi(rot, None, "SONAR", nota=SEM_API[0] + ".")
                continue
            x = atual[atual["metrica"] == m]
            topo = x.loc[x["valor"].idxmax()] if not x.empty else None
            kpi(rot, sn.formatar(m, a["atual"]), "SONAR", delta=variacao(a["atual"], a["anterior"],
                                                                          sn.METRICAS[m][1], False),
                nota=f"soma de {a['n_repos']} repositórios" + (f" · maior: {sn.nome_curto(topo['repositorio'])} "
                                                               f"({sn.formatar(m, topo['valor'])})"
                                                               if topo is not None else ""),
                origem=[(sn.nome_curto(topo["repositorio"]), rastreio.sonar(topo["repositorio"]))]
                if topo is not None else None)


def _placar(ctx, api, atual, qg, repos):
    a = atual[atual["repositorio"].isin(repos)]
    if a.empty:
        st.caption("Sem métricas atuais.")
        return
    pivo = a.pivot_table(index="repositorio", columns="metrica", values="valor", aggfunc="last")
    placar = pd.DataFrame(index=pivo.index)
    placar["Repositório"] = [layout.link_celula(rastreio.sonar(r), sn.nome_curto(r)) for r in pivo.index]
    if not qg.empty:
        placar["Quality Gate"] = qg.set_index("repositorio")["status"].reindex(placar.index).fillna("—")
    for m in ["coverage", "duplicated_lines_density", "bugs", "vulnerabilities", "code_smells", "security_hotspots",
              "sqale_index", "reliability_rating", "security_rating", "sqale_rating", "tests", "ncloc"]:
        placar[sn.METRICAS[m][0]] = pivo[m].map(lambda v, m=m: sn.formatar(m, v)) if m in pivo else "—"
    placar["Última coleta"] = a.groupby("repositorio")["coleta"].max().map(lambda d: data_br(d, True))
    st.dataframe(placar.reset_index(drop=True), use_container_width=True, hide_index=True,
                 column_config={"Repositório": layout.coluna_link("Repositório", help="abre o projeto no SonarCloud")})
    st.download_button("Baixar CSV", placar.assign(Repositório=[sn.nome_curto(r) for r in placar.index])
                       .to_csv(index=False).encode("utf-8-sig"), file_name="sonar_por_repositorio.csv",
                       mime="text/csv", key="csv_sonar")
    cond = api.get("condicoes", pd.DataFrame()) if not qg.empty else pd.DataFrame()
    if not cond.empty:
        falhas = cond[(cond["status"] == "ERROR") & cond["repositorio"].isin(repos)]
        if not falhas.empty:
            layout.tabela(falhas.assign(repositorio=falhas["repositorio"].map(sn.nome_curto)),
                          f"Condições do Quality Gate que reprovaram ({len(falhas)})")


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Qualidade técnica", "Métricas de qualidade do código medidas pelo SonarCloud, por "
                         "repositório e ao longo do tempo.", ["SONAR"])
    api = ctx.sonar_api or {}
    _menus(f)

    if ctx.sonar_serie.empty and ctx.sonar_atual.empty:
        layout.indisponivel("Nenhuma métrica do SonarCloud encontrada",
                            "não há arquivos do pipeline em `Analytics/data/` nem snapshot em `Analytics/data/sonar/`.",
                            "rodar o workflow `metrics.yml` em cada repositório ou `scripts/coleta_sonar.py`.")
        return

    # ── filtros: globais (período, repositórios, branch) + os da página, todos na barra lateral ──
    rec = filters.sonar(ctx, f)
    serie, atual = rec["serie"], rec["atual"]
    qg = api.get("quality_gate", pd.DataFrame()) if rec["api_no_periodo"] else pd.DataFrame()
    lang = api.get("linguagens", pd.DataFrame())
    caixa = filters.da_pagina(f, ESCOPO)
    repos = rec["repos"]
    if not qg.empty:
        estados = sorted(qg["status"].unique())
        sel_qg = caixa.multiselect("Quality Gate", estados, key="sonar_qg", placeholder="Todos")
        if sel_qg:
            repos = [r for r in repos if r in set(qg.loc[qg["status"].isin(sel_qg), "repositorio"])]
    if not lang.empty:
        sel_l = caixa.multiselect("Linguagem", sorted(lang["linguagem"].unique()), key="sonar_lang",
                                  placeholder="Todas")
        if sel_l:
            repos = [r for r in repos if r in set(lang.loc[lang["linguagem"].isin(sel_l), "repositorio"])]
    disponiveis = [m for m in sn.METRICAS if m in set(serie["metrica"])] if not serie.empty else []
    metrica = None
    if disponiveis:
        padrao = "coverage" if "coverage" in disponiveis else disponiveis[0]
        metrica = caixa.selectbox("Métrica do gráfico de evolução", disponiveis, index=disponiveis.index(padrao),
                                  key="sonar_metrica", format_func=lambda m: sn.METRICAS[m][0])
    if not rec["api_no_periodo"] and api.get("quality_gate") is not None and not api["quality_gate"].empty:
        st.caption(f"Quality Gate e problemas por severidade não aparecem: o snapshot da API é posterior ao fim "
                   f"do período ({data_br(rec['fim'])}) e não tem histórico.")
    st.caption(f"Situação no fim do período ({data_br(rec['fim'])}) · {filters.resumo_ativos(f, ESCOPO)}")
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

    # ── resumo ──
    layout.secao("Resumo", "Como está a qualidade técnica agora, e mudou desde a última coleta?", ["SONAR"])
    rel = f["release_metas"]
    _resumo(atual, rec["serie_ate"], repos, qg, rel)

    # ── dado bruto ──
    layout.secao("Dado bruto", "Qual é a situação de cada repositório?", ["SONAR"])
    _placar(ctx, api, atual, qg, repos)

    layout.secao("Análise", "A qualidade está melhorando, e onde o teste rende mais?", ["SONAR"])
    _analise(ctx, f, rec, serie, repos, rel, metrica)
    st.caption("A nota de qualidade (modelo Q-Rapids, do arquivo à nota) está na página **Qualidade (Q-Rapids)**.")


def _analise(ctx, f, rec, serie, repos, rel, metrica):
    # ── evolução ──
    if not metrica:
        layout.indisponivel("Sem série temporal no período", "nenhuma coleta do Sonar no período selecionado.")
    else:
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


    # ── cobertura por componente ──
    # cobertura por arquivo: .json do pipeline + árvore da API do SonarCloud (component_tree), para o gráfico
    # não sumir em repositório sem .json recente do metrics.yml; a coleta mais recente de cada arquivo vale
    partes = [x.assign(origem=o) for x, o in ((ctx.sonar_componentes, "pipeline"),
                                               ((ctx.sonar_api or {}).get("arquivos", pd.DataFrame()), "api"))
              if x is not None and not x.empty]
    comp = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    if not comp.empty:
        comp = comp[comp["repositorio"].isin(repos)]
        if f["branch"]:
            comp = comp[(comp["branch"] == f["branch"]) | (comp["origem"] == "api")]
        comp = comp[pd.to_datetime(comp["coleta"]) <= rec["fim"] + pd.Timedelta(days=1)]
        cob = (comp[(comp["metrica"] == "coverage") & (comp["tipo"] == "FIL")].sort_values("coleta")
               .drop_duplicates(["repositorio", "componente"], keep="last"))
        if not cob.empty:
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
                           "cobertura de testes (%) · última coleta do pipeline ou da API do SonarCloud",
                           cob[["repo", "componente", "valor"]].rename(columns={"valor": "cobertura (%)"}),
                           altura=charts.altura_categorias(len(cob), 24))

