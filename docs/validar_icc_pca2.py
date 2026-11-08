"""PCA2: proyección/reconstrucción, planos, temporalidad y separación del ICC.
Desde raíz: python -m unittest docs.validar_icc_pca2 -v
"""
from pathlib import Path
import copy
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ml import pca2 as p, baseline as b, score as s
from docs.validar_icc_s1 import matrix
from docs.validar_evaluate_features import mensual

class Matematica(unittest.TestCase):
    def setUp(self):self.Z=np.random.default_rng(37).normal(size=(80,3))@np.array([[1,.5,0],[0,2,.7],[.2,0,.5]])
    def test_proyeccion_y_signos_reproducen_sklearn(self):
        params=p.ajustar_factor(self.Z);estimator=PCA(2,svd_solver='full',whiten=False).fit(self.Z)
        orientation=np.array([1 if row[np.argmax(np.abs(row))]>=0 else -1 for row in estimator.components_])
        np.testing.assert_allclose(p.proyectar(self.Z,params),estimator.transform(self.Z)*orientation,atol=1e-12)
    def test_reconstruccion_reproduce_inverse_transform(self):
        params=p.ajustar_factor(self.Z);estimator=PCA(2,svd_solver='full',whiten=False).fit(self.Z)
        np.testing.assert_allclose(p.reconstruir(self.Z,params),estimator.inverse_transform(estimator.transform(self.Z)),atol=1e-12)
    def test_planos_invariantes_a_signos_y_rotacion(self):
        A=np.asarray(p.ajustar_factor(self.Z)['cargas']);angle=.7
        Q=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        np.testing.assert_allclose(p.cosenos_subespacios(A,Q@A),[1,1],atol=1e-12)
        np.testing.assert_allclose(p.cosenos_subespacios(A,-A),[1,1],atol=1e-12)
    def test_planos_distintos_detectados(self):
        np.testing.assert_allclose(p.cosenos_subespacios([[1,0,0],[0,1,0]],[[1,0,0],[0,0,1]]),[1,0],atol=1e-12)
    def test_rango_uno_no_identifica_dos_ejes(self):
        x=np.arange(60,dtype=float);params=p.ajustar_factor(np.column_stack([x,2*x,3*x]))
        self.assertLessEqual(params['varianza_explicada'][1],1e-12)
    def test_comparador_cero_inconcluso(self):
        c={'por_input':[0,0,0]};m={'por_input':[1,2,3]}
        result=p.contraste(m,c);self.assertFalse(result['pasa']);self.assertIsNone(result['mejora_promedio'])
    def test_promedio_no_compensa_input_peor(self):
        c={'por_input':[10,1,1]};m={'por_input':[1,2,1]}
        result=p.contraste(m,c);self.assertGreater(result['mejora_promedio'],.1);self.assertFalse(result['pasa'])

