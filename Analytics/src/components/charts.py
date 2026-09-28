"""Gráficos Altair com a identidade visual da documentação.

Cada gráfico: título (pergunta ou objeto), subtítulo com unidade e período,
legenda quando há mais de uma série, tooltip e, logo abaixo, a tabela dos dados.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components.layout import tabela

alt.data_transformers.disable_max_rows()


def finalizar(chart, titulo: str | None = None, subtitulo: str | None = None):
    if titulo:
        chart = chart.properties(title=alt.TitleParams(titulo, subtitle=subtitulo or "", anchor="start",
                                                       fontSize=13, fontWeight=600, color=theme.INK["primary"],
                                                       subtitleColor=theme.INK["muted"], subtitleFontSize=11,
                                                       offset=10))
    return (chart
            .configure(font="Roboto")
            .configure_view(strokeWidth=0)
            .configure_axis(grid=True, gridColor=theme.INK["grid"], domainColor=theme.INK["axis"],
                            tickColor=theme.INK["axis"], labelColor=theme.INK["muted"],
                            titleColor=theme.INK["secondary"], labelFontSize=11, titleFontSize=11,
                            titleFontWeight=500)
            .configure_legend(labelColor=theme.INK["secondary"], titleColor=theme.INK["secondary"],
                              labelFontSize=11, titleFontSize=11, orient="top", symbolStrokeWidth=2))


def mostrar(chart, titulo: str, subtitulo: str, dados: pd.DataFrame | None = None, nota: str | None = None,
            altura: int = 300) -> None:
    st.altair_chart(finalizar(chart.properties(height=altura), titulo, subtitulo), use_container_width=True, theme=None)
    if nota:
        st.caption(nota)
    if dados is not None:
        tabela(dados)


def regra_horizontal(valor: float, texto: str, cor: str = theme.INK["muted"], tracejado=(6, 4)):
    base = pd.DataFrame({"y": [valor], "t": [texto]})
    return (alt.Chart(base).mark_rule(strokeDash=list(tracejado), color=cor, strokeWidth=1.5).encode(y="y:Q")
            + alt.Chart(base).mark_text(align="left", dx=4, dy=-7, fontSize=11, color=cor)
            .encode(y="y:Q", text="t:N", x=alt.value(0)))


def marcos_release(inicio, fim):
    """Linhas verticais pontilhadas nas datas de entrega das releases que caem no período."""
    d = pd.DataFrame({"data": pd.to_datetime(list(config.RELEASES.values())), "release": list(config.RELEASES)})
    if inicio is not None and fim is not None:
        d = d[(d["data"] >= pd.Timestamp(inicio) - pd.Timedelta(days=2))
              & (d["data"] <= pd.Timestamp(fim) + pd.Timedelta(days=7))]
    regra = alt.Chart(d).mark_rule(strokeDash=[2, 3], color=theme.INK["muted"], strokeWidth=1).encode(
        x="data:T", tooltip=[alt.Tooltip("release:N", title="Entrega"), alt.Tooltip("data:T", format="%d/%m/%Y")])
    texto = (alt.Chart(d).mark_text(align="left", dx=3, y=4, baseline="top", fontSize=10, color=theme.INK["muted"])
             .encode(x="data:T", text="release:N"))
    return regra + texto


def escala_status(dominio: list[str], status: list[str]) -> alt.Scale:
    return alt.Scale(domain=dominio, range=[theme.cor_status(s) for s in status])


def escala_series(dominio: list[str]) -> alt.Scale:
    return alt.Scale(domain=dominio, range=theme.SERIES[:len(dominio)])
