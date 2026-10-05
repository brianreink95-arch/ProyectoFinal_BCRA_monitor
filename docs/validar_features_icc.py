"""Pruebas ICC: calendario, fórmulas, elegibilidad, procedencia y exportación."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.common import fingerprint, read_csv
from ml.features import (DESGLOSE_ICC, FEATURES_ICC, SERIES_ICC, agregar_mensual_icc,
                         calcular_features_icc, construir_icc, exportar_icc,
                         leer_icc, validar_matriz_icc)


class FeaturesICC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.provenance = leer_icc(ROOT)
        cls.monthly = agregar_mensual_icc(cls.tables['series'], cls.tables['observaciones'])
        cls.real = construir_icc(ROOT)

    def grilla(self):
        grid = pd.period_range('2020-01', periods=18, freq='M')
        monthly = pd.DataFrame(index=grid, columns=SERIES_ICC, dtype=float)
        monthly[927] = 100 + 10 * np.arange(len(grid))
        for sid, weight in zip(DESGLOSE_ICC, [0.1, 0.2, 0.3, 0.25, 0.15]):
            monthly[sid] = monthly[927] * weight
        monthly[1240] = 6 + np.arange(len(grid)) / 10
        return monthly

    def test_formulas_y_calentamiento(self):
        monthly = self.grilla()
        result = calcular_features_icc(monthly)
        self.assertTrue(result.loc[:2, 'credito_var_nominal_3m_pct'].isna().all())
        self.assertTrue(result.loc[:5, 'credito_volatilidad_6m_pp'].isna().all())
        self.assertFalse(result.loc[:5, 'elegible_icc'].any())
        self.assertTrue(result.loc[6:, 'elegible_icc'].all())
        self.assertAlmostEqual(result.loc[6, 'credito_var_nominal_1m_pct'], 100 * (160 / 150 - 1))
        self.assertAlmostEqual(result.loc[6, 'credito_var_nominal_3m_pct'], 100 * (160 / 130 - 1))
        self.assertAlmostEqual(result.loc[6, 'tasa_uva_delta_3m_pp'], 0.3)
        self.assertAlmostEqual(result.loc[6, 'participacion_construccion_pct'], 10)
        changes = 100 * (monthly[927].iloc[1:7].to_numpy() / monthly[927].iloc[:6].to_numpy() - 1)
        self.assertAlmostEqual(result.loc[6, 'credito_volatilidad_6m_pp'], np.std(changes, ddof=0))
        validar_matriz_icc(result)

    def test_hueco_no_se_salta_y_ventanas_recuperan(self):
        monthly = self.grilla()
        monthly.loc[monthly.index[7], 927] = np.nan
        result = calcular_features_icc(monthly)
        self.assertTrue(result.loc[7:8, 'credito_var_nominal_1m_pct'].isna().all())
        self.assertTrue(result.loc[7:10, 'credito_var_nominal_3m_pct'].isna().all())
        self.assertTrue(result.loc[7:13, 'credito_volatilidad_6m_pp'].isna().all())
        self.assertTrue(result.loc[14, 'elegible_icc'])
        self.assertEqual(len(result), len(monthly))
        self.assertIn('ventana_stock_incompleta', result.loc[10, 'motivos_no_elegible'])

    def test_denominador_cero_y_cero_reportado(self):
        monthly = self.grilla()
        monthly.loc[monthly.index[7], [927, *DESGLOSE_ICC]] = 0
        result = calcular_features_icc(monthly)
        self.assertEqual(result.loc[7, 'credito_var_nominal_1m_pct'], -100)
        self.assertTrue(pd.isna(result.loc[7, 'participacion_construccion_pct']))
        self.assertTrue(pd.isna(result.loc[8, 'credito_var_nominal_1m_pct']))
        self.assertEqual(result.loc[8, 'motivo_credito_var_nominal_1m_pct'], 'denominador_stock_no_positivo')
        self.assertFalse(np.isinf(result[list(FEATURES_ICC)].to_numpy()).any())

    def test_tasa_cero_valida_gap_y_negativa_no(self):
        monthly = self.grilla()
        monthly.loc[monthly.index[7], 1240] = 0
        monthly.loc[monthly.index[9], 1240] = np.nan
        monthly.loc[monthly.index[14], 1240] = -1
        result = calcular_features_icc(monthly)
        self.assertEqual(result.loc[7, 'tasa_uva_tna_pct'], 0)
        self.assertTrue(result.loc[9:12, 'tasa_uva_delta_3m_pp'].isna().all())
        self.assertTrue(pd.notna(result.loc[13, 'tasa_uva_delta_3m_pp']))
        self.assertTrue(pd.isna(result.loc[14, 'tasa_uva_tna_pct']))

    def test_composicion_solo_con_reconciliacion(self):
        monthly = self.grilla()
        monthly.loc[monthly.index[7], 1145] += 3
        monthly.loc[monthly.index[8], 1145] += 3.01
        monthly.loc[monthly.index[9], 1146] = np.nan
        result = calcular_features_icc(monthly)
        self.assertTrue(pd.notna(result.loc[7, 'participacion_construccion_pct']))
        self.assertTrue(pd.isna(result.loc[8, 'participacion_construccion_pct']))
        self.assertEqual(result.loc[8, 'motivo_participacion_construccion_pct'], 'desglose_no_reconciliado')
        self.assertEqual(result.loc[9, 'motivo_participacion_construccion_pct'], 'desglose_ausente_o_invalido')
        self.assertTrue(pd.notna(result.loc[9, 'credito_var_nominal_1m_pct']))

    def test_no_usa_futuro(self):
        monthly = self.grilla()
        original = calcular_features_icc(monthly)
        changed = monthly.copy()
        changed.iloc[10:] *= 1000
        pd.testing.assert_frame_equal(original.iloc[:10], calcular_features_icc(changed).iloc[:10])

    def test_grilla_desordenada_o_con_huecos_se_rechaza(self):
        monthly = self.grilla()
        for changed in [monthly.drop(monthly.index[7]), monthly.iloc[::-1]]:
            with self.assertRaisesRegex(ValueError, 'grilla'):
                calcular_features_icc(changed)

    def test_agregacion_reinserta_mes_ausente(self):
        observations = self.tables['observaciones']
        date = '2020-05-31'
        changed = observations.loc[~(observations['serie_id'].isin(SERIES_ICC) & observations['fecha'].eq(date))]
        monthly = agregar_mensual_icc(self.tables['series'], changed)
        self.assertTrue(monthly.loc[pd.Period('2020-05', freq='M')].isna().all())
        self.assertEqual(len(monthly), len(self.monthly))

    def test_dos_observaciones_en_mes_se_rechazan(self):
        observations = self.tables['observaciones']
        extra = observations.loc[observations['serie_id'].eq(927)].iloc[:1].copy()
        extra['fecha'] = '1999-12-30'
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            agregar_mensual_icc(self.tables['series'], pd.concat([observations, extra]))

    def test_reglas_catalogo_y_1199_no_se_alteran(self):
        series = self.tables['series'].copy()
        series.loc[series['serie_id'].eq(927), 'moneda'] = 'ME'
        with self.assertRaisesRegex(ValueError, 'moneda'):
            agregar_mensual_icc(series, self.tables['observaciones'])
        observations = self.tables['observaciones'].copy()
        exception = observations['excepcion_precobertura']
        self.assertTrue(observations.loc[exception, 'valor_original'].eq(0).all())
        observations.loc[exception, 'valor_analitico'] = 0
        with self.assertRaisesRegex(ValueError, '1199'):
            agregar_mensual_icc(self.tables['series'], observations)

    def test_nulo_analitico_fuera_de_excepcion_se_rechaza(self):
        observations = self.tables['observaciones'].copy()
        observations.loc[observations['serie_id'].eq(927), 'valor_analitico'] = pd.NA
        with self.assertRaisesRegex(ValueError, '1199'):
            agregar_mensual_icc(self.tables['series'], observations)

    def test_cambio_precision_stock_se_rechaza(self):
        observations = self.tables['observaciones'].copy()
        idx = observations.index[observations['serie_id'].eq(927)][0]
        observations.loc[idx, ['valor_original', 'valor_analitico']] = 100.5
        with self.assertRaisesRegex(ValueError, 'precisión'):
            agregar_mensual_icc(self.tables['series'], observations)

    def test_formulas_reales_junio_2026(self):
        row = self.real.set_index('fecha_mes').loc['2026-06-30']
        monthly = self.monthly
        t = pd.Period('2026-06', freq='M')
        self.assertAlmostEqual(row['credito_var_nominal_1m_pct'], 100 * (6943415 / 6728825 - 1))
        self.assertAlmostEqual(row['credito_var_nominal_3m_pct'], 100 * (6943415 / 6400004 - 1))
        self.assertAlmostEqual(row['participacion_construccion_pct'], 100 * 384720 / 6943415)
        self.assertAlmostEqual(row['tasa_uva_tna_pct'], 7.02)
        self.assertAlmostEqual(row['tasa_uva_delta_3m_pp'], 7.02 - 6.37)
        window = monthly.loc[t-6:t, 927].to_numpy()
        self.assertAlmostEqual(row['credito_volatilidad_6m_pp'], np.std(100 * (window[1:] / window[:-1] - 1), ddof=0))
        self.assertTrue(row['elegible_icc'])

    def test_matriz_real_y_motivos(self):
        validar_matriz_icc(self.real)
        self.assertTrue(self.real['elegible_icc'].any())
        eligible = self.real[self.real['elegible_icc']]
        self.assertTrue(eligible[list(FEATURES_ICC)].notna().all().all())
        self.assertTrue(eligible['composicion_consistente'].all())
        self.assertTrue(eligible['n_meses_stock_4m'].eq(4).all())
        self.assertTrue(eligible['n_meses_tasa_4m'].eq(4).all())
        self.assertTrue(eligible['n_variaciones_6m'].eq(6).all())
        for date in ['2026-07-31', '2026-08-31']:
            row = self.real.set_index('fecha_mes').loc[date]
            self.assertFalse(row['elegible_icc'])
            self.assertIn('stock_actual_ausente_o_invalido', row['motivos_no_elegible'])

    def test_matriz_rechaza_pk_nula_y_duplicada(self):
        changed = self.real.copy()
        changed.loc[0, 'segmento'] = None
        with self.assertRaisesRegex(ValueError, 'nula'):
            validar_matriz_icc(changed)
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            validar_matriz_icc(pd.concat([self.real, self.real.iloc[:1]], ignore_index=True))

    def test_integridad_y_corrida_incompleta_se_rechazan(self):
        run_id = self.provenance['run_origen']
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'config').mkdir()
            shutil.copyfile(ROOT / 'config' / 'esquema_tablas.json', root / 'config' / 'esquema_tablas.json')
            target = root / 'data_analytics' / 'runs' / run_id
            shutil.copytree(ROOT / 'data_analytics' / 'runs' / run_id / 'base_a', target / 'base_a')
            meta = target / 'run_metadata.json'
            shutil.copyfile(ROOT / 'data_analytics' / 'runs' / run_id / 'run_metadata.json', meta)
            shutil.copyfile(ROOT / 'data_analytics' / 'latest.json', root / 'data_analytics' / 'latest.json')
            data = json.loads(meta.read_text(encoding='utf-8'))
            data['status'] = 'running'
            meta.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'completa'):
                leer_icc(root)
            data['status'] = 'completed'
            meta.write_text(json.dumps(data), encoding='utf-8')
            path = target / 'base_a' / 'observaciones.csv'
            with path.open('a', encoding='utf-8') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'consolidación'):
                leer_icc(root)

    def test_reproducibilidad_exportacion_y_fuentes_intactas(self):
        before = fingerprint(ROOT)
        again = construir_icc(ROOT)
        pd.testing.assert_frame_equal(self.real, again)
        with tempfile.TemporaryDirectory() as temp:
            path = exportar_icc(self.real, temp)
            first = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(exportar_icc(again, temp), path)
            self.assertEqual(first, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(len(list(Path(temp).rglob('*.csv'))), 1)
            text_columns = self.real.select_dtypes(include=['object', 'string']).columns
            saved = read_csv(path, dtype={name: str for name in text_columns})
            for name in saved.columns:
                if name.startswith('motivo_') or name == 'motivos_no_elegible':
                    saved[name] = saved[name].fillna('')
            validar_matriz_icc(saved)
            pd.testing.assert_frame_equal(self.real, saved, check_dtype=False)
            self.assertFalse(path.with_name(path.name + '.tmp').exists())
        self.assertEqual(before, fingerprint(ROOT))


if __name__ == '__main__':
    unittest.main(verbosity=2)
