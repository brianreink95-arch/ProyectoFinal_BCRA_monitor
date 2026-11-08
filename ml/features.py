"""Candidatas ICC retrospectivas: volumen real, dinámica, costo y composición.

Solo lee tablas A/IPC de una consolidación ABC íntegra. No estima accesibilidad
directa, no calibra referencias y no selecciona automáticamente predictores.
"""
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
from lib.precios import validar_ipc, validar_referencias_ipc

VERSION_ICC = '3.0'
SEGMENTO_ICC = 'Hipotecarios ML a personas humanas'
DESGLOSE_ICC = (1145, 1146, 1147, 1148, 1149)
SERIES_ICC = (927, *DESGLOSE_ICC, 1240)
FEATURES_ICC_2_0 = (
    'credito_var_real_1m_pct',
    'credito_var_real_3m_pct',
    'tasa_uva_tna_pct',
    'tasa_uva_delta_3m_pp',
    'participacion_construccion_pct',
    'credito_volatilidad_real_6m_pp',
)
STOCK_REAL = 'credito_stock_real_millones_ars_dic2016'
DELTA_STOCK_REAL = 'credito_delta_real_3m_millones_ars_dic2016'
ACELERACION_REAL = 'credito_aceleracion_real_3m_pp'
PARTICIPACIONES_ICC = {
    1145: 'participacion_construccion_pct',
    1146: 'participacion_refaccion_pct',
    1147: 'participacion_compra_nuevas_pct',
    1148: 'participacion_compra_usadas_pct',
    1149: 'participacion_otras_pct',
}
# Registro de candidatas calculadas, no selección definitiva de un modelo.
FEATURES_ICC = (*FEATURES_ICC_2_0, STOCK_REAL, 'credito_var_real_12m_pct',
                DELTA_STOCK_REAL, ACELERACION_REAL,
                *tuple(PARTICIPACIONES_ICC.values())[1:])
PREDICTORES_BASELINE_HISTORICO = (
    'credito_var_real_1m_pct', 'credito_var_real_3m_pct',
    'tasa_uva_tna_pct', 'tasa_uva_delta_3m_pp',
)
PERFILES_ICC = {
    'comparacion_2_0': FEATURES_ICC_2_0,
    'baseline_historico': PREDICTORES_BASELINE_HISTORICO,
}
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
    if schema['version'] != '2.0' or metadata['schema_version'] != '2.0':
        raise ValueError('ICC real requiere contrato 2.0; no reutilizar corridas nominales.')
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
    validar_insumos_icc(tables['series'], tables['observaciones'], tables['deflactor_ipc'])
    provenance = {
        'run_origen': run_id,
        'consolidacion_utc': metadata['created_at_utc'],
        'version_features': VERSION_ICC,
        'medida_credito': 'precios_constantes_dic2016',
        'unidad_stock_constante': 'millones_ARS_dic2016',
        'version_contrato': schema['version'],
        'deflactor_sha256': hashes['deflactor_ipc'],
        'ipc_version_fuente': tables['deflactor_ipc']['version_fuente'].iloc[0],
        'ipc_desde': tables['deflactor_ipc']['fecha_mes'].min(),
        'ipc_hasta': tables['deflactor_ipc']['fecha_mes'].max(),
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

def validar_insumos_icc(series, observaciones, ipc):
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
            and stocks['segmento'].eq('Personas humanas').all()
            and stocks['unidad_validada'].eq('millones_ARS').all()
            and stocks['validacion_escala'].eq('contraste_oficial_por_mes').all()
            and stocks['ajuste_ipc'].eq(True).all()
            and stocks['consumidor_ajuste'].eq('ICC').all()):
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
    ipc = validar_ipc(ipc)
    validar_referencias_ipc({'observaciones': observaciones}, ipc)
    stock_rows = observaciones.loc[observaciones['serie_id'].isin([927, *DESGLOSE_ICC])]
    adjusted = stock_rows['estado_ajuste_ipc'].eq('ajustado')
    if not stock_rows['valor_constante_dic2016'].notna().eq(adjusted).all():
        raise ValueError('ICC: valor constante incompatible con estado_ajuste_ipc.')
    adjusted_rows = stock_rows.loc[adjusted]
    if not adjusted_rows['ipc_fecha_mes'].eq(adjusted_rows['fecha']).all():
        raise ValueError('ICC: el IPC no corresponde al mes del stock.')
    factors = adjusted_rows['fecha'].map(ipc.set_index('fecha_mes')['factor_deflacion'])
    expected = adjusted_rows['valor_analitico'].astype(float) * factors.astype(float)
    if not np.allclose(adjusted_rows['valor_constante_dic2016'].astype(float), expected,
                       rtol=1e-12, atol=1e-10):
        raise ValueError('ICC: fórmula de valores constantes incompatible con IPC.')
    rates = observaciones.loc[observaciones['serie_id'].eq(1240)]
    if (rates['valor_constante_dic2016'].notna().any()
            or not rates['estado_ajuste_ipc'].eq('no_aplica').all()):
        raise ValueError('ICC: la tasa UVA no debe deflactarse.')


