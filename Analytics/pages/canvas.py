"""Canvas Analytics — síntese do semestre em uma tela: produto, projeto, processo e gestão em R1 → R2 → R3."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import filters, layout, rastreio
from src.data import contexto
from src.metrics import canvas as cv
from src.metrics import fluxo, qrapids, resumo
from src.metrics.calculations import data_br

ESCOPO = {
    "release": None,
    "periodo": None,
    "repos": "Sonar, Zenhub, Q-Rapids, EVM (prazo), Fluxo e CI só desses repositórios "
             "(período fixo nas janelas R1, R2 e R3; custo, riscos e decisões são do time)",
    "branch": "coletas do Sonar desta branch (período fixo nas janelas R1, R2 e R3)",
}

BLOCOS_POR_EIXO = {
    "Produto": [("qrapids", "Qualidade (Q-Rapids)", "Qualidade (Q-Rapids)"),
                ("tecnica", "Qualidade técnica (Sonar)", "Qualidade técnica")],
    "Projeto": [("evm", "Custo e prazo (EVM)", "Agile EVM"),
                ("escopo", "Escopo", "Gestão ágil")],
    "Processo": [("fluxo", "Fluxo", "Fluxo"),
                 ("ci", "Integração contínua", "Integração contínua")],
}


def _cartao_bloco(id_bloco: str, titulo_padrao: str, onde_padrao: str,
                  linhas: pd.DataFrame, situacoes: dict[str, str]) -> None:
    sub = linhas[linhas["bloco"] == id_bloco] if not linhas.empty else pd.DataFrame()
    titulo = str(sub["titulo_bloco"].iloc[0]) if not sub.empty else titulo_padrao
    status = situacoes.get(id_bloco, "unavailable" if sub.empty else "neutral")
    cor = theme.cor_status(status)
    rotulo_st = theme.ROTULO_STATUS.get(status, "")
    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
            f"gap:.5rem;margin-bottom:.35rem'>"
            f"<span style='font-weight:700;font-size:.98rem;color:{theme.INK['primary']}'>"
            f"{html.escape(titulo)}</span>"
            f"<span style='font-size:.72rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:.04em;color:{cor}'>{html.escape(rotulo_st)}</span></div>",
            unsafe_allow_html=True,
        )
        if sub.empty:
            layout.alerta("unavailable", "Sem dado neste recorte")
        else:
            tab = pd.DataFrame({
                "Indicador": sub["indicador"],
                "R1": sub["R1"].fillna("—"),
                "R2": sub["R2"].fillna("—"),
                "R3": sub["R3"].fillna("—"),
                "Situação": sub["status"].map(lambda s: theme.ROTULO_STATUS.get(s, str(s))),
            })
            st.dataframe(tab, use_container_width=True, hide_index=True)
        onde = str(sub["onde"].iloc[0]) if not sub.empty and sub["onde"].iloc[0] else onde_padrao
        url = rastreio.pagina(onde)
        if url:
            st.markdown(
                f"<div style='font-size:.8rem;margin-top:.2rem'>"
                f"<a href='{html.escape(url)}' target='_self' style='color:{theme.IDV['primaria']}'>"
                f"ver em {html.escape(onde)}</a></div>",
                unsafe_allow_html=True,
            )


def pagina():
    ctx, f = layout.estado()
    ctx = contexto.com_recorte(ctx, f["repos"])
    filters.da_pagina(f, ESCOPO, tem_filtros=False)

    jan = cv.janelas(ctx.hoje)
    ind: dict[str, pd.DataFrame] = {}
    for r in cv.JANELAS:
        f_r = {**f, "periodo": jan[r], "release": r, "release_metas": "R3"}
        try:
            ind[r] = resumo.indicadores(ctx, f_r)
        except Exception:  # noqa: BLE001 — falha em uma fonte não derruba o Canvas
            ind[r] = pd.DataFrame()

    try:
        df_qr = cv.linhas_qrapids(qrapids.avaliar_releases(ctx, f)["indicadores"])
    except Exception:  # noqa: BLE001
        df_qr = cv.linhas_qrapids(pd.DataFrame())

    try:
        universo = filters.por_repo(ctx.zh_issues, f["repos"])
        trans = (ctx.zh_snap or {}).get("transferencias_pipeline")
        itens_fl = fluxo.itens_de_fluxo(universo, transferencias=trans)
        df_fl = cv.linhas_fluxo(itens_fl, jan, coletado=trans is not None)
    except Exception:  # noqa: BLE001
        df_fl = cv.linhas_fluxo(pd.DataFrame(), jan, coletado=False)

    df_res = cv.montar(ind)
    linhas = pd.concat([df_qr, df_res, df_fl], ignore_index=True)
    situacoes = cv.situacao_blocos(linhas)

    layout.titulo_pagina(
        "Canvas Analytics",
        "Síntese do semestre: produto, projeto e processo em R1 → R2 → R3, contra a meta da R3.",
        ["SONAR", "ZENHUB", "PLANILHA", "GITHUB"],
    )
    if ctx.repos_recorte:
        layout.alerta(
            "neutral",
            "Filtro de repositórios ativo (" + ", ".join(ctx.repos_recorte) + "): período fixo em R1, R2 e R3. "
            "Orçamento, custo, CPI, riscos e decisões são do time inteiro.",
        )

    status_geral, frase = resumo.situacao_geral(ind["R3"])
    entrega_r3 = pd.Timestamp(config.RELEASES["R3"])
    dias = (entrega_r3 - ctx.hoje).days
    prazo = "hoje" if dias == 0 else (f"faltam {dias} dia(s)" if dias > 0 else f"entregue há {-dias} dia(s)")
    parcial = f" · R3 parcial até {ctx.hoje:%d/%m}" if ctx.hoje < entrega_r3 else ""
    cor = theme.cor_status(status_geral)
    st.markdown(
        f"<div class='msg-status-geral' style='--kpi-cor:{cor}'>"
        f"<div class='rotulo'>Situação do semestre (R3)</div>"
        f"<div class='valor' style='color:{cor}'>{theme.ROTULO_STATUS[status_geral]}</div>"
        f"<div style='font-size:.85rem;color:{theme.INK['secondary']}'>{html.escape(frase)}</div>"
        f"<div style='font-size:.8rem;color:{theme.INK['muted']};margin-top:.4rem'>"
        f"R3: entrega {data_br(entrega_r3)} ({prazo}){html.escape(parcial)} · metas da R3</div></div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for col, eixo in zip(cols, ("Produto", "Projeto", "Processo")):
        with col:
            layout.secao(eixo)
            for id_bloco, titulo_padrao, onde_padrao in BLOCOS_POR_EIXO[eixo]:
                _cartao_bloco(id_bloco, titulo_padrao, onde_padrao, linhas, situacoes)

    layout.secao("Gestão")
    g_cols = st.columns(3)
    with g_cols[0]:
        _cartao_bloco("riscos", "Riscos", "Riscos", linhas, situacoes)
    with g_cols[1]:
        _cartao_bloco("decisoes", "Decisões gerenciais", "Decisões", linhas, situacoes)
    with g_cols[2]:
        with st.container(border=True):
            cor_ia = theme.cor_status("neutral")
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
                f"gap:.5rem;margin-bottom:.35rem'>"
                f"<span style='font-weight:700;font-size:.98rem;color:{theme.INK['primary']}'>Uso de IA</span>"
                f"<span style='font-size:.72rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:.04em;color:{cor_ia}'>{theme.ROTULO_STATUS['neutral']}</span></div>",
                unsafe_allow_html=True,
            )
            layout.alerta("neutral", "Aguardando a página Uso de IA (TASK38.04, #364 e #365).")

    layout.secao("Síntese do semestre", "Principais pontos de atenção na R3 e espaço para a leitura crítica do time.")
    at = resumo.pontos_de_atencao(ind["R3"]).head(3)
    if at.empty:
        layout.alerta("good", "Nenhum indicador crítico, em atenção ou sem dado na R3.")
    else:
        for i in at.itertuples():
            valor = f": {i.valor}" if i.valor else ""
            layout.alerta(i.status, f"{i.indicador}{valor} — {i.leitura}", f"ver em {i.onde}",
                          link=(i.indicador, rastreio.pagina(i.onde)))
    st.caption("A síntese textual do semestre (o que melhorou, o que piorou e o que aprendemos) é escrita pelo time.")
