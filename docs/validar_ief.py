"""Pruebas de calendario, unidades, ausencia de leakage y reproducción de IEF."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from ml import ief
from ml import baseline_ief as baseline

ROOT = Path(__file__).resolve().parents[1]


def ejemplo():
    empresas = pd.DataFrame({
        'cuit_normalizado': ['001', '002'], 'razon_social': ['A', 'B'],
        'grupo_economico': [None, 'G'], 'perfil_sectorial': ['Uno;Dos', 'Uno'],
    })
    rows = []
    for cuit in empresas.cuit_normalizado:
        for i, date in enumerate(pd.date_range('2024-08-01', periods=8, freq='MS')):
            rows.append({
                'cuit_normalizado': cuit, 'fecha': date.strftime('%Y-%m-%d'),
                'mes_observado': True, 'empresa_con_deuda_activa': True,
                ief.NOMINAL: 2000 * (i + 1), ief.REAL: 100.0,
                ief.COUNT: 2 + i, 'hhi_deuda_positiva': .5,
                'situacion_max_activa': 2, 'pct_deuda_situacion_2': 10.0 * i,
                'pct_deuda_situacion_3_mas': 5.0,
                'estado_ajuste_ipc': 'ajustado',
                'ipc_fecha_mes': (date + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d'),
            })
    return pd.DataFrame(rows), empresas


class SemanticaIEF(unittest.TestCase):
    def setUp(self):
        self.panel, self.empresas = ejemplo()

    def matriz(self):
        return ief.construir_matriz(self.panel, self.empresas)

    def test_crecimiento_real_no_confunde_inflacion_y_pp(self):
        d = self.matriz().iloc[3]
        self.assertEqual(d.deuda_var_real_3m_pct, 0)
        self.assertEqual(d.acreedores_delta_3m, 3)
        self.assertEqual(d.pct_deuda_situacion_2_mas, 35)
        self.assertEqual(d.pct_deuda_situacion_2_mas_delta_3m_pp, 30)
        self.assertTrue(d.elegible_ief)

    def test_variacion_real_usa_extremo_de_tres_meses(self):
        self.panel.loc[3, ief.REAL] = 125
        self.assertEqual(self.matriz().iloc[3].deuda_var_real_3m_pct, 25)

    def test_calentamiento_conserva_filas(self):
        d = self.matriz()
        self.assertEqual(len(d), 16)
        self.assertEqual(int(d.elegible_ief.sum()), 10)
        self.assertTrue(d.iloc[:3].motivos_no_elegible.str.contains('historia_insuficiente_3m').all())

    def test_hueco_no_comprime_lag_ni_inventa_cero(self):
        self.panel = self.panel.drop(index=1)
        d = self.matriz().query("cuit_normalizado == '001'").reset_index(drop=True)
        self.assertEqual(len(d), 8)
        self.assertFalse(d.iloc[1].fila_presente_fuente)
        self.assertTrue(pd.isna(d.iloc[1][ief.REAL]))
        self.assertTrue(d.iloc[3:5].deuda_var_real_3m_pct.isna().all())
        self.assertTrue(d.iloc[5].elegible_ief)

    def test_mes_no_observado_aunque_tenga_valores_no_se_usa(self):
        self.panel.loc[1, 'mes_observado'] = False
        d = self.matriz()
        self.assertFalse(d.iloc[1].elegible_ief)
        self.assertTrue(pd.isna(d.iloc[3].deuda_var_real_3m_pct))

    def test_cero_observado_intermedio_y_denominador_cero(self):
        self.panel.loc[1, [ief.NOMINAL, ief.REAL, ief.COUNT]] = 0
        self.panel.loc[1, 'empresa_con_deuda_activa'] = False
        d = self.matriz()
        self.assertTrue(d.iloc[3].elegible_ief)  # cero intermedio observado no es un hueco
        self.assertFalse(d.iloc[4].elegible_ief)  # deuda base cero tres meses antes
        self.assertTrue(pd.isna(d.iloc[4].deuda_var_real_3m_pct))
        self.assertIn('deuda_base_3m_no_positiva', d.iloc[4].motivos_no_elegible)
        self.assertTrue(pd.isna(d.iloc[1].hhi_deuda_positiva))
        self.assertFalse(np.isinf(d[list(ief.FEATURES)].to_numpy(dtype=float)).any())

    def test_ipc_faltante_no_se_arrastra(self):
        self.panel.loc[1, 'estado_ajuste_ipc'] = 'ipc_faltante'
        self.panel.loc[1, ief.REAL] = np.nan
        d = self.matriz()
        self.assertTrue(pd.isna(d.iloc[3].deuda_var_real_3m_pct))
        self.assertIn('ajuste_ipc_no_disponible_ventana', d.iloc[3].motivos_no_elegible)

    def test_composicion_faltante_no_se_suma_como_cero(self):
        self.panel.loc[3, 'pct_deuda_situacion_2'] = np.nan
        d = self.matriz().iloc[3]
        self.assertTrue(pd.isna(d.pct_deuda_situacion_2_mas))
        self.assertFalse(d.elegible_ief)

    def test_situacion_desconocida_no_es_categoria_uno(self):
        self.panel.loc[3, 'situacion_max_activa'] = np.nan
        d = self.matriz().iloc[3]
        self.assertTrue(pd.isna(d.situacion_max_activa))
        self.assertIn('no_disponible:situacion_max_activa', d.motivos_no_elegible)

    def test_cambiar_futuro_no_cambia_pasado(self):
        before = self.matriz()
        future = self.panel.fecha.ge('2025-02-01')
        self.panel.loc[future, ief.REAL] *= 100
        self.panel.loc[future, 'situacion_max_activa'] = 5
        after = self.matriz()
        assert_frame_equal(before.loc[before.fecha.lt('2025-02-01')],
                           after.loc[after.fecha.lt('2025-02-01')])

    def test_no_mutar_entradas_ni_multiplicar_pertenencias(self):
        original = self.panel.copy(deep=True)
        empresas = self.empresas.copy(deep=True)
        d = self.matriz()
        assert_frame_equal(self.panel, original)
        assert_frame_equal(self.empresas, empresas)
        self.assertEqual(len(d), len(original))
        self.assertEqual(d.cuit_normalizado.nunique(), 2)
        self.assertEqual(d.cuit_normalizado.iloc[0], '001')

    def test_claves_invalidas_rechazadas(self):
        for invalid in (pd.concat([self.panel, self.panel.iloc[[0]]]),
                        self.panel.assign(cuit_normalizado=123),
                        self.panel.assign(cuit_normalizado='999'),
                        self.panel.assign(fecha='2024-08-15')):
            with self.subTest(invalid=invalid.iloc[0].to_dict()):
                with self.assertRaises(ValueError):
                    ief.construir_matriz(invalid, self.empresas)

    def test_numeros_invalidos_rechazados(self):
        for col, value in [(ief.REAL, -1), (ief.REAL, np.inf),
                           ('hhi_deuda_positiva', 1.2), ('pct_deuda_situacion_2', 101),
                           ('situacion_max_activa', 1.5), ('situacion_max_activa', 7), (ief.COUNT, .5)]:
            invalid = self.panel.copy()
            invalid[col] = invalid[col].astype(float)
            invalid.loc[3, col] = value
            with self.subTest(col=col, value=value), self.assertRaises(ValueError):
                ief.construir_matriz(invalid, self.empresas)


class IntegracionIEF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.provenance = ief.leer_insumos(ROOT)
        cls.frame = ief.construir_matriz(cls.tables['empresa_mes'], cls.tables['empresas'])

    def test_cobertura_y_seis_predictores(self):
        self.assertEqual(len(ief.FEATURES), 6)
        self.assertEqual(len(self.frame), 2400)
        self.assertEqual(self.frame.cuit_normalizado.nunique(), 100)
        self.assertEqual(int(self.frame.elegible_ief.sum()), 2047)
        self.assertEqual({k: v['elegibles'] for k, v in ief.resumir(self.frame).items()},
                         {'train': 875, 'validacion': 587, 'evaluacion': 585})
        self.assertFalse(self.frame.duplicated(ief.KEY).any())
        self.assertEqual(int((~self.frame.empresa_con_deuda_activa).sum()), 47)
        self.assertTrue(self.frame.loc[~self.frame.empresa_con_deuda_activa, 'elegible_ief'].eq(False).all())

    def test_cortes_por_mes_y_reserva_no_extensible(self):
        self.assertTrue(self.frame.groupby('fecha').split.nunique().eq(1).all())
        for month, split in [('2025-07-01', 'train'), ('2025-08-01', 'validacion'),
                             ('2026-01-01', 'validacion'), ('2026-02-01', 'evaluacion')]:
            self.assertTrue(self.frame.loc[self.frame.fecha.eq(month), 'split'].eq(split).all())
        panel = self.tables['empresa_mes'].copy()
        extra = panel.loc[panel.fecha.eq('2026-07-01')].copy()
        extra['fecha'], extra['ipc_fecha_mes'] = '2026-08-01', '2026-08-31'
        d = ief.construir_matriz(pd.concat([panel, extra]), self.tables['empresas'])
        outside = d.loc[d.fecha.eq('2026-08-01')]
        self.assertTrue(outside.split.eq('fuera_protocolo').all())
        self.assertFalse(outside.elegible_ief.any())

    def test_lag_puede_usar_historia_del_bloque_previo(self):
        first_validation = self.frame.loc[self.frame.fecha.eq('2025-08-01')]
        self.assertGreater(int(first_validation.elegible_ief.sum()), 90)

    def test_exportacion_reproducible_e_inmutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'matriz'
            _, report, _ = ief.ejecutar(ROOT, destination)
            digest = ief.sha256(destination / 'features_ief.csv')
            self.assertEqual(report['features_sha256'], digest)
            ief.ejecutar(ROOT, destination)
            self.assertEqual(ief.sha256(destination / 'features_ief.csv'), digest)
            stored = json.loads((destination / 'protocolo_resultados.json').read_text())
            self.assertFalse(stored['modelo_entrenado'])
            self.assertEqual(stored['unidad_deuda_real'], 'miles_ARS_dic2016')
            self.assertEqual(stored['predictores_ordenados'], list(ief.FEATURES_MODELO))
            self.assertEqual(stored['filas_grilla_agregadas'], 0)
            (destination / 'features_ief.csv').write_text('alterado')
            with self.assertRaises(FileExistsError):
                ief.ejecutar(ROOT, destination)
            self.assertEqual((destination / 'features_ief.csv').read_text(), 'alterado')

    def test_tabla_o_contrato_alterado_rechazados(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / 'config', root / 'config')
            shutil.copytree(ROOT / 'lib', root / 'lib')
            analytics = root / 'data_analytics'
            analytics.mkdir()
            shutil.copy2(ROOT / 'data_analytics/latest.json', analytics / 'latest.json')
            run = analytics / 'runs' / self.provenance['run_origen']
            original = ROOT / 'data_analytics/runs' / self.provenance['run_origen']
            run.mkdir(parents=True)
            shutil.copytree(original / 'base_c', run / 'base_c')
            shutil.copy2(original / 'run_metadata.json', run / 'run_metadata.json')
            (run / 'base_a').mkdir()
            shutil.copy2(original / 'base_a/deflactor_ipc.csv', run / 'base_a/deflactor_ipc.csv')
            ief.leer_insumos(root)
            path = run / 'base_c/empresa_mes.csv'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'tabla alterada'):
                ief.leer_insumos(root)
            schema = root / 'config/esquema_tablas.json'
            schema.write_bytes(schema.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'contrato incompatible'):
                ief.leer_insumos(root)

    def test_interrupcion_no_publica_bundle_parcial(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'matriz'
            with patch.object(ief, 'write_csv', side_effect=RuntimeError('interrupcion')):
                with self.assertRaises(RuntimeError):
                    ief.ejecutar(ROOT, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_destino_no_puede_ser_fuente(self):
        with self.assertRaisesRegex(ValueError, 'destino protegido'):
            ief.ejecutar(ROOT, ROOT / 'data_c/no_crear_ief')


class TratamientoIEF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.provenance = ief.leer_insumos(ROOT)
        cls.original = ief.construir_matriz(cls.tables['empresa_mes'], cls.tables['empresas'])
        cls.processed, cls.refs = ief.tratar_matriz(cls.original)

    def test_log_simetrico_para_duplicacion_y_reduccion_mitad(self):
        panel, empresas = ejemplo()
        panel.loc[3, ief.REAL] = 200
        panel.loc[11, ief.REAL] = 50
        d = ief.transformar_crecimiento(ief.construir_matriz(panel, empresas))
        self.assertAlmostEqual(d.iloc[3][ief.LOG_RATIO], np.log(2))
        self.assertAlmostEqual(d.iloc[11][ief.LOG_RATIO], -np.log(2))

    def test_log_robusto_a_ratio_que_redondea_menos_cien(self):
        panel, empresas = ejemplo()
        panel.loc[3, ief.REAL] = 1e-200
        original = ief.construir_matriz(panel, empresas)
        self.assertEqual(original.iloc[3].deuda_var_real_3m_pct, -100)
        d = ief.transformar_crecimiento(original)
        self.assertTrue(np.isfinite(d.iloc[3][ief.LOG_RATIO]))
        self.assertAlmostEqual(d.iloc[3][ief.LOG_RATIO], np.log(1e-200) - np.log(100))

    def test_no_modifica_originales_elegibilidad_ni_otros_cinco(self):
        assert_frame_equal(self.processed[self.original.columns], self.original)
        self.assertEqual(int(self.processed.elegible_ief.sum()), 2047)
        self.assertEqual(len(ief.FEATURES_MODELO), 6)
        self.assertNotIn(ief.FEATURES[0], ief.FEATURES_MODELO)
        self.assertNotIn('crecimiento_fuera_rango_train', ief.FEATURES_MODELO)
        self.assertTrue(np.isfinite(self.processed.loc[self.processed.elegible_ief,
                                                     list(ief.FEATURES_MODELO)]).all().all())

    def test_no_imputa_ceros_o_historia_faltante(self):
        panel, empresas = ejemplo()
        panel.loc[1, [ief.NOMINAL, ief.REAL, ief.COUNT]] = 0
        panel.loc[1, 'empresa_con_deuda_activa'] = False
        d = ief.transformar_crecimiento(ief.construir_matriz(panel, empresas))
        self.assertTrue(pd.isna(d.iloc[4][ief.LOG_RATIO]))
        self.assertTrue(d.iloc[:3][ief.LOG_RATIO].isna().all())

    def test_referencias_solo_train_invariantes_al_futuro(self):
        modified = self.original.copy()
        future = modified.split.ne('train')
        modified.loc[future, ief.REAL] *= 1000
        modified.loc[future, ief.FEATURES[0]] *= 1000
        processed, refs = ief.tratar_matriz(modified)
        self.assertEqual(refs, self.refs)
        assert_frame_equal(processed.loc[processed.split.eq('train')],
                           self.processed.loc[self.processed.split.eq('train')])

    def test_aplicacion_de_referencias_guardadas_sin_refit(self):
        d = self.original.copy()
        d['split'] = 'validacion'
        with patch.object(ief, 'ajustar_referencias_tratamiento', side_effect=AssertionError('refit')):
            processed, refs = ief.tratar_matriz(d, referencias=json.loads(json.dumps(self.refs)))
        self.assertEqual(refs, self.refs)
        assert_frame_equal(processed[list(ief.FEATURES_MODELO)],
                           self.processed[list(ief.FEATURES_MODELO)])

    def test_extremos_futuros_conservados_y_marcados(self):
        evaluation = self.processed.loc[self.processed.elegible_ief & self.processed.split.eq('evaluacion')]
        largest = evaluation.loc[evaluation[ief.LOG_RATIO].idxmax()]
        self.assertGreater(largest[ief.LOG_RATIO], self.refs['resumen_train'][ief.LOG_RATIO]['max'])
        self.assertTrue(largest.crecimiento_fuera_rango_train)
        # El mapeo logaritmico conserva el crecimiento original, sin winsorizar.
        self.assertAlmostEqual(np.expm1(largest[ief.LOG_RATIO]) * 100,
                               largest[ief.FEATURES[0]], places=5)

    def test_no_ajustar_referencias_sin_train_o_con_columna_constante(self):
        no_train = self.processed.assign(split='validacion')
        with self.assertRaisesRegex(ValueError, 'faltan filas'):
            ief.ajustar_referencias_tratamiento(no_train)
        constant = self.processed.copy()
        constant['hhi_deuda_positiva'] = .5
        with self.assertRaisesRegex(ValueError, 'constante'):
            ief.ajustar_referencias_tratamiento(constant)

    def test_orden_y_version_de_referencias_obligatorios(self):
        for key, value in [('version', '0.1'), ('predictores_ordenados', list(reversed(ief.FEATURES_MODELO))),
                           ('winsorizacion', True)]:
            refs = json.loads(json.dumps(self.refs))
            refs[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ief.tratar_matriz(self.original, refs)

    def test_reconciliacion_con_detalle_detecta_hhi_incorrecto(self):
        panel = self.tables['empresa_mes'].copy()
        index = panel.loc[panel.empresa_con_deuda_activa].index[0]
        panel.loc[index, 'hhi_deuda_positiva'] = 1 - panel.loc[index, 'hhi_deuda_positiva']
        with self.assertRaisesRegex(ValueError, 'hhi_deuda_positiva'):
            ief.auditar_detalle_c(panel, self.tables['deuda_entidad_mes'])

    def test_seis_extremos_de_train_coinciden_con_capturas(self):
        cases = ief.auditar_extremos_fuente(ROOT, self.processed, self.tables['empresa_mes'],
                                           self.provenance['run_origen'])
        self.assertEqual(len(cases), 6)
        self.assertTrue(all('2024-08-01' <= row['fecha'] <= '2025-07-01' for row in cases))
        with patch.object(ief, 'sha256', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'captura original de extremo alterada'):
                ief.auditar_extremos_fuente(ROOT, self.processed, self.tables['empresa_mes'],
                                            self.provenance['run_origen'])


class BaselineIEF(unittest.TestCase):
    def ejemplo(self):
        # El empate de tres empresas ocupa las posiciones 4 a 6 y cruza el top 5.
        return pd.DataFrame({
            'cuit_normalizado': list('ABCDEFGH'), 'fecha': ['2025-08-01'] * 8,
            'split': ['validacion'] * 8, 'elegible_ief': [True] * 8,
            baseline.SITUACION: [5, 4, 2, 2, 2, 1, 2, 1],
            baseline.PROPORCION: [.000063, 100, 20, 20, 20, 0, 20, 0],
            baseline.DELTA: [.000063, 100, 0, -5, 1, 0, -1, 0],
        })

    def test_orden_lexicografico_antepone_situacion_a_monto_relativo(self):
        d = baseline.construir_baseline(self.ejemplo()).set_index('cuit_normalizado')
        self.assertEqual(int(d.loc['A', baseline.RANK_MIN]), 1)
        self.assertEqual(int(d.loc['B', baseline.RANK_MIN]), 2)
        self.assertEqual(int(d.loc['E', baseline.RANK_MIN]), 3)
        for key in 'CDG':
            self.assertEqual(int(d.loc[key, baseline.RANK_MIN]), 4)
            self.assertEqual(int(d.loc[key, baseline.RANK_MAX]), 6)
            self.assertEqual(int(d.loc[key, baseline.TIES]), 3)

    def test_empate_en_borde_top5_ponderado_sin_falsa_seleccion(self):
        d = baseline.construir_baseline(self.ejemplo()).set_index('cuit_normalizado')
        for key in 'CDG':
            self.assertAlmostEqual(d.loc[key, 'baseline_peso_top5'], 2 / 3)
        self.assertAlmostEqual(d.baseline_peso_top5.sum(), 5)
        self.assertEqual(int(d.baseline_peso_top5.gt(0).sum()), 6)
        self.assertAlmostEqual(d.baseline_peso_top10.sum(), 8)

    def test_empate_total_y_universo_menor_que_k(self):
        source = self.ejemplo()
        source[[baseline.SITUACION, baseline.PROPORCION, baseline.DELTA]] = [1, 0, 0]
        d = baseline.construir_baseline(source)
        self.assertTrue(d[baseline.RANK_MIN].eq(1).all())
        self.assertTrue(d[baseline.RANK_MAX].eq(8).all())
        self.assertTrue(d.baseline_peso_top5.eq(5 / 8).all())
        self.assertTrue(d.baseline_peso_top10.eq(1).all())

    def test_mejora_no_suma_prioridad_y_delta_original_se_conserva(self):
        source = self.ejemplo()
        d = baseline.construir_baseline(source)
        self.assertEqual(float(d.loc[d.cuit_normalizado.eq('D'), baseline.DELTA].iloc[0]), -5)
        self.assertEqual(float(d.loc[d.cuit_normalizado.eq('D'), baseline.AUMENTO].iloc[0]), 0)
        assert_frame_equal(d[source.columns], source)

    def test_orden_de_filas_y_cuit_no_rompen_empates(self):
        source = self.ejemplo()
        assert_frame_equal(baseline.construir_baseline(source),
                           baseline.construir_baseline(source.sample(frac=1, random_state=42)))
        renamed = source.copy()
        renamed.loc[renamed.cuit_normalizado.eq('C'), 'cuit_normalizado'] = 'ZZZ'
        d = baseline.construir_baseline(renamed).set_index('cuit_normalizado')
        self.assertEqual(int(d.loc['ZZZ', baseline.RANK_MIN]), 4)
        self.assertAlmostEqual(d.loc['ZZZ', 'baseline_peso_top5'], 2 / 3)

    def test_mes_futuro_no_modifica_pasado(self):
        source = self.ejemplo()
        future = source.copy().assign(fecha='2025-09-01')
        future[baseline.SITUACION] = 6
        d = baseline.construir_baseline(pd.concat([source, future]))
        assert_frame_equal(d.loc[d.fecha.eq('2025-08-01')].reset_index(drop=True),
                           baseline.construir_baseline(source))

    def test_no_elegibles_nulos_y_mes_sin_elegibles(self):
        source = self.ejemplo()
        source.loc[source.cuit_normalizado.eq('A'), 'elegible_ief'] = False
        source['motivos_no_elegible'] = ''
        source.loc[source.cuit_normalizado.eq('A'), 'motivos_no_elegible'] = 'historia_insuficiente_3m'
        d = baseline.construir_baseline(source)
        excluded = d.loc[d.cuit_normalizado.eq('A')].iloc[0]
        for col in (baseline.RANK_MIN, baseline.RANK_MAX, baseline.TIES, 'baseline_peso_top5'):
            self.assertTrue(pd.isna(excluded[col]))
        self.assertEqual(excluded.motivos_no_elegible, 'historia_insuficiente_3m')
        all_excluded = baseline.construir_baseline(source.assign(elegible_ief=False))
        self.assertTrue(all_excluded[baseline.RANK_MIN].isna().all())
        self.assertEqual(baseline.resumir_baseline(all_excluded)[0]['masa_top5'], 0)

    def test_no_acepta_claves_duplicadas_o_predictores_invalidos(self):
        source = self.ejemplo()
        with self.assertRaises(ValueError):
            baseline.construir_baseline(pd.concat([source, source.iloc[[0]]]))
        for col, value in [(baseline.SITUACION, 7), (baseline.PROPORCION, 101),
                           (baseline.DELTA, np.inf), (baseline.DELTA, np.nan)]:
            invalid = source.copy()
            invalid[col] = invalid[col].astype(float)
            invalid.loc[0, col] = value
            with self.subTest(col=col, value=value), self.assertRaises(ValueError):
                baseline.construir_baseline(invalid)

    def test_matriz_real_preservada_y_ranking_completo(self):
        frame, _ = baseline.cargar_matriz(ROOT)
        d = baseline.construir_baseline(frame)
        assert_frame_equal(d[frame.columns], frame)
        self.assertEqual(len(d), 2400)
        self.assertEqual(int(d[baseline.RANK_MIN].notna().sum()), 2047)
        self.assertEqual(int(d[baseline.RANK_MIN].isna().sum()), 353)
        months = baseline.resumir_baseline(d)
        self.assertEqual(len(months), 24)
        self.assertEqual(sum(m['masa_top5'] for m in months), 105)
        self.assertTrue(all(m['masa_top5'] == 0 for m in months[:3]))

    def test_publicacion_reproducible_sin_refit_y_matriz_alterada_rechazada(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'baseline'
            with patch.object(ief, 'ajustar_referencias_tratamiento', side_effect=AssertionError('refit')):
                _, report, _ = baseline.ejecutar(ROOT, dest)
                baseline.ejecutar(ROOT, dest)
            self.assertFalse(report['parametros_ajustados'])
            self.assertFalse(report['modelo_entrenado'])
            self.assertEqual(ief.sha256(dest / 'baseline_ief.csv'), report['baseline_sha256'])
            feature_dir = Path(tmp) / 'matriz'
            source = ROOT / 'data_analytics/modelos_ief/20261006_231124_214604/v0.2'
            shutil.copytree(source, feature_dir)
            (feature_dir / 'features_ief.csv').write_text('alterado')
            with self.assertRaisesRegex(ValueError, 'matriz alterada'):
                baseline.cargar_matriz(ROOT, feature_dir)
            (dest / 'baseline_ief.csv').write_text('alterado')
            with self.assertRaises(FileExistsError):
                baseline.ejecutar(ROOT, dest)
            self.assertEqual((dest / 'baseline_ief.csv').read_text(), 'alterado')

    def test_interrupcion_y_destino_protegido(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'baseline'
            with patch.object(baseline, 'write_csv', side_effect=RuntimeError('interrupcion')):
                with self.assertRaises(RuntimeError):
                    baseline.ejecutar(ROOT, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])
        with self.assertRaisesRegex(ValueError, 'destino protegido'):
            baseline.ejecutar(ROOT, ROOT / 'data_c/no_crear_baseline')


if __name__ == '__main__':
    unittest.main()
