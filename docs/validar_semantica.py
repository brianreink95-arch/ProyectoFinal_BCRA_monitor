"""Pruebas de casos límite de la semántica descriptiva. python validar_semantica.py"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import numpy as np
import pandas as pd
from lib.eda import build_c, transitions_c

class SemanticaC(unittest.TestCase):
    def setUp(self):
        self.master=pd.DataFrame({'cuit_normalizado':['A','B','C'],
                                  'razon_social':['A','B','C']})
        self.long=pd.DataFrame([
            ['A',202401,'Banco 1',1,100], ['A',202401,'Banco 2',0,0],
            ['A',202403,'Banco 1',3,120],  # febrero ausente: no saltar el gap
            ['B',202401,'Banco 1',0,0],
            ['B',202402,'Banco 1',1,200],  # entrada de exposición, no deterioro
            ['B',202403,'Banco 1',2,100],
            ['B',202403,'Banco 2',np.nan,100], # 50% con situación desconocida
        ], columns=['cuit_normalizado','periodo','entidad','situacion','monto_miles_pesos'])
        _,_,self.panel=build_c(self.long,self.master)

    def getrow(self,cuit,month):
        return self.panel[self.panel.cuit_normalizado.eq(cuit)&self.panel.fecha.eq(pd.Timestamp(month))].iloc[0]

    def test_cero_es_observado_pero_no_riesgo(self):
        r=self.getrow('B','2024-01-01')
        self.assertEqual(r.n_entidades_reportadas,1)
        self.assertEqual(r.n_entidades_con_saldo_positivo,0)
        self.assertEqual(r.deuda_total_positiva,0)
        self.assertTrue(pd.isna(r.situacion_max_activa))
        self.assertTrue(pd.isna(r.hhi_deuda_positiva))

    def test_mes_ausente_no_se_convierte_en_cero(self):
        r=self.getrow('A','2024-02-01')
        self.assertFalse(r.mes_observado)
        self.assertTrue(pd.isna(r.deuda_total_positiva))
        self.assertTrue(pd.isna(r.empresa_con_deuda_activa))
        self.assertEqual(r.estado_eda,'SIN_OBSERVACION')
        self.assertEqual(len(self.panel[self.panel.cuit_normalizado.eq('C')]),3)

    def test_desconocida_conserva_exposicion(self):
        r=self.getrow('B','2024-03-01')
        self.assertEqual(r.deuda_total_positiva,200)
        self.assertEqual(r.pct_deuda_situacion_desconocida,50)
        self.assertEqual(r.pct_deuda_situacion_2,50)
        self.assertTrue(pd.isna(r.situacion_max_activa))
        self.assertAlmostEqual(r.hhi_deuda_positiva,.5)

    def test_transiciones_no_saltan_gaps_ni_clasifican_entrada_como_deterioro(self):
        pairs,risk,_,_=transitions_c(self.panel)
        self.assertFalse(pairs.cuit_normalizado.eq('A').any())
        self.assertEqual(len(pairs),2)
        self.assertEqual(len(risk),0)

    def test_entidad_cero_no_influye_concentracion(self):
        r=self.getrow('A','2024-01-01')
        self.assertEqual(r.n_entidades_reportadas,2)
        self.assertEqual(r.n_entidades_con_saldo_positivo,1)
        self.assertEqual(r.hhi_deuda_positiva,1)

    def test_duplica_clave_es_error(self):
        duplicate=pd.concat([self.long,self.long.iloc[[0]]],ignore_index=True)
        with self.assertRaises(ValueError):build_c(duplicate,self.master)

if __name__=='__main__':unittest.main(verbosity=2)
