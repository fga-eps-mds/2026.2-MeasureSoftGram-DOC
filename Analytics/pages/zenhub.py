"""Gestão ágil — planejado × realizado em Story Points, com rastreabilidade até a issue (fonte ZENHUB).

Ordem da página: filtros → KPIs → planejamento → realizado → planejado × realizado →
velocity → burndown → análises qualitativas → detalhamento das issues → confiabilidade
dos dados. Todo número sai de ``gestao_agil.stories_por_sprint`` (uma linha por Story
em cada sprint) depois dos filtros, então os blocos ficam sincronizados e cada total
pode ser aberto até as issues.
"""

from __future__ import annotations

import sys

import altair as alt
import pandas as pd
import streamlit as st

import config
from pages import zenhub_dados as apoio
from src import theme
from src.data import contexto
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.metrics import gestao_agil as ga
from src.metrics import velocity as vel
from src.metrics.calculations import data_br, num, pct, status_taxa

COR_PLAN, COR_REAL, COR_EXTRA = theme.SERIES[2], theme.SERIES[0], theme.SERIES[1]
SERIES_PR = ["Planejado", "Realizado"]
ESCALA_PR = alt.Scale(domain=SERIES_PR, range=[COR_PLAN, COR_REAL])
COR_RESULTADO = alt.Scale(domain=ga.RESULTADOS + [ga.EM_ANDAMENTO],
                          range=[COR_REAL, theme.STATUS["critical"], COR_EXTRA, theme.STATUS["warning"],
                                 theme.NEUTRO_CLARO, theme.INK["muted"]])

COLUNAS_STORY = {
    "release": "Release", "sprint": "Sprint", "epico": "Épico", "issue": "Issue", "titulo": "Título", "url": "Link",
    "tipo": "Tipo", "sp_planejado": "SP planejado", "sp_realizado": "SP realizado", "sp_atual": "SP atual",
    "resultado": "Resultado na sprint", "status_atual": "Status atual", "pipeline": "Pipeline",
    "levada_para": "Levada para", "criada_em": "Criada em", "entrou_em": "Entrou na sprint",
    "saiu_em": "Saiu da sprint", "concluida_em": "Concluída em", "responsavel": "Responsável",
}


def _sp(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{num(v)} SP"


def _brt(serie: pd.Series) -> pd.Series:
    s = pd.to_datetime(serie, utc=True, errors="coerce")
    return s.dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)


def _botao_atualizar(ctx) -> None:
    """Coleta nova pela API (só rodando localmente com a chave no .env)."""
    if sys.platform == "emscripten":
        st.caption("Na versão publicada os dados do Zenhub são atualizados pelo workflow `coleta-dados.yml`.")
        return
    from src.zenhub.client import carregar_env, chave_do_ambiente
    from src.data.contexto import RAIZ
    carregar_env(RAIZ / ".env")
    pode = bool(chave_do_ambiente())
    if st.button("Atualizar dados do Zenhub", disabled=not pode, key="zh_atualizar",
                 help="Consulta a API do Zenhub agora e grava um snapshot novo." if pode
                 else "Defina ZENHUB_API_KEY em Analytics/.env."):
        from scripts.coleta_velocity import executar
        from src.zenhub.client import ZenhubError
        try:
            with st.spinner("Consultando o Zenhub (alguns minutos por causa do limite de complexidade)..."):
                executar(log=lambda _m: None)
        except ZenhubError as e:
            st.error(f"Não foi possível atualizar: {e}. O painel continua com o último snapshot.")
            return
        st.cache_data.clear()
        st.rerun()


def tabela_stories(df: pd.DataFrame, chave: str, arquivo: str, colunas: list[str] | None = None) -> None:
    """Tabela de stories com link para a issue e download do CSV (o mesmo recorte da tela)."""
    if df is None or df.empty:
        st.caption("Nenhuma story neste recorte.")
        return
    cols = colunas or list(COLUNAS_STORY)
    t = df[[c for c in cols if c in df]].copy()
    for c in ("criada_em", "entrou_em", "saiu_em", "concluida_em"):
        if c in t:
            t[c] = _brt(t[c])
    # links embutidos no próprio texto: Issue e Título abrem a issue; Épico abre o épico
    url = df.loc[t.index, "url"] if "url" in df else pd.Series(None, index=t.index)
    if "issue" in t:
        t["issue"] = [layout.link_celula(u, ga.rotulo_issue(i)) for i, u in zip(t["issue"], url)]
    if "titulo" in t:
        t["titulo"] = [layout.link_celula(u, x) for x, u in zip(t["titulo"], url)]
    if "epico" in t and "epico_url" in df:
        t["epico"] = [layout.link_celula(u, x) for x, u in zip(t["epico"], df.loc[t.index, "epico_url"])]
    t = t.drop(columns=["url"], errors="ignore")
    for c in ("sp_planejado", "sp_realizado", "sp_atual"):
        if c in t:   # ausente vira "—" (a tabela mostraria "None")
            t[c] = t[c].map(lambda v: "—" if v is None or pd.isna(v) else num(v))
    t = t.rename(columns=COLUNAS_STORY)
    datas = {v: st.column_config.DatetimeColumn(v, format="DD/MM/YYYY HH:mm") for k, v in COLUNAS_STORY.items()
             if k in ("criada_em", "entrou_em", "saiu_em", "concluida_em")}
    st.dataframe(t, use_container_width=True, hide_index=True, key=f"tab_{chave}", column_config={
        "Issue": layout.coluna_link("Issue", help="clique para abrir a issue"),
        "Título": layout.coluna_link("Título", width="large", help="clique para abrir a issue"),
        "Épico": layout.coluna_link("Épico", help="clique para abrir o épico"),
        "SP planejado": st.column_config.TextColumn("SP planejado", help="pontos na planning; — = não planejada"),
        "SP realizado": st.column_config.TextColumn("SP realizado", help="pontos concluídos; — = não concluída"),
        "SP atual": st.column_config.TextColumn("SP atual", help="estimativa hoje; — = sem estimativa"), **datas})
    csv = t.copy()
    for c in ("Issue", "Título", "Épico"):
        if c in csv:
            csv[c] = csv[c].map(layout.texto_de_link)
    if "Issue" in csv:
        csv.insert(csv.columns.get_loc("Issue") + 1, "Link", url.values)
    st.download_button(f"Baixar CSV ({len(t)} linhas)", csv.to_csv(index=False).encode("utf-8-sig"),
                       file_name=arquivo, mime="text/csv", key=f"csv_{chave}")


