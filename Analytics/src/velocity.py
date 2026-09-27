"""Velocity por sprint a partir do snapshot do Zenhub (``src/zenhub/coleta.py``).

Funções puras: recebem o snapshot (dict) e devolvem números. Não falam com a API
nem com o Streamlit, por isso são testadas em ``tests/test_velocity.py``.

Regras (documentadas também em ``docs/metricas/velocity-zenhub.mdx``)
----------------------------------------------------------------------

**Issue pontuável.** Só US (``Feature``), ``Task`` e ``Bug`` sem filhas contam
pontos (``planilhas/parametros.csv``, ``niveis_pontuados``); PR, Épico e
Sub-task não. Issue pontuável sem estimativa conta como issue (planejada ou
concluída) com **0 SP** e aparece na coluna "sem estimativa" — nunca recebe um
valor estimado pelo painel.

**Planejado (linha de base).** Issues pontuáveis que estavam na sprint no fim da
janela de planning (``inicio + janela_planning``, 24 h por padrão, porque a
planning acontece no primeiro dia da sprint), reconstituídas pelo histórico
``Sprint.scopeChange`` (eventos ``ISSUE_ADDED``/``ISSUE_REMOVED`` com data). A
estimativa é a registrada no evento de entrada (``estimateValue``). Issue que
entra depois disso não altera o planejado: aparece como "adicionado depois".
Na primeira coleta após a janela, o planejado é **congelado** em
``linhas-de-base.json`` e, daí em diante, vale o congelado. Sem histórico de
escopo para a sprint, o planejado fica **indisponível** (nunca é trocado pelo
escopo atual, que aparece separado como ``current_story_points``).

**Concluído.** Issue pontuável cuja conclusão aconteceu entre o início e o fim da
sprint **e** que estava na sprint naquele momento. Conclusão = ``closedAt``
quando a issue está fechada; se está aberta no pipeline de feito (``Done``),
``pipelineIssue.latestTransferTime`` (a última movimentação de pipeline). Issue
fechada depois do fim conta na sprint em que estava quando fechou (ou em
nenhuma). Os pontos são a estimativa atual da issue.

**Velocity** = pontos concluídos. **Média** = média da velocity das sprints
concluídas (nunca da sprint em andamento), só com pelo menos
``min_sprints_media`` sprints.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

STATUS_CONCLUIDA = "concluída"
STATUS_ANDAMENTO = "em andamento"
STATUS_FUTURA = "futura"
STATUS_CANCELADA = "cancelada"


@dataclass
class Regras:
    tipos_pontuados: set = field(default_factory=lambda: {"Feature", "Task", "Bug"})
    pipeline_feito: str = "Done"
    janela_planning: timedelta = timedelta(hours=24)
    min_sprints_media: int = 2
    sprints_canceladas: set = field(default_factory=set)

    @classmethod
    def dos_parametros(cls, params: dict) -> "Regras":
        """Monta as regras a partir de ``gestao.carregar_parametros`` (planilhas/parametros.csv)."""
        tabela = params.get("tabela")
        brutos = dict(zip(tabela["parametro"], tabela["valor"])) if tabela is not None and not tabela.empty else {}

        def num(chave, padrao):
            try:
                return float(str(brutos.get(chave, "")).replace(",", "."))
            except ValueError:
                return padrao

        canceladas = {s.strip() for s in str(brutos.get("sprints_canceladas", "")).split(";") if s.strip()}
        return cls(tipos_pontuados=set(params.get("tipos_pontuados") or cls().tipos_pontuados),
                   pipeline_feito=params.get("criterio_feito") or "Done",
                   janela_planning=timedelta(hours=num("janela_planning_horas", 24.0)),
                   min_sprints_media=int(num("min_sprints_media_velocity", 2)),
                   sprints_canceladas=canceladas)


# ───────────────────────── utilidades ─────────────────────────

def _dt(texto) -> datetime | None:
    if texto is None or texto == "" or (isinstance(texto, float) and pd.isna(texto)):
        return None
    if isinstance(texto, datetime):
        return texto if texto.tzinfo else texto.replace(tzinfo=timezone.utc)
    d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _sp(valor) -> float:
    return 0.0 if valor is None else float(valor)


def ids_com_filhas(issues: dict, regras: Regras) -> set:
    """Issues que têm filhas pontuáveis: quem pontua são as filhas."""
    return {i["parent_id"] for i in issues.values()
            if i.get("parent_id") and i.get("issue_type") in regras.tipos_pontuados}


def pontuavel(issue: dict | None, regras: Regras, pais: set) -> bool:
    if not issue:
        return False  # issue sem detalhe: não dá para saber o tipo, não entra
    if issue.get("is_pull_request"):
        return False
    if issue.get("issue_type") not in regras.tipos_pontuados:
        return False
    return issue["issue_id"] not in pais


def membros_em(eventos: list[dict], momento: datetime) -> dict:
    """Issues na sprint em ``momento`` -> estimativa registrada no evento de entrada.

    Os eventos são aplicados em ordem de ``effective_at``; ``ISSUE_REMOVED`` tira
    a issue, um novo ``ISSUE_ADDED`` a traz de volta (issue movida e devolvida).
    """
    membros: dict = {}
    for e in sorted(eventos, key=lambda e: e.get("effective_at") or ""):
        quando = _dt(e.get("effective_at"))
        if quando is None or quando > momento or not e.get("issue_id"):
            continue
        if e.get("action") == "ISSUE_ADDED":
            membros[e["issue_id"]] = e.get("estimate_value")
        elif e.get("action") == "ISSUE_REMOVED":
            membros.pop(e["issue_id"], None)
    return membros


def momento_conclusao(issue: dict, regras: Regras) -> datetime | None:
    if issue.get("state") == "CLOSED":
        return _dt(issue.get("closed_at"))
    if issue.get("pipeline") == regras.pipeline_feito:
        return _dt(issue.get("pipeline_moved_at"))
    return None


def status_da_sprint(sprint: dict, agora: datetime, regras: Regras) -> str:
    if sprint["sprint_id"] in regras.sprints_canceladas:
        return STATUS_CANCELADA
    inicio, fim = _dt(sprint.get("start_at")), _dt(sprint.get("end_at"))
    if inicio is None or inicio > agora:
        return STATUS_FUTURA
    if (fim is not None and fim <= agora) or sprint.get("state") == "CLOSED":
        return STATUS_CONCLUIDA
    return STATUS_ANDAMENTO


# ───────────────────────── linha de base ─────────────────────────

def linha_de_base(sprint: dict, issues: dict, regras: Regras) -> dict | None:
    """Planejado no fim da janela de planning, ou None se não há como saber."""
    eventos = sprint.get("scope_changes") or []
    inicio = _dt(sprint.get("start_at"))
    if inicio is None or set(sprint.get("falhas") or []) & {"scope", "issues"}:
        return None  # coleta incompleta desta sprint: não congela nem estima
    if not eventos:
        if not sprint.get("issue_ids"):
            return {"issues": {}, "fonte": "sprint sem issues"}
        return None  # tem issues mas o Zenhub não devolveu histórico: não inventar
    corte = inicio + regras.janela_planning
    pais = ids_com_filhas(issues, regras)
    membros = membros_em(eventos, corte)
    planejadas = {iid: est for iid, est in membros.items() if pontuavel(issues.get(iid), regras, pais)}
    return {"issues": planejadas, "fonte": "histórico do Zenhub (scopeChange)",
            "corte": corte.isoformat(timespec="seconds")}


def congelar_linhas_de_base(snapshot: dict, linhas: dict, agora: datetime, regras: Regras) -> tuple[dict, list[str]]:
    """Grava o planejado das sprints cuja janela de planning já passou e que ainda não têm linha de base."""
    novas = dict(linhas)
    congeladas = []
    for s in snapshot.get("sprints", []):
        inicio = _dt(s.get("start_at"))
        if not s.get("coletada") or inicio is None or agora < inicio + regras.janela_planning:
            continue
        if s["sprint_id"] in novas or s["sprint_id"] in regras.sprints_canceladas:
            continue
        base = linha_de_base(s, snapshot.get("issues", {}), regras)
        if base is None:
            continue
        novas[s["sprint_id"]] = {
            "sprint_name": s["sprint_name"],
            "planned_story_points": sum(_sp(v) for v in base["issues"].values()),
            "planned_issues": len(base["issues"]),
            "planned_unestimated_issues": sum(v is None for v in base["issues"].values()),
            "issues": base["issues"],
            "fonte": base["fonte"],
            "corte": base.get("corte"),
            "congelado_em": agora.astimezone(timezone.utc).isoformat(timespec="seconds"),
        }
        congeladas.append(s["sprint_name"])
    return novas, congeladas


# ───────────────────────── release ─────────────────────────

# Datas de entrega do plano de ensino (EPS 2026.2). Só valem quando o Zenhub
# não tem Release para a sprint: a sprint entra na primeira release cuja
# entrega é igual ou posterior ao último dia dela (horário de Brasília).
ENTREGAS_PLANO = [("R1", "2026-09-28"), ("R2", "2026-10-26"), ("R3", "2026-11-30")]
BRT = timezone(timedelta(hours=-3))


def associar_release(sprint: dict, ids: set, releases: list[dict]) -> tuple:
    """(release_id, release_name, fonte). Ordem: issues da sprint -> datas da release no Zenhub -> plano de ensino."""
    if releases and ids:
        votos = Counter()
        for r in releases:
            comum = len(ids & set(r.get("issue_ids") or []))
            if comum:
                votos[r["release_id"]] = comum
        if votos:
            rid = votos.most_common(1)[0][0]
            r = next(r for r in releases if r["release_id"] == rid)
            return rid, r["release_name"], "Zenhub (issues da sprint na release)"
    fim = _dt(sprint.get("end_at"))
    if releases and fim is not None:
        for r in releases:
            ini, fim_r = r.get("start_on"), r.get("end_on")
            if ini and fim_r and _dt(ini + "T00:00:00+00:00") <= fim <= _dt(fim_r + "T23:59:59+00:00") + timedelta(days=1):
                return r["release_id"], r["release_name"], "Zenhub (datas da release)"
    if fim is not None:
        ultimo_dia = (fim - timedelta(seconds=1)).astimezone(BRT).date().isoformat()
        for nome, entrega in ENTREGAS_PLANO:
            if ultimo_dia <= entrega:
                return None, nome, "plano de ensino (datas de entrega)"
    return None, None, "sem release"


# ───────────────────────── cálculo ─────────────────────────

def calculate_velocity(snapshot: dict, regras: Regras | None = None, agora: datetime | None = None,
                       linhas_de_base: dict | None = None, incluir_futuras: bool = False) -> pd.DataFrame:
    """Uma linha por sprint, no formato pedido para o gráfico e a tabela.

    ``sprint_label`` é S1, S2... na ordem de início (a mesma numeração do time).
    Com ``incluir_futuras``, as sprints ainda não iniciadas entram com os
    números vazios — o AgileEVM precisa delas para saber o tamanho da release.
    As colunas ``planned_ids``, ``completed_ids`` e ``scope_ids`` guardam as
    issues de cada conjunto, para o AgileEVM somar escopo sem contar duas vezes.
    """
    regras = regras or Regras()
    agora = agora or datetime.now(timezone.utc)
    linhas_de_base = linhas_de_base or {}
    issues = snapshot.get("issues", {})
    releases = snapshot.get("releases", [])
    pais = ids_com_filhas(issues, regras)
    saida = []

    ordem = sorted(snapshot.get("sprints", []), key=lambda s: s.get("start_at") or "")
    for n, s in enumerate(ordem, start=1):
        status = status_da_sprint(s, agora, regras)
        inicio, fim = _dt(s["start_at"]), _dt(s["end_at"])
        if status == STATUS_FUTURA:
            if incluir_futuras:
                rel_id, rel_nome, rel_fonte = associar_release(s, set(s.get("issue_ids", [])), releases)
                saida.append({"sprint_id": s["sprint_id"], "sprint_label": f"S{n}", "sprint_name": s["sprint_name"],
                              "start_date": inicio, "end_date": fim, "status": status, "release_id": rel_id,
                              "release_name": rel_nome, "release_source": rel_fonte, "planned_ids": None,
                              "completed_ids": [], "scope_ids": [], "notes": "Sprint futura."})
            continue
        eventos = s.get("scope_changes") or []
        atuais = [i for i in dict.fromkeys(s.get("issue_ids", [])) if pontuavel(issues.get(i), regras, pais)]
        notas = []

        # planejado
        congelada = linhas_de_base.get(s["sprint_id"])
        if congelada:
            planejadas = congelada.get("issues", {})
            fonte_base = f"linha de base congelada em {congelada.get('congelado_em', '')[:10]}"
        else:
            base = linha_de_base(s, issues, regras)
            planejadas = base["issues"] if base else None
            fonte_base = base["fonte"] if base else "indisponível (sem histórico de escopo)"
        if s.get("falhas"):
            notas.append("Coleta incompleta desta sprint (" + ", ".join(s["falhas"]) + "): rode a coleta de novo.")
        if planejadas is None:
            notas.append("Planejado indisponível: sem histórico de escopo desta sprint.")

        # concluído
        candidatas = set(s.get("issue_ids", [])) | {e["issue_id"] for e in eventos if e.get("issue_id")}
        limite = min(fim, agora) if fim else agora
        concluidas = {}
        for iid in candidatas:
            i = issues.get(iid)
            if not pontuavel(i, regras, pais):
                continue
            quando = momento_conclusao(i, regras)
            if quando is None or not (inicio <= quando <= limite):
                continue
            na_sprint = (iid in membros_em(eventos, quando)) if eventos else (iid in s.get("issue_ids", []))
            if na_sprint:
                concluidas[iid] = i.get("estimate")
        if status == STATUS_ANDAMENTO:
            notas.append("Sprint em andamento: valores parciais, fora da média.")
        if status == STATUS_CANCELADA:
            notas.append("Sprint marcada como cancelada em planilhas/parametros.csv: fora da média.")
        sem_est = [i for i in atuais if issues[i].get("estimate") is None]
        if sem_est:
            notas.append(f"{len(sem_est)} issue(s) pontuável(is) sem estimativa na sprint (contam 0 SP).")
        sem_detalhe = [e["issue_id"] for e in eventos if e.get("issue_id") and e["issue_id"] not in issues]
        if sem_detalhe:
            notas.append(f"{len(set(sem_detalhe))} issue(s) do histórico sem detalhe (ignoradas).")

        ids_rel = set(s.get("issue_ids", [])) | set(planejadas or {})
        rel_id, rel_nome, rel_fonte = associar_release(s, ids_rel, releases)

        planned_sp = sum(_sp(v) for v in planejadas.values()) if planejadas is not None else None
        completed_sp = sum(_sp(v) for v in concluidas.values())
        fora_do_plano = {k: v for k, v in concluidas.items() if planejadas is None or k not in planejadas}
        if eventos:
            passaram = set(membros_em(eventos, inicio)) | {
                e["issue_id"] for e in eventos if e.get("action") == "ISSUE_ADDED" and e.get("issue_id")
                and inicio <= (_dt(e.get("effective_at")) or inicio) <= limite}
        else:
            passaram = set(s.get("issue_ids", []))
        escopo = sorted(i for i in passaram if pontuavel(issues.get(i), regras, pais))
        saida.append({
            "sprint_id": s["sprint_id"],
            "sprint_label": f"S{n}",
            "sprint_name": s["sprint_name"],
            "start_date": inicio,
            "end_date": fim,
            "status": status,
            "release_id": rel_id,
            "release_name": rel_nome,
            "release_source": rel_fonte,
            "planned_story_points": planned_sp,
            "planned_issues": len(planejadas) if planejadas is not None else None,
            "planned_unestimated_issues": sum(v is None for v in planejadas.values()) if planejadas is not None else None,
            "baseline_source": fonte_base,
            "current_story_points": sum(_sp(issues[i].get("estimate")) for i in atuais),
            "current_issues": len(atuais),
            "completed_story_points": completed_sp,
            "completed_issues": len(concluidas),
            "completed_unestimated_issues": sum(v is None for v in concluidas.values()),
            "completed_unplanned_story_points": sum(_sp(v) for v in fora_do_plano.values()),
            "velocity": completed_sp,
            "completion_rate": calculate_completion_rate(planned_sp, completed_sp),
            "zenhub_completed_points": s.get("zenhub_completed_points"),
            "planned_ids": sorted(planejadas) if planejadas is not None else None,
            "completed_ids": sorted(concluidas),
            "scope_ids": sorted(set(escopo) | set(planejadas or {}) | set(concluidas)),
            "notes": " ".join(notas),
        })
    return pd.DataFrame(saida)


def calculate_average_velocity(df: pd.DataFrame, minimo: int = 2) -> dict:
    """Média da velocity das sprints concluídas. ``valor`` é None sem histórico suficiente."""
    if df is None or df.empty:
        return {"valor": None, "n": 0, "sprints": [], "motivo": "nenhuma sprint"}
    base = df[df["status"] == STATUS_CONCLUIDA]
    n = len(base)
    if n < max(1, minimo):
        return {"valor": None, "n": n, "sprints": list(base["sprint_label"]),
                "motivo": f"histórico insuficiente ({n} sprint(s) concluída(s); mínimo {minimo})"}
    return {"valor": float(base["velocity"].sum()) / n, "n": n, "sprints": list(base["sprint_label"]), "motivo": ""}


def calculate_completion_rate(planned, completed) -> float | None:
    """completed / planned * 100; None quando o planejado é zero ou desconhecido."""
    if planned is None or completed is None:
        return None
    try:
        if pd.isna(planned) or float(planned) == 0:
            return None
    except TypeError:
        return None
    return float(completed) / float(planned) * 100
