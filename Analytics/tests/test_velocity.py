"""Testes dos cálculos de velocity (``src/metrics/velocity.py``).

Rodar na pasta Analytics/:  python -m unittest discover -s tests -v
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import velocity as v  # noqa: E402

UTC = timezone.utc
S1_INI = datetime(2026, 9, 7, 3, 59, tzinfo=UTC)
S1_FIM = datetime(2026, 9, 21, 2, 59, tzinfo=UTC)
S2_INI, S2_FIM = S1_FIM + timedelta(hours=1), S1_FIM + timedelta(days=7)


def t(base, dias=0, horas=0):
    return (base + timedelta(days=dias, hours=horas)).isoformat()


def issue(iid, est=None, tipo="Task", estado="OPEN", fechada=None, pipeline=None, movida=None, pai=None, pr=False):
    return {"issue_id": iid, "number": 1, "title": iid, "repository": "r", "state": estado, "closed_at": fechada,
            "is_pull_request": pr, "estimate": est, "issue_type": tipo, "parent_id": pai,
            "pipeline": pipeline, "pipeline_moved_at": movida, "url": ""}


def ev(iid, acao, quando, est=None):
    return {"action": acao, "effective_at": quando, "estimate_value": est, "issue_id": iid}


def sprint(sid, ini, fim, ids, eventos, estado="CLOSED"):
    return {"sprint_id": sid, "sprint_name": sid, "state": estado, "start_at": ini.isoformat(),
            "end_at": fim.isoformat(), "issue_ids": ids, "scope_changes": eventos, "coletada": True,
            "zenhub_completed_points": None}


def linha(df, sid):
    return df[df["sprint_id"] == sid].iloc[0]


class PlanejadoTest(unittest.TestCase):
    def setUp(self):
        # Exemplo do enunciado: A=5, B=8, C=3 no início (16 SP); D=8 entra no 3º dia.
        self.issues = {
            "A": issue("A", 5, estado="CLOSED", fechada=t(S1_INI, 2)),
            "B": issue("B", 8, estado="CLOSED", fechada=t(S1_INI, 5)),
            "C": issue("C", 3),
            "D": issue("D", 8, estado="CLOSED", fechada=t(S1_INI, 6)),
        }
        eventos = [ev("A", "ISSUE_ADDED", t(S1_INI, horas=-2), 5), ev("B", "ISSUE_ADDED", t(S1_INI, horas=-2), 8),
                   ev("C", "ISSUE_ADDED", t(S1_INI, horas=3), 3), ev("D", "ISSUE_ADDED", t(S1_INI, 3), 8)]
        self.snap = {"sprints": [sprint("S1", S1_INI, S1_FIM, ["A", "B", "C", "D"], eventos)],
                     "issues": self.issues, "releases": []}
        self.agora = S1_FIM + timedelta(days=1)

    def test_issue_adicionada_depois_nao_altera_planejado(self):
        r = linha(v.calculate_velocity(self.snap, agora=self.agora), "S1")
        self.assertEqual(r["planned_story_points"], 16)      # A + B + C (C entrou na planning)
        self.assertEqual(r["planned_issues"], 3)
        self.assertEqual(r["current_story_points"], 24)      # escopo atual separado
        self.assertEqual(r["completed_story_points"], 21)    # A + B + D
        self.assertEqual(r["completed_unplanned_story_points"], 8)
        self.assertEqual(r["velocity"], r["completed_story_points"])
        self.assertAlmostEqual(r["completion_rate"], 21 / 16 * 100)

    def test_janela_de_planning_configuravel(self):
        regras = v.Regras(janela_planning=timedelta(0))
        r = linha(v.calculate_velocity(self.snap, regras, agora=self.agora), "S1")
        self.assertEqual(r["planned_story_points"], 13)      # C entrou 3 h depois do início

    def test_estimativa_do_planejado_e_a_do_evento(self):
        self.issues["A"]["estimate"] = 13                    # re-estimada depois
        r = linha(v.calculate_velocity(self.snap, agora=self.agora), "S1")
        self.assertEqual(r["planned_story_points"], 16)      # planejado usa o estimateValue do evento
        self.assertEqual(r["completed_story_points"], 29)    # concluído usa a estimativa atual

    def test_linha_de_base_congelada_prevalece(self):
        linhas, congeladas = v.congelar_linhas_de_base(self.snap, {}, self.agora, v.Regras())
        self.assertEqual(congeladas, ["S1"])
        self.assertEqual(linhas["S1"]["planned_story_points"], 16)
        self.snap["sprints"][0]["scope_changes"].append(ev("C", "ISSUE_REMOVED", t(S1_INI, horas=1)))
        r = linha(v.calculate_velocity(self.snap, agora=self.agora, linhas_de_base=linhas), "S1")
        self.assertEqual(r["planned_story_points"], 16)
        self.assertTrue(r["baseline_source"].startswith("linha de base congelada"))

    def test_coleta_incompleta_nao_congela(self):
        self.snap["sprints"][0]["falhas"] = ["scope"]
        linhas, congeladas = v.congelar_linhas_de_base(self.snap, {}, self.agora, v.Regras())
        self.assertEqual(congeladas, [])
        r = linha(v.calculate_velocity(self.snap, agora=self.agora), "S1")
        self.assertIsNone(r["planned_story_points"])
        self.assertIn("Coleta incompleta", r["notes"])

    def test_nao_congela_antes_do_fim_da_janela(self):
        linhas, congeladas = v.congelar_linhas_de_base(self.snap, {}, S1_INI + timedelta(hours=5), v.Regras())
        self.assertEqual((linhas, congeladas), ({}, []))

    def test_sem_eventos_issues_ja_estavam_na_sprint(self):
        # O Zenhub só registra mudanças depois do início: sem eventos, quem está na sprint estava desde o início.
        self.snap["sprints"][0]["scope_changes"] = []
        r = linha(v.calculate_velocity(self.snap, agora=self.agora), "S1")
        self.assertEqual(r["planned_story_points"], 24)        # estimativa atual das issues iniciais
        self.assertIn("já estavam na sprint", r["baseline_source"])
        self.assertEqual(r["completed_story_points"], 21)

    def test_coleta_do_historico_falhou_fica_indisponivel(self):
        self.snap["sprints"][0]["scope_changes"] = []
        self.snap["sprints"][0]["falhas"] = ["scope"]
        r = linha(v.calculate_velocity(self.snap, agora=self.agora), "S1")
        self.assertIsNone(r["planned_story_points"])
        self.assertIn("indisponível", r["baseline_source"])

    def test_primeiro_evento_de_saida_estava_desde_o_inicio(self):
        s = {"issue_ids": ["A"], "scope_changes": [ev("B", "ISSUE_REMOVED", t(S1_INI, 3))]}
        ini = v.membros_iniciais(s, {"A": {"estimate": 2}, "B": {"estimate": 5}})
        self.assertEqual(ini, {"A": 2, "B": 5})
        self.assertEqual(v.membros_em(s["scope_changes"], datetime.fromisoformat(t(S1_INI, 1)), ini), {"A": 2, "B": 5})
        self.assertEqual(v.membros_em(s["scope_changes"], datetime.fromisoformat(t(S1_INI, 4)), ini), {"A": 2})

    def test_linha_de_base_de_regra_antiga_e_recalculada(self):
        antiga = {"S1": {"issues": {}, "planned_story_points": 0, "congelado_em": "2026-09-27"}}
        self.snap["sprints"][0]["scope_changes"] = []
        r = linha(v.calculate_velocity(self.snap, agora=self.agora, linhas_de_base=antiga), "S1")
        self.assertEqual(r["planned_story_points"], 24)
        novas, congeladas = v.congelar_linhas_de_base(self.snap, antiga, self.agora, v.Regras())
        self.assertEqual(novas["S1"]["regra"], v.REGRA_LINHA_DE_BASE)
        self.assertIn("S1", congeladas)


class ConcluidoTest(unittest.TestCase):
    agora = S2_FIM + timedelta(days=1)

    def calc(self, issues, s1_ids, s1_ev, s2_ids=(), s2_ev=()):
        snap = {"sprints": [sprint("S1", S1_INI, S1_FIM, list(s1_ids), list(s1_ev)),
                            sprint("S2", S2_INI, S2_FIM, list(s2_ids), list(s2_ev))],
                "issues": issues, "releases": []}
        return v.calculate_velocity(snap, agora=self.agora)

    def test_concluida_depois_do_fim_nao_conta_na_sprint(self):
        issues = {"A": issue("A", 5, estado="CLOSED", fechada=t(S1_FIM, 1))}
        df = self.calc(issues, ["A"], [ev("A", "ISSUE_ADDED", t(S1_INI, -1), 5)])
        self.assertEqual(linha(df, "S1")["completed_story_points"], 0)
        self.assertEqual(linha(df, "S2")["completed_story_points"], 0)  # não estava na S2

    def test_fechada_no_intervalo_entre_sprints_conta_na_seguinte(self):
        # S1 termina 02:59 e S2 começa 03:59 (como no Zenhub): fechar às 03:30 conta na S2
        issues = {"A": issue("A", 3, estado="CLOSED", fechada=(S1_FIM + timedelta(minutes=30)).isoformat())}
        df = self.calc(issues, [], [], ["A"], [])
        self.assertEqual(linha(df, "S1")["completed_story_points"], 0)
        self.assertEqual(linha(df, "S2")["completed_story_points"], 3)

    def calc_prazo(self, fechada):
        issues = {"A": issue("A", 3, estado="CLOSED", fechada=fechada.isoformat())}
        s1 = [ev("A", "ISSUE_REMOVED", t(S1_FIM, 0, 0.2))]        # Zenhub leva a aberta para a próxima
        s2 = [ev("A", "ISSUE_ADDED", t(S1_FIM, 0, 0.2), 3)]
        snap = {"sprints": [sprint("S1", S1_INI, S1_FIM, [], s1), sprint("S2", S2_INI, S2_FIM, ["A"], s2)],
                "issues": issues, "releases": []}
        snap["sprints"][0]["issue_ids"] = []
        # A estava na S1 desde o início (primeiro evento é a remoção)
        return v.calculate_velocity(snap, v.Regras(prazo_fechamento="08:00"), agora=self.agora)

    def test_prazo_de_fechamento_conta_na_sprint_que_terminou(self):
        df = self.calc_prazo(S1_FIM + timedelta(hours=5))           # 07:59 de Brasília do dia seguinte
        self.assertEqual(linha(df, "S1")["completed_story_points"], 3)
        self.assertEqual(linha(df, "S2")["completed_story_points"], 0)

    def test_depois_do_prazo_conta_na_sprint_seguinte(self):
        df = self.calc_prazo(S1_FIM + timedelta(hours=9))           # 11:59 de Brasília
        self.assertEqual(linha(df, "S1")["completed_story_points"], 0)
        self.assertEqual(linha(df, "S2")["completed_story_points"], 3)

    def test_concluida_antes_do_inicio_nao_conta(self):
        issues = {"A": issue("A", 5, estado="CLOSED", fechada=t(S1_INI, -3))}
        df = self.calc(issues, ["A"], [ev("A", "ISSUE_ADDED", t(S1_INI, -1), 5)])
        self.assertEqual(linha(df, "S1")["completed_story_points"], 0)

    def test_issue_movida_entre_sprints_conta_so_onde_fechou(self):
        issues = {"A": issue("A", 5, estado="CLOSED", fechada=t(S2_INI, 2))}
        s1 = [ev("A", "ISSUE_ADDED", t(S1_INI, -1), 5), ev("A", "ISSUE_REMOVED", t(S1_FIM, 0))]
        s2 = [ev("A", "ISSUE_ADDED", t(S2_INI, 0), 5)]
        df = self.calc(issues, [], s1, ["A"], s2)
        self.assertEqual(linha(df, "S1")["completed_story_points"], 0)
        self.assertEqual(linha(df, "S1")["planned_story_points"], 5)
        self.assertEqual(linha(df, "S2")["completed_story_points"], 5)

    def test_issue_sem_evento_que_esta_na_sprint_conta(self):
        # O Zenhub só registra mudanças depois do início: B já estava na sprint e não tem evento.
        issues = {"A": issue("A", 2, estado="CLOSED", fechada=t(S1_INI, 3)),
                  "B": issue("B", 3, estado="CLOSED", fechada=t(S1_INI, 4))}
        s1 = [ev("A", "ISSUE_ADDED", t(S1_INI, 1), 2)]
        self.assertEqual(linha(self.calc(issues, ["A", "B"], s1), "S1")["completed_story_points"], 5)

    def test_removida_antes_de_fechar_nao_conta(self):
        issues = {"A": issue("A", 5, estado="CLOSED", fechada=t(S1_INI, 5))}
        s1 = [ev("A", "ISSUE_ADDED", t(S1_INI, -1), 5), ev("A", "ISSUE_REMOVED", t(S1_INI, 2))]
        self.assertEqual(linha(self.calc(issues, [], s1), "S1")["completed_story_points"], 0)

    def test_so_issue_fechada_conta(self):
        # Critério de feito: a issue só precisa estar fechada. Aberta no Done não conta; fechada fora do Done conta.
        issues = {"A": issue("A", 3, pipeline="Done", movida=t(S1_INI, 4)),
                  "B": issue("B", 2, estado="CLOSED", fechada=t(S1_INI, 5), pipeline="In Progress")}
        eventos = [ev("A", "ISSUE_ADDED", t(S1_INI, -1), 3), ev("B", "ISSUE_ADDED", t(S1_INI, -1), 2)]
        self.assertEqual(linha(self.calc(issues, ["A", "B"], eventos), "S1")["completed_story_points"], 2)

    def test_sem_estimativa_conta_issue_com_zero_pontos(self):
        issues = {"A": issue("A", None, estado="CLOSED", fechada=t(S1_INI, 2)), "B": issue("B", 5)}
        eventos = [ev("A", "ISSUE_ADDED", t(S1_INI, -1), None), ev("B", "ISSUE_ADDED", t(S1_INI, -1), 5)]
        r = linha(self.calc(issues, ["A", "B"], eventos), "S1")
        self.assertEqual((r["planned_story_points"], r["planned_issues"], r["planned_unestimated_issues"]), (5, 2, 1))
        self.assertEqual((r["completed_story_points"], r["completed_issues"], r["completed_unestimated_issues"]), (0, 1, 1))

    def test_pr_epico_e_pai_com_filhas_nao_pontuam(self):
        issues = {"PR": issue("PR", 5, estado="CLOSED", fechada=t(S1_INI, 1), pr=True),
                  "EP": issue("EP", 8, tipo="Epic", estado="CLOSED", fechada=t(S1_INI, 1)),
                  "US": issue("US", 8, tipo="Feature", estado="CLOSED", fechada=t(S1_INI, 1)),
                  "T1": issue("T1", 3, estado="CLOSED", fechada=t(S1_INI, 1), pai="US")}
        eventos = [ev(i, "ISSUE_ADDED", t(S1_INI, -1), issues[i]["estimate"]) for i in issues]
        r = linha(self.calc(issues, list(issues), eventos), "S1")
        self.assertEqual((r["planned_story_points"], r["completed_story_points"]), (3, 3))

    def test_eventos_duplicados_nao_duplicam_pontos(self):
        issues = {"A": issue("A", 5, estado="CLOSED", fechada=t(S1_INI, 2))}
        e = ev("A", "ISSUE_ADDED", t(S1_INI, -1), 5)
        r = linha(self.calc(issues, ["A", "A"], [e, dict(e)]), "S1")
        self.assertEqual((r["planned_story_points"], r["completed_story_points"], r["planned_issues"],
                          r["current_issues"]), (5, 5, 1, 1))

    def test_sprint_sem_issues(self):
        r = linha(self.calc({}, [], []), "S1")
        self.assertEqual((r["planned_story_points"], r["completed_story_points"]), (0, 0))
        self.assertIsNone(r["completion_rate"])


class StatusEMediaTest(unittest.TestCase):
    def snap(self):
        return {"sprints": [sprint("S1", S1_INI, S1_FIM, [], []), sprint("S2", S2_INI, S2_FIM, [], [], "OPEN"),
                            sprint("S3", S2_FIM + timedelta(hours=1), S2_FIM + timedelta(days=7), [], [], "OPEN")],
                "issues": {}, "releases": []}

    def test_status(self):
        df = v.calculate_velocity(self.snap(), agora=S2_INI + timedelta(days=2))
        self.assertEqual(list(df["status"]), [v.STATUS_CONCLUIDA, v.STATUS_ANDAMENTO])  # S3 futura some
        todas = v.calculate_velocity(self.snap(), agora=S2_INI + timedelta(days=2), incluir_futuras=True)
        self.assertEqual(list(todas["status"])[-1], v.STATUS_FUTURA)

    def test_media_exclui_andamento_e_exige_historico(self):
        df = v.calculate_velocity(self.snap(), agora=S2_INI + timedelta(days=2))
        df.loc[df["sprint_id"] == "S1", "velocity"] = 20
        df.loc[df["sprint_id"] == "S2", "velocity"] = 99
        self.assertIsNone(v.calculate_average_velocity(df, minimo=2)["valor"])
        self.assertEqual(v.calculate_average_velocity(df, minimo=1)["valor"], 20)

    def test_media_das_concluidas(self):
        import pandas as pd
        df = pd.DataFrame({"status": [v.STATUS_CONCLUIDA] * 4 + [v.STATUS_ANDAMENTO],
                           "velocity": [24, 26, 29, 25, 18], "sprint_label": ["S1", "S2", "S3", "S4", "S5"]})
        m = v.calculate_average_velocity(df, minimo=2)
        self.assertEqual((m["valor"], m["n"]), (26, 4))

    def test_cancelada_fica_fora(self):
        regras = v.Regras(sprints_canceladas={"S1"})
        df = v.calculate_velocity(self.snap(), regras, agora=S2_FIM + timedelta(days=1))
        self.assertEqual(linha(df, "S1")["status"], v.STATUS_CANCELADA)
        self.assertEqual(v.calculate_average_velocity(df, minimo=1)["n"], 1)

    def test_completion_rate(self):
        self.assertEqual(v.calculate_completion_rate(30, 24), 80)
        self.assertIsNone(v.calculate_completion_rate(0, 5))
        self.assertIsNone(v.calculate_completion_rate(None, 5))
        self.assertIsNone(v.calculate_completion_rate(float("nan"), 5))


class ReleaseTest(unittest.TestCase):
    def test_por_issues_datas_e_calendario(self):
        s = sprint("S1", S1_INI, S1_FIM, ["A", "B"], [])
        rels = [{"release_id": "r1", "release_name": "R1", "start_on": None, "end_on": None, "issue_ids": ["A"]},
                {"release_id": "r2", "release_name": "R2", "start_on": "2026-09-01", "end_on": "2026-09-30",
                 "issue_ids": []}]
        self.assertEqual(v.associar_release(s, {"A", "B"}, rels)[:2], ("r1", "R1"))
        self.assertEqual(v.associar_release(s, {"Z"}, rels)[:2], ("r2", "R2"))
        # sem release no Zenhub: datas de entrega do plano de ensino (S1 termina 20/09 -> R1)
        self.assertEqual(v.associar_release(s, set(), [])[1:], ("R1", "plano de ensino (datas de entrega)"))
        s4 = sprint("S4", datetime(2026, 9, 28, 3, 59, tzinfo=UTC), datetime(2026, 10, 5, 2, 59, tzinfo=UTC), [], [])
        self.assertEqual(v.associar_release(s4, set(), [])[1], "R2")
        tarde = sprint("SX", datetime(2027, 1, 1, tzinfo=UTC), datetime(2027, 1, 8, tzinfo=UTC), [], [])
        self.assertEqual(v.associar_release(tarde, set(), [])[:2], (None, None))

    def test_issue_levada_para_a_proxima_sprint_nao_arrasta_a_sprint(self):
        # Release 01 termina 28/09; a S4 (até 04/10) tem issues da Release 01 levadas da S3
        rels = [{"release_id": "r1", "release_name": "Release 01", "start_on": "2026-08-10", "end_on": "2026-09-28",
                 "issue_ids": ["A"]}]
        s4 = sprint("S4", datetime(2026, 9, 28, 3, 59, tzinfo=UTC), datetime(2026, 10, 5, 2, 59, tzinfo=UTC), ["A"], [])
        self.assertEqual(v.associar_release(s4, {"A"}, rels)[1:], ("R2", "plano de ensino (datas de entrega)"))


class ComparacaoZenhubTest(unittest.TestCase):
    def test_reproduz_o_zenhub_e_explica_cada_diferenca(self):
        dentro = t(S1_INI, 2)
        issues = {"T": issue("T", 3, estado="CLOSED", fechada=dentro),
                  "PR": issue("PR", 2, tipo=None, estado="CLOSED", fechada=dentro, pr=True),
                  "US": issue("US", 8, tipo="Feature", estado="CLOSED", fechada=dentro),
                  "F": issue("F", 1, estado="CLOSED", fechada=dentro, pai="US"),
                  "P": issue("P", 5, estado="CLOSED", fechada=(S1_FIM + timedelta(hours=4)).isoformat())}
        s1 = sprint("S1", S1_INI, S1_FIM, ["T", "PR", "US", "F", "P"], [])
        s1["zenhub_completed_points"] = 14.0                           # T + PR + US + F
        snap = {"sprints": [s1], "issues": issues, "releases": []}
        regras = v.Regras(prazo_fechamento="08:00")
        agora = S1_FIM + timedelta(days=1)
        df = v.calculate_velocity(snap, regras, agora=agora)
        resumo, difs = v.comparar_com_zenhub(snap, df, regras, agora)
        r = resumo.iloc[0]
        self.assertTrue(r["reproduz"])
        self.assertEqual(r["zenhub_reproduzido"], 14)
        self.assertEqual(r["painel"], 9)                                  # T + F + P
        motivos = dict(zip(difs["issue"].str.split("#").str[0].str[-2:], difs["motivo"]))
        self.assertEqual(set(difs["sp"]), {2, 8, 5})
        self.assertTrue(any("pull request" in m for m in difs["motivo"]))
        self.assertTrue(any("pai com filhas" in m for m in difs["motivo"]))
        self.assertTrue(any("prazo de fechamento" in m for m in difs["motivo"]))
        self.assertIsNotNone(motivos)
        self.assertEqual(v.frase_comparacao(resumo, difs)[0].split(" · ")[0],
                         "S1: Zenhub 14 SP (reproduzido pelas regras do Zenhub: 14) → painel 9 SP")


class RecorteTest(unittest.TestCase):
    def test_filtro_de_repositorio_so_conta_as_issues_do_recorte(self):
        a = issue("A", 5, estado="CLOSED", fechada=t(S1_INI, 1)); a["repository"] = "front"
        b = issue("B", 3, estado="CLOSED", fechada=t(S1_INI, 1)); b["repository"] = "doc"
        snap = {"sprints": [sprint("S1", S1_INI, S1_FIM, ["A", "B"], [])], "issues": {"A": a, "B": b},
                "releases": []}
        agora = S1_FIM + timedelta(days=1)
        todas = v.calculate_velocity(snap, agora=agora).iloc[0]
        so_front = v.calculate_velocity(snap, agora=agora, filtro_issue=lambda i: i["repository"] == "front").iloc[0]
        self.assertEqual((todas["planned_story_points"], todas["completed_story_points"]), (8, 8))
        self.assertEqual((so_front["planned_story_points"], so_front["completed_story_points"]), (5, 5))


if __name__ == "__main__":
    unittest.main()