# 3. Agregación temporal: constantes para crecimiento, nominales para composición

def agregar_mensual_icc(series, observaciones, ipc):
    validar_insumos_icc(series, observaciones, ipc)
    selected = observaciones.loc[observaciones['serie_id'].isin(SERIES_ICC)].copy()
    selected['fecha'] = pd.to_datetime(selected['fecha'], errors='raise')
    selected['mes'] = selected['fecha'].dt.to_period('M')
    require_unique(selected, ['serie_id', 'mes'], 'ICC mensual')
    if not selected['fecha'].dt.is_month_end.all():
        raise ValueError('ICC: una serie mensual tiene referencia distinta del cierre.')
    grid = pd.period_range(selected['mes'].min(), selected['mes'].max(), freq='M')
    wide = selected.pivot(index='mes', columns='serie_id', values='valor_analitico')
    wide = wide.reindex(index=grid, columns=SERIES_ICC).astype(float)
    stock = selected.loc[selected['serie_id'].eq(927)].set_index('mes').reindex(grid)
    wide['stock_constante_dic2016'] = stock['valor_constante_dic2016'].astype(float)
    wide['estado_ajuste_ipc_stock'] = stock['estado_ajuste_ipc'].astype('string').fillna('sin_observacion')
    return wide


# 4. Cálculo, ventanas de calendario y elegibilidad

def variacion_real(stock, meses):
    count = stock.rolling(meses + 1, min_periods=1).count()
    denominator = stock.shift(meses)
    valid = count.eq(meses + 1) & denominator.gt(0)
    value = (100 * (stock / denominator.where(denominator.gt(0)) - 1)).where(valid)
    reason = pd.Series('', index=stock.index, dtype='string')
    reason.loc[~valid] = 'ventana_stock_incompleta'
    reason.loc[count.eq(meses + 1) & ~denominator.gt(0)] = 'denominador_stock_no_positivo'
    reason.loc[stock.isna()] = 'stock_actual_ausente_o_invalido'
    return value, reason


def elegibilidad_features(frame, requeridas):
    """Disponibilidad según consumidor; jamás exige todas las candidatas.

    La selección debe ser explícita. Devuelve máscara y motivos sin recortar
    el calendario ni sustituir nulos. No define splits ni suficiencia de train.
    """
    requeridas = tuple(requeridas)
    if not requeridas or len(set(requeridas)) != len(requeridas):
        raise ValueError('Lista de features requerida vacía o duplicada.')
    if not set(requeridas).issubset(FEATURES_ICC):
        raise ValueError('Feature requerida fuera del registro de candidatas ICC.')
    mask = frame[list(requeridas)].notna().all(axis=1)
    reason = pd.Series('', index=frame.index, dtype='string')
    for name in requeridas:
        missing = frame[name].isna()
        separator = reason.loc[missing].ne('').map({True: ';', False: ''})
        reason.loc[missing] = (reason.loc[missing] + separator + name + ':'
                               + frame.loc[missing, f'motivo_{name}'].astype('string'))
    return mask, reason


