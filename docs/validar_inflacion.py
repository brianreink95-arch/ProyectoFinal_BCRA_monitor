"""Pruebas económicas e integración offline: python docs/validar_inflacion.py."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import base_a
from lib.common import build_analytical_run, fingerprint
from lib.precios import cargar_ipc, validar_ipc, ajustar_montos, validar_referencias_ipc


class Precios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ipc, cls.metadata = cargar_ipc(ROOT)

    def adjust(self, values, dates, **kwargs):
        frame = pd.DataFrame({'fecha': dates, 'nominal': values})
        return ajustar_montos(frame, {'nominal': 'real'}, self.ipc, **kwargs)

    def test_base_nominal_igual_real(self):
        result = self.adjust([1000], ['2016-12-01'])
        self.assertEqual(result.real.iloc[0], 1000)
        self.assertEqual(result.ipc_fecha_mes.iloc[0], '2016-12-31')

    def test_nivel_oficial_nacional_no_gba(self):
        self.assertEqual(self.ipc.set_index('fecha_mes').loc['2017-01-31', 'ipc_nacional'], 101.5859)

    def test_formula_e_identidad_crecimiento_real(self):
        result = self.adjust([1000, 1100], ['2016-12-31', '2017-01-31'])
        ratio = 101.5859 / 100
        self.assertAlmostEqual(result.real.iloc[1], 1100 / ratio)
        self.assertAlmostEqual(result.real.iloc[1] / result.real.iloc[0] - 1, 1.1 / ratio - 1)

    def test_cero_observado_no_es_hueco(self):
        r = self.adjust([0, np.nan], ['2017-01-01'] * 2,
                        observado=pd.Series([True, False]))
        self.assertEqual(r.real.iloc[0], 0)
        self.assertTrue(pd.isna(r.real.iloc[1]))
        self.assertEqual(r.estado_ajuste_ipc.tolist(), ['ajustado', 'sin_observacion'])

    def test_no_arrastrar_ipc_a_mes_no_publicado(self):
        future = pd.Timestamp(self.ipc.fecha_mes.max()) + pd.offsets.MonthEnd(1)
        r = self.adjust([50], [future])
        self.assertEqual(r.estado_ajuste_ipc.iloc[0], 'ipc_no_publicado')
        self.assertTrue(pd.isna(r.real.iloc[0]))
        self.assertEqual(r.nominal.iloc[0], 50)

    def test_historia_anterior_conserva_nominal(self):
        r = self.adjust([50], ['2016-11-30'], elegible=pd.Series([False]))
        self.assertEqual(r.estado_ajuste_ipc.iloc[0], 'anterior_base')
        self.assertTrue(pd.isna(r.real.iloc[0]))

    def test_unidad_no_validada_no_habilita_importe(self):
        r = self.adjust([50], ['2017-01-31'], elegible=pd.Series([False]))
        self.assertEqual(r.estado_ajuste_ipc.iloc[0], 'unidad_no_validada')
        self.assertTrue(pd.isna(r.real.iloc[0]))

    def test_tasa_excluida_conserva_valor(self):
        r = self.adjust([20], ['2017-01-31'], no_aplica=pd.Series([True]))
        self.assertEqual(r.nominal.iloc[0], 20)
        self.assertEqual(r.estado_ajuste_ipc.iloc[0], 'no_aplica')
        self.assertTrue(pd.isna(r.real.iloc[0]))

    def test_ratio_mismo_mes_invariante(self):
        r = self.adjust([20, 80], ['2017-01-31'] * 2)
        self.assertAlmostEqual(r.real.iloc[0] / r.real.sum(), .2)

    def test_indice_duplicado_rechazado(self):
        with self.assertRaises(ValueError):
            validar_ipc(pd.concat([self.ipc, self.ipc.iloc[:1]]))

    def test_indice_cero_negativo_infinito_rechazados(self):
        for value in [0, -1, np.inf, np.nan]:
            with self.subTest(value=value):
                f = self.ipc.copy(); f.loc[0, 'ipc_nacional'] = value
                with self.assertRaises(ValueError): validar_ipc(f)

    def test_cambio_base_rechazado(self):
        f = self.ipc.copy(); f['periodo_base'] = '2025-12'
        with self.assertRaises(ValueError): validar_ipc(f)

    def test_mes_ausente_rechazado_sin_interpolacion(self):
        with self.assertRaises(ValueError): validar_ipc(self.ipc.drop(index=1))

    def test_factor_alterado_rechazado(self):
        f = self.ipc.copy(); f.loc[1, 'factor_deflacion'] = 1
        with self.assertRaises(ValueError): validar_ipc(f)

    def test_fecha_nula_rechazada(self):
        with self.assertRaises(ValueError): self.adjust([10], [None])

    def test_fk_ipc_huerfana_rechazada(self):
        r = self.adjust([50], ['2017-01-31']); r['ipc_fecha_mes'] = '2030-01-31'
        with self.assertRaises(ValueError): validar_referencias_ipc({'prueba':r}, self.ipc)


class Integracion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='validar_inflacion_')
        before = fingerprint(ROOT)
        with patch('requests.Session.get', side_effect=AssertionError('Red prohibida en offline')), \
             patch('requests.get', side_effect=AssertionError('Red prohibida en offline')):
            cls.dataset_dir, cls.meta = build_analytical_run(ROOT, Path(cls.temp.name) / 'salidas')
        assert fingerprint(ROOT) == before
        cls.a = pd.read_csv(cls.dataset_dir / 'base_a/observaciones.csv')
        cls.c = pd.read_csv(cls.dataset_dir / 'base_c/empresa_mes.csv', dtype={'cuit_normalizado':'string'})
        cls.debt = pd.read_csv(cls.dataset_dir / 'base_c/deuda_entidad_mes.csv', dtype={'cuit_normalizado':'string'})

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_nominales_a_iguales_fuente_y_excepcion(self):
        h, _ = base_a.load_a_inputs(ROOT, ROOT / 'config/catalogo_base_a.csv')
        h = h.assign(fecha=h.fecha.dt.strftime('%Y-%m-%d'))
        j = self.a.merge(h[['idVariable','fecha','valor','valor_eda']],
                        left_on=['serie_id','fecha'], right_on=['idVariable','fecha'], validate='one_to_one')
        self.assertEqual(len(j), len(h))
        np.testing.assert_allclose(j.valor_original, j.valor, rtol=0, atol=0)
        np.testing.assert_allclose(j.valor_analitico, j.valor_eda, rtol=0, atol=0, equal_nan=True)

    def test_seis_stocks_y_solo_meses_con_evidencia(self):
        adjusted = self.a[self.a.estado_ajuste_ipc.eq('ajustado')]
        self.assertEqual(set(adjusted.serie_id), set(base_a.UNIDADES_ICC))
        eligible, _ = base_a.unidades_icc_validadas(ROOT, self.a)
        self.assertTrue(eligible.loc[adjusted.index].all())
        self.assertTrue(adjusted.fecha.ge('2016-12-31').all())

    def test_ninguna_tasa_ajustada(self):
        cat = pd.read_csv(ROOT / 'config/catalogo_base_a.csv')
        ids = cat.loc[~cat.ajuste_ipc, 'serie_id']
        self.assertTrue(self.a.loc[self.a.serie_id.isin(ids), 'valor_constante_dic2016'].isna().all())

    def test_c_reconciliacion_por_empresa_mes(self):
        sums = self.debt.groupby(['cuit_normalizado','fecha']).monto_miles_pesos_dic2016.sum(min_count=1)
        panel = self.c.set_index(['cuit_normalizado','fecha'])
        np.testing.assert_allclose(sums, panel.deuda_total_positiva_constante_dic2016.reindex(sums.index), rtol=1e-10)
        self.assertTrue(self.c.loc[~self.c.mes_observado,'deuda_total_positiva_constante_dic2016'].isna().all())
        self.assertTrue(self.c.loc[self.c.deuda_total_positiva.eq(0),'deuda_total_positiva_constante_dic2016'].eq(0).all())

    def test_c_universo_y_ratios_preservados(self):
        from lib.common import get_pipeline
        _, master, _, _, _, _, old = get_pipeline('c').load_c(ROOT, self.meta['summary']['c']['run_id'])
        self.assertEqual(set(self.c.cuit_normalizado), set(master.cuit_normalizado))
        self.assertEqual(len(self.c), len(old))
        old = old.assign(fecha=old.fecha.dt.strftime('%Y-%m-%d'))
        keys = ['cuit_normalizado','fecha']
        j = self.c.merge(old, on=keys, suffixes=('_csv','_fuente'), validate='one_to_one')
        for col in ['deuda_total_positiva','hhi_deuda_positiva','participacion_acreedor_principal',
                    'pct_deuda_situacion_1','pct_deuda_situacion_2','pct_deuda_situacion_3_mas',
                    'pct_deuda_situacion_desconocida']:
            np.testing.assert_allclose(j[col+'_csv'], j[col+'_fuente'], rtol=1e-12, equal_nan=True)

    def test_version_unica_y_trazabilidad(self):
        self.assertEqual(self.meta['schema_version'], '2.0')
        self.assertTrue(self.meta['inputs_unchanged'])
        self.assertIn('precios.py', self.meta['code_sha256'])
        self.assertEqual(len(self.meta['outputs']), 13)
        self.assertTrue(self.meta['preparacion_precios']['fk_ipc_validada'])
        self.assertEqual(self.meta['summary']['b']['ajuste_ipc']['estado'], 'diferido')

    def test_reproducibilidad_de_csv(self):
        second, meta = build_analytical_run(ROOT, Path(self.temp.name) / 'segunda')
        one = {x['path']:x['sha256'] for x in self.meta['outputs']}
        two = {x['path']:x['sha256'] for x in meta['outputs']}
        self.assertEqual(one, two)

    def test_c_individual_sin_descargar_a(self):
        with patch('requests.Session.get', side_effect=AssertionError('No extraer A')), \
             patch('requests.get', side_effect=AssertionError('No extraer A')):
            run, meta = build_analytical_run(ROOT, Path(self.temp.name) / 'c_sola', bases=('c',))
        self.assertTrue((run / 'base_a/deflactor_ipc.csv').exists())
        self.assertEqual(meta['ipc']['version_fuente'], self.meta['ipc']['version_fuente'])

    def test_fallo_ipc_no_publica_puntero(self):
        output = Path(self.temp.name) / 'fallo'
        with patch('lib.precios.cargar_ipc', side_effect=ValueError('IPC corrupto')):
            with self.assertRaises(ValueError): build_analytical_run(ROOT, output, bases=('a',))
        self.assertFalse((output / 'latest_a.json').exists())
        metas = list((output / 'runs').glob('*/run_metadata.json'))
        self.assertEqual(json.loads(metas[0].read_text())['status'], 'failed')

    def test_staging_valida_su_cache_y_conserva_original_si_falla(self):
        root = Path(self.temp.name) / 'staging_project'; root.mkdir()
        shutil.copytree(ROOT / 'config', root / 'config')
        shutil.copytree(ROOT / 'data_a', root / 'data_a')
        before = fingerprint(root)
        def check_stage(stage_root):
            self.assertNotEqual(Path(stage_root), root)
            cargar_ipc(stage_root)
        with patch.object(base_a, 'extract_base_a'), patch.object(base_a, 'adquirir_ipc', side_effect=check_stage), \
             patch.object(base_a, 'auditar_unidades_icc'):
            base_a.acquire(root)
        self.assertEqual(before, fingerprint(root))
        with patch.object(base_a, 'extract_base_a'), patch.object(base_a, 'adquirir_ipc', side_effect=ValueError('IPC inválido')):
            with self.assertRaises(ValueError): base_a.acquire(root)
        self.assertEqual(before, fingerprint(root))


if __name__ == '__main__':
    unittest.main(verbosity=2)
