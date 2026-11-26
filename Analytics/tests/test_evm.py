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


def issue(iid, est, fechada=None, tipo="Feature"):
    return {"issue_id": iid, "state": "CLOSED" if fechada else "OPEN", "closed_at": fechada, "estimate": est,
            "issue_type": tipo, "is_pull_request": False, "parent_id": None, "pipeline": None}


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
        # AC = custo do time nas sprints iniciadas: S1 (2 semanas) + S2 (1 semana) a 100 por semana
        self.assertEqual(list(r1["AC"]), [200, 300])
        self.assertTrue(r1.loc[1, "origem_do_ac"].startswith("custo do time"))
        self.assertAlmostEqual(r1.loc[1, "SV"], r1.loc[1, "EV"] - r1.loc[1, "PV"])

    def test_ac_e_o_custo_do_time_sem_horas(self):
        # horas e custo/hora não mudam nada: o método não usa horas
        horas = pd.DataFrame({"sprint": [1, 2], "horas": [2.0, 1.0]})
        a = self.calc()
        b = self.calc(horas, custo_hora=10.0)
        pd.testing.assert_series_equal(a["AC"], b["AC"])
        self.assertNotIn("horas_reais", a)

    def test_time_menor_custa_menos(self):
        # alguém saiu do time na S2: a semana dela custa 50 e o AC acompanha
        self.plano.loc[2, "custo"] = 50.0
        r1 = self.calc()
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(list(r1["AC"]), [200, 250])
        self.assertAlmostEqual(r1.loc[1, "CPI"], r1.loc[1, "EV"] / 250)

    def test_semana_sem_custo_deixa_ac_indisponivel(self):
        self.plano = self.plano[self.plano["semana"] != pd.Timestamp("2026-09-21")]    # semana da S2
        r1 = self.calc()
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(r1.loc[0, "AC"], 200)
        self.assertTrue(math.isnan(r1.loc[1, "AC"]))
        self.assertIn("S2", r1.loc[1, "origem_do_ac"])
        for col in ("CPI", "CV", "ETC", "EAC"):
            self.assertTrue(math.isnan(r1.loc[1, col]), col)

    def test_recorte_mantem_prazo_e_tira_valores_em_reais(self):
        d = evm.agile_evm(self.vel, self.issues, self.plano, recorte="só alguns repositórios")
        r1 = d[d["release"] == "R1"].reset_index(drop=True)
        self.assertAlmostEqual(r1.loc[1, "SPI"], 0.75)                     # prazo continua
        for col in ("BAC", "PV", "EV", "AC", "CPI", "EAC"):
            self.assertTrue(math.isnan(r1.loc[1, col]), col)
        self.assertIn("só alguns repositórios", r1.loc[1, "origem_do_ac"])

    def test_recorte_com_time_usa_custo_do_time_inteiro(self):
        time = evm.agile_evm(self.vel, self.issues, self.plano)
        d = evm.agile_evm(self.vel, self.issues, self.plano, recorte="só alguns", time=time)
        a, b = d[d["release"] == "R1"].reset_index(drop=True), time[time["release"] == "R1"].reset_index(drop=True)
        for col in ("BAC", "AC", "CPI", "EAC"):
            self.assertEqual(a.loc[1, col], b.loc[1, col], col)
        self.assertIn("time inteiro", a.loc[1, "escopo_custo"])
        self.assertNotIn("motivo_valor", d)

    def test_formulas_basicas(self):
        u = self.calc().iloc[1]
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


class AnaliseCriticaTest(unittest.TestCase):
    """DA-R3.02 (ata R2, C1.3): cada gráfico do EVM traz uma leitura crítica gerada dos números."""

    def u(self, **kw):
        base = {"PV": 100000.0, "EV": 20000.0, "AC": 90000.0, "BAC": 300000.0, "SPI": 0.2, "CPI": 0.22,
                "PRP": 100.0, "RPC": 20.0, "prp_linha_de_base": 60.0}
        return pd.Series({**base, **kw})

    def test_atraso_aponta_a_fila_de_aceite_do_po(self):
        a = evm.analise_critica(self.u(), {"issues": 12, "sp": 83.0})
        self.assertIn("atrasada em valor", a["curvas"])
        self.assertIn("12 US (83 SP) aguardam o aceite do PO", a["curvas"])
        self.assertIn("acima do entregue", a["curvas"])
        self.assertIn("fila de aceite", a["indices"])
        self.assertIn("cresceu de 60 para 100 SP", a["burndown"])

    def test_no_ritmo_nao_inventa_atraso(self):
        a = evm.analise_critica(self.u(EV=100000.0, AC=100000.0, SPI=1.0, CPI=1.0, prp_linha_de_base=100.0))
        self.assertIn("no ritmo", a["curvas"])
        self.assertNotIn("aceite", a["indices"])

    def test_sem_custo_ou_sem_us_nao_ha_leitura_inventada(self):
        a = evm.analise_critica(self.u(BAC=float("nan"), PV=float("nan"), EV=float("nan"), SPI=float("nan"),
                                       CPI=float("nan")))
        self.assertNotIn("curvas", a)
        self.assertNotIn("indices", a)
        sem_us = evm.analise_critica(self.u(PRP=0.0, RPC=0.0, prp_linha_de_base=0.0))
        self.assertIn("nenhuma US", sem_us["burndown"])


