"""Verificação por hashing (SHA-256) e saneamento de snapshots duplicados em Analytics/data.

Uso (na pasta Analytics/):

    python scripts/saneamento_dados.py             # remove snapshots JSON redundantes
    python scripts/saneamento_dados.py --dry-run   # apenas lista o que seria removido
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import config  # noqa: E402

PASTA_DADOS = RAIZ / "data"
CAMPOS_VOLATEIS = frozenset({"coletado_em", "requisicoes", "detalhes_novos"})

_SONAR_PIPELINE = re.compile(
    r"^(?P<prefixo>.+?)-(?P<mes>\d{2})-(?P<dia>\d{2})-(?P<ano>\d{4})"
    r"-(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})-(?P<branch>.+)\.json$"
)


def _janela_release(data_iso: str) -> str:
    """Identifica a janela de release (R1, R2, R3...) de uma data AAAA-MM-DD para preservar marcos por release."""
    d = str(data_iso)[:10]
    for nome, fim in sorted(getattr(config, "RELEASES", {}).items(), key=lambda x: x[1]):
        if d <= str(fim)[:10]:
            return nome
    return "POS"


def hash_payload(dados: dict | list, ignorar: Iterable[str] = CAMPOS_VOLATEIS) -> str:
    """Calcula o hash SHA-256 canônico do payload JSON ignorando metadados voláteis de coleta."""
    ignorar_set = set(ignorar)
    if isinstance(dados, dict):
        limpo = {k: v for k, v in dados.items() if k not in ignorar_set}
    else:
        limpo = dados
    serializado = json.dumps(limpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def mesmo_payload(
    novo: dict | list | None,
    antigo: dict | list | None,
    ignorar: Iterable[str] = CAMPOS_VOLATEIS,
) -> bool:
    """Retorna True se ambos os snapshots existem e possuem o mesmo hash de conteúdo útil."""
    if novo is None or antigo is None:
        return False
    return hash_payload(novo, ignorar=ignorar) == hash_payload(antigo, ignorar=ignorar)


def _sanear_lista_snapshots(arquivos: list[Path], dry_run: bool = False) -> list[Path]:
    """Remove arquivos cujo hash de payload já ocorreu anteriormente na sequência ordenada."""
    vistos: set[str] = set()
    removidos: list[Path] = []
    for arq in arquivos:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        h = hash_payload(dados)
        if h in vistos:
            if not dry_run:
                arq.unlink()
            removidos.append(arq)
        else:
            vistos.add(h)
    return removidos


def sanear_sonar_api(pasta: Path, dry_run: bool = False) -> list[Path]:
    """Expurga snapshots redundantes em data/sonar/sonar-*.json."""
    if not pasta.exists():
        return []
    return _sanear_lista_snapshots(sorted(pasta.glob("sonar-*.json")), dry_run=dry_run)


def sanear_zenhub_velocity(pasta: Path, dry_run: bool = False) -> list[Path]:
    """Expurga snapshots redundantes em data/zenhub/velocity/zenhub-velocity-*.json."""
    if not pasta.exists():
        return []
    return _sanear_lista_snapshots(sorted(pasta.glob("zenhub-velocity-*.json")), dry_run=dry_run)


def sanear_sonar_pipeline(pasta: Path, dry_run: bool = False) -> list[Path]:
    """Expurga snapshots redundantes do pipeline (<org>-<repo>-MM-DD-YYYY-HH-MM-SS-<branch>.json)."""
    if not pasta.exists():
        return []
    por_repo_branch: dict[tuple[str, str, str], list[tuple[str, Path]]] = {}
    for arq in sorted(pasta.glob("*.json")):
        if arq.name.startswith("GitHub_API-"):
            continue
        m = _SONAR_PIPELINE.match(arq.name)
        if not m:
            continue
        g = m.groupdict()
        chave_tempo = f"{g['ano']}-{g['mes']}-{g['dia']}T{g['h']}:{g['m']}:{g['s']}"
        janela = _janela_release(chave_tempo)
        por_repo_branch.setdefault((g["prefixo"], g["branch"], janela), []).append((chave_tempo, arq))

    removidos: list[Path] = []
    for chave in sorted(por_repo_branch):
        ordenados = [arq for _, arq in sorted(por_repo_branch[chave], key=lambda x: x[0])]
        removidos.extend(_sanear_lista_snapshots(ordenados, dry_run=dry_run))
    return removidos


def sanear_tudo(pasta_dados: Path = PASTA_DADOS, dry_run: bool = False, log=print) -> dict[str, list[Path]]:
    """Executa o saneamento em todas as subpastas de snapshots de Analytics/data."""
    pasta_dados = Path(pasta_dados)
    rem_sonar_api = sanear_sonar_api(pasta_dados / "sonar", dry_run=dry_run)
    rem_zenhub = sanear_zenhub_velocity(pasta_dados / "zenhub" / "velocity", dry_run=dry_run)
    rem_pipeline = sanear_sonar_pipeline(pasta_dados, dry_run=dry_run)

    acao = "Seriam removidos" if dry_run else "Removidos"
    total = len(rem_sonar_api) + len(rem_zenhub) + len(rem_pipeline)
    log(
        f"{acao} {total} arquivos duplicados "
        f"(sonar_api={len(rem_sonar_api)}, zenhub_velocity={len(rem_zenhub)}, sonar_pipeline={len(rem_pipeline)})"
    )
    return {
        "sonar_api": rem_sonar_api,
        "zenhub_velocity": rem_zenhub,
        "sonar_pipeline": rem_pipeline,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Saneamento de arquivos JSON duplicados em Analytics/data.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas exibe os arquivos que seriam removidos")
    args = parser.parse_args()
    sanear_tudo(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
