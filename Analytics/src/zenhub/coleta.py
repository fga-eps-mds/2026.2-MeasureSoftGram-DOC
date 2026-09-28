"""Orquestra a coleta: cliente -> normalização -> snapshot em disco.

O snapshot é um JSON com tudo o que o cálculo de velocity precisa. O dashboard
lê o snapshot mais recente; ele nunca chama a API durante a renderização (a não
ser pelo botão "Atualizar dados", que roda esta mesma coleta).

Arquivos em ``Analytics/data/zenhub/velocity/``:

* ``zenhub-velocity-AAAA-MM-DDTHHMM.json`` — um por coleta (histórico reprodutível);
* ``linhas-de-base.json`` — o planejado de cada sprint, congelado na primeira
  coleta feita depois do início da sprint (ver ``src/metrics/velocity.py``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.zenhub import normalizacao as norm
from src.zenhub.client import ZenhubAuthError, ZenhubClient, ZenhubError

PASTA = Path(__file__).resolve().parents[2] / "data" / "zenhub" / "velocity"
ARQ_LINHAS_DE_BASE = "linhas-de-base.json"
MAX_ISSUES_AVULSAS = 400  # teto de consultas individuais por coleta


def _dt(texto: str | None) -> datetime | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def coletar(cliente: ZenhubClient, agora: datetime | None = None, log=print) -> dict:
    agora = agora or datetime.now(timezone.utc)
    avisos: list[str] = []
    if hasattr(cliente, "log"):
        cliente.log = log

    sprints = [norm.sprint(s) for s in cliente.get_sprints()]
    sprints.sort(key=lambda s: s["start_at"] or "")
    log(f"{len(sprints)} sprints no workspace")

    issues: dict[str, dict] = {}
    for s in sprints:
        s["issue_ids"], s["scope_changes"], s["scope_total"] = [], [], 0
        inicio = _dt(s["start_at"])
        if inicio is None or inicio > agora:
            s["coletada"] = False  # sprint futura: nada a medir ainda
            continue
        s["coletada"] = True
        log(f"  {s['sprint_name']}: lendo issues e histórico de escopo...")
        s["falhas"] = []
        try:
            for no in cliente.get_sprint_issues(s["sprint_id"]):
                i = norm.issue(no)
                issues[i["issue_id"]] = i
                if i["issue_id"] not in s["issue_ids"]:
                    s["issue_ids"].append(i["issue_id"])
        except ZenhubAuthError:
            raise
        except ZenhubError as erro:
            s["falhas"].append("issues")
            avisos.append(f"{s['sprint_name']}: issues não coletadas ({erro}).")
            log(f"    falhou ao ler as issues: {erro}")
        try:
            eventos, total = cliente.get_sprint_scope_changes(s["sprint_id"])
            s["scope_changes"] = sorted((norm.scope_change(e) for e in eventos),
                                        key=lambda e: e["effective_at"] or "")
            s["scope_total"] = total if total is not None else len(eventos)
            if total is not None and total != len(eventos):
                avisos.append(f"{s['sprint_name']}: o Zenhub informou {total} eventos de escopo e vieram "
                              f"{len(eventos)} (duplicatas descartadas ou paginação incompleta).")
        except ZenhubAuthError:
            raise
        except ZenhubError as erro:
            # Sem histórico o planejado fica "indisponível" (e não é congelado).
            s["falhas"].append("scope")
            avisos.append(f"{s['sprint_name']}: histórico de escopo não coletado ({erro}).")
            log(f"    falhou ao ler o histórico de escopo: {erro}")
        log(f"    {len(s['issue_ids'])} issues, {len(s['scope_changes'])} eventos de escopo")

    # Issues que passaram pela sprint mas saíram dela: detalhe individual.
    faltam = sorted({e["issue_id"] for s in sprints for e in s["scope_changes"]
                     if e["issue_id"] and e["issue_id"] not in issues})
    if len(faltam) > MAX_ISSUES_AVULSAS:
        avisos.append(f"{len(faltam)} issues só aparecem no histórico de escopo; detalhadas as "
                      f"{MAX_ISSUES_AVULSAS} primeiras.")
    if faltam:
        log(f"Detalhando {min(len(faltam), MAX_ISSUES_AVULSAS)} issues que saíram das sprints...")
    for issue_id in faltam[:MAX_ISSUES_AVULSAS]:
        try:
            no = cliente.get_issue(issue_id)
        except ZenhubError as erro:
            avisos.append(f"Issue {issue_id} não detalhada: {erro}")
            continue
        if no:
            issues[issue_id] = norm.issue(no)
    if faltam:
        log(f"{min(len(faltam), MAX_ISSUES_AVULSAS)} issues detalhadas fora das sprints atuais")

    releases = []
    for r in cliente.get_releases():
        rel = norm.release(r)
        rel["issue_ids"] = cliente.get_release_issue_ids(rel["release_id"])
        releases.append(rel)
    log(f"{len(releases)} releases")

    backlog = coletar_backlog(cliente, avisos, log)

    return {
        "versao": 2,
        "fonte": "Zenhub GraphQL API (https://api.zenhub.com/public/graphql)",
        "workspace_id": cliente.workspace_id,
        "coletado_em": agora.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "requisicoes": cliente.requisicoes,
        "sprints": sprints,
        "issues": issues,
        "releases": releases,
        "backlog": backlog,
        "avisos": avisos,
    }


def coletar_backlog(cliente: ZenhubClient, avisos: list[str], log=print) -> dict | None:
    """Todas as issues abertas do quadro, pipeline por pipeline.

    Falha aqui não derruba a coleta: vira aviso e ``backlog = None`` (a página
    do Zenhub diz que o backlog completo está indisponível).
    """
    if not hasattr(cliente, "get_pipelines"):
        return None
    try:
        pipelines = [{"pipeline_id": p.get("id"), "pipeline": p.get("name")} for p in cliente.get_pipelines()]
    except ZenhubAuthError:
        raise
    except ZenhubError as erro:
        avisos.append(f"Backlog não coletado: a lista de pipelines falhou ({erro}).")
        log(f"Backlog: falhou ao ler os pipelines: {erro}")
        return None
    log(f"Backlog: {len(pipelines)} pipelines")
    issues, falhas = [], []
    for ordem, p in enumerate(pipelines):
        p["ordem"] = ordem
        try:
            nos, total = cliente.get_pipeline_issues(p["pipeline_id"])
        except ZenhubAuthError:
            raise
        except ZenhubError as erro:
            falhas.append(p["pipeline"])
            avisos.append(f"Backlog: pipeline {p['pipeline']} não coletado ({erro}).")
            continue
        p["total"] = total if total is not None else len(nos)
        for no in nos:
            issues.append({**norm.issue_backlog(no, p["pipeline"]), "pipeline_ordem": ordem})
        log(f"  {p['pipeline']}: {len(nos)} issues")
    if falhas and len(falhas) == len(pipelines):
        return None
    return {"pipelines": pipelines, "issues": issues, "pipelines_com_falha": falhas}


def salvar_snapshot(snapshot: dict, pasta: Path = PASTA) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    quando = _dt(snapshot["coletado_em"]).strftime("%Y-%m-%dT%H%M")
    destino = pasta / f"zenhub-velocity-{quando}.json"
    destino.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


def ultimo_snapshot(pasta: Path = PASTA) -> tuple[dict | None, str]:
    arquivos = sorted(Path(pasta).glob("zenhub-velocity-*.json"))
    if not arquivos:
        return None, ""
    return json.loads(arquivos[-1].read_text(encoding="utf-8")), arquivos[-1].name


def ler_linhas_de_base(pasta: Path = PASTA) -> dict:
    arq = Path(pasta) / ARQ_LINHAS_DE_BASE
    if not arq.exists():
        return {}
    return json.loads(arq.read_text(encoding="utf-8"))


def gravar_linhas_de_base(linhas: dict, pasta: Path = PASTA) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    arq = Path(pasta) / ARQ_LINHAS_DE_BASE
    arq.write_text(json.dumps(linhas, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return arq
