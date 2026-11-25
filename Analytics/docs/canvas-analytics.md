# Canvas Analytics: blocos e fontes de dado

> TASK38.01.01 (#357) · Épico MSG38 (#351) · Entrega DA-R3 (30/11)

O Plano de Ensino define o Canvas Analytics como a forma final do dashboard na R3: *"uma síntese visual do desempenho do produto e do projeto ao longo de todo o semestre, incluindo a análise planejado × realizado e uma retrospectiva crítica sobre o uso de IA generativa no projeto"*.

O Canvas não cria métricas novas. Ele reúne numa tela só o que as outras páginas já calculam e mostra cada número em três momentos: **R1 → R2 → R3**.

## Regras do Canvas

1. **Uma tela, três eixos.** Colunas Produto, Projeto e Processo. Rodapé com Riscos, Decisões e Uso de IA.
2. **Cada bloco tem o mesmo formato:** valor em R1, R2 e R3, a meta da R3, a situação (cor do `theme.STATUS`) e uma frase de leitura.
3. **Nada fixo no código.** Todo número vem de `data/*.json` ou das planilhas, pelas funções de `src/metrics/` listadas abaixo.
4. **Cada bloco aponta para a página de detalhe**, como os cartões da Visão Executiva.

## Janelas de tempo

| Janela | Período | Fonte |
| --- | --- | --- |
| R1 | 24/08 a 28/09 | `config.RELEASES`, `config.INICIO_SEMESTRE` |
| R2 | 29/09 a 26/10 | `config.RELEASES` |
| R3 | 27/10 até hoje (limitada a 30/11) | `qrapids.janelas()`, onde a janela aparece com o nome `"Atual"` |

Até a entrega, a coluna R3 é **parcial**, e o Canvas precisa dizer isso.

## Layout

```
┌───────────────────────────────────────────────────────────────────────┐
│ 0. SITUAÇÃO DO SEMESTRE: status geral · dias até a R3 · sprint atual  │
├───────────────────────┬───────────────────────┬───────────────────────┤
│ PRODUTO               │ PROJETO               │ PROCESSO              │
│ 1. Qualidade Q-Rapids │ 3. Custo e prazo (EVM)│ 5. Fluxo              │
│ 2. Qualidade técnica  │ 4. Escopo             │ 6. Integração contínua│
├───────────────────────┴──────────┬────────────┴───────────────────────┤
│ 7. Riscos   │ 8. Decisões gerenciais │ 9. Uso de IA                   │
├──────────────────────────────────┴────────────────────────────────────┤
│ 10. Síntese do semestre: o que melhorou, o que piorou, o que aprendemos│
└───────────────────────────────────────────────────────────────────────┘
```

## Blocos e fontes

| # | Bloco | O que mostra (R1 → R2 → R3, contra a meta) | Função e dado | Página de detalhe |
| --- | --- | --- | --- | --- |
| 0 | Situação do semestre | Status geral, release em foco, dias até 30/11 | `resumo.indicadores()` + `resumo.situacao_geral()`; `config.RELEASES` | Visão Executiva |
| 1 | Qualidade Q-Rapids | Os 4 indicadores do plano de qualidade por release, contra a meta e o piso | `qrapids.avaliar_releases()` (R1, R2, Atual) + `qrapids.metas_agregadas()` | Qualidade |
| 2 | Qualidade técnica | Cobertura, duplicação e bugs agregados dos 8 repositórios, no dia de cada entrega | `sonar.serie_temporal()` + `sonar.serie_agregada()`, cortadas nas datas de `config.RELEASES`; metas em `config.METAS` | Qualidade técnica |
| 3 | Custo e prazo | SPI e CPI por release; VP, VA e CR acumulados | `evm.agile_evm()` + `evm.sumario()`; planilha "Custos e AgileEVM" | Agile EVM |
| 4 | Escopo | Story points planejados × entregues por release | `velocity.calculate_velocity()` + `gestao_agil.resumo_por_release()`; `data/zenhub/velocity/` | Gestão ágil |
| 5 | Fluxo | Throughput, lead time e cycle time medianos por janela | `fluxo.throughput_semanal()`, `fluxo.lead_time()`, `fluxo.cycle_time()`, `fluxo.taxa_conclusao()` com (ini, fim) de cada janela | Fluxo |
| 6 | Integração contínua | Taxa de sucesso da CI e tempo de build por janela, contra a meta de 95 % | linhas de CI de `resumo.indicadores()`; `qrapids.runs_de_build()`; `data/github/runs-*.json` | Integração contínua |
| 7 | Riscos | Riscos elevados e médios e sua evolução | `resumo.contagem_riscos()`; planilha "Riscos e Decisões" | Riscos |
| 8 | Decisões gerenciais | Decisões registradas contra a meta (R2: 3, R3: 5), com a mais recente em destaque | `ctx.decisoes` (planilha "Riscos e Decisões", aba "Decisões"); `config.METAS_DECISOES` | Riscos e decisões |
| 9 | Uso de IA | Acertos, erros e casos de julgamento humano; nº de prompts aceitos e descartados | Entregue pela TASK38.04 (#364, #365) | Uso de IA (nova) |
| 10 | Síntese do semestre | 3 a 5 frases: o que melhorou, o que piorou e o que o time aprendeu | Texto do time, apoiado em `resumo.pontos_de_atencao()` | — |

## Lacunas encontradas

| Lacuna | Impacto no Canvas | Onde resolver |
| --- | --- | --- |
| A janela R3 existe só com o nome `"Atual"` em `qrapids.janelas()` | Renomear na exibição para "R3 (parcial)"; não exige mudar o cálculo | #358 |
| Não há tag de release da R3 nos snapshots do Sonar (a última é de 10/11) | O bloco 2 usa o snapshot mais recente da `develop` como R3 | #343 (retrato por release) |
| As tags não seguem a mesma numeração: Core, CLI e Plugin usam versões próprias | Cortar por data (`config.RELEASES`), não por tag | #358 |
| A planilha tem 3 decisões e a meta da R3 é 5 | O bloco 8 fica amarelo até a #363 | #363 |
| Ainda não existe dado sobre o uso de IA | O bloco 9 fica "sem dado" até a #364 e a #365 | #364, #365 |
| VP, VA e CR acumulados no semestre ainda não existem | O bloco 3 mostra SPI e CPI por release até a #360 | #360 |

## Validação pelo time

- [ ] Blocos e layout aprovados pelo time antes da implementação (#358).
