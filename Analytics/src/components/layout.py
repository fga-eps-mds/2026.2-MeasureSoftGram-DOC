"""Blocos de página: cabeçalho, seção com pergunta gerencial, etiqueta de fonte, dado indisponível."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import theme
from src.metrics.calculations import data_br


def etiqueta(fonte: str) -> str:
    """HTML da etiqueta de fonte (SONAR, ZENHUB, PLANILHA, GITHUB, CALCULADO)."""
    nome, cor = theme.FONTES.get(fonte, (fonte, theme.INK["muted"]))
    return f"<span class='msg-fonte' style='background:{cor}' title='Fonte: {html.escape(nome)}'>{fonte}</span>"


def etiquetas(fontes) -> str:
    return " ".join(etiqueta(f) for f in (fontes or []))


def aplicar_tema() -> None:
    st.markdown(theme.CSS, unsafe_allow_html=True)


def cabecalho(ctx, filtros: dict) -> None:
    """Título, período analisado e última atualização de cada fonte."""
    ini, fim = filtros.get("periodo", (None, None))
    ultimas = []
    for nome in ("SONAR", "ZENHUB", "PLANILHA", "GITHUB"):
        datas = [f.ultima_atualizacao for f in ctx.fonte(nome) if f.ultima_atualizacao is not None]
        rotulo = theme.FONTES[nome][0]
        ultimas.append(f"{rotulo} <b>{data_br(max(datas), True) if datas else 'sem dados'}</b>")
    st.markdown(
        f"""<div class='msg-topo'>
  <div class='msg-marca'>MeasureSoftGram</div>
  <div class='msg-titulo'>Dashboard de Gestão de Projeto</div>
  <div class='msg-meta'>
    <span>Período analisado <b>{data_br(ini)} a {data_br(fim)}</b></span>
    <span>Release <b>{html.escape(str(filtros.get('release_rotulo', '—')))}</b></span>
    <span>Situação em <b>{data_br(ctx.hoje)}</b></span>
  </div>
  <div class='msg-meta' style='margin-top:.25rem'>Última atualização: {' · '.join(ultimas)}</div>
</div>""", unsafe_allow_html=True)


def titulo_pagina(titulo: str, subtitulo: str, fontes=()) -> None:
    st.markdown(f"## {titulo} {etiquetas(fontes)}", unsafe_allow_html=True)
    st.caption(subtitulo)


def secao(titulo: str, pergunta: str | None = None, fontes=()) -> None:
    """Título do bloco + a pergunta gerencial que ele responde."""
    p = f"<div class='msg-pergunta'>{html.escape(pergunta)}</div>" if pergunta else ""
    st.markdown(f"<div class='msg-secao'><h3>{html.escape(titulo)} {etiquetas(fontes)}</h3>{p}</div>",
                unsafe_allow_html=True)


def indisponivel(titulo: str, motivo: str, necessario: str | None = None) -> None:
    """Dado ausente: diz que não existe, por quê e o que seria preciso para calcular."""
    extra = f"<br><b>Para calcular:</b> {html.escape(necessario)}" if necessario else ""
    st.markdown(f"<div class='msg-ausente'><b>{html.escape(titulo)}</b> — {html.escape(motivo)}{extra}</div>",
                unsafe_allow_html=True)


def alerta(status: str, texto: str, onde: str = "") -> None:
    cor = theme.cor_status(status)
    rot = theme.ROTULO_STATUS.get(status, "")
    o = f" <span class='onde'>· {html.escape(onde)}</span>" if onde else ""
    st.markdown(f"<div class='msg-alerta' style='--kpi-cor:{cor}'><span class='st' style='color:{cor}'>{rot}</span>"
                f"{html.escape(texto)}{o}</div>", unsafe_allow_html=True)


def metodologia(linhas: list[tuple[str, str, str]], titulo: str = "Metodologia desta página") -> None:
    """Expansor com indicador, fonte e fórmula de cada número da página."""
    with st.expander(titulo):
        md = "| Indicador | Fonte | Definição / fórmula |\n|---|---|---|\n"
        md += "\n".join(f"| {a} | {b} | {c} |" for a, b, c in linhas)
        st.markdown(md)


def tabela(df: pd.DataFrame, rotulo: str = "Ver os dados em tabela", **kw) -> None:
    with st.expander(rotulo):
        if df is None or df.empty:
            st.caption("Sem linhas.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, **kw)


def estado():
    """(contexto, filtros) montados pelo app.py nesta execução."""
    return st.session_state["ctx"], st.session_state["filtros"]
