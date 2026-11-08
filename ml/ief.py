"""Matriz retrospectiva IEF 0.2: tratamiento de seis predictores, sin modelo.

Ejecutar desde cualquier directorio: python ml/ief.py [--output-dir DESTINO].
La deuda real está expresada en miles de ARS de diciembre de 2016.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.common import read_csv, require_unique, runtime_metadata, write_csv
from lib.precios import validar_ipc, validar_referencias_ipc
from lib.relacional import booleanos, validar_tablas

VERSION = '0.2'
KEY = ['cuit_normalizado', 'fecha']
REAL = 'deuda_total_positiva_constante_dic2016'
NOMINAL = 'deuda_total_positiva'
COUNT = 'n_entidades_con_saldo_positivo'
FEATURES = (
    'deuda_var_real_3m_pct',
    'acreedores_delta_3m',
    'hhi_deuda_positiva',
    'situacion_max_activa',
    'pct_deuda_situacion_2_mas',
    'pct_deuda_situacion_2_mas_delta_3m_pp',
)
LOG_RATIO = 'deuda_log_ratio_real_3m'
FEATURES_MODELO = (LOG_RATIO, *FEATURES[1:])
SPLITS = {
    'train': ('2024-08-01', '2025-07-01'),
    'validacion': ('2025-08-01', '2026-01-01'),
    'evaluacion': ('2026-02-01', '2026-07-01'),
}
DICCIONARIO = {
    FEATURES[0]: {'unidad': 'porcentaje', 'formula': '100 * (R_t / R_t-3 - 1)',
                  'condicion': '4 meses observados y ajustados; R_t-3 > 0'},
    FEATURES[1]: {'unidad': 'cantidad', 'formula': 'N_t - N_t-3',
                  'condicion': '4 meses observados; extremos conocidos'},
    FEATURES[2]: {'unidad': 'indice_0_1', 'formula': 'HHI de saldos positivos en t'},
    FEATURES[3]: {'unidad': 'categoria_ordinal', 'formula': 'maxima situacion activa conocida en t'},
    FEATURES[4]: {'unidad': 'porcentaje', 'formula': 'pct_situacion_2_t + pct_situacion_3_mas_t'},
    FEATURES[5]: {'unidad': 'puntos_porcentuales', 'formula': 'pct_2_mas_t - pct_2_mas_t-3',
                  'condicion': '4 meses observados; composicion conocida en ambos extremos'},
}
DICCIONARIO[LOG_RATIO] = {
    'unidad': 'log_ratio_adimensional', 'formula': 'ln(R_t) - ln(R_t-3)',
    'condicion': 'misma ventana valida que crecimiento; ambos extremos positivos',
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def leer_insumos(root=ROOT):
    """Verificar contrato, siete tablas C y deflactor contra la corrida vigente."""
    root = Path(root).resolve()
    analytics = root / 'data_analytics'
    pointer = json.loads((analytics / 'latest.json').read_text(encoding='utf-8'))
    run_id = pointer['run_id']
    if not isinstance(run_id, str) or run_id in ('.', '..') or Path(run_id).name != run_id:
        raise ValueError('IEF: identificador de corrida invalido.')
    run = (analytics / pointer['path']).resolve()
    if run != (analytics / 'runs' / run_id).resolve() or not run.is_relative_to(analytics):
        raise ValueError('IEF: puntero fuera de runs/run_id.')
    metadata = json.loads((run / 'run_metadata.json').read_text(encoding='utf-8'))
    if (set(pointer['bases']) != {'a', 'b', 'c'}
            or set(metadata['bases']) != {'a', 'b', 'c'}
            or metadata['run_id'] != run_id or metadata['status'] != 'completed'
            or metadata.get('inputs_unchanged') is not True):
        raise ValueError('IEF: se requiere consolidacion ABC completa e integra.')
    schema_path = root / 'config/esquema_tablas.json'
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    if (sha256(schema_path) != metadata['schema_sha256']
            or schema['version'] != '2.0' or metadata['schema_version'] != '2.0'):
        raise ValueError('IEF: contrato incompatible; reconsolidar offline.')
    expected = {item['path']: item['sha256'] for item in metadata['outputs']}
    hashes, tables = {}, {}
    types = {'integer': 'Int64', 'number': 'Float64', 'boolean': 'boolean'}
    specs = {f'base_c/{name}.csv': (name, spec) for name, spec in schema['bases']['c'].items()}
    specs['base_a/deflactor_ipc.csv'] = ('deflactor_ipc', schema['bases']['a']['deflactor_ipc'])
    for relative, (name, spec) in specs.items():
        path = run / relative
        hashes[relative] = sha256(path)
        if hashes[relative] != expected.get(relative):
            raise ValueError(f'IEF: tabla alterada: {relative}')
        tables[name] = read_csv(path, dtype={col: types.get(rule['type'], 'string')
                                             for col, rule in spec['columns'].items()})
    ipc = validar_ipc(tables.pop('deflactor_ipc'))
    validar_tablas(tables, schema['bases']['c'])
    adjusted_tables = {k: tables[k] for k in ('empresa_mes', 'deuda_entidad_mes')}
    validar_referencias_ipc(adjusted_tables, ipc)
    # Evita reutilizar una columna nominal renombrada como real, o un IPC de otro mes.
    for name, frame in adjusted_tables.items():
        pairs = ({NOMINAL: REAL} if name == 'empresa_mes' else
                 {'monto_miles_pesos': 'monto_miles_pesos_dic2016'})
        adjusted = frame.estado_ajuste_ipc.eq('ajustado')
        month_end = pd.to_datetime(frame.fecha).dt.to_period('M').dt.to_timestamp('M').dt.strftime('%Y-%m-%d')
        if not frame.loc[adjusted, 'ipc_fecha_mes'].eq(month_end[adjusted]).all():
            raise ValueError(f'IEF: mes IPC incorrecto en {name}.')
        factor = frame.ipc_fecha_mes.map(ipc.set_index('fecha_mes').factor_deflacion)
        for nominal, real in pairs.items():
            if not frame[real].notna().eq(adjusted).all():
                raise ValueError(f'IEF: estado IPC incoherente en {name}.')
            if not np.allclose(frame.loc[adjusted, real].astype(float),
                               (frame[nominal] * factor)[adjusted].astype(float),
                               rtol=1e-12, atol=1e-10):
                raise ValueError(f'IEF: deuda real no reconcilia con IPC en {name}.')
    audit = auditar_detalle_c(tables['empresa_mes'], tables['deuda_entidad_mes'])
    provenance = {
        'run_origen': run_id, 'consolidacion_utc': metadata['created_at_utc'],
        'contrato_version': schema['version'], 'contrato_sha256': sha256(schema_path),
        'insumos_sha256': hashes, 'ipc_version_fuente': ipc.version_fuente.iloc[0],
        'codigo_sha256': sha256(__file__),
        'dependencias_codigo_sha256': {name: sha256(root / name) for name in
                                      ('lib/common.py', 'lib/relacional.py', 'lib/precios.py')},
        'auditoria_detalle_c': audit,
    }
    return tables, provenance


def auditar_detalle_c(panel, debt):
    """Reconciliar predictores actuales con saldos positivos por acreedor."""
    positive = debt.loc[debt.monto_miles_pesos.gt(0)].copy()
    groups = positive.groupby(KEY, sort=True)
    nominal = groups.monto_miles_pesos.sum()
    real = groups.monto_miles_pesos_dic2016.sum(min_count=1)
    count = groups.acreedor_id.nunique()
    shares = positive.monto_miles_pesos / groups.monto_miles_pesos.transform('sum')
    hhi = shares.pow(2).groupby([positive[c] for c in KEY]).sum()
    known = positive.situacion.isin([1, 2, 3, 4, 5, 6])
    all_known = known.groupby([positive[c] for c in KEY]).all()
    situation = groups.situacion.max().where(all_known)
    bad_amount = positive.monto_miles_pesos.where(positive.situacion.isin([2, 3, 4, 5, 6]), 0)
    bad = 100 * bad_amount.groupby([positive[c] for c in KEY]).sum() / nominal
    source = panel.set_index(KEY)
    observed = source.mes_observado.fillna(False)
    active = source.empresa_con_deuda_activa.fillna(False) & observed
    checks = {
        NOMINAL: nominal.reindex(source.index).where(active, 0).where(observed),
        REAL: real.reindex(source.index).where(active, 0).where(observed & source.estado_ajuste_ipc.eq('ajustado')),
        COUNT: count.reindex(source.index).where(active, 0).where(observed),
        FEATURES[2]: hhi.reindex(source.index),
        FEATURES[3]: situation.reindex(source.index),
        FEATURES[4]: bad.reindex(source.index),
    }
    for col, expected in checks.items():
        actual = (source.pct_deuda_situacion_2 + source.pct_deuda_situacion_3_mas
                  if col == FEATURES[4] else source[col])
        if not np.allclose(actual.to_numpy(dtype=float, na_value=np.nan),
                           expected.to_numpy(dtype=float, na_value=np.nan),
                           rtol=1e-10, atol=1e-8, equal_nan=True):
            raise ValueError(f'IEF: agregado no reconcilia con detalle C: {col}')
    return {'empresa_mes': len(panel), 'deuda_entidad_mes': len(debt),
            'deuda_positiva_entidad_mes': len(positive),
            'columnas_reconciliadas': list(checks), 'resultado': 'coinciden',
            'alcance': 'consistencia con detalle capturado; no certifica continuidad economica'}


def construir_matriz(panel, empresas):
    """Puro y sin fit: conserva universo, explicita huecos y usa solo [t-3, t]."""
    panel, empresas = panel.copy(), empresas.copy()
    if panel.empty or empresas.empty:
        raise ValueError('IEF: universo o panel vacio.')
    for frame, keys in ((panel, KEY), (empresas, ['cuit_normalizado'])):
        if frame[keys].isna().any().any():
            raise ValueError('IEF: clave nula.')
        if not frame.cuit_normalizado.map(lambda x: isinstance(x, str)).all():
            raise ValueError('IEF: CUIT debe conservarse como texto.')
        require_unique(frame, keys, 'IEF')
    if not panel.cuit_normalizado.isin(empresas.cuit_normalizado).all():
        raise ValueError('IEF: empresa fuera del universo.')
    dates = pd.to_datetime(panel.fecha, format='%Y-%m-%d', errors='raise')
    if not dates.dt.is_month_start.all():
        raise ValueError('IEF: fecha debe ser el primer dia del mes de referencia.')
    panel['fecha'] = dates
    for col in ('mes_observado', 'empresa_con_deuda_activa'):
        panel[col] = booleanos(panel[col])
        if panel[col].isna().any():
            raise ValueError(f'IEF: bandera nula: {col}')
    numeric = [NOMINAL, REAL, COUNT, FEATURES[2], FEATURES[3],
               'pct_deuda_situacion_2', 'pct_deuda_situacion_3_mas']
    for col in numeric:
        panel[col] = pd.to_numeric(panel[col], errors='raise').astype(float)
        if not np.isfinite(panel[col].dropna()).all() or panel[col].dropna().lt(0).any():
            raise ValueError(f'IEF: valor negativo o no finito: {col}')
    if (panel[FEATURES[2]].dropna().gt(1 + 1e-10).any()
            or panel[FEATURES[3]].dropna().mod(1).ne(0).any()
            or panel[FEATURES[3]].dropna().lt(1).any()
            or panel[FEATURES[3]].dropna().gt(6).any()
            or panel[COUNT].dropna().mod(1).ne(0).any()):
        raise ValueError('IEF: HHI, situacion o cantidad fuera de dominio.')
    for col in ('pct_deuda_situacion_2', 'pct_deuda_situacion_3_mas'):
        if panel[col].dropna().gt(100 + 1e-8).any():
            raise ValueError('IEF: proporciones fuera de 0 a 100.')
    if (panel.pct_deuda_situacion_2 + panel.pct_deuda_situacion_3_mas).gt(100 + 1e-8).any():
        raise ValueError('IEF: composicion total superior a 100%.')
    observed = panel.mes_observado
    if (not panel.loc[observed, NOMINAL].notna().all()
            or not panel.loc[observed, 'empresa_con_deuda_activa'].eq(panel.loc[observed, NOMINAL].gt(0)).all()
            or not panel.loc[observed, 'empresa_con_deuda_activa'].eq(panel.loc[observed, COUNT].gt(0)).all()):
        raise ValueError('IEF: saldo, cantidad y deuda activa incoherentes.')
    adjusted = panel.estado_ajuste_ipc.eq('ajustado') & observed
    if not panel.loc[adjusted, REAL].notna().all():
        raise ValueError('IEF: ajuste IPC declarado sin deuda real.')
    if (panel.loc[adjusted & panel[NOMINAL].gt(0), REAL].le(0).any()
            or panel.loc[adjusted & panel[NOMINAL].eq(0), REAL].ne(0).any()):
        raise ValueError('IEF: cero o signo real incompatible con nominal.')

    months = pd.date_range(dates.min(), dates.max(), freq='MS')
    grid = pd.MultiIndex.from_product([sorted(empresas.cuit_normalizado), months], names=KEY)
    source_keys = pd.MultiIndex.from_frame(panel[KEY])
    d = panel.set_index(KEY).reindex(grid).reset_index()
    d['fila_presente_fuente'] = grid.isin(source_keys)
    d['mes_observado'] = d.mes_observado.fillna(False).astype(bool)
    d['empresa_con_deuda_activa'] = d.empresa_con_deuda_activa.astype('boolean')
    ids = d.cuit_normalizado
    observed = d.mes_observado
    active = observed & d.empresa_con_deuda_activa.fillna(False)

    def lag(s):
        return s.groupby(ids, sort=False).shift(3)

    def window(s):
        return s.astype(int).groupby(ids, sort=False).transform(
            lambda x: x.rolling(4, min_periods=4).sum()).eq(4)

    history = d.groupby('cuit_normalizado', sort=False).cumcount().ge(3)
    complete = window(observed)
    adjusted_window = window(observed & d.estado_ajuste_ipc.eq('ajustado') & d[REAL].notna())
    real = d[REAL].where(observed & d.estado_ajuste_ipc.eq('ajustado'))
    previous_real = lag(real)
    # where antes de dividir: nunca crear un infinito intermedio por deuda base cero.
    growth = 100 * (real / previous_real.where(previous_real.gt(0)) - 1)
    d[FEATURES[0]] = growth.where(adjusted_window)
    count = d[COUNT].where(observed)
    d[FEATURES[1]] = (count - lag(count)).where(complete)
    for col in FEATURES[2:4]:
        d[col] = d[col].where(active)
    bad = (d.pct_deuda_situacion_2 + d.pct_deuda_situacion_3_mas).where(active)
    d[FEATURES[4]] = bad
    d[FEATURES[5]] = (bad - lag(bad)).where(complete)
    d['split'] = 'fuera_protocolo'
    for name, (start, end) in SPLITS.items():
        d.loc[d.fecha.between(start, end), 'split'] = name
    d['n_features_disponibles'] = d[list(FEATURES)].notna().sum(axis=1)
    d['elegible_ief'] = active & d.n_features_disponibles.eq(len(FEATURES)) & d.split.ne('fuera_protocolo')
    reasons = [
        ('fuera_protocolo', d.split.eq('fuera_protocolo')),
        ('mes_sin_observacion', ~observed),
        ('sin_deuda_activa', observed & ~active),
        ('historia_insuficiente_3m', ~history),
        ('ventana_3m_sin_observacion', history & ~complete),
        ('ajuste_ipc_no_disponible_ventana', complete & ~adjusted_window),
        ('deuda_base_3m_no_positiva', adjusted_window & previous_real.le(0)),
    ]
    reasons += [(f'no_disponible:{col}', d[col].isna()) for col in FEATURES]
    d['motivos_no_elegible'] = [';'.join(name for name, mask in reasons if bool(mask.iloc[i]))
                                for i in range(len(d))]
    if not d.motivos_no_elegible.eq('').eq(d.elegible_ief).all():
        raise ValueError('IEF: elegibilidad incoherente con motivos.')
    if np.isinf(d[list(FEATURES)].to_numpy(dtype=float)).any():
        raise ValueError('IEF: overflow en una feature; revisar magnitudes.')
    d['cutoff_referencia'] = d.fecha.dt.to_period('M').dt.to_timestamp('M').dt.strftime('%Y-%m-%d')
    d['fecha'] = d.fecha.dt.strftime('%Y-%m-%d')
    context = ['cuit_normalizado', 'razon_social', 'grupo_economico', 'perfil_sectorial']
    d = d.merge(empresas[context], on='cuit_normalizado', how='left', validate='many_to_one')
    columns = [*KEY, *context[1:], 'cutoff_referencia', 'split', 'fila_presente_fuente',
               'mes_observado', 'empresa_con_deuda_activa', NOMINAL, REAL, COUNT,
               'estado_ajuste_ipc', 'ipc_fecha_mes', *FEATURES,
               'n_features_disponibles', 'elegible_ief', 'motivos_no_elegible']
    return d[columns].sort_values(KEY).reset_index(drop=True)


def resumir(frame):
    return {str(name): {'filas': len(part), 'elegibles': int(part.elegible_ief.sum()),
                       'empresas': int(part.cuit_normalizado.nunique()),
                       'meses': int(part.fecha.nunique())}
            for name, part in frame.groupby('split', sort=True)}


def transformar_crecimiento(frame):
    """Transformacion fija, sin fit, sobre la grilla completa y antes de filtrar."""
    d = frame.copy().sort_values(KEY).reset_index(drop=True)
    require_unique(d, KEY, 'Tratamiento IEF')
    dates = pd.to_datetime(d.fecha, format='%Y-%m-%d', errors='raise')
    group = d.groupby('cuit_normalizado', sort=False)
    previous = group[REAL].shift(3)
    previous_date = dates.groupby(d.cuit_normalizado, sort=False).shift(3)
    calendar_ok = (dates.dt.year * 12 + dates.dt.month -
                   (previous_date.dt.year * 12 + previous_date.dt.month)).eq(3)
    valid = d[FEATURES[0]].notna() & d[REAL].gt(0) & previous.gt(0) & calendar_ok
    # Diferencia de logaritmos: evita overflow/underflow del cociente intermedio.
    d[LOG_RATIO] = np.log(d[REAL].where(valid).astype(float)) - np.log(previous.where(valid).astype(float))
    eligible = d.elegible_ief.astype(bool)
    if (d.loc[eligible, LOG_RATIO].isna().any()
            or not np.isfinite(d.loc[eligible, list(FEATURES_MODELO)].to_numpy(dtype=float)).all()):
        raise ValueError('IEF: fila elegible sin seis predictores tratados finitos.')
    return d


def ajustar_referencias_tratamiento(frame):
    """Solo diagnostico de train: los percentiles no recortan ni escalan datos."""
    train = frame.loc[frame.elegible_ief & frame.split.eq('train')].sort_values(KEY)
    if train.empty:
        raise ValueError('IEF: faltan filas elegibles de train para fijar referencias.')
    summaries = {}
    for col in dict.fromkeys((*FEATURES, LOG_RATIO)):
        values = train[col].astype(float)
        summaries[col] = {
            'min': float(values.min()), 'p01': float(values.quantile(.01)),
            'mediana': float(values.median()), 'p99': float(values.quantile(.99)),
            'max': float(values.max()), 'valores_distintos': int(values.nunique()),
        }
    if any(summaries[col]['valores_distintos'] < 2 for col in FEATURES_MODELO):
        raise ValueError('IEF: predictor constante en train; requiere revisar el protocolo.')
    payload = train[[*KEY, *FEATURES_MODELO]].to_csv(index=False, lineterminator='\n')
    return {
        'version': VERSION, 'crecimiento': 'log_ratio_real_3m',
        'formula': 'ln(R_t) - ln(R_t-3)', 'transformacion_ajustada': False,
        'referencias_ajustadas_en': 'train_elegible', 'filas_train': len(train),
        'desde_train': train.fecha.min(), 'hasta_train': train.fecha.max(),
        'train_predictores_sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest(),
        'predictores_ordenados': list(FEATURES_MODELO), 'resumen_train': summaries,
        'imputacion': False, 'winsorizacion': False, 'escalado': False,
        'eliminar_extremos': False, 'redondear_predictores': False,
        'etiqueta_extremo': 'fuera del minimo/maximo de crecimiento logaritmico de train; solo contexto',
    }


def tratar_matriz(frame, referencias=None):
    """Aplicar reglas fijas; referencias provistas nunca se vuelven a ajustar."""
    d = transformar_crecimiento(frame)
    refs = ajustar_referencias_tratamiento(d) if referencias is None else referencias
    if (refs.get('version') != VERSION
            or refs.get('crecimiento') != 'log_ratio_real_3m'
            or refs.get('predictores_ordenados') != list(FEATURES_MODELO)
            or any(refs.get(k) is not False for k in
                   ('imputacion', 'winsorizacion', 'escalado', 'eliminar_extremos', 'redondear_predictores'))):
        raise ValueError('IEF: referencias de tratamiento incompatibles.')
    limits = refs['resumen_train'][LOG_RATIO]
    lower, upper = float(limits['min']), float(limits['max'])
    if not np.isfinite([lower, upper]).all() or lower >= upper:
        raise ValueError('IEF: limites de referencia invalidos.')
    # Contexto para revisar casos futuros; esta bandera nunca entra en X.
    flag = d[LOG_RATIO].lt(lower) | d[LOG_RATIO].gt(upper)
    d['crecimiento_fuera_rango_train'] = flag.astype('boolean').where(d[LOG_RATIO].notna())
    return d, refs


def diagnostico_tratamiento(frame):
    """Cobertura y extremos por bloque; no interviene en la transformacion."""
    summary = {}
    for name, part in frame.groupby('split', sort=True):
        valid = part.loc[part.elegible_ief]
        summary[str(name)] = {
            'filas_elegibles': len(valid),
            'crecimientos_fuera_rango_train': int(valid.crecimiento_fuera_rango_train.sum()),
            'crecimientos_mayores_1000_pct': int(valid[FEATURES[0]].gt(1000).sum()),
            'log_ratio_min': float(valid[LOG_RATIO].min()) if len(valid) else None,
            'log_ratio_mediana': float(valid[LOG_RATIO].median()) if len(valid) else None,
            'log_ratio_max': float(valid[LOG_RATIO].max()) if len(valid) else None,
        }
    return summary


def auditar_extremos_fuente(root, frame, panel, run_id):
    """Tres mayores y tres menores crecimientos de train, contra la captura JSON."""
    metadata = json.loads((Path(root) / 'data_analytics/runs' / run_id / 'run_metadata.json').read_text(encoding='utf-8'))
    expected = metadata['source_sha256']
    train = frame.loc[frame.elegible_ief & frame.split.eq('train')]
    cases = pd.concat([train.nlargest(3, FEATURES[0]), train.nsmallest(3, FEATURES[0])]).drop_duplicates(KEY)
    source = panel.set_index(KEY)
    result = []
    for _, row in cases.iterrows():
        date = pd.Timestamp(row.fecha)
        previous_date = (date - pd.DateOffset(months=3)).strftime('%Y-%m-%d')
        ends = []
        for reference in (previous_date, row.fecha):
            point = source.loc[(row.cuit_normalizado, reference)]
            capture = str(point.run_fuente)
            if Path(capture).name != capture or capture in ('.', '..'):
                raise ValueError('IEF: captura C invalida.')
            paths = list((Path(root) / 'data_c/runs').glob(f'*/{capture}/raw/deudas/{row.cuit_normalizado}.json'))
            if len(paths) != 1:
                raise ValueError('IEF: falta captura unica para auditar extremos.')
            path = paths[0]
            relative = path.relative_to(root).as_posix()
            digest = sha256(path)
            if expected.get(relative) != digest:
                raise ValueError('IEF: captura original de extremo alterada.')
            raw = json.loads(path.read_text(encoding='utf-8-sig'))
            periods = [p for p in raw['results']['periodos']
                       if str(p['periodo']) == pd.Timestamp(reference).strftime('%Y%m')]
            if raw.get('status') != 200 or len(periods) != 1:
                raise ValueError('IEF: periodo ausente en captura original.')
            amount = sum(float(e['monto']) for e in periods[0]['entidades'] if float(e['monto']) > 0)
            if not np.isclose(amount, float(point[NOMINAL]), rtol=1e-12, atol=1e-8):
                raise ValueError('IEF: extremo no reconcilia con captura original.')
            ends.append({'fecha': reference, 'nominal_miles_ARS': amount,
                         'real_miles_ARS_dic2016': float(point[REAL]),
                         'captura': relative, 'captura_sha256': digest})
        result.append({'cuit_normalizado': row.cuit_normalizado, 'razon_social': row.razon_social,
                       'fecha': row.fecha, 'crecimiento_real_pct': float(row[FEATURES[0]]),
                       'log_ratio_real': float(row[LOG_RATIO]), 'extremos': ends,
                       'resultado': 'coincide_con_captura_no_demuestra_continuidad_economica'})
    return result


def ejecutar(root=ROOT, output_dir=None):
    """Publicar dos archivos juntos. Un destino existente debe ser identico."""
    root = Path(root).resolve()
    tables, provenance = leer_insumos(root)
    original = construir_matriz(tables['empresa_mes'], tables['empresas'])
    frame, tratamiento = tratar_matriz(original)
    audit_cases = auditar_extremos_fuente(root, frame, tables['empresa_mes'], provenance['run_origen'])
    output = (Path(output_dir).resolve() if output_dir is not None else
              root / 'data_analytics/modelos_ief' / provenance['run_origen'] / f'v{VERSION}')
    # Un error de destino no puede tocar fuentes, tablas, código ni otra versión.
    default_parent = root / 'data_analytics/modelos_ief'
    if output.is_relative_to(root):
        allowed = (output.is_relative_to(default_parent) or
                   not output.is_relative_to(root / 'data_analytics'))
        protected = ['data_a', 'data_b', 'data_c', 'config', 'ml', 'lib', 'docs', 'analisis', 'experimentos']
        if output == root or not allowed or any(output.is_relative_to(root / p) for p in protected):
            raise ValueError('IEF: destino protegido.')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ief_', dir=output.parent))
    try:
        csv_path = stage / 'features_ief.csv'
        write_csv(frame, csv_path)
        train = frame.loc[frame.elegible_ief & frame.split.eq('train'), list(FEATURES_MODELO)]
        distinct = {col: int(train[col].nunique()) for col in FEATURES_MODELO}
        report = {
            'version_features': VERSION, 'etapa': 'matriz_tratada_sin_modelo', 'modelo_entrenado': False,
            **provenance, 'entorno': runtime_metadata(), 'predictores_ordenados': list(FEATURES_MODELO),
            'predictores_originales_ordenados': list(FEATURES),
            'tratamiento': tratamiento, 'diagnostico_tratamiento': diagnostico_tratamiento(frame),
            'auditoria_extremos_train': audit_cases,
            'diccionario': DICCIONARIO, 'splits_fijos': SPLITS,
            'unidad_deuda_nominal': 'miles_ARS', 'unidad_deuda_real': 'miles_ARS_dic2016',
            'deflacion': 'nominal * 100 / IPC nacional del mismo mes; base diciembre 2016 = 100',
            'cutoff': 'cierre del mes de referencia; no certifica disponibilidad historica',
            'disponibilidad_historica_verificada': False,
            'ventana_cambio_3m': 't-3, t-2, t-1, t; sin comprimir huecos ni imputar',
            'poblacion': 'panel intencional de agroindustria; empresas repetidas entre bloques',
            'filas_fuente': len(tables['empresa_mes']), 'filas_matriz': len(frame),
            'filas_grilla_agregadas': int((~frame.fila_presente_fuente).sum()),
            'cobertura': resumir(frame),
            'diagnostico_train': {
                'valores_distintos': distinct,
                'predictores_constantes': [col for col, n in distinct.items() if n <= 1],
                'seleccion_automatica': False,
            },
            'faltantes_por_predictor': {col: int(frame[col].isna().sum()) for col in FEATURES_MODELO},
            'motivos_no_excluyentes': frame.loc[~frame.elegible_ief, 'motivos_no_elegible'].str.split(';').explode().value_counts().to_dict(),
            'features_sha256': sha256(csv_path),
        }
        (stage / 'protocolo_resultados.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            if (not output.is_dir() or {p.name for p in output.iterdir()} != {p.name for p in stage.iterdir()}
                    or any(sha256(output / p.name) != sha256(p) for p in stage.iterdir())):
                raise FileExistsError('IEF: bundle diferente; indicar otro --output-dir o nueva version.')
        else:
            stage.rename(output)
        return frame, report, output
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, help='Destino nuevo para una reproduccion.')
    args = parser.parse_args()
    frame, report, path = ejecutar(args.root, args.output_dir)
    print(f'IEF {VERSION}: {len(frame)} filas; {int(frame.elegible_ief.sum())} elegibles; sin modelo entrenado.')
    print(json.dumps(report['cobertura'], ensure_ascii=False))
    print(f'Salida: {path}')


if __name__ == '__main__':
    main()
