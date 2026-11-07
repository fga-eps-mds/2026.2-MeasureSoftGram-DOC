"""Métricas de fluxo (Kanban) do trabalho técnico e dos defeitos — DA-R3.02.

Task, Sub-task, Bug e issue sem tipo não pontuam no Velocity nem no Agile EVM (só a US aceita pelo PO
pontua, ver ``velocity.py``). Em vez de story points, o trabalho técnico é acompanhado pelo fluxo:

* **Throughput**: itens concluídos por semana (segunda a domingo, horário de Brasília);
* **Lead Time**: da criação da issue até o fechamento (mediana e percentil 85, em dias);
* **Cycle Time**: da **primeira entrada em In Progress** (``config.FLUXO``) até o fechamento, pelo histórico de
  transferências de pipeline do Zenhub (``snapshot["transferencias_pipeline"]``). Só entram issues fechadas
  que passaram por In Progress e que não foram movidas para lá em cima da hora de fechar (menos de
  ``cycle_minimo_min``); as demais são contadas à parte e a cobertura aparece na tela, sem estimar um início.
  Sem o histórico no snapshot, o Cycle Time fica "coleta pendente";
* **Taxa de conclusão**: fechadas ÷ ativas no período (Q-Rapids, *Development Task Completion*).

Funções puras (sem Streamlit e sem rede), testadas em ``tests/test_fluxo.py``. Nenhuma delas usa story points.
"""

from __future__ import annotations

import pandas as pd

import config

TIPOS_FLUXO = ("Task", "Sub-task", "Bug", "Sem tipo")
FUSO = "America/Sao_Paulo"


def _local(serie: pd.Series) -> pd.Series:
    s = pd.to_datetime(serie, utc=True, errors="coerce")
    try:
        return s.dt.tz_convert(FUSO).dt.tz_localize(None)
    except Exception:  # noqa: BLE001 — sem base de fusos no navegador
        return s.dt.tz_convert(None) - pd.Timedelta(hours=3)


def _primeira_entrada(transferencias: list[dict] | None, pipeline: str):
    """Primeira transferência para ``pipeline`` (UTC), ou NaT."""
    datas = [t["em"] for t in transferencias or [] if t.get("para") == pipeline and t.get("em")]
    return pd.to_datetime(min(datas), utc=True) if datas else pd.NaT


def itens_de_fluxo(universo: pd.DataFrame, tipos: tuple[str, ...] = TIPOS_FLUXO,
                   transferencias: dict | None = None) -> pd.DataFrame:
    """Issues de trabalho técnico e defeitos, com datas locais, Lead Time e Cycle Time.

    ``universo`` é a saída de ``agile.universo_issues``. Fora ficam US (Feature, medidas pelo EVM), épicos,
    initiatives e pacotes de trabalho. Issue sem tipo entra como "Sem tipo" (o painel não adivinha o tipo).
    ``transferencias`` é ``snapshot["transferencias_pipeline"]``: com ele, ``inicio`` é a primeira entrada em
    ``config.FLUXO["pipeline_inicio"]`` e ``cycle_dias`` vai do início ao fechamento (``cycle_valido`` marca o
    que entra no Cycle Time: início anterior ao fechamento por pelo menos ``cycle_minimo_min``).
    """
    colunas = ["issue_id", "number", "title", "repositorio", "url", "tipo", "criada", "fechada", "lead_dias",
               "aberta", "inicio", "cycle_dias", "cycle_valido"]
    if universo is None or universo.empty:
        return pd.DataFrame(columns=colunas)
    d = universo.copy()
    d["tipo"] = d["issue_type"].where(d["issue_type"].map(lambda x: isinstance(x, str) and bool(x.strip())),
                                      "Sem tipo")
    d = d[d["tipo"].isin(tipos)].copy()
    d["criada"] = _local(d["created_at"])
    d["fechada"] = _local(d["concluida_em"])
    d["aberta"] = d["fechada"].isna()
    d["lead_dias"] = (d["fechada"] - d["criada"]).dt.total_seconds() / 86400
    d.loc[d["lead_dias"] < 0, "lead_dias"] = float("nan")     # fechada "antes" de criada: dado inconsistente
    pipeline = config.FLUXO["pipeline_inicio"]
    ini_utc = pd.Series([_primeira_entrada((transferencias or {}).get(i), pipeline) for i in d["issue_id"]],
                        index=d.index, dtype="datetime64[ns, UTC]")
    d["inicio"] = _local(ini_utc)
    d["cycle_dias"] = (d["fechada"] - d["inicio"]).dt.total_seconds() / 86400
    minimo = config.FLUXO["cycle_minimo_min"] / 1440
    d["cycle_valido"] = d["cycle_dias"].notna() & (d["cycle_dias"] >= minimo)
    for c in ("url", "number", "title"):
        if c not in d:
            d[c] = None
    return d[colunas].reset_index(drop=True)


