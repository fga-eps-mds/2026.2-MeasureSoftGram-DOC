"""Grava um retrato do SonarCloud para cada release nova dos repositórios do projeto.

Uso (na pasta Analytics/):

    python scripts/coleta_releases.py                    # todos os repositórios
    python scripts/coleta_releases.py --repos Service    # só os indicados

Substitui o que o ``metrics.yml`` de cada repositório fazia na criação de uma tag ``v*``:
guardar as métricas do momento da entrega com o nome da tag.

Como funciona:

1. Lista as releases de cada repositório pela API do GitHub (rascunhos e tags que não começam
   com ``v`` ficam de fora, como no ``metrics.yml``).
2. Compara com ``data/sonar/releases/registro.json``. Release que não está no registro é nova:
   coleta o SonarCloud só daquele projeto (branch ``config.SONAR_BRANCH``) e grava
   ``data/sonar/releases/<Repo>-<tag>.json`` no mesmo formato de ``sonar-*.json``, com um bloco
   ``release`` (tag, data de publicação, link e atraso entre a publicação e a coleta).
3. Se o secret ``RELEASE_ASSETS_TOKEN`` existir, anexa o arquivo nos Assets da release, como o
   ``metrics.yml`` fazia. Sem o token, registra ``sem_token`` e tenta de novo nas próximas coletas.

Primeira vez de um repositório no registro: as releases que já existem entram como ``anterior``
e NÃO são coletadas (os retratos de R1 a R3 já estão em ``data/*.json``; coletar agora gravaria
o código de hoje com o nome de uma tag antiga).

A coleta é diária, então o retrato pode vir horas depois da tag. Para pegar o momento exato,
rode o workflow "Coleta de dados do dashboard" manualmente logo depois de publicar a release.
Os tokens nunca são impressos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from scripts.verificar_novos_prs import normalizar_repositorios  # noqa: E402
from src.data import sonar_api  # noqa: E402
from src.data.sonar import PASTA_API  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
PASTA_RELEASES = PASTA_API / "releases"
ARQUIVO_REGISTRO = "registro.json"


# ───────────────────────── regras (funções puras) ─────────────────────────

def release_valida(rel: dict) -> bool:
    """Mesma regra do metrics.yml: só tags ``v*`` e nada de rascunho."""
    return not rel.get("draft") and str(rel.get("tag_name") or "").startswith("v")


def releases_novas(releases: list[dict], registradas: dict) -> list[dict]:
    """Releases válidas que ainda não estão no registro, da mais antiga para a mais nova."""
    novas = [r for r in releases if release_valida(r) and r["tag_name"] not in registradas]
    return sorted(novas, key=lambda r: r.get("published_at") or r.get("created_at") or "")


def nome_arquivo(repo: str, tag: str) -> str:
    curto = repo.removeprefix(config.PREFIXO_REPOS_PROJETO) if config.PREFIXO_REPOS_PROJETO else repo
    seguro = "".join(c if c.isalnum() or c in "._-" else "_" for c in tag)
    return f"{curto}-{seguro}.json"


def atraso_horas(publicada_em: str | None, coletado_em: datetime) -> float | None:
    if not publicada_em:
        return None
    publicada = datetime.fromisoformat(publicada_em.replace("Z", "+00:00"))
    return round((coletado_em - publicada).total_seconds() / 3600, 1)


def projeto_sonar(repo: str) -> str | None:
    chave = f"{config.SONAR_ORGANIZACAO}_{repo}"
    return chave if chave in config.SONAR_PROJETOS else None


# ───────────────────────── registro ─────────────────────────

def carregar_registro(pasta: Path) -> dict:
    arq = pasta / ARQUIVO_REGISTRO
    if not arq.exists():
        return {"repositorios": {}}
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"repositorios": {}}
    dados.setdefault("repositorios", {})
    return dados


def salvar_registro(pasta: Path, registro: dict) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ARQUIVO_REGISTRO).write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")


# ───────────────────────── GitHub ─────────────────────────

def _sessao(token: str | None):
    import requests
    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def listar_releases(sessao, repo: str) -> list[dict]:
    r = sessao.get(f"{API}/repos/{config.GITHUB_ORG}/{repo}/releases", params={"per_page": 100}, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json() or []


def anexar_asset(sessao, repo: str, release: dict, arquivo: Path) -> str:
    """Anexa o JSON na release. Devolve a situação para o registro."""
    nome = f"metricas-sonar-{arquivo.name}"
    if any(a.get("name") == nome for a in release.get("assets") or []):
        return "anexado"
    r = sessao.post(f"{UPLOADS}/repos/{config.GITHUB_ORG}/{repo}/releases/{release['id']}/assets",
                    params={"name": nome}, data=arquivo.read_bytes(),
                    headers={"Content-Type": "application/json"}, timeout=60)
    if r.status_code == 422:      # já existe um asset com esse nome
        return "anexado"
    r.raise_for_status()
    return "anexado"


# ───────────────────────── execução ─────────────────────────

def executar(pasta: Path = PASTA_RELEASES, repos: list[str] | str | None = None, *,
             sessao=None, sessao_assets=None, cliente=None,
             coletar: Callable = sonar_api.coletar, agora: datetime | None = None, log=print) -> list[Path]:
    if sessao is None or cliente is None:
        carregar_env(RAIZ / ".env")
    sessao = sessao or _sessao(os.environ.get("GITHUB_TOKEN"))
    if sessao_assets is None and os.environ.get("RELEASE_ASSETS_TOKEN"):
        sessao_assets = _sessao(os.environ["RELEASE_ASSETS_TOKEN"])
    cliente = cliente or sonar_api.SonarClient.do_ambiente(url=config.SONAR_URL, organizacao=config.SONAR_ORGANIZACAO)

    registro = carregar_registro(pasta)
    gravados: list[Path] = []
    alvos = [r for r in normalizar_repositorios(repos) if projeto_sonar(r)]
    log(f"Releases: verificando {len(alvos)} repositórios")

    for repo in alvos:
        try:
            releases = listar_releases(sessao, repo)
        except Exception as erro:  # noqa: BLE001 — um repositório com erro não para os outros
            log(f"{repo}: não deu para listar as releases ({erro.__class__.__name__})")
            continue
        validas = [r for r in releases if release_valida(r)]
        por_tag = {r["tag_name"]: r for r in validas}

        if repo not in registro["repositorios"]:
            registro["repositorios"][repo] = {
                r["tag_name"]: {"situacao": "anterior", "publicada_em": r.get("published_at")} for r in validas}
            log(f"{repo}: primeira verificação; {len(validas)} releases já existentes marcadas como anteriores")
            continue

        registradas = registro["repositorios"][repo]
        for rel in releases_novas(validas, registradas):
            tag = rel["tag_name"]
            momento = agora or datetime.now(timezone.utc)
            try:
                snap = coletar(cliente, [projeto_sonar(repo)], config.SONAR_BRANCH, log=log)
            except sonar_api.SonarError as erro:
                log(f"{repo} {tag}: coleta do SonarCloud falhou ({erro}); tenta de novo na próxima")
                continue
            falha = next((p.get("erro") for p in snap.get("projetos", []) if p.get("erro")), None)
            if falha:
                log(f"{repo} {tag}: coleta do SonarCloud falhou ({falha}); tenta de novo na próxima")
                continue
            snap["release"] = {
                "repositorio": repo, "tag": tag, "nome": rel.get("name") or tag,
                "publicada_em": rel.get("published_at"), "url": rel.get("html_url"),
                "coletado_em": momento.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "atraso_horas": atraso_horas(rel.get("published_at"), momento),
            }
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / nome_arquivo(repo, tag)
            destino.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
            registradas[tag] = {"situacao": "coletado", "arquivo": destino.name,
                                "publicada_em": rel.get("published_at"),
                                "atraso_horas": snap["release"]["atraso_horas"], "asset": "pendente"}
            gravados.append(destino)
            log(f"{repo} {tag}: retrato gravado em {destino.name} "
                f"({snap['release']['atraso_horas']} h depois da publicação)")

        # anexa nas releases o que ainda não foi anexado (inclusive de coletas anteriores sem token)
        for tag, item in registradas.items():
            if item.get("situacao") != "coletado" or item.get("asset") == "anexado":
                continue
            if sessao_assets is None:
                item["asset"] = "sem_token"
                continue
            arq = pasta / item["arquivo"]
            if tag not in por_tag or not arq.exists():
                continue
            try:
                item["asset"] = anexar_asset(sessao_assets, repo, por_tag[tag], arq)
                log(f"{repo} {tag}: JSON anexado na release")
            except Exception as erro:  # noqa: BLE001
                item["asset"] = "falhou"
                log(f"{repo} {tag}: não deu para anexar na release ({erro.__class__.__name__})")

    if sessao_assets is None and any(i.get("asset") == "sem_token" for r in registro["repositorios"].values()
                                     for i in r.values()):
        log("Aviso: secret RELEASE_ASSETS_TOKEN não configurado; os retratos não foram anexados nas releases.")
    salvar_registro(pasta, registro)
    return gravados


def main() -> int:
    parser = argparse.ArgumentParser(description="Grava o retrato do SonarCloud de cada release nova.")
    parser.add_argument("--repos", type=str, default="", help="Repositórios (nomes curtos ou 'todos')")
    args = parser.parse_args()
    executar(repos=args.repos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