NAN = float("nan")


def linha(rel, sprint, n, ini, pv, ev, ac, bac, status="concluída", prp=10.0, apc=None, spi=None, cpi=None):
    """Linha mínima do ``agile_evm`` (só as colunas que o semestre usa)."""
    return {"release": rel, "sprint": sprint, "n": n, "status": status, "inicio_da_sprint": pd.Timestamp(ini),
            "fim_da_sprint": pd.Timestamp(ini) + pd.Timedelta(days=13), "BAC": bac, "PV": pv, "EV": ev, "AC": ac,
            "PRP": prp, "APC": apc if apc is not None else (ev / bac if bac else NAN),
            "SPI": spi if spi is not None else (ev / pv if pv else NAN),
            "CPI": cpi if cpi is not None else (ev / ac if ac else NAN)}


class EvmSemestreTest(unittest.TestCase):
    """TASK38.02.01: curvas VP, VA e CR acumuladas no semestre, não só por release."""

    def evm_tres_releases(self):
        return pd.DataFrame([
            linha("R1", "S1", 1, "2026-09-01", 50.0, 40.0, 50.0, 100.0),
            linha("R1", "S2", 2, "2026-09-15", 100.0, 80.0, 100.0, 100.0),
            linha("R2", "S3", 1, "2026-09-29", 100.0, 100.0, 100.0, 200.0),
            linha("R2", "S4", 2, "2026-10-13", 200.0, 150.0, 200.0, 200.0),
            linha("R3", "S5", 1, "2026-10-27", 60.0, 30.0, 60.0, 120.0, status="em andamento"),
            linha("R3", "S6", 2, "2026-11-10", 120.0, NAN, NAN, 120.0, status="futura", prp=NAN),
        ])

    def test_acumula_o_fechamento_das_releases_anteriores(self):
        s = evm.evm_semestre(self.evm_tres_releases())
        self.assertEqual(list(s["sprint"]), ["S1", "S2", "S3", "S4", "S5", "S6"])
        self.assertEqual(set(s["BAC"]), {420.0})                       # 100 + 200 + 120
        self.assertEqual(list(s["PV"]), [50, 100, 200, 300, 360, 420])  # o plano vai até a última sprint
        self.assertEqual(list(s["EV"][:5]), [40, 80, 180, 230, 260])    # R1 fecha em 80, R2 em 150
        self.assertEqual(list(s["AC"][:5]), [50, 100, 200, 300, 360])
        self.assertAlmostEqual(s.loc[4, "SPI"], 260 / 360)
        self.assertAlmostEqual(s.loc[4, "CPI"], 260 / 360)

    def test_sprint_futura_nao_tem_entregue_nem_gasto(self):
        s = evm.evm_semestre(self.evm_tres_releases())
        for col in ("EV", "AC", "SPI", "CPI"):
            self.assertTrue(math.isnan(s.loc[5, col]), col)

    def test_custo_indisponivel_numa_release_nao_e_inventado_depois(self):
        e = self.evm_tres_releases()
        e.loc[e["sprint"] == "S4", ["AC", "CPI"]] = NAN                # R2 fecha sem custo
        s = evm.evm_semestre(e)
        self.assertEqual(s.loc[2, "AC"], 200)
        for i in (3, 4):
            self.assertTrue(math.isnan(s.loc[i, "AC"]), i)
            self.assertTrue(math.isnan(s.loc[i, "CPI"]), i)
        self.assertFalse(math.isnan(s.loc[4, "EV"]))                   # prazo continua: não depende de custo

    def test_release_futura_sem_orcamento_fica_fora_do_bac(self):
        e = pd.concat([self.evm_tres_releases(), pd.DataFrame([
            linha("Final", "S7", 1, "2026-11-24", NAN, NAN, NAN, NAN, status="futura", prp=NAN)])],
            ignore_index=True)
        s = evm.evm_semestre(e)
        self.assertEqual(set(s["BAC"]), {420.0})                       # só o orçamento conhecido
        self.assertEqual(evm.releases_sem_orcamento(e), ["Final"])
        self.assertEqual(s.loc[4, "EV"], 260)                          # não apaga o que já foi calculado
        self.assertTrue(math.isnan(s.loc[6, "PV"]))

    def test_release_iniciada_sem_orcamento_deixa_o_plano_indisponivel_dali_em_diante(self):
        e = self.evm_tres_releases()
        e.loc[e["release"] == "R2", ["BAC", "PV", "EV"]] = NAN
        s = evm.evm_semestre(e)
        self.assertEqual(s.loc[1, "PV"], 100)                          # R1 segue com plano
        for i in (2, 3, 4):
            self.assertTrue(math.isnan(s.loc[i, "PV"]), i)
            self.assertTrue(math.isnan(s.loc[i, "SPI"]), i)

    def test_sprint_sem_nenhuma_us_entrega_zero_e_nao_apaga_o_semestre(self):
        """Caso real: a S1 caiu numa release sem US (PRP = 0) e o EVM dela tem EV vazio (0 ÷ 0)."""
        e = self.evm_tres_releases()
        e.loc[e["sprint"].isin(["S1", "S2"]), ["PRP", "EV", "APC", "SPI", "CPI"]] = [0.0, NAN, NAN, NAN, NAN]
        s = evm.evm_semestre(e)
        self.assertEqual(list(s["EV"][:5]), [0, 0, 100, 150, 180])
        f = evm.fechamento_releases(e)
        self.assertEqual(f.loc[0, "EV"], 0)
        self.assertEqual(f.loc[0, "SPI"], 0)
        self.assertTrue(f.loc[0, "sem_us"])

    def test_vazio(self):
        self.assertTrue(evm.evm_semestre(pd.DataFrame()).empty)
        self.assertEqual(evm.analise_semestre(pd.DataFrame(), pd.DataFrame()), {})

    def test_fechamento_de_cada_release(self):
        f = evm.fechamento_releases(self.evm_tres_releases())
        self.assertEqual(list(f["release"]), ["R1", "R2", "R3"])
        self.assertEqual(list(f["EV"]), [80, 150, 30])
        self.assertEqual(list(f["encerrada"]), [True, True, False])

    def test_analise_aponta_a_release_com_maior_distancia(self):
        e = self.evm_tres_releases()
        a = evm.analise_semestre(evm.evm_semestre(e), evm.fechamento_releases(e))
        self.assertIn("até a S5 (R3)", a["curvas"])
        self.assertIn("planejou R$ 360", a["curvas"])
        self.assertIn("maior distância", a["curvas"])
        self.assertIn("na R2: R$ 50", a["curvas"])
        self.assertIn("Decisão que isso apoia", a["curvas"])
        self.assertIn("SPI do semestre 0,72", a["indices"])
        self.assertIn("R1 0,80, R2 0,75", a["indices"])

    def test_no_plano_nao_inventa_atraso(self):
        e = pd.DataFrame([linha("R1", "S1", 1, "2026-09-01", 100.0, 100.0, 100.0, 100.0)])
        a = evm.analise_semestre(evm.evm_semestre(e), evm.fechamento_releases(e))
        self.assertNotIn("maior distância", a["curvas"])
        self.assertIn("no ritmo planejado", a["indices"])


