"""A nota de qualidade do dashboard é a do notebook da disciplina: mesmos .json, mesmos números."""

import glob
import os
import re
import sys
import unittest
import warnings
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import referencia_notebook as nb  # noqa: E402
from src.data import sonar  # noqa: E402
from src.metrics import qualidade  # noqa: E402

NOME = re.compile(r"fga-eps-mds-(2026\.2-MeasureSoftGram-[A-Za-z]+)-(\d\d-\d\d-\d{4}-\d\d-\d\d-\d\d)-.+\.json$")


class NotebookTest(unittest.TestCase):
    def test_mesmo_resultado_do_notebook_em_todas_as_coletas(self):
        arquivos = [a for a in sorted(glob.glob(str(RAIZ / "data" / "fga-eps-mds-2026.2-*.json")))
                    if NOME.search(os.path.basename(a))]
        if not arquivos:
            self.skipTest("sem .json do pipeline em data/")
        esperado = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in arquivos:
                m = NOME.search(os.path.basename(a))
                j = nb.unmarshall(a)
                if "components" not in j:
                    continue
                df = nb.generate_component_dataframe_data(nb.metric_list, nb.metric_per_file(j),
                                                          config.QRAPIDS["linguagem"][m.group(1)])
                df["datetime"], df["repository"] = m.group(2), m.group(1)
                r = nb.create_metrics_df(df).iloc[0]
                esperado[os.path.basename(a)] = r
        _, comp = sonar.carregar_sonar([RAIZ / "data"])
        meu = qualidade.serie(comp[comp["repositorio"].isin(config.QRAPIDS["linguagem"])]).set_index("arquivo")
        pares = {"complexity": "complexidade", "comments": "comentarios", "duplication": "duplicacao",
                 "test_success": "testes_passando", "fast_tests": "testes_rapidos", "coverage": "cobertura"}
        self.assertEqual(set(esperado), set(meu.index))
        for arq, r in esperado.items():
            for a, b in pares.items():
                self.assertAlmostEqual(float(r[a]), float(meu.loc[arq, b]), places=12, msg=f"{arq} · {a}")
            total = (r["complexity"] * .33 + r["comments"] * .33 + r["duplication"] * .33) * .5 \
                + (r["test_success"] * .25 + r["fast_tests"] * .25 + r["coverage"] * .5) * .5
            self.assertAlmostEqual(total, meu.loc[arq, "total"], places=12)

    def test_rastreio_numerador_e_denominador(self):
        comp = pd.DataFrame([
            {"componente": f, "tipo": "FIL", "linguagem": "py", "metrica": m, "valor": v}
            for f, vals in {"a.py": (10, 2, 15, 0, 90, 100), "b.py": (40, 2, 5, 10, 30, 50)}.items()
            for m, v in zip(["complexity", "functions", "comment_lines_density", "duplicated_lines_density",
                             "coverage", "ncloc"], vals)] + [
            {"componente": "src", "tipo": "DIR", "linguagem": None, "metrica": m, "valor": v}
            for m, v in (("tests", 10), ("test_errors", 1), ("test_failures", 1))])
        a = qualidade.avaliar(comp, "2026.2-MeasureSoftGram-Core")
        c = a["metricas"]["complexidade"]
        self.assertEqual((c["numerador"], c["denominador"], c["valor"]), (1, 2, 0.5))   # 5 < 10, 20 ≥ 10
        self.assertEqual(list(c["itens"].query("not passa")["componente"]), ["b.py"])
        self.assertEqual(a["metricas"]["testes_passando"]["valor"], 0.8)
        r = a["metricas"]["testes_rapidos"]
        self.assertEqual(r["valor"], 0.0)                     # sem suíte: 0, marcado como falta de dado
        self.assertTrue(r["zero_por_falta"])


if __name__ == "__main__":
    unittest.main()
