"""Plano de qualidade Q-Rapids: indicadores estratégicos → fatores → métricas → dado bruto.

Segue ``docs/planejamento/selecaometricas.mdx`` (quais métricas entram) e ``docs/planejamento/metas.mdx``
(como agregar, metas da R3, piso, situação e portões). O que o plano decide:

* **10 métricas incluídas** (M1, M2, M3, M5, M6, M7, M8, M9, M10 e DT) entram na agregação;
* **8 monitoradas** aparecem com valor, mas não têm peso em nenhum fator;
* **8 habilitáveis** e **18 excluídas** só aparecem no catálogo, com a justificativa do plano;
* fator = média simples das suas métricas incluídas (escala 0–1, 1 = melhor);
* indicador = soma dos fatores avaliados com peso 1/n; fator sem dado sai do denominador, nunca vale zero;
* M8 (minutos) não está em 0–1: é **portão**, não entra na média;
* a meta nasce na métrica; a do fator é a média das metas das métricas e a do indicador é a fórmula aplicada
  às metas dos fatores, truncada em 2 casas; o piso é o valor da R2.

Os valores de M1, M2, M3 e M5 usam as funções do notebook da disciplina (``src/metrics/qualidade.py``).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pandas as pd

import config
from src.metrics import qualidade as nq

L = config.QRAPIDS["limiares"]
PLANO = config.QRAPIDS["plano"]

CALCULADA, SEM_DADO, PENDENTE, INFORMATIVA = "calculada", "sem dado no recorte", "coleta pendente", "informativa"
ROTULO = {CALCULADA: "Calculada", SEM_DADO: "Sem dado no recorte", PENDENTE: "Coleta pendente",
          INFORMATIVA: "Só informativa"}
INCLUIDA, MONITORADA, HABILITAVEL, EXCLUIDA = "Incluída", "Monitorada", "Habilitável", "Excluída"

# ───────────────────────── estrutura do modelo (mapa da seção "Indicadores estratégicos e fatores") ─────────────────────────

INDICADORES = config.QRAPIDS_INDICADORES
# fatores que entram na média de cada indicador (os demais não têm métrica incluída ou são só portão)
AVALIADOS = config.QRAPIDS_AVALIADOS
FATORES = config.QRAPIDS_FATORES

# chave → (código, nome, fator, decisão). Só as incluídas e as monitoradas são calculadas.
METRICAS = config.QRAPIDS_METRICAS
TIPO_META = config.QRAPIDS_TIPO_META
TIPOS_FORA_M9 = {"Epic", "Project (pacote trabalho)", "Initiative (entrega)"}
STATUS = {"verde": "🟢 Atingido", "amarelo": "🟡 Em evolução", "vermelho": "🔴 Abaixo do piso", "sem": "—"}


@dataclass
class Resultado:
    fator: str
    chave: str
    nome: str
    descricao: str
    formula: str
    dado_bruto: str
    fonte: str
    codigo: str = "—"
    decisao: str = MONITORADA
    situacao: str = SEM_DADO
    valor: float | None = None          # 0 a 1, 1 = melhor
    bruto: str = ""                     # o número como o plano define (ex.: "12 de 40 = 30,0%")
    numerador: float | None = None
    denominador: float | None = None
    motivo: str = ""                    # por que não foi calculada, ou observação
    escala01: bool = True               # False: grandeza fora de 0–1 (M8), nunca entra na média
    medida: float | None = None         # valor fora de 0–1 (ex.: minutos)
    itens: pd.DataFrame = field(default_factory=pd.DataFrame)       # dado bruto para conferência
    por_repo: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def na_media(self) -> bool:
        return (self.decisao == INCLUIDA and self.situacao == CALCULADA and self.escala01
                and self.valor is not None and not pd.isna(self.valor))


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


def nq_nome(repo: str) -> str:
    from src.data.sonar import nome_curto
    return nome_curto(repo)


def truncar(x: float, casas: int = 2) -> float:
    """Trunca (não arredonda) — a meta do indicador nunca pode subir por arredondamento (regra 2 do plano)."""
    f = 10 ** casas
    return math.floor(x * f + 1e-9) / f


def repos_esperados(f: dict) -> list[str]:
    """O escopo vem da configuração/seleção, nunca da disponibilidade da coleta."""
    return [r for r in config.QRAPIDS["linguagem"] if not f.get("repos")
            or nq_nome(r) in f["repos"] or r in f["repos"]]


def media_fatores(indicador: str, valores: dict) -> float | None:
    pesos = PLANO["pesos_fatores"].get(indicador)
    if pesos is None:
        return sum(valores.values()) / len(valores) if valores else None
    fatores = AVALIADOS[indicador]
    if (set(pesos) != set(fatores) or any(not math.isfinite(v) or v < 0 for v in pesos.values())
            or sum(pesos.values()) <= 0):
        raise ValueError(f"Pesos inválidos para {indicador}: informar todos os fatores com pesos não negativos")
    total = sum(pesos[f] for f in valores)
    return sum(v * pesos[f] for f, v in valores.items()) / total if total else None


def restricoes_por_repo(res: dict, rec: dict) -> pd.DataFrame:
    """Pisos de M5/M10 independentes da média; ausência de dado impede comprovar o piso."""
    resultados = {r.chave: r for r in res["metricas"]}
    linhas = []
    for chave, piso in PLANO["piso_por_repo"].items():
        r = resultados[chave]
        valores = dict(zip(r.por_repo["repositorio"], r.por_repo["valor"])) if not r.por_repo.empty else {}
        ausentes = set(r.por_repo.loc[r.por_repo.get("zero_por_falta", pd.Series("", index=r.por_repo.index)) != "",
                                        "repositorio"]) if not r.por_repo.empty else set()
        indicador = "blocking" if chave == "test_coverage" else "product_readiness"
        for repo in rec["repos"]:
            nome = nq_nome(repo)
            valor = valores.get(nome) if nome not in ausentes else None
            linhas.append({"indicador": indicador, "metrica": r.codigo, "repositorio": nome, "valor": valor,
                           "piso": piso, "passa": valor is not None and pd.notna(valor) and valor >= piso,
                           "situacao": "Sem dado" if valor is None or pd.isna(valor) else
                                       ("Passa" if valor >= piso else "Abaixo do piso")})
    return pd.DataFrame(linhas, columns=["indicador", "metrica", "repositorio", "valor", "piso", "passa", "situacao"])


# ───────────────────────── dados do SonarCloud por repositório ─────────────────────────

def avaliacoes_por_repo(ctx, f: dict, rec: dict) -> dict:
    """Avaliação das métricas do notebook na última coleta do pipeline dentro do período, por repositório.

    ``{repo: {"avaliacao": ..., "coleta": Timestamp, "arquivo": nome do .json}}``.
    """
    comp = ctx.sonar_componentes
    if comp is None or comp.empty:
        return {}
    fim = pd.Timestamp(rec["fim"]) + pd.Timedelta(days=1)
    inicio = pd.Timestamp(f["periodo"][0])
    coletas = pd.to_datetime(comp["coleta"])
    c = comp[comp["repositorio"].isin(rec["repos"]) & (coletas >= inicio) & (coletas < fim)]
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


def _sonar_media(chave_nb: str, notas: dict, r: Resultado) -> Resultado:
    """Métrica do notebook como média simples dos repositórios (o detalhe por repositório vai junto)."""
    linhas, itens = [], []
    for repo, n in notas.items():
        m = n["avaliacao"]["metricas"][chave_nb]
        if not m["itens"].empty:
            itens.append(m["itens"].assign(repositorio=nq_nome(repo), linguagem=n["avaliacao"]["linguagem"],
                                         coleta=n["coleta"], arquivo_coleta=n["arquivo"]))
        linhas.append({"repositorio": nq_nome(repo), "linguagem": n["avaliacao"]["linguagem"], "valor": m["valor"], "numerador": m["numerador"],
                       "denominador": m["denominador"], "zero_por_falta": m["zero_por_falta"] or "",
                       "coleta": n["coleta"], "arquivo": n["arquivo"]})
    if not linhas:
        r.situacao, r.motivo = SEM_DADO, "nenhuma coleta do pipeline até o fim do período"
        return r
    d = pd.DataFrame(linhas)
    r.por_repo = d
    r.itens = pd.concat(itens, ignore_index=True) if itens else pd.DataFrame()
    com = d[d["zero_por_falta"] == ""]
    if com.empty:
        r.situacao, r.motivo = SEM_DADO, "nenhum repositório com esse dado no .json do pipeline"
        return r
    r.valor = float(com["valor"].mean())
    r.situacao = CALCULADA
    r.bruto = f"média de {len(com)} repositórios"
    zeros = d[d["zero_por_falta"] != ""]
    if len(zeros):
        r.motivo = ("sem o dado no .json do pipeline (fora da média): " + ", ".join(zeros["repositorio"]))
    return r


def _arquivos_api(ctx, rec) -> pd.DataFrame:
    """Medidas por arquivo da API do SonarCloud (última coleta até o fim do período), código da linguagem."""
    a = (ctx.sonar_api or {}).get("arquivos", pd.DataFrame())
    if a is None or a.empty:
        return pd.DataFrame()
    fim = pd.Timestamp(rec["fim"]) + pd.Timedelta(days=1)
    inicio = pd.Timestamp(rec.get("inicio", config.INICIO_SEMESTRE))
    a = a[a["repositorio"].isin(rec["repos"]) & (pd.to_datetime(a["coleta"]) >= inicio)
          & (pd.to_datetime(a["coleta"]) < fim) & (a["tipo"] == "FIL")]
    if not a.empty:
        a = a[a["coleta"] == a.groupby("repositorio")["coleta"].transform("max")]
    if a.empty:
        return a
    w = a.pivot_table(index=["repositorio", "componente", "linguagem"], columns="metrica", values="valor",
                      aggfunc="last").reset_index()
    w["lingua_repo"] = w["repositorio"].map(config.QRAPIDS["linguagem"])
    w = w[(w["linguagem"] == w["lingua_repo"]) | w["lingua_repo"].isna()]
    return w[w.get("ncloc", pd.Series(0, index=w.index)) > 0] if "ncloc" in w else w


# ───────────────────────── dados do Zenhub e do GitHub ─────────────────────────

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


def runs_de_build(runs: pd.DataFrame) -> pd.DataFrame:
    """Execuções que contam como build: só os workflows de ``config.QRAPIDS["workflows_build"]`` e só as
    que terminaram em sucesso ou falha (cancelada e ignorada não dizem se o build está estável nem quanto
    ele demora). Lista de workflows vazia = todos."""
    if runs is None or runs.empty:
        return runs if runs is not None else pd.DataFrame()
    nomes = set(config.QRAPIDS.get("workflows_build") or [])
    r = runs[runs["workflow"].isin(nomes)] if nomes else runs
    return r[r["conclusao"].isin(["success", "failure"])]


def _sprints(ctx) -> pd.DataFrame:
    s = getattr(ctx, "zh_sprints", None)
    if s is None or s.empty:
        return pd.DataFrame()
    s = s.copy()
    s["inicio"], s["fim"], s["prazo"] = _local(s["start_date"]), _local(s["end_date"]), _local(s["count_until"])
    return s


def _agora(ctx) -> pd.Timestamp:
    a = getattr(ctx, "agora_utc", None)
    if a is not None:
        return _local(pd.Series([pd.Timestamp(a)])).iloc[0]
    return pd.Timestamp(ctx.hoje) + pd.Timedelta(days=1)


def _na_sprint(lista, rotulo) -> bool:
    return isinstance(lista, (list, tuple)) and rotulo in lista


def _janela(rel: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    nomes = list(config.RELEASES)
    fim = pd.Timestamp(config.RELEASES[rel])
    i = nomes.index(rel)
    ini = pd.Timestamp(config.RELEASES[nomes[i - 1]]) + pd.Timedelta(days=1) if i else pd.Timestamp(config.INICIO_SEMESTRE)
    return ini, fim


def _release_de(fim: pd.Timestamp) -> str:
    return next((r for r, d in config.RELEASES.items() if pd.Timestamp(d) >= fim), list(config.RELEASES)[-1])


# ───────────────────────── cálculo das métricas ─────────────────────────

def calcular(ctx, f: dict, rec: dict, ultima_sprint: bool = False) -> dict:
    """Métricas incluídas e monitoradas do plano no período ``f["periodo"]`` (Sonar: último snapshot até o fim).

    ``ultima_sprint``: M9 usa só a última sprint concluída do período (como a coluna "Atual" do metas.mdx);
    sem isso, M9 é a razão agregada das sprints concluídas no período (como R1 e R2).
    Devolve ``{"metricas": [Resultado], "fatores": DataFrame, "indicadores": DataFrame, "avaliacoes": {...}}``.
    """
    ini = pd.Timestamp(f["periodo"][0])
    fim = pd.Timestamp(rec["fim"])
    fim_ex = fim + pd.Timedelta(days=1)
    avs = avaliacoes_por_repo(ctx, f, rec)
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
        runs = runs_de_build(runs)      # só o workflow de testes, concluído (D5)
    out: list[Resultado] = []

    def novo(chave, descricao, formula, dado_bruto, fonte):
        codigo, nome, fator, decisao = METRICAS[chave]
        r = Resultado(fator, chave, f"{codigo} {nome}" if codigo != "—" else nome, descricao, formula, dado_bruto,
                      fonte, codigo=codigo, decisao=decisao)
        out.append(r)
        return r

    # ── Code Quality: M1, M2 (incluídas) e Mc (monitorada) ──
    for chave_nb, chave, desc in (
            ("complexidade", "complexity", "arquivos abaixo do limiar de complexidade ciclomática"),
            ("duplicacao", "duplication", "arquivos abaixo do limiar de linhas duplicadas"),
            ("comentarios", "comments", "arquivos com densidade de comentários dentro da faixa")):
        _, _, _, regra, formula = nq.METRICAS[chave_nb]
        _sonar_media(chave_nb, avs, novo(chave, desc, f"{formula} · {regra}", "medidas de cada arquivo (.json do pipeline)",
                                         "SonarCloud via metrics.yml"))

    # ── Quality Issues' Specification: M7 ──
    r = novo("well_defined_issues", "issues com descrição e prazo preenchidos",
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
        no_sprint = pd.Series([(nq_nome(a), int(b)) in em_sprint for a, b in zip(g["repositorio"], g["number"])],
                              index=g.index, dtype=bool)
        g["com_prazo"] = g["milestone"].notna() | no_sprint
        g["bem_definida"] = g["com_descricao"] & g["com_prazo"]
        r.motivo = ("prazo = milestone do GitHub ou sprint no Zenhub"
                    + (f"; {aviso_zh}" if aviso_zh else "")
                    + ("; nenhuma issue tem milestone" if g["milestone"].isna().all() else ""))
        r.itens = g[["repositorio", "number", "title", "com_descricao", "com_prazo", "bem_definida"]]
        _razao(r, int(g["bem_definida"].sum()), len(g))

    # ── Blocking Code: M6 ──
    r = novo("non_blocking_files", "arquivos sem violação bloqueante ou crítica",
             "arquivos com 0 blocker_violations e 0 critical_violations ÷ arquivos de código",
             "violações por arquivo e severidade", "API do SonarCloud (component_tree)")
    aa = _arquivos_api(ctx, rec)
    if aa.empty or not {"blocker_violations", "critical_violations"} <= set(aa.columns):
        r.situacao, r.motivo = PENDENTE, ("sem coleta de violações por arquivo até o fim do período (a coleta por "
                                          "arquivo só existe a partir de 07/11; rodar scripts/coleta_sonar.py)")
    else:
        aa = aa.dropna(subset=["blocker_violations", "critical_violations"])
        aa = aa.copy()
        aa["passa"] = (aa["blocker_violations"] == 0) & (aa["critical_violations"] == 0)
        r.itens = aa[["repositorio", "linguagem", "componente", "blocker_violations", "critical_violations", "passa"]]
        r.por_repo = (aa.assign(repositorio=aa["repositorio"].map(nq_nome)).groupby(["repositorio", "linguagem"])["passa"].agg(numerador="sum", denominador="size")
                      .reset_index().assign(valor=lambda d: d["numerador"] / d["denominador"]))
        _razao(r, int(aa["passa"].sum()), len(aa))

    # ── Testing Status: M3, M5 ──
    for chave_nb, chave in (("testes_passando", "test_success"), ("cobertura", "test_coverage")):
        _, _, _, regra, formula = nq.METRICAS[chave_nb]
        _sonar_media(chave_nb, avs, novo(chave, regra, formula, "testes, erros e falhas / cobertura de cada arquivo",
                                         "SonarCloud via metrics.yml"))

    # ── Testing Performance: M8 (portão) e M4 (monitorada) ──
    r = novo("ci_feedback_time", "tempo que o workflow de testes (test.yml) leva para responder",
             "mediana da duração das execuções de test.yml concluídas no período, em minutos (por repositório)",
             "duração de cada execução do workflow de testes", "GitHub Actions")
    r.escala01 = False
    if not runs.empty and runs["duracao_min"].notna().any():
        d = runs.dropna(subset=["duracao_min"])
        r.itens = d[["repositorio", "workflow", "duracao_min", "criado", "url"]].sort_values("duracao_min",
                                                                                            ascending=False)
        r.por_repo = (d.groupby(d["repositorio"].map(nq_nome))["duracao_min"]
                      .agg(mediana="median", execucoes="size").reset_index())
        r.medida = float(d["duracao_min"].median())
        r.numerador, r.denominador = float(d["duracao_min"].sum()), len(d)
        r.bruto = f"mediana {r.medida:.1f} min em {len(d)} execuções".replace(".", ",")
        r.situacao = CALCULADA
        r.motivo = f"portão: mediana ≤ {PLANO['portao_ci_mediana_min']:g} min em cada repositório; fora da média 0–1"
    _, _, _, regra, formula = nq.METRICAS["testes_rapidos"]
    _sonar_media("testes_rapidos", avs, novo("fast_tests", regra, formula, "duração de cada suíte de teste (UTS)",
                                             "SonarCloud via metrics.yml"))

    # ── Issues' Velocity: M9 ──
    r = novo("team_throughput", "issues da sprint fechadas até o prazo de fechamento da sprint",
             "issues da sprint fechadas até 08:00 do dia seguinte ao fim da sprint ÷ issues da sprint "
             "(sem Epic, pacote de trabalho e Iniciativa)", "status e datas de cada issue da sprint", "Zenhub")
    sp = _sprints(ctx)
    if not zh_ok or sp.empty:
        r.situacao, r.motivo = SEM_DADO, "sem snapshot do Zenhub com sprints"
    else:
        base = z[~z["tipo_issue"].isin(TIPOS_FORA_M9)]
        limite = min(fim_ex, _agora(ctx))
        linhas = []
        for s in sp.itertuples():
            conc = s.prazo <= limite
            if (ini <= s.fim < fim_ex) or (ultima_sprint and not conc and s.inicio < fim_ex <= s.fim + pd.Timedelta(days=1)
                                           and s.fim >= ini):
                x = base[base["sprints"].map(lambda l, rot=s.sprint_label: _na_sprint(l, rot))]
                fech = int((x["fechada"].notna() & (x["fechada"] <= s.prazo)).sum())
                linhas.append({"sprint": s.sprint_label, "inicio": s.inicio, "fim": s.fim, "prazo": s.prazo,
                               "fechadas": fech, "planejadas": len(x), "concluida": bool(conc),
                               "valor": fech / len(x) if len(x) else None})
        t = pd.DataFrame(linhas)
        conc = t[t["concluida"] & (t["planejadas"] > 0)] if not t.empty else t
        if conc.empty:
            r.situacao, r.motivo = SEM_DADO, "nenhuma sprint concluída no período"
            r.itens = t
        else:
            r.itens = t
            if ultima_sprint:
                u = conc.sort_values("fim").iloc[-1]
                _razao(r, int(u["fechadas"]), int(u["planejadas"]), rotulo_bruto=f"sprint {u['sprint']}")
            else:
                _razao(r, int(conc["fechadas"].sum()), int(conc["planejadas"].sum()),
                       rotulo_bruto=f"sprints {conc['sprint'].iloc[0]}–{conc['sprint'].iloc[-1]}")
            r.motivo = aviso_zh

    # ── Product Stability: M10 ──
    r = novo("build_stability", "execuções do workflow de testes (test.yml) com sucesso",
             "execuções de test.yml com sucesso ÷ execuções de test.yml com sucesso ou falha, no período",
             "resultado de cada execução do workflow de testes", "GitHub Actions")
    if not runs.empty:
        c = runs[runs["conclusao"].isin(["success", "failure"])]
        r.itens = c[["repositorio", "workflow", "conclusao", "criado", "duracao_min", "url"]]
        r.por_repo = (c.groupby(c["repositorio"].map(nq_nome))["conclusao"].agg(
            sucesso=lambda s: int((s == "success").sum()), total="size").reset_index()
            .assign(valor=lambda d: d["sucesso"] / d["total"]))
        _razao(r, int((c["conclusao"] == "success").sum()), len(c))

    # ── Activities Completion: DT ──
    r = novo("development_task_completion", "Tasks e Sub-tasks das sprints da release fechadas até a data da release",
             "Tasks e Sub-tasks das sprints da release fechadas até a data da release (ou do fim do período, se "
             "vier antes) ÷ Tasks e Sub-tasks das sprints da release", "tipo, status e sprint de cada issue", "Zenhub")
    if not zh_ok or sp.empty:
        r.situacao, r.motivo = SEM_DADO, "sem snapshot do Zenhub com sprints"
    else:
        rel = _release_de(fim)
        rel_ini, rel_fim = _janela(rel)
        rel_fim_ex = rel_fim + pd.Timedelta(days=1)
        doss = sp[(sp["fim"] >= rel_ini) & (sp["fim"] < rel_fim_ex) & (sp["inicio"] < fim_ex)]
        rotulos = set(doss["sprint_label"])
        t = z[z["tipo_issue"].isin(["Task", "Sub-task"])
              & z["sprints"].map(lambda l: any(_na_sprint(l, x) for x in rotulos))].copy()
        corte = min(fim_ex, rel_fim_ex)
        t["concluida"] = t["fechada"].notna() & (t["fechada"] < corte)
        r.itens = t[["repositorio", "number", "title", "tipo_issue", "criada", "fechada", "concluida"]]
        _razao(r, int(t["concluida"].sum()), len(t), rotulo_bruto=f"release {rel}, sprints "
               + ", ".join(sorted(rotulos, key=lambda x: int(re.sub(r"\D", "", x) or 0))))
        r.motivo = ("release em andamento: o valor só é comparável ao piso no fechamento" if fim < rel_fim else "")
        r.motivo = "; ".join(x for x in (r.motivo, aviso_zh) if x)

    # ── monitoradas de processo: sem peso em nenhum fator ──
    r = novo("resolved_issues_throughput", f"issues resolvidas em até {L['resolucao_dias']} dias",
             f"issues fechadas no período em até {L['resolucao_dias']} dias após criadas ÷ issues fechadas no período",
             "criação e fechamento de cada issue", "Zenhub")
    if zh_ok:
        fe = z[(z["fechada"] >= ini) & (z["fechada"] < fim_ex)].copy()
        fe["dias"] = (fe["fechada"] - fe["criada"]).dt.total_seconds() / 86400
        r.itens = fe[["repositorio", "number", "title", "tipo_issue", "dias"]].sort_values("dias", ascending=False)
        _razao(r, int((fe["dias"] <= L["resolucao_dias"]).sum()), len(fe))
        r.motivo = aviso_zh
    r = novo("old_issues", f"issues abertas há mais de {L['issue_antiga_dias']} dias (valor = 1 − proporção)",
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
    r = novo("build_performance", f"execuções do workflow de testes que não passaram de {L['build_rapido_min']} min",
             f"execuções de test.yml com duração ≤ {L['build_rapido_min']} min ÷ execuções de test.yml concluídas "
             "no período", "duração de cada execução do workflow de testes", "GitHub Actions")
    if not runs.empty:
        d = runs.dropna(subset=["duracao_min"])
        r.itens = d[["repositorio", "workflow", "duracao_min", "criado", "url"]].sort_values("duracao_min",
                                                                                            ascending=False)
        _razao(r, int((d["duracao_min"] <= L["build_rapido_min"]).sum()), len(d))
    r = novo("commit_review_duration", f"pull requests fechados em até {L['revisao_pr_horas']} h",
             f"PRs fechados em até {L['revisao_pr_horas']} h após abertos ÷ PRs fechados no período",
             "abertura e fechamento de cada PR", "API do GitHub (issues/PRs)")
    if gi is None or gi.empty:
        r.situacao, r.motivo = PENDENTE, "PRs ainda não coletados: rodar scripts/coleta_github.py"
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
    r = novo("timely_feature_delivery", "histórias (Feature) concluídas na primeira sprint em que entraram",
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
    r = novo("non_issue_commits", "commits que citam uma issue (valor = 1 − proporção de commits sem issue)",
             "commits sem referência a issue (#número) na mensagem ÷ commits no período",
             "mensagem de cada commit", "API do GitHub (commits)")
    if cm is None or cm.empty:
        r.situacao, r.motivo = PENDENTE, "commits ainda não coletados: rodar scripts/coleta_github.py"
    else:
        c = cm.copy()
        if f.get("repos"):
            c = c[c["repositorio"].map(nq_nome).isin(f["repos"])]
        c["quando"] = _local(c["data"])
        c = c[(c["quando"] >= ini) & (c["quando"] < fim_ex) & ~c["merge"]].drop_duplicates("sha")
        sem = ~c["mensagem"].fillna("").str.contains(r"#\d+|[A-Z]+-\d+", regex=True)
        r.itens = c[["repositorio", "sha", "mensagem"]].assign(sem_issue=sem)
        _razao(r, int(sem.sum()), len(c), complemento=True, rotulo_bruto="sem issue")

    fat, ind = agregar(out)
    return {"metricas": out, "fatores": fat, "indicadores": ind, "avaliacoes": avs}


# ───────────────────────── agregação (metas.mdx: "Fórmula dos indicadores") ─────────────────────────

def agregar(resultados: list[Resultado]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fator = média das métricas incluídas calculadas (0–1); indicador = soma dos fatores avaliados com peso 1/n.

    Fator sem métrica calculada sai do denominador do indicador: a falta de dado não vira nota ruim.
    """
    fatores = []
    for fc, (nome, tipo, motivo) in FATORES.items():
        x = [r.valor for r in resultados if r.fator == fc and r.na_media]
        fatores.append({"fator": fc, "nome": nome, "tipo": tipo,
                        "valor": float(sum(x) / len(x)) if x else None, "metricas_na_media": len(x),
                        "metricas": sum(1 for r in resultados if r.fator == fc and r.decisao == INCLUIDA),
                        "fora_do_calculo": motivo})
    fat = pd.DataFrame(fatores)
    indicadores = []
    for ic, (nome, desc, fs) in INDICADORES.items():
        x = fat[fat["fator"].isin(AVALIADOS[ic]) & fat["valor"].notna()]
        indicadores.append({"indicador": ic, "nome": nome, "descricao": desc,
                            "valor": media_fatores(ic, dict(zip(x["fator"], x["valor"]))),
                            "fatores_na_media": len(x), "fatores_avaliados": len(AVALIADOS[ic]), "fatores": len(fs)})
    return fat, pd.DataFrame(indicadores)


