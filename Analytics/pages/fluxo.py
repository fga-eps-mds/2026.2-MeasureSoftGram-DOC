"""Fluxo — Throughput, Lead Time e Cycle Time do trabalho técnico e dos defeitos (fonte ZENHUB).

Task, Sub-task, Bug e issues sem tipo não pontuam no Velocity nem no Agile EVM: só a US aceita pelo PO
pontua (DA-R3.02, ata R2 ação C1.4). Aqui elas são acompanhadas pelo fluxo, **sem story points**, para não
distorcer o EVM. Os cálculos estão em ``src/metrics/fluxo.py``.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import theme
from src.components import charts, filters, layout
from src.components.kpi import kpi
from src.metrics import fluxo
from src.metrics.calculations import data_br, num

ZENHUB = ("Zenhub · issues (Gestão ágil)", "./zenhub")

ESCOPO = {
    "periodo": "itens concluídos no período (Throughput e Lead Time) e issues ativas nele (taxa de conclusão)",
    "repos": "só as issues desses repositórios",
}
COR_TIPO = {"Task": theme.SERIES[0], "Sub-task": theme.SERIES[2], "Bug": theme.SERIES[1], "Sem tipo": theme.INK["muted"]}


def _menus():
    layout.menus([
        ("Throughput", "quantos itens o time conclui por semana", "issues fechadas por semana (segunda a domingo, "
         "Brasília); sem story points", [ZENHUB]),
        ("Lead Time", "quanto tempo uma issue leva da criação ao fechamento", "mediana e percentil 85, em dias, das "
         "issues fechadas no período", [ZENHUB]),
        ("Cycle Time", "quanto tempo leva do início do trabalho ao fechamento", "entrada em In Progress → fechamento; "
         "indisponível: a coleta não guarda essa data", []),
        ("Taxa de conclusão", "quanto do trabalho técnico ativo foi concluído", "fechadas ÷ ativas no período "
         "(Development Task Completion do Q-Rapids)", [ZENHUB]),
    ], [
        ("Tipos acompanhados", ", ".join(fluxo.TIPOS_FLUXO), "src/metrics/fluxo.py · TIPOS_FLUXO", None),
        ("Fora do fluxo", "Feature (US, medida pelo Agile EVM), Epic, Initiative, Project",
         "a US é medida em story points", None),
    ], fontes=["ZENHUB", "CALCULADO"])


def _serie_chart(tp: pd.DataFrame, media: float):
    ordem = [t for t in fluxo.TIPOS_FLUXO if t in set(tp["tipo"])]
    barras = (alt.Chart(tp).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
              .encode(x=alt.X("semana:T", title="Semana (segunda-feira)", axis=alt.Axis(format="%d/%m")),
                      y=alt.Y("itens:Q", title="Itens concluídos"),
                      color=alt.Color("tipo:N", title="Tipo", sort=ordem,
                                      scale=alt.Scale(domain=ordem, range=[COR_TIPO[t] for t in ordem])),
                      tooltip=[alt.Tooltip("semana:T", title="Semana de", format="%d/%m/%Y"),
                               alt.Tooltip("tipo:N", title="Tipo"), alt.Tooltip("itens:Q", title="Itens")]))
    return barras + charts.regra_horizontal(media, f"média {num(media, 1)} por semana", theme.INK["muted"])


def _lead_chart(fechadas: pd.DataFrame, lt: dict):
    ordem = [t for t in fluxo.TIPOS_FLUXO if t in set(fechadas["tipo"])]
    hist = (alt.Chart(fechadas).mark_bar()
            .encode(x=alt.X("lead_dias:Q", bin=alt.Bin(maxbins=20), title="Lead Time (dias)"),
                    y=alt.Y("count():Q", title="Issues"),
                    color=alt.Color("tipo:N", title="Tipo", sort=ordem,
                                    scale=alt.Scale(domain=ordem, range=[COR_TIPO[t] for t in ordem])),
                    tooltip=[alt.Tooltip("count():Q", title="Issues")]))
    return hist + charts.regra_vertical(lt["mediana"], f"mediana {num(lt['mediana'], 1)} d", theme.INK["muted"])


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Fluxo", "Trabalho técnico e defeitos pelo fluxo (Throughput, Lead Time, Cycle Time), "
                         "sem story points e sem alterar o Agile EVM.", ["ZENHUB", "CALCULADO"])
    _menus()
    universo = ctx.zh_issues
    if universo is None or universo.empty:
        layout.indisponivel("Fluxo indisponível", "não há issues do Zenhub carregadas.",
                            "snapshot do Zenhub (`scripts/coleta_velocity.py`).")
        return

    caixa = filters.da_pagina(f, ESCOPO)
    universo = filters.por_repo(universo, f["repos"])
    itens = fluxo.itens_de_fluxo(universo)
    if itens.empty:
        st.info("Nenhuma Task, Sub-task, Bug ou issue sem tipo nos repositórios selecionados.")
        return
    tipos = caixa.multiselect("Tipo", list(fluxo.TIPOS_FLUXO), key="fluxo_tipos", placeholder="Todos")
    if tipos:
        itens = itens[itens["tipo"].isin(tipos)]
    ini, fim = pd.Timestamp(f["periodo"][0]), pd.Timestamp(f["periodo"][1])
    st.caption(f"{filters.resumo_ativos(f, ESCOPO)} · atualizado com o snapshot do Zenhub")

    layout.alerta("neutral", "Task, Sub-task e Bug não pontuam: o Agile EVM, a Velocity, o SPI e o CPI contam só "
                             "story points de US aceitas pelo PO. Aqui o trabalho técnico é medido em itens e dias.")

    tp = fluxo.throughput_semanal(itens, ini, fim)
    lt = fluxo.lead_time(itens, ini, fim)
    ct = fluxo.cycle_time(itens)
    taxa = fluxo.taxa_conclusao(itens, ini, fim)
    abertas = int((itens["aberta"] & (itens["criada"] < fim + pd.Timedelta(days=1))).sum())
    analise = fluxo.analise_critica(tp, lt, taxa, abertas)

    layout.secao("Resumo", "O trabalho técnico está fluindo e em que ritmo?", ["ZENHUB", "CALCULADO"])
    k = st.columns(4)
    por_semana = tp.groupby("semana")["itens"].sum() if not tp.empty else pd.Series(dtype=float)
    with k[0]:
        kpi("Throughput médio", f"{num(por_semana.mean(), 1)} por semana" if len(por_semana) else None, "CALCULADO",
            nota=f"{int(por_semana.sum())} itens em {len(por_semana)} semanas" if len(por_semana)
            else "Indisponível: nenhum item concluído no período.", origem=[ZENHUB])
    with k[1]:
        kpi("Lead Time (mediana)", f"{num(lt['mediana'], 1)} dias" if lt["n"] else None, "CALCULADO",
            nota=f"P85 {num(lt['p85'], 1)} dias · {lt['n']} issues fechadas" if lt["n"]
            else "Indisponível: nenhuma issue fechada no período.", origem=[ZENHUB])
    with k[2]:
        kpi("Cycle Time", None, "CALCULADO", nota=f"Indisponível: {ct['motivo']}.")
    with k[3]:
        kpi("Taxa de conclusão", f"{taxa['taxa'] * 100:.0f}%" if taxa["taxa"] is not None else None, "CALCULADO",
            nota=f"{taxa['fechadas']} de {taxa['ativas']} issues ativas no período" if taxa["taxa"] is not None
            else "Indisponível: nenhuma issue ativa no período.", origem=[ZENHUB])

    layout.secao("Análise", "Quanto o time conclui por semana e quanto tempo cada issue leva?", ["CALCULADO"])
    if tp.empty:
        layout.indisponivel("Sem conclusões no período", "nenhuma Task, Sub-task ou Bug foi fechada entre "
                            f"{data_br(ini)} e {data_br(fim)}.")
    else:
        charts.mostrar(_serie_chart(tp, float(por_semana.mean())), "Throughput semanal",
                       "itens concluídos por semana e tipo · semanas sem conclusão aparecem com 0",
                       nota=analise.get("throughput"), altura=240)
    fechadas = itens[itens["fechada"].notna() & itens["lead_dias"].notna()
                     & (itens["fechada"] >= ini) & (itens["fechada"] < fim + pd.Timedelta(days=1))]
    if lt["n"]:
        charts.mostrar(_lead_chart(fechadas, lt), "Lead Time das issues fechadas",
                       "dias da criação ao fechamento · cada barra agrupa issues por faixa de dias",
                       nota=analise.get("lead_time"), altura=240)
        por = lt["por_tipo"].rename(columns={"tipo": "Tipo", "n": "Issues", "mediana": "Mediana (dias)",
                                             "p85": "P85 (dias)"})
        st.dataframe(por, use_container_width=True, hide_index=True,
                     column_config={"Mediana (dias)": st.column_config.NumberColumn(format="%.1f"),
                                    "P85 (dias)": st.column_config.NumberColumn(format="%.1f")})
    if analise.get("taxa"):
        st.caption(analise["taxa"])
    layout.indisponivel("Cycle Time indisponível", ct["motivo"], ct["necessario"])

    sem = fluxo.sem_tipo(universo)
    if not sem.empty:
        layout.alerta("warning", f"{len(sem)} issue(s) sem tipo no Zenhub entram no fluxo como \"Sem tipo\" "
                                 "(o painel não adivinha o tipo). Marcar o tipo no Zenhub as coloca na categoria certa "
                                 "(Task, Bug ou Feature).")
        if layout.detalhes("fluxo_sem_tipo", "Mostrar as issues sem tipo"):
            layout.tabela_html(sem.assign(titulo_l=[[(str(t), u)] for t, u in zip(sem["title"], sem["url"])],
                                          criada=sem["criada"].map(data_br),
                                          fechada=sem["fechada"].map(lambda x: data_br(x) if pd.notna(x) else "aberta")),
                               {"titulo_l": "Issue", "repositorio": "Repositório", "criada": "Criada",
                                "fechada": "Fechada"}, links=("titulo_l",))

    if layout.detalhes("fluxo", "Mostrar as issues do fluxo"):
        layout.secao("Dado bruto", "Quais issues formam o fluxo?", ["ZENHUB"])
        t = itens.sort_values("criada", ascending=False).assign(
            criada=lambda d: d["criada"].dt.strftime("%d/%m/%Y"),
            fechada=lambda d: d["fechada"].dt.strftime("%d/%m/%Y").fillna("aberta"))
        cols = ["repositorio", "number", "title", "tipo", "criada", "fechada", "lead_dias"]
        st.dataframe(t[cols].rename(columns={"repositorio": "Repositório", "number": "Nº", "title": "Título",
                                             "tipo": "Tipo", "criada": "Criada", "fechada": "Fechada",
                                             "lead_dias": "Lead Time (dias)"}),
                     use_container_width=True, hide_index=True,
                     column_config={"Lead Time (dias)": st.column_config.NumberColumn(format="%.1f")})
        st.download_button("Baixar CSV do fluxo", t[cols].to_csv(index=False).encode("utf-8-sig"),
                           file_name="fluxo_trabalho_tecnico.csv", mime="text/csv", key="csv_fluxo")
