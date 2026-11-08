"""Pruebas del evaluador ICC. Sin red, selección o calibración."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ml import features as f
from ml import evaluate_features as e


def mensual(n=112):
    grid=pd.period_range('2016-12',periods=n,freq='M'); k=np.arange(n,dtype=float)
    frame=pd.DataFrame(index=grid); real=100+2*k+3*np.sin(k/3)
    frame[927]=real*10
    for sid,share in zip(f.DESGLOSE_ICC,(.4,.15,.15,.15,.15)):frame[sid]=frame[927]*share
    frame[1240]=4+.02*k+np.cos(k/6)
    frame['stock_constante_dic2016']=real; frame['estado_ajuste_ipc_stock']='ajustado'
    return frame


def matriz(raw=None):
    frame=f.calcular_features_icc(mensual() if raw is None else raw)
    for name in ('deflactor_sha256','observaciones_sha256','series_sha256','contrato_sha256','codigo_features_sha256'):frame[name]='0'*64
    for name,value in {'version_features':'3.0','version_contrato':'2.0','run_origen':'prueba_2026','medida_credito':'precios_constantes_dic2016','unidad_stock_constante':'millones_ARS_dic2016'}.items():frame[name]=value
    return frame


class Estadisticas(unittest.TestCase):
    def test_pearson_conocido(self):
        x=pd.Series([1,2,3,4]); r=e.correlacion(x,2*x+3,minimo=3)
        self.assertEqual(r['n'],4);self.assertAlmostEqual(r['valor'],1)
    def test_spearman_empates(self):
        r=e.correlacion(pd.Series([1,1,2,3]),pd.Series([2,2,4,9]),'spearman',3)
        self.assertAlmostEqual(r['valor'],1)
    def test_sin_imputacion_pares(self):
        r=e.correlacion(pd.Series([1,np.nan,3,4]),pd.Series([2,4,np.nan,8]),minimo=3)
        self.assertEqual(r,{'n':2,'valor':None,'motivo':'pocos_meses'})
    def test_constante_indefinida(self):
        self.assertEqual(e.correlacion(pd.Series([1]*4),pd.Series(range(4)),minimo=3)['motivo'],'variable_constante')
    def test_autocorrelacion_no_salta_hueco(self):
        frame=pd.DataFrame({'fecha_mes':pd.period_range('2020-01',periods=24,freq='M').to_timestamp('M').strftime('%Y-%m-%d'),'x':np.arange(24,dtype=float)})
        frame.loc[5,'x']=np.nan; r=e.resumen_variable(frame,'x')
        self.assertEqual(r['autocorrelacion_1m']['n'],21);self.assertEqual(r['n'],23)
    def test_extremos_no_modifican_valores(self):
        frame=pd.DataFrame({'fecha_mes':pd.period_range('2020-01',periods=24,freq='M').to_timestamp('M').strftime('%Y-%m-%d'),'x':[1]*23+[100]})
        before=frame.copy();r=e.resumen_variable(frame,'x')
        self.assertEqual(r['n_extremos_iqr'],1);pd.testing.assert_frame_equal(frame,before)
    def test_validacion_referencia_train(self):
        stats={'x':{'n':3,'min':1,'max':3,'mediana':2,'iqr':1}}
        r=e.contraste_validacion(stats,pd.DataFrame({'x':[0,2,4,np.nan]}),'x')
        self.assertEqual(r['n'],3);self.assertEqual(r['fuera_rango_train_n'],2)
        self.assertAlmostEqual(r['fuera_rango_train_pct'],200/3);self.assertEqual(r['cambio_mediana_en_iqr_train'],0)
    def test_iqr_cero_sin_infinito(self):
        r=e.contraste_validacion({'x':{'n':3,'min':2,'max':2,'mediana':2,'iqr':0}},pd.DataFrame({'x':[1,3]}),'x')
        self.assertIsNone(r['cambio_mediana_en_iqr_train']);self.assertEqual(r['motivo'],'iqr_train_cero')
    def test_validacion_vacia(self):
        r=e.contraste_validacion({'x':{'n':0}},pd.DataFrame({'x':[np.nan]}),'x')
        self.assertIsNone(r['fuera_rango_train_pct'])


class Protocolo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.frame=matriz();cls.result=e.evaluar(cls.frame)
    def test_minimo_por_conjunto(self):
        p=self.result['conjuntos_propuestos']
        self.assertEqual(p['nucleo_volumen_dinamica_costo']['meses_por_split']['train'],60)
        self.assertEqual(p['sensibilidad_aceleracion']['meses_por_split']['train'],57)
        self.assertEqual(p['todas_candidatas']['meses_por_split']['train'],51)
        self.assertTrue(p['nucleo_volumen_dinamica_costo']['cumple_minimo_train'])
        self.assertFalse(p['todas_candidatas']['cumple_minimo_train'])
    def test_sin_seleccion_automatica(self):
        self.assertEqual(len(self.result['train']['estadisticas']),14);self.assertEqual(len(self.result['train']['pares']),91)
        self.assertFalse(self.result['seleccion_automatica']);self.assertFalse(self.result['modelo_entrenado'])
        self.assertTrue(all(not p['seleccion_aprobada'] for p in self.result['conjuntos_propuestos'].values()))
    def test_train_invariante_ante_futuro(self):
        raw=mensual();cut=raw.index>pd.Period('2022-02','M')
        raw.loc[cut,list(f.SERIES_ICC)]*=3;raw.loc[cut,'stock_constante_dic2016']*=3
        r=e.evaluar(matriz(raw))
        self.assertEqual(self.result['train'],r['train']);self.assertEqual(self.result['conjuntos_propuestos'],r['conjuntos_propuestos'])
        self.assertNotEqual(self.result['validacion'],r['validacion'])
    def test_retrospectiva_excluida_del_analisis(self):
        raw=mensual();cut=raw.index>=pd.Period('2024-01','M')
        raw.loc[cut,list(f.SERIES_ICC)]*=2;raw.loc[cut,'stock_constante_dic2016']*=2
        r=e.evaluar(matriz(raw))
        for key in ('train','validacion','trayectorias_train_validacion'):self.assertEqual(self.result[key],r[key])
        self.assertTrue(all(p['fecha']<='2023-12-31' for rows in r['trayectorias_train_validacion'].values() for p in rows))
    def test_cortes_mitades_compartidos(self):
        self.assertEqual(self.result['train']['fin_primera_mitad'],'2019-07-31')
        pair=self.result['train']['pares_muestra_comun_14'][0]
        self.assertEqual(pair['primera_mitad_spearman']['n'],20);self.assertEqual(pair['segunda_mitad_spearman']['n'],31)
    def test_identidad_erronea_rechazada(self):
        bad=self.frame.copy();bad.loc[20,e.G3]+=1
        with self.assertRaisesRegex(ValueError,'Identidad'):e.evaluar(bad)
    def test_minimo_pares_invalido(self):
        with self.assertRaises(ValueError):e.evaluar(self.frame,2)
    def test_sin_train_falla(self):
        frame=self.frame.loc[self.frame.fecha_mes.ge('2024-01-01')].reset_index(drop=True)
        with self.assertRaisesRegex(ValueError,'entrenamiento'):e.evaluar(frame)
    def test_identidades_comprobadas(self):
        self.assertEqual(len(self.result['identidades_internas_csv']),7)
        self.assertTrue(all(x['coincide'] for x in self.result['identidades_internas_csv'].values()))


class LecturaPersistencia(unittest.TestCase):
    def setUp(self):
        self.frame=matriz();self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.input=self.root/'icc.csv';self.frame.to_csv(self.input,index=False)
    def tearDown(self):self.temp.cleanup()
    def test_modo_csv_honesto(self):
        r=e.construir_evaluacion(input_path=self.input)
        self.assertFalse(r['procedencia']['fuentes_reconstruidas']);self.assertEqual(r['procedencia']['modo_lectura'],'csv_independiente')
    def test_exportacion_repetible_y_fuente_intacta(self):
        before=self.input.read_bytes();r=e.construir_evaluacion(input_path=self.input)
        paths=e.exportar_evaluacion(r,output_dir=self.root/'salida');first=[p.read_bytes() for p in paths]
        e.exportar_evaluacion(r,output_dir=self.root/'salida')
        self.assertEqual(first,[p.read_bytes() for p in paths]);self.assertEqual(before,self.input.read_bytes())
        stored=json.loads(paths[1].read_text());self.assertEqual(stored['informe_html_sha256'],hashlib.sha256(paths[0].read_bytes()).hexdigest())
    def test_flags_invalidos(self):
        self.frame['elegible_baseline_historico']=self.frame['elegible_baseline_historico'].astype(object)
        self.frame.loc[0,'elegible_baseline_historico']='sí';self.frame.to_csv(self.input,index=False)
        with self.assertRaisesRegex(ValueError,'booleano'):e.cargar_csv(self.input)
    def test_procedencia_mezclada(self):
        self.frame.loc[0,'run_origen']='otro';self.frame.to_csv(self.input,index=False)
        with self.assertRaisesRegex(ValueError,'mezclada'):e.cargar_csv(self.input)
    def test_unidad_incorrecta(self):
        self.frame['unidad_stock_constante']='miles_ARS';self.frame.to_csv(self.input,index=False)
        with self.assertRaisesRegex(ValueError,'unidad'):e.cargar_csv(self.input)
    def test_columnas_duplicadas(self):
        header,rest=self.input.read_text().split('\n',1);self.input.write_text(header+','+header.split(',')[0]+'\n'+rest)
        with self.assertRaisesRegex(ValueError,'duplicadas'):e.cargar_csv(self.input)
    def test_csv_no_finito(self):
        self.frame.loc[20,e.G1]=np.inf;self.frame.to_csv(self.input,index=False)
        with self.assertRaisesRegex(ValueError,'infinitos'):e.cargar_csv(self.input)
    def test_texto_escapado_en_html(self):
        r=e.construir_evaluacion(input_path=self.input);r['procedencia']['modo_lectura']='<script>alert(1)</script>'
        rendered=e.render_informe(r);self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
    def test_grafico_interrumpe_huecos(self):
        points=[{'fecha':'2020-01-31','valor':1,'bloque':'train'},{'fecha':'2020-02-29','valor':None,'bloque':'train'},{'fecha':'2020-03-31','valor':3,'bloque':'train'}]
        self.assertEqual(e.grafico_svg(points,'Ejemplo','%').count('<polyline'),2)


if __name__=='__main__':unittest.main()
