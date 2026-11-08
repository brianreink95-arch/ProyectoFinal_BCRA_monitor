"""ICC S1 experimental: referencias congeladas, volumen × costo/momentum.

1. Entrada y calidad. 2. Calendario. 3. Ajuste exclusivo en train.
4. Aplicación sin reajuste. 5. Publicación versionada y trazable.
El saldo no mide acceso individual y la TNA UVA es un proxy parcial de costo.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib.common import read_csv, require_unique, runtime_metadata, write_csv
from ml.features import (FEATURES_ICC, SERIES_ICC, STOCK_REAL, DELTA_STOCK_REAL,
                         elegibilidad_features, construir_icc, validar_matriz_icc,
                         ruta_matriz_icc)

VERSION_BASELINE = '4.0'
VERSION_PROTOCOLO = '3.1'
METODOLOGIA_ICC_APROBADA = True  # Adopción S1 experimental; no certificación operativa.
MOTIVO_METODOLOGICO = ''
CORTES_ICC = {
    'train': ('2016-08-31', '2022-02-28'),
    'validacion': ('2022-03-31', '2023-12-31'),
    'evaluacion_retrospectiva': ('2024-01-31', '2026-06-30'),
}
MIN_TRAIN = 60
G1 = 'credito_var_real_1m_pct'
G3 = 'credito_var_real_3m_pct'
TASA = 'tasa_uva_tna_pct'
DELTA = 'tasa_uva_delta_3m_pp'
PREDICTORES_BASELINE = (STOCK_REAL, G3, TASA)
CONFIG_S1 = {
    'metodo': 'S1', 'version': VERSION_BASELINE, 'protocolo': VERSION_PROTOCOLO,
    'adopcion_local': '2026-10-06', 'features': list(PREDICTORES_BASELINE),
    'min_train': 60, 'min_validacion': 18, 'cuantiles': 'linear',
    'peso_costo': .80, 'peso_momentum': .20, 'divisor_iqr': 1.349,
    'piso_tasa_pp': .10, 'piso_crecimiento_pp': .50, 'piso_delta_stock': 1.,
    'piso_factor': 1e-6, 'piso_std': 1e-12,
    'cargas_l1_min': [.20, .20, .10], 'tolerancia_economica': 1e-9,
    'sensibilidad_rho_min': .90, 'sensibilidad_mae_max': 10.,
    'perturbacion': [.90, 1.10], 'coseno_min': .95,
    'mejora_mse_min': .10, 'empeoramiento_columna_max': .25,
    'saturacion_latente_max': .10, 'prospectivos_operacion_min': 12,
    'cortes': CORTES_ICC,
}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def hash_json(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def hash_bloque(frame, columns=PREDICTORES_BASELINE):
    return hashlib.sha256(frame[['fecha_mes', *columns]].to_csv(
        index=False, float_format='%.17g', lineterminator='\n').encode()).hexdigest()


def mascara_core(frame):
    return elegibilidad_features(frame, PREDICTORES_BASELINE)[0]


def leer_matriz_icc(root=ROOT):
    root = Path(root)
    expected = construir_icc(root)
    run_id = expected['run_origen'].iloc[0]
    path = ruta_matriz_icc(root, run_id)
    if not path.is_file():
        raise FileNotFoundError('Primero ejecutar ml/features.py; no generar una matriz implícita.')
    text = expected.select_dtypes(include=['object', 'string']).columns
    frame = read_csv(path, dtype={name: str for name in text})
    for name in frame.columns:
        if name.startswith(('motivo_', 'motivos_')):
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
              'medida_credito': frame['medida_credito'].iloc[0],
              'deflactor_sha256': frame['deflactor_sha256'].iloc[0],
              'ipc_version_fuente': frame['ipc_version_fuente'].iloc[0],
              'metodologia_sha256': method_hash,
              'codigo_baseline_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'codigo_features_sha256': frame['codigo_features_sha256'].iloc[0]}
    return frame, source


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


def comprobar_protocolo_icc(frame):
    split = asignar_splits_icc(frame)
    eligible = mascara_core(frame)
    counts = {name: int((split.eq(name) & eligible).sum()) for name in CORTES_ICC}
    return {'version_protocolo': VERSION_PROTOCOLO,
            'cortes_calendario': {k: {'desde': v[0], 'hasta': v[1]} for k,v in CORTES_ICC.items()},
            'meses_elegibles_por_split': counts, 'min_meses_train': MIN_TRAIN,
            'cumple_minimo_train': counts['train'] >= MIN_TRAIN,
            'perfil_diagnostico': 'core_s1',
            'features_requeridas_diagnostico': list(PREDICTORES_BASELINE),
            'primera_fila_elegible': frame.loc[eligible, 'fecha_mes'].min(),
            'meses_comparacion_2_0_por_split': {
                name: int((split.eq(name) & frame['elegible_comparacion_2_0']).sum()) for name in CORTES_ICC},
            'meses_todas_candidatas_por_split': {
                name: int((split.eq(name) & frame['candidatas_completas']).sum()) for name in CORTES_ICC},
            'metodologia_aprobada': True, 'motivo_bloqueo_metodologico': '',
            'alcance_aprobacion': 'experimento S1; no uso operativo',
            'puede_calibrar': counts['train'] >= MIN_TRAIN}


# Referencias: una sola muestra común. Ningún cuantil posterior participa.
def escala(values, floor):
    q = np.quantile(np.asarray(values, dtype=float), [.25, .75], method='linear')
    return float(max((q[1]-q[0])/1.349, floor))


def ajustar_referencias_icc(frame, min_train=MIN_TRAIN):
    if (isinstance(min_train, bool) or not isinstance(min_train, (int, np.integer))
            or min_train < MIN_TRAIN):
        raise ValueError('No se permite reducir el mínimo de 60 meses.')
    split = asignar_splits_icc(frame)
    train = frame.loc[split.eq('train') & mascara_core(frame)]
    if len(train) < min_train:
        raise ValueError(f'Train ICC insuficiente: {len(train)} meses; mínimo {min_train}.')
    x = train[list(PREDICTORES_BASELINE)].to_numpy(float)
    if not np.isfinite(x).all() or np.any(x[:, 0] < 0) or np.any(x[:, 2] < 0):
        raise ValueError('Valores core inválidos.')
    refs = {'metodo': 'S1', 'version': VERSION_BASELINE, 'n_train': len(train),
            'fechas_train': train['fecha_mes'].tolist(), 'train_sha256': hash_bloque(train),
            'R0': float(train[STOCK_REAL].median()), 'r0': float(train[TASA].median()),
            'sr': escala(train[TASA], .10), 'sg': escala(train[G3], .50),
            'rangos_train': {k: [float(train[k].min()), float(train[k].max())]
                             for k in PREDICTORES_BASELINE}}
    validar_referencias(refs)
    return refs


def validar_referencias(refs):
    if refs.get('metodo') != 'S1' or refs.get('version') != VERSION_BASELINE:
        raise ValueError('Referencias incompatibles con metodología S1 4.0.')
    for key in ('R0', 'r0', 'sr', 'sg'):
        v = refs.get(key)
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not np.isfinite(v):
            raise ValueError('Referencia no finita o incompleta: ' + key)
    if refs['R0'] <= 0 or refs['r0'] < 0 or refs['sr'] < .10 or refs['sg'] < .50:
        raise ValueError('Referencia fuera de dominio S1.')
    if refs.get('n_train', 0) < MIN_TRAIN:
        raise ValueError('Referencias requieren al menos 60 meses.')


def logistica(x):
    x = np.asarray(x, dtype=float)
    # Evita exp(+1000) y conserva extremos finitos sin recortar observaciones.
    a = np.exp(-np.abs(x))
    return np.where(x >= 0, 1/(1+a), a/(1+a))


def componentes(R, r, g, refs, peso_momentum=.20):
    R, r, g = np.broadcast_arrays(np.asarray(R,float), np.asarray(r,float), np.asarray(g,float))
    if not (np.isfinite(R).all() and np.isfinite(r).all() and np.isfinite(g).all()):
        raise ValueError('Componentes requieren valores finitos.')
    if np.any(R < 0) or np.any(r < 0) or not 0 <= peso_momentum <= 1:
        raise ValueError('Dominio económico inválido.')
    V = R / (R + refs['R0'])
    C = logistica((refs['r0'] - r)/refs['sr'])
    M = logistica(g/refs['sg'])
    return V, C, M, 100*V*((1-peso_momentum)*C+peso_momentum*M)


# Aplicación congelada. Reserva posterior permanece sin score.
def aplicar_baseline_icc(frame, references, roles=None):
    validar_referencias(references)
    split = asignar_splits_icc(frame)
    eligible, reasons = elegibilidad_features(frame, PREDICTORES_BASELINE)
    if roles is None:
        roles = tuple(CORTES_ICC)
    if not set(roles).issubset(CORTES_ICC):
        raise ValueError('No se habilita reserva ni fechas fuera del protocolo.')
    usable = eligible & split.isin(roles)
    keep = ['fecha_mes', *PREDICTORES_BASELINE]
    keep += [c for c in ('segmento', 'run_origen', 'cutoff_referencia', DELTA_STOCK_REAL,
                         DELTA, 'participacion_construccion_pct', 'credito_volatilidad_real_6m_pp')
             if c in frame]
    out = frame[keep].copy()
    out['split_temporal'] = split
    out['utilizable_baseline'] = usable
    out['motivo_no_utilizable_baseline'] = reasons
    out.loc[~split.isin(roles), 'motivo_no_utilizable_baseline'] = split.loc[~split.isin(roles)] + ':no_habilitado'
    for c in ('V_volumen', 'C_costo', 'M_momentum', 'icc_baseline_s1'):
        out[c] = np.nan
    values = componentes(frame.loc[usable, STOCK_REAL], frame.loc[usable, TASA],
                         frame.loc[usable, G3], references)
    for c, v in zip(('V_volumen','C_costo','M_momentum','icc_baseline_s1'), values):
        out.loc[usable, c] = v
    out['version_baseline'] = VERSION_BASELINE
    out['disponibilidad_historica_verificada'] = False
    out['estado_producto'] = 'experimental'
    return out


def validar_baseline_icc(frame):
    values = frame.loc[frame['utilizable_baseline'], 'icc_baseline_s1']
    if not np.isfinite(values).all() or not values.between(0, 100).all():
        raise ValueError('Baseline no finito/fuera de rango.')
    if frame.loc[~frame['utilizable_baseline'], 'icc_baseline_s1'].notna().any():
        raise ValueError('Score generado fuera de elegibilidad.')


def controles_economicos(refs, scorer=None):
    """Escenarios independientes, no una simulación de historias físicas de stock."""
    if scorer is None:
        scorer = lambda R,r,g: componentes(R,r,g,refs)[3]
    volumes = np.array([0,.01,.10,.25,.50,1,2,5])*refs['R0']
    rates = np.unique(np.maximum(0, [0,refs['r0']-2*refs['sr'],refs['r0'],refs['r0']+2*refs['sr']]))
    growths = np.array([-2,0,2])*refs['sg']
    R,r,g = np.meshgrid(volumes,rates,growths,indexing='ij')
    scores = scorer(R,r,g)
    tol = 1e-9
    failures = {
        'rango': int((~np.isfinite(scores) | (scores < -tol) | (scores > 100+tol)).sum()),
        'volumen_monotono': int((np.diff(scores,axis=0) < -tol).sum()),
        'tasa_monotona': int((np.diff(scores,axis=1) > tol).sum()),
        'momentum_monotono': int((np.diff(scores,axis=2) < -tol).sum()),
        'bajo_volumen': int((scores[:4] > 20+tol).sum()),
        'cero_volumen': int((np.abs(scores[0]) > tol).sum()),
        'mejora_estricta_tasa': int((np.diff(scores[1:],axis=1) >= 0).sum()),
    }
    return {'pasa': not any(failures.values()), 'violaciones': failures,
            'n_escenarios': int(scores.size), 'tolerancia': tol,
            'naturaleza': 'inputs independientes; g fijo al variar R'}


def cargar_entrada(root=ROOT, input_path=None):
    if input_path is None:
        frame, source = leer_matriz_icc(root)
        source['fuentes_reconstruidas'] = True
    else:
        from ml.evaluate_features import cargar_csv
        path = Path(input_path)
        frame = cargar_csv(path)
        source = {'run_origen': str(frame['run_origen'].iloc[0]),
                  'matriz_features_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'fuentes_reconstruidas': False,
                  'modo': 'csv_independiente; originales no adjuntos',
                  'metadatos_declarados': {k:str(frame[k].iloc[0]) for k in (
                      'version_features','version_contrato','medida_credito','deflactor_sha256',
                      'ipc_version_fuente','codigo_features_sha256')}}
    from ml.evaluate_features import evaluar
    source['identidades_internas_csv'] = evaluar(frame)['identidades_internas_csv']
    return frame, source


def directorio_modelo(root, frame):
    return Path(root)/'data_analytics'/'modelos_icc'/str(frame['run_origen'].iloc[0])/('v'+VERSION_BASELINE)


def publicar_bundle(output, files, manifest_name, manifest):
    """JSON se publica al final; hashes detectan una escritura parcial.

    El directorio versionado es inmutable: un rerun idéntico es un no-op;
    otro experimento debe elegir otro --output-dir. No pisa modelos previos.
    """
    output = Path(output)
    expected = dict(files)
    payload = dict(manifest)
    payload['archivos_sha256'] = {k: hashlib.sha256(v).hexdigest() for k,v in files.items()}
    expected[manifest_name] = json_bytes(payload)
    if output.exists():
        if all((output/k).is_file() and (output/k).read_bytes() == v for k,v in expected.items()):
            return payload
        raise FileExistsError('Salida existente distinta; elegir otro --output-dir.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='icc_s1_', dir=output.parent) as temporary:
        tmp = Path(temporary)/'bundle'
        tmp.mkdir()
        for name, data in expected.items():
            (tmp/name).write_bytes(data)
        os.rename(tmp, output)
    return payload


def construir_baseline_icc(root=ROOT, input_path=None):
    frame, source = cargar_entrada(root, input_path)
    refs = ajustar_referencias_icc(frame)
    economic = controles_economicos(refs)
    if not economic['pasa']:
        raise ValueError('Baseline falla controles económicos.')
    result = aplicar_baseline_icc(frame, refs)
    validar_baseline_icc(result)
    return result, {'referencias': refs, 'fuente': source, 'config_s1': CONFIG_S1,
                    'protocolo': comprobar_protocolo_icc(frame), 'economia': economic}


def exportar_baseline_icc(frame, metadata, root=ROOT, output_dir=None):
    if 'referencias' not in metadata:
        raise ValueError('Metodología S1 requiere referencias/proveniencia.')
    validar_referencias(metadata['referencias'])
    validar_baseline_icc(frame)
    output = Path(output_dir) if output_dir else directorio_modelo(root,frame)/'baseline'
    publicar_bundle(output, {'icc_baseline.csv': frame.to_csv(index=False).encode()},
                     'referencias_icc.json', metadata)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.check_only:
        frame, _ = cargar_entrada(args.root,args.input)
        print(json_bytes(comprobar_protocolo_icc(frame)).decode())
    else:
        frame, metadata = construir_baseline_icc(args.root,args.input)
        print(exportar_baseline_icc(frame,metadata,args.root,args.output_dir))


if __name__ == '__main__':
    main()
