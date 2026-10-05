"""Referencias experimentales ICC hipotecario; splits fijos y percentiles solo en train."""
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

from lib.common import read_csv, require_unique, runtime_metadata, write_csv
from ml.features import FEATURES_ICC, SERIES_ICC, construir_icc, validar_matriz_icc

VERSION_BASELINE = '1.0'
CORTES_ICC = {
    'train': ('2016-08-31', '2021-12-31'),
    'validacion': ('2022-01-31', '2023-12-31'),
    'evaluacion_retrospectiva': ('2024-01-31', '2026-06-30'),
}
MIN_TRAIN = 60
G1 = 'credito_var_nominal_1m_pct'
G3 = 'credito_var_nominal_3m_pct'
TASA = 'tasa_uva_tna_pct'
DELTA = 'tasa_uva_delta_3m_pp'
PREDICTORES_BASELINE = (G1, G3, TASA, DELTA)
VARIANTES = {
    'referencia_trimestral': {G3: (0.5, 1), TASA: (0.5, -1)},
    'referencia_mensual': {G1: (0.5, 1), TASA: (0.5, -1)},
    'referencia_balanceada': {G1: (0.25, 1), G3: (0.25, 1),
                            TASA: (0.25, -1), DELTA: (0.25, -1)},
}
CASOS_REVISION = ('2024-02-29', '2024-10-31', '2024-11-30')


# 1. Lectura de la matriz persistida y de la metodología inmutable

def leer_matriz_icc(root=ROOT):
    root = Path(root)
    expected = construir_icc(root)
    run_id = expected['run_origen'].iloc[0]
    path = root / 'data_analytics' / 'features' / run_id / 'icc.csv'
    if not path.is_file():
        raise FileNotFoundError('Primero ejecutar ml/features.py; no generar una matriz implícita.')
    text = expected.select_dtypes(include=['object', 'string']).columns
    frame = read_csv(path, dtype={name: str for name in text})
    for name in frame.columns:
        if name.startswith('motivo_') or name == 'motivos_no_elegible':
            frame[name] = frame[name].fillna('')
    validar_matriz_icc(frame)
    try:
        pd.testing.assert_frame_equal(expected, frame, check_dtype=False, check_exact=False,
                                      rtol=1e-12, atol=1e-12)
    except AssertionError as exc:
        raise ValueError('La matriz no corresponde a las fuentes/código vigentes; ejecutar features.') from exc
    method_path = root / 'data_a' / 'metadata' / 'bcra_monetarias_metodologia.csv'
    method_hash = hashlib.sha256(method_path.read_bytes()).hexdigest()
    metadata_path = root / 'data_analytics' / 'runs' / run_id / 'run_metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if method_hash != metadata['source_sha256'].get('data_a/metadata/bcra_monetarias_metodologia.csv'):
        raise ValueError('La metodología no coincide con la consolidación de origen.')
    method = read_csv(method_path)
    selected = method.loc[method['idVariable'].isin(SERIES_ICC)]
    require_unique(selected, ['idVariable'], 'Metodología ICC')
    if (set(selected['idVariable']) != set(SERIES_ICC)
            or selected['detalle'].isna().any()):
        raise ValueError('Falta metodología para una serie ICC.')
    source = {'run_origen': run_id, 'matriz_features_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'version_features': frame['version_features'].iloc[0],
              'metodologia_sha256': method_hash,
              'codigo_baseline_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'codigo_features_sha256': frame['codigo_features_sha256'].iloc[0]}
    return frame, source


# 2. Splits por calendario; ni los valores ni los extremos eligen las fronteras

def _splits_por_fecha(values):
    dates = pd.to_datetime(values, format='%Y-%m-%d', errors='raise')
    split = pd.Series('fuera_protocolo', index=values.index, dtype='string')
    for name, (start, end) in CORTES_ICC.items():
        split.loc[dates.between(start, end)] = name
    split.loc[dates.ge('2026-07-01')] = 'reserva_futura'
    return split


def asignar_splits_icc(frame):
    validar_matriz_icc(frame)
    return _splits_por_fecha(frame['fecha_mes'])


# 3. Ajuste de referencias: ninguna observación de validación/evaluación participa

def ajustar_referencias_icc(frame, min_train=MIN_TRAIN):
    if min_train < 1:
        raise ValueError('El mínimo de train debe ser positivo.')
    split = asignar_splits_icc(frame)
    train = frame.loc[split.eq('train') & frame['elegible_icc']]
    if len(train) < min_train:
        raise ValueError(f'Train ICC insuficiente: {len(train)} meses; se requieren {min_train}.')
    references = {}
    for name in PREDICTORES_BASELINE:
        values = train[name].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f'Train contiene nulos/infinitos: {name}')
        references[name] = np.sort(values).tolist()
    return references


