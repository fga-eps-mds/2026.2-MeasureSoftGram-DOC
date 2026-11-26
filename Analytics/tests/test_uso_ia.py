"""Testes de src/data/uso_ia.py: leitura e validação das evidências de uso de IA."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import uso_ia  # noqa: E402


def evidencia(**extra):
    base = {"data": "2026-10-13", "area": "Código", "pedido": "corrigir o login", "onde": "Service#32",
            "link": "https://github.com/x/pull/32", "resultado": "aceito", "motivo": "testes verdes"}
    return {**base, **extra}


class EvidenciasTest(unittest.TestCase):
    def _gravar(self, d, itens):
        caminho = Path(d) / "evidencias.json"
        caminho.write_text(json.dumps(itens), encoding="utf-8")
        return caminho

    def test_arquivo_versionado_cobre_as_tres_areas_com_aceito_e_descartado(self):
        df = uso_ia.evidencias()
        self.assertEqual(set(df["area"]), set(uso_ia.AREAS))
        self.assertEqual(set(df["resultado"]), set(uso_ia.RESULTADOS))

    def test_evidencias_do_time_sao_impessoais(self):
        # a página é análise do grupo: nada em primeira pessoa nem dado pessoal de um integrante
        primeira_pessoa = re.compile(r"\b(eu|mim|meu|meus|minha|minhas|comigo)\b", re.IGNORECASE)
        df = uso_ia.evidencias()
        for coluna in ("pedido", "onde", "motivo"):
            for texto in df[coluna]:
                self.assertIsNone(primeira_pessoa.search(texto), f"{coluna}: {texto}")

    def test_planejamento_e_gestao_e_uma_area(self):
        self.assertIn("Planejamento e gestão", uso_ia.AREAS)

    def test_le_ordenado_da_mais_recente(self):
        with tempfile.TemporaryDirectory() as d:
            df = uso_ia.evidencias(self._gravar(d, [evidencia(data="2026-09-01"), evidencia(data="2026-11-01")]))
        self.assertEqual(list(df["data"].dt.strftime("%m")), ["11", "09"])

    def test_campo_ausente_e_recusado(self):
        item = evidencia()
        del item["motivo"]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "motivo"):
                uso_ia.evidencias(self._gravar(d, [item]))

    def test_resultado_ou_area_fora_da_lista_sao_recusados(self):
        for item in (evidencia(resultado="talvez"), evidencia(area="Marketing")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):
                    uso_ia.evidencias(self._gravar(d, [item]))


if __name__ == "__main__":
    unittest.main()
