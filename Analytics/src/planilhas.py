"""Leitura das duas planilhas de gestão do time (Google Sheets publicadas em CSV).

Planilha "Custos e AgileEVM"  -> abas Custos, Planejamento, Horas, Sumário EVM,
                                 EVM - Valor Agregado, EVM - Velocity
Planilha "Riscos e Decisões"  -> abas Riscos, Monitoramento, Decisões

Todos os cálculos de custo e de AgileEVM são feitos por fórmula **na planilha**
(igual a 2026.1). O dashboard só lê o resultado e desenha; assim o número do
painel é sempre o mesmo da planilha. Sem URL publicada, lê o CSV de mesmo nome
em ``planilhas/`` (exportado da planilha) e diz isso na tela.
"""

from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path

import pandas as pd

# nome da chave em config.PLANILHAS -> (planilha, aba) — mostrado na tela como fonte
ABAS = {
    "custos": ("Custos e AgileEVM", "Custos"),
    "planejamento": ("Custos e AgileEVM", "Planejamento"),
    "horas": ("Custos e AgileEVM", "Horas"),
    "sumario_evm": ("Custos e AgileEVM", "Sumário EVM"),
    "valor_agregado": ("Custos e AgileEVM", "EVM - Valor Agregado"),
    "velocity": ("Custos e AgileEVM", "EVM - Velocity"),
    "riscos": ("Riscos e Decisões", "Riscos"),
    "monitoramento": ("Riscos e Decisões", "Monitoramento"),
    "decisoes": ("Riscos e Decisões", "Decisões"),
}

ORIGEM: dict[str, str] = {}


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = re.sub(r"\(.*?\)", "", t).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def _chave_coluna(titulo: str, siglas: bool) -> str:
    """'Pontos planejados (PP)' -> 'PP' (abas do EVM); 'Início da sprint' -> 'inicio_da_sprint'."""
    m = re.search(r"\(([A-Za-z]{1,4})\)\s*$", str(titulo))
    if siglas and m:
        return m.group(1)
    return _slug(titulo)


def numero(valor) -> float:
    """Converte 'R$ 1.234,56', '25,0%', '0,42', '1234.5' em float. '25%' -> 0.25."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return float("nan")
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor).strip().replace("R$", "").replace("\xa0", "").replace(" ", "")
    if not t or t in ("-", "—"):
        return float("nan")
    pct = t.endswith("%")
    t = t.rstrip("%")
    if "," in t and "." in t:
        # o separador decimal é o que aparece por último (pt-BR 1.234,56 ou en-US 1,234.56)
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return float("nan")
    return v / 100 if pct else v


def data(valor):
    if valor is None or str(valor).strip() == "":
        return pd.NaT
    return pd.to_datetime(str(valor).strip(), dayfirst="/" in str(valor), errors="coerce")


def ler(chave: str, urls: dict, pasta: Path, siglas: bool = False) -> pd.DataFrame:
    """Lê a aba publicada (URL em config.PLANILHAS) ou o CSV local ``planilhas/<chave>.csv``."""
    planilha, aba = ABAS.get(chave, ("?", chave))
    url = (urls or {}).get(chave, "")
    bruto = None
    if url:
        try:
            import requests
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            bruto = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str, header=None)
            ORIGEM[chave] = f"planilha **{planilha}**, aba **{aba}** (Google Sheets)"
        except Exception as erro:  # noqa: BLE001 — qualquer falha cai para o CSV local
            ORIGEM[chave] = f"CSV local `planilhas/{chave}.csv` (a planilha publicada falhou: {erro.__class__.__name__})"
    if bruto is None:
        caminho = Path(pasta) / f"{chave}.csv"
        if not url:
            ORIGEM[chave] = f"CSV local `planilhas/{chave}.csv` (cópia da aba **{aba}** da planilha **{planilha}**)"
        try:
            bruto = pd.read_csv(caminho, dtype=str, header=None)
        except (OSError, pd.errors.EmptyDataError):
            ORIGEM[chave] = f"não encontrado (`planilhas/{chave}.csv`)"
            return pd.DataFrame()
    bruto = bruto.fillna("")
    cab = [str(x).strip() for x in bruto.iloc[0]]
    df = bruto.iloc[1:].copy()
    df.columns = cab
    df = df.loc[:, [c for c in df.columns if c]]
    df = df[(df.astype(str).apply(lambda s: s.str.strip()) != "").any(axis=1)].reset_index(drop=True)
    df.attrs["titulos"] = dict(zip([_chave_coluna(c, siglas) for c in df.columns], df.columns))
    df.columns = [_chave_coluna(c, siglas) for c in df.columns]
    return df


def custos(df: pd.DataFrame) -> dict:
    """Aba Custos -> {chave: valor}."""
    if df.empty or "chave" not in df:
        return {}
    return {k: numero(v) for k, v in zip(df["chave"], df["valor"])}


def planejamento_semanal(df: pd.DataFrame) -> pd.DataFrame:
    """Aba Planejamento -> uma linha por semana: início, integrantes ativos, custo, release, sprint."""
    if df.empty:
        return pd.DataFrame()
    rotulo = df.columns[0]
    semanas = [c for c in df.columns[1:] if pd.notna(data(df.attrs["titulos"].get(c, c)))]
    linhas = {str(v).strip().lower(): i for i, v in enumerate(df[rotulo])}

    def linha(prefixo):
        for nome, i in linhas.items():
            if nome.startswith(prefixo):
                return df.iloc[i]
        return None

    ativos, custo, rel, spr = (linha(p) for p in ("integrantes ativos", "custo planejado", "release", "sprint"))
    out = []
    for c in semanas:
        out.append({"semana": data(df.attrs["titulos"].get(c, c)),
                    "integrantes": numero(ativos[c]) if ativos is not None else float("nan"),
                    "custo": numero(custo[c]) if custo is not None else float("nan"),
                    "release": rel[c] if rel is not None else "",
                    "sprint": numero(spr[c]) if spr is not None else float("nan")})
    return pd.DataFrame(out)


def converter(df: pd.DataFrame, numericas=(), datas=()) -> pd.DataFrame:
    df = df.copy()
    for c in numericas:
        if c in df:
            df[c] = df[c].map(numero)
    for c in datas:
        if c in df:
            df[c] = df[c].map(data)
    return df
