"""Testes unitários para o script scripts/verificar_novos_prs.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from scripts import verificar_novos_prs as v


class NormalizarRepositoriosTest(unittest.TestCase):
    def test_todos_retorna_lista_completa(self):
        self.assertEqual(v.normalizar_repositorios("todos"), list(config.GITHUB_REPOS))
        self.assertEqual(v.normalizar_repositorios(""), list(config.GITHUB_REPOS))
        self.assertEqual(v.normalizar_repositorios(None), list(config.GITHUB_REPOS))

    def test_nomes_curtos(self):
        res = v.normalizar_repositorios("Service, Front")
        self.assertIn("2026.2-MeasureSoftGram-Service", res)
        self.assertIn("2026.2-MeasureSoftGram-Front", res)
        self.assertEqual(len(res), 2)

    def test_nomes_completos(self):
        res = v.normalizar_repositorios("2026.2-MeasureSoftGram-Service")
        self.assertEqual(res, ["2026.2-MeasureSoftGram-Service"])

    def test_com_prefixo_org(self):
        res = v.normalizar_repositorios("fga-eps-mds_2026.2-MeasureSoftGram-Core")
        self.assertEqual(res, ["2026.2-MeasureSoftGram-Core"])


class VerificarNovosPRsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.caminho_estado = Path(self.temp_dir.name) / ".last_pr_state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("scripts.verificar_novos_prs.consultar_prs_develop")
    def test_detecta_novo_pr_com_merged_at(self, mock_consultar):
        mock_consultar.return_value = [
            {
                "number": 101,
                "title": "feat: novo endpoint",
                "merged_at": "2026-11-06T12:00:00Z",
                "user": {"login": "dev1"},
            }
        ]

        # Estado inicial com PR antigo #99
        v.salvar_estado(
            {
                "2026.2-MeasureSoftGram-Service": {
                    "number": 99,
                    "last_merged_at": "2026-11-05T10:00:00Z",
                }
            },
            self.caminho_estado,
        )

        res = v.verificar(
            repos=["2026.2-MeasureSoftGram-Service"],
            caminho_estado=self.caminho_estado,
            log=lambda _: None,
        )

        self.assertTrue(res["houve_novo_pr"])
        self.assertIn("2026.2-MeasureSoftGram-Service", res["novos_prs"])
        self.assertEqual(res["novos_prs"]["2026.2-MeasureSoftGram-Service"][0]["number"], 101)

        # Verifica se o cursor foi atualizado
        novo_estado = v.carregar_estado(self.caminho_estado)
        self.assertEqual(novo_estado["2026.2-MeasureSoftGram-Service"]["number"], 101)
        self.assertEqual(novo_estado["2026.2-MeasureSoftGram-Service"]["last_merged_at"], "2026-11-06T12:00:00Z")

    @patch("scripts.verificar_novos_prs.consultar_prs_develop")
    def test_ignora_quando_nao_ha_pr_novo(self, mock_consultar):
        mock_consultar.return_value = [
            {
                "number": 100,
                "title": "fix: ajuste",
                "merged_at": "2026-11-05T10:00:00Z",
                "user": {"login": "dev1"},
            }
        ]

        # Estado atual igual ao retornado
        v.salvar_estado(
            {
                "2026.2-MeasureSoftGram-Service": {
                    "number": 100,
                    "last_merged_at": "2026-11-05T10:00:00Z",
                }
            },
            self.caminho_estado,
        )

        res = v.verificar(
            repos=["2026.2-MeasureSoftGram-Service"],
            caminho_estado=self.caminho_estado,
            log=lambda _: None,
        )

        self.assertFalse(res["houve_novo_pr"])
        self.assertEqual(res["novos_prs"], {})

    @patch("scripts.verificar_novos_prs.consultar_prs_develop")
    def test_forcar_coleta_retorna_true_mesmo_sem_pr_novo(self, mock_consultar):
        mock_consultar.return_value = []

        res = v.verificar(
            repos=["2026.2-MeasureSoftGram-Service"],
            force=True,
            caminho_estado=self.caminho_estado,
            log=lambda _: None,
        )

        self.assertTrue(res["houve_novo_pr"])


if __name__ == "__main__":
    unittest.main()
