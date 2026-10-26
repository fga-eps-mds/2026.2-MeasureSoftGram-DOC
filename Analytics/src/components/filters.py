"""Filtros do painel — todos na barra lateral, com o mesmo desenho em todas as páginas.

**Filtros globais** (sempre no topo da barra lateral, valem em todas as páginas onde a dimensão existe):

* **Release** — define o período padrão, as metas de qualidade e a release em foco (EVM, Gestão ágil);
* **Período** — recorta tudo o que tem data: coletas do Sonar (a "situação atual" passa a ser a do fim
  do período), sprints (as que terminam no período), execuções de CI, semanas de custo, horas,
  revisões de risco e decisões;
* **Repositórios** — Sonar, Zenhub (repositório da issue), EVM (prazo) e GitHub;
* **Branch** — só métricas do Sonar.

**Filtros da página** ficam logo abaixo, na seção "Filtros desta página" (:func:`da_pagina`), que também
diz, para a página aberta, como cada filtro global vale ali (ou que não se aplica). Nenhuma página
desenha filtro no corpo.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src.data import sonar as sn
from src.data.sonar import nome_curto
from src.metrics.calculations import release_atual

TODAS = "Semestre inteiro"
GLOBAIS = {"release": "Release", "periodo": "Período", "repos": "Repositórios", "branch": "Branch"}


def janela_release(release: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Início e fim de uma release: do dia seguinte à entrega anterior até a entrega dela."""
    nomes = list(config.RELEASES)
    fim = pd.Timestamp(config.RELEASES[release])
    i = nomes.index(release)
    inicio = (pd.Timestamp(config.RELEASES[nomes[i - 1]]) + pd.Timedelta(days=1) if i
              else pd.Timestamp(config.INICIO_SEMESTRE))
    return inicio, fim


def _repos(ctx) -> list[str]:
    """Repositórios do projeto que aparecem em alguma fonte (os do projeto primeiro, depois os outros do Zenhub)."""
    nomes = set()
    for df, col in ((ctx.sonar_atual, "repositorio"), (ctx.gh_runs, "repositorio"), (ctx.zh_issues, "repositorio")):
        if df is not None and not df.empty and col in df:
            nomes |= {str(r) for r in df[col].dropna().unique() if r and r != "—"}
    nomes = {config.APELIDOS_REPO.get(r, r) for r in nomes}
    prefixo = config.PREFIXO_REPOS_PROJETO
    return sorted({nome_curto(r) for r in nomes}, key=lambda c: (not (prefixo + c) in nomes, c.lower()))


def barra_lateral(ctx) -> dict:
    rel_hoje, _ = release_atual(ctx.hoje)
    with st.sidebar:
        st.header("Filtros globais")
        opcoes = [TODAS, *config.RELEASES]
        release = st.selectbox("Release", opcoes, index=opcoes.index(rel_hoje), key="f_release",
                               help="Define o período padrão, as metas de qualidade e a release em foco.")
        if release == TODAS:
            ini, fim = pd.Timestamp(config.INICIO_SEMESTRE), pd.Timestamp(list(config.RELEASES.values())[-1])
        else:
            ini, fim = janela_release(release)
        periodo = st.date_input("Período", value=(ini.date(), fim.date()), format="DD/MM/YYYY",
                                key=f"f_periodo_{release}",
                                help="Recorta tudo o que tem data. No Sonar, a situação mostrada é a do fim do período.")
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
        repos = _repos(ctx)
        repos_sel = st.multiselect("Repositórios", repos, default=[], key="f_repos", placeholder="Todos",
                                   help="Vale para Sonar, Zenhub (repositório da issue), EVM (prazo) e GitHub.")
        branches = sorted(set(ctx.sonar_pipeline["branch"].dropna()) if not ctx.sonar_pipeline.empty else set())
        branch = None
        if branches:
            padrao = config.SONAR_BRANCH if config.SONAR_BRANCH in branches else branches[0]
            branch = st.selectbox("Branch (Sonar)", branches, index=branches.index(padrao), key="f_branch",
                                  help="Coletas do pipeline desta branch. O snapshot da API é sempre da "
                                       f"branch {config.SONAR_BRANCH}.")
        st.caption("Cada bloco mostra a fonte do dado: SONAR, ZENHUB, PLANILHA ou GITHUB. "
                   "Datas e status das coletas em **Metodologia e Fontes**.")
    metas = rel_hoje if release == TODAS else release
    return {"release": None if release == TODAS else release, "release_rotulo": release, "release_metas": metas,
            "periodo": (ini, fim), "repos": repos_sel, "branch": branch}


