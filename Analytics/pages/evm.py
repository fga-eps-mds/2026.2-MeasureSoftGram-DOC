"""Agile EVM — pontos do ZENHUB + custos da PLANILHA (Sulaiman, Barton & Blackburn, 2006)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config

from src import theme
from src.components import charts, layout
from src.components.kpi import kpi
from src.metrics import resumo
from src.metrics import velocity as vel
from src.metrics.calculations import brl, data_br, data_limite, num, pct, status_indice, vazio

NOMES = {"PV": "PV — valor planejado", "EV": "EV — valor agregado", "AC": "AC — custo real"}


def _motivo_ac(u) -> str:
    o = str(u.get("origem_do_ac") or "")
    return o.replace("indisponível: ", "") if o.startswith("indisponível") else "sem horas registradas"


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Agile EVM", "Valor agregado por release: pontos do Zenhub, orçamento e custo real da "
                         "planilha do time.", ["ZENHUB", "PLANILHA", "CALCULADO"])
    layout.metodologia([
        ("PRP — escopo da release", "ZENHUB", "SP das issues pontuáveis que passaram pelas sprints da release até a "
         "sprint n (cada issue uma vez); linha de base = planejado da 1ª sprint; PA = o que entrou depois"),
        ("RPC · APC", "ZENHUB", "RPC = SP do escopo já concluídos; APC = RPC ÷ PRP (% realizado)"),
        ("PPC — % planejado", "ZENHUB (datas das sprints)", "semanas decorridas da release ÷ semanas da release"),
        ("BAC — orçamento", "PLANILHA (abas Custos e Planejamento)", "soma do custo planejado das semanas da release "
         "(integrantes ativos × custo semanal de um integrante)"),
        ("PV · EV", "cálculo", "PV = PPC × BAC · EV = APC × BAC"),
        ("AC — custo real", "PLANILHA (aba Horas × custo/hora da aba Custos)", "acumulado das sprints da release; "
         "sprint sem horas registradas deixa o AC indisponível (nunca é trocado pelo custo planejado)"),
        ("SV · CV", "cálculo", "SV = EV − PV · CV = EV − AC"),
        ("SPI · CPI", "cálculo", f"SPI = EV ÷ PV · CPI = EV ÷ AC · 1,0 = no plano; meta ≥ {num(config.META_INDICE_EVM, 2)}"),
        ("ETC · EAC", "cálculo", "ETC = (BAC − EV) ÷ CPI · EAC = AC + ETC"),
        ("Término estimado", "cálculo", "início da release + duração ÷ SPI (projeção no ritmo atual); se passar da "
         f"Release Final ({data_limite(config.RELEASE_FINAL)}) aparece como \"após {data_limite(config.RELEASE_FINAL)}\" — o prazo não se estende, a projeção mostra o atraso"),
    ])
    e = ctx.evm
    if e is None or e.empty:
        layout.indisponivel("Agile EVM indisponível", "não há sprints do Zenhub associadas a releases.",
                            "snapshot do Zenhub (`scripts/coleta_velocity.py`) e aba Planejamento da planilha.")
        return

    rels = list(dict.fromkeys(e["release"]))
    iniciadas = e.dropna(subset=["PRP"])
    padrao = resumo.release_em_foco(ctx, f["release"])[0] or (iniciadas["release"].iloc[-1] if not iniciadas.empty
                                                              else rels[0])
    rel = st.radio("Release", rels, index=rels.index(padrao), horizontal=True, key="evm_release")
    d = e[e["release"] == rel]
    feitas = d.dropna(subset=["PRP"])
    if feitas.empty:
        layout.indisponivel(f"A {rel} ainda não começou", "nenhuma sprint dela foi iniciada.")
        return
    # Sprint de referência: por padrão a última concluída (a em andamento ainda não tem horas nem
    # todos os pontos); o seletor deixa ver a situação em qualquer sprint já iniciada.
    opcoes = list(feitas["sprint"])
    concluidas = feitas[feitas["status"] == vel.STATUS_CONCLUIDA]
    padrao_sprint = concluidas["sprint"].iloc[-1] if not concluidas.empty else opcoes[-1]
    rotulos = {r.sprint: f"{r.sprint} ({r.status}, até {data_br(r.fim_da_sprint)})" for r in feitas.itertuples()}
    escolhida = st.selectbox("Situação ao fim da sprint", opcoes, index=opcoes.index(padrao_sprint),
                             format_func=rotulos.get, key=f"evm_sprint_{rel}")
    u = feitas[feitas["sprint"] == escolhida].iloc[-1]
    ate = feitas[feitas["n"] <= u["n"]]   # sprints até a escolhida (os gráficos mostram todas)
    parcial = u["status"] == vel.STATUS_ANDAMENTO
    motivo_ac = _motivo_ac(u)

    # ── dados usados ──
    layout.secao("Dados usados no cálculo", "Com quais números este EVM foi montado?",
                 ["ZENHUB", "PLANILHA"])
    tem_bac = not vazio(u["BAC"])
    tem_ac = not vazio(u["AC"])
    horas_reg = float(ate["horas_reais"].fillna(0).sum())
    insumos = pd.DataFrame([
        {"insumo": "Sprints e datas da release", "fonte": "ZENHUB", "situação": "disponível",
         "valor": f"{len(ate)} de {len(d)} sprints iniciadas · até {data_br(u['fim_da_sprint'])}"},
        {"insumo": "Escopo e pontos concluídos (PRP, RPC)", "fonte": "ZENHUB", "situação": "disponível",
         "valor": f"{num(u['RPC'])} de {num(u['PRP'])} SP · linha de base {num(u['prp_linha_de_base'])} SP"},
        {"insumo": "Orçamento da release (BAC)", "fonte": "PLANILHA",
         "situação": "disponível" if tem_bac else "indisponível", "valor": brl(u["BAC"])},
        {"insumo": "Custo por hora", "fonte": "PLANILHA",
         "situação": "disponível" if ctx.custo.get("custo_hora") else "indisponível",
         "valor": brl(ctx.custo.get("custo_hora"))},
        {"insumo": "Horas registradas na release", "fonte": "PLANILHA",
         "situação": "disponível" if tem_ac else "indisponível",
         "valor": f"{num(horas_reg)} h" + ("" if tem_ac else f" ({motivo_ac})")},
    ])
    st.dataframe(insumos, use_container_width=True, hide_index=True)

    # ── KPIs ──
    layout.secao(f"Situação da {rel} na {u['sprint']}" + (" (em andamento)" if parcial else ""),
                 "O projeto está no prazo e no custo previstos?", ["CALCULADO"])
    sem_ac = f"Indisponível: Actual Cost não foi fornecido ({motivo_ac})."
    sem_bac = "Indisponível: orçamento (BAC) não encontrado na planilha."
    linha1 = st.columns(4)
    with linha1[0]:
        kpi("Budget at Completion (BAC)", brl(u["BAC"]) if tem_bac else None, "PLANILHA", nota=None if tem_bac else sem_bac)
    with linha1[1]:
        kpi("Planned Value (PV)", brl(u["PV"]) if tem_bac else None, "CALCULADO",
            nota=f"PPC {pct(u['PPC'])} × BAC" if tem_bac else sem_bac)
    with linha1[2]:
        kpi("Earned Value (EV)", brl(u["EV"]) if tem_bac else None, "CALCULADO",
            nota=f"APC {pct(u['APC'])} × BAC" if tem_bac else sem_bac)
    with linha1[3]:
        kpi("Actual Cost (AC)", brl(u["AC"]) if tem_ac else None, "PLANILHA",
            nota="horas reais × custo/hora" if tem_ac else sem_ac)
    linha2 = st.columns(4)
    with linha2[0]:
        kpi("Schedule Performance Index (SPI)", num(u["SPI"], 2) if not vazio(u["SPI"]) else None, "CALCULADO",
            status=status_indice(u["SPI"]), nota=f"EV ÷ PV · meta ≥ {num(config.META_INDICE_EVM, 2)}" if not vazio(u["SPI"]) else
            "Indisponível: PV é zero ou não existe.")
    with linha2[1]:
        kpi("Cost Performance Index (CPI)", num(u["CPI"], 2) if not vazio(u["CPI"]) else None, "CALCULADO",
            status=status_indice(u["CPI"]), nota=f"EV ÷ AC · meta ≥ {num(config.META_INDICE_EVM, 2)}" if not vazio(u["CPI"]) else
            "CPI indisponível: Actual Cost não foi fornecido.")
    with linha2[2]:
        kpi("Schedule Variance (SV)", brl(u["SV"]) if not vazio(u["SV"]) else None, "CALCULADO",
            status=None if vazio(u["SV"]) else ("good" if u["SV"] >= 0 else "critical"),
            nota="EV − PV (negativo = atraso)" if not vazio(u["SV"]) else sem_bac)
    with linha2[3]:
        kpi("Cost Variance (CV)", brl(u["CV"]) if not vazio(u["CV"]) else None, "CALCULADO",
            status=None if vazio(u["CV"]) else ("good" if u["CV"] >= 0 else "critical"),
            nota="EV − AC (negativo = acima do custo)" if not vazio(u["CV"]) else sem_ac)
    linha3 = st.columns(4)
    with linha3[0]:
        kpi("Estimate at Completion (EAC)", brl(u["EAC"]) if not vazio(u["EAC"]) else None, "CALCULADO",
            nota="AC + ETC" if not vazio(u["EAC"]) else "EAC indisponível: depende do CPI, que depende do AC.")
    with linha3[1]:
        kpi("Estimate to Complete (ETC)", brl(u["ETC"]) if not vazio(u["ETC"]) else None, "CALCULADO",
            nota="(BAC − EV) ÷ CPI" if not vazio(u["ETC"]) else "ETC indisponível: depende do CPI, que depende do AC.")
    with linha3[2]:
        kpi("Planejado × realizado", f"{pct(u['PPC'])} × {pct(u['APC'])}", "CALCULADO",
            status=status_indice(u["SPI"]), nota="% do prazo decorrido (PPC) × % do escopo entregue (APC)")
    with linha3[3]:
        entrega = d["fim_da_sprint"].max()
        final = pd.Timestamp(config.RELEASE_FINAL)
        if vazio(u["RD"]):
            kpi("Término estimado", None, "CALCULADO", nota="Indisponível: SPI zero ou inexistente.")
        elif u["RD"] > final:
            # Projeção, não prazo: no ritmo atual a release só terminaria depois do fim do semestre.
            kpi("Término estimado", f"após {data_br(final)}", "CALCULADO", status="critical",
                nota=f"no ritmo atual (SPI {num(u['SPI'], 2)}) terminaria em {data_br(u['RD'])}, depois da Release "
                     f"Final; entrega planejada {data_br(entrega)}")
        else:
            kpi("Término estimado", data_br(u["RD"]), "CALCULADO",
                status="good" if u["RD"] <= entrega else "warning",
                nota=f"entrega planejada {data_br(entrega)}")
    if not vazio(u["SPI"]):
        st.markdown(f"**Leitura:** até a {u['sprint']}, a {rel} deveria ter entregue **{pct(u['PPC'])}** do escopo e "
                    f"entregou **{pct(u['APC'])}** ({num(u['RPC'])} de {num(u['PRP'])} SP)."
                    + (" Valores da sprint em andamento são parciais." if parcial else ""))
    base = u["prp_linha_de_base"]
    if not vazio(base) and base > 0 and u["PRP"] > base * 1.5:
        layout.alerta("warning", f"O escopo da {rel} cresceu de {num(base)} para {num(u['PRP'])} SP durante a release "
                                 "(pontos adicionados depois da linha de base).", "Agile EVM · PRP")
    elif not vazio(base) and base == 0 and u["PRP"] > 0:
        layout.alerta("warning", f"A linha de base da {rel} é 0 SP (nada estimado na planning da 1ª sprint); todo o "
                                 f"escopo atual ({num(u['PRP'])} SP) entrou depois.", "Agile EVM · PRP")

    # ── PV × EV × AC ──
    layout.secao("Planejado × Realizado × Valor Agregado", "Estamos entregando e gastando conforme o planejado?",
                 ["CALCULADO"])
    if not tem_bac:
        layout.indisponivel("Curvas de valor indisponíveis", sem_bac, "abas Custos e Planejamento da planilha.")
    else:
        longo = feitas.melt(id_vars=["sprint", "fim_da_sprint"], value_vars=["PV", "EV", "AC"], var_name="serie",
                            value_name="valor").dropna(subset=["valor"])
        longo["nome"] = longo["serie"].map(NOMES)
        dom = [NOMES[k] for k in ("PV", "EV", "AC") if NOMES[k] in set(longo["nome"])]
        traco = {NOMES["PV"]: [6, 4], NOMES["EV"]: [1, 0], NOMES["AC"]: [2, 2]}
        linhas = (alt.Chart(longo).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
                  .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                          y=alt.Y("valor:Q", title="R$ acumulado na release"),
                          color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[
                              {"PV — valor planejado": theme.SERIES[2], "EV — valor agregado": theme.SERIES[0],
                               "AC — custo real": theme.SERIES[1]}[x] for x in dom])),
                          strokeDash=alt.StrokeDash("nome:N", legend=None,
                                                    scale=alt.Scale(domain=dom, range=[traco[x] for x in dom])),
                          tooltip=[alt.Tooltip("sprint:O", title="Sprint"), alt.Tooltip("nome:N", title="Série"),
                                   alt.Tooltip("valor:Q", title="R$", format=",.2f")]))
        camadas = linhas + charts.regra_horizontal(u["BAC"], f"BAC {brl(u['BAC'])}", theme.INK["muted"])
        nota = "EV abaixo de PV = atraso. AC acima de EV = custou mais do que entregou."
        if not tem_ac:
            nota += f" AC não aparece: {motivo_ac}."
        charts.mostrar(camadas, f"PV, EV e AC acumulados — {rel}", "R$ acumulado · uma marca por sprint iniciada",
                       feitas[["sprint", "status", "PPC", "APC", "BAC", "PV", "EV", "AC", "origem_do_ac"]], nota=nota,
                       altura=300)

    e2, d2 = st.columns(2)
    with e2:
        prog = feitas.melt(id_vars=["sprint"], value_vars=["PPC", "APC"], var_name="serie", value_name="valor")
        prog["nome"] = prog["serie"].map({"PPC": "Planejado (PPC)", "APC": "Realizado (APC)"})
        dom = ["Planejado (PPC)", "Realizado (APC)"]
        g = (alt.Chart(prog).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
             .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                     y=alt.Y("valor:Q", title="% da release", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                     color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[theme.SERIES[2],
                                                                                           theme.SERIES[0]])),
                     strokeDash=alt.StrokeDash("nome:N", legend=None, scale=alt.Scale(domain=dom, range=[[6, 4], [1, 0]])),
                     tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Série"),
                              alt.Tooltip("valor:Q", title="%", format=".0%")]))
        charts.mostrar(g, "Progresso planejado × realizado", "% da release · PPC (prazo) e APC (escopo)",
                       feitas[["sprint", "PPC", "APC"]], altura=240)
    with d2:
        idx = feitas.melt(id_vars=["sprint"], value_vars=["SPI", "CPI"], var_name="indice", value_name="valor").dropna()
        if idx.empty:
            layout.indisponivel("SPI e CPI indisponíveis", "sem PV nem AC.")
        else:
            dom = [x for x in ("SPI", "CPI") if x in set(idx["indice"])]
            g = (alt.Chart(idx).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
                 .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])),
                         y=alt.Y("valor:Q", title="Índice", scale=alt.Scale(domain=[0, max(1.2, idx["valor"].max() + .1)])),
                         color=alt.Color("indice:N", title=None, scale=alt.Scale(domain=dom,
                                                                                 range=theme.SERIES[:len(dom)])),
                         strokeDash=alt.StrokeDash("indice:N", legend=None,
                                                   scale=alt.Scale(domain=dom, range=[[1, 0], [5, 3]][:len(dom)])),
                         tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("indice:N", title="Índice"),
                                  alt.Tooltip("valor:Q", title="Valor", format=".2f")]))
            nota = None if "CPI" in dom else "CPI não aparece: Actual Cost não foi fornecido."
            charts.mostrar(g + charts.regra_horizontal(1.0, "1,0 = no plano"), "Índices de desempenho",
                           "SPI (prazo) e CPI (custo) · 1,0 = no plano", idx, nota=nota, altura=240)

    # ── burndown ──
    layout.secao("Burndown da release", "Quanto falta entregar, e o escopo está crescendo?", ["ZENHUB"])
    b = feitas.assign(restante=feitas["PRP"] - feitas["RPC"], ideal=feitas["PRP"] * (1 - feitas["PPC"]))
    longo_b = b.melt(id_vars=["sprint"], value_vars=["restante", "ideal", "PRP"], var_name="serie", value_name="pontos")
    nomes_b = {"restante": "Restante (real)", "ideal": "Restante ideal", "PRP": "Escopo da release (PRP)"}
    longo_b["nome"] = longo_b["serie"].map(nomes_b)
    dom = list(nomes_b.values())
    g = (alt.Chart(longo_b).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True))
         .encode(x=alt.X("sprint:O", title="Sprint", sort=list(feitas["sprint"])), y=alt.Y("pontos:Q", title="Story Points"),
                 color=alt.Color("nome:N", title=None, scale=alt.Scale(domain=dom, range=[theme.SERIES[0],
                                                                                       theme.SERIES[2], theme.SERIES[1]])),
                 strokeDash=alt.StrokeDash("nome:N", legend=None, scale=alt.Scale(domain=dom,
                                                                                range=[[1, 0], [6, 4], [2, 2]])),
                 tooltip=[alt.Tooltip("sprint:O"), alt.Tooltip("nome:N", title="Série"),
                          alt.Tooltip("pontos:Q", title="SP", format=".0f")]))
    charts.mostrar(g, f"Burndown — {rel}", "Story Points · uma marca por sprint iniciada", b[["sprint", "PRP", "RPC",
                                                                                               "restante", "ideal"]],
                   nota="Quando o escopo (PRP) sobe, entrou trabalho novo na release — o restante sobe junto mesmo "
                        "que o time esteja entregando.", altura=280)

    with st.expander("Ver o Agile EVM completo da release"):
        st.dataframe(d.drop(columns=["L"], errors="ignore"), use_container_width=True, hide_index=True)
    if not ctx.evm_sumario.empty:
        with st.expander("Ver o sumário por release"):
            st.dataframe(ctx.evm_sumario, use_container_width=True, hide_index=True)