def percentil_referencia(values, reference):
    ref = np.asarray(reference, dtype=float)
    if ref.ndim != 1 or not len(ref) or not np.isfinite(ref).all() or np.any(np.diff(ref) < 0):
        raise ValueError('Referencia empírica vacía, desordenada o no finita.')
    values = values.astype(float)
    if np.isinf(values.to_numpy()).any():
        raise ValueError('Infinito al calcular percentiles.')
    result = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.notna()
    x = values.loc[valid].to_numpy()
    left = np.searchsorted(ref, x, side='left')
    right = np.searchsorted(ref, x, side='right')
    # ECDF de rango medio: los empates reciben el mismo percentil.
    result.loc[valid] = 100 * (left + right) / (2 * len(ref))
    return result


# 4. Aplicación congelada; composición y volatilidad se conservan como descriptores

def aplicar_baseline_icc(frame, references):
    if set(references) != set(PREDICTORES_BASELINE):
        raise ValueError('Predictores de referencia distintos del protocolo.')
    split = asignar_splits_icc(frame)
    usable = frame['elegible_icc'] & split.isin(CORTES_ICC)
    result = frame[['fecha_mes', 'segmento', 'cutoff_referencia', 'run_origen',
                    'elegible_icc', 'motivos_no_elegible', 'stock_observado',
                    'participacion_construccion_pct', 'credito_volatilidad_6m_pp']].copy()
    result['split_temporal'] = split
    result['utilizable_baseline'] = usable
    result['contemporaneidad_stock_verificada'] = False
    result['disponibilidad_historica_verificada'] = False
    result['estado_producto'] = 'referencia_experimental_hipotecaria'
    result['version_baseline'] = VERSION_BASELINE
    reason = frame['motivos_no_elegible'].copy()
    for role in ('fuera_protocolo', 'reserva_futura'):
        mask = split.eq(role)
        reason.loc[mask] = reason.loc[mask].apply(lambda value: role + (';' + value if value else ''))
    result['motivo_no_utilizable_baseline'] = reason
    for name in PREDICTORES_BASELINE:
        result[f'percentil_{name}'] = percentil_referencia(frame[name].where(usable), references[name])
    for variant, components in VARIANTES.items():
        if not np.isclose(sum(weight for weight, _ in components.values()), 1):
            raise ValueError('Pesos de baseline no suman uno.')
        weighted = []
        for name, (weight, direction) in components.items():
            percentile = result[f'percentil_{name}']
            weighted.append(weight * (percentile if direction == 1 else 100 - percentile))
        result[variant] = sum(weighted)
    for name in ('referencia_mensual', 'referencia_balanceada'):
        result[f'diferencia_{name}_vs_trimestral_pp'] = result[name] - result['referencia_trimestral']
    validar_baseline_icc(result)
    return result


