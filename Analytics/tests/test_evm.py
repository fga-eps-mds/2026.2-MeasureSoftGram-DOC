"""Testes do AgileEVM (``src/metrics/evm.py``) com pontos do Zenhub e custos da planilha."""

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import evm  # noqa: E402
from src.metrics import velocity as v  # noqa: E402

UTC = timezone.utc


def sprint(sid, ini, dias, ids, eventos, estado="CLOSED"):
    return {"sprint_id": sid, "sprint_name": sid, "state": estado, "start_at": ini.isoformat(),
            "end_at": (ini + timedelta(days=dias, hours=-1)).isoformat(), "issue_ids": ids,
            "scope_changes": eventos, "coletada": True}


def issue(iid, est, fechada=None):
    return {"issue_id": iid, "state": "CLOSED" if fechada else "OPEN", "closed_at": fechada, "estimate": est,
            "issue_type": "Task", "is_pull_request": False, "parent_id": None, "pipeline": None}


def ev(iid, quando, est):
    return {"action": "ISSUE_ADDED", "effective_at": quando.isoformat(), "estimate_value": est, "issue_id": iid}


# Release R1 do plano: S1 (2 semanas) e S2 (1 semana) antes de 28/09; S3 futura na R2.
S1 = datetime(2026, 9, 7, 3, 59, tzinfo=UTC)
S2 = S1 + timedelta(days=14)
S3 = S2 + timedelta(days=7)