def calcular_features_icc(mensual):
    expected = pd.period_range(mensual.index.min(), mensual.index.max(), freq='M')
    if not mensual.index.equals(expected) or not mensual.columns.is_unique:
        raise ValueError('ICC requiere grilla mensual continua, ordenada y columnas únicas.')
    if set(mensual.columns) != {*SERIES_ICC, 'stock_constante_dic2016', 'estado_ajuste_ipc_stock'}:
        raise ValueError('Series de la grilla ICC incorrectas.')
    if np.isinf(mensual.select_dtypes(include='number').to_numpy(dtype=float)).any():
        raise ValueError('Infinito en insumos ICC.')
    frame = pd.DataFrame(index=mensual.index)
    stock = mensual[927].where(mensual[927].ge(0))
    state = mensual['estado_ajuste_ipc_stock']
    # La presencia del nominal no habilita un constante pendiente de IPC/unidades.
    constant = mensual['stock_constante_dic2016'].where(
        state.eq('ajustado') & mensual['stock_constante_dic2016'].ge(0) & stock.notna())
    rate = mensual[1240].where(mensual[1240].ge(0))
    parts = mensual[list(DESGLOSE_ICC)]
    complete = parts.notna().all(axis=1) & parts.ge(0).all(axis=1)
    # Suma solo de reconciliación; no crea un stock ni mezcla ML con ME.
    difference = (parts.sum(axis=1, min_count=len(DESGLOSE_ICC)) - stock).abs()
    consistent = (complete & stock.notna() & difference.le(TOLERANCIA_DESGLOSE)
                  & parts.le(stock, axis=0).all(axis=1))
    frame['stock_observado'] = mensual[927].notna()
    frame['stock_constante_utilizable'] = constant.notna()
    frame['estado_ajuste_ipc_stock'] = state
    frame['tasa_observada'] = mensual[1240].notna()
    frame['desglose_completo'] = complete
    frame['composicion_consistente'] = consistent
    frame['n_meses_stock_real_4m'] = constant.rolling(4, min_periods=1).count().astype(int)
    frame['n_meses_stock_real_7m'] = constant.rolling(7, min_periods=1).count().astype(int)
    frame['n_meses_stock_real_13m'] = constant.rolling(13, min_periods=1).count().astype(int)
    frame['n_meses_tasa_4m'] = rate.rolling(4, min_periods=1).count().astype(int)
    frame[STOCK_REAL] = constant
    frame[f'motivo_{STOCK_REAL}'] = np.where(
        constant.notna(), '', 'stock_actual_ausente_o_invalido')
    for lag in (1, 3, 12):
        name = f'credito_var_real_{lag}m_pct'
        frame[name], frame[f'motivo_{name}'] = variacion_real(constant, lag)
    valid_absolute = frame['n_meses_stock_real_4m'].eq(4)
    frame[DELTA_STOCK_REAL] = (constant - constant.shift(3)).where(valid_absolute)
    frame[f'motivo_{DELTA_STOCK_REAL}'] = np.where(
        valid_absolute, '', 'ventana_stock_incompleta')
    # Dos trimestres adyacentes: denominadores t-3 y t-6, siete stocks válidos.
    quarterly = frame['credito_var_real_3m_pct']
    full_acceleration = frame['n_meses_stock_real_7m'].eq(7)
    valid_acceleration = full_acceleration & quarterly.notna() & quarterly.shift(3).notna()
    frame[ACELERACION_REAL] = (quarterly - quarterly.shift(3)).where(valid_acceleration)
    reason_acceleration = pd.Series('', index=frame.index, dtype='string')
    reason_acceleration.loc[~full_acceleration] = 'ventana_stock_incompleta'
    reason_acceleration.loc[full_acceleration & ~valid_acceleration] = 'denominador_stock_no_positivo'
    frame[f'motivo_{ACELERACION_REAL}'] = reason_acceleration
    monetary = (STOCK_REAL, DELTA_STOCK_REAL, ACELERACION_REAL,
                'credito_var_real_1m_pct', 'credito_var_real_3m_pct', 'credito_var_real_12m_pct')
    for name in monetary:
        unavailable = constant.isna()
        frame.loc[unavailable, f'motivo_{name}'] = 'stock_actual_ausente_o_invalido'
        not_adjusted = unavailable & state.ne('ajustado')
        frame.loc[not_adjusted, f'motivo_{name}'] = (
            'stock_constante_no_utilizable:' + state.loc[not_adjusted])
    frame['tasa_uva_tna_pct'] = rate
    frame['motivo_tasa_uva_tna_pct'] = np.where(rate.notna(), '', 'tasa_ausente_o_invalida')
    valid_delta = frame['n_meses_tasa_4m'].eq(4)
    frame['tasa_uva_delta_3m_pp'] = (rate - rate.shift(3)).where(valid_delta)
    frame['motivo_tasa_uva_delta_3m_pp'] = np.where(valid_delta, '', 'ventana_tasa_incompleta')
    valid_share = consistent & stock.gt(0)
    reason = pd.Series('', index=frame.index, dtype='string')
    reason.loc[~valid_share] = 'desglose_no_reconciliado'
    reason.loc[~complete] = 'desglose_ausente_o_invalido'
    reason.loc[stock.eq(0)] = 'denominador_stock_no_positivo'
    reason.loc[stock.isna()] = 'stock_actual_ausente_o_invalido'
    for sid, name in PARTICIPACIONES_ICC.items():
        frame[name] = (100 * mensual[sid] / stock.where(stock.gt(0))).where(valid_share)
        frame[f'motivo_{name}'] = reason.copy()
    growth = frame['credito_var_real_1m_pct']
    frame['n_variaciones_reales_6m'] = growth.rolling(6, min_periods=1).count().astype(int)
    frame['credito_volatilidad_real_6m_pp'] = growth.rolling(6, min_periods=6).std(ddof=0)
    frame['motivo_credito_volatilidad_real_6m_pp'] = np.where(
        frame['n_variaciones_reales_6m'].eq(6), '', 'ventana_variaciones_incompleta')
    frame['n_features_disponibles'] = frame[list(FEATURES_ICC)].notna().sum(axis=1)
    frame['candidatas_completas'], frame['motivos_features_no_disponibles'] = (
        elegibilidad_features(frame, FEATURES_ICC))
    for profile, required in PERFILES_ICC.items():
        frame[f'elegible_{profile}'], frame[f'motivos_no_elegible_{profile}'] = (
            elegibilidad_features(frame, required))
    frame['n_features_disponibles_2_0'] = frame[list(FEATURES_ICC_2_0)].notna().sum(axis=1)
    # Alias de compatibilidad 2.0: no es elegibilidad del nuevo índice.
    frame['elegible_icc'] = frame['elegible_comparacion_2_0']
    frame['motivos_no_elegible'] = frame['motivos_no_elegible_comparacion_2_0']
    frame.insert(0, 'segmento', SEGMENTO_ICC)
    frame.insert(0, 'fecha_mes', frame.index.to_timestamp('M').strftime('%Y-%m-%d'))
    frame.insert(2, 'cutoff_referencia', frame['fecha_mes'])
    return frame.reset_index(drop=True)


