"""Fonte GITHUB — issues e execuções de CI coletadas pelo ``metrics.yml``.

``GitHub_API-Issues-<org>-<repo>.json`` (lista de issues) e
``GitHub_API-Runs-<org>-<repo>-<data>.json`` (``{total_count, workflow_runs[]}``).
Alimenta a página Processo (saúde da integração contínua). Pontos, sprints e
backlog vêm do Zenhub, não daqui.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ORG = "fga-eps-mds"
_ISSUES = re.compile(r"^GitHub_API-Issues-(?P<prefixo>.+)\.json$")
_RUNS = re.compile(r"^GitHub_API-Runs-(?P<prefixo>.+?)-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}-\d{2}\.json$")


def _pastas(entrada) -> list[Path]:
    if isinstance(entrada, (str, Path)):
        entrada = [entrada]
    return [Path(p) for p in entrada if Path(p).is_dir()]


def _repo(prefixo: str) -> str:
    return prefixo[len(ORG) + 1:] if prefixo.startswith(ORG + "-") else prefixo


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


