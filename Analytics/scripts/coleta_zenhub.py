"""Coleta as sprints do Zenhub e grava um snapshot em data/zenhub/.

Uso:
    # copie .env.example para .env e preencha o ZENHUB_TOKEN
    python scripts/coleta_zenhub.py

Grava ``data/zenhub/zenhub-sprints-AAAA-MM-DD.json`` no mesmo formato que
``src/gestao.py`` lê. Cada execução é um novo arquivo: o histórico de snapshots
é o que permite reconstruir o estado do quadro em cada data (reprodutibilidade).
Rodar ao fim de cada sprint, antes da review, ou agendar no GitHub Actions.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests

API = "https://api.zenhub.com/public/graphql"
WORKSPACE_PADRAO = "6a8326e265e211000ef9379a"
def workspace() -> str:
    return os.environ.get("ZENHUB_WORKSPACE", WORKSPACE_PADRAO)


SAIDA = Path(__file__).resolve().parents[1] / "data" / "zenhub"

CONSULTA = """
query($ws: ID!, $depois: String) {
  workspace(id: $ws) {
    sprints(first: 50) {
      nodes {
        id name startAt endAt
        issues(first: 100, after: $depois) {
          pageInfo { hasNextPage endCursor }
          nodes {
            number title state htmlUrl
            repository { name }
            issueType { name }
            estimate { value }
            parentIssue { number repository { name } }
            pipelineIssue(workspaceId: $ws) { pipeline { name } }
          }
        }
      }
    }
  }
}
"""


def _post(token: str, corpo: dict, ignorar_proxy: bool) -> requests.Response:
    sessao = requests.Session()
    # trust_env=False ignora HTTPS_PROXY e o proxy do sistema do Windows, que o
    # requests lê do registro e que costuma derrubar o handshake TLS.
    sessao.trust_env = not ignorar_proxy
    return sessao.post(API, json=corpo, headers={"Authorization": f"Bearer {token}"},
                       timeout=60)


def consultar(token: str, depois: str | None = None) -> dict:
    corpo = {"query": CONSULTA, "variables": {"ws": workspace(), "depois": depois}}
    ignorar = os.environ.get("ZENHUB_IGNORAR_PROXY", "").lower() in {"1", "true", "sim"}
    try:
        r = _post(token, corpo, ignorar)
    except requests.exceptions.SSLError:
        if ignorar:
            raise
        print("Falha de TLS pelo proxy do sistema; tentando conexão direta...", file=sys.stderr)
        r = _post(token, corpo, ignorar_proxy=True)
    if r.status_code == 401:
        raise SystemExit("Token recusado (401). Gere um novo em Zenhub > Settings > API e atualize o .env.")
    r.raise_for_status()
    corpo = r.json()
    if corpo.get("errors"):
        raise RuntimeError(corpo["errors"])
    return corpo["data"]["workspace"]["sprints"]["nodes"]


def enxugar(i: dict) -> dict:
    return {
        "numero": i["number"], "repositorio": i["repository"]["name"], "titulo": i["title"],
        "tipo": (i.get("issueType") or {}).get("name"),
        "estimativa": (i.get("estimate") or {}).get("value"),
        "estado": i["state"],
        "pipeline": ((i.get("pipelineIssue") or {}).get("pipeline") or {}).get("name"),
        "pai": (i.get("parentIssue") or {}).get("number"),
        "pai_repositorio": ((i.get("parentIssue") or {}).get("repository") or {}).get("name"),
        "url": i["htmlUrl"],
    }


def carregar_env() -> None:
    """Lê Analytics/.env (CHAVE=valor), sem dependência extra."""
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def main() -> int:
    carregar_env()
    token = os.environ.get("ZENHUB_TOKEN")
    if not token:
        print("Defina ZENHUB_TOKEN.", file=sys.stderr)
        return 1
    sprints = []
    for s in consultar(token):
        issues = [enxugar(i) for i in s["issues"]["nodes"]]
        # Sprints com mais de 100 issues: o Zenhub pagina por sprint.
        # Quase nunca acontece; avisamos em vez de truncar em silêncio.
        completo = not s["issues"]["pageInfo"]["hasNextPage"]
        if not completo:
            print(f"Aviso: {s['name']} tem mais de 100 issues; coleta parcial.", file=sys.stderr)
        sprints.append({"id": s["id"], "nome": s["name"], "inicio": s["startAt"],
                        "fim": s["endAt"], "completo": completo,
                        "total_issues": len(issues), "issues": issues})
    sprints.sort(key=lambda s: s["inicio"])
    agora = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"zenhub-sprints-{agora:%Y-%m-%d}.json"
    destino.write_text(json.dumps({
        "fonte": f"Zenhub GraphQL, workspace {workspace()}",
        "coletado_em": agora.isoformat(timespec="seconds"),
        "sprints": sprints,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Gravado {destino} ({len(sprints)} sprints)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
