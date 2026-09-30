"""Coleta as métricas de qualidade pela API do SonarCloud.

Uso (na pasta Analytics/):

    python scripts/coleta_sonar.py            # SONAR_TOKEN opcional no .env

Grava ``data/sonar/sonar-AAAA-MM-DDTHHMM.json`` com, para cada projeto de
``config.SONAR_PROJETOS``: métricas atuais (bugs, vulnerabilidades, code smells,
hotspots, dívida técnica, cobertura, duplicação, ratings, testes), métricas por
componente (``api/measures/component_tree`` para cobertura por arquivo e modelo
DA-R2), histórico, Quality Gate e problemas abertos por severidade e tipo. No
GitHub, o workflow ``.github/workflows/coleta-dados.yml`` roda este script a
cada push na main e 3 vezes por dia.

O token nunca é impresso.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from src.data import sonar_api  # noqa: E402
from src.data.sonar import PASTA_API  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402


def executar(pasta: Path = PASTA_API, log=print) -> Path:
    carregar_env(RAIZ / ".env")
    cliente = sonar_api.SonarClient.do_ambiente(url=config.SONAR_URL, organizacao=config.SONAR_ORGANIZACAO)
    snap = sonar_api.coletar(cliente, list(config.SONAR_PROJETOS), config.SONAR_BRANCH, config.SONAR_BUSCA,
                             log=log)
    pasta.mkdir(parents=True, exist_ok=True)
    quando = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    destino = pasta / f"sonar-{quando}.json"
    destino.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Gravado {destino.name} ({cliente.requisicoes} requisições)")
    for aviso in snap["avisos"]:
        log(f"Aviso: {aviso}")
    return destino


def main() -> int:
    try:
        executar()
    except sonar_api.SonarAuthError as erro:
        print(f"Erro de autenticação: {erro}", file=sys.stderr)
        return 2
    except sonar_api.SonarError as erro:
        print(f"Erro ao consultar o SonarCloud: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
