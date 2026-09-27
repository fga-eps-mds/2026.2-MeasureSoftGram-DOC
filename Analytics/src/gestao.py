"""Modelo de gestão: calendário, linha de base, velocity, burndown e AgileEVM.

Fontes (nenhum número é digitado à mão aqui):

* ``planilhas/sprints.csv``    calendário oficial (o do Zenhub) e release de cada sprint
* ``planilhas/releases.csv``   data de entrega e PRP de linha de base de cada release
* ``planilhas/parametros.csv`` capacidade e custo/hora (PMBOK: estimar custos -> orçamento)
* ``planilhas/horas.csv``      horas reais por integrante e sprint (origem do AC)
* ``data/zenhub/*.json``       issues de cada sprint, com estimativa e pipeline

AgileEVM segue Sulaiman, Barton & Blackburn (2006), por release:

    PPC = n / L                  APC = pontos Done acumulados / PRP
    PV  = PPC * BAC              EV  = APC * BAC             AC = horas reais (* custo/hora)
    CPI = EV / AC                SPI = EV / PV = APC / PPC
    CV  = EV - AC                SV  = EV - PV
    ETC = (BAC - EV) / CPI       EAC = AC + ETC              RD = L / SPI (sprints)

Tudo é calculado em **horas** e convertido para R$ só quando ``custo_hora``
existe. CPI e SPI não dependem do custo/hora, porque ele aparece no numerador e
no denominador; ele só muda o valor absoluto de BAC, PV, EV, AC e EAC.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

TIPOS_PONTUADOS_PADRAO = {"Feature", "Task", "Bug"}


# ───────────────────────── leitura ─────────────────────────

# Preenchido pelo app com config.PLANILHAS: {nome da aba: URL do CSV publicado}.
URLS: dict = {}
ORIGEM: dict = {}   # de onde cada aba foi lida, para o app mostrar na tela


def _csv(pasta: Path, nome: str) -> pd.DataFrame:
    """Lê a aba publicada da planilha do Google; sem URL ou em falha, o CSV local."""
    url = URLS.get(nome, "")
    if url:
        try:
            import io
            import requests
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.content.decode("utf-8")), dtype=str).fillna("")
            df.columns = [str(c).strip() for c in df.columns]
            ORIGEM[nome] = "planilha do Google"
            return df
        except Exception as erro:  # noqa: BLE001 - qualquer falha cai para o CSV local
            ORIGEM[nome] = f"CSV local (a planilha falhou: {erro.__class__.__name__})"
    else:
        ORIGEM[nome] = "CSV local"
    try:
        return pd.read_csv(Path(pasta) / f"{nome}.csv", dtype=str).fillna("")
    except (OSError, pd.errors.EmptyDataError):
        ORIGEM[nome] = "não encontrado"
        return pd.DataFrame()


def _numero(serie: pd.Series) -> pd.Series:
    """'1.234,5' ou '1234.5' -> float (a planilha publica no formato brasileiro)."""
    texto = serie.astype(str).str.strip()
    br = texto.str.contains(",")
    texto = texto.where(~br, texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(texto, errors="coerce")


def carregar_parametros(pasta: Path) -> dict:
    df = _csv(pasta, "parametros")
    brutos = dict(zip(df.get("parametro", []), df.get("valor", [])))

    def num(chave):
        try:
            v = _numero(pd.Series([brutos.get(chave, "")])).iloc[0]
            return None if pd.isna(v) else float(v)
        except (ValueError, TypeError):
            return None

    tipos = str(brutos.get("niveis_pontuados", "")).strip()
    return {
        "pessoas": num("pessoas"),
        "horas_semana_pessoa": num("horas_semana_pessoa"),
        "custo_hora": num("custo_hora"),
        "criterio_feito": brutos.get("criterio_feito", "Done") or "Done",
        "tipos_pontuados": set(tipos.split(";")) if tipos else TIPOS_PONTUADOS_PADRAO,
        "tabela": df,
    }


def carregar_calendario(pasta: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sprints = _csv(pasta, "sprints")
    releases = _csv(pasta, "releases")
    if not sprints.empty:
        sprints = sprints[sprints["sprint"].str.strip() != ""].copy()
        sprints["sprint"] = _numero(sprints["sprint"]).astype(int)
        sprints["inicio"] = pd.to_datetime(sprints["inicio"], format="%Y-%m-%d")
        sprints["fim"] = pd.to_datetime(sprints["fim"], format="%Y-%m-%d")
        sprints["semanas"] = ((sprints["fim"] - sprints["inicio"]).dt.days + 1) / 7
    if not releases.empty:
        releases = releases[releases["release"].str.strip() != ""].copy()
        releases["entrega"] = pd.to_datetime(releases["entrega"], format="%Y-%m-%d")
        releases["prp_linha_de_base"] = _numero(releases["prp_linha_de_base"])
    return sprints, releases


def carregar_horas(pasta: Path) -> pd.DataFrame:
    df = _csv(pasta, "horas")
    if df.empty or "horas" not in df:
        return pd.DataFrame(columns=["sprint", "integrante", "horas"])
    df = df[df["sprint"].str.strip() != ""].copy()
    df["sprint"] = _numero(df["sprint"]).astype(int)
    df["horas"] = _numero(df["horas"]).fillna(0)
    return df


def carregar_zenhub(pasta: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Lê o snapshot mais recente do Zenhub.

    Devolve (issues por sprint, resumo das sprints, nome do arquivo lido).
    """
    arquivos = sorted(Path(pasta).glob("zenhub-sprints-*.json"))
    if not arquivos:
        return pd.DataFrame(), pd.DataFrame(), ""
    dado = json.loads(arquivos[-1].read_text(encoding="utf-8"))
    linhas, resumo = [], []
    for s in dado.get("sprints", []):
        resumo.append({"zenhub_sprint_id": s["id"], "nome": s["nome"],
                       "total_issues": s.get("total_issues", len(s["issues"])),
                       "coleta_completa": s.get("completo", True)})
        for i in s["issues"]:
            linhas.append({"zenhub_sprint_id": s["id"], **i})
    return pd.DataFrame(linhas), pd.DataFrame(resumo), arquivos[-1].name


