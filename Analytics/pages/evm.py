"""Agile EVM — prazo e custo da release: pontos do ZENHUB + orçamento e horas da PLANILHA.

Método de Sulaiman, Barton & Blackburn (2006). A página vai do resumo ao dado de origem:

1. release e sprint de referência;
2. leitura em linguagem simples (prazo, custo, projeção);
3. indicadores de prazo e de custo — cada cartão diz a fórmula e linka a fonte;
4. legenda das siglas;
5. evolução (PV × EV × AC, PPC × APC, SPI × CPI, burndown da release);
6. rastreabilidade: as stories que formam o escopo e o entregue, as horas por sprint e o
   orçamento por semana, com link para a issue e para a aba da planilha.

Nenhum valor é estimado: sem horas, o custo real e o que depende dele ficam indisponíveis.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import charts, layout
from src.components.kpi import kpi
from src.data import planilha
from src.metrics import gestao_agil as ga
from src.metrics import resumo
from src.metrics import velocity as vel
from src.metrics.calculations import brl, data_br, data_limite, num, pct, status_indice, vazio

PAGINA_ZENHUB = "./zenhub"


def _aba(chave: str) -> tuple[str, str | None]:
    return (f"Planilha · aba {planilha.nome_aba(chave)}", planilha.link_aba(chave))


ZENHUB = ("Zenhub · stories (Gestão ágil)", PAGINA_ZENHUB)
CALC = ("cálculo do painel", None)

# sigla: (nome, o que significa, fórmula, fontes)
LEGENDA = {
    "BAC": ("Orçamento da release", "quanto a release deve custar do início ao fim",
            "soma do custo planejado das semanas da release (integrantes ativos × custo de um integrante por "
            "semana)", [_aba("planejamento"), _aba("custos")]),
    "PPC": ("% do prazo decorrido", "quanto do tempo da release já passou",
            "semanas decorridas ÷ semanas da release", [("Zenhub · datas das sprints", PAGINA_ZENHUB)]),
    "PRP": ("Escopo da release (SP)", "story points das stories que passaram pelas sprints da release",
            "soma da estimativa atual de cada story (uma vez só)", [ZENHUB]),
    "RPC": ("SP entregues", "story points das stories do escopo já concluídas", "soma das stories fechadas",
            [ZENHUB]),
    "APC": ("% do escopo entregue", "quanto do escopo já foi concluído", "RPC ÷ PRP", [ZENHUB]),
    "PV": ("Valor planejado", "quanto do orçamento deveria ter virado entrega até agora", "PPC × BAC", [CALC]),
    "EV": ("Valor agregado", "quanto do orçamento de fato virou entrega", "APC × BAC", [CALC]),
    "AC": ("Custo real", "quanto já foi gasto, pelas horas registradas", "horas registradas × custo por hora",
           [_aba("horas"), _aba("custos")]),
    "SV": ("Variação de prazo (R$)", "negativo = entrega atrasada em relação ao plano", "EV − PV", [CALC]),
    "CV": ("Variação de custo (R$)", "negativo = gastou mais do que entregou", "EV − AC", [CALC]),
    "SPI": ("Índice de prazo", "1,0 = no ritmo planejado; abaixo de 1 = atrasado", "EV ÷ PV", [CALC]),
    "CPI": ("Índice de custo", "1,0 = no orçamento; abaixo de 1 = gastando mais do que entrega", "EV ÷ AC", [CALC]),
    "ETC": ("Custo para terminar", "quanto ainda deve custar, no ritmo de custo atual", "(BAC − EV) ÷ CPI", [CALC]),
    "EAC": ("Custo total estimado", "quanto a release deve custar no fim, no ritmo atual", "AC + ETC", [CALC]),
    "RD": ("Término estimado", "quando a release terminaria no ritmo de prazo atual",
           "início da release + duração ÷ SPI", [CALC]),
}


def _rotulo(sigla: str) -> str:
    return f"{LEGENDA[sigla][0]} ({sigla})"


def _nota(sigla: str, extra: str = "") -> str:
    return f"{LEGENDA[sigla][2]}" + (f" · {extra}" if extra else "")


def _motivo_ac(u) -> str:
    o = str(u.get("origem_do_ac") or "")
    return o.replace("indisponível: ", "") if o.startswith("indisponível") else "sem horas registradas"


# ───────────────────────── blocos ─────────────────────────

def _leitura(rel, u, parcial):
    """Três frases em linguagem simples, geradas dos números."""
    frases = []
    if not vazio(u["SPI"]):
        frases.append(f"**Prazo:** até a {u['sprint']} já passou **{pct(u['PPC'])}** do tempo da {rel} e foi "
                      f"entregue **{pct(u['APC'])}** do escopo ({num(u['RPC'])} de {num(u['PRP'])} SP) — SPI "
                      f"**{num(u['SPI'], 2)}**: " + ("no ritmo planejado." if u["SPI"] >= config.META_INDICE_EVM
                                                     else f"para cada R$ 1 planejado, R$ {num(u['SPI'], 2)} virou "
                                                          "entrega."))
    if not vazio(u["CPI"]):
        frases.append(f"**Custo:** gastou {brl(u['AC'], 0)} e entregou {brl(u['EV'], 0)} em valor — CPI "
                      f"**{num(u['CPI'], 2)}**: " + ("dentro do custo." if u["CPI"] >= 1 else
                                                     f"cada R$ 1 gasto rendeu R$ {num(u['CPI'], 2)} de entrega."))
    else:
        frases.append(f"**Custo:** indisponível — {_motivo_ac(u)}.")
    if not vazio(u["RD"]):
        final = pd.Timestamp(config.RELEASE_FINAL)
        frases.append(f"**Projeção:** no ritmo atual a release terminaria em **{data_br(u['RD'])}**"
                      + (f", depois da Release Final ({data_br(final)})." if u["RD"] > final else "."))
    if parcial:
        frases.append("Sprint em andamento: os valores ainda são parciais.")
    st.markdown("  \n".join(frases))


def _kpis(u, d):
    tem_bac, tem_ac = not vazio(u["BAC"]), not vazio(u["AC"])
    sem_bac = "Indisponível: orçamento não encontrado na planilha."
    sem_ac = f"Indisponível: {_motivo_ac(u)}."
    st.markdown("**Prazo** — o time está entregando no ritmo planejado?")
    c = st.columns(4)
    with c[0]:
        kpi(_rotulo("SPI"), num(u["SPI"], 2) if not vazio(u["SPI"]) else None, "CALCULADO",
            status=status_indice(u["SPI"]),
            nota=_nota("SPI", f"meta ≥ {num(config.META_INDICE_EVM, 2)}") if not vazio(u["SPI"]) else
            "Indisponível: PV é zero.")
    with c[1]:
        kpi("Prazo decorrido × escopo entregue", f"{pct(u['PPC'])} × {pct(u['APC'])}", "CALCULADO",
            status=status_indice(u["SPI"]), nota=f"PPC × APC · {num(u['RPC'])} de {num(u['PRP'])} SP",
            origem=[ZENHUB])
    with c[2]:
        kpi(_rotulo("SV"), brl(u["SV"], 0) if not vazio(u["SV"]) else None, "CALCULADO",
            status=None if vazio(u["SV"]) else ("good" if u["SV"] >= 0 else "critical"),
            nota=_nota("SV", f"PV {brl(u['PV'], 0)} · EV {brl(u['EV'], 0)}") if not vazio(u["SV"]) else sem_bac)
    with c[3]:
        entrega = d["fim_da_sprint"].max()
        final = pd.Timestamp(config.RELEASE_FINAL)
        if vazio(u["RD"]):
            kpi(_rotulo("RD"), None, "CALCULADO", nota="Indisponível: SPI zero ou inexistente.")
        elif u["RD"] > final:
            kpi(_rotulo("RD"), f"após {data_br(final)}", "CALCULADO", status="critical",
                nota=f"no ritmo atual: {data_br(u['RD'])}, depois da Release Final "
                     f"({data_limite(config.RELEASE_FINAL)}) · entrega planejada {data_br(entrega)}")
        else:
            kpi(_rotulo("RD"), data_br(u["RD"]), "CALCULADO", status="good" if u["RD"] <= entrega else "warning",
                nota=f"entrega planejada {data_br(entrega)}")
    st.markdown("**Custo** — o que foi gasto está de acordo com o que foi entregue?")
    c = st.columns(4)
    with c[0]:
        kpi(_rotulo("BAC"), brl(u["BAC"], 0) if tem_bac else None, "PLANILHA",
            nota=f"PV até a {u['sprint']}: {brl(u['PV'], 0)}" if tem_bac else sem_bac, origem=LEGENDA["BAC"][3])
    with c[1]:
        kpi(_rotulo("AC"), brl(u["AC"], 0) if tem_ac else None, "PLANILHA",
            nota=_nota("AC") if tem_ac else sem_ac, origem=LEGENDA["AC"][3])
    with c[2]:
        kpi(_rotulo("CPI"), num(u["CPI"], 2) if not vazio(u["CPI"]) else None, "CALCULADO",
            status=status_indice(u["CPI"]),
            nota=_nota("CPI", f"CV {brl(u['CV'], 0)}") if not vazio(u["CPI"]) else sem_ac)
    with c[3]:
        kpi(_rotulo("EAC"), brl(u["EAC"], 0) if not vazio(u["EAC"]) else None, "CALCULADO",
            status=None if vazio(u["EAC"]) or vazio(u["BAC"]) else ("good" if u["EAC"] <= u["BAC"] else "warning"),
            nota=(f"AC + ETC ({brl(u['ETC'], 0)} para terminar) · orçamento {brl(u['BAC'], 0)}"
                  if not vazio(u["EAC"]) else "Indisponível: depende do CPI, que depende do custo real."))


def _legenda():
    tab = pd.DataFrame([{"sigla": k, "nome": v[0], "significa": v[1], "formula": v[2], "fonte": v[3]}
                        for k, v in LEGENDA.items()])
    layout.tabela_html(tab, {"sigla": "Sigla", "nome": "Nome", "significa": "O que significa",
                             "formula": "Como é calculado", "fonte": "De onde vem"}, links=("fonte",), altura=None)
    st.caption(f"Status: SPI e CPI ≥ {num(config.META_INDICE_EVM, 2)} conforme, entre "
               f"{num(config.LIMITE_INDICE_CRITICO, 2)} e {num(config.META_INDICE_EVM, 2)} atenção, abaixo crítico. "
               "Método: Sulaiman, Barton & Blackburn (2006), AgileEVM.")


def _graficos(rel, feitas, u):
    tem_bac, tem_ac = not vazio(u["BAC"]), not vazio(u["AC"])
    nomes = {"PV": "Planejado (PV)", "EV": "Entregue em valor (EV)", "AC": "Gasto (AC)"}
    if not tem_bac:
        layout.indisponivel("Curvas de valor indisponíveis", "orçamento não encontrado na planilha.",
                            "abas Custos e Planejamento da planilha.")
    else:
        longo = feitas.melt(id_vars=["sprint"], value_vars=["PV", "EV", "AC"], var_name="serie",
                            value_name="valor").dropna(subset=["valor"])
        longo["nome"] = longo["serie"].map(nomes)
        dom = [nomes[k] for k in ("PV", "EV", "AC") if nomes[k] in set(longo["nome"])]
        cor = {nomes["PV"]: theme.SERIES[2], nomes["EV"]: theme.SERIES[0], nomes["AC"]: theme.SERIES[1]}
        traco = {nomes["PV"]: [6, 4], nomes["EV"]: [1, 0], nomes["AC"]: [2, 2]}
        linhas = (alt.Chart(longo).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
                  .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                          y=alt.Y("valor:Q", title="R$ acumulado na release"),
                          color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom,
                                                                                range=[cor[x] for x in dom])),
                          strokeDash=alt.StrokeDash("nome:N", legend=None,
                                                    scale=alt.Scale(domain=dom, range=[traco[x] for x in dom])),
                          tooltip=[alt.Tooltip("sprint:O", title="Sprint"), alt.Tooltip("nome:N", title="Série"),
                                   alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
        nota = "Entregue abaixo do planejado = atraso. Gasto acima do entregue = custou mais do que entregou."
        if not tem_ac:
            nota += f" O gasto não aparece: {_motivo_ac(u)}."
        charts.mostrar(linhas + charts.regra_horizontal(u["BAC"], f"orçamento {brl(u['BAC'], 0)}", theme.INK["muted"]),
                       f"Planejado × entregue × gasto — {rel}", "R$ acumulado · uma marca por sprint iniciada",
                       nota=nota, altura=280)
    e2, d2 = st.columns(2)
    with e2:
        prog = feitas.melt(id_vars=["sprint"], value_vars=["PPC", "APC"], var_name="serie", value_name="valor")
        prog["nome"] = prog["serie"].map({"PPC": "Prazo decorrido (PPC)", "APC": "Escopo entregue (APC)"})
        dom = ["Prazo decorrido (PPC)", "Escopo entregue (APC)"]
        g = (alt.Chart(prog).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
             .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                     y=alt.Y("valor:Q", title="% da release", axis=alt.Axis(format="%"),
                             scale=alt.Scale(domain=[0, 1])),
                     color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[theme.SERIES[2],
                                                                                           theme.SERIES[0]])),
                     strokeDash=alt.StrokeDash("nome:N", legend=None,
                                               scale=alt.Scale(domain=dom, range=[[6, 4], [1, 0]])),
                     tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Série"),
                              alt.Tooltip("valor:Q", title="%", format=".0%")]))
        charts.mostrar(g, "Prazo decorrido × escopo entregue", "a distância entre as linhas é o atraso", altura=220)
    with d2:
        idx = feitas.melt(id_vars=["sprint"], value_vars=["SPI", "CPI"], var_name="indice",
                          value_name="valor").dropna()
        if idx.empty:
            layout.indisponivel("Índices indisponíveis", "sem valor planejado nem custo real.")
        else:
            idx["nome"] = idx["indice"].map({"SPI": "Prazo (SPI)", "CPI": "Custo (CPI)"})
            dom = [x for x in ("Prazo (SPI)", "Custo (CPI)") if x in set(idx["nome"])]
            g = (alt.Chart(idx).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
                 .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                         y=alt.Y("valor:Q", title="Índice",
                                 scale=alt.Scale(domain=[0, max(1.2, idx["valor"].max() + .1)])),
                         color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom,
                                                                               range=theme.SERIES[:len(dom)])),
                         tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Índice"),
                                  alt.Tooltip("valor:Q", title="Valor", format=".2f")]))
            charts.mostrar(g + charts.regra_horizontal(1.0, "1,0 = no plano"), "Índices de prazo e custo",
                           "acima de 1,0 = melhor que o plano", altura=220,
                           nota=None if "Custo (CPI)" in dom else f"Custo não aparece: {_motivo_ac(u)}.")
    b = feitas.assign(restante=feitas["PRP"] - feitas["RPC"], ideal=feitas["PRP"] * (1 - feitas["PPC"]))
    nomes_b = {"restante": "Falta entregar", "ideal": "Deveria faltar", "PRP": "Escopo total (PRP)"}
    longo_b = b.melt(id_vars=["sprint"], value_vars=list(nomes_b), var_name="serie", value_name="pontos")
    longo_b["nome"] = longo_b["serie"].map(nomes_b)
    dom = list(nomes_b.values())
    g = (alt.Chart(longo_b).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True))
         .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                 y=alt.Y("pontos:Q", title="Story Points"),
                 color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[
                     theme.SERIES[0], theme.SERIES[2], theme.SERIES[1]])),
                 strokeDash=alt.StrokeDash("nome:N", legend=None,
                                           scale=alt.Scale(domain=dom, range=[[1, 0], [6, 4], [2, 2]])),
                 tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Série"),
                          alt.Tooltip("pontos:Q", title="SP", format=".0f")]))
    charts.mostrar(g, f"Burndown da release — {rel}", "Story Points no fim de cada sprint", altura=240,
                   nota="Se o escopo total sobe, entrou trabalho novo na release e o que falta sobe junto, mesmo com "
                        "o time entregando. Burndown dia a dia de cada sprint: página Gestão ágil.")


def _rastreabilidade(ctx, rel, d, u):
    """De onde vem cada número: stories (Zenhub), horas por sprint e orçamento por semana (planilha)."""
    ate = d[(d["n"] <= u["n"]) & d["PRP"].notna()]
    ids = set(ctx.zh_iniciadas.loc[(ctx.zh_iniciadas["release_name"] == rel)
                                   & ctx.zh_iniciadas["sprint_label"].isin(ate["sprint"]), "sprint_id"])
    linhas = ga.stories_por_sprint(ctx.zh_snap, ctx.zh_iniciadas, ctx.zh_issues, ctx.zh_regras)
    x = linhas[linhas["sprint_id"].isin(ids)].sort_values("ordem_sprint")
    t1, t2, t3 = st.tabs([f"Stories do escopo (PRP {num(u['PRP'])} SP · RPC {num(u['RPC'])} SP)",
                          "Horas e custo real por sprint (AC)", "Orçamento por semana (BAC)"])
    with t1:
        if x.empty:
            st.caption("Sem stories nas sprints da release.")
        else:
            por = x.groupby("issue_id").agg(
                issue=("issue", "first"), url=("url", "first"), titulo=("titulo", "first"),
                epico=("epico", "first"), epico_url=("epico_url", "first"), sp=("sp_atual", "first"),
                sprints=("sprint", lambda s: ", ".join(dict.fromkeys(s))),
                concluida=("concluida", "any"),
                concluida_na=("sprint", lambda s: ", ".join(s[x.loc[s.index, "concluida"]])),
            ).reset_index(drop=True)
            por["sp"] = por["sp"].map(lambda v: 0 if v is None or pd.isna(v) else float(v))
            prp, rpc = por["sp"].sum(), por.loc[por["concluida"], "sp"].sum()
            ok = abs(prp - u["PRP"]) < 1e-9 and abs(rpc - u["RPC"]) < 1e-9
            layout.alerta("good" if ok else "critical",
                          f"{len(por)} stories somam {num(prp)} SP (PRP) e as {int(por['concluida'].sum())} "
                          f"concluídas somam {num(rpc)} SP (RPC)" + (" — confere com o EVM." if ok else
                                                                      f" — NÃO confere com o EVM ({num(u['PRP'])} / "
                                                                      f"{num(u['RPC'])})."))
            por["issue_l"] = [[(ga.rotulo_issue(i), l)] for i, l in zip(por["issue"], por["url"])]
            por["titulo_l"] = [[(str(t), l)] for t, l in zip(por["titulo"], por["url"])]
            por["epico_l"] = [[(str(e), l if isinstance(l, str) else None)] for e, l in zip(por["epico"],
                                                                                          por["epico_url"])]
            por["situacao"] = por.apply(lambda r: f"concluída na {r['concluida_na']}" if r["concluida"]
                                        else "não concluída", axis=1)
            layout.tabela_html(por.sort_values(["concluida", "sp"], ascending=[False, False]),
                               {"issue_l": "Issue", "titulo_l": "Título", "epico_l": "Épico", "sp": "SP",
                                "sprints": "Passou pelas sprints", "situacao": "Situação"},
                               links=("issue_l", "titulo_l", "epico_l"), numericas=("sp",))
            st.caption("SP = estimativa atual (a mesma do PRP). Uma story que passou por várias sprints conta uma vez.")
    with t2:
        h = ctx.horas
        if h is None or h.empty:
            layout.indisponivel("Aba Horas não lida", _motivo_ac(u))
        else:
            reg = []
            for r in ate.itertuples():
                numero = int(r.sprint.lstrip("S")) if r.sprint.lstrip("S").isdigit() else None
                hs = h[h["sprint"] == numero] if numero is not None else h.iloc[0:0]
                reg.append({"sprint": r.sprint, "horas": r.horas_reais,
                            "integrantes": f"{int(r.integrantes_com_horas)} de {num(r.integrantes_ativos)}"
                            if not vazio(r.integrantes_ativos) else f"{int(r.integrantes_com_horas)}",
                            "custo": r.horas_reais * ctx.custo["custo_hora"] if ctx.custo.get("custo_hora")
                            and r.horas_reais else None,
                            "situacao": str(r.origem_do_ac), "linhas": len(hs)})
            layout.tabela_html(pd.DataFrame(reg), {"sprint": "Sprint", "horas": "Horas registradas",
                                                   "integrantes": "Integrantes com horas / ativos",
                                                   "custo": "Custo real da sprint (R$)", "situacao": "Situação"},
                               numericas=("horas", "custo"), altura=None)
            st.markdown(f"Custo por hora: **{brl(ctx.custo.get('custo_hora'))}** (chave `custo_hora`) · fontes: "
                        f"[aba Horas]({planilha.link_aba('horas')}) · [aba Custos]({planilha.link_aba('custos')})")
    with t3:
        p = ctx.plano
        if p is None or p.empty:
            layout.indisponivel("Aba Planejamento não lida", "sem custo planejado por semana.")
        else:
            ini, fim = d["inicio_da_sprint"].min(), d["fim_da_sprint"].max()
            w = p[(p["semana"] >= ini) & (p["semana"] <= fim)][["semana", "sprint", "integrantes", "custo"]].copy()
            w["semana"] = w["semana"].map(data_br)
            layout.tabela_html(w, {"semana": "Semana de", "sprint": "Sprint", "integrantes": "Integrantes ativos",
                                   "custo": "Custo planejado (R$)"}, numericas=("sprint", "integrantes", "custo"),
                               altura=None)
            st.markdown(f"Total = **{brl(w['custo'].sum() if not w.empty else None, 0)}** = BAC da {rel} · custo de "
                        f"um integrante por semana: **{brl(ctx.custo.get('custo_membro_semana'))}** · fontes: "
                        f"[aba Planejamento]({planilha.link_aba('planejamento')}) · "
                        f"[aba Custos]({planilha.link_aba('custos')})")


def _tabela_completa(d):
    cols = {"sprint": "Sprint", "status": "Situação", "PPC": "PPC", "PRP": "PRP (SP)", "RPC": "RPC (SP)",
            "APC": "APC", "BAC": "BAC", "PV": "PV", "EV": "EV", "horas_reais": "Horas", "AC": "AC",
            "SV": "SV", "CV": "CV", "SPI": "SPI", "CPI": "CPI", "ETC": "ETC", "EAC": "EAC",
            "origem_do_ac": "Origem do AC"}
    t = d[[c for c in cols if c in d]].rename(columns=cols)
    fmt = {c: st.column_config.NumberColumn(c, format="R$ %.0f") for c in ("BAC", "PV", "EV", "AC", "SV", "CV", "ETC",
                                                                          "EAC")}
    fmt.update({c: st.column_config.NumberColumn(c, format="%.2f") for c in ("SPI", "CPI")})
    fmt.update({c: st.column_config.NumberColumn(c, format="%.2f") for c in ("PPC", "APC")})
    st.dataframe(t, use_container_width=True, hide_index=True, column_config=fmt)
    st.download_button("Baixar CSV do Agile EVM", t.to_csv(index=False).encode("utf-8-sig"),
                       file_name="agile_evm.csv", mime="text/csv", key="csv_evm")


# ───────────────────────── página ─────────────────────────

def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Agile EVM", "Prazo e custo da release: entregas do Zenhub × orçamento e horas da planilha.",
                         ["ZENHUB", "PLANILHA", "CALCULADO"])
    e = ctx.evm
    if e is None or e.empty:
        layout.indisponivel("Agile EVM indisponível", "não há sprints do Zenhub associadas a releases.",
                            "snapshot do Zenhub (`scripts/coleta_velocity.py`) e aba Planejamento da planilha.")
        return
    rels = list(dict.fromkeys(e["release"]))
    iniciadas = e.dropna(subset=["PRP"])
    padrao = resumo.release_em_foco(ctx, f["release"])[0] or (iniciadas["release"].iloc[-1] if not iniciadas.empty
                                                              else rels[0])
    c1, c2 = st.columns([1, 1.4])
    rel = c1.radio("Release", rels, index=rels.index(padrao) if padrao in rels else 0, horizontal=True,
                   key="evm_release")
    d = e[e["release"] == rel]
    feitas = d.dropna(subset=["PRP"])
    if feitas.empty:
        layout.indisponivel(f"A {rel} ainda não começou", "nenhuma sprint dela foi iniciada.")
        return
    opcoes = list(feitas["sprint"])
    concluidas = feitas[feitas["status"] == vel.STATUS_CONCLUIDA]
    padrao_sprint = concluidas["sprint"].iloc[-1] if not concluidas.empty else opcoes[-1]
    rotulos = {r.sprint: f"{r.sprint} ({r.status}, até {data_br(r.fim_da_sprint)})" for r in feitas.itertuples()}
    escolhida = c2.selectbox("Situação ao fim da sprint", opcoes, index=opcoes.index(padrao_sprint),
                             format_func=rotulos.get, key=f"evm_sprint_{rel}",
                             help="Por padrão a última concluída: a sprint em andamento ainda não tem horas.")
    u = feitas[feitas["sprint"] == escolhida].iloc[-1]
    parcial = u["status"] == vel.STATUS_ANDAMENTO

    layout.secao(f"Situação da {rel} ao fim da {u['sprint']}" + (" (em andamento)" if parcial else ""),
                 "O projeto está no prazo e no custo previstos?", ["CALCULADO"])
    _leitura(rel, u, parcial)
    _kpis(u, d)
    base = u["prp_linha_de_base"]
    if not vazio(base) and base > 0 and u["PRP"] > base * 1.5:
        layout.alerta("warning", f"O escopo da {rel} cresceu de {num(base)} SP (planejado na 1ª sprint) para "
                                 f"{num(u['PRP'])} SP: o SPI compara a entrega com um escopo maior do que o planejado.")
    elif not vazio(base) and base == 0 and u["PRP"] > 0:
        layout.alerta("warning", f"Nada foi estimado na planning da 1ª sprint da {rel}; todo o escopo "
                                 f"({num(u['PRP'])} SP) entrou depois.")

    layout.secao("Legenda", "O que significa cada sigla e de onde vem?", ["ZENHUB", "PLANILHA"])
    _legenda()

    layout.secao("Evolução da release", "Como prazo, custo e escopo evoluíram sprint a sprint?", ["CALCULADO"])
    _graficos(rel, feitas, u)

    layout.secao("De onde vem cada número", "Quais stories, horas e semanas formam o EVM?", ["ZENHUB", "PLANILHA"])
    _rastreabilidade(ctx, rel, d, u)

    with st.expander("Tabela completa do Agile EVM (todas as sprints da release)"):
        _tabela_completa(d)
