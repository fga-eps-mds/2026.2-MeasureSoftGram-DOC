"""Tabelas de detalhe com formatação pt-BR."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def detalhe(df: pd.DataFrame, colunas: dict[str, str], config: dict | None = None, busca: str | None = None,
            chave: str | None = None) -> None:
    """Mostra ``df`` com as colunas renomeadas (``{coluna: título}``); ``busca`` adiciona filtro de texto."""
    if df is None or df.empty:
        st.caption("Sem linhas para os filtros selecionados.")
        return
    t = df[[c for c in colunas if c in df]].rename(columns=colunas)
    if busca:
        termo = st.text_input(busca, key=chave, placeholder="digite para filtrar")
        if termo:
            t = t[t.astype(str).apply(lambda s: s.str.contains(termo, case=False, regex=False)).any(axis=1)]
    st.dataframe(t, use_container_width=True, hide_index=True, column_config=config or {})
