import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import evaluar_hipotecarios as e

class Validaciones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames,cls.audit=e.leer_fuentes(e.ROOT)
        e.b.asignar_splits_icc=e.splits

    def test_escala_y_revisiones(self):
        bad=self.audit.loc[~self.audit.coincide_redondeo]
        self.assertEqual(len(bad),4)
        self.assertEqual(set(bad.fecha.dt.strftime('%Y-%m')),{'2026-05','2026-06'})

    def test_referencias_no_usan_futuro(self):
        for f in self.frames.values():
            refs=e.b.ajustar_referencias_icc(f)
            alt=f.copy();future=alt.fecha_mes.gt('2022-02-28')
            alt.loc[future,e.b.STOCK_REAL]*=10;alt.loc[future,e.b.TASA]+=70
            self.assertEqual(refs,e.b.ajustar_referencias_icc(alt))
            self.assertEqual(refs['n_train'],60)

    def test_calendario_no_comprime_huecos(self):
        f=self.frames[935]
        with self.assertRaises(ValueError):e.splits(f.drop(index=60))

    def test_nulos_no_se_imputan(self):
        f=self.frames[935].copy();refs=e.b.ajustar_referencias_icc(f)
        idx=f.index[f.fecha_mes.eq('2023-01-31')][0];f.loc[idx,e.b.TASA]=np.nan
        out=e.b.aplicar_baseline_icc(f,refs)
        self.assertTrue(pd.isna(out.loc[idx,'icc_baseline_s1']))

    def test_reserva_sin_score(self):
        for f in self.frames.values():
            out=e.b.aplicar_baseline_icc(f,e.b.ajustar_referencias_icc(f))
            self.assertTrue(out.loc[out.fecha_mes.ge('2026-07-01'),'icc_baseline_s1'].isna().all())

    def test_dominio_economico(self):
        for f in self.frames.values():
            self.assertTrue(e.b.controles_economicos(e.b.ajustar_referencias_icc(f))['pasa'])

    def test_salidas_no_etiquetan_uva(self):
        for f in self.frames.values():
            out=e.salida_publica(f)
            self.assertFalse(any('uva' in c for c in out.columns))
            self.assertIn('tasa_hipotecaria_nominal_pct',out)

    def test_atribucion_reconcilia(self):
        for sid in self.frames:
            f=pd.read_csv(e.ROOT/'resultados'/str(sid)/'icc_candidato.csv')
            np.testing.assert_allclose(f.aporte_costo+f.aporte_momentum,f.icc_candidato_s1,atol=1e-12)
            np.testing.assert_allclose(f.aporte_delta_volumen+f.aporte_delta_costo+f.aporte_delta_momentum,f.delta_icc,atol=1e-12)

if __name__=='__main__':unittest.main()
