"""Decisões — decisões baseadas em dados registradas pelo time (fonte: planilha, aba Decisões).

Caminhos citados na evidência (docs/..., Analytics/...) viram link para o arquivo no GitHub.
"""

from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

import config
from src.components import layout, rastreio
from src.components.kpi import kpi
from src.metrics.calculations import num

REPO = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-docs-eps/blob/main/"
CAMINHO = re.compile(r"((?:docs|Analytics)/[\w./-]+\.\w+)")


def _evidencia(texto) -> str:
    """Texto da evidência com cada caminho de arquivo virando link."""
    t = html.escape("" if texto is None or (isinstance(texto, float) and pd.isna(texto)) else str(texto))
    return CAMINHO.sub(lambda m: f"<a href='{REPO}{m.group(1)}' target='_blank' rel='noopener'>{m.group(1)}</a>", t)


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Decisões", "Decisões de gestão tomadas a partir dos dados, com evidência e critério de "
                         "sucesso.", ["PLANILHA"])
    metas = config.METAS_DECISOES
    layout.menus([
        ("Decisão baseada em dados", "escolha do time justificada por um número do painel ou da planilha",
         "uma linha na aba Decisões: contexto e dado → decisão → evidência → critério de sucesso → resultado",
         [rastreio.aba("decisoes")]),
        ("Com resultado medido", "decisão cujo critério de sucesso já foi conferido", "coluna Resultado preenchida",
         [rastreio.aba("decisoes")]),
    ], [(f"Meta de decisões na {k}", f"≥ {v}", "config.py · METAS_DECISOES", rastreio.codigo())
        for k, v in metas.items()], fontes=["PLANILHA"])
    dec = ctx.decisoes
    if dec is None or dec.empty:
        layout.indisponivel("Nenhuma decisão registrada", "a aba Decisões está vazia ou não foi lida.")
        rastreio.aba_original("decisoes")
        return
    meta = metas.get(f["release_metas"])
    medidas = int((dec.get("resultado", pd.Series(dtype=str)).astype(str).str.strip().replace("nan", "") != "").sum())
    layout.secao("Resumo", "Quantas decisões foram registradas e medidas?", ["PLANILHA"])
    k = st.columns(3)
    with k[0]:
        kpi("Decisões registradas", num(len(dec)), "PLANILHA",
            status=None if not meta else ("good" if len(dec) >= meta else "warning"),
            nota=f"meta da {f['release_metas']}: ≥ {meta}" if meta else
            "metas: " + ", ".join(f"≥ {v} na {k}" for k, v in metas.items()), origem=[rastreio.aba("decisoes")])
    with k[1]:
        kpi("Com resultado medido", num(medidas), "PLANILHA", nota=f"de {len(dec)}")
    with k[2]:
        kpi("Vigentes", num(int((dec.get("status", pd.Series(dtype=str)) == "Vigente").sum())), "PLANILHA")

    layout.secao("Dado bruto", "O que foi decidido, com base em quê, e como saber se deu certo?", ["PLANILHA"])
    t = dec.copy()
    t["evidencia_html"] = t.get("evidencia", pd.Series([""] * len(t))).map(_evidencia)
    cols = {"data": "Data", "sprint": "Sprint", "tipo": "Tipo", "indicador": "Indicador",
            "contexto_e_dado": "Contexto e dado", "decisao": "Decisão", "evidencia_html": "Evidência",
            "criterio_de_sucesso": "Critério de sucesso", "resultado": "Resultado", "status": "Status"}
    cab = "".join(f"<th>{html.escape(v)}</th>" for c, v in cols.items() if c in t)
    corpo = "".join("<tr>" + "".join(
        f"<td>{r[c] if c == 'evidencia_html' else html.escape('' if pd.isna(r[c]) else str(r[c])) or '—'}</td>"
        for c in cols if c in t) + "</tr>" for _, r in t.iterrows())
    st.markdown(f"<div class='msg-tabela'><table><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>",
                unsafe_allow_html=True)
    st.caption("Caminhos de arquivo na evidência abrem o arquivo no GitHub.")
    rastreio.aba_original("decisoes")
