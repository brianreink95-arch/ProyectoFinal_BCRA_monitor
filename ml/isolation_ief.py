"""Isolation Forest IEF 0.1: entrenar en train, congelar, puntuar y comparar.

python ml/isolation_ief.py entrenar
python ml/isolation_ief.py puntuar --model-dir CARPETA --output-dir DESTINO
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import spearmanr
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import ief, baseline_ief as baseline
from lib.common import require_unique, runtime_metadata, write_csv
from lib.relacional import booleanos

VERSION = '0.1'
RAW = 'ief_anomalia_cruda'
PERCENTIL = 'ief_percentil_train'
PARAMS = dict(n_estimators=300, max_samples='auto', max_features=1.0,
              contamination='auto', bootstrap=False, random_state=42, n_jobs=1)


def entorno():
    return {**runtime_metadata(), 'python_serie': '.'.join(platform.python_version_tuple()[:2]),
            'scikit_learn': sklearn.__version__, 'joblib': joblib.__version__, 'scipy': scipy.__version__}


def hash_frame(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode('utf-8-sig')).hexdigest()


def cargar_entrada(root=ROOT):
    """Consumir matriz y baseline existentes, verificados; nunca reajustarlos."""
    root = Path(root).resolve()
    frame, provenance = baseline.cargar_matriz(root)
    directory = root / 'data_analytics/modelos_ief' / provenance['run_origen'] / 'baseline_v0.1'
    path = directory / 'protocolo_baseline.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report['version_baseline'] != baseline.VERSION
            or report['features_sha256'] != provenance['features_sha256']
            or report['codigo_baseline_sha256'] != provenance['codigo_baseline_sha256']
            or report['prioridad_descendente'] != baseline.PRIORIDAD):
        raise ValueError('Bosque IEF: baseline incompatible.')
    if ief.sha256(directory / 'baseline_ief.csv') != report['baseline_sha256']:
        raise ValueError('Bosque IEF: baseline alterado.')
    frame = baseline.construir_baseline(frame)
    if hash_frame(frame) != report['baseline_sha256']:
        raise ValueError('Bosque IEF: reconstruccion del baseline diferente.')
    return frame, {**provenance, 'baseline_sha256': report['baseline_sha256'],
                   'protocolo_baseline_sha256': ief.sha256(path),
                   'codigo_bosque_sha256': ief.sha256(__file__)}


def validar_panel(frame, features):
    if frame.empty or frame[ief.KEY].isna().any().any():
        raise ValueError('Bosque IEF: panel vacio o clave nula.')
    require_unique(frame, ief.KEY, 'Bosque IEF')
    if not frame.cuit_normalizado.map(lambda value: isinstance(value, str)).all():
        raise ValueError('Bosque IEF: CUIT debe ser texto.')
    dates = pd.to_datetime(frame.fecha, format='%Y-%m-%d', errors='raise')
    if not dates.dt.is_month_start.all():
        raise ValueError('Bosque IEF: fecha distinta de inicio de mes.')
    expected = pd.Series('fuera_protocolo', index=frame.index)
    for name, (start, end) in ief.SPLITS.items():
        expected.loc[dates.between(start, end)] = name
    if not expected.eq(frame.split).all():
        raise ValueError('Bosque IEF: split incompatible con calendario fijado.')
    eligible = booleanos(frame.elegible_ief)
    if eligible.isna().any() or (eligible & frame.split.eq('fuera_protocolo')).any():
        raise ValueError('Bosque IEF: elegibilidad incompatible con protocolo.')
    if not set(features).issubset(frame.columns):
        raise ValueError('Bosque IEF: faltan predictores requeridos.')
    x = frame.loc[eligible, list(features)].astype(float)
    if not np.isfinite(x.to_numpy()).all():
        raise ValueError('Bosque IEF: predictor elegible ausente o no finito.')
    return eligible


def entrenar_modelo(frame, seed=42, features=ief.FEATURES_MODELO):
    """Unica funcion que ajusta un estimador y su referencia, solo en train."""
    features = tuple(features)
    if features not in (ief.FEATURES_MODELO, ief.FEATURES):
        raise ValueError('Bosque IEF: familia de predictores no fijada en el protocolo.')
    eligible = validar_panel(frame, features)
    train = frame.loc[eligible & frame.split.eq('train')].sort_values(ief.KEY)
    if len(train) < 2:
        raise ValueError('Bosque IEF: train elegible insuficiente.')
    x = train[list(features)].astype(float)
    params = {**PARAMS, 'random_state': seed}
    estimator = IsolationForest(**params).fit(x)
    reference = np.sort(-estimator.score_samples(x))
    return {
        'version_modelo': VERSION, 'estimator': estimator, 'features': list(features),
        'params': params, 'entorno': entorno(), 'referencia_train': reference,
        'filas_train': len(train), 'empresas_train': int(train.cuit_normalizado.nunique()),
        'train_desde': train.fecha.min(), 'train_hasta': train.fecha.max(),
        'train_sha256': hash_frame(train[[*ief.KEY, *features]]),
        'claves_train': list(train[ief.KEY].itertuples(index=False, name=None)),
        'percentil_regla': '100 * (n_referencia_menor + 0.5 * n_referencia_igual) / n_train',
    }


def percentil_train(values, reference):
    values, reference = np.asarray(values, dtype=float), np.asarray(reference, dtype=float)
    if (reference.ndim != 1 or not len(reference) or not np.isfinite(reference).all()
            or (np.diff(reference) < 0).any() or not np.isfinite(values).all()):
        raise ValueError('Bosque IEF: scores o referencia no validos.')
    left = np.searchsorted(reference, values, side='left')
    right = np.searchsorted(reference, values, side='right')
    return 100 * (left + .5 * (right - left)) / len(reference)


def agregar_rangos(frame):
    d = frame.copy()
    grouped = d.groupby('fecha', sort=False)[RAW]
    d['ief_posicion_desde'] = grouped.rank(method='min', ascending=False).astype('Int64')
    d['ief_posicion_hasta'] = grouped.rank(method='max', ascending=False).astype('Int64')
    d['ief_n_empatadas'] = d.ief_posicion_hasta - d.ief_posicion_desde + 1
    for k in baseline.TOP_K:
        d[f'ief_peso_top{k}'] = ((k - d.ief_posicion_desde + 1) / d.ief_n_empatadas).clip(0, 1).astype('Float64')
    return d


def puntuar(frame, artifact):
    """Solo score_samples: no fit, no recalibracion. Ranking por score crudo."""
    features = artifact['features']
    if tuple(features) not in (ief.FEATURES_MODELO, ief.FEATURES):
        raise ValueError('Bosque IEF: predictores del artefacto no compatibles.')
    estimator = artifact['estimator']
    if list(estimator.feature_names_in_) != features:
        raise ValueError('Bosque IEF: orden de predictores del estimador incorrecto.')
    eligible = validar_panel(frame, features)
    d = frame.copy().sort_values(ief.KEY).reset_index(drop=True)
    eligible = booleanos(d.elegible_ief)
    d[RAW], d[PERCENTIL] = np.nan, np.nan
    if eligible.any():
        scores = -estimator.score_samples(d.loc[eligible, features].astype(float))
        d.loc[eligible, RAW] = scores
        d.loc[eligible, PERCENTIL] = percentil_train(scores, artifact['referencia_train'])
    return agregar_rangos(d)


def correlacion(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    valid = np.isfinite(a) & np.isfinite(b)
    if valid.sum() < 2 or len(np.unique(a[valid])) < 2 or len(np.unique(b[valid])) < 2:
        return None
    return float(spearmanr(a[valid], b[valid]).statistic)


def media_valida(values):
    values = [x for x in values if x is not None]
    return float(np.mean(values)) if values else None


def comparar(frame, candidate=None):
    """Coincidencia fraccional top-k = sum(min(pesos)) / min(k, n_mes)."""
    monthly = []
    if candidate is not None and not frame[ief.KEY].equals(candidate[ief.KEY]):
        raise ValueError('Bosque IEF: comparacion de paneles desalineados.')
    for date, part in frame.groupby('fecha', sort=True):
        valid = part.loc[booleanos(part.elegible_ief)]
        row = {'fecha': date, 'split': part.split.iloc[0], 'elegibles': len(valid)}
        if not len(valid):
            row['spearman'] = None
            for k in baseline.TOP_K:
                row[f'coincidencia_top{k}'] = None
        else:
            if candidate is None:
                other = -(valid[baseline.RANK_MIN].astype(float) + valid[baseline.RANK_MAX].astype(float)) / 2
            else:
                other = candidate.loc[valid.index, RAW]
            row['spearman'] = correlacion(valid[RAW], other)
            for k in baseline.TOP_K:
                a = valid[f'ief_peso_top{k}'].to_numpy(dtype=float)
                b = (valid[f'baseline_peso_top{k}'] if candidate is None else
                     candidate.loc[valid.index, f'ief_peso_top{k}']).to_numpy(dtype=float)
                row[f'coincidencia_top{k}'] = float(np.minimum(a, b).sum() / min(k, len(valid)))
        monthly.append(row)
    blocks = {}
    for name in ief.SPLITS:
        rows = [r for r in monthly if r['split'] == name and r['elegibles']]
        blocks[name] = {'meses_con_ranking': len(rows),
                        'spearman_medio_mensual': media_valida([r['spearman'] for r in rows]),
                        **{f'coincidencia_top{k}_media_mensual': media_valida([r[f'coincidencia_top{k}'] for r in rows])
                           for k in baseline.TOP_K}}
    return {'por_bloque': blocks, 'por_mes': monthly}


def describir_scores(frame):
    summary = {}
    for name, part in frame.groupby('split', sort=True):
        valid = part.loc[booleanos(part.elegible_ief)]
        values = valid[RAW]
        summary[name] = {
            'filas': len(part), 'elegibles': len(valid), 'sin_score': len(part) - len(valid),
            'empresas_elegibles': int(valid.cuit_normalizado.nunique()),
            'crudo_min': float(values.min()) if len(valid) else None,
            'crudo_mediana': float(values.median()) if len(valid) else None,
            'crudo_max': float(values.max()) if len(valid) else None,
            'percentil_0': int(valid[PERCENTIL].eq(0).sum()),
            'percentil_100': int(valid[PERCENTIL].eq(100).sum()),
        }
    return summary


def diagnostico_componentes(frame):
    train = frame.loc[booleanos(frame.elegible_ief) & frame.split.eq('train'), list(ief.FEATURES_MODELO)]
    correlation = train.corr(method='spearman')
    pairs = [{'a': a, 'b': b, 'spearman_train': float(correlation.loc[a, b])}
             for i, a in enumerate(ief.FEATURES_MODELO) for b in ief.FEATURES_MODELO[i + 1:]]
    composition = []
    for date, part in frame.groupby('fecha', sort=True):
        valid = part.loc[booleanos(part.elegible_ief)]
        if len(valid):
            weight = valid.ief_peso_top5.to_numpy(dtype=float)
            composition.append({'fecha': date, 'split': part.split.iloc[0],
                                'fraccion_top5_situacion_2_mas': float(np.dot(weight, valid[baseline.SITUACION].ge(2)) / min(5, len(valid))),
                                'fraccion_top5_crecimiento_real_negativo': float(np.dot(weight, valid[ief.FEATURES[0]].lt(0)) / min(5, len(valid)))})
    return {'correlaciones_spearman_train': pairs, 'composicion_top5_mensual': composition,
            'interpretacion': 'Descriptores y redundancia entre variables; no contribuciones causales ni importancia del modelo.'}


def evaluar(frame, artifact):
    """Contrastes predefinidos; semilla 42 y transformacion log no se seleccionan."""
    main = puntuar(frame, artifact)
    stability = {}
    for seed in (43, 44):
        alternative = puntuar(frame, entrenar_modelo(frame, seed=seed))
        stability[str(seed)] = comparar(main, alternative)
    raw = puntuar(frame, entrenar_modelo(frame, features=ief.FEATURES))
    return main, {'comparacion_baseline': comparar(main), 'estabilidad_semillas': stability,
                  'sensibilidad_crecimiento_original': comparar(main, raw),
                  'distribucion_scores': describir_scores(main),
                  'diagnostico_componentes': diagnostico_componentes(main),
                  'regla_comparacion': 'media de meses; empates fraccionales, sin elegir empresas por CUIT',
                  'regla_seleccion': 'principal log y semilla 42 fijados; alternativas solo diagnostico',
                  'pendiente': ['Contraste secundario con deterioro t+1, separado de predictores.',
                                'Holdout por grupos y revision humana de fichas.',
                                'Notebook y graficos de la entrega final.']}


def informe(frame, report):
    lines = ['# Isolation Forest IEF 0.1 — resultado retrospectivo', '',
             'Se ajustó el bosque principal con 875 filas elegibles de train, seis predictores,',
             '300 árboles y semilla 42. Se preservaron las 2.400 filas; 353 quedan sin score.',
             'El score crudo es `-score_samples`: mayor valor significa mayor anomalía.',
             'El percentil 0–100 usa la distribución congelada de train, con empates a mitad de masa.',
             'No es probabilidad de default ni un índice de estrés validado.', '',
             '## Comparación con el baseline', '',
             '| Bloque | Filas puntuadas | Spearman mensual medio | Coincidencia top 5 | Coincidencia top 10 |',
             '| --- | ---: | ---: | ---: | ---: |']
    evaluation = report['evaluacion']
    for name, row in evaluation['comparacion_baseline']['por_bloque'].items():
        lines.append(f'| {name} | {evaluation["distribucion_scores"][name]["elegibles"]} | '
                     f'{row["spearman_medio_mensual"]:.4f} | '
                     f'{100 * row["coincidencia_top5_media_mensual"]:.2f}% | '
                     f'{100 * row["coincidencia_top10_media_mensual"]:.2f}% |')
    lines += ['', 'La coincidencia es `sum(min(peso_modelo, peso_comparador)) / min(k, n_mes)`.',
              'Se promedian meses con ranking. No es precisión predictiva. La correlación compara',
              'anomalía con prioridad descendente del baseline, conservando sus empates.', '',
              '## Estabilidad y sensibilidad', '',
              '| Diagnóstico, validación | Spearman mensual medio | Coincidencia top 5 |',
              '| --- | ---: | ---: |']
    for seed, results in evaluation['estabilidad_semillas'].items():
        row = results['por_bloque']['validacion']
        lines.append(f'| Principal vs. semilla {seed} | {row["spearman_medio_mensual"]:.4f} | '
                     f'{100 * row["coincidencia_top5_media_mensual"]:.2f}% |')
    row = evaluation['sensibilidad_crecimiento_original']['por_bloque']['validacion']
    lines.append(f'| Logarítmico vs. porcentual original | {row["spearman_medio_mensual"]:.4f} | '
                 f'{100 * row["coincidencia_top5_media_mensual"]:.2f}% |')
    lines += ['', 'Los diagnósticos no cambian la semilla ni la transformación principal.', '',
              '## Último mes, julio de 2026', '',
              '| Empresa | Anomalía cruda | Percentil train | Posición modelo | Posición baseline | Situación | Deuda en situación ≥2 |',
              '| --- | ---: | ---: | --- | --- | ---: | ---: |']
    latest = frame.loc[frame.fecha.eq(frame.fecha.max()) & frame.ief_peso_top5.gt(0)].sort_values('ief_posicion_desde')
    for _, row in latest.iterrows():
        lines.append(f'| {row.razon_social.replace("|", "/")} | {row[RAW]:.6f} | {row[PERCENTIL]:.2f} | '
                     f'{row.ief_posicion_desde}–{row.ief_posicion_hasta} | '
                     f'{row[baseline.RANK_MIN]}–{row[baseline.RANK_MAX]} | '
                     f'{int(row[baseline.SITUACION])} | {row[baseline.PROPORCION]:.6f}% |')
    diagnostic = evaluation['diagnostico_componentes']
    strongest = max(diagnostic['correlaciones_spearman_train'], key=lambda p: abs(p['spearman_train']))
    validation_mix = [r['fraccion_top5_situacion_2_mas'] for r in diagnostic['composicion_top5_mensual']
                      if r['split'] == 'validacion']
    lines += ['', 'El orden usa el score crudo: varios valores pueden saturar el percentil en 100',
              'sin quedar empatados en anomalía. Las filas excluidas mantienen score y pesos nulos.', '',
              '## Interpretación de las señales', '',
              f'La correlación de train más alta entre predictores es {strongest["spearman_train"]:.4f}',
              f'entre `{strongest["a"]}` y `{strongest["b"]}`. Las dos variables describen',
              'señales muy próximas y su redundancia limita la lectura multivariada.',
              f'En validación, {100 * np.mean(validation_mix):.2f}% de la participación del top 5',
              'corresponde a empresas con situación máxima activa ≥2. Son señales ya informadas,',
              'no prueba de anticipación. Estos descriptores no son importancia de variables ni causalidad.', '',
              '## Alcance y limitaciones', '',
              'Se describen rarezas de un panel sectorial intencional y retrospectivo. Las filas',
              'repiten empresas y no son observaciones independientes. El panel completo ya fue explorado;',
              'la evaluación posterior no es un test histórico intacto ni una validación prospectiva.',
              'El train puede contener empresas con dificultades; no es un conjunto de normalidad certificada.',
              'La coincidencia con mora ya informada no demuestra anticipación ni utilidad incremental.',
              'Crecimiento, contracción y concentración no tienen una dirección automática de riesgo.',
              'Los parámetros y la referencia se ajustaron exclusivamente en train. No se utilizó un target futuro.', '',
              'Quedan pendientes el contraste descriptivo t+1, el holdout por grupos, las fichas y la',
              'revisión de Brian antes de concluir sobre utilidad económica. Este resultado no habilita alertas.', '',
              '## Reproducción', '', 'Desde la raíz del proyecto:', '', '```bash',
              'python ml/isolation_ief.py entrenar --output-dir reproduccion_ief/bosque',
              'python ml/isolation_ief.py puntuar --model-dir reproduccion_ief/bosque --output-dir reproduccion_ief/score',
              '```', '', 'La puntuación carga el artefacto y verifica hashes y versiones antes de aplicarlo sin fit.',
              'Las referencias y el modelo principal están en `modelo_ief.joblib`; los modelos auxiliares',
              'no se guardan. Sus métricas completas permanecen en `protocolo_resultados.json`.']
    return '\n'.join(lines) + '\n'


@contextmanager
def publicacion(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root):
        protected = ['data_a', 'data_b', 'data_c', 'config', 'ml', 'lib', 'docs', 'analisis', 'experimentos']
        analytics = root / 'data_analytics'
        if (output == root or any(output.is_relative_to(root / p) for p in protected)
                or (output.is_relative_to(analytics) and not output.is_relative_to(analytics / 'modelos_ief'))):
            raise ValueError('Bosque IEF: destino protegido.')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.bosque_ief_', dir=output.parent))
    try:
        yield stage
        if output.exists():
            if (not output.is_dir() or {p.name for p in output.iterdir()} != {p.name for p in stage.iterdir()}
                    or any(ief.sha256(output / p.name) != ief.sha256(p) for p in stage.iterdir())):
                raise FileExistsError('Bosque IEF: bundle diferente; indicar otro --output-dir.')
        else:
            stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def ejecutar_entrenamiento(root=ROOT, output_dir=None):
    root = Path(root).resolve()
    frame, provenance = cargar_entrada(root)
    artifact = entrenar_modelo(frame)
    scores, evaluation = evaluar(frame, artifact)
    output = (Path(output_dir).resolve() if output_dir is not None else
              root / 'data_analytics/modelos_ief' / provenance['run_origen'] / f'bosque_v{VERSION}')
    with publicacion(root, output) as stage:
        model_path = stage / 'modelo_ief.joblib'
        joblib.dump(artifact, model_path, compress=3, protocol=5)
        write_csv(scores, stage / 'scores_ief.csv')
        reference = artifact['referencia_train']
        report = {
            'version_modelo': VERSION, 'modelo_entrenado': True, **provenance,
            'entorno': entorno(), 'params': artifact['params'], 'predictores_ordenados': artifact['features'],
            'filas_train': artifact['filas_train'], 'empresas_train': artifact['empresas_train'],
            'train_desde': artifact['train_desde'], 'train_hasta': artifact['train_hasta'],
            'train_sha256': artifact['train_sha256'], 'calibracion': artifact['percentil_regla'],
            'referencia_train_n': len(reference), 'referencia_train_min': float(reference.min()),
            'referencia_train_max': float(reference.max()),
            'referencia_train_sha256': hashlib.sha256(reference.tobytes()).hexdigest(),
            'score': '-score_samples; mayor = mayor anomalia',
            'ranking': 'score crudo por mes; empates exactos y top-k fraccional',
            'evaluacion': evaluation,
            'modelo_sha256': ief.sha256(model_path), 'scores_sha256': ief.sha256(stage / 'scores_ief.csv'),
        }
        (stage / 'protocolo_resultados.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'informe_ief.md').write_text(informe(scores, report), encoding='utf-8')
    return scores, report, output


def cargar_modelo(directory):
    """Leer un bundle propio verificado; las versiones se comprueban antes de joblib.load."""
    directory = Path(directory).resolve()
    report = json.loads((directory / 'protocolo_resultados.json').read_text(encoding='utf-8'))
    if report['version_modelo'] != VERSION or report['modelo_entrenado'] is not True:
        raise ValueError('Bosque IEF: version de modelo incompatible.')
    current = entorno()
    for key in ('python_serie', 'numpy', 'pandas', 'scikit_learn', 'joblib', 'scipy'):
        if report['entorno'][key] != current[key]:
            raise ValueError(f'Bosque IEF: recrear entorno de entrenamiento; version incompatible de {key}.')
    model_path = directory / 'modelo_ief.joblib'
    if ief.sha256(model_path) != report['modelo_sha256']:
        raise ValueError('Bosque IEF: modelo alterado.')
    artifact = joblib.load(model_path)
    reference = artifact['referencia_train']
    if (artifact['version_modelo'] != VERSION or artifact['features'] != report['predictores_ordenados']
            or artifact['params'] != PARAMS or artifact['estimator'].get_params() != IsolationForest(**PARAMS).get_params()
            or artifact['train_sha256'] != report['train_sha256']
            or len(reference) != report['referencia_train_n']
            or hashlib.sha256(reference.tobytes()).hexdigest() != report['referencia_train_sha256']):
        raise ValueError('Bosque IEF: artefacto no coincide con protocolo.')
    return artifact, report


def ejecutar_score(root=ROOT, model_dir=None, output_dir=None):
    root = Path(root).resolve()
    frame, provenance = cargar_entrada(root)
    parent = root / 'data_analytics/modelos_ief' / provenance['run_origen']
    model_dir = Path(model_dir).resolve() if model_dir is not None else parent / f'bosque_v{VERSION}'
    artifact, report = cargar_modelo(model_dir)
    for key in ('run_origen', 'features_sha256', 'baseline_sha256'):
        if report[key] != provenance[key]:
            raise ValueError('Bosque IEF: scoring sobre insumos distintos del protocolo congelado.')
    scores = puntuar(frame, artifact)
    output = Path(output_dir).resolve() if output_dir is not None else parent / f'score_bosque_v{VERSION}'
    with publicacion(root, output) as stage:
        write_csv(scores, stage / 'scores_ief.csv')
        metadata = {'version_modelo': VERSION, 'operacion': 'score_sin_fit', **provenance,
                    'modelo_sha256': report['modelo_sha256'], 'entorno': entorno(),
                    'scores_sha256': ief.sha256(stage / 'scores_ief.csv'),
                    'cobertura': describir_scores(scores)}
        (stage / 'protocolo_score.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return scores, metadata, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=['entrenar', 'puntuar'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.accion == 'entrenar':
        if args.model_dir is not None:
            parser.error('--model-dir corresponde a puntuar, no a entrenar.')
        scores, report, output = ejecutar_entrenamiento(args.root, args.output_dir)
    else:
        scores, report, output = ejecutar_score(args.root, args.model_dir, args.output_dir)
    print(f'Bosque IEF {VERSION}: {len(scores)} filas; {int(scores[RAW].notna().sum())} puntuadas.')
    print(f'Salida: {output}')


if __name__ == '__main__':
    main()
