"""Grava o JSON de métricas do SonarCloud de cada release nova e anexa na release.

Uso (na pasta Analytics/):

    python scripts/coleta_releases.py                    # todos os repositórios
    python scripts/coleta_releases.py --repos Service    # só os indicados

Substitui o que o ``metrics.yml`` + ``parser.py`` de cada repositório faziam na tag ``v*``, no
MESMO formato: a resposta crua de ``api/measures/component_tree`` (``paging``, ``baseComponent``,
``components``), que é a entrada do ``msgram extract``, com o nome
``fga-eps-mds-<repo>-MM-DD-AAAA-HH-MM-SS-<tag>.json``.

Como funciona:

1. Lista as releases de cada repositório pela API do GitHub (rascunhos e tags que não começam
   com ``v`` ficam de fora, como no ``metrics.yml``).
2. Compara com ``data/sonar/releases/registro.json``. Release que não está no registro é nova:
   baixa a árvore do SonarCloud daquele projeto na **branch padrão** (sem ``branch``, como o
   ``parser.py``; no fluxo do projeto é a ``main``, que só muda na release, então coletar horas
   depois ainda retrata o código da tag), com as medidas de ``METRICAS_MSGRAM`` e todas as páginas
   (o ``parser.py`` lia só as 500 primeiras), e grava em ``data/`` junto dos .json do pipeline.
3. Se o secret ``RELEASE_ASSETS_TOKEN`` existir, anexa o arquivo nos Assets da release com o mesmo
   nome. Sem o token, registra ``sem_token`` e tenta de novo nas próximas coletas.

Primeira vez de um repositório no registro: as releases que já existem entram como ``anterior``
e NÃO são coletadas (os arquivos de R1 a R3 já estão em ``data/*.json`` e nos Assets).
Os tokens nunca são impressos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from scripts.verificar_novos_prs import normalizar_repositorios  # noqa: E402
from src.data import sonar_api  # noqa: E402
from src.data.sonar import ORG, PASTA_API  # noqa: E402
from src.zenhub.client import carregar_env  # noqa: E402

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
PASTA_RELEASES = PASTA_API / "releases"     # só o registro.json
PASTA_DADOS = RAIZ / "data"                 # onde o metrics.yml deixava os .json
ARQUIVO_REGISTRO = "registro.json"

# União das medidas que os 8 parser.py pediam (a do CLI, a mais completa). 15 = limite do component_tree.
METRICAS_MSGRAM = [
    "files", "functions", "complexity", "comment_lines_density", "duplicated_lines_density", "coverage",
    "ncloc", "tests", "test_errors", "test_failures", "test_execution_time", "security_rating",
    "test_success_density", "reliability_rating", "sqale_debt_ratio",
]
# O msgram recusa o arquivo sem estas medidas no baseComponent (CLI, jsonReader.REQUIRED_TRK_MEASURES).
MEDIDAS_OBRIGATORIAS_MSGRAM = ["test_failures", "test_errors", "files", "ncloc"]


# ───────────────────────── regras (funções puras) ─────────────────────────

def release_valida(rel: dict) -> bool:
    """Mesma regra do metrics.yml: só tags ``v*`` e nada de rascunho."""
    return not rel.get("draft") and str(rel.get("tag_name") or "").startswith("v")


def releases_novas(releases: list[dict], registradas: dict) -> list[dict]:
    """Releases válidas que ainda não estão no registro, da mais antiga para a mais nova."""
    novas = [r for r in releases if release_valida(r) and r["tag_name"] not in registradas]
    return sorted(novas, key=lambda r: r.get("published_at") or r.get("created_at") or "")


def nome_arquivo(repo: str, tag: str, momento: datetime) -> str:
    """Mesmo padrão do parser.py: ``fga-eps-mds-<repo>-MM-DD-AAAA-HH-MM-SS-<tag>.json`` (hora em UTC)."""
    seguro = "".join(c if c.isalnum() or c in "._-" else "_" for c in tag)
    return f"{ORG}-{repo}-{momento.astimezone(timezone.utc):%m-%d-%Y-%H-%M-%S}-{seguro}.json"


def atraso_horas(publicada_em: str | None, coletado_em: datetime) -> float | None:
    if not publicada_em:
        return None
    publicada = datetime.fromisoformat(publicada_em.replace("Z", "+00:00"))
    return round((coletado_em - publicada).total_seconds() / 3600, 1)


def projeto_sonar(repo: str) -> str | None:
    chave = f"{config.SONAR_ORGANIZACAO}_{repo}"
    return chave if chave in config.SONAR_PROJETOS else None


# ───────────────────────── SonarCloud (formato do msgram) ─────────────────────────

def arvore_msgram(cliente, projeto: str, max_paginas: int = 20) -> dict:
    """``api/measures/component_tree`` cru, com todas as páginas juntas, na branch padrão do projeto."""
    componentes, base, total, pagina = [], None, 0, 1
    while pagina <= max_paginas:
        d = cliente.get("api/measures/component_tree", {"component": projeto, "metricKeys": ",".join(METRICAS_MSGRAM),
                                                        "ps": 500, "p": pagina})
        base = base or d.get("baseComponent")
        comps = d.get("components") or []
        componentes.extend(comps)
        total = (d.get("paging") or {}).get("total", len(componentes))
        if pagina * 500 >= total or not comps:
            break
        pagina += 1
    if not base or not componentes:
        raise sonar_api.SonarError("árvore do projeto vazia")
    return {"paging": {"pageIndex": 1, "pageSize": len(componentes), "total": total},
            "baseComponent": base, "components": componentes}


def faltam_no_msgram(arvore: dict) -> list[str]:
    medidas = {m.get("metric") for m in (arvore.get("baseComponent") or {}).get("measures", [])}
    return [m for m in MEDIDAS_OBRIGATORIAS_MSGRAM if m not in medidas]


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
    nome = arquivo.name
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
             pasta_dados: Path = PASTA_DADOS, sessao=None, sessao_assets=None, cliente=None,
             agora: datetime | None = None, log=print) -> list[Path]:
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
                arvore = arvore_msgram(cliente, projeto_sonar(repo))
            except sonar_api.SonarError as erro:
                log(f"{repo} {tag}: coleta do SonarCloud falhou ({erro}); tenta de novo na próxima")
                continue
            faltam = faltam_no_msgram(arvore)
            if faltam:
                log(f"{repo} {tag}: aviso — sem {', '.join(faltam)} no projeto; o msgram vai recusar o arquivo")
            pasta_dados.mkdir(parents=True, exist_ok=True)
            destino = pasta_dados / nome_arquivo(repo, tag, momento)
            destino.write_text(json.dumps(arvore), encoding="utf-8")
            atraso = atraso_horas(rel.get("published_at"), momento)
            registradas[tag] = {"situacao": "coletado", "arquivo": destino.name,
                                "publicada_em": rel.get("published_at"), "url": rel.get("html_url"),
                                "coletado_em": momento.astimezone(timezone.utc).isoformat(timespec="seconds"),
                                "atraso_horas": atraso, "componentes": len(arvore["components"]),
                                "faltam_no_msgram": faltam, "asset": "pendente"}
            gravados.append(destino)
            log(f"{repo} {tag}: {destino.name} gravado ({len(arvore['components'])} componentes, "
                f"{atraso} h depois da publicação)")

        # anexa nas releases o que ainda não foi anexado (inclusive de coletas anteriores sem token)
        for tag, item in registradas.items():
            if item.get("situacao") != "coletado" or item.get("asset") == "anexado":
                continue
            if sessao_assets is None:
                item["asset"] = "sem_token"
                continue
            arq = pasta_dados / item["arquivo"]
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
        log("Aviso: secret RELEASE_ASSETS_TOKEN não configurado; os JSON não foram anexados nas releases.")
    salvar_registro(pasta, registro)
    return gravados


def main() -> int:
    parser = argparse.ArgumentParser(description="Grava e anexa o JSON do SonarCloud de cada release nova.")
    parser.add_argument("--repos", type=str, default="", help="Repositórios (nomes curtos ou 'todos')")
    args = parser.parse_args()
    executar(repos=args.repos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