def construir_icc(root=ROOT):
    tables, provenance = leer_icc(root)
    monthly = agregar_mensual_icc(tables['series'], tables['observaciones'], tables['deflactor_ipc'])
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
    if not set(FEATURES_ICC).issubset(frame.columns):
        raise ValueError('ICC 3.0 requiere las 14 candidatas reales y de composición.')
    if 'version_features' in frame and not frame['version_features'].eq(VERSION_ICC).all():
        raise ValueError('Versión de features ICC incompatible.')
    if 'medida_credito' in frame and not frame['medida_credito'].eq('precios_constantes_dic2016').all():
        raise ValueError('Medida del crédito incompatible con features reales.')
    available = frame[list(FEATURES_ICC)].notna().sum(axis=1)
    if not available.eq(frame['n_features_disponibles']).all():
        raise ValueError('Disponibilidad de candidatas ICC inconsistente.')
    for name in FEATURES_ICC:
        if not frame[name].isna().eq(frame[f'motivo_{name}'].ne('')).all():
            raise ValueError(f'Motivo de ausencia inconsistente: {name}')
    for profile, required in {'candidatas': FEATURES_ICC, **PERFILES_ICC}.items():
        mask, reason = elegibilidad_features(frame, required)
        flag = 'candidatas_completas' if profile == 'candidatas' else f'elegible_{profile}'
        motive = ('motivos_features_no_disponibles' if profile == 'candidatas'
                  else f'motivos_no_elegible_{profile}')
        if not frame[flag].eq(mask).all() or not frame[motive].eq(reason).all():
            raise ValueError(f'Elegibilidad/motivos ICC inconsistentes: {profile}')
    if (not frame['elegible_icc'].eq(frame['elegible_comparacion_2_0']).all()
            or not frame['motivos_no_elegible'].eq(frame['motivos_no_elegible_comparacion_2_0']).all()
            or not frame['n_features_disponibles_2_0'].eq(
                frame[list(FEATURES_ICC_2_0)].notna().sum(axis=1)).all()):
        raise ValueError('Alias de comparación ICC 2.0 inconsistente.')
    for name in PARTICIPACIONES_ICC.values():
        if not frame[name].dropna().between(0, 100).all():
            raise ValueError(f'Participación ICC fuera de 0–100: {name}')
    if not frame[STOCK_REAL].dropna().ge(0).all():
        raise ValueError('Nivel de stock real negativo.')


