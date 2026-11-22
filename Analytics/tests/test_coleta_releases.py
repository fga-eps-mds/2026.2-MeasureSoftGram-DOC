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


def coletar_falso(cliente, projetos, branch, log=print):
    return {"versao": 1, "branch": branch, "projetos": [{"key": projetos[0], "medidas": {"coverage": 90.3}}]}


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

    def test_nome_do_arquivo_e_atraso(self):
        self.assertEqual(cr.nome_arquivo(SERVICE, "v2.1.0"), "Service-v2.1.0.json")
        self.assertEqual(cr.nome_arquivo(SERVICE, "v2/rc 1"), "Service-v2_rc_1.json")
        self.assertEqual(cr.atraso_horas("2026-11-10T02:13:00Z", AGORA), 1.0)
        self.assertIsNone(cr.atraso_horas(None, AGORA))

    def test_doc_nao_tem_projeto_no_sonar(self):
        self.assertIsNone(cr.projeto_sonar("2026.2-MeasureSoftGram-DOC"))
        self.assertEqual(cr.projeto_sonar(SERVICE), f"fga-eps-mds_{SERVICE}")


class ExecutarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def rodar(self, sessao, sessao_assets=None, coletar=coletar_falso):
        return cr.executar(self.pasta, "Service", sessao=sessao, sessao_assets=sessao_assets, cliente=object(),
                           coletar=coletar, agora=AGORA, log=lambda *_: None)

    def test_primeira_vez_marca_existentes_como_anteriores_sem_coletar(self):
        sessao = SessaoFalsa({SERVICE: [rel("v1.0.0"), rel("v2.1.0")]})
        self.assertEqual(self.rodar(sessao), [])
        reg = cr.carregar_registro(self.pasta)["repositorios"][SERVICE]
        self.assertEqual({t: i["situacao"] for t, i in reg.items()}, {"v1.0.0": "anterior", "v2.1.0": "anterior"})
        self.assertFalse(list(self.pasta.glob("Service-*.json")))

    def test_release_nova_grava_retrato_com_a_tag(self):
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0")]}))
        gravados = self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0"), rel("v2.1.0")]}))
        self.assertEqual([g.name for g in gravados], ["Service-v2.1.0.json"])
        snap = json.loads(gravados[0].read_text(encoding="utf-8"))
        self.assertEqual(snap["branch"], "develop")
        self.assertEqual(snap["release"]["tag"], "v2.1.0")
        self.assertEqual(snap["release"]["atraso_horas"], 1.0)
        item = cr.carregar_registro(self.pasta)["repositorios"][SERVICE]["v2.1.0"]
        self.assertEqual((item["situacao"], item["asset"]), ("coletado", "sem_token"))
        # rodar de novo não coleta a mesma release outra vez
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: [rel("v2.0.0"), rel("v2.1.0")]})), [])

    def test_anexa_na_release_quando_ha_token_inclusive_pendente(self):
        self.rodar(SessaoFalsa({SERVICE: []}))
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0", id_=42)]}))          # sem token: fica pendente
        assets = SessaoFalsa()
        self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0", id_=42)]}), sessao_assets=assets)
        self.assertEqual(len(assets.uploads), 1)
        url, nome, corpo = assets.uploads[0]
        self.assertIn(f"/repos/fga-eps-mds/{SERVICE}/releases/42/assets", url)
        self.assertEqual(nome, "metricas-sonar-Service-v2.1.0.json")
        self.assertEqual(corpo["release"]["tag"], "v2.1.0")
        self.assertEqual(cr.carregar_registro(self.pasta)["repositorios"][SERVICE]["v2.1.0"]["asset"], "anexado")

    def test_falha_no_sonar_nao_registra_e_tenta_de_novo(self):
        def coletar_com_erro(cliente, projetos, branch, log=print):
            return {"projetos": [{"key": projetos[0], "erro": "HTTP 500"}]}

        self.rodar(SessaoFalsa({SERVICE: []}))
        self.assertEqual(self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}), coletar=coletar_com_erro), [])
        self.assertNotIn("v2.1.0", cr.carregar_registro(self.pasta)["repositorios"][SERVICE])
        self.assertEqual(len(self.rodar(SessaoFalsa({SERVICE: [rel("v2.1.0")]}))), 1)


if __name__ == "__main__":
    unittest.main()
