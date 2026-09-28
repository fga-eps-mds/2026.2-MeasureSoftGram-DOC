"""Fonte PLANILHA — as abas do time (Google Sheets publicadas em CSV).

Só o que nem o SonarCloud nem o Zenhub têm vem da planilha: Custos,
Planejamento (quem está no time em cada semana), Horas, Riscos, Monitoramento e
Decisões. Nenhum ponto, sprint ou métrica de código é digitado aqui.
As regras do time usadas no cálculo da velocity ficam em ``config.PARAMETROS``.

Não há cópia local: sem URL publicada, ou se a planilha não responder, a aba
fica indisponível e a tela diz isso.
"""

from __future__ import annotations

import io
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# nome da chave em config.PLANILHAS -> (planilha, aba) — mostrado na tela como fonte
ABAS = {
    "custos": ("Custos e AgileEVM", "Custos"),
    "planejamento": ("Custos e AgileEVM", "Planejamento"),
    "horas": ("Custos e AgileEVM", "Horas"),
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


def ler(chave: str, urls: dict, pasta: Path | None = None, siglas: bool = False) -> pd.DataFrame:
    """Lê a aba publicada (URL em ``config.PLANILHAS``).

    No navegador (GitHub Pages) lê o CSV que o deploy baixou da versão publicada
    e empacotou em ``pasta``. Sem URL ou com falha, devolve vazio e registra o
    motivo em ``ORIGEM`` — nunca usa dado de outra origem.
    """
    planilha, aba = ABAS.get(chave, ("?", chave))
    url = (urls or {}).get(chave, "")
    bruto = None
    if sys.platform == "emscripten":
        try:
            bruto = pd.read_csv(Path(pasta) / f"{chave}.csv", dtype=str, header=None)
            ORIGEM[chave] = f"planilha **{planilha}**, aba **{aba}** (versão publicada, baixada no deploy)"
        except (OSError, TypeError, pd.errors.EmptyDataError):
            ORIGEM[chave] = f"indisponível: a aba **{aba}** não foi baixada no deploy"
            return pd.DataFrame()
    elif not url:
        ORIGEM[chave] = f"indisponível: a aba **{aba}** não tem URL publicada em `config.PLANILHAS`"
        return pd.DataFrame()
    else:
        try:
            import requests
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            bruto = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str, header=None)
            ORIGEM[chave] = f"planilha **{planilha}**, aba **{aba}** (Google Sheets)"
        except Exception as erro:  # noqa: BLE001 — a aba fica indisponível, o painel segue
            ORIGEM[chave] = (f"indisponível: a planilha publicada não respondeu ({erro.__class__.__name__}); "
                             "confira a conexão ou a URL em `config.PLANILHAS`")
            return pd.DataFrame()
    if bruto is None or bruto.empty:
        ORIGEM[chave] = f"indisponível: a aba **{aba}** está vazia"
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


# ───────────────────────── parâmetros do modelo de gestão ─────────────────────────

TIPOS_PONTUADOS_PADRAO = {"Feature", "Task", "Bug"}


def carregar_parametros(pasta: Path | None = None) -> dict:
    """Regras do time (``config.PARAMETROS``): níveis pontuados, janela de planning, sprints canceladas."""
    import config
    brutos = dict(getattr(config, "PARAMETROS", {}) or {})
    tipos = str(brutos.get("niveis_pontuados", "")).strip()
    return {"tipos_pontuados": set(tipos.split(";")) if tipos else TIPOS_PONTUADOS_PADRAO,
            "tabela": pd.DataFrame({"parametro": list(brutos), "valor": [str(v) for v in brutos.values()]})}


# ───────────────────────── custos ─────────────────────────

# Componentes do custo semanal de um integrante (chaves da aba Custos) -> categoria.
COMPONENTES_CUSTO = {
    "custo_eps_semana": "Dedicação à disciplina (custo do aluno)",
    "energia_semana": "Energia",
    "internet_semana": "Internet",
    "depreciacao_semana": "Depreciação do notebook",
}


def custo_por_recurso(plano_bruto: pd.DataFrame, custo_membro_semana: float | None) -> pd.DataFrame:
    """Aba Planejamento (integrante × semana, 1 = ativo) -> custo planejado por integrante e semana."""
    if plano_bruto is None or plano_bruto.empty or not custo_membro_semana:
        return pd.DataFrame(columns=["integrante", "semana", "ativo", "custo"])
    rotulo = plano_bruto.columns[0]
    titulos = plano_bruto.attrs.get("titulos", {})
    semanas = [c for c in plano_bruto.columns[1:] if pd.notna(data(titulos.get(c, c)))]
    linhas = []
    for _, r in plano_bruto.iterrows():
        nome = str(r[rotulo]).strip()
        baixo = nome.lower()
        if not nome or baixo.startswith(("integrantes ativos", "custo planejado", "release", "sprint", "total",
                                         "infraestrutura")):
            continue
        for c in semanas:
            ativo = numero(r[c])
            if pd.isna(ativo):
                continue
            linhas.append({"integrante": nome, "semana": data(titulos.get(c, c)), "ativo": ativo,
                           "custo": ativo * float(custo_membro_semana)})
    return pd.DataFrame(linhas)


def link_aba(chave: str) -> str | None:
    """Link para a aba na planilha original (mesmo ``gid`` da URL publicada em ``config.PLANILHAS``)."""
    import re

    import config
    url = config.PLANILHAS.get(chave, "")
    m = re.search(r"[?&]gid=(\d+)", url)
    if not m or not getattr(config, "PLANILHA_ID_EDICAO", ""):
        return None
    return f"https://docs.google.com/spreadsheets/d/{config.PLANILHA_ID_EDICAO}/edit#gid={m.group(1)}"


def nome_aba(chave: str) -> str:
    return ABAS.get(chave, ("", chave))[1]
