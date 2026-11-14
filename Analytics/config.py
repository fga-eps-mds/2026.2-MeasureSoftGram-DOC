"""Configuração do dashboard — o único arquivo que o time precisa editar.

Cada informação vem da fonte mais adequada:

* **SonarCloud** — qualidade do código. Duas entradas: os ``.json`` que o
  ``metrics.yml`` de cada repositório publica em ``data/`` (base da nota de
  qualidade do notebook da disciplina) e o snapshot da API do SonarCloud
  (``scripts/coleta_sonar.py`` → ``data/sonar/``, workflow ``coleta-dados.yml``),
  com métricas agregadas, histórico, Quality Gate, issues e medidas por arquivo
  (``api/measures/component_tree``).
* **Zenhub** — sprints, pontos, backlog, épicos, releases
  (``scripts/coleta_velocity.py`` → ``data/zenhub/velocity/``).
* **Planilha** — só o que nem o Sonar nem o Zenhub têm: custos, quem está no
  time em cada semana, horas, riscos e decisões.

Nenhum token fica aqui. ``ZENHUB_API_KEY`` e ``SONAR_TOKEN`` (opcional: os
projetos do SonarCloud são públicos) ficam em ``Analytics/.env`` ou nos secrets
do GitHub. Ver ``.env.example``.
"""

# ───────────────────────── planilha do time ─────────────────────────
# Para cada aba: Arquivo > Compartilhar > Publicar na Web > escolher a aba >
# "Valores separados por vírgula (.csv)" > Publicar, e colar o link na chave.
# Não há cópia local: aba sem URL (ou que não responde) aparece como indisponível.
# No GitHub Pages o deploy baixa as abas publicadas e empacota junto do app.

PLANILHAS = {
    "custos": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=668960529&single=true&output=csv",
    "planejamento": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=1362167559&single=true&output=csv",
    "horas": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=874852730&single=true&output=csv",
    "riscos": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=844810192&single=true&output=csv",
    "monitoramento": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=546490889&single=true&output=csv",
    "decisoes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=2101696466&single=true&output=csv",
}

# Planilha original (edição) — só para os links "ver na planilha"; o painel lê a versão publicada acima.
# Quem abre o link precisa ter acesso à planilha no Google (as permissões são as do Google).
PLANILHA_ID_EDICAO = "1iucrFAgDsj8adfkzzcUfnMIkJwoAVVHPLkpdJ8lDSHc"

CACHE_PLANILHAS_S = 300  # a planilha publicada é relida a cada 5 minutos

# Regras do time usadas no cálculo da velocity (antes em planilhas/parametros.csv).
PARAMETROS = {
    # Critério de feito: a issue só precisa estar FECHADA (closedAt) — fixo no código, sem pipeline.
    # DA-R3.02 (ata R2, ação C1.2): Velocity, SPI e CPI contam só Story Points de US (Feature) aceitas pelo PO.
    # Tasks, Sub-tasks e Bugs saem do cálculo e são acompanhados pelas métricas de fluxo (página Fluxo).
    "niveis_pontuados": "Feature",
    "janela_planning_horas": "24",             # planejado = escopo da sprint ao fim do 1º dia (planning)
    "min_sprints_media_velocity": "2",         # velocity média só com pelo menos 2 sprints concluídas
    "sprints_canceladas": "",                  # ids de sprint separados por ";"
    # Prazo de fechamento: issue fechada até esta hora (Brasília) do dia seguinte ao último dia da
    # sprint ainda conta nela (e na release dela). Vazio = só até o fim da sprint no Zenhub.
    "prazo_fechamento_dia_seguinte": "08:00",
}

# Métricas de fluxo (página Fluxo; DA-R3.02, ata R2 ação C1.4).
FLUXO = {
    # Cycle Time = fechamento − primeira entrada neste pipeline do Zenhub (histórico de transferências).
    "pipeline_inicio": "In Progress",
    # Card movido para o pipeline de início menos de N minutos antes de fechar é movimentação de cadastro, não
    # trabalho: fica fora do Cycle Time (continua no Lead Time e no Throughput) e é contado na tela.
    "cycle_minimo_min": 5,
}

# ───────────────────────── SonarCloud ─────────────────────────

