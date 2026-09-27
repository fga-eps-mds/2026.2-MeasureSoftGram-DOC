"""Configuração do dashboard: o único arquivo que o time precisa editar.

Tudo o que é ponto, sprint, velocity, AgileEVM e burndown vem do Zenhub
(``scripts/coleta_velocity.py``). Da planilha "MeasureSoftGram" vêm só as abas
que o Zenhub não tem:

    custos         -> aba "Custos"
    planejamento   -> aba "Planejamento"  (quem está no time em cada semana)
    horas          -> aba "Horas"
    riscos         -> aba "Riscos"
    monitoramento  -> aba "Monitoramento"
    decisoes       -> aba "Decisões"

Para cada aba: Arquivo > Compartilhar > Publicar na Web > escolher a aba >
"Valores separados por vírgula (.csv)" > Publicar, e colar o link na chave.
Enquanto a URL estiver vazia, o app lê o CSV de mesmo nome em ``planilhas/``.
"""

PLANILHAS = {
    "custos": "",
    "planejamento": "",
    "horas": "",
    "riscos": "",
    "monitoramento": "",
    "decisoes": "",
}

CACHE_PLANILHAS_S = 300
