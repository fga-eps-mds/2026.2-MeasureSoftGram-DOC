"""Filtros globais (barra lateral) e utilitários de filtragem.

Globais, válidos em todas as páginas onde a dimensão existe:

* **Release** — define o período padrão e as metas de qualidade;
* **Período** — recorta séries temporais (coletas do Sonar, sprints, semanas de custo);
* **Repositórios** — métricas do Sonar, issues do Zenhub e CI do GitHub;
* **Branch** — só métricas do Sonar.

Filtros que só fazem sentido numa fonte (severidade, sprint, épico,
responsável, prioridade, categoria de risco...) ficam na própria página, e só
aparecem quando o dado tem aquela dimensão.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src.data.sonar import nome_curto
from src.metrics.calculations import release_atual

TODAS = "Semestre inteiro"


def janela_release(release: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Início e fim de uma release: do dia seguinte à entrega anterior até a entrega dela."""
    nomes = list(config.RELEASES)
    fim = pd.Timestamp(config.RELEASES[release])
    i = nomes.index(release)
    inicio = (pd.Timestamp(config.RELEASES[nomes[i - 1]]) + pd.Timedelta(days=1) if i
              else pd.Timestamp(config.INICIO_SEMESTRE))
    return inicio, fim


def _repos(ctx) -> list[str]:
    nomes = set()
    for df, col in ((ctx.sonar_atual, "repositorio"), (ctx.gh_runs, "repositorio"), (ctx.zh_issues, "repositorio")):
        if df is not None and not df.empty and col in df:
            nomes |= {nome_curto(r) for r in df[col].dropna().unique() if r and r != "—"}
    return sorted(nomes)


def barra_lateral(ctx) -> dict:
    rel_hoje, _ = release_atual(ctx.hoje)
    with st.sidebar:
        st.header("Filtros globais")
        opcoes = [TODAS, *config.RELEASES]
        release = st.selectbox("Release", opcoes, index=opcoes.index(rel_hoje), key="f_release",
                               help="Define o período padrão e as metas de qualidade usadas nos status.")
        if release == TODAS:
            ini, fim = pd.Timestamp(config.INICIO_SEMESTRE), pd.Timestamp(list(config.RELEASES.values())[-1])
        else:
            ini, fim = janela_release(release)
        periodo = st.date_input("Período", value=(ini.date(), fim.date()), format="DD/MM/YYYY",
                                key=f"f_periodo_{release}",
                                help="Recorta coletas do Sonar, sprints do Zenhub e semanas de custo.")
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
        repos = _repos(ctx)
        repos_sel = st.multiselect("Repositórios", repos, default=[], key="f_repos", placeholder="Todos",
                                   help="Vale para Sonar, Zenhub (repositório da issue) e GitHub.")
        branches = sorted(b for b in set(ctx.sonar_pipeline["branch"].dropna()) if b) \
            if not ctx.sonar_pipeline.empty else []
        branch = None
        if branches:
            padrao = config.SONAR_BRANCH if config.SONAR_BRANCH in branches else branches[0]
            branch = st.selectbox("Branch (Sonar)", branches, index=branches.index(padrao), key="f_branch")
        st.divider()
        st.caption("Cada bloco mostra a fonte do dado: SONAR, ZENHUB, PLANILHA ou GITHUB. "
                   "Datas e status das coletas em **Metodologia e Fontes**.")
    metas = rel_hoje if release == TODAS else release
    return {"release": None if release == TODAS else release, "release_rotulo": release, "release_metas": metas,
            "periodo": (ini, fim), "repos": repos_sel, "branch": branch}


# ───────────────────────── utilitários ─────────────────────────

def por_periodo(df: pd.DataFrame, coluna: str, periodo: tuple, fim_coluna: str | None = None) -> pd.DataFrame:
    """Linhas cuja data (ou intervalo ``coluna``..``fim_coluna``) toca o período. Datas com fuso viram BRT."""
    if df is None or df.empty or coluna not in df:
        return df
    ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1]) + pd.Timedelta(days=1)

    def local(s):
        s = pd.to_datetime(s)
        if getattr(s.dt, "tz", None) is not None:
            try:
                s = s.dt.tz_convert("America/Sao_Paulo")
            except Exception:  # noqa: BLE001
                s = s.dt.tz_convert("UTC") - pd.Timedelta(hours=3)
            s = s.dt.tz_localize(None)
        return s

    a = local(df[coluna])
    if fim_coluna and fim_coluna in df:
        b = local(df[fim_coluna])
        return df[(b >= ini) & (a < fim)]
    return df[(a >= ini) & (a < fim)]


def por_repo(df: pd.DataFrame, repos: list[str], coluna: str = "repositorio") -> pd.DataFrame:
    if df is None or df.empty or not repos or coluna not in df:
        return df
    return df[df[coluna].map(nome_curto).isin(repos)]
