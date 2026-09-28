"""Carga de todas as fontes, com cache e metadados de atualização.

Cada fonte é carregada de forma independente: se uma falha (arquivo ilegível,
planilha fora do ar), ela aparece como indisponível em "Metodologia e Fontes" e
nas páginas que a usam — as outras continuam funcionando.

O cache (``st.cache_data``) é invalidado pela lista de arquivos e datas de
modificação (fontes em disco) ou por tempo (planilha publicada, 5 minutos).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from src.data import github, planilha, sonar
from src.metrics import agile, evm, velocity
from src.zenhub import coleta as zh_coleta

RAIZ = Path(__file__).resolve().parents[2]
PASTAS_PIPELINE = [RAIZ / "data"]          # todos os .json do pipeline ficam em Analytics/data
PASTA_PLANILHAS = RAIZ / "planilhas"       # só no navegador: CSVs baixados da planilha publicada no deploy
NO_NAVEGADOR = sys.platform == "emscripten"


def _agora_brt() -> pd.Timestamp:
    try:
        return pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None)
    except Exception:  # noqa: BLE001 — ambiente sem base de fusos
        return pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(hours=3)


def _para_brt(ts) -> pd.Timestamp | None:
    if ts is None or (not isinstance(ts, str) and pd.isna(ts)):
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t
    try:
        return t.tz_convert("America/Sao_Paulo").tz_localize(None)
    except Exception:  # noqa: BLE001
        return t.tz_convert(None) - pd.Timedelta(hours=3)


def _marca(pastas: list[Path], padrao: str = "*.json") -> tuple:
    return tuple(sorted((str(p), p.stat().st_mtime) for pasta in pastas if pasta.exists()
                        for p in pasta.glob(padrao)))


@dataclass
class Fonte:
    """Metadados de uma fonte, exibidos no cabeçalho e em Metodologia e Fontes."""
    fonte: str                 # SONAR, ZENHUB, PLANILHA, GITHUB
    entrada: str               # o que exatamente foi lido
    status: str                # ok | parcial | sem dados | erro
    ultima_atualizacao: pd.Timestamp | None = None
    periodo: tuple | None = None
    registros: int = 0
    mensagem: str = ""


@dataclass
class Contexto:
    hoje: pd.Timestamp
    agora_utc: datetime
    fontes: list[Fonte] = field(default_factory=list)
    # SONAR
    sonar_pipeline: pd.DataFrame = field(default_factory=pd.DataFrame)
    sonar_componentes: pd.DataFrame = field(default_factory=pd.DataFrame)
    sonar_erros: pd.DataFrame = field(default_factory=pd.DataFrame)
    sonar_api: dict = field(default_factory=dict)
    sonar_api_snap: dict | None = None
    sonar_serie: pd.DataFrame = field(default_factory=pd.DataFrame)
    sonar_atual: pd.DataFrame = field(default_factory=pd.DataFrame)
    # GITHUB
    gh_issues: pd.DataFrame = field(default_factory=pd.DataFrame)
    gh_runs: pd.DataFrame = field(default_factory=pd.DataFrame)
    # ZENHUB
    zh_snap: dict | None = None
    zh_arquivo: str = ""
    zh_regras: velocity.Regras = field(default_factory=velocity.Regras)
    zh_sprints: pd.DataFrame = field(default_factory=pd.DataFrame)      # inclui futuras
    zh_issues: pd.DataFrame = field(default_factory=pd.DataFrame)
    zh_backlog_completo: bool = False
    # PLANILHA
    custos_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    custo: dict = field(default_factory=dict)
    plano_bruto: pd.DataFrame = field(default_factory=pd.DataFrame)
    plano: pd.DataFrame = field(default_factory=pd.DataFrame)
    horas: pd.DataFrame = field(default_factory=pd.DataFrame)
    riscos: pd.DataFrame = field(default_factory=pd.DataFrame)
    monitoramento: pd.DataFrame = field(default_factory=pd.DataFrame)
    decisoes: pd.DataFrame = field(default_factory=pd.DataFrame)
    origem_planilha: dict = field(default_factory=dict)
    parametros: dict = field(default_factory=dict)
    # CALCULADO
    evm: pd.DataFrame = field(default_factory=pd.DataFrame)
    evm_sumario: pd.DataFrame = field(default_factory=pd.DataFrame)
    calendario: pd.DataFrame = field(default_factory=pd.DataFrame)

    def fonte(self, nome: str) -> list[Fonte]:
        return [f for f in self.fontes if f.fonte == nome]

    @property
    def zh_iniciadas(self) -> pd.DataFrame:
        s = self.zh_sprints
        return s[s["status"] != velocity.STATUS_FUTURA] if not s.empty else s


# ───────────────────────── carregadores com cache ─────────────────────────

@st.cache_data(show_spinner="Lendo as métricas do SonarCloud...")
def _sonar(pastas: tuple[str, ...], _marca_arquivos: tuple):
    p = [Path(x) for x in pastas]
    agregado, componentes = sonar.carregar_sonar(p)
    snap, nome = sonar.ultimo_snapshot()
    return agregado, componentes, sonar.coletas_com_erro(p), snap, nome


@st.cache_data(show_spinner="Lendo os dados do GitHub...")
def _github(pastas: tuple[str, ...], _marca_arquivos: tuple):
    p = [Path(x) for x in pastas]
    return github.carregar_issues(p), github.carregar_runs(p)


@st.cache_data(show_spinner="Lendo o snapshot do Zenhub...")
def _zenhub(pasta: str, _marca_arquivos: tuple):
    snap, nome = zh_coleta.ultimo_snapshot(Path(pasta))
    return snap, nome, zh_coleta.ler_linhas_de_base(Path(pasta))


@st.cache_data(ttl=config.CACHE_PLANILHAS_S, show_spinner="Lendo a planilha do time...")
def _planilha(urls: dict):
    ler = lambda chave, **kw: planilha.ler(chave, urls, PASTA_PLANILHAS, **kw)  # noqa: E731
    c_df = ler("custos")
    plano_bruto = ler("planejamento")
    horas = planilha.converter(ler("horas"), numericas=["sprint", "horas"],
                               datas=["inicio_da_sprint", "fim_da_sprint"])
    riscos = planilha.converter(ler("riscos"), numericas=["ultima_sprint_avaliada", "probabilidade_atual",
                                                          "impacto_atual", "exposicao_atual"],
                                datas=["identificado_em", "prazo"])
    mon = planilha.converter(ler("monitoramento"), numericas=["sprint", "probabilidade", "impacto", "exposicao"],
                             datas=["data_da_revisao"])
    dec = ler("decisoes")
    lidos_em = _agora_brt()
    return (c_df, planilha.custos(c_df), plano_bruto, planilha.planejamento_semanal(plano_bruto), horas, riscos,
            mon, dec, dict(planilha.ORIGEM), lidos_em)


# ───────────────────────── montagem ─────────────────────────

def _registrar_erro(ctx: Contexto, fonte: str, entrada: str, erro: Exception) -> None:
    ctx.fontes.append(Fonte(fonte, entrada, "erro", mensagem=f"{erro.__class__.__name__}: {erro}"[:240]))


def carregar() -> Contexto:
    ctx = Contexto(hoje=_agora_brt().normalize(), agora_utc=datetime.now(timezone.utc))
    pastas = tuple(str(p) for p in PASTAS_PIPELINE)

    # SONAR ────────────────────────────────────────────
    try:
        agregado, comp, erros, snap, nome = _sonar(pastas, _marca(PASTAS_PIPELINE + [sonar.PASTA_API]))
        ctx.sonar_pipeline, ctx.sonar_componentes, ctx.sonar_erros = agregado, comp, erros
        ctx.sonar_api_snap, ctx.sonar_api = snap, sonar.snapshot_para_tabelas(snap)
        ctx.sonar_serie = sonar.serie_temporal(agregado, ctx.sonar_api["historico"])
        atual = [x for x in (sonar.ultimo_por_repo(agregado), ctx.sonar_api["medidas"]) if not x.empty]
        ctx.sonar_atual = (sonar.ultimo_por_repo(pd.concat(atual, ignore_index=True)) if atual
                           else pd.DataFrame(columns=["repositorio", "metrica", "valor", "coleta"]))
        if agregado.empty:
            ctx.fontes.append(Fonte("SONAR", "Pipeline (metrics.yml → data/*.json)", "sem dados",
                                    mensagem="Nenhum .json do SonarCloud em Analytics/data/."))
        else:
            n_arq = agregado["arquivo"].nunique()
            ctx.fontes.append(Fonte(
                "SONAR", "Pipeline (metrics.yml → data/*.json)", "parcial" if not erros.empty else "ok",
                agregado["coleta"].max(), (agregado["coleta"].min(), agregado["coleta"].max()), n_arq,
                (f"{erros['repositorio'].nunique()} repositório(s) sem projeto no SonarCloud: "
                 + ", ".join(sorted(sonar.nome_curto(r) for r in erros["repositorio"].unique())))
                if not erros.empty else f"{agregado['repositorio'].nunique()} repositórios"))
        if snap:
            h = ctx.sonar_api["historico"]
            n_erro = len(ctx.sonar_api["erros"])
            ctx.fontes.append(Fonte(
                "SONAR", f"API do SonarCloud (data/sonar/{nome})", "parcial" if n_erro else "ok",
                _para_brt(snap.get("coletado_em")),
                (h["coleta"].min(), h["coleta"].max()) if not h.empty else None,
                len(snap.get("projetos", [])),
                f"{n_erro} projeto(s) com erro" if n_erro else f"{len(snap.get('projetos', []))} projetos"))
        else:
            ctx.fontes.append(Fonte("SONAR", "API do SonarCloud (data/sonar/)", "sem dados",
                                    mensagem="Ainda não coletado: rode python scripts/coleta_sonar.py "
                                             "(ou o workflow coleta-dados.yml)."))
    except Exception as erro:  # noqa: BLE001 — a fonte cai, o dashboard não
        _registrar_erro(ctx, "SONAR", "SonarCloud", erro)

    # GITHUB ───────────────────────────────────────────
    try:
        ctx.gh_issues, ctx.gh_runs = _github(pastas, _marca(PASTAS_PIPELINE, "GitHub_API-*.json"))
        r = ctx.gh_runs
        if r.empty:
            ctx.fontes.append(Fonte("GITHUB", "API do GitHub (GitHub_API-Runs-*.json)", "sem dados",
                                    mensagem="Nenhuma execução de CI coletada."))
        else:
            ctx.fontes.append(Fonte("GITHUB", "API do GitHub (GitHub_API-Runs-*.json)", "ok",
                                    _para_brt(r["atualizado_em"].max()),
                                    (_para_brt(r["criado_em"].min()), _para_brt(r["criado_em"].max())), len(r),
                                    f"{r['repositorio'].nunique()} repositórios"))
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(ctx, "GITHUB", "API do GitHub", erro)

    # PLANILHA ─────────────────────────────────────────
    try:
        (ctx.custos_df, ctx.custo, ctx.plano_bruto, ctx.plano, ctx.horas, ctx.riscos, ctx.monitoramento,
         ctx.decisoes, ctx.origem_planilha, lidos_em) = _planilha(dict(config.PLANILHAS))
        for chave, df in (("custos", ctx.custos_df), ("planejamento", ctx.plano_bruto), ("horas", ctx.horas),
                          ("riscos", ctx.riscos), ("monitoramento", ctx.monitoramento),
                          ("decisoes", ctx.decisoes)):
            origem = ctx.origem_planilha.get(chave, "—")
            quando = lidos_em if not df.empty else None
            status = "ok" if not df.empty else ("erro" if "não respondeu" in origem else "sem dados")
            ctx.fontes.append(Fonte("PLANILHA", f"Aba {planilha.ABAS.get(chave, ('', chave))[1]}", status, quando,
                                    None, len(df), origem.replace("**", "")))
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(ctx, "PLANILHA", "Planilha do time", erro)
    ctx.parametros = planilha.carregar_parametros()

    # ZENHUB ───────────────────────────────────────────
    try:
        ctx.zh_regras = velocity.Regras.dos_parametros(ctx.parametros)
        snap, nome, linhas = _zenhub(str(zh_coleta.PASTA), _marca([zh_coleta.PASTA]))
        ctx.zh_snap, ctx.zh_arquivo = snap, nome
        if not snap:
            ctx.fontes.append(Fonte("ZENHUB", "API GraphQL do Zenhub (data/zenhub/velocity/)", "sem dados",
                                    mensagem="Nenhum snapshot: rode python scripts/coleta_velocity.py."))
        else:
            ctx.zh_sprints = velocity.calculate_velocity(snap, ctx.zh_regras, ctx.agora_utc, linhas,
                                                         incluir_futuras=True)
            ctx.zh_issues, ctx.zh_backlog_completo = agile.universo_issues(snap)
            s = ctx.zh_sprints
            periodo = (_para_brt(s["start_date"].min()), _para_brt(s["end_date"].max())) if not s.empty else None
            avisos = snap.get("avisos") or []
            msg = f"{len(s)} sprints, {len(ctx.zh_issues)} issues"
            if not ctx.zh_backlog_completo:
                msg += " · backlog completo não coletado (só issues que passaram por sprints)"
            if avisos:
                msg += f" · {len(avisos)} aviso(s) na coleta"
            ctx.fontes.append(Fonte("ZENHUB", f"API GraphQL do Zenhub ({nome})",
                                    "ok" if ctx.zh_backlog_completo and not avisos else "parcial",
                                    _para_brt(snap.get("coletado_em")), periodo, len(ctx.zh_issues), msg))
            ctx.calendario = pd.DataFrame({
                "sprint": s["sprint_label"], "nome": s["sprint_name"], "release": s["release_name"],
                "status": s["status"], "inicio": evm._data_local(s["start_date"]),
                "fim": evm._data_local(s["end_date"])}) if not s.empty else pd.DataFrame()
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(ctx, "ZENHUB", "API GraphQL do Zenhub", erro)

    # CALCULADO: AgileEVM (pontos do Zenhub + custos da planilha) ─────────
    try:
        if ctx.zh_snap and not ctx.zh_sprints.empty:
            ctx.evm = evm.agile_evm(ctx.zh_sprints, ctx.zh_snap.get("issues", {}), ctx.plano, ctx.horas,
                                    ctx.custo.get("custo_hora"))
            ctx.evm_sumario = evm.sumario(ctx.evm)
    except Exception as erro:  # noqa: BLE001
        _registrar_erro(ctx, "CALCULADO", "AgileEVM", erro)
    return ctx
