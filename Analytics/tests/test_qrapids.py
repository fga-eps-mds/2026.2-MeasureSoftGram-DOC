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
        # 3 execuções do workflow de testes + ruído que NÃO é build (D5): deploy cancelado após ~24 h,
        # dependabot ignorado e coleta de dados com sucesso
        testes = [("Rodar Testes", c, d) for c, d in (("success", 2.0), ("success", 15.0), ("failure", 3.0))]
        ruido = [("Deploy Prod (self-hosted)", "cancelled", 1440.0), ("Dependabot Auto-merge", "skipped", 0.0),
                 ("Coleta de dados do dashboard", "success", 1.4), ("Deploy to GitHub Pages", "failure", 0.5)]
        runs = pd.DataFrame([{"repositorio": "2026.2-MeasureSoftGram-Core", "workflow": w, "conclusao": c,
                              "criado_em": pd.Timestamp("2026-10-10T12:00:00Z"), "duracao_min": d, "url": ""}
                             for w, c, d in testes + ruido])
        return SimpleNamespace(sonar_componentes=pd.DataFrame(), sonar_api={}, zh_issues=z, zh_snap={},
                               gh_runs=runs, gh_issues_coleta=pd.DataFrame(), gh_commits=pd.DataFrame(),
                               hoje=pd.Timestamp("2026-10-20"), zh_iniciadas=pd.DataFrame(), zh_regras=None)

    def test_metricas_de_processo_com_numerador_e_denominador(self):
        f = {"periodo": (pd.Timestamp("2026-09-29"), pd.Timestamp("2026-10-26")), "repos": [], "branch": None}
        res = qrapids.calcular(self.ctx(), f, {"fim": pd.Timestamp("2026-10-26"), "repos": []})
        m = {r.chave: r for r in res["metricas"]}
        self.assertEqual((m["build_stability"].numerador, m["build_stability"].denominador), (2, 3))   # M10, só test.yml
        self.assertEqual(m["build_performance"].numerador, 2)                                  # 15 min > 10 (monitorada)
        self.assertEqual(m["build_performance"].denominador, 3)
        self.assertAlmostEqual(m["ci_feedback_time"].medida, 3.0)                              # M8: mediana, sem os 1440 min
        self.assertFalse(m["ci_feedback_time"].escala01)                                       # minutos: portão, não média
        self.assertEqual(m["old_issues"].numerador, 1)                                         # #3 é antiga (monitorada)
        self.assertEqual(m["non_blocking_files"].situacao, qrapids.PENDENTE)
        self.assertEqual(m["team_throughput"].situacao, qrapids.SEM_DADO)                      # sem sprints no snapshot
        self.assertIsNone(m["non_blocking_files"].valor)                                       # nunca vira zero
        fat = res["fatores"].set_index("fator")
        self.assertAlmostEqual(fat.loc["product_stability", "valor"], 2 / 3)
        self.assertTrue(pd.isna(fat.loc["testing_performance", "valor"]))                      # M8 é portão
        self.assertTrue(pd.isna(fat.loc["development_speed", "valor"]))                        # só monitoradas
        self.assertTrue(pd.isna(fat.loc["issues_velocity", "valor"]))

    def test_monitoradas_nao_entram_na_media(self):
        """Monitorada tem valor mas nenhum peso: Old issues e Build performance não mexem em fator algum."""
        f = {"periodo": (pd.Timestamp("2026-09-29"), pd.Timestamp("2026-10-26")), "repos": [], "branch": None}
        res = qrapids.calcular(self.ctx(), f, {"fim": pd.Timestamp("2026-10-26"), "repos": []})
        m = {r.chave: r for r in res["metricas"]}
        for chave in ("old_issues", "build_performance"):
            self.assertEqual(m[chave].decisao, qrapids.MONITORADA)
            self.assertIsNotNone(m[chave].valor)
            self.assertFalse(m[chave].na_media)
        self.assertTrue(m["build_stability"].na_media)

    def test_so_o_plano_e_calculado(self):
        """10 métricas incluídas e 8 monitoradas; as outras 26 só existem no catálogo do plano."""
        decisoes = [v[3] for v in qrapids.METRICAS.values()]
        self.assertEqual((decisoes.count(qrapids.INCLUIDA), decisoes.count(qrapids.MONITORADA)), (10, 8))
        self.assertEqual({v[0] for v in qrapids.METRICAS.values() if v[3] == qrapids.INCLUIDA},
                         {"M1", "M2", "M3", "M5", "M6", "M7", "M8", "M9", "M10", "DT"})
        cat = qrapids.catalogo()
        self.assertEqual(cat["decisao"].value_counts().to_dict(),
                         {qrapids.INCLUIDA: 10, qrapids.MONITORADA: 8, qrapids.HABILITAVEL: 8, qrapids.EXCLUIDA: 18})
        monitoradas = {v[0] + " " + v[1] if v[0] != "—" else v[1] for v in qrapids.METRICAS.values()
                       if v[3] == qrapids.MONITORADA}
        self.assertEqual(monitoradas, set(cat.loc[cat["decisao"] == qrapids.MONITORADA, "metrica"]))

    def test_arvore_segue_o_mapa_do_plano_sem_iso(self):
        """metas.mdx, "Indicadores estratégicos e fatores": 13 fatores, 14 vínculos (Code Quality em dois indicadores)."""
        self.assertEqual(set(qrapids.INDICADORES), {"product_quality", "product_readiness", "blocking",
                                                    "process_performance"})
        vinculos = [fc for _, _, fs in qrapids.INDICADORES.values() for fc in fs]
        self.assertEqual((len(set(vinculos)), len(vinculos)), (13, 14))
        self.assertEqual(set(vinculos), set(qrapids.FATORES))
        self.assertEqual(qrapids.AVALIADOS["product_quality"], ["code_quality"])
        self.assertEqual(qrapids.AVALIADOS["process_performance"], ["issues_velocity"])     # M8 é só portão
        self.assertIn("code_quality", qrapids.AVALIADOS["product_readiness"])
        self.assertNotIn("software_security", qrapids.FATORES)
        res = qrapids.calcular(self.ctx(), {"periodo": (pd.Timestamp("2026-09-29"), pd.Timestamp("2026-10-26")),
                                            "repos": [], "branch": None},
                               {"fim": pd.Timestamp("2026-10-26"), "repos": []})
        tab = qrapids.tabela(res["metricas"])
        cq = tab[tab["fator"] == "Code Quality"]["indicador"].unique()
        self.assertEqual(list(cq), ["Product Quality · Product Readiness"])
        self.assertFalse(any("nota" in c.lower() for c in tab.columns))

    def test_agregacao_tira_fator_sem_dado_do_denominador(self):
        def r(fator, chave, valor, dec=qrapids.INCLUIDA, **kw):
            x = qrapids.Resultado(fator, chave, chave, "", "", "", "", decisao=dec, **kw)
            x.valor, x.situacao = valor, (qrapids.CALCULADA if valor is not None else qrapids.SEM_DADO)
            return x
        fat, ind = qrapids.agregar([r("quality_issues_specification", "a", 0.8), r("testing_status", "b", 0.9),
                                    r("testing_status", "c", 0.7), r("blocking_code", "d", None),
                                    r("code_quality", "e", 0.6, dec=qrapids.MONITORADA)])
        fat, ind = fat.set_index("fator"), ind.set_index("indicador")
        self.assertAlmostEqual(fat.loc["testing_status", "valor"], 0.8)
        self.assertTrue(pd.isna(fat.loc["code_quality", "valor"]))                  # monitorada não pesa
        self.assertAlmostEqual(ind.loc["blocking", "valor"], (0.8 + 0.8) / 2)       # Blocking Code sem dado: n = 2
        self.assertTrue(pd.isna(ind.loc["product_quality", "valor"]))

    def test_metas_seguem_a_regra_do_metas_mdx(self):
        mf, mi = qrapids.metas_agregadas()
        self.assertAlmostEqual(mf["code_quality"], 0.935)
        self.assertAlmostEqual(mf["testing_status"], 0.95)
        self.assertEqual(mi, {"product_quality": 0.93, "blocking": 0.96, "process_performance": 0.60,
                              "product_readiness": 0.89})                           # truncadas, não arredondadas
        self.assertEqual(qrapids.truncar(0.9667), 0.96)
        self.assertEqual(qrapids.truncar(0.895), 0.89)

    def test_so_o_workflow_de_testes_conta_como_build(self):
        """DA-R3.02/D5: deploy, coleta e dependabot não entram; cancelada e ignorada também não."""
        runs = pd.DataFrame({"workflow": ["Rodar Testes", "Testes", ".github/workflows/test.yml", "Linter",
                                          "Deploy Prod (self-hosted)", "Rodar Testes", "Rodar Testes"],
                             "conclusao": ["success", "failure", "failure", "success", "success", "cancelled",
                                           "skipped"]})
        self.assertEqual(list(qrapids.runs_de_build(runs).index), [0, 1, 2])
        self.assertTrue(qrapids.runs_de_build(pd.DataFrame()).empty)


if __name__ == "__main__":
    unittest.main()
