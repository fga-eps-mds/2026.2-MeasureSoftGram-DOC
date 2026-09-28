"""Fonte SONAR — métricas de qualidade do SonarCloud.

Duas entradas, as duas geradas automaticamente (nada digitado à mão):

1. **Pipeline** — ``<org>-<repo>-MM-DD-YYYY-HH-MM-SS-<branch>.json`` em
   ``Analytics/data/``, gravados pelo ``metrics.yml`` de cada
   repositório. ``baseComponent.measures`` = agregado do repositório;
   ``components`` = detalhe por arquivo/pasta. A data sai do nome do arquivo.
2. **API do SonarCloud** — ``data/sonar/sonar-AAAA-MM-DDTHHMM.json``, gravado por
   ``scripts/coleta_sonar.py``. Traz o que o pipeline não pede: bugs,
   vulnerabilidades, code smells, security hotspots, dívida técnica, Quality
   Gate, ratings, problemas por severidade e o histórico de cada métrica.

Se um arquivo não existe, as funções devolvem DataFrame vazio e a página diz
que o dado falta — nunca inventa valor.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ORG = "fga-eps-mds"
PREFIXO_REPO = "2026.2-MeasureSoftGram-"
PASTA_API = Path(__file__).resolve().parents[2] / "data" / "sonar"

# Ancora no bloco de data, porque org e repositório contêm hífens e pontos.
_SONAR = re.compile(
    r"^(?P<prefixo>.+?)-(?P<mes>\d{2})-(?P<dia>\d{2})-(?P<ano>\d{4})"
    r"-(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})-(?P<branch>.+)\.json$"
)

# Métrica -> (nome, unidade, maior é melhor?). None = sem direção (tamanho).
METRICAS = {
    "bugs": ("Bugs", "", False),
    "vulnerabilities": ("Vulnerabilidades", "", False),
    "code_smells": ("Code smells", "", False),
    "security_hotspots": ("Security hotspots", "", False),
    "sqale_index": ("Dívida técnica", "min", False),
    "sqale_debt_ratio": ("Razão de dívida técnica", "%", False),
    "coverage": ("Cobertura de testes", "%", True),
    "duplicated_lines": ("Linhas duplicadas", "", False),
    "duplicated_lines_density": ("Densidade de duplicação", "%", False),
    "ncloc": ("Linhas de código", "", None),
    "reliability_rating": ("Rating de confiabilidade", "", False),
    "security_rating": ("Rating de segurança", "", False),
    "sqale_rating": ("Rating de manutenibilidade", "", False),
    "tests": ("Testes", "", True),
    "test_errors": ("Erros de teste", "", False),
    "test_failures": ("Falhas de teste", "", False),
    "test_success_density": ("Sucesso dos testes", "%", True),
    "test_execution_time": ("Tempo de execução dos testes", "ms", False),
    "comment_lines_density": ("Densidade de comentários", "%", None),
    "complexity": ("Complexidade ciclomática", "", None),
    "files": ("Arquivos", "", None),
    "functions": ("Funções", "", None),
}
RATING = {1.0: "A", 2.0: "B", 3.0: "C", 4.0: "D", 5.0: "E"}
SEVERIDADES = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
SEVERIDADE_PT = {"BLOCKER": "Bloqueante", "CRITICAL": "Crítica", "MAJOR": "Alta", "MINOR": "Baixa", "INFO": "Info"}


def nome_curto(repo: str) -> str:
    return str(repo).replace(PREFIXO_REPO, "")


def _pastas(entrada) -> list[Path]:
    if isinstance(entrada, (str, Path)):
        entrada = [entrada]
    return [Path(p) for p in entrada if Path(p).is_dir()]


def _repo(prefixo: str) -> str:
    return prefixo[len(ORG) + 1:] if prefixo.startswith(ORG + "-") else prefixo


def _num(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# ───────────────────────── pipeline (metrics.yml) ─────────────────────────

def carregar_sonar(pastas) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(agregado por repositório, detalhe por componente) dos .json do pipeline."""
    linhas_repo, linhas_comp = [], []
    arquivos = [a for pasta in _pastas(pastas) for a in sorted(pasta.glob("*.json"))]
    for arquivo in arquivos:
        if arquivo.name.startswith("GitHub_API-"):
            continue
        casado = _SONAR.match(arquivo.name)
        if not casado:
            continue
        g = casado.groupdict()
        try:
            coleta = datetime(int(g["ano"]), int(g["mes"]), int(g["dia"]), int(g["h"]), int(g["m"]), int(g["s"]))
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError, OSError):
            continue
        if not isinstance(dados, dict):
            continue
        repo, branch = _repo(g["prefixo"]), g["branch"]
        base = {"repositorio": repo, "branch": branch, "coleta": coleta, "arquivo": arquivo.name}
        for medida in (dados.get("baseComponent") or {}).get("measures", []):
            linhas_repo.append({**base, "metrica": medida.get("metric"), "valor": _num(medida.get("value")),
                                "origem": "pipeline"})
        for componente in dados.get("components") or []:
            for medida in componente.get("measures", []):
                linhas_comp.append({**base, "componente": componente.get("path") or componente.get("name"),
                                    "tipo": componente.get("qualifier"), "metrica": medida.get("metric"),
                                    "valor": _num(medida.get("value"))})
    return pd.DataFrame(linhas_repo), pd.DataFrame(linhas_comp)