def _eh_pr(url) -> bool:
    return isinstance(url, str) and "/pull/" in url


def _pais(issues: pd.DataFrame, tipos: set | None = None) -> set:
    """Chaves (repo, número) das issues que têm filhas.

    Uma US decomposta em Tasks não recebe pontos: quem pontua são as Tasks.
    O snapshot antigo guarda só o número do pai; quando o repositório do pai
    não vem, assumimos o repositório central de documentação, onde vivem
    Épicos e US.
    """
    if issues.empty or "pai" not in issues:
        return set()
    repo_pai = issues["pai_repositorio"] if "pai_repositorio" in issues else None
    chaves = set()
    filhas = issues if tipos is None else issues[issues["tipo"].isin(tipos)]
    for idx, pai in filhas["pai"].items():
        if pd.isna(pai):
            continue
        repo = repo_pai[idx] if repo_pai is not None and isinstance(repo_pai[idx], str) else "2026.2-MeasureSoftGram-DOC"
        chaves.add((repo, int(pai)))
    return chaves


def pontuaveis(issues: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Issues que carregam story points: US/Task/Bug sem filhas, e que não são PR."""
    if issues.empty:
        return issues
    pais = _pais(issues, params["tipos_pontuados"])
    d = issues[issues["tipo"].isin(params["tipos_pontuados"]) & ~issues["url"].map(_eh_pr)]
    return d[[(r, int(n)) not in pais for r, n in zip(d["repositorio"], d["numero"])]]


# ───────────────────────── processo ─────────────────────────

def qualidade_do_quadro(issues: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Problemas de higiene do Zenhub que distorcem velocity e EVM."""
    if issues.empty:
        return pd.DataFrame()
    tipos = params["tipos_pontuados"]
    feito = params["criterio_feito"]
    i = issues.drop_duplicates(["repositorio", "numero"], keep="last")
    chaves_pont = set(zip(*[pontuaveis(i, params)[c] for c in ("repositorio", "numero")])) if not i.empty else set()
    pais = _pais(issues, tipos)
    problemas = []
    for _, r in i.iterrows():
        if _eh_pr(r["url"]):
            continue  # PR não é item de backlog; entra no quadro só pela issue ligada
        chave = (r["repositorio"], r["numero"])
        pontuavel = chave in chaves_pont
        if chave in pais and r["tipo"] in tipos and pd.notna(r["estimativa"]):
            problemas.append((r, "US/Task com filhas estimadas na própria issue",
                              "Deixar os pontos só nas filhas (Tasks)"))
            continue
        if pontuavel and pd.isna(r["estimativa"]):
            problemas.append((r, "Sem estimativa", "Estimar em planning poker"))
        if not pontuavel and pd.notna(r["estimativa"]) and chave not in pais:
            tipo_txt = r["tipo"] if isinstance(r["tipo"], str) and r["tipo"] else "sem tipo"
            problemas.append((r, f"Estimativa em nível não pontuado ({tipo_txt})",
                              "Mover os pontos para a US/Task ou remover"))
        if r["estado"] == "CLOSED" and r["pipeline"] != feito:
            problemas.append((r, f"Fechada, mas no pipeline '{r['pipeline']}'",
                              f"Mover para {feito} se cumpriu o DoD, ou reabrir"))
        if r["tipo"] in (None, "") or pd.isna(r["tipo"]):
            problemas.append((r, "Sem tipo de issue (PR ou issue solta)",
                              "Tipar e ligar a um pai, ou remover da sprint"))
    return pd.DataFrame([{
        "issue": f"{p['repositorio'].replace('2026.2-MeasureSoftGram-', '')}#{p['numero']}",
        "titulo": p["titulo"], "problema": prob, "acao": acao, "url": p["url"],
    } for p, prob, acao in problemas])


def velocity_por_sprint(sprints: pd.DataFrame, issues: pd.DataFrame,
                        params: dict, hoje: pd.Timestamp) -> pd.DataFrame:
    """PP = pontos comprometidos na sprint; PC = pontos no pipeline Done.

    Só conta issues dos tipos pontuados, para não somar pai e filho.
    """
    tipos = params["tipos_pontuados"]
    feito = params["criterio_feito"]
    linhas = []
    for _, s in sprints.iterrows():
        if s["inicio"] > hoje:
            continue
        d = issues[(issues.get("zenhub_sprint_id") == s["zenhub_sprint_id"])] if not issues.empty else issues
        d = pontuaveis(d, params) if not d.empty else d
        pp = d["estimativa"].fillna(0).sum() if not d.empty else 0
        pc = d.loc[d["pipeline"] == feito, "estimativa"].fillna(0).sum() if not d.empty else 0
        linhas.append({"sprint": int(s["sprint"]), "release": s["release"],
                       "inicio": s["inicio"].date(), "fim": s["fim"].date(),
                       "pp": float(pp), "pc": float(pc),
                       "encerrada": bool(s["fim"] < hoje)})
    df = pd.DataFrame(linhas)
    if not df.empty:
        encerradas = df[df["encerrada"]]
        df["velocity_media"] = encerradas["pc"].mean() if not encerradas.empty else float("nan")
    return df


# ───────────────────────── projeto (AgileEVM) ─────────────────────────

def agile_evm(sprints: pd.DataFrame, releases: pd.DataFrame, issues: pd.DataFrame,
              horas: pd.DataFrame, params: dict, hoje: pd.Timestamp) -> pd.DataFrame:
    tipos = params["tipos_pontuados"]
    feito = params["criterio_feito"]
    capacidade = (params["pessoas"] or 0) * (params["horas_semana_pessoa"] or 0)
    custo = params["custo_hora"]
    linhas = []

    for _, rel in releases.iterrows():
        cal = sprints[sprints["release"] == rel["release"]].sort_values("sprint")
        if cal.empty:
            continue
        L = len(cal)
        bac_h = capacidade * cal["semanas"].sum() if capacidade else float("nan")
        prp_base = rel["prp_linha_de_base"]
        vistos: dict = {}      # issue -> pontos (escopo que já entrou na release)
        feitos: set = set()    # issues que chegaram ao pipeline Done
        prp_anterior = prp_base if pd.notna(prp_base) else 0.0
        for n, (_, s) in enumerate(cal.iterrows(), start=1):
            iniciou = s["inicio"] <= hoje
            d = issues[issues["zenhub_sprint_id"] == s["zenhub_sprint_id"]] if not issues.empty else issues
            d = pontuaveis(d, params) if not d.empty else d
            if iniciou and not d.empty:
                for _, r in d.iterrows():
                    chave = (r["repositorio"], r["numero"])
                    vistos[chave] = 0.0 if pd.isna(r["estimativa"]) else float(r["estimativa"])
                    if r["pipeline"] == feito:
                        feitos.add(chave)
            escopo = sum(vistos.values())
            # Com linha de base, só o que passa dela é escopo adicionado (PA).
            # Sem linha de base (R1), o PRP é reconstituído com tudo o que entrou.
            prp = max(prp_base, escopo) if pd.notna(prp_base) else escopo
            pa_registrado = prp - prp_anterior
            prp_anterior = prp
            pc_acum = sum(v for k, v in vistos.items() if k in feitos)
            ppc = n / L
            apc = (pc_acum / prp) if prp else float("nan")
            h_real = horas.loc[horas["sprint"].isin(cal["sprint"].head(n)), "horas"].sum() if not horas.empty else 0.0
            ac_h = h_real if h_real > 0 else float("nan")
            pv_h, ev_h = ppc * bac_h, apc * bac_h
            spi = apc / ppc if ppc and pd.notna(apc) else float("nan")
            cpi = ev_h / ac_h if pd.notna(ac_h) and ac_h else float("nan")
            etc_h = (bac_h - ev_h) / cpi if pd.notna(cpi) and cpi else float("nan")
            linhas.append({
                "release": rel["release"], "sprint": int(s["sprint"]), "n": n, "L": L,
                "iniciada": iniciou, "linha_de_base": "declarada" if pd.notna(prp_base) else "reconstituída",
                "PA": pa_registrado if iniciou else float("nan"),
                "PRP": prp if iniciou else float("nan"),
                "RPC": pc_acum if iniciou else float("nan"),
                "PPC": ppc, "APC": apc if iniciou else float("nan"),
                "BAC_h": bac_h, "PV_h": pv_h, "EV_h": ev_h if iniciou else float("nan"),
                "AC_h": ac_h if iniciou else float("nan"),
                "SPI": spi if iniciou else float("nan"), "CPI": cpi if iniciou else float("nan"),
                "SV_h": (ev_h - pv_h) if iniciou else float("nan"),
                "CV_h": (ev_h - ac_h) if iniciou else float("nan"),
                "EAC_h": (ac_h + etc_h) if iniciou else float("nan"),
                "RD_sprints": (L / spi) if iniciou and spi else float("nan"),
            })
    df = pd.DataFrame(linhas)
    if not df.empty and custo:
        for col in ("BAC", "PV", "EV", "AC", "SV", "CV", "EAC"):
            df[f"{col}_rs"] = df[f"{col}_h"] * custo
    return df


def burndown_release(evm: pd.DataFrame, release: str) -> pd.DataFrame:
    """Pontos restantes da release ao fim de cada sprint, contra a linha ideal."""
    d = evm[evm["release"] == release].copy()
    if d.empty:
        return d
    # Ideal recalculado com o escopo de cada sprint: quando entra escopo (PA),
    # a linha ideal sobe junto, e o gráfico mostra a mudança em vez de escondê-la.
    d["restante"] = d["PRP"] - d["RPC"]
    d["ideal"] = d["PRP"] * (1 - d["n"] / d["L"])
    return d[["sprint", "n", "PRP", "RPC", "restante", "ideal", "iniciada"]]
