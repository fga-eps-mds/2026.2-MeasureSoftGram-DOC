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
    "niveis_pontuados": "Feature;Task;Bug",    # US (Feature), Task e Bug; US com Tasks filhas não pontua
    "janela_planning_horas": "24",             # planejado = escopo da sprint ao fim do 1º dia (planning)
    "min_sprints_media_velocity": "2",         # velocity média só com pelo menos 2 sprints concluídas
    "sprints_canceladas": "",                  # ids de sprint separados por ";"
    # Prazo de fechamento: issue fechada até esta hora (Brasília) do dia seguinte ao último dia da
    # sprint ainda conta nela (e na release dela). Vazio = só até o fim da sprint no Zenhub.
    "prazo_fechamento_dia_seguinte": "08:00",
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
META_CI_SUCESSO = 80.0   # % de execuções da CI com sucesso
LIMITE_CI_CRITICO = 60.0 # abaixo disso = crítico

# ───────────────────────── modelo de qualidade Q-Rapids ─────────────────────────
# Base: notebook da disciplina (fga-eps-mds/Analytics, internal_quality_analysis-sonarqube.ipynb), que
# implementa o "Q-Rapids Quality Model" (abril/2019, q-rapids model-doc.pdf). Os limiares e pesos abaixo
# são os do notebook; "justificativa" é o texto que o time apresenta (a R2 pede métricas interpretadas
# pelo time) e aparece na página Qualidade (Q-Rapids) ao lado de cada número.
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
    # pesos do notebook (pm = métrica, psc = fator, pc = aspecto)
    "pesos": {
        "complexidade": 0.33, "comentarios": 0.33, "duplicacao": 0.33,          # → Qualidade do código
        "testes_passando": 0.25, "testes_rapidos": 0.25, "cobertura": 0.5,       # → Situação dos testes
        "qualidade_codigo": 1.0, "situacao_testes": 1.0,                          # psc1, psc2
        "manutenibilidade": 0.5, "confiabilidade": 0.5,                           # pc1, pc2 → nota total
    },
    # Segurança: extensão do time (27/10/2026). O notebook só tem Manutenibilidade e Confiabilidade, então uma
    # nota de segurança E no SonarCloud não mudava a nota. A nota oficial (do notebook) fica igual; ao lado dela
    # o painel mostra a "nota com segurança", e uma nota de segurança ruim rebaixa o repositório (veto).
    #   Segurança = (5 − security_rating) ÷ 4   →  A = 1 · B = 0,75 · C = 0,5 · D = 0,25 · E = 0
    "seguranca": {
        "pesos": {"manutenibilidade": 0.4, "confiabilidade": 0.4, "seguranca": 0.2},
        "rating_veto": 4,   # security_rating ≥ 4 (D ou E) → repositório crítico, seja qual for a nota
    },
    "justificativa": {
        "seguranca_pesos": "a preencher pelo time",
        "seguranca_veto": "a preencher pelo time",
        "complexidade_por_funcao": "a preencher pelo time",
        "comentarios_min": "a preencher pelo time",
        "duplicacao_max": "a preencher pelo time",
        "cobertura_min": "a preencher pelo time",
        "teste_rapido_ms": "a preencher pelo time",
        "pesos": "a preencher pelo time",
    },
}
