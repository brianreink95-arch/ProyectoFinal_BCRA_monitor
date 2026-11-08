"""Regresiones económicas, temporales y de publicación S1; sin red ni tuning.
Ejecutar desde raíz: python -m unittest docs.validar_icc_s1 -v
"""
from pathlib import Path
import copy
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ml import baseline as b, train as t, score as s, features as f
from docs.validar_evaluate_features import mensual

def matrix(raw=None):
    return f.calcular_features_icc(mensual(120) if raw is None else raw)

class Economia(unittest.TestCase):
    def setUp(self):self.frame=matrix();self.q=b.ajustar_referencias_icc(self.frame)
    def test_ancla_25_no_50(self):
        V,C,M,B=b.componentes(self.q['R0'],self.q['r0'],0,self.q)
        np.testing.assert_allclose([V,C,M,B],[.5,.5,.5,25])
    def test_bajo_stock_y_cero(self):
        x=b.componentes(np.array([0,.01,.25])*self.q['R0'],0,1e4,self.q)[3]
        self.assertEqual(x[0],0);self.assertTrue((x<=20).all())
    def test_menor_tasa_mejora(self):
        R=self.q['R0'];r=self.q['r0']
        self.assertGreater(b.componentes(R,r-1,0,self.q)[3],b.componentes(R,r+1,0,self.q)[3])
    def test_mas_stock_mejora(self):
        x=b.componentes(np.array([.1,1,2])*self.q['R0'],self.q['r0'],0,self.q)[3]
        self.assertTrue((np.diff(x)>0).all())
    def test_g_cero_economico(self):self.assertEqual(b.componentes(1,2,0,self.q)[2],.5)
    def test_extremos_y_tasa_cero_finitos(self):
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            x=b.componentes([0,1e20],0,[-1e4,1e4],self.q)[3]
            np.testing.assert_allclose(b.logistica([-1000,0,1000]),[0,.5,1])
        self.assertTrue(np.isfinite(x).all())
    def test_escenarios_detectan_signo_invertido(self):
        self.assertTrue(b.controles_economicos(self.q)['pasa'])
        self.assertFalse(b.controles_economicos(self.q,lambda R,r,g:b.componentes(R,100-r,g,self.q)[3])['pasa'])
    def test_negativos_no_validos(self):
        for R,r in [(-1,2),(2,-1)]:
            with self.assertRaises(ValueError):b.componentes(R,r,0,self.q)
    def test_pisos_constantes(self):
        self.assertEqual(b.escala([3]*60,.1),.1);self.assertEqual(b.escala([3]*60,.5),.5)

class Temporal(unittest.TestCase):
    def setUp(self):self.frame=matrix()
    def test_minimo_no_reducible(self):
        for n in (1,57,59,True,float('nan')):
            with self.assertRaises(ValueError):b.ajustar_referencias_icc(self.frame,n)
    def test_train_59_bloquea(self):
        raw=mensual(120);raw.loc[pd.Period('2022-02','M'),'stock_constante_dic2016']=np.nan
        with self.assertRaisesRegex(ValueError,'insuficiente'):t.entrenar_icc(matrix(raw))
    def test_validacion_17_bloquea(self):
        with self.assertRaisesRegex(ValueError,'Validacion insuficiente'):t.entrenar_icc(matrix(mensual(80)))
    def test_muestra_comun_60(self):
        q=b.ajustar_referencias_icc(self.frame)
        train=self.frame.loc[b.asignar_splits_icc(self.frame).eq('train')&b.mascara_core(self.frame)]
        self.assertEqual(q['n_train'],60);self.assertEqual(q['R0'],float(train[b.STOCK_REAL].median()))
        self.assertEqual(q['fechas_train'][0],'2017-03-31');self.assertEqual(q['fechas_train'][-1],'2022-02-28')
    def test_futuro_no_cambia_parametros(self):
        model,_=t.entrenar_icc(self.frame)
        raw=mensual(120);mask=raw.index>=pd.Period('2022-03','M')
        raw.loc[mask,'stock_constante_dic2016']*=2;raw.loc[mask,1240]+=5
        alt,_=t.entrenar_icc(matrix(raw))
        self.assertEqual(model['referencias'],alt['referencias'])
        self.assertEqual(model['parametros_pca'],alt['parametros_pca'])
    def test_retrospectiva_no_cambia_decision(self):
        model,_=t.entrenar_icc(self.frame)
        raw=mensual(120);mask=raw.index>=pd.Period('2024-01','M')
        raw.loc[mask,'stock_constante_dic2016']*=3;raw.loc[mask,1240]+=5
        alt,_=t.entrenar_icc(matrix(raw));self.assertEqual(model,alt)
    def test_reserva_no_score_y_retro_solo_despues(self):
        model,trained=t.entrenar_icc(self.frame);out=s.generar_indice(self.frame,model)
        self.assertTrue(out.loc[out['split_temporal'].eq('reserva_futura'),'icc_indice'].isna().all())
        self.assertTrue(trained.loc[trained['split_temporal'].eq('evaluacion_retrospectiva'),'icc_indice'].isna().all())
        with self.assertRaises(ValueError):b.aplicar_baseline_icc(self.frame,model['referencias'],('reserva_futura',))
    def test_nulo_core_no_imputa_opcional_no_bloquea(self):
        raw=mensual(120);raw.loc[pd.Period('2024-07','M'),1240]=np.nan
        raw.loc[pd.Period('2024-11','M'),next(iter(f.DESGLOSE_ICC))]=np.nan
        frame=matrix(raw);model,_=t.entrenar_icc(frame);out=s.generar_indice(frame,model).set_index('fecha_mes')
        self.assertTrue(np.isnan(out.loc['2024-07-31','icc_indice']))
        self.assertTrue(np.isfinite(out.loc['2024-11-30','icc_indice']))