def metas_agregadas() -> tuple[dict, dict]:
    """Meta de cada fator (média das metas das métricas) e de cada indicador (fórmula sobre as metas, truncada)."""
    metas = PLANO["metas"]
    mf = {}
    for fc in FATORES:
        v = [metas[k] for k, (_, _, fator, dec) in METRICAS.items() if fator == fc and dec == INCLUIDA and k in metas]
        if v:
            mf[fc] = sum(v) / len(v)
    mi = {}
    for ic, fs in AVALIADOS.items():
        v = [mf[fc] for fc in fs if fc in mf]
        if v:
            mi[ic] = truncar(media_fatores(ic, {fc: mf[fc] for fc in fs if fc in mf}))
    return mf, mi


# ───────────────────────── portões (metas.mdx: "Portões obrigatórios") ─────────────────────────

def portoes(res: dict, rec: dict) -> pd.DataFrame:
    """Condições obrigatórias que ficam fora da nota: o indicador só conta como atingido se todas passarem."""
    m = {r.chave: r for r in res["metricas"]}
    linhas = []
    atual = rec["atual"]
    esperados = {nq_nome(r) for r in rec.get("repos", repos_esperados({}))}
    regras = PLANO["portoes"]

    def por_repo(metrica, ok, rotulo, indicador, unidade="%"):
        d = atual[atual["metrica"] == metrica]
        if d.empty:
            linhas.append({"portao": rotulo, "indicador": indicador, "passa": None,
                           "detalhe": "sem dado do SonarCloud: " + ", ".join(sorted(esperados))})
            return
        bons = {nq_nome(r): v for r, v in zip(d["repositorio"], d["valor"])}
        ruins = {k: v for k, v in bons.items() if not ok(v)}
        faltam = esperados - bons.keys()
        linhas.append({"portao": rotulo, "indicador": indicador, "passa": False if ruins else (None if faltam else True),
                       "detalhe": ("todos os disponíveis passam" if not ruins else "reprovam: " + ", ".join(
                           f"{k} {v:.1f}".replace(".", ",") + unidade for k, v in sorted(ruins.items())))
                                  + ("; sem dado: " + ", ".join(sorted(faltam)) if faltam else "")})

    cob = regras["coverage"]["limiar"]
    dup = regras["duplicated_lines_density"]["limiar"]
    por_repo("coverage", lambda v: v >= cob, f"Cobertura global ≥ {cob:g}% em cada repositório", "Blocking")
    por_repo("duplicated_lines_density", lambda v: v <= dup,
             f"Duplicação global ≤ {dup:g}% em cada repositório", "Product Quality · Product Readiness")
    r6 = m["non_blocking_files"]
    if r6.situacao == CALCULADA:
        ruins = int(r6.denominador - r6.numerador)
        repos_ruins = r6.por_repo.loc[r6.por_repo["valor"] < 1, "repositorio"]
        linhas.append({"portao": "Zero arquivo com violação blocker ou critical", "indicador": "Blocking",
                       "passa": False if ruins else (True if esperados <= set(r6.por_repo["repositorio"]) else None),
                       "detalhe": ("nenhum arquivo" if ruins == 0 else f"{ruins} arquivos a corrigir")
                                  + ("; repositórios: " + ", ".join(sorted(repos_ruins)) if len(repos_ruins) else "")
                                  + ("; sem dado: " + ", ".join(sorted(esperados - set(r6.por_repo["repositorio"])))
                                     if esperados - set(r6.por_repo["repositorio"]) else "")})
    else:
        linhas.append({"portao": "Zero arquivo com violação blocker ou critical", "indicador": "Blocking",
                       "passa": None, "detalhe": "sem coleta de violações por arquivo"})
    r8, lim = m["ci_feedback_time"], regras["ci_feedback_time"]["limiar"]
    if r8.situacao == CALCULADA and not r8.por_repo.empty:
        ruins = r8.por_repo[r8.por_repo["mediana"] > lim]
        faltam = esperados - set(r8.por_repo["repositorio"])
        linhas.append({"portao": f"Mediana do test.yml ≤ {lim:g} min em cada repositório", "indicador": "Process Performance",
                       "passa": False if not ruins.empty else (None if faltam else True), "detalhe": ("todos os disponíveis passam" if ruins.empty else "reprovam: " + ", ".join(
                           f"{a} {b:.1f} min".replace(".", ",") for a, b in zip(ruins["repositorio"], ruins["mediana"])))
                       + ("; sem execuções: " + ", ".join(sorted(faltam)) if faltam else "")})
    else:
        linhas.append({"portao": f"Mediana do test.yml ≤ {lim:g} min em cada repositório",
                       "indicador": "Process Performance", "passa": None, "detalhe": "sem execuções no período"})
    r3, alvo = m["test_success"], len(esperados)
    if not r3.por_repo.empty:
        presentes = set(r3.por_repo.loc[r3.por_repo["zero_por_falta"] == "", "repositorio"]) & esperados
        com = len(presentes)
        sem = sorted(esperados - presentes)
        linhas.append({"portao": f"Relatório de testes em {alvo} de {alvo} repositórios", "indicador": "Blocking",
                       "passa": bool(alvo and com >= alvo), "detalhe": f"{com} de {alvo}" + (f"; sem relatório: {', '.join(sem)}" if sem else "")})
    else:
        linhas.append({"portao": f"Relatório de testes em {alvo} de {alvo} repositórios", "indicador": "Blocking",
                       "passa": None, "detalhe": "sem coleta do pipeline"})
    tabela_portoes = pd.DataFrame(linhas)
    for i, chave in enumerate(("coverage", "duplicated_lines_density", "non_blocking_files", "ci_feedback_time", "test_success")):
        tabela_portoes.loc[i, "indicador"] = " · ".join(INDICADORES[k][0] for k in regras[chave]["indicadores"])
    return tabela_portoes


