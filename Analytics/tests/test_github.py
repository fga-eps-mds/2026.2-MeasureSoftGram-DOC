"""Testes de src/data/github.py (execuções de CI) e da normalização de responsáveis do Zenhub."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import github  # noqa: E402
from src.zenhub import normalizacao as norm  # noqa: E402


def run(i, concl, quando="2026-09-10T10:00:00Z"):
    return {"id": i, "name": "CI", "status": "completed", "conclusion": concl, "head_branch": "develop",
            "event": "push", "created_at": quando, "run_started_at": quando, "updated_at": quando,
            "html_url": f"https://github.com/x/actions/runs/{i}"}


class RunsTest(unittest.TestCase):
    def test_coleta_propria_completa_e_sem_duplicar(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            # arquivo antigo do metrics.yml com 2 runs; coleta do dashboard com 3 (um repetido)
            (d / "GitHub_API-Runs-fga-eps-mds-Repo-09-10-2026-10-00-00.json").write_text(
                json.dumps({"total_count": 2, "workflow_runs": [run(1, "success"), run(2, "failure")]}))
            (d / "github").mkdir()
            (d / "github" / "runs-Repo.json").write_text(json.dumps({
                "repositorio": "Repo", "coletado_em": "2026-09-28T12:00:00+00:00",
                "workflow_runs": [run(1, "success"), run(2, "failure"), run(3, "cancelled")]}))
            r = github.carregar_runs([d])
        self.assertEqual(len(r), 3)
        self.assertEqual(set(r["origem"]), {"coleta do dashboard"})
        self.assertEqual(r["conclusao"].value_counts().to_dict(), {"success": 1, "failure": 1, "cancelled": 1})


class ResponsaveisTest(unittest.TestCase):
    def test_ausente_e_diferente_de_vazio(self):
        base = {"id": "I", "number": 1, "title": "t", "state": "CLOSED"}
        self.assertNotIn("assignees", norm.issue(base))                        # campo não pedido
        self.assertEqual(norm.issue({**base, "assignees": {"nodes": []}})["assignees"], [])
        self.assertEqual(norm.issue({**base, "assignees": {"nodes": [{"login": "ana"}]},
                                     "createdAt": "2026-09-01T00:00:00Z"})["assignees"], ["ana"])


if __name__ == "__main__":
    unittest.main()
