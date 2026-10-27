"""Nota de qualidade do produto — cálculo do notebook da disciplina, com rastreabilidade.

Reproduz ``internal_quality_analysis-sonarqube.ipynb`` (fga-eps-mds/Analytics), que implementa o
modelo Q-Rapids (``q-rapids model-doc.pdf``, abril/2019) para os dados do SonarCloud:

    dado bruto (arquivo)  →  métrica (0 a 1)  →  fator  →  aspecto  →  nota total

    Qualidade do código   = (0,33·complexidade + 0,33·comentários + 0,33·duplicação) · psc1
    Situação dos testes   = (0,25·testes que passam + 0,25·testes rápidos + 0,5·cobertura) · psc2
    Manutenibilidade      = Qualidade do código · pc1 (0,5)
    Confiabilidade        = Situação dos testes · pc2 (0,5)
    Nota total            = Manutenibilidade + Confiabilidade

Regras do notebook mantidas de propósito (para o número ser o mesmo):

* entram só os arquivos de código (FIL) **da linguagem do repositório** com ``ncloc > 0``;
* as três métricas de código e a cobertura usam **o mesmo conjunto de arquivos**: os que têm as cinco
  medidas (functions, complexity, comment_lines_density, duplicated_lines_density, coverage);
* "testes que passam" usa a pasta (DIR) com mais testes;
* "testes rápidos" conta as suítes (UTS); suíte sem tempo de execução conta como 0 ms (rápida);
* métrica que não pode ser calculada (sem arquivos, sem testes) **vale 0** — e aqui fica marcada
  como "0 por falta de dado", para não ser confundida com 0 medido.

Cada métrica devolve, além do valor, o numerador, o denominador, a regra e a lista de arquivos com
"passa / não passa" — é o que a página Qualidade (Q-Rapids) mostra em cada nível.
"""

from __future__ import annotations

import pandas as pd

import config

Q = config.QRAPIDS
LIMIARES, PESOS = Q["limiares"], Q["pesos"]
SEG = Q.get("seguranca", {})
PESOS_SEG = SEG.get("pesos", {"manutenibilidade": 0.4, "confiabilidade": 0.4, "seguranca": 0.2})
RATING_VETO = SEG.get("rating_veto", 4)
LETRA = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}
CINCO = ["functions", "complexity", "comment_lines_density", "duplicated_lines_density", "coverage"]

# chave → (nome, fator, aspecto, regra legível, fórmula)
METRICAS = {
    "complexidade": ("Complexidade (arquivos não complexos)", "qualidade_codigo", "manutenibilidade",
                     f"complexidade ciclomática ÷ funções < {LIMIARES['complexidade_por_funcao']}",
                     "arquivos não complexos ÷ total de arquivos"),
    "comentarios": ("Comentários (arquivos comentados)", "qualidade_codigo", "manutenibilidade",
                    f"{LIMIARES['comentarios_min']}% < densidade de comentários < {LIMIARES['comentarios_max']}%",
                    "arquivos comentados ÷ total de arquivos"),
    "duplicacao": ("Duplicação (arquivos sem duplicação)", "qualidade_codigo", "manutenibilidade",
                   f"densidade de linhas duplicadas < {LIMIARES['duplicacao_max']}%",
                   "arquivos sem duplicação ÷ total de arquivos"),
    "testes_passando": ("Testes que passam", "situacao_testes", "confiabilidade",
                        "testes − (erros + falhas), na pasta com mais testes",
                        "(testes − (erros + falhas)) ÷ testes"),
    "testes_rapidos": ("Testes rápidos", "situacao_testes", "confiabilidade",
                       f"tempo de execução da suíte < {LIMIARES['teste_rapido_ms'] / 60000:g} min",
                       "suítes rápidas ÷ total de suítes"),
    "cobertura": ("Cobertura de testes", "situacao_testes", "confiabilidade",
                  f"cobertura do arquivo > {LIMIARES['cobertura_min']}%",
                  "arquivos com cobertura acima do limiar ÷ total de arquivos"),
}
FATORES = {
    "qualidade_codigo": ("Qualidade do código", "manutenibilidade", ["complexidade", "comentarios", "duplicacao"]),
    "situacao_testes": ("Situação dos testes", "confiabilidade", ["testes_passando", "testes_rapidos", "cobertura"]),
}
ASPECTOS = {"manutenibilidade": ("Manutenibilidade", "qualidade_codigo"),
            "confiabilidade": ("Confiabilidade", "situacao_testes")}


def linguagem(repo: str, comp: pd.DataFrame | None = None) -> str | None:
    """Linguagem do repositório (config; se faltar, a mais comum entre os arquivos de código)."""
    lg = Q["linguagem"].get(repo)
    if lg or comp is None or comp.empty or "linguagem" not in comp:
        return lg
    fil = comp[comp["tipo"] == "FIL"]["linguagem"].dropna()
    return fil.mode().iloc[0] if not fil.empty else None


