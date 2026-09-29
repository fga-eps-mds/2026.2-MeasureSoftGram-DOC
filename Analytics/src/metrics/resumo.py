"""Visão executiva: indicadores de todas as fontes com status frente à meta.

Nada é calculado de novo aqui: o módulo lê o contexto já carregado (as mesmas
tabelas das outras páginas) e resume. Cada indicador sabe sua fonte e em que
página está o detalhe. Indicador sem dado entra como ``unavailable`` — aparece
nos pontos de atenção como dado faltante, nunca como valor inventado.
"""

from __future__ import annotations

import pandas as pd

import config
from src import theme
from src.data import sonar as sn
from src.metrics import velocity as vel
from src.metrics.calculations import brl, num, pct, status_indice, status_meta, status_taxa, vazio


def _item(dimensao, indicador, valor, status, leitura, onde, fonte):
    return {"dimensao": dimensao, "indicador": indicador, "valor": valor, "status": status, "leitura": leitura,
            "onde": onde, "fonte": fonte}


def release_em_foco(ctx, release: str | None) -> tuple[str | None, pd.DataFrame]:
    """Release do EVM que corresponde ao filtro (ou a última iniciada) e as sprints iniciadas dela.

    O nome da release no Zenhub ("Release 01") pode diferir do plano ("R1"): a
    correspondência é pela data de entrega (fim da última sprint a até 7 dias da entrega).
    """
    e = ctx.evm
    if e is None or e.empty:
        return None, pd.DataFrame()
    feitas = e.dropna(subset=["PRP"])
    alvo = None
    if release in config.RELEASES:
        entrega = pd.Timestamp(config.RELEASES[release])
        fins = e.groupby("release", sort=False)["fim_da_sprint"].max()
        perto = fins[(fins - entrega).abs() <= pd.Timedelta(days=7)]
        alvo = perto.index[0] if len(perto) else None
    if alvo is None:
        alvo = feitas["release"].iloc[-1] if not feitas.empty else e["release"].iloc[0]
    return alvo, feitas[feitas["release"] == alvo]


