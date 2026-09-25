---
name: Task Técnica (Engenharia)
about: Atividade técnica, arquitetural, de infraestrutura, pipeline ou sustentação
title: '[TASKXX.YY] '
labels: task
assignees: ''
---

<!--
================================================================================
PADRONIZAÇÃO HIERÁRQUICA DO TÍTULO:
Formato: [TASKXX.YY] Nome da Tarefa
- 'XX': Número do Épico pai com dois dígitos (ex: 01, 02...).
        Caso seja uma tarefa técnica transversal/avulsa sem épico direto, utilize '00'.
- 'YY': Número sequencial da tarefa com dois dígitos dentro do Épico (ex: 01, 02, 03...).
Exemplo: Para a 2ª tarefa técnica vinculada ao Épico 01 [MSG01]:
-> [TASK01.02] Otimizar requisições SWR no frontend
Para uma tarefa transversal/geral:
-> [TASK00.01] Atualizar dependências globais do repositório
================================================================================
-->

## 1. Objetivo Técnico e Motivação

<!--
Descreva claramente O QUE precisa ser feito tecnicamente e POR QUÊ.
Explique qual benefício arquitetural, de sustentação, performance ou segurança esta tarefa entrega.
-->

[Descreva a motivação técnica e o objetivo desta implementação]

---

## 2. Escopo e Repositórios Afetados

<!--
Mapeie exatamente as fronteiras técnicas da tarefa:
- Repositórios e microsserviços impactados
- Pacotes, arquivos principais ou contratos de banco de dados
-->

- **Repositórios afetados:** [ex: MeasureSoftGram-Service / msgram-frontend / 2026.2-Docs / Docs]
- **Arquivos/Contratos principais:** [ex: src/services/swrConfig.ts, Dockerfile]

---

## 3. Critérios Técnicos de Execução

<!--
Liste os requisitos e etapas técnicas detalhadas para a realização da tarefa.
-->

- [ ] [Requisito técnico 1: ex. Adicionar cache no endpoint X]
- [ ] [Requisito técnico 2: ex. Configurar workflow do GitHub Actions no repositório central]
- [ ] [Requisito técnico 3: ex. Atualizar dependências e corrigir avisos de tipagem]

---

<!--
================================================================================
ATENÇÃO: IMPACTO EM COMPORTAMENTO FUNCIONAL
Caso esta tarefa implique em QUALQUER alteração de comportamento visível para o usuário,
mudança de fluxo ou de regra de negócio, DESCOMENTE o bloco abaixo e alinhe com o PO:
Consulte: https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/backlog#2-regra-de-ouro-alterações-em-comportamento-funcional
================================================================================
-->

<!--
## 4. Critérios de Aceitação (Impacto Funcional)

### Cenário 1: [Título do Cenário de Comportamento Alterado]
* **Dado** que [contexto prévio / estado inicial]
* **Quando** [ação realizada pelo usuário]
* **Então** [novo comportamento esperado alinhado com o PO]
-->

---

## 4. Configuração no ZenHub (DoR de Metadados)

<!--
ATENÇÃO: Este checklist deve ser marcado diretamente no card após configurar os metadados nativos no ZenHub:
-->
- [ ] Estimativa de esforço pontuada no card (Story Points)
- [ ] Desenvolvedores e integrantes do Squad atribuídos aos **Assignees**
- [ ] Issue Type configurado como **Task** no ZenHub
- [ ] Labels dos repositórios que serão alterados adicionadas (ex: Service, Core, Frontend)
- [ ] Épico pai vinculado (Parent Epic de Correção ou Feature)
- [ ] Sprint correspondente associada

---

## 5. Definição de Pronto (DoD)

<!--
Checklist obrigatório de qualidade para mover este card para Closed / Done:
-->
- [ ] Código implementado estritamente aderente aos Critérios Técnicos acordados
- [ ] Conformidade com linter, padrões de código e diretrizes arquiteturais
- [ ] Testes automatizados cobrindo a alteração implementados e aprovados
- [ ] Pipeline de CI/CD executado com sucesso no repositório central
- [ ] Pull Request (PR) revisado e aprovado por pelo menos um integrante
- [ ] Código integrado à branch `develop` do repositório central
- [ ] Documentação técnica ou de governança atualizada no `2026.2-Docs` e/ou `Docs` (quando aplicável)

<!--
DESCOMENTE OS ITENS ABAIXO CASO A TAREFA TENHA IMPACTO FUNCIONAL VISÍVEL:
- [ ] Todos os cenários BDD demonstrados e aprovados
- [ ] Funcionalidade validada e homologada pelo Product Owner na branch develop
-->