def ruta_matriz_icc(root, run_id):
    """Nueva versión en carpeta propia; conserva las matrices 1.0/2.0."""
    return Path(root) / 'data_analytics' / 'features' / run_id / f'v{VERSION_ICC}' / 'icc.csv'


def exportar_icc(frame, root=ROOT):
    validar_matriz_icc(frame)
    if frame['run_origen'].nunique() != 1:
        raise ValueError('No mezclar consolidaciones en una matriz ICC.')
    path = ruta_matriz_icc(root, frame['run_origen'].iloc[0])
    if path.exists():
        old = read_csv(path, usecols=['version_features'], dtype='string')
        if not old['version_features'].eq(VERSION_ICC).all():
            raise ValueError('No sobrescribir una matriz de otra versión de features.')
    write_csv(frame, path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Raíz del proyecto; no utiliza la red.')
    args = parser.parse_args()
    frame = construir_icc(args.root)
    output = exportar_icc(frame, args.root)
    print(f'ICC {VERSION_ICC}: {len(frame)} filas; {len(FEATURES_ICC)} candidatas, sin selección de modelo.')
    for profile in PERFILES_ICC:
        valid = frame.loc[frame[f'elegible_{profile}'], 'fecha_mes']
        print(f'{profile}: {len(valid)} meses; '
              f'{valid.min() if len(valid) else "sin cobertura"} a '
              f'{valid.max() if len(valid) else "sin cobertura"}.')
    print(f'Todas las candidatas disponibles: {int(frame["candidatas_completas"].sum())} meses; '
          'no es un requisito global de entrenamiento.')
    print(f'Origen: {frame["run_origen"].iloc[0]}')
    print(f'Salida: {output}')


if __name__ == '__main__':
    main()