SONAR_URL = "https://sonarcloud.io"
SONAR_ORGANIZACAO = "fga-eps-mds"
SONAR_BRANCH = "develop"
# Chaves dos projetos no SonarCloud. Vazio = descobrir pela API (projetos da
# organização cujo nome contém SONAR_BUSCA).
SONAR_PROJETOS: list[str] = [
    "fga-eps-mds_2026.2-MeasureSoftGram-Action",
    "fga-eps-mds_2026.2-MeasureSoftGram-AI",
    "fga-eps-mds_2026.2-MeasureSoftGram-CLI",
    "fga-eps-mds_2026.2-MeasureSoftGram-Core",
    "fga-eps-mds_2026.2-MeasureSoftGram-Front",
    "fga-eps-mds_2026.2-MeasureSoftGram-Parser",
    "fga-eps-mds_2026.2-MeasureSoftGram-Plugin",
    "fga-eps-mds_2026.2-MeasureSoftGram-Service",
]
SONAR_BUSCA = "2026.2-MeasureSoftGram"

# ───────────────────────── GitHub Actions ─────────────────────────
# Repositórios cujas execuções de CI o dashboard coleta direto da API do GitHub
# (scripts/coleta_github.py). Execuções criadas a partir de INICIO_SEMESTRE.
GITHUB_ORG = "fga-eps-mds"
# O repositório 2026.2-MeasureSoftGram-docs-eps foi renomeado para -DOC: a API do GitHub redireciona o nome
# antigo, então coletar os dois duplicava todas as execuções da documentação. Fica só o nome novo.
GITHUB_REPOS: list[str] = [k.split("_", 1)[1] for k in SONAR_PROJETOS] + ["2026.2-MeasureSoftGram-DOC"]

# Repositórios do projeto: só os do semestre 2026.2 entram no painel. Os .json que chegam em data/ de
# outros repositórios (ex.: os centrais fga-eps-mds/MeasureSoftGram-*, cujo metrics.yml também grava aqui)
# e as issues do Zenhub desses repositórios ficam fora de TODAS as métricas (Sonar, GitHub, Zenhub, EVM e
# qualidade); aparecem só em "Metodologia e Fontes" como ignorados. Vazio = não filtra.
PREFIXO_REPOS_PROJETO = "2026.2-MeasureSoftGram-"
APELIDOS_REPO = {"2026.2-MeasureSoftGram-docs-eps": "2026.2-MeasureSoftGram-DOC"}   # nome antigo -> atual

# ───────────────────────── calendário e metas ─────────────────────────
# Datas de entrega do plano de ensino (EPS 2026.2).

RELEASES = {"R1": "2026-09-28", "R2": "2026-10-26", "R3": "2026-11-30"}
INICIO_SEMESTRE = "2026-08-24"
RELEASE_FINAL = "2026-12-07"   # Release Final (aceitação e defesas orais): nenhum prazo passa daqui

# Metas de qualidade por release (critérios enviados pelo professor, ver
# docs/disciplina/avaliacao.mdx). Metas de gestão: SPI e CPI >= 0,95.
METAS = {
    "coverage": {"R1": 85.0, "R2": 85.0, "R3": 90.0},
    "duplicated_lines_density": {"R1": 5.0, "R2": 5.0, "R3": 3.0},
}
RISCO_ELEVADO = 15   # P × I a partir do qual o risco é elevado (escala do plano de riscos)
RISCO_MEDIO = 6      # P × I a partir do qual o risco é médio
METAS_DECISOES = {"R2": 3, "R3": 5}   # decisões baseadas em dados registradas (plano de ensino)
META_INDICE_EVM = 0.95   # SPI/CPI abaixo disso = atenção
LIMITE_INDICE_CRITICO = 0.80   # SPI/CPI abaixo disso = crítico
META_TAXA_CONCLUSAO = 80.0     # % de SP concluídos ÷ planejados nas sprints concluídas
LIMITE_TAXA_CRITICO = 60.0     # abaixo disso = crítico
META_CI_SUCESSO = 95.0   # % de execuções da CI com sucesso (metas.mdx, M10: meta ≥ 0,95)
LIMITE_CI_CRITICO = 60.0 # abaixo disso = crítico