def indicadores(ctx, filtros) -> pd.DataFrame:
    rel_meta = filtros["release_metas"]
    repos = [r for r in ctx.sonar_atual["repositorio"].unique()] if not ctx.sonar_atual.empty else []
    if filtros["repos"]:
        repos = [r for r in repos if sn.nome_curto(r) in filtros["repos"]]
    out = []

    # ── Qualidade (SONAR) ──
    cob = sn.atual_e_anterior(ctx.sonar_serie, "coverage", repos)
    meta_c = config.METAS["coverage"][rel_meta]
    if cob["atual"] is None:
        out.append(_item("Qualidade", "Cobertura de testes", None, "unavailable",
                         "sem métricas do SonarCloud", "Qualidade técnica", "SONAR"))
    else:
        ult = ctx.sonar_atual[(ctx.sonar_atual["metrica"] == "coverage") & ctx.sonar_atual["repositorio"].isin(repos)]
        abaixo = sorted(sn.nome_curto(r) for r in ult.loc[ult["valor"] < meta_c, "repositorio"])
        # A meta vale por repositório: a média pode passar com repositórios abaixo, então o status
        # é o do pior repositório (a média fica só como valor de referência).
        s = theme.pior([status_meta("coverage", v, rel_meta, True) for v in ult["valor"]]) if not ult.empty \
            else status_meta("coverage", cob["atual"], rel_meta, True)
        out.append(_item("Qualidade", "Cobertura (média dos repositórios)", f"{num(cob['atual'], 1)}%", s,
                         f"meta ≥ {num(meta_c)}% em cada repositório · {len(abaixo)} de {len(ult)} abaixo: "
                         f"{', '.join(abaixo)}" if abaixo else f"meta ≥ {num(meta_c)}% · todos os repositórios na meta",
                         "Qualidade técnica", "SONAR"))
    dup = ctx.sonar_atual[(ctx.sonar_atual["metrica"] == "duplicated_lines_density")
                          & ctx.sonar_atual["repositorio"].isin(repos)]
    if not dup.empty:
        pior = dup.loc[dup["valor"].idxmax()]
        meta_d = config.METAS["duplicated_lines_density"][rel_meta]
        out.append(_item("Qualidade", "Duplicação (pior repositório)", f"{num(pior['valor'], 1)}%",
                         status_meta("duplicated_lines_density", pior["valor"], rel_meta, False),
                         f"{sn.nome_curto(pior['repositorio'])} · meta ≤ {num(meta_d)}%", "Qualidade técnica", "SONAR"))
    qg = (ctx.sonar_api or {}).get("quality_gate", pd.DataFrame())
    if qg is not None and not qg.empty:
        q = qg[qg["repositorio"].isin(repos)] if repos else qg
        reprov = sorted(sn.nome_curto(r) for r in q.loc[q["status"] != "OK", "repositorio"])
        out.append(_item("Qualidade", "Quality Gate", f"{len(q) - len(reprov)} de {len(q)} aprovados",
                         "good" if not reprov else ("warning" if len(reprov) <= len(q) / 2 else "critical"),
                         f"reprovados: {', '.join(reprov)}" if reprov else "todos aprovados", "Qualidade técnica",
                         "SONAR"))
        bugs = sn.atual_e_anterior(ctx.sonar_serie, "bugs", repos)
        if bugs["atual"] is not None:
            out.append(_item("Qualidade", "Bugs abertos", num(bugs["atual"]),
                             "good" if bugs["atual"] == 0 else "warning", "soma dos repositórios (SonarCloud)",
                             "Qualidade técnica", "SONAR"))
    else:
        out.append(_item("Qualidade", "Quality Gate, bugs e vulnerabilidades", None, "unavailable",
                         "não coletados: rodar scripts/coleta_sonar.py", "Qualidade técnica", "SONAR"))
    if not ctx.sonar_erros.empty:
        sem = sorted({sn.nome_curto(r) for r in ctx.sonar_erros["repositorio"]}
                     - {sn.nome_curto(r) for r in ctx.sonar_atual["repositorio"]})
        if sem:
            out.append(_item("Qualidade", "Repositórios sem projeto no SonarCloud", str(len(sem)), "warning",
                             ", ".join(sem), "Qualidade técnica", "SONAR"))

    # ── Entrega e prazo (ZENHUB + EVM) ──
    alvo, feitas = release_em_foco(ctx, filtros["release"])
    if feitas.empty:
        out.append(_item("Entrega", "SPI (prazo)", None, "unavailable", "sem sprints do Zenhub na release",
                         "Agile EVM", "ZENHUB"))
    else:
        u = feitas.iloc[-1]
        out.append(_item("Entrega", f"Progresso da {alvo} (APC)", f"{pct(u['APC'])} entregue",
                         status_indice(u["SPI"]),
                         f"{num(u['RPC'])} de {num(u['PRP'])} SP do escopo atual da release · planejado até a "
                         f"{u['sprint']}: {pct(u['PPC'])} do prazo", "Agile EVM", "ZENHUB"))
        out.append(_item("Entrega", f"SPI da {alvo}", num(u["SPI"], 2) if not vazio(u["SPI"]) else None,
                         status_indice(u["SPI"]), f"EV ÷ PV · meta ≥ {num(config.META_INDICE_EVM, 2)}", "Agile EVM", "CALCULADO"))
        base = u["prp_linha_de_base"]
        if not vazio(base) and not vazio(u["PRP"]):
            cresc = (u["PRP"] / base) if base else None
            s = "unavailable" if cresc is None else ("good" if cresc <= 1.2 else ("warning" if cresc <= 1.5 else "critical"))
            out.append(_item("Entrega", "Escopo da release", f"{num(base)} → {num(u['PRP'])} SP",
                             "warning" if base == 0 and u["PRP"] > 0 else s,
                             "linha de base 0 SP: nada estimado na planning" if base == 0
                             else "crescimento do escopo desde a linha de base (≤ +20%)", "Agile EVM", "ZENHUB"))
    v = ctx.zh_iniciadas
    concl = v[v["status"] == vel.STATUS_CONCLUIDA] if not v.empty else v
    if not concl.empty:
        plan, feito = concl["planned_story_points"].sum(min_count=1), concl["completed_story_points"].sum(min_count=1)
        taxa = vel.calculate_completion_rate(plan, feito)
        out.append(_item("Entrega", "Taxa de conclusão das sprints", f"{num(taxa)}%" if taxa is not None else None,
                         status_taxa(taxa, config.META_TAXA_CONCLUSAO, config.LIMITE_TAXA_CRITICO),
                         f"{num(feito)} de {num(plan)} SP planejados nas plannings de {', '.join(concl['sprint_label'])} "
                         f"(issue levada de sprint conta em cada planning; não é o denominador do APC) · "
                         f"meta ≥ {num(config.META_TAXA_CONCLUSAO)}%" if taxa is not None
                         else "planejado das sprints concluídas = 0 SP (issues sem estimativa na planning)",
                         "Gestão ágil", "ZENHUB"))
    iss = ctx.zh_issues
    if iss is not None and not iss.empty:
        sem_est = iss[iss["issue_type"].isin(ctx.zh_regras.tipos_pontuados) & iss["pontos"].isna()]
        if len(sem_est):
            out.append(_item("Entrega", "Issues pontuáveis sem estimativa", num(len(sem_est)), "warning",
                             "contam 0 SP na velocity e no EVM", "Gestão ágil", "ZENHUB"))

    # ── Custo (PLANILHA + EVM) ──
    if feitas.empty or vazio(feitas.iloc[-1]["BAC"]):
        motivo = feitas.iloc[-1].get("motivo_valor") if not feitas.empty else None
        out.append(_item("Custo", "Orçamento (BAC)", None, "unavailable",
                         motivo if isinstance(motivo, str) else "abas Custos/Planejamento não lidas",
                         "Custos", "PLANILHA"))
    else:
        u = feitas.iloc[-1]
        out.append(_item("Custo", f"Orçamento da {alvo} (BAC)", brl(u["BAC"], 0), "neutral",
                         f"PV até a {u['sprint']}: {brl(u['PV'], 0)}", "Agile EVM", "PLANILHA"))
        if vazio(u["CPI"]):
            out.append(_item("Custo", "CPI (custo)", None, "unavailable",
                             f"Actual Cost indisponível: {str(u['origem_do_ac']).replace('indisponível: ', '')}",
                             "Agile EVM",
                             "PLANILHA"))
        else:
            h = float(feitas["horas_reais"].fillna(0).sum())
            out.append(_item("Custo", "CPI (custo)", num(u["CPI"], 2), status_indice(u["CPI"]),
                             f"EV {brl(u['EV'], 0)} ÷ AC {brl(u['AC'], 0)} ({num(h)} h registradas na aba Horas até a "
                             f"{u['sprint']}) · meta ≥ {num(config.META_INDICE_EVM, 2)}", "Agile EVM", "CALCULADO"))

    # ── Riscos (PLANILHA) ──
    r = ctx.riscos
    if r is None or r.empty or "exposicao_atual" not in r:
        out.append(_item("Riscos", "Plano de riscos", None, "unavailable", "aba Riscos não lida", "Riscos",
                         "PLANILHA"))
    else:
        cont = contagem_riscos(r)
        elev = cont["elevados"]
        out.append(_item("Riscos", "Riscos elevados não encerrados", f"{len(elev)} de {cont['nao_encerrados']}",
                         "critical" if len(elev) >= 3 else ("warning" if len(elev) else "good"),
                         f"{cont['frase']} · " + (("elevados: " + ", ".join(
                             f"{x.id} ({num(x.exposicao_atual)}, {str(x.status).lower()})" for x in elev.itertuples()))
                             if len(elev) else f"nenhum com P × I ≥ {config.RISCO_ELEVADO}"),
                         "Riscos", "PLANILHA"))
        faltam = riscos_fora_da_aba(r, ctx.monitoramento)
        if faltam:
            out.append(_item("Riscos", "Riscos só no Monitoramento", ", ".join(faltam), "warning",
                             "aparecem na aba Monitoramento e não na aba Riscos: cadastrar na aba Riscos",
                             "Riscos", "PLANILHA"))
    n_dec = len(ctx.decisoes) if ctx.decisoes is not None else 0
    meta_dec = config.METAS_DECISOES.get(rel_meta)
    out.append(_item("Riscos", "Decisões baseadas em dados", num(n_dec),
                     "neutral" if not meta_dec else ("good" if n_dec >= meta_dec else "warning"),
                     f"meta da {rel_meta}: ≥ {meta_dec}" if meta_dec else
                     "metas: " + ", ".join(f"≥ {v} na {k}" for k, v in config.METAS_DECISOES.items()),
                     "Decisões", "PLANILHA"))

    # ── Processo (GITHUB) ──
    runs = ctx.gh_runs
    if runs is not None and not runs.empty:
        c = runs[runs["conclusao"].isin(["success", "failure"])]
        if filtros["repos"]:
            c = c[c["repositorio"].map(sn.nome_curto).isin(filtros["repos"])]
        if not c.empty:
            t = (c["conclusao"] == "success").mean() * 100
            out.append(_item("Processo", "Sucesso da CI", f"{num(t)}%", status_taxa(t, config.META_CI_SUCESSO, config.LIMITE_CI_CRITICO),
                             f"{int((c['conclusao'] == 'failure').sum())} falhas em {len(c)} execuções · meta ≥ {num(config.META_CI_SUCESSO)}%",
                             "Integração contínua", "GITHUB"))
    df = pd.DataFrame(out)
    if not df.empty:  # None continua None (o pandas trocaria por NaN)
        df["valor"] = pd.Series([v if isinstance(v, str) else None for v in df["valor"]], index=df.index, dtype=object)
    return df


