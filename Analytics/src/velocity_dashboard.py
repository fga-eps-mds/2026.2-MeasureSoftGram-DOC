"""Aba "Velocity (Zenhub)": gráfico, cards, filtros e tabela.

Camada visual apenas. Os dados vêm do snapshot gravado por
``scripts/coleta_velocity.py`` (``src/zenhub``) e os números de
``src/velocity.py``. Nenhuma query GraphQL aqui.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src import velocity as vel
from src.zenhub import coleta

RAIZ = Path(__file__).resolve().parents[1]
NO_NAVEGADOR = sys.platform == "emscripten"  # stlite (GitHub Pages): sem chave, sem rede para o Zenhub

COR_PLANNED = theme.SERIES[0]
COR_COMPLETED = theme.SERIES[1]
SEM_RELEASE = "Sem release"


# ───────────────────────── dados ─────────────────────────

@st.cache_data(show_spinner="Lendo o snapshot do Zenhub...")
def _carregar(pasta: str, marca: tuple) -> tuple:
    """Cache invalidado pela lista de arquivos (``marca``): só relê quando há coleta nova."""
    snap, nome = coleta.ultimo_snapshot(Path(pasta))
    return snap, nome, coleta.ler_linhas_de_base(Path(pasta))


def _marca(pasta: Path) -> tuple:
    return tuple(sorted((p.name, p.stat().st_mtime) for p in pasta.glob("*.json"))) if pasta.exists() else ()


def carregar_velocity(regras: vel.Regras, calendario_df: pd.DataFrame, agora: datetime):
    pasta = coleta.PASTA
    snap, nome, linhas = _carregar(str(pasta), _marca(pasta))
    if not snap:
        return pd.DataFrame(), None, ""
    calendario, rotulos = {}, {}
    if calendario_df is not None and not calendario_df.empty and "zenhub_sprint_id" in calendario_df:
        for _, c in calendario_df.iterrows():
            if str(c["zenhub_sprint_id"]).strip():
                calendario[c["zenhub_sprint_id"]] = c["release"]
                rotulos[c["zenhub_sprint_id"]] = f"S{int(c['sprint'])}"
    df = vel.calculate_velocity(snap, regras, agora, linhas, calendario, rotulos)
    return df, snap, nome


def _pode_atualizar() -> tuple[bool, str]:
    if NO_NAVEGADOR:
        return False, ("Na versão publicada (GitHub Pages) a chave do Zenhub não pode ir para o navegador. "
                       "Os dados são atualizados pelo workflow `zenhub-velocity.yml`; localmente, rode "
                       "`streamlit run app.py` com `ZENHUB_API_KEY` no `.env`.")
    from src.zenhub.client import carregar_env, chave_do_ambiente
    carregar_env(RAIZ / ".env")
    if not chave_do_ambiente():
        return False, "Defina `ZENHUB_API_KEY` em `Analytics/.env` para consultar a API a partir daqui."
    return True, "Consulta a API do Zenhub agora e grava um snapshot novo."


def botao_atualizar() -> None:
    pode, ajuda = _pode_atualizar()
    if st.button("🔄 Atualizar dados", disabled=not pode, help=ajuda, key="zh_atualizar"):
        from scripts.coleta_velocity import executar
        from src.zenhub.client import (ZenhubAuthError, ZenhubError, ZenhubRateLimitError,
                                       ZenhubUnavailableError)
        mensagens: list[str] = []
        try:
            with st.spinner("Consultando o Zenhub (pode levar alguns minutos por causa do limite de complexidade)..."):
                executar(log=mensagens.append)
        except ZenhubAuthError as e:
            st.error(f"**Autenticação recusada.** {e}", icon="🔑")
            return
        except ZenhubRateLimitError as e:
            st.warning(f"**Limite de uso do Zenhub.** {e}", icon="⏳")
            return
        except ZenhubUnavailableError as e:
            st.warning(f"**Zenhub indisponível.** {e} O painel continua com o último snapshot.", icon="📡")
            return
        except ZenhubError as e:
            st.error(f"**Erro ao consultar o Zenhub.** {e}")
            return
        st.cache_data.clear()
        st.session_state["zh_log"] = mensagens
        st.rerun()
    if not pode:
        st.caption(ajuda)


# ───────────────────────── filtros ─────────────────────────

def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Filtros numa linha acima do gráfico. Sem seleção = tudo."""
    d = df.assign(release_filtro=df["release_name"].fillna(SEM_RELEASE))
    c1, c2, c3, c4 = st.columns([1.1, 1.4, 1.3, 1.2])
    rels = c1.multiselect("Release", sorted(d["release_filtro"].unique()), key="zh_rel",
                          placeholder="Todas")
    sprints = c2.multiselect("Sprint", list(d["sprint_label"]), key="zh_sprint", placeholder="Todas",
                             format_func=lambda s: f"{s} · {d.loc[d['sprint_label'] == s, 'sprint_name'].iloc[0]}")
    ini, fim = d["start_date"].min().date(), d["end_date"].max().date()
    periodo = c3.date_input("Período", value=(ini, fim), min_value=ini, max_value=fim, format="DD/MM/YYYY",
                            key="zh_periodo")
    status = c4.multiselect("Situação", [vel.STATUS_CONCLUIDA, vel.STATUS_ANDAMENTO, vel.STATUS_CANCELADA],
                            key="zh_status", placeholder="Todas")
    if rels:
        d = d[d["release_filtro"].isin(rels)]
    if sprints:
        d = d[d["sprint_label"].isin(sprints)]
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        tz = d["start_date"].dt.tz
        a = pd.Timestamp(periodo[0]).tz_localize(tz)
        b = pd.Timestamp(periodo[1]).tz_localize(tz) + pd.Timedelta(days=1)
        d = d[(d["end_date"] > a) & (d["start_date"] < b)]
    if status:
        d = d[d["status"].isin(status)]
    return d