# ───────────────────────── modelo de qualidade Q-Rapids ─────────────────────────
# As fórmulas por arquivo preservam o notebook de referência. Os pesos legados são usados
# somente pela avaliação de compatibilidade em qualidade.py e seus testes; não compõem os
# quatro indicadores estratégicos. As decisões e metas do plano estão abaixo.
QRAPIDS = {
    # linguagem dos arquivos de código que entram no cálculo de cada repositório (como repos_language
    # no notebook). Arquivos de outra linguagem (yaml, css, shell...) ficam de fora.
    "linguagem": {
        "2026.2-MeasureSoftGram-AI": "py", "2026.2-MeasureSoftGram-Action": "ts",
        "2026.2-MeasureSoftGram-CLI": "py", "2026.2-MeasureSoftGram-Core": "py",
        "2026.2-MeasureSoftGram-Front": "ts", "2026.2-MeasureSoftGram-Parser": "py",
        "2026.2-MeasureSoftGram-Plugin": "ts", "2026.2-MeasureSoftGram-Service": "py",
    },
    "limiares": {
        "complexidade_por_funcao": 10,      # arquivo complexo: complexidade ciclomática / funções >= 10
        "comentarios_min": 10,              # arquivo comentado: 10% < densidade de comentários < 30%
        "comentarios_max": 30,
        "duplicacao_max": 5,                # arquivo sem duplicação: densidade de duplicação < 5%
        "cobertura_min": 60,                # arquivo coberto: cobertura > 60%
        "teste_rapido_ms": 300_000,         # suíte de teste rápida: < 5 minutos
        # métricas de processo (model-doc): limiares "definidos pelo usuário"
        "build_rapido_min": 10,             # execução de CI rápida: até 10 minutos
        "resolucao_dias": 14,               # issue resolvida dentro do prazo: até 1 sprint (14 dias)
        "issue_antiga_dias": 28,            # issue aberta há mais de 2 sprints = antiga
        "correcao_bug_dias": 7,             # bug corrigido rápido: até 7 dias
        "revisao_pr_horas": 48,             # PR revisado e fechado em até 48 h
    },
    # Workflows que contam como "build" em Build stability, Build performance e CI feedback time (DA-R3.02,
    # decisão D5 em docs/planejamento/decisoes.mdx). Só o workflow de testes (test.yml, que o time padronizou
    # como "Rodar Testes"): deploy, coleta de dados, dependabot e publicação não dizem se o produto está estável,
    # e o Deploy Prod cancelado após ~24 h distorcia o tempo médio. Os dados coletados não trazem o caminho do
    # arquivo, então o filtro é pelo nome; os caminhos entram porque o GitHub usa o caminho como nome quando o
    # arquivo do workflow falha ao carregar. Lista vazia = todos os workflows.
    "workflows_build": ["Rodar Testes", "Testes", ".github/workflows/test.yml", ".github/workflows/tests.yml"],
    # pesos do notebook (pm = métrica, psc = fator, pc = aspecto)
    "pesos": {
        "complexidade": 0.33, "comentarios": 0.33, "duplicacao": 0.33,          # → Qualidade do código
        "testes_passando": 0.25, "testes_rapidos": 0.25, "cobertura": 0.5,       # → Situação dos testes
        "qualidade_codigo": 1.0, "situacao_testes": 1.0,                          # psc1, psc2
        "manutenibilidade": 0.5, "confiabilidade": 0.5,                           # pc1, pc2 → nota total
    },
    # Metas da R3 do plano de qualidade (docs/planejamento/metas.mdx). Só as métricas têm meta: a do fator é a
    # média das metas das métricas e a do indicador é a fórmula aplicada às metas dos fatores, truncada em 2 casas.
    "plano": {
        "metas": {
            "complexity": 0.88, "duplication": 0.99,                     # M1, M2
            "test_success": 1.00, "test_coverage": 0.90,                 # M3, M5
            "non_blocking_files": 1.00, "well_defined_issues": 0.95,     # M6, M7
            "team_throughput": 0.60, "build_stability": 0.95,            # M9, M10
            "development_task_completion": 0.80,                         # DT
        },
        "piso_por_repo": {"test_coverage": 0.80, "build_stability": 0.90},   # M5 e M10: piso por repositório
        "portao_ci_mediana_min": 5.0,            # M8: mediana do test.yml por repositório (portão, fora da média)
        "repos_com_relatorio_de_testes": 8,      # M3: todos os repositórios enviam o relatório de testes
        "meta_throughput_por_sprint": True,      # M9: a meta vale para cada sprint
    },

}

# Estrutura e decisões do plano publicado; pesos do notebook acima são apenas legado.
QRAPIDS_INDICADORES = {'product_quality': ('Product Quality',
                     'manutenibilidade, confiabilidade e adequação funcional do produto',
                     ['code_quality', 'software_stability', 'software_usage']),
 'blocking': ('Blocking',
              'condições que atrapalham o fluxo do projeto (parar a linha, adiar uma feature)',
              ['quality_issues_specification', 'testing_status', 'blocking_code']),
 'process_performance': ('Process Performance',
                         'eficiência e qualidade do processo de desenvolvimento',
                         ['issues_velocity', 'testing_performance', 'development_speed', 'external_quality']),
 'product_readiness': ('Product Readiness',
                       'produto pronto para a próxima release: implementa o planejado e sem bloqueios',
                       ['activities_completion',
                        'code_quality',
                        'product_stability',
                        'known_remaining_defects'])}

