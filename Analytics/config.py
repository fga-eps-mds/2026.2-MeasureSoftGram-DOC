"""Configuração do dashboard: o único arquivo que o time precisa editar.

Produto e processo vêm automaticamente dos .json do pipeline e do Zenhub.

Projeto (custo, horas, risco, decisões) vem da planilha
"MeasureSoftGram 2026.2 · Gestão do Projeto (v2)" no Google Drive:
https://docs.google.com/spreadsheets/d/1W_Z-u_tUhLymgUIJFh2h2b1T5RjmBKli4s_ricDaXxA/edit

Para cada aba abaixo: Arquivo > Compartilhar > Publicar na web > escolher a aba >
formato CSV > Publicar, e colar o link na chave de mesmo nome. Enquanto a URL
estiver vazia, o app lê o CSV de mesmo nome em planilhas/ e diz isso na tela.
"""

PLANILHAS = {
    "parametros": "",
    "sprints": "",
    "releases": "",
    "horas": "",
    "riscos": "",
    "decisoes": "",
    # Abas da planilha antiga (layout AgileEVM de 2026.1). Não são mais usadas
    # pela aba Projeto; ficam aqui só enquanto a planilha antiga existir.
    "evm": "",
    "velocity": "",
}

CACHE_PLANILHAS_S = 300
