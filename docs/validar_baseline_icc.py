"""Validar splits y referencias ICC sin ajustar sobre validación o futuro."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.common import fingerprint, read_csv
from ml.features import DESGLOSE_ICC, SERIES_ICC, calcular_features_icc
from ml.baseline import (CORTES_ICC, DELTA, G1, G3, PREDICTORES_BASELINE, TASA, VARIANTES,
                         ajustar_referencias_icc, aplicar_baseline_icc, asignar_splits_icc,
                         construir_baseline_icc, exportar_baseline_icc, leer_matriz_icc,
                         percentil_referencia, preparar_protocolo_icc, validar_baseline_icc)


class BaselineICC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real, cls.source = leer_matriz_icc(ROOT)
        cls.references = ajustar_referencias_icc(cls.real)
        cls.baseline = aplicar_baseline_icc(cls.real, cls.references)

    def grilla(self):
        grid = pd.period_range('2016-01', '2026-08', freq='M')
        monthly = pd.DataFrame(index=grid, columns=SERIES_ICC, dtype=float)
        monthly[927] = 100 + 10 * np.arange(len(grid))
        for sid, weight in zip(DESGLOSE_ICC, [0.1, 0.2, 0.3, 0.25, 0.15]):
            monthly[sid] = monthly[927] * weight
        monthly[1240] = 6 + np.arange(len(grid)) / 100
        frame = calcular_features_icc(monthly)
        frame['run_origen'] = 'sintetico'
        return frame

    def test_cortes_por_calendario_y_reserva(self):
        frame = self.grilla()
        split = asignar_splits_icc(frame)
        lookup = pd.Series(split.to_numpy(), index=frame['fecha_mes'])
        expected = {'2016-07-31': 'fuera_protocolo', '2016-08-31': 'train',
                    '2021-12-31': 'train', '2022-01-31': 'validacion',
                    '2023-12-31': 'validacion', '2024-01-31': 'evaluacion_retrospectiva',
                    '2026-06-30': 'evaluacion_retrospectiva', '2026-07-31': 'reserva_futura'}
        for date, role in expected.items():
            self.assertEqual(lookup.loc[date], role)
        altered = frame.copy()
        altered.loc[:, G1] *= 100
        pd.testing.assert_series_equal(split, asignar_splits_icc(altered))

    def test_counts_reales_y_referencias_solo_train(self):
        split = asignar_splits_icc(self.real)
        self.assertEqual([int((split.eq(role) & self.real['elegible_icc']).sum())
                          for role in CORTES_ICC], [65, 24, 30])
        for name, ref in self.references.items():
            train = self.real.loc[split.eq('train') & self.real['elegible_icc'], name]
            np.testing.assert_array_equal(ref, np.sort(train.to_numpy()))
            self.assertEqual(len(ref), 65)
        self.assertEqual(len(self.baseline), len(self.real))
        self.assertEqual(int(self.baseline['utilizable_baseline'].sum()), 119)

    def test_ecdf_empates_cola_nulos_y_constantes(self):
        values = pd.Series([-1, 1, 2, 3, 5, np.nan])
        result = percentil_referencia(values, [1, 2, 2, 4])
        np.testing.assert_allclose(result, [0, 12.5, 50, 75, 100, np.nan], equal_nan=True)
        result = percentil_referencia(pd.Series([6, 7, 8]), [7, 7, 7])
        np.testing.assert_allclose(result, [0, 50, 100])
        for ref in [[], [2, 1], [1, np.inf], [np.nan]]:
            with self.assertRaises(ValueError):
                percentil_referencia(values, ref)
        with self.assertRaises(ValueError):
            percentil_referencia(pd.Series([np.inf]), [1, 2])

    def test_minimo_train_y_referencia_invalida(self):
        frame = self.grilla()
        with self.assertRaisesRegex(ValueError, 'insuficiente'):
            ajustar_referencias_icc(frame, min_train=66)
        with self.assertRaisesRegex(ValueError, 'positivo'):
            ajustar_referencias_icc(frame, min_train=0)
        references = ajustar_referencias_icc(frame)
        del references[G1]
        with self.assertRaisesRegex(ValueError, 'Predictores'):
            aplicar_baseline_icc(frame, references)

    def test_no_ajusta_sobre_validacion_evaluacion_o_reserva(self):
        frame = self.grilla()
        refs = ajustar_referencias_icc(frame)
        original = aplicar_baseline_icc(frame, refs)
        changed = frame.copy()
        future = changed['fecha_mes'].gt('2021-12-31')
        changed.loc[future, list(PREDICTORES_BASELINE)] *= 1000
        self.assertEqual(refs, ajustar_referencias_icc(changed))
        recalculated = aplicar_baseline_icc(changed, ajustar_referencias_icc(changed))
        pd.testing.assert_frame_equal(original.loc[~future], recalculated.loc[~future])
        changed = frame.copy()
        later = changed['fecha_mes'].gt('2023-12-31')
        changed.loc[later, list(PREDICTORES_BASELINE)] *= 1000
        recalculated = aplicar_baseline_icc(changed, ajustar_referencias_icc(changed))
        pd.testing.assert_frame_equal(original.loc[~later], recalculated.loc[~later])

    def test_reserva_futura_no_se_puntua_aunque_sea_elegible(self):
        frame = self.grilla()
        result = aplicar_baseline_icc(frame, ajustar_referencias_icc(frame))
        reserve = result['split_temporal'].eq('reserva_futura')
        self.assertTrue(result.loc[reserve, 'elegible_icc'].all())
        self.assertFalse(result.loc[reserve, 'utilizable_baseline'].any())
        self.assertTrue(result.loc[reserve, list(VARIANTES)].isna().all().all())
        self.assertTrue(result.loc[reserve, 'motivo_no_utilizable_baseline'].str.contains('reserva_futura').all())

    def test_direccion_tasas_y_pesos_por_dimension(self):
        frame = self.grilla()
        refs = ajustar_referencias_icc(frame)
        result = aplicar_baseline_icc(frame, refs)
        row = result.loc[result['utilizable_baseline']].iloc[0]
        p1, p3 = row[f'percentil_{G1}'], row[f'percentil_{G3}']
        pt, pdiff = row[f'percentil_{TASA}'], row[f'percentil_{DELTA}']
        self.assertAlmostEqual(row['referencia_trimestral'], 0.5 * p3 + 0.5 * (100 - pt))
        self.assertAlmostEqual(row['referencia_mensual'], 0.5 * p1 + 0.5 * (100 - pt))
        self.assertAlmostEqual(row['referencia_balanceada'], 0.25 * (p1 + p3 + 200 - pt - pdiff))
        for components in VARIANTES.values():
            stock_weight = sum(weight for name, (weight, _) in components.items() if name in (G1, G3))
            self.assertAlmostEqual(stock_weight, 0.5)
        changed = frame.copy()
        index = changed.index[changed['fecha_mes'].eq('2022-01-31')][0]
        changed.loc[index, TASA] = max(refs[TASA]) + 100
        worse = aplicar_baseline_icc(changed, refs)
        self.assertLessEqual(worse.loc[index, 'referencia_trimestral'], result.loc[index, 'referencia_trimestral'])

    def test_descriptores_no_integran_referencia_y_no_se_eliminan(self):
        frame = self.grilla()
        refs = ajustar_referencias_icc(frame)
        original = aplicar_baseline_icc(frame, refs)
        changed = frame.copy()
        changed.loc[changed['participacion_construccion_pct'].notna(), 'participacion_construccion_pct'] = 99
        changed.loc[changed['credito_volatilidad_6m_pp'].notna(), 'credito_volatilidad_6m_pp'] = 999
        result = aplicar_baseline_icc(changed, ajustar_referencias_icc(changed))
        pd.testing.assert_frame_equal(original[list(VARIANTES)], result[list(VARIANTES)])
        self.assertTrue(result['participacion_construccion_pct'].dropna().eq(99).all())
        self.assertTrue(result['credito_volatilidad_6m_pp'].dropna().eq(999).all())

    def test_hueco_no_mueve_split_y_no_se_imputa(self):
        frame = self.real.copy()
        index = frame.index[frame['fecha_mes'].eq('2020-05-31')][0]
        name = G1
        frame.loc[index, name] = np.nan
        frame.loc[index, f'motivo_{name}'] = 'stock_actual_ausente_o_invalido'
        frame.loc[index, 'motivos_no_elegible'] = f'{name}:stock_actual_ausente_o_invalido'
        frame.loc[index, 'n_features_disponibles'] -= 1
        frame.loc[index, 'elegible_icc'] = False
        refs = ajustar_referencias_icc(frame)
        result = aplicar_baseline_icc(frame, refs)
        self.assertEqual(len(refs[G1]), 64)
        self.assertEqual(result.loc[index, 'split_temporal'], 'train')
        self.assertTrue(result.loc[index, list(VARIANTES)].isna().all())
        self.assertEqual(result.loc[index+1, 'fecha_mes'], '2020-06-30')

    def test_extremos_reales_no_se_corrigen_y_etiologia_pendiente(self):
        lookup = self.real.set_index('fecha_mes')
        self.assertAlmostEqual(lookup.loc['2024-10-31', G1], 45.08107260776, places=7)
        self.assertAlmostEqual(lookup.loc['2024-11-30', G3], 153.7610402, places=6)
        self.assertEqual(lookup.loc['2024-02-29', TASA], 0.2)
        protocol = preparar_protocolo_icc(self.real, self.baseline, self.references, self.source)
        self.assertEqual(len(protocol['casos_revision_ex_post']), 3)
        self.assertTrue(all('no_identificada' in row['estado'] for row in protocol['casos_revision_ex_post']))
        self.assertNotIn('evaluacion_retrospectiva', protocol['diagnosticos_train_validacion'])
        self.assertFalse(self.baseline['contemporaneidad_stock_verificada'].any())

    def test_correlaciones_de_train_y_pesos_no_usar_test(self):
        protocol = preparar_protocolo_icc(self.real, self.baseline, self.references, self.source)
        self.assertTrue(all(date <= '2021-12-31' for date in protocol['train_fechas_utilizadas']))
        train = self.real.loc[asignar_splits_icc(self.real).eq('train') & self.real['elegible_icc']]
        corr = train[[G1, G3]].corr().iloc[0, 1]
        self.assertAlmostEqual(protocol['correlaciones_solo_train']['pearson'][G1][G3], corr)
        for item in protocol['variantes_pesos_y_direccion'].values():
            self.assertNotIn('credito_volatilidad_6m_pp', item)
            self.assertNotIn('participacion_construccion_pct', item)
        json.dumps(protocol, allow_nan=False)

    def test_splits_alterados_pk_duplicada_e_infinitos_se_rechazan(self):
        changed = self.baseline.copy()
        changed.loc[changed['split_temporal'].eq('validacion'), 'split_temporal'] = 'train'
        with self.assertRaisesRegex(ValueError, 'Split'):
            validar_baseline_icc(changed)
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            validar_baseline_icc(pd.concat([self.baseline, self.baseline.iloc[:1]], ignore_index=True))
        changed = self.baseline.copy()
        changed.loc[changed['utilizable_baseline'], 'referencia_trimestral'] = np.inf
        with self.assertRaises(ValueError):
            validar_baseline_icc(changed)

    def test_matriz_alterada_y_metodologia_distinta_se_rechazan(self):
        with tempfile.TemporaryDirectory() as temp, patch('ml.baseline.construir_icc', return_value=self.real):
            root = Path(temp)
            path = root / 'data_analytics' / 'features' / self.source['run_origen'] / 'icc.csv'
            path.parent.mkdir(parents=True)
            changed = self.real.copy()
            changed.loc[changed['elegible_icc'], G1] += 1
            changed.to_csv(path, index=False, encoding='utf-8-sig')
            with self.assertRaisesRegex(ValueError, 'no corresponde'):
                leer_matriz_icc(root)
            self.real.to_csv(path, index=False, encoding='utf-8-sig')
            method = root / 'data_a' / 'metadata' / 'bcra_monetarias_metodologia.csv'
            method.parent.mkdir(parents=True)
            method.write_text('idVariable,nombre_corto,id,detalle\n', encoding='utf-8')
            meta = root / 'data_analytics' / 'runs' / self.source['run_origen'] / 'run_metadata.json'
            meta.parent.mkdir(parents=True)
            meta.write_text(json.dumps({'source_sha256': {
                'data_a/metadata/bcra_monetarias_metodologia.csv': self.source['metodologia_sha256']}}),
                encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'metodología'):
                leer_matriz_icc(root)

    def test_publicacion_reproducible_y_fuentes_intactas(self):
        before = fingerprint(ROOT)
        baseline, protocol = construir_baseline_icc(ROOT)
        with tempfile.TemporaryDirectory() as temp:
            paths = exportar_baseline_icc(baseline, protocol, temp)
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
            again, artifact = construir_baseline_icc(ROOT)
            paths_again = exportar_baseline_icc(again, artifact, temp)
            self.assertEqual(paths, paths_again)
            self.assertEqual(hashes, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths_again])
            self.assertEqual(len(list(Path(temp).rglob('*.csv'))), 1)
            self.assertEqual(len(list(Path(temp).rglob('*.json'))), 1)
            saved_protocol = json.loads(paths[1].read_text(encoding='utf-8'))
            self.assertEqual(saved_protocol['baseline_csv_sha256'], hashes[0])
            text = baseline.select_dtypes(include=['object', 'string']).columns
            saved = read_csv(paths[0], dtype={name: str for name in text})
            for name in ['motivos_no_elegible', 'motivo_no_utilizable_baseline']:
                saved[name] = saved[name].fillna('')
            validar_baseline_icc(saved)
            pd.testing.assert_frame_equal(baseline, saved, check_dtype=False)
            self.assertFalse(list(Path(temp).rglob('*.tmp')))
        self.assertEqual(before, fingerprint(ROOT))


if __name__ == '__main__':
    unittest.main(verbosity=2)
