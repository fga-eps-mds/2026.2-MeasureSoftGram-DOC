"""Testes unitários do Canvas Analytics (``src/metrics/canvas.py``)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import agile, canvas, fluxo, qrapids  # noqa: E402


def _df_resumo(linhas: list[tuple]) -> pd.DataFrame:
    cols = ["dimensao", "indicador", "valor", "status", "leitura", "onde", "fonte"]
    return pd.DataFrame(linhas, columns=cols) if linhas else pd.DataFrame(columns=cols)


class CanvasTest(unittest.TestCase):
    def test_sem_streamlit_no_modulo(self):
        fonte = (Path(__file__).resolve().parents[1] / "src" / "metrics" / "canvas.py").read_text(encoding="utf-8")
        self.assertNotIn("import streamlit", fonte)

    def test_janelas_datas_e_limite_r3(self):
        jan_antes = canvas.janelas(pd.Timestamp("2026-11-15"))
        self.assertEqual(jan_antes["R1"], (pd.Timestamp("2026-08-24"), pd.Timestamp("2026-09-28")))
        self.assertEqual(jan_antes["R2"], (pd.Timestamp("2026-09-29"), pd.Timestamp("2026-10-26")))
        self.assertEqual(jan_antes["R3"], (pd.Timestamp("2026-10-27"), pd.Timestamp("2026-11-15")))

        jan_depois = canvas.janelas(pd.Timestamp("2026-12-10"))
        self.assertEqual(jan_depois["R3"], (pd.Timestamp("2026-10-27"), pd.Timestamp("2026-11-30")))

    def test_montar_prefixos_ausencias_e_ordem(self):
        r1 = _df_resumo([
            ("Processo", "Sucesso da CI (testes)", "80%", "warning", "leitura R1", "Integração contínua", "GITHUB"),
            ("Entrega", "SPI da Release 01", "0,90", "warning", "meta R1", "Agile EVM", "CALCULADO"),
        ])
        r2 = _df_resumo([
            ("Qualidade", "Cobertura (média dos repositórios)", "86,0%", "good", "ok R2", "Qualidade técnica", "SONAR"),
            ("Entrega", "SPI da Release 02", "0,95", "good", "meta R2", "Agile EVM", "CALCULADO"),
            ("Processo", "Sucesso da CI (testes)", "90%", "warning", "leitura R2", "Integração contínua", "GITHUB"),
        ])
        r3 = _df_resumo([
            ("Qualidade", "Cobertura (média dos repositórios)", "91,2%", "good", "meta ≥ 90%",
             "Qualidade técnica", "SONAR"),
            ("Entrega", "SPI da Release 03", "1,02", "good", "EV ÷ PV · meta ≥ 0,95", "Agile EVM", "CALCULADO"),
        ])
        df = canvas.montar({"R1": r1, "R2": r2, "R3": r3})

        # Ordem dos blocos respeitada: tecnica (Produto) → evm (Projeto) → ci (Processo)
        self.assertEqual(list(df["bloco"]), ["tecnica", "evm", "ci"])

        # Indicador ausente na R1 vira None; status e leitura vêm da R3
        cob = df[df["bloco"] == "tecnica"].iloc[0]
        self.assertIsNone(cob["R1"])
        self.assertEqual((cob["R2"], cob["R3"]), ("86,0%", "91,2%"))
        self.assertEqual((cob["status"], cob["leitura"], cob["onde"]),
                         ("good", "meta ≥ 90%", "Qualidade técnica"))

        # "SPI da Release 01" e "SPI da Release 03" caem na mesma linha com o nome da R3
        spi = df[df["bloco"] == "evm"].iloc[0]
        self.assertEqual(spi["indicador"], "SPI da Release 03")
        self.assertEqual((spi["R1"], spi["R2"], spi["R3"]), ("0,90", "0,95", "1,02"))
        self.assertEqual((spi["status"], spi["leitura"]), ("good", "EV ÷ PV · meta ≥ 0,95"))

        # R3 sem a linha → status="unavailable", leitura="sem dado na R3", nome e onde da última janela (R2)
        ci = df[df["bloco"] == "ci"].iloc[0]
        self.assertEqual(ci["indicador"], "Sucesso da CI (testes)")
        self.assertEqual((ci["R1"], ci["R2"], ci["R3"]), ("80%", "90%", None))
        self.assertEqual((ci["status"], ci["leitura"], ci["onde"]),
                         ("unavailable", "sem dado na R3", "Integração contínua"))

    def test_montar_dict_sem_r2_ou_vazio_nao_quebra(self):
        r1 = _df_resumo([("Riscos", "Decisões baseadas em dados", "2", "neutral", "l1", "Decisões", "PLANILHA")])
        r3 = _df_resumo([("Riscos", "Decisões baseadas em dados", "5", "good", "meta ≥ 5", "Decisões", "PLANILHA")])
        df = canvas.montar({"R1": r1, "R3": r3})
        self.assertEqual(len(df), 1)
        self.assertEqual((df.loc[0, "R1"], df.loc[0, "R2"], df.loc[0, "R3"]), ("2", None, "5"))
        self.assertTrue(canvas.montar({}).empty)

    def test_linhas_qrapids_mapeia_status_nan_e_vazio(self):
        vazio = canvas.linhas_qrapids(pd.DataFrame())
        self.assertTrue(vazio.empty)
        self.assertEqual(list(vazio.columns), canvas.COLUNAS)

        ind = pd.DataFrame([
            {"nome": "Product Quality", "R1": 0.98, "R2": 0.993, "Atual": 0.996,
             "meta": 0.99, "situacao": qrapids.STATUS["verde"]},
            {"nome": "Blocking", "R1": float("nan"), "R2": 0.92, "Atual": 0.93,
             "meta": 0.95, "situacao": qrapids.STATUS["amarelo"]},
            {"nome": "Process Performance", "R1": 0.50, "R2": 0.40, "Atual": 0.35,
             "meta": 0.60, "situacao": qrapids.STATUS["vermelho"]},
            {"nome": "Product Readiness", "R1": 0.80, "R2": 0.85, "Atual": float("nan"),
             "meta": 0.89, "situacao": "Parcial"},
            {"nome": "Outro", "R1": None, "R2": None, "Atual": None,
             "meta": 0.90, "situacao": qrapids.STATUS["sem"]},
        ])
        out = canvas.linhas_qrapids(ind)
        self.assertEqual(list(out["status"]), ["good", "warning", "critical", "neutral", "unavailable"])
        self.assertEqual((out.loc[0, "R1"], out.loc[0, "R2"], out.loc[0, "R3"]), ("0,98", "0,99", "1,00"))
        self.assertIsNone(out.loc[1, "R1"])
        self.assertIsNone(out.loc[3, "R3"])
        self.assertEqual(out.loc[0, "leitura"], "meta ≥ 0,99")
        self.assertEqual(out.loc[0, "onde"], "Qualidade (Q-Rapids)")

    def test_linhas_fluxo(self):
        self.assertTrue(canvas.linhas_fluxo(pd.DataFrame(), {}, False).empty)
        snap = {
            "issues": {
                "T1": {"issue_id": "T1", "number": 1, "title": "T1", "repository": "2026.2-MeasureSoftGram-Core",
                       "state": "CLOSED", "created_at": "2026-09-01T12:00:00Z", "closed_at": "2026-09-05T12:00:00Z",
                       "is_pull_request": False, "estimate": None, "issue_type": "Task", "parent_id": None,
                       "pipeline": "Closed", "pipeline_moved_at": None, "url": ""},
            },
            "sprints": [], "releases": [],
        }
        uni, _ = agile.universo_issues(snap)
        itens = fluxo.itens_de_fluxo(uni, transferencias={"T1": [{"em": "2026-09-03T12:00:00Z", "para": "In Progress"}]})
        jan = canvas.janelas(pd.Timestamp("2026-11-15"))
        out = canvas.linhas_fluxo(itens, jan, coletado=True)
        self.assertEqual(len(out), 3)
        self.assertEqual(list(out["R1"]), ["1", "4,0", "2,0"])
        self.assertEqual(out.loc[0, "R2"], "0")
        self.assertIsNone(out.loc[1, "R2"])
        self.assertIsNone(out.loc[2, "R2"])

    def test_situacao_blocos(self):
        linhas = pd.DataFrame([
            {"bloco": "tecnica", "status": "good"},
            {"bloco": "tecnica", "status": "warning"},
            {"bloco": "evm", "status": "critical"},
            {"bloco": "evm", "status": "good"},
            {"bloco": "fluxo", "status": "neutral"},
            {"bloco": "fluxo", "status": "unavailable"},
        ])
        self.assertEqual(canvas.situacao_blocos(linhas),
                         {"tecnica": "warning", "evm": "critical", "fluxo": "neutral"})


if __name__ == "__main__":
    unittest.main()
