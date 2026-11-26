"""Testes de src/data/contexto.py: recorte dos repositórios do projeto sem gastar memória à toa."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import contexto  # noqa: E402

DO_PROJETO = "2026.2-MeasureSoftGram-Front"
CENTRAL = "MeasureSoftGram-Front"


def ctx():
    return contexto.Contexto(hoje=pd.Timestamp("2026-11-26"), agora_utc=datetime(2026, 11, 26, tzinfo=timezone.utc))


class SoDoProjetoTest(unittest.TestCase):
    def test_sem_repositorio_de_fora_mas_indice_fora_de_ordem_renumera_como_antes(self):
        df = pd.DataFrame({"repositorio": [DO_PROJETO, DO_PROJETO], "valor": [1, 2]}, index=[7, 3])
        saida = contexto._so_do_projeto(ctx(), "SONAR", df)
        self.assertEqual(list(saida.index), [0, 1])
        self.assertEqual(list(saida["valor"]), [1, 2])
        self.assertEqual(list(df.index), [7, 3])

    def test_repositorio_de_fora_sai_e_fica_anotado(self):
        df = pd.DataFrame({"repositorio": [DO_PROJETO, CENTRAL], "valor": [1, 2]})
        c = ctx()
        saida = contexto._so_do_projeto(c, "SONAR", df)
        self.assertEqual(list(saida["repositorio"]), [DO_PROJETO])
        self.assertEqual(list(saida.index), [0])
        self.assertEqual(c.repos_ignorados, {"SONAR": {CENTRAL}})
        self.assertEqual(len(df), 2)

    def test_tabela_vazia_ou_sem_coluna_de_repositorio_passa_direto(self):
        vazia, sem_coluna = pd.DataFrame(), pd.DataFrame({"x": [1]})
        self.assertIs(contexto._so_do_projeto(ctx(), "SONAR", vazia), vazia)
        self.assertIs(contexto._so_do_projeto(ctx(), "SONAR", sem_coluna), sem_coluna)


if __name__ == "__main__":
    unittest.main()