# ───────────────────────── R1 × R2 × Atual com meta, piso e situação ─────────────────────────

def janelas(ctx, fim_atual=None) -> dict:
    """Janelas de comparação: R1, R2 e "Atual" (do dia seguinte à entrega da R2 até hoje ou ``fim_atual``)."""
    r2_fim = pd.Timestamp(config.RELEASES["R2"])
    r3_fim = pd.Timestamp(config.RELEASES["R3"])
    fim = pd.Timestamp(fim_atual) if fim_atual is not None else min(pd.Timestamp(ctx.hoje), r3_fim)
    return {"R1": _janela("R1"), "R2": _janela("R2"), "Atual": (r2_fim + pd.Timedelta(days=1), fim)}


def _situacao(valor, piso, meta, portoes_ok) -> str:
    if valor is None or pd.isna(valor):
        return STATUS["sem"]
    if piso is not None and not pd.isna(piso) and valor < piso:
        return STATUS["vermelho"]
    if valor >= meta and portoes_ok is True:
        return STATUS["verde"]
    return STATUS["amarelo"]


def avaliar_releases(ctx, f: dict, fim_atual=None) -> dict:
    """Todas as métricas, fatores e indicadores em R1, R2 e Atual, com meta da R3, piso (R2) e situação."""
    from src.components import filters   # import tardio: filters usa streamlit
    jan = janelas(ctx, fim_atual)
    branch = f.get("branch") or config.SONAR_BRANCH
    res, recs = {}, {}
    for nome, (ini, fim) in jan.items():
        f2 = {**f, "periodo": (ini, fim), "branch": branch}
        rec = filters.sonar(ctx, f2)
        rec = {**rec, "inicio": ini, "repos": repos_esperados(f)}
        rec["atual"] = rec["atual"][pd.to_datetime(rec["atual"]["coleta"]) >= ini]
        rec["atual"] = rec["atual"][rec["atual"]["repositorio"].isin(rec["repos"])]
        res[nome], recs[nome] = calcular(ctx, f2, rec, ultima_sprint=(nome == "Atual")), rec
    mf, mi = metas_agregadas()
    metas = PLANO["metas"]

    linhas = []
    for k, (codigo, nome, fator, dec) in METRICAS.items():
        linha = {"chave": k, "codigo": codigo, "nome": nome, "fator": fator, "decisao": dec,
                 "tipo_meta": TIPO_META.get(k, "Monitorada: sem meta"), "meta": metas.get(k)}
        for rel in jan:
            r = next(x for x in res[rel]["metricas"] if x.chave == k)
            linha[rel] = r.medida if not r.escala01 else r.valor
            linha[f"{rel}_bruto"] = r.bruto
        linhas.append(linha)
    met = pd.DataFrame(linhas)

    fat = []
    for fc, (nome, tipo, motivo) in FATORES.items():
        linha = {"fator": fc, "nome": nome, "tipo": tipo, "meta": mf.get(fc), "fora_do_calculo": motivo}
        for rel in jan:
            linha[rel] = res[rel]["fatores"].set_index("fator").loc[fc, "valor"]
        fat.append(linha)
    fatores = pd.DataFrame(fat)

    port = portoes(res["Atual"], recs["Atual"])
    restricoes = restricoes_por_repo(res["Atual"], recs["Atual"])
    ind = []
    for ic, (nome, desc, fs) in INDICADORES.items():
        linha = {"indicador": ic, "nome": nome, "descricao": desc, "meta": mi.get(ic),
                 "avaliados": f"{len(AVALIADOS[ic])} de {len(fs)}"}
        for rel in jan:
            agregado = res[rel]["indicadores"].set_index("indicador").loc[ic]
            linha[rel] = agregado["valor"]
            linha[f"n_{rel}"] = int(agregado["fatores_na_media"])
        ok = _portoes_do(ic, port)
        restricoes_i = restricoes[restricoes["indicador"] == ic]
        linha["restricoes_ok"] = bool(restricoes_i["passa"].all()) if not restricoes_i.empty else True
        linha["parcial"] = ic == "product_readiness" and jan["Atual"][1] < pd.Timestamp(config.RELEASES["R3"])
        linha["fatores_na_media"] = res["Atual"]["indicadores"].set_index("indicador").loc[ic, "fatores_na_media"]
        linha["portoes_ok"] = ok
        linha["piso"] = linha["R2"]
        linha["situacao"] = ("Parcial" if linha["parcial"] else
                             _situacao(linha["Atual"], linha["piso"], linha["meta"],
                                       ok if linha["restricoes_ok"] else False))
        ind.append(linha)
    return {"janelas": jan, "res": res, "recs": recs, "metricas": met, "fatores": fatores,
            "indicadores": pd.DataFrame(ind), "portoes": port, "restricoes": restricoes}


