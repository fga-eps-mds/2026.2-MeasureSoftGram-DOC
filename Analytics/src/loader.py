"""Leitura dos arquivos gerados automaticamente pelo pipeline de CI/CD.

Nada aqui recebe dado digitado à mão: tudo vem de `analytics-raw-data/`, que é
populado pelo workflow `metrics.yml` de cada repositório. Se um arquivo não
existe, a função devolve um DataFrame vazio e o painel correspondente diz que o
dado falta — nunca inventa valor.

Três formatos convivem na pasta:

1. `<org>-<repo>-<MM>-<DD>-<YYYY>-<HH>-<MM>-<SS>-<branch>.json`
   Métricas do SonarCloud. `baseComponent.measures` traz o agregado do
   repositório; `components` traz o detalhe por diretório/arquivo.
2. `GitHub_API-Issues-<org>-<repo>.json`
   Issues do repositório via API do GitHub.
3. `GitHub_API-Runs-<org>-<repo>-<data>.json`
   Execuções de workflow (CI) via API do GitHub.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import io

import pandas as pd
import requests

ORG = "fga-eps-mds"

# Ancora no bloco de data, porque org e repositório contêm hífens e pontos.
_SONAR = re.compile(
    r"^(?P<prefixo>.+?)-(?P<mes>\d{2})-(?P<dia>\d{2})-(?P<ano>\d{4})"
    r"-(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})-(?P<branch>.+)\.json$"
)
_ISSUES = re.compile(r"^GitHub_API-Issues-(?P<prefixo>.+)\.json$")
_RUNS = re.compile(r"^GitHub_API-Runs-(?P<prefixo>.+?)-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}-\d{2}\.json$")


def _pastas(entrada) -> list[Path]:
    """Normaliza a entrada para uma lista de pastas existentes.

    O ecossistema publica em dois lugares — `analytics-raw-data/` e
    `Analytics/data/` — porque os workflows divergiram entre repositórios.
    O app lê os dois para não ficar cego em nenhum.
    """
    if isinstance(entrada, (str, Path)):
        entrada = [entrada]
    return [Path(p) for p in entrada if Path(p).is_dir()]


def _repo(prefixo: str) -> str:
    """Tira o prefixo da organização do nome do arquivo."""
    return prefixo[len(ORG) + 1:] if prefixo.startswith(ORG + "-") else prefixo


def _num(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def carregar_sonar(pastas) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê as métricas do SonarCloud.

    Devolve (agregado_por_repositorio, detalhe_por_componente).
    """
    linhas_repo, linhas_comp = [], []
    arquivos = [a for pasta in _pastas(pastas) for a in sorted(pasta.glob("*.json"))]

    for arquivo in arquivos:
        if arquivo.name.startswith("GitHub_API-"):
            continue
        casado = _SONAR.match(arquivo.name)
        if not casado:
            continue
        g = casado.groupdict()
        try:
            coleta = datetime(
                int(g["ano"]), int(g["mes"]), int(g["dia"]),
                int(g["h"]), int(g["m"]), int(g["s"]),
            )
        except ValueError:
            continue

        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        repo, branch = _repo(g["prefixo"]), g["branch"]
        base = {"repositorio": repo, "branch": branch, "coleta": coleta, "arquivo": arquivo.name}

        for medida in (dados.get("baseComponent") or {}).get("measures", []):
            linhas_repo.append({**base, "metrica": medida.get("metric"),
                                "valor": _num(medida.get("value"))})

        for componente in dados.get("components") or []:
            for medida in componente.get("measures", []):
                linhas_comp.append({
                    **base,
                    "componente": componente.get("path") or componente.get("name"),
                    "tipo": componente.get("qualifier"),
                    "metrica": medida.get("metric"),
                    "valor": _num(medida.get("value")),
                })

    return pd.DataFrame(linhas_repo), pd.DataFrame(linhas_comp)


def carregar_issues(pastas) -> pd.DataFrame:
    """Lê as issues coletadas pela API do GitHub."""
    linhas = []
    for arquivo in [a for p in _pastas(pastas)
                    for a in sorted(p.glob("GitHub_API-Issues-*.json"))]:
        casado = _ISSUES.match(arquivo.name)
        if not casado:
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(dados, list):
            dados = dados.get("items", []) if isinstance(dados, dict) else []
        for item in dados:
            if not isinstance(item, dict):
                continue
            linhas.append({
                "repositorio": _repo(casado.group("prefixo")),
                "numero": item.get("number"),
                "titulo": item.get("title"),
                "estado": item.get("state"),
                "criada_em": pd.to_datetime(item.get("created_at"), errors="coerce", utc=True),
                "fechada_em": pd.to_datetime(item.get("closed_at"), errors="coerce", utc=True),
                "labels": [l.get("name") for l in (item.get("labels") or []) if isinstance(l, dict)],
            })
    df = pd.DataFrame(linhas)
    if not df.empty:
        df["lead_time_dias"] = (df["fechada_em"] - df["criada_em"]).dt.total_seconds() / 86400
    return df


