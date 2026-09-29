"""AgileEVM por release com os pontos do Zenhub e os custos da planilha.

Método de Sulaiman, Barton & Blackburn (2006), o mesmo da planilha de 2026.1.
Tudo o que é ponto vem do Zenhub (``src/metrics/velocity.py``); da planilha vêm só o que
o Zenhub não tem: o custo planejado de cada semana (abas Custos e Planejamento)
e as horas reais (aba Horas).

Para cada sprint ``n`` de uma release com ``L`` sprints:

* **Escopo (PRP)**: pontos das issues pontuáveis que passaram pelas sprints da
  release até ``n`` (cada issue uma vez, com a estimativa atual). A **linha de
  base** é o planejado da primeira sprint; **PA** é o que entrou depois.
* **RPC**: pontos das issues desse escopo concluídas até o fim da sprint ``n``.
* **APC** = RPC ÷ PRP · **PPC** = semanas decorridas ÷ semanas da release.
* **BAC** = custo planejado das semanas da release · **PV** = PPC × BAC ·
  **EV** = APC × BAC.
* **AC**: horas reais (aba Horas) × custo/hora (aba Custos), acumulado. Se
  alguma sprint iniciada da release não tem horas registradas, o AC fica
  **indisponível** a partir dela (também quando só parte dos integrantes ativos da aba
  Planejamento registrou horas, porque o AC sairia subestimado) — nunca é trocado pelo custo planejado — e
  CPI, CV, ETC e EAC ficam indisponíveis junto. ``origem_do_ac`` diz o motivo.
* **SPI** = EV ÷ PV · **CPI** = EV ÷ AC · **CV**, **SV**, **ETC** = (BAC − EV) ÷ CPI,
  **EAC** = AC + ETC · **RD** = início + duração ÷ SPI.
"""

from __future__ import annotations

import math

import pandas as pd

from src.metrics import velocity as vel

NAN = float("nan")


def _data_local(serie: pd.Series) -> pd.Series:
    """Datas do Zenhub (UTC) no dia de Brasília. O fim 02:59 UTC de segunda é domingo."""
    s = pd.to_datetime(serie, utc=True)
    try:
        s = s.dt.tz_convert("America/Sao_Paulo")
    except Exception:  # noqa: BLE001 — sem base de fusos no navegador
        s = s - pd.Timedelta(hours=3)
    return s.dt.tz_localize(None).dt.normalize()


def _div(a, b):
    return a / b if b and not (isinstance(b, float) and math.isnan(b)) else NAN


def custo_da_sprint(inicio: pd.Timestamp, fim: pd.Timestamp, plano: pd.DataFrame) -> float:
    """Soma do custo planejado das semanas (aba Planejamento) que começam dentro da sprint."""
    if plano is None or plano.empty or "semana" not in plano:
        return NAN
    p = plano.dropna(subset=["semana", "custo"])
    semanas = p[(p["semana"] >= inicio) & (p["semana"] <= fim)]
    return float(semanas["custo"].sum()) if not semanas.empty else NAN


def integrantes_com_horas(label: str, inicio: pd.Timestamp, horas: pd.DataFrame) -> int:
    """Quantos integrantes têm horas (> 0) registradas na sprint (aba Horas)."""
    if horas is None or horas.empty or "horas" not in horas or "integrante" not in horas:
        return 0
    h = horas[pd.to_numeric(horas["horas"], errors="coerce").fillna(0) > 0]
    if "inicio_da_sprint" in h and h["inicio_da_sprint"].notna().any():
        h = h[h["inicio_da_sprint"] == inicio]
    else:
        numero = int(label.lstrip("S")) if label.lstrip("S").isdigit() else None
        h = h[h["sprint"] == numero] if numero is not None and "sprint" in h else h.iloc[0:0]
    return int(h["integrante"].astype(str).str.strip().nunique())


def integrantes_planejados(inicio: pd.Timestamp, fim: pd.Timestamp, plano: pd.DataFrame) -> float:
    """Maior número de integrantes ativos (aba Planejamento) nas semanas da sprint."""
    if plano is None or plano.empty or "integrantes" not in plano:
        return NAN
    p = plano[(plano["semana"] >= inicio) & (plano["semana"] <= fim)]["integrantes"].dropna()
    return float(p.max()) if not p.empty else NAN


