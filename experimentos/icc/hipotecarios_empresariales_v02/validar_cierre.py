import json,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from cierre_icc import ROOT,extraer_ecc,candidatos,pares_trimestrales

class Cierre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ecc=extraer_ecc(ROOT);cls.f=candidatos(ROOT,[.5,.6,.7,.8]);cls.p=pares_trimestrales(cls.ecc,cls.f)

    def test_ecc_no_expectativas(self):
        self.assertEqual(set(self.ecc.hoja),{'1','4','6'})
        self.assertTrue(self.ecc.tipo.eq('observado_ponderado').all())

    def test_37_trimestres_contiguos(self):
        for _,f in self.p.groupby(['serie_id','peso_costo','dimension']):
            self.assertEqual(f.trimestre.tolist(),pd.period_range('2017Q2','2026Q2',freq='Q').astype(str).tolist())

    def test_pesos_aplicados(self):
        for sid,alpha in [(935,.6),(936,.8)]:
            f=pd.read_csv(ROOT/'resultados'/f'icc_{sid}_v02.csv')
            self.assertTrue(f.peso_costo.eq(alpha).all())
            self.assertTrue(f.adoptado_descriptivo_interno.all())
            self.assertFalse(f.uso_operativo_habilitado.any())

    def test_referencias_sin_refit(self):
        for sid in [935,936]:
            a=json.loads((ROOT/'insumos'/f'referencias_{sid}.json').read_text())
            b=json.loads((ROOT/'resultados'/f'modelo_{sid}_v02.json').read_text())
            self.assertEqual(a,b['referencias'])
            self.assertEqual(a['n_train'],60)

    def test_no_pymes_preserva_valores_80_20(self):
        a=pd.read_csv(ROOT/'insumos/icc_80_20_936.csv');b=pd.read_csv(ROOT/'resultados/icc_936_v02.csv')
        np.testing.assert_allclose(a.icc_candidato_s1,b.icc_indice,atol=1e-10,equal_nan=True)

    def test_pymes_cambio_efectivo(self):
        a=pd.read_csv(ROOT/'insumos/icc_80_20_935.csv');b=pd.read_csv(ROOT/'resultados/icc_935_v02.csv')
        self.assertGreater((a.icc_candidato_s1-b.icc_indice).abs().max(),1)

    def test_reserva_y_nulos(self):
        for sid in [935,936]:
            a=pd.read_csv(ROOT/'insumos'/f'icc_80_20_{sid}.csv');b=pd.read_csv(ROOT/'resultados'/f'icc_{sid}_v02.csv')
            self.assertTrue(b.loc[b.fecha_mes.ge('2026-07-01'),'icc_indice'].isna().all())
            self.assertTrue(a.icc_candidato_s1.isna().equals(b.icc_indice.isna()))

    def test_aportes_y_rango(self):
        for sid in [935,936]:
            f=pd.read_csv(ROOT/'resultados'/f'icc_{sid}_v02.csv')
            self.assertTrue(f.icc_indice.dropna().between(0,100).all())
            np.testing.assert_allclose(f.aporte_costo+f.aporte_momentum,f.icc_indice,atol=1e-10,equal_nan=True)
            np.testing.assert_allclose(f.aporte_delta_volumen+f.aporte_delta_costo+f.aporte_delta_momentum,f.delta_icc,atol=1e-10,equal_nan=True)

if __name__=='__main__':unittest.main()
