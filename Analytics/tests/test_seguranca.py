"""Testes da extensão de segurança da nota Q-Rapids (src/metrics/qualidade.py)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import qualidade as nq  # noqa: E402


def avaliacao(man, con):
    return {"aspectos": {"manutenibilidade": {"valor": man}, "confiabilidade": {"valor": con}},
            "total": 0.5 * man + 0.5 * con}


class SegurancaTest(unittest.TestCase):
    def test_escala_a_ate_e(self):
        self.assertEqual([nq.nota_seguranca(r) for r in (1, 2, 3, 4, 5)], [1.0, 0.75, 0.5, 0.25, 0.0])
        self.assertIsNone(nq.nota_seguranca(None))

    def test_nota_com_seguranca_nao_muda_a_oficial(self):
        a = nq.com_seguranca(avaliacao(0.6, 0.8), rating=3, vulnerabilidades=26)
        p = nq.PESOS_SEG
        self.assertAlmostEqual(a["total_seguranca"],
                               p["manutenibilidade"] * 0.6 + p["confiabilidade"] * 0.8 + p["seguranca"] * 0.5)
        self.assertAlmostEqual(a["total"], 0.7)          # a nota do notebook continua a mesma
        self.assertEqual(a["seguranca"]["letra"], "C")
        self.assertFalse(a["veto_seguranca"])

    def test_veto_em_d_ou_e(self):
        self.assertTrue(nq.com_seguranca(avaliacao(0.9, 0.9), rating=5)["veto_seguranca"])
        self.assertTrue(nq.com_seguranca(avaliacao(0.9, 0.9), rating=4)["veto_seguranca"])

    def test_sem_dado_nao_vira_zero(self):
        a = nq.com_seguranca(avaliacao(0.9, 0.9), rating=None)
        self.assertIsNone(a["seguranca"]["valor"])
        self.assertIsNone(a["total_seguranca"])
        self.assertFalse(a["veto_seguranca"])


if __name__ == "__main__":
    unittest.main()
