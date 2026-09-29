"""Links de rastreio: para onde cada número pode ser conferido (página, aba da planilha, config, repositório)."""

from __future__ import annotations

import re

import streamlit as st

import config
from src.data import planilha

REPO_DOCS = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-docs-eps/blob/main/Analytics/"

PAGINAS = {
    "Visão Executiva": "./visao-executiva", "Agile EVM": "./agile-evm", "Gestão ágil": "./zenhub",
    "Qualidade técnica": "./sonar", "Custos": "./custos", "Riscos": "./riscos", "Decisões": "./decisoes",
    "Integração contínua": "./processo", "Metodologia": "./metodologia",
}


def codigo(caminho: str = "config.py") -> str:
    """Link para um arquivo do Analytics/ no GitHub (onde o parâmetro ou a fórmula está escrito)."""
    return REPO_DOCS + caminho


def pagina(nome: str) -> str | None:
    return PAGINAS.get(nome)


def aba(chave: str) -> tuple[str, str | None]:
    """(texto, link) da aba da planilha original."""
    return (f"Planilha · aba {planilha.nome_aba(chave)}", planilha.link_aba(chave))


def sonar(repositorio: str) -> str:
    chave = repositorio if repositorio.startswith(config.SONAR_ORGANIZACAO) else \
        f"{config.SONAR_ORGANIZACAO}_{repositorio}"
    return f"{config.SONAR_URL}/project/overview?id={chave}"


def actions(repositorio: str) -> str:
    return f"https://github.com/{config.GITHUB_ORG}/{repositorio}/actions"


def aba_original(chave: str, altura: int = 460) -> None:
    """Menu recolhido com a aba publicada da planilha embutida (somente leitura)."""
    url = config.PLANILHAS.get(chave, "")
    m = re.search(r"/d/e/([^/]+)/pub\?gid=(\d+)", url)
    with st.expander(f"Ver a aba original ({planilha.nome_aba(chave)})"):
        if not m:
            st.caption("Aba sem URL publicada em `config.PLANILHAS`.")
            return
        import streamlit.components.v1 as components
        components.iframe(f"https://docs.google.com/spreadsheets/d/e/{m.group(1)}/pubhtml?gid={m.group(2)}"
                          "&single=true&widget=true&headers=false", height=altura, scrolling=True)
        link = planilha.link_aba(chave)
        st.caption("Versão publicada (atualiza em alguns minutos). " +
                   (f"[Abrir para editar]({link}) — exige acesso à planilha." if link else ""))
