"""Modelo de qualidade Q-Rapids completo, com rastreabilidade de cada número.

Duas camadas, as duas exibidas na página Qualidade (Q-Rapids):

1. **Nota do notebook** (``src/metrics/qualidade.py``): as 6 métricas do SonarCloud que o notebook da
   disciplina calcula, com os mesmos pesos. É a nota oficial (Manutenibilidade, Confiabilidade, total).
2. **Modelo completo** (este módulo): todas as métricas do *Q-Rapids Quality Model* (abril/2019,
   ``q-rapids model-doc.pdf``) — indicadores estratégicos → fatores → métricas avaliadas → dado bruto.
   Cada métrica é calculada com o dado que o projeto tem (SonarCloud, GitHub, Zenhub). A que não tem
   fonte aparece com o motivo e fica fora da agregação: nunca vira zero.

Convenção: ``valor`` vai de 0 a 1 e **1 é sempre o melhor**. Métricas que o documento define "ao contrário"
(densidade de bugs, issues antigas, commits sem issue) entram pelo complemento, e o valor bruto do documento
fica em ``bruto``. Métricas sem escala 0–1 (tempo de feedback da CI, testes por produto, bug leakage) são
mostradas, mas não entram na média.

Agregação do modelo completo: o model-doc não fixa pesos, então fator = média simples das métricas
calculadas e indicador = média simples dos fatores calculados. Os pesos do notebook valem só para a nota
oficial.

Referências: Martínez-Fernández et al., "A Quality Model for Actionable Analytics in Rapid Software
Development", SEAA 2018 (Tabela I e Fig. 1) e Q-Rapids Quality Model (abril/2019).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import config
from src.metrics import qualidade as nq

L = config.QRAPIDS["limiares"]
CALCULADA, SEM_DADO, PENDENTE, SEM_FONTE, DERIVADA, INFORMATIVA = (
    "calculada", "sem dado no recorte", "coleta pendente", "sem fonte no projeto", "derivada", "informativa")
ROTULO = {CALCULADA: "Calculada", SEM_DADO: "Sem dado no recorte", PENDENTE: "Coleta pendente",
          SEM_FONTE: "Sem fonte no projeto", DERIVADA: "Repete outra métrica", INFORMATIVA: "Só informativa"}
NA_MEDIA = {CALCULADA}

INDICADORES = {
    "product_quality": ("Product Quality (qualidade do produto)",
                        "manutenibilidade, confiabilidade e adequação funcional do produto",
                        ["code_quality", "software_stability", "software_usage"]),
    "product_readiness": ("Product Readiness (prontidão do produto)",
                          "o produto está pronto para ser entregue?",
                          ["product_stability", "known_remaining_defects", "activities_completion"]),
    "blocking": ("Blocking (bloqueios)", "condições que atrapalham o fluxo do projeto",
                 ["quality_issues_specification", "blocking_code", "testing_status"]),
    "process_performance": ("Process Performance (desempenho do processo)",
                            "eficiência e qualidade do processo de desenvolvimento",
                            ["development_speed", "issues_velocity", "testing_performance", "external_quality"]),
}
FATORES = {
    "code_quality": ("Code Quality (qualidade do código)", "Manutenibilidade", "produto"),
    "software_stability": ("Software Stability (estabilidade)", "Confiabilidade", "produto"),
    "software_usage": ("Software Usage (uso)", "Adequação funcional", "produto"),
    "product_stability": ("Product Stability (estabilidade do produto)", "Confiabilidade", "produto"),
    "known_remaining_defects": ("Known Remaining Defects (defeitos conhecidos)", "Confiabilidade", "processo"),
    "activities_completion": ("Activities Completion (conclusão das atividades)", "Produtividade", "processo"),
    "quality_issues_specification": ("Quality Issues' Specification (especificação das issues)",
                                     "Manutenibilidade", "produto"),
    "blocking_code": ("Blocking Code (código bloqueante)", "Manutenibilidade", "produto"),
    "testing_status": ("Testing Status (situação dos testes)", "Confiabilidade", "produto"),
    "development_speed": ("Development Speed (velocidade de desenvolvimento)", "Produtividade", "processo"),
    "issues_velocity": ("Issues' Velocity (velocidade das issues)", "Produtividade", "processo"),
    "testing_performance": ("Testing Performance (desempenho dos testes)", "Produtividade", "processo"),
    "external_quality": ("External Quality (qualidade externa)", "Adequação funcional", "processo"),
}


@dataclass
class Resultado:
    fator: str
    chave: str
    nome: str
    descricao: str
    formula: str
    dado_bruto: str
    fonte: str
    situacao: str = SEM_DADO
    valor: float | None = None          # 0 a 1, 1 = melhor
    bruto: str = ""                     # o número como o documento define (ex.: "12% de bugs")
    numerador: float | None = None
    denominador: float | None = None
    motivo: str = ""                    # por que não foi calculada, ou observação
    itens: pd.DataFrame = field(default_factory=pd.DataFrame)   # dado bruto para conferência
    por_repo: pd.DataFrame = field(default_factory=pd.DataFrame)


def _pct(x):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.1f}%".replace(".", ",")


def _razao(r: Resultado, num, den, complemento=False, rotulo_bruto=None):
    """Preenche numerador, denominador, valor e bruto; denominador 0 = sem dado."""
    if not den:
        r.situacao, r.motivo = SEM_DADO, r.motivo or "denominador zero no recorte"
        return r
    bruto = num / den
    r.numerador, r.denominador = num, den
    r.valor = 1 - bruto if complemento else bruto
    r.bruto = f"{int(num)} de {int(den)} = {_pct(bruto)}" + (f" ({rotulo_bruto})" if rotulo_bruto else "")
    r.situacao = CALCULADA
    return r


def _local(s):
    s = pd.to_datetime(s, utc=True, errors="coerce")
    try:
        return s.dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    except Exception:  # noqa: BLE001
        return s.dt.tz_convert(None) - pd.Timedelta(hours=3)


# ───────────────────────── nota do notebook por repositório ─────────────────────────

def notas_por_repo(ctx, f: dict, rec: dict) -> dict:
    """Avaliação do notebook na última coleta do pipeline até o fim do período, por repositório.

    ``{repo: {"avaliacao": ..., "coleta": Timestamp, "arquivo": nome do .json}}``.
    """
    comp = ctx.sonar_componentes
    if comp is None or comp.empty:
        return {}
    fim = pd.Timestamp(rec["fim"]) + pd.Timedelta(days=1)
    c = comp[comp["repositorio"].isin(rec["repos"]) & (pd.to_datetime(comp["coleta"]) < fim)]
    if f.get("branch"):
        c = c[c["branch"] == f["branch"]]
    saida = {}
    for repo, x in c.groupby("repositorio"):
        ult = x["coleta"].max()
        y = x[x["coleta"] == ult]
        arq = y["arquivo"].iloc[0] if "arquivo" in y else ""
        y = y[y["arquivo"] == arq] if "arquivo" in y else y
        saida[repo] = {"avaliacao": nq.avaliar(y, repo), "coleta": ult, "arquivo": arq}
    return saida


def serie_notebook(ctx, f: dict, rec: dict) -> pd.DataFrame:
    """Nota do notebook em cada coleta do período (gráfico de evolução)."""
    comp = ctx.sonar_componentes
    if comp is None or comp.empty:
        return pd.DataFrame()
    ini = pd.Timestamp(f["periodo"][0])
    fim = pd.Timestamp(rec["fim"]) + pd.Timedelta(days=1)
    c = comp[comp["repositorio"].isin(rec["repos"]) & (pd.to_datetime(comp["coleta"]) >= ini)
             & (pd.to_datetime(comp["coleta"]) < fim)]
    if f.get("branch"):
        c = c[c["branch"] == f["branch"]]
    return nq.serie(c)


def sem_dado_algum(avaliacao: dict) -> bool:
    """Todas as métricas do repositório são "0 por falta de dado" (ex.: AI sem cobertura nem testes no .json)."""
    return all(r["zero_por_falta"] for r in avaliacao["metricas"].values())


def media_repos(notas: dict, fn, metrica: str | None = None) -> tuple[float | None, list[str]]:
    """Média simples entre repositórios, sem os valores que são só "0 por falta de dado".

    O notebook não faz média entre repositórios (calcula um por um); a média é do painel. Ela deixa de
    fora: para uma métrica, os repositórios em que ela é 0 por falta de dado; para fator, aspecto e nota
    total, os repositórios sem nenhum dado. Devolve (média, repositórios deixados de fora).
    """
    vals, fora = [], []
    for repo, n in notas.items():
        a = n["avaliacao"]
        vazio = a["metricas"][metrica]["zero_por_falta"] if metrica else sem_dado_algum(a)
        if vazio:
            fora.append(nq_nome(repo))
        else:
            vals.append(fn(a))
    return (sum(vals) / len(vals) if vals else None), fora


# ───────────────────────── modelo completo ─────────────────────────

def _sonar_media(chave_nb: str, notas: dict, r: Resultado) -> Resultado:
    """Métrica do notebook como média simples dos repositórios (o detalhe por repositório vai junto)."""
    linhas = []
    for repo, n in notas.items():
        m = n["avaliacao"]["metricas"][chave_nb]
        linhas.append({"repositorio": nq_nome(repo), "valor": m["valor"], "numerador": m["numerador"],
                       "denominador": m["denominador"], "zero_por_falta": m["zero_por_falta"] or "",
                       "coleta": n["coleta"], "arquivo": n["arquivo"]})
    if not linhas:
        r.situacao, r.motivo = SEM_DADO, "nenhuma coleta do pipeline até o fim do período"
        return r
    d = pd.DataFrame(linhas)
    r.por_repo = d
    com = d[d["zero_por_falta"] == ""]
    if com.empty:
        r.situacao, r.motivo = SEM_DADO, "nenhum repositório com esse dado no .json do pipeline"
        return r
    r.valor = float(com["valor"].mean())
    r.situacao = CALCULADA
    r.bruto = f"média de {len(com)} repositórios"
    zeros = d[d["zero_por_falta"] != ""]
    if len(zeros):
        r.motivo = (f"fora da média por não terem o dado (no notebook valeriam 0): "
                    + ", ".join(zeros["repositorio"]))
    return r


def nq_nome(repo: str) -> str:
    from src.data.sonar import nome_curto
    return nome_curto(repo)


def _arquivos_api(ctx, rec) -> pd.DataFrame:
    """Medidas por arquivo da API do SonarCloud (última coleta até o fim do período), código da linguagem."""
    a = (ctx.sonar_api or {}).get("arquivos", pd.DataFrame())
    if a is None or a.empty:
        return pd.DataFrame()
    fim = pd.Timestamp(rec["fim"]) + pd.Timedelta(days=1)
    a = a[a["repositorio"].isin(rec["repos"]) & (pd.to_datetime(a["coleta"]) < fim) & (a["tipo"] == "FIL")]
    if a.empty:
        return a
    w = a.pivot_table(index=["repositorio", "componente", "linguagem"], columns="metrica", values="valor",
                      aggfunc="last").reset_index()
    w["lingua_repo"] = w["repositorio"].map(config.QRAPIDS["linguagem"])
    w = w[(w["linguagem"] == w["lingua_repo"]) | w["lingua_repo"].isna()]
    return w[w.get("ncloc", pd.Series(0, index=w.index)) > 0] if "ncloc" in w else w


def _issues(ctx, f: dict) -> pd.DataFrame:
    """Issues do Zenhub (sem PR) no recorte de repositórios, com datas locais."""
    z = ctx.zh_issues
    if z is None or z.empty:
        return pd.DataFrame()
    z = z[~z["is_pull_request"].fillna(False).astype(bool)].copy()
    if f.get("repos"):
        z = z[z["repositorio"].map(nq_nome).isin(f["repos"])]
    z["criada"] = _local(z["created_at"])
    z["fechada"] = _local(z["closed_at"])
    z["tipo_issue"] = z["issue_type"].fillna("Sem tipo")
    return z


def calcular(ctx, f: dict, rec: dict) -> dict:
    """Todas as métricas do modelo completo no recorte dos filtros globais.

    Devolve ``{"metricas": [Resultado], "fatores": DataFrame, "indicadores": DataFrame, "notas": {...}}``.
    """
    ini = pd.Timestamp(f["periodo"][0])
    fim = pd.Timestamp(rec["fim"])
    fim_ex = fim + pd.Timedelta(days=1)
    notas = notas_por_repo(ctx, f, rec)
    z = _issues(ctx, f)
    zh_ok = not z.empty
    snap = ctx.zh_snap or {}
    coleta_zh = _local(pd.Series([snap.get("coletado_em")])).iloc[0] if snap else None
    aviso_zh = (f"snapshot do Zenhub de {coleta_zh:%d/%m/%Y}: o que mudou depois disso não aparece"
                if coleta_zh is not None and pd.notna(coleta_zh) and coleta_zh < min(fim, ctx.hoje) - pd.Timedelta(days=3)
                else "")
    gi = getattr(ctx, "gh_issues_coleta", pd.DataFrame())
    cm = getattr(ctx, "gh_commits", pd.DataFrame())
    runs = ctx.gh_runs if ctx.gh_runs is not None else pd.DataFrame()
    if not runs.empty:
        if f.get("repos"):
            runs = runs[runs["repositorio"].map(nq_nome).isin(f["repos"])]
        runs = runs.assign(criado=_local(runs["criado_em"]))
        runs = runs[(runs["criado"] >= ini) & (runs["criado"] < fim_ex)]
    out: list[Resultado] = []

    def novo(fator, chave, nome, descricao, formula, dado_bruto, fonte):
        r = Resultado(fator, chave, nome, descricao, formula, dado_bruto, fonte)
        out.append(r)
        return r

    # ── Code Quality (notebook) ──
    for chave_nb, chave, nome, desc in (
            ("complexidade", "complexity", "Complexity", "arquivos abaixo do limiar de complexidade ciclomática"),
            ("comentarios", "comments", "Comments", "arquivos com densidade de comentários dentro da faixa"),
            ("duplicacao", "duplication", "Duplication", "arquivos abaixo do limiar de linhas duplicadas")):
        nome_nb, _, _, regra, formula = nq.METRICAS[chave_nb]
        _sonar_media(chave_nb, notas, novo("code_quality", chave, f"{nome} — {nome_nb}", desc,
                                           f"{formula} · {regra}", "medidas de cada arquivo (.json do pipeline)",
                                           "SonarCloud via metrics.yml"))

    # ── Software Stability: Bug density ──
    r = novo("software_stability", "bug_density", "Bug density — densidade de bugs",
             "proporção de issues abertas do tipo bug (valor = 1 − proporção)",
             "issues abertas do tipo Bug ÷ issues abertas, no fim do período",
             "tipo e status de cada issue", "Zenhub")
    if zh_ok:
        abertas = z[(z["criada"] < fim_ex) & (z["fechada"].isna() | (z["fechada"] >= fim_ex))]
        bugs = abertas[abertas["tipo_issue"] == "Bug"]
        r.itens = bugs[["repositorio", "number", "title", "criada"]]
        _razao(r, len(bugs), len(abertas), complemento=True, rotulo_bruto="bugs entre as abertas")
        r.motivo = aviso_zh

    # ── Software Usage / External Quality: sem fonte ──
    for fator, chave, nome, desc, dado in (
            ("software_usage", "feature_usage", "Feature usage — uso das funcionalidades",
             "adequação das funcionalidades ao uso real", "uso por funcionalidade (vezes, tempo)"),
            ("external_quality", "end_user_feedback", "End user feedback — retorno do usuário",
             "feedback do usuário final ligado a issues", "feedbacks recebidos no período")):
        r = novo(fator, chave, nome, desc, "—", dado, "nenhuma")
        r.situacao = SEM_FONTE
        r.motivo = ("o produto não registra telemetria de uso" if chave == "feature_usage" else
                    "não há canal de feedback do usuário final registrado (ex.: formulário ou label de issue)")

    # ── Product Stability: Critical issues ratio + Build stability ──
    r = novo("product_stability", "critical_issues_ratio", "Critical issues ratio — issues críticas resolvidas",
             "proporção das issues de alta severidade que foram fechadas",
             "issues de alta prioridade fechadas ÷ issues de alta prioridade", "severidade/prioridade de cada issue",
             "Zenhub (prioridade)")
    if zh_ok and (z["prioridade"].fillna("Sem prioridade") != "Sem prioridade").any():
        alta = z[(z["prioridade"] != "Sem prioridade") & (z["criada"] < fim_ex)]
        fechadas = alta[alta["fechada"].notna() & (alta["fechada"] < fim_ex)]
        _razao(r, len(fechadas), len(alta))
    else:
        r.situacao, r.motivo = SEM_DADO, ("nenhuma issue com prioridade no Zenhub: marcar prioridade (ou "
                                         "severidade) nas issues habilita esta métrica")
    r = novo("product_stability", "build_stability", "Build stability — builds com sucesso",
             "densidade de execuções de CI com sucesso",
             "execuções com sucesso ÷ execuções com sucesso ou falha, no período",
             "resultado de cada execução de CI", "GitHub Actions")
    if not runs.empty:
        c = runs[runs["conclusao"].isin(["success", "failure"])]
        r.itens = c[["repositorio", "workflow", "conclusao", "criado", "duracao_min", "url"]]
        r.por_repo = (c.groupby(c["repositorio"].map(nq_nome))["conclusao"].agg(
            sucesso=lambda s: int((s == "success").sum()), total="size").reset_index()
            .assign(valor=lambda d: d["sucesso"] / d["total"]))
        _razao(r, int((c["conclusao"] == "success").sum()), len(c))

    # ── Known Remaining Defects: Postponed issues ratio ──
    r = novo("known_remaining_defects", "postponed_issues_ratio", "Postponed issues ratio — issues adiadas",
             "proporção das issues de baixa severidade que não foram fechadas",
             "issues de baixa prioridade fechadas ÷ issues de baixa prioridade", "severidade de cada issue",
             "Zenhub (prioridade)")
    r.situacao, r.motivo = SEM_DADO, "nenhuma issue com prioridade/severidade no Zenhub"

    # ── Activities Completion ──
    r = novo("activities_completion", "development_task_completion", "Development task completion — tarefas concluídas",
             "densidade de tarefas de desenvolvimento concluídas",
             "Tasks e Sub-tasks fechadas ÷ Tasks e Sub-tasks ativas no período",
             "tipo e status de cada issue", "Zenhub")
    if zh_ok:
        t = z[z["tipo_issue"].isin(["Task", "Sub-task"]) & (z["criada"] < fim_ex)
              & (z["fechada"].isna() | (z["fechada"] >= ini))]
        feitas = t[t["fechada"].notna() & (t["fechada"] < fim_ex)]
        r.itens = t[["repositorio", "number", "title", "tipo_issue", "criada", "fechada"]]
        _razao(r, len(feitas), len(t))
        r.motivo = aviso_zh
    r = novo("activities_completion", "specification_task_completion",
             "Specification task completion — tarefas de especificação concluídas",
             "densidade de tarefas de especificação concluídas", "—", "tarefas marcadas como especificação",
             "nenhuma")
    r.situacao, r.motivo = SEM_FONTE, ("o time não separa tarefas de especificação (tipo ou label); criar um "
                                      "tipo/label 'especificação' habilita esta métrica")

    # ── Quality Issues' Specification: Well defined issues ──
    r = novo("quality_issues_specification", "well_defined_issues", "Well defined issues — issues bem definidas",
             "issues com descrição e prazo preenchidos",
             "issues com descrição e prazo (sprint ou milestone) ÷ issues criadas no período",
             "descrição e prazo de cada issue", "GitHub (descrição, milestone) + Zenhub (sprint)")
    if gi is None or gi.empty:
        r.situacao, r.motivo = PENDENTE, ("descrição das issues ainda não coletada: rodar scripts/coleta_github.py "
                                          "(workflow Coleta de dados do dashboard)")
    else:
        g = gi[~gi["is_pull_request"].fillna(False).astype(bool)].copy()
        if f.get("repos"):
            g = g[g["repositorio"].map(nq_nome).isin(f["repos"])]
        g["criada"] = _local(g["created_at"])
        g = g[(g["criada"] >= ini) & (g["criada"] < fim_ex)]
        em_sprint = set()
        if zh_ok:
            em_sprint = {(nq_nome(a), int(b)) for a, b, s in zip(z["repositorio"], z["number"], z["sprints"])
                         if isinstance(s, list) and s}
        g["com_descricao"] = g["body_chars"].fillna(0) > 0
        g["com_prazo"] = g["milestone"].notna() | [(nq_nome(a), int(b)) in em_sprint
                                                   for a, b in zip(g["repositorio"], g["number"])]
        g["bem_definida"] = g["com_descricao"] & g["com_prazo"]
        r.itens = g[["repositorio", "number", "title", "com_descricao", "com_prazo", "bem_definida"]]
        _razao(r, int(g["bem_definida"].sum()), len(g))

    # ── Blocking Code: Non-blocking files (+ highly changed files) ──
    r = novo("blocking_code", "non_blocking_files", "Non-blocking files — arquivos sem violação crítica",
             "arquivos sem violação bloqueante ou crítica",
             "arquivos sem blocker_violations e critical_violations ÷ total de arquivos de código",
             "violações por arquivo e severidade", "API do SonarCloud (component_tree)")
    aa = _arquivos_api(ctx, rec)
    if aa.empty or not {"blocker_violations", "critical_violations"} <= set(aa.columns):
        r.situacao, r.motivo = PENDENTE, ("violações por arquivo ainda não coletadas: rodar scripts/coleta_sonar.py "
                                          "(versão nova) ou o workflow Coleta de dados do dashboard")
    else:
        aa = aa.dropna(subset=["blocker_violations", "critical_violations"])
        aa["passa"] = (aa["blocker_violations"] == 0) & (aa["critical_violations"] == 0)
        r.itens = aa[["repositorio", "componente", "blocker_violations", "critical_violations", "passa"]]
        r.por_repo = (aa.groupby(aa["repositorio"].map(nq_nome))["passa"].agg(numerador="sum", denominador="size")
                      .reset_index().assign(valor=lambda d: d["numerador"] / d["denominador"]))
        _razao(r, int(aa["passa"].sum()), len(aa))
    r = novo("blocking_code", "highly_changed_files", "Highly changed files — arquivos estáveis",
             "arquivos que não foram alterados muitas vezes no período (valor = 1 − proporção de muito alterados)",
             "arquivos alterados em mais de 5 commits ÷ arquivos alterados no período",
             "arquivos alterados em cada commit", "API do GitHub (commits)")
    if cm is None or cm.empty:
        r.situacao, r.motivo = PENDENTE, "commits ainda não coletados: rodar scripts/coleta_github.py (versão nova)"
    else:
        c = cm.copy()
        if f.get("repos"):
            c = c[c["repositorio"].map(nq_nome).isin(f["repos"])]
        c["quando"] = _local(c["data"])
        c = c[(c["quando"] >= ini) & (c["quando"] < fim_ex) & ~c["merge"]]
        vezes = c.groupby(["repositorio", "arquivo"])["sha"].nunique().reset_index(name="commits")
        vezes["muito_alterado"] = vezes["commits"] > 5
        r.itens = vezes.sort_values("commits", ascending=False)
        _razao(r, int(vezes["muito_alterado"].sum()), len(vezes), complemento=True,
               rotulo_bruto="alterados em mais de 5 commits")

    # ── Testing Status: Test success + coverage (Tabela I do artigo) ──
    for chave_nb, chave, nome in (("testes_passando", "test_success", "Test success — testes que passam"),
                                  ("cobertura", "test_coverage", "Test coverage — cobertura de testes")):
        _, _, _, regra, formula = nq.METRICAS[chave_nb]
        _sonar_media(chave_nb, notas, novo("testing_status", chave, nome, regra, formula,
                                           "testes, erros e falhas / cobertura de cada arquivo",
                                           "SonarCloud via metrics.yml"))

    # ── Development Speed ──
    r = novo("development_speed", "build_performance", "Build performance — builds rápidos",
             f"execuções de CI que não passaram de {L['build_rapido_min']} min",
             f"execuções com duração ≤ {L['build_rapido_min']} min ÷ execuções no período",
             "duração de cada execução de CI", "GitHub Actions")
    if not runs.empty:
        d = runs.dropna(subset=["duracao_min"])
        r.itens = d[["repositorio", "workflow", "duracao_min", "criado", "url"]].sort_values("duracao_min",
                                                                                            ascending=False)
        _razao(r, int((d["duracao_min"] <= L["build_rapido_min"]).sum()), len(d))
    r = novo("development_speed", "avg_automation_duration", "Avg. automation duration — testes automatizados rápidos",
             "testes automatizados abaixo do limiar de duração", "igual a Testes rápidos (suítes UTS do SonarCloud)",
             "duração de cada suíte de teste", "SonarCloud")
    r.situacao, r.motivo = DERIVADA, "mesmo dado e mesma fórmula de Fast tests (Testing Performance): fica fora da média"
    r = novo("development_speed", "commit_review_duration", "Commit review duration — PRs revisados no prazo",
             f"pull requests fechados em até {L['revisao_pr_horas']} h",
             f"PRs fechados em até {L['revisao_pr_horas']} h após abertos ÷ PRs fechados no período",
             "abertura e fechamento de cada PR", "API do GitHub (issues/PRs)")
    if gi is None or gi.empty:
        r.situacao, r.motivo = PENDENTE, "PRs ainda não coletados: rodar scripts/coleta_github.py (versão nova)"
    else:
        p = gi[gi["is_pull_request"].fillna(False).astype(bool)].copy()
        if f.get("repos"):
            p = p[p["repositorio"].map(nq_nome).isin(f["repos"])]
        p["fechado"] = _local(p["closed_at"])
        p["aberto"] = _local(p["created_at"])
        p = p[(p["fechado"] >= ini) & (p["fechado"] < fim_ex)]
        p["horas"] = (p["fechado"] - p["aberto"]).dt.total_seconds() / 3600
        r.itens = p[["repositorio", "number", "title", "horas"]].sort_values("horas", ascending=False)
        _razao(r, int((p["horas"] <= L["revisao_pr_horas"]).sum()), len(p))
    r = novo("development_speed", "timely_feature_delivery", "Timely feature delivery — features entregues no prazo",
             "histórias (Feature) concluídas na primeira sprint em que entraram",
             "Features concluídas sem serem levadas para outra sprint ÷ Features concluídas no período",
             "sprints de cada história e data de conclusão", "Zenhub")
    if zh_ok:
        try:
            from src.metrics import gestao_agil as ga
            lin = ga.stories_por_sprint(snap, ctx.zh_iniciadas, ctx.zh_issues, ctx.zh_regras)
            lin = lin[lin["tipo"] == "Feature"].copy()
            lin["fim_sprint"] = _local(lin["sprint_fim"])
            concl = lin[lin["concluida"]]
            concl = concl[(concl["fim_sprint"] >= ini) & (concl["fim_sprint"] < fim_ex + pd.Timedelta(days=14))]
            primeira = lin.sort_values("ordem_sprint").groupby("issue_id")["sprint"].first()
            concl = concl.assign(no_prazo=concl["sprint"].values == primeira.reindex(concl["issue_id"]).values)
            r.itens = concl[["issue", "titulo", "sprint", "no_prazo"]]
            _razao(r, int(concl["no_prazo"].sum()), len(concl))
            r.motivo = aviso_zh
        except Exception as erro:  # noqa: BLE001
            r.situacao, r.motivo = SEM_DADO, f"não foi possível montar as sprints das histórias ({erro})"
    r = novo("development_speed", "timely_feature_specifications_delivery",
             "Timely feature specifications delivery — especificações no prazo",
             "especificações de features entregues no prazo", "—", "tarefas de especificação", "nenhuma")
    r.situacao, r.motivo = SEM_FONTE, "não há tarefas de especificação separadas (tipo ou label)"
    r = novo("development_speed", "core_component_commits", "Core component commits — commits no componente central",
             "commits no componente central antes da release", "—", "commits por componente", "nenhuma")
    r.situacao, r.motivo = SEM_FONTE, ("o documento define componente central por arquivos .bpmn (caso de uso da "
                                      "Modelio): não se aplica ao MeasureSoftGram")
    r = novo("development_speed", "non_issue_commits", "Non-issue component commit — commits ligados a issue",
             "commits que citam uma issue (valor = 1 − proporção de commits sem issue)",
             "commits sem referência a issue (#número) na mensagem ÷ commits no período",
             "mensagem de cada commit", "API do GitHub (commits)")
    if cm is None or cm.empty:
        r.situacao, r.motivo = PENDENTE, "commits ainda não coletados: rodar scripts/coleta_github.py (versão nova)"
    else:
        c = cm.copy()
        if f.get("repos"):
            c = c[c["repositorio"].map(nq_nome).isin(f["repos"])]
        c["quando"] = _local(c["data"])
        c = c[(c["quando"] >= ini) & (c["quando"] < fim_ex) & ~c["merge"]].drop_duplicates("sha")
        sem = ~c["mensagem"].fillna("").str.contains(r"#\d+|[A-Z]+-\d+", regex=True)
        r.itens = c[["repositorio", "sha", "mensagem"]].assign(sem_issue=sem)
        _razao(r, int(sem.sum()), len(c), complemento=True, rotulo_bruto="sem issue")

    # ── Issues' Velocity ──
    r = novo("issues_velocity", "resolved_issues_throughput", "Resolved issues' throughput — resolvidas no prazo",
             f"issues resolvidas em até {L['resolucao_dias']} dias",
             f"issues fechadas no período em até {L['resolucao_dias']} dias após criadas ÷ issues fechadas no período",
             "criação e fechamento de cada issue", "Zenhub")
    if zh_ok:
        fe = z[(z["fechada"] >= ini) & (z["fechada"] < fim_ex)].copy()
        fe["dias"] = (fe["fechada"] - fe["criada"]).dt.total_seconds() / 86400
        r.itens = fe[["repositorio", "number", "title", "tipo_issue", "dias"]].sort_values("dias", ascending=False)
        _razao(r, int((fe["dias"] <= L["resolucao_dias"]).sum()), len(fe))
        r.motivo = aviso_zh
    r = novo("issues_velocity", "issue_type_timeframe", "Issues-type in a timeframe — issues de um tipo",
             "densidade de issues de um tipo (aqui: Bug) criadas no período",
             "issues do tipo Bug criadas no período ÷ issues criadas no período", "tipo de cada issue", "Zenhub")
    if zh_ok:
        cr = z[(z["criada"] >= ini) & (z["criada"] < fim_ex)]
        _razao(r, int((cr["tipo_issue"] == "Bug").sum()), len(cr), rotulo_bruto="bugs entre as criadas")
        if r.situacao == CALCULADA:
            r.situacao, r.valor = INFORMATIVA, None
            r.motivo = "o documento deixa o tipo livre; com Bug repete Bug density, por isso fica fora da média"
    r = novo("issues_velocity", "team_throughput", "Team throughput — vazão do time",
             "densidade de issues resolvidas pelo time no período",
             "issues fechadas no período ÷ issues ativas no período (abertas em algum momento dele)",
             "status e datas de cada issue", "Zenhub")
    if zh_ok:
        ativas = z[(z["criada"] < fim_ex) & (z["fechada"].isna() | (z["fechada"] >= ini))]
        fe = ativas[ativas["fechada"].notna() & (ativas["fechada"] < fim_ex)]
        r.itens = ativas[["repositorio", "number", "title", "tipo_issue", "criada", "fechada"]]
        _razao(r, len(fe), len(ativas))
        r.motivo = aviso_zh
    r = novo("issues_velocity", "bugs_ratio", "Bugs ratio — issues abertas que não são bug",
             "densidade de issues abertas que não são bug", "issues abertas que não são Bug ÷ issues abertas",
             "tipo e status de cada issue", "Zenhub")
    if zh_ok:
        abertas = z[(z["criada"] < fim_ex) & (z["fechada"].isna() | (z["fechada"] >= fim_ex))]
        _razao(r, int((abertas["tipo_issue"] != "Bug").sum()), len(abertas))
        if r.situacao == CALCULADA:
            r.situacao = DERIVADA
            r.motivo = "é o complemento de Bug density (Software Stability): fica fora da média para não contar duas vezes"
    r = novo("issues_velocity", "old_issues", "Old issues — issues antigas",
             f"issues abertas há mais de {L['issue_antiga_dias']} dias (valor = 1 − proporção)",
             f"issues abertas há mais de {L['issue_antiga_dias']} dias no fim do período ÷ issues abertas",
             "criação e status de cada issue", "Zenhub")
    if zh_ok:
        abertas = z[(z["criada"] < fim_ex) & (z["fechada"].isna() | (z["fechada"] >= fim_ex))].copy()
        abertas["idade_dias"] = (fim_ex - abertas["criada"]).dt.days
        r.itens = abertas[["repositorio", "number", "title", "tipo_issue", "idade_dias"]].sort_values(
            "idade_dias", ascending=False)
        _razao(r, int((abertas["idade_dias"] > L["issue_antiga_dias"]).sum()), len(abertas), complemento=True,
               rotulo_bruto="antigas")
        r.motivo = aviso_zh

    # ── Testing Performance ──
    _, _, _, regra, formula = nq.METRICAS["testes_rapidos"]
    _sonar_media("testes_rapidos", notas, novo("testing_performance", "fast_tests", "Fast tests — testes rápidos",
                                               regra, formula, "duração de cada suíte de teste (UTS)",
                                               "SonarCloud via metrics.yml"))
    for chave, nome in (("long_tests", "Long tests — testes longos"),
                        ("unit_test_duration", "Unit test duration — duração dos testes unitários")):
        r = novo("testing_performance", chave, nome, "testes acima/abaixo do limiar de duração",
                 "complemento ou repetição de Fast tests", "duração de cada suíte", "SonarCloud")
        r.situacao, r.motivo = DERIVADA, "mesmo dado de Fast tests: fica fora da média para não contar duas vezes"
    r = novo("testing_performance", "error_identification", "Error identification — bugs identificados no período",
             "bugs identificados no período em relação a todos os identificados desde o início",
             "bugs criados no período ÷ bugs criados desde o início do semestre", "tipo e criação de cada issue",
             "Zenhub")
    if zh_ok:
        b = z[(z["tipo_issue"] == "Bug") & (z["criada"] < fim_ex)]
        _razao(r, int((b["criada"] >= ini).sum()), len(b), rotulo_bruto="dos bugs do semestre")
        if r.situacao == CALCULADA:
            r.situacao, r.valor = INFORMATIVA, None
            r.motivo = "não tem direção boa/ruim (mais bugs achados pode ser teste melhor): fica fora da média"
    r = novo("testing_performance", "error_correction", "Error correction — bugs corrigidos no prazo",
             f"bugs resolvidos em até {L['correcao_bug_dias']} dias",
             f"bugs fechados no período em até {L['correcao_bug_dias']} dias ÷ bugs fechados no período",
             "criação e fechamento de cada bug", "Zenhub")
    if zh_ok:
        b = z[(z["tipo_issue"] == "Bug") & (z["fechada"] >= ini) & (z["fechada"] < fim_ex)].copy()
        b["dias"] = (b["fechada"] - b["criada"]).dt.total_seconds() / 86400
        r.itens = b[["repositorio", "number", "title", "dias"]]
        _razao(r, int((b["dias"] <= L["correcao_bug_dias"]).sum()), len(b))
        if r.situacao != CALCULADA:
            r.motivo = "nenhum bug fechado no período"
    r = novo("testing_performance", "bug_leakage", "Bug leakage — bugs que escaparam da release",
             "bugs identificados depois da release em relação aos de antes",
             "bugs criados no período ÷ bugs criados antes do início do período", "tipo e criação de cada issue",
             "Zenhub")
    if zh_ok:
        b = z[z["tipo_issue"] == "Bug"]
        depois, antes = int(((b["criada"] >= ini) & (b["criada"] < fim_ex)).sum()), int((b["criada"] < ini).sum())
        r.numerador, r.denominador = depois, antes
        r.bruto = f"{depois} depois ÷ {antes} antes" + (f" = {depois / antes:.2f}".replace(".", ",") if antes else "")
        r.situacao = INFORMATIVA
        r.motivo = "razão sem teto (pode passar de 1): mostrada, fora da média"
    r = novo("testing_performance", "tests_per_product", "Tests per product — testes por issue",
             "número de testes em relação às issues do período", "testes (soma dos repositórios) ÷ issues fechadas no período",
             "testes de cada repositório e issues fechadas", "SonarCloud + Zenhub")
    tot = sum((n["avaliacao"]["metricas"]["testes_passando"]["denominador"] or 0) for n in notas.values())
    if zh_ok and tot:
        fe = z[(z["fechada"] >= ini) & (z["fechada"] < fim_ex)]
        r.numerador, r.denominador = tot, len(fe)
        r.bruto = f"{int(tot)} testes ÷ {len(fe)} issues" + (f" = {tot / len(fe):.1f}".replace(".", ",") if len(fe) else "")
        r.situacao, r.motivo = INFORMATIVA, "não é proporção de 0 a 1: mostrada, fora da média"
    r = novo("testing_performance", "ci_feedback_time", "CI feedback time — tempo de feedback da CI",
             "tempo médio que a CI leva para responder", "Σ duração das execuções ÷ execuções no período",
             "duração de cada execução de CI", "GitHub Actions")
    if not runs.empty and runs["duracao_min"].notna().any():
        d = runs["duracao_min"].dropna()
        r.numerador, r.denominador = float(d.sum()), len(d)
        r.bruto = f"{d.mean():.1f} min em média ({len(d)} execuções; mediana {d.median():.1f} min)".replace(".", ",")
        r.situacao, r.motivo = INFORMATIVA, "é um tempo, não proporção: a versão 0–1 é Build performance"
    for chave, nome, motivo in (
            ("developer_tester_communication", "Developer-tester communication — comunicação dev-teste",
             "não há papel de testador separado nem registro de feedback de teste nas issues"),
            ("commit_review_iterations", "Commit review iterations — iterações de revisão",
             "rodadas de revisão de cada PR não são coletadas (exigiria a API de reviews do GitHub)"),
            ("commit_response_time", "Commit response time — tempo de resposta da revisão",
             "horário da primeira revisão de cada PR não é coletado (exigiria a API de reviews do GitHub)")):
        r = novo("testing_performance", chave, nome, "—", "—", "—", "nenhuma")
        r.situacao, r.motivo = SEM_FONTE, motivo

    # ── agregação ──
    m = pd.DataFrame([{"fator": x.fator, "chave": x.chave, "valor": x.valor, "situacao": x.situacao} for x in out])
    fatores = []
    for fc, (nome, aspecto, tipo) in FATORES.items():
        x = m[(m["fator"] == fc) & m["situacao"].isin(NA_MEDIA)]
        fatores.append({"fator": fc, "nome": nome, "aspecto": aspecto, "tipo": tipo,
                        "valor": float(x["valor"].mean()) if not x.empty else None,
                        "metricas_na_media": len(x), "metricas": int((m["fator"] == fc).sum())})
    fat = pd.DataFrame(fatores)
    indicadores = []
    for ic, (nome, desc, fs) in INDICADORES.items():
        x = fat[fat["fator"].isin(fs) & fat["valor"].notna()]
        indicadores.append({"indicador": ic, "nome": nome, "descricao": desc,
                            "valor": float(x["valor"].mean()) if not x.empty else None,
                            "fatores_na_media": len(x), "fatores": len(fs)})
    return {"metricas": out, "fatores": fat, "indicadores": pd.DataFrame(indicadores), "notas": notas}


def tabela(resultados: list[Resultado]) -> pd.DataFrame:
    """Resultados em tabela (CSV e telas)."""
    return pd.DataFrame([{
        "indicador": next((v[0] for v in INDICADORES.values() if r.fator in v[2]), ""),
        "fator": FATORES[r.fator][0], "aspecto": FATORES[r.fator][1], "chave": r.chave, "metrica": r.nome,
        "descricao": r.descricao, "formula": r.formula, "dado_bruto": r.dado_bruto, "fonte": r.fonte,
        "situacao": ROTULO[r.situacao], "valor": r.valor, "bruto": r.bruto, "numerador": r.numerador,
        "denominador": r.denominador, "observacao": r.motivo} for r in resultados])


def resumo_situacao(resultados: list[Resultado]) -> dict:
    s = pd.Series([r.situacao for r in resultados]).value_counts()
    return {ROTULO[k]: int(s.get(k, 0)) for k in ROTULO}


# Compatibilidade: a conferência simples de dados (usada antes na página Qualidade técnica).
def disponibilidade(ctx, f: dict, rec: dict) -> pd.DataFrame:
    t = tabela(calcular(ctx, f, rec)["metricas"])
    return t.rename(columns={"observacao": "detalhe"})