class SoUsAceitaPontuaTest(AgileEvmTest):
    """Feedback da R2: SPI e CPI só com SP de US aceitas pelo PO (fechadas); Task e Bug não entram."""

    def test_task_e_bug_fechados_nao_mudam_spi_nem_cpi(self):
        antes = self.calc()
        self.issues["T"] = issue("T", 8, (S1 + timedelta(days=2)).isoformat(), tipo="Task")
        self.issues["G"] = issue("G", 3, (S1 + timedelta(days=2)).isoformat(), tipo="Bug")
        snap = {"issues": self.issues, "releases": [], "sprints": [
            sprint("s1", S1, 14, ["A", "B", "T", "G"], [ev(i, S1 - timedelta(hours=1), e)
                                                        for i, e in (("A", 5), ("B", 5), ("T", 8), ("G", 3))]),
            sprint("s2", S2, 7, ["B", "C"], [ev("B", S2, 5), ev("C", S2 + timedelta(days=2), 10)], "OPEN"),
            sprint("s3", S3, 7, [], [], "OPEN")]}
        self.vel = v.calculate_velocity(snap, agora=S2 + timedelta(days=3), incluir_futuras=True)
        depois = self.calc()
        for col in ("PRP", "RPC", "SPI", "CPI"):
            pd.testing.assert_series_equal(antes[col], depois[col], check_names=False)

    def test_us_aberta_vale_zero_ate_o_aceite(self):
        r1 = self.calc()
        r1 = r1[r1["release"] == "R1"].reset_index(drop=True)
        self.assertEqual(r1.loc[1, "RPC"], 15)                         # B (5 SP) segue aberta: não conta


if __name__ == "__main__":
    unittest.main()