def validar_baseline_icc(frame):
    if frame.empty:
        raise ValueError('Baseline vacío.')
    require_unique(frame, ['fecha_mes', 'segmento'], 'Baseline ICC')
    if frame[['fecha_mes', 'segmento']].isna().any().any():
        raise ValueError('Clave nula en baseline.')
    timestamps = pd.to_datetime(frame['fecha_mes'], format='%Y-%m-%d', errors='raise')
    dates = pd.PeriodIndex(timestamps, freq='M')
    if (not dates.equals(pd.period_range(dates.min(), dates.max(), freq='M'))
            or not timestamps.dt.is_month_end.all()
            or not frame['cutoff_referencia'].eq(frame['fecha_mes']).all()):
        raise ValueError('Baseline desordenado, con huecos o cutoff inválido.')
    if not frame['split_temporal'].eq(_splits_por_fecha(frame['fecha_mes'])).all():
        raise ValueError('Split distinto del protocolo de calendario.')
    allowed = frame['elegible_icc'] & frame['split_temporal'].isin(CORTES_ICC)
    if not allowed.eq(frame['utilizable_baseline']).all():
        raise ValueError('Elegibilidad de baseline inconsistente.')
    for name in [*VARIANTES, *[f'percentil_{col}' for col in PREDICTORES_BASELINE]]:
        if not frame[name].notna().eq(allowed).all() or not frame[name].dropna().between(0, 100).all():
            raise ValueError(f'Referencia ausente o fuera de 0–100: {name}')
    if not allowed.eq(frame['motivo_no_utilizable_baseline'].eq('')).all():
        raise ValueError('Motivos de exclusión de baseline inconsistentes.')
    if np.isinf(frame.select_dtypes(include='number').to_numpy(dtype=float)).any():
        raise ValueError('Infinito en baseline.')


# 5. Diagnósticos train/validación y protocolo reproducible para el futuro entrenamiento

def preparar_protocolo_icc(frame, baseline, references, source):
    split = asignar_splits_icc(frame)
    eligible = frame['elegible_icc']
    train = frame.loc[eligible & split.eq('train')]
    diagnostics = {}
    # No elegir variantes ni calibraciones a partir del bloque retrospectivo ya observado.
    for role in ('train', 'validacion'):
        mask = eligible & split.eq(role)
        block = baseline.loc[mask]
        comparisons = {}
        for variant in ('referencia_mensual', 'referencia_balanceada'):
            difference = block[variant] - block['referencia_trimestral']
            comparisons[variant] = {
                'media_diferencia_absoluta_pp': float(difference.abs().mean()) if len(block) else None,
                'max_diferencia_absoluta_pp': float(difference.abs().max()) if len(block) else None,
                'correlacion_pearson_con_trimestral': float(block[variant].corr(block['referencia_trimestral']))
                if len(block) > 1 and block[variant].nunique() > 1
                and block['referencia_trimestral'].nunique() > 1 else None,
            }
        diagnostics[role] = {'n_meses': len(block), 'comparaciones': comparisons,
                             'fuera_rango_train': {
                                 name: int((frame.loc[mask, name].lt(min(ref))
                                            | frame.loc[mask, name].gt(max(ref))).sum())
                                 for name, ref in references.items()}}
    cases = []
    for date in CASOS_REVISION:
        row = frame.loc[frame['fecha_mes'].eq(date)]
        if not row.empty:
            cases.append({'fecha_mes': date, 'estado': 'causa_economica_o_metodologica_no_identificada',
                          'valores_publicados_sin_corregir': {
                              name: float(row[name].iloc[0]) if pd.notna(row[name].iloc[0]) else None
                              for name in FEATURES_ICC}})
    protocol = {
        'version': VERSION_BASELINE, 'estado': 'experimental_no_score_productivo',
        'alcance': 'Hipotecarios ML a personas humanas; tasa UVA de otorgamientos al sector privado',
        'origen': source, 'runtime': runtime_metadata(),
        'splits_calendario': {name: {'desde': start, 'hasta': end,
                                    'meses_elegibles': int((eligible & split.eq(name)).sum())}
                             for name, (start, end) in CORTES_ICC.items()},
        'reserva_futura_desde': '2026-07-01', 'min_meses_train': MIN_TRAIN,
        'train_fechas_utilizadas': train['fecha_mes'].tolist(),
        'regla_ecdf': '100 * (n_train_menor + 0.5 * n_train_igual) / n_train',
        'referencias_train_ordenadas': references,
        'variantes_pesos_y_direccion': {variant: {
            name: {'peso': weight, 'direccion': direction} for name, (weight, direction) in values.items()}
            for variant, values in VARIANTES.items()},
        'descriptores_sin_peso': ['participacion_construccion_pct', 'credito_volatilidad_6m_pp'],
        'correlaciones_solo_train': {
            'pearson': train[list(FEATURES_ICC)].corr(method='pearson').to_dict(),
            'spearman': train[list(FEATURES_ICC)].corr(method='spearman').to_dict()},
        'diagnosticos_train_validacion': diagnostics,
        'casos_revision_ex_post': cases,
        'limitaciones': [
            'Evaluación 2024–2026 ya observada: no es test final intacto ni point-in-time.',
            'Reserva futura no se puntúa; un test verdaderamente no inspeccionado sigue pendiente.',
            'Stock publicado puede repetir el último saldo conocido; contemporaneidad no identificable.',
            'Saldo vigente PH y tasa ponderada de otorgamientos UVA al sector privado no son la misma población.',
            'Causas de extremos 2024 sin identificar; no winsorizar ni eliminar automáticamente.',
            'Percentiles congelados saturan fuera del rango de train; no miden la magnitud del extremo.',
            'No hay etiquetas, accuracy, optimización de pesos, PCA ni calibración de regímenes.',
        ],
    }
    # Correlaciones indefinidas (p.ej. descriptor constante) son nulos JSON, no NaN.
    for matrix in protocol['correlaciones_solo_train'].values():
        for row in matrix.values():
            for name, value in row.items():
                if not np.isfinite(value):
                    row[name] = None
    return protocol


