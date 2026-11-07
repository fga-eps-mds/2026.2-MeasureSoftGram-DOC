"""Métricas de fluxo (Throughput, Lead Time, taxa de conclusão) do trabalho técnico e dos defeitos."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import agile, fluxo  # noqa: E402


def issue(iid, tipo, criada, fechada=None, est=None, pai=None):
    return {"issue_id": iid, "number": hash(iid) % 1000, "title": iid, "repository": "2026.2-MeasureSoftGram-Front",
            "state": "CLOSED" if fechada else "OPEN", "closed_at": fechada, "created_at": criada,
            "is_pull_request": False, "estimate": est, "issue_type": tipo, "parent_id": pai,
            "pipeline": "Sprint Backlog", "pipeline_moved_at": None, "url": ""}


class FluxoTest(unittest.TestCase):
    def itens(self, transferencias=None):
        snap = {"issues": {
            "T1": issue("T1", "Task", "2026-10-01T12:00:00Z", "2026-10-03T12:00:00Z", est=5),   # lead 2 d
            "T2": issue("T2", "Task", "2026-10-01T12:00:00Z", "2026-10-11T12:00:00Z"),          # lead 10 d
            "B1": issue("B1", "Bug", "2026-10-05T12:00:00Z", "2026-10-06T12:00:00Z", est=3),    # lead 1 d
            "S1": issue("S1", "Sub-task", "2026-10-05T12:00:00Z"),                              # aberta
            "N1": issue("N1", None, "2026-10-07T12:00:00Z", "2026-10-08T12:00:00Z"),            # sem tipo
            "US": issue("US", "Feature", "2026-10-01T12:00:00Z", "2026-10-04T12:00:00Z", est=8),
            "EP": issue("EP", "Epic", "2026-09-01T12:00:00Z")},
            "sprints": [], "releases": []}
        df, _ = agile.universo_issues(snap)
        return fluxo.itens_de_fluxo(df, transferencias=transferencias)

    @staticmethod
    def transferencias():
        def t(em, para, de="Sprint Backlog"):
            return {"em": em, "de": de, "para": para}
        return {
            "T1": [t("2026-09-30T10:00:00Z", "Sprint Backlog", "New Issues"), t("2026-10-02T12:00:00Z", "In Progress")],
            # retrabalho: sai para Review/QA e volta; vale a PRIMEIRA entrada (10-05), não a última
            "T2": [t("2026-10-05T12:00:00Z", "In Progress"), t("2026-10-07T12:00:00Z", "Review/QA", "In Progress"),
                   t("2026-10-09T12:00:00Z", "In Progress", "Review/QA")],
            # movida para In Progress 2 min antes de fechar: movimentação de cadastro
            "B1": [t("2026-10-06T11:58:00Z", "In Progress")],
            "S1": [t("2026-10-06T12:00:00Z", "In Progress")],     # aberta: fora
            "N1": [],                                              # fechada direto do backlog
        }

    def test_so_trabalho_tecnico_e_defeitos_sem_story_points(self):
        it = self.itens()
        self.assertEqual(set(it["tipo"]), {"Task", "Bug", "Sub-task", "Sem tipo"})   # sem Feature nem Epic
        self.assertNotIn("sp", it.columns)
        self.assertNotIn("pontos", it.columns)

    def test_lead_time_e_so_das_fechadas(self):
        lt = fluxo.lead_time(self.itens())
        self.assertEqual(lt["n"], 4)                       # T1, T2, B1, N1 (a Sub-task aberta fica fora)
        self.assertAlmostEqual(lt["mediana"], 1.5, places=2)   # 1, 1, 2, 10 -> 1,5
        por = lt["por_tipo"].set_index("tipo")
        self.assertAlmostEqual(por.loc["Task", "mediana"], 6.0, places=2)

    def test_throughput_por_semana_zera_semana_sem_conclusao(self):
        tp = fluxo.throughput_semanal(self.itens())
        # 03/10 (sáb) e 06/10 (ter) e 08/10: semanas de 28/09 e 05/10; 11/10 é domingo, semana de 05/10
        total = tp.groupby("semana")["itens"].sum()
        self.assertEqual(int(total.sum()), 4)
        self.assertEqual(list(total.index), [pd.Timestamp("2026-09-28"), pd.Timestamp("2026-10-05")])
        self.assertEqual(int(total.loc[pd.Timestamp("2026-09-28")]), 1)            # T1 (sábado 03/10)
        self.assertEqual(int(total.loc[pd.Timestamp("2026-10-05")]), 3)            # B1, N1 e T2 (domingo 11/10)

    def test_taxa_de_conclusao_do_periodo(self):
        taxa = fluxo.taxa_conclusao(self.itens(), pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31"))
        self.assertEqual((taxa["fechadas"], taxa["ativas"]), (4, 5))
        self.assertAlmostEqual(taxa["taxa"], 0.8)

    def test_cycle_time_sem_historico_e_coleta_pendente(self):
        """Snapshot antigo (sem transferencias_pipeline): nada de número aproximado."""
        ct = fluxo.cycle_time(self.itens(), coletado=False)
        self.assertFalse(ct["disponivel"])
        self.assertIsNone(ct["mediana"])
        self.assertIn("coleta pendente", ct["motivo"])
        self.assertIn("coleta_velocity", ct["necessario"])
        self.assertTrue(self.itens()["inicio"].isna().all())

    def test_cycle_time_primeira_entrada_cobertura_e_exclusoes(self):
        it = self.itens(self.transferencias())
        ini, fim = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31")
        ct = fluxo.cycle_time(it, ini, fim, coletado=True)
        self.assertTrue(ct["disponivel"])
        self.assertEqual((ct["n"], ct["fechadas"]), (2, 4))              # T1 e T2 de T1, T2, B1, N1
        self.assertAlmostEqual(ct["cobertura"], 0.5)
        self.assertEqual((ct["sem_inicio"], ct["movidas_ao_fechar"]), (1, 1))   # N1 nunca entrou; B1 movida ao fechar
        self.assertAlmostEqual(ct["mediana"], 3.5, places=2)             # T1 = 1 dia, T2 = 6 dias (primeira entrada)
        self.assertAlmostEqual(ct["p85"], 1 + 5 * 0.85, places=2)
        self.assertAlmostEqual(ct["espera_mediana"], 2.5, places=2)      # Lead 2 e 10 menos Cycle 1 e 6 = 1 e 4
        self.assertEqual(set(ct["por_tipo"]["tipo"]), {"Task"})

    def test_cycle_time_so_conta_fechadas_no_periodo(self):
        it = self.itens(self.transferencias())
        ct = fluxo.cycle_time(it, pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-31"), coletado=True)
        self.assertEqual((ct["n"], ct["fechadas"]), (1, 3))              # T1 fechou antes do período
        self.assertAlmostEqual(ct["mediana"], 6.0, places=2)
        vazio = fluxo.cycle_time(it, pd.Timestamp("2026-12-01"), pd.Timestamp("2026-12-31"), coletado=True)
        self.assertFalse(vazio["disponivel"])
        self.assertIn("nenhuma issue fechada", vazio["motivo"])

    def test_cycle_time_nenhuma_passou_por_in_progress(self):
        it = self.itens({"T1": [], "T2": [], "B1": [], "N1": []})
        ct = fluxo.cycle_time(it, pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31"), coletado=True)
        self.assertFalse(ct["disponivel"])
        self.assertEqual((ct["n"], ct["cobertura"], ct["sem_inicio"]), (0, 0.0, 4))
        self.assertIn("passou por In Progress", ct["motivo"])

    def test_cycle_nao_afeta_lead_time_nem_throughput(self):
        sem, com = self.itens(), self.itens(self.transferencias())
        self.assertEqual(fluxo.lead_time(sem)["mediana"], fluxo.lead_time(com)["mediana"])
        self.assertEqual(int(fluxo.throughput_semanal(sem)["itens"].sum()),
                         int(fluxo.throughput_semanal(com)["itens"].sum()))

    def test_sem_tipo_lista_para_corrigir(self):
        snap = {"issues": {"N1": issue("N1", None, "2026-10-07T12:00:00Z", "2026-10-08T12:00:00Z", est=3),
                           "T1": issue("T1", "Task", "2026-10-07T12:00:00Z")}, "sprints": [], "releases": []}
        df, _ = agile.universo_issues(snap)
        self.assertEqual(list(fluxo.sem_tipo(df)["issue_id"]), ["N1"])

    def test_vazio_nao_quebra(self):
        it = fluxo.itens_de_fluxo(pd.DataFrame())
        self.assertTrue(it.empty)
        self.assertTrue(fluxo.throughput_semanal(it).empty)
        self.assertIsNone(fluxo.lead_time(it)["mediana"])
        self.assertIsNone(fluxo.taxa_conclusao(it, pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31"))["taxa"])

    def test_analise_critica_gerada_dos_numeros(self):
        it = self.itens()
        ini, fim = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31")
        ct = fluxo.cycle_time(self.itens(self.transferencias()), ini, fim, coletado=True)
        a = fluxo.analise_critica(fluxo.throughput_semanal(it), fluxo.lead_time(it), fluxo.taxa_conclusao(it, ini, fim),
                                  abertas=1, cycle=ct)
        self.assertIn("4 itens concluídos em 2 semanas", a["throughput"])
        self.assertIn("4 issues fecha em até 1,5 dias", a["lead_time"])
        self.assertIn("A cauda (P85) é muito maior", a["lead_time"])
        self.assertIn("4 de 5 issues ativas", a["taxa"])
        self.assertIn("2 (50%) passaram por In Progress", a["cycle_time"])
        self.assertIn("2,5 dias foram de espera", a["cycle_time"])
        self.assertNotIn("Menos da metade", a["cycle_time"])           # 50% não é "menos da metade"
        baixa = {**ct, "cobertura": 0.3, "n": 3}
        self.assertIn("Menos da metade", fluxo.analise_critica(fluxo.throughput_semanal(it), fluxo.lead_time(it), {}, 0, baixa)["cycle_time"])


if __name__ == "__main__":
    unittest.main()
