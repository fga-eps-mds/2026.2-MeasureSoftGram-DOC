"""Configuração do dashboard — o único arquivo que o time precisa editar.

Cada informação vem da fonte mais adequada:

* **SonarCloud** — qualidade do código. Duas entradas: os ``.json`` que o
  ``metrics.yml`` de cada repositório publica em ``data/`` e o snapshot da API
  do SonarCloud (``scripts/coleta_sonar.py`` → ``data/sonar/``), que traz o que
  o pipeline não coleta (bugs, vulnerabilidades, code smells, hotspots, dívida
  técnica, Quality Gate, histórico).
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
# Enquanto a URL estiver vazia, o app lê o CSV de mesmo nome em ``planilhas/``.

PLANILHAS = {
    "custos": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=668960529&single=true&output=csv",
    "planejamento": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=1362167559&single=true&output=csv",
    "horas": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=874852730&single=true&output=csv",
    "riscos": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=844810192&single=true&output=csv",
    "monitoramento": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=546490889&single=true&output=csv",
    "decisoes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTv3UZwvn0vVDrRZj1Pa6woJwnFZdJtE1MtR5tn-yrrO7AYBcCs--Zcw89nv66QKNVqIoy3EQHT7UZo/pub?gid=2101696466&single=true&output=csv",
}

CACHE_PLANILHAS_S = 300  # a planilha publicada é relida a cada 5 minutos

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

# ───────────────────────── calendário e metas ─────────────────────────
# Datas de entrega do plano de ensino (EPS 2026.2).

RELEASES = {"R1": "2026-09-28", "R2": "2026-10-26", "R3": "2026-11-30"}
INICIO_SEMESTRE = "2026-08-24"

# Metas de qualidade por release (critérios enviados pelo professor, ver
# docs/disciplina/avaliacao.mdx). Metas de gestão: SPI e CPI >= 0,95.
METAS = {
    "coverage": {"R1": 85.0, "R2": 85.0, "R3": 90.0},
    "duplicated_lines_density": {"R1": 5.0, "R2": 5.0, "R3": 3.0},
}
META_INDICE_EVM = 0.95   # SPI/CPI abaixo disso = atenção; abaixo de 0,80 = crítico
META_CI_SUCESSO = 80.0   # % de execuções da CI com sucesso