def throughput_semanal(itens: pd.DataFrame, ini: pd.Timestamp | None = None,
                       fim: pd.Timestamp | None = None) -> pd.DataFrame:
    """Itens concluídos por semana e tipo (``semana`` = segunda-feira). Semanas sem conclusão aparecem com 0."""
    vazio = pd.DataFrame(columns=["semana", "tipo", "itens"])
    if itens is None or itens.empty:
        return vazio
    d = itens[itens["fechada"].notna()].copy()
    if ini is not None:
        d = d[d["fechada"] >= pd.Timestamp(ini)]
    if fim is not None:
        d = d[d["fechada"] < pd.Timestamp(fim) + pd.Timedelta(days=1)]
    if d.empty:
        return vazio
    d["semana"] = (d["fechada"] - pd.to_timedelta(d["fechada"].dt.weekday, unit="D")).dt.normalize()
    g = d.groupby(["semana", "tipo"]).size().rename("itens").reset_index()
    semanas = pd.date_range(g["semana"].min(), g["semana"].max(), freq="7D")
    grade = pd.MultiIndex.from_product([semanas, sorted(g["tipo"].unique())], names=["semana", "tipo"])
    return g.set_index(["semana", "tipo"]).reindex(grade, fill_value=0).reset_index()


def lead_time(itens: pd.DataFrame, ini: pd.Timestamp | None = None, fim: pd.Timestamp | None = None) -> dict:
    """Mediana e percentil 85 do Lead Time das issues fechadas no período, geral e por tipo."""
    base = {"n": 0, "mediana": None, "p85": None, "media": None, "por_tipo": pd.DataFrame()}
    if itens is None or itens.empty:
        return base
    d = itens[itens["fechada"].notna() & itens["lead_dias"].notna()]
    if ini is not None:
        d = d[d["fechada"] >= pd.Timestamp(ini)]
    if fim is not None:
        d = d[d["fechada"] < pd.Timestamp(fim) + pd.Timedelta(days=1)]
    if d.empty:
        return base
    por = (d.groupby("tipo")["lead_dias"].agg(n="size", mediana="median", p85=lambda s: s.quantile(0.85))
           .reset_index())
    return {"n": len(d), "mediana": float(d["lead_dias"].median()), "p85": float(d["lead_dias"].quantile(0.85)),
            "media": float(d["lead_dias"].mean()), "por_tipo": por}


def cycle_time(itens: pd.DataFrame | None = None, ini: pd.Timestamp | None = None, fim: pd.Timestamp | None = None,
               coletado: bool = False) -> dict:
    """Cycle Time (primeira entrada em In Progress → fechamento) das issues fechadas no período.

    ``coletado``: o snapshot tem o histórico de transferências. Sem ele, "coleta pendente". Com ele, devolve a
    mediana e o P85 das issues com Cycle Time válido e a **cobertura** (válidas ÷ fechadas no período), além de
    quantas ficaram de fora e por quê (nunca passaram por In Progress, ou foram movidas em cima da hora de fechar).
    ``espera_mediana`` = Lead Time − Cycle Time das mesmas issues: o tempo parado antes de começar.
    """
    pipeline = config.FLUXO["pipeline_inicio"]
    base = {"disponivel": False, "pipeline": pipeline, "fechadas": 0, "n": 0, "cobertura": None, "sem_inicio": 0,
            "movidas_ao_fechar": 0, "mediana": None, "p85": None, "media": None, "espera_mediana": None,
            "por_tipo": pd.DataFrame(), "motivo": "", "necessario": ""}
    if not coletado:
        base["motivo"] = (f"o snapshot do Zenhub não tem o histórico de transferências de pipeline (entrada em "
                          f"{pipeline}): coleta pendente")
        base["necessario"] = ("rodar a coleta do Zenhub (`python scripts/coleta_velocity.py` ou o workflow Coleta "
                              "de dados do dashboard), que passa a gravar `transferencias_pipeline`")
        return base
    if itens is None or itens.empty:
        base["motivo"] = "nenhuma issue de trabalho técnico ou defeito"
        return base
    d = itens[itens["fechada"].notna()]
    if ini is not None:
        d = d[d["fechada"] >= pd.Timestamp(ini)]
    if fim is not None:
        d = d[d["fechada"] < pd.Timestamp(fim) + pd.Timedelta(days=1)]
    base["fechadas"] = len(d)
    if d.empty:
        base["motivo"] = "nenhuma issue fechada no período"
        return base
    ok = d[d["cycle_valido"]]
    base["sem_inicio"] = int(d["inicio"].isna().sum())
    base["movidas_ao_fechar"] = int((d["inicio"].notna() & ~d["cycle_valido"]).sum())
    base["n"] = len(ok)
    base["cobertura"] = len(ok) / len(d)
    if ok.empty:
        base["motivo"] = f"nenhuma issue fechada no período passou por {pipeline} antes de fechar"
        return base
    por = (ok.groupby("tipo")["cycle_dias"].agg(n="size", mediana="median", p85=lambda s: s.quantile(0.85))
           .reset_index())
    espera = (ok["lead_dias"] - ok["cycle_dias"]).dropna()
    base.update(disponivel=True, mediana=float(ok["cycle_dias"].median()), p85=float(ok["cycle_dias"].quantile(0.85)),
                media=float(ok["cycle_dias"].mean()), por_tipo=por,
                espera_mediana=float(espera.median()) if len(espera) else None)
    return base


