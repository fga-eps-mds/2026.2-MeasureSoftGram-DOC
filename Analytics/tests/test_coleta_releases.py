"""Testes do scripts/coleta_releases.py (retrato do SonarCloud por release), sem rede."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import coleta_releases as cr

SERVICE = "2026.2-MeasureSoftGram-Service"


def rel(tag, publicada="2026-11-10T02:13:00Z", draft=False, id_=1, assets=None):
    return {"id": id_, "tag_name": tag, "name": f"Release {tag}", "draft": draft, "published_at": publicada,
            "html_url": f"https://github.com/fga-eps-mds/{SERVICE}/releases/tag/{tag}", "assets": assets or []}


class Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code, self._corpo = status, corpo

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class SessaoFalsa:
    """GET devolve as releases por repositório; POST registra o upload."""

    def __init__(self, releases_por_repo=None):
        self.releases = releases_por_repo or {}
        self.uploads = []

    def get(self, url, params=None, timeout=None):
        repo = url.split("/repos/fga-eps-mds/")[1].split("/")[0]
        return Resp(200, self.releases.get(repo, []))

    def post(self, url, params=None, data=None, headers=None, timeout=None):
        self.uploads.append((url, params["name"], json.loads(data)))
        return Resp(201, {})


def medidas(*nomes):
    return [{"metric": m, "value": "1"} for m in nomes]


class SonarFalso:
    """component_tree cru: ``n`` arquivos, paginados de 500 em 500; ``erro`` simula falha."""

    def __init__(self, n=2, erro=None, base_medidas=("files", "ncloc", "test_errors", "test_failures")):
        self.n, self.erro, self.base, self.chamadas = n, erro, base_medidas, []

    def get(self, caminho, params):
        self.chamadas.append((caminho, dict(params)))
        if self.erro:
            raise cr.sonar_api.SonarError(self.erro)
        ini = (params["p"] - 1) * 500
        comps = [{"key": f"k:src/a{i}.py", "path": f"src/a{i}.py", "qualifier": "FIL", "measures": medidas("ncloc")}
                 for i in range(ini, min(ini + 500, self.n))]
        return {"paging": {"pageIndex": params["p"], "pageSize": 500, "total": self.n},
                "baseComponent": {"id": "x", "key": params["component"], "name": "Service", "qualifier": "TRK",
                                  "measures": medidas(*self.base)},
                "components": comps}


AGORA = datetime(2026, 11, 10, 3, 13, tzinfo=timezone.utc)


class RegrasTest(unittest.TestCase):
    def test_so_tags_v_e_sem_rascunho(self):
        self.assertTrue(cr.release_valida(rel("v2.1.0")))
        self.assertFalse(cr.release_valida(rel("v3.0.0", draft=True)))
        self.assertFalse(cr.release_valida(rel("1.5.5rc7")))

    def test_novas_em_ordem_e_sem_as_registradas(self):
        rels = [rel("v2.1.0", "2026-11-10T02:13:00Z"), rel("v2.0.0", "2026-10-26T16:30:00Z"), rel("v1.0.0")]
        novas = cr.releases_novas(rels, {"v1.0.0": {}})
        self.assertEqual([r["tag_name"] for r in novas], ["v2.0.0", "v2.1.0"])

    def test_nome_do_arquivo_igual_ao_do_parser_e_atraso(self):
        self.assertEqual(cr.nome_arquivo(SERVICE, "v2.1.0", AGORA),
                         f"fga-eps-mds-{SERVICE}-11-10-2026-03-13-00-v2.1.0.json")
        self.assertEqual(cr.nome_arquivo(SERVICE, "v2/rc 1", AGORA),
                         f"fga-eps-mds-{SERVICE}-11-10-2026-03-13-00-v2_rc_1.json")
        self.assertEqual(cr.atraso_horas("2026-11-10T02:13:00Z", AGORA), 1.0)
        self.assertIsNone(cr.atraso_horas(None, AGORA))

    def test_doc_nao_tem_projeto_no_sonar(self):
        self.assertIsNone(cr.projeto_sonar("2026.2-MeasureSoftGram-DOC"))
        self.assertEqual(cr.projeto_sonar(SERVICE), f"fga-eps-mds_{SERVICE}")


class ExecutarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name) / "releases"
        self.dados = Path(self.tmp.name) / "data"

    def tearDown(self):
        self.tmp.cleanup()

    def rodar(self, sessao, sessao_assets=None, cliente=None):
        return cr.executar(self.pasta, "Service", pasta_dados=self.dados, sessao=sessao, sessao_assets=sessao_assets,
                           cliente=cliente or SonarFalso(), agora=AGORA, log=lambda *_: None)

    def test_primeira_vez_marca_existentes_como_anteriores_sem_coletar(self):
        sessao = SessaoFalsa({SERVICE: [rel("v1.0.0"), rel("v2.1.0")]})
        self.assertEqual(self.rodar(sessao), [])
        reg = cr.carregar_registro(self.pasta)["repositorios"][SERVICE]
        self.assertEqual({t: i["situacao"] for t, i in reg.items()}, {"v1.0.0": "anterior", "v2.1.0": "anterior"})
        self.assertFalse(self.dados.exists() and list(self.dados.glob("*.json")))

    def test_release_nova_grava_o_json_no_formato_do_msgram(self):
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0")]}))
        sonar = SonarFalso(n=3)
        gravados = self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0"), rel("v2.1.0")]}), cliente=sonar)
        self.assertEqual([g.name for g in gravados], [f"fga-eps-mds-{SERVICE}-11-10-2026-03-13-00-v2.1.0.json"])
        self.assertEqual(gravados[0].parent, self.dados)                    # junto dos .json do pipeline
        arv = json.loads(gravados[0].read_text(encoding="utf-8"))
        self.assertEqual(set(arv), {"paging", "baseComponent", "components"})   # jsonReader do CLI
        self.assertEqual(len(arv["components"]), 3)
        self.assertEqual(set(arv["baseComponent"]) >= {"id", "key", "name", "qualifier", "measures"}, True)
        params = sonar.chamadas[0][1]
        self.assertNotIn("branch", params)                                  # branch padrão, como o parser.py
        self.assertEqual(params["metricKeys"].split(","), cr.METRICAS_MSGRAM)
        self.assertLessEqual(len(cr.METRICAS_MSGRAM), 15)                   # limite do component_tree
        item = cr.carregar_registro(self.pasta)["repositorios"][SERVICE]["v2.1.0"]
        self.assertEqual((item["situacao"], item["asset"], item["atraso_horas"]), ("coletado", "sem_token", 1.0))
        self.assertEqual(item["faltam_no_msgram"], [])
        # rodar de novo não coleta a mesma release outra vez
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0"), rel("v2.1.0")]})), [])

    def test_junta_todas_as_paginas(self):
        # o parser.py pedia só a 1ª página (500 componentes)
        self.rodar(SessaoFalsa({SERVICE: []}))
        sonar = SonarFalso(n=1203)
        gravados = self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}), cliente=sonar)
        arv = json.loads(gravados[0].read_text(encoding="utf-8"))
        self.assertEqual(len(sonar.chamadas), 3)
        self.assertEqual(len(arv["components"]), 1203)
        self.assertEqual(arv["paging"]["total"], 1203)

    def test_avisa_quando_o_msgram_vai_recusar(self):
        self.rodar(SessaoFalsa({SERVICE: []}))
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}), cliente=SonarFalso(base_medidas=("files", "ncloc")))
        item = cr.carregar_registro(self.pasta)["repositorios"][SERVICE]["v2.1.0"]
        self.assertEqual(item["faltam_no_msgram"], ["test_failures", "test_errors"])

    def test_anexa_na_release_com_o_mesmo_nome_inclusive_pendente(self):
        self.rodar(SessaoFalsa({SERVICE: []}))
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0", id_=42)]}))          # sem token: fica pendente
        assets = SessaoFalsa()
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0", id_=42)]}), sessao_assets=assets)
        self.assertEqual(len(assets.uploads), 1)
        url, nome, corpo = assets.uploads[0]
        self.assertIn(f"/repos/fga-eps-mds/{SERVICE}/releases/42/assets", url)
        self.assertEqual(nome, f"fga-eps-mds-{SERVICE}-11-10-2026-03-13-00-v2.1.0.json")
        self.assertIn("baseComponent", corpo)
        self.assertEqual(cr.carregar_registro(self.pasta)["repositorios"][SERVICE]["v2.1.0"]["asset"], "anexado")
        # já anexado: não sobe de novo
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0", id_=42)]}), sessao_assets=assets)
        self.assertEqual(len(assets.uploads), 1)

    def test_falha_no_sonar_nao_registra_e_tenta_de_novo(self):
        self.rodar(SessaoFalsa({SERVICE: []}))
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}), cliente=SonarFalso(erro="HTTP 500")), [])
        self.assertNotIn("v2.1.0", cr.carregar_registro(self.pasta)["repositorios"][SERVICE])
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: []})), [])
        self.assertEqual(len(self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}))), 1)

    def test_arvore_vazia_conta_como_falha(self):
        self.rodar(SessaoFalsa({SERVICE: []}))
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}), cliente=SonarFalso(n=0)), [])
        self.assertNotIn("v2.1.0", cr.carregar_registro(self.pasta)["repositorios"][SERVICE])


if __name__ == "__main__":
    unittest.main()