# ───────────────────────── cards ─────────────────────────

def _sp(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} SP".replace(",", ".")


def render_metrics(df: pd.DataFrame, media: dict) -> None:
    concluidas = df[df["status"] == vel.STATUS_CONCLUIDA].sort_values("end_date")
    ultima = concluidas.iloc[-1] if not concluidas.empty else None
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Average Velocity", _sp(media["valor"]),
              f"média de {media['n']} sprints concluídas" if media["valor"] is not None else media["motivo"],
              delta_color="off")
    if ultima is None:
        c2.metric("Última sprint concluída", "—")
        for c, t in ((c3, "SP concluídos"), (c4, "SP planejados"), (c5, "Completion rate")):
            c.metric(t, "—")
    else:
        c2.metric("Última sprint concluída", ultima["sprint_label"],
                  f"{ultima['start_date']:%d/%m} a {ultima['end_date']:%d/%m}", delta_color="off")
        c3.metric("SP concluídos (velocity)", _sp(ultima["completed_story_points"]),
                  f"{int(ultima['completed_issues'])} issues", delta_color="off")
        c4.metric("SP planejados", _sp(ultima["planned_story_points"]),
                  f"{int(ultima['planned_issues'])} issues" if pd.notna(ultima["planned_issues"])
                  else "sem linha de base", delta_color="off")
        taxa = ultima["completion_rate"]
        c5.metric("Completion rate", "—" if taxa is None or pd.isna(taxa) else f"{taxa:.0f}%",
                  "concluído ÷ planejado" if taxa is not None and pd.notna(taxa) else "planejado zero ou indisponível",
                  delta_color="off")

    andamento = df[df["status"] == vel.STATUS_ANDAMENTO]
    for _, s in andamento.iterrows():
        st.info(f"**{s['sprint_label']} — em andamento** ({s['start_date']:%d/%m} a {s['end_date']:%d/%m}) · "
                f"planejado **{_sp(s['planned_story_points'])}** · concluído até agora "
                f"**{_sp(s['completed_story_points'])}**. Valores parciais: esta sprint não entra na Average Velocity.",
                icon="⏱️")


# ───────────────────────── gráfico ─────────────────────────