QRAPIDS_AVALIADOS = {'product_quality': ['code_quality'],
 'blocking': ['quality_issues_specification', 'testing_status', 'blocking_code'],
 'process_performance': ['issues_velocity'],
 'product_readiness': ['activities_completion', 'code_quality', 'product_stability']}

QRAPIDS_FATORES = {'code_quality': ('Code Quality', 'produto', ''),
 'software_stability': ('Software Stability',
                        'produto',
                        'sem fonte: não há logs de produção (Bug density é habilitável)'),
 'software_usage': ('Software Usage', 'produto', 'sem fonte: o produto não tem telemetria de uso'),
 'quality_issues_specification': ("Quality Issues' Specification", 'produto', ''),
 'testing_status': ('Testing Status', 'produto', ''),
 'blocking_code': ('Blocking Code', 'produto', ''),
 'issues_velocity': ("Issues' Velocity", 'processo', ''),
 'testing_performance': ('Testing Performance',
                         'processo',
                         'portão: M8 é medido em minutos, fora da escala 0–1'),
 'development_speed': ('Development Speed', 'processo', 'as métricas do fator são só monitoradas'),
 'external_quality': ('External Quality', 'processo', 'sem fonte: o feedback do cliente não é registrado'),
 'activities_completion': ('Activities Completion', 'processo', ''),
 'product_stability': ('Product Stability', 'produto', ''),
 'known_remaining_defects': ('Known Remaining Defects',
                             'processo',
                             'prioridade não é marcada nas issues (Postponed issues ratio é habilitável)')}

QRAPIDS_METRICAS = {'complexity': ('M1', 'Complexity', 'code_quality', 'Incluída'),
 'duplication': ('M2', 'Duplication', 'code_quality', 'Incluída'),
 'well_defined_issues': ('M7', 'Well defined issues', 'quality_issues_specification', 'Incluída'),
 'non_blocking_files': ('M6', 'Non-blocking files', 'blocking_code', 'Incluída'),
 'test_success': ('M3', 'Test success', 'testing_status', 'Incluída'),
 'test_coverage': ('M5', 'Test coverage', 'testing_status', 'Incluída'),
 'ci_feedback_time': ('M8', 'CI feedback time', 'testing_performance', 'Incluída'),
 'team_throughput': ('M9', 'Team throughput', 'issues_velocity', 'Incluída'),
 'build_stability': ('M10', 'Build stability', 'product_stability', 'Incluída'),
 'development_task_completion': ('DT', 'Development task completion', 'activities_completion', 'Incluída'),
 'comments': ('Mc', 'Comments', 'code_quality', 'Monitorada'),
 'fast_tests': ('M4', 'Fast tests', 'testing_performance', 'Monitorada'),
 'resolved_issues_throughput': ('—', "Resolved issues' throughput", 'issues_velocity', 'Monitorada'),
 'old_issues': ('—', 'Old issues', 'issues_velocity', 'Monitorada'),
 'build_performance': ('—', 'Build performance', 'development_speed', 'Monitorada'),
 'commit_review_duration': ('—', 'Commit review duration', 'development_speed', 'Monitorada'),
 'timely_feature_delivery': ('—', 'Timely feature delivery', 'development_speed', 'Monitorada'),
 'non_issue_commits': ('—', 'Non-issue component commit', 'development_speed', 'Monitorada')}

QRAPIDS_TIPO_META = {'complexity': 'Relativa por repositório',
 'duplication': 'Relativa (não regredir)',
 'test_success': 'Absoluta (8 de 8 repositórios)',
 'test_coverage': 'Absoluta + piso 0,80 por repositório',
 'non_blocking_files': 'Absoluta (zero)',
 'well_defined_issues': 'Absoluta',
 'ci_feedback_time': 'Portão: mediana ≤ 5 min por repositório',
 'team_throughput': 'Absoluta por sprint',
 'build_stability': 'Absoluta + piso 0,90 por repositório',
 'development_task_completion': 'Absoluta (escopo da release)'}

