---
name: História de Usuário (US)
about: Demanda funcional com entrega direta de valor de negócio ao usuário final
title: '[USXX.YY] '
labels: US
assignees: ''
---

<!--
================================================================================
PADRONIZAÇÃO HIERÁRQUICA DO TÍTULO:
Formato: [USXX.YY] Nome da História
- 'XX': Número do Épico pai com dois dígitos (ex: 01, 02...).
- 'YY': Número sequencial da US com dois dígitos dentro do Épico (ex: 01, 02, 03...).
Exemplo: Para a 1ª História de Usuário vinculada ao Épico 01 [MSG01]:
-> [US01.01] Visualizar histórico do TSQMI
================================================================================
-->

## 1. Descrição da História

<!--
Descreva a necessidade funcional sob a perspectiva do usuário final/persona.
Evite termos técnicos ou decisões de arquitetura nesta seção.
-->

**Como** [persona / papel do usuário, ex: Desenvolvedor, PO, Gestor de Qualidade]  
**Quero** [ação / objetivo funcional]  
**Para que** [benefício ou valor de negócio alcançado]  

---

## 2. Protótipo e Interface

<!--
Insira o link para o frame correspondente no Figma ou anexe prints do protótipo de alta fidelidade.
Caso esta US não envolva alterações na interface gráfica, registre: "Não se aplica (sem interface gráfica)".
-->

- [ ] [Link para o frame no Figma](https://www.figma.com/...)

---

## 3. Critérios de Aceitação (BDD Obrigatório)

<!--
Os Critérios de Aceitação definem O QUE o sistema deve fazer sob a ótica de negócio.
OBRIGATÓRIO: Redigir exclusivamente em formato BDD (Dado / Quando / Então).
ATENÇÃO: Cenários devem ser alinhados e validados previamente com o Product Owner.
-->

### Cenário 1: [Título do Cenário de Sucesso]
* **Dado** que [contexto prévio / estado inicial do sistema]
* **Quando** [ação realizada pelo usuário]
* **Então** [resultado esperado observável]

### Cenário 2: [Título do Cenário de Exceção ou Alternativo]
* **Dado** que [contexto prévio]
* **Quando** [ação ou condição de erro]
* **Então** [tratamento ou feedback esperado]

---

## 4. Critérios Técnicos, Restrições e Dependências

<!--
Os Critérios Técnicos definem COMO a solução será construída internamente pelos desenvolvedores.
Liste endpoints, contratos de API, microsserviços afetados, padrões de código, restrições e dependências.
-->

- **Repositórios / Serviços afetados:** [ex: MeasureSoftGram-Service, msgram-core, frontend]
- **Endpoints e contratos:** [ex: GET /api/v1/metrics/tsqmi]
- **Diretrizes de implementação:** [ex: uso de SWR com mutate, tipagem estrita com TypeScript]
- **Restrições:** [ex: compatibilidade, performance, limitação de API]
- **Dependências:** [ex: dependência de outra US, serviço ou pacote]

---

## 5. Configuração no ZenHub (DoR de Metadados)

<!--
ATENÇÃO: Este checklist deve ser marcado diretamente no card após configurar os metadados nativos no ZenHub:
-->
- [ ] Estimativa de esforço pontuada no card (Story Points via Planning Poker)
- [ ] Desenvolvedores e integrantes do Squad atribuídos aos **Assignees**
- [ ] Issue Type configurado como **Feature** no ZenHub
- [ ] Labels dos repositórios que serão alterados adicionadas (ex: Service, Core, Frontend)
- [ ] Épico pai vinculado (Parent Epic)
- [ ] Sprint correspondente associada

---

## 6. Definição de Pronto (DoD)

<!--
Checklist obrigatório de qualidade para mover este card para Closed / Done:
-->
- [ ] Código implementado aderente aos Critérios Técnicos e convenções de estilo/linter
- [ ] Testes automatizados implementados e executados com sucesso (unitários e/ou integração)
- [ ] Pipeline de CI/CD executado com sucesso no repositório central
- [ ] Pull Request (PR) revisado e aprovado por pelo menos um integrante da equipe
- [ ] Código integrado à branch `develop` do repositório central (ambiente de homologação)
- [ ] Todos os cenários BDD demonstrados e validados
- [ ] Interface validada em conformidade com o protótipo do Figma (quando aplicável)
- [ ] **Funcionalidade validada e homologada pelo Product Owner na branch `develop`**
- [ ] Documentação atualizada (no `2026.2-Docs` e/ou `Docs`, quando aplicável)
