"""Testes de src/metrics/agile.py e src/metrics/calculations.py (sem Streamlit, sem rede)."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import agile  # noqa: E402
from src.metrics.calculations import pct, status_indice, variacao  # noqa: E402


def issue(iid, tipo="Task", estado="OPEN", pipeline="Sprint Backlog", est=None, pai=None, fechada=None, pr=False,
          titulo=None):
    return {"issue_id": iid, "number": int(iid[1:]) if iid[1:].isdigit() else 0, "title": titulo or iid,
            "issue_type": tipo, "state": estado, "pipeline": pipeline, "estimate": est, "parent_id": pai,
            "closed_at": fechada, "pipeline_moved_at": None, "is_pull_request": pr, "repository": "repo-x"}


class UniversoTest(unittest.TestCase):
    def setUp(self):
        self.snap = {
            "issues": {
                "E1": issue("E1", "Epic", titulo="Épico 1"),
                "T1": issue("T1", est=3, pai="E1", estado="CLOSED", fechada="2026-09-22T12:00:00Z", pipeline="Done"),
                "T2": issue("T2", est=5, pai="E1", pipeline="In Progress"),
                "S1": issue("S1", "Sub-task", pai="T2", pipeline="Review/QA"),
                "P1": issue("P1", pr=True),
                "X1": issue("X1", pipeline="Pipeline Novo"),
            },
            "sprints": [{"start_at": "2026-09-21T03:59:00Z", "issue_ids": ["T1", "T2"]}],
            "releases": [{"release_name": "Release 01", "issue_ids": ["T1", "T2"], "state": "OPEN", "issues_count": 3}],
        }

    def test_situacao_epico_release_e_sem_pr(self):
        df, completo = agile.universo_issues(self.snap)
        self.assertFalse(completo)                       # sem backlog = só issues das sprints
        d = df.set_index("issue_id")
        self.assertNotIn("P1", d.index)                  # pull request fica fora
        self.assertEqual(d.loc["T1", "situacao"], agile.CONCLUIDO)
        self.assertEqual(d.loc["T2", "situacao"], agile.ANDAMENTO)
        self.assertEqual(d.loc["X1", "situacao"], agile.NAO_CLASSIFICADO)   # pipeline fora do mapa
        self.assertEqual(d.loc["S1", "epico"], "Épico 1")                   # neta do épico
        self.assertEqual(d.loc["T1", "release"], "Release 01")
        self.assertEqual(d.loc["T1", "sprint"], "S1")
        self.assertEqual(d.loc["X1", "release"], "Sem release")

    def test_aberta_no_done_nao_e_concluida(self):
        self.snap["issues"]["D1"] = issue("D1", est=2, pipeline="Done")
        d = agile.universo_issues(self.snap)[0].set_index("issue_id")
        self.assertEqual(d.loc["D1", "situacao"], agile.ANDAMENTO)
        self.assertTrue(pd.isna(d.loc["D1", "concluida_em"]))

    def test_backlog_completo_mescla(self):
        self.snap["backlog"] = {"pipelines": [], "pipelines_com_falha": [], "issues": [
            {**issue("B1", pipeline="Product Backlog", est=2), "priority": "High priority", "assignees": ["ana"]}]}
        df, completo = agile.universo_issues(self.snap)
        self.assertTrue(completo)
        b = df.set_index("issue_id").loc["B1"]
        self.assertEqual((b["situacao"], b["prioridade"], b["responsavel"]), (agile.PLANEJADO, "High priority", "ana"))

    def test_backlog_com_falha_nao_e_completo(self):
        self.snap["backlog"] = {"pipelines": [], "pipelines_com_falha": ["Icebox"], "issues": []}
        self.assertFalse(agile.universo_issues(self.snap)[1])

    def test_progresso_epicos_e_releases(self):
        df, _ = agile.universo_issues(self.snap)
        ep = agile.progresso_epicos(df).set_index("epico").loc["Épico 1"]
        self.assertEqual((ep["filhas"], ep["concluidas"]), (3, 1))
        self.assertAlmostEqual(ep["progresso"], 1 / 3)
        rel = agile.progresso_releases(self.snap, df).iloc[0]
        self.assertEqual((rel["issues"], rel["concluidas"], rel["pontos"]), (2, 1, 8))

    def test_throughput_semana_e_media_movel(self):
        df, _ = agile.universo_issues(self.snap)
        tp = agile.throughput_semanal(df, {"Task"})
        self.assertEqual(list(tp["itens"]), [1])
        self.assertEqual(tp["semana"].iloc[0], pd.Timestamp("2026-09-21"))
        mm = agile.media_movel(pd.Series([1.0, 2.0, 3.0, 4.0]))
        self.assertTrue(pd.isna(mm.iloc[1]))
        self.assertAlmostEqual(mm.iloc[3], 3.0)


class CalculosTest(unittest.TestCase):
    def test_variacao(self):
        self.assertEqual(variacao(82.4, 79.2, "%", True)["texto"], "+3,2 p.p.")
        v = variacao(12, 17, "", False)
        self.assertEqual((v["texto"], v["sentido"]), ("−5", "good"))
        self.assertEqual(variacao(10, None)["texto"], "sem coleta anterior")

    def test_status_indice_sem_dado(self):
        self.assertEqual(status_indice(float("nan")), "unavailable")
        self.assertEqual(status_indice(0.97), "good")
        self.assertEqual(status_indice(0.85), "warning")
        self.assertEqual(pct(None), "—")


if __name__ == "__main__":
    unittest.main()


class ColetaBacklogTest(unittest.TestCase):
    def test_falha_de_pipeline_vira_aviso(self):
        from src.zenhub import coleta
        from src.zenhub.client import ZenhubError

        class Falso:
            def get_pipelines(self):
                return [{"id": "p1", "name": "Product Backlog"}, {"id": "p2", "name": "Icebox"}]

            def get_pipeline_issues(self, pid):
                if pid == "p2":
                    raise ZenhubError("campo inexistente")
                return [{"id": "I1", "number": 1, "title": "t", "state": "OPEN", "estimate": {"value": 2},
                         "issueType": {"name": "Task"}, "assignees": {"nodes": [{"login": "ana"}]},
                         "pipelineIssue": {"priority": {"name": "High"}, "pipeline": None}}], 1

        avisos = []
        b = coleta.coletar_backlog(Falso(), avisos, log=lambda m: None)
        self.assertEqual(b["pipelines_com_falha"], ["Icebox"])
        self.assertEqual(b["issues"][0]["pipeline"], "Product Backlog")     # pipeline vem do laço
        self.assertEqual((b["issues"][0]["priority"], b["issues"][0]["assignees"]), ("High", ["ana"]))
        self.assertEqual(len(avisos), 1)

    def test_lista_de_pipelines_falha(self):
        from src.zenhub import coleta
        from src.zenhub.client import ZenhubError

        class Falso:
            def get_pipelines(self):
                raise ZenhubError("x")

        avisos = []
        self.assertIsNone(coleta.coletar_backlog(Falso(), avisos, log=lambda m: None))
        self.assertTrue(avisos)
