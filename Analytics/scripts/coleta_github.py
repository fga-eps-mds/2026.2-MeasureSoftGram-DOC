"""Coleta do GitHub para o dashboard: execuções de CI, issues e commits (com arquivos alterados).

Uso (na pasta Analytics/):

    python scripts/coleta_github.py          # GITHUB_TOKEN no ambiente ou no .env (opcional)

Grava, um arquivo por repositório (sempre o mais recente):

* ``data/github/runs-<repo>.json`` — todas as execuções criadas desde ``config.INICIO_SEMESTRE``,
  página a página (100 por página). Assim o total bate com a aba Actions do GitHub para o
  mesmo período — os arquivos ``GitHub_API-Runs-*.json`` do metrics.yml só têm as
  execuções até o último push de cada repositório.
* ``data/github/issues-<repo>.json`` — issues e PRs (abertas e fechadas) com tipo/labels,
  responsáveis, milestone e se têm descrição. Insumo do modelo de qualidade (Q-Rapids):
  densidade de bugs e issues completamente especificadas.
* ``data/github/commits-<repo>.json`` — commits da branch ``config.SONAR_BRANCH`` (ou da
  padrão) desde o início do semestre, com os arquivos alterados em cada um. Insumo do
  fator "Highly changed files" do Q-Rapids. Incremental: só busca o detalhe dos commits novos.

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


def _paginas(sessao, url: str, params: dict, max_paginas: int = 30) -> list:
    itens, pagina = [], 1
    while pagina <= max_paginas:
        r = sessao.get(url, params={**params, "per_page": 100, "page": pagina}, timeout=30)
        if r.status_code in (404, 409):          # 409 = repositório vazio
            return itens
        r.raise_for_status()
        lote = r.json() or []
        itens += lote
        if len(lote) < 100:
            break
        pagina += 1
    return itens


def coletar_issues(sessao, repo: str) -> list[dict]:
    """Issues e PRs do repositório (todas), só com os campos que o painel usa."""
    saida = []
    for x in _paginas(sessao, f"{API}/repos/{config.GITHUB_ORG}/{repo}/issues", {"state": "all"}):
        corpo = (x.get("body") or "").strip()
        saida.append({
            "number": x.get("number"), "title": x.get("title"), "state": x.get("state"),
            "is_pull_request": "pull_request" in x, "created_at": x.get("created_at"),
            "closed_at": x.get("closed_at"), "updated_at": x.get("updated_at"),
            "labels": [l.get("name") for l in x.get("labels") or [] if isinstance(l, dict)],
            "type": (x.get("type") or {}).get("name") if isinstance(x.get("type"), dict) else None,
            "assignees": [a.get("login") for a in x.get("assignees") or [] if isinstance(a, dict)],
            "milestone": (x.get("milestone") or {}).get("title") if x.get("milestone") else None,
            "milestone_due_on": (x.get("milestone") or {}).get("due_on") if x.get("milestone") else None,
            "body_chars": len(corpo), "html_url": x.get("html_url"),
            "author": (x.get("user") or {}).get("login")})
    return saida


def coletar_commits(sessao, repo: str, desde: str, anteriores: dict | None = None,
                    max_detalhes: int = 300) -> dict:
    """Commits desde ``desde`` na branch de desenvolvimento, com os arquivos alterados.

    O detalhe (arquivos) custa uma requisição por commit: commits já coletados em ``anteriores``
    (sha -> commit) são reaproveitados.
    """
    base = f"{API}/repos/{config.GITHUB_ORG}/{repo}"
    branch = config.SONAR_BRANCH
    lista = _paginas(sessao, f"{base}/commits", {"since": f"{desde}T00:00:00Z", "sha": branch})
    if not lista:                         # sem a branch de desenvolvimento: usa a padrão
        branch = None
        lista = _paginas(sessao, f"{base}/commits", {"since": f"{desde}T00:00:00Z"})
    anteriores = anteriores or {}
    commits, novos = [], 0
    for c in lista:
        sha = c.get("sha")
        if sha in anteriores:
            commits.append(anteriores[sha])
            continue
        if novos >= max_detalhes:
            break
        r = sessao.get(f"{base}/commits/{sha}", timeout=30)
        r.raise_for_status()
        d = r.json()
        novos += 1
        info = d.get("commit") or {}
        commits.append({
            "sha": sha, "date": (info.get("author") or {}).get("date"),
            "author": (d.get("author") or {}).get("login") or (info.get("author") or {}).get("name"),
            "message": (info.get("message") or "").splitlines()[0][:200] if info.get("message") else "",
            "parents": len(d.get("parents") or []),
            "files": [{"filename": f.get("filename"), "status": f.get("status"), "additions": f.get("additions"),
                       "deletions": f.get("deletions")} for f in d.get("files") or []]})
    return {"branch": branch or "(padrão)", "commits": commits, "detalhes_novos": novos}


def _gravar(destino: Path, cabecalho: dict, dados: dict) -> None:
    destino.write_text(json.dumps({**cabecalho, **dados}, ensure_ascii=False, indent=1), encoding="utf-8")


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
        cab = {"coletado_em": agora, "organizacao": config.GITHUB_ORG, "repositorio": repo, "desde": desde}
        destino = pasta / f"runs-{repo}.json"
        _gravar(destino, {"fonte": "API do GitHub (actions/runs)", **cab}, dados)
        log(f"{repo}: {len(dados['workflow_runs'])} execuções (total_count {dados['total_count']})")
        gravados.append(destino)
        # issues e commits: falha aqui não apaga o que já foi gravado
        try:
            issues = coletar_issues(sessao, repo)
            destino = pasta / f"issues-{repo}.json"
            _gravar(destino, {"fonte": "API do GitHub (issues)", **cab}, {"issues": issues})
            gravados.append(destino)
            log(f"{repo}: {len(issues)} issues e PRs")
        except Exception as erro:  # noqa: BLE001
            log(f"{repo}: issues falharam ({erro.__class__.__name__})")
        try:
            arq = pasta / f"commits-{repo}.json"
            antes = {}
            if arq.exists():
                try:
                    antes = {c["sha"]: c for c in json.loads(arq.read_text(encoding="utf-8")).get("commits", [])}
                except (json.JSONDecodeError, OSError, KeyError, TypeError):
                    antes = {}
            com = coletar_commits(sessao, repo, desde, antes)
            _gravar(arq, {"fonte": "API do GitHub (commits)", **cab}, com)
            gravados.append(arq)
            log(f"{repo}: {len(com['commits'])} commits na branch {com['branch']} ({com['detalhes_novos']} novos)")
        except Exception as erro:  # noqa: BLE001
            log(f"{repo}: commits falharam ({erro.__class__.__name__})")
    if falhas and not gravados:
        raise SystemExit("Nenhum repositório coletado.")
    return gravados


if __name__ == "__main__":
    executar()
