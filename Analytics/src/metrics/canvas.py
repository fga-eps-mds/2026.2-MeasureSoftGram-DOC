"""Cálculo e montagem dos blocos do Canvas Analytics (R1 → R2 → R3 contra as metas da R3)."""

from __future__ import annotations

import pandas as pd

import config
from src import theme
from src.metrics import fluxo
from src.metrics.calculations import num, vazio

JANELAS = ("R1", "R2", "R3")
EIXOS = ("Produto", "Projeto", "Processo", "Gestão")
COLUNAS = ["bloco", "eixo", "titulo_bloco", "indicador", "R1", "R2", "R3", "status", "leitura", "onde"]

# Blocos alimentados por resumo.indicadores, por prefixo do nome do indicador (str.startswith).
BLOCOS = [
    {"id": "tecnica",  "eixo": "Produto",  "titulo": "Qualidade técnica (Sonar)",
     "prefixos": ["Cobertura (média", "Duplicação (pior", "Bugs abertos", "Quality Gate"]},
    {"id": "evm",      "eixo": "Projeto",  "titulo": "Custo e prazo (EVM)",
     "prefixos": ["SPI da", "CPI (custo)"]},
    {"id": "escopo",   "eixo": "Projeto",  "titulo": "Escopo",
     "prefixos": ["Escopo da release", "Progresso da", "Taxa de conclusão das sprints"]},
    {"id": "ci",       "eixo": "Processo", "titulo": "Integração contínua",
     "prefixos": ["Sucesso da CI"]},
    {"id": "riscos",   "eixo": "Gestão",   "titulo": "Riscos",
     "prefixos": ["Riscos elevados não encerrados"]},
    {"id": "decisoes", "eixo": "Gestão",   "titulo": "Decisões gerenciais",
     "prefixos": ["Decisões baseadas em dados"]},
]


