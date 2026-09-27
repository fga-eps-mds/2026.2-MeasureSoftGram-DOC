"""Diagnóstico de conexão com a API do Zenhub (não imprime a chave).

Uso (na pasta Analytics/):  python scripts/diagnostico_zenhub.py

Testa, pelo proxy do sistema e em conexão direta, uma requisição sem chave e as
queries da coleta com página de 1 item. Cole a saída para quem for depurar.
"""

from __future__ import annotations

import os
import platform
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import requests  # noqa: E402

from src.zenhub import queries  # noqa: E402
from src.zenhub.client import (API_URL, _resumo, _transporte_node, carregar_env, chave_do_ambiente,  # noqa: E402
                               workspace_do_ambiente)


def host(url):
    return urlparse(url).netloc.split("@")[-1] if url else "-"


def teste(nome, direta, query=None, variaveis=None, chave=None):
    s = requests.Session()
    s.trust_env = not direta
    ini = time.time()
    try:
        if query is None:
            r = s.post(API_URL, json={"query": "{__typename}"}, timeout=30, headers={"Connection": "close"})
        else:
            r = s.post(API_URL, json={"query": query, "variables": variaveis}, timeout=60,
                       headers={"Authorization": f"Bearer {chave}", "Connection": "close"})
        corpo = r.text[:160].replace(chave or "\0", "***").replace("\n", " ")
        res = f"HTTP {r.status_code} · {corpo}"
    except Exception as erro:  # noqa: BLE001
        res = _resumo(erro)
    modo = "direto" if direta else "proxy "
    print(f"[{modo}] {nome:<22} {time.time() - ini:5.1f}s  {res}", flush=True)
    return res


def main():
    carregar_env(RAIZ / ".env")
    chave = chave_do_ambiente()
    print(f"Python {platform.python_version()} · requests {requests.__version__} · {ssl.OPENSSL_VERSION}")
    print(f"HTTPS_PROXY={host(os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'))} · "
          f"proxy do sistema={host(urllib.request.getproxies().get('https'))} · "
          f"ZENHUB_IGNORAR_PROXY={os.environ.get('ZENHUB_IGNORAR_PROXY', '-')} · chave={'sim' if chave else 'NÃO'}")
    ws = workspace_do_ambiente()
    for direta in (False, True):
        teste("sem chave (espera 401)", direta)
        if not chave:
            continue
        res = teste("sprints (1)", direta, queries.SPRINTS, {"workspaceId": ws, "first": 1, "after": None}, chave)
        sid = None
        if res.startswith("HTTP 200"):
            r = requests.Session()
            r.trust_env = not direta
            try:
                dados = r.post(API_URL, json={"query": queries.SPRINTS, "variables": {"workspaceId": ws, "first": 1}},
                               headers={"Authorization": f"Bearer {chave}"}, timeout=60).json()
                sid = dados["data"]["workspace"]["sprints"]["nodes"][0]["id"]
            except Exception:  # noqa: BLE001
                pass
        if sid:
            for n in (1, 8):
                teste(f"issues da sprint ({n})", direta, queries.SPRINT_ISSUES,
                      {"sprintId": sid, "workspaceId": ws, "first": n, "after": None}, chave)
            teste("scopeChange (1)", direta, queries.SPRINT_SCOPE_CHANGES,
                  {"sprintId": sid, "first": 1, "after": None}, chave)
            teste("releases (1)", direta, queries.RELEASES, {"workspaceId": ws, "first": 1, "after": None}, chave)
    teste_node(chave, ws)


def teste_node(chave, ws):
    import shutil
    if not shutil.which("node"):
        print("[node  ] node não encontrado no PATH (instale o Node 18+)")
        return
    for nome, q, v in (("sem chave (espera 401)", "{__typename}", {}),
                       ("sprints (1)", queries.SPRINTS, {"workspaceId": ws, "first": 1, "after": None})):
        ini = time.time()
        try:
            h = {"Authorization": f"Bearer {chave}"} if chave and nome != "sem chave (espera 401)" else {}
            r = _transporte_node(API_URL, {"query": q, "variables": v}, h, 60)
            res = f"HTTP {r.status} · {str(r.corpo)[:120]}"
        except Exception as erro:  # noqa: BLE001
            res = str(erro)[:200]
        print(f"[node  ] {nome:<22} {time.time() - ini:5.1f}s  {res}", flush=True)


if __name__ == "__main__":
    main()
