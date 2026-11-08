"""Análisis factorial ICC: posterior correcto, temporalidad, rechazo y bundles.
Desde raíz: python -m unittest docs.validar_icc_factor -v
"""
from pathlib import Path
import copy
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import numpy as np
import pandas as pd
from sklearn.decomposition import FactorAnalysis
from sklearn.exceptions import ConvergenceWarning
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ml import factor as fa, baseline as b, train as t, score as s
from docs.validar_icc_s1 import matrix
from docs.validar_evaluate_features import mensual

class Matematica(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(17);f=rng.normal(size=(120,1))
        self.Z=f@np.array([[.8,.9,.7]])+rng.normal(size=(120,3))*.3
    def test_posterior_formula_conocida(self):
        np.testing.assert_allclose(fa.pesos_posteriores([.5]*3,[.5]*3),[.4]*3)
    def test_posterior_no_es_carga(self):
        w=fa.pesos_posteriores([.5]*3,[.1,1.,2.])
        self.assertGreater(w[0],w[1]);self.assertGreater(w[1],w[2])
    def test_psi_cero_negativo_nan_rechazados(self):
        for psi in ([0,1,1],[-1,1,1],[float('nan'),1,1]):
            with self.assertRaises(ValueError):fa.pesos_posteriores([.5]*3,psi)
    def test_proyeccion_reproduce_sklearn(self):
        f=fa.ajustar_factor(self.Z)
        estimator=FactorAnalysis(1,svd_method='lapack',rotation=None,tol=.01,max_iter=1000).fit(self.Z)
        sign=1 if estimator.components_[0,1]>=0 else -1
        np.testing.assert_allclose(t.proyectar(self.Z,f),estimator.transform(self.Z).ravel()*sign,atol=1e-12)
    def test_reconstruccion_es_media_condicional_no_proyeccion_pca(self):
        f=fa.ajustar_factor(self.Z)
        reconstructed=np.outer(t.proyectar(self.Z,f),f['cargas'])+f['centro_factor']
        estimator=FactorAnalysis(1,svd_method='lapack',rotation=None,tol=.01,max_iter=1000).fit(self.Z)
        expected=estimator.transform(self.Z)@estimator.components_+estimator.mean_
        np.testing.assert_allclose(reconstructed,expected,atol=1e-12)
    def test_cargas_positivas_no_bastan_pesos_volume_bajos(self):
        f={'cargas':[.6,.6,.6],'pesos_score':fa.pesos_posteriores([.6]*3,[100,.1,.1]).tolist()}
        self.assertTrue(fa.direcciones(f)['cargas_generativas']['pasa'])
        self.assertFalse(fa.direcciones(f)['pasa'])
    def test_advertencia_convergencia_bloquea(self):
        original=FactorAnalysis.fit
        def fake_fit(estimator,Z,*args,**kwargs):
            result=original(estimator,Z,*args,**kwargs)
            warnings.warn('Convergencia insuficiente simulada',ConvergenceWarning)
            return result
        with patch.object(FactorAnalysis,'fit',fake_fit):f=fa.ajustar_factor(self.Z)
        self.assertFalse(f['convergio']);self.assertTrue(f['advertencias'])
    def test_signos_conservados(self):
        Z=self.Z.copy();Z[:,0]*=-1
        f=fa.ajustar_factor(Z)
        self.assertGreaterEqual(f['cargas'][1],0);self.assertLess(f['cargas'][0],0)
        self.assertFalse(fa.direcciones(f)['pasa'])

class Temporal(unittest.TestCase):
    def setUp(self):self.frame=matrix();self.model,self.scores=fa.entrenar_icc(self.frame)
    def test_futuro_no_cambia_fit(self):
        raw=mensual(120);mask=raw.index>=pd.Period('2022-03','M')
        raw.loc[mask,'stock_constante_dic2016']*=2;raw.loc[mask,1240]+=4
        changed,_=fa.entrenar_icc(matrix(raw))
        self.assertEqual(changed['referencias'],self.model['referencias'])
        self.assertEqual(changed['parametros_factor'],self.model['parametros_factor'])
    def test_retrospectiva_no_cambia_decision(self):
        raw=mensual(120);mask=raw.index>=pd.Period('2024-01','M')
        raw.loc[mask,'stock_constante_dic2016']*=2;raw.loc[mask,1240]+=4
        changed,_=fa.entrenar_icc(matrix(raw));self.assertEqual(changed,self.model)
    def test_59_train_bloquea(self):
        raw=mensual(120);raw.loc[pd.Period('2022-02','M'),'stock_constante_dic2016']=np.nan
        with self.assertRaisesRegex(ValueError,'insuficiente'):fa.entrenar_icc(matrix(raw))
    def test_validacion_17_bloquea(self):
        with self.assertRaisesRegex(ValueError,'Validacion insuficiente'):fa.entrenar_icc(matrix(mensual(80)))
    def test_constante_no_fuerza_factor(self):
        raw=mensual(120);raw[1240]=4
        model,out=fa.entrenar_icc(matrix(raw))
        self.assertIsNone(model['parametros_factor']);self.assertFalse(model['factor_aceptado'])
        self.assertTrue(out['icc_indice'].notna().any());fa.validar_modelo(model)
    def test_train_excluye_retro_y_reserva(self):
        self.assertTrue(self.scores.loc[self.scores.split_temporal.isin(['evaluacion_retrospectiva','reserva_futura']),'icc_indice'].isna().all())
        out=s.generar_indice(self.frame,self.model)
        self.assertTrue(out.loc[out.split_temporal.eq('reserva_futura'),'icc_indice'].isna().all())
        mask=self.scores['utilizable_baseline']
        np.testing.assert_array_equal(out.loc[mask,'icc_indice'],self.scores.loc[mask,'icc_indice'])
    def test_scoring_sin_fit(self):
        with patch.object(FactorAnalysis,'fit',side_effect=AssertionError('fit prohibido')):
            out=s.generar_indice(self.frame,self.model)
        self.assertTrue(out['icc_indice'].notna().any())
    def test_revision_historica_no_reajusta(self):
        raw=mensual(120);raw.loc[pd.Period('2021-01','M'),'stock_constante_dic2016']*=1.1
        self.assertFalse(s.generar_indice(matrix(raw),self.model)['historia_train_coincide'].any())
    def test_no_imputa_core(self):
        raw=mensual(120);raw.loc[pd.Period('2024-08','M'),1240]=np.nan
        out=s.generar_indice(matrix(raw),self.model).set_index('fecha_mes')
        self.assertTrue(np.isnan(out.loc['2024-08-31','icc_indice']))
    def test_integridad_modelo_y_bundle(self):
        alt=copy.deepcopy(self.model);alt['factor_aceptado']=not alt['factor_aceptado']
        with self.assertRaisesRegex(ValueError,'Integridad'):s.validar_modelo(alt)
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'fa';fa.exportar_entrenamiento(self.model,self.scores,out)
            before=(out/'modelo_icc.json').read_bytes()
            fa.exportar_entrenamiento(self.model,self.scores,out)
            self.assertEqual(before,(out/'modelo_icc.json').read_bytes());s.cargar_modelo(out/'modelo_icc.json')
            (out/'icc_entrenamiento.csv').write_text('corrupto')
            with self.assertRaisesRegex(ValueError,'alterado'):s.cargar_modelo(out/'modelo_icc.json')

class IntegracionReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame,cls.source=b.cargar_entrada(ROOT);cls.model,cls.out=fa.entrenar_icc(cls.frame,cls.source)
    def test_60_22_y_referencias_baseline_preservadas(self):
        self.assertEqual(self.model['gates']['cobertura'],{'pasa':True,'n_train':60,'n_validacion':22})
        self.assertEqual(self.model['referencias'],b.ajustar_referencias_icc(self.frame))
    def test_fallo_no_oculta_volumen_7pct(self):
        gate=self.model['gates']['direccion_factor']
        self.assertAlmostEqual(gate['pesos_efectivos_score']['participaciones_l1'][0],.0709660982600378)
        self.assertFalse(self.model['factor_aceptado'])
        self.assertIn('direccion_factor',self.model['motivos_rechazo_factor'])
        self.assertIn('reconstruccion',self.model['motivos_rechazo_factor'])
        self.assertTrue(self.out['icc_fa_candidato'].isna().all())
        self.assertTrue(self.out['factor_fa_diagnostico'].notna().any())
    def test_promedio_mejora_columnas_fallan(self):
        m=self.model['gates']['reconstruccion']['metricas']['validacion']
        self.assertGreater(m['mejora_relativa'],.10);self.assertGreater(m['ratios_por_columna'][0],1.25)
        self.assertGreater(m['ratios_por_columna'][2],1.25);self.assertFalse(m['pasa'])
    def test_direcciones_perturbaciones_fallan_con_ranking_estable(self):
        cases=self.model['gates']['perturbaciones_factor']['casos'];self.assertEqual(len(cases),6)
        self.assertTrue(all(x['coseno']>=.95 and x['spearman_val']>=.90 for x in cases))
        self.assertTrue(all(not x['direccion_admisible'] for x in cases))
    def test_factor_determinista_y_df_cero_visible(self):
        model,out=fa.entrenar_icc(self.frame,self.source)
        self.assertEqual(model,self.model);pd.testing.assert_frame_equal(out,self.out)
        self.assertEqual(model['parametros_factor']['grados_libertad_covarianza'],0)
        self.assertTrue(model['parametros_factor']['convergio'])
    def test_salida_112_no_muta_igual_baseline_s1(self):
        before=self.frame.copy(deep=True);out=s.generar_indice(self.frame,self.model)
        baseline=b.aplicar_baseline_icc(self.frame,self.model['referencias'])
        pd.testing.assert_frame_equal(before,self.frame)
        np.testing.assert_array_equal(out['icc_indice'],baseline['icc_baseline_s1'])
        self.assertEqual(int(out['icc_indice'].notna().sum()),112)

if __name__=='__main__':unittest.main()