class AgileEvmTest(unittest.TestCase):
    def setUp(self):
        self.issues = {"A": issue("A", 5, (S1 + timedelta(days=3)).isoformat()),
                       "B": issue("B", 5),
                       "C": issue("C", 10, (S2 + timedelta(days=2)).isoformat())}
        snap = {"issues": self.issues, "releases": [], "sprints": [
            sprint("s1", S1, 14, ["A", "B"], [ev("A", S1 - timedelta(hours=1), 5), ev("B", S1 - timedelta(hours=1), 5)]),
            sprint("s2", S2, 7, ["B", "C"], [ev("B", S2, 5), ev("C", S2 + timedelta(days=2), 10)], "OPEN"),
            sprint("s3", S3, 7, [], [], "OPEN")]}
        self.vel = v.calculate_velocity(snap, agora=S2 + timedelta(days=3), incluir_futuras=True)
        semanas = pd.date_range("2026-09-07", periods=4, freq="7D")
        self.plano = pd.DataFrame({"semana": semanas, "custo": [100.0] * 4})

    def calc(self, horas=None, custo_hora=None):
        return evm.agile_evm(self.vel, self.issues, self.plano, horas if horas is not None else pd.DataFrame(),
                             custo_hora)

    def test_pontos_escopo_e_indices(self):
        d = self.calc()
        r1 = d[d["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(list(r1["sprint"]), ["S1", "S2"])
        self.assertEqual(r1.loc[0, "prp_linha_de_base"], 10)           # A + B planejados na S1
        self.assertEqual(list(r1["PRP"]), [10, 20])                    # C entrou na S2 (PA = 10)
        self.assertEqual(list(r1["PA"]), [0, 10])
        self.assertEqual(list(r1["RPC"]), [5, 15])                     # A na S1, C na S2; B não conta 2x
        self.assertEqual(r1.loc[0, "BAC"], 300)                        # 3 semanas × 100
        self.assertAlmostEqual(r1.loc[0, "PPC"], 2 / 3)
        self.assertAlmostEqual(r1.loc[1, "SPI"], (15 / 20) / 1)
        # sem horas registradas o AC não é estimado: fica indisponível, e com ele CPI, CV, ETC e EAC
        self.assertTrue(r1.loc[1, "origem_do_ac"].startswith("indisponível"))
        for col in ("AC", "CPI", "CV", "ETC", "EAC"):
            self.assertTrue(math.isnan(r1.loc[1, col]), col)
        self.assertAlmostEqual(r1.loc[1, "SV"], r1.loc[1, "EV"] - r1.loc[1, "PV"])

    def test_horas_reais_viram_ac(self):
        horas = pd.DataFrame({"sprint": [1, 2], "horas": [2.0, 1.0]})
        r1 = self.calc(horas, custo_hora=10.0)
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(list(r1["AC"]), [20, 30])
        self.assertEqual(r1.loc[0, "origem_do_ac"], "horas reais × custo/hora")

    def test_sprint_sem_horas_interrompe_o_ac(self):
        horas = pd.DataFrame({"sprint": [1], "horas": [2.0]})           # S2 sem horas
        r1 = self.calc(horas, custo_hora=10.0)
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(r1.loc[0, "AC"], 20)
        self.assertAlmostEqual(r1.loc[0, "CPI"], r1.loc[0, "EV"] / 20)
        self.assertTrue(math.isnan(r1.loc[1, "AC"]))
        self.assertIn("S2", r1.loc[1, "origem_do_ac"])

    def test_horas_de_parte_do_time_nao_viram_ac(self):
        self.plano["integrantes"] = 2.0                                  # 2 ativos por semana
        horas = pd.DataFrame({"sprint": [1, 1, 2], "integrante": ["Ana", "Bia", "Ana"], "horas": [2.0, 3.0, 1.0]})
        r1 = self.calc(horas, custo_hora=10.0)
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(r1.loc[0, "AC"], 50)                            # S1: os 2 registraram
        self.assertTrue(math.isnan(r1.loc[1, "AC"]))                     # S2: só 1 de 2
        self.assertIn("1 de 2 integrantes", r1.loc[1, "origem_do_ac"])

    def test_recorte_mantem_prazo_e_tira_valores_em_reais(self):
        horas = pd.DataFrame({"sprint": [1, 2], "horas": [2.0, 1.0]})
        d = evm.agile_evm(self.vel, self.issues, self.plano, horas, 10.0, recorte="só alguns repositórios")
        r1 = d[d["release"] == "R1"].reset_index(drop=True)
        self.assertAlmostEqual(r1.loc[1, "SPI"], 0.75)                     # prazo continua
        for col in ("BAC", "PV", "EV", "AC", "CPI", "EAC"):
            self.assertTrue(math.isnan(r1.loc[1, col]), col)
        self.assertIn("só alguns repositórios", r1.loc[1, "origem_do_ac"])

    def test_recorte_com_time_usa_custo_do_time_inteiro(self):
        horas = pd.DataFrame({"sprint": [1, 2], "horas": [2.0, 1.0]})
        time = evm.agile_evm(self.vel, self.issues, self.plano, horas, 10.0)
        d = evm.agile_evm(self.vel, self.issues, self.plano, horas, 10.0, recorte="só alguns", time=time)
        a, b = d[d["release"] == "R1"].reset_index(drop=True), time[time["release"] == "R1"].reset_index(drop=True)
        for col in ("BAC", "AC", "CPI", "EAC"):
            self.assertEqual(a.loc[1, col], b.loc[1, col], col)
        self.assertIn("time inteiro", a.loc[1, "escopo_custo"])
        self.assertNotIn("motivo_valor", d)

    def test_formulas_basicas(self):
        horas = pd.DataFrame({"sprint": [1, 2], "horas": [2.0, 1.0]})
        u = self.calc(horas, custo_hora=10.0).iloc[1]
        self.assertAlmostEqual(u["SV"], u["EV"] - u["PV"])
        self.assertAlmostEqual(u["CV"], u["EV"] - u["AC"])
        self.assertAlmostEqual(u["SPI"], u["EV"] / u["PV"])
        self.assertAlmostEqual(u["CPI"], u["EV"] / u["AC"])
        self.assertAlmostEqual(u["ETC"], (u["BAC"] - u["EV"]) / u["CPI"])
        self.assertAlmostEqual(u["EAC"], u["AC"] + u["ETC"])

    def test_sprint_futura_sem_valores_e_sumario(self):
        d = self.calc()
        r2 = d[d["release"] == "R2"].iloc[0]
        self.assertTrue(math.isnan(r2["PRP"]))
        self.assertEqual(r2["BAC"], 100)
        s = evm.sumario(d).set_index("release")
        self.assertEqual(s.loc["R1", "prp_atual"], 20)
        self.assertTrue(math.isnan(s.loc["R2", "prp_atual"]))

    def test_sem_custos_nao_inventa(self):
        d = evm.agile_evm(self.vel, self.issues, pd.DataFrame(), pd.DataFrame(), None)
        self.assertTrue(math.isnan(d.iloc[0]["BAC"]))
        self.assertTrue(math.isnan(d.iloc[0]["CPI"]))
        self.assertAlmostEqual(d.iloc[1]["SPI"], 0.75)                 # SPI = APC ÷ PPC, sem custo
        self.assertEqual(d.iloc[1]["RPC"], 15)                         # pontos continuam


if __name__ == "__main__":
    unittest.main()