class Temporal(unittest.TestCase):
    def setUp(self):self.frame=matrix();self.model,self.out=p.entrenar_icc(self.frame)
    def test_futuro_no_cambia_parametros_ni_comparador(self):
        raw=mensual(120);mask=raw.index>=pd.Period('2022-03','M')
        raw.loc[mask,'stock_constante_dic2016']*=2;raw.loc[mask,1240]+=3
        alt,_=p.entrenar_icc(matrix(raw))
        self.assertEqual(alt['referencias'],self.model['referencias'])
        self.assertEqual(alt['parametros_pca2'],self.model['parametros_pca2'])
        for field in ['coeficientes_baseline_1d_train','coeficientes_comparador_2d_train']:
            self.assertEqual(alt['controles_diagnosticos']['reconstruccion_2d'][field],self.model['controles_diagnosticos']['reconstruccion_2d'][field])
    def test_retrospectiva_no_cambia_decision(self):
        raw=mensual(120);mask=raw.index>=pd.Period('2024-01','M')
        raw.loc[mask,'stock_constante_dic2016']*=3;raw.loc[mask,1240]+=4
        alt,_=p.entrenar_icc(matrix(raw));self.assertEqual(alt,self.model)
    def test_train_59_no_entrena(self):
        raw=mensual(120);raw.loc[pd.Period('2022-02','M'),'stock_constante_dic2016']=np.nan
        with self.assertRaisesRegex(ValueError,'insuficiente'):p.entrenar_icc(matrix(raw))
    def test_validacion_17_no_evalua(self):
        with self.assertRaisesRegex(ValueError,'Validacion insuficiente'):p.entrenar_icc(matrix(mensual(80)))
    def test_columna_constante_no_crea_pcs(self):
        raw=mensual(120);raw[1240]=4
        model,out=p.entrenar_icc(matrix(raw));self.assertIsNone(model['parametros_pca2'])
        self.assertTrue(out['pc1_diagnostico'].isna().all());self.assertTrue(out['icc_indice'].notna().any())
    def test_reserva_sin_score_ni_proyeccion(self):
        out=s.generar_indice(self.frame,self.model);mask=out.split_temporal.eq('reserva_futura')
        self.assertTrue(out.loc[mask,['icc_indice','pc1_diagnostico','pc2_diagnostico']].isna().all().all())
        self.assertTrue(self.out.loc[self.out.split_temporal.eq('evaluacion_retrospectiva'),'pc1_diagnostico'].isna().all())
    def test_scoring_sin_fit_y_train_val_identicos(self):
        with patch.object(PCA,'fit',side_effect=AssertionError('fit prohibido')):out=s.generar_indice(self.frame,self.model)
        mask=self.out['utilizable_baseline']
        np.testing.assert_array_equal(out.loc[mask,['pc1_diagnostico','pc2_diagnostico','icc_indice']],self.out.loc[mask,['pc1_diagnostico','pc2_diagnostico','icc_indice']])
    def test_core_nulo_no_imputa(self):
        raw=mensual(120);raw.loc[pd.Period('2024-08','M'),1240]=np.nan
        out=s.generar_indice(matrix(raw),self.model).set_index('fecha_mes')
        self.assertTrue(out.loc['2024-08-31',['icc_indice','pc1_diagnostico','pc2_diagnostico']].isna().all())
    def test_revision_historica_flag(self):
        raw=mensual(120);raw.loc[pd.Period('2021-01','M'),'stock_constante_dic2016']*=1.1
        self.assertFalse(s.generar_indice(matrix(raw),self.model)['historia_train_coincide'].any())
    def test_artefacto_no_admite_agregacion_por_bandera(self):
        altered=copy.deepcopy(self.model);altered['indice_pca2_definido']=True
        with self.assertRaisesRegex(ValueError,'Integridad'):s.validar_modelo(altered)
        altered['modelo_id']=b.hash_json({k:v for k,v in altered.items() if k!='modelo_id'})[:20]
        with self.assertRaisesRegex(ValueError,'agregado ICC'):s.validar_modelo(altered)
    def test_bundle_idempotente_y_protegido(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'pca2';p.exportar_entrenamiento(self.model,self.out,path)
            before=(path/'modelo_pca2.json').read_bytes();p.exportar_entrenamiento(self.model,self.out,path)
            self.assertEqual(before,(path/'modelo_pca2.json').read_bytes());s.cargar_modelo(path/'modelo_pca2.json')
            (path/'icc_pca2_diagnostico.csv').write_text('corrupto')
            with self.assertRaisesRegex(ValueError,'alterado'):s.cargar_modelo(path/'modelo_pca2.json')

class IntegracionReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame,cls.source=b.cargar_entrada(ROOT);cls.model,cls.out=p.entrenar_icc(cls.frame,cls.source)
    def test_varianza_90pct_y_stock_mejora(self):
        ratio=sum(self.model['parametros_pca2']['varianza_explicada_ratio'])
        self.assertAlmostEqual(ratio,.9024921276432865)
        m=self.model['controles_diagnosticos']['reconstruccion_2d']['metricas']
        self.assertLess(m['pca2']['validacion']['por_input'][0],m['pca1']['validacion']['por_input'][0])
    def test_comparacion_dimensionalidad_equivalente_falla(self):
        c=self.model['controles_diagnosticos']['reconstruccion_2d']['contraste_2d']
        self.assertFalse(c['pasa']);self.assertAlmostEqual(c['mejora_promedio'],-.1961978963297717)
        self.assertGreater(c['ratios_por_input'][1],1.25)
    def test_subespacio_estable_no_indice_aceptado(self):
        self.assertTrue(self.model['controles_diagnosticos']['perturbaciones_subespacio']['pasa'])
        self.assertFalse(self.model['indice_pca2_definido']);self.assertFalse(self.model['pca2_admitido_como_icc'])
    def test_112_baseline_preservado_no_muta(self):
        before=self.frame.copy(deep=True);out=s.generar_indice(self.frame,self.model)
        baseline=b.aplicar_baseline_icc(self.frame,self.model['referencias'])
        pd.testing.assert_frame_equal(before,self.frame);np.testing.assert_array_equal(out['icc_indice'],baseline['icc_baseline_s1'])
        self.assertEqual(int(out['icc_indice'].notna().sum()),112)
        self.assertEqual(int(out['pc2_diagnostico'].notna().sum()),112)
    def test_60_22_y_reconstrucciones_anteriores_reproducidas(self):
        self.assertEqual(self.model['controles_diagnosticos']['cobertura'],{'pasa':True,'n_train':60,'n_validacion':22})
        m=self.model['controles_diagnosticos']['reconstruccion_2d']['metricas']
        self.assertAlmostEqual(m['baseline_1d']['validacion']['promedio'],8.463186210110491)
        self.assertAlmostEqual(m['pca1']['validacion']['promedio'],7.260624591114609)
        self.assertAlmostEqual(m['fa1']['validacion']['promedio'],7.2861539689413455)

if __name__=='__main__':unittest.main()
