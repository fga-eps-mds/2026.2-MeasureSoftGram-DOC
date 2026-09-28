---
name: Defeito (Bug)
about: Relato de falha, anomalia ou regressão em comportamento já existente
title: '[BUGXX.YY] '
labels: bug
assignees: ''
---

<!--
================================================================================
PADRONIZAÇÃO HIERÁRQUICA DO TÍTULO:
Formato: [BUGXX.YY] Descrição Sucinta da Falha
- 'XX': Número do Épico pai com dois dígitos (ex: 01, 02...).
        Caso seja um defeito legado/transversal sem épico direto, utilize '00'.
- 'YY': Número sequencial do defeito com dois dígitos dentro do Épico (ex: 01, 02, 03...).
Exemplo: Para o 1º bug vinculado ao Épico 01 [MSG01]:
-> [BUG01.01] Correção de piscamento no menu lateral
Para um defeito geral:
-> [BUG00.01] Falha de autenticação ao recarregar a página
================================================================================
-->

## 1. Descrição do Defeito

<!--
Resuma o defeito em uma ou duas frases de forma clara e objetiva.
-->

[Descrição sucinta da anomalia identificada]

---

## 2. Passos para Reproduzir

<!--
Indique o passo a passo exato e ordenado para reproduzir o problema:
-->

1. Acessar a página/rota [...]
2. Clicar no botão [...]
3. Selecionar o item [...]
4. Observar a ocorrência do erro [...]

---

## 3. Comportamento Esperado vs. Observado

* **Comportamento Esperado:** [O que o sistema deveria fazer de acordo com as regras acordadas]
* **Comportamento Observado:** [O que o sistema realmente fez ou exibiu (erro, travamento, cálculo divergente)]

---

## 4. Evidências

<!--
Anexe prints de tela, gravações (GIF/vídeo), payloads de requisições, respostas de API ou logs de console/terminal.
-->

[Anexe as evidências aqui]

---

## 5. Ambiente e Severidade

| Item | Descrição / Valor |
| :--- | :--- |
| **Repositório / Serviço** | [ex: frontend, service, core] |
| **Ambiente de Ocorrência** | [Local / Homologação (develop) / Produção] |
| **Navegador / SO** | [ex: Chrome 128 / Linux Ubuntu 22.04] |
| **Severidade** | [Bloqueante / Alta / Média / Baixa] |

---

<!--
================================================================================
ATENÇÃO: IMPACTO EM COMPORTAMENTO FUNCIONAL
Caso a correção deste bug altere o fluxo ou comportamento de interface para o usuário final,
DESCOMENTE o bloco abaixo e alinhe a nova expectativa com o PO:
Consulte: https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/backlog#2-regra-de-ouro-alterações-em-comportamento-funcional
================================================================================
-->

<!--
## 6. Critérios de Aceitação (Impacto Funcional)

### Cenário 1: [Título do Cenário de Comportamento Corrigido]
* **Dado** que [contexto prévio / estado inicial]
* **Quando** [ação realizada pelo usuário]
* **Então** [comportamento corrigido esperado]
-->

---

## 6. Configuração no ZenHub (DoR de Metadados)

<!--
ATENÇÃO: Este checklist deve ser marcado diretamente no card após configurar os metadados nativos no ZenHub:
-->
- [ ] Estimativa de esforço pontuada no card
- [ ] Desenvolvedores e integrantes do Squad atribuídos aos **Assignees**
- [ ] Issue Type configurado como **Bug** no ZenHub
- [ ] Labels dos repositórios que serão alterados adicionadas (ex: Service, Core, Frontend)
- [ ] Épico pai vinculado (caso pertença a um Épico de Correção/Manutenção)
- [ ] Sprint correspondente associada

---

## 7. Definição de Pronto (DoD)

<!--
Checklist obrigatório de qualidade para mover este card para Closed / Done:
-->
- [ ] Defeito corrigido e verificado: não mais se reproduz seguindo os passos descritos
- [ ] Teste automatizado de regressão implementado para garantir que a falha não reapareça
- [ ] Código aderente aos padrões de linter e arquitetura
- [ ] Pipeline de CI/CD executado com sucesso no repositório central
- [ ] Pull Request (PR) revisado e aprovado por pelo menos um integrante
- [ ] Código integrado à branch `develop` do repositório central
- [ ] Documentação técnica ou guias atualizados no `2026.2-Docs` e/ou `Docs` (quando aplicável)

<!--
DESCOMENTE OS ITENS ABAIXO CASO A CORREÇÃO TENHA IMPACTO FUNCIONAL VISÍVEL:
- [ ] Todos os cenários BDD demonstrados e aprovados
- [ ] Correção validada e homologada pelo Product Owner na branch develop
-->
