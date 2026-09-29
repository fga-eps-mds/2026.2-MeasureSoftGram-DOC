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
# Coleta própria (scripts/coleta_github.py): um arquivo por repositório, com todas as execuções do semestre.
PASTA_COLETA = Path(__file__).resolve().parents[2] / "data" / "github"
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


def _linha_run(repo: str, item: dict, origem: str, coletado_em) -> dict:
    return {"repositorio": repo, "workflow": item.get("name"), "status": item.get("status"),
            "conclusao": item.get("conclusion"), "branch": item.get("head_branch"),
            "criado_em": pd.to_datetime(item.get("created_at"), errors="coerce", utc=True),
            "iniciado_em": pd.to_datetime(item.get("run_started_at"), errors="coerce", utc=True),
            "atualizado_em": pd.to_datetime(item.get("updated_at"), errors="coerce", utc=True),
            "evento": item.get("event"), "id": item.get("id"), "url": item.get("html_url"),
            "origem": origem, "coletado_em": pd.to_datetime(coletado_em, errors="coerce", utc=True)}


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
            linhas.append(_linha_run(_repo(casado.group("prefixo")), item, "metrics.yml", None))
    # coleta própria: completa até a hora da coleta (os arquivos do metrics.yml param no último push)
    for p in _pastas(pastas):
        for arquivo in sorted((p / "github").glob("runs-*.json")) if (p / "github").is_dir() else []:
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for item in dados.get("workflow_runs") or []:
                linhas.append(_linha_run(dados.get("repositorio") or arquivo.stem[5:], item, "coleta do dashboard",
                                         dados.get("coletado_em")))
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    # O mesmo run aparece em várias coletas; fica a versão mais recente dele.
    # A coleta própria vem por último na ordenação de empate e ganha (é a mais completa e recente).
    df["_ordem"] = (df["origem"] == "coleta do dashboard").astype(int)
    df = df.sort_values(["atualizado_em", "_ordem"]).drop_duplicates(["repositorio", "id"], keep="last")
    df = df.drop(columns="_ordem")
    df["duracao_min"] = (df["atualizado_em"] - df["iniciado_em"]).dt.total_seconds() / 60
    return df.drop(columns=["id"])


