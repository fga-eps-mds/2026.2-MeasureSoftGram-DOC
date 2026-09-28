"""Cálculos transversais: variação entre coletas, status frente à meta e formatação pt-BR.

Nada aqui lê arquivo: recebe números e devolve números ou texto.
"""

from __future__ import annotations

import math

import pandas as pd

import config


def vazio(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (not isinstance(v, str) and pd.isna(v))


# ───────────────────────── formatação ─────────────────────────

def num(v, casas: int = 0) -> str:
    if vazio(v):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v, casas: int = 2) -> str:
    return "—" if vazio(v) else "R$ " + num(v, casas)


def pct(v, casas: int = 0) -> str:
    """0,42 -> '42%'."""
    return "—" if vazio(v) else num(v * 100, casas) + "%"


def data_br(v, com_hora: bool = False) -> str:
    if vazio(v):
        return "—"
    t = pd.Timestamp(v)
    return t.strftime("%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y")


# ───────────────────────── variação ─────────────────────────

def variacao(atual, anterior, unidade: str = "", maior_melhor: bool | None = None) -> dict:
    """Atual → anterior → variação. Em % a variação é em pontos percentuais (p.p.).

    ``sentido``: ``good`` quando a variação vai na direção boa, ``critical`` na
    ruim, ``neutral`` sem direção definida ou sem variação.
    """
    if vazio(atual) or vazio(anterior):
        return {"delta": None, "texto": "sem coleta anterior", "sentido": "neutral"}
    delta = float(atual) - float(anterior)
    if abs(delta) < 1e-9:
        return {"delta": 0.0, "texto": "sem variação", "sentido": "neutral"}
    sinal = "+" if delta > 0 else "−"
    if unidade == "%":
        texto = f"{sinal}{num(abs(delta), 1)} p.p."
    elif unidade == "min":
        texto = f"{sinal}{num(abs(delta) / 60, 1)} h"
    else:
        texto = f"{sinal}{num(abs(delta), 0 if float(delta).is_integer() else 1)}"
    if maior_melhor is None:
        sentido = "neutral"
    else:
        sentido = "good" if (delta > 0) == maior_melhor else "critical"
    return {"delta": delta, "texto": texto, "sentido": sentido}


# ───────────────────────── status ─────────────────────────

def status_meta(metrica: str, valor, release: str, maior_melhor: bool | None) -> str:
    """Status do valor frente à meta da release em ``config.METAS`` (neutral sem meta)."""
    meta = config.METAS.get(metrica, {}).get(release)
    if meta is None or vazio(valor) or maior_melhor is None:
        return "neutral"
    if maior_melhor:
        return "good" if valor >= meta else ("warning" if valor >= meta * 0.9 else "critical")
    return "good" if valor <= meta else ("warning" if valor <= meta * 1.5 else "critical")


def status_indice(valor) -> str:
    """SPI/CPI: ≥ meta conforme; ≥ 0,80 atenção; abaixo, crítico."""
    if vazio(valor):
        return "unavailable"
    if valor >= config.META_INDICE_EVM:
        return "good"
    return "warning" if valor >= 0.80 else "critical"


def status_taxa(valor, meta: float, atencao: float) -> str:
    if vazio(valor):
        return "unavailable"
    return "good" if valor >= meta else ("warning" if valor >= atencao else "critical")


def release_atual(hoje: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    """Primeira release cuja entrega ainda não passou (a última depois do fim do semestre)."""
    entregas = [(nome, pd.Timestamp(d)) for nome, d in config.RELEASES.items()]
    for nome, entrega in entregas:
        if hoje <= entrega:
            return nome, entrega
    return entregas[-1]
