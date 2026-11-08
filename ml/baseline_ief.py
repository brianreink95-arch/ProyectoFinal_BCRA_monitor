"""Baseline IEF 0.1: prioridad mensual lexicografica, sin parametros ajustados.

Consume la matriz tratada 0.2 congelada. No entrena Isolation Forest.
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

from ml import ief
from lib.common import require_unique, runtime_metadata, write_csv
from lib.relacional import booleanos

VERSION = '0.1'
SITUACION, PROPORCION, DELTA = ief.FEATURES[3:]
AUMENTO = 'baseline_aumento_3m_pp'
PRIORIDAD = [SITUACION, PROPORCION, AUMENTO]
RANK_MIN = 'baseline_posicion_desde'
RANK_MAX = 'baseline_posicion_hasta'
TIES = 'baseline_n_empatadas'
TOP_K = (5, 10)


def cargar_matriz(root=ROOT, features_dir=None):
    """Verificar bundle congelado y reconstruirlo sin refit ni modificarlo."""
    root = Path(root).resolve()
    tables, provenance = ief.leer_insumos(root)
    source = (Path(features_dir).resolve() if features_dir is not None else
              root / 'data_analytics/modelos_ief' / provenance['run_origen'] / 'v0.2')
    report_path = source / 'protocolo_resultados.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if (report['version_features'] != '0.2'
            or report['etapa'] != 'matriz_tratada_sin_modelo'
            or report['modelo_entrenado'] is not False
            or report['run_origen'] != provenance['run_origen']
            or report['predictores_ordenados'] != list(ief.FEATURES_MODELO)
            or report['splits_fijos'] != json.loads(json.dumps(ief.SPLITS))):
        raise ValueError('Baseline IEF: matriz o protocolo incompatible.')
    for name in ('codigo_sha256', 'dependencias_codigo_sha256', 'contrato_sha256', 'insumos_sha256'):
        if report[name] != provenance[name]:
            raise ValueError(f'Baseline IEF: procedencia de matriz incompatible: {name}')
    csv_path = source / 'features_ief.csv'
    if ief.sha256(csv_path) != report['features_sha256']:
        raise ValueError('Baseline IEF: matriz alterada.')
    original = ief.construir_matriz(tables['empresa_mes'], tables['empresas'])
    frame, _ = ief.tratar_matriz(original, referencias=report['tratamiento'])
    digest = hashlib.sha256(frame.to_csv(index=False).encode('utf-8-sig')).hexdigest()
    if digest != report['features_sha256']:
        raise ValueError('Baseline IEF: reconstruccion distinta de la matriz congelada.')
    return frame, {
        'run_origen': provenance['run_origen'], 'version_features': report['version_features'],
        'features_sha256': digest, 'protocolo_matriz_sha256': ief.sha256(report_path),
        'codigo_features_sha256': report['codigo_sha256'],
        'codigo_baseline_sha256': ief.sha256(__file__),
    }


def construir_baseline(frame):
    """Ranking por mes sobre el universo comun elegible, conservando empates."""
    d = frame.copy().sort_values(ief.KEY).reset_index(drop=True)
    if d.empty or d[ief.KEY].isna().any().any():
        raise ValueError('Baseline IEF: panel vacio o clave nula.')
    require_unique(d, ief.KEY, 'Baseline IEF')
    if not d.cuit_normalizado.map(lambda v: isinstance(v, str)).all():
        raise ValueError('Baseline IEF: CUIT debe ser texto.')
    dates = pd.to_datetime(d.fecha, format='%Y-%m-%d', errors='raise')
    if not dates.dt.is_month_start.all():
        raise ValueError('Baseline IEF: fecha distinta del inicio de mes.')
    eligible = booleanos(d.elegible_ief)
    if eligible.isna().any():
        raise ValueError('Baseline IEF: elegibilidad desconocida.')
    for col in (SITUACION, PROPORCION, DELTA):
        values = pd.to_numeric(d[col], errors='raise')
        if not np.isfinite(values.loc[eligible].to_numpy(dtype=float, na_value=np.nan)).all():
            raise ValueError(f'Baseline IEF: predictor elegible ausente/no finito: {col}')
        if col == SITUACION:
            invalid = ~values.loc[eligible].between(1, 6) | values.loc[eligible].mod(1).ne(0)
        elif col == PROPORCION:
            invalid = ~values.loc[eligible].between(0, 100 + 1e-8)
        else:
            invalid = ~values.loc[eligible].between(-100 - 1e-8, 100 + 1e-8)
        if invalid.any():
            raise ValueError(f'Baseline IEF: dominio invalido: {col}')
    # La mejora no suma prioridad en el tercer criterio; el delta original permanece.
    d[AUMENTO] = pd.to_numeric(d[DELTA]).clip(lower=0).where(eligible)
    keys = ['fecha', *PRIORIDAD]
    groups = (d.loc[eligible].groupby(keys, sort=False).size().rename(TIES).reset_index()
              .sort_values(keys, ascending=[True, False, False, False]))
    groups[RANK_MAX] = groups.groupby('fecha', sort=False)[TIES].cumsum()
    groups[RANK_MIN] = groups[RANK_MAX] - groups[TIES] + 1
    d = d.merge(groups, on=keys, how='left', sort=False, validate='many_to_one')
    for col in (RANK_MIN, RANK_MAX, TIES):
        d[col] = d[col].where(eligible).astype('Int64')
    for k in TOP_K:
        # Una fraccion igual por empresa en el empate que atraviesa la frontera k.
        d[f'baseline_peso_top{k}'] = ((k - d[RANK_MIN] + 1) / d[TIES]).clip(0, 1).astype('Float64')
    d = d.sort_values(ief.KEY).reset_index(drop=True)
    for _, part in d.groupby('fecha', sort=True):
        active = part.loc[booleanos(part.elegible_ief)]
        for k in TOP_K:
            if not np.isclose(active[f'baseline_peso_top{k}'].sum(), min(k, len(active)), rtol=0, atol=1e-10):
                raise ValueError('Baseline IEF: masa top-k inconsistente.')
    return d


def resumir_baseline(frame):
    months = []
    for date, part in frame.groupby('fecha', sort=True):
        valid = part.loc[booleanos(part.elegible_ief)]
        groups = valid[PRIORIDAD].drop_duplicates()
        row = {'fecha': date, 'split': part.split.iloc[0], 'filas': len(part),
               'elegibles': len(valid), 'no_elegibles': len(part) - len(valid),
               'niveles_prioridad': len(groups),
               'mayor_empate': int(valid[TIES].max()) if len(valid) else 0,
               'situacion_2_mas': int(valid[SITUACION].ge(2).sum())}
        for k in TOP_K:
            w = valid[f'baseline_peso_top{k}']
            row[f'empresas_con_peso_top{k}'] = int(w.gt(0).sum())
            row[f'masa_top{k}'] = round(float(w.sum()), 12)
            row[f'empresas_con_peso_fraccional_top{k}'] = int((w.gt(0) & w.lt(1)).sum())
        months.append(row)
    return months


def ejecutar(root=ROOT, output_dir=None, features_dir=None):
    root = Path(root).resolve()
    frame, provenance = cargar_matriz(root, features_dir)
    baseline = construir_baseline(frame)
    output = (Path(output_dir).resolve() if output_dir is not None else
              root / 'data_analytics/modelos_ief' / provenance['run_origen'] / f'baseline_v{VERSION}')
    if output.is_relative_to(root):
        protected = ['data_a', 'data_b', 'data_c', 'config', 'ml', 'lib', 'docs', 'analisis', 'experimentos']
        analytics = root / 'data_analytics'
        if (output == root or any(output.is_relative_to(root / p) for p in protected)
                or (output.is_relative_to(analytics) and not output.is_relative_to(analytics / 'modelos_ief'))):
            raise ValueError('Baseline IEF: destino protegido.')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.baseline_ief_', dir=output.parent))
    try:
        csv_path = stage / 'baseline_ief.csv'
        write_csv(baseline, csv_path)
        report = {
            'version_baseline': VERSION, 'tipo': 'prioridad_lexicografica_mensual',
            'modelo_entrenado': False, 'parametros_ajustados': False,
            **provenance, 'entorno': runtime_metadata(),
            'prioridad_descendente': PRIORIDAD,
            'aumento_3m': 'max(delta_pct_deuda_situacion_2_mas_3m_pp, 0)',
            'universo': 'mismas filas elegibles que la matriz tratada 0.2',
            'empates': 'igualdad exacta de los tres criterios, sin redondeo ni desempate por CUIT',
            'posiciones': '1 es primera prioridad; intervalo cerrado para empates',
            'peso_top_k': 'clip((k - posicion_desde + 1) / n_empatadas, 0, 1)',
            'interpretacion_peso': 'participacion en capacidad de revision; no probabilidad ni riesgo',
            'sin_ranking': 'filas no elegibles conservadas con motivos originales y posiciones/pesos nulos',
            'limites': ['No es probabilidad de default ni indice de estres validado.',
                        'La situacion maxima tiene prioridad incluso si la proporcion afectada es pequena.',
                        'Resume deterioro observado; no demuestra anticipacion ni utilidad incremental.',
                        'Panel retrospectivo sectorial, sin disponibilidad historica contemporanea verificada.'],
            'filas': len(baseline), 'elegibles': int(baseline.elegible_ief.sum()),
            'cobertura': ief.resumir(baseline), 'resumen_mensual': resumir_baseline(baseline),
            'baseline_sha256': ief.sha256(csv_path),
        }
        (stage / 'protocolo_baseline.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            if (not output.is_dir() or {p.name for p in output.iterdir()} != {p.name for p in stage.iterdir()}
                    or any(ief.sha256(output / p.name) != ief.sha256(p) for p in stage.iterdir())):
                raise FileExistsError('Baseline IEF: bundle diferente; indicar otro --output-dir.')
        else:
            stage.rename(output)
        return baseline, report, output
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--features-dir', type=Path, help='Bundle tratado 0.2, ya congelado.')
    parser.add_argument('--output-dir', type=Path, help='Destino nuevo para reproducir sin sobrescribir.')
    args = parser.parse_args()
    frame, report, output = ejecutar(args.root, args.output_dir, args.features_dir)
    print(f'Baseline IEF {VERSION}: {len(frame)} filas; {report["elegibles"]} prioridades mensuales.')
    print(f'Salida: {output}')


if __name__ == '__main__':
    main()
