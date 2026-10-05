"""Features retrospectivas ICC; solo tablas A de la última consolidación ABC."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.common import read_csv, require_unique, write_csv
from lib.relacional import validar_tablas

VERSION_ICC = '1.0'
SEGMENTO_ICC = 'Hipotecarios ML a personas humanas'
DESGLOSE_ICC = (1145, 1146, 1147, 1148, 1149)
SERIES_ICC = (927, *DESGLOSE_ICC, 1240)
FEATURES_ICC = (
    'credito_var_nominal_1m_pct',
    'credito_var_nominal_3m_pct',
    'tasa_uva_tna_pct',
    'tasa_uva_delta_3m_pp',
    'participacion_construccion_pct',
    'credito_volatilidad_6m_pp',
)
# Cinco componentes y total redondeados a enteros: error máximo 6 * 0,5.
TOLERANCIA_DESGLOSE = 3.0


# 1. Lectura y procedencia

def leer_icc(root=ROOT):
    root = Path(root).resolve()
    analytics = root / 'data_analytics'
    pointer = json.loads((analytics / 'latest.json').read_text(encoding='utf-8'))
    run_id = pointer['run_id']
    if not isinstance(run_id, str) or Path(run_id).name != run_id:
        raise ValueError('Identificador de consolidación inválido.')
    run = (analytics / pointer['path']).resolve()
    if run != (analytics / 'runs' / run_id).resolve():
        raise ValueError('El puntero no identifica una carpeta runs/run_id.')
    metadata = json.loads((run / 'run_metadata.json').read_text(encoding='utf-8'))
    if (set(pointer['bases']) != {'a', 'b', 'c'}
            or set(metadata['bases']) != {'a', 'b', 'c'}
            or metadata['status'] != 'completed'
            or metadata['run_id'] != run_id
            or metadata.get('inputs_unchanged') is not True):
        raise ValueError('Se requiere una consolidación ABC completa e íntegra.')
    schema_path = root / 'config' / 'esquema_tablas.json'
    schema_hash = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    if schema_hash != metadata['schema_sha256']:
        raise ValueError('El contrato cambió desde la consolidación; reconsolidar offline.')
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    output_hashes = {item['path']: item['sha256'] for item in metadata['outputs']}
    tables, hashes = {}, {}
    for name, spec in schema['bases']['a'].items():
        path = run / 'base_a' / f'{name}.csv'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != output_hashes.get(f'base_a/{name}.csv'):
            raise ValueError(f'La tabla A {name} no coincide con la consolidación.')
        hashes[name] = digest
        types = {'integer': 'Int64', 'number': 'Float64', 'boolean': 'boolean'}
        tables[name] = read_csv(path, dtype={col: types.get(rule['type'], 'string')
                                          for col, rule in spec['columns'].items()})
    validar_tablas(tables, schema['bases']['a'])
    validar_insumos_icc(tables['series'], tables['observaciones'])
    provenance = {
        'run_origen': run_id,
        'consolidacion_utc': metadata['created_at_utc'],
        'version_features': VERSION_ICC,
        'series_sha256': hashes['series'],
        'observaciones_sha256': hashes['observaciones'],
        'contrato_sha256': schema_hash,
        'catalogo_origen_sha256': metadata['catalog_sha256'],
        'codigo_features_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ultima_referencia_a': tables['observaciones']['fecha'].max(),
        'disponibilidad_historica_verificada': False,
    }
    return tables, provenance


# 2. Validación semántica

def validar_insumos_icc(series, observaciones):
    selected = series.set_index('serie_id').reindex(SERIES_ICC)
    if selected['descripcion'].isna().any():
        raise ValueError('Faltan series requeridas por ICC.')
    if not (selected['frecuencia'].eq('M').all()
            and selected['agregacion_mensual'].eq('observacion_mensual').all()
            and selected['moneda'].eq('ML').all()):
        raise ValueError('Cambió la frecuencia, agregación o moneda de las series ICC.')
    stocks = selected.loc[[927, *DESGLOSE_ICC]]
    if not (stocks['unidad'].eq('En miles de ARS').all()
            and stocks['tipo_valor'].eq('stock_nominal').all()
            and stocks['segmento'].eq('Personas humanas').all()):
        raise ValueError('Stocks ICC incompatibles con la definición económica.')
    concepts = {927: 'hipotecarios_ml_personas_humanas',
                1145: 'hipotecarios_ml_ph_construccion',
                1146: 'hipotecarios_ml_ph_refaccion',
                1147: 'hipotecarios_ml_ph_compra_nuevas',
                1148: 'hipotecarios_ml_ph_compra_usadas',
                1149: 'hipotecarios_ml_ph_otras', 1240: 'tasa_hipotecarios_uva'}
    for sid, concept in concepts.items():
        if selected.loc[sid, 'concepto'] != concept:
            raise ValueError(f'La serie {sid} cambió de concepto.')
    if (selected.loc[1240, 'unidad'] != 'En porcentaje nominal anual'
            or selected.loc[1240, 'tipo_valor'] != 'tasa_sobre_UVA'):
        raise ValueError('La tasa ICC debe ser TNA sobre UVA, no costo total.')
    dates = pd.to_datetime(observaciones['fecha'], format='%Y-%m-%d', errors='raise')
    exception = (observaciones['serie_id'].eq(1199) & dates.lt('1993-06-01')
                 & observaciones['valor_original'].eq(0))
    if not observaciones['excepcion_precobertura'].eq(exception).all():
        raise ValueError('La excepción 1199 no coincide con la regla documentada.')
    if (not observaciones.loc[exception, 'valor_analitico'].isna().all()
            or not observaciones.loc[~exception, 'valor_analitico'].eq(
                observaciones.loc[~exception, 'valor_original']).fillna(False).all()):
        raise ValueError('Se alteraron valores analíticos fuera de la excepción 1199.')
    if not set(SERIES_ICC).issubset(set(observaciones['serie_id'])):
        raise ValueError('Faltan observaciones de las series ICC.')
    published_stocks = observaciones.loc[observaciones['serie_id'].isin([927, *DESGLOSE_ICC]),
                                        'valor_original']
    if not published_stocks.mod(1).eq(0).all():
        raise ValueError('Cambió la precisión de stocks ICC; revisar tolerancia de reconciliación.')


# 3. Agregación temporal: estas siete series ya son mensuales

def agregar_mensual_icc(series, observaciones):
    validar_insumos_icc(series, observaciones)
    selected = observaciones.loc[observaciones['serie_id'].isin(SERIES_ICC)].copy()
    selected['fecha'] = pd.to_datetime(selected['fecha'], errors='raise')
    selected['mes'] = selected['fecha'].dt.to_period('M')
    require_unique(selected, ['serie_id', 'mes'], 'ICC mensual')
    if not selected['fecha'].dt.is_month_end.all():
        raise ValueError('ICC: una serie mensual tiene referencia distinta del cierre.')
    wide = selected.pivot(index='mes', columns='serie_id', values='valor_analitico')
    grid = pd.period_range(selected['mes'].min(), selected['mes'].max(), freq='M')
    return wide.reindex(index=grid, columns=SERIES_ICC).astype(float)


# 4. Cálculo, ventanas de calendario y elegibilidad

def variacion_nominal(stock, meses):
    count = stock.rolling(meses + 1, min_periods=1).count()
    denominator = stock.shift(meses)
    valid = count.eq(meses + 1) & denominator.gt(0)
    value = (100 * (stock / denominator.where(denominator.gt(0)) - 1)).where(valid)
    reason = pd.Series('', index=stock.index, dtype='string')
    reason.loc[~valid] = 'ventana_stock_incompleta'
    reason.loc[count.eq(meses + 1) & ~denominator.gt(0)] = 'denominador_stock_no_positivo'
    reason.loc[stock.isna()] = 'stock_actual_ausente_o_invalido'
    return value, reason


def calcular_features_icc(mensual):
    expected = pd.period_range(mensual.index.min(), mensual.index.max(), freq='M')
    if not mensual.index.equals(expected) or not mensual.columns.is_unique:
        raise ValueError('ICC requiere grilla mensual continua, ordenada y columnas únicas.')
    if set(mensual.columns) != set(SERIES_ICC):
        raise ValueError('Series de la grilla ICC incorrectas.')
    if np.isinf(mensual.to_numpy(dtype=float)).any():
        raise ValueError('Infinito en insumos ICC.')
    frame = pd.DataFrame(index=mensual.index)
    stock = mensual[927].where(mensual[927].ge(0))
    rate = mensual[1240].where(mensual[1240].ge(0))
    parts = mensual[list(DESGLOSE_ICC)]
    complete = parts.notna().all(axis=1) & parts.ge(0).all(axis=1)
    # Suma solo de reconciliación; no crea un stock ni mezcla ML con ME.
    difference = (parts.sum(axis=1, min_count=len(DESGLOSE_ICC)) - stock).abs()
    consistent = (complete & stock.notna() & difference.le(TOLERANCIA_DESGLOSE)
                  & parts.le(stock, axis=0).all(axis=1))
    frame['stock_observado'] = mensual[927].notna()
    frame['tasa_observada'] = mensual[1240].notna()
    frame['desglose_completo'] = complete
    frame['composicion_consistente'] = consistent
    frame['n_meses_stock_4m'] = stock.rolling(4, min_periods=1).count().astype(int)
    frame['n_meses_tasa_4m'] = rate.rolling(4, min_periods=1).count().astype(int)
    for lag in (1, 3):
        name = f'credito_var_nominal_{lag}m_pct'
        frame[name], frame[f'motivo_{name}'] = variacion_nominal(stock, lag)
    frame['tasa_uva_tna_pct'] = rate
    frame['motivo_tasa_uva_tna_pct'] = np.where(rate.notna(), '', 'tasa_ausente_o_invalida')
    valid_delta = frame['n_meses_tasa_4m'].eq(4)
    frame['tasa_uva_delta_3m_pp'] = (rate - rate.shift(3)).where(valid_delta)
    frame['motivo_tasa_uva_delta_3m_pp'] = np.where(valid_delta, '', 'ventana_tasa_incompleta')
    valid_share = consistent & stock.gt(0)
    frame['participacion_construccion_pct'] = (100 * mensual[1145] / stock.where(stock.gt(0))).where(valid_share)
    reason = pd.Series('', index=frame.index, dtype='string')
    reason.loc[~valid_share] = 'desglose_no_reconciliado'
    reason.loc[~complete] = 'desglose_ausente_o_invalido'
    reason.loc[stock.eq(0)] = 'denominador_stock_no_positivo'
    reason.loc[stock.isna()] = 'stock_actual_ausente_o_invalido'
    frame['motivo_participacion_construccion_pct'] = reason
    growth = frame['credito_var_nominal_1m_pct']
    frame['n_variaciones_6m'] = growth.rolling(6, min_periods=1).count().astype(int)
    frame['credito_volatilidad_6m_pp'] = growth.rolling(6, min_periods=6).std(ddof=0)
    frame['motivo_credito_volatilidad_6m_pp'] = np.where(
        frame['n_variaciones_6m'].eq(6), '', 'ventana_variaciones_incompleta')
    frame['n_features_disponibles'] = frame[list(FEATURES_ICC)].notna().sum(axis=1)
    frame['elegible_icc'] = frame['n_features_disponibles'].eq(len(FEATURES_ICC))
    frame['motivos_no_elegible'] = frame.apply(
        lambda row: ';'.join(f'{name}:{row[f"motivo_{name}"]}' for name in FEATURES_ICC
                             if pd.isna(row[name])), axis=1)
    frame.insert(0, 'segmento', SEGMENTO_ICC)
    frame.insert(0, 'fecha_mes', frame.index.to_timestamp('M').strftime('%Y-%m-%d'))
    frame.insert(2, 'cutoff_referencia', frame['fecha_mes'])
    return frame.reset_index(drop=True)


def construir_icc(root=ROOT):
    tables, provenance = leer_icc(root)
    monthly = agregar_mensual_icc(tables['series'], tables['observaciones'])
    frame = calcular_features_icc(monthly)
    for name, value in provenance.items():
        frame[name] = value
    validar_matriz_icc(frame)
    return frame


# 5. Validación de matriz y exportación única atómica

def validar_matriz_icc(frame):
    if frame.empty:
        raise ValueError('Matriz ICC vacía.')
    if frame[['fecha_mes', 'segmento']].isna().any().any():
        raise ValueError('Clave primaria ICC nula.')
    require_unique(frame, ['fecha_mes', 'segmento'], 'Matriz ICC')
    dates = pd.to_datetime(frame['fecha_mes'], format='%Y-%m-%d', errors='raise')
    periods = pd.PeriodIndex(dates, freq='M')
    if (not periods.equals(pd.period_range(periods.min(), periods.max(), freq='M'))
            or not dates.dt.is_month_end.all()):
        raise ValueError('Matriz ICC desordenada o con huecos de calendario.')
    if not frame['segmento'].eq(SEGMENTO_ICC).all():
        raise ValueError('Segmento ICC no definido.')
    if not frame['cutoff_referencia'].eq(frame['fecha_mes']).all():
        raise ValueError('Cutoff distinto del período de la fila.')
    if 'ultima_referencia_a' in frame and dates.gt(pd.to_datetime(frame['ultima_referencia_a'])).any():
        raise ValueError('ICC contiene un mes posterior a la última referencia A.')
    numeric = frame.select_dtypes(include='number').to_numpy(dtype=float)
    if np.isinf(numeric).any():
        raise ValueError('Matriz ICC contiene infinitos.')
    available = frame[list(FEATURES_ICC)].notna().sum(axis=1)
    if (not available.eq(frame['n_features_disponibles']).all()
            or not frame['elegible_icc'].eq(available.eq(len(FEATURES_ICC))).all()):
        raise ValueError('Elegibilidad ICC inconsistente.')
    for name in FEATURES_ICC:
        if not frame[name].isna().eq(frame[f'motivo_{name}'].ne('')).all():
            raise ValueError(f'Motivo de ausencia inconsistente: {name}')
    if not frame['elegible_icc'].eq(frame['motivos_no_elegible'].eq('')).all():
        raise ValueError('Faltan motivos de exclusión ICC.')
    share = frame['participacion_construccion_pct'].dropna()
    if not share.between(0, 100).all():
        raise ValueError('Participación ICC fuera de 0–100.')


def exportar_icc(frame, root=ROOT):
    validar_matriz_icc(frame)
    if frame['run_origen'].nunique() != 1:
        raise ValueError('No mezclar consolidaciones en una matriz ICC.')
    path = Path(root) / 'data_analytics' / 'features' / frame['run_origen'].iloc[0] / 'icc.csv'
    write_csv(frame, path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Raíz del proyecto; no utiliza la red.')
    args = parser.parse_args()
    frame = construir_icc(args.root)
    output = exportar_icc(frame, args.root)
    valid = frame.loc[frame['elegible_icc'], 'fecha_mes']
    print(f'ICC: {len(frame)} filas; {len(valid)} elegibles; {len(frame) - len(valid)} no elegibles.')
    if not valid.empty:
        print(f'Períodos elegibles: {valid.min()} a {valid.max()} (revisar banderas por fila).')
    print(f'Origen: {frame["run_origen"].iloc[0]}')
    print(f'Salida: {output}')


if __name__ == '__main__':
    main()