def contagem_riscos(r: pd.DataFrame) -> dict:
    """Contagem por status da aba Riscos (texto gerado dos dados)."""
    st_ = r["status"].fillna("sem status").astype(str).str.strip()
    encerrado = st_.str.lower().str.startswith(("encerr", "mitigad", "fechad"))
    nao_enc = r[~encerrado]
    elevados = nao_enc[pd.to_numeric(nao_enc["exposicao_atual"], errors="coerce") >= config.RISCO_ELEVADO] \
        .sort_values("exposicao_atual", ascending=False)
    por = st_[~encerrado].value_counts()
    frase = ", ".join(f"{n} {s.lower()}" for s, n in por.items())
    return {"nao_encerrados": len(nao_enc), "elevados": elevados, "por_status": por, "frase": frase}


def riscos_fora_da_aba(riscos: pd.DataFrame, monitoramento: pd.DataFrame) -> list[str]:
    """IDs avaliados no Monitoramento que não existem na aba Riscos."""
    if monitoramento is None or monitoramento.empty or "id_do_risco" not in monitoramento or "id" not in riscos:
        return []
    ids = set(riscos["id"].astype(str).str.strip())
    return sorted({str(i).strip() for i in monitoramento["id_do_risco"].dropna()} - ids - {""})


def situacao_geral(df: pd.DataFrame) -> tuple[str, str]:
    """(status, frase) do projeto: o pior status entre os indicadores com meta."""
    if df.empty:
        return "unavailable", "Sem dados para avaliar."
    s = theme.pior(list(df["status"]))
    n_c, n_w = int((df["status"] == "critical").sum()), int((df["status"] == "warning").sum())
    n_u = int((df["status"] == "unavailable").sum())
    frase = {"critical": f"{n_c} indicador(es) crítico(s) e {n_w} em atenção.",
             "warning": f"Nenhum indicador crítico; {n_w} em atenção.",
             "good": "Todos os indicadores com meta estão conformes.",
             "neutral": "Nenhum indicador com meta disponível."}[s]
    if n_u:
        frase += f" {n_u} indicador(es) sem dado."
    return s, frase


def pontos_de_atencao(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    a = df[df["status"].isin(["critical", "warning", "unavailable"])].copy()
    a["_o"] = a["status"].map(theme.ORDEM_STATUS)
    return a.sort_values("_o", kind="stable").drop(columns="_o")
