"""Métricas de fluxo (Kanban) do trabalho técnico e dos defeitos — DA-R3.02.

Task, Sub-task, Bug e issue sem tipo não pontuam no Velocity nem no Agile EVM (só a US aceita pelo PO
pontua, ver ``velocity.py``). Em vez de story points, o trabalho técnico é acompanhado pelo fluxo:

* **Throughput**: itens concluídos por semana (segunda a domingo, horário de Brasília);
* **Lead Time**: da criação da issue até o fechamento (mediana e percentil 85, em dias);
* **Cycle Time**: da entrada em *In Progress* até o fechamento. **Indisponível** hoje: a coleta do Zenhub
  guarda só a última transferência de pipeline (``pipeline_moved_at``), não a data em que a issue começou
  a ser trabalhada. Aproximar pelo Lead Time ou pela última transferência daria um número errado com cara
  de certo; o motivo e o que falta aparecem na tela (``cycle_time``);
* **Taxa de conclusão**: fechadas ÷ ativas no período (Q-Rapids, *Development Task Completion*).

Funções puras (sem Streamlit e sem rede), testadas em ``tests/test_fluxo.py``. Nenhuma delas usa story points.
"""

from __future__ import annotations

import pandas as pd

TIPOS_FLUXO = ("Task", "Sub-task", "Bug", "Sem tipo")
FUSO = "America/Sao_Paulo"


def _local(serie: pd.Series) -> pd.Series:
    s = pd.to_datetime(serie, utc=True, errors="coerce")
    try:
        return s.dt.tz_convert(FUSO).dt.tz_localize(None)
    except Exception:  # noqa: BLE001 — sem base de fusos no navegador
        return s.dt.tz_convert(None) - pd.Timedelta(hours=3)


def itens_de_fluxo(universo: pd.DataFrame, tipos: tuple[str, ...] = TIPOS_FLUXO) -> pd.DataFrame:
    """Issues de trabalho técnico e defeitos, com datas locais e Lead Time.

    ``universo`` é a saída de ``agile.universo_issues``. Fora ficam US (Feature, medidas pelo EVM), épicos,
    initiatives e pacotes de trabalho. Issue sem tipo entra como "Sem tipo" (o painel não adivinha o tipo).
    """
    colunas = ["issue_id", "number", "title", "repositorio", "url", "tipo", "criada", "fechada", "lead_dias",
               "aberta"]
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


def cycle_time(itens: pd.DataFrame | None = None) -> dict:
    """Cycle Time (entrada em In Progress → fechamento): indisponível com a coleta atual."""
    return {"disponivel": False, "mediana": None, "p85": None,
            "motivo": "a coleta do Zenhub guarda só a última transferência de pipeline, não a data em que a "
                      "issue entrou em In Progress",
            "necessario": "coletar o histórico de transferências de pipeline de cada issue (Issue.timelineItems "
                          "da API do Zenhub) em src/zenhub/coleta.py; exige validar a query com "
                          "scripts/diagnostico_zenhub.py e a chave ZENHUB_API_KEY"}


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


def analise_critica(tp: pd.DataFrame, lead: dict, taxa: dict, abertas: int = 0) -> dict[str, str]:
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
    if taxa.get("taxa") is not None:
        t = (f"Leitura crítica: {taxa['fechadas']} de {taxa['ativas']} issues ativas no período foram fechadas "
             f"({taxa['taxa'] * 100:.0f}%).")
        if abertas:
            t += f" Há {abertas} abertas no fim do período."
        t += (" O trabalho técnico está sendo concluído." if taxa["taxa"] >= 0.8 else
              " Menos de 80% concluído: o backlog técnico está crescendo mais rápido do que fecha.")
        saida["taxa"] = t
    return saida