def render_velocity_chart(df: pd.DataFrame, media: dict, finalizar) -> None:
    d = df.sort_values("start_date").copy()
    d["eixo"] = d.apply(lambda r: r["sprint_label"] + (" (parcial)" if r["status"] == vel.STATUS_ANDAMENTO
                                                         else " (cancelada)" if r["status"] == vel.STATUS_CANCELADA
                                                         else ""), axis=1)
    longo = pd.concat([
        d.assign(serie="Planned", pontos=d["planned_story_points"], issues=d["planned_issues"]),
        d.assign(serie="Completed (velocity)", pontos=d["completed_story_points"], issues=d["completed_issues"]),
    ])
    longo = longo.dropna(subset=["pontos"])
    longo["parcial"] = longo["status"] != vel.STATUS_CONCLUIDA
    longo["periodo"] = longo["start_date"].dt.strftime("%d/%m") + " a " + longo["end_date"].dt.strftime("%d/%m")
    longo["release"] = longo["release_name"].fillna(SEM_RELEASE)
    ordem = list(d["eixo"])
    series = ["Planned", "Completed (velocity)"]

    barras = (alt.Chart(longo).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=18,
                                         stroke="#fcfcfb", strokeWidth=2)
              .encode(x=alt.X("eixo:N", title="Sprint", sort=ordem, axis=alt.Axis(labelAngle=0)),
                      xOffset=alt.XOffset("serie:N", sort=series),
                      y=alt.Y("pontos:Q", title="Story Points"),
                      color=alt.Color("serie:N", title=None, sort=series,
                                      scale=alt.Scale(domain=series, range=[COR_PLANNED, COR_COMPLETED])),
                      opacity=alt.condition("datum.parcial", alt.value(0.45), alt.value(1)),
                      tooltip=[alt.Tooltip("sprint_name:N", title="Sprint"), alt.Tooltip("release:N", title="Release"),
                               alt.Tooltip("periodo:N", title="Período"), alt.Tooltip("status:N", title="Situação"),
                               alt.Tooltip("serie:N", title="Série"), alt.Tooltip("pontos:Q", title="SP", format=".0f"),
                               alt.Tooltip("issues:Q", title="Issues", format=".0f")]))
    rotulos = barras.mark_text(dy=-7, fontSize=11, color=theme.INK["secondary"]).encode(
        text=alt.Text("pontos:Q", format=".0f"), opacity=alt.value(1), color=alt.value(theme.INK["secondary"]))
    camadas = barras + rotulos
    if media["valor"] is not None:
        m = pd.DataFrame({"y": [media["valor"]], "t": [f"Average Velocity = {media['valor']:.0f} SP"]})
        camadas = (camadas
                   + alt.Chart(m).mark_rule(strokeDash=[6, 4], strokeWidth=2, color=theme.INK["primary"]).encode(y="y:Q")
                   + alt.Chart(m).mark_text(align="left", dx=4, dy=-8, fontSize=12, fontWeight="bold",
                                            color=theme.INK["primary"]).encode(y="y:Q", text="t:N", x=alt.value(0)))
    st.altair_chart(finalizar(camadas.properties(height=340)), use_container_width=True)
    legenda = "Barras claras = sprint em andamento (parcial) ou cancelada, fora da média."
    if media["valor"] is not None:
        legenda += f" Linha tracejada = Average Velocity das sprints concluídas ({', '.join(media['sprints'])})."
    else:
        legenda += f" Average Velocity não exibida: {media['motivo']}."
    if d["planned_story_points"].isna().any():
        legenda += " Sprint sem barra azul = planejado indisponível (ver tabela)."
    st.caption(legenda)


# ───────────────────────── tabela ─────────────────────────

def render_table(df: pd.DataFrame) -> None:
    busca = st.text_input("Filtrar a tabela", placeholder="sprint, release, situação...", key="zh_busca")
    t = pd.DataFrame({
        "Sprint": df["sprint_label"] + " · " + df["sprint_name"],
        "Release": df["release_name"].fillna("—"),
        "Período": df["start_date"].dt.strftime("%d/%m/%Y") + " a " + df["end_date"].dt.strftime("%d/%m/%Y"),
        "Situação": df["status"],
        "Planned SP": df["planned_story_points"],
        "Completed SP": df["completed_story_points"],
        "Issues planejadas": df["planned_issues"],
        "Issues concluídas": df["completed_issues"],
        "Completion rate": df["completion_rate"],
        "Adicionado depois (SP concluídos)": df["completed_unplanned_story_points"],
        "Escopo atual SP": df["current_story_points"],
        "Zenhub completedPoints": df["zenhub_completed_points"],
        "Linha de base": df["baseline_source"],
        "Fonte da release": df["release_source"],
        "Observações": df["notes"],
    })
    if busca:
        t = t[t.astype(str).apply(lambda s: s.str.contains(busca, case=False, regex=False)).any(axis=1)]
    st.dataframe(t, use_container_width=True, hide_index=True, column_config={
        "Planned SP": st.column_config.NumberColumn(format="%.0f"),
        "Completed SP": st.column_config.NumberColumn(format="%.0f"),
        "Issues planejadas": st.column_config.NumberColumn(format="%d"),
        "Issues concluídas": st.column_config.NumberColumn(format="%d"),
        "Completion rate": st.column_config.NumberColumn(format="%.0f%%"),
        "Adicionado depois (SP concluídos)": st.column_config.NumberColumn(format="%.0f"),
        "Escopo atual SP": st.column_config.NumberColumn(format="%.0f"),
        "Zenhub completedPoints": st.column_config.NumberColumn(format="%.0f"),
    })
    st.caption("Clique no cabeçalho para ordenar. 'Zenhub completedPoints' é o número do próprio Zenhub, só para "
               "conferência: ele usa o estado atual das issues, não a data de conclusão.")


