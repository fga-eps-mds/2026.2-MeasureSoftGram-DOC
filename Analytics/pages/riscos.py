"""Riscos — plano de riscos do time (fonte: planilha, abas Riscos e Monitoramento).

Ordem: cartões → dado bruto (tabela de riscos) → análise (matriz P × I e evolução
da exposição) → aba original. Riscos avaliados no Monitoramento que não existem na
aba Riscos aparecem como aviso (o painel não os inventa).
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config

from src import theme
from src.components import charts, layout, rastreio
from src.components.kpi import kpi
from src.metrics import resumo
from src.metrics.calculations import num, vazio

NIVEIS = ["Elevado", "Médio", "Baixo"]
COR_NIVEL = alt.Scale(domain=NIVEIS, range=[theme.RISCO["Elevado"], theme.RISCO["Médio"], theme.RISCO["Baixo"]])
ELEVADO, MEDIO = config.RISCO_ELEVADO, config.RISCO_MEDIO
ENCERRADO = ("encerr", "mitigad", "fechad")


def _nivel(exposicao) -> str | None:
    if vazio(exposicao):
        return None
    return "Elevado" if exposicao >= ELEVADO else ("Médio" if exposicao >= MEDIO else "Baixo")


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Riscos", "Quais riscos ameaçam o projeto, quão graves são e qual a resposta planejada.",
                         ["PLANILHA"])
    layout.menus([
        ("Probabilidade (P) e impacto (I)", "chance de acontecer e tamanho do estrago, de 1 a 5",
         "avaliação do time na revisão mais recente", [rastreio.aba("riscos"), rastreio.aba("monitoramento")]),
        ("Exposição", "gravidade do risco", "P × I (1 a 25)", [rastreio.aba("riscos")]),
        ("Nível", "faixa da exposição", f"Baixo < {MEDIO} ≤ Médio < {ELEVADO} ≤ Elevado", []),
        ("Não encerrado", "risco que ainda exige acompanhamento", "status diferente de encerrado, mitigado ou fechado "
         "(aberto, em monitoramento e materializado contam)", [rastreio.aba("riscos")]),
        ("Materializado", "o risco aconteceu: virou problema", "status Materializado na aba Riscos",
         [rastreio.aba("riscos")]),
    ], [
        ("Limite de risco elevado", f"P × I ≥ {ELEVADO}", "config.py · RISCO_ELEVADO", rastreio.codigo()),
        ("Limite de risco médio", f"P × I ≥ {MEDIO}", "config.py · RISCO_MEDIO", rastreio.codigo()),
    ], fontes=["PLANILHA", "CALCULADO"])
    r = ctx.riscos
    if r is None or r.empty:
        layout.indisponivel("Aba Riscos não lida", ctx.origem_planilha.get("riscos", "não lida").replace("**", ""),
                            "publicar a aba Riscos e colar o link em `config.PLANILHAS`.")
        return
    r = r.copy()
    r["nivel"] = r["exposicao_atual"].map(_nivel)
    r["status"] = r["status"].astype(str).str.strip()
    baixo = r["status"].str.lower()
    ativos = r[~baixo.str.startswith(ENCERRADO)]
    cont = resumo.contagem_riscos(r)

    layout.secao("Resumo", "Quantos riscos estão ativos e quão graves eles são?", ["PLANILHA"])
    k = st.columns(4)
    with k[0]:
        kpi("Não encerrados", num(len(ativos)), "PLANILHA", nota=f"{cont['frase'] or 'nenhum'} · {len(r)} registrados",
            origem=[rastreio.aba("riscos")])
    with k[1]:
        n = int((ativos["exposicao_atual"] >= ELEVADO).sum())
        kpi("Exposição elevada", num(n), "PLANILHA", status="critical" if n >= 3 else ("warning" if n else "good"),
            nota=", ".join(ativos.loc[ativos["exposicao_atual"] >= ELEVADO, "id"]) or f"nenhum com P × I ≥ {ELEVADO}")
    with k[2]:
        m = r[baixo.str.startswith("materializ")]
        kpi("Materializados", num(len(m)), "PLANILHA", status="critical" if len(m) else "good",
            nota=", ".join(m["id"]) or "nenhum")
    with k[3]:
        sem = ativos[ativos["responsavel"].astype(str).str.strip().isin(["", "nan", "None"])] \
            if "responsavel" in ativos else None
        kpi("Sem responsável", num(len(sem)) if sem is not None else None, "PLANILHA",
            status=None if sem is None else ("good" if sem.empty else "warning"),
            nota=", ".join(sem["id"]) if sem is not None and len(sem) else "todos com responsável")
    for rid in resumo.riscos_fora_da_aba(ctx.riscos, ctx.monitoramento):
        layout.alerta("warning", f"{rid} tem avaliação na aba Monitoramento, mas não existe na aba Riscos: o painel "
                                 "não o conta até ser cadastrado lá.", link=(rid, rastreio.aba("monitoramento")[1]))

    layout.secao("Dado bruto", "Qual é o plano de resposta de cada risco?", ["PLANILHA"])
    c = st.columns(3)
    t = r
    for col, (campo, rot) in zip(c, [("status", "Status"), ("nivel", "Nível"), ("categoria", "Categoria")]):
        if campo in t:
            sel = col.multiselect(rot, sorted(v for v in t[campo].dropna().unique() if str(v).strip()),
                                  key=f"risco_{campo}", placeholder="Todos")
            if sel:
                t = t[t[campo].isin(sel)]
    colunas = {"id": "ID", "risco": "Risco", "categoria": "Categoria", "probabilidade_atual": "P",
               "impacto_atual": "I", "exposicao_atual": "P × I", "nivel": "Nível", "status": "Status",
               "resposta": "Resposta", "acao_preventiva": "Ação preventiva", "contingencia": "Contingência",
               "responsavel": "Responsável", "ultima_sprint_avaliada": "Última sprint avaliada"}
    tt = t.sort_values("exposicao_atual", ascending=False)
    st.dataframe(tt[[x for x in colunas if x in tt]].rename(columns=colunas), use_container_width=True,
                 hide_index=True, column_config={
                     "Risco": st.column_config.TextColumn(width="large"),
                     "Ação preventiva": st.column_config.TextColumn(width="large"),
                     "P × I": st.column_config.NumberColumn(format="%d")})
    st.caption(f"{len(tt)} de {len(r)} riscos · ordenados pela exposição.")

    layout.secao("Análise", "Onde estão os riscos mais graves e a exposição está caindo?", ["PLANILHA"])
    e, d = st.columns([1.1, 1])
    with e:
        grade = pd.DataFrame([(p, i) for p in range(1, 6) for i in range(1, 6)], columns=["p", "i"])
        grade["nivel"] = (grade["p"] * grade["i"]).map(_nivel)
        cont_g = (ativos.dropna(subset=["probabilidade_atual", "impacto_atual"])
                  .assign(p=lambda x: x["probabilidade_atual"].astype(int),
                          i=lambda x: x["impacto_atual"].astype(int))
                  .groupby(["p", "i"]).agg(ids=("id", lambda x: ", ".join(map(str, x)))).reset_index())
        grade = grade.merge(cont_g, on=["p", "i"], how="left").fillna({"ids": ""})
        fundo = (alt.Chart(grade).mark_rect(stroke=theme.INK["surface"], strokeWidth=2)
                 .encode(x=alt.X("p:O", title="Probabilidade", axis=alt.Axis(labelAngle=0)),
                         y=alt.Y("i:O", title="Impacto", sort="descending"),
                         color=alt.Color("nivel:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                         tooltip=[alt.Tooltip("p:O", title="P"), alt.Tooltip("i:O", title="I"),
                                  alt.Tooltip("nivel:N"), alt.Tooltip("ids:N", title="Riscos")]))
        txt = (alt.Chart(grade[grade["ids"] != ""]).mark_text(fontSize=11, fontWeight=600,
                                                             color=theme.INK["primary"], lineBreak=", ")
               .encode(x="p:O", y=alt.Y("i:O", sort="descending"), text="ids:N"))
        charts.mostrar(fundo + txt, "Matriz probabilidade × impacto", "riscos não encerrados · avaliação mais recente",
                       altura=300)
    with d:
        m = ctx.monitoramento
        if m is None or m.empty or m["sprint"].dropna().empty:
            layout.indisponivel("Evolução indisponível", "a aba Monitoramento não tem avaliações.")
        else:
            m = m.dropna(subset=["exposicao"]).assign(nivel=lambda x: x["exposicao"].map(_nivel))
            heat = (alt.Chart(m).mark_rect(stroke=theme.INK["surface"], strokeWidth=2)
                    .encode(x=alt.X("sprint:O", title="Sprint avaliada", axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("id_do_risco:N", title=None),
                            color=alt.Color("nivel:N", title="Nível", scale=COR_NIVEL, sort=NIVEIS),
                            tooltip=[alt.Tooltip("id_do_risco:N", title="Risco"), alt.Tooltip("sprint:O"),
                                     alt.Tooltip("probabilidade:Q", title="P"), alt.Tooltip("impacto:Q", title="I"),
                                     alt.Tooltip("exposicao:Q", title="P × I"), alt.Tooltip("status:N")]))
            txt = heat.mark_text(fontSize=10).encode(text="exposicao:Q", color=alt.value(theme.INK["primary"]))
            charts.mostrar(heat + txt, "Exposição de cada risco por revisão", "P × I em cada sprint avaliada",
                           altura=max(200, 20 * m["id_do_risco"].nunique()),
                           nota="Só há uma revisão: cada nova avaliação na planning vira uma coluna."
                           if m["sprint"].nunique() < 2 else None)

    for chave in ("riscos", "monitoramento"):
        rastreio.aba_original(chave)
