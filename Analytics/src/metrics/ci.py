"""Integração contínua: recorte de build (test.yml) e leitura crítica da taxa de sucesso.

Build stability, Build performance e CI feedback time só olham o workflow de testes (decisão D5 em
``docs/planejamento/decisoes.mdx``, ``config.QRAPIDS["workflows_build"]``): deploy, coleta de dados,
dependabot e publicação não dizem se o produto está estável. A página Integração contínua usa o mesmo
recorte por padrão, para o número dela bater com o M10 do Q-Rapids (pendência da #193, TASK38.05.01).
"""

from __future__ import annotations

import pandas as pd

import config


def workflows_de_build() -> list[str]:
    return list(config.QRAPIDS.get("workflows_build") or [])


def so_build(runs: pd.DataFrame) -> pd.DataFrame:
    """Execuções dos workflows de build (test.yml), fora das branches do Dependabot (D7), com qualquer conclusão.

    Lista de workflows vazia em ``config`` = todos os workflows.
    """
    if runs is None or runs.empty:
        return runs if runs is not None else pd.DataFrame()
    nomes = set(workflows_de_build())
    r = runs[runs["workflow"].isin(nomes)] if nomes else runs
    fora = tuple(config.QRAPIDS.get("branches_fora_do_build") or ())
    if fora and "branch" in r:
        r = r[~r["branch"].fillna("").str.startswith(fora)]
    return r


def analise_critica(semanal: pd.DataFrame, concluidas: pd.DataFrame, meta: float, limite: float,
                    so_testes: bool = True) -> str | None:
    """Leitura crítica do gráfico "Taxa de sucesso da CI por semana", gerada dos números.

    ``semanal``: uma linha por semana com ``semana``, ``execucoes`` e ``sucesso`` (%). ``concluidas``: as
    execuções que terminaram em sucesso ou falha (com ``repositorio`` e ``conclusao``), para apontar onde
    estão as falhas. ``meta`` e ``limite`` em %. Sem semanas = sem leitura (``None``).
    """
    from src.data.sonar import nome_curto
    from src.metrics.calculations import num
    if semanal is None or semanal.empty:
        return None
    s = semanal.sort_values("semana")
    total = (concluidas["conclusao"] == "success").mean() * 100 if not concluidas.empty else float("nan")
    recorte = "do workflow de testes (test.yml)" if so_testes else "de todos os workflows"
    t = (f"Leitura crítica: {num(total)}% das execuções {recorte} passaram em {len(s)} semanas "
         f"(meta ≥ {num(meta)}%).")
    if len(s) >= 4:
        recente, antes = s["sucesso"].iloc[-3:].mean(), s["sucesso"].iloc[:-3].mean()
        if recente >= antes + 5:
            t += f" As 3 últimas semanas ({num(recente)}%) estão acima das anteriores ({num(antes)}%): a CI está estabilizando."
        elif recente <= antes - 5:
            t += (f" As 3 últimas semanas ({num(recente)}%) estão abaixo das anteriores ({num(antes)}%): a CI está "
                  "piorando.")
        else:
            t += f" As 3 últimas semanas ({num(recente)}%) seguem o patamar das anteriores ({num(antes)}%)."
    pior = s.loc[s["sucesso"].idxmin()]
    if pior["sucesso"] < limite:
        t += (f" A pior semana foi a de {pd.Timestamp(pior['semana']).strftime('%d/%m')} ({num(pior['sucesso'])}%, "
              f"abaixo do limite crítico de {num(limite)}%).")
    falhas = concluidas[concluidas["conclusao"] == "failure"]
    if not falhas.empty and "repositorio" in falhas:
        por_repo = falhas["repositorio"].value_counts()
        repo, n = por_repo.index[0], int(por_repo.iloc[0])
        t += f" {nome_curto(repo)} concentra {n} das {len(falhas)} falhas ({num(n / len(falhas) * 100)}%)."
    if total >= meta:
        t += " Decisão que isso apoia: a CI já serve de portão de qualidade; manter o bloqueio de merge com teste falhando."
    else:
        t += (" Decisão que isso apoia: tratar teste quebrado antes de abrir PR novo, começando pelo repositório "
              "com mais falhas, até a CI voltar à meta e poder servir de portão de qualidade.")
    if not so_testes:
        t += " Com todos os workflows, deploy, coleta e dependabot entram na taxa e ela deixa de medir só o produto."
    return t
