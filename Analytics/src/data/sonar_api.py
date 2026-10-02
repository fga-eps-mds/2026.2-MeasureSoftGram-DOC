"""Cliente da Web API do SonarCloud — usado só pela coleta (``scripts/coleta_sonar.py``).

O dashboard nunca chama a API durante a renderização: lê o snapshot que a
coleta grava em ``data/sonar/``. Assim a página abre rápido, funciona no GitHub
Pages (onde não há token nem rede para o Sonar) e todo número é reprodutível.

Endpoints (https://sonarcloud.io/web_api), todos de leitura:

* ``api/measures/component``      valores atuais das métricas
* ``api/measures/component_tree`` métricas por arquivo/suíte (cobertura por componente e modelo DA-R2)
* ``api/measures/search_history`` série histórica de cada métrica
* ``api/qualitygates/project_status`` situação do Quality Gate e condições
* ``api/issues/search`` (``ps=1`` + ``facets``) problemas abertos por severidade e tipo
* ``api/components/search``       descoberta dos projetos da organização

Projetos públicos dispensam token. ``SONAR_TOKEN`` (opcional, no ``.env`` ou no
secret do GitHub) é enviado como Bearer e nunca aparece em log.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

METRICAS_ATUAIS = [
    "bugs", "vulnerabilities", "code_smells", "security_hotspots", "sqale_index", "sqale_debt_ratio",
    "coverage", "duplicated_lines", "duplicated_lines_density", "ncloc", "reliability_rating",
    "security_rating", "sqale_rating", "tests", "test_errors", "test_failures", "test_success_density",
    "test_execution_time", "comment_lines_density", "complexity", "files", "functions",
    "alert_status", "ncloc_language_distribution",
]
METRICAS_COMPONENTES = [
    "files", "functions", "complexity", "comment_lines_density", "duplicated_lines_density",
    "coverage", "ncloc", "tests", "test_errors", "test_failures", "test_execution_time",
    "security_rating",
]
METRICAS_HISTORICO = [
    "bugs", "vulnerabilities", "code_smells", "security_hotspots", "sqale_index", "coverage",
    "duplicated_lines_density", "ncloc", "reliability_rating", "security_rating", "sqale_rating", "tests",
]


class SonarError(RuntimeError):
    pass


class SonarAuthError(SonarError):
    pass


@dataclass
class Resposta:
    status: int
    corpo: dict | None


def _transporte_requests(url: str, params: dict, headers: dict, timeout: float) -> Resposta:
    import requests
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    try:
        corpo = r.json()
    except ValueError:
        corpo = None
    return Resposta(r.status_code, corpo)


@dataclass
class SonarClient:
    url: str = "https://sonarcloud.io"
    organizacao: str = "fga-eps-mds"
    token: str | None = field(default=None, repr=False)
    transporte: Callable[[str, dict, dict, float], Resposta] = _transporte_requests
    timeout: float = 30.0
    max_tentativas: int = 4
    dormir: Callable[[float], None] = time.sleep
    requisicoes: int = 0

    @classmethod
    def do_ambiente(cls, **kw) -> "SonarClient":
        return cls(token=os.environ.get("SONAR_TOKEN") or None, **kw)

    def __repr__(self) -> str:  # nunca expõe o token
        return f"SonarClient(url={self.url!r}, organizacao={self.organizacao!r}, token={'***' if self.token else None})"

    def get(self, caminho: str, params: dict) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        ultimo = "sem resposta"
        for tentativa in range(self.max_tentativas):
            self.requisicoes += 1
            try:
                r = self.transporte(f"{self.url}/{caminho}", params, headers, self.timeout)
            except (TimeoutError, ConnectionError, OSError) as erro:
                ultimo = str(erro) or erro.__class__.__name__
                self.dormir(2 ** tentativa)
                continue
            if r.status in (401, 403):
                raise SonarAuthError(f"O SonarCloud recusou o acesso (HTTP {r.status}). Confira o SONAR_TOKEN.")
            if r.status == 429 or r.status >= 500:
                ultimo = f"HTTP {r.status}"
                self.dormir(2 ** tentativa)
                continue
            if r.status >= 400:
                msgs = "; ".join(e.get("msg", "") for e in (r.corpo or {}).get("errors", []) if isinstance(e, dict))
                raise SonarError(msgs or f"HTTP {r.status}")
            return r.corpo or {}
        raise SonarError(f"SonarCloud indisponível depois de {self.max_tentativas} tentativas ({ultimo}).")

    # ───────────────────────── recursos ─────────────────────────

    def descobrir_projetos(self, busca: str) -> list[str]:
        d = self.get("api/components/search", {"organization": self.organizacao, "qualifiers": "TRK",
                                                "q": busca, "ps": 100})
        return sorted(c["key"] for c in d.get("components", []) if c.get("key"))

    def medidas(self, projeto: str, branch: str | None) -> dict:
        p = {"component": projeto, "metricKeys": ",".join(METRICAS_ATUAIS)}
        if branch:
            p["branch"] = branch
        d = self.get("api/measures/component", p)
        comp = d.get("component") or {}
        return {m["metric"]: m.get("value") for m in comp.get("measures", []) if "metric" in m}

    def componentes(self, projeto: str, branch: str | None, max_paginas: int = 10) -> list[dict]:
        """Métricas por arquivo/suíte (api/measures/component_tree) para cobertura por arquivo e modelo DA-R2."""
        itens, pagina = [], 1
        while pagina <= max_paginas:
            p = {"component": projeto, "metricKeys": ",".join(METRICAS_COMPONENTES),
                 "qualifiers": "FIL,UTS", "ps": 500, "p": pagina}
            if branch:
                p["branch"] = branch
            d = self.get("api/measures/component_tree", p)
            lote = d.get("components") or []
            for c in lote:
                med = {m["metric"]: m.get("value") for m in c.get("measures", [])
                       if "metric" in m and m.get("value") is not None}
                if med:
                    itens.append({"path": c.get("path") or c.get("name"),
                                  "qualifier": c.get("qualifier"), "measures": med})
            total = (d.get("paging") or {}).get("total", len(lote))
            if len(lote) < 500 or pagina * 500 >= total:
                break
            pagina += 1
        return itens

    def historico(self, projeto: str, branch: str | None) -> dict:
        p = {"component": projeto, "metrics": ",".join(METRICAS_HISTORICO), "ps": 1000}
        if branch:
            p["branch"] = branch
        d = self.get("api/measures/search_history", p)
        return {m["metric"]: [{"date": h.get("date"), "value": h.get("value")} for h in m.get("history", [])
                              if h.get("value") is not None]
                for m in d.get("measures", []) if "metric" in m}

    def quality_gate(self, projeto: str, branch: str | None) -> dict:
        p = {"projectKey": projeto}
        if branch:
            p["branch"] = branch
        d = self.get("api/qualitygates/project_status", p).get("projectStatus") or {}
        return {"status": d.get("status"),
                "condicoes": [{"metrica": c.get("metricKey"), "status": c.get("status"),
                               "valor": c.get("actualValue"), "limite": c.get("errorThreshold"),
                               "comparador": c.get("comparator")} for c in d.get("conditions", [])]}

    def issues_abertas(self, projeto: str, branch: str | None) -> dict:
        p = {"componentKeys": projeto, "resolved": "false", "ps": 1, "facets": "severities,types",
             "organization": self.organizacao}
        if branch:
            p["branch"] = branch
        d = self.get("api/issues/search", p)
        facetas = {f.get("property"): {v["val"]: v.get("count", 0) for v in f.get("values", [])}
                   for f in d.get("facets", [])}
        return {"total": d.get("total", (d.get("paging") or {}).get("total")),
                "severidades": facetas.get("severities", {}), "tipos": facetas.get("types", {})}


def _linguagens(texto) -> dict:
    """'py=1200;js=300' -> {'py': 1200, 'js': 300}."""
    out = {}
    for parte in str(texto or "").split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return out


def coletar(cliente: SonarClient, projetos: list[str], branch: str | None, busca: str = "",
            agora: datetime | None = None, log=print) -> dict:
    """Snapshot com todos os projetos. Falha de um projeto vira ``erro`` nele, não derruba os outros."""
    agora = agora or datetime.now(timezone.utc)
    avisos: list[str] = []
    if not projetos and busca:
        projetos = cliente.descobrir_projetos(busca)
        log(f"{len(projetos)} projetos encontrados na organização")
    saida = []
    for chave in projetos:
        repo = chave.split("_", 1)[1] if "_" in chave else chave
        registro = {"key": chave, "repositorio": repo, "branch": branch}
        try:
            try:
                medidas = cliente.medidas(chave, branch)
            except SonarError as erro:
                if branch and "branch" in str(erro).lower():
                    # projeto sem análise da branch: usa a branch principal e registra isso
                    avisos.append(f"{repo}: sem análise da branch {branch}; usada a branch principal.")
                    registro["branch"] = None
                    medidas = cliente.medidas(chave, None)
                else:
                    raise
            b = registro["branch"]
            registro["linguagens"] = _linguagens(medidas.pop("ncloc_language_distribution", None))
            status_gate = medidas.pop("alert_status", None)
            registro["medidas"] = medidas
            registro["historico"] = cliente.historico(chave, b)
            registro["quality_gate"] = cliente.quality_gate(chave, b)
            if not registro["quality_gate"].get("status") and status_gate:
                registro["quality_gate"]["status"] = status_gate
            registro["issues"] = cliente.issues_abertas(chave, b)
            registro["componentes"] = cliente.componentes(chave, b)
            log(f"  {repo}: {len(medidas)} métricas, {len(registro['componentes'])} componentes, "
                f"Quality Gate {registro['quality_gate'].get('status')}")
        except SonarAuthError:
            raise
        except SonarError as erro:
            registro["erro"] = str(erro)
            avisos.append(f"{repo}: {erro}")
            log(f"  {repo}: falhou ({erro})")
        saida.append(registro)
    return {"versao": 1, "fonte": f"SonarCloud Web API ({cliente.url})", "organizacao": cliente.organizacao,
            "branch": branch, "coletado_em": agora.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "requisicoes": cliente.requisicoes, "projetos": saida, "avisos": avisos}