# 6. Publicación: un CSV de comparación y un artefacto JSON de referencias/splits

def construir_baseline_icc(root=ROOT):
    frame, source = leer_matriz_icc(root)
    references = ajustar_referencias_icc(frame)
    baseline = aplicar_baseline_icc(frame, references)
    protocol = preparar_protocolo_icc(frame, baseline, references, source)
    return baseline, protocol


def exportar_baseline_icc(frame, protocol, root=ROOT):
    validar_baseline_icc(frame)
    run_id = protocol['origen']['run_origen']
    if not frame['run_origen'].eq(run_id).all():
        raise ValueError('Baseline mezcla consolidaciones.')
    output = Path(root) / 'data_analytics' / 'baselines' / run_id
    csv_path, json_path = output / 'icc_hipotecario.csv', output / 'protocolo_icc.json'
    write_csv(frame, csv_path)
    protocol = {**protocol, 'baseline_csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()}
    payload = json.dumps(protocol, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    temp = json_path.with_name(json_path.name + '.tmp')
    try:
        temp.write_text(payload, encoding='utf-8')
        temp.replace(json_path)
    finally:
        temp.unlink(missing_ok=True)
    return csv_path, json_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Raíz del proyecto; sin red.')
    args = parser.parse_args()
    frame, protocol = construir_baseline_icc(args.root)
    paths = exportar_baseline_icc(frame, protocol, args.root)
    print('ICC hipotecario: referencias experimentales, no score productivo.')
    for role, spec in protocol['splits_calendario'].items():
        print(f'{role}: {spec["desde"]} a {spec["hasta"]}; {spec["meses_elegibles"]} meses elegibles.')
    print('Composición/volatilidad: descriptores sin peso. Reserva futura: sin puntuar.')
    for path in paths:
        print(f'Salida: {path}')


if __name__ == '__main__':
    main()