# ───────────────────────── aba ─────────────────────────

def render(params: dict, calendario_df: pd.DataFrame, finalizar) -> None:
    st.subheader("Velocity por sprint (API do Zenhub)")
    regras = vel.Regras.dos_parametros(params)
    agora = datetime.now(timezone.utc)
    df, snap, nome = carregar_velocity(regras, calendario_df, agora)

    topo_e, topo_d = st.columns([3, 1])
    with topo_d:
        botao_atualizar()
    with topo_e:
        if snap:
            quando = pd.Timestamp(snap["coletado_em"])
            try:
                quando = quando.tz_convert("America/Sao_Paulo")
            except Exception:  # noqa: BLE001 — sem base de fusos no navegador
                quando = quando - pd.Timedelta(hours=3)
            st.caption(f"Fonte: Zenhub GraphQL, workspace `{snap.get('workspace_id')}` · coleta de "
                       f"**{quando:%d/%m/%Y %H:%M}** (`{nome}`) · {snap.get('requisicoes', '?')} requisições. "
                       f"Janela de planning: {regras.janela_planning.total_seconds() / 3600:.0f} h · "
                       f"pontuam: {', '.join(sorted(regras.tipos_pontuados))} · feito: fechada ou `{regras.pipeline_feito}`.")
    for linha in st.session_state.pop("zh_log", []):
        st.caption(linha)

    with st.expander("📌 Como cada número é calculado"):
        st.markdown(
            "| Indicador | Regra |\n|---|---|\n"
            "| **Planned SP** | Issues pontuáveis na sprint ao fim da janela de planning, pelo histórico "
            "`Sprint.scopeChange` (entradas e saídas com data); estimativa do momento da entrada. Congelado em "
            "`linhas-de-base.json` na primeira coleta após a janela. Sem histórico: *indisponível* (nunca o escopo atual). |\n"
            "| **Completed SP (velocity)** | Issues pontuáveis concluídas entre o início e o fim da sprint *e* que estavam "
            "na sprint naquele momento. Conclusão = `closedAt`; aberta no pipeline de feito = "
            "`pipelineIssue.latestTransferTime`. |\n"
            "| **Issue sem estimativa** | Conta como issue, com 0 SP, e aparece nas observações. |\n"
            "| **Average Velocity** | Média da velocity das sprints *concluídas* no filtro (a em andamento e as "
            f"canceladas ficam fora); só com ≥ {regras.min_sprints_media} sprints. |\n"
            "| **Completion rate** | Completed ÷ Planned × 100; vazio quando o planejado é zero ou indisponível. |\n"
            "| **Release** | Release do Zenhub que contém mais issues da sprint; sem isso, a que cobre a data; sem isso, "
            "o calendário do time (`planilhas/sprints.csv`). |")

    if df.empty:
        st.warning("**Ainda não há snapshot de velocity do Zenhub.** Rode `python scripts/coleta_velocity.py` "
                   "(com `ZENHUB_API_KEY` no `Analytics/.env`) ou use o botão **Atualizar dados**. O painel não "
                   "mostra números de exemplo.", icon="📭")
        return
    # datas exibidas no horário de Brasília (o fim 02:59 UTC é 23:59 do domingo)
    for col in ("start_date", "end_date"):
        try:
            df[col] = df[col].dt.tz_convert("America/Sao_Paulo")
        except Exception:  # noqa: BLE001 — sem base de fusos no navegador
            df[col] = df[col] - pd.Timedelta(hours=3)
    for aviso in snap.get("avisos", []):
        st.caption(f"⚠️ {aviso}")

    d = render_filters(df)
    if d.empty:
        st.info("Nenhuma sprint no filtro selecionado.")
        return
    media = vel.calculate_average_velocity(d, regras.min_sprints_media)
    render_metrics(d, media)
    st.markdown("#### Velocity por sprint")
    render_velocity_chart(d, media, finalizar)
    st.markdown("#### Detalhes")
    render_table(d)
