"""Dashboard Gerencial e Analítico — MeasureSoftGram EPS 2026.2.

Regra que governa este app: **todo número exibido vem de arquivo gerado
automaticamente pelo pipeline**. Quando um dado não existe, o painel diz que
não existe e por quê — nunca preenche com estimativa. Um indicador ausente e
declarado é informação; um indicador inventado é ruído.

Rodar:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import gestao, qualidade, theme
from src.loader import (
    carregar_evm,
    carregar_issues,
    coletas_com_erro,
    carregar_runs,
    carregar_sonar,
    carregar_tabela,
    carregar_velocity,
    ultimo_por_repo,
)

RAIZ = Path(__file__).resolve().parent

# `Analytics/data/` é o destino padrão dos workflows, herdado de 2026.1.
# `analytics-raw-data/` na raiz é o destino de dois repositórios que ainda não
# foram padronizados — lemos os dois para não ficar cego em nenhum.
DADOS_BRUTOS = [RAIZ / "data", RAIZ.parent / "analytics-raw-data"]

# Planilhas do time. Ficam fora de `data/`, que é território do pipeline.
PLANILHAS_LOCAIS = RAIZ / "planilhas"

st.set_page_config(page_title="Dashboard Analítico — MeasureSoftGram EPS 2026.2",
                   page_icon="📊", layout="wide")

alt.data_transformers.disable_max_rows()


def finalizar(chart):
    """Chrome comum: grade discreta, eixos recessivos, sem moldura.

    Aplicado sempre no gráfico de nível mais alto — em Altair, `configure_*`
    só é válido no topo, nunca numa camada interna.
    """
    return (
        chart
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True, gridColor=theme.INK["grid"], gridOpacity=0.9,
            domainColor=theme.INK["axis"], tickColor=theme.INK["axis"],
            labelColor=theme.INK["muted"], titleColor=theme.INK["secondary"],
            labelFontSize=11, titleFontSize=11,
        )
        .configure_legend(labelColor=theme.INK["secondary"],
                          titleColor=theme.INK["secondary"], labelFontSize=11)
    )


def tabela(df: pd.DataFrame, rotulo: str = "Ver os dados em tabela") -> None:
    """Visão tabular ao lado de todo gráfico (exigência de acessibilidade)."""
    with st.expander(rotulo):
        st.dataframe(df, use_container_width=True, hide_index=True)


# Datas das releases major (plano de ensino 2026.2), marcadas nos gráficos de tendência.
RELEASES = pd.DataFrame({"data": pd.to_datetime(["2026-09-28", "2026-10-26", "2026-11-30"]),
                         "release": ["R1", "R2", "R3"]})


def linhas_de_release(inicio, fim):
    """Réguas verticais nas datas de release que caem dentro do período mostrado."""
    d = RELEASES[(RELEASES["data"] >= pd.Timestamp(inicio) - pd.Timedelta(days=3))
                 & (RELEASES["data"] <= pd.Timestamp(fim) + pd.Timedelta(days=10))]
    regra = (alt.Chart(d).mark_rule(strokeDash=[2, 3], color=theme.SERIES[1], strokeWidth=1.5)
             .encode(x="data:T"))
    texto = (alt.Chart(d).mark_text(align="left", dx=4, dy=-110, fontSize=11, color=theme.SERIES[1])
             .encode(x="data:T", text="release:N"))
    return regra + texto


def aviso_sem_dado(titulo: str, motivo: str, como_resolver: str) -> None:
    st.warning(f"**{titulo}**\n\n{motivo}\n\n**Como resolver:** {como_resolver}")


# ───────────────────────── carga ─────────────────────────

@st.cache_data(show_spinner="Lendo os arquivos do pipeline...")
def carregar_tudo(pastas: tuple[str, ...]):
    p = [Path(x) for x in pastas]
    agregado, componentes = carregar_sonar(p)
    return agregado, componentes, carregar_issues(p), carregar_runs(p), coletas_com_erro(p)


agregado, componentes, issues, runs, erros_sonar = carregar_tudo(
    tuple(str(p) for p in DADOS_BRUTOS))

@st.cache_data(ttl=config.CACHE_PLANILHAS_S, show_spinner="Lendo as planilhas do time...")
def carregar_planilha(chave: str, colunas: tuple[str, ...]):
    return carregar_tabela(config.PLANILHAS.get(chave, ""),
                           PLANILHAS_LOCAIS / f"{chave}.csv", list(colunas))


@st.cache_data(ttl=config.CACHE_PLANILHAS_S, show_spinner="Lendo o EVM...")
def carregar_planilha_evm():
    return carregar_evm(config.PLANILHAS.get("evm", ""), PLANILHAS_LOCAIS / "evm.csv")


@st.cache_data(ttl=config.CACHE_PLANILHAS_S, show_spinner="Lendo a velocity...")
def carregar_planilha_velocity():
    return carregar_velocity(config.PLANILHAS.get("velocity", ""),
                             PLANILHAS_LOCAIS / "velocity.csv")


# A aba de EVM segue o layout AgileEVM herdado de 2026.1: três linhas de
# cabeçalho e valores em moeda BR. Por isso tem leitor próprio, e não o
# `carregar_tabela` genérico.
evm, origem_evm = carregar_planilha_evm()
velocity, origem_velocity = carregar_planilha_velocity()
riscos, origem_riscos = carregar_planilha(
    "riscos", ("id", "categoria", "risco", "causa", "consequencia", "gatilho",
               "probabilidade", "impacto", "resposta", "prevencao", "contingencia",
               "responsavel", "status", "ultima_revisao"))
decisoes, origem_decisoes = carregar_planilha(
    "decisoes", ("data", "metrica", "causa", "decisao", "resultado"))


# Modelo de gestão (calendário, linha de base, Zenhub, horas). Ver src/gestao.py.
HOJE = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize()
gestao.URLS = config.PLANILHAS
params = gestao.carregar_parametros(PLANILHAS_LOCAIS)
cal_sprints, cal_releases = gestao.carregar_calendario(PLANILHAS_LOCAIS)
horas_reais = gestao.carregar_horas(PLANILHAS_LOCAIS)
zh_issues, zh_resumo, zh_arquivo = gestao.carregar_zenhub(RAIZ / "data" / "zenhub")
zh_issues_cal = (zh_issues.merge(cal_sprints[["zenhub_sprint_id", "sprint"]], on="zenhub_sprint_id")
                 if not zh_issues.empty and not cal_sprints.empty else zh_issues)
vel_zh = gestao.velocity_por_sprint(cal_sprints, zh_issues, params, HOJE) if not cal_sprints.empty else pd.DataFrame()
evm_zh = gestao.agile_evm(cal_sprints, cal_releases, zh_issues, horas_reais, params, HOJE) if not cal_sprints.empty else pd.DataFrame()

# ───────────────────────── cabeçalho ─────────────────────────

st.title("Dashboard Gerencial e Analítico")
st.caption("MeasureSoftGram · Engenharia de Produto de Software · 2026.2")

if agregado.empty:
    aviso_sem_dado(
        "Nenhuma métrica do SonarCloud encontrada",
        "Nenhuma das pastas `analytics-raw-data/` ou `Analytics/data/` tem "
        "arquivos no formato esperado.",
        "Rodar o workflow `metrics.yml` (via *workflow_dispatch*) em cada "
        "repositório e conferir se ele publica neste repositório de documentação.",
    )
    st.stop()

repos = sorted(agregado["repositorio"].unique())
with st.sidebar:
    st.header("Filtros")
    repos_sel = st.multiselect("Repositórios", repos, default=repos)
    branches = sorted(agregado["branch"].unique())
    branch_sel = st.selectbox("Branch", branches,
                              index=branches.index("develop") if "develop" in branches else 0)
    release = st.radio("Metas da release", ["R1", "R2", "R3"], horizontal=True)
    st.divider()
    st.caption(f"Última coleta: **{agregado['coleta'].max():%d/%m/%Y %H:%M}**")
    st.caption(f"{agregado['arquivo'].nunique()} arquivos · {len(repos)} repositório(s)")

filtro = agregado[(agregado["repositorio"].isin(repos_sel)) &
                  (agregado["branch"] == branch_sel)]
comp_filtro = componentes[(componentes["repositorio"].isin(repos_sel)) &
                          (componentes["branch"] == branch_sel)]

if len(repos) < 6:
    st.info(
        f"**Cobertura parcial do ecossistema.** Há métricas de {len(repos)} de 8 "
        "repositórios. Os demais têm `metrics.yml`, mas publicam em repositórios "
        "de semestres anteriores — ver a issue de organização dos repositórios.",
        icon="⚠️",
    )

aba_produto, aba_processo, aba_projeto, aba_decisoes = st.tabs(
    ["Produto", "Processo", "Projeto", "Decisões"]
)

# ───────────────────────── produto ─────────────────────────

with aba_produto:
    st.subheader("Qualidade do produto")
    st.caption("Fonte: SonarCloud, via `metrics.yml`. Metas conforme os critérios da release.")

    if not erros_sonar.empty:
        faltantes = ", ".join(sorted(erros_sonar["repositorio"].unique()))
        with st.expander(f"⚠️ {erros_sonar['repositorio'].nunique()} repositório(s) "
                         "coletam mas não têm projeto no SonarCloud"):
            st.markdown(
                f"O workflow roda em **{faltantes}** e grava o arquivo, mas a API "
                "responde erro em vez de métrica. O painel não pode mostrar "
                "qualidade desses repositórios — não é ausência de dado, é "
                "ausência de projeto no SonarCloud."
            )
            st.dataframe(erros_sonar, use_container_width=True, hide_index=True)

    ultimo = ultimo_por_repo(filtro)
    destaque = ["coverage", "duplicated_lines_density", "test_success_density", "tests"]
    colunas = st.columns(len(destaque))
    for coluna, metrica in zip(colunas, destaque):
        linha = ultimo[ultimo["metrica"] == metrica]
        if linha.empty:
            coluna.metric(theme.METRICAS.get(metrica, (metrica,))[0], "—")
            continue
        valor = linha["valor"].mean()
        rotulo, unidade, _ = theme.METRICAS.get(metrica, (metrica, "", None))
        status = theme.status_por_meta(metrica, valor, release)
        meta = theme.METAS.get(metrica, {}).get(release)
        icone = {"good": "✅", "warning": "⚠️", "critical": "🔴"}.get(status, "")
        coluna.metric(rotulo, f"{valor:.1f}{unidade}",
                      delta=f"{icone} meta {meta:.0f}{unidade}" if meta else None,
                      delta_color="off")

    st.divider()
    st.markdown("#### Evolução da cobertura de testes")

    cobertura = filtro[filtro["metrica"] == "coverage"].sort_values("coleta")
    if cobertura["coleta"].nunique() < 2:
        st.caption(
            "Só há uma data de coleta — a série temporal aparece quando o "
            "pipeline rodar novamente. Cada execução do `metrics.yml` vira um ponto."
        )
    meta_cob = theme.METAS["coverage"][release]
    linha = (
        alt.Chart(cobertura)
        .mark_line(point=alt.OverlayMarkDef(size=90, filled=True), strokeWidth=2)
        .encode(
            x=alt.X("coleta:T", title="Coleta"),
            y=alt.Y("valor:Q", title="Cobertura (%)",
                    scale=alt.Scale(domain=[0, 100], nice=False)),
            color=alt.Color(
                "repositorio:N", title="Repositório",
                scale=alt.Scale(range=theme.SERIES),
                legend=alt.Legend() if cobertura["repositorio"].nunique() > 1 else None,
            ),
            tooltip=[alt.Tooltip("repositorio:N", title="Repositório"),
                     alt.Tooltip("coleta:T", title="Coleta", format="%d/%m %H:%M"),
                     alt.Tooltip("valor:Q", title="Cobertura", format=".1f")],
        )
    )
    regra = (
        alt.Chart(pd.DataFrame({"meta": [meta_cob]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=2, color=theme.STATUS["critical"])
        .encode(y="meta:Q")
    )
    rotulo_meta = (
        alt.Chart(pd.DataFrame({"meta": [meta_cob], "texto": [f"meta {release}: {meta_cob:.0f}%"]}))
        .mark_text(align="left", dx=6, dy=-8, fontSize=11, color=theme.STATUS["critical"])
        .encode(y="meta:Q", text="texto:N")
    )
    camadas = linha + regra + rotulo_meta
    if not cobertura.empty:
        camadas = camadas + linhas_de_release(cobertura["coleta"].min(), cobertura["coleta"].max())
    st.altair_chart(finalizar(camadas.properties(height=320)), use_container_width=True)
    tabela(cobertura[["repositorio", "branch", "coleta", "valor"]]
           .rename(columns={"valor": "cobertura (%)"}))

    st.markdown("#### Cobertura por componente")
    cob_comp = (comp_filtro[comp_filtro["metrica"] == "coverage"]
                .sort_values("coleta")
                .drop_duplicates(["repositorio", "componente"], keep="last"))
    if cob_comp.empty:
        st.caption("O SonarCloud não reportou cobertura por componente nesta coleta.")
    else:
        cob_comp = cob_comp.nsmallest(15, "valor")
        barras = (
            alt.Chart(cob_comp)
            .mark_bar(cornerRadiusEnd=4, size=14)
            .encode(
                y=alt.Y("componente:N", sort="x", title=None),
                x=alt.X("valor:Q", title="Cobertura (%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.value(theme.SERIES[0]),
                tooltip=[alt.Tooltip("componente:N", title="Componente"),
                         alt.Tooltip("valor:Q", title="Cobertura", format=".1f")],
            )
        )
        rotulos = barras.mark_text(align="left", dx=4, fontSize=11,
                                   color=theme.INK["secondary"]).encode(
            text=alt.Text("valor:Q", format=".0f"))
        st.altair_chart(
            finalizar((barras + rotulos).properties(height=28 * len(cob_comp) + 30)),
            use_container_width=True)
        st.caption("Os 15 componentes com menor cobertura — onde o esforço de teste rende mais.")
        tabela(cob_comp[["repositorio", "componente", "valor"]]
               .rename(columns={"valor": "cobertura (%)"}))

    st.divider()
    st.markdown("#### Modelo de qualidade agregado (prévia do DA-R2)")
    st.caption(
        "Cada métrica vira a proporção de arquivos dentro de um limiar (0 a 1), "
        "ponderada em Manutenibilidade e Confiabilidade. Limiares e pesos herdados de "
        "2026.1 (`src/qualidade.py`); a R2 pede que o time os valide e justifique."
    )
    mq = qualidade.calcular(comp_filtro, filtro)
    if mq.empty:
        st.caption("Sem métricas por arquivo nesta coleta.")
    else:
        atual = mq.sort_values("coleta").groupby("repositorio").tail(1)
        cols_q = st.columns(min(len(atual), 6))
        for col, linha_q in zip(cols_q, atual.itertuples()):
            col.metric(linha_q.repositorio.replace("2026.2-MeasureSoftGram-", ""),
                       f"{qualidade.nota(linha_q.total)} · {linha_q.total:.2f}",
                       f"M {linha_q.manutenibilidade:.2f} · C {linha_q.confiabilidade:.2f}",
                       delta_color="off")
        longo_q = mq.melt(id_vars=["repositorio", "coleta"],
                          value_vars=["manutenibilidade", "confiabilidade", "total"],
                          var_name="fator", value_name="valor")
        graf_q = (alt.Chart(longo_q[longo_q["fator"] == "total"])
                  .mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=2)
                  .encode(x=alt.X("coleta:T", title="Coleta"),
                          y=alt.Y("valor:Q", title="Nota total (0 a 1)", scale=alt.Scale(domain=[0, 1])),
                          color=alt.Color("repositorio:N", title="Repositório"),
                          tooltip=["repositorio:N", alt.Tooltip("coleta:T", format="%d/%m %H:%M"),
                                   alt.Tooltip("valor:Q", format=".2f")]))
        graf_q = graf_q + linhas_de_release(mq["coleta"].min(), mq["coleta"].max())
        st.altair_chart(finalizar(graf_q.properties(height=300)), use_container_width=True)
        tabela(atual.drop(columns=["branch"]).round(3), "Ver os fatores da última coleta")

    st.markdown("#### Todas as métricas da última coleta")
    pivo = (ultimo.pivot_table(index="repositorio", columns="metrica", values="valor")
            .rename(columns={k: v[0] for k, v in theme.METRICAS.items()}))
    st.dataframe(pivo, use_container_width=True)

# ───────────────────────── processo ─────────────────────────

with aba_processo:
    st.subheader("Processo de desenvolvimento")
    st.caption("Fonte: API do GitHub, coletada pelo mesmo pipeline.")

    st.markdown("#### Saúde da integração contínua")
    if runs.empty:
        aviso_sem_dado(
            "Sem dados de execução de CI",
            "Nenhum arquivo `GitHub_API-Runs-*.json` foi encontrado.",
            "Rodar o `metrics.yml` novamente — ele coleta as execuções junto das métricas.",
        )
    else:
        runs_f = runs[runs["repositorio"].isin(repos_sel)]
        concluidas = runs_f[runs_f["conclusao"].notna()]
        if concluidas.empty:
            st.caption("As execuções coletadas ainda estavam em andamento.")
        else:
            total = len(concluidas)
            sucesso = (concluidas["conclusao"] == "success").sum()
            taxa = 100 * sucesso / total
            c1, c2, c3 = st.columns(3)
            c1.metric("Execuções concluídas", total)
            c2.metric("Taxa de sucesso", f"{taxa:.0f}%",
                      delta="🔴 abaixo de 80%" if taxa < 80 else "✅", delta_color="off")
            c3.metric("Falhas", int(total - sucesso))

            if taxa < 80:
                st.error(
                    f"**{total - sucesso} de {total} execuções falharam.** Uma CI instável "
                    "invalida o portão de qualidade exigido na R1: se o pipeline falha "
                    "com frequência, o time aprende a ignorá-lo.",
                    icon="🔴",
                )

            por_wf = (concluidas.groupby(["workflow", "conclusao"])
                      .size().reset_index(name="execucoes"))
            cores = alt.Scale(domain=["success", "failure"],
                              range=[theme.STATUS["good"], theme.STATUS["critical"]])
            barras = (
                alt.Chart(por_wf)
                .mark_bar(cornerRadiusEnd=4, size=18, stroke="#fcfcfb", strokeWidth=2)
                .encode(
                    y=alt.Y("workflow:N", title=None, sort="-x"),
                    x=alt.X("execucoes:Q", title="Execuções", stack=True),
                    color=alt.Color("conclusao:N", title="Conclusão", scale=cores),
                    tooltip=["workflow:N", "conclusao:N", "execucoes:Q"],
                )
            )
            st.altair_chart(
                finalizar(barras.properties(height=32 * por_wf["workflow"].nunique() + 40)),
                use_container_width=True)
            tabela(por_wf)

            st.markdown("##### Sucesso e falha por repositório")
            por_repo = (concluidas.assign(repo=concluidas["repositorio"].str.replace("2026.2-MeasureSoftGram-", ""))
                        .groupby(["repo", "conclusao"]).size().reset_index(name="execucoes"))
            barras_r = (alt.Chart(por_repo)
                        .mark_bar(cornerRadiusEnd=4, size=18, stroke="#fcfcfb", strokeWidth=2)
                        .encode(y=alt.Y("repo:N", title=None, sort="-x"),
                                x=alt.X("execucoes:Q", title="Execuções", stack=True),
                                color=alt.Color("conclusao:N", title="Conclusão",
                                                scale=alt.Scale(domain=["success", "failure", "cancelled", "skipped"],
                                                                range=[theme.STATUS["good"], theme.STATUS["critical"],
                                                                       theme.STATUS["warning"], theme.INK["muted"]])),
                                tooltip=["repo:N", "conclusao:N", "execucoes:Q"]))
            st.altair_chart(finalizar(barras_r.properties(height=32 * por_repo["repo"].nunique() + 40)),
                            use_container_width=True)
            tabela(por_repo)

            if "duracao_min" in concluidas and concluidas["duracao_min"].notna().any():
                st.markdown("##### Tempo de feedback da CI")
                st.caption("Duração de cada execução (início ao fim), em minutos. "
                           "Feedback lento desestimula rodar a CI antes do merge.")
                dur = (concluidas.dropna(subset=["duracao_min"])
                       .assign(repo=lambda d: d["repositorio"].str.replace("2026.2-MeasureSoftGram-", ""),
                               quando=lambda d: d["criado_em"].dt.tz_localize(None)))
                c1, c2 = st.columns(2)
                c1.metric("Duração mediana", f"{dur['duracao_min'].median():.1f} min")
                c2.metric("Execução mais lenta", f"{dur['duracao_min'].max():.1f} min")
                pontos = (alt.Chart(dur).mark_circle(size=55, opacity=0.8)
                          .encode(x=alt.X("quando:T", title="Execução"),
                                  y=alt.Y("duracao_min:Q", title="Minutos"),
                                  color=alt.Color("repo:N", title="Repositório"),
                                  tooltip=["repo:N", "workflow:N", "conclusao:N",
                                           alt.Tooltip("quando:T", format="%d/%m %H:%M"),
                                           alt.Tooltip("duracao_min:Q", format=".1f")]))
                pontos = pontos + linhas_de_release(dur["quando"].min(), dur["quando"].max())
                st.altair_chart(finalizar(pontos.properties(height=280)), use_container_width=True)

    st.divider()
    st.markdown("#### Fluxo de issues")
    if issues.empty:
        aviso_sem_dado(
            "Sem dados de issues",
            "O arquivo `GitHub_API-Issues-*.json` está vazio. Ele foi coletado antes "
            "de o time abrir as issues do semestre, e ainda não foi atualizado.",
            "Rodar o `metrics.yml` novamente — as issues já existentes serão coletadas.",
        )
        st.caption(
            "**Velocity e burndown dependem de estimativa em pontos.** Sem pontos nas "
            "issues do ZenHub, o painel mede contagem de issues, não velocidade — e "
            "essa limitação precisa estar declarada aqui, não escondida."
        )
    else:
        issues_f = issues[issues["repositorio"].isin(repos_sel)]
        abertas = (issues_f["estado"] == "open").sum()
        fechadas = (issues_f["estado"] == "closed").sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Abertas", int(abertas))
        c2.metric("Fechadas", int(fechadas))
        lead = issues_f["lead_time_dias"].median()
        c3.metric("Lead time mediano", f"{lead:.1f} d" if pd.notna(lead) else "—")

        serie = (issues_f.dropna(subset=["criada_em"])
                 .assign(semana=lambda d: d["criada_em"].dt.to_period("W").dt.start_time)
                 .groupby(["semana", "estado"]).size().reset_index(name="issues"))
        grafico = (
            alt.Chart(serie)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("semana:T", title="Semana"),
                y=alt.Y("issues:Q", title="Issues"),
                color=alt.Color("estado:N", title="Estado",
                                scale=alt.Scale(range=theme.SERIES[:2])),
                tooltip=["semana:T", "estado:N", "issues:Q"],
            )
        )
        st.altair_chart(finalizar(grafico.properties(height=300)), use_container_width=True)
        tabela(serie)

# ───────────────────────── projeto ─────────────────────────

with aba_projeto:
    st.subheader("Projeto")
    st.caption(
        f"Fonte do EVM: **{origem_evm}** · Fonte dos riscos: **{origem_riscos}**. "
        "Preenchimento manual, porque custo e risco não são coletáveis de "
        "repositório. Configure as URLs das planilhas em `config.py`."
    )

    # ── Linha de base e calendário ──
    st.markdown("#### Linha de base da release")
    if cal_sprints.empty or cal_releases.empty:
        aviso_sem_dado("Sem calendário", "`planilhas/sprints.csv` ou `releases.csv` não encontrado.",
                       "Restaurar os arquivos do calendário oficial (o do Zenhub).")
    else:
        atual = cal_sprints[(cal_sprints["inicio"] <= HOJE)].tail(1)
        rel_atual = atual["release"].iloc[0] if not atual.empty else cal_releases["release"].iloc[0]
        e_rel = evm_zh[(evm_zh["release"] == rel_atual) & evm_zh["iniciada"]] if not evm_zh.empty else pd.DataFrame()
        c1, c2, c3, c4 = st.columns(4)
        entrega = cal_releases.loc[cal_releases["release"] == rel_atual, "entrega"].iloc[0]
        c1.metric("Release em curso", rel_atual, f"entrega {entrega:%d/%m}", delta_color="off")
        if not e_rel.empty:
            ult = e_rel.iloc[-1]
            c2.metric("Sprint da release", f"{int(ult['n'])} de {int(ult['L'])}")
            c3.metric("PRP (pontos da release)", f"{ult['PRP']:.0f}",
                      ult["linha_de_base"], delta_color="off")
            c4.metric("Pontos em Done", f"{ult['RPC']:.0f}",
                      f"APC {ult['APC']:.0%}" if pd.notna(ult["APC"]) else "APC —", delta_color="off")
            if ult["linha_de_base"] == "reconstituída":
                st.info(
                    f"**A {rel_atual} não tem linha de base declarada.** O PRP foi reconstituído "
                    "com todos os pontos que entraram nas sprints da release no Zenhub. "
                    "Isso é consequência do sequenciador da Lean Inception não ter fechado "
                    "(risco R10, materializado). A partir da próxima release, o PRP é "
                    "congelado na planning de abertura em `planilhas/releases.csv` e todo "
                    "ponto que passar dele aparece como PA (escopo adicionado).", icon="ℹ️")
        st.caption("Fontes: " + " · ".join(f"{k}: **{v}**" for k, v in gestao.ORIGEM.items()) + ". "
                   f"Calendário oficial: o do Zenhub. "
                   f"Snapshot do quadro: `{zh_arquivo or 'nenhum'}`. "
                   f"Critério de feito: pipeline **{params['criterio_feito']}**. "
                   f"Tipos pontuados: {', '.join(sorted(params['tipos_pontuados']))}.")

    # ── Higiene do quadro ──
    st.divider()
    st.markdown("#### Confiabilidade do dado do Zenhub")
    problemas = gestao.qualidade_do_quadro(zh_issues, params)
    if zh_issues.empty:
        aviso_sem_dado("Sem snapshot do Zenhub", "Nenhum `data/zenhub/zenhub-sprints-*.json`.",
                       "Rodar `python scripts/coleta_zenhub.py` com `ZENHUB_TOKEN` definido.")
    elif problemas.empty:
        st.success("Nenhum problema de estimativa ou de pipeline nas sprints coletadas.", icon="✅")
    else:
        contagem = problemas["problema"].str.replace(r"\s*\(.*|'.*", "", regex=True).value_counts()
        cols = st.columns(min(4, len(contagem)))
        for col, (nome, qtd) in zip(cols, contagem.items()):
            col.metric(nome, int(qtd))
        st.warning(
            "**Velocity e EVM só são tão bons quanto o quadro.** Issue sem estimativa não "
            "conta ponto; issue fechada fora do pipeline Done não conta como entregue; "
            "pontos em Epic ou Sub-task seriam contados duas vezes. Cada linha abaixo é "
            "uma ação para a próxima planning.", icon="⚠️")
        with st.expander(f"Ver as {len(problemas)} pendências"):
            st.dataframe(problemas, use_container_width=True, hide_index=True,
                         column_config={"url": st.column_config.LinkColumn("link")})

    # ── Velocity ──
    st.divider()
    st.markdown("#### Velocity")
    st.caption("Fonte: Zenhub. PP = pontos comprometidos na sprint · PC = pontos no pipeline Done.")
    if vel_zh.empty or vel_zh["pp"].sum() == 0:
        aviso_sem_dado("Sem pontos estimados", "Nenhuma sprint iniciada tem issues estimadas.",
                       "Estimar as US e Tasks da sprint em planning poker.")
    else:
        encerradas = vel_zh[vel_zh["encerrada"]]
        media = encerradas["pc"].mean() if not encerradas.empty else float("nan")
        c1, c2, c3 = st.columns(3)
        c1.metric("Velocity média (sprints encerradas)", f"{media:.1f} pts" if pd.notna(media) else "—")
        c2.metric("Comprometido na última sprint", f"{vel_zh['pp'].iloc[-1]:.0f} pts")
        taxa = vel_zh["pc"].sum() / vel_zh["pp"].sum() if vel_zh["pp"].sum() else float("nan")
        c3.metric("Taxa de conclusão (PC/PP)", f"{taxa:.0%}" if pd.notna(taxa) else "—",
                  "meta ≥ 80%", delta_color="off")
        longo_v = vel_zh.melt(id_vars=["sprint"], value_vars=["pp", "pc"],
                              var_name="serie", value_name="pontos")
        longo_v["serie"] = longo_v["serie"].map({"pp": "Comprometido (PP)", "pc": "Concluído (PC)"})
        barras = (
            alt.Chart(longo_v).mark_bar()
            .encode(x=alt.X("sprint:O", title="Sprint"),
                    y=alt.Y("pontos:Q", title="Story points"),
                    xOffset=alt.XOffset("serie:N"),
                    color=alt.Color("serie:N", title="",
                                    scale=alt.Scale(domain=["Comprometido (PP)", "Concluído (PC)"],
                                                    range=theme.SERIES[:2])),
                    tooltip=["sprint:O", "serie:N", "pontos:Q"]))
        media_acum = vel_zh.assign(media=vel_zh["pc"].expanding().mean())
        linha_media = (alt.Chart(media_acum)
                       .mark_line(point=alt.OverlayMarkDef(shape="diamond", size=70, filled=True),
                                  strokeDash=[6, 4], color=theme.STATUS["serious"], strokeWidth=2)
                       .encode(x="sprint:O", y="media:Q",
                               tooltip=["sprint:O", alt.Tooltip("media:Q", title="média acumulada", format=".1f")]))
        st.altair_chart(finalizar((barras + linha_media).properties(height=300)), use_container_width=True)
        st.caption("Linha tracejada: velocity média acumulada (PC médio até a sprint). "
                   "É a base para projetar quantas sprints o backlog restante consome.")
        tabela(media_acum)

    # ── Burndown ──
    st.divider()
    st.markdown("#### Burndown da release")
    if evm_zh.empty:
        st.caption("Sem dados.")
    else:
        rel_sel = st.radio("Release", sorted(evm_zh["release"].unique()), horizontal=True,
                           key="burndown_release")
        bd = gestao.burndown_release(evm_zh, rel_sel)
        bd_ini = bd[bd["iniciada"]]
        if bd_ini.empty or bd_ini["PRP"].fillna(0).max() == 0:
            st.caption(f"A {rel_sel} ainda não tem pontos estimados em sprints iniciadas.")
        else:
            longo_b = pd.concat([
                bd_ini.assign(serie="Restante (real)", valor=bd_ini["restante"])[["sprint", "serie", "valor"]],
                bd.assign(serie="Ideal", valor=bd["ideal"])[["sprint", "serie", "valor"]],
            ])
            linha = (alt.Chart(longo_b)
                     .mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=2)
                     .encode(x=alt.X("sprint:O", title="Sprint"),
                             y=alt.Y("valor:Q", title="Pontos restantes"),
                             color=alt.Color("serie:N", title="",
                                             scale=alt.Scale(domain=["Restante (real)", "Ideal"],
                                                             range=[theme.SERIES[0], theme.INK["muted"]])),
                             strokeDash=alt.StrokeDash("serie:N", legend=None,
                                                       scale=alt.Scale(domain=["Restante (real)", "Ideal"],
                                                                       range=[[1, 0], [6, 4]])),
                             tooltip=["sprint:O", "serie:N", alt.Tooltip("valor:Q", format=".1f")]))
            st.altair_chart(finalizar(linha.properties(height=300)), use_container_width=True)
            st.caption("Granularidade por sprint: o snapshot guarda o estado do quadro ao fim de cada "
                       "sprint. A linha ideal é recalculada com o PRP de cada sprint: quando entra escopo, ela sobe junto.")
            tabela(bd)

    # ── AgileEVM ──
    st.divider()
    st.markdown("#### EVM-Ágil (AgileEVM)")
    st.caption("Sulaiman, Barton & Blackburn (2006). PPC = n/L · APC = pontos Done/PRP · "
               "SPI = APC/PPC · CPI = EV/AC. Calculado em horas; R$ quando há custo/hora.")
    faltando = [nome for nome, v in (("horas_semana_pessoa", params["horas_semana_pessoa"]),
                                     ("custo_hora", params["custo_hora"])) if not v]
    if faltando:
        st.warning(
            f"**Parâmetros não definidos em `planilhas/parametros.csv`: {', '.join(faltando)}.** "
            "Sem capacidade (horas/semana) não há BAC, e sem BAC não há PV, EV nem EAC em valor. "
            "O SPI continua calculável, porque só depende de percentuais (APC/PPC). "
            "O custo/hora só converte horas em R$: não altera CPI nem SPI.", icon="⚠️")
    if horas_reais.empty:
        st.warning("**Nenhuma hora real registrada (`planilhas/horas.csv`).** Sem AC não há CPI, "
                   "CV nem EAC. O registro começa na planning de 28/09; o período anterior fica "
                   "declarado como sem dado, e não é preenchido por estimativa.", icon="⚠️")
    if not evm_zh.empty:
        e = evm_zh[evm_zh["iniciada"]]
        if not e.empty:
            ult = e.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PPC (planejado)", f"{ult['PPC']:.0%}")
            c2.metric("APC (realizado)", f"{ult['APC']:.0%}" if pd.notna(ult["APC"]) else "—")
            c3.metric("SPI", f"{ult['SPI']:.2f}" if pd.notna(ult["SPI"]) else "—",
                      ("✅ no prazo" if ult["SPI"] >= 0.95 else "🔴 atrasado") if pd.notna(ult["SPI"]) else "",
                      delta_color="off")
            c4.metric("CPI", f"{ult['CPI']:.2f}" if pd.notna(ult["CPI"]) else "—",
                      "" if pd.notna(ult["CPI"]) else "sem horas reais", delta_color="off")
            perc = e.melt(id_vars=["sprint"], value_vars=["PPC", "APC"],
                          var_name="indicador", value_name="valor")
            graf = (alt.Chart(perc)
                    .mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=2)
                    .encode(x=alt.X("sprint:O", title="Sprint"),
                            y=alt.Y("valor:Q", title="% da release", axis=alt.Axis(format="%")),
                            color=alt.Color("indicador:N", title="",
                                            scale=alt.Scale(domain=["PPC", "APC"], range=theme.SERIES[:2])),
                            tooltip=["sprint:O", "indicador:N", alt.Tooltip("valor:Q", format=".0%")]))
            st.altair_chart(finalizar(graf.properties(height=280)), use_container_width=True)
        tabela(evm_zh, "Ver a tabela AgileEVM completa")

    st.divider()
    st.markdown("#### Matriz de riscos")
    st.caption(f"Fonte: **{origem_riscos}**. Probabilidade e impacto de 1 a 5; "
               "exposição = P × I: 1 a 5 baixo, 6 a 12 médio, 15 a 25 elevado.")
    if riscos.empty:
        aviso_sem_dado("Matriz de riscos vazia", f"A fonte lida foi: {origem_riscos}, e ela não tem linhas.",
                       "Preencher a aba Riscos da planilha do time.")
    else:
        # Aceita a escala 1 a 5 e, por compatibilidade, os rótulos antigos.
        rotulos = {"muito baix": 1, "baix": 2, "méd": 3, "med": 3, "alt": 4, "muito alt": 5}

        def escala(valor) -> float:
            texto = str(valor).strip().lower().replace(",", ".")
            try:
                n = float(texto)
                return n if 1 <= n <= 5 else float("nan")
            except ValueError:
                for prefixo in sorted(rotulos, key=len, reverse=True):
                    if texto.startswith(prefixo):
                        return rotulos[prefixo]
            return float("nan")

        r = riscos.copy()
        r["p"] = r["probabilidade"].map(escala)
        r["i"] = r["impacto"].map(escala)
        sem_classe = int(r[["p", "i"]].isna().any(axis=1).sum())
        r = r.dropna(subset=["p", "i"])
        r["exposicao"] = r["p"] * r["i"]
        r["nivel"] = pd.cut(r["exposicao"], [0, 5, 12, 25], labels=["Baixo", "Médio", "Elevado"])
        ativos = r[~r["status"].astype(str).str.lower().str.startswith("encerr")]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Riscos ativos", len(ativos))
        c2.metric("Exposição elevada", int((ativos["nivel"] == "Elevado").sum()), "🔴 15 a 25", delta_color="off")
        c3.metric("Materializados", int(r["status"].astype(str).str.lower().str.startswith("materializ").sum()))
        sem_dono = int(ativos["responsavel"].isna().sum() + (ativos["responsavel"].astype(str).str.strip() == "").sum())
        c4.metric("Sem responsável", sem_dono, "precisa de dono" if sem_dono else "✅", delta_color="off")
        if sem_classe:
            st.caption(f"⚠️ {sem_classe} risco(s) sem probabilidade ou impacto válido ficaram fora da matriz.")

        grade = pd.DataFrame([(p, i) for p in range(1, 6) for i in range(1, 6)], columns=["p", "i"])
        grade["exposicao"] = grade["p"] * grade["i"]
        contagem = ativos.groupby(["p", "i"]).agg(qtd=("id", "count"),
                                                  ids=("id", lambda x: ", ".join(map(str, x)))).reset_index()
        grade = grade.merge(contagem, on=["p", "i"], how="left").fillna({"qtd": 0, "ids": ""})
        fundo = (alt.Chart(grade).mark_rect(stroke="#fcfcfb", strokeWidth=2)
                 .encode(x=alt.X("p:O", title="Probabilidade (1 a 5)"),
                         y=alt.Y("i:O", title="Impacto (1 a 5)", sort="descending"),
                         color=alt.Color("exposicao:Q", title="Exposição",
                                         scale=alt.Scale(domain=[1, 6, 15, 25],
                                                         range=["#cdebd3", "#fce8b2", "#f4c7c3", "#e8998f"])),
                         tooltip=[alt.Tooltip("p:O", title="P"), alt.Tooltip("i:O", title="I"),
                                  alt.Tooltip("exposicao:Q", title="P×I"), alt.Tooltip("ids:N", title="Riscos")]))
        rotulo_ids = (alt.Chart(grade[grade["qtd"] > 0]).mark_text(fontSize=12, fontWeight="bold",
                                                                    color=theme.INK["primary"])
                      .encode(x="p:O", y=alt.Y("i:O", sort="descending"), text="ids:N"))
        st.altair_chart(finalizar((fundo + rotulo_ids).properties(height=340)), use_container_width=True)

        if "categoria" in ativos and ativos["categoria"].astype(str).str.strip().ne("").any():
            st.markdown("##### Exposição por categoria (EAR)")
            por_cat = ativos.groupby("categoria", dropna=False)["exposicao"].sum().reset_index()
            barras_c = (alt.Chart(por_cat).mark_bar(cornerRadiusEnd=4, size=18, color=theme.SERIES[0])
                        .encode(y=alt.Y("categoria:N", title=None, sort="-x"),
                                x=alt.X("exposicao:Q", title="Exposição somada (P×I)"),
                                tooltip=["categoria:N", "exposicao:Q"]))
            st.altair_chart(finalizar(barras_c.properties(height=40 * len(por_cat) + 30)), use_container_width=True)

        colunas_r = [c for c in ["id", "categoria", "risco", "p", "i", "exposicao", "nivel", "resposta",
                                 "prevencao", "contingencia", "responsavel", "status", "ultima_revisao"]
                     if c in r]
        st.dataframe(r.sort_values("exposicao", ascending=False)[colunas_r]
                     .rename(columns={"p": "prob.", "i": "impacto"}),
                     use_container_width=True, hide_index=True)

# ───────────────────────── decisões ─────────────────────────

with aba_decisoes:
    st.subheader("Decisões baseadas em dados")
    st.markdown(
        "A disciplina exige **≥ 3 decisões documentadas na R2** e **≥ 5 na R3**, "
        "cada uma com causa, evidência, ação e resultado. Esta aba é o registro — "
        f"preencha a planilha de decisões ({origem_decisoes}) a cada decisão "
        "tomada a partir de um número deste dashboard."
    )
    if decisoes.empty:
        st.info("Nenhuma decisão registrada ainda.", icon="📝")
        # As candidatas saem dos dados carregados agora, não de texto fixo:
        # um número que envelhece na tela é pior do que número nenhum.
        candidatas = []

        ult = ultimo_por_repo(agregado)
        cob = ult[ult["metrica"] == "coverage"] if not ult.empty else pd.DataFrame()
        meta = theme.METAS.get("coverage", {}).get(release, 85)
        abaixo = cob[cob["valor"] < meta] if not cob.empty else pd.DataFrame()
        if not abaixo.empty:
            detalhe = ", ".join(f"{l.repositorio.split('-')[-1]} {l.valor:.1f}%"
                                for l in abaixo.itertuples())
            candidatas.append(
                f"**Cobertura abaixo da meta de {meta:.0f}%** em "
                f"{len(abaixo)} de {len(cob)} repositórios: {detalhe}.")

        if not runs.empty:
            concluidas = runs[runs["conclusao"].isin(["success", "failure"])]
            if not concluidas.empty:
                falha = (concluidas["conclusao"] == "failure").mean() * 100
                if falha >= 20:
                    candidatas.append(
                        f"**Taxa de falha da CI em {falha:.0f}%** "
                        f"({(concluidas['conclusao'] == 'failure').sum()} de "
                        f"{len(concluidas)} execuções conclusivas).")

        if not erros_sonar.empty:
            candidatas.append(
                f"**{erros_sonar['repositorio'].nunique()} repositórios sem projeto "
                "no SonarCloud**: coletam, gravam arquivo de erro, e ficam invisíveis "
                "para a avaliação de qualidade.")

        if not issues.empty:
            abertas = (issues["estado"] == "open").sum()
            if abertas:
                candidatas.append(f"**{abertas} issues abertas** contra "
                                  f"{(issues['estado'] == 'closed').sum()} fechadas.")

        if candidatas:
            st.markdown("Candidatas visíveis nos dados carregados agora:\n\n"
                        + "\n".join(f"- {c}" for c in candidatas))
    else:
        for _, linha in decisoes.iterrows():
            with st.container(border=True):
                tipo_d = linha.get("tipo", "") or ""
                st.markdown(f"**{linha.get('data', '')} · {linha.get('metrica', '')}**"
                            + (f" · {tipo_d}" if isinstance(tipo_d, str) and tipo_d else ""))
                st.markdown(f"**Contexto e dado:** {linha.get('causa', '')}")
                st.markdown(f"**Decisão:** {linha.get('decisao', '')}")
                for campo, rot in (("evidencia", "Evidência"), ("criterio_sucesso", "Critério de sucesso")):
                    v = linha.get(campo, "")
                    if isinstance(v, str) and v.strip():
                        st.markdown(f"**{rot}:** {v}")
                st.markdown(f"**Resultado:** {linha.get('resultado', '') or '_em observação_'}")

st.divider()
st.caption(
    "Todo indicador de Produto e Processo é lido de arquivos gerados pelo pipeline "
    "de CI/CD. Projeto vem das planilhas do time. Nenhum número é digitado no código."
)
