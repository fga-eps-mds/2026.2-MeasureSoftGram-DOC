"""Visão Executiva — situação do projeto em uma tela, com link para a página que explica cada número."""

from __future__ import annotations

import html

import streamlit as st

from src import theme
from src.data import contexto
from src.components import layout, rastreio
from src.components.kpi import kpi
from src.metrics import resumo
from src.metrics.calculations import data_br, release_atual

# (tema, prefixo do indicador em resumo.indicadores, fonte)
CARTOES = [
    ("Prazo", "SPI da", "CALCULADO"), ("Custo", "CPI (custo)", "CALCULADO"),
    ("Entrega", "Taxa de conclusão das sprints", "ZENHUB"), ("Qualidade", "Cobertura", "SONAR"),
    ("Riscos", "Riscos elevados", "PLANILHA"), ("Integração contínua", "Sucesso da CI", "GITHUB"),
]


def pagina():
    ctx, f = layout.estado()
    ctx = contexto.com_recorte(ctx, f["repos"])
    ind = resumo.indicadores(ctx, f)
    status, frase = resumo.situacao_geral(ind)
    rel_nome, entrega = release_atual(ctx.hoje)
    dias = (entrega - ctx.hoje).days
    cal = ctx.calendario
    atual = cal[(cal["inicio"] <= ctx.hoje) & (cal["fim"] >= ctx.hoje)] if cal is not None and not cal.empty else None

    layout.titulo_pagina("Visão Executiva", "O projeto em uma tela: cada cartão leva à página que explica o número.",
                         ["SONAR", "ZENHUB", "PLANILHA", "GITHUB"])
    if ctx.repos_recorte:
        layout.alerta("neutral", "Filtro de repositórios ativo (" + ", ".join(ctx.repos_recorte) + "): pontos, sprints, "
                      "velocity e SPI são só desses repositórios. Orçamento, horas, custo e CPI são do time inteiro "
                      "(não dependem de repositório).")
    layout.menus([
        ("Status geral", "a pior situação entre os indicadores com meta", "Crítico se algum indicador é crítico; "
         "Atenção se algum está em atenção; senão Conforme", []),
        ("Cada cartão", "o indicador principal de um tema", "detalhe, fórmula e dado bruto na página indicada no "
         "cartão", []),
    ], [("Metas usadas", f["release_metas"], "release da barra lateral", None),
        ("Situação calculada em", data_br(ctx.hoje), "data de hoje", None)])

    cor = theme.cor_status(status)
    sprint = f"{atual.iloc[0]['sprint']} ({data_br(atual.iloc[0]['inicio'])} a {data_br(atual.iloc[0]['fim'])})" \
        if atual is not None and not atual.empty else "nenhuma sprint cobre hoje"
    prazo = "hoje" if dias == 0 else (f"faltam {dias} dia(s)" if dias > 0 else f"entregue há {-dias} dia(s)")
    st.markdown(f"<div class='msg-status-geral' style='--kpi-cor:{cor}'><div class='rotulo'>Status geral do projeto"
                f"</div><div class='valor' style='color:{cor}'>{theme.ROTULO_STATUS[status]}</div>"
                f"<div style='font-size:.85rem;color:{theme.INK['secondary']}'>{html.escape(frase)}</div>"
                f"<div style='font-size:.8rem;color:{theme.INK['muted']};margin-top:.4rem'>{rel_nome}: entrega "
                f"{data_br(entrega)} ({prazo}) · sprint atual: {html.escape(sprint)} · metas da "
                f"{f['release_metas']}</div></div>", unsafe_allow_html=True)

    layout.secao("Resumo por tema", "Como estamos em prazo, custo, entrega, qualidade, riscos e CI?")
    for n, (tema, prefixo, fonte) in enumerate(CARTOES):
        if n % 3 == 0:
            cols = st.columns(3)   # uma linha por vez: os cartões de cada linha ficam com a mesma altura
        m = ind[ind["indicador"].str.startswith(prefixo)]
        with cols[n % 3]:
            if m.empty:
                kpi(tema, None, fonte, nota="Indisponível: indicador não calculado (fonte não lida).")
                continue
            i = m.iloc[0]
            kpi(f"{tema} · {i['indicador']}", i["valor"], fonte, status=i["status"],
                nota=("Indisponível: " if i["valor"] is None else "") + str(i["leitura"]),
                origem=[(f"página {i['onde']}", rastreio.pagina(i["onde"]))])

    layout.secao("Pontos de atenção", "O que precisa de ação, em ordem de gravidade?")
    at = resumo.pontos_de_atencao(ind)
    if at.empty:
        layout.alerta("good", "Nenhum indicador crítico, em atenção ou sem dado.")
    else:
        for i in at.itertuples():
            valor = f": {i.valor}" if i.valor else ""
            layout.alerta(i.status, f"{i.indicador}{valor} — {i.leitura}", f"ver em {i.onde}",
                          link=(i.indicador, rastreio.pagina(i.onde)))
