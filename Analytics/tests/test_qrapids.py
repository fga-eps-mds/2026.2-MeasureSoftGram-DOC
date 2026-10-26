"""Dados do modelo Q-Rapids: commits e issues da coleta própria do GitHub, runs sem duplicar o
repositório renomeado e medidas por arquivo no recorte do período."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import github  # noqa: E402
from src.metrics import qrapids  # noqa: E402


def run(i, repo):
    q = "2026-10-10T10:00:00Z"
    return {"id": i, "name": "CI", "status": "completed", "conclusion": "success", "head_branch": "main",
            "event": "push", "created_at": q, "run_started_at": q, "updated_at": q,
            "html_url": f"https://github.com/fga-eps-mds/{repo}/actions/runs/{i}"}


class GithubTest(unittest.TestCase):
    def test_repositorio_renomeado_nao_duplica_runs(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "github").mkdir()
            for nome in ("2026.2-MeasureSoftGram-DOC", "2026.2-MeasureSoftGram-docs-eps"):
                (d / "github" / f"runs-{nome}.json").write_text(json.dumps(
                    {"repositorio": nome, "workflow_runs": [run(1, nome), run(2, nome)]}))
            r = github.carregar_runs([d])
        self.assertEqual(len(r), 2)
        self.assertEqual(set(r["repositorio"]), {"2026.2-MeasureSoftGram-DOC"})

    def test_commits_e_issues_da_coleta(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "github").mkdir()
            (d / "github" / "commits-2026.2-MeasureSoftGram-Core.json").write_text(json.dumps({
                "repositorio": "2026.2-MeasureSoftGram-Core", "commits": [
                    {"sha": "a", "date": "2026-10-01T12:00:00Z", "author": "ana", "parents": 1,
                     "files": [{"filename": "x.py", "status": "modified", "additions": 3, "deletions": 1},
                               {"filename": "y.py", "status": "added", "additions": 9, "deletions": 0}]},
                    {"sha": "b", "date": "2026-10-02T12:00:00Z", "author": "bia", "parents": 2, "files": []}]}))
            (d / "github" / "issues-2026.2-MeasureSoftGram-Core.json").write_text(json.dumps({
                "repositorio": "2026.2-MeasureSoftGram-Core", "issues": [
                    {"number": 1, "state": "open", "labels": ["bug"], "assignees": [], "body_chars": 0,
                     "created_at": "2026-10-01T00:00:00Z", "closed_at": None}]}))
            c = github.carregar_commits([d])
            i = github.carregar_issues_coleta([d])
        self.assertEqual(list(c["arquivo"]), ["x.py", "y.py"])          # commit sem arquivo não gera linha
        self.assertEqual(c["sha"].nunique(), 1)
        self.assertEqual(i.iloc[0]["labels"], ["bug"])
        self.assertTrue(pd.isna(i.iloc[0]["closed_at"]))


def issue(n, tipo, criada, fechada=None, repo="2026.2-MeasureSoftGram-DOC"):
    return {"repositorio": repo, "number": n, "title": f"#{n}", "issue_type": tipo, "is_pull_request": False,
            "created_at": criada, "closed_at": fechada, "prioridade": "Sem prioridade", "sprints": ["S1"]}


class ModeloCompletoTest(unittest.TestCase):
    def ctx(self):
        z = pd.DataFrame([issue(1, "Bug", "2026-10-01T12:00:00Z"),
                          issue(2, "Task", "2026-10-01T12:00:00Z", "2026-10-05T12:00:00Z"),
                          issue(3, "Task", "2026-08-01T12:00:00Z"),
                          issue(4, "Feature", "2026-10-02T12:00:00Z")])
        runs = pd.DataFrame([{"repositorio": "2026.2-MeasureSoftGram-Core", "workflow": "CI", "conclusao": c,
                              "criado_em": pd.Timestamp("2026-10-10T12:00:00Z"), "duracao_min": d, "url": ""}
                             for c, d in (("success", 2.0), ("success", 15.0), ("failure", 3.0))])
        return SimpleNamespace(sonar_componentes=pd.DataFrame(), sonar_api={}, zh_issues=z, zh_snap={},
                               gh_runs=runs, gh_issues_coleta=pd.DataFrame(), gh_commits=pd.DataFrame(),
                               hoje=pd.Timestamp("2026-10-20"), zh_iniciadas=pd.DataFrame(), zh_regras=None)

    def test_metricas_de_processo_com_numerador_e_denominador(self):
        f = {"periodo": (pd.Timestamp("2026-09-29"), pd.Timestamp("2026-10-26")), "repos": [], "branch": None}
        res = qrapids.calcular(self.ctx(), f, {"fim": pd.Timestamp("2026-10-26"), "repos": []})
        m = {r.chave: r for r in res["metricas"]}
        self.assertEqual((m["bug_density"].numerador, m["bug_density"].denominador), (1, 3))   # 1 bug em 3 abertas
        self.assertAlmostEqual(m["bug_density"].valor, 2 / 3)                                 # 1 = melhor
        self.assertEqual((m["build_stability"].numerador, m["build_stability"].denominador), (2, 3))
        self.assertEqual(m["build_performance"].numerador, 2)                                  # 15 min > 10
        self.assertEqual(m["old_issues"].numerador, 1)                                       # #3 é antiga
        self.assertAlmostEqual(m["old_issues"].valor, 2 / 3)
        self.assertEqual(m["feature_usage"].situacao, qrapids.SEM_FONTE)
        self.assertEqual(m["non_blocking_files"].situacao, qrapids.PENDENTE)
        self.assertIsNone(m["feature_usage"].valor)                                            # nunca vira zero
        # agregação: só métricas calculadas entram; fator sem nenhuma fica sem valor
        fat = res["fatores"].set_index("fator")
        self.assertTrue(pd.isna(fat.loc["software_usage", "valor"]))
        self.assertAlmostEqual(fat.loc["software_stability", "valor"], 2 / 3)

    def test_catalogo_cobre_os_indicadores_do_model_doc(self):
        self.assertEqual(set(qrapids.INDICADORES), {"product_quality", "product_readiness", "blocking",
                                                    "process_performance"})
        fatores = {fc for _, _, fs in qrapids.INDICADORES.values() for fc in fs}
        self.assertEqual(fatores, set(qrapids.FATORES))

    def test_media_sem_os_zeros_por_falta_de_dado(self):
        def av(total, falta):
            return {"avaliacao": {"total": total, "metricas": {"a": {"zero_por_falta": falta},
                                                              "b": {"zero_por_falta": falta}}}}
        notas = {"2026.2-MeasureSoftGram-AI": av(0.0, "sem dado"), "2026.2-MeasureSoftGram-Core": av(0.8, None)}
        media, fora = qrapids.media_repos(notas, lambda a: a["total"])
        self.assertEqual((media, fora), (0.8, ["AI"]))


if __name__ == "__main__":
    unittest.main()
