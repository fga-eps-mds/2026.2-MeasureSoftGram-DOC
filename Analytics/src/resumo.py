"""Visão geral: o estado do projeto numa tela.

Cada indicador vira uma linha com valor, meta, status e onde olhar o detalhe.
O status segue a mesma regra das outras abas (metas da release em
``theme.METAS``, SPI 1,0 = no plano, CI >= 80%). Nada é calculado de novo aqui
que já não esteja nas abas: este módulo só lê os mesmos DataFrames e resume.

Status: ``good`` (no plano), ``warning`` (atenção), ``critical`` (fora do plano),
``neutral`` (informativo, sem meta definida).
"""

from __future__ import annotations

import pandas as pd

from src import theme

ORDEM_STATUS = {"critical": 0, "warning": 1, "good": 2, "neutral": 3}
ICONE = {"good": "✅", "warning": "⚠️", "critical": "🔴", "neutral": "ℹ️"}
ROTULO = {"good": "no plano", "warning": "atenção", "critical": "fora do plano", "neutral": "informativo"}

RELEASES = [("R1", pd.Timestamp("2026-09-28")), ("R2", pd.Timestamp("2026-10-26")), ("R3", pd.Timestamp("2026-11-30"))]


def _br(v, casas=1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _item(dimensao, indicador, valor, meta, status, leitura, aba):
    return {"dimensao": dimensao, "indicador": indicador, "valor": valor, "meta": meta,
            "status": status, "leitura": leitura, "aba": aba}


def release_atual(hoje: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    """Primeira release cuja entrega ainda não passou (a R3 depois do fim)."""
    for nome, entrega in RELEASES:
        if hoje <= entrega:
            return nome, entrega
    return RELEASES[-1]


def sprint_atual(calendario: pd.DataFrame, hoje: pd.Timestamp):
    if calendario is None or calendario.empty:
        return None
    s = calendario[(calendario["inicio"] <= hoje) & (calendario["fim"] >= hoje)]
    return s.iloc[0] if not s.empty else None


def pior(status: list[str]) -> str:
    validos = [s for s in status if s != "neutral"]
    return min(validos, key=ORDEM_STATUS.get) if validos else "neutral"


# ───────────────────────── por dimensão ─────────────────────────

def produto(ultimo: pd.DataFrame, erros: pd.DataFrame, release: str) -> list[dict]:
    aba = "Produto"
    if ultimo is None or ultimo.empty:
        return [_item("Produto", "Métricas do SonarCloud", "sem dados", "—", "critical",
                      "Nenhum arquivo do SonarCloud encontrado; rodar o metrics.yml.", aba)]
    out = []
    cob = ultimo[ultimo["metrica"] == "coverage"]
    meta_cob = theme.METAS["coverage"][release]
    if not cob.empty:
        media = cob["valor"].mean()
        out.append(_item("Produto", "Cobertura média", f"{_br(media)}%", f"≥ {meta_cob:.0f}%",
                         theme.status_por_meta("coverage", media, release),
                         f"média de {len(cob)} repositórios na última coleta", aba))
        abaixo = cob[cob["valor"] < meta_cob]
        n, k = len(cob), len(cob) - len(abaixo)
        st_ = "good" if k == n else ("warning" if k >= n / 2 else "critical")
        nomes = ", ".join(sorted(abaixo["repositorio"].str.replace("2026.2-MeasureSoftGram-", "")))
        out.append(_item("Produto", "Repositórios na meta de cobertura", f"{k} de {n}", "todos",
                         st_, f"abaixo da meta: {nomes}" if nomes else "todos acima da meta", aba))
    dup = ultimo[ultimo["metrica"] == "duplicated_lines_density"]
    if not dup.empty:
        pior_dup = dup["valor"].max()
        meta_dup = theme.METAS["duplicated_lines_density"][release]
        out.append(_item("Produto", "Duplicação (pior repositório)", f"{_br(pior_dup)}%", f"≤ {meta_dup:.0f}%",
                         theme.status_por_meta("duplicated_lines_density", pior_dup, release),
                         "densidade de linhas duplicadas", aba))
    if erros is not None and not erros.empty:
        com_metrica = set(ultimo["repositorio"])
        sem = sorted(set(erros["repositorio"]) - com_metrica)
        if sem:
            out.append(_item("Produto", "Repositórios sem projeto no SonarCloud", str(len(sem)), "0", "warning",
                             ", ".join(s.replace("2026.2-MeasureSoftGram-", "") for s in sem), aba))
    return out


def processo(runs: pd.DataFrame, issues: pd.DataFrame) -> list[dict]:
    aba = "Processo"
    out = []
    if runs is None or runs.empty:
        out.append(_item("Processo", "Execuções da CI", "sem dados", "—", "warning",
                         "Nenhum GitHub_API-Runs-*.json encontrado.", aba))
    else:
        conc = runs[runs["conclusao"].isin(["success", "failure"])]
        if not conc.empty:
            taxa = (conc["conclusao"] == "success").mean() * 100
            st_ = "good" if taxa >= 80 else ("warning" if taxa >= 60 else "critical")
            por_repo = conc.groupby("repositorio")["conclusao"].apply(lambda s: (s == "success").mean() * 100)
            pior_r = por_repo.idxmin()
            out.append(_item("Processo", "Sucesso da CI", f"{taxa:.0f}%", "≥ 80%", st_,
                             f"{int((conc['conclusao'] == 'failure').sum())} falhas em {len(conc)} execuções; "
                             f"pior: {pior_r.replace('2026.2-MeasureSoftGram-', '')} ({por_repo.min():.0f}%)", aba))
        if "duracao_min" in runs and runs["duracao_min"].notna().any():
            out.append(_item("Processo", "Tempo mediano da CI", f"{_br(runs['duracao_min'].median())} min", "—",
                             "neutral", "tempo de feedback de cada execução", aba))
    if issues is not None and not issues.empty:
        abertas = int((issues["estado"] == "open").sum())
        fechadas = int((issues["estado"] == "closed").sum())
        lead = issues["lead_time_dias"].median()
        out.append(_item("Processo", "Issues abertas / fechadas", f"{abertas} / {fechadas}", "—", "neutral",
                         f"lead time mediano {_br(lead)} dias" if pd.notna(lead) else "sem issue fechada", aba))
    return out


def projeto(evm_df: pd.DataFrame, vel: pd.DataFrame, horas: pd.DataFrame, sumario: pd.DataFrame) -> list[dict]:
    """AgileEVM e velocity com os pontos do Zenhub (src/evm.py, src/velocity.py)."""
    aba = "Projeto"
    out = []
    feitas = evm_df.dropna(subset=["PRP"]) if evm_df is not None and not evm_df.empty else pd.DataFrame()
    if feitas.empty:
        out.append(_item("Projeto", "AgileEVM", "sem dados do Zenhub", "—", "warning",
                         "Rodar scripts/coleta_velocity.py para trazer sprints e pontos.", aba))
    else:
        u = feitas.iloc[-1]
        spi = u.get("SPI")
        if pd.notna(spi):
            st_ = "good" if spi >= 0.95 else ("warning" if spi >= 0.8 else "critical")
            out.append(_item("Projeto", f"SPI da {u['release']} (prazo)", _br(spi, 2), "≥ 0,95", st_,
                             f"{u['sprint']}: entregou {u['APC']:.0%} do escopo, o plano previa {u['PPC']:.0%}",
                             aba))
        base = u.get("prp_linha_de_base")
        if pd.notna(base) and base > 0 and pd.notna(u.get("PRP")):
            cresc = u["PRP"] / base
            st_ = "good" if cresc <= 1.2 else ("warning" if cresc <= 1.5 else "critical")
            out.append(_item("Projeto", "Escopo da release (PRP)", f"{_br(base, 0)} → {_br(u['PRP'], 0)} pts",
                             "≤ +20% da linha de base", st_, "pontos que entraram depois da linha de base (PA)", aba))
    v = vel[vel["status"] == "concluída"] if vel is not None and not vel.empty else pd.DataFrame()
    v = v.dropna(subset=["planned_story_points"]) if not v.empty else v
    if not v.empty and v["planned_story_points"].sum():
        taxa = v["completed_story_points"].sum() / v["planned_story_points"].sum()
        st_ = "good" if taxa >= 0.8 else ("warning" if taxa >= 0.6 else "critical")
        media = v["velocity"].mean()
        out.append(_item("Projeto", "Taxa de conclusão (concluído ÷ planejado)", f"{taxa:.0%}", "≥ 80%", st_,
                         f"velocity média {_br(media)} SP por sprint ({len(v)} concluídas)", aba))
    h = horas.dropna(subset=["horas"]) if horas is not None and not horas.empty and "horas" in horas else pd.DataFrame()
    total_h = h["horas"].sum() if not h.empty else 0
    out.append(_item("Projeto", "Horas registradas", f"{_br(total_h, 0)} h", "todas as sprints",
                     "good" if total_h > 0 else "warning",
                     "com horas reais o CPI mede custo de verdade" if total_h > 0
                     else "sem horas, AC = custo planejado e o CPI repete o SPI", aba))
    return out


def gestao(riscos: pd.DataFrame, decisoes: pd.DataFrame, release: str) -> list[dict]:
    aba = "Riscos e decisões"
    out = []
    if riscos is not None and not riscos.empty and "exposicao_atual" in riscos:
        r = riscos.dropna(subset=["exposicao_atual"])
        ativos = r[~r["status"].astype(str).str.lower().str.startswith("encerr")]
        elevados = ativos[ativos["exposicao_atual"] >= 15]
        out.append(_item("Gestão", "Riscos com exposição elevada", f"{len(elevados)} de {len(ativos)}", "0",
                         "critical" if len(elevados) >= 3 else ("warning" if len(elevados) else "good"),
                         ("maior: " + ", ".join(f"{a.id} ({a.exposicao_atual:.0f})" for a in
                                                elevados.sort_values("exposicao_atual", ascending=False).head(3).itertuples()))
                         if len(elevados) else "nenhum risco com P×I ≥ 15", aba))
        sem_dono = int((ativos["responsavel"].astype(str).str.strip() == "").sum()) if "responsavel" in ativos else 0
        if sem_dono:
            out.append(_item("Gestão", "Riscos sem responsável", str(sem_dono), "0", "warning",
                             "todo risco ativo precisa de dono", aba))
    else:
        out.append(_item("Gestão", "Plano de riscos", "sem dados", "—", "warning", "Aba Riscos não encontrada.", aba))
    n = 0 if decisoes is None else len(decisoes)
    meta = {"R1": None, "R2": 3, "R3": 5}.get(release)
    if meta:
        st_ = "good" if n >= meta else ("warning" if n >= meta - 1 else "critical")
        meta_txt = f"≥ {meta} na {release}"
    else:
        st_, meta_txt = "neutral", "≥ 3 na R2 · ≥ 5 na R3"
    medidas = 0
    if n and "resultado" in decisoes:
        medidas = int((decisoes["resultado"].astype(str).str.strip() != "").sum())
    out.append(_item("Gestão", "Decisões baseadas em dados", str(n), meta_txt, st_,
                     f"{medidas} com resultado medido", aba))
    return out


def tudo(*, ultimo, erros, runs, issues, evm_df, vel, horas, sumario, riscos, decisoes, release) -> pd.DataFrame:
    linhas = (produto(ultimo, erros, release) + processo(runs, issues)
              + projeto(evm_df, vel, horas, sumario) + gestao(riscos, decisoes, release))
    return pd.DataFrame(linhas)


def atencao(resumo: pd.DataFrame) -> pd.DataFrame:
    """Indicadores fora do plano ou em atenção, do mais grave para o menos."""
    if resumo.empty:
        return resumo
    r = resumo[resumo["status"].isin(["critical", "warning"])].copy()
    r["_o"] = r["status"].map(ORDEM_STATUS)
    return r.sort_values("_o", kind="stable").drop(columns="_o")


def scorecard_repos(ultimo: pd.DataFrame, runs: pd.DataFrame, issues: pd.DataFrame, release: str) -> pd.DataFrame:
    """Uma linha por repositório: qualidade (SonarCloud) + CI + issues."""
    partes = []
    if ultimo is not None and not ultimo.empty:
        p = ultimo.pivot_table(index="repositorio", columns="metrica", values="valor")
        cols = {"coverage": "cobertura", "duplicated_lines_density": "duplicacao", "tests": "testes",
                "ncloc": "linhas"}
        partes.append(p[[c for c in cols if c in p]].rename(columns=cols))
    if runs is not None and not runs.empty:
        conc = runs[runs["conclusao"].isin(["success", "failure"])]
        g = conc.groupby("repositorio")["conclusao"]
        partes.append(pd.DataFrame({"ci_sucesso": g.apply(lambda s: (s == "success").mean() * 100),
                                    "ci_execucoes": g.size()}))
    if issues is not None and not issues.empty:
        partes.append(issues.assign(ab=issues["estado"] == "open").groupby("repositorio")
                      .agg(issues_abertas=("ab", "sum")))
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, axis=1).reset_index().rename(columns={"index": "repositorio"})
    meta = theme.METAS["coverage"][release]

    def situacao(l):
        s = []
        if pd.notna(l.get("cobertura")):
            s.append(theme.status_por_meta("coverage", l["cobertura"], release))
        if pd.notna(l.get("ci_sucesso")):
            s.append("good" if l["ci_sucesso"] >= 80 else ("warning" if l["ci_sucesso"] >= 60 else "critical"))
        if pd.isna(l.get("cobertura")):
            s.append("warning")
        st_ = pior(s)
        return f"{ICONE[st_]} {ROTULO[st_]}"

    df["situacao"] = df.apply(situacao, axis=1)
    df["repositorio"] = df["repositorio"].str.replace("2026.2-MeasureSoftGram-", "", regex=False)
    df.attrs["meta_cobertura"] = meta
    return df.sort_values("repositorio").reset_index(drop=True)
