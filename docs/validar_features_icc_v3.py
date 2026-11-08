"""Validación ICC 3.0: fórmulas, calendario, elegibilidad y contrato S1.

Ejecutar desde la raíz: python -m unittest docs.validar_features_icc_v3 -v
Usa la consolidación local vigente; no consulta internet ni calibra modelos.
"""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml import features as f
from ml import baseline as b


def mensual(n=24):
    index = pd.period_range('2016-12', periods=n, freq='M')
    stock = 100 + 10 * np.arange(n, dtype=float)
    frame = pd.DataFrame(index=index)
    frame[927] = stock * 10
    for sid, share in zip(f.DESGLOSE_ICC, (.4, .15, .15, .15, .15)):
        frame[sid] = frame[927] * share
    frame[1240] = 3 + .1 * np.arange(n)
    frame['stock_constante_dic2016'] = stock
    frame['estado_ajuste_ipc_stock'] = 'ajustado'
    return frame


class FormulasICC(unittest.TestCase):
    def setUp(self):
        self.monthly = mensual()
        self.frame = f.calcular_features_icc(self.monthly)

    def test_nivel_en_unidad_constante(self):
        np.testing.assert_allclose(self.frame[f.STOCK_REAL], 100 + 10 * np.arange(24))

    def test_crecimiento_anual_y_inicio(self):
        self.assertTrue(self.frame.loc[:11, 'credito_var_real_12m_pct'].isna().all())
        self.assertAlmostEqual(self.frame.loc[12, 'credito_var_real_12m_pct'], 120)
        self.assertEqual(self.frame.loc[12, 'n_meses_stock_real_13m'], 13)

    def test_delta_absoluto_no_es_porcentaje(self):
        self.assertTrue(self.frame.loc[:2, f.DELTA_STOCK_REAL].isna().all())
        np.testing.assert_allclose(self.frame.loc[3:, f.DELTA_STOCK_REAL], 30)

    def test_aceleracion_compara_trimestres_contiguos(self):
        self.assertTrue(self.frame.loc[:5, f.ACELERACION_REAL].isna().all())
        expected = 100 * (160 / 130 - 1) - 100 * (130 / 100 - 1)
        self.assertAlmostEqual(self.frame.loc[6, f.ACELERACION_REAL], expected)
        self.assertLess(expected, 0)  # Suba absoluta constante, ritmo porcentual menor.

    def test_volatilidad_poblacional_seis_cambios(self):
        values = [100 * ((100 + 10 * i) / (100 + 10 * (i-1)) - 1) for i in range(1, 7)]
        self.assertAlmostEqual(self.frame.loc[6, 'credito_volatilidad_real_6m_pp'], np.std(values, ddof=0))
        self.assertTrue(self.frame.loc[:5, 'credito_volatilidad_real_6m_pp'].isna().all())

    def test_tasa_sin_deflactar_y_delta_en_pp(self):
        np.testing.assert_allclose(self.frame['tasa_uva_tna_pct'], self.monthly[1240])
        self.assertAlmostEqual(self.frame.loc[3, 'tasa_uva_delta_3m_pp'], .3)

    def test_cinco_destinos(self):
        for sid, expected in zip(f.DESGLOSE_ICC, (40, 15, 15, 15, 15)):
            np.testing.assert_allclose(self.frame[f.PARTICIPACIONES_ICC[sid]], expected)
        np.testing.assert_allclose(self.frame[list(f.PARTICIPACIONES_ICC.values())].sum(axis=1), 100)

    def test_nivel_y_delta_admiten_cero(self):
        self.monthly.loc[self.monthly.index[0], 'stock_constante_dic2016'] = 0
        frame = f.calcular_features_icc(self.monthly)
        self.assertEqual(frame.loc[0, f.STOCK_REAL], 0)
        self.assertEqual(frame.loc[3, f.DELTA_STOCK_REAL], 130)
        self.assertTrue(pd.isna(frame.loc[3, 'credito_var_real_3m_pct']))
        self.assertTrue(pd.isna(frame.loc[6, f.ACELERACION_REAL]))
        self.assertTrue(pd.isna(frame.loc[12, 'credito_var_real_12m_pct']))

    def test_cero_actual_es_caida_cien_por_ciento(self):
        self.monthly.loc[self.monthly.index[12], 'stock_constante_dic2016'] = 0
        frame = f.calcular_features_icc(self.monthly)
        for lag in (1, 3, 12):
            self.assertEqual(frame.loc[12, f'credito_var_real_{lag}m_pct'], -100)

    def test_hueco_stock_no_se_salta(self):
        self.monthly.loc[self.monthly.index[5], 'stock_constante_dic2016'] = np.nan
        frame = f.calcular_features_icc(self.monthly)
        for row, name in ((6, 'credito_var_real_3m_pct'), (6, f.DELTA_STOCK_REAL),
                          (9, f.ACELERACION_REAL), (12, 'credito_var_real_12m_pct')):
            self.assertTrue(pd.isna(frame.loc[row, name]), (row, name))
        self.assertTrue(pd.notna(frame.loc[9, f.DELTA_STOCK_REAL]))

    def test_ipc_o_unidad_pendiente_no_habilita_nominal(self):
        for state in ('ipc_no_publicado', 'unidad_no_validada', 'anterior_base'):
            with self.subTest(state=state):
                monthly = self.monthly.copy()
                monthly.loc[monthly.index[12], 'estado_ajuste_ipc_stock'] = state
                frame = f.calcular_features_icc(monthly)
                self.assertTrue(pd.isna(frame.loc[12, f.STOCK_REAL]))
                self.assertIn(state, frame.loc[12, f'motivo_{f.STOCK_REAL}'])
                self.assertEqual(frame.loc[12, 'participacion_construccion_pct'], 40)

    def test_nominal_ausente_impide_constante(self):
        self.monthly.loc[self.monthly.index[12], 927] = np.nan
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(pd.isna(frame.loc[12, f.STOCK_REAL]))

    def test_negativos_no_son_observaciones_utilizables(self):
        self.monthly.loc[self.monthly.index[12], 'stock_constante_dic2016'] = -1
        self.monthly.loc[self.monthly.index[12], 1240] = -1
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(pd.isna(frame.loc[12, f.STOCK_REAL]))
        self.assertTrue(pd.isna(frame.loc[12, 'tasa_uva_tna_pct']))

    def test_destino_ausente_no_impide_perfil_de_costo_dinamica(self):
        self.monthly.loc[self.monthly.index[12], 1146] = np.nan
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(frame.loc[12, 'elegible_baseline_historico'])
        self.assertFalse(frame.loc[12, 'elegible_comparacion_2_0'])
        self.assertTrue(frame.loc[12, list(f.PARTICIPACIONES_ICC.values())].isna().all())

    def test_desglose_no_reconciliado_se_rechaza(self):
        self.monthly.loc[self.monthly.index[12], 1146] += 4
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(frame.loc[12, list(f.PARTICIPACIONES_ICC.values())].isna().all())

    def test_tolerancia_redondeo_no_renormaliza(self):
        self.monthly.loc[self.monthly.index[12], 1146] += 3
        frame = f.calcular_features_icc(self.monthly)
        total = frame.loc[12, list(f.PARTICIPACIONES_ICC.values())].sum()
        self.assertGreater(total, 100)
        self.assertTrue(frame.loc[12, 'composicion_consistente'])

    def test_total_cero_no_crea_participacion(self):
        self.monthly.loc[self.monthly.index[12], [927, *f.DESGLOSE_ICC]] = 0
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(frame.loc[12, list(f.PARTICIPACIONES_ICC.values())].isna().all())

    def test_hueco_tasa_impide_delta(self):
        self.monthly.loc[self.monthly.index[5], 1240] = np.nan
        frame = f.calcular_features_icc(self.monthly)
        self.assertTrue(pd.isna(frame.loc[7, 'tasa_uva_delta_3m_pp']))
        self.assertTrue(pd.notna(frame.loc[9, 'tasa_uva_delta_3m_pp']))

    def test_elegibilidad_no_exige_candidata_anual(self):
        self.assertTrue(self.frame.loc[3, 'elegible_baseline_historico'])
        self.assertTrue(self.frame.loc[6, 'elegible_comparacion_2_0'])
        self.assertFalse(self.frame.loc[6, 'candidatas_completas'])
        self.assertTrue(self.frame.loc[12, 'candidatas_completas'])
        self.assertEqual(self.frame.loc[6, 'elegible_icc'], self.frame.loc[6, 'elegible_comparacion_2_0'])

    def test_requisitos_explicitos_y_motivos_solo_del_consumidor(self):
        mask, reason = f.elegibilidad_features(self.frame, [f.STOCK_REAL])
        self.assertTrue(mask.all())
        self.assertTrue(reason.eq('').all())
        for required in ([], [f.STOCK_REAL, f.STOCK_REAL], ['acceso_inventado']):
            with self.assertRaises(ValueError):
                f.elegibilidad_features(self.frame, required)

    def test_no_contaminacion_por_futuro(self):
        future = self.monthly.copy()
        future.loc[future.index[15]:, list(f.SERIES_ICC)] *= 5
        future.loc[future.index[15]:, 'stock_constante_dic2016'] *= 5
        result = f.calcular_features_icc(future)
        pd.testing.assert_frame_equal(self.frame.loc[:14], result.loc[:14])

    def test_rechaza_grilla_comprimida(self):
        with self.assertRaises(ValueError):
            f.calcular_features_icc(self.monthly.drop(self.monthly.index[5]))

    def test_rechaza_columnas_duplicadas(self):
        with self.assertRaises(ValueError):
            f.calcular_features_icc(pd.concat([self.monthly, self.monthly[[927]]], axis=1))

    def test_rechaza_infinitos(self):
        self.monthly.loc[self.monthly.index[5], 'stock_constante_dic2016'] = np.inf
        with self.assertRaises(ValueError):
            f.calcular_features_icc(self.monthly)

    def test_validador_detecta_motivos_inconsistentes(self):
        altered = self.frame.copy()
        altered.loc[12, f'motivo_{f.STOCK_REAL}'] = 'ausente'
        with self.assertRaises(ValueError):
            f.validar_matriz_icc(altered)

    def test_validador_detecta_perfil_inconsistente(self):
        altered = self.frame.copy()
        altered.loc[0, 'elegible_baseline_historico'] = True
        with self.assertRaises(ValueError):
            f.validar_matriz_icc(altered)

    def test_minimo_y_referencias_historicas_no_habilitan_s1(self):
        with self.assertRaisesRegex(ValueError, 'mínimo'):
            b.ajustar_referencias_icc(self.frame, min_train=1)
        with self.assertRaisesRegex(ValueError, 'metodología'):
            b.aplicar_baseline_icc(self.frame, {name: [1] for name in b.PREDICTORES_BASELINE})
        with self.assertRaisesRegex(ValueError, 'Metodología'):
            b.exportar_baseline_icc(self.frame, {})

    def test_s1_usa_muestra_core_y_no_percentiles_historicos(self):
        monthly = mensual(73)
        monthly.index = pd.period_range('2015-12', periods=len(monthly), freq='M')
        frame = f.calcular_features_icc(monthly)
        check = b.comprobar_protocolo_icc(frame)
        self.assertTrue(check['cumple_minimo_train'])
        self.assertTrue(check['puede_calibrar'])
        refs = b.ajustar_referencias_icc(frame)
        self.assertEqual(refs['metodo'], 'S1')
        self.assertNotIn(b.G1, refs)
        mask = b.mascara_core(frame) & b.asignar_splits_icc(frame).eq('train')
        self.assertEqual(refs['n_train'], int(mask.sum()))

    def test_calendario_splits_y_reserva_sin_shuffle(self):
        dates = pd.Series(['2016-07-31', '2016-08-31', '2021-12-31', '2022-01-31',
                           '2022-02-28', '2022-03-31', '2023-12-31', '2024-01-31',
                           '2026-06-30', '2026-07-31'])
        self.assertEqual(b._splits_por_fecha(dates).tolist(), ['fuera_protocolo', 'train', 'train',
                         'train', 'train', 'validacion', 'validacion', 'evaluacion_retrospectiva',
                         'evaluacion_retrospectiva', 'reserva_futura'])

    def test_dos_meses_adicionales_cumplen_minimo_del_s1_adoptado(self):
        frame = f.calcular_features_icc(mensual(63))  # Diciembre 2016–febrero 2022.
        check = b.comprobar_protocolo_icc(frame)
        self.assertEqual(check['meses_elegibles_por_split']['train'], 60)
        self.assertEqual(check['meses_comparacion_2_0_por_split']['train'], 57)
        self.assertEqual(check['meses_todas_candidatas_por_split']['train'], 51)
        self.assertTrue(check['cumple_minimo_train'])
        self.assertTrue(check['puede_calibrar'])
        self.assertTrue(check['metodologia_aprobada'])


