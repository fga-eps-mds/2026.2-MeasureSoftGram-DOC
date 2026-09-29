"""Queries GraphQL da API pública do Zenhub.

Todos os campos abaixo foram conferidos no schema público publicado pelo Zenhub
(https://developers.zenhub.com/schema/zenhub-public-api.graphql, lido em
27/09/2026) e validados contra ele com ``graphql.validate`` — ver
``docs/metricas/velocity-zenhub.mdx``. Nenhum nome de campo foi suposto.

Limites que moldam as queries (https://developers.zenhub.com/graphql-api-docs/):

* paginação Relay (``first``/``after``, ``pageInfo { hasNextPage endCursor }``),
  no máximo 100 por página;
* complexidade máxima de 200 pontos por query: cada campo e cada objeto vale 1 e
  uma conexão multiplica os filhos pelo ``first``. Por isso cada query pede uma
  conexão só, com poucos campos, e o tamanho de página é uma variável que o
  cliente reduz sozinho se o Zenhub reclamar de complexidade.
"""

# Sprints do workspace, da mais antiga para a mais recente.
# ~10 pontos por sprint -> first <= 18.
SPRINTS = """
query Sprints($workspaceId: ID!, $first: Int!, $after: String) {
  workspace(id: $workspaceId) {
    sprints(first: $first, after: $after, orderBy: {field: START_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        name
        generatedName
        state
        startAt
        endAt
        totalPoints
        completedPoints
        closedIssuesCount
      }
    }
  }
}
"""

# Issues que estão AGORA na sprint (escopo atual). ~25 pontos por issue (com responsáveis e criação:
# as issues fechadas saem do quadro e só aqui trazem quem foi o responsável).
SPRINT_ISSUES = """
query SprintIssues($sprintId: ID!, $workspaceId: ID!, $first: Int!, $after: String) {
  node(id: $sprintId) {
    ... on Sprint {
      issues(first: $first, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          number
          title
          state
          closedAt
          htmlUrl
          pullRequest
          repository { name }
          estimate { value }
          issueType {
            ... on GithubIssueType { name }
            ... on ZenhubIssueType { name }
          }
          parentIssue { id }
          createdAt
          assignees(first: 10) { nodes { login name } }
          pipelineIssue(workspaceId: $workspaceId) {
            latestTransferTime
            pipeline { name }
          }
        }
      }
    }
  }
}
"""

# Histórico de escopo da sprint: cada entrada/saída de issue, com data e a
# estimativa no momento do evento. É o que permite reconstituir o planejado
# no início da sprint sem usar o estado atual. ~8 pontos por evento.
SPRINT_SCOPE_CHANGES = """
query SprintScopeChanges($sprintId: ID!, $first: Int!, $after: String) {
  node(id: $sprintId) {
    ... on Sprint {
      scopeChange(first: $first, after: $after) {
        pageInfo { hasNextPage endCursor }
        totalCount
        nodes {
          action
          effectiveAt
          estimateValue
          issue {
            id
            number
            title
            repository { name }
          }
        }
      }
    }
  }
}
"""

# Detalhe de uma issue pelo id — para as issues que passaram pela sprint mas já
# saíram dela (aparecem só no scopeChange, sem tipo, estado nem estimativa).
ISSUE = """
query Issue($issueId: ID!, $workspaceId: ID!) {
  node(id: $issueId) {
    ... on Issue {
      id
      number
      title
      state
      closedAt
      htmlUrl
      pullRequest
      repository { name }
      estimate { value }
      issueType {
        ... on GithubIssueType { name }
        ... on ZenhubIssueType { name }
      }
      parentIssue { id }
      createdAt
      assignees(first: 10) { nodes { login name } }
      pipelineIssue(workspaceId: $workspaceId) {
        latestTransferTime
        pipeline { name }
      }
    }
  }
}
"""

# Releases (Release Reports) do workspace. ~8 pontos por release.
RELEASES = """
query Releases($workspaceId: ID!, $first: Int!, $after: String) {
  workspace(id: $workspaceId) {
    releases(first: $first, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        title
        state
        startOn
        endOn
        closedAt
        issuesCount
      }
    }
  }
}
"""

# Issues de uma release (para ligar sprint -> release pelas issues).
RELEASE_ISSUES = """
query ReleaseIssues($releaseId: ID!, $first: Int!, $after: String) {
  node(id: $releaseId) {
    ... on Release {
      issues(first: $first, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id }
      }
    }
  }
}
"""

# ───────────────────────── backlog (quadro inteiro) ─────────────────────────
#
# As queries acima só enxergam o que passou por uma sprint. Para o backlog
# (itens planejados, prioridade, épico, responsável) a coleta percorre todos os
# pipelines do workspace. ATENÇÃO: estas duas queries NÃO foram validadas
# contra o schema no ambiente em que foram escritas (sem acesso à rede do
# Zenhub). A coleta trata falha nelas como aviso: a velocity continua, e a
# página do Zenhub diz que o backlog completo está indisponível. Validar com
# ``python scripts/diagnostico_zenhub.py`` antes de confiar nos números.

PIPELINES = """
query Pipelines($workspaceId: ID!, $first: Int!, $after: String) {
  workspace(id: $workspaceId) {
    pipelinesConnection(first: $first, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { id name }
    }
  }
}
"""

# Issues abertas de um pipeline. ~25 pontos por issue -> first <= 7.
PIPELINE_ISSUES = """
query PipelineIssues($pipelineId: ID!, $workspaceId: ID!, $first: Int!, $after: String) {
  searchIssuesByPipeline(pipelineId: $pipelineId, filters: {}, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    totalCount
    nodes {
      id
      number
      title
      state
      createdAt
      closedAt
      htmlUrl
      pullRequest
      repository { name }
      estimate { value }
      issueType {
        ... on GithubIssueType { name }
        ... on ZenhubIssueType { name }
      }
      parentIssue { id }
      assignees(first: 10) { nodes { login name } }
      pipelineIssue(workspaceId: $workspaceId) {
        latestTransferTime
        pipeline { name }
        priority { name }
      }
    }
  }
}
"""

TODAS = {
    "SPRINTS": SPRINTS,
    "SPRINT_ISSUES": SPRINT_ISSUES,
    "SPRINT_SCOPE_CHANGES": SPRINT_SCOPE_CHANGES,
    "ISSUE": ISSUE,
    "RELEASES": RELEASES,
    "RELEASE_ISSUES": RELEASE_ISSUES,
    "PIPELINES": PIPELINES,
    "PIPELINE_ISSUES": PIPELINE_ISSUES,
}
