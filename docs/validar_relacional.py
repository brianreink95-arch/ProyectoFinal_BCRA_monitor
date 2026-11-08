"""Verificar las tablas de la última corrida y casos de rechazo del contrato."""
from pathlib import Path
import json
import sys
import unittest
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.relacional import validar_tablas, id_estable, booleanos
from lib.common import get_pipeline


class Relacional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / 'config/esquema_tablas.json').read_text())['bases']
        latest = json.loads((ROOT / 'data_analytics/latest.json').read_text())
        cls.dataset_dir = ROOT / 'data_analytics' / latest['path']
        cls.tables = {}
        for base, contract in cls.schema.items():
            path = cls.dataset_dir / f'base_{base}'
            assert {p.stem for p in path.glob('*.csv')} == set(contract)
            cls.tables[base] = {name: pd.read_csv(path / f'{name}.csv',
                dtype={col:'string' for col,spec in rule['columns'].items() if spec['type']=='text'},
                low_memory=False, encoding='utf-8-sig') for name,rule in contract.items()}

    def test_contrato_completo(self):
        for base in self.schema:
            validar_tablas(self.tables[base], self.schema[base])
        self.assertEqual(sum(len(x) for x in self.tables.values()), 13)

    def test_pk_duplicada_se_rechaza(self):
        tables = self.tables['a'].copy()
        df = tables['observaciones']
        tables['observaciones'] = pd.concat([df, df.iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, 'primaria'):
            validar_tablas(tables, self.schema['a'])

    def test_fk_huerfana_se_rechaza(self):
        tables = self.tables['c'].copy()
        df = tables['deuda_entidad_mes'].copy()
        df.loc[0, 'acreedor_id'] = 'acreedor_ajeno'
        tables['deuda_entidad_mes'] = df
        with self.assertRaisesRegex(ValueError, 'huérfana'):
            validar_tablas(tables, self.schema['c'])

    def test_tipo_temporal_invalido_se_rechaza(self):
        tables = self.tables['a'].copy()
        df = tables['observaciones'].copy()
        df.loc[0, 'fecha'] = 'fecha inválida'
        tables['observaciones'] = df
        with self.assertRaisesRegex(ValueError, 'fecha'):
            validar_tablas(tables, self.schema['a'])

    def test_booleano_desconocido_no_es_false(self):
        self.assertEqual(booleanos(pd.Series(['SI','NO',None])).tolist()[:2], [True,False])
        with self.assertRaises(ValueError):
            booleanos(pd.Series(['no informado']))

    def test_identidad_de_oferta_reproducible(self):
        b = self.tables['b']['ofertas']
        expected = [id_estable('oferta',sid,family,row) for sid,family,row in
                    b[['snapshot_id','familia','fila_fuente']].itertuples(index=False,name=None)]
        self.assertEqual(expected, b.observacion_id.tolist())
        self.assertTrue(b.observacion_id.is_unique)
        # No confundir la clave provisional de producto con la identidad de observación.
        self.assertGreater(len(b), b.clave_variante_provisional.nunique())

    def test_ofertas_conservadas(self):
        old, inventory, _ = get_pipeline('b').load_b(ROOT)
        exported = self.tables['b']['ofertas']
        joined = exported.merge(old[['snapshot_id','family','fila_fuente','tea','cftea']],
            left_on=['snapshot_id','familia','fila_fuente'],right_on=['snapshot_id','family','fila_fuente'],
            suffixes=('_csv','_fuente'),validate='one_to_one')
        self.assertEqual(len(joined), len(old))
        self.assertEqual(len(exported), len(old))
        for metric in ['tea','cftea']:
            np.testing.assert_allclose(joined[metric+'_csv'],joined[metric+'_fuente'],equal_nan=True)
        counts = self.tables['b']['snapshots'].set_index('snapshot_id').completo
        self.assertTrue(counts.loc[exported.snapshot_id].eq(True).all())

    def test_panel_reconcilia_y_conserva_huecos(self):
        tables = self.tables['c']
        debt = tables['deuda_entidad_mes']
        panel = tables['empresa_mes']
        positive = debt[debt.monto_miles_pesos.gt(0)].groupby(['cuit_normalizado','fecha']).monto_miles_pesos.sum()
        lookup = panel.set_index(['cuit_normalizado','fecha']).deuda_total_positiva
        np.testing.assert_allclose(positive,lookup.reindex(positive.index))
        self.assertEqual(set(panel.cuit_normalizado),set(tables['empresas'].cuit_normalizado))
        self.assertTrue(panel.loc[~panel.mes_observado,'deuda_total_positiva'].isna().all())
        zero = panel.deuda_total_positiva.eq(0)
        self.assertTrue(panel.loc[zero,'situacion_max_activa'].isna().all())
        self.assertTrue(panel.loc[zero,'hhi_deuda_positiva'].isna().all())


if __name__ == '__main__':
    unittest.main(verbosity=2)
