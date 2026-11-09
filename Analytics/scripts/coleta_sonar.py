"""Coleta as métricas de qualidade pela API do SonarCloud.

Uso (na pasta Analytics/):

    python scripts/coleta_sonar.py                          # coleta todos os projetos
    python scripts/coleta_sonar.py --repos Service          # coleta apenas o Service
    python scripts/coleta_sonar.py --repos "Service, Front"  # coleta apenas os indicados

Grava ``data/sonar/sonar-AAAA-MM-DDTHHMM.json`` com as métricas atuais, por componente,
histórico, Quality Gate e issues abertas. Se rodado para um subconjunto de repositórios,
mescla com o snapshot anterior para não perder os dados dos demais.

O token nunca é impresso.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from scripts.saneamento_dados import mesmo_payload  # noqa: E402
from scripts.verificar_novos_prs import normalizar_repositorios  # noqa: E402
from src.data import sonar_api  # noqa: E402
from src.data.sonar import PASTA_API, ultimo_snapshot  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402


def filtrar_projetos_sonar(repos: list[str] | str | None) -> list[str]:
    """Filtra config.SONAR_PROJETOS com base nos repositórios desejados."""
    if not repos:
        return list(config.SONAR_PROJETOS)

    repos_norm = normalizar_repositorios(repos)
    filtrados = []
    for proj in config.SONAR_PROJETOS:
        nome_repo = proj.split("_", 1)[1] if "_" in proj else proj
        if nome_repo in repos_norm:
            filtrados.append(proj)
    return filtrados if filtrados else list(config.SONAR_PROJETOS)


def executar(pasta: Path = PASTA_API, repos: list[str] | str | None = None, log=print) -> Path:
    carregar_env(RAIZ / ".env")
    cliente = sonar_api.SonarClient.do_ambiente(url=config.SONAR_URL, organizacao=config.SONAR_ORGANIZACAO)

    projetos_alvo = filtrar_projetos_sonar(repos)
    log(f"Projetos SonarCloud a coletar ({len(projetos_alvo)}): {', '.join(projetos_alvo)}")

    snap = sonar_api.coletar(cliente, projetos_alvo, config.SONAR_BRANCH, config.SONAR_BUSCA, log=log)

    snap_antigo, nome_antigo = ultimo_snapshot(pasta)

    # Se coletamos um subconjunto, mesclamos com o último snapshot para manter os demais projetos
    todos_projetos = set(config.SONAR_PROJETOS)
    if set(projetos_alvo) < todos_projetos:
        if snap_antigo and "projetos" in snap_antigo:
            keys_novas = {p["key"] for p in snap["projetos"]}
            projetos_preservados = [p for p in snap_antigo["projetos"] if p.get("key") not in keys_novas]
            snap["projetos"].extend(projetos_preservados)
            snap["projetos"].sort(key=lambda p: p.get("key", ""))
            log(f"Mesclados {len(projetos_preservados)} projetos do snapshot anterior ({nome_antigo})")

    if snap_antigo and nome_antigo and mesmo_payload(snap, snap_antigo):
        log(f"Snapshot SonarCloud idêntico ao anterior ({nome_antigo}); gravação ignorada ({cliente.requisicoes} requisições)")
        return pasta / nome_antigo

    pasta.mkdir(parents=True, exist_ok=True)
    quando = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    destino = pasta / f"sonar-{quando}.json"
    destino.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Gravado {destino.name} ({cliente.requisicoes} requisições)")
    for aviso in snap.get("avisos", []):
        log(f"Aviso: {aviso}")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta métricas da API do SonarCloud.")
    parser.add_argument("--repos", type=str, default="", help="Repositórios a coletar (ou 'todos')")
    args = parser.parse_args()

    try:
        executar(repos=args.repos)
    except sonar_api.SonarAuthError as erro:
        print(f"Erro de autenticação: {erro}", file=sys.stderr)
        return 2
    except sonar_api.SonarError as erro:
        print(f"Erro ao consultar o SonarCloud: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
