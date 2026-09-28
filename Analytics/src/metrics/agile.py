"""Métricas de gestão ágil a partir do snapshot do Zenhub.

Funções puras (sem Streamlit, sem rede), testadas em ``tests/test_agile.py``.

**Universo de issues.** Quando o snapshot tem ``backlog`` (coleta v2, todos os
pipelines do quadro), ele é a base dos itens abertos; as issues fechadas vêm das
sprints. Sem ``backlog`` (coleta v1), o universo são só as issues que passaram
por alguma sprint — e ``universo_issues`` devolve ``completo=False`` para que a
página diga isso em vez de apresentar como backlog inteiro.

**Situação.** Cada pipeline do Zenhub cai em uma de três situações
(``SITUACAO_PIPELINE``): *Planejado*, *Em andamento* ou *Concluído*. Issue
fechada é sempre *Concluído* — e só ela: o critério de feito é a issue estar
fechada. Issue aberta no pipeline Done aparece como *Em andamento* (aguardando
fechamento). Pipeline que não está no mapa aparece como
*Não classificado* — nunca é encaixado à força.

**Throughput** = itens pontuáveis concluídos por semana (contagem) e os pontos
deles. **Progresso do épico** = filhas concluídas ÷ filhas. **Progresso da
release** = issues da release concluídas ÷ issues da release.
"""

from __future__ import annotations

import pandas as pd

PLANEJADO, ANDAMENTO, CONCLUIDO, NAO_CLASSIFICADO = "Planejado", "Em andamento", "Concluído", "Não classificado"
SITUACOES = [PLANEJADO, ANDAMENTO, CONCLUIDO, NAO_CLASSIFICADO]

SITUACAO_PIPELINE = {
    "New Issues": PLANEJADO,
    "Icebox": PLANEJADO,
    "Product Backlog": PLANEJADO,
    "Aguardando Validação do PO (DoR)": PLANEJADO,
    "Sprint Backlog": PLANEJADO,
    "In Progress": ANDAMENTO,
    "Review/QA": ANDAMENTO,
    "Aguardando aprovação do PO (DoD)": ANDAMENTO,
    "Migração de repositório": ANDAMENTO,
    "Done": ANDAMENTO,          # aberta no Done: ainda não fechada, não conta como feita
}


def _para_data(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, utc=True, errors="coerce")


def universo_issues(snap: dict | None) -> tuple[pd.DataFrame, bool]:
    """(uma linha por issue, backlog completo?). Pull requests ficam de fora."""
    if not snap:
        return pd.DataFrame(), False
    backlog = snap.get("backlog") or None
    registros: dict[str, dict] = {i: dict(v) for i, v in (snap.get("issues") or {}).items()}
    completo = bool(backlog and backlog.get("issues") is not None and not backlog.get("pipelines_com_falha"))
    if backlog:
        for b in backlog.get("issues") or []:
            atual = registros.get(b["issue_id"], {})
            registros[b["issue_id"]] = {**atual, **{k: v for k, v in b.items() if v is not None}}
    if not registros:
        return pd.DataFrame(), completo
    df = pd.DataFrame(list(registros.values()))
    for col in ("created_at", "priority", "assignees", "pipeline", "closed_at", "pipeline_moved_at", "parent_id",
                "issue_type", "estimate", "repository", "state", "is_pull_request"):
        if col not in df:
            df[col] = None
    df = df[~df["is_pull_request"].fillna(False).astype(bool)].copy()

    def situacao(r):
        if r["state"] == "CLOSED":
            return CONCLUIDO
        return SITUACAO_PIPELINE.get(r["pipeline"], NAO_CLASSIFICADO)

    df["situacao"] = df.apply(situacao, axis=1)
    df["concluida_em"] = _para_data(df["closed_at"]).where(df["state"] == "CLOSED")
    df["tipo"] = df["issue_type"].fillna("Sem tipo")
    df["prioridade"] = df["priority"].fillna("Sem prioridade")
    df["responsavel"] = df["assignees"].map(lambda a: ", ".join(a) if isinstance(a, list) and a else "Sem responsável")
    df["repositorio"] = df["repository"].fillna("—")
    df["pipeline"] = df["pipeline"].where(df["pipeline"].notna(),
                                          df["state"].map(lambda e: "Fechada" if e == "CLOSED" else "Sem pipeline"))
    df["pontos"] = pd.to_numeric(df["estimate"], errors="coerce")

    # épico de cada issue: sobe pela cadeia de pais até achar um Epic (no máximo 4 níveis)
    tipo = dict(zip(df["issue_id"], df["issue_type"]))
    pai = dict(zip(df["issue_id"], df["parent_id"]))
    titulo = dict(zip(df["issue_id"], df["title"]))

    def epico(iid):
        atual = pai.get(iid)
        for _ in range(4):
            if not atual:
                return None
            if tipo.get(atual) == "Epic":
                return atual
            atual = pai.get(atual)
        return None

    df["epico_id"] = df["issue_id"].map(epico)
    df["epico"] = df["epico_id"].map(lambda e: titulo.get(e) if e else None).fillna("Sem épico")

    # release: issues ligadas a cada release do Zenhub
    rel = {}
    for r in snap.get("releases") or []:
        for iid in r.get("issue_ids") or []:
            rel.setdefault(iid, r.get("release_name"))
    df["release"] = df["issue_id"].map(rel).fillna("Sem release")

    # sprint: a sprint mais recente em que a issue está
    sprint_de = {}
    for n, s in enumerate(sorted(snap.get("sprints") or [], key=lambda s: s.get("start_at") or ""), start=1):
        for iid in s.get("issue_ids") or []:
            sprint_de[iid] = f"S{n}"
    df["sprint"] = df["issue_id"].map(sprint_de).fillna("Sem sprint")
    return df.reset_index(drop=True), completo


