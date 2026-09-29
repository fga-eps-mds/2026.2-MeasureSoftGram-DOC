"""MeasureSoftGram — Dashboard de Gestão de Projeto (EPS 2026.2).

Entrada do Streamlit. Aqui só acontece o que é comum a todas as páginas:
tema (IDV da documentação), carga das fontes, filtros globais, cabeçalho e
navegação. Cada página está em ``pages/`` e só desenha; coleta e tratamento
ficam em ``src/data``, cálculos em ``src/metrics`` e peças visuais em
``src/components``.

Rodar:
    pip install -r requirements.txt
    streamlit run app.py

Publicado no Streamlit Community Cloud: https://20262-measuresoftgram-doc.streamlit.app/
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante os imports de pages/ e src/ quando o app é iniciado de outra pasta (ex.: Streamlit Cloud).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="MeasureSoftGram — Dashboard de Gestão de Projeto", layout="wide",
                   initial_sidebar_state="expanded")

from pages import custos, decisoes, evm, metodologia, processo, riscos, sonar, visao_executiva, zenhub  # noqa: E402
from src.components import filters, layout  # noqa: E402
from src.data import contexto  # noqa: E402

layout.aplicar_tema()
ctx = contexto.carregar()
filtros = filters.barra_lateral(ctx)
st.session_state["ctx"], st.session_state["filtros"] = ctx, filtros

navegacao = st.navigation({
    "Gestão": [
        st.Page(visao_executiva.pagina, title="Visão Executiva", url_path="visao-executiva",
                icon=":material/dashboard:", default=True),
        st.Page(zenhub.pagina, title="Gestão ágil", url_path="zenhub", icon=":material/view_kanban:"),
        st.Page(evm.pagina, title="Agile EVM", url_path="agile-evm", icon=":material/stacked_line_chart:"),
        st.Page(custos.pagina, title="Custos", url_path="custos", icon=":material/payments:"),
        st.Page(riscos.pagina, title="Riscos", url_path="riscos", icon=":material/warning:"),
        st.Page(decisoes.pagina, title="Decisões", url_path="decisoes", icon=":material/gavel:"),
    ],
    "Qualidade e processo": [
        st.Page(sonar.pagina, title="Qualidade técnica", url_path="sonar", icon=":material/code:"),
        st.Page(processo.pagina, title="Integração contínua", url_path="processo", icon=":material/sync:"),
    ],
    "Referência": [
        st.Page(metodologia.pagina, title="Metodologia e Fontes", url_path="metodologia",
                icon=":material/info:"),
    ],
})
layout.cabecalho(ctx, filtros)
navegacao.run()
