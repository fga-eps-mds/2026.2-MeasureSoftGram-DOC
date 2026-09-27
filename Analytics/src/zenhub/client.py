"""Camada de comunicação com a API GraphQL pública do Zenhub.

Só este módulo fala com a rede. Ele não sabe nada de velocity nem de Streamlit:
recebe e devolve nós GraphQL crus (dicts), já paginados e sem duplicatas.

Tratamentos (https://developers.zenhub.com/graphql-api-docs/):

* autenticação: ``Authorization: Bearer <ZENHUB_API_KEY>``; 401/403 viram
  :class:`ZenhubAuthError` na hora, sem nova tentativa;
* rate limit: 90 s de processamento por minuto por chave e 30 requisições
  simultâneas. HTTP 429 ou erro GraphQL de limite -> espera (``Retry-After`` ou
  backoff exponencial) e tenta de novo; o cliente faz uma requisição por vez;
* complexidade: máximo de 200 pontos por query. Se o Zenhub recusar por
  complexidade, a página é reduzida pela metade e a mesma página é refeita;
* timeout, erro de conexão e 5xx: backoff exponencial até ``max_tentativas``;
* paginação Relay: segue ``pageInfo.endCursor`` enquanto ``hasNextPage``;
* duplicatas: nós repetidos entre páginas (mesmo ``id``) são descartados.

A chave nunca é impressa: ``repr`` e as mensagens de erro a mascaram.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from src.zenhub import queries

API_URL = "https://api.zenhub.com/public/graphql"
WORKSPACE_PADRAO = "6a8326e265e211000ef9379a"  # workspace MeasureSoftGram 2026.2 (não é segredo)

# Tamanhos de página iniciais, calculados para ficar abaixo de 200 pontos de
# complexidade (ver src/zenhub/queries.py). O cliente reduz se precisar.
PAGINA = {"sprints": 15, "issues": 8, "scope": 18, "releases": 20, "release_issues": 100}


class ZenhubError(RuntimeError):
    """Falha ao consultar o Zenhub."""


class ZenhubAuthError(ZenhubError):
    """Chave ausente, inválida ou sem acesso ao workspace."""


class ZenhubRateLimitError(ZenhubError):
    """Limite de uso esgotado mesmo depois das novas tentativas."""


class ZenhubUnavailableError(ZenhubError):
    """Timeout, erro de rede ou 5xx persistente."""


class _Complexidade(ZenhubError):
    """Query acima do limite de complexidade (tratada dentro da paginação)."""


@dataclass
class Resposta:
    status: int
    headers: dict
    corpo: Any  # JSON decodificado, ou texto quando não é JSON


Transporte = Callable[[str, dict, dict, float], Resposta]


def _transporte_requests(url: str, corpo: dict, headers: dict, timeout: float) -> Resposta:
    """Transporte padrão. Importa requests aqui para o módulo carregar sem ele."""
    import requests

    sessao = requests.Session()
    # ZENHUB_IGNORAR_PROXY=1 ignora o proxy do sistema (no Windows ele costuma derrubar o TLS).
    sessao.trust_env = os.environ.get("ZENHUB_IGNORAR_PROXY", "").lower() not in {"1", "true", "sim"}
    try:
        r = sessao.post(url, json=corpo, headers=headers, timeout=timeout)
    except requests.Timeout as erro:
        raise TimeoutError(str(erro)) from None
    except requests.ConnectionError as erro:
        raise ConnectionError(str(erro)) from None
    try:
        dado = r.json()
    except ValueError:
        dado = r.text
    return Resposta(r.status_code, {k.lower(): v for k, v in r.headers.items()}, dado)


def carregar_env(caminho) -> None:
    """Lê um .env simples (CHAVE=valor) sem sobrescrever o ambiente."""
    from pathlib import Path

    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def chave_do_ambiente() -> str | None:
    """ZENHUB_API_KEY (nome oficial) ou ZENHUB_TOKEN (nome antigo do .env)."""
    return os.environ.get("ZENHUB_API_KEY") or os.environ.get("ZENHUB_TOKEN") or None


def workspace_do_ambiente() -> str:
    return os.environ.get("ZENHUB_WORKSPACE_ID") or os.environ.get("ZENHUB_WORKSPACE") or WORKSPACE_PADRAO


@dataclass
class ZenhubClient:
    api_key: str = field(repr=False)
    workspace_id: str = WORKSPACE_PADRAO
    transporte: Transporte = _transporte_requests
    timeout: float = 30.0
    max_tentativas: int = 5
    espera_base: float = 2.0
    dormir: Callable[[float], None] = time.sleep
    url: str = API_URL
    requisicoes: int = 0  # contador, para o log de coleta

    def __post_init__(self):
        if not self.api_key:
            raise ZenhubAuthError("ZENHUB_API_KEY não definida. Coloque a chave no Analytics/.env "
                                  "(Zenhub > Settings > API > Generate new token).")

    @classmethod
    def do_ambiente(cls, **kw) -> "ZenhubClient":
        return cls(api_key=chave_do_ambiente() or "", workspace_id=workspace_do_ambiente(), **kw)

    def __repr__(self) -> str:  # nunca expõe a chave
        return f"ZenhubClient(workspace_id={self.workspace_id!r}, api_key='***')"

    # ───────────────────────── núcleo ─────────────────────────

    def _espera(self, tentativa: int, retry_after=None) -> float:
        if retry_after:
            try:
                return max(float(retry_after), 0.5)
            except (TypeError, ValueError):
                pass
        return self.espera_base * (2 ** tentativa) + random.uniform(0, 0.5)

    def executar(self, query: str, variaveis: dict) -> dict:
        """POST de uma query; devolve ``data``. Refaz em timeout, 5xx e rate limit."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        ultimo = "sem resposta"
        for tentativa in range(self.max_tentativas):
            self.requisicoes += 1
            try:
                r = self.transporte(self.url, {"query": query, "variables": variaveis}, headers, self.timeout)
            except (TimeoutError, ConnectionError, OSError) as erro:
                ultimo = f"{erro.__class__.__name__}"
                self.dormir(self._espera(tentativa))
                continue

            if r.status in (401, 403):
                raise ZenhubAuthError(f"O Zenhub recusou a chave (HTTP {r.status}). Gere uma nova em "
                                      "Zenhub > Settings > API e atualize ZENHUB_API_KEY.")
            if r.status == 429:
                ultimo = "HTTP 429 (rate limit)"
                self.dormir(self._espera(tentativa, r.headers.get("retry-after")))
                continue
            if r.status >= 500:
                ultimo = f"HTTP {r.status}"
                self.dormir(self._espera(tentativa))
                continue
            if not isinstance(r.corpo, dict):
                raise ZenhubError(f"Resposta inesperada do Zenhub (HTTP {r.status}).")

            erros = r.corpo.get("errors") or []
            if erros:
                texto = "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in erros)
                baixo = texto.lower()
                if "complexity" in baixo or "complexidade" in baixo:
                    raise _Complexidade(texto)
                if "rate limit" in baixo or "throttl" in baixo or "too many" in baixo:
                    ultimo = "rate limit (GraphQL)"
                    self.dormir(self._espera(tentativa, r.headers.get("retry-after")))
                    continue
                if "unauthor" in baixo or "access denied" in baixo:
                    raise ZenhubAuthError(f"O Zenhub recusou o acesso: {texto}")
                if r.corpo.get("data") is None:
                    raise ZenhubError(f"Erro GraphQL: {texto}")
            if r.status >= 400:
                raise ZenhubError(f"HTTP {r.status} do Zenhub.")
            return r.corpo.get("data") or {}

        if "rate limit" in ultimo or "429" in ultimo:
            raise ZenhubRateLimitError(f"Limite de uso do Zenhub esgotado ({ultimo}). Tente em alguns minutos.")
        raise ZenhubUnavailableError(f"Zenhub indisponível depois de {self.max_tentativas} tentativas ({ultimo}).")

    def paginar(self, query: str, variaveis: dict, caminho: list[str], pagina: int) -> tuple[list[dict], dict]:
        """Percorre uma conexão Relay inteira.

        ``caminho`` leva de ``data`` até a conexão (ex.: ``["workspace", "sprints"]``).
        Devolve (nós sem duplicata, extras da conexão como ``totalCount``).
        """
        nos: list[dict] = []
        vistos: set = set()
        depois = None
        extras: dict = {}
        tamanho = pagina
        while True:
            try:
                data = self.executar(query, {**variaveis, "first": tamanho, "after": depois})
            except _Complexidade:
                if tamanho <= 1:
                    raise ZenhubError("Query acima do limite de complexidade do Zenhub mesmo com 1 item por página.")
                tamanho = max(1, tamanho // 2)
                continue
            conexao = data
            for chave in caminho:
                conexao = (conexao or {}).get(chave)
            if conexao is None:
                break  # objeto inexistente (id errado ou sem acesso): lista vazia
            for k, v in conexao.items():
                if k not in ("nodes", "pageInfo", "edges"):
                    extras[k] = v
            for no in conexao.get("nodes") or []:
                if not isinstance(no, dict):
                    continue
                chave_no = no.get("id") or repr(sorted(no.items(), key=str))
                if chave_no in vistos:
                    continue
                vistos.add(chave_no)
                nos.append(no)
            info = conexao.get("pageInfo") or {}
            if not info.get("hasNextPage") or not info.get("endCursor") or info.get("endCursor") == depois:
                break
            depois = info["endCursor"]
        return nos, extras

    # ───────────────────────── recursos ─────────────────────────

    def get_sprints(self) -> list[dict]:
        nos, _ = self.paginar(queries.SPRINTS, {"workspaceId": self.workspace_id},
                              ["workspace", "sprints"], PAGINA["sprints"])
        return nos

    def get_sprint_issues(self, sprint_id: str) -> list[dict]:
        nos, _ = self.paginar(queries.SPRINT_ISSUES, {"sprintId": sprint_id, "workspaceId": self.workspace_id},
                              ["node", "issues"], PAGINA["issues"])
        return nos

    def get_sprint_scope_changes(self, sprint_id: str) -> tuple[list[dict], int | None]:
        """Eventos ISSUE_ADDED/ISSUE_REMOVED da sprint (sem id próprio: não deduplica por id)."""
        nos, extras = self.paginar(queries.SPRINT_SCOPE_CHANGES, {"sprintId": sprint_id},
                                   ["node", "scopeChange"], PAGINA["scope"])
        return nos, extras.get("totalCount")

    def get_issue(self, issue_id: str) -> dict | None:
        data = self.executar(queries.ISSUE, {"issueId": issue_id, "workspaceId": self.workspace_id})
        no = data.get("node")
        return no if isinstance(no, dict) and no.get("id") else None

    def get_releases(self) -> list[dict]:
        nos, _ = self.paginar(queries.RELEASES, {"workspaceId": self.workspace_id},
                              ["workspace", "releases"], PAGINA["releases"])
        return nos

    def get_release_issue_ids(self, release_id: str) -> list[str]:
        nos, _ = self.paginar(queries.RELEASE_ISSUES, {"releaseId": release_id},
                              ["node", "issues"], PAGINA["release_issues"])
        return [n["id"] for n in nos if n.get("id")]
