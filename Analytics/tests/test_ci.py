"""Testes da página Integração contínua (``src/metrics/ci.py``): recorte do test.yml e leitura crítica.

Pendência da ata da R2 (#193, TASK38.05.01): a estabilidade do build filtrada pelo test.yml também na
página de CI, e análise textual no gráfico semanal.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import ci, qrapids  # noqa: E402


def semanas(taxas, execucoes=10):
    return pd.DataFrame({"semana": pd.date_range("2026-09-07", periods=len(taxas), freq="7D"),
                         "execucoes": [execucoes] * len(taxas), "sucesso": taxas})


def concluidas(ok, falhas_por_repo):
    linhas = [{"repositorio": "fga-eps-mds/2026.2-MeasureSoftGram-Front", "conclusao": "success"}] * ok
    for repo, n in falhas_por_repo.items():
        linhas += [{"repositorio": f"fga-eps-mds/2026.2-MeasureSoftGram-{repo}", "conclusao": "failure"}] * n
    return pd.DataFrame(linhas)


class SoBuildTest(unittest.TestCase):
    def setUp(self):
        self.runs = pd.DataFrame({
            "workflow": ["Rodar Testes", "Deploy Prod (self-hosted)", "Rodar Testes", "Coleta", "Rodar Testes"],
            "branch": ["develop", "main", "dependabot/pip/requests-2.32", "main", "feat/x"],
            "conclusao": ["success", "success", "failure", "success", "cancelled"]})

    def test_so_test_yml_fora_do_dependabot_com_qualquer_conclusao(self):
        self.assertEqual(list(ci.so_build(self.runs).index), [0, 4])     # cancelada fica: conta como execução

    def test_qrapids_usa_o_mesmo_recorte_e_tira_cancelada(self):
        self.assertEqual(list(qrapids.runs_de_build(self.runs).index), [0])

    def test_vazio(self):
        self.assertTrue(ci.so_build(pd.DataFrame()).empty)
        self.assertIsNone(ci.analise_critica(pd.DataFrame(), pd.DataFrame(), 95, 60))


class AnaliseCiTest(unittest.TestCase):
    def test_abaixo_da_meta_aponta_tendencia_pior_semana_e_repositorio(self):
        t = ci.analise_critica(semanas([90, 85, 50, 70, 75, 80]), concluidas(80, {"Service": 15, "Front": 5}), 95, 60)
        self.assertIn("80% das execuções do workflow de testes (test.yml)", t)
        self.assertIn("6 semanas", t)
        self.assertIn("pior semana foi a de 21/09 (50%", t)
        self.assertIn("Service concentra 15 das 20 falhas (75%)", t)
        self.assertIn("Decisão que isso apoia: tratar teste quebrado", t)

    def test_tendencia(self):
        subindo = ci.analise_critica(semanas([60, 65, 70, 90, 95, 98]), concluidas(9, {"Front": 1}), 95, 60)
        self.assertIn("a CI está estabilizando", subindo)
        caindo = ci.analise_critica(semanas([98, 95, 97, 70, 65, 60]), concluidas(9, {"Front": 1}), 95, 60)
        self.assertIn("a CI está piorando", caindo)

    def test_na_meta_nao_inventa_problema(self):
        t = ci.analise_critica(semanas([97, 96, 98]), concluidas(97, {"Front": 3}), 95, 60)
        self.assertIn("já serve de portão de qualidade", t)
        self.assertNotIn("pior semana", t)

    def test_avisa_quando_mistura_todos_os_workflows(self):
        t = ci.analise_critica(semanas([80]), concluidas(8, {"Front": 2}), 95, 60, so_testes=False)
        self.assertIn("de todos os workflows", t)
        self.assertIn("deixa de medir só o produto", t)


if __name__ == "__main__":
    unittest.main()