class PCAContrato(unittest.TestCase):
    def setUp(self):self.frame=matrix();self.model,self.scores=t.entrenar_icc(self.frame)
    def test_no_abs_ni_cargas_insuficientes(self):
        self.assertFalse(t.cargas_admisibles([-.3,.7,.6])['pasa'])
        self.assertFalse(t.cargas_admisibles([.1,.8,.1])['pasa'])
        self.assertTrue(t.cargas_admisibles([.4,.3,.3])['pasa'])
    def test_constante_bloquea_pca_no_baseline(self):
        raw=mensual(120);raw[1240]=4.
        model,out=t.entrenar_icc(matrix(raw));self.assertIsNone(model['parametros_pca'])
        self.assertEqual(model['metodo_elegido'],'baseline_s1')
        self.assertTrue(out['icc_indice'].notna().any());s.validar_modelo(model)
    def test_numpy_reproduce_sklearn(self):
        p=self.model['parametros_pca'];q=self.model['referencias']
        block=self.frame.loc[b.asignar_splits_icc(self.frame).eq('train')&b.mascara_core(self.frame)]
        Z=(t.transformar(block,q)-p['media_y_train'])/p['std_y_train']
        from sklearn.decomposition import PCA
        original=PCA(1,svd_solver='full',whiten=False).fit(Z)
        sign=1 if original.components_[0,1]>=0 else -1
        np.testing.assert_allclose(t.proyectar(Z,p),original.transform(Z).ravel()*sign,atol=1e-12)
    def test_9_sensibilidades_6_perturbaciones(self):
        self.assertEqual(len(self.model['gates']['sensibilidad_baseline']['variantes']),9)
        cases=self.model['gates']['perturbaciones_pca']['casos'];self.assertEqual(len(cases),6)
        self.assertEqual({x['multiplicador'] for x in cases},{.9,1.1})
    def test_correlacion_indefinida_no_pasa(self):
        self.assertIsNone(t.rho([1]*10,np.arange(10)))
        self.assertFalse(t.comparar([1]*10,[1]*10)['pasa'])
    def test_modelo_alterado_rechazado(self):
        alt=copy.deepcopy(self.model);alt['pca_aceptado']=not alt['pca_aceptado']
        with self.assertRaisesRegex(ValueError,'Integridad'):s.validar_modelo(alt)
    def test_score_sin_fit(self):
        with patch('sklearn.decomposition.PCA.fit',side_effect=AssertionError('fit prohibido')):
            out=s.generar_indice(self.frame,self.model)
        self.assertTrue(out['icc_indice'].notna().any())
    def test_score_train_val_identico(self):
        out=s.generar_indice(self.frame,self.model);mask=self.scores['utilizable_baseline']
        np.testing.assert_array_equal(out.loc[mask,'icc_indice'],self.scores.loc[mask,'icc_indice'])
    def test_revision_historica_flag(self):
        raw=mensual(120);raw.loc[pd.Period('2021-01','M'),'stock_constante_dic2016']*=1.1
        self.assertFalse(s.generar_indice(matrix(raw),self.model)['historia_train_coincide'].any())
    def test_bundle_idempotente_conflicto_y_corrupcion(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model';t.exportar_entrenamiento(self.model,self.scores,path)
            first=(path/'modelo_icc.json').read_bytes();t.exportar_entrenamiento(self.model,self.scores,path)
            self.assertEqual(first,(path/'modelo_icc.json').read_bytes());s.cargar_modelo(path/'modelo_icc.json')
            alt=copy.deepcopy(self.model);alt['estado_producto']='cambio'
            with self.assertRaises(FileExistsError):t.exportar_entrenamiento(alt,self.scores,path)
            (path/'icc_entrenamiento.csv').write_text('incompleto')
            with self.assertRaisesRegex(ValueError,'alterado'):s.cargar_modelo(path/'modelo_icc.json')

class IntegracionReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame,cls.source=b.cargar_entrada(ROOT);cls.model,cls.trained=t.entrenar_icc(cls.frame,cls.source)
    def test_fuentes_y_cobertura(self):
        self.assertTrue(self.source['fuentes_reconstruidas']);self.assertEqual(len(self.source['identidades_internas_csv']),7)
        self.assertEqual(self.model['gates']['cobertura']['n_train'],60)
        self.assertEqual(self.model['gates']['cobertura']['n_validacion'],22)
    def test_rechazo_real_visible(self):
        self.assertFalse(self.model['pca_aceptado']);self.assertEqual(self.model['motivos_rechazo_pca'],['reconstruccion'])
        self.assertTrue(self.model['gates']['sensibilidad_baseline']['pasa'])
    def test_promedio_no_basta(self):
        m=self.model['gates']['reconstruccion']['metricas']['validacion']
        self.assertGreater(m['mejora_relativa'],.10);self.assertGreater(m['ratios_por_columna'][0],1.25)
        self.assertGreater(m['ratios_por_columna'][2],1.25);self.assertFalse(m['pasa'])
    def test_no_muta_y_scorea_112(self):
        before=self.frame.copy(deep=True);out=s.generar_indice(self.frame,self.model)
        pd.testing.assert_frame_equal(before,self.frame);self.assertEqual(int(out['icc_indice'].notna().sum()),112)
        self.assertEqual(len(out),321);self.assertFalse(out['disponibilidad_historica_verificada'].any())

if __name__=='__main__':unittest.main()