QRAPIDS_CATALOGO = [{'decisao': 'Monitorada',
  'indicador_fator': 'Product Quality › Code Quality · Manutenibilidade › Analisabilidade',
  'metrica': 'Mc Comments',
  'motivo': '',
  'justificativa': 'A faixa de 10–30% é fixa e não considera a linguagem: TS *strict* usa tipos no lugar de '
                   'comentários, e as docstrings inflam o valor em Python. Uma meta levaria o time a comentar '
                   'só para bater o número, sem ganho de manutenibilidade. Fica como alerta para a API pública '
                   'de Core e Parser, que são bibliotecas publicadas.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'M4 Fast tests',
  'motivo': '',
  'justificativa': 'Provisória. O limiar do modelo (5 min por suíte) é alto para testes unitários, então a '
                   'métrica tende a não variar e não levar a ação. Se a coleta corrigida mostrar variação '
                   'entre repositórios, a métrica passa a ser incluída.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': "Process Performance › Issues' Velocity · Produtividade",
  'metrica': "Resolved issues' throughput",
  'motivo': '',
  'justificativa': 'Complementa M9 com o tempo de resolução. Na nota, repetiria parte do que M9 já mede.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': "Process Performance › Issues' Velocity · Produtividade",
  'metrica': 'Old issues',
  'motivo': '',
  'justificativa': 'Serve de alerta de backlog esquecido, mas não responde a nenhum objetivo da R3.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Build performance',
  'motivo': '',
  'justificativa': 'É a versão 0–1 de M8 e levaria o mesmo dado duas vezes para a nota.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Commit review duration',
  'motivo': '',
  'justificativa': 'Mostra se a revisão de PR trava o fluxo, mas o time não tem objetivo declarado sobre isso. '
                   'A coleta ainda está pendente.',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Timely feature delivery',
  'motivo': '',
  'justificativa': 'Se sobrepõe em parte a M9. O modelo usa o campo `ontime` do OpenProject, e a versão pelo '
                   'histórico de sprints é uma adaptação do time (pendente de decisão pelo critério 5).',
  'condicao': ''},
 {'decisao': 'Monitorada',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Non-issue component commit',
  'motivo': '',
  'justificativa': 'Mede a rastreabilidade entre commit e issue. É útil como alerta de processo, mas não diz '
                   'nada sobre a qualidade da entrega. A coleta ainda está pendente.',
  'condicao': ''},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Product Quality › Software Stability · Confiabilidade › Maturidade',
  'metrica': 'Bug density',
  'motivo': '',
  'justificativa': 'Depende de defeitos registrados com o rótulo de bug, o que não é prática sistemática do '
                   'time.',
  'condicao': 'Rótulo de bug obrigatório pelo template de Defeito, com volume suficiente para calcular'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Error correction',
  'motivo': '',
  'justificativa': 'Mesma dependência do rótulo de bug.',
  'condicao': 'Mesma condição de Bug density'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Bug leakage',
  'motivo': '',
  'justificativa': 'Depende do rótulo de bug e da origem do defeito. É uma razão sem teto.',
  'condicao': 'Rótulo de bug + marcação de origem pós-release'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Commit review iterations',
  'motivo': '',
  'justificativa': 'O dado existe no GitHub, mas não é coletado.',
  'condicao': 'Coleta nova da API de reviews'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Commit response time',
  'motivo': '',
  'justificativa': 'O dado existe no GitHub, mas não é coletado.',
  'condicao': 'Mesma coleta da métrica anterior'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Product Readiness › Product Stability · Confiabilidade › Maturidade',
  'metrica': 'Critical issues ratio',
  'motivo': '',
  'justificativa': 'Depende de prioridade marcada nas issues, que não é campo obrigatório no fluxo atual.',
  'condicao': 'Prioridade como campo do template de issue'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Product Readiness › Known Remaining Defects · Confiabilidade › Maturidade',
  'metrica': 'Postponed issues ratio',
  'motivo': '',
  'justificativa': 'Mesma dependência da métrica anterior.',
  'condicao': 'Prioridade ou severidade nas issues'},
 {'decisao': 'Habilitável',
  'indicador_fator': 'Product Readiness › Activities Completion · Produtividade',
  'metrica': 'Specification task completion',
  'motivo': '',
  'justificativa': 'O time não separa tarefas de especificação por tipo ou label.',
  'condicao': 'Tipo ou label de especificação'},
 {'decisao': 'Excluída',
  'indicador_fator': 'Product Quality › Software Stability · Confiabilidade › Maturidade',
  'metrica': 'Errors at runtime (SEAA 2018)',
  'motivo': 'Sem fonte',
  'justificativa': 'Nenhum log de produção do Service é coletado para análise.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Product Quality › Software Stability · Confiabilidade › Disponibilidade',
  'metrica': 'Availability uptime (SEAA 2018)',
  'motivo': 'Sem fonte',
  'justificativa': 'Não há monitoramento de disponibilidade.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Product Quality › Software Usage · Adequação funcional › Aptidão funcional',
  'metrica': 'Feature usage',
  'motivo': 'Sem fonte',
  'justificativa': 'O produto não tem telemetria de uso.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › External Quality · Adequação funcional › Correção',
  'metrica': 'End user feedback',
  'motivo': 'Sem fonte',
  'justificativa': 'O feedback do cliente não é registrado em ferramenta.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Developer-tester communication',
  'motivo': 'Sem fonte',
  'justificativa': 'Não há papel de testador separado.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Core component commits',
  'motivo': 'Sem fonte',
  'justificativa': 'É específica do caso original (SVN e arquivos `.bpmn`).',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Timely feature specifications delivery',
  'motivo': 'Sem fonte',
  'justificativa': 'O time não separa tarefas de especificação.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Blocking › Blocking Code · Manutenibilidade › Modificabilidade',
  'metrica': 'Highly changed files (SEAA 2018)',
  'motivo': 'Sem fórmula de referência',
  'justificativa': 'O artigo SEAA 2018 não traz fórmula, a métrica não existe no modelo de 2019 e não está no '
                   'notebook da disciplina. A fórmula e o limiar de 5 commits foram criados pelo time no '
                   'dashboard, então a métrica falha o critério 5.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Error identification',
  'motivo': 'Sem direção',
  'justificativa': 'Achar mais bugs pode significar teste melhor, então não há valor bom ou ruim. Também '
                   'depende do rótulo de bug.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Tests per product',
  'motivo': 'Fora da escala',
  'justificativa': 'Fica fora de 0–1 e não tem sentido sem uma linha de produtos.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Long tests',
  'motivo': 'Repete M4',
  'justificativa': 'É o complemento de Fast tests.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Testing Performance · Produtividade',
  'metrica': 'Unit test duration',
  'motivo': 'Repete M4',
  'justificativa': 'Usa o mesmo dado de duração das suítes.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Process Performance › Development Speed · Produtividade',
  'metrica': 'Avg. automation duration',
  'motivo': 'Repete M4',
  'justificativa': 'Tem o mesmo dado e a mesma fórmula.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': "Process Performance › Issues' Velocity · Produtividade",
  'metrica': 'Issues-type in a timeframe',
  'motivo': 'Repete Bug density',
  'justificativa': 'O tipo é livre; com Bug, repete Bug density.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': "Process Performance › Issues' Velocity · Produtividade",
  'metrica': 'Bugs ratio',
  'motivo': 'Repete Bug density',
  'justificativa': 'É o complemento de Bug density.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': "Process Performance › Issues' Velocity · Produtividade",
  'metrica': 'Resolved issues assigned to a date (SEAA 2018)',
  'motivo': 'Repete outras',
  'justificativa': "Já é coberta por Resolved issues' throughput e Timely feature delivery.",
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': "Blocking › Quality Issues' Specification · Manutenibilidade (Q-Rapids)",
  'metrica': 'Issues completely specified (SEAA 2018)',
  'motivo': 'Repete M7',
  'justificativa': 'É o mesmo conceito de M7 com o sinal invertido.',
  'condicao': ''},
 {'decisao': 'Excluída',
  'indicador_fator': 'Blocking › Testing Status · Confiabilidade › Maturidade',
  'metrica': 'Fast test builds (SEAA 2018)',
  'motivo': 'Repete M4',
  'justificativa': 'É igual a Fast tests do modelo de 2019.',
  'condicao': ''}]