def taxa_conclusao(itens: pd.DataFrame, ini: pd.Timestamp, fim: pd.Timestamp) -> dict:
    """Fechadas ÷ ativas no período (ativa = criada até o fim e ainda aberta, ou fechada a partir do início)."""
    r = {"fechadas": 0, "ativas": 0, "taxa": None}
    if itens is None or itens.empty:
        return r
    fim_ex = pd.Timestamp(fim) + pd.Timedelta(days=1)
    ativas = itens[(itens["criada"] < fim_ex) & (itens["fechada"].isna() | (itens["fechada"] >= pd.Timestamp(ini)))]
    feitas = ativas[ativas["fechada"].notna() & (ativas["fechada"] < fim_ex)]
    r.update(ativas=len(ativas), fechadas=len(feitas), taxa=len(feitas) / len(ativas) if len(ativas) else None)
    return r


def sem_tipo(universo: pd.DataFrame) -> pd.DataFrame:
    """Issues sem tipo no Zenhub (fecham como "Sem tipo" no fluxo): lista para corrigir o cadastro."""
    itens = itens_de_fluxo(universo, ("Sem tipo",))
    return itens.sort_values("criada", ascending=False).reset_index(drop=True)


def analise_critica(tp: pd.DataFrame, lead: dict, taxa: dict, abertas: int = 0,
                    cycle: dict | None = None) -> dict[str, str]:
    """Leitura crítica de cada gráfico do painel de fluxo, gerada dos números (sem texto escrito à mão)."""
    def f1(v):
        return f"{v:.1f}".replace(".", ",")
    saida: dict[str, str] = {}
    if tp is not None and not tp.empty:
        por_semana = tp.groupby("semana")["itens"].sum()
        media = por_semana.mean()
        ultima = por_semana.iloc[-1]
        t = (f"Leitura crítica: {int(por_semana.sum())} itens concluídos em {len(por_semana)} semanas, média de "
             f"{f1(media)} por semana; a última semana teve {int(ultima)}.")
        if len(por_semana) >= 3:
            recente = por_semana.iloc[-3:].mean()
            t += (" Ritmo recente acima da média: o time está absorvendo o trabalho técnico." if recente > media * 1.2
                  else " Ritmo recente abaixo da média: investigar bloqueios ou acúmulo de revisão." if recente < media * 0.8
                  else " Ritmo recente estável.")
        saida["throughput"] = t
    if lead.get("n"):
        t = (f"Leitura crítica: metade das {lead['n']} issues fecha em até {f1(lead['mediana'])} dias e 85% em até "
             f"{f1(lead['p85'])} dias. ")
        t += ("A cauda (P85) é muito maior que a mediana: poucas issues ficam paradas por muito tempo; priorizar as "
              "mais antigas." if lead["mediana"] and lead["p85"] > 3 * lead["mediana"] else
              "Mediana e P85 próximas: o tempo de entrega é previsível.")
        saida["lead_time"] = t
    if cycle and cycle.get("disponivel"):
        t = (f"Leitura crítica: das {cycle['fechadas']} issues fechadas no período, {cycle['n']} "
             f"({cycle['cobertura'] * 100:.0f}%) passaram por {cycle['pipeline']}; metade delas leva até "
             f"{f1(cycle['mediana'])} dias do início do trabalho ao fechamento e 85% até {f1(cycle['p85'])} dias.")
        if cycle.get("espera_mediana") is not None:
            t += (f" Em mediana, {f1(cycle['espera_mediana'])} dias foram de espera antes de começar "
                  "(Lead Time − Cycle Time): parte do prazo está na fila, não no trabalho.")
        if cycle["cobertura"] < 0.5:
            t += (f" Menos da metade das issues passa por {cycle['pipeline']}: o card é fechado sem mover no "
                  "quadro, então este Cycle Time descreve só parte do trabalho. Mover o card ao começar melhora a medida.")
        saida["cycle_time"] = t
    if taxa.get("taxa") is not None:
        t = (f"Leitura crítica: {taxa['fechadas']} de {taxa['ativas']} issues ativas no período foram fechadas "
             f"({taxa['taxa'] * 100:.0f}%).")
        if abertas:
            t += f" Há {abertas} abertas no fim do período."
        t += (" O trabalho técnico está sendo concluído." if taxa["taxa"] >= 0.8 else
              " Menos de 80% concluído: o backlog técnico está crescendo mais rápido do que fecha.")
        saida["taxa"] = t
    return saida
