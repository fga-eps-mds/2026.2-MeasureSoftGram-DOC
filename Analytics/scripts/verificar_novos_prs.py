"""Verifica se novos Pull Requests foram adicionados (mergeados) na branch develop.

Uso:
    python scripts/verificar_novos_prs.py                    # verifica todos os repositórios
    python scripts/verificar_novos_prs.py --repos Service   # verifica apenas o Service
    python scripts/verificar_novos_prs.py --force            # força resultado positivo (para workflow_dispatch)
    python scripts/verificar_novos_prs.py --dry-run          # simula sem gravar cursor em disco

Grava o estado em data/.last_pr_state.json e emite variáveis para o $GITHUB_OUTPUT:
    houve_novo_pr=true|false
    repos_alvo=repo1,repo2,...
    resumo_prs=texto de resumo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402

API = "https://api.github.com"
ARQUIVO_ESTADO = RAIZ / "data" / ".last_pr_state.json"


def normalizar_repositorios(entrada: str | list[str] | None) -> list[str]:
    """Converte entrada do usuário (nomes curtos ou completos) para a lista de repositórios do config.GITHUB_REPOS."""
    if not entrada:
        return list(config.GITHUB_REPOS)

    if isinstance(entrada, str):
        if entrada.strip().lower() in ("todos", "all", "*", ""):
            return list(config.GITHUB_REPOS)
        partes = [p.strip() for p in entrada.replace(";", ",").split(",") if p.strip()]
    else:
        partes = [str(p).strip() for p in entrada if str(p).strip()]

    todos = config.GITHUB_REPOS
    selecionados: list[str] = []

    for item in partes:
        item_limpo = item
        if item_limpo.startswith(config.GITHUB_ORG + "_"):
            item_limpo = item_limpo[len(config.GITHUB_ORG) + 1:]
        if item_limpo.startswith(config.GITHUB_ORG + "/"):
            item_limpo = item_limpo[len(config.GITHUB_ORG) + 1:]

        # Busca exata
        if item_limpo in todos:
            if item_limpo not in selecionados:
                selecionados.append(item_limpo)
            continue

        # Busca com prefixo padrão do projeto
        com_prefixo = f"{config.PREFIXO_REPOS_PROJETO}{item_limpo}"
        if com_prefixo in todos:
            if com_prefixo not in selecionados:
                selecionados.append(com_prefixo)
            continue

        # Busca insensível a maiúsculas/minúsculas
        match = next((r for r in todos if r.lower() in (item_limpo.lower(), com_prefixo.lower())), None)
        if match and match not in selecionados:
            selecionados.append(match)

    return selecionados if selecionados else list(config.GITHUB_REPOS)


def carregar_estado(caminho: Path = ARQUIVO_ESTADO) -> dict:
    if caminho.exists():
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def salvar_estado(estado: dict, caminho: Path = ARQUIVO_ESTADO) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def consultar_prs_develop(sessao, org: str, repo: str, branch: str = "develop") -> list[dict]:
    """Consulta os PRs fechados mais recentes direcionados à branch especificada."""
    url = f"{API}/repos/{org}/{repo}/pulls"
    params = {
        "state": "closed",
        "base": branch,
        "sort": "updated",
        "direction": "desc",
        "per_page": 10,
    }
    r = sessao.get(url, params=params, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    dados = r.json() or []
    # Apenas PRs efetivamente mergeados
    return [p for p in dados if p.get("merged_at")]


def verificar(
    repos: list[str] | None = None,
    force: bool = False,
    init: bool = False,
    dry_run: bool = False,
    log=print,
    caminho_estado: Path = ARQUIVO_ESTADO,
) -> dict:
    """Verifica se há novos PRs mergeados na branch develop.

    Retorna um dicionário com:
        houve_novo_pr: bool
        repos_alvo: list[str]
        novos_prs: dict[str, list[dict]]
        resumo: str
    """
    import requests

    carregar_env(RAIZ / ".env")
    token = os.environ.get("GITHUB_TOKEN")

    sessao = requests.Session()
    sessao.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    if token:
        sessao.headers["Authorization"] = f"Bearer {token}"

    repos_alvo = normalizar_repositorios(repos)
    log(f"Repositórios avaliados ({len(repos_alvo)}): {', '.join(repos_alvo)}")

    estado_anterior = carregar_estado(caminho_estado)
    novo_estado = dict(estado_anterior)

    branch_alvo = getattr(config, "SONAR_BRANCH", "develop")
    novos_encontrados: dict[str, list[dict]] = {}
    mensagens_resumo: list[str] = []

    for repo in repos_alvo:
        try:
            prs_mergeados = consultar_prs_develop(sessao, config.GITHUB_ORG, repo, branch=branch_alvo)
        except Exception as erro:  # noqa: BLE001
            log(f"[{repo}] Aviso: falha ao consultar PRs ({erro.__class__.__name__}: {erro})")
            continue

        if not prs_mergeados:
            continue

        ultimo_pr = prs_mergeados[0]
        pr_id = int(ultimo_pr["number"])
        merge_at = ultimo_pr["merged_at"]
        titulo = ultimo_pr.get("title", "")
        autor = (ultimo_pr.get("user") or {}).get("login", "")

        cursor_repo = estado_anterior.get(repo, {})
        ultimo_conhecido_merge = cursor_repo.get("last_merged_at")

        # Se for inicialização, apenas registra o estado mais recente sem marcar novo
        if init:
            novo_estado[repo] = {
                "number": pr_id,
                "last_merged_at": merge_at,
                "title": titulo,
                "author": autor,
            }
            continue

        # Se o repositório ainda não tinha cursor ou o merge_at é mais recente
        if not ultimo_conhecido_merge:
            # Primeiro registro do repositório: registra o PR atual
            log(f"[{repo}] Inicializando cursor com PR #{pr_id} ({merge_at})")
            novo_estado[repo] = {
                "number": pr_id,
                "last_merged_at": merge_at,
                "title": titulo,
                "author": autor,
            }
            novos_encontrados[repo] = [{
                "number": pr_id,
                "title": titulo,
                "merged_at": merge_at,
                "author": autor,
            }]
            mensagens_resumo.append(f"{repo}: PR #{pr_id} ('{titulo}') por @{autor}")
        elif merge_at > ultimo_conhecido_merge:
            log(f"[{repo}] NOVO PR detectado na {branch_alvo}: #{pr_id} - '{titulo}' por @{autor} ({merge_at})")
            novo_estado[repo] = {
                "number": pr_id,
                "last_merged_at": merge_at,
                "title": titulo,
                "author": autor,
            }
            novos_encontrados[repo] = [{
                "number": pr_id,
                "title": titulo,
                "merged_at": merge_at,
                "author": autor,
            }]
            mensagens_resumo.append(f"{repo}: PR #{pr_id} ('{titulo}') por @{autor}")
        else:
            log(f"[{repo}] Sem novos PRs na {branch_alvo} (último: #{cursor_repo.get('number')} em {ultimo_conhecido_merge})")

    houve_novo_pr = bool(novos_encontrados) or force

    if force:
        log("Forçar coleta ativo: execução do SonarCloud autorizada.")
        resumo = f"Coleta forçada manualmente para: {', '.join(repos_alvo)}"
    elif novos_encontrados:
        resumo = "; ".join(mensagens_resumo)
    else:
        resumo = f"Nenhum novo PR na branch {branch_alvo} nos repositórios avaliados."

    if not dry_run and (novos_encontrados or init):
        salvar_estado(novo_estado, caminho_estado)
        log(f"Estado salvo em {caminho_estado.name}")

    resultado = {
        "houve_novo_pr": houve_novo_pr,
        "repos_alvo": repos_alvo,
        "novos_prs": novos_encontrados,
        "resumo": resumo,
    }

    # Integração com GitHub Actions Step Outputs
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output and Path(github_output).exists():
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"houve_novo_pr={'true' if houve_novo_pr else 'false'}\n")
            f.write(f"repos_alvo={','.join(repos_alvo)}\n")
            f.write(f"resumo_prs={resumo}\n")

    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica se há novos PRs mergeados na branch develop.")
    parser.add_argument("--repos", type=str, default="", help="Lista de repositórios (ou 'todos')")
    parser.add_argument("--force", action="store_true", help="Força resultado positivo")
    parser.add_argument("--init", action="store_true", help="Apenas inicializa o cursor sem disparar coleta")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem salvar o arquivo de estado")
    args = parser.parse_args()

    res = verificar(repos=args.repos, force=args.force, init=args.init, dry_run=args.dry_run)
    print(f"\nResultado: houve_novo_pr={res['houve_novo_pr']}")
    print(f"Resumo: {res['resumo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
