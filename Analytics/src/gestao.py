"""Parâmetros do modelo de gestão (``planilhas/parametros.csv``).

Regras que o time decidiu e que o cálculo da velocity usa: critério de feito,
níveis pontuados, janela de planning, mínimo de sprints para a média e sprints
canceladas. Pontos, sprints e AgileEVM vêm do Zenhub (``src/velocity.py`` e
``src/evm.py``); custos, horas e riscos, da planilha (``src/planilhas.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

TIPOS_PONTUADOS_PADRAO = {"Feature", "Task", "Bug"}


# ───────────────────────── leitura ─────────────────────────

# Preenchido pelo app com config.PLANILHAS: {nome da aba: URL do CSV publicado}.
URLS: dict = {}
ORIGEM: dict = {}   # de onde cada aba foi lida, para o app mostrar na tela


def _csv(pasta: Path, nome: str) -> pd.DataFrame:
    """Lê a aba publicada da planilha do Google; sem URL ou em falha, o CSV local."""
    url = URLS.get(nome, "")
    if url:
        try:
            import io
            import requests
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str).fillna("")
            df.columns = [str(c).strip() for c in df.columns]
            ORIGEM[nome] = "planilha do Google"
            return df
        except Exception as erro:  # noqa: BLE001 - qualquer falha cai para o CSV local
            ORIGEM[nome] = f"CSV local (a planilha falhou: {erro.__class__.__name__})"
    else:
        ORIGEM[nome] = "CSV local"
    try:
        return pd.read_csv(Path(pasta) / f"{nome}.csv", dtype=str).fillna("")
    except (OSError, pd.errors.EmptyDataError):
        ORIGEM[nome] = "não encontrado"
        return pd.DataFrame()


def _numero(serie: pd.Series) -> pd.Series:
    """'1.234,5' ou '1234.5' -> float (a planilha publica no formato brasileiro)."""
    texto = serie.astype(str).str.strip()
    br = texto.str.contains(",")
    texto = texto.where(~br, texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(texto, errors="coerce")


def carregar_parametros(pasta: Path) -> dict:
    df = _csv(pasta, "parametros")
    brutos = dict(zip(df.get("parametro", []), df.get("valor", [])))

    tipos = str(brutos.get("niveis_pontuados", "")).strip()
    return {
        "criterio_feito": brutos.get("criterio_feito", "Done") or "Done",
        "tipos_pontuados": set(tipos.split(";")) if tipos else TIPOS_PONTUADOS_PADRAO,
        "tabela": df,
    }