def coletas_com_erro(pastas) -> pd.DataFrame:
    """Coletas que voltaram erro em vez de métrica (ex.: repositório sem projeto no SonarCloud)."""
    linhas = []
    for pasta in _pastas(pastas):
        for arquivo in sorted(pasta.glob("*.json")):
            if arquivo.name.startswith("GitHub_API-"):
                continue
            casado = _SONAR.match(arquivo.name)
            if not casado:
                continue
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(dados, dict) or not dados.get("errors"):
                continue
            g = casado.groupdict()
            msg = "; ".join(str(e.get("msg", e)) for e in dados["errors"] if isinstance(e, dict)) or "erro sem mensagem"
            linhas.append({"repositorio": _repo(g["prefixo"]), "coleta": f"{g['dia']}/{g['mes']}/{g['ano']}",
                           "erro": msg})
    df = pd.DataFrame(linhas)
    return df.drop_duplicates(subset=["repositorio", "erro"]) if not df.empty else df


def ultimo_por_repo(agregado: pd.DataFrame) -> pd.DataFrame:
    """Valor mais recente de cada métrica em cada repositório."""
    if agregado is None or agregado.empty:
        return pd.DataFrame(columns=["repositorio", "metrica", "valor", "coleta"])
    idx = agregado.groupby(["repositorio", "metrica"])["coleta"].idxmax()
    return agregado.loc[idx].reset_index(drop=True)


# ───────────────────────── API do SonarCloud (snapshot) ─────────────────────────

def ultimo_snapshot(pasta: Path = PASTA_API) -> tuple[dict | None, str]:
    arquivos = sorted(Path(pasta).glob("sonar-*.json")) if Path(pasta).exists() else []
    for arq in reversed(arquivos):
        try:
            return json.loads(arq.read_text(encoding="utf-8")), arq.name
        except (json.JSONDecodeError, OSError):
            continue
    return None, ""


def _repo_do_projeto(p: dict) -> str:
    chave = str(p.get("key") or "")
    return p.get("repositorio") or (chave.split("_", 1)[1] if "_" in chave else chave)


def snapshot_para_tabelas(snap: dict | None) -> dict[str, pd.DataFrame]:
    """Snapshot da API -> tabelas planas (vazias quando não há snapshot)."""
    vazio = {"medidas": pd.DataFrame(), "historico": pd.DataFrame(), "quality_gate": pd.DataFrame(),
             "condicoes": pd.DataFrame(), "severidades": pd.DataFrame(), "tipos": pd.DataFrame(),
             "linguagens": pd.DataFrame(), "erros": pd.DataFrame()}
    if not snap:
        return vazio
    coleta = pd.to_datetime(snap.get("coletado_em"), utc=True, errors="coerce")
    coleta = coleta.tz_convert(None) if pd.notna(coleta) else pd.NaT
    med, hist, qg, cond, sev, tip, lang, err = [], [], [], [], [], [], [], []
    for p in snap.get("projetos", []):
        repo = _repo_do_projeto(p)
        branch = p.get("branch") or snap.get("branch") or ""
        if p.get("erro"):
            err.append({"repositorio": repo, "erro": p["erro"]})
            continue
        for metrica, valor in (p.get("medidas") or {}).items():
            med.append({"repositorio": repo, "branch": branch, "coleta": coleta, "metrica": metrica,
                        "valor": _num(valor), "origem": "api", "arquivo": ""})
        for metrica, pontos in (p.get("historico") or {}).items():
            for ponto in pontos or []:
                if ponto.get("value") is None:
                    continue
                hist.append({"repositorio": repo, "branch": branch, "metrica": metrica,
                             "coleta": pd.to_datetime(ponto.get("date"), utc=True, errors="coerce"),
                             "valor": _num(ponto.get("value"))})
        g = p.get("quality_gate") or {}
        if g.get("status"):
            qg.append({"repositorio": repo, "status": g["status"]})
            for c in g.get("condicoes") or []:
                cond.append({"repositorio": repo, **c})
        for s, n in ((p.get("issues") or {}).get("severidades") or {}).items():
            sev.append({"repositorio": repo, "severidade": s, "quantidade": _num(n) or 0.0})
        for t, n in ((p.get("issues") or {}).get("tipos") or {}).items():
            tip.append({"repositorio": repo, "tipo": t, "quantidade": _num(n) or 0.0})
        for linguagem, n in (p.get("linguagens") or {}).items():
            lang.append({"repositorio": repo, "linguagem": linguagem, "ncloc": _num(n) or 0.0})
    h = pd.DataFrame(hist)
    if not h.empty:
        h["coleta"] = h["coleta"].dt.tz_convert(None)
        h = h.dropna(subset=["coleta", "valor"])
    return {"medidas": pd.DataFrame(med), "historico": h, "quality_gate": pd.DataFrame(qg),
            "condicoes": pd.DataFrame(cond), "severidades": pd.DataFrame(sev), "tipos": pd.DataFrame(tip),
            "linguagens": pd.DataFrame(lang), "erros": pd.DataFrame(err)}


