"""Configuração do dashboard — o único arquivo que o time precisa editar.

Cada informação vem da fonte mais adequada:

* **SonarCloud** — qualidade do código. Coletado centralmente pela API do
  SonarCloud (``scripts/coleta_sonar.py`` → ``data/sonar/``, executado pelo
  workflow ``coleta-dados.yml``), que traz todas as métricas agregadas,
  histórico, Quality Gate, issues e métricas por componente
  (``api/measures/component_tree``). Mantém compatibilidade com os ``.json``
  legados em ``data/``.
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
GITHUB_REPOS: list[str] = [k.split("_", 1)[1] for k in SONAR_PROJETOS] + [
    "2026.2-MeasureSoftGram-DOC", "2026.2-MeasureSoftGram-docs-eps"]

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
