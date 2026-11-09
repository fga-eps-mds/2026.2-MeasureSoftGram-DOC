"""O painel calcula os indicadores do plano de qualidade com os mesmos números do ``docs/planejamento/metas.mdx``.

Duas conferências, cada uma contra as tabelas do documento:

* **Dados de 07/11** (commit ``43c22d6``, o mesmo que o ``metas.mdx`` cita): R1, R2 e Atual com o corte em
  07/11, tolerância de arredondamento (o documento mostra 3 casas). Roda só se o histórico do git tiver o commit.
* **Dados atuais**: R1 e R2, que já fecharam, com uma folga maior (a coleta foi refeita depois de 07/11).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from src.metrics import qrapids  # noqa: E402

COMMIT_DOS_DADOS = "43c22d6"
FIM_ATUAL = "2026-11-07"
F = {"periodo": (pd.Timestamp(config.INICIO_SEMESTRE), pd.Timestamp(config.RELEASES["R3"])), "repos": [],
     "branch": "develop", "release": None}

# metas.mdx · "Cálculo dos fatores", "Cálculo dos indicadores" e "Resumo das metas": (R1, R2, Atual)
METRICAS = {"M1": (.807, .828, .835), "M2": (.980, .988, .997), "M3": (1.0, 1.0, 1.0), "M5": (.807, .855, .862),
            "M6": (None, None, .938), "M7": (.838, .932, .931), "M9": (.391, .400, .222),
            "M10": (.766, .890, .939), "DT": (.612, .648, .303)}
M8_MIN = (1.6, 2.2, 3.0)                      # medianas de test.yml, em minutos
FATORES = {"code_quality": (.894, .908, .916), "quality_issues_specification": (.838, .932, .931),
           "testing_status": (.904, .927, .931), "blocking_code": (None, None, .938),
           "issues_velocity": (.391, .400, .222), "product_stability": (.766, .890, .939),
           "activities_completion": (.612, .648, .303)}
INDICADORES = {"product_quality": (.894, .908, .916), "blocking": (.871, .929, .933),
               "process_performance": (.391, .400, .222), "product_readiness": (.757, .815, .719)}
METAS_FATOR = {"code_quality": .935, "quality_issues_specification": .95, "testing_status": .95,
               "blocking_code": 1.0, "issues_velocity": .60, "product_stability": .95, "activities_completion": .80}
METAS_INDICADOR = {"product_quality": .93, "blocking": .96, "process_performance": .60, "product_readiness": .89}
SITUACAO = {"product_quality": "🟡", "blocking": "🟡", "process_performance": "🔴", "product_readiness": "🔴"}


def _carregar(dados: Path | None):
    """Contexto do painel; com ``dados``, aponta as pastas de coleta para essa cópia de Analytics/data."""
    from src.data import contexto, github, sonar
    from src.zenhub import coleta as zh_coleta
    antes = (contexto.PASTAS_PIPELINE, sonar.PASTA_API, zh_coleta.PASTA, github.PASTA_COLETA, sonar.ultimo_snapshot.__defaults__)
    try:
        if dados is not None:
            contexto.PASTAS_PIPELINE, sonar.PASTA_API = [dados], dados / "sonar"
            zh_coleta.PASTA, github.PASTA_COLETA = dados / "zenhub" / "velocity", dados / "github"
            sonar.ultimo_snapshot.__defaults__ = (dados / "sonar",)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ctx = contexto.carregar()
    finally:
        contexto.PASTAS_PIPELINE, sonar.PASTA_API, zh_coleta.PASTA, github.PASTA_COLETA, sonar.ultimo_snapshot.__defaults__ = antes
    return ctx


def _dados_de_07_11() -> Path | None:
    try:
        topo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=RAIZ, capture_output=True, text=True,
                              check=True).stdout.strip()
        tmp = Path(tempfile.mkdtemp(prefix="dados-0711-"))
        arq = subprocess.run(["git", "archive", COMMIT_DOS_DADOS, "Analytics/data"], cwd=topo, capture_output=True,
                             check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tmp)], input=arq, check=True)
        return tmp / "Analytics" / "data"
    except Exception:  # noqa: BLE001 — sem histórico do git (clone raso) ou sem git: o teste é pulado
        return None


def _confere(teste, obtido, esperado, rotulo, tol=.0011):
    if esperado is None:
        teste.assertTrue(obtido is None or pd.isna(obtido), f"{rotulo}: esperado sem valor, veio {obtido}")
    else:
        teste.assertFalse(obtido is None or pd.isna(obtido), f"{rotulo}: sem valor")
        teste.assertAlmostEqual(float(obtido), esperado, delta=tol, msg=rotulo)


class PlanoNosDadosDe0711Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = _dados_de_07_11()
        if cls.dir is None:
            raise unittest.SkipTest(f"commit {COMMIT_DOS_DADOS} não está no histórico do git")
        cls.av = qrapids.avaliar_releases(_carregar(cls.dir), F, fim_atual=FIM_ATUAL)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "dir", None):
            shutil.rmtree(cls.dir.parents[1], ignore_errors=True)

    def test_metricas_incluidas_batem_com_o_documento(self):
        m = self.av["metricas"].set_index("codigo")
        for cod, esperado in METRICAS.items():
            for rel, e in zip(("R1", "R2", "Atual"), esperado):
                _confere(self, m.loc[cod, rel], e, f"{cod} {rel}")
        for rel, e in zip(("R1", "R2", "Atual"), M8_MIN):
            _confere(self, m.loc["M8", rel], e, f"M8 {rel}", tol=.06)

    def test_numerador_e_denominador_do_documento(self):
        """Contagens que o metas.mdx cita: M9 27/69, 62/155 e 6/27; DT 30/49, 35/54 e 10/33; M10 31/33 em 07/11."""
        def conta(rel, chave):
            r = next(x for x in self.av["res"][rel]["metricas"] if x.chave == chave)
            return int(r.numerador), int(r.denominador)
        self.assertEqual([conta(r, "team_throughput") for r in ("R1", "R2", "Atual")], [(27, 69), (62, 155), (6, 27)])
        self.assertEqual([conta(r, "development_task_completion") for r in ("R1", "R2", "Atual")],
                         [(30, 49), (35, 54), (10, 33)])
        self.assertEqual(conta("Atual", "build_stability"), (31, 33))
        self.assertEqual(conta("Atual", "non_blocking_files"), (392, 418))

    def test_fatores_batem_com_o_documento(self):
        f = self.av["fatores"].set_index("fator")
        for fc, esperado in FATORES.items():
            for rel, e in zip(("R1", "R2", "Atual"), esperado):
                _confere(self, f.loc[fc, rel], e, f"{fc} {rel}")
            _confere(self, f.loc[fc, "meta"], METAS_FATOR[fc], f"meta {fc}", tol=1e-9)

    def test_indicadores_metas_e_situacao_batem_com_o_documento(self):
        i = self.av["indicadores"].set_index("indicador")
        for ic, esperado in INDICADORES.items():
            for rel, e in zip(("R1", "R2", "Atual"), esperado):
                _confere(self, i.loc[ic, rel], e, f"{ic} {rel}")
            _confere(self, i.loc[ic, "meta"], METAS_INDICADOR[ic], f"meta {ic}", tol=1e-9)
            self.assertTrue(i.loc[ic, "situacao"].startswith(SITUACAO[ic]), f"{ic}: {i.loc[ic, 'situacao']}")
            self.assertFalse(bool(i.loc[ic, "portoes_ok"]), f"{ic}: os cinco portões reprovam em 07/11")

    def test_portoes_reprovados_como_no_documento(self):
        p = self.av["portoes"]
        self.assertEqual(len(p), 5)
        self.assertTrue((p["passa"] == False).all())    # noqa: E712
        d = " ".join(p["detalhe"])
        for trecho in ("Action 83,3%", "Plugin 89,6%", "Plugin 3,9%", "26 arquivos", "Front 7,2 min", "AI, Plugin"):
            self.assertIn(trecho, d)


class PlanoNosDadosAtuaisTest(unittest.TestCase):
    """R1 e R2 já fecharam: os dados atuais têm de dar os mesmos valores do documento, com folga maior porque a
    coleta de issues e de execuções foi refeita depois de 07/11 (ex.: S7 tem 62 issues hoje e 63 no documento)."""

    @classmethod
    def setUpClass(cls):
        cls.av = qrapids.avaliar_releases(_carregar(None), F, fim_atual=FIM_ATUAL)

    def test_r1_e_r2_batem_com_o_documento(self):
        tol = .006
        i = self.av["indicadores"].set_index("indicador")
        for ic, esperado in INDICADORES.items():
            for rel, e in zip(("R1", "R2"), esperado[:2]):
                _confere(self, i.loc[ic, rel], e, f"{ic} {rel}", tol)
        f = self.av["fatores"].set_index("fator")
        for fc, esperado in FATORES.items():
            for rel, e in zip(("R1", "R2"), esperado[:2]):
                _confere(self, f.loc[fc, rel], e, f"{fc} {rel}", tol)

    def test_nenhuma_tela_fala_em_nota(self):
        """A página não tem mais nota total nem aspecto ISO: só indicadores."""
        fonte = (RAIZ / "pages" / "qualidade.py").read_text(encoding="utf-8")
        for termo in ("Nota total", "Nota do notebook", "Evolução da nota", "Manutenibilidade", "Confiabilidade"):
            self.assertNotIn(termo, fonte)
        self.assertIn("Evolução dos indicadores", fonte)


if __name__ == "__main__":
    unittest.main()
