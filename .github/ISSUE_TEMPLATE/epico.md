---
name: Épico
about: Entrega macro de valor (Funcionalidade ou Manutenção/Dívida Técnica)
title: '[MSGXX] '
labels: epico
assignees: ''
---

<!--
================================================================================
PADRONIZAÇÃO DO TÍTULO DO ÉPICO:
Formato: [MSGXX] Nome do Épico
- Substitua 'XX' pelo número sequencial com dois dígitos do Épico (ex: 01, 02, 03...).
Exemplo:
-> [MSG01] Operacionalizar a Medição de Dívida Técnica
================================================================================
-->

## 1. Tipo de Épico

<!--
Marque uma das opções abaixo:
-->
- [ ] **Épico de Funcionalidade (Feature):** Nova capacidade percebida pelo usuário (requer alinhamento obrigatório com o PO).
- [ ] **Épico de Correção / Dívida Técnica:** Saneamento arquitetural, infraestrutura, performance ou pipelines.

---

## 2. Objetivo e Dor Resolvida

<!--
Para Funcionalidade: Qual dor da persona resolve e qual valor gera ao produto?
Para Correção: Qual diagnóstico técnico ou gargalo arquitetural motivou este épico?
-->

[Descreva o objetivo macro e a motivação do épico]

---

## 3. Escopo e Fronteiras de Não-Escopo

### O que FAZ parte deste épico (Escopo)
- [Item 1 do escopo]
- [Item 2 do escopo]

### O que NÃO FAZ parte deste épico (Não-Escopo Obrigatório)
<!--
Evite scope creep: registre explicitamente o que não será feito, refatorações que serão ignoradas e limites de atuação.
-->
- [Não-escopo 1]
- [Não-escopo 2]

---

## 4. Metas e Critérios de Sucesso

<!--
Como saberemos que este épico funcionou? (ex: métricas de tempo de resposta, estabilidade de pipeline, fluxo operacional no PO)
-->

- [ ] [Critério de sucesso / Métrica esperada]

---

## 5. Configuração no ZenHub (DoR de Metadados)

- [ ] Épico cadastrado no ZenHub (Convert to Epic / Create Epic)
- [ ] Integrantes do Squad atribuídos aos **Assignees**
- [ ] Validação prévia com o PO realizada (se for Épico de Funcionalidade)
- [ ] Decomposição preliminar em itens filhos vinculados (US, Tasks ou Bugs)

---

## 6. Definição de Pronto (DoD de Épico)

- [ ] 100% dos itens filhos vinculados (US, Tasks e Bugs) concluídos e fechados no ZenHub
- [ ] Fluxo integrado ponta a ponta validado sem regressões no ambiente de homologação (`develop`)
- [ ] **Demonstração e homologação do fluxo completo aprovadas pelo Product Owner** (para Épico de Funcionalidade)
- [ ] **Atingimento das metas técnicas comprovado por métricas** (para Épico de Correção)
- [ ] Documentação de arquitetura, governança ou guias de usuário atualizados no `2026.2-Docs` e/ou `Docs`
