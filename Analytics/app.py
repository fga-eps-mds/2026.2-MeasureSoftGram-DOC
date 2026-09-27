"""Dashboard Gerencial e Analítico — MeasureSoftGram EPS 2026.2.

Abas (espelham as planilhas do time e os dados automáticos do pipeline):

* Produto (SonarCloud) e Processo (GitHub) — lidos dos .json que o `metrics.yml` publica.
* Custos, AgileEVM, Velocity e Burndown — planilha "Custos e AgileEVM".
* Riscos e Decisões — planilha "Riscos e Decisões".

Os cálculos de custo e AgileEVM são feitos **por fórmula na planilha**; o painel
só desenha o resultado e mostra, em cada aba, de onde veio cada número e como
ele é calculado. Quando um dado não existe, o painel diz que não existe.

Rodar:
    pip install -r requirements.txt
    streamlit run app.py

Publicado no GitHub Pages via stlite (Streamlit no navegador): ver stlite/build.py.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# No navegador (stlite, GitHub Pages) o diretório do app nem sempre está no path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # noqa: E402
import pandas as pd
import streamlit as st

import config
from src import evm, gestao, planilhas, qualidade, resumo, theme, velocity, velocity_dashboard
from src.loader import (
    carregar_issues,
    carregar_runs,
    carregar_sonar,
    coletas_com_erro,
    ultimo_por_repo,
)

RAIZ = Path(__file__).resolve().parent
DADOS_BRUTOS = [RAIZ / "data", RAIZ.parent / "analytics-raw-data"]
PLANILHAS_LOCAIS = RAIZ / "planilhas"

st.set_page_config(page_title="Dashboard Analítico — MeasureSoftGram EPS 2026.2",
                   page_icon="📊", layout="wide")
alt.data_transformers.disable_max_rows()


def finalizar(chart):
    """Chrome comum: grade discreta, eixos recessivos, sem moldura."""
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
                          titleColor=theme.INK["secondary"], labelFontSize=11, orient="top")
    )


def tabela(df: pd.DataFrame, rotulo: str = "Ver os dados em tabela") -> None:
    with st.expander(rotulo):
        st.dataframe(df, use_container_width=True, hide_index=True)


def fonte_e_calculo(linhas: list[tuple[str, str, str]], aberto: bool = False) -> None:
    """Quadro 'de onde vem e como é calculado' no topo de cada aba."""
    with st.expander("📌 De onde vêm os dados e como cada número é calculado", expanded=aberto):
        md = "| Indicador | De onde vem | Como é calculado |\n|---|---|---|\n"
        md += "\n".join(f"| {a} | {b} | {c} |" for a, b, c in linhas)
        st.markdown(md)


def aviso_sem_dado(titulo: str, motivo: str, como_resolver: str) -> None:
    st.warning(f"**{titulo}**\n\n{motivo}\n\n**Como resolver:** {como_resolver}")


def brl(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(v, casas=2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:.0%}"


RELEASES = pd.DataFrame({"data": pd.to_datetime(["2026-09-28", "2026-10-26", "2026-11-30"]),
                         "release": ["R1", "R2", "R3"]})
COR_RELEASE = alt.Scale(domain=["R1", "R2", "R3"], range=theme.SERIES[:3])


def linhas_de_release(inicio, fim):
    d = RELEASES[(RELEASES["data"] >= pd.Timestamp(inicio) - pd.Timedelta(days=3))
                 & (RELEASES["data"] <= pd.Timestamp(fim) + pd.Timedelta(days=10))]
    regra = (alt.Chart(d).mark_rule(strokeDash=[2, 3], color=theme.SERIES[1], strokeWidth=1.5)
             .encode(x="data:T"))
    texto = (alt.Chart(d).mark_text(align="left", dx=4, dy=-110, fontSize=11, color=theme.SERIES[1])
             .encode(x="data:T", text="release:N"))
    return regra + texto


def regra_um(texto="1,0 = no plano"):
    base = pd.DataFrame({"y": [1.0], "t": [texto]})
    return (alt.Chart(base).mark_rule(strokeDash=[6, 4], color=theme.INK["muted"]).encode(y="y:Q")
            + alt.Chart(base).mark_text(align="left", dx=4, dy=-7, fontSize=11, color=theme.INK["muted"])
            .encode(y="y:Q", text="t:N", x=alt.value(0)))


# ───────────────────────── carga ─────────────────────────

@st.cache_data(show_spinner="Lendo os arquivos do pipeline...")
def carregar_tudo(pastas: tuple[str, ...]):
    p = [Path(x) for x in pastas]
    agregado, componentes = carregar_sonar(p)
    return agregado, componentes, carregar_issues(p), carregar_runs(p), coletas_com_erro(p)


@st.cache_data(ttl=config.CACHE_PLANILHAS_S, show_spinner="Lendo as planilhas do time...")
def carregar_planilhas(urls: dict):
    """Só o que o Zenhub não tem: custos, quem está no time, horas, riscos e decisões."""
    P = PLANILHAS_LOCAIS
    ler = lambda chave, **kw: planilhas.ler(chave, urls, P, **kw)
    c_df = ler("custos")
    plano = planilhas.planejamento_semanal(ler("planejamento"))
    horas = planilhas.converter(ler("horas"), numericas=["sprint", "horas"],
                                datas=["inicio_da_sprint", "fim_da_sprint"])
    riscos = planilhas.converter(ler("riscos"), numericas=["ultima_sprint_avaliada", "probabilidade_atual",
                                                           "impacto_atual", "exposicao_atual"],
                                 datas=["identificado_em"])
    mon = planilhas.converter(ler("monitoramento"), numericas=["sprint", "probabilidade", "impacto", "exposicao"],
                              datas=["data_da_revisao"])
    dec = ler("decisoes")
    return c_df, planilhas.custos(c_df), plano, horas, riscos, mon, dec, dict(planilhas.ORIGEM)


agregado, componentes, issues, runs, erros_sonar = carregar_tudo(tuple(str(p) for p in DADOS_BRUTOS))
custos_df, custo, plano, horas, riscos, monit, decisoes, ORIGEM = carregar_planilhas(dict(config.PLANILHAS))
origem = lambda chave: ORIGEM.get(chave, "—")

try:
    HOJE = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize()
except Exception:  # noqa: BLE001 — no navegador (stlite) pode faltar a base de fusos
    HOJE = (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(hours=3)).normalize()

# Zenhub: sprints, pontos, velocity e escopo (tudo o que é ponto vem daqui)
params = gestao.carregar_parametros(PLANILHAS_LOCAIS)
regras = velocity.Regras.dos_parametros(params)
AGORA = datetime.now(timezone.utc)
zh_todas, zh_snap, zh_arquivo = velocity_dashboard.carregar_velocity(regras, AGORA)
zh_vel = zh_todas[zh_todas["status"] != velocity.STATUS_FUTURA] if not zh_todas.empty else zh_todas
evm_df = (evm.agile_evm(zh_todas, zh_snap.get("issues", {}), plano, horas, custo.get("custo_hora"))
          if zh_snap else pd.DataFrame())
sumario = evm.sumario(evm_df)
if not zh_todas.empty:
    cal_sprints = pd.DataFrame({"sprint": zh_todas["sprint_label"], "release": zh_todas["release_name"],
                                "inicio": evm._data_local(zh_todas["start_date"]),
                                "fim": evm._data_local(zh_todas["end_date"])})
else:
    cal_sprints = pd.DataFrame(columns=["sprint", "release", "inicio", "fim"])

# ───────────────────────── cabeçalho ─────────────────────────

st.title("Dashboard Gerencial e Analítico")
st.caption("MeasureSoftGram · Engenharia de Produto de Software · 2026.2")

repos = sorted(agregado["repositorio"].unique()) if not agregado.empty else []
with st.sidebar:
    st.header("Filtros (Produto e Processo)")
    repos_sel = st.multiselect("Repositórios", repos, default=repos)
    branches = sorted(agregado["branch"].unique()) if not agregado.empty else ["develop"]
    branch_sel = st.selectbox("Branch", branches,
                              index=branches.index("develop") if "develop" in branches else 0)
    REL_ATUAL, ENTREGA_ATUAL = resumo.release_atual(HOJE)
    release = st.radio("Metas da release", ["R1", "R2", "R3"], horizontal=True,
                       index=["R1", "R2", "R3"].index(REL_ATUAL),
                       help="Começa na release em andamento. As metas mudam os status de todas as abas.")
    st.divider()
    if not agregado.empty:
        st.caption(f"Última coleta do SonarCloud: **{agregado['coleta'].max():%d/%m/%Y %H:%M}**")
    st.caption(f"Snapshot do Zenhub: `{zh_arquivo or 'nenhum — rode scripts/coleta_velocity.py'}`")
    st.caption("Planilha (custos, time, horas, riscos, decisões): "
               + ("publicada no Google" if any(config.PLANILHAS.values()) else "CSVs locais em `planilhas/`"))

if not agregado.empty:
    filtro = agregado[(agregado["repositorio"].isin(repos_sel)) & (agregado["branch"] == branch_sel)]
    comp_filtro = componentes[(componentes["repositorio"].isin(repos_sel)) & (componentes["branch"] == branch_sel)]

# Navegação em quatro níveis de leitura: a visão geral responde "como estamos?";
# as outras abas respondem "por quê?" em cada dimensão exigida pela disciplina.
(aba_geral, aba_produto, aba_processo, aba_projeto, aba_gestao) = st.tabs(
    ["🧭 Visão geral", "🧪 Produto", "⚙️ Processo", "📈 Projeto", "🛡️ Riscos e decisões"])
with aba_projeto:
    aba_vel_zh, aba_evm, aba_custos = st.tabs(["Velocity", "AgileEVM e burndown", "Custos"])
with aba_gestao:
    aba_riscos, aba_decisoes = st.tabs(["Riscos", "Decisões"])

# ───────────────────────── visão geral ─────────────────────────

def _card_dimensao(titulo: str, itens: pd.DataFrame) -> None:
    status = resumo.pior(list(itens["status"])) if not itens.empty else "neutral"
    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        st.caption(f"{resumo.ICONE[status]} **{resumo.ROTULO[status].capitalize()}**")
        for it in itens.itertuples():
            meta = f" · meta {it.meta}" if it.meta and it.meta != "—" else ""
            st.markdown(f"{resumo.ICONE[it.status]} **{it.indicador}**  \n"
                        f"<span style='font-size:1.35rem;font-weight:600'>{it.valor}</span>"
                        f"<span style='color:{theme.INK['secondary']};font-size:0.85rem'>{meta}</span>  \n"
                        f"<span style='color:{theme.INK['secondary']};font-size:0.85rem'>{it.leitura}</span>",
                        unsafe_allow_html=True)


with aba_geral:
    ultimo_geral = ultimo_por_repo(filtro) if not agregado.empty else pd.DataFrame()
    runs_geral = runs[runs["repositorio"].isin(repos_sel)] if not runs.empty and repos_sel else runs
    issues_geral = issues[issues["repositorio"].isin(repos_sel)] if not issues.empty and repos_sel else issues
    painel = resumo.tudo(ultimo=ultimo_geral, erros=erros_sonar, runs=runs_geral, issues=issues_geral,
                         evm_df=evm_df, vel=zh_vel, horas=horas, sumario=sumario, riscos=riscos, decisoes=decisoes,
                         release=release)
    alertas = resumo.atencao(painel)
    sprint_hoje = resumo.sprint_atual(cal_sprints, HOJE)

    st.subheader("Como está o projeto agora")
    st.caption(f"Situação em {HOJE:%d/%m/%Y}, medida contra as metas da **{release}**. "
               "Cada indicador aponta a aba onde está o detalhe e a fonte do número.")

    dias = (ENTREGA_ATUAL - HOJE).days
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Release em andamento", REL_ATUAL,
              f"entrega {ENTREGA_ATUAL:%d/%m} · " + ("hoje" if dias == 0 else f"faltam {dias} dia(s)" if dias > 0
                                                     else f"entregue há {-dias} dia(s)"),
              delta_color="off")
    if sprint_hoje is not None:
        c2.metric("Sprint atual", str(sprint_hoje['sprint']),
                  f"{sprint_hoje['inicio']:%d/%m} a {sprint_hoje['fim']:%d/%m}", delta_color="off")
    else:
        c2.metric("Sprint atual", "—", "fora do calendário", delta_color="off")
    com_meta = painel[painel["status"] != "neutral"]
    c3.metric("Indicadores no plano", f"{int((com_meta['status'] == 'good').sum())} de {len(com_meta)}")
    n_crit = int((painel["status"] == "critical").sum())
    c4.metric("Fora do plano", n_crit, f"+ {int((painel['status'] == 'warning').sum())} em atenção",
              delta_color="off")

    # Linha do tempo do semestre: onde estamos entre as três entregas.
    if not cal_sprints.empty:
        cal = cal_sprints.assign(fim_barra=cal_sprints["fim"] + pd.Timedelta(days=1),
                                 rotulo=cal_sprints["sprint"],
                                 encerrada=cal_sprints["fim"] < HOJE)
        cal["meio"] = cal["inicio"] + (cal["fim_barra"] - cal["inicio"]) / 2
        barras_t = (alt.Chart(cal).mark_bar(cornerRadius=4, height=26, stroke="#fcfcfb", strokeWidth=2)
                    .encode(x=alt.X("inicio:T", title=None, axis=alt.Axis(format="%d/%m", tickCount=14)),
                            x2="fim_barra:T",
                            color=alt.Color("release:N", title="Release", scale=COR_RELEASE),
                            opacity=alt.condition("datum.encerrada", alt.value(0.45), alt.value(1)),
                            tooltip=[alt.Tooltip("rotulo:N", title="Sprint"), alt.Tooltip("release:N", title="Release"),
                                     alt.Tooltip("inicio:T", title="Início", format="%d/%m"),
                                     alt.Tooltip("fim:T", title="Fim", format="%d/%m")]))
        rot_t = (alt.Chart(cal).mark_text(fontSize=11, color="#ffffff", fontWeight="bold")
                 .encode(x="meio:T", text="rotulo:N"))
        hoje_df = pd.DataFrame({"d": [HOJE], "t": ["hoje"]})
        regra_h = alt.Chart(hoje_df).mark_rule(color=theme.INK["primary"], strokeWidth=2).encode(x="d:T")
        txt_h = (alt.Chart(hoje_df).mark_text(dy=-22, fontSize=11, fontWeight="bold", color=theme.INK["primary"])
                 .encode(x="d:T", text="t:N"))
        st.altair_chart(finalizar((barras_t + rot_t + regra_h + txt_h).properties(height=90)),
                        use_container_width=True)
        st.caption("Sprints do Zenhub, coloridas por release; as já encerradas ficam claras. "
                   "Entregas: R1 28/09 · R2 26/10 · R3 30/11.")

    st.markdown("### Pontos de atenção")
    if alertas.empty:
        st.success("Nenhum indicador fora do plano ou em atenção.", icon="✅")
    else:
        for it in alertas.itertuples():
            meta = f" (meta {it.meta})" if it.meta and it.meta != "—" else ""
            st.markdown(f"{resumo.ICONE[it.status]} **{it.indicador}: {it.valor}**{meta} — {it.leitura} "
                        f"· _detalhe na aba {it.aba}_")

    st.markdown("### Situação por dimensão")
    cols_d = st.columns(4)
    for col, (dim, titulo) in zip(cols_d, [("Produto", "🧪 Produto"), ("Processo", "⚙️ Processo"),
                                           ("Projeto", "📈 Projeto"), ("Gestão", "🛡️ Riscos e decisões")]):
        with col:
            _card_dimensao(titulo, painel[painel["dimensao"] == dim])

    st.markdown("### Placar por repositório")
    placar = resumo.scorecard_repos(ultimo_geral, runs_geral, issues_geral, release)
    if placar.empty:
        st.caption("Sem dados de SonarCloud nem de CI para os repositórios selecionados.")
    else:
        meta_c = theme.METAS["coverage"][release]
        st.dataframe(
            placar[[c for c in ["repositorio", "situacao", "cobertura", "duplicacao", "testes", "ci_sucesso",
                                "ci_execucoes", "issues_abertas", "linhas"] if c in placar]],
            use_container_width=True, hide_index=True,
            column_config={
                "repositorio": st.column_config.TextColumn("Repositório"),
                "situacao": st.column_config.TextColumn("Situação"),
                "cobertura": st.column_config.ProgressColumn(f"Cobertura (meta {meta_c:.0f}%)", min_value=0,
                                                             max_value=100, format="%.1f%%"),
                "duplicacao": st.column_config.NumberColumn("Duplicação", format="%.1f%%"),
                "testes": st.column_config.NumberColumn("Testes", format="%d"),
                "ci_sucesso": st.column_config.ProgressColumn("Sucesso da CI (meta 80%)", min_value=0,
                                                              max_value=100, format="%.0f%%"),
                "ci_execucoes": st.column_config.NumberColumn("Execuções da CI", format="%d"),
                "issues_abertas": st.column_config.NumberColumn("Issues abertas", format="%d"),
                "linhas": st.column_config.NumberColumn("Linhas de código", format="%d"),
            })
        st.caption("Situação = pior status entre cobertura e sucesso da CI. Repositório sem cobertura aparece em "
                   "atenção: sem projeto no SonarCloud não há como medir a qualidade dele.")

    tabela(painel.assign(status=painel["status"].map(lambda s: f"{resumo.ICONE[s]} {resumo.ROTULO[s]}")),
           "Ver todos os indicadores da visão geral em tabela")


# ───────────────────────── produto ─────────────────────────

with aba_produto:
    st.subheader("Qualidade do produto")
    st.caption("Fonte: SonarCloud, via `metrics.yml`. Metas conforme os critérios da release.")
    fonte_e_calculo([
        ("Cobertura, duplicação, sucesso dos testes, nº de testes", "SonarCloud → workflow `metrics.yml` de cada repositório → arquivos `Analytics/data/fga-eps-mds-*.json`",
         "valor do projeto na última coleta; nos cartões, média entre os repositórios selecionados"),
        ("Meta da release", "Critérios da release (plano de ensino)", "ex.: cobertura ≥ 85% na R1"),
        ("Cobertura por componente", "mesmos arquivos, métricas por arquivo/pasta", "os 15 componentes com menor cobertura"),
        ("Modelo de qualidade", "mesmos arquivos, métricas por arquivo (`src/qualidade.py`)",
         "proporção de arquivos dentro do limiar (complexidade/função < 10; comentários 10–30%; duplicação < 5%; cobertura > 60%; testes < 300 ms); "
         "qualidade do código = média de complexidade, comentários e duplicação; testes = 0,25 sucesso + 0,25 rápidos + 0,5 cobertura; "
         "total = 0,5 × código + 0,5 × testes"),
    ])
    if agregado.empty:
        aviso_sem_dado("Nenhuma métrica do SonarCloud encontrada",
                       "Nenhuma das pastas `analytics-raw-data/` ou `Analytics/data/` tem arquivos no formato esperado.",
                       "Rodar o workflow `metrics.yml` (workflow_dispatch) em cada repositório.")
    else:

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
    fonte_e_calculo([
        ("Execuções da CI, taxa de sucesso, falhas", "API do GitHub (Actions) → arquivos `GitHub_API-Runs-*.json`",
         "taxa de sucesso = execuções com sucesso ÷ execuções concluídas"),
        ("Tempo de feedback da CI", "mesmos arquivos", "fim − início de cada execução, em minutos (mediana e máximo)"),
        ("Issues abertas e fechadas, lead time", "API do GitHub → arquivos `GitHub_API-Issues-*.json`",
         "lead time = data de fechamento − data de criação (mediana, em dias)"),
    ])

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


# ───────────────────────── custos ─────────────────────────

with aba_custos:
    st.subheader("Custos do projeto")
    st.caption(f"Fonte: {origem('custos')} e {origem('planejamento')}.")
    fonte_e_calculo([
        ("Custo de um integrante por semana", "Aba **Custos** (premissas de 2026.1 atualizadas)",
         "custo de EPS por semana + energia + internet + depreciação do notebook"),
        ("Custo de EPS por semana", "Aba **Custos**: custo anual do aluno (R$ 52.533), 40 créditos/ano, 4 créditos de EPS, 18 semanas",
         "52.533 ÷ 40 × 4 ÷ 18"),
        ("Energia, internet e depreciação", "Aba **Custos** (tarifa Neoenergia, plano de internet, notebook de referência)",
         "(W computador + W modem) ÷ 1000 × R$/kWh × horas remotas · internet × 12 ÷ 52 · notebook ÷ semanas de vida útil"),
        ("Custo por hora", "Aba **Custos**", "custo de um integrante por semana ÷ horas por semana (4 presenciais + 10 remotas)"),
        ("Custo planejado da semana", "Aba **Planejamento** (quem está no time em cada semana: 1 ou 0)",
         "integrantes ativos × custo de um integrante por semana + infraestrutura"),
        ("Orçamento da release (BAC)", "Aba **Planejamento** + datas das sprints no Zenhub", "soma do custo planejado das semanas da release"),
    ])
    if not custo:
        aviso_sem_dado("Aba Custos não encontrada", f"Fonte lida: {origem('custos')}.",
                       "Publicar a aba Custos em CSV e colar o link em `config.py` (chave `custos`).")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Custo de um integrante por semana", brl(custo.get("custo_membro_semana")))
        c2.metric("Custo por hora", brl(custo.get("custo_hora")),
                  f"{num(custo.get('horas_semana_total'), 0)} h por semana", delta_color="off")
        c3.metric("Integrantes", num(custo.get("integrantes"), 0))
        c4.metric("Orçamento total (BAC)", brl(custo.get("bac_total")), "R1 + R2 + R3", delta_color="off")

        st.markdown("#### Do que é feito o custo semanal de um integrante")
        comp = pd.DataFrame({
            "componente": ["Cursar EPS (custo do aluno UnB)", "Internet", "Depreciação do notebook", "Energia"],
            "valor": [custo.get("custo_eps_semana"), custo.get("internet_semana"),
                      custo.get("depreciacao_semana"), custo.get("energia_semana")]}).dropna()
        comp["texto"] = comp["valor"].map(brl)
        barras = (alt.Chart(comp).mark_bar(cornerRadiusEnd=4, size=20, color=theme.SERIES[0])
                  .encode(y=alt.Y("componente:N", sort="-x", title=None),
                          x=alt.X("valor:Q", title="R$ por semana"),
                          tooltip=["componente:N", alt.Tooltip("valor:Q", format=",.2f")]))
        rot = barras.mark_text(align="left", dx=4, fontSize=11, color=theme.INK["secondary"]).encode(text="texto:N")
        st.altair_chart(finalizar((barras + rot).properties(height=170)), use_container_width=True)
        st.caption("Quase todo o custo é o custo de oportunidade de cursar a disciplina; "
                   "infraestrutura é zero porque o deploy é no LAPPIS e a documentação no GitHub Pages.")

    if not sumario.empty:
        st.markdown("#### Orçamento (BAC) por release")
        b = sumario[["release", "semanas", "BAC"]].dropna(subset=["BAC"]).assign(texto=lambda d: d["BAC"].map(brl))
        barras = (alt.Chart(b).mark_bar(cornerRadiusEnd=4, size=28)
                  .encode(x=alt.X("release:N", title=None, axis=alt.Axis(labelAngle=0)),
                          y=alt.Y("BAC:Q", title="R$"),
                          color=alt.Color("release:N", scale=COR_RELEASE, legend=None),
                          tooltip=["release:N", "semanas:Q", alt.Tooltip("BAC:Q", format=",.2f")]))
        rot = barras.mark_text(dy=-8, fontSize=11, color=theme.INK["secondary"]).encode(text="texto:N")
        st.altair_chart(finalizar((barras + rot).properties(height=260)), use_container_width=True)
        st.caption("A R2 custa menos porque tem 4 semanas; R1 e R3 têm 5.")

    if not plano.empty:
        st.markdown("#### Custo planejado por semana")
        p = plano.dropna(subset=["custo"]).copy()
        if not cal_sprints.empty:  # release e sprint de cada semana pelo calendário do Zenhub
            def _sprint_da_semana(semana):
                c = cal_sprints[(cal_sprints["inicio"] <= semana) & (cal_sprints["fim"] >= semana)]
                return (c["release"].iloc[0], c["sprint"].iloc[0]) if not c.empty else ("", "")
            p[["release", "sprint"]] = pd.DataFrame(p["semana"].map(_sprint_da_semana).tolist(), index=p.index)
        barras = (alt.Chart(p).mark_bar(cornerRadiusEnd=3)
                  .encode(x=alt.X("semana:T", title="Semana", axis=alt.Axis(format="%d/%m")),
                          y=alt.Y("custo:Q", title="R$"),
                          color=alt.Color("release:N", title="Release", scale=COR_RELEASE),
                          tooltip=[alt.Tooltip("semana:T", format="%d/%m"), "release:N", "sprint:N",
                                   "integrantes:Q", alt.Tooltip("custo:Q", format=",.2f")]))
        st.altair_chart(finalizar(barras.properties(height=240)), use_container_width=True)
        st.caption("Se alguém sair do time, troque o 1 por 0 na aba Planejamento a partir da semana de saída: "
                   "o custo e o orçamento se ajustam sozinhos.")
        tabela(p, "Ver o custo por semana")

    if not custos_df.empty:
        with st.expander("Ver todas as premissas de custo (aba Custos)"):
            st.dataframe(custos_df.drop(columns=["chave"], errors="ignore"), use_container_width=True, hide_index=True)

    st.markdown("#### Horas registradas")
    h = horas.dropna(subset=["horas"]) if not horas.empty else horas
    if h.empty:
        st.info("**Nenhuma hora registrada na aba Horas.** Por isso o custo real (AC) do AgileEVM usa o custo "
                "planejado de cada sprint, como na planilha de 2026.1. Quando o time registrar horas, o AC da sprint "
                "passa a ser horas × custo por hora e o CPI passa a mostrar se estamos gastando mais ou menos que o planejado.",
                icon="ℹ️")
    else:
        por_sprint = h.groupby("sprint", as_index=False)["horas"].sum()
        st.dataframe(por_sprint, hide_index=True)

# ───────────────────────── AgileEVM e burndown ─────────────────────────

with aba_evm:
    st.subheader("AgileEVM — valor agregado por release")
    st.caption(f"Pontos: Zenhub (`{zh_arquivo or 'sem snapshot'}`). Custos: {origem('planejamento')}. "
               f"Horas: {origem('horas')}. Método: Sulaiman, Barton & Blackburn (2006).")
    fonte_e_calculo([
        ("Sprints e releases", "Zenhub (datas das sprints; Release do Zenhub ou, sem ela, as entregas do plano de ensino)",
         "cada sprint entra na release cuja entrega vem logo depois do último dia dela"),
        ("PP · PC", "Zenhub (aba Velocity)", "planejado no início da sprint · concluído dentro da sprint"),
        ("PRP (escopo da release)", "Zenhub", "pontos das issues pontuáveis que passaram pelas sprints da release até agora, "
                                              "cada issue uma vez; linha de base = planejado da 1ª sprint"),
        ("PA (pontos adicionados)", "Zenhub", "quanto o PRP cresceu na sprint"),
        ("RPC · APC", "Zenhub", "pontos do escopo já concluídos · RPC ÷ PRP"),
        ("PPC (% planejado)", "datas das sprints no Zenhub", "semanas decorridas da release ÷ semanas da release"),
        ("BAC (orçamento)", "Planilha: abas **Custos** e **Planejamento**", "custo planejado das semanas da release"),
        ("PV · EV", "cálculo", "PV = PPC × BAC · EV = APC × BAC"),
        ("AC (custo real)", "Planilha: aba **Horas** × custo/hora (aba Custos)", "sprint sem horas registradas usa o custo planejado"),
        ("SPI · CPI", "cálculo", "SPI = EV ÷ PV = APC ÷ PPC (prazo) · CPI = EV ÷ AC (custo). 1,0 = no plano"),
        ("ETC · EAC · RD", "cálculo", "ETC = (BAC − EV) ÷ CPI · EAC = AC + ETC · término = início + duração ÷ SPI"),
    ])
    if evm_df.empty:
        aviso_sem_dado("Sem dados do Zenhub para o AgileEVM",
                       "Ainda não há snapshot em `data/zenhub/velocity/`.",
                       "Rodar `python scripts/coleta_velocity.py` (ver a aba Velocity).")
    else:
        iniciadas = evm_df.dropna(subset=["PRP"])
        rels = list(dict.fromkeys(evm_df["release"]))
        padrao = iniciadas["release"].iloc[-1] if not iniciadas.empty else rels[0]
        rel_sel = st.radio("Release", rels, index=rels.index(padrao), horizontal=True, key="evm_rel")
        d = evm_df[evm_df["release"] == rel_sel]
        feitas = d.dropna(subset=["PRP"])
        if feitas.empty:
            st.info(f"A {rel_sel} ainda não começou.", icon="🗓️")
        else:
            u = feitas.iloc[-1]
            parcial = u["status"] == velocity.STATUS_ANDAMENTO
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Sprint", f"{u['sprint']} (fim {u['fim_da_sprint']:%d/%m})",
                      f"{len(feitas)} de {len(d)} da release" + (" · em andamento" if parcial else ""),
                      delta_color="off")
            c2.metric("Planejado (PPC)", pct(u["PPC"]))
            c3.metric("Realizado (APC)", pct(u["APC"]), f"{num(u['RPC'], 0)} de {num(u['PRP'], 0)} pontos",
                      delta_color="off")
            if pd.notna(u["SPI"]):
                c4.metric("SPI (prazo)", num(u["SPI"]), "no prazo" if u["SPI"] >= 0.95 else "atrasado",
                          delta_color="normal" if u["SPI"] >= 0.95 else "inverse")
            else:
                c4.metric("SPI (prazo)", "—")
            c5.metric("CPI (custo)", num(u["CPI"]),
                      "AC estimado" if str(u["origem_do_ac"]).startswith("estim") else "AC com horas reais",
                      delta_color="off")
            if pd.notna(u["SPI"]):
                st.markdown(
                    f"**Leitura:** até a {u['sprint']}, a {rel_sel} deveria ter entregue **{pct(u['PPC'])}** do escopo "
                    f"e entregou **{pct(u['APC'])}** ({num(u['RPC'], 0)} de {num(u['PRP'], 0)} pontos). "
                    + (f"No ritmo atual, terminaria em **{u['RD']:%d/%m/%Y}**. " if pd.notna(u["RD"]) else "")
                    + ("Valores da sprint em andamento são parciais." if parcial else ""))
            if str(u["origem_do_ac"]).startswith("estim"):
                st.caption("Sem horas registradas, AC = custo planejado e o CPI fica igual ao SPI. "
                           "Registrar horas na aba Horas faz o CPI medir custo de verdade.")
            base = u["prp_linha_de_base"]
            if pd.notna(base) and base > 0 and u["PRP"] > base * 1.5:
                st.warning(f"**O escopo da {rel_sel} cresceu de {num(base, 0)} para {num(u['PRP'], 0)} pontos** "
                           "durante a release (PA). Na planning, mover para a próxima release o que não termina nesta.",
                           icon="⚠️")

            if feitas["BAC"].notna().any():
                st.markdown("#### Valor planejado (PV), valor agregado (EV) e custo real (AC)")
                longo = feitas.melt(id_vars=["sprint"], value_vars=["PV", "EV", "AC"], var_name="serie",
                                    value_name="valor").dropna()
                nomes = {"PV": "PV — planejado", "EV": "EV — entregue", "AC": "AC — gasto"}
                longo["serie"] = longo["serie"].map(nomes)
                linha = (alt.Chart(longo).mark_line(point=alt.OverlayMarkDef(size=80, filled=True), strokeWidth=2.5)
                         .encode(x=alt.X("sprint:O", title="Sprint"), y=alt.Y("valor:Q", title="R$ acumulado na release"),
                                 color=alt.Color("serie:N", title=None,
                                                 scale=alt.Scale(domain=list(nomes.values()),
                                                                 range=[theme.INK["muted"], theme.SERIES[0],
                                                                        theme.STATUS["serious"]])),
                                 tooltip=["sprint:O", "serie:N", alt.Tooltip("valor:Q", format=",.2f")]))
                bac = pd.DataFrame({"y": [u["BAC"]], "t": [f"BAC {brl(u['BAC'])}"]})
                camadas = (linha + alt.Chart(bac).mark_rule(strokeDash=[6, 4], color=theme.INK["axis"]).encode(y="y:Q")
                           + alt.Chart(bac).mark_text(align="left", dy=-7, fontSize=11, color=theme.INK["secondary"])
                           .encode(y="y:Q", text="t:N", x=alt.value(0)))
                st.altair_chart(finalizar(camadas.properties(height=300)), use_container_width=True)
                st.caption("EV abaixo de PV = atraso. AC acima de EV = custou mais do que entregou.")

            st.markdown("#### Índices de desempenho (SPI e CPI)")
            idx = feitas.melt(id_vars=["sprint"], value_vars=["SPI", "CPI"], var_name="indice",
                              value_name="valor").dropna()
            if not idx.empty:
                graf = (alt.Chart(idx).mark_line(point=alt.OverlayMarkDef(size=80, filled=True), strokeWidth=2.5)
                        .encode(x=alt.X("sprint:O", title="Sprint"),
                                y=alt.Y("valor:Q", title="Índice",
                                        scale=alt.Scale(domain=[0, max(1.2, idx["valor"].max() + 0.1)])),
                                color=alt.Color("indice:N", title=None,
                                                scale=alt.Scale(domain=["SPI", "CPI"], range=theme.SERIES[:2])),
                                strokeDash=alt.StrokeDash("indice:N", legend=None,
                                                          scale=alt.Scale(domain=["SPI", "CPI"], range=[[1, 0], [5, 3]])),
                                tooltip=["sprint:O", "indice:N", alt.Tooltip("valor:Q", format=".2f")]))
                st.altair_chart(finalizar((graf + regra_um()).properties(height=260)), use_container_width=True)

            st.markdown("#### Burndown da release")
            b = feitas.assign(restante=feitas["PRP"] - feitas["RPC"], ideal=feitas["PRP"] * (1 - feitas["PPC"]))
            longo_b = b.melt(id_vars=["sprint"], value_vars=["restante", "ideal", "PRP"], var_name="serie",
                             value_name="pontos")
            nomes_b = {"restante": "Restante (real)", "ideal": "Restante ideal", "PRP": "Escopo da release (PRP)"}
            longo_b["serie"] = longo_b["serie"].map(nomes_b)
            graf_b = (alt.Chart(longo_b).mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=2.5)
                      .encode(x=alt.X("sprint:O", title="Sprint"), y=alt.Y("pontos:Q", title="Story points"),
                              color=alt.Color("serie:N", title=None,
                                              scale=alt.Scale(domain=list(nomes_b.values()),
                                                              range=[theme.SERIES[0], theme.INK["muted"],
                                                                     theme.STATUS["warning"]])),
                              strokeDash=alt.StrokeDash("serie:N", legend=None,
                                                        scale=alt.Scale(domain=list(nomes_b.values()),
                                                                        range=[[1, 0], [6, 4], [2, 2]])),
                              tooltip=["sprint:O", "serie:N", alt.Tooltip("pontos:Q", format=".0f")]))
            st.altair_chart(finalizar(graf_b.properties(height=300)), use_container_width=True)
            st.caption("Quando a linha do escopo (PRP) sobe, entrou trabalho novo na release — o restante sobe junto "
                       "mesmo que o time esteja entregando.")

        with st.expander("Ver o AgileEVM completo da release"):
            st.dataframe(d.drop(columns=["L"], errors="ignore"), use_container_width=True, hide_index=True)
        if not sumario.empty:
            with st.expander("Ver o sumário por release"):
                st.dataframe(sumario, use_container_width=True, hide_index=True)

# ───────────────────────── velocity (API do Zenhub) ─────────────────────────

with aba_vel_zh:
    velocity_dashboard.render(regras, zh_vel, zh_snap, zh_arquivo, finalizar)

# ───────────────────────── riscos ─────────────────────────

with aba_riscos:
    st.subheader("Riscos")
    st.caption(f"Fonte: {origem('riscos')} e {origem('monitoramento')}.")
    fonte_e_calculo([
        ("Risco, causa, resposta, responsável", "Aba **Riscos**", "preenchido pelo time (identificação e plano de resposta)"),
        ("Probabilidade e impacto", "Aba **Monitoramento** (uma linha por risco por sprint avaliada)",
         "escala de 1 a 5 (aba **Escalas**); vale a avaliação da sprint mais recente de cada risco"),
        ("Exposição", "idem", "probabilidade × impacto: 1 a 5 baixo, 6 a 12 médio, 15 a 25 elevado"),
        ("Matriz", "Aba **Riscos** (valores atuais)", "quantidade de riscos não encerrados em cada combinação de P e I"),
        ("Evolução", "Aba **Monitoramento**", "exposição de cada risco em cada sprint avaliada"),
    ])
    if riscos.empty:
        aviso_sem_dado("Aba Riscos não encontrada", f"Fonte lida: {origem('riscos')}.",
                       "Publicar a aba Riscos em CSV e colar o link em `config.py` (chave `riscos`).")
    else:
        r = riscos.dropna(subset=["exposicao_atual"]).copy()
        ativos = r[~r["status"].astype(str).str.lower().str.startswith("encerr")]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Riscos ativos", len(ativos))
        c2.metric("Exposição elevada (15 a 25)", int((ativos["exposicao_atual"] >= 15).sum()))
        c3.metric("Materializados", int(r["status"].astype(str).str.lower().str.startswith("materializ").sum()))
        sem_dono = int((ativos["responsavel"].astype(str).str.strip() == "").sum())
        c4.metric("Sem responsável", sem_dono)

        esq, dir_ = st.columns([1, 1])
        with esq:
            st.markdown("#### Matriz probabilidade × impacto")
            grade = pd.DataFrame([(p, i) for p in range(1, 6) for i in range(1, 6)], columns=["p", "i"])
            grade["exposicao"] = grade["p"] * grade["i"]
            cont = (ativos.assign(p=ativos["probabilidade_atual"], i=ativos["impacto_atual"])
                    .groupby(["p", "i"]).agg(ids=("id", lambda x: ", ".join(map(str, x)))).reset_index())
            grade = grade.merge(cont, on=["p", "i"], how="left").fillna({"ids": ""})
            fundo = (alt.Chart(grade).mark_rect(stroke="#fcfcfb", strokeWidth=2)
                     .encode(x=alt.X("p:O", title="Probabilidade"), y=alt.Y("i:O", title="Impacto", sort="descending"),
                             color=alt.Color("exposicao:Q", legend=None,
                                             scale=alt.Scale(domain=[1, 6, 15, 25], range=["#cdebd3", "#fce8b2", "#f4c7c3", "#e8998f"])),
                             tooltip=[alt.Tooltip("p:O", title="P"), alt.Tooltip("i:O", title="I"),
                                      alt.Tooltip("exposicao:Q", title="P×I"), alt.Tooltip("ids:N", title="Riscos")]))
            txt = (alt.Chart(grade[grade["ids"] != ""]).mark_text(fontSize=11, fontWeight="bold", color=theme.INK["primary"])
                   .encode(x="p:O", y=alt.Y("i:O", sort="descending"), text="ids:N"))
            st.altair_chart(finalizar((fundo + txt).properties(height=320)), use_container_width=True)
        with dir_:
            st.markdown("#### Exposição por categoria (EAR)")
            por_cat = ativos.groupby("categoria", as_index=False)["exposicao_atual"].sum()
            barras = (alt.Chart(por_cat).mark_bar(cornerRadiusEnd=4, size=22, color=theme.SERIES[0])
                      .encode(y=alt.Y("categoria:N", title=None, sort="-x"),
                              x=alt.X("exposicao_atual:Q", title="Exposição somada (P × I)"),
                              tooltip=["categoria:N", "exposicao_atual:Q"]))
            st.altair_chart(finalizar(barras.properties(height=320)), use_container_width=True)

        if not monit.empty and monit["sprint"].notna().any():
            st.markdown("#### Evolução da exposição por sprint")
            m = monit.dropna(subset=["exposicao"])
            m = m.merge(riscos[["id", "risco"]], left_on="id_do_risco", right_on="id", how="left")
            heat = (alt.Chart(m).mark_rect(stroke="#fcfcfb", strokeWidth=2)
                    .encode(x=alt.X("sprint:O", title="Sprint"), y=alt.Y("id_do_risco:N", title=None),
                            color=alt.Color("exposicao:Q", title="Exposição",
                                            scale=alt.Scale(domain=[1, 6, 15, 25], range=["#cdebd3", "#fce8b2", "#f4c7c3", "#e8998f"])),
                            tooltip=["id_do_risco:N", "risco:N", "sprint:O", "probabilidade:Q", "impacto:Q", "exposicao:Q", "status:N"]))
            txt = heat.mark_text(fontSize=11, color=theme.INK["primary"]).encode(text="exposicao:Q", color=alt.value(theme.INK["primary"]))
            st.altair_chart(finalizar((heat + txt).properties(height=24 * m["id_do_risco"].nunique() + 40)), use_container_width=True)
            if m["sprint"].nunique() < 2:
                st.caption("Só há uma avaliação (sprint 3). Cada planning em que o time reavaliar os riscos vira uma coluna nova.")

        st.markdown("#### Plano de riscos")
        cols = [c for c in ["id", "categoria", "risco", "probabilidade_atual", "impacto_atual", "exposicao_atual", "nivel",
                            "resposta", "acao_preventiva", "contingencia", "responsavel", "status"] if c in r]
        st.dataframe(r.sort_values("exposicao_atual", ascending=False)[cols]
                     .rename(columns={"probabilidade_atual": "P", "impacto_atual": "I", "exposicao_atual": "P×I"}),
                     use_container_width=True, hide_index=True)

# ───────────────────────── decisões ─────────────────────────

with aba_decisoes:
    st.subheader("Decisões baseadas em dados")
    st.caption(f"Fonte: {origem('decisoes')}.")
    fonte_e_calculo([
        ("Decisões", "Aba **Decisões** da planilha Riscos e Decisões",
         "registro do time: contexto e dado, decisão, evidência (onde está o número), critério de sucesso e resultado"),
        ("Meta da disciplina", "Plano de ensino EPS 2026.2", "≥ 3 decisões documentadas na R2 e ≥ 5 na R3"),
    ])
    if decisoes.empty:
        st.info("Nenhuma decisão registrada ainda.", icon="📝")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Decisões registradas", len(decisoes))
        c2.metric("Com resultado medido", int((decisoes.get("resultado", pd.Series(dtype=str)).astype(str).str.strip() != "").sum()))
        for _, d in decisoes.iterrows():
            with st.container(border=True):
                st.markdown(f"**{d.get('data', '')} · sprint {d.get('sprint', '')} · {d.get('indicador', '')}** · "
                            f"{d.get('tipo', '')} · _{d.get('status', '')}_")
                st.markdown(f"**Contexto e dado:** {d.get('contexto_e_dado', '')}")
                st.markdown(f"**Decisão:** {d.get('decisao', '')}")
                st.markdown(f"**Evidência:** {d.get('evidencia', '')}")
                st.markdown(f"**Critério de sucesso:** {d.get('criterio_de_sucesso', '')}")
                st.markdown(f"**Resultado:** {d.get('resultado', '') or '_em observação_'}")

st.divider()
st.caption("Produto e Processo: arquivos gerados pelo pipeline de CI/CD. Sprints, pontos, velocity, AgileEVM e "
           "burndown: API do Zenhub. Custos, time por semana, horas, riscos e decisões: planilha do time. "
           "Nenhum número é digitado no código.")
