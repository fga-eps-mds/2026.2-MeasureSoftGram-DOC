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


def alerta(status: str, texto: str, onde: str = "", link: tuple[str, str] | None = None) -> None:
    """``link`` = (trecho do texto, url): esse trecho vira link embutido."""
    cor = theme.cor_status(status)
    rot = theme.ROTULO_STATUS.get(status, "")
    o = f" <span class='onde'>· {html.escape(onde)}</span>" if onde else ""
    corpo = html.escape(texto)
    if link and link[1] and link[0] in texto:
        trecho = html.escape(link[0])
        corpo = corpo.replace(trecho, f"<a href='{html.escape(link[1])}' target='_blank' rel='noopener'>{trecho}</a>", 1)
    st.markdown(f"<div class='msg-alerta' style='--kpi-cor:{cor}'><span class='st' style='color:{cor}'>{rot}</span>"
                f"{corpo}{o}</div>", unsafe_allow_html=True)


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


def tabela_html(df: pd.DataFrame, colunas: dict[str, str], links: tuple[str, ...] = (),
                numericas: tuple[str, ...] = (), altura: int | None = 420) -> None:
    """Tabela em HTML quando uma célula precisa de vários links (ex.: as issues de um épico).

    ``links``: colunas com listas de (rótulo, url), cada item vira um link para a issue.
    Número ausente aparece como "—", nunca como None.
    """
    if df is None or df.empty:
        st.caption("Sem linhas.")
        return

    def celula(col, v):
        if col in links:
            itens = v if isinstance(v, (list, tuple)) else []
            return ", ".join(f"<a href='{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(r)}</a>"
                             if u else html.escape(r) for r, u in itens) or "—"
        if col in numericas:
            return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{float(v):,.0f}".replace(",", ".")
        return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else html.escape(str(v))

    cab = "".join(f"<th class='{'num' if c in numericas else ''}'>{html.escape(t)}</th>" for c, t in colunas.items())
    corpo = "".join("<tr>" + "".join(f"<td class='{'num' if c in numericas else ''}'>{celula(c, r[c])}</td>"
                                     for c in colunas) + "</tr>" for _, r in df.iterrows())
    estilo = f" style='max-height:{altura}px'" if altura else ""
    st.markdown(f"<div class='msg-tabela'{estilo}><table><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody>"
                "</table></div>", unsafe_allow_html=True)


# ───────── links embutidos no próprio texto da célula ─────────
# A tabela do Streamlit só põe um link por célula, com texto tirado da URL por regex. Para o
# texto ser o nome da issue/épico, ele vai no fragmento da URL (…/issues/42#DOC#42): o GitHub
# ignora o fragmento e a coluna exibe só o que vem depois do primeiro "#".
REGEX_TEXTO_LINK = r"#(.+)$"


def link_celula(url, texto) -> str | None:
    """Valor de célula que é, ao mesmo tempo, o texto e o link. Sem URL, fica só o texto."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    texto = str(texto)
    return f"{url}#{texto}" if isinstance(url, str) and url.startswith("http") else texto


def coluna_link(rotulo: str, **kw):
    """Coluna cujo texto é clicável (use com valores de :func:`link_celula`)."""
    return st.column_config.LinkColumn(rotulo, display_text=REGEX_TEXTO_LINK, **kw)


def texto_de_link(valor) -> str:
    """Desfaz :func:`link_celula` (para CSV): devolve só o texto."""
    v = "" if valor is None else str(valor)
    return v.split("#", 1)[1] if v.startswith("http") and "#" in v else v