def _largo(comp: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por componente (arquivo, pasta ou suíte), uma coluna por métrica."""
    idx = ["componente", "tipo"] + (["linguagem"] if "linguagem" in comp else [])
    c = comp.copy()
    if "linguagem" in c:
        c["linguagem"] = c["linguagem"].fillna("")
    w = c.pivot_table(index=idx, columns="metrica", values="valor", aggfunc="last").reset_index()
    for m in CINCO + ["ncloc", "tests", "test_errors", "test_failures", "test_execution_time"]:
        if m not in w:
            w[m] = float("nan")
    return w


def _resultado(chave, valor, num, den, itens=None, falta=None):
    nome, fator, aspecto, regra, formula = METRICAS[chave]
    return {"chave": chave, "nome": nome, "fator": fator, "aspecto": aspecto, "regra": regra, "formula": formula,
            "valor": float(valor) if valor is not None else 0.0, "numerador": num, "denominador": den,
            "zero_por_falta": falta, "peso": PESOS[chave],
            "itens": itens if itens is not None else pd.DataFrame()}


def avaliar(comp: pd.DataFrame, repo: str) -> dict:
    """Avaliação de UMA coleta de UM repositório (componentes do .json do pipeline).

    Devolve ``{"metricas": {chave: resultado}, "fatores": {...}, "aspectos": {...}, "total": float,
    "arquivos_base": int, "arquivos_codigo": int, "linguagem": str}``.
    """
    lg = linguagem(repo, comp)
    w = _largo(comp)
    fil = w[(w["tipo"] == "FIL") & (w["ncloc"] > 0)]
    if lg and "linguagem" in fil:
        fil = fil[fil["linguagem"] == lg]
    base = fil.dropna(subset=CINCO).copy()                        # get_files_df do notebook
    n = len(base)
    falta_arq = None if n else "nenhum arquivo com as cinco medidas (functions, complexity, comentários, " \
                               "duplicação, cobertura)"
    res = {}

    def por_arquivo(chave, passa, coluna_valor):
        itens = base[["componente"]].assign(valor=coluna_valor, passa=passa).sort_values(["passa", "valor"])
        k = int(passa.sum())
        return _resultado(chave, k / n if n else 0.0, k, n, itens, falta_arq)

    razao = base["complexity"] / base["functions"]
    res["complexidade"] = por_arquivo("complexidade", razao < LIMIARES["complexidade_por_funcao"], razao)
    cld = base["comment_lines_density"]
    res["comentarios"] = por_arquivo("comentarios", (cld > LIMIARES["comentarios_min"])
                                     & (cld < LIMIARES["comentarios_max"]), cld)
    dld = base["duplicated_lines_density"]
    res["duplicacao"] = por_arquivo("duplicacao", dld < LIMIARES["duplicacao_max"], dld)
    cov = base["coverage"]
    res["cobertura"] = por_arquivo("cobertura", cov > LIMIARES["cobertura_min"], cov)

    # testes que passam: pasta com mais testes (get_dir_df)
    dirs = w[(w["tipo"] == "DIR") & w["tests"].notna()]
    if dirs.empty:
        res["testes_passando"] = _resultado("testes_passando", 0.0, None, None, None,
                                            "nenhuma pasta com testes no .json (o repositório não publica o "
                                            "relatório de testes no SonarCloud)")
    else:
        d = dirs.loc[dirs["tests"].idxmax()]
        t, e, fl = d["tests"], d["test_errors"], d["test_failures"]
        if pd.isna(e) or pd.isna(fl) or not t:
            res["testes_passando"] = _resultado("testes_passando", 0.0, None, t, None,
                                                "pasta de testes sem test_errors/test_failures")
        else:
            itens = pd.DataFrame([{"componente": d["componente"], "testes": t, "erros": e, "falhas": fl}])
            res["testes_passando"] = _resultado("testes_passando", (t - (e + fl)) / t, t - (e + fl), t, itens)

    # testes rápidos: suítes (get_uts_df: fillna(0))
    uts = w[w["tipo"] == "UTS"].copy()
    if uts.empty:
        res["testes_rapidos"] = _resultado("testes_rapidos", 0.0, None, None, None,
                                           "nenhuma suíte de teste (UTS) no .json")
    else:
        sem_tempo = int(uts["test_execution_time"].isna().sum())
        uts["test_execution_time"] = uts["test_execution_time"].fillna(0)
        passa = uts["test_execution_time"] < LIMIARES["teste_rapido_ms"]
        itens = uts[["componente"]].assign(valor=uts["test_execution_time"], passa=passa,
                                           sem_tempo=w.loc[uts.index, "test_execution_time"].isna())
        r = _resultado("testes_rapidos", passa.mean(), int(passa.sum()), len(uts), itens.sort_values("valor"))
        r["observacao"] = (f"{sem_tempo} suíte(s) sem tempo de execução contam como 0 ms (regra do notebook)"
                           if sem_tempo else "")
        res["testes_rapidos"] = r

    fatores, aspectos = {}, {}
    for f, (nome, aspecto, metricas) in FATORES.items():
        v = sum(res[m]["valor"] * PESOS[m] for m in metricas) * PESOS[f]
        fatores[f] = {"chave": f, "nome": nome, "valor": v, "metricas": metricas, "peso": PESOS[f],
                      "formula": " + ".join(f"{PESOS[m]:g}·{METRICAS[m][0].split(' (')[0].lower()}"
                                            for m in metricas) + f" (× {PESOS[f]:g})"}
    for a, (nome, f) in ASPECTOS.items():
        aspectos[a] = {"chave": a, "nome": nome, "valor": fatores[f]["valor"], "peso": PESOS[a],
                       "contribuicao": fatores[f]["valor"] * PESOS[a], "fator": f}
    total = sum(x["contribuicao"] for x in aspectos.values())
    return {"metricas": res, "fatores": fatores, "aspectos": aspectos, "total": total, "arquivos_base": n,
            "arquivos_codigo": len(fil), "linguagem": lg}


# ───────────────────────── segurança (extensão do time) ─────────────────────────

def nota_seguranca(rating) -> float | None:
    """security_rating do SonarCloud (1 = A … 5 = E) em 0 a 1: (5 − rating) ÷ 4. Sem dado → None."""
    if rating is None or pd.isna(rating):
        return None
    return max(0.0, min(1.0, (5 - float(rating)) / 4))


def com_seguranca(avaliacao: dict, rating=None, vulnerabilidades=None, coleta=None) -> dict:
    """Acrescenta à avaliação do notebook o aspecto Segurança, a nota com segurança e o veto.

    A nota oficial (``total``) não muda: ela é a do notebook. ``total_seguranca`` =
    Σ peso × aspecto com ``PESOS_SEG``; ``veto_seguranca`` = rating ≥ ``RATING_VETO`` (D ou E).
    Sem security_rating, a segurança fica "sem dado" e a nota com segurança não é calculada (nunca vira 0).
    """
    s = nota_seguranca(rating)
    avaliacao["seguranca"] = {
        "valor": s, "rating": None if s is None else float(rating),
        "letra": None if s is None else LETRA.get(int(round(float(rating)))),
        "vulnerabilidades": vulnerabilidades, "coleta": coleta,
        "sem_dado": None if s is not None else "sem security_rating do SonarCloud até o fim do período"}
    man = avaliacao["aspectos"]["manutenibilidade"]["valor"]
    con = avaliacao["aspectos"]["confiabilidade"]["valor"]
    avaliacao["total_seguranca"] = None if s is None else (
        PESOS_SEG["manutenibilidade"] * man + PESOS_SEG["confiabilidade"] * con + PESOS_SEG["seguranca"] * s)
    avaliacao["veto_seguranca"] = s is not None and float(rating) >= RATING_VETO
    return avaliacao


def serie(componentes: pd.DataFrame, agregado: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por repositório × coleta (cada .json do pipeline), como o ``metrics_df`` do notebook."""
    if componentes is None or componentes.empty:
        return pd.DataFrame()
    linhas = []
    chaves = ["repositorio", "branch", "coleta", "arquivo"] if "arquivo" in componentes else \
        ["repositorio", "branch", "coleta"]
    rating = {}
    if agregado is not None and not agregado.empty and "arquivo" in agregado:
        x = agregado[agregado["metrica"] == "security_rating"]
        rating = dict(zip(x["arquivo"], x["valor"]))
    for k, comp in componentes.groupby(chaves, sort=True):
        k = dict(zip(chaves, k))
        a = com_seguranca(avaliar(comp, k["repositorio"]), rating.get(k.get("arquivo")))
        linhas.append({**k, **{m: r["valor"] for m, r in a["metricas"].items()},
                       **{f: x["valor"] for f, x in a["fatores"].items()},
                       **{x: y["valor"] for x, y in a["aspectos"].items()}, "total": a["total"],
                       "seguranca": a["seguranca"]["valor"], "total_seguranca": a["total_seguranca"],
                       "arquivos": a["arquivos_base"],
                       "zeros_por_falta": ", ".join(m for m, r in a["metricas"].items() if r["zero_por_falta"])})
    return pd.DataFrame(linhas).sort_values(["repositorio", "coleta"]).reset_index(drop=True)


# compatibilidade com a prévia antiga (página Qualidade técnica)
def calcular(componentes: pd.DataFrame, agregado: pd.DataFrame | None = None) -> pd.DataFrame:
    s = serie(componentes)
    return s.rename(columns={"manutenibilidade": "manutenibilidade", "confiabilidade": "confiabilidade"})


def nota(valor: float) -> str:
    """Faixa A a E usada em 2026.1 (A >= 0,8 ... E < 0,2)."""
    if pd.isna(valor):
        return "—"
    for limite, letra in ((0.8, "A"), (0.6, "B"), (0.4, "C"), (0.2, "D")):
        if valor >= limite:
            return letra
    return "E"
