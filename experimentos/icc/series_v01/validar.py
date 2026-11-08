"""Pruebas metodológicas: calendario, precisión, fuga temporal y atribuciones."""
from pathlib import Path
import argparse,json,sys,unittest
import numpy as np
import pandas as pd
from ejecutar import ROOT,crecimiento,GRID,hash_file
from modelos import fit,score,components,economic

OUTPUT=ROOT/'resultados'

class Validaciones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=OUTPUT
        cls.registry=pd.read_csv(cls.out/'registro_decisiones.csv',dtype={'serie':str})
    def frame(self,sid):
        return pd.read_csv(self.out/'features'/f'{sid}.csv',parse_dates=['fecha_mes']).set_index('fecha_mes')
    def test_calendario_y_ceros(self):
        for sid in self.registry.serie:
            f=self.frame(sid);self.assertTrue(f.index.equals(GRID))
        g=crecimiento(pd.Series([1.,0.,1.,np.nan,2.,3.]),1)
        self.assertEqual(g.iloc[1],-100)
        self.assertTrue(pd.isna(g.iloc[2]))
        self.assertTrue(pd.isna(g.iloc[4]))
        self.assertEqual(g.iloc[5],50)
    def test_precision_se_conserva(self):
        a=pd.read_csv(self.out/'auditoria_api_xls.csv',dtype={'serie':str})
        s=a.loc[a.serie.eq('929')&a.api_cero_xls_positivo]
        self.assertGreater(len(s),0)
        self.assertTrue(s.xls_miles_original.gt(0).all())
        self.assertTrue(s.stock_nominal_millones_ars.lt(.501).all())
        np.testing.assert_allclose(a.xls_miles_original/1000,a.stock_nominal_millones_ars)
    def test_fx_y_atribucion_economica(self):
        for sid in ['938','946','947','971','979','980']:
            f=self.frame(sid).loc['2016-12-31':]
            np.testing.assert_allclose(f.R*f.tc_a3500,f.stock_nominal_millones_ars,rtol=1e-10,atol=1e-7)
            np.testing.assert_allclose(f.delta_ars,f.delta_ars_por_volumen+f.delta_ars_por_tc+f.delta_ars_interaccion,rtol=1e-9,atol=1e-6)
            dates=pd.to_datetime(f.fecha_tc)
            self.assertTrue((dates<=f.index).all());self.assertTrue((dates.dt.to_period('M')==f.index.to_period('M')).all())
            self.assertTrue(f.antiguedad_cierre_dias.le(7).all())
    def test_referencias_no_usan_futuro(self):
        for sid in self.registry.loc[self.registry.estado.eq('ICC_experimental'),'serie']:
            f=self.frame(sid);a=fit(f);mut=f.copy();m=~mut.split.eq('train')
            mut.loc[m,'R']*=100;mut.loc[m,'tasa_pct']+=150;mut.loc[m,'g3_pct']-=80
            self.assertEqual(a,fit(mut))
            self.assertEqual(a['n_train'],60)
            self.assertLessEqual(max(a['fechas_train']),'2022-02-28')
    def test_minimo_no_se_relaja(self):
        f=self.frame('971')
        self.assertEqual(int((f.split.eq('train')&f.core_completo).sum()),59)
        with self.assertRaises(ValueError):fit(f)
        self.assertFalse((self.out/'indices/icc_971.csv').exists())
    def test_reserva_y_huecos_sin_score(self):
        f=self.frame('960');ref=fit(f)
        future=f.iloc[[-1]].copy();future.index=pd.DatetimeIndex(['2026-07-31'],name='fecha_mes');future['split']='reserva'
        f=pd.concat([f,future]);f.loc['2023-06-30','tasa_pct']=np.nan
        sc=score(f,ref,.5)
        self.assertTrue(pd.isna(sc.loc['2026-07-31','icc_candidato']))
        self.assertTrue(pd.isna(sc.loc['2023-06-30','icc_candidato']))
        self.assertTrue(pd.isna(sc.loc['2023-07-31','delta_icc']))
    def test_rango_y_contribuciones(self):
        for p in sorted((self.out/'indices').glob('*.csv')):
            f=pd.read_csv(p);values=f.icc_experimental.dropna()
            self.assertEqual(len(values),112);self.assertTrue(values.between(0,100).all())
            np.testing.assert_allclose(f.aporte_nivel_costo+f.aporte_nivel_momentum,f.icc_experimental,atol=1e-8,equal_nan=True)
            np.testing.assert_allclose(f.aporte_delta_volumen+f.aporte_delta_costo+f.aporte_delta_momentum,f.delta_icc,atol=1e-8,equal_nan=True)
    def test_economia_y_pesos_seleccionados(self):
        checks=pd.read_csv(self.out/'sensibilidades.csv',dtype={'serie':str})
        for _,d in self.registry.loc[self.registry.estado.eq('ICC_experimental')].iterrows():
            c=checks.loc[checks.serie.eq(d.serie)&checks.alpha.eq(d.alpha)]
            self.assertEqual(c.variante.nunique(),9);self.assertEqual(len(c),18);self.assertTrue(c.pasa.all())
            ref=fit(self.frame(d.serie));self.assertTrue(all(economic(ref,d.alpha).values()))
            for alpha in [.5,.6,.7,.8]:
                if alpha<d.alpha:self.assertFalse(checks.loc[checks.serie.eq(d.serie)&checks.alpha.eq(alpha),'pasa'].all())
    def test_ecc_solo_observado_y_universos(self):
        e=pd.read_csv(self.out/'ecc_familias_normalizada.csv')
        self.assertFalse(e.duplicated(['trimestre','familia','dimension']).any());self.assertTrue(e.id_ecc.abs().le(100).all())
        self.assertEqual(set(e.dimension),{'estandares','demanda','spread','montos','plazo'})
        old=pd.read_csv(ROOT/'fuentes/ecc_empresas_normalizada.csv')
        new=pd.read_csv(self.out/'ecc_empresas_normalizada_ampliada.csv')
        matched=new.merge(old,on=['trimestre','poblacion','dimension'],suffixes=('_new','_old'))
        np.testing.assert_allclose(matched.id_ecc_new,matched.id_ecc_old,atol=1e-12)
        m=pd.read_csv(self.out/'contraste_ecc.csv',dtype={'serie':str})
        self.assertTrue(m.n.eq(37).all())
    def test_global_y_fallos_sin_promocion(self):
        g=json.loads((self.out/'decision_global.json').read_text());self.assertFalse(g['formula_aprobada'])
        for sid in ['968','969','finserprom_tarjetas_ml_privado']:
            row=self.registry.set_index('serie').loc[sid]
            self.assertEqual(row.estado,'indicador_parcial')
            p=pd.read_csv(self.out/'parciales'/f'ivd_{sid}.csv')
            self.assertTrue(p.ivd_parcial.dropna().between(0,100).all());self.assertFalse(p.es_icc.any())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();OUTPUT=args.output
    unittest.main(argv=[sys.argv[0]],verbosity=2)