def carregar_runs(pastas) -> pd.DataFrame:
    """Lê as execuções de workflow coletadas pela API do GitHub."""
    linhas = []
    for arquivo in [a for p in _pastas(pastas)
                    for a in sorted(p.glob("GitHub_API-Runs-*.json"))]:
        casado = _RUNS.match(arquivo.name)
        if not casado:
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(dados, dict):
            dados = dados.get("workflow_runs") or dados.get("items") or []
        for item in dados:
            if not isinstance(item, dict):
                continue
            linhas.append({
                "repositorio": _repo(casado.group("prefixo")),
                "workflow": item.get("name"),
                "status": item.get("status"),
                "conclusao": item.get("conclusion"),
                "branch": item.get("head_branch"),
                "criado_em": pd.to_datetime(item.get("created_at"), errors="coerce", utc=True),
                "iniciado_em": pd.to_datetime(item.get("run_started_at"), errors="coerce", utc=True),
                "atualizado_em": pd.to_datetime(item.get("updated_at"), errors="coerce", utc=True),
                "evento": item.get("event"),
                "id": item.get("id"),
            })
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    # O mesmo run aparece em várias coletas; fica a versão mais recente dele.
    df = df.sort_values("atualizado_em").drop_duplicates(["repositorio", "id"], keep="last")
    df["duracao_min"] = (df["atualizado_em"] - df["iniciado_em"]).dt.total_seconds() / 60
    return df.drop(columns=["id"])


def carregar_tabela(url: str, caminho_local: Path,
                    colunas: list[str]) -> tuple[pd.DataFrame, str]:
    """Lê uma planilha de apoio (EVM, riscos, decisões).

    Tenta primeiro a planilha publicada do Google; sem URL, ou se a busca
    falhar, cai para o CSV local. Devolve também a origem do dado, para que o
    painel possa dizer na tela de onde veio — se o número aparece, a pessoa
    precisa poder rastrear a fonte.
    """
    if url:
        try:
            resposta = requests.get(url, timeout=10)
            resposta.raise_for_status()
            df = pd.read_csv(io.StringIO(resposta.content.decode("utf-8")))
            return _limpar(df, colunas), "planilha do Google"
        except (requests.RequestException, pd.errors.ParserError,
                pd.errors.EmptyDataError, UnicodeDecodeError) as erro:
            caminho_local = Path(caminho_local)
            if not caminho_local.exists():
                return pd.DataFrame(columns=colunas), f"falha ao ler a planilha ({erro.__class__.__name__})"
            # cai para o local, mas avisa que a planilha falhou
            df, _ = carregar_tabela("", caminho_local, colunas)
            return df, f"CSV local (a planilha falhou: {erro.__class__.__name__})"

    caminho_local = Path(caminho_local)
    if not caminho_local.exists():
        return pd.DataFrame(columns=colunas), "arquivo não encontrado"
    try:
        df = pd.read_csv(caminho_local)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=colunas), "arquivo ilegível"
    return _limpar(df, colunas), "CSV local"


