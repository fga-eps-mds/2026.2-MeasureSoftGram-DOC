"""Cartão de KPI: rótulo, valor, variação (atual → anterior), status em texto e fonte."""

from __future__ import annotations

import html

import streamlit as st

from src import theme
from src.components.layout import _alvo, etiqueta


def kpi(rotulo: str, valor: str | None, fonte: str, *, status: str | None = None, delta: dict | None = None,
        nota: str | None = None, ajuda: str | None = None, origem: list | None = None) -> None:
    """``valor=None`` = indisponível (mostra 'Indisponível' e a ``nota`` explica o motivo).

    ``delta``: saída de ``calculations.variacao`` — o texto ganha a cor do sentido
    (bom/ruim) e um rótulo, nunca só a cor.
    """
    indisp = valor is None
    st_ = "unavailable" if indisp else (status or "neutral")
    cor = theme.cor_status(st_)
    rot_status = theme.ROTULO_STATUS.get(st_, "") if (status or indisp) else ""
    d = ""
    if delta and not indisp:
        cor_d = {"good": theme.STATUS["good"], "critical": theme.STATUS["critical"]}.get(delta["sentido"],
                                                                                          theme.INK["secondary"])
        palavra = {"good": " (melhora)", "critical": " (piora)"}.get(delta["sentido"], "")
        d = (f"<div class='msg-kpi-delta'><span style='color:{cor_d};font-weight:600'>{html.escape(delta['texto'])}"
             f"</span>{palavra} vs. coleta anterior</div>")
    n = f"<div class='msg-kpi-nota'>{html.escape(nota)}</div>" if nota else ""
    if origem:   # [(texto, url)] — de onde vem o dado, com link embutido
        itens = " · ".join(f"<a href='{html.escape(u)}' {_alvo(u)}>{html.escape(t)}</a>" if u
                           else html.escape(t) for t, u in origem)
        n += f"<div class='msg-kpi-nota'>Fonte: {itens}</div>"
    t = f" title='{html.escape(ajuda)}'" if ajuda else ""
    st.markdown(f"""<div class='msg-kpi' style='--kpi-cor:{cor}'{t}>
  <div class='msg-kpi-topo'><span class='msg-kpi-rotulo'>{html.escape(rotulo)}</span>{etiqueta(fonte)}</div>
  <div class='msg-kpi-valor{" indisponivel" if indisp else ""}'>{"Indisponível" if indisp else html.escape(str(valor))}</div>
  {d}
  {f"<div class='msg-kpi-status' style='color:{cor}'>{rot_status}</div>" if rot_status else ""}
  {n}
</div>""", unsafe_allow_html=True)


def linha(cartoes: list[dict], colunas: int | None = None) -> None:
    """Uma linha de KPIs (cada item = kwargs de ``kpi``)."""
    if not cartoes:
        return
    cols = st.columns(colunas or len(cartoes))
    for i, c in enumerate(cartoes):
        with cols[i % len(cols)]:
            kpi(**c)
