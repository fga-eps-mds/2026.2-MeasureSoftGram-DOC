"""Testes unitários e de integração para deduplicação por hashing e agendamento (DA-R3.03.09)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from scripts import coleta_github, coleta_sonar, saneamento_dados  # noqa: E402
from src.data import sonar_api as api  # noqa: E402
from src.zenhub import coleta as zh_coleta  # noqa: E402


class CronWorkflowTest(unittest.TestCase):
    def test_cron_agendado_uma_vez_ao_dia_as_23_59_brt(self):
        workflow = RAIZ.parent / ".github" / "workflows" / "coleta-dados.yml"
        conteudo = workflow.read_text(encoding="utf-8")
        self.assertIn('cron: "59 2 * * *"', conteudo)
        self.assertNotIn("7 11,17,23 * * *", conteudo)


class HashingPayloadTest(unittest.TestCase):
    def test_ignora_campos_volateis_e_detecta_mudanca_real(self):
        snap1 = {
            "versao": 1,
            "coletado_em": "2026-11-07T11:00:00+00:00",
            "requisicoes": 15,
            "detalhes_novos": 3,
            "projetos": [{"key": "org_Core", "medidas": {"bugs": "0", "coverage": "91.2"}}],
        }
        snap2 = {
            "versao": 1,
            "coletado_em": "2026-11-08T23:59:00+00:00",
            "requisicoes": 42,
            "detalhes_novos": 0,
            "projetos": [{"key": "org_Core", "medidas": {"coverage": "91.2", "bugs": "0"}}],
        }
        snap3 = {
            "versao": 1,
            "coletado_em": "2026-11-08T23:59:00+00:00",
            "requisicoes": 42,
            "projetos": [{"key": "org_Core", "medidas": {"coverage": "92.0", "bugs": "0"}}],
        }
        self.assertEqual(saneamento_dados.hash_payload(snap1), saneamento_dados.hash_payload(snap2))
        self.assertTrue(saneamento_dados.mesmo_payload(snap1, snap2))
        self.assertNotEqual(saneamento_dados.hash_payload(snap1), saneamento_dados.hash_payload(snap3))
        self.assertFalse(saneamento_dados.mesmo_payload(snap1, snap3))
        self.assertFalse(saneamento_dados.mesmo_payload(snap1, None))


class DeduplicacaoColetaTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pasta = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_zenhub_salvar_snapshot_evita_duplicata(self):
        snap1 = {
            "versao": 2,
            "coletado_em": "2026-11-07T11:00:00+00:00",
            "requisicoes": 10,
            "sprints": [{"sprint_id": "s1", "sprint_name": "Sprint 1"}],
            "issues": {"i1": {"number": 1, "state": "OPEN"}},
        }
        snap2 = {
            **snap1,
            "coletado_em": "2026-11-08T02:59:00+00:00",
            "requisicoes": 12,
        }
        snap3 = {
            **snap2,
            "coletado_em": "2026-11-09T02:59:00+00:00",
            "issues": {"i1": {"number": 1, "state": "CLOSED"}},
        }

        arq1 = zh_coleta.salvar_snapshot(snap1, self.pasta)
        arq2 = zh_coleta.salvar_snapshot(snap2, self.pasta)
        self.assertEqual(arq1, arq2)
        self.assertEqual(len(list(self.pasta.glob("zenhub-velocity-*.json"))), 1)

        arq3 = zh_coleta.salvar_snapshot(snap3, self.pasta)
        self.assertNotEqual(arq1, arq3)
        self.assertEqual(len(list(self.pasta.glob("zenhub-velocity-*.json"))), 2)

    @patch("scripts.coleta_sonar.sonar_api.coletar")
    @patch("scripts.coleta_sonar.sonar_api.SonarClient.do_ambiente")
    def test_sonar_executar_evita_duplicata(self, mock_cliente, mock_coletar):
        mock_cliente.return_value.requisicoes = 5
        base_projetos = [{"key": "fga-eps-mds_2026.2-MeasureSoftGram-Core", "medidas": {"bugs": "0"}}]
        mock_coletar.side_effect = [
            {"versao": 1, "coletado_em": "2026-11-07T10:00:00+00:00", "requisicoes": 5, "projetos": base_projetos},
            {"versao": 1, "coletado_em": "2026-11-08T02:59:00+00:00", "requisicoes": 5, "projetos": base_projetos},
            {
                "versao": 1,
                "coletado_em": "2026-11-09T02:59:00+00:00",
                "requisicoes": 5,
                "projetos": [{"key": "fga-eps-mds_2026.2-MeasureSoftGram-Core", "medidas": {"bugs": "1"}}],
            },
        ]

        with patch("scripts.coleta_sonar.datetime") as mock_dt:
            mock_dt.now.side_effect = [
                datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 11, 8, 2, 59, tzinfo=timezone.utc),
                datetime(2026, 11, 9, 2, 59, tzinfo=timezone.utc),
            ]
            d1 = coleta_sonar.executar(pasta=self.pasta, log=lambda _: None)
            d2 = coleta_sonar.executar(pasta=self.pasta, log=lambda _: None)
            self.assertEqual(d1, d2)
            self.assertEqual(len(list(self.pasta.glob("sonar-*.json"))), 1)

            d3 = coleta_sonar.executar(pasta=self.pasta, log=lambda _: None)
            self.assertNotEqual(d1, d3)
            self.assertEqual(len(list(self.pasta.glob("sonar-*.json"))), 2)

    def test_github_gravar_evita_reescrita_sem_mudanca(self):
        destino = self.pasta / "runs-2026.2-MeasureSoftGram-Core.json"
        cab1 = {"fonte": "API do GitHub", "coletado_em": "2026-11-07T10:00:00Z", "repositorio": "Core"}
        cab2 = {"fonte": "API do GitHub", "coletado_em": "2026-11-08T02:59:00Z", "repositorio": "Core"}
        dados1 = {"total_count": 1, "workflow_runs": [{"id": 1, "conclusion": "success"}]}
        dados2 = {"total_count": 2, "workflow_runs": [{"id": 1, "conclusion": "success"}, {"id": 2, "conclusion": "failure"}]}

        gravou1 = coleta_github._gravar(destino, cab1, dados1)
        self.assertTrue(gravou1)
        conteudo_original = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(conteudo_original["coletado_em"], "2026-11-07T10:00:00Z")

        gravou2 = coleta_github._gravar(destino, cab2, dados1)
        self.assertFalse(gravou2)
        conteudo_apos = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(conteudo_apos["coletado_em"], "2026-11-07T10:00:00Z")

        gravou3 = coleta_github._gravar(destino, cab2, dados2)
        self.assertTrue(gravou3)
        conteudo_final = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(conteudo_final["coletado_em"], "2026-11-08T02:59:00Z")


class SaneamentoDadosTest(unittest.TestCase):
    def test_saneamento_expurga_duplicatas_em_todas_as_pastas(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            pasta_sonar = raiz / "sonar"
            pasta_zh = raiz / "zenhub" / "velocity"
            pasta_sonar.mkdir(parents=True)
            pasta_zh.mkdir(parents=True)

            # 1. Sonar API: 2 iguais + 1 diferente
            (pasta_sonar / "sonar-2026-10-01T1100.json").write_text(
                json.dumps({"coletado_em": "2026-10-01T11:00:00Z", "requisicoes": 10, "projetos": [{"k": 1}]})
            )
            (pasta_sonar / "sonar-2026-10-01T1700.json").write_text(
                json.dumps({"coletado_em": "2026-10-01T17:00:00Z", "requisicoes": 12, "projetos": [{"k": 1}]})
            )
            (pasta_sonar / "sonar-2026-10-02T1100.json").write_text(
                json.dumps({"coletado_em": "2026-10-02T11:00:00Z", "requisicoes": 10, "projetos": [{"k": 2}]})
            )

            # 2. Zenhub velocity: 2 iguais + linhas-de-base preservado
            (pasta_zh / "zenhub-velocity-2026-10-01T1100.json").write_text(
                json.dumps({"coletado_em": "2026-10-01T11:00:00Z", "sprints": [1]})
            )
            (pasta_zh / "zenhub-velocity-2026-10-01T1700.json").write_text(
                json.dumps({"coletado_em": "2026-10-01T17:00:00Z", "sprints": [1]})
            )
            (pasta_zh / "linhas-de-base.json").write_text(json.dumps({"s1": 10}))

            # 3. Pipeline Sonar na raiz: 2 iguais na mesma release + 1 igual em outra release (preservado) + 1 com valor novo
            p1 = raiz / "fga-eps-mds-2026.2-MeasureSoftGram-Core-09-26-2026-18-34-32-develop.json"
            p2 = raiz / "fga-eps-mds-2026.2-MeasureSoftGram-Core-09-26-2026-18-35-16-develop.json"
            p_r3 = raiz / "fga-eps-mds-2026.2-MeasureSoftGram-Core-11-07-2026-12-47-51-develop.json"
            p3 = raiz / "fga-eps-mds-2026.2-MeasureSoftGram-Core-09-27-2026-10-00-00-develop.json"
            p1.write_text(json.dumps({"baseComponent": {"measures": [{"metric": "bugs", "value": "0"}]}}))
            p2.write_text(json.dumps({"baseComponent": {"measures": [{"metric": "bugs", "value": "0"}]}}))
            p_r3.write_text(json.dumps({"baseComponent": {"measures": [{"metric": "bugs", "value": "0"}]}}))
            p3.write_text(json.dumps({"baseComponent": {"measures": [{"metric": "bugs", "value": "1"}]}}))

            removidos = saneamento_dados.sanear_tudo(raiz, log=lambda _: None)
            self.assertEqual(len(removidos["sonar_api"]), 1)
            self.assertEqual(len(removidos["zenhub_velocity"]), 1)
            self.assertEqual(len(removidos["sonar_pipeline"]), 1)
            self.assertTrue((pasta_zh / "linhas-de-base.json").exists())
            self.assertTrue(p1.exists())
            self.assertFalse(p2.exists())
            self.assertTrue(p_r3.exists())
            self.assertTrue(p3.exists())

    def test_pasta_data_real_sem_snapshots_duplicados(self):
        pasta_dados = RAIZ / "data"
        removidos = saneamento_dados.sanear_tudo(pasta_dados, dry_run=True, log=lambda _: None)
        self.assertEqual(removidos["sonar_api"], [])
        self.assertEqual(removidos["zenhub_velocity"], [])
        self.assertEqual(removidos["sonar_pipeline"], [])


if __name__ == "__main__":
    unittest.main()
