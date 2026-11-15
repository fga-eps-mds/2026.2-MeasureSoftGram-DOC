"""Casos ausentes na base histórica: coleta incompleta, pisos e regressões entre releases."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src.metrics import qrapids as q

CORE = '2026.2-MeasureSoftGram-Core'
FRONT = '2026.2-MeasureSoftGram-Front'


def resultado(chave, **kwargs):
    codigo, nome, fator, decisao = q.METRICAS[chave]
    return q.Resultado(fator, chave, nome, '', '', '', '', codigo=codigo, decisao=decisao, **kwargs)


class PortoesRegressaoTest(unittest.TestCase):
    def exemplo(self, repos=None):
        repos = repos or [CORE, FRONT]
        r6 = resultado('non_blocking_files', situacao=q.CALCULADA, numerador=2, denominador=2,
                       por_repo=pd.DataFrame({'repositorio': ['Core', 'Front'], 'valor': [1., 1.]}))
        r8 = resultado('ci_feedback_time', situacao=q.CALCULADA,
                       por_repo=pd.DataFrame({'repositorio': ['Core', 'Front'], 'mediana': [2., 3.]}))
        r3 = resultado('test_success', por_repo=pd.DataFrame({'repositorio': ['Core', 'Front'],
                                                             'zero_por_falta': ['', '']}))
        atual = pd.DataFrame([{'repositorio': r, 'metrica': m, 'valor': v}
                              for r in repos for m, v in [('coverage', 95.), ('duplicated_lines_density', 0.)]])
        return {'metricas': [r6, r8, r3]}, {'repos': repos, 'atual': atual}

    def test_indisponibilidade_nunca_comprova_atingido(self):
        self.assertNotEqual(q._situacao(.95, .9, .93, None), q.STATUS['verde'])
        self.assertEqual(q._situacao(.95, .9, .93, True), q.STATUS['verde'])
        self.assertNotEqual(q._situacao(.95, .9, .93, False), q.STATUS['verde'])

    def test_portoes_exigem_todos_os_repos_do_escopo(self):
        res, rec = self.exemplo()
        self.assertTrue(q.portoes(res, rec)['passa'].all())
        rec['atual'] = rec['atual'][rec['atual']['repositorio'] == CORE]
        res['metricas'][0].por_repo = res['metricas'][0].por_repo.iloc[:1]
        res['metricas'][1].por_repo = res['metricas'][1].por_repo.iloc[:1]
        res['metricas'][2].por_repo = res['metricas'][2].por_repo.iloc[:1]
        port = q.portoes(res, rec)
        self.assertFalse((port['passa'] == True).any())
        for detalhe in port['detalhe']:
            self.assertIn('Front', detalhe)

    def test_reprovacao_prevalece_sobre_indisponibilidade(self):
        res, rec = self.exemplo()
        rec['atual'] = rec['atual'][rec['atual']['repositorio'] == CORE].copy()
        rec['atual'].loc[rec['atual']['metrica'] == 'coverage', 'valor'] = 80.
        self.assertEqual(q.portoes(res, rec).iloc[0]['passa'], False)

    def test_filtro_de_repo_nao_exige_relatorio_dos_outros_sete(self):
        res, rec = self.exemplo([CORE])
        for r in res['metricas']:
            r.por_repo = r.por_repo.iloc[:1]
        self.assertTrue(q.portoes(res, rec)['passa'].all())
        self.assertEqual(q.repos_esperados({'repos': ['Core']}), [CORE])
        self.assertEqual(len(q.repos_esperados({})), 8)

    def test_pisos_detectam_repo_ruim_e_repo_sem_dado(self):
        res = {'metricas': [
            resultado('test_coverage', por_repo=pd.DataFrame({'repositorio': ['Core', 'Front'],
                       'valor': [.79, .99], 'zero_por_falta': ['', '']})),
            resultado('build_stability', por_repo=pd.DataFrame({'repositorio': ['Front'], 'valor': [1.]})),
        ]}
        r = q.restricoes_por_repo(res, {'repos': [CORE, FRONT]})
        self.assertEqual(list(r['situacao']), ['Abaixo do piso', 'Passa', 'Sem dado', 'Passa'])
        self.assertEqual(list(r['passa']), [False, True, False, True])

    def test_pesos_recalculam_valor_e_meta_sem_contar_fator_sem_dado(self):
        pesos = {'quality_issues_specification': 4., 'testing_status': 1., 'blocking_code': 1.}
        with patch.dict(q.PLANO['pesos_fatores'], blocking=pesos):
            self.assertAlmostEqual(q.media_fatores('blocking', {'quality_issues_specification': .8,
                                                               'testing_status': 1.}), 4.2 / 5)
            _, metas = q.metas_agregadas()
            self.assertEqual(metas['blocking'], .95)
        with patch.dict(q.PLANO['pesos_fatores'], blocking={'testing_status': -1.}):
            with self.assertRaises(ValueError):
                q.media_fatores('blocking', {'testing_status': 1.})

    def test_r2_nao_herda_snapshot_da_r1(self):
        ctx = SimpleNamespace(sonar_componentes=pd.DataFrame([
            {'repositorio': CORE, 'coleta': pd.Timestamp('2026-09-20'), 'branch': 'develop', 'arquivo': 'r1'}]))
        with patch.object(q.nq, 'avaliar', return_value={}):
            av = q.avaliacoes_por_repo(ctx, {'periodo': (pd.Timestamp('2026-09-29'), pd.Timestamp('2026-10-26')),
                                            'branch': 'develop'}, {'repos': [CORE], 'fim': pd.Timestamp('2026-10-26')})
        self.assertEqual(av, {})

    def test_detalhamento_preserva_arquivos_e_linguagem(self):
        met = {'valor': .5, 'numerador': 1, 'denominador': 2, 'zero_por_falta': '',
               'itens': pd.DataFrame({'componente': ['a.py', 'b.py'], 'passa': [True, False]})}
        av = {CORE: {'avaliacao': {'metricas': {'complexidade': met}, 'linguagem': 'py'},
                     'coleta': pd.Timestamp('2026-11-07'), 'arquivo': 'base.json'}}
        r = q._sonar_media('complexidade', av, resultado('complexity'))
        self.assertEqual(set(r.itens['componente']), {'a.py', 'b.py'})
        self.assertEqual(set(r.itens['linguagem']), {'py'})
        self.assertEqual(r.valor, .5)

    def test_catalogo_completo_e_links_estaveis(self):
        self.assertEqual(len(q.catalogo()), 44)
        self.assertEqual(len(config.QRAPIDS_DEFINICOES), 10)
        doc = (Path(__file__).resolve().parents[2] / 'docs/planejamento/selecaometricas.mdx').read_text()
        for definicao in config.QRAPIDS_DEFINICOES.values():
            self.assertIn('id="' + definicao['codigo'].lower() + '"', doc)
            self.assertTrue(definicao['fonte'])
            self.assertTrue(definicao['formula'])
        habilitaveis = q.catalogo().query('decisao == "Habilitável"')
        self.assertTrue(habilitaveis['condicao'].str.len().gt(0).all())


if __name__ == '__main__':
    unittest.main()
