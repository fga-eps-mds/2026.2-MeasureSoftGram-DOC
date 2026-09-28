#!/usr/bin/env bash
# Aplica a limpeza "tudo do Zenhub, só o resto da planilha" na raiz do repositório.
# Uso (Git Bash, na raiz 2026.2-MeasureSoftGram-docs-eps, com o zip já extraído por cima):
#   bash aplicar.sh
set -e
git rm -q --ignore-unmatch \
  Analytics/planilhas/sumario_evm.csv Analytics/planilhas/valor_agregado.csv Analytics/planilhas/velocity.csv \
  Analytics/planilhas/sprints.csv Analytics/planilhas/releases.csv \
  Analytics/scripts/coleta_zenhub.py Analytics/scripts/coleta_zenhub.mjs \
  "Analytics/data/zenhub/zenhub-sprints-2026-09-27.json" "Analytics/data/zenhub/zenhub-sprints-2026-09-27T1630.json"
# parametros.csv: tira pessoas/horas/custo_hora (vêm da aba Custos)
python - <<'PY'
p = "Analytics/planilhas/parametros.csv"
linhas = open(p, encoding="utf-8").read().replace("\r\n", "\n").splitlines()
fora = ("pessoas,", "horas_semana_pessoa,", "custo_hora,")
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(l for l in linhas if not l.startswith(fora)) + "\n")
PY
(cd Analytics && python -m unittest discover -s tests)
git add Analytics/app.py Analytics/config.py Analytics/README.md Analytics/src/evm.py Analytics/src/velocity.py \
  Analytics/src/velocity_dashboard.py Analytics/src/resumo.py Analytics/src/planilhas.py Analytics/src/gestao.py \
  Analytics/stlite/build.py Analytics/tests/test_velocity.py Analytics/tests/test_evm.py \
  Analytics/planilhas/parametros.csv docs/metricas/modelo-de-gestao.mdx docs/metricas/velocity-zenhub.mdx
git commit -q -F - <<'MSG'
refactor(dashboard): pontos só do Zenhub; planilha só com custos, time, horas, riscos e decisões

- AgileEVM e burndown calculados em src/evm.py com os pontos do Zenhub
  (PRP, PA, RPC, APC) e os custos/horas da planilha (BAC, PV, AC, CPI).
- Release da sprint: Release do Zenhub ou datas de entrega do plano de ensino.
- Removidas as abas EVM - Velocity, Valor Agregado, Sumário EVM (e sprints.csv,
  releases.csv, coletor antigo e snapshot antigo do Zenhub).
- config.py com as 6 abas que ficam na planilha; o deploy baixa as abas
  publicadas para o GitHub Pages.

Co-authored-by: DanielFsR <danielferreirasantosd12@gmail.com>
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01C6uqepKv4Ci1KcUHwKpGfU
MSG
git log --oneline -1
