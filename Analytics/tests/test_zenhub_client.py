"""Testes do cliente do Zenhub com um transporte falso (sem rede)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.zenhub import client as zc  # noqa: E402
from src.zenhub.client import Resposta, ZenhubClient  # noqa: E402


def pagina(nos, proxima=None, extra=None):
    conexao = {"nodes": nos, "pageInfo": {"hasNextPage": proxima is not None, "endCursor": proxima}, **(extra or {})}
    return Resposta(200, {}, {"data": {"workspace": {"sprints": conexao}}})


class Falso:
    """Devolve as respostas em ordem e guarda as chamadas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, url, corpo, headers, timeout):
        self.chamadas.append((corpo, headers))
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def cliente(transporte, **kw):
    return ZenhubClient(api_key="segredo-123", workspace_id="ws", transporte=transporte, dormir=lambda s: None, **kw)


class ClienteTest(unittest.TestCase):
    def test_paginacao_e_duplicatas(self):
        f = Falso(pagina([{"id": "1"}, {"id": "2"}], "c1"), pagina([{"id": "2"}, {"id": "3"}]))
        nos = cliente(f).get_sprints()
        self.assertEqual([n["id"] for n in nos], ["1", "2", "3"])
        self.assertEqual(f.chamadas[1][0]["variables"]["after"], "c1")
        self.assertEqual(f.chamadas[0][1]["Authorization"], "Bearer segredo-123")

    def test_complexidade_reduz_a_pagina(self):
        erro = Resposta(200, {}, {"errors": [{"message": "Query has complexity of 320, which exceeds max complexity of 200"}]})
        f = Falso(erro, pagina([{"id": "1"}]))
        cliente(f).get_sprints()
        self.assertEqual(f.chamadas[1][0]["variables"]["first"], zc.PAGINA["sprints"] // 2)

    def test_401_nao_repete_e_nao_vaza_chave(self):
        f = Falso(Resposta(401, {}, "HTTP Token: Access denied."))
        c = cliente(f)
        with self.assertRaises(zc.ZenhubAuthError) as ctx:
            c.get_sprints()
        self.assertEqual(len(f.chamadas), 1)
        self.assertNotIn("segredo-123", str(ctx.exception))
        self.assertNotIn("segredo-123", repr(c))

    def test_sem_chave(self):
        with self.assertRaises(zc.ZenhubAuthError):
            ZenhubClient(api_key="", transporte=Falso())

    def test_rate_limit_espera_e_repete(self):
        esperas = []
        f = Falso(Resposta(429, {"retry-after": "7"}, {}), pagina([{"id": "1"}]))
        c = ZenhubClient(api_key="k", transporte=f, dormir=esperas.append)
        self.assertEqual(len(c.get_sprints()), 1)
        self.assertEqual(esperas, [7.0])

    def test_rate_limit_persistente(self):
        f = Falso(*[Resposta(429, {}, {})] * 3)
        with self.assertRaises(zc.ZenhubRateLimitError):
            cliente(f, max_tentativas=3).get_sprints()

    def test_timeout_e_5xx_repetem(self):
        f = Falso(TimeoutError("lento"), Resposta(503, {}, "down"), pagina([{"id": "1"}]))
        self.assertEqual(len(cliente(f).get_sprints()), 1)

    def test_indisponivel_depois_das_tentativas(self):
        f = Falso(*[ConnectionError("x")] * 3)
        with self.assertRaises(zc.ZenhubUnavailableError):
            cliente(f, max_tentativas=3).get_sprints()

    def test_erro_graphql_sem_data(self):
        f = Falso(Resposta(200, {}, {"data": None, "errors": [{"message": "Field 'x' doesn't exist"}]}))
        with self.assertRaises(zc.ZenhubError):
            cliente(f).get_sprints()

    def test_objeto_inexistente_devolve_vazio(self):
        f = Falso(Resposta(200, {}, {"data": {"node": None}}))
        self.assertEqual(cliente(f).get_sprint_issues("x"), [])


class ColetaFalhaTest(unittest.TestCase):
    def test_falha_de_rede_numa_sprint_nao_derruba_a_coleta(self):
        from datetime import datetime, timezone
        from src.zenhub import coleta

        class C:
            workspace_id, requisicoes = "ws", 0

            def get_sprints(self):
                return [{"id": "s1", "name": "S1", "state": "CLOSED",
                         "startAt": "2026-09-07T03:59:00Z", "endAt": "2026-09-21T02:59:00Z"}]

            def get_sprint_issues(self, sid):
                return []

            def get_sprint_scope_changes(self, sid):
                raise zc.ZenhubUnavailableError("rede")

            def get_releases(self):
                return []

        snap = coleta.coletar(C(), datetime(2026, 9, 27, tzinfo=timezone.utc), log=lambda *_: None)
        self.assertEqual(snap["sprints"][0]["falhas"], ["scope"])
        self.assertTrue(snap["avisos"])


class ColetaTest(unittest.TestCase):
    def test_coleta_normaliza_e_pula_futuras(self):
        from datetime import datetime, timezone
        from src.zenhub import coleta

        class C:
            workspace_id, requisicoes = "ws", 0

            def get_sprints(self):
                return [{"id": "s1", "name": None, "generatedName": "Sprint 1", "state": "CLOSED",
                         "startAt": "2026-09-07T03:59:00Z", "endAt": "2026-09-21T02:59:00Z"},
                        {"id": "s2", "name": "Futura", "state": "OPEN",
                         "startAt": "2030-01-01T00:00:00Z", "endAt": "2030-01-08T00:00:00Z"}]

            def get_sprint_issues(self, sid):
                return [{"id": "i1", "number": 1, "title": "t", "state": "CLOSED", "closedAt": "2026-09-10T00:00:00Z",
                         "pullRequest": False, "repository": {"name": "r"}, "estimate": {"value": 3},
                         "issueType": {"name": "Task"}, "parentIssue": None,
                         "pipelineIssue": {"latestTransferTime": None, "pipeline": {"name": "Closed"}}}]

            def get_sprint_scope_changes(self, sid):
                return [{"action": "ISSUE_ADDED", "effectiveAt": "2026-09-07T04:00:00Z", "estimateValue": 3,
                         "issue": {"id": "i1"}}, {"action": "ISSUE_ADDED", "effectiveAt": "2026-09-08T00:00:00Z",
                                                  "estimateValue": None, "issue": {"id": "i9"}}], 2

            def get_issue(self, iid):
                return {"id": iid, "number": 9, "title": "saiu", "state": "OPEN", "issueType": None}

            def get_releases(self):
                return [{"id": "r1", "title": "R1", "state": "OPEN"}]

            def get_release_issue_ids(self, rid):
                return ["i1"]

        snap = coleta.coletar(C(), datetime(2026, 9, 27, tzinfo=timezone.utc), log=lambda *_: None)
        s1, s2 = snap["sprints"]
        self.assertEqual(s1["sprint_name"], "Sprint 1")
        self.assertEqual(s1["issue_ids"], ["i1"])
        self.assertFalse(s2["coletada"])
        self.assertEqual(snap["issues"]["i1"]["estimate"], 3.0)
        self.assertIn("i9", snap["issues"])              # detalhada à parte
        self.assertEqual(snap["releases"][0]["issue_ids"], ["i1"])


if __name__ == "__main__":
    unittest.main()
