# Atividade 8

## Dimensionamento das Atividades

Esta é a atividade central de dimensionamento. Em vez de horas, as tarefas são comparadas **umas com as outras** em termos de esforço.

### Montagem do canvas

```
 ┌──────────────────────────────────┐
 │  G   ▢ ▢                         │  ← mais esforço
 │                                  │
 │  M   ▢ ▢ ▢                       │
 │                                  │
 │  P   ▢ ▢ ▢ ▢                     │  ← menos esforço
 └──────────────────────────────────┘
```

### Passo a passo utilizado

1. Escreve-se os tamanhos **P**, **M** e **G** em post-its e posicioná-los verticalmente no canvas (G no alto, P embaixo, M entre eles).
2. Pega-se duas tarefas e perguntar: *comparando o esforço, como uma se relaciona com a outra?*
3. Posicioná-se: **lado a lado** se exigem esforço equivalente; **uma acima da outra** se uma exige mais.
4. Delimita-se as fronteiras entre P, M e G e reposicionar tarefas quando necessário.
5. Se surgirem tarefas muito menores ou muito maiores que as demais, criar os tamanhos **XP** ou **XG**.
6. Repeti-se até que todas as tarefas da amostra estejam no canvas.

**Resultado:** cada tarefa associada a um tamanho de camiseta.

## Conversão de tamanho em tempo

Cada tamanho recebeu uma duração média.

1. Escolheu-se uma tarefa **P** e perguntar quanto tempo leva para ser concluída.
2. Repetiu-se a pergunta para mais duas ou três tarefas do mesmo tamanho.
3. Calculou-se a média e registrá-la.
4. Repetiu-se para M, G (e XP/XG, se existirem).

### Como fazer a pergunta

A estimativa individual de prazo pode gerar maior variabilidade nas respostas. Como alternativa, recomenda-se considerar uma **dupla heterogênea**, composta por pessoas com diferentes níveis de experiência e conhecimentos complementares, como domínio do negócio e conhecimento técnico. A partir disso, a estimativa deve considerar a seguinte questão: **quanto tempo essa dupla levaria para concluir a tarefa?**

Caso a descrição de uma tarefa gere dúvidas ou dificuldades durante a estimativa, recomenda-se revisá-la, tornando-a mais clara, ou dividi-la em partes menores e mais bem definidas.


| Tamanho | Tempo médio estimado (dupla) |
|---|---|
| P | *definido pelo time* |
| M | *definido pelo time* |
| G | *definido pelo time* |
| XG *(opcional)* | *definido pelo time* |

## Média por onda e projeção

Com o tempo de cada tamanho definido:

1. Somou-se o tempo das tarefas de cada funcionalidade.
2. Somou-se o tempo das funcionalidades de cada onda de amostra.
3. Calculou-se a **média de esforço por onda** (em pessoa·tempo ou dupla·tempo).

A partir dessa média, as projeções seguem diretamente:

```
Esforço até o MVP     = média por onda × nº de ondas até o MVP
Duração no calendário ≈ esforço até o MVP ÷ nº de duplas disponíveis
Custo estimado        = esforço até o MVP × custo por dupla·dia
```

## Descrição

Seguindo as etapas e os procedimentos descritos anteriormente, o grupo realizou as atividades de forma colaborativa, considerando os critérios e orientações estabelecidos ao longo do processo. Como resultado da aplicação dessas etapas, foram obtidos os seguintes resultados para as funcionalidades analisadas:

# INSERIR O IFRAME

## Referência

CAROLI, Paulo. **Lean Inception**: como alinhar pessoas e construir o produto certo. São Paulo: Editora Caroli, 2018.

## Histórico de Versão

| Alteração | Data | Autor | 
| - | - | - |
| Criação do documento | 26/09/2026 | [Guilherme Storch](https://github.com/storch7) |