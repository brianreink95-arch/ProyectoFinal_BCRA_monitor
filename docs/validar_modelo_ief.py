"""Entrenamiento exclusivo en train, calibracion congelada, scoring y persistencia."""
from pathlib import Path
import io
import json
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from sklearn.ensemble import IsolationForest

from ml import ief, baseline_ief as baseline, isolation_ief as model

ROOT = Path(__file__).resolve().parents[1]


def bytes_artefacto(artifact):
    buffer = io.BytesIO()
    joblib.dump(artifact, buffer, compress=3, protocol=5)
    return buffer.getvalue()


class ModeloIEF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame, cls.provenance = model.cargar_entrada(ROOT)
        cls.artifact = model.entrenar_modelo(cls.frame)
        cls.scores = model.puntuar(cls.frame, cls.artifact)

    def test_ajuste_exclusivo_train_y_seis_columnas(self):
        artifact = self.artifact
        self.assertEqual(artifact['filas_train'], 875)
        self.assertEqual(artifact['empresas_train'], 98)
        self.assertEqual(artifact['features'], list(ief.FEATURES_MODELO))
        self.assertEqual(artifact['params'], model.PARAMS)
        self.assertEqual(len(artifact['estimator'].estimators_), 300)
        self.assertEqual(artifact['estimator'].max_samples_, 256)
        self.assertEqual(len(artifact['referencia_train']), 875)
        self.assertTrue(all('2024-11-01' <= date <= '2025-07-01' for _, date in artifact['claves_train']))

    def test_modificar_futuro_no_cambia_modelo_ni_referencia(self):
        changed = self.frame.copy()
        future = changed.split.ne('train')
        for col in ief.FEATURES_MODELO:
            changed.loc[future, col] = 12345.0
        alternative = model.entrenar_modelo(changed)
        self.assertEqual(bytes_artefacto(alternative), bytes_artefacto(self.artifact))

    def test_no_puede_etiquetar_meses_posteriores_como_train(self):
        changed = self.frame.copy()
        changed.loc[changed.split.eq('validacion'), 'split'] = 'train'
        with self.assertRaisesRegex(ValueError, 'split incompatible'):
            model.entrenar_modelo(changed)

    def test_calibracion_ecdf_con_empates_y_saturacion(self):
        actual = model.percentil_train([0, 1, 2, 3, 4, 5], [1, 2, 2, 4])
        np.testing.assert_allclose(actual, [0, 12.5, 50, 75, 87.5, 100])
        for reference in ([], [1, np.inf], [2, 1]):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                model.percentil_train([1], reference)

    def test_score_sin_fit_o_reajuste_y_orientacion_correcta(self):
        before = bytes_artefacto(self.artifact)
        with patch.object(IsolationForest, 'fit', side_effect=AssertionError('refit')):
            scores = model.puntuar(self.frame, self.artifact)
        self.assertEqual(before, bytes_artefacto(self.artifact))
        eligible = scores.elegible_ief
        expected = -self.artifact['estimator'].score_samples(
            scores.loc[eligible, list(ief.FEATURES_MODELO)].astype(float))
        np.testing.assert_array_equal(scores.loc[eligible, model.RAW], expected)
        self.assertTrue(scores.loc[eligible, model.PERCENTIL].between(0, 100).all())

    def test_preserva_panel_y_no_elegibles_sin_score(self):
        assert_frame_equal(self.scores[self.frame.columns], self.frame)
        self.assertEqual(int(self.scores[model.RAW].notna().sum()), 2047)
        self.assertEqual(int(self.scores[model.RAW].isna().sum()), 353)
        excluded = self.scores.loc[~self.scores.elegible_ief]
        self.assertTrue(excluded[[model.RAW, model.PERCENTIL, 'ief_peso_top5']].isna().all().all())
        self.assertTrue(excluded.motivos_no_elegible.ne('').all())
        for _, month in self.scores.groupby('fecha'):
            n = int(month.elegible_ief.sum())
            for k in (5, 10):
                self.assertAlmostEqual(month[f'ief_peso_top{k}'].sum(), min(k, n))

    def test_ranking_crudo_no_empata_por_saturacion_percentil(self):
        frame = pd.DataFrame({'fecha': ['2026-07-01'] * 3,
                              model.RAW: [.9, .8, .8], model.PERCENTIL: [100, 100, 100]})
        ranked = model.agregar_rangos(frame)
        self.assertEqual(ranked.ief_posicion_desde.tolist(), [1, 2, 2])
        self.assertEqual(ranked.ief_posicion_hasta.tolist(), [1, 3, 3])

    def test_orden_de_entrada_y_columnas_no_cambia_scores(self):
        shuffled = self.frame.sample(frac=1, random_state=42)
        shuffled = shuffled[list(reversed(shuffled.columns))]
        actual = model.puntuar(shuffled, self.artifact)
        assert_frame_equal(actual[self.scores.columns], self.scores)

    def test_puntuar_lote_sin_train_no_recalibra(self):
        batch = self.frame.loc[self.frame.split.eq('evaluacion')].copy()
        with patch.object(IsolationForest, 'fit', side_effect=AssertionError('refit')):
            actual = model.puntuar(batch, self.artifact)
        expected = self.scores.loc[self.scores.split.eq('evaluacion')].reset_index(drop=True)
        assert_frame_equal(actual, expected)

    def test_no_silencia_faltantes_o_columnas_ajenas(self):
        changed = self.frame.copy()
        index = changed.loc[changed.elegible_ief].index[0]
        changed.loc[index, ief.LOG_RATIO] = np.nan
        with self.assertRaisesRegex(ValueError, 'predictor elegible'):
            model.puntuar(changed, self.artifact)
        with self.assertRaises(ValueError):
            model.entrenar_modelo(self.frame, features=('cuit_normalizado',))

    def test_comparacion_consigo_mismo_y_empates_sin_diferencia(self):
        result = model.comparar(self.scores, self.scores)
        for block in result['por_bloque'].values():
            self.assertAlmostEqual(block['coincidencia_top5_media_mensual'], 1)
            self.assertAlmostEqual(block['coincidencia_top10_media_mensual'], 1)
            self.assertAlmostEqual(block['spearman_medio_mensual'], 1)
        with self.assertRaisesRegex(ValueError, 'desalineados'):
            model.comparar(self.scores, self.scores.iloc[::-1])

    def test_semilla_fija_reproduce_y_alternativa_no_reemplaza(self):
        alternative = model.entrenar_modelo(self.frame, seed=43)
        a = model.puntuar(self.frame, alternative)
        self.assertFalse(np.array_equal(a.loc[a.elegible_ief, model.RAW],
                                        self.scores.loc[self.scores.elegible_ief, model.RAW]))
        self.assertEqual(self.artifact['params']['random_state'], 42)

    def test_publicacion_modelo_y_scoring_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'bosque'
            scores, report, _ = model.ejecutar_entrenamiento(ROOT, directory)
            self.assertEqual(report['filas_train'], 875)
            artifact, _ = model.cargar_modelo(directory)
            np.testing.assert_array_equal(artifact['referencia_train'], self.artifact['referencia_train'])
            with patch.object(IsolationForest, 'fit', side_effect=AssertionError('refit')):
                scored, metadata, path = model.ejecutar_score(ROOT, directory, Path(tmp) / 'score')
            self.assertEqual((directory / 'scores_ief.csv').read_bytes(), (path / 'scores_ief.csv').read_bytes())
            assert_frame_equal(scores, scored)
            # No se guarda un estimador para cada semilla de diagnostico.
            self.assertEqual(sorted(p.name for p in directory.iterdir()),
                             ['informe_ief.md', 'modelo_ief.joblib', 'protocolo_resultados.json', 'scores_ief.csv'])
            manifest_path = directory / 'protocolo_resultados.json'
            altered = json.loads(manifest_path.read_text())
            altered['entorno']['scikit_learn'] = '0.0.0'
            manifest_path.write_text(json.dumps(altered))
            with patch.object(model.joblib, 'load', side_effect=AssertionError('no cargar')):
                with self.assertRaisesRegex(ValueError, 'version incompatible'):
                    model.cargar_modelo(directory)
            manifest_path.write_text(json.dumps(report))
            (directory / 'modelo_ief.joblib').write_bytes(b'alterado')
            with patch.object(model.joblib, 'load', side_effect=AssertionError('no cargar')):
                with self.assertRaisesRegex(ValueError, 'modelo alterado'):
                    model.cargar_modelo(directory)

    def test_publicacion_atomica_y_destino_protegido(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'bosque'
            with self.assertRaises(RuntimeError):
                with model.publicacion(ROOT, output) as stage:
                    (stage / 'modelo_ief.joblib').write_bytes(b'parcial')
                    raise RuntimeError('interrupcion')
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])
            with model.publicacion(ROOT, output) as stage:
                (stage / 'test').write_text('original')
            with self.assertRaises(FileExistsError):
                with model.publicacion(ROOT, output) as stage:
                    (stage / 'test').write_text('diferente')
            self.assertEqual((output / 'test').read_text(), 'original')
        with self.assertRaisesRegex(ValueError, 'destino protegido'):
            with model.publicacion(ROOT, ROOT / 'data_c/bosque'):
                pass


if __name__ == '__main__':
    unittest.main()
