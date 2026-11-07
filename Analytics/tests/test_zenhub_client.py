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


@unittest.skipUnless(__import__("shutil").which("node"), "node não instalado")
class TransporteNodeTest(unittest.TestCase):
    """O transporte em Node (fallback do TLS do Python) contra um servidor HTTP local."""

    def test_post_status_headers_e_chave_por_ambiente(self):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        recebido = {}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                recebido["auth"] = self.headers.get("Authorization")
                recebido["corpo"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(429)
                self.send_header("Retry-After", "3")
                self.end_headers()
                self.wfile.write(b'{"errors": []}')

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        r = zc._transporte_node(f"http://127.0.0.1:{srv.server_port}/", {"query": "{x}"},
                                {"Authorization": "Bearer k"}, 10)
        srv.server_close()
        self.assertEqual((r.status, r.headers.get("retry-after"), r.corpo), (429, "3", {"errors": []}))
        self.assertEqual(recebido, {"auth": "Bearer k", "corpo": {"query": "{x}"}})

    def test_erro_de_rede_vira_connection_error(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
        s.close()
        with self.assertRaises(ConnectionError):
            zc._transporte_node(f"http://127.0.0.1:{porta}/", {}, {}, 5)


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


def pagina_historico(nos, proxima=None):
    conexao = {"nodes": nos, "pageInfo": {"hasNextPage": proxima is not None, "endCursor": proxima}}
    return Resposta(200, {}, {"data": {"node": {"timelineItems": conexao}}})


def evento(em, de, para, chave="issue.change_pipeline", ws="ws", id_=None):
    return {"id": id_ or f"{em}-{para}", "key": chave, "createdAt": em,
            "data": {"workspace": {"mongo_id": ws}, "from_pipeline": {"name": de}, "to_pipeline": {"name": para}}}


class HistoricoDePipelinesTest(unittest.TestCase):
    """Cycle Time: transferências de pipeline vindas de Issue.timelineItems."""

    def test_pagina_o_historico_da_issue(self):
        f = Falso(pagina_historico([evento("2026-10-01T10:00:00Z", "Sprint Backlog", "In Progress")], "c1"),
                  pagina_historico([evento("2026-10-05T10:00:00Z", "In Progress", "Review/QA")]))
        nos = cliente(f).get_issue_timeline("i1")
        self.assertEqual(len(nos), 2)
        self.assertEqual(f.chamadas[0][0]["variables"]["issueId"], "i1")
        self.assertEqual(f.chamadas[1][0]["variables"]["after"], "c1")

    def test_so_transferencia_do_workspace_atual(self):
        from src.zenhub import normalizacao as norm
        t = norm.transferencia(evento("2026-10-01T10:00:00Z", "Sprint Backlog", "In Progress"), "ws")
        self.assertEqual(t, {"em": "2026-10-01T10:00:00Z", "de": "Sprint Backlog", "para": "In Progress"})
        self.assertIsNone(norm.transferencia(evento("2026-10-01T10:00:00Z", "a", "b", chave="issue.set_estimate"), "ws"))
        self.assertIsNone(norm.transferencia(evento("2026-10-01T10:00:00Z", "a", "b", ws="outro"), "ws"))

    def _cliente(self, historicos, falhar=()):
        outer = self

        class C:
            workspace_id = "ws"

            def __init__(self):
                self.buscadas = []

            def get_issue_timeline(self, iid):
                self.buscadas.append(iid)
                if iid in falhar:
                    raise zc.ZenhubUnavailableError("rede")
                return historicos.get(iid, [])

        outer.c = C()
        return outer.c

    @staticmethod
    def _issue(iid, estado="CLOSED", fechada="2026-10-10T00:00:00Z", repo="2026.2-MeasureSoftGram-Front", pr=False):
        return {"issue_id": iid, "number": 1, "state": estado, "closed_at": fechada, "repository": repo,
                "is_pull_request": pr}

    def test_reaproveita_issue_fechada_e_busca_aberta_ou_reaberta(self):
        from src.zenhub import coleta
        antiga = {"issues": {"f": self._issue("f"), "r": self._issue("r")},
                  "transferencias_pipeline": {"f": [{"em": "2026-10-02T00:00:00Z", "de": "a", "para": "In Progress"}],
                                              "r": []}}
        atual = {"f": self._issue("f"),                                             # fechada igual: reaproveita
                 "r": self._issue("r", fechada="2026-10-20T00:00:00Z"),              # fechada em outra data: busca
                 "a": self._issue("a", estado="OPEN", fechada=None),                 # aberta: busca
                 "pr": self._issue("pr", pr=True),                                   # PR: ignora
                 "c": self._issue("c", repo="MeasureSoftGram-Core")}                 # fora do projeto: ignora
        c = self._cliente({"a": [evento("2026-10-03T00:00:00Z", "Sprint Backlog", "In Progress")]})
        avisos = []
        saida = coleta.coletar_transferencias(c, atual, None, antiga, avisos, log=lambda *_: None)
        self.assertEqual(sorted(c.buscadas), ["a", "r"])
        self.assertEqual(saida["f"][0]["para"], "In Progress")
        self.assertEqual(saida["a"], [{"em": "2026-10-03T00:00:00Z", "de": "Sprint Backlog", "para": "In Progress"}])
        self.assertEqual(saida["r"], [])
        self.assertNotIn("pr", saida)
        self.assertNotIn("c", saida)
        self.assertEqual(avisos, [])

    def test_falha_numa_issue_vira_aviso_e_nao_derruba(self):
        from src.zenhub import coleta
        atual = {"a": self._issue("a"), "b": self._issue("b")}
        c = self._cliente({"b": [evento("2026-10-03T00:00:00Z", "x", "In Progress")]}, falhar={"a"})
        avisos = []
        saida = coleta.coletar_transferencias(c, atual, None, None, avisos, log=lambda *_: None)
        self.assertEqual(list(saida), ["b"])
        self.assertEqual(len(avisos), 1)
        self.assertIn("1 issue(s)", avisos[0])

    def test_tudo_falhando_devolve_none_para_nao_parecer_que_ninguem_se_moveu(self):
        from src.zenhub import coleta
        atual = {"a": self._issue("a"), "b": self._issue("b")}
        c = self._cliente({}, falhar={"a", "b"})
        self.assertIsNone(coleta.coletar_transferencias(c, atual, None, None, [], log=lambda *_: None))

    def test_cliente_sem_suporte_ao_historico(self):
        from src.zenhub import coleta

        class Antigo:
            workspace_id = "ws"

        self.assertIsNone(coleta.coletar_transferencias(Antigo(), {"a": self._issue("a")}, None, None, []))

    def test_auth_error_sobe(self):
        from src.zenhub import coleta

        class C:
            workspace_id = "ws"

            def get_issue_timeline(self, iid):
                raise zc.ZenhubAuthError("chave")

        with self.assertRaises(zc.ZenhubAuthError):
            coleta.coletar_transferencias(C(), {"a": self._issue("a")}, None, None, [], log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
