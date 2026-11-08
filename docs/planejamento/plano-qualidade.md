# Seleção de Métricas Q-Rapids — MeasureSoftGram 2026.2

> Documento relacionado: [Metas dos Indicadores Estratégicos Q-Rapids — R3](metas-indicadores-qrapids-r3.md)

## Sumário

1. [Objetivo e como ler](#1-objetivo-e-como-ler)
2. [Métricas incluídas](#2-métricas-incluídas)
3. [Métricas excluídas](#3-métricas-excluídas)
4. [Resumo da seleção](#4-resumo-da-seleção)
5. [Viés de linguagem e decisões pendentes](#5-viés-de-linguagem-e-decisões-pendentes)
6. [Referências](#referências)

---

## 1. Objetivo e como ler

Das 44 métricas do Q-Rapids, o plano inclui **10** com meta para a R3, monitora **8** sem peso na nota, deixa **8** como habilitáveis e exclui **18**. Cada decisão abaixo segue a hierarquia de avaliação *bottom-up* do modelo.

O catálogo junta as 37 métricas do Q-Rapids Quality Model (abr/2019) e mais 7 do artigo SEAA 2018 que não aparecem nele. Três dessas 7 equivalem a métricas de 2019, então o catálogo tem 41 conceitos distintos. A estrutura de indicadores e fatores é a do modelo de 2019.

### 1.1. Hierarquia de avaliação (bottom-up)

Lida em cada tabela da esquerda para a direita:

1. **Fonte:** SonarCloud, GitHub Actions, GitHub ou Zenhub.
2. **Dado bruto:** o valor como sai da fonte, por exemplo `complexity` e `functions` de cada arquivo.
3. **Métrica avaliada:** um limiar ou função de utilidade transforma o dado em valor de 0 (pior) a 1 (melhor).
4. **Fator:** agrega as métricas e corresponde a uma subcaracterística da ISO/IEC 25010:2011.
5. **Indicador estratégico:** agrega os fatores e cobre uma ou mais características de qualidade.

### 1.2. Critérios de seleção

Uma métrica é incluída só se cumprir os cinco critérios:

1. Responde a um objetivo do projeto ou da disciplina.
2. Tem dado coletado automaticamente por uma fonte que o projeto já usa. **É eliminatório.**
3. É acionável: varia entre repositórios ou aponta um risco que o time consegue corrigir no semestre.
4. Não repete outra métrica já selecionada.
5. Tem fórmula de cálculo no modelo de referência (Q-Rapids Quality Model, 2019) ou no notebook oficial da disciplina (`fga-eps-mds/Analytics`). Fórmulas criadas só pelo time não entram. **É eliminatório.**

### 1.3. Decisões possíveis

- **Incluída:** entra na agregação e tem meta para a R3.
- **Monitorada:** aparece no painel e pode gerar alerta, mas não entra na nota.
- **Habilitável:** fica fora por enquanto e entra quando o time adotar a prática ou a coleta indicada.
- **Excluída:** não tem fonte no projeto, não tem fórmula de referência ou repete outra métrica.

---

## 2. Métricas incluídas

As 10 métricas abaixo entram na agregação, e M1 e M2 também alimentam Product Readiness. Cada uma cumpre os cinco critérios de seleção. As justificativas são conceituais: dizem qual objetivo a métrica responde, onde ela se encaixa no modelo e de onde vem o dado. Nenhum valor medido é usado, porque o time ainda está corrigindo a coleta do SonarCloud. A última coluna diz o que a coleta corrigida precisa confirmar antes de definir linha de base e metas.

### Product Quality — característica trabalhada: Manutenibilidade

| Fator · subcaracterística | Métrica | Dado bruto · fonte | Métrica avaliada (cálculo) | Justificativa da inclusão | A confirmar na coleta corrigida |
|---|---|---|---|---|---|
| Code Quality · Manutenibilidade › Analisabilidade, Modificabilidade | **M1** Complexity | `complexity` e `functions` de cada arquivo · SonarCloud | Arquivo não complexo: complexidade ÷ funções < 10. Valor = não complexos ÷ arquivos | Mede o custo de entender e alterar o código, núcleo da Manutenibilidade. Funciona como guarda contra regressão enquanto o produto cresce. A fórmula está no modelo de 2019 e no notebook. Tem viés de linguagem, então só é comparada dentro do mesmo grupo (Python ou TS). | Valor por repositório e quantos arquivos ficam fora da base de cálculo |
| Code Quality · Manutenibilidade › Analisabilidade, Modificabilidade | **M2** Duplication | `duplicated_lines_density` de cada arquivo · SonarCloud | Arquivo sem duplicação: densidade < 5%. Valor = sem duplicação ÷ arquivos | Código duplicado multiplica o esforço de cada mudança e espalha defeitos. O risco é maior em repositórios de interface, onde componentes são copiados e adaptados. A correção é feita por refatoração dentro do semestre. A fórmula está no modelo e no notebook. | Valor por repositório e quais arquivos passam de 5% |

### Blocking — características trabalhadas: Manutenibilidade e Confiabilidade

| Fator · subcaracterística | Métrica | Dado bruto · fonte | Métrica avaliada (cálculo) | Justificativa da inclusão | A confirmar na coleta corrigida |
|---|---|---|---|---|---|
| Quality Issues' Specification · Manutenibilidade (Q-Rapids); sem subcaracterística direta na ISO 25010 | **M7** Well defined issues | `body` e `milestone` (GitHub); sprint (Zenhub) | Issue bem definida: descrição e prazo preenchidos. Valor = bem definidas ÷ issues criadas no período | Issue mal definida entra na sprint sem critério claro de pronto e distorce velocity, burndown e EVM, que compõem o dashboard avaliado. Usa a definição do modelo, a mesma do dashboard. Estimativa e responsável passam a ser critérios da *Definition of Ready*. | Linha de base com a definição do modelo |
| Blocking Code · Manutenibilidade › Modificabilidade, Analisabilidade | **M6** Non-blocking files | `blocker_violations` e `critical_violations` de cada arquivo · API do SonarCloud | Arquivo não bloqueante: 0 blocker e 0 critical. Valor = não bloqueantes ÷ arquivos de código | Violações graves são o que pode travar uma entrega, e o modelo as mede por arquivo, de qualquer tipo (bug, vulnerabilidade, code smell). Substitui as notas de segurança e confiabilidade, que são por repositório e não fazem parte do Q-Rapids. O script do dashboard já lê as chaves por arquivo. Meta absoluta (zero), porque as regras mudam com a linguagem. | Nomes das chaves no SonarCloud e valor por repositório |
| Testing Status · Confiabilidade › Maturidade; Manutenibilidade › Testabilidade | **M3** Test success | `tests`, `test_errors` e `test_failures` · SonarCloud | (testes − erros − falhas) ÷ testes | Teste falhando na branch de integração é o defeito mais grave do fator e bloqueia o time. A fórmula está no modelo e no notebook. Pela configuração dos repositórios, AI e Plugin não enviam relatório de testes ao SonarCloud, e a métrica obriga a fechar essa lacuna. | Se todos os repositórios passam a reportar testes |
| Testing Status · Confiabilidade › Maturidade; Manutenibilidade › Testabilidade | **M5** Test coverage (SEAA 2018) | `coverage` de cada arquivo · SonarCloud | Arquivo coberto: cobertura > 60%. Valor = cobertos ÷ arquivos (notebook, célula 44) | É a única métrica com meta fixada pela disciplina (cobertura ≥ 90% na R3). Por arquivo, mostra o que a cobertura global esconde: arquivos pouco testados dentro de um repositório bem coberto na média. Pela configuração, CLI, Core e Parser medem só linhas, então a cobertura de ramos precisa ser padronizada antes de fixar a meta. | Valor por arquivo e global, com `line_coverage` e `branch_coverage` separados |

### Process Performance — característica trabalhada: Produtividade

| Fator · subcaracterística | Métrica | Dado bruto · fonte | Métrica avaliada (cálculo) | Justificativa da inclusão | A confirmar na coleta corrigida |
|---|---|---|---|---|---|
| Testing Performance · Produtividade (fator de processo) | **M8** CI feedback time | Duração de cada execução de `test.yml` · GitHub Actions | Duração das execuções de `test.yml`, em minutos (o modelo usa média; a troca por mediana está pendente) | Feedback lento faz o desenvolvedor juntar commits antes de validar, e o tempo tende a crescer junto com a suíte de testes. A fórmula está no modelo de 2019. Fica fora da média 0–1, com meta em minutos. | Tempo por repositório e por release |
| Issues' Velocity · Produtividade (fator de processo) | **M9** Team throughput | Status e datas de cada issue da sprint · Zenhub | Issues fechadas até o fim da sprint ÷ issues planejadas na sprint | Mede a capacidade de planejamento do time, que é a história de usuário do fator no modelo: entregar o que foi planejado em cada ciclo. A definição deve ficar igual à do dashboard. | Conclusão por sprint desde 21/09 |

### Product Readiness — características trabalhadas: Confiabilidade, Manutenibilidade e Produtividade

| Fator · subcaracterística | Métrica | Dado bruto · fonte | Métrica avaliada (cálculo) | Justificativa da inclusão | A confirmar na coleta corrigida |
|---|---|---|---|---|---|
| Product Stability · Confiabilidade › Maturidade | **M10** Build stability | `conclusion` de cada execução de `test.yml` · GitHub Actions | Execuções com sucesso ÷ execuções com sucesso ou falha | Uma build quebrada bloqueia o merge de todo o time e atrasa a release. A fórmula está no modelo de 2019. | Taxa de sucesso por repositório e por release |
| Activities Completion · Produtividade (fator de processo) | **DT** Development task completion | Tipo e status das tarefas do escopo da R3 · Zenhub | Tarefas da R3 concluídas ÷ tarefas planejadas para a R3 | Responde à pergunta do indicador: a release fica pronta? Não repete M9, que mede a sprint e não o escopo da release. A fórmula está no modelo de 2019. | Recorte da R3 no Zenhub (épico ou release) |
| Code Quality (reuso) · Manutenibilidade › Analisabilidade, Modificabilidade | **M1** e **M2** | Os mesmos de Product Quality | Os mesmos de Product Quality | O modelo de 2019 coloca Code Quality também neste indicador, porque código difícil de manter é risco de entrega. Não exige coleta nova. | — |

---

## 3. Métricas excluídas

As outras 34 métricas ficam fora da agregação. Elas se dividem em três grupos, pelo motivo da exclusão: 8 são monitoradas no painel, 8 podem entrar quando o time adotar uma prática ou coleta, e 18 ficam totalmente de fora. Como nas incluídas, as justificativas não usam valores medidos. Uma decisão marcada como provisória pode mudar depois da coleta corrigida.

### 3.1. Monitoradas: acompanhadas no painel, sem peso na nota (8)

Essas métricas têm fonte e fórmula no projeto, mas falham o critério 3 (acionável) ou o 4 (não repetir) como componente da nota. Continuam no painel e podem gerar alerta.

| Indicador › Fator · subcaracterística | Métrica | Dado bruto · fonte | Justificativa da exclusão da agregação |
|---|---|---|---|
| Product Quality › Code Quality · Manutenibilidade › Analisabilidade | **Mc** Comments | `comment_lines_density` de cada arquivo · SonarCloud | A faixa de 10–30% é fixa e não considera a linguagem: TS *strict* usa tipos no lugar de comentários, e as docstrings inflam o valor em Python. Uma meta levaria o time a comentar só para bater o número, sem ganho de manutenibilidade. Fica como alerta para a API pública de Core e Parser, que são bibliotecas publicadas. |
| Process Performance › Testing Performance · Produtividade | **M4** Fast tests | `test_execution_time` de cada suíte · SonarCloud | **Provisória.** O limiar do modelo (5 min por suíte) é alto para testes unitários, então a métrica tende a não variar e não levar a ação. Se a coleta corrigida mostrar variação entre repositórios, a métrica passa a ser incluída. |
| Process Performance › Issues' Velocity · Produtividade | Resolved issues' throughput | Criação e fechamento de cada issue · Zenhub | Complementa M9 com o tempo de resolução. Na nota, repetiria parte do que M9 já mede. |
| Process Performance › Issues' Velocity · Produtividade | Old issues | Criação e status de cada issue · Zenhub | Serve de alerta de backlog esquecido, mas não responde a nenhum objetivo da R3. |
| Process Performance › Development Speed · Produtividade | Build performance | Duração de cada execução de `test.yml` · GitHub Actions | É a versão 0–1 de M8 e levaria o mesmo dado duas vezes para a nota. |
| Process Performance › Development Speed · Produtividade | Commit review duration | Abertura e fechamento de cada PR · GitHub | Mostra se a revisão de PR trava o fluxo, mas o time não tem objetivo declarado sobre isso. A coleta ainda está pendente. |
| Process Performance › Development Speed · Produtividade | Timely feature delivery | Sprints de cada história e data de conclusão · Zenhub | Se sobrepõe em parte a M9. O modelo usa o campo `ontime` do OpenProject, e a versão pelo histórico de sprints é uma adaptação do time (pendente de decisão pelo critério 5). |
| Process Performance › Development Speed · Produtividade | Non-issue component commit | Mensagem de cada commit · GitHub | Mede a rastreabilidade entre commit e issue. É útil como alerta de processo, mas não diz nada sobre a qualidade da entrega. A coleta ainda está pendente. |

### 3.2. Habilitáveis: entram quando o time adotar a prática ou a coleta (8)

Essas métricas falham o critério 2: dependem de um dado que o fluxo atual não garante.

| Indicador › Fator · subcaracterística | Métrica | Dado bruto · fonte | Justificativa da exclusão | Condição para incluir |
|---|---|---|---|---|
| Product Quality › Software Stability · Confiabilidade › Maturidade | Bug density | Tipo e status de cada issue · Zenhub | Depende de defeitos registrados com o rótulo de bug, o que não é prática sistemática do time. | Rótulo de bug obrigatório pelo template de Defeito, com volume suficiente para calcular |
| Process Performance › Testing Performance · Produtividade | Error correction | Criação e fechamento de cada bug · Zenhub | Mesma dependência do rótulo de bug. | Mesma condição de Bug density |
| Process Performance › Testing Performance · Produtividade | Bug leakage | Bugs antes e depois da release · Zenhub | Depende do rótulo de bug e da origem do defeito. É uma razão sem teto. | Rótulo de bug + marcação de origem pós-release |
| Process Performance › Testing Performance · Produtividade | Commit review iterations | Rodadas de revisão de cada PR · GitHub (API de reviews) | O dado existe no GitHub, mas não é coletado. | Coleta nova da API de reviews |
| Process Performance › Testing Performance · Produtividade | Commit response time | Horário da primeira revisão de cada PR · GitHub (API de reviews) | O dado existe no GitHub, mas não é coletado. | Mesma coleta da métrica anterior |
| Product Readiness › Product Stability · Confiabilidade › Maturidade | Critical issues ratio | Prioridade e status de cada issue · Zenhub | Depende de prioridade marcada nas issues, que não é campo obrigatório no fluxo atual. | Prioridade como campo do template de issue |
| Product Readiness › Known Remaining Defects · Confiabilidade › Maturidade | Postponed issues ratio | Prioridade e status de cada issue · Zenhub | Mesma dependência da métrica anterior. | Prioridade ou severidade nas issues |
| Product Readiness › Activities Completion · Produtividade | Specification task completion | Tarefas de especificação · Zenhub | O time não separa tarefas de especificação por tipo ou label. | Tipo ou label de especificação |

### 3.3. Excluídas: sem fonte, sem fórmula de referência ou repetidas (18)

| Indicador › Fator · subcaracterística | Métrica | Motivo | Justificativa da exclusão |
|---|---|---|---|
| Product Quality › Software Stability · Confiabilidade › Maturidade | Errors at runtime (SEAA 2018) | Sem fonte | Nenhum log de produção do Service é coletado para análise. |
| Product Quality › Software Stability · Confiabilidade › Disponibilidade | Availability uptime (SEAA 2018) | Sem fonte | Não há monitoramento de disponibilidade. |
| Product Quality › Software Usage · Adequação funcional › Aptidão funcional | Feature usage | Sem fonte | O produto não tem telemetria de uso. |
| Process Performance › External Quality · Adequação funcional › Correção | End user feedback | Sem fonte | O feedback do cliente não é registrado em ferramenta. |
| Process Performance › Testing Performance · Produtividade | Developer-tester communication | Sem fonte | Não há papel de testador separado. |
| Process Performance › Development Speed · Produtividade | Core component commits | Sem fonte | É específica do caso original (SVN e arquivos `.bpmn`). |
| Process Performance › Development Speed · Produtividade | Timely feature specifications delivery | Sem fonte | O time não separa tarefas de especificação. |
| Blocking › Blocking Code · Manutenibilidade › Modificabilidade | Highly changed files (SEAA 2018) | Sem fórmula de referência | O artigo SEAA 2018 não traz fórmula, a métrica não existe no modelo de 2019 e não está no notebook da disciplina. A fórmula e o limiar de 5 commits foram criados pelo time no dashboard, então a métrica falha o critério 5. |
| Process Performance › Testing Performance · Produtividade | Error identification | Sem direção | Achar mais bugs pode significar teste melhor, então não há valor bom ou ruim. Também depende do rótulo de bug. |
| Process Performance › Testing Performance · Produtividade | Tests per product | Fora da escala | Fica fora de 0–1 e não tem sentido sem uma linha de produtos. |
| Process Performance › Testing Performance · Produtividade | Long tests | Repete M4 | É o complemento de Fast tests. |
| Process Performance › Testing Performance · Produtividade | Unit test duration | Repete M4 | Usa o mesmo dado de duração das suítes. |
| Process Performance › Development Speed · Produtividade | Avg. automation duration | Repete M4 | Tem o mesmo dado e a mesma fórmula. |
| Process Performance › Issues' Velocity · Produtividade | Issues-type in a timeframe | Repete Bug density | O tipo é livre; com Bug, repete Bug density. |
| Process Performance › Issues' Velocity · Produtividade | Bugs ratio | Repete Bug density | É o complemento de Bug density. |
| Process Performance › Issues' Velocity · Produtividade | Resolved issues assigned to a date (SEAA 2018) | Repete outras | Já é coberta por Resolved issues' throughput e Timely feature delivery. |
| Blocking › Quality Issues' Specification · Manutenibilidade (Q-Rapids) | Issues completely specified (SEAA 2018) | Repete M7 | É o mesmo conceito de M7 com o sinal invertido. |
| Blocking › Testing Status · Confiabilidade › Maturidade | Fast test builds (SEAA 2018) | Repete M4 | É igual a Fast tests do modelo de 2019. |

---

## 4. Resumo da seleção

Com as 10 métricas incluídas, Blocking e Product Readiness ficam com todas as suas características avaliadas. Product Quality cobre só Manutenibilidade, porque o projeto não tem dado de estabilidade em produção nem de uso.

| Indicador estratégico | Fatores avaliados | Características trabalhadas | Características sem métrica | Métricas incluídas |
|---|---|---|---|---|
| Product Quality | 1 de 3 | Manutenibilidade | Confiabilidade, Adequação funcional | M1, M2 |
| Blocking | 3 de 3 | Manutenibilidade, Confiabilidade | — | M3, M5, M6, M7 |
| Process Performance | 2 de 4 | Produtividade | Adequação funcional | M8, M9 |
| Product Readiness | 3 de 4 | Confiabilidade, Manutenibilidade, Produtividade | — | M10, DT, M1 e M2 (reuso) |

| Decisão | Quantidade |
|---|---:|
| Incluída | 10 |
| Monitorada | 8 |
| Habilitável | 8 |
| Excluída | 18 |
| **Total** | **44** |

Os fatores de processo (Issues' Velocity, Development Speed, Testing Performance, Activities Completion) não têm subcaracterística na ISO 25010, que só descreve qualidade de produto. Para eles, o Q-Rapids usa a característica Produtividade.

Enquanto o time não definir pesos, a agregação de fator e de indicador é a média simples das métricas na escala 0–1, como faz o dashboard.

---

## 5. Viés de linguagem e decisões pendentes

As métricas incluídas que vêm do SonarCloud reagem à linguagem. Por isso o plano nunca compara um repositório Python com um TypeScript na mesma métrica. M3, M7, M8, M9, M10 e DT não dependem da linguagem.

| Métrica incluída | Viés | Tratamento |
|---|---|---|
| M5 Test coverage | **Alto:** CLI, Core e Parser medem só linhas; os demais medem linhas e ramos | Ligar `branch = True` nos três e coletar `line_coverage` e `branch_coverage` antes de fixar a meta |
| M1 Complexity | **Médio:** em TS, cada callback conta como função e reduz a razão | Meta relativa à linha de base de cada repositório |
| M2 Duplication | **Médio:** código declarativo (JSX, tipos, serializers) repete estrutura | Meta relativa à linha de base de cada repositório |
| M6 Non-blocking files | **Médio:** as regras e severidades mudam por linguagem | Meta absoluta: zero blocker ou critical |

---

## Referências

FGA-EPS-MDS. **2026.2-MeasureSoftGram-Platform**. GitHub, 2026. Disponível em: <https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-Platform>. Acesso em: 7 nov. 2026.

FGA-EPS-MDS. **Analytics**: internal_quality_analysis-sonarqube.ipynb. GitHub, 2024. Disponível em: <https://github.com/fga-eps-mds/Analytics>. Acesso em: 7 nov. 2026.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 25010:2011**: systems and software engineering — systems and software Quality Requirements and Evaluation (SQuaRE) — system and software quality models. Geneva: ISO, 2011.

MARTÍNEZ-FERNÁNDEZ, S. *et al*. A quality model for actionable analytics in rapid software development. *In*: EUROMICRO CONFERENCE ON SOFTWARE ENGINEERING AND ADVANCED APPLICATIONS, 44., 2018, Praga. **Proceedings** [...]. [*S. l.*]: IEEE, 2018.

MARTÍNEZ-FERNÁNDEZ, S. *et al*. Continuously assessing and improving software quality with software analytics tools: a case study. **IEEE Access**, v. 7, p. 68219-68239, 2019.

Q-RAPIDS CONSORTIUM. **Q-Rapids Quality Model (April 2019)**. [*S. l.*]: Q-Rapids, 2019. Apêndice de Martínez-Fernández *et al*. (2019). Disponível em: <https://figshare.com/s/217851eed7ec1da7ab86>.

---

## Histórico de versão

| Versão | Data | Descrição | Autor | Revisor |
| --- | --- | --- | --- | --- |
| 1.0 | 08/11/2026 | Criacao do documento | [@storch7](https://github.com/storch7) |  |