PLANO_QUALIDADE_URL = "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/"
METAS_QUALIDADE_URL = "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/metas/"
# Pesos relativos; normalizados apenas entre fatores com dados. None mantém o padrão 1/n.
QRAPIDS["plano"]["pesos_fatores"] = {indicador: None for indicador in QRAPIDS_AVALIADOS}
METAS_QRAPIDS = {
    "metricas": QRAPIDS["plano"]["metas"],
    "piso_r2": {"product_quality": .908, "blocking": .929, "process_performance": .400,
                "product_readiness": .815},
    "por_repo": {
        "complexity": {"Core": .64, "Parser": .83, "Service": .77, "CLI": .89, "AI": 1.,
                       "Front": .95, "Plugin": .94, "Action": 1.},
        "duplication": {"Core": 1., "Parser": 1., "Service": .989, "CLI": 1., "AI": 1.,
                       "Front": .986, "Plugin": 1., "Action": 1.},
        "test_coverage": {"Core": .86, "Action": .86, "Parser": .83, "Service": .90,
                          "Plugin": .92, "Front": .94, "CLI": .95, "AI": 1.},
    },
    "tipo": QRAPIDS_TIPO_META,
    "fonte_baseline": "43c22d6 (07/11/2026); metas.mdx",
}
# As cinco condições do plano. Pisos por repo são restrições das métricas, não novos portões.
QRAPIDS["plano"]["portoes"] = {
    "coverage": {"indicadores": ["blocking"], "limiar": METAS["coverage"]["R3"], "operador": ">="},
    "duplicated_lines_density": {"indicadores": ["product_quality", "product_readiness"],
                                 "limiar": METAS["duplicated_lines_density"]["R3"], "operador": "<="},
    "non_blocking_files": {"indicadores": ["blocking"], "limiar": 1., "operador": ">="},
    "ci_feedback_time": {"indicadores": ["process_performance"], "limiar": QRAPIDS["plano"]["portao_ci_mediana_min"],
                         "critico": QRAPIDS["limiares"]["build_rapido_min"], "operador": "<="},
    "test_success": {"indicadores": ["blocking"], "limiar": 8, "operador": ">="},
}