def da_pagina(f: dict, aplica: dict[str, str | None], tem_filtros: bool = True):
    """Abre a seção "Filtros desta página" na barra lateral.

    ``aplica``: para cada filtro global (``release``, ``periodo``, ``repos``, ``branch``), como ele vale
    nesta página, ou ``None``/ausente quando não se aplica. Devolve o container onde a página põe os
    próprios filtros (fica antes do resumo de como os globais valem aqui).
    """
    sb = st.sidebar
    sb.divider()
    sb.subheader("Filtros desta página")
    caixa = sb.container()
    if not tem_filtros:
        caixa.caption("Esta página não tem filtros próprios.")
    linhas = []
    for chave, rotulo in GLOBAIS.items():
        como = aplica.get(chave)
        ativo = {"release": f.get("release_rotulo"), "periodo": None, "repos": ", ".join(f.get("repos") or [])
                 or "todos", "branch": f.get("branch")}.get(chave)
        if como:
            linhas.append(f"**{rotulo}**{f' ({ativo})' if ativo and chave != 'periodo' else ''}: {como}")
        else:
            linhas.append(f"~~{rotulo}~~: não se aplica nesta página")
    with sb.expander("Como os filtros globais valem aqui", expanded=False):
        st.markdown("\n".join(f"- {x}" for x in linhas))
    return caixa


def resumo_ativos(f: dict, aplica: dict[str, str | None]) -> str:
    """Frase curta com os filtros globais que estão valendo na página (para a legenda de gráficos e tabelas)."""
    partes = []
    if aplica.get("periodo"):
        partes.append(f"{f['periodo'][0]:%d/%m/%Y} a {f['periodo'][1]:%d/%m/%Y}")
    if aplica.get("repos") and f.get("repos"):
        partes.append("repositórios: " + ", ".join(f["repos"]))
    if aplica.get("branch") and f.get("branch"):
        partes.append(f"branch {f['branch']}")
    return " · ".join(partes)


# ───────────────────────── Sonar no recorte ─────────────────────────

def sonar(ctx, f: dict) -> dict:
    """Dados do Sonar no recorte global: branch, repositórios e período.

    * ``serie``: coletas dentro do período (gráficos de evolução);
    * ``serie_ate``: coletas até o fim do período (variação "atual × anterior" no fim do período);
    * ``atual``: valor de cada métrica em cada repositório **no fim do período** (última coleta até lá);
    * ``repos``: nomes completos dos repositórios no recorte;
    * ``fim``: fim do período; ``api_no_periodo``: o snapshot da API (Quality Gate, problemas por
      severidade) foi tirado até o fim do período — se não, esses dados são de depois e ficam de fora.
    """
    fim = pd.Timestamp(f["periodo"][1]) + pd.Timedelta(days=1)
    serie = ctx.sonar_serie
    if serie is not None and not serie.empty and f.get("branch"):
        serie = serie[(serie["branch"] == f["branch"]) | (serie["origem"] == "api")]
    partes = []
    pipe = ctx.sonar_pipeline
    if pipe is not None and not pipe.empty:
        if f.get("branch"):
            pipe = pipe[pipe["branch"] == f["branch"]]
        partes.append(pipe[["repositorio", "metrica", "valor", "coleta"]])
    api = ctx.sonar_api or {}
    for chave in ("historico", "medidas"):
        d = api.get(chave, pd.DataFrame())
        if d is not None and not d.empty:
            partes.append(d[["repositorio", "metrica", "valor", "coleta"]])
    todas = pd.concat(partes, ignore_index=True).dropna(subset=["coleta"]) if partes else pd.DataFrame(
        columns=["repositorio", "metrica", "valor", "coleta"])
    todas = todas[pd.to_datetime(todas["coleta"]) < fim]
    atual = sn.ultimo_por_repo(todas)
    nomes = set(atual["repositorio"]) | (set(serie["repositorio"]) if serie is not None and not serie.empty else set())
    repos = sorted(r for r in nomes if not f.get("repos") or nome_curto(r) in f["repos"])
    serie_ate = serie[pd.to_datetime(serie["coleta"]) < fim] if serie is not None and not serie.empty else serie
    snap = getattr(ctx, "sonar_api_snap", None) or {}
    coleta_api = pd.to_datetime(snap.get("coletado_em"), utc=True, errors="coerce")
    api_ok = pd.notna(coleta_api) and coleta_api.tz_convert(None) < fim
    return {"serie": por_periodo(serie, "coleta", f["periodo"]), "serie_ate": serie_ate,
            "atual": atual[atual["repositorio"].isin(repos)], "repos": repos, "fim": fim - pd.Timedelta(days=1),
            "api_no_periodo": bool(api_ok)}


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
