"""Gestão ágil orientada a evidências: planejado × realizado por Story, com rastreabilidade.

Tudo aqui parte de duas saídas já calculadas e testadas:

* ``velocity.calculate_velocity`` — por sprint: o planejado congelado na planning
  (``planned_estimates``), o concluído (``completed_ids``) e o escopo;
* ``agile.universo_issues`` — por issue: título, link, tipo, épico, status, datas.

A função central, :func:`stories_por_sprint`, abre cada sprint em uma linha por
Story (issue pontuável), e todo número agregado da página sai da soma dessas
linhas. Assim qualquer total pode ser rastreado até as issues:
Release → Sprint → Épico → Story → SP → status → resultado.

Regras (as mesmas da velocity, para os totais baterem):

* **Planejada** = estava na sprint ao fim da janela de planning; SP planejado =
  estimativa daquele momento (a do evento de entrada, ou a atual para quem já
  estava na sprint no início, porque o Zenhub não guarda a antiga).
* **Realizada** = fechada dentro da sprint (até o prazo de fechamento), estando
  nela; SP realizado = estimativa atual.
* **Adicionada** = entrou depois da janela de planning; **removida** = saiu antes
  do fim sem ter sido concluída; **levada** = não concluída e presente na sprint
  seguinte.

Nada é estimado: estimativa ausente vale 0 SP e é sinalizada.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.metrics import velocity as vel

BRT = timezone(timedelta(hours=-3))

PLANEJADA_CONCLUIDA = "Planejada e concluída"
PLANEJADA_NAO_CONCLUIDA = "Planejada, não concluída"
ADICIONADA_CONCLUIDA = "Adicionada depois da planning e concluída"
ADICIONADA_NAO_CONCLUIDA = "Adicionada depois da planning, não concluída"
REMOVIDA = "Removida da sprint"
EM_ANDAMENTO = "Sprint em andamento"
RESULTADOS = [PLANEJADA_CONCLUIDA, PLANEJADA_NAO_CONCLUIDA, ADICIONADA_CONCLUIDA, ADICIONADA_NAO_CONCLUIDA, REMOVIDA]

# limites das análises qualitativas (interpretação, não regra de negócio)
LIMITE_DIFERENCA = 0.30        # |realizado − planejado| ÷ planejado
LIMITE_OVERCOMMIT = 1.30       # planejado ÷ velocity média das sprints anteriores
LIMITE_VARIACAO_VELOCITY = 0.50
LIMITE_CONCENTRACAO = 0.50     # parcela do SP nas 20% maiores stories
LIMITE_ESCOPO = 0.20           # SP adicionado ÷ SP planejado


def _dt(v):
    return vel._dt(v)


def _num(v) -> float:
    try:
        return 0.0 if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return 0.0


def _local(ts):
    return None if ts is None or pd.isna(ts) else pd.Timestamp(ts).tz_convert(BRT).tz_localize(None)


# ───────────────────────── linhas Story × Sprint ─────────────────────────

COLUNAS = ["release", "sprint", "sprint_nome", "sprint_status", "sprint_inicio", "sprint_fim", "epico", "issue",
           "numero", "repositorio", "titulo", "url", "tipo", "planejada", "sp_planejado", "concluida", "sp_realizado",
           "sp_atual", "sem_estimativa_na_planning", "sem_estimativa", "adicionada", "entrou_em", "removida", "saiu_em", "levada_para",
           "resultado", "status_atual", "pipeline", "criada_em", "concluida_em", "responsavel", "release_da_issue",
           "issue_id", "sprint_id", "ordem_sprint"]


def stories_por_sprint(snap: dict | None, sprints: pd.DataFrame, universo: pd.DataFrame,
                       regras: vel.Regras | None = None) -> pd.DataFrame:
    """Uma linha por (sprint iniciada, Story pontuável que passou por ela)."""
    regras = regras or vel.Regras()
    if not snap or sprints is None or sprints.empty:
        return pd.DataFrame(columns=COLUNAS)
    issues = snap.get("issues", {})
    por_id = {s["sprint_id"]: s for s in snap.get("sprints", [])}
    info = universo.set_index("issue_id") if universo is not None and not universo.empty else pd.DataFrame()
    ordem = sprints.sort_values("start_date").reset_index(drop=True)
    linhas = []
    for n, r in enumerate(ordem.itertuples()):
        s = por_id.get(r.sprint_id)
        if s is None or r.status == vel.STATUS_FUTURA:
            continue
        eventos = sorted(s.get("scope_changes") or [], key=lambda e: e.get("effective_at") or "")
        iniciais = vel.membros_iniciais(s, issues)
        planejadas = r.planned_estimates if isinstance(r.planned_estimates, dict) else None
        concluidas = set(r.completed_ids or [])
        escopo = set(r.scope_ids or []) | set(planejadas or {}) | concluidas
        inicio, fim = r.start_date, r.end_date
        corte = r.planning_cutoff if r.planning_cutoff is not None and not pd.isna(r.planning_cutoff) else inicio
        ate = r.count_until if r.count_until is not None and not pd.isna(r.count_until) else fim
        no_fim = set(vel.membros_em(eventos, fim, iniciais)) if fim is not None else set(s.get("issue_ids") or [])
        for iid in sorted(escopo):
            i = issues.get(iid) or {}
            evs = [e for e in eventos if e.get("issue_id") == iid]
            entradas = [_dt(e["effective_at"]) for e in evs if e.get("action") == "ISSUE_ADDED"]
            saidas = [_dt(e["effective_at"]) for e in evs if e.get("action") == "ISSUE_REMOVED"]
            planejada = planejadas is not None and iid in planejadas
            concluida = iid in concluidas
            adicionada = (not planejada) and any(x is not None and x > corte for x in entradas)
            entrou = inicio if iid in iniciais else (min(entradas) if entradas else None)
            removida = (not concluida) and iid not in no_fim and bool(saidas)
            if concluida:
                resultado = PLANEJADA_CONCLUIDA if planejada else ADICIONADA_CONCLUIDA
            elif removida:
                resultado = REMOVIDA
            elif r.status == vel.STATUS_ANDAMENTO:
                resultado = EM_ANDAMENTO
            else:
                resultado = PLANEJADA_NAO_CONCLUIDA if planejada else ADICIONADA_NAO_CONCLUIDA
            est_atual = i.get("estimate")
            est_plan = planejadas.get(iid) if planejada else None
            m = info.loc[iid] if iid in info.index else {}
            g = (lambda c, d=None: m.get(c, d) if isinstance(m, dict) else (m[c] if c in m.index else d))
            linhas.append({
                "release": r.release_name or "Sem release", "sprint": r.sprint_label, "sprint_nome": r.sprint_name,
                "sprint_status": r.status, "sprint_inicio": inicio, "sprint_fim": fim,
                "epico": g("epico", "Sem épico"), "issue": f"{i.get('repository', '')}#{i.get('number', '')}",
                "numero": i.get("number"), "repositorio": i.get("repository"), "titulo": i.get("title"),
                "url": i.get("url"), "tipo": i.get("issue_type"), "planejada": planejada,
                "sp_planejado": _num(est_plan) if planejada else None,
                "concluida": concluida, "sp_realizado": _num(est_atual) if concluida else None,
                "sp_atual": est_atual, "sem_estimativa_na_planning": planejada and est_plan is None,
                "sem_estimativa": est_atual is None,
                "adicionada": adicionada, "entrou_em": entrou, "removida": removida,
                "saiu_em": max(x for x in saidas if x is not None) if removida else None, "levada_para": None,
                "resultado": resultado, "status_atual": g("situacao"), "pipeline": g("pipeline", i.get("pipeline")),
                "criada_em": pd.to_datetime(g("created_at"), utc=True, errors="coerce"),
                "concluida_em": _dt(i.get("closed_at")) if i.get("state") == "CLOSED" else None,
                "responsavel": g("responsavel"), "release_da_issue": g("release"),
                "issue_id": iid, "sprint_id": r.sprint_id, "ordem_sprint": n,
                "_ate": ate})
    df = pd.DataFrame(linhas)
    if df.empty:
        return pd.DataFrame(columns=COLUNAS)
    # levada: não concluída (nem removida) e presente na sprint seguinte
    por_sprint = df.groupby("ordem_sprint")["issue_id"].apply(set).to_dict()
    rotulo = df.drop_duplicates("ordem_sprint").set_index("ordem_sprint")["sprint"].to_dict()
    for idx, x in df.iterrows():
        prox = x["ordem_sprint"] + 1
        if not x["concluida"] and not x["removida"] and x["issue_id"] in por_sprint.get(prox, set()):
            df.at[idx, "levada_para"] = rotulo[prox]
    return df.drop(columns="_ate")[COLUNAS]


# ───────────────────────── agregados ─────────────────────────

def resumo_por_sprint(linhas: pd.DataFrame) -> pd.DataFrame:
    """Planejado × realizado por sprint, somando as linhas (é o que a velocity mostra)."""
    if linhas is None or linhas.empty:
        return pd.DataFrame()
    g = linhas.groupby(["ordem_sprint", "sprint", "sprint_nome", "release", "sprint_status", "sprint_inicio",
                        "sprint_fim"], dropna=False)
    out = g.apply(lambda x: pd.Series({
        "stories_planejadas": int(x["planejada"].sum()),
        "sp_planejado": x["sp_planejado"].sum(min_count=1),
        "stories_concluidas": int(x["concluida"].sum()),
        "sp_realizado": x["sp_realizado"].fillna(0).sum(),
        "sp_realizado_do_plano": x.loc[x["planejada"], "sp_realizado"].fillna(0).sum(),
        "sp_realizado_fora_do_plano": x.loc[~x["planejada"], "sp_realizado"].fillna(0).sum(),
        "stories_adicionadas": int(x["adicionada"].sum()),
        "sp_adicionado": x.loc[x["adicionada"], "sp_atual"].map(_num).sum(),
        "stories_removidas": int(x["removida"].sum()),
        "sp_removido": x.loc[x["removida"], "sp_atual"].map(_num).sum(),
        "stories_levadas": int(x["levada_para"].notna().sum()),
        "sem_estimativa_na_planning": int(x["sem_estimativa_na_planning"].sum()),
        "sem_estimativa": int(x["sem_estimativa"].sum()),
    }), include_groups=False).reset_index()
    out["diferenca"] = out["sp_realizado"] - out["sp_planejado"]
    out["taxa"] = out.apply(lambda r: r["sp_realizado"] / r["sp_planejado"] * 100
                            if r["sp_planejado"] and not pd.isna(r["sp_planejado"]) else None, axis=1)
    return out.sort_values("ordem_sprint").reset_index(drop=True)


def resumo_por_release(por_sprint: pd.DataFrame) -> pd.DataFrame:
    if por_sprint is None or por_sprint.empty:
        return pd.DataFrame()
    g = por_sprint.groupby("release", sort=False).agg(
        sprints=("sprint", lambda s: ", ".join(s)), sp_planejado=("sp_planejado", lambda s: s.sum(min_count=1)),
        sp_realizado=("sp_realizado", "sum"), stories_planejadas=("stories_planejadas", "sum"),
        stories_concluidas=("stories_concluidas", "sum")).reset_index()
    g["diferenca"] = g["sp_realizado"] - g["sp_planejado"]
    g["taxa"] = g.apply(lambda r: r["sp_realizado"] / r["sp_planejado"] * 100 if r["sp_planejado"] else None, axis=1)
    return g


def hierarquia(linhas: pd.DataFrame) -> pd.DataFrame:
    """Release → Sprint → Épico com planejado, realizado e as stories de cada nó."""
    if linhas is None or linhas.empty:
        return pd.DataFrame()
    g = linhas.groupby(["ordem_sprint", "release", "sprint", "epico"], dropna=False).apply(
        lambda x: pd.Series({"stories": len(x), "sp_planejado": x["sp_planejado"].sum(min_count=1),
                             "sp_realizado": x["sp_realizado"].fillna(0).sum(),
                             "issues": _lista(x)}),
        include_groups=False).reset_index()
    return g.sort_values(["ordem_sprint", "sp_realizado"], ascending=[True, False]).drop(columns="ordem_sprint")


def tendencia(por_sprint: pd.DataFrame, minimo: int = 3) -> dict:
    """Inclinação (SP por sprint) da velocity nas sprints concluídas, por mínimos quadrados."""
    c = por_sprint[por_sprint["sprint_status"] == vel.STATUS_CONCLUIDA] if por_sprint is not None and \
        not por_sprint.empty else pd.DataFrame()
    if len(c) < minimo:
        return {"valor": None, "motivo": f"exige {minimo} sprints concluídas (há {len(c)})"}
    x = pd.Series(range(len(c)), dtype=float)
    y = c["sp_realizado"].reset_index(drop=True).astype(float)
    inclinacao = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
    sentido = "subindo" if inclinacao > 0.5 else ("caindo" if inclinacao < -0.5 else "estável")
    return {"valor": float(inclinacao), "sentido": sentido, "n": len(c)}


def entregas_no_tempo(linhas: pd.DataFrame) -> pd.DataFrame:
    """SP realizados por dia de conclusão (Brasília), com o acumulado."""
    c = linhas[linhas["concluida"]].copy() if linhas is not None and not linhas.empty else pd.DataFrame()
    if c.empty:
        return pd.DataFrame(columns=["dia", "sp", "stories", "acumulado"])
    c["dia"] = c["concluida_em"].map(lambda t: _local(t).normalize())
    d = c.groupby("dia").agg(sp=("sp_realizado", "sum"), stories=("issue", "count")).reset_index()
    d["acumulado"] = d["sp"].cumsum()
    return d


def planejado_no_tempo(por_sprint: pd.DataFrame) -> pd.DataFrame:
    """SP planejados e realizados por sprint, posicionados na data de início (para o eixo de tempo)."""
    if por_sprint is None or por_sprint.empty:
        return pd.DataFrame()
    d = por_sprint.copy()
    d["inicio"] = d["sprint_inicio"].map(lambda t: _local(t).normalize())
    return d


# ───────────────────────── burndown ─────────────────────────

def burndown(snap: dict, sprint: pd.Series, regras: vel.Regras | None = None,
             agora: datetime | None = None) -> dict:
    """Trabalho restante ao fim de cada dia da sprint, só com dados do histórico.

    Escopo em cada momento = issues pontuáveis na sprint pelo ``scopeChange`` (quem já
    estava no início + entradas − saídas), com a estimativa do evento de entrada (ou
    a atual para quem já estava). Feito = issue da velocity fechada até aquele momento.
    Restante = escopo − feito. Ideal = planejado da planning até 0 no último dia.
    """
    regras = regras or vel.Regras()
    agora = agora or datetime.now(timezone.utc)
    s = next((x for x in snap.get("sprints", []) if x["sprint_id"] == sprint["sprint_id"]), None)
    if s is None or sprint["start_date"] is None or sprint["end_date"] is None:
        return {"dados": pd.DataFrame(), "motivo": "sprint sem datas de início e fim"}
    issues = snap.get("issues", {})
    pais = vel.ids_com_filhas(issues, regras)
    eventos = s.get("scope_changes") or []
    iniciais = vel.membros_iniciais(s, issues)
    concluidas = set(sprint["completed_ids"] or [])
    inicio, fim = sprint["start_date"], sprint["end_date"]
    ate = sprint.get("count_until") if sprint.get("count_until") is not None else fim
    planejado = sprint.get("planned_story_points")
    dia0 = _local(inicio).normalize()
    ultimo = _local(fim - timedelta(seconds=1)).normalize()
    dias = pd.date_range(dia0, ultimo, freq="D")
    linhas = []
    for k, d in enumerate(dias):
        momento = min((d + pd.Timedelta(days=1)).tz_localize(BRT).tz_convert("UTC").to_pydatetime(), ate)
        if d == ultimo:
            momento = ate            # o último dia vai até o prazo de fechamento
        if momento > agora:
            real = None
            escopo_sp = None
        else:
            membros = vel.membros_em(eventos, min(momento, fim), iniciais)
            membros = {i: v for i, v in membros.items() if vel.pontuavel(issues.get(i), regras, pais)}
            # concluída que já saiu da sprint pelo histórico ainda conta como feita
            feitos = {i for i in concluidas if (issues.get(i) or {}).get("closed_at")
                      and _dt(issues[i]["closed_at"]) <= momento}
            escopo = {**{i: _num(v) for i, v in membros.items()},
                      **{i: _num((issues.get(i) or {}).get("estimate")) for i in feitos}}
            escopo_sp = sum(escopo.values())
            real = escopo_sp - sum(_num((issues.get(i) or {}).get("estimate")) for i in feitos)
        ideal = None
        if planejado is not None and not pd.isna(planejado):
            ideal = planejado * (1 - k / max(len(dias) - 1, 1))
        linhas.append({"dia": d, "ideal": ideal, "restante": real, "escopo": escopo_sp})
    return {"dados": pd.DataFrame(linhas), "motivo": None, "inicio": dia0, "fim": ultimo,
            "planejado": planejado, "prazo": _local(ate)}


# ───────────────────────── análises qualitativas ─────────────────────────

def rotulo_issue(issue: str) -> str:
    """'2026.2-MeasureSoftGram-DOC#42' -> 'DOC#42'."""
    return str(issue).split("-")[-1]


def _lista(x: pd.DataFrame) -> list[tuple[str, str | None]]:
    """[(rótulo, url)] das issues, para a tela mostrar cada uma como link."""
    return [(rotulo_issue(i), u if isinstance(u, str) and u else None)
            for i, u in zip(x["issue"], x["url"] if "url" in x else [None] * len(x))]


def analises(por_sprint: pd.DataFrame, linhas: pd.DataFrame) -> pd.DataFrame:
    """Fatos observados (números das linhas) e a interpretação possível de cada um."""
    out = []
    if por_sprint is None or por_sprint.empty:
        return pd.DataFrame(columns=["tema", "sprint", "fato", "interpretacao", "issues"])

    def add(tema, sprint, fato, interp, issues=None):
        out.append({"tema": tema, "sprint": sprint, "fato": fato, "interpretacao": interp, "issues": issues or []})

    concl = por_sprint[por_sprint["sprint_status"] == vel.STATUS_CONCLUIDA].reset_index(drop=True)
    for k, r in concl.iterrows():
        x = linhas[linhas["sprint"] == r["sprint"]]
        plan = r["sp_planejado"]
        if plan and not pd.isna(plan):
            dif = (r["sp_realizado"] - plan) / plan
            if abs(dif) >= LIMITE_DIFERENCA:
                nao = x[x["resultado"] == PLANEJADA_NAO_CONCLUIDA]
                add("Diferença planejado × realizado", r["sprint"],
                    f"planejado {plan:.0f} SP, realizado {r['sp_realizado']:.0f} SP ({dif * 100:+.0f}%); "
                    f"{len(nao)} story(ies) planejada(s) não concluída(s)",
                    "o time entregou bem menos do que se comprometeu" if dif < 0
                    else "entrou mais trabalho do que o planejado, ou o planejado estava subestimado",
                    _lista(nao) if len(nao) else [])
        anteriores = concl.iloc[:k]
        media_ant = anteriores["sp_realizado"].mean() if len(anteriores) else None
        if media_ant and plan and plan / media_ant >= LIMITE_OVERCOMMIT:
            add("Possível overcommitment", r["sprint"],
                f"planejado {plan:.0f} SP contra velocity média de {media_ant:.0f} SP nas sprints anteriores "
                f"({plan / media_ant:.1f}×)", "o compromisso ficou acima do histórico de entrega do time")
        elif plan and not len(anteriores):
            pass
        if k and concl.loc[k - 1, "sp_realizado"] is not None:
            ant = concl.loc[k - 1, "sp_realizado"]
            base = max(ant, 1)
            if abs(r["sp_realizado"] - ant) / base >= LIMITE_VARIACAO_VELOCITY:
                add("Variação de velocity", r["sprint"],
                    f"velocity foi de {ant:.0f} SP ({concl.loc[k - 1, 'sprint']}) para {r['sp_realizado']:.0f} SP",
                    "mudança grande de ritmo: conferir se houve mudança de escopo, de time ou de critério de "
                    "estimativa antes de tirar conclusão")
        if plan and r["sp_adicionado"] / plan >= LIMITE_ESCOPO:
            ad = x[x["adicionada"]]
            add("Mudança de escopo durante a sprint", r["sprint"],
                f"{int(r['stories_adicionadas'])} story(ies) ({r['sp_adicionado']:.0f} SP) entraram depois da "
                f"planning, {r['sp_adicionado'] / plan * 100:.0f}% do planejado; {int(r['stories_removidas'])} "
                "removida(s)", "o planejamento não se manteve estável durante a sprint", _lista(ad))
        feitas = x[x["concluida"] & (x["sp_realizado"].fillna(0) > 0)].sort_values("sp_realizado", ascending=False)
        if len(feitas) >= 5 and r["sp_realizado"]:
            topo = feitas.head(max(1, round(len(feitas) * 0.2)))
            parte = topo["sp_realizado"].sum() / r["sp_realizado"]
            if parte >= LIMITE_CONCENTRACAO:
                add("Concentração de pontos", r["sprint"],
                    f"{len(topo)} de {len(feitas)} stories concluídas somam {parte * 100:.0f}% do realizado",
                    "o resultado da sprint depende de poucas stories grandes: atraso numa delas pesa muito",
                    _lista(topo))
    levadas = linhas[linhas["levada_para"].notna()]
    for spr, x in levadas.groupby("sprint", sort=False):
        add("Stories levadas para a sprint seguinte", spr,
            f"{len(x)} story(ies) ({x['sp_atual'].map(_num).sum():.0f} SP) não concluída(s) e presentes na "
            f"{x['levada_para'].iloc[0]}", "trabalho iniciado e não terminado passa de sprint em sprint", _lista(x))
    nao = linhas[linhas["resultado"].isin([PLANEJADA_NAO_CONCLUIDA, ADICIONADA_NAO_CONCLUIDA])]
    rec = nao.groupby("issue_id").filter(lambda g: len(g) >= 2).drop_duplicates("issue_id")
    if len(rec):
        add("Não conclusão recorrente", "várias",
            f"{len(rec)} story(ies) ficaram sem concluir em 2 ou mais sprints",
            "itens grandes demais, bloqueados ou sem responsável: vale quebrar ou revisar", _lista(rec))
    sem_p = linhas[linhas["sem_estimativa_na_planning"]]
    for spr, x in sem_p.groupby("sprint", sort=False):
        add("Dado ausente", spr, f"{len(x)} story(ies) planejada(s) sem estimativa no momento da planning "
            "contam 0 SP no planejado", "o planejado desta sprint está subestimado", _lista(x))
    sem = linhas[linhas["sem_estimativa"]].drop_duplicates("issue_id")
    if len(sem):
        add("Dado ausente", "várias", f"{len(sem)} story(ies) seguem sem estimativa e contam 0 SP",
            "planejado e realizado ficam subestimados até alguém estimar", _lista(sem))
    return pd.DataFrame(out)