def _janela_release(release: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Início e fim de uma release: do dia seguinte à entrega anterior até a entrega dela."""
    nomes = list(config.RELEASES)
    fim = pd.Timestamp(config.RELEASES[release])
    i = nomes.index(release)
    inicio = (pd.Timestamp(config.RELEASES[nomes[i - 1]]) + pd.Timedelta(days=1) if i
              else pd.Timestamp(config.INICIO_SEMESTRE))
    return inicio, fim


def janelas(hoje) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Janelas R1, R2 e R3 (do dia seguinte à R2 até min(hoje, entrega da R3))."""
    r1 = _janela_release("R1")
    r2 = _janela_release("R2")
    r3_ini = r2[1] + pd.Timedelta(days=1)
    r3_fim = min(pd.Timestamp(hoje), pd.Timestamp(config.RELEASES["R3"]))
    return {"R1": r1, "R2": r2, "R3": (r3_ini, r3_fim)}


def _normalizar_valor(v) -> str | None:
    return None if vazio(v) else str(v)


def montar(por_janela: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Alinha os indicadores de ``resumo.indicadores`` nas janelas R1, R2 e R3 por bloco e prefixo."""
    por_janela = por_janela or {}
    linhas = []
    for bloco in BLOCOS:
        for prefixo in bloco["prefixos"]:
            achados = {}
            for r in JANELAS:
                df = por_janela.get(r)
                if df is None or df.empty or "indicador" not in df:
                    continue
                m = df[df["indicador"].fillna("").astype(str).str.startswith(prefixo)]
                if not m.empty:
                    achados[r] = m.iloc[0]
            if not achados:
                continue
            ult = achados["R3"] if "R3" in achados else achados[max(achados, key=JANELAS.index)]
            r3 = achados.get("R3")
            linhas.append({
                "bloco": bloco["id"],
                "eixo": bloco["eixo"],
                "titulo_bloco": bloco["titulo"],
                "indicador": str(ult["indicador"]),
                "R1": _normalizar_valor(achados["R1"].get("valor")) if "R1" in achados else None,
                "R2": _normalizar_valor(achados["R2"].get("valor")) if "R2" in achados else None,
                "R3": _normalizar_valor(r3.get("valor")) if r3 is not None else None,
                "status": str(r3.get("status", "unavailable")) if r3 is not None else "unavailable",
                "leitura": str(r3.get("leitura", "")) if r3 is not None else "sem dado na R3",
                "onde": str(r3.get("onde", ult.get("onde", ""))) if r3 is not None else str(ult.get("onde", "")),
            })
    return pd.DataFrame(linhas, columns=COLUNAS)


def _fmt_num(x, casas: int = 2) -> str | None:
    return None if vazio(x) else num(float(x), casas)


def linhas_qrapids(ind: pd.DataFrame | None) -> pd.DataFrame:
    """Converte ``qrapids.avaliar_releases(...)['indicadores']`` para o formato do Canvas."""
    if ind is None or ind.empty:
        return pd.DataFrame(columns=COLUNAS)
    from src.metrics import qrapids
    estados = {qrapids.STATUS["verde"]: "good", qrapids.STATUS["amarelo"]: "warning",
               qrapids.STATUS["vermelho"]: "critical", "Parcial": "neutral"}
    linhas = []
    for r in ind.itertuples():
        meta_str = _fmt_num(getattr(r, "meta", None), 2)
        linhas.append({
            "bloco": "qrapids",
            "eixo": "Produto",
            "titulo_bloco": "Qualidade (Q-Rapids)",
            "indicador": str(r.nome),
            "R1": _fmt_num(getattr(r, "R1", None), 2),
            "R2": _fmt_num(getattr(r, "R2", None), 2),
            "R3": _fmt_num(getattr(r, "Atual", None), 2),
            "status": estados.get(getattr(r, "situacao", None), "unavailable"),
            "leitura": f"meta ≥ {meta_str}" if meta_str is not None else "meta ≥ —",
            "onde": "Qualidade (Q-Rapids)",
        })
    return pd.DataFrame(linhas, columns=COLUNAS)


def linhas_fluxo(itens: pd.DataFrame | None, jan: dict, coletado: bool) -> pd.DataFrame:
    """Calcula itens concluídos, Lead Time e Cycle Time (mediana) em cada janela do Canvas."""
    if itens is None or itens.empty:
        return pd.DataFrame(columns=COLUNAS)
    fechadas, lt_med, ct_med = {}, {}, {}
    for r in JANELAS:
        if r not in jan:
            fechadas[r] = lt_med[r] = ct_med[r] = None
            continue
        ini, fim = jan[r]
        tc = fluxo.taxa_conclusao(itens, ini, fim)
        lt = fluxo.lead_time(itens, ini, fim)
        ct = fluxo.cycle_time(itens, ini, fim, coletado=coletado)
        f_val = tc.get("fechadas")
        fechadas[r] = None if vazio(f_val) else num(f_val, 0)
        l_val = lt.get("mediana")
        lt_med[r] = None if vazio(l_val) else num(l_val, 1)
        c_val = ct.get("mediana")
        ct_med[r] = None if vazio(c_val) else num(c_val, 1)

    base = {"bloco": "fluxo", "eixo": "Processo", "titulo_bloco": "Fluxo",
            "status": "neutral", "leitura": "informativo: sem meta no plano", "onde": "Fluxo"}
    linhas = [
        {**base, "indicador": "Itens concluídos",
         "R1": fechadas["R1"], "R2": fechadas["R2"], "R3": fechadas["R3"]},
        {**base, "indicador": "Lead time (mediana, dias)",
         "R1": lt_med["R1"], "R2": lt_med["R2"], "R3": lt_med["R3"]},
        {**base, "indicador": "Cycle time (mediana, dias)",
         "R1": ct_med["R1"], "R2": ct_med["R2"], "R3": ct_med["R3"]},
    ]
    return pd.DataFrame(linhas, columns=COLUNAS)


def situacao_blocos(linhas: pd.DataFrame | None) -> dict[str, str]:
    """Mapeia cada bloco para o pior status entre os seus indicadores (via ``theme.pior``)."""
    if linhas is None or linhas.empty or "bloco" not in linhas:
        return {}
    return {bloco: theme.pior(list(grupo["status"]))
            for bloco, grupo in linhas.groupby("bloco", sort=False)}
