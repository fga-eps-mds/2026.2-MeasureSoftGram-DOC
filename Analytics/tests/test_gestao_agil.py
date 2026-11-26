"""Testes de src/metrics/gestao_agil.py: linhas story × sprint, totais, burndown e análises."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import agile  # noqa: E402
from src.metrics import gestao_agil as ga  # noqa: E402
from src.metrics import velocity as v  # noqa: E402

UTC = timezone.utc
S1 = datetime(2026, 9, 7, 3, 59, tzinfo=UTC)
S1_FIM = S1 + timedelta(days=7, hours=-1)
S2 = S1_FIM + timedelta(hours=1)
S2_FIM = S2 + timedelta(days=7, hours=-1)


def issue(iid, est, fechada=None, tipo="Feature"):
    return {"issue_id": iid, "number": int(iid[1:]), "title": f"Story {iid}", "repository": "repo",
            "state": "CLOSED" if fechada else "OPEN", "closed_at": fechada.isoformat() if fechada else None,
            "estimate": est, "issue_type": tipo, "parent_id": None, "is_pull_request": False, "pipeline": None,
            "url": f"https://x/{iid}"}


def ev(iid, acao, quando, est=None):
    return {"action": acao, "effective_at": quando.isoformat(), "estimate_value": est, "issue_id": iid}


class GestaoAgilTest(unittest.TestCase):
    def setUp(self):
        issues = {"A1": issue("A1", 5, S1 + timedelta(days=2)),      # planejada e concluída na S1
                  "A2": issue("A2", 3),                                # planejada, não concluída, levada à S2
                  "A3": issue("A3", 2, S1 + timedelta(days=4)),       # adicionada depois da planning e concluída
                  "A4": issue("A4", 8),                                # planejada e removida
                  "A5": issue("A5", 1, S2 + timedelta(days=1))}       # S2
        s1 = {"sprint_id": "s1", "sprint_name": "S1", "state": "CLOSED", "start_at": S1.isoformat(),
              "end_at": S1_FIM.isoformat(), "issue_ids": ["A1", "A3"], "coletada": True,
              "scope_changes": [ev("A3", "ISSUE_ADDED", S1 + timedelta(days=3), 2),
                                ev("A4", "ISSUE_REMOVED", S1 + timedelta(days=3)),
                                ev("A2", "ISSUE_REMOVED", S1_FIM + timedelta(minutes=5))]}
        s2 = {"sprint_id": "s2", "sprint_name": "S2", "state": "CLOSED", "start_at": S2.isoformat(),
              "end_at": S2_FIM.isoformat(), "issue_ids": ["A2", "A5"], "coletada": True, "scope_changes": []}
        self.snap = {"sprints": [s1, s2], "issues": issues, "releases": []}
        self.agora = S2_FIM + timedelta(days=2)
        self.vel = v.calculate_velocity(self.snap, agora=self.agora)
        universo, _ = agile.universo_issues(self.snap)
        self.linhas = ga.stories_por_sprint(self.snap, self.vel, universo)

    def linha(self, sprint, iid):
        x = self.linhas[(self.linhas["sprint"] == sprint) & (self.linhas["issue_id"] == iid)]
        return x.iloc[0]

    def test_resultado_de_cada_story(self):
        self.assertEqual(self.linha("S1", "A1")["resultado"], ga.PLANEJADA_CONCLUIDA)
        self.assertEqual(self.linha("S1", "A2")["resultado"], ga.PLANEJADA_NAO_CONCLUIDA)
        self.assertEqual(self.linha("S1", "A2")["levada_para"], "S2")
        self.assertEqual(self.linha("S1", "A3")["resultado"], ga.ADICIONADA_CONCLUIDA)
        self.assertEqual(self.linha("S1", "A4")["resultado"], ga.REMOVIDA)
        self.assertEqual(self.linha("S1", "A1")["url"], "https://x/A1")

    def test_totais_batem_com_a_velocity(self):
        r = ga.resumo_por_sprint(self.linhas).set_index("sprint")
        vv = self.vel.set_index("sprint_label")
        for s in ("S1", "S2"):
            self.assertEqual(r.loc[s, "sp_planejado"], vv.loc[s, "planned_story_points"], s)
            self.assertEqual(r.loc[s, "sp_realizado"], vv.loc[s, "completed_story_points"], s)
        self.assertEqual(r.loc["S1", "sp_planejado"], 16)          # A1 + A2 + A4
        self.assertEqual(r.loc["S1", "sp_realizado"], 7)           # A1 + A3
        self.assertEqual(r.loc["S1", "sp_realizado_fora_do_plano"], 2)
        self.assertEqual(r.loc["S1", "stories_adicionadas"], 1)
        self.assertEqual(r.loc["S1", "stories_removidas"], 1)
        rel = ga.resumo_por_release(ga.resumo_por_sprint(self.linhas))
        self.assertEqual(rel["sp_realizado"].sum(), 8)

    def test_burndown_so_com_dados_do_historico(self):
        s = self.vel[self.vel["sprint_label"] == "S1"].iloc[0]
        b = ga.burndown(self.snap, s, agora=self.agora)["dados"]
        self.assertEqual(len(b), 7)
        self.assertEqual(b["ideal"].iloc[0], 16)
        self.assertEqual(b["ideal"].iloc[-1], 0)
        self.assertEqual(b["restante"].iloc[0], 16)                # A1 + A2 + A4 no fim do 1º dia
        self.assertEqual(b["restante"].iloc[-1], 3)                # sobrou A2
        futuro = ga.burndown(self.snap, s, agora=S1 + timedelta(days=1, hours=1))["dados"]
        self.assertTrue(futuro["restante"].iloc[3:].isna().all())  # dias futuros sem ponto

    def test_analises_separam_fato_de_interpretacao(self):
        a = ga.analises(ga.resumo_por_sprint(self.linhas), self.linhas)
        self.assertIn("Stories levadas para a sprint seguinte", set(a["tema"]))
        self.assertIn("Diferença planejado × realizado", set(a["tema"]))
        self.assertTrue((a["fato"].str.len() > 0).all() and (a["interpretacao"].str.len() > 0).all())

    def test_tendencia_exige_tres_sprints(self):
        self.assertIsNone(ga.tendencia(ga.resumo_por_sprint(self.linhas))["valor"])


class SprintXSprintTest(unittest.TestCase):
    """#194 / TASK38.05.01: comparar uma sprint com outra."""

    def setUp(self):
        import pandas as pd
        self.pd = pd
        self.R = pd.DataFrame([
            {"sprint": "S10", "release": "R3", "sprint_status": "concluída", "sp_planejado": 20.0, "sp_realizado": 10.0,
             "taxa": 50.0, "sp_realizado_fora_do_plano": 2.0, "sp_adicionado": 8.0, "sp_removido": 3.0,
             "stories_levadas": 4, "sprint_inicio": datetime(2026, 11, 9, 3, 59, tzinfo=UTC),
             "sprint_fim": datetime(2026, 11, 16, 2, 59, tzinfo=UTC)},
            {"sprint": "S11", "release": "R3", "sprint_status": "concluída", "sp_planejado": 20.0, "sp_realizado": 18.0,
             "taxa": 90.0, "sp_realizado_fora_do_plano": 0.0, "sp_adicionado": 2.0, "sp_removido": 5.0,
             "stories_levadas": 1, "sprint_inicio": datetime(2026, 11, 16, 3, 59, tzinfo=UTC),
             "sprint_fim": datetime(2026, 11, 23, 2, 59, tzinfo=UTC)}])
        dia = lambda d, h=12: pd.Timestamp(2026, 11, d, h)          # noqa: E731  (hora de Brasília, sem fuso)
        self.itens = pd.DataFrame([
            {"tipo": "Task", "fechada": dia(9), "lead_dias": 2.0},
            {"tipo": "Bug", "fechada": dia(15, 23), "lead_dias": 4.0},     # último dia da S10, 23h
            {"tipo": "Task", "fechada": dia(16), "lead_dias": 6.0},
            {"tipo": "Task", "fechada": dia(18), "lead_dias": 8.0},
            {"tipo": "Bug", "fechada": dia(22), "lead_dias": 10.0},
            {"tipo": "Task", "fechada": pd.NaT, "lead_dias": float("nan")}])

    def test_valores_diferenca_e_leitura(self):
        t = ga.comparar_sprints(self.R, "S10", "S11", self.itens).set_index("chave")
        self.assertEqual((t.loc["sp_realizado", "a"], t.loc["sp_realizado", "b"]), (10, 18))
        self.assertEqual(t.loc["sp_realizado", "diferenca"], 8)
        self.assertEqual(t.loc["sp_realizado", "leitura"], "melhorou")
        self.assertEqual(t.loc["sp_adicionado", "leitura"], "melhorou")    # menos entrada no meio da sprint
        self.assertEqual(t.loc["sp_removido", "leitura"], "piorou")
        self.assertEqual(t.loc["sp_planejado", "leitura"], "")             # contexto: sem lado bom
        self.assertEqual(t.loc["sp_planejado", "diferenca"], 0)

    def test_fluxo_conta_os_fechados_dentro_dos_dias_da_sprint(self):
        t = ga.comparar_sprints(self.R, "S10", "S11", self.itens).set_index("chave")
        self.assertEqual((t.loc["fluxo_concluidos", "a"], t.loc["fluxo_concluidos", "b"]), (2, 3))
        self.assertEqual((t.loc["bugs_concluidos", "a"], t.loc["bugs_concluidos", "b"]), (1, 1))
        self.assertEqual((t.loc["lead_mediano", "a"], t.loc["lead_mediano", "b"]), (3.0, 8.0))
        self.assertEqual(t.loc["lead_mediano", "leitura"], "piorou")

    def test_sem_itens_de_fluxo_nao_inventa(self):
        t = ga.comparar_sprints(self.R, "S10", "S11", None).set_index("chave")
        self.assertTrue(self.pd.isna(t.loc["fluxo_concluidos", "a"]))
        self.assertEqual(t.loc["fluxo_concluidos", "leitura"], "")

    def test_sprint_fora_do_recorte(self):
        self.assertTrue(ga.comparar_sprints(self.R, "S10", "S99").empty)
        self.assertTrue(ga.comparar_sprints(self.pd.DataFrame(), "S10", "S11").empty)
        self.assertIsNone(ga.analise_comparacao(self.pd.DataFrame(), "S10", "S11"))

    def test_analise(self):
        tab = ga.comparar_sprints(self.R, "S10", "S11", self.itens)
        a = ga.analise_comparacao(tab, "S10", "S11")
        self.assertIn("da S10 para a S11, a entrega de US foi de 10 SP para 18 SP (50% → 90% do planejado)", a)
        self.assertIn("Melhorou:", a)
        self.assertIn("Piorou: SP removidos sem concluir (3 SP → 5 SP)", a)
        self.assertIn("proteger o escopo depois da planning", a)     # entrega melhorou; o que piorou foi o escopo
        self.assertIn("Stories levadas para a sprint seguinte (4 stories → 1 story)", a)

    def test_queda_de_entrega_vem_antes_do_escopo_na_decisao(self):
        R = self.R.copy()
        R.loc[1, ["sp_realizado", "taxa", "stories_levadas"]] = [0.0, 0.0, 6]
        a = ga.analise_comparacao(ga.comparar_sprints(R, "S10", "S11", self.itens), "S10", "S11")
        self.assertIn("investigar o que travou o aceite das US", a)
        self.assertIn("Houve também mais mudança de escopo", a)


if __name__ == "__main__":
    unittest.main()
