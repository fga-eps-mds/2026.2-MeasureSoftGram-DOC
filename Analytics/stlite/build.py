"""Empacota o dashboard Streamlit para rodar no GitHub Pages (sem servidor).

O GitHub Pages só serve arquivos estáticos. O stlite (https://github.com/whitphx/stlite)
roda o próprio Streamlit dentro do navegador, com Python compilado para
WebAssembly (Pyodide). Este script:

1. copia o app (``app.py``, ``config.py``, ``pages/``, ``src/``) e os dados do pipeline
   (``Analytics/data/**/*.json``), baixa as abas publicadas da planilha (``config.PLANILHAS``)
   para a pasta de saída, mantendo a mesma estrutura do repositório;
2. gera um ``index.html`` que monta esses arquivos no sistema de arquivos virtual
   do Pyodide e executa ``Analytics/app.py`` — o mesmo arquivo que roda com
   ``streamlit run``. Não existe uma segunda versão do dashboard.

O workflow ``deploy.yml`` roda este script antes do build do Docusaurus, então
cada push na ``main`` (inclusive os commits do pipeline de métricas) republica o
dashboard com os dados novos em ``<site>/dashboard/``.

Uso local::

    python Analytics/stlite/build.py              # gera static/dashboard/
    cd static/dashboard && python -m http.server  # abre http://localhost:8000

Nunca entram no pacote: ``.env`` (token do Zenhub), ``scripts/``, ``*.xlsx`` e caches.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

ANALYTICS = Path(__file__).resolve().parent.parent
RAIZ = ANALYTICS.parent

# Versão do stlite no CDN. "0" = última 0.x; fixe uma versão exata (ex.: "0.86.0")
# se uma atualização do stlite quebrar algo.
STLITE = "0"

# Pacotes além dos que o Streamlit já traz. pandas e requests vêm do Pyodide;
# tzdata dá o fuso America/Sao_Paulo no navegador.
REQUISITOS = ["altair", "requests", "tzdata"]

INCLUIR = [
    ("Analytics", ["app.py", "config.py", "pages/*.py", "src/*.py", "src/*/*.py",
                   "data/*.json", "data/sonar/*.json", "data/zenhub/*.json", "data/zenhub/velocity/*.json"]),
]


def _tema() -> dict:
    """Lê a seção [theme] de .streamlit/config.toml (o stlite não lê o arquivo sozinho)."""
    cfg = ANALYTICS / ".streamlit" / "config.toml"
    tema, secao = {}, None
    for linha in cfg.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if m := re.fullmatch(r"\[(.+)\]", linha):
            secao = m.group(1).strip()
        elif secao == "theme" and (m := re.fullmatch(r'(\w+)\s*=\s*"(.*)"', linha)):
            tema[f"theme.{m.group(1)}"] = m.group(2)
    return tema


def _arquivos() -> list[str]:
    caminhos = []
    for base, padroes in INCLUIR:
        pasta = RAIZ / base
        for padrao in padroes:
            for arq in sorted(pasta.glob(padrao)):
                if arq.is_file() and "__pycache__" not in arq.parts:
                    caminhos.append(arq.relative_to(RAIZ).as_posix())
    return caminhos


PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
  <title>MeasureSoftGram — Dashboard de Gestão de Projeto</title>
  <link rel="icon" href="../img/favicon.png" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{stlite}/build/stlite.css" />
  <style>
    body {{ margin: 0; font-family: "Roboto", system-ui, sans-serif; background: #F4F5F6; color: #1F2933; }}
    #carregando {{ max-width: 560px; margin: 18vh auto 0; padding: 0 16px; text-align: center; }}
    #carregando h1 {{ font-size: 1.4rem; margin-bottom: .4rem; }}
    #carregando p {{ color: #4B5563; line-height: 1.5; }}
    #carregando a {{ color: #2B4D6F; }}
  </style>
</head>
<body>
  <div id="root">
    <div id="carregando">
      <h1>MeasureSoftGram — Dashboard de Gestão de Projeto</h1>
      <p>Carregando o Python no navegador. Na primeira visita leva de 20 a 40 segundos;
         depois o navegador guarda o cache e abre bem mais rápido.</p>
      <p>Publicado em <strong>{gerado}</strong> · <a href="../">voltar para a documentação</a></p>
      <noscript><p>Este dashboard precisa de JavaScript habilitado.</p></noscript>
    </div>
  </div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{stlite}/build/stlite.js";
    const arquivos = {arquivos};
    const files = Object.fromEntries(arquivos.map((p) => [p, {{ url: "./" + p }}]));
    mount(
      {{
        requirements: {requisitos},
        entrypoint: "Analytics/app.py",
        files,
        streamlitConfig: {tema},
      }},
      document.getElementById("root"),
    );
  </script>
</body>
</html>
"""


def _baixar_planilhas(saida: Path) -> list[str]:
    """Baixa as abas publicadas no Google (URLs de config.py) para o pacote.

    O navegador não lê a planilha direto; por isso o deploy baixa a versão
    publicada aqui. Aba que falhar fica fora do pacote e o painel a mostra como
    indisponível. Devolve os caminhos baixados (para montar no navegador).
    """
    baixados: list[str] = []
    import importlib.util
    import urllib.request

    spec = importlib.util.spec_from_file_location("config_dash", ANALYTICS / "config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    for chave, url in (getattr(cfg, "PLANILHAS", {}) or {}).items():
        if not url:
            continue
        destino = saida / "Analytics" / "planilhas" / f"{chave}.csv"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                conteudo = r.read()
            conteudo.decode("utf-8")  # garante texto antes de gravar
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            baixados.append(destino.relative_to(saida).as_posix())
            print(f"planilha: {chave} baixada da versão publicada")
        except Exception as erro:  # noqa: BLE001
            print(f"planilha: {chave} NÃO baixada ({erro.__class__.__name__}); a aba ficará indisponível")
    return baixados


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saida", type=Path, default=RAIZ / "static" / "dashboard",
                    help="pasta de saída (padrão: static/dashboard, que o Docusaurus publica em /dashboard/)")
    args = ap.parse_args()
    saida: Path = args.saida.resolve()

    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True)

    arquivos = _arquivos()
    for rel in arquivos:
        destino = saida / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, destino)
    arquivos += _baixar_planilhas(saida)

    from datetime import datetime, timedelta, timezone
    gerado = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    tema = {**_tema(), "client.toolbarMode": "minimal"}
    (saida / "index.html").write_text(PAGINA.format(
        stlite=STLITE,
        gerado=html.escape(gerado),
        arquivos=json.dumps(arquivos, ensure_ascii=False, indent=6),
        requisitos=json.dumps(REQUISITOS),
        tema=json.dumps(tema),
    ), encoding="utf-8")

    total = sum((saida / r).stat().st_size for r in arquivos)
    print(f"dashboard: {len(arquivos)} arquivos ({total / 1e6:.1f} MB) em {saida}")


if __name__ == "__main__":
    main()