def horas_da_sprint(label: str, inicio: pd.Timestamp, horas: pd.DataFrame) -> float:
    """Horas da aba Horas: pela data de início da sprint, ou pelo número (S3 = sprint 3)."""
    if horas is None or horas.empty or "horas" not in horas:
        return 0.0
    h = horas.dropna(subset=["horas"])
    if "inicio_da_sprint" in h and h["inicio_da_sprint"].notna().any():
        return float(h.loc[h["inicio_da_sprint"] == inicio, "horas"].sum())
    numero = int(label.lstrip("S")) if label.lstrip("S").isdigit() else None
    return float(h.loc[h["sprint"] == numero, "horas"].sum()) if numero is not None and "sprint" in h else 0.0


def agile_evm(sprints: pd.DataFrame, issues: dict, plano: pd.DataFrame, horas: pd.DataFrame,
              custo_hora: float | None, recorte: str | None = None) -> pd.DataFrame:
    """Uma linha por sprint de cada release (inclusive as futuras, com valores vazios).

    ``sprints`` é a saída de ``velocity.calculate_velocity(..., incluir_futuras=True)``.
    """
    if sprints is None or sprints.empty:
        return pd.DataFrame()
    d = sprints[sprints["release_name"].notna() & (sprints["status"] != vel.STATUS_CANCELADA)].copy()
    if d.empty:
        return pd.DataFrame()
    d["inicio"] = _data_local(d["start_date"])
    # o fim do Zenhub é 02:59 UTC do dia seguinte = 23:59 do último dia em Brasília
    d["fim"] = _data_local(d["end_date"])
    d["semanas"] = (((d["fim"] - d["inicio"]).dt.days + 1) / 7).round()
    est = {i: (issues.get(i, {}).get("estimate") or 0.0) for i in issues}
    linhas = []
    for rel, grupo in d.sort_values("start_date").groupby("release_name", sort=False):
        grupo = grupo.reset_index(drop=True)
        L = len(grupo)
        semanas_rel = float(grupo["semanas"].sum())
        custos = [custo_da_sprint(r.inicio, r.fim, plano) for r in grupo.itertuples()]
        bac = float(pd.Series(custos).sum(min_count=1))
        primeira = grupo.iloc[0]
        base_ids = primeira["planned_ids"] if isinstance(primeira["planned_ids"], list) else primeira["scope_ids"]
        prp_base = sum(est.get(i, 0.0) for i in (base_ids or []))
        escopo, feitos = set(base_ids or []), set()
        prp_ant = prp_base
        semanas_acum, ac_acum, ac_completo = 0.0, 0.0, True
        for n, r in enumerate(grupo.itertuples(), start=1):
            semanas_acum += r.semanas
            ppc = _div(semanas_acum, semanas_rel)
            sc = custos[n - 1]
            iniciou = r.status != vel.STATUS_FUTURA
            linha = {"release": rel, "sprint": r.sprint_label, "n": n, "L": L, "status": r.status,
                     "inicio_da_sprint": r.inicio, "fim_da_sprint": r.fim, "semanas": r.semanas,
                     "PPC": ppc, "BAC": bac, "SC": sc, "PV": ppc * bac if not math.isnan(bac) else NAN,
                     "prp_linha_de_base": prp_base}
            if not iniciou:
                linhas.append({**linha, **{k: NAN for k in ("PP", "PC", "PA", "PRP", "RPC", "APC", "horas_reais", "AC",
                                                              "EV", "CV", "SV", "CPI", "SPI", "ETC", "EAC")},
                               "origem_do_ac": "", "RD": pd.NaT, "issues": 0})
                continue
            escopo |= set(r.scope_ids or [])
            feitos |= set(r.completed_ids or []) & escopo
            prp = sum(est.get(i, 0.0) for i in escopo)
            rpc = sum(est.get(i, 0.0) for i in feitos)
            pa = prp - prp_ant if n > 1 else prp - prp_base
            prp_ant = prp
            apc = _div(rpc, prp)
            h = horas_da_sprint(r.sprint_label, r.inicio, horas)
            com_horas = integrantes_com_horas(r.sprint_label, r.inicio, horas)
            ativos = integrantes_planejados(r.inicio, r.fim, plano)
            if h > 0 and custo_hora and not math.isnan(ativos) and com_horas < ativos:
                # horas de só parte do time: o AC sairia subestimado e o CPI melhor do que é
                custo_real, origem = NAN, (f"indisponível: horas de {com_horas} de {ativos:.0f} integrantes ativos na "
                                           f"{r.sprint_label} (aba Horas × aba Planejamento)")
            elif h > 0 and custo_hora:
                custo_real, origem = h * custo_hora, "horas reais × custo/hora"
            elif not custo_hora:
                custo_real, origem = NAN, "indisponível: custo/hora não informado (aba Custos)"
            else:
                custo_real, origem = NAN, f"indisponível: sem horas registradas na {r.sprint_label} (aba Horas)"
            if math.isnan(custo_real):
                ac_completo = False
            if ac_completo:
                ac_acum += custo_real
            elif not math.isnan(custo_real):
                origem = "indisponível: sprint anterior da release sem horas registradas"
            ev = apc * bac if not math.isnan(bac) else NAN
            pv = linha["PV"]
            spi = _div(apc, ppc)          # = EV ÷ PV, e não depende do custo
            ac = ac_acum if ac_completo else NAN
            cpi = _div(ev, ac) if not math.isnan(ac) else NAN
            etc = _div(bac - ev, cpi) if not math.isnan(cpi) else NAN
            duracao = (grupo["fim"].iloc[-1] - grupo["inicio"].iloc[0]).days + 1
            rd = (grupo["inicio"].iloc[0] + pd.Timedelta(days=duracao / spi)) if spi and not math.isnan(spi) else pd.NaT
            linhas.append({**linha, "PP": r.planned_story_points, "PC": r.completed_story_points, "PA": pa,
                           "PRP": prp, "RPC": rpc, "APC": apc, "horas_reais": h, "AC": ac,
                           "origem_do_ac": origem, "EV": ev, "CV": ev - ac, "SV": ev - pv, "CPI": cpi,
                           "SPI": spi, "integrantes_com_horas": com_horas, "integrantes_ativos": ativos, "ETC": etc, "EAC": ac + etc if not math.isnan(etc) else NAN, "RD": rd,
                           "issues": len(escopo)})
    df = pd.DataFrame(linhas)
    if recorte and not df.empty:
        # Com recorte (ex.: só alguns repositórios) os pontos são do recorte, mas orçamento e horas são do
        # time inteiro: juntar os dois daria valores em R$ sem sentido. Fica só o prazo (PPC, APC, SPI).
        for col in ("BAC", "SC", "PV", "EV", "AC", "CV", "SV", "CPI", "ETC", "EAC", "horas_reais"):
            if col in df:
                df[col] = NAN
        df["origem_do_ac"] = f"indisponível: {recorte}"
        df["motivo_valor"] = recorte
    return df


def sumario(evm: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por release: situação na última sprint iniciada."""
    if evm is None or evm.empty:
        return pd.DataFrame()
    out = []
    for rel, g in evm.groupby("release", sort=False):
        feitas = g.dropna(subset=["PRP"])
        u = feitas.iloc[-1] if not feitas.empty else None
        out.append({"release": rel, "inicio": g["inicio_da_sprint"].min(), "fim": g["fim_da_sprint"].max(),
                    "L": int(g["L"].iloc[0]), "semanas": float(g["semanas"].sum()), "BAC": g["BAC"].iloc[0],
                    "prp_linha_de_base": g["prp_linha_de_base"].iloc[0] if u is not None else NAN,
                    "prp_atual": u["PRP"] if u is not None else NAN, "RPC": u["RPC"] if u is not None else NAN,
                    "pv": u["PV"] if u is not None else NAN, "ev": u["EV"] if u is not None else NAN,
                    "ac": u["AC"] if u is not None else NAN, "spi": u["SPI"] if u is not None else NAN,
                    "cpi": u["CPI"] if u is not None else NAN, "RD": u["RD"] if u is not None else pd.NaT})
    return pd.DataFrame(out)
