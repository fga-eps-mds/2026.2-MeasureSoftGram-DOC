"""Orquestra a coleta: cliente -> normalização -> snapshot em disco.

O snapshot é um JSON com tudo o que o cálculo de velocity precisa. O dashboard
lê o snapshot mais recente; ele nunca chama a API durante a renderização (a não
ser pelo botão "Atualizar dados", que roda esta mesma coleta).

Arquivos em ``Analytics/data/zenhub/velocity/``:

* ``zenhub-velocity-AAAA-MM-DDTHHMM.json`` — um por coleta (histórico reprodutível);
* ``linhas-de-base.json`` — o planejado de cada sprint, congelado na primeira
  coleta feita depois do início da sprint (ver ``src/velocity.py``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.zenhub import normalizacao as norm
from src.zenhub.client import ZenhubClient, ZenhubError

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
        for no in cliente.get_sprint_issues(s["sprint_id"]):
            i = norm.issue(no)
            issues[i["issue_id"]] = i
            if i["issue_id"] not in s["issue_ids"]:
                s["issue_ids"].append(i["issue_id"])
        eventos, total = cliente.get_sprint_scope_changes(s["sprint_id"])
        s["scope_changes"] = sorted((norm.scope_change(e) for e in eventos), key=lambda e: e["effective_at"] or "")
        s["scope_total"] = total if total is not None else len(eventos)
        if total is not None and total != len(eventos):
            avisos.append(f"{s['sprint_name']}: o Zenhub informou {total} eventos de escopo e vieram "
                          f"{len(eventos)} (duplicatas descartadas ou paginação incompleta).")
        log(f"  {s['sprint_name']}: {len(s['issue_ids'])} issues, {len(s['scope_changes'])} eventos de escopo")

    # Issues que passaram pela sprint mas saíram dela: detalhe individual.
    faltam = sorted({e["issue_id"] for s in sprints for e in s["scope_changes"]
                     if e["issue_id"] and e["issue_id"] not in issues})
    if len(faltam) > MAX_ISSUES_AVULSAS:
        avisos.append(f"{len(faltam)} issues só aparecem no histórico de escopo; detalhadas as "
                      f"{MAX_ISSUES_AVULSAS} primeiras.")
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

    return {
        "versao": 1,
        "fonte": "Zenhub GraphQL API (https://api.zenhub.com/public/graphql)",
        "workspace_id": cliente.workspace_id,
        "coletado_em": agora.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "requisicoes": cliente.requisicoes,
        "sprints": sprints,
        "issues": issues,
        "releases": releases,
        "avisos": avisos,
    }


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
