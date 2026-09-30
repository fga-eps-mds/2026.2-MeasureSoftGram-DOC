"""Testes da fonte SONAR: snapshot da API, série temporal, variação e cliente (transporte falso)."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import sonar as sn  # noqa: E402
from src.data import sonar_api as api  # noqa: E402
from src.metrics import qualidade  # noqa: E402


class SerieTest(unittest.TestCase):
    def setUp(self):
        linhas = []
        for repo, dia, cob, bugs in (("A", "2026-09-20", 80, 5), ("A", "2026-09-27", 84, 3), ("B", "2026-09-27", 90, 1)):
            for m, v in (("coverage", cob), ("bugs", bugs)):
                linhas.append({"repositorio": repo, "branch": "develop", "metrica": m,
                               "coleta": pd.Timestamp(dia + " 10:00"), "valor": float(v)})
        self.serie = sn.serie_temporal(pd.DataFrame(linhas), pd.DataFrame())

    def test_atual_anterior_sem_interpolar(self):
        a = sn.atual_e_anterior(self.serie, "coverage")
        self.assertAlmostEqual(a["atual"], 87.0)        # média simples de A (84) e B (90)
        self.assertAlmostEqual(a["anterior"], 80.0)     # em 20/09 só A tinha coleta
        b = sn.atual_e_anterior(self.serie, "bugs")
        self.assertEqual((b["atual"], b["anterior"]), (4.0, 5.0))   # contagens somam

    def test_serie_agregada_usa_ultimo_valor(self):
        s = sn.serie_agregada(self.serie, "bugs")
        self.assertEqual(list(s["valor"]), [5.0, 4.0])
        self.assertEqual(list(s["repos"]), [1, 2])

    def test_formatar(self):
        self.assertEqual(sn.formatar("reliability_rating", 1.0), "A")
        self.assertEqual(sn.formatar("sqale_index", 90), "1,5 h")
        self.assertEqual(sn.formatar("coverage", 82.44), "82,4%")
        self.assertEqual(sn.formatar("bugs", None), "—")


class Transporte:
    def __init__(self, respostas):
        self.respostas, self.chamadas = respostas, []

    def __call__(self, url, params, headers, timeout):
        self.chamadas.append((url, dict(params), dict(headers)))
        caminho = url.split("sonarcloud.io/")[1]
        r = self.respostas[caminho]
        return r(params) if callable(r) else r


def respostas_ok():
    return {
        "api/measures/component": lambda p: api.Resposta(404, {"errors": [{"msg": "Component 'x' on branch 'develop' not found"}]})
        if p.get("branch") else api.Resposta(200, {"component": {"measures": [
            {"metric": "bugs", "value": "3"}, {"metric": "tests", "value": "10"},
            {"metric": "test_errors", "value": "0"}, {"metric": "test_failures", "value": "0"},
            {"metric": "alert_status", "value": "ERROR"},
            {"metric": "ncloc_language_distribution", "value": "py=1200;js=300"}]}}),
        "api/measures/component_tree": api.Resposta(200, {"paging": {"total": 2}, "components": [
            {"path": "src/main.py", "qualifier": "FIL", "measures": [
                {"metric": "coverage", "value": "85.0"},
                {"metric": "complexity", "value": "4"},
                {"metric": "functions", "value": "2"},
                {"metric": "comment_lines_density", "value": "15.0"},
                {"metric": "duplicated_lines_density", "value": "0.0"},
            ]},
            {"path": "tests/test_main.py", "qualifier": "UTS", "measures": [
                {"metric": "test_execution_time", "value": "120"},
            ]},
        ]}),
        "api/measures/search_history": api.Resposta(200, {"measures": [
            {"metric": "bugs", "history": [{"date": "2026-09-20T10:00:00+0000", "value": "5"},
                                           {"date": "2026-09-27T10:00:00+0000"}]}]}),
        "api/qualitygates/project_status": api.Resposta(200, {"projectStatus": {"status": "ERROR", "conditions": [
            {"metricKey": "new_coverage", "status": "ERROR", "actualValue": "60", "errorThreshold": "80",
             "comparator": "LT"}]}}),
        "api/issues/search": api.Resposta(200, {"total": 7, "facets": [
            {"property": "severities", "values": [{"val": "MAJOR", "count": 5}, {"val": "MINOR", "count": 2}]},
            {"property": "types", "values": [{"val": "BUG", "count": 3}]}]}),
    }


class ClienteTest(unittest.TestCase):
    def test_coleta_cai_para_branch_principal_e_gera_tabelas(self):
        t = Transporte(respostas_ok())
        c = api.SonarClient(token="segredo", transporte=t, dormir=lambda s: None)
        snap = api.coletar(c, ["fga-eps-mds_2026.2-MeasureSoftGram-Core"], "develop",
                           agora=datetime(2026, 9, 27, tzinfo=timezone.utc), log=lambda m: None)
        p = snap["projetos"][0]
        self.assertIsNone(p["branch"])                              # sem análise da develop
        self.assertTrue(any("branch principal" in a for a in snap["avisos"]))
        self.assertEqual(p["linguagens"], {"py": 1200.0, "js": 300.0})
        self.assertEqual(p["quality_gate"]["status"], "ERROR")
        self.assertEqual(len(p["historico"]["bugs"]), 1)            # ponto sem valor descartado
        self.assertEqual(len(p["componentes"]), 2)
        self.assertEqual(t.chamadas[0][2]["Authorization"], "Bearer segredo")
        self.assertNotIn("segredo", repr(c))
        tab = sn.snapshot_para_tabelas(snap)
        self.assertEqual(tab["medidas"].set_index("metrica").loc["bugs", "valor"], 3.0)
        self.assertEqual(tab["severidades"]["quantidade"].sum(), 7)
        self.assertEqual(tab["quality_gate"].iloc[0]["repositorio"], "2026.2-MeasureSoftGram-Core")
        self.assertFalse(tab["componentes"].empty)
        mq = qualidade.calcular(tab["componentes"], tab["medidas"])
        self.assertEqual(len(mq), 1)
        self.assertAlmostEqual(mq.iloc[0]["total"], 1.0)

    def test_erro_de_um_projeto_nao_derruba_os_outros(self):
        r = respostas_ok()
        r["api/measures/component"] = lambda p: api.Resposta(404, {"errors": [{"msg": "Component key not found"}]}) \
            if "AI" in p["component"] else api.Resposta(200, {"component": {"measures": [{"metric": "bugs", "value": "1"}]}})
        c = api.SonarClient(transporte=Transporte(r), dormir=lambda s: None)
        snap = api.coletar(c, ["org_AI", "org_Core"], None, log=lambda m: None)
        self.assertIn("erro", snap["projetos"][0])
        self.assertNotIn("erro", snap["projetos"][1])
        self.assertEqual(len(sn.snapshot_para_tabelas(snap)["erros"]), 1)

    def test_401_e_5xx(self):
        c = api.SonarClient(transporte=lambda *a: api.Resposta(401, None), dormir=lambda s: None)
        with self.assertRaises(api.SonarAuthError):
            c.get("api/x", {})
        n = {"k": 0}

        def instavel(*a):
            n["k"] += 1
            return api.Resposta(503, None) if n["k"] < 3 else api.Resposta(200, {"ok": 1})
        c = api.SonarClient(transporte=instavel, dormir=lambda s: None)
        self.assertEqual(c.get("api/x", {}), {"ok": 1})

    def test_sem_snapshot_tabelas_vazias(self):
        self.assertTrue(all(df.empty for df in sn.snapshot_para_tabelas(None).values()))


if __name__ == "__main__":
    unittest.main()