def distribuicao(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Contagem e pontos por valor de ``coluna``, com a situação empilhada."""
    if df is None or df.empty or coluna not in df:
        return pd.DataFrame(columns=[coluna, "situacao", "itens", "pontos"])
    g = (df.groupby([coluna, "situacao"], dropna=False)
         .agg(itens=("issue_id", "count"), pontos=("pontos", "sum")).reset_index())
    return g


def throughput_semanal(df: pd.DataFrame, tipos_pontuados: set) -> pd.DataFrame:
    """Itens pontuáveis concluídos por semana (segunda a domingo, horário de Brasília)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["semana", "itens", "pontos", "sem_estimativa"])
    d = df[df["concluida_em"].notna() & df["issue_type"].isin(tipos_pontuados)].copy()
    if d.empty:
        return pd.DataFrame(columns=["semana", "itens", "pontos", "sem_estimativa"])
    local = d["concluida_em"].dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    d["semana"] = (local - pd.to_timedelta(local.dt.weekday, unit="D")).dt.normalize()
    return (d.groupby("semana").agg(itens=("issue_id", "count"), pontos=("pontos", "sum"),
                                    sem_estimativa=("pontos", lambda s: int(s.isna().sum())))
            .reset_index().sort_values("semana"))


def progresso_epicos(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por épico: filhas, concluídas, pontos e % concluído (por contagem)."""
    if df is None or df.empty:
        return pd.DataFrame()
    epicos = df[df["issue_type"] == "Epic"][["issue_id", "title", "number", "repositorio", "situacao"]]
    filhas = df[df["epico_id"].notna()]
    linhas = []
    for e in epicos.itertuples():
        f = filhas[filhas["epico_id"] == e.issue_id]
        total, feitas = len(f), int((f["situacao"] == CONCLUIDO).sum())
        linhas.append({"epico": e.title, "numero": e.number, "repositorio": e.repositorio, "situacao": e.situacao,
                       "filhas": total, "concluidas": feitas, "em_andamento": int((f["situacao"] == ANDAMENTO).sum()),
                       "pontos": f["pontos"].sum(min_count=1),
                       "pontos_concluidos": f.loc[f["situacao"] == CONCLUIDO, "pontos"].sum(min_count=1),
                       "progresso": feitas / total if total else None})
    return pd.DataFrame(linhas).sort_values(["progresso", "filhas"], ascending=[True, False], na_position="last")


def progresso_releases(snap: dict | None, df: pd.DataFrame) -> pd.DataFrame:
    """Releases do Zenhub: issues, concluídas, pontos e datas."""
    if not snap or df is None or df.empty:
        return pd.DataFrame()
    base = df.set_index("issue_id")
    linhas = []
    for r in snap.get("releases") or []:
        ids = [i for i in (r.get("issue_ids") or []) if i in base.index]
        sub = base.loc[ids] if ids else base.iloc[0:0]
        total, feitas = len(sub), int((sub["situacao"] == CONCLUIDO).sum()) if len(sub) else 0
        linhas.append({"release": r.get("release_name"), "estado": r.get("state"), "inicio": r.get("start_on"),
                       "fim": r.get("end_on"), "issues": total, "concluidas": feitas,
                       "pontos": sub["pontos"].sum(min_count=1) if len(sub) else None,
                       "pontos_concluidos": sub.loc[sub["situacao"] == CONCLUIDO, "pontos"].sum(min_count=1)
                       if len(sub) else None,
                       "progresso": feitas / total if total else None,
                       "issues_no_zenhub": r.get("issues_count")})
    return pd.DataFrame(linhas)


def media_movel(valores: pd.Series, janela: int = 3) -> pd.Series:
    """Média móvel simples; só existe quando há ``janela`` valores (não completa com zero)."""
    return valores.rolling(janela, min_periods=janela).mean()


def alertas_de_dados(df: pd.DataFrame, tipos_pontuados: set) -> pd.DataFrame:
    """Issues cujo cadastro no Zenhub distorce os números (o painel não corrige: aponta).

    * sem tipo, mas com filhas — se for épico, some da lista de épicos e as filhas
      ficam "Sem épico";
    * sem tipo, com estimativa — os pontos não contam (só Feature, Task e Bug pontuam);
    * épico com estimativa — épico não pontua, a estimativa é ignorada;
    * pontuável sem estimativa — conta como 0 SP no planejado e no concluído.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["numero", "titulo", "repositorio", "tipo", "problema", "url"])
    pais = set(df["parent_id"].dropna())
    linhas = []
    for r in df.itertuples():
        tipo, est = r.issue_type, r.pontos
        problemas = []
        if not tipo and r.issue_id in pais:
            problemas.append("sem tipo, mas tem filhas: se for épico, marque o tipo Epic no Zenhub")
        if not tipo and pd.notna(est):
            problemas.append(f"tem estimativa ({est:g} SP) mas não tem tipo: os pontos não contam")
        if tipo == "Epic" and pd.notna(est):
            problemas.append(f"épico com estimativa ({est:g} SP): épico não pontua, a estimativa é ignorada")
        if tipo in tipos_pontuados and pd.isna(est) and r.issue_id not in pais:
            problemas.append("sem estimativa: conta 0 SP")
        for pr in problemas:
            linhas.append({"numero": r.number, "titulo": r.title, "repositorio": r.repositorio,
                           "tipo": tipo or "Sem tipo", "problema": pr, "url": getattr(r, "url", None)})
    return pd.DataFrame(linhas)
