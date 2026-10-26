"""AgileEVM por release com os pontos do Zenhub e os custos da planilha.

Método de Sulaiman, Barton & Blackburn (2006), o mesmo da planilha de 2026.1.
Tudo o que é ponto vem do Zenhub (``src/metrics/velocity.py``); da planilha vem só o que
o Zenhub não tem: quem está no time em cada semana e quanto isso custa (abas Custos e
Planejamento). Horas não entram: a estimativa é em Story Points e o custo é o do time.

Para cada sprint ``n`` de uma release com ``L`` sprints:

* **Escopo (PRP)**: pontos das issues pontuáveis que passaram pelas sprints da
  release até ``n`` (cada issue uma vez, com a estimativa atual). A **linha de
  base** é o planejado da primeira sprint; **PA** é o que entrou depois.
* **RPC**: pontos das issues desse escopo concluídas até o fim da sprint ``n``.
* **APC** = RPC ÷ PRP · **PPC** = semanas decorridas ÷ semanas da release.
* **BAC** = custo planejado das semanas da release · **PV** = PPC × BAC ·
  **EV** = APC × BAC.
* **AC** (custo real) = custo do time nas sprints já iniciadas, acumulado: em cada semana, integrantes
  ativos (aba Planejamento) × custo de um integrante por semana + infraestrutura. É o "run rate" do time,
  como na literatura de EVM ágil (Sulaiman et al., 2006; Cohn, *Agile Estimating and Planning*): ninguém
  estima nem aponta horas; o custo muda quando a composição do time muda. Sprint sem custo na aba
  Planejamento deixa o AC **indisponível** a partir dela (nunca é inventado), e CPI, CV, ETC e EAC junto.
  Com o time estável, AC acompanha o PV e o CPI fica próximo do SPI — é o esperado nesse método.
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


def integrantes_planejados(inicio: pd.Timestamp, fim: pd.Timestamp, plano: pd.DataFrame) -> float:
    """Maior número de integrantes ativos (aba Planejamento) nas semanas da sprint."""
    if plano is None or plano.empty or "integrantes" not in plano:
        return NAN
    p = plano[(plano["semana"] >= inicio) & (plano["semana"] <= fim)]["integrantes"].dropna()
    return float(p.max()) if not p.empty else NAN


# lado de custo do EVM: não depende de quais repositórios estão no filtro
COLUNAS_CUSTO = ("BAC", "SC", "PV", "EV", "AC", "CV", "SV", "CPI", "ETC", "EAC", "origem_do_ac", "integrantes_ativos")


def agile_evm(sprints: pd.DataFrame, issues: dict, plano: pd.DataFrame, horas: pd.DataFrame | None = None,
              custo_hora: float | None = None, recorte: str | None = None,
              time: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por sprint de cada release (inclusive as futuras, com valores vazios).

    ``sprints`` é a saída de ``velocity.calculate_velocity(..., incluir_futuras=True)``.
    ``horas`` e ``custo_hora`` não são mais usados (o AC é o custo do time); ficam na assinatura só para
    não quebrar quem chama.
    ``recorte`` (ex.: filtro de repositórios): os pontos e o prazo (PPC, APC, SPI) são do recorte, mas
    orçamento e horas não dependem de repositório. Com ``time`` (o EVM do time inteiro) os valores em R$ e o
    CPI vêm dele e ``escopo_custo`` diz isso; sem ``time`` ficam indisponíveis.
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
                linhas.append({**linha, **{k: NAN for k in ("PP", "PC", "PA", "PRP", "RPC", "APC", "AC",
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
            ativos = integrantes_planejados(r.inicio, r.fim, plano)
            # custo real = custo do time na sprint (run rate), acumulado na release
            if math.isnan(sc):
                ac_completo = False
                origem = (f"indisponível: a aba Planejamento não tem o custo das semanas da {r.sprint_label}")
            elif not ac_completo:
                origem = "indisponível: sprint anterior da release sem custo na aba Planejamento"
            else:
                ac_acum += sc
                origem = "custo do time na sprint (integrantes ativos × custo por semana + infraestrutura)"
            ev = apc * bac if not math.isnan(bac) else NAN
            pv = linha["PV"]
            spi = _div(apc, ppc)          # = EV ÷ PV, e não depende do custo
            ac = ac_acum if ac_completo else NAN
            cpi = _div(ev, ac) if not math.isnan(ac) else NAN
            etc = _div(bac - ev, cpi) if not math.isnan(cpi) else NAN
            duracao = (grupo["fim"].iloc[-1] - grupo["inicio"].iloc[0]).days + 1
            rd = (grupo["inicio"].iloc[0] + pd.Timedelta(days=duracao / spi)) if spi and not math.isnan(spi) else pd.NaT
            linhas.append({**linha, "PP": r.planned_story_points, "PC": r.completed_story_points, "PA": pa,
                           "PRP": prp, "RPC": rpc, "APC": apc, "AC": ac,
                           "origem_do_ac": origem, "EV": ev, "CV": ev - ac, "SV": ev - pv, "CPI": cpi,
                           "SPI": spi, "integrantes_ativos": ativos, "ETC": etc,
                           "EAC": ac + etc if not math.isnan(etc) else NAN, "RD": rd,
                           "issues": len(escopo)})
    df = pd.DataFrame(linhas)
    if recorte and not df.empty:
        # Pontos são do recorte; orçamento e custo são do time inteiro. Misturar os dois (EV do recorte ÷ AC
        # do time) daria um CPI sem sentido, então o lado de custo vem inteiro do EVM do time.
        custo = [c for c in COLUNAS_CUSTO if c in df]
        if time is not None and not time.empty:
            t = time.set_index(["release", "sprint"])
            for col in custo:
                if col in t:
                    df[col] = [t[col].get((r, s_), NAN) for r, s_ in zip(df["release"], df["sprint"])]
            df["escopo_custo"] = "time inteiro (orçamento e horas não dependem do filtro de repositórios)"
        else:
            for col in custo:
                if col not in ("origem_do_ac", "integrantes_ativos"):
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
