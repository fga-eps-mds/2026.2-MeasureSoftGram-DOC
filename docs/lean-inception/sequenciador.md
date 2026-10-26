---
title: 9. Sequenciador
sidebar_label: 9. Sequenciador
sidebar_position: 10
description: Resultado da atividade "9. Sequenciador" da Lean Inception 2026.2.
---

# 9. Sequenciador

O sequenciador ordena as funcionalidades em ondas, respeitando dependências,
esforço, valor e a capacidade do time. As primeiras ondas formam o MVP. Referência: CAROLI, P. *Lean Inception: como alinhar pessoas e construir o produto certo*.

## Resultado

![Sequenciador de funcionalidades](@site/static/img/sequenciador.png)

## O que decidimos

| Onda | Release | Funcionalidades |
| --- | --- | --- |
| 1 | R1 | Operacionalizar a medida de dívida técnica · Revisar o fluxo de carregamento do frontend (correção) · Adequar à LGPD (correção) · Autenticar usuários pelo GitLab |
| 2 | R2 | Novos gráficos no dashboard · Importar repositórios do GitLab · Planejado × realizado sobre o equalizador da qualidade · Rastreabilidade dos arquivos de código-fonte entre métricas e medidas |
| 3 | R3 (**MVP**) | Pesos das entidades de qualidade por AHP · CI/CD para GitLab (análogo à Action) · Alerta de decaimento da qualidade antes do merge · Característica de segurança |
| 4 | pós-MVP | Gráficos de pulso · Relatório de release · Qualidade em uso · PR e causa raiz da degradação entre dois períodos |
| 5 | pós-MVP | Relatório de qualidade como nota de release · Diferença de indicadores entre releases · Configuração de release via LLM |

Parte da onda 1 (GitLab, dívida técnica) ficou para a R2; ver [Release 2](/docs/releases/release-2).

## Impacto no projeto

Define as ondas do [Roadmap](/docs/planejamento/roadmap#ondas-de-escopo) e a
formação dos [squads](/docs/planejamento/squads).

## Histórico de versão

| Versão | Data | Descrição | Autor | Revisor |
| --- | --- | --- | --- | --- |
| 1.0 | 26/09/2026 | Criação da página | [@storch7](https://github.com/storch7) |  |
| 2.0 | 21/10/2026 | Modelo padrão: teoria resumida, seção "O que decidimos" e impacto no projeto | [@MilenaFRocha](https://github.com/MilenaFRocha) |  |
