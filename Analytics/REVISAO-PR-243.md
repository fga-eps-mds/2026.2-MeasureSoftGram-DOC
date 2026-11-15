# Correções e validação do PR #243

Data: 10/11/2026. Trabalho local com auxílio de IA, sem publicação, merge ou registro de aprovação.

## Branches e escopo

| Repositório | Branch local | Base | Alteração |
| --- | --- | --- | --- |
| DOC | `fix/243-validacao-plano-qualidade` | `8e37235`, head revisado do PR #243 | Correções dos cálculos, configuração, interface, documentação e ambiente |
| CLI | `fix/qualidade-cobertura-ramos` | `d745b6c`, checkout local anterior | `branch = True` e `relative_files = True` em `tox.ini` |

As alterações foram organizadas em commits locais, sem push. No DOC, o diff é incremental sobre
as mudanças do colega. Nenhum snapshot em `Analytics/data/` foi editado.

## O que foi corrigido

- Portão indisponível impede comprovar "Atingido"; reprovação conhecida prevalece sobre dado ausente.
- O escopo esperado vem da configuração e do filtro de repositórios, não da coleta disponível.
  Ausências aparecem nominalmente em cobertura, duplicação, violações, CI e relatório de testes.
- Pisos M5 ≥ 0,80 e M10 ≥ 0,90 avaliados por repositório e vinculados aos respectivos indicadores.
- Snapshot por repositório limitado à janela de cada release, sem herdar silenciosamente a release anterior.
- Detalhamento do Sonar preserva arquivos, linguagem, coleta e numeradores/denominadores por repositório.
- Catálogo completo das 44 métricas e estrutura do modelo centralizados em `config.py`, sem parser de MDX
  em tempo de execução. As 10 incluídas têm fontes, fórmulas, justificativas e links estáveis.
- Metas por repositório transcritas do plano; pesos dos fatores configuráveis, padrão 1/n e normalização
  somente entre fatores com dados. As metas usam os mesmos pesos e são truncadas em duas casas.
- Tela mostra pisos, metas por repositório, Python/TypeScript separados e número de fatores com dados
  por release. Product Readiness permanece parcial durante a R3. M8 exibe limite de 5 min e teto crítico de 10 min.
- Metodologia inclui catálogo, critérios e limitações; Visão Executiva consome os quatro indicadores.
- Coletor Sonar preparado para ler cobertura de linhas e de ramos separadamente, sem inventar valores.
- TypeScript 7: removida a herança de `baseUrl`, preservando as opções necessárias e o alias `@site`.
- Dev Container instala as dependências Python do caminho correto e as dependências npm, com Node 20;
  Streamlit usa as proteções padrão. Imports sem uso encontrados pelo lint também foram removidos.

## Verificação executada

| Verificação | Resultado |
| --- | --- |
| DOC: `python -m unittest discover -s Analytics/tests -v` | 151 testes passaram, incluindo os históricos e os de sockets locais |
| DOC: `ruff check Analytics --select E9,F` | Passou |
| DOC: `npm run typecheck` | Passou |
| DOC: `npm run build` | Passou |
| DOC: `pip check` | Sem dependências inconsistentes |
| Interface Qualidade: Streamlit AppTest | Todos os blocos renderizaram; 65 tabelas; sem exceção ou erro capturado |
| Visão Executiva: cálculo com snapshots versionados | Quatro indicadores Q-Rapids presentes, fonte CALCULADO |
| Âncoras no HTML gerado | 10 métricas, 4 indicadores e 13 fatores presentes |
| CLI: testes sob coverage | 134 testes passaram; relatório XML registra 290 ramos, 245 cobertos |
| CLI: configuração de coverage | Cobertura de ramos, caminhos relativos e exclusões conferidos |
| Diffs dos dois repositórios | Sem erros de whitespace; dados gerados preservados |

DOC validado com Python 3.14.4, Node 24.22.0 e npm 11.19.1. Sintaxe dos módulos principais também
verificada com Python 3.11. A CLI foi validada em ambiente isolado Python 3.11 com suas dependências,
ativando o ambiente para que os testes de sistema encontrem o executável `msgram`.

## Limites e próximas etapas externas

- O Dev Container foi configurado e seu JSON conferido, mas não foi reconstruído: este ambiente não tem
  permissão para acessar o daemon Docker. A configuração local efetivamente utilizada passou nos checks acima.
- Core e Parser já habilitam cobertura de ramos em `.coveragerc`; não precisaram de alteração.
- Os pipelines públicos atuais da `develop` de AI e Plugin já geram e declaram relatórios de testes.
  Isso foi conferido em `test.yml` e `sonar-project.properties`; não equivale a confirmar a importação
  dos relatórios no Sonar. Não foram feitas alterações nesses dois repositórios.
- Confirmar nova análise e coleta do Sonar depois da mudança na CLI; preservar a linha de base histórica
  e declarar a mudança da instrumentação antes de comparar M5.
- D6 a D9 não foram inventadas nem registradas como aprovadas. A ata de 09/11 na main menciona a aprovação
  da execução do plano; a rastreabilidade formal das decisões e os aceites previstos nas issues cabem à equipe.
- Revisão humana e validação visual em navegador/Deploy Preview ainda são necessárias antes de integrar.
  AppTest verifica a execução dos componentes, não substitui inspeção visual nem aceite do professor.