def _limpar(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Descarta linhas em branco e garante que as colunas esperadas existam."""
    df = df.dropna(how="all")
    df.columns = [str(c).strip().lower() for c in df.columns]
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = pd.NA
    return df


def ultimo_por_repo(agregado: pd.DataFrame) -> pd.DataFrame:
    """Última coleta de cada repositório, para os indicadores do topo."""
    if agregado.empty:
        return agregado
    idx = agregado.groupby(["repositorio", "metrica"])["coleta"].idxmax()
    return agregado.loc[idx].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Planilhas no formato AgileEVM
#
# O layout vem da equipe de 2026.1 e é o do artigo AgileEVM (Sulaiman, Barton &
# Blackburn): cabeçalho na terceira linha, valores em moeda brasileira, colunas
# agrupadas por tema. Em vez de exigir um formato novo do time, o parser se
# adapta ao que a planilha já tem.
# ---------------------------------------------------------------------------

def _ler_csv(url: str, caminho_local: Path, header: int):
    """Busca a planilha publicada ou o CSV local, sem interpretar colunas."""
    if url:
        try:
            resposta = requests.get(url, allow_redirects=True, timeout=15)
            resposta.raise_for_status()
            return (pd.read_csv(io.StringIO(resposta.content.decode("utf-8")),
                                header=header),
                    "planilha do Google")
        except (requests.RequestException, pd.errors.ParserError,
                pd.errors.EmptyDataError, UnicodeDecodeError) as erro:
            origem_falha = f"a planilha falhou ({erro.__class__.__name__})"
    else:
        origem_falha = None

    caminho_local = Path(caminho_local)
    if not caminho_local.exists():
        return None, origem_falha or "arquivo não encontrado"
    try:
        df = pd.read_csv(caminho_local, header=header)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None, "arquivo ilegível"
    return df, ("CSV local" if not origem_falha else f"CSV local ({origem_falha})")


def _coluna(df: pd.DataFrame, *palavras: str):
    """Acha a coluna cujo nome contém todas as palavras, ignorando quebras."""
    for coluna in df.columns:
        normalizada = str(coluna).replace("\n", " ").strip().lower()
        if all(p.lower() in normalizada for p in palavras):
            return coluna
    return None


def _moeda_br(valor) -> float:
    """Converte 'R$ 5.282,36' ou 5282.36 em float. Texto não numérico vira NaN."""
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto or texto in {"-", "nan"} or "planejado" in texto.lower():
        return float("nan")
    texto = re.sub(r"[R$\s%]", "", texto)
    if "," in texto:  # formato BR: ponto separa milhar, vírgula separa decimal
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return float("nan")


def carregar_evm(url: str, caminho_local: Path) -> tuple[pd.DataFrame, str]:
    """Lê a aba de EVM no layout AgileEVM e devolve as colunas essenciais."""
    bruto, origem = _ler_csv(url, caminho_local, header=2)
    if bruto is None:
        return pd.DataFrame(columns=["sprint", "inicio", "fim", "pp", "pc",
                                     "pv", "ev", "ac"]), origem

    mapa = {
        "sprint": _coluna(bruto, "sprint", "(n)") or _coluna(bruto, "sprint"),
        "inicio": _coluna(bruto, "início") or _coluna(bruto, "inicio"),
        "fim": _coluna(bruto, "fim da sprint"),
        "pp": _coluna(bruto, "pontos", "planejados"),
        "pc": _coluna(bruto, "points", "completed"),
        "pv": _coluna(bruto, "planned value"),
        "ev": _coluna(bruto, "earned value"),
        "ac": _coluna(bruto, "actual", "cost"),
    }
    if not mapa["sprint"]:
        return pd.DataFrame(), f"{origem} — coluna de sprint não encontrada"

    df = pd.DataFrame({
        destino: bruto[origem_col] if origem_col else pd.NA
        for destino, origem_col in mapa.items()
    })
    df = df[pd.to_numeric(df["sprint"], errors="coerce").notna()].copy()
    if df.empty:
        return df, origem

    df["sprint"] = df["sprint"].astype(float).astype(int)
    for coluna in ("inicio", "fim"):
        df[coluna] = pd.to_datetime(df[coluna], format="%d/%m/%Y", errors="coerce")
    for coluna in ("pp", "pc"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
    for coluna in ("pv", "ev", "ac"):
        df[coluna] = df[coluna].apply(_moeda_br)

    return df.reset_index(drop=True), origem


def carregar_velocity(url: str, caminho_local: Path) -> tuple[pd.DataFrame, str]:
    """Lê a aba de velocity. Sem ela, o painel deriva de pp/pc do EVM."""
    bruto, origem = _ler_csv(url, caminho_local, header=1)
    if bruto is None:
        return pd.DataFrame(columns=["sprint", "pp", "pc", "velocity"]), origem

    mapa = {
        "sprint": _coluna(bruto, "sprint"),
        "pp": _coluna(bruto, "planejados") or _coluna(bruto, "(pp)"),
        "pc": _coluna(bruto, "completed") or _coluna(bruto, "conclu"),
        "velocity": _coluna(bruto, "velocity"),
    }
    if not mapa["sprint"]:
        return pd.DataFrame(), f"{origem} — coluna de sprint não encontrada"

    df = pd.DataFrame({d: bruto[o] if o else pd.NA for d, o in mapa.items()})
    df = df[pd.to_numeric(df["sprint"], errors="coerce").notna()].copy()
    if df.empty:
        return df, origem
    df["sprint"] = df["sprint"].astype(float).astype(int)
    for coluna in ("pp", "pc", "velocity"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
    return df.reset_index(drop=True), origem


def coletas_com_erro(pastas) -> pd.DataFrame:
    """Coletas do SonarCloud que voltaram erro em vez de métrica.

    O workflow grava o `.json` mesmo quando a API responde erro — tipicamente
    `Component key not found`, ou seja: o repositório roda o pipeline mas não
    tem projeto criado no SonarCloud. Sem isto o painel só ficaria silencioso
    sobre esses repositórios, e silêncio não é informação.
    """
    linhas = []
    for pasta in _pastas(pastas):
        for arquivo in sorted(pasta.glob("*.json")):
            if arquivo.name.startswith("GitHub_API-"):
                continue
            casado = _SONAR.match(arquivo.name)
            if not casado:
                continue
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(dados, dict) or not dados.get("errors"):
                continue
            g = casado.groupdict()
            mensagens = "; ".join(
                str(e.get("msg", e)) for e in dados["errors"] if isinstance(e, dict)
            ) or "erro sem mensagem"
            linhas.append({
                "repositorio": _repo(g["prefixo"]),
                "coleta": f"{g['dia']}/{g['mes']}/{g['ano']}",
                "erro": mensagens,
            })
    df = pd.DataFrame(linhas)
    return df.drop_duplicates(subset=["repositorio", "erro"]) if not df.empty else df
