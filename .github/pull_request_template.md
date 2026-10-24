<!--
Título do PR no padrão de commit, com o código da issue:
  feat(front): [US11.01] login com GitLab
  fix(service): [BUG05.03] invalida o token no logout
Fluxo completo: https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/processo/fluxo-de-trabalho/
PR com CI vermelha não é revisado.
-->

## Issue

<!-- Use "Refs" quando a issue depende de aprovação do PO (ela é fechada só depois da validação).
     Use "Closes" apenas para tasks e bugs sem impacto funcional. -->
Refs fga-eps-mds/2026.2-MeasureSoftGram-DOC#<!-- número -->

## Etapa do fluxo

- [ ] 1. Branch de trabalho → `develop` do fork `2026.2-*`
- [ ] 2. `develop` do fork → `develop` do repositório central (liste as issues incluídas abaixo)
- [ ] 3. `develop` → `main` do repositório central (release `vX.Y.Z`)

## O que muda e por quê

<!-- 2 a 5 frases: o problema, a solução escolhida e alternativas descartadas, se houver. -->

## Tipo de mudança

- [ ] `feat` nova funcionalidade
- [ ] `fix` correção de defeito
- [ ] `refactor` sem mudança de comportamento
- [ ] `test` · `docs` · `ci` · `build` · `chore`
- [ ] Muda comportamento visível para o usuário (exige validação do PO)

## Como testar

<!-- Passo a passo que qualquer pessoa da equipe consiga seguir sem perguntar ao autor. -->

1.
2.
3.

## Evidências

<!-- Prints, GIF, logs, saída dos testes ou link da homologação. -->

## Impacto na qualidade

- Testes adicionados ou alterados: <!-- quais -->
- Quality gate do SonarCloud: <!-- aprovado / reprovado (motivo) -->
- Problemas novos apontados pelo SonarCloud: <!-- nenhum / quais e por que ficam -->

## Checklist do autor

- [ ] Branch e commits seguem o padrão (`tipo/CODIGO-descricao`, Conventional Commits).
- [ ] A CI está verde (lint, build, testes, SonarCloud).
- [ ] Os critérios de aceitação da issue estão atendidos.
- [ ] A documentação afetada foi atualizada.
- [ ] Sei explicar qualquer trecho deste PR em revisão síncrona.
- [ ] Uso relevante de IA registrado no meu `MD_Template.md` (ou não houve).

## Checklist do revisor

- [ ] Li a issue e os critérios de aceitação antes do código.
- [ ] Testei seguindo o "Como testar" (ou na homologação).
- [ ] O código é compreensível e segue os padrões do repositório.
- [ ] Há testes para a mudança.
- [ ] A revisão foi feita por mim, não por uma ferramenta de IA.
