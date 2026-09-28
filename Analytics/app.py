"""MeasureSoftGram — Dashboard de Gestão de Projeto (EPS 2026.2).

Entrada do Streamlit. Aqui só acontece o que é comum a todas as páginas:
tema (IDV da documentação), carga das fontes, filtros globais, cabeçalho e
navegação. Cada página está em ``pages/`` e só desenha; coleta e tratamento
ficam em ``src/data``, cálculos em ``src/metrics`` e peças visuais em
``src/components``.

Rodar:
    pip install -r requirements.txt
    streamlit run app.py

Publicado no GitHub Pages via stlite (Streamlit no navegador): ver stlite/build.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# No navegador (stlite, GitHub Pages) o diretório do app nem sempre está no path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="MeasureSoftGram — Dashboard de Gestão de Projeto", layout="wide",
                   initial_sidebar_state="expanded")

from pages import evm, metodologia, planilha, processo, sonar, visao_executiva, zenhub  # noqa: E402
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
        st.Page(evm.pagina, title="Agile EVM", url_path="agile-evm", icon=":material/stacked_line_chart:"),
    ],
    "Por fonte": [
        st.Page(sonar.pagina, title="Qualidade técnica (Sonar)", url_path="sonar", icon=":material/code:"),
        st.Page(zenhub.pagina, title="Gestão ágil (ZenHub)", url_path="zenhub", icon=":material/view_kanban:"),
        st.Page(planilha.pagina, title="Custos e riscos (Planilha)", url_path="planilha",
                icon=":material/table_chart:"),
        st.Page(processo.pagina, title="Integração contínua (GitHub)", url_path="processo",
                icon=":material/sync:"),
    ],
    "Referência": [
        st.Page(metodologia.pagina, title="Metodologia e Fontes", url_path="metodologia",
                icon=":material/info:"),
    ],
})
layout.cabecalho(ctx, filtros)
navegacao.run()
