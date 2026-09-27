"""Configuração do dashboard: o único arquivo que o time precisa editar.

Produto e Processo vêm sozinhos dos .json que o `metrics.yml` publica em `data/`.

Custos, AgileEVM, Velocity, Riscos e Decisões vêm de duas planilhas do Google:

* "MeasureSoftGram 2026.2 · Custos e AgileEVM"
  (abas Custos, Planejamento, Horas, Sumário EVM, EVM - Valor Agregado, EVM - Velocity)
* "MeasureSoftGram 2026.2 · Riscos e Decisões"
  (abas Riscos, Monitoramento, Decisões)

Para cada aba: Arquivo > Compartilhar > Publicar na Web > escolher a aba >
"Valores separados por vírgula (.csv)" > Publicar, e colar o link na chave abaixo.
Enquanto a URL estiver vazia, o app lê o CSV de mesmo nome em `planilhas/`
(cópia exportada da planilha) e diz isso na tela.
"""

PLANILHAS = {
    # Custos e AgileEVM
    "custos": "",
    "planejamento": "",
    "horas": "",
    "sumario_evm": "",
    "valor_agregado": "",
    "velocity": "",
    # Riscos e Decisões
    "riscos": "",
    "monitoramento": "",
    "decisoes": "",
}

CACHE_PLANILHAS_S = 300
