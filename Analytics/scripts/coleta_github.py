"""Coleta as execuções de workflow (GitHub Actions) de cada repositório do projeto.

Uso (na pasta Analytics/):

    python scripts/coleta_github.py          # GITHUB_TOKEN no ambiente ou no .env (opcional)

Grava ``data/github/runs-<repo>.json`` (um arquivo por repositório, sempre o mais
recente) com todas as execuções criadas desde ``config.INICIO_SEMESTRE``, página a
página (100 por página). Assim o total bate com a aba Actions do GitHub para o
mesmo período — os arquivos ``GitHub_API-Runs-*.json`` do metrics.yml só têm as
execuções até o último push de cada repositório.

Sem token funciona para repositórios públicos, com limite de 60 requisições/hora.
O token nunca é impresso.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from src.data.github import PASTA_COLETA  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402

API = "https://api.github.com"
CAMPOS = ("id", "name", "status", "conclusion", "head_branch", "event", "created_at", "run_started_at",
          "updated_at", "html_url", "run_number", "workflow_id")


def coletar_repo(sessao, repo: str, desde: str, max_paginas: int = 30) -> dict:
    runs, pagina, total = [], 1, None
    while pagina <= max_paginas:
        r = sessao.get(f"{API}/repos/{config.GITHUB_ORG}/{repo}/actions/runs",
                       params={"per_page": 100, "page": pagina, "created": f">={desde}"}, timeout=30)
        if r.status_code == 404:
            return {"erro": "repositório não encontrado ou sem Actions"}
        r.raise_for_status()
        dados = r.json()
        total = dados.get("total_count", total)
        lote = dados.get("workflow_runs") or []
        runs += [{k: x.get(k) for k in CAMPOS} for x in lote]
        if len(lote) < 100:
            break
        pagina += 1
    vistos, unicos = set(), []
    for x in runs:                       # a API pode repetir um run entre páginas se chegar um novo no meio
        if x["id"] not in vistos:
            vistos.add(x["id"])
            unicos.append(x)
    return {"total_count": total, "workflow_runs": unicos}


def executar(pasta: Path = PASTA_COLETA, log=print) -> list[Path]:
    import requests

    carregar_env(RAIZ / ".env")
    sessao = requests.Session()
    sessao.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        sessao.headers["Authorization"] = f"Bearer {token}"
    pasta.mkdir(parents=True, exist_ok=True)
    desde = str(config.INICIO_SEMESTRE)[:10]
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gravados, falhas = [], 0
    for repo in config.GITHUB_REPOS:
        try:
            dados = coletar_repo(sessao, repo, desde)
        except Exception as erro:  # noqa: BLE001 — um repositório com erro não para os outros
            log(f"{repo}: falhou ({erro.__class__.__name__})")
            falhas += 1
            continue
        if "erro" in dados:
            log(f"{repo}: {dados['erro']}")
            continue
        destino = pasta / f"runs-{repo}.json"
        destino.write_text(json.dumps({"fonte": "API do GitHub (actions/runs)", "coletado_em": agora,
                                       "organizacao": config.GITHUB_ORG, "repositorio": repo, "desde": desde,
                                       **dados}, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{repo}: {len(dados['workflow_runs'])} execuções (total_count {dados['total_count']})")
        gravados.append(destino)
    if falhas and not gravados:
        raise SystemExit("Nenhum repositório coletado.")
    return gravados


if __name__ == "__main__":
    executar()
