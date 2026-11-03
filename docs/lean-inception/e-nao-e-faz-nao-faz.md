---
id: e-nao-e-faz-nao-faz
title: É - Não é - Faz - Não faz
sidebar_position: 3
---

# É — Não é — Faz — Não faz

Classificação construída na Lean Inception para definir fronteiras claras do
MeasureSoftGram em 2026.2, evitar desvios de escopo e concentrar o esforço no
que agrega valor ao usuário.

## Matriz

| É | Não é |
| --- | --- |
| Plataforma de gestão contínua da qualidade de software | Ferramenta de análise estática de código (não substitui o SonarQube) |
| Integrador de métricas com modelo matemático hierárquico | Sistema de gerenciamento de tarefas ou chamados |
| Calculador do indicador global de qualidade (TSQMI) | Substituto de pipelines de CI/CD (consome, não executa) |
| Ferramenta para apoio à tomada de decisão sobre releases | Ambiente de desenvolvimento (IDE) |

---

| Faz | Não faz |
| --- | --- |
| Coleta métricas de ferramentas externas (SonarQube) | Análise estática diretamente no código-fonte |
| Calcula índices ponderados por características e medidas | Gerenciamento de branches ou automação de git |
| Suporta múltiplos provedores de código (GitHub e GitLab) | Armazenamento de credenciais ou tokens em texto plano |
| Compara qualidade planejada versus realizada por release | Bloqueio direto de deploy sem integração configurada |

## Ajustes de escopo

- **Manter fora:** funcionalidades que pertencem a ferramentas parceiras (ex.:
  qualidade, code review, certificação de conformidade, coleta de métricas por
  conta própria e gestão de projeto/backlog.
- **Retirar:** disponibilização do plugin no VS Code. Confirmado pelo PO na
  [reunião de 07/10](/docs/reunioes/reunioes-po/ata-po-07-10).

## Impacto no projeto

A definição estrita de fronteiras evita retrabalho e foca a capacidade do time
nas histórias das ondas do [sequenciador](/docs/lean-inception/sequenciador).

## Histórico de versão

| Versão | Data | Descrição | Autor | Revisor |
| --- | --- | --- | --- | --- |
| 1.0 | 04/09/2026 | Criação durante a dinâmica da Lean Inception | [@LuizaMaluf](https://github.com/LuizaMaluf) |  |
| 1.1 | 21/10/2026 | Atualização com a retirada do plugin do VS Code | [@MilenaFRocha](https://github.com/MilenaFRocha) |  |
| 1.2 | 02/11/2026 | Atualiza link da ata de 07/10 para `reunioes-po` | [@luciano-freitas-melo](https://github.com/luciano-freitas-melo) |  |