QRAPIDS_DEFINICOES = {'complexity': {'chave': 'complexity',
                'codigo': 'M1',
                'nome': 'Complexity',
                'fator': 'code_quality',
                'indicadores': ['product_quality', 'product_readiness'],
                'fonte': '`complexity` e `functions` de cada arquivo · SonarCloud',
                'formula': 'Arquivo não complexo: complexidade ÷ funções < 10. Valor = não complexos ÷ '
                           'arquivos',
                'justificativa': 'Mede o custo de entender e alterar o código, núcleo da Manutenibilidade. '
                                 'Funciona como guarda contra regressão enquanto o produto cresce. A fórmula '
                                 'está no modelo de 2019 e no notebook. Tem viés de linguagem, então só é '
                                 'comparada dentro do mesmo grupo (Python ou TS).',
                'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m1'},
 'duplication': {'chave': 'duplication',
                 'codigo': 'M2',
                 'nome': 'Duplication',
                 'fator': 'code_quality',
                 'indicadores': ['product_quality', 'product_readiness'],
                 'fonte': '`duplicated_lines_density` de cada arquivo · SonarCloud',
                 'formula': 'Arquivo sem duplicação: densidade < 5%. Valor = sem duplicação ÷ arquivos',
                 'justificativa': 'Código duplicado multiplica o esforço de cada mudança e espalha defeitos. O '
                                  'risco é maior em repositórios de interface, onde componentes são copiados e '
                                  'adaptados. A correção é feita por refatoração dentro do semestre. A fórmula '
                                  'está no modelo e no notebook.',
                 'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m2'},
 'well_defined_issues': {'chave': 'well_defined_issues',
                         'codigo': 'M7',
                         'nome': 'Well defined issues',
                         'fator': 'quality_issues_specification',
                         'indicadores': ['blocking'],
                         'fonte': '`body` e `milestone` (GitHub); sprint (Zenhub)',
                         'formula': 'Issue bem definida: descrição e prazo preenchidos. Valor = bem definidas '
                                    '÷ issues criadas no período',
                         'justificativa': 'Issue mal definida entra na sprint sem critério claro de pronto e '
                                          'distorce velocity, burndown e EVM, que compõem o dashboard '
                                          'avaliado. Usa a definição do modelo, a mesma do dashboard. '
                                          'Estimativa e responsável passam a ser critérios da *Definition of '
                                          'Ready*.',
                         'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m7'},
 'non_blocking_files': {'chave': 'non_blocking_files',
                        'codigo': 'M6',
                        'nome': 'Non-blocking files',
                        'fator': 'blocking_code',
                        'indicadores': ['blocking'],
                        'fonte': '`blocker_violations` e `critical_violations` de cada arquivo · API do '
                                 'SonarCloud',
                        'formula': 'Arquivo não bloqueante: 0 blocker e 0 critical. Valor = não bloqueantes ÷ '
                                   'arquivos de código',
                        'justificativa': 'Violações graves são o que pode travar uma entrega, e o modelo as '
                                         'mede por arquivo, de qualquer tipo (bug, vulnerabilidade, code '
                                         'smell). Substitui as notas de segurança e confiabilidade, que são '
                                         'por repositório e não fazem parte do Q-Rapids. O script do dashboard '
                                         'já lê as chaves por arquivo. Meta absoluta (zero), porque as regras '
                                         'mudam com a linguagem.',
                        'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m6'},
 'test_success': {'chave': 'test_success',
                  'codigo': 'M3',
                  'nome': 'Test success',
                  'fator': 'testing_status',
                  'indicadores': ['blocking'],
                  'fonte': '`tests`, `test_errors` e `test_failures` · SonarCloud',
                  'formula': '(testes − erros − falhas) ÷ testes',
                  'justificativa': 'Teste falhando na branch de integração é o defeito mais grave do fator e '
                                   'bloqueia o time. A fórmula está no modelo e no notebook. Pela configuração '
                                   'dos repositórios, AI e Plugin não enviam relatório de testes ao '
                                   'SonarCloud, e a métrica obriga a fechar essa lacuna.',
                  'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m3'},
 'test_coverage': {'chave': 'test_coverage',
                   'codigo': 'M5',
                   'nome': 'Test coverage',
                   'fator': 'testing_status',
                   'indicadores': ['blocking'],
                   'fonte': '`coverage` de cada arquivo · SonarCloud',
                   'formula': 'Arquivo coberto: cobertura > 60%. Valor = cobertos ÷ arquivos (notebook, célula '
                              '44)',
                   'justificativa': 'É a única métrica com meta fixada pela disciplina (cobertura ≥ 90% na '
                                    'R3). Por arquivo, mostra o que a cobertura global esconde: arquivos pouco '
                                    'testados dentro de um repositório bem coberto na média. Pela '
                                    'configuração, CLI, Core e Parser medem só linhas, então a cobertura de '
                                    'ramos precisa ser padronizada antes de fixar a meta.',
                   'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m5'},
 'ci_feedback_time': {'chave': 'ci_feedback_time',
                      'codigo': 'M8',
                      'nome': 'CI feedback time',
                      'fator': 'testing_performance',
                      'indicadores': ['process_performance'],
                      'fonte': 'Duração de cada execução de `test.yml` · GitHub Actions',
                      'formula': 'Duração das execuções de `test.yml`, em minutos (o modelo usa média; a troca '
                                 'por mediana está pendente)',
                      'justificativa': 'Feedback lento faz o desenvolvedor juntar commits antes de validar, e '
                                       'o tempo tende a crescer junto com a suíte de testes. A fórmula está no '
                                       'modelo de 2019. Fica fora da média 0–1, com meta em minutos.',
                      'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m8'},
 'team_throughput': {'chave': 'team_throughput',
                     'codigo': 'M9',
                     'nome': 'Team throughput',
                     'fator': 'issues_velocity',
                     'indicadores': ['process_performance'],
                     'fonte': 'Status e datas de cada issue da sprint · Zenhub',
                     'formula': 'Issues fechadas até o fim da sprint ÷ issues planejadas na sprint',
                     'justificativa': 'Mede a capacidade de planejamento do time, que é a história de usuário '
                                      'do fator no modelo: entregar o que foi planejado em cada ciclo. A '
                                      'definição deve ficar igual à do dashboard.',
                     'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m9'},
 'build_stability': {'chave': 'build_stability',
                     'codigo': 'M10',
                     'nome': 'Build stability',
                     'fator': 'product_stability',
                     'indicadores': ['product_readiness'],
                     'fonte': '`conclusion` de cada execução de `test.yml` · GitHub Actions',
                     'formula': 'Execuções com sucesso ÷ execuções com sucesso ou falha',
                     'justificativa': 'Uma build quebrada bloqueia o merge de todo o time e atrasa a release. '
                                      'A fórmula está no modelo de 2019.',
                     'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#m10'},
 'development_task_completion': {'chave': 'development_task_completion',
                                 'codigo': 'DT',
                                 'nome': 'Development task completion',
                                 'fator': 'activities_completion',
                                 'indicadores': ['product_readiness'],
                                 'fonte': 'Tipo e status das tarefas do escopo da R3 · Zenhub',
                                 'formula': 'Tarefas da R3 concluídas ÷ tarefas planejadas para a R3',
                                 'justificativa': 'Responde à pergunta do indicador: a release fica pronta? '
                                                  'Não repete M9, que mede a sprint e não o escopo da release. '
                                                  'A fórmula está no modelo de 2019.',
                                 'plano': 'https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/#dt'}}

for _chave, _definicao in QRAPIDS_DEFINICOES.items():
    _definicao["tipo_meta"] = METAS_QRAPIDS["tipo"][_chave]
    _definicao["limiar"] = {
        "complexity": "complexidade_por_funcao", "duplication": "duplicacao_max",
        "test_coverage": "cobertura_min", "ci_feedback_time": "portao_ci_mediana_min",
    }.get(_chave, "meta da métrica")
    QRAPIDS_CATALOGO.append({
        "decisao": "Incluída", "indicador_fator": " · ".join(
            QRAPIDS_INDICADORES[_ic][0] for _ic in _definicao["indicadores"]),
        "metrica": _definicao["nome"], "motivo": "", "justificativa": _definicao["justificativa"], "condicao": "",
    })