def serie_temporal(pipeline: pd.DataFrame, historico_api: pd.DataFrame) -> pd.DataFrame:
    """Uma série por (repositório, métrica, dia): pipeline + histórico da API, o valor mais recente do dia."""
    partes = []
    if pipeline is not None and not pipeline.empty:
        partes.append(pipeline[["repositorio", "branch", "metrica", "coleta", "valor"]].assign(origem="pipeline"))
    if historico_api is not None and not historico_api.empty:
        partes.append(historico_api[["repositorio", "branch", "metrica", "coleta", "valor"]].assign(origem="api"))
    if not partes:
        return pd.DataFrame(columns=["repositorio", "branch", "metrica", "coleta", "valor", "origem", "dia"])
    d = pd.concat(partes, ignore_index=True).dropna(subset=["valor"])
    d["dia"] = pd.to_datetime(d["coleta"]).dt.normalize()
    d = d.sort_values("coleta").drop_duplicates(["repositorio", "branch", "metrica", "dia"], keep="last")
    return d.reset_index(drop=True)


def agregacao(metrica: str) -> str:
    """Como juntar repositórios: percentuais = média simples; ratings = o pior (maior); contagens = soma."""
    if metrica.endswith("_rating"):
        return "max"
    return "mean" if METRICAS.get(metrica, ("", "", None))[1] == "%" else "sum"


def serie_agregada(serie: pd.DataFrame, metrica: str, repos: list[str] | None = None) -> pd.DataFrame:
    """Valor do conjunto de repositórios em cada dia com coleta.

    Em cada dia, cada repositório entra com o último valor conhecido até aquele
    dia (repositório ainda sem coleta fica de fora — nada é interpolado).
    Colunas: ``dia``, ``valor``, ``repos`` (quantos entraram).
    """
    if serie is None or serie.empty:
        return pd.DataFrame(columns=["dia", "valor", "repos"])
    s = serie[serie["metrica"] == metrica]
    if repos:
        s = s[s["repositorio"].isin(repos)]
    if s.empty:
        return pd.DataFrame(columns=["dia", "valor", "repos"])
    largo = (s.pivot_table(index="dia", columns="repositorio", values="valor", aggfunc="last")
             .sort_index().ffill())
    return pd.DataFrame({"dia": largo.index, "valor": largo.agg(agregacao(metrica), axis=1).values,
                         "repos": largo.notna().sum(axis=1).values}).reset_index(drop=True)


def atual_e_anterior(serie: pd.DataFrame, metrica: str, repos: list[str] | None = None) -> dict:
    """Soma (contagens) ou média (percentuais) do último e do penúltimo dia com dado, nos repositórios filtrados.

    Devolve ``{"atual", "anterior", "data_atual", "data_anterior", "n_repos"}``; valores None quando faltam.
    Cada repositório entra com o seu último valor até a data de corte (sem interpolar).
    """
    vazio = {"atual": None, "anterior": None, "data_atual": None, "data_anterior": None, "n_repos": 0}
    if serie is None or serie.empty:
        return vazio
    s = serie[serie["metrica"] == metrica]
    if repos:
        s = s[s["repositorio"].isin(repos)]
    if s.empty:
        return vazio
    dias = sorted(s["dia"].unique())
    agrega = agregacao(metrica)

    def ate(dia):
        corte = s[s["dia"] <= dia].sort_values("dia").groupby("repositorio").tail(1)
        return (float(corte["valor"].agg(agrega)) if not corte.empty else None), corte["repositorio"].nunique()

    atual, n = ate(dias[-1])
    anterior = ate(dias[-2])[0] if len(dias) > 1 else None
    return {"atual": atual, "anterior": anterior, "data_atual": pd.Timestamp(dias[-1]),
            "data_anterior": pd.Timestamp(dias[-2]) if len(dias) > 1 else None, "n_repos": n}


def formatar(metrica: str, valor) -> str:
    """Valor legível: % com 1 casa, rating como letra, dívida em h, contagens inteiras."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    unidade = METRICAS.get(metrica, ("", "", None))[1]
    if metrica.endswith("_rating"):
        return RATING.get(round(float(valor)), f"{valor:.1f}")
    if metrica == "sqale_index":
        horas = float(valor) / 60
        return f"{horas:,.0f} h".replace(",", ".") if horas >= 10 else f"{horas:.1f} h".replace(".", ",")
    if unidade == "%":
        return f"{valor:.1f}%".replace(".", ",")
    if unidade == "ms":
        return f"{valor / 1000:.1f} s".replace(".", ",")
    return f"{valor:,.0f}".replace(",", ".")