# ───────────────────────── 1. filtros ─────────────────────────

def _filtros(ctx, f, linhas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(sprints do recorte, linhas do recorte, descrição). Os filtros se combinam (E)."""
    sprints = ctx.zh_iniciadas.sort_values("start_date").copy()
    sprints["release_name"] = sprints["release_name"].fillna("Sem release")
    sprints["ultimo_dia"] = _brt(sprints["end_date"] - pd.Timedelta(seconds=1)).dt.normalize()
    sprints["primeiro_dia"] = _brt(sprints["start_date"]).dt.normalize()
    rotulo = {r.sprint_label: f"{r.sprint_label} · {data_br(r.primeiro_dia)} a {data_br(r.ultimo_dia)} · "
                              f"{r.release_name}" for r in sprints.itertuples()}
    c = st.columns([1.0, 1.6, 1.3, 1.6, 1.5, 1.4])
    rels = list(dict.fromkeys(sprints["release_name"]))
    rel_sel = c[0].multiselect("Release", rels, key="ga_release", placeholder="Todas")
    opc = sprints[sprints["release_name"].isin(rel_sel)] if rel_sel else sprints
    spr_sel = c[1].multiselect("Sprint", list(opc["sprint_label"]), format_func=rotulo.get, key="ga_sprint",
                               placeholder="Todas as da release" if rel_sel else "Todas")
    per = c[2].date_input("Período (último dia da sprint)", value=(f["periodo"][0].date(), f["periodo"][1].date()),
                          format="DD/MM/YYYY", key="ga_periodo",
                          help="Entram as sprints cujo último dia cai no período; as entregas no tempo usam a data "
                               "de conclusão. Começa no período da barra lateral.")
    ini, fim = (pd.Timestamp(per[0]), pd.Timestamp(per[1])) if isinstance(per, (tuple, list)) and len(per) == 2 \
        else f["periodo"]
    s = opc[opc["sprint_label"].isin(spr_sel)] if spr_sel else opc
    no_periodo = (s["ultimo_dia"] >= ini) & (s["ultimo_dia"] <= fim)
    fora = list(s.loc[~no_periodo, "sprint_label"]) if spr_sel else []
    s = s[no_periodo]
    base = filters.por_repo(linhas[linhas["sprint_id"].isin(s["sprint_id"])], f["repos"])
    epicos = sorted(base["epico"].dropna().unique(), key=lambda e: (e == "Sem épico", e))
    ep_sel = c[3].multiselect("Épico", epicos, key="ga_epico", placeholder="Todos")
    pessoas = sorted({p for ps in base["pessoas"] for p in ps},
                     key=lambda p: (p in ("Sem responsável", "Não coletado"), p.lower()))
    pes_sel = c[4].multiselect("Pessoa", pessoas, key="ga_pessoa", placeholder="Todas",
                               help="responsável (assignee) da story; story com várias pessoas entra inteira para "
                                    "cada uma")
    busca = c[5].text_input("Issue / Story", key="ga_issue", placeholder="número ou parte do título")
    d = base[base["epico"].isin(ep_sel)] if ep_sel else base
    if pes_sel:
        d = d[d["pessoas"].map(lambda ps: bool(set(ps) & set(pes_sel)))]
    if busca.strip():
        b = busca.strip().lstrip("#").lower()
        d = d[d["issue"].str.lower().str.endswith("#" + b)
              | d["titulo"].fillna("").str.lower().str.contains(b, regex=False)]
    desc = {"sprints": s, "fora": fora, "parcial": bool(ep_sel or pes_sel or busca.strip()), "pessoas": pes_sel, "periodo": (ini, fim),
            "texto": (f"**{len(s)} sprint(s)** · **{d['issue_id'].nunique()} stories** "
                      f"({len(d)} registros story × sprint) · sprints terminando de {data_br(ini)} a {data_br(fim)}"
                      + (f" · repositórios: {', '.join(f['repos'])}" if f["repos"] else "")
                      + (f" · pessoa: {', '.join(pes_sel)}" if pes_sel else ""))}
    return s, d, desc


# ───────────────────────── 2. KPIs ─────────────────────────

def _horas_por_sprint(ctx, concl: pd.DataFrame) -> dict:
    h = ctx.horas
    if h is None or h.empty or "horas" not in h or concl.empty:
        return {"media": None, "nota": "Indisponível: sem horas na aba Horas para as sprints concluídas do recorte."}
    numeros = [int(x.lstrip("S")) for x in concl["sprint"] if x.lstrip("S").isdigit()]
    por = h[h["sprint"].isin(numeros)].groupby("sprint")["horas"].sum()
    por = por[por > 0]
    if por.empty:
        return {"media": None, "nota": "Indisponível: nenhuma hora registrada nessas sprints (aba Horas)."}
    return {"media": float(por.mean()), "nota": f"média de horas da equipe nas {len(por)} sprint(s); a planilha "
                                                "não tem capacidade em SP"}


def _kpis(ctx, R: pd.DataFrame, d: pd.DataFrame, desc: dict) -> None:
    concl = R[R["sprint_status"] == vel.STATUS_CONCLUIDA]
    plan_c = concl["sp_planejado"].sum(min_count=1)
    real_c = concl["sp_realizado"].sum()
    taxa = vel.calculate_completion_rate(plan_c, real_c) if not concl.empty else None
    media = concl["sp_realizado"].mean() if len(concl) >= ctx.zh_regras.min_sprints_media else None
    tend = ga.tendencia(R)
    planejadas = d[d["planejada"]]
    feitas = d[d["concluida"]]
    k1 = st.columns(5)
    with k1[0]:
        kpi("SP planejados", _sp(R["sp_planejado"].sum(min_count=1)), "ZENHUB",
            nota=f"soma dos compromissos de {len(R)} sprint(s); story levada conta em cada planning")
    with k1[1]:
        kpi("SP realizados", _sp(R["sp_realizado"].sum()), "ZENHUB",
            nota="stories fechadas dentro da sprint em que estavam")
    with k1[2]:
        kpi("Stories planejadas", num(len(planejadas)), "ZENHUB",
            nota=f"{planejadas['issue_id'].nunique()} distintas")
    with k1[3]:
        kpi("Stories concluídas", num(len(feitas)), "ZENHUB",
            nota=f"{len(feitas[feitas['planejada']])} do plano · {len(feitas[~feitas['planejada']])} fora do plano")
    with k1[4]:
        if taxa is None:
            kpi("Conclusão (sprints concluídas)", None, "CALCULADO",
                nota="Indisponível: nenhuma sprint concluída com planejado > 0 no recorte.")
        else:
            kpi("Conclusão (sprints concluídas)", f"{num(taxa)}%", "CALCULADO",
                status=status_taxa(taxa, config.META_TAXA_CONCLUSAO, config.LIMITE_TAXA_CRITICO),
                nota=f"{num(real_c)} de {num(plan_c)} SP · meta ≥ {num(config.META_TAXA_CONCLUSAO)}%")
    k2 = st.columns(5)
    with k2[0]:
        kpi("Compromisso médio por sprint", _sp(concl["sp_planejado"].mean()) if not concl.empty else None,
            "CALCULADO", nota="SP planejados por sprint concluída" if not concl.empty else
            "Indisponível: nenhuma sprint concluída no recorte.")
    with k2[1]:
        horas = _horas_por_sprint(ctx, concl)
        kpi("Capacidade registrada por sprint", f"{num(horas['media'])} h" if horas["media"] else None, "PLANILHA",
            nota=horas["nota"])
    with k2[2]:
        dif = (real_c - plan_c) if not concl.empty and not pd.isna(plan_c) else None
        kpi("Variação realizado − planejado", f"{dif:+.0f} SP" if dif is not None else None, "CALCULADO",
            status=None if dif is None else ("good" if dif >= 0 else "warning"),
            nota="sprints concluídas do recorte" if dif is not None else "Indisponível: nenhuma sprint concluída.")
    with k2[3]:
        if media is None:
            kpi("Velocity média", None, "CALCULADO",
                nota=f"Indisponível: exige {ctx.zh_regras.min_sprints_media} sprints concluídas no recorte.")
        else:
            t = (f"tendência {tend['sentido']} ({'+' if tend['valor'] >= 0 else '−'}{num(abs(tend['valor']), 1)} SP/sprint)" if tend["valor"] is not None
                 else f"tendência indisponível: {tend['motivo']}")
            kpi("Velocity média", _sp(media), "CALCULADO", nota=f"{len(concl)} sprint(s) concluída(s) · {t}")
    with k2[4]:
        kpi("Mudança de escopo após a planning", f"+{int(R['stories_adicionadas'].sum())} / "
            f"−{int(R['stories_removidas'].sum())}", "ZENHUB",
            nota=f"stories adicionadas / removidas · +{num(R['sp_adicionado'].sum())} SP / "
                 f"−{num(R['sp_removido'].sum())} SP (histórico scopeChange)")
    if desc["parcial"]:
        st.caption("Com filtro de épico, pessoa ou issue, os totais são só das stories filtradas, não da sprint "
                   "inteira." + (" Story com mais de uma pessoa entra inteira para cada uma (os pontos não são "
                                 "divididos)." if desc.get("pessoas") else ""))


# ───────────────────────── 3–5. planejado, realizado, comparação ─────────────────────────

def _barras_sprint(R, campo, cor, titulo, sub):
    b = (alt.Chart(R).mark_bar(size=24, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=cor)
         .encode(x=alt.X("sprint:N", sort=list(R["sprint"]), title="Sprint", axis=alt.Axis(labelAngle=0)),
                 y=alt.Y(f"{campo}:Q", title="Story Points"),
                 tooltip=[alt.Tooltip("sprint_nome:N", title="Sprint"), alt.Tooltip("release:N", title="Release"),
                          alt.Tooltip(f"{campo}:Q", title="SP", format=".0f")]))
    rot = b.mark_text(dy=-7, fontSize=11, color=theme.INK["secondary"]).encode(
        text=alt.Text(f"{campo}:Q", format=".0f"))
    charts.mostrar(b + rot, titulo, sub, altura=220)


def _planejamento(R, d, rel):
    layout.secao("Planejamento", "O que o time se comprometeu a entregar em cada sprint?", ["ZENHUB"])
    e, dd = st.columns([1.3, 1])
    with e:
        _barras_sprint(R, "sp_planejado", COR_PLAN, "SP planejados por sprint",
                       "estimativa ao fim da janela de planning · sprints em ordem de tempo")
    with dd:
        st.markdown("**Por release**")
        st.dataframe(rel[["release", "sprints", "stories_planejadas", "sp_planejado"]], hide_index=True,
                     use_container_width=True, column_config={
                         "release": "Release", "sprints": "Sprints", "stories_planejadas": "Stories planejadas",
                         "sp_planejado": st.column_config.NumberColumn("SP planejados", format="%.0f")})
        sem = int(R["sem_estimativa_na_planning"].sum())
        if sem:
            st.caption(f"{sem} story(ies) planejada(s) sem estimativa na planning contam 0 SP no planejado.")
    alvo = st.selectbox("Stories planejadas de", ["Todas as sprints do recorte", *R["sprint"]], key="ga_plan_sprint")
    x = d[d["planejada"]]
    if alvo != "Todas as sprints do recorte":
        x = x[x["sprint"] == alvo]
    st.caption(f"{len(x)} story(ies) · {num(x['sp_planejado'].sum())} SP planejados"
               + ("" if alvo.startswith("Todas") else f" = barra da {alvo} no gráfico"))
    tabela_stories(x.sort_values(["ordem_sprint", "sp_planejado"], ascending=[True, False]), "plan",
                   "stories_planejadas.csv",
                   ["release", "sprint", "epico", "issue", "titulo", "url", "sp_planejado", "resultado",
                    "status_atual", "levada_para", "criada_em", "entrou_em", "concluida_em", "responsavel"])


def _realizado(R, d, rel, desc):
    layout.secao("Realizado", "O que foi efetivamente concluído, e quando?", ["ZENHUB"])
    e, dd = st.columns([1.3, 1])
    with e:
        ordem_o = ["Do plano", "Fora do plano (adicionada)"]
        longo = pd.concat(ignore_index=True, objs=[
            R.assign(origem=ordem_o[0], sp=R["sp_realizado_do_plano"]),
            R.assign(origem=ordem_o[1], sp=R["sp_realizado_fora_do_plano"])])
        b = (alt.Chart(longo).mark_bar(size=24, stroke=theme.INK["surface"], strokeWidth=1)
             .encode(x=alt.X("sprint:N", sort=list(R["sprint"]), title="Sprint", axis=alt.Axis(labelAngle=0)),
                     y=alt.Y("sp:Q", title="Story Points", stack=True),
                     color=alt.Color("origem:N", title=None, sort=ordem_o,
                                     scale=alt.Scale(domain=ordem_o, range=[COR_REAL, COR_EXTRA])),
                     tooltip=[alt.Tooltip("sprint:N"), alt.Tooltip("origem:N", title="Origem"),
                              alt.Tooltip("sp:Q", title="SP", format=".0f")]))
        charts.mostrar(b, "SP realizados por sprint", "stories fechadas dentro da sprint · do plano ou adicionadas",
                       altura=220)
    with dd:
        st.markdown("**Por release**")
        st.dataframe(rel[["release", "sprints", "stories_concluidas", "sp_realizado"]], hide_index=True,
                     use_container_width=True, column_config={
                         "release": "Release", "sprints": "Sprints", "stories_concluidas": "Stories concluídas",
                         "sp_realizado": st.column_config.NumberColumn("SP realizados", format="%.0f")})
    ent = ga.entregas_no_tempo(d)
    ini, fim = desc["periodo"]
    if not ent.empty:
        ent = ent[(ent["dia"] >= ini) & (ent["dia"] <= fim + pd.Timedelta(days=1))]
    if ent.empty:
        layout.indisponivel("Sem entregas no período", "nenhuma story do recorte foi concluída entre as datas.")
    else:
        ent = ent.assign(acumulado=ent["sp"].cumsum())
        barras = (alt.Chart(ent).mark_bar(size=10, color=COR_REAL, opacity=0.55)
                  .encode(x=alt.X("dia:T", title="Data de conclusão", axis=alt.Axis(format="%d/%m")),
                          y=alt.Y("sp:Q", title="SP no dia"),
                          tooltip=[alt.Tooltip("dia:T", title="Dia", format="%d/%m/%Y"),
                                   alt.Tooltip("sp:Q", title="SP", format=".0f"), alt.Tooltip("stories:Q")]))
        linha = (alt.Chart(ent).mark_line(color=theme.INK["primary"], interpolate="step-after", point=True)
                 .encode(x="dia:T", y=alt.Y("acumulado:Q", title="SP acumulados"),
                         tooltip=[alt.Tooltip("dia:T", format="%d/%m/%Y"), alt.Tooltip("acumulado:Q", format=".0f")]))
        charts.mostrar(alt.layer(barras, linha).resolve_scale(y="independent"), "Evolução das entregas",
                       "barras = SP concluídos no dia · linha = acumulado (horário de Brasília)", altura=220)
    alvo = st.selectbox("Stories concluídas de", ["Todas as sprints do recorte", *R["sprint"]], key="ga_real_sprint")
    x = d[d["concluida"]]
    if alvo != "Todas as sprints do recorte":
        x = x[x["sprint"] == alvo]
    st.caption(f"{len(x)} story(ies) · {num(x['sp_realizado'].sum())} SP realizados")
    tabela_stories(x.sort_values(["ordem_sprint", "concluida_em"]), "real", "stories_concluidas.csv",
                   ["release", "sprint", "epico", "issue", "titulo", "url", "sp_planejado", "sp_realizado",
                    "resultado", "concluida_em", "criada_em", "entrou_em", "responsavel"])


def _comparacao(R, d, rel):
    layout.secao("Planejado × realizado", "Onde a execução se afastou do planejamento?", ["ZENHUB", "CALCULADO"])
    longo = pd.concat(ignore_index=True, objs=[R.assign(serie="Planejado", sp=R["sp_planejado"]),
                                               R.assign(serie="Realizado", sp=R["sp_realizado"])])
    e, dd = st.columns(2)
    with e:
        b = (alt.Chart(longo).mark_bar(size=16, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
             .encode(x=alt.X("sprint:N", sort=list(R["sprint"]), title="Sprint", axis=alt.Axis(labelAngle=0)),
                     xOffset=alt.XOffset("serie:N", sort=SERIES_PR), y=alt.Y("sp:Q", title="Story Points"),
                     color=alt.Color("serie:N", title=None, scale=ESCALA_PR, sort=SERIES_PR),
                     tooltip=[alt.Tooltip("sprint:N"), alt.Tooltip("serie:N"), alt.Tooltip("sp:Q", format=".0f")]))
        charts.mostrar(b, "Por sprint", "SP planejados × realizados", altura=220)
    with dd:
        comp = d.assign(sp=d["sp_atual"].map(lambda v: 0 if v is None or pd.isna(v) else v))
        g = comp.groupby(["sprint", "resultado"], as_index=False).agg(sp=("sp", "sum"), stories=("issue", "count"))
        b = (alt.Chart(g).mark_bar(size=24, stroke=theme.INK["surface"], strokeWidth=1)
             .encode(x=alt.X("sprint:N", sort=list(R["sprint"]), title="Sprint", axis=alt.Axis(labelAngle=0)),
                     y=alt.Y("sp:Q", title="Story Points (estimativa atual)", stack=True),
                     color=alt.Color("resultado:N", title="Resultado", scale=COR_RESULTADO,
                                     sort=ga.RESULTADOS + [ga.EM_ANDAMENTO]),
                     tooltip=[alt.Tooltip("sprint:N"), alt.Tooltip("resultado:N"), alt.Tooltip("stories:Q"),
                              alt.Tooltip("sp:Q", title="SP", format=".0f")]))
        charts.mostrar(b, "O que aconteceu com cada story", "SP por resultado na sprint", altura=220)
    st.markdown("**Por release**")
    st.dataframe(rel, hide_index=True, use_container_width=True, column_config={
        "release": "Release", "sprints": "Sprints", "stories_planejadas": "Stories planejadas",
        "stories_concluidas": "Stories concluídas",
        "sp_planejado": st.column_config.NumberColumn("SP planejados", format="%.0f"),
        "sp_realizado": st.column_config.NumberColumn("SP realizados", format="%.0f"),
        "diferenca": st.column_config.NumberColumn("Diferença", format="%+.0f"),
        "taxa": st.column_config.NumberColumn("Conclusão", format="%.0f%%")})
    # por período: planejado acumulado (na data de início de cada sprint) × realizado acumulado (dia a dia)
    p = ga.planejado_no_tempo(R)
    ent = ga.entregas_no_tempo(d)
    partes = [p.assign(dia=p["inicio"], serie="Planejado", valor=p["sp_planejado"].fillna(0).cumsum())
              [["dia", "serie", "valor"]]]
    if not ent.empty:
        partes.append(ent.assign(serie="Realizado", valor=ent["acumulado"])[["dia", "serie", "valor"]])
    acum = pd.concat(partes, ignore_index=True)
    linha = (alt.Chart(acum).mark_line(interpolate="step-after", point=True)
             .encode(x=alt.X("dia:T", title="Data", axis=alt.Axis(format="%d/%m")),
                     y=alt.Y("valor:Q", title="SP acumulados"),
                     color=alt.Color("serie:N", title=None, scale=ESCALA_PR, sort=SERIES_PR),
                     tooltip=[alt.Tooltip("dia:T", format="%d/%m/%Y"), alt.Tooltip("serie:N"),
                              alt.Tooltip("valor:Q", format=".0f")]))
    charts.mostrar(linha, "Por período", "planejado acumulado (sobe no início de cada sprint) × realizado acumulado "
                                         "(sobe na data de conclusão)", altura=220)
    st.markdown("**Por story**")
    x = d.assign(diferenca=d["sp_realizado"].fillna(0) - d["sp_planejado"].fillna(0))
    tabela_stories(x.sort_values(["ordem_sprint", "diferenca"]), "comp", "planejado_x_realizado_por_story.csv",
                   ["sprint", "epico", "issue", "titulo", "url", "sp_planejado", "sp_realizado", "resultado",
                    "levada_para", "status_atual"])


# ───────────────────────── 6. velocity ─────────────────────────

def _velocity(ctx, R, d):
    layout.secao("Velocity", "Quanto foi planejado e entregue em cada sprint, e como o ritmo variou?", ["ZENHUB"])
    concl = R[R["sprint_status"] == vel.STATUS_CONCLUIDA]
    media = concl["sp_realizado"].mean() if len(concl) >= ctx.zh_regras.min_sprints_media else None
    v = R.assign(eixo=R["sprint"] + R["sprint_status"].map({vel.STATUS_ANDAMENTO: " (parcial)"}).fillna(""))
    ordem = list(v["eixo"])
    longo = pd.concat(ignore_index=True, objs=[v.assign(serie="Planejado", sp=v["sp_planejado"]),
                                               v.assign(serie="Realizado", sp=v["sp_realizado"])])
    longo["parcial"] = longo["sprint_status"] != vel.STATUS_CONCLUIDA
    barras = (alt.Chart(longo).mark_bar(size=18, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
              .encode(x=alt.X("eixo:N", sort=ordem, title="Sprint", axis=alt.Axis(labelAngle=0)),
                      xOffset=alt.XOffset("serie:N", sort=SERIES_PR), y=alt.Y("sp:Q", title="Story Points"),
                      color=alt.Color("serie:N", title=None, scale=ESCALA_PR, sort=SERIES_PR),
                      opacity=alt.condition("datum.parcial", alt.value(0.45), alt.value(1)),
                      tooltip=[alt.Tooltip("sprint_nome:N", title="Sprint"), alt.Tooltip("serie:N"),
                               alt.Tooltip("sp:Q", title="SP", format=".0f")]))
    rot = barras.mark_text(dy=-7, fontSize=11).encode(text=alt.Text("sp:Q", format=".0f"),
                                                      color=alt.value(theme.INK["secondary"]), opacity=alt.value(1))
    linha = (alt.Chart(v).mark_line(color=theme.INK["primary"], strokeWidth=2, point=True)
             .encode(x=alt.X("eixo:N", sort=ordem), y="sp_realizado:Q",
                     tooltip=[alt.Tooltip("eixo:N", title="Sprint"),
                              alt.Tooltip("sp_realizado:Q", title="Velocity", format=".0f")]))
    camadas = barras + rot + linha
    if media is not None:
        camadas = camadas + charts.regra_horizontal(media, f"média {num(media)} SP", theme.INK["muted"])
    tend = ga.tendencia(R)
    nota = ("Linha = velocity (SP realizados). Barras claras = sprint em andamento, fora da média. "
            + (f"Média das {len(concl)} sprints concluídas: {num(media)} SP. " if media is not None else
               f"Média indisponível: exige {ctx.zh_regras.min_sprints_media} sprints concluídas. ")
            + (f"Tendência {tend['sentido']} ({'+' if tend['valor'] >= 0 else '−'}{num(abs(tend['valor']), 1)} SP por sprint, {tend['n']} sprints)."
               if tend["valor"] is not None else f"Tendência indisponível: {tend['motivo']}."))
    charts.mostrar(camadas, "Planejado, realizado e velocity por sprint", "Story Points", nota=nota, altura=260)
    t = R[["sprint", "sprint_nome", "release", "sprint_status", "sp_planejado", "sp_realizado", "diferenca", "taxa",
           "stories_planejadas", "stories_concluidas", "stories_adicionadas", "stories_removidas",
           "stories_levadas"]]
    st.caption("Clique numa sprint da tabela para ver as stories que compõem a velocity dela.")
    ev = st.dataframe(t, hide_index=True, use_container_width=True, key="ga_vel_tab", on_select="rerun",
                      selection_mode="single-row", column_config={
                          "sprint": "Sprint", "sprint_nome": "Nome", "release": "Release", "sprint_status": "Situação",
                          "sp_planejado": st.column_config.NumberColumn("SP planejados", format="%.0f",
                                                                        help="soma dos story points planejados"),
                          "sp_realizado": st.column_config.NumberColumn("SP realizados", format="%.0f",
                                                                        help="soma dos story points concluídos"),
                          "diferenca": st.column_config.NumberColumn("Diferença (SP)", format="%+.0f"),
                          "taxa": st.column_config.NumberColumn("Conclusão (SP)", format="%.0f%%"),
                          "stories_planejadas": st.column_config.NumberColumn(
                              "Stories planejadas", help="quantidade de stories (issues), não pontos"),
                          "stories_concluidas": st.column_config.NumberColumn("Stories concluídas"),
                          "stories_adicionadas": st.column_config.NumberColumn(
                              "Stories adicionadas", help="entraram depois da planning"),
                          "stories_removidas": st.column_config.NumberColumn(
                              "Stories removidas", help="saíram antes do fim sem concluir"),
                          "stories_levadas": st.column_config.NumberColumn(
                              "Stories levadas", help="não concluídas e presentes na sprint seguinte")})
    try:
        linhas_sel = list(ev.selection.rows)
    except AttributeError:
        linhas_sel = []
    alvo = t.iloc[linhas_sel[0]]["sprint"] if linhas_sel else (concl["sprint"].iloc[-1] if not concl.empty
                                                               else t["sprint"].iloc[-1])
    x = d[(d["sprint"] == alvo) & d["concluida"]]
    st.markdown(f"**Velocity da {alvo}: {_sp(x['sp_realizado'].sum())} em {len(x)} story(ies)**"
                + ("" if linhas_sel else " · última sprint concluída; clique em outra linha para trocar"))
    tabela_stories(x.sort_values("sp_realizado", ascending=False), "vel", f"velocity_{alvo}.csv",
                   ["epico", "issue", "titulo", "url", "sp_realizado", "sp_planejado", "resultado", "concluida_em",
                    "responsavel"])


# ───────────────────────── 7. burndown ─────────────────────────

def _burndown(ctx, sprints_rec: pd.DataFrame):
    layout.secao("Burndown", "Como o trabalho restante evoluiu ao longo da sprint?", ["ZENHUB", "CALCULADO"])
    if sprints_rec.empty:
        layout.indisponivel("Burndown indisponível", "nenhuma sprint no recorte.")
        return
    padrao = sprints_rec[sprints_rec["status"] == vel.STATUS_ANDAMENTO]
    opcoes = list(sprints_rec["sprint_label"])
    idx = opcoes.index(padrao["sprint_label"].iloc[0]) if not padrao.empty else len(opcoes) - 1
    alvo = st.selectbox("Sprint do burndown", opcoes, index=idx, key="ga_burn")
    s = sprints_rec[sprints_rec["sprint_label"] == alvo].iloc[0]
    b = ga.burndown(ctx.zh_snap, s, ctx.zh_regras, ctx.agora_utc, filtro_issue=ctx.zh_filtro)
    dados = b["dados"]
    if dados.empty:
        layout.indisponivel("Burndown indisponível", b["motivo"] or "sem dados")
        return
    series = ["Ideal (a partir do planejado)", "Restante real", "Escopo total"]
    longo = pd.concat(ignore_index=True, objs=[
        dados.assign(serie=series[0], valor=dados["ideal"]),
        dados.assign(serie=series[1], valor=dados["restante"]),
        dados.assign(serie=series[2], valor=dados["escopo"])]).dropna(subset=["valor"])
    linha = (alt.Chart(longo).mark_line(point=True)
             .encode(x=alt.X("dia:T", title="Dia da sprint", axis=alt.Axis(format="%d/%m")),
                     y=alt.Y("valor:Q", title="Story Points"),
                     color=alt.Color("serie:N", title=None, sort=series,
                                     scale=alt.Scale(domain=series, range=[COR_PLAN, COR_REAL, theme.INK["muted"]])),
                     strokeDash=alt.StrokeDash("serie:N", sort=series, legend=None,
                                               scale=alt.Scale(domain=series, range=[[6, 4], [1, 0], [2, 3]])),
                     tooltip=[alt.Tooltip("dia:T", title="Fim do dia", format="%d/%m/%Y"), alt.Tooltip("serie:N"),
                              alt.Tooltip("valor:Q", title="SP", format=".0f")]))
    marcos = pd.DataFrame({"dia": [b["inicio"], b["fim"]], "t": ["início", "fim"]})
    regra = alt.Chart(marcos).mark_rule(color=theme.INK["muted"], strokeDash=[2, 3]).encode(x="dia:T")
    texto = alt.Chart(marcos).mark_text(align="left", dx=3, y=4, baseline="top", fontSize=10,
                                        color=theme.INK["muted"]).encode(x="dia:T", text="t:N")
    ultimo = dados.dropna(subset=["restante"]).tail(1)
    sub = (f"{s['sprint_name']} · {data_br(b['inicio'])} a {data_br(b['fim'])}"
           + (f" · contagem até {b['prazo']:%d/%m %H:%M}" if b.get("prazo") is not None else "")
           + (f" · restante no último dia com dado: {num(ultimo['restante'].iloc[0])} SP" if not ultimo.empty else ""))
    charts.mostrar(linha + regra + texto, f"Burndown da {alvo}", sub, dados, altura=260, nota=(
        "Dados verificáveis usados: planejado da planning, entradas e saídas do histórico scopeChange (com data e "
        "hora) e a data de fechamento de cada issue. Restante = escopo no fim do dia − SP das stories fechadas até "
        "ali. Fora do cálculo: mudança de estimativa no meio da sprint (o Zenhub não guarda esse histórico) — quem "
        "já estava na sprint no início usa a estimativa atual. Dias futuros ficam sem ponto."))


# ───────────────────────── 8. análises qualitativas ─────────────────────────

def _analises(R, d):
    layout.secao("Análises qualitativas", "O que explica as diferenças entre planejamento e execução?",
                 ["CALCULADO"])
    a = ga.analises(R, d)
    if a.empty:
        layout.alerta("good", "Nenhum padrão relevante encontrado no recorte com os limites atuais.")
        return
    st.caption("**Fato observado** = número tirado das stories do recorte. **Interpretação** = leitura possível "
               "desse fato, a confirmar com o time; não substitui o dado. Limites em `src/metrics/gestao_agil.py`: "
               f"diferença ≥ {ga.LIMITE_DIFERENCA:.0%}, overcommitment ≥ {ga.LIMITE_OVERCOMMIT:.1f}× a média "
               f"anterior, variação de velocity ≥ {ga.LIMITE_VARIACAO_VELOCITY:.0%}, escopo adicionado ≥ "
               f"{ga.LIMITE_ESCOPO:.0%}, concentração ≥ {ga.LIMITE_CONCENTRACAO:.0%} nas 20% maiores stories.")
    layout.tabela_html(a, {"tema": "Tema", "sprint": "Sprint", "fato": "Fato observado",
                           "interpretacao": "Interpretação", "issues": "Issues envolvidas"}, links=("issues",))
    st.download_button("Baixar CSV das análises", a.assign(issues=a["issues"].map(
        lambda xs: ", ".join(f"{r} ({u})" if u else r for r, u in xs))).to_csv(index=False).encode("utf-8-sig"),
        file_name="analises_qualitativas.csv", mime="text/csv", key="csv_analises")


# ───────────────────────── 9. detalhamento ─────────────────────────

def _detalhamento(d):
    layout.secao("Detalhamento das issues", "De quais issues vem cada número?", ["ZENHUB"])
    h = ga.hierarquia(d)
    st.markdown("**Release → Sprint → Épico**")
    layout.tabela_html(h, {"release": "Release", "sprint": "Sprint", "epico_link": "Épico", "stories": "Stories",
                           "sp_planejado": "SP planejados", "sp_realizado": "SP realizados", "issues": "Issues"},
                       links=("epico_link", "issues"), numericas=("stories", "sp_planejado", "sp_realizado"))
    st.caption("SP planejados = soma dos pontos das stories planejadas; '—' = nenhuma story daquele grupo estava "
               "no planejado (entrou depois da planning). Stories = quantidade de issues do grupo.")
    st.markdown("**Todas as stories do recorte** (uma linha por story em cada sprint)")
    tabela_stories(d.sort_values(["ordem_sprint", "epico", "issue"]), "todas", "stories_do_recorte.csv")
    ausentes = []
    if d["criada_em"].isna().any():
        ausentes.append(f"data de criação ausente em {int(d['criada_em'].isna().sum())} registro(s): ela só vem da "
                        "coleta do backlog completo")
    if (d["responsavel"] == "Não coletado").any():
        ausentes.append("responsável 'Não coletado' = issue fora do backlog coletado")
    ausentes.append("data de início da issue (start date do Zenhub) não é coletada; 'Entrou na sprint' é a data do "
                    "histórico de escopo")
    st.caption("Dados ausentes: " + "; ".join(ausentes) + ".")


# ───────────────────────── página ─────────────────────────

def pagina():
    ctx, f = layout.estado()
    ctx = contexto.com_recorte(ctx, f["repos"])
    layout.titulo_pagina("Gestão ágil", "Planejado × realizado em Story Points, do resumo até cada issue.", ["ZENHUB"])
    if ctx.repos_recorte:
        layout.alerta("neutral", "Filtro de repositórios ativo (" + ", ".join(ctx.repos_recorte) + "): pontos, sprints, "
                      "velocity e SPI são só desses repositórios. Orçamento, horas, custo e CPI são do time inteiro "
                      "(não dependem de repositório).")
    snap = ctx.zh_snap
    topo_e, topo_d = st.columns([3, 1])
    with topo_d:
        _botao_atualizar(ctx)
    with topo_e:
        if snap:
            fonte = ctx.fonte("ZENHUB")[0]
            st.caption(f"Snapshot `{ctx.zh_arquivo}` · coletado em **{data_br(fonte.ultima_atualizacao, True)}** · "
                       f"pontuam: {', '.join(sorted(ctx.zh_regras.tipos_pontuados))} sem filhas pontuáveis · "
                       "feito = issue fechada.")
    r = ctx.zh_regras
    layout.metodologia([
        ("Story", "ZENHUB", f"issue {', '.join(sorted(r.tipos_pontuados))} sem filhas pontuáveis (PR, Épico, "
         "Sub-task e pai de Tasks não pontuam, para não contar o mesmo trabalho duas vezes)"),
        ("SP planejados", "ZENHUB — `Sprint.scopeChange`", "stories na sprint ao fim da janela de planning "
         f"({r.janela_planning.total_seconds() / 3600:.0f} h), com a estimativa daquele momento; quem já estava na "
         "sprint no início entra com a estimativa atual; congelado em `linhas-de-base.json`"),
        ("SP realizados / velocity", "ZENHUB", "estimativa atual das stories fechadas dentro da sprint em que estavam"
         + (f", até {r.prazo_fechamento} (Brasília) do dia seguinte ao último dia" if r.prazo_fechamento else "")),
        ("Adicionada / removida / levada", "ZENHUB — `scopeChange`", "entrou depois da planning / saiu antes do fim "
         "sem concluir / não concluída e presente na sprint seguinte"),
        ("Conclusão", "cálculo", "SP realizados ÷ SP planejados das sprints concluídas do recorte"),
        ("Velocity média e tendência", "cálculo", f"média das sprints concluídas (≥ {r.min_sprints_media}); "
         "tendência = inclinação da reta de mínimos quadrados (≥ 3 sprints)"),
        ("Capacidade registrada", "PLANILHA — aba Horas", "média das horas registradas por sprint concluída"),
        ("Burndown", "cálculo", "escopo no fim de cada dia (histórico) − SP fechados até ali; ideal = planejado → 0"),
        ("Filtros", "—", "release, sprint, período (último dia da sprint), épico e issue se combinam; todos os "
         "blocos usam o mesmo recorte"),
    ])
    if not snap:
        layout.indisponivel("Sem dados do Zenhub", "ainda não há snapshot em `data/zenhub/velocity/`.",
                            "rodar `python scripts/coleta_velocity.py` com `ZENHUB_API_KEY` no `Analytics/.env`.")
        return
    for aviso in snap.get("avisos") or []:
        st.caption(f"Aviso da coleta: {aviso}")
    if ctx.zh_iniciadas.empty:
        layout.indisponivel("Nenhuma sprint iniciada", "o snapshot não tem sprints com data de início passada.")
        return

    linhas = ga.stories_por_sprint(snap, ctx.zh_iniciadas, ctx.zh_issues, ctx.zh_regras)

    layout.secao("Filtros", "Qual recorte analisar?", ["ZENHUB"])          # 1
    sprints_rec, d, desc = _filtros(ctx, f, linhas)
    st.markdown(f"Encontrados: {desc['texto']}")
    if desc["fora"]:
        st.caption(f"Sprint(s) {', '.join(desc['fora'])} fora do período escolhido: amplie o período para incluí-la(s).")
    R = ga.resumo_por_sprint(d)
    if R.empty:
        layout.indisponivel("Nenhuma story no recorte", "os filtros escolhidos não deixaram nenhuma story.",
                            "limpar algum filtro ou ampliar o período.")
        return
    rel = ga.resumo_por_release(R)

    layout.secao("Resumo", "Quanto foi planejado, quanto foi entregue e como está o ritmo?",   # 2
                 ["ZENHUB", "CALCULADO"])
    _kpis(ctx, R, d, desc)
    _planejamento(R, d, rel)          # 3
    _realizado(R, d, rel, desc)       # 4
    _comparacao(R, d, rel)            # 5
    _velocity(ctx, R, d)              # 6
    if desc.get("pessoas") or desc["parcial"]:
        st.caption("O burndown abaixo é da sprint inteira: ele usa o histórico da sprint e não segue os filtros de "
                   "épico, pessoa e issue.")
    _burndown(ctx, sprints_rec)       # 7
    _analises(R, d)                   # 8
    _detalhamento(d)                  # 9

    layout.secao("Confiabilidade dos dados", "Os números batem com o Zenhub e o cadastro está consistente?",
                 ["ZENHUB"])
    todas = ctx.zh_issues
    # abas (e não expansores): os blocos têm tabelas em expansores, e o Streamlit não aninha expansores
    t1, t2, t3 = st.tabs(["Comparação com o Zenhub", "Consistência do cadastro",
                          "Backlog atual, releases e épicos"])
    with t1:
        if ctx.repos_recorte:
            st.caption("A comparação usa o workspace inteiro: o número do Zenhub não se divide por repositório.")
        apoio.comparacao_zenhub(ctx.base or ctx, f, snap, (ctx.base or ctx).zh_issues, (ctx.base or ctx).zh_issues)
        apoio.conferencia(ctx, f, snap, todas, todas)
    with t2:
        apoio.consistencia(ctx, f, snap, todas, todas)
    with t3:
        base = filters.por_repo(todas, f["repos"])
        apoio.backlog(ctx, f, snap, todas, base)
        apoio.releases_e_epicos(ctx, f, snap, todas, base)
    st.caption(f"Base: {len(linhas)} registros story × sprint de {ctx.zh_iniciadas['sprint_label'].nunique()} "
               f"sprints iniciadas · {pct(len(d) / len(linhas)) if len(linhas) else '—'} no recorte atual.")
