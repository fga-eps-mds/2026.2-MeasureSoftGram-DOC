"""Modelo de qualidade agregado (base para o DA-R2).

Adaptado do dashboard de 2026.1 (estilo Q-Rapids / MeasureSoftGram): cada
métrica do SonarCloud vira a *proporção de arquivos dentro de um limiar*
(normalização para 0 a 1), as proporções são ponderadas em fatores e os
fatores em uma nota total.

    Complexidade      arquivos com complexity/functions < 10
    Comentários       arquivos com 10 < comment_lines_density < 30
    Duplicação        arquivos com duplicated_lines_density < 5
    Cobertura         arquivos com coverage > 60
    Sucesso de testes (tests - errors - failures) / tests
    Testes rápidos    suítes com test_execution_time < 300000 ms

    Manutenibilidade  = média(complexidade, comentários, duplicação)
    Confiabilidade    = 0,25 sucesso + 0,25 rápidos + 0,5 cobertura
    Total             = 0,5 manutenibilidade + 0,5 confiabilidade

Limiares e pesos são os de 2026.1. A disciplina pede que o time os valide e
justifique na R2 (ATP4, 19/10); por isso ficam aqui como constantes nomeadas.
"""

from __future__ import annotations

import pandas as pd

LIMIARES = {
    "complexidade_por_funcao": 10,
    "comentarios_min": 10,
    "comentarios_max": 30,
    "duplicacao_max": 5,
    "cobertura_min": 60,
    "teste_rapido_ms": 300_000,
}
PESOS = {
    "manutenibilidade": {"complexidade": 1 / 3, "comentarios": 1 / 3, "duplicacao": 1 / 3},
    "confiabilidade": {"sucesso_testes": 0.25, "testes_rapidos": 0.25, "cobertura": 0.5},
    "total": {"manutenibilidade": 0.5, "confiabilidade": 0.5},
}


def _proporcao(mascara: pd.Series) -> float:
    return float(mascara.mean()) if len(mascara) else float("nan")


def _pondera(valores: dict, pesos: dict) -> float:
    soma = peso = 0.0
    for chave, p in pesos.items():
        v = valores.get(chave)
        if v is not None and pd.notna(v):
            soma += v * p
            peso += p
    return soma / peso if peso else float("nan")


def calcular(componentes: pd.DataFrame, agregado: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por repositório × coleta com os fatores normalizados (0 a 1)."""
    if componentes.empty:
        return pd.DataFrame()
    linhas = []
    chaves = ["repositorio", "branch", "coleta"]
    for (repo, branch, coleta), comp in componentes.groupby(chaves, dropna=False):
        branch_norm = branch if pd.notna(branch) and branch is not None else ""
        arq = comp[comp["tipo"] == "FIL"].pivot_table(
            index="componente", columns="metrica", values="valor", aggfunc="last")
        uts = comp[comp["tipo"] == "UTS"].pivot_table(
            index="componente", columns="metrica", values="valor", aggfunc="last")
        if agregado is not None and not agregado.empty:
            rec = agregado[(agregado["repositorio"] == repo)
                           & (agregado["branch"].fillna("") == branch_norm)
                           & (agregado["coleta"] == coleta)].dropna(subset=["valor"])
            base = rec.drop_duplicates("metrica", keep="last").set_index("metrica")["valor"]
        else:
            base = pd.Series(dtype=float)

        f = {}
        if {"complexity", "functions"} <= set(arq.columns):
            a = arq.dropna(subset=["complexity", "functions"])
            a = a[a["functions"] > 0]
            f["complexidade"] = _proporcao(a["complexity"] / a["functions"]
                                           < LIMIARES["complexidade_por_funcao"])
        if "comment_lines_density" in arq:
            c = arq["comment_lines_density"].dropna()
            f["comentarios"] = _proporcao((c > LIMIARES["comentarios_min"]) & (c < LIMIARES["comentarios_max"]))
        if "duplicated_lines_density" in arq:
            f["duplicacao"] = _proporcao(arq["duplicated_lines_density"].dropna() < LIMIARES["duplicacao_max"])
        if "coverage" in arq:
            f["cobertura"] = _proporcao(arq["coverage"].dropna() > LIMIARES["cobertura_min"])
        testes = base.get("tests")
        if testes is not None and pd.notna(testes) and testes > 0:
            err_t = base.get("test_errors")
            fal_t = base.get("test_failures")
            erros = (err_t if err_t is not None and pd.notna(err_t) else 0.0) + (
                fal_t if fal_t is not None and pd.notna(fal_t) else 0.0)
            f["sucesso_testes"] = max(0.0, (testes - erros) / testes)
        if "test_execution_time" in uts:
            f["testes_rapidos"] = _proporcao(uts["test_execution_time"].dropna() < LIMIARES["teste_rapido_ms"])

        f["manutenibilidade"] = _pondera(f, PESOS["manutenibilidade"])
        f["confiabilidade"] = _pondera(f, PESOS["confiabilidade"])
        f["total"] = _pondera(f, PESOS["total"])
        linhas.append({"repositorio": repo, "branch": branch_norm, "coleta": coleta, **f})
    return pd.DataFrame(linhas).sort_values(["repositorio", "coleta"])


def nota(valor: float) -> str:
    """Faixa A a E usada em 2026.1 (A >= 0,8 ... E < 0,2)."""
    if pd.isna(valor):
        return "—"
    for limite, letra in ((0.8, "A"), (0.6, "B"), (0.4, "C"), (0.2, "D")):
        if valor >= limite:
            return letra
    return "E"
