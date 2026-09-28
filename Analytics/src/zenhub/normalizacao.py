"""Converte os nós GraphQL do Zenhub em registros planos e estáveis.

Nenhuma regra de negócio aqui: só renomeia campos, trata ``null`` e padroniza
datas em ISO 8601 UTC. As regras (o que conta como planejado ou concluído)
ficam em ``src/metrics/velocity.py``.
"""

from __future__ import annotations


def _nome(obj) -> str | None:
    return (obj or {}).get("name") if isinstance(obj, dict) else None


def sprint(no: dict) -> dict:
    return {
        "sprint_id": no.get("id"),
        # `name` é opcional no schema; sprints automáticas têm só `generatedName`.
        "sprint_name": no.get("name") or no.get("generatedName") or no.get("id"),
        "state": no.get("state"),              # SprintState: OPEN | CLOSED
        "start_at": no.get("startAt"),
        "end_at": no.get("endAt"),
        # Números do próprio Zenhub, guardados só para conferência.
        "zenhub_total_points": no.get("totalPoints"),
        "zenhub_completed_points": no.get("completedPoints"),
        "zenhub_closed_issues": no.get("closedIssuesCount"),
    }


def issue(no: dict) -> dict:
    pipeline_issue = no.get("pipelineIssue") or {}
    estimativa = (no.get("estimate") or {}).get("value")
    return {
        "issue_id": no.get("id"),
        "number": no.get("number"),
        "title": no.get("title"),
        "repository": _nome(no.get("repository")),
        "state": no.get("state"),              # IssueState: OPEN | CLOSED
        "closed_at": no.get("closedAt"),
        "is_pull_request": bool(no.get("pullRequest")),
        "estimate": float(estimativa) if estimativa is not None else None,
        "issue_type": _nome(no.get("issueType")),
        "parent_id": (no.get("parentIssue") or {}).get("id"),
        "pipeline": _nome(pipeline_issue.get("pipeline")),
        "pipeline_moved_at": pipeline_issue.get("latestTransferTime"),
        "url": no.get("htmlUrl"),
    }


def scope_change(no: dict) -> dict:
    alvo = no.get("issue") or {}
    valor = no.get("estimateValue")
    return {
        "action": no.get("action"),            # BucketIssueHistoryAction: ISSUE_ADDED | ISSUE_REMOVED
        "effective_at": no.get("effectiveAt"),
        "estimate_value": float(valor) if valor is not None else None,
        "issue_id": alvo.get("id"),
        "number": alvo.get("number"),
        "title": alvo.get("title"),
        "repository": _nome(alvo.get("repository")),
    }


def release(no: dict) -> dict:
    return {
        "release_id": no.get("id"),
        "release_name": no.get("title"),
        "state": no.get("state"),              # ReleaseState: OPEN | CLOSED
        "start_on": no.get("startOn"),
        "end_on": no.get("endOn"),
        "closed_at": no.get("closedAt"),
        "issues_count": no.get("issuesCount"),
    }


def issue_backlog(no: dict, pipeline_nome: str | None = None) -> dict:
    """Issue do quadro (backlog): os campos de ``issue`` + criação, prioridade e responsáveis."""
    base = issue(no)
    pipeline_issue = no.get("pipelineIssue") or {}
    responsaveis = [a.get("login") for a in ((no.get("assignees") or {}).get("nodes") or []) if isinstance(a, dict)]
    base.update({
        "created_at": no.get("createdAt"),
        "priority": _nome(pipeline_issue.get("priority")),
        "assignees": [r for r in responsaveis if r],
    })
    if not base.get("pipeline") and pipeline_nome:
        base["pipeline"] = pipeline_nome
    return base