def _portoes_do(indicador: str, port: pd.DataFrame) -> bool | None:
    """True se todos os portões do indicador passam; False se algum reprova; None se algum não tem dado."""
    nome = INDICADORES[indicador][0]
    x = port[port["indicador"].str.contains(nome, regex=False)]
    if x.empty:
        return True
    if (x["passa"] == False).any():   # noqa: E712 — coluna pode ter None
        return False
    return None if x["passa"].isna().any() else True


# ───────────────────────── catálogo das 44 métricas (lido do selecaometricas.mdx) ─────────────────────────

def catalogo() -> pd.DataFrame:
    """Catálogo completo, versionado em config.py com as justificativas do plano."""
    return pd.DataFrame(config.QRAPIDS_CATALOGO).copy()


def tabela(resultados: list[Resultado]) -> pd.DataFrame:
    """Resultados em tabela (CSV e telas)."""
    return pd.DataFrame([{
        "indicador": " · ".join(v[0] for k, v in INDICADORES.items() if r.fator in v[2]),
        "fator": FATORES[r.fator][0], "codigo": r.codigo, "metrica": r.nome, "decisao": r.decisao,
        "descricao": r.descricao, "formula": r.formula, "dado_bruto": r.dado_bruto, "fonte": r.fonte,
        "situacao": ROTULO[r.situacao], "valor": r.medida if not r.escala01 else r.valor, "bruto": r.bruto,
        "numerador": r.numerador, "denominador": r.denominador, "observacao": r.motivo} for r in resultados])