class IntegracionICC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, _ = f.leer_icc(ROOT)
        cls.monthly = f.agregar_mensual_icc(cls.tables['series'], cls.tables['observaciones'],
                                         cls.tables['deflactor_ipc'])
        cls.frame = f.construir_icc(ROOT)

    def test_formula_directa_ipc_fuente(self):
        obs = self.tables['observaciones']
        selected = obs.loc[obs['serie_id'].eq(927) & obs['estado_ajuste_ipc'].eq('ajustado')]
        ipc = self.tables['deflactor_ipc'].set_index('fecha_mes')['ipc_nacional']
        expected = selected['valor_original'].astype(float).to_numpy() * 100 / selected['fecha'].map(ipc).astype(float).to_numpy()
        actual = self.frame.set_index('fecha_mes').loc[selected['fecha'], f.STOCK_REAL]
        np.testing.assert_allclose(actual, expected, rtol=1e-12)

    def test_formulas_nuevas_sobre_serie_real(self):
        r = self.monthly['stock_constante_dic2016']
        expected = {
            'credito_var_real_12m_pct': 100 * (r / r.shift(12) - 1),
            f.DELTA_STOCK_REAL: r - r.shift(3),
            f.ACELERACION_REAL: 100 * (r / r.shift(3) - 1) - 100 * (r.shift(3) / r.shift(6) - 1),
        }
        for name, values in expected.items():
            actual = self.frame[name]
            valid = actual.notna().to_numpy()
            np.testing.assert_allclose(actual[valid], values.to_numpy()[valid], rtol=1e-12)
            self.assertTrue(valid.any())

    def test_integridad_de_consolidacion_tras_transformar(self):
        run = ROOT / 'data_analytics' / 'runs' / self.frame['run_origen'].iloc[0]
        metadata = json.loads((run / 'run_metadata.json').read_text())
        for item in metadata['outputs']:
            with self.subTest(path=item['path']):
                self.assertEqual(hashlib.sha256((run / item['path']).read_bytes()).hexdigest(), item['sha256'])

    def test_exportacion_versionada_preserva_anterior_y_es_repetible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'data_analytics' / 'features' / self.frame['run_origen'].iloc[0] / 'icc.csv'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'artefacto anterior sin cambios\n')
            original = old.read_bytes()
            path = f.exportar_icc(self.frame, root)
            content = path.read_bytes()
            self.assertEqual(path.parent.name, 'v3.0')
            f.exportar_icc(self.frame, root)
            self.assertEqual(content, path.read_bytes())
            self.assertEqual(original, old.read_bytes())

    def test_matriz_persistida_se_relee_sin_perder_perfiles(self):
        # Solo lee el archivo generado por features; no escribe en la corrida fuente.
        path = f.ruta_matriz_icc(ROOT, self.frame['run_origen'].iloc[0])
        if not path.exists():
            self.skipTest('Ejecutar ml/features.py antes de validar la relectura persistida.')
        stored, source = b.leer_matriz_icc(ROOT)
        pd.testing.assert_frame_equal(self.frame, stored, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12)
        self.assertEqual(source['version_features'], '3.0')

    def test_tasa_y_cinco_participaciones_desde_nominales(self):
        np.testing.assert_allclose(self.frame['tasa_uva_tna_pct'], self.monthly[1240], equal_nan=True)
        for sid, name in f.PARTICIPACIONES_ICC.items():
            valid = self.frame[name].notna().to_numpy()
            expected = (100 * self.monthly[sid] / self.monthly[927]).to_numpy()
            np.testing.assert_allclose(self.frame.loc[valid, name], expected[valid], rtol=1e-12)


if __name__ == '__main__':
    unittest.main()
