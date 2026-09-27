"""Coleta sprints, issues, histórico de escopo e releases do Zenhub para a velocity.

Uso (na pasta Analytics/):

    # Analytics/.env  ->  ZENHUB_API_KEY=...   (opcional: ZENHUB_WORKSPACE_ID=...)
    python scripts/coleta_velocity.py

Grava ``data/zenhub/velocity/zenhub-velocity-<data>.json`` e atualiza
``data/zenhub/velocity/linhas-de-base.json`` (planejado congelado de cada sprint
que já passou da janela de planning). No GitHub, o workflow
``.github/workflows/zenhub-velocity.yml`` roda este script com o secret
``ZENHUB_API_KEY``.

A chave nunca é impressa.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import gestao  # noqa: E402
from src.velocity import Regras, congelar_linhas_de_base  # noqa: E402
from src.zenhub import coleta  # noqa: E402
from src.zenhub.client import ZenhubAuthError, ZenhubClient, ZenhubError, carregar_env  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)  # flush: o Git Bash do Windows segura a saída sem isso


def executar(pasta: Path = coleta.PASTA, log=_log) -> Path:
    """Coleta completa. Usada pelo script e pelo botão "Atualizar dados" do dashboard."""
    carregar_env(RAIZ / ".env")
    cliente = ZenhubClient.do_ambiente()
    agora = datetime.now(timezone.utc)
    snapshot = coleta.coletar(cliente, agora, log=log)
    destino = coleta.salvar_snapshot(snapshot, pasta)
    regras = Regras.dos_parametros(gestao.carregar_parametros(RAIZ / "planilhas"))
    linhas, congeladas = congelar_linhas_de_base(snapshot, coleta.ler_linhas_de_base(pasta), agora, regras)
    coleta.gravar_linhas_de_base(linhas, pasta)
    log(f"Gravado {destino.name} ({cliente.requisicoes} requisições)")
    if congeladas:
        log("Linha de base congelada agora: " + ", ".join(congeladas))
    for aviso in snapshot["avisos"]:
        log(f"Aviso: {aviso}")
    return destino


def main() -> int:
    try:
        executar()
    except ZenhubAuthError as erro:
        print(f"Erro de autenticação: {erro}", file=sys.stderr)
        return 2
    except ZenhubError as erro:
        print(f"Erro ao consultar o Zenhub: {erro}", file=sys.stderr)
        print("Se for erro de rede/TLS, tente: ZENHUB_IGNORAR_PROXY=1 python scripts/coleta_velocity.py",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
