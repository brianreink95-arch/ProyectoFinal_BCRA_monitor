"""Evaluación descriptiva ICC: train para diagnóstico, validación para contraste.

Uso habitual: python ml/evaluate_features.py
CSV independiente: python ml/evaluate_features.py --input ruta/icc.csv
No adquiere datos, imputa, selecciona automáticamente ni ajusta el índice.
"""
from pathlib import Path
from itertools import combinations
import argparse
import csv
import hashlib
import html
import json
import re
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml.features import (FEATURES_ICC, PARTICIPACIONES_ICC, STOCK_REAL,
                         DELTA_STOCK_REAL, ACELERACION_REAL, validar_matriz_icc,
                         elegibilidad_features, VERSION_ICC)
from ml.baseline import (CORTES_ICC, MIN_TRAIN, VERSION_PROTOCOLO,
                         asignar_splits_icc, comprobar_protocolo_icc, leer_matriz_icc)

VERSION_EVALUACION = '1.1'
G1, G3, G12 = (f'credito_var_real_{k}m_pct' for k in (1, 3, 12))
RATE, RATE_DELTA = 'tasa_uva_tna_pct', 'tasa_uva_delta_3m_pp'
VOL = 'credito_volatilidad_real_6m_pp'
ETIQUETAS = {
    STOCK_REAL: ('Stock real', 'Volumen', 'millones ARS dic. 2016', 'Mayor volumen; referencia S1 documentada'),
    G1: ('Crecimiento real 1m', 'Dinámica', '%', 'Mayor crecimiento'),
    G3: ('Crecimiento real 3m', 'Dinámica', '%', 'Mayor crecimiento'),
    G12: ('Crecimiento real 12m', 'Dinámica', '%', 'Mayor crecimiento'),
    DELTA_STOCK_REAL: ('Cambio absoluto 3m', 'Volumen', 'millones ARS dic. 2016', 'Mayor expansión del saldo'),
    ACELERACION_REAL: ('Aceleración 3m', 'Dinámica', 'pp', 'Mayor aceleración, condicionada al nivel'),
    RATE: ('TNA UVA', 'Costo parcial', '% anual sobre UVA', 'Menor tasa, con igual volumen'),
    RATE_DELTA: ('Cambio TNA UVA 3m', 'Costo parcial', 'pp', 'Menor cambio, con igual volumen'),
    VOL: ('Volatilidad real 6m', 'Descriptor', 'pp', 'Sin orientación automática'),
    **{name: (label, 'Composición', '%', 'Sin orientación automática')
       for name, label in zip(PARTICIPACIONES_ICC.values(),
                              ('Construcción', 'Refacción', 'Compra nuevas', 'Compra usadas', 'Otras'))},
}
# Hipótesis de cobertura; este evaluador no aprueba métodos automáticamente.
CONJUNTOS = {
    'nucleo_volumen_dinamica_costo': (STOCK_REAL, G3, RATE),
    'nucleo_con_cambio_tasa': (STOCK_REAL, G3, RATE, RATE_DELTA),
    'sensibilidad_cambio_absoluto': (STOCK_REAL, DELTA_STOCK_REAL, RATE),
    'sensibilidad_horizonte_anual': (STOCK_REAL, G12, RATE),
    'sensibilidad_aceleracion': (STOCK_REAL, G3, RATE, ACELERACION_REAL),
    'todas_candidatas': FEATURES_ICC,
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cargar_csv(path):
    """Revisa esquema y procedencia declarada; no reconstruye fuentes externas."""
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        names = next(csv.reader(handle), [])
    if len(names) != len(set(names)):
        raise ValueError('CSV con columnas duplicadas.')
    strings = {name: 'string' for name in names if name.startswith(('motivo_', 'motivos_'))
               or name.endswith('_sha256')
               or name in ('version_features', 'version_contrato', 'run_origen', 'fecha_mes',
                           'medida_credito', 'unidad_stock_constante')}
    frame = pd.read_csv(path, dtype=strings)
    for name in strings:
        if name.startswith(('motivo_', 'motivos_')):
            frame[name] = frame[name].fillna('')
    required = {*FEATURES_ICC, 'version_features', 'version_contrato', 'run_origen',
                'medida_credito', 'unidad_stock_constante', 'deflactor_sha256',
                'observaciones_sha256', 'series_sha256', 'contrato_sha256',
                'codigo_features_sha256'}
    if not required.issubset(frame.columns):
        raise ValueError('CSV incompleto para evaluar ICC 3.0.')
    for name in FEATURES_ICC:
        frame[name] = pd.to_numeric(frame[name], errors='raise')
    for name in ('candidatas_completas', 'elegible_icc', 'elegible_comparacion_2_0',
                 'elegible_baseline_historico'):
        if name not in frame or not frame[name].map(lambda x: isinstance(x, (bool, np.bool_))).all():
            raise ValueError(f'Flag de elegibilidad no booleano: {name}')
    for name in required - set(FEATURES_ICC):
        if frame[name].isna().any() or frame[name].nunique() != 1:
            raise ValueError(f'Procedencia nula o mezclada: {name}')
    if (frame['version_features'].iloc[0] != VERSION_ICC
            or frame['version_contrato'].iloc[0] != '2.0'
            or frame['unidad_stock_constante'].iloc[0] != 'millones_ARS_dic2016'):
        raise ValueError('Versión, contrato o unidad de stock incompatible.')
    for name in required:
        if name.endswith('_sha256') and not re.fullmatch(r'[0-9a-f]{64}', str(frame[name].iloc[0])):
            raise ValueError(f'Hash declarado inválido: {name}')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', str(frame['run_origen'].iloc[0])):
        raise ValueError('Identificador de corrida inválido.')
    validar_matriz_icc(frame)
    return frame


def numero(value):
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def correlacion(x, y, metodo='pearson', minimo=24):
    pair = pd.concat([x, y], axis=1).dropna()
    n = len(pair)
    if n < minimo:
        return {'n': n, 'valor': None, 'motivo': 'pocos_meses'}
    if pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return {'n': n, 'valor': None, 'motivo': 'variable_constante'}
    if metodo == 'spearman':
        pair = pair.rank(method='average')
    elif metodo != 'pearson':
        raise ValueError('Método de correlación desconocido.')
    return {'n': n, 'valor': numero(pair.iloc[:, 0].corr(pair.iloc[:, 1])), 'motivo': ''}


def resumen_variable(block, name):
    values = block[name].dropna()
    n = len(values)
    q1, median, q3 = (values.quantile(q) if n else np.nan for q in (.25, .5, .75))
    iqr = q3 - q1
    extreme = values.lt(q1 - 1.5 * iqr) | values.gt(q3 + 1.5 * iqr) if n else pd.Series(dtype=bool)
    # shift sobre calendario conservado: un hueco no pasa a ser un mes adyacente.
    lag = correlacion(block[name], block[name].shift(1), minimo=18)
    return {'n': n, 'meses_calendario': len(block), 'ausentes': len(block) - n,
            'primera_fecha': block.loc[block[name].notna(), 'fecha_mes'].min() if n else None,
            'ultima_fecha': block.loc[block[name].notna(), 'fecha_mes'].max() if n else None,
            'media': numero(values.mean()), 'mediana': numero(median),
            'desvio_muestral': numero(values.std(ddof=1)),
            'min': numero(values.min()), 'max': numero(values.max()),
            'q1': numero(q1), 'q3': numero(q3), 'iqr': numero(iqr),
            'n_unicos': int(values.nunique()), 'n_ceros': int(values.eq(0).sum()),
            'n_negativos': int(values.lt(0).sum()),
            'n_extremos_iqr': int(extreme.sum()),
            'fechas_extremos_iqr': block.loc[values.index[extreme], 'fecha_mes'].tolist(),
            'autocorrelacion_1m': lag,
            'fecha_min': block.loc[values.idxmin(), 'fecha_mes'] if n else None,
            'fecha_max': block.loc[values.idxmax(), 'fecha_mes'] if n else None}


def limites_mitades(train):
    first, last = pd.Period(train['fecha_mes'].min(), 'M'), pd.Period(train['fecha_mes'].max(), 'M')
    calendar = pd.period_range(first, last, freq='M')
    return str(calendar[(len(calendar) + 1) // 2 - 1].to_timestamp('M').date())


def pares_train(train, minimo, fin_primera_mitad=None):
    # La muestra común conserva exactamente los cortes de la muestra completa.
    boundary = fin_primera_mitad or limites_mitades(train)
    early = train.loc[train['fecha_mes'].le(boundary)]
    late = train.loc[train['fecha_mes'].gt(boundary)]
    rows = []
    for a, b in combinations(FEATURES_ICC, 2):
        p = correlacion(train[a], train[b], minimo=minimo)
        s = correlacion(train[a], train[b], 'spearman', minimo)
        first = correlacion(early[a], early[b], 'spearman', 18)
        second = correlacion(late[a], late[b], 'spearman', 18)
        x, y = first['valor'], second['valor']
        rows.append({'a': a, 'b': b, 'pearson': p, 'spearman': s,
                     'primera_mitad_spearman': first, 'segunda_mitad_spearman': second,
                     'alerta_correlacion_alta': any(abs(v) >= .85 for v in (p['valor'], s['valor']) if v is not None),
                     'cambio_signo_entre_mitades': (x is not None and y is not None
                                                  and x * y < 0 and min(abs(x), abs(y)) >= .15)})
    return rows


def contraste_validacion(train_stats, validation, name):
    reference = train_stats[name]
    values = validation[name].dropna()
    if not reference['n'] or not len(values):
        return {'n': len(values), 'fuera_rango_train_n': None, 'fuera_rango_train_pct': None,
                'cambio_mediana_en_iqr_train': None, 'motivo': 'sin_referencia_o_validacion'}
    out = values.lt(reference['min']) | values.gt(reference['max'])
    return {'n': len(values), 'fuera_rango_train_n': int(out.sum()),
            'fuera_rango_train_pct': float(100 * out.mean()),
            'cambio_mediana_en_iqr_train': numero((values.median() - reference['mediana']) / reference['iqr'])
            if reference['iqr'] > 0 else None,
            'motivo': '' if reference['iqr'] > 0 else 'iqr_train_cero'}


def evaluar(frame, minimo_pares=24):
    if minimo_pares < 3:
        raise ValueError('Mínimo de pares debe ser al menos 3.')
    split = asignar_splits_icc(frame)
    train = frame.loc[split.eq('train')].copy()
    validation = frame.loc[split.eq('validacion')].copy()
    if train.empty:
        raise ValueError('Sin calendario de entrenamiento en el CSV.')
    stats = {name: resumen_variable(train, name) for name in FEATURES_ICC}
    common = train.loc[train[list(FEATURES_ICC)].notna().all(axis=1)]
    boundary = limites_mitades(train)
    profiles = {}
    # Los bloques posteriores aportan solo cobertura, jamás estadísticas de selección.
    for label, required in CONJUNTOS.items():
        available, _ = elegibilidad_features(frame, required)
        counts = {role: int((available & split.eq(role)).sum()) for role in CORTES_ICC}
        profiles[label] = {'features': list(required), 'meses_por_split': counts,
                           'cumple_minimo_train': counts['train'] >= MIN_TRAIN,
                           'seleccion_aprobada': False}
    shares = train[list(PARTICIPACIONES_ICC.values())].sum(axis=1, min_count=5)
    # Esta igualdad solo comprueba identidades dentro del CSV; no audita IPC original.
    actual = frame.set_index(pd.PeriodIndex(frame['fecha_mes'], freq='M'))
    r = actual[STOCK_REAL]
    identities = {}
    formula = {G1: 100 * (r / r.shift(1) - 1), G3: 100 * (r / r.shift(3) - 1),
               G12: 100 * (r / r.shift(12) - 1), DELTA_STOCK_REAL: r - r.shift(3),
               ACELERACION_REAL: actual[G3] - actual[G3].shift(3),
               VOL: actual[G1].rolling(6, min_periods=6).std(ddof=0),
               RATE_DELTA: actual[RATE] - actual[RATE].shift(3)}
    # Verificación estructural sobre valores disponibles, incluyendo todos los bloques.
    # No devuelve magnitudes/fechas retrospectivas al análisis económico.
    for name, expected in formula.items():
        valid = actual[name].notna()
        ok = expected.loc[valid].notna().all() and np.allclose(actual.loc[valid, name], expected.loc[valid], rtol=1e-10, atol=1e-9)
        if not ok:
            raise ValueError(f'Identidad de feature incompatible: {name}')
        identities[name] = {'n_comprobados': int(valid.sum()), 'coincide': True}
    return {'version_evaluacion': VERSION_EVALUACION, 'version_features': VERSION_ICC,
            'version_protocolo': VERSION_PROTOCOLO, 'min_pares_correlacion': minimo_pares,
            'criterios_alerta': {'correlacion_alta_abs': .85, 'min_pares_mitades': 18,
                                'min_abs_para_cambio_signo': .15, 'extremos_iqr_factor': 1.5},
            'cortes_calendario': {k: {'desde': v[0], 'hasta': v[1]} for k, v in CORTES_ICC.items()},
            'min_train': MIN_TRAIN, 'protocolo': comprobar_protocolo_icc(frame),
            'meses_calendario': {role: int(split.eq(role).sum()) for role in CORTES_ICC},
            'train': {'estadisticas': stats, 'fin_primera_mitad': boundary,
                      'pares': pares_train(train, minimo_pares, boundary),
                      'meses_muestra_comun_14': len(common),
                      'pares_muestra_comun_14': pares_train(common, minimo_pares, boundary),
                      'suma_participaciones': {'n': int(shares.notna().sum()),
                                               'max_desvio_100_pp': numero((shares - 100).abs().max()),
                                               'desvio_muestral_pp': numero(shares.std(ddof=1))}},
            'validacion': {'contrastes': {name: contraste_validacion(stats, validation, name) for name in FEATURES_ICC}},
            'conjuntos_propuestos': profiles,
            'identidades_internas_csv': identities,
            'trayectorias_train_validacion': {name: [
                {'fecha': row['fecha_mes'], 'valor': numero(row[name]), 'bloque': str(split.loc[i])}
                for i, row in frame.loc[split.isin(['train', 'validacion'])].iterrows()]
                for name in FEATURES_ICC},
            'seleccion_automatica': False, 'modelo_entrenado': False,
            'limitaciones': ['Stock es saldo vigente, no otorgamientos, oferta ni acceso individual.',
                             'Saldo PH y TNA UVA de otorgamientos al sector privado son poblaciones distintas.',
                             'Meses autocorrelacionados: conteo de filas no es tamaño independiente de muestra.',
                             'Correlación alta orienta revisión, no prueba equivalencia ni causalidad.',
                             'Extremos IQR son descriptivos: no se borran ni winsorizan.',
                             'Retrospectiva y reserva excluidas de estadísticas, gráficos y decisiones de selección.',
                             'Los cortes de referencia no certifican disponibilidad histórica sin vintages.']}


def fmt(value, decimals=2):
    if value is None:
        return 'No disponible'
    return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def tabla(headers, rows):
    return '<table><thead><tr>' + ''.join(f'<th>{html.escape(str(x))}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table>'


def grafico_svg(points, label, unit):
    """Línea con cortes en los nulos. No conecta a través de meses ausentes."""
    finite = [p['valor'] for p in points if p['valor'] is not None]
    if not finite:
        return '<p>Sin valores disponibles en train/validación.</p>'
    bottom, top = min(0, min(finite)), max(0, max(finite))
    if top == bottom:
        top = bottom + 1
    left, right, ytop, ybottom = 90, 850, 35, 210
    def xy(i, value):
        return left + (right-left) * i / max(1, len(points)-1), ybottom - (value-bottom)/(top-bottom)*(ybottom-ytop)
    paths, segment = [], []
    for i, point in enumerate(points):
        if point['valor'] is None:
            if segment: paths.append(segment); segment=[]
        else:
            x, y = xy(i, point['valor']); segment.append(f'{x:.2f},{y:.2f}')
    if segment:paths.append(segment)
    lines = ''.join(f'<polyline points="{" ".join(path)}" fill="none" stroke="#245c83" stroke-width="2.5"/>' for path in paths)
    grid = ''
    for k in range(5):
        value = bottom + (top-bottom)*k/4; _, y = xy(0, value)
        grid += f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#d9e0e6"/><text x="78" y="{y+5}" text-anchor="end">{fmt(value,1)}</text>'
    cutoff = next((i for i,p in enumerate(points) if p['bloque']=='validacion'), None)
    if cutoff is not None:
        x, _ = xy(cutoff-.5, bottom)
        grid += f'<line x1="{x}" y1="{ytop}" x2="{x}" y2="{ybottom}" stroke="#995a2a" stroke-dasharray="5 4"/>'
    dates = ''.join(f'<text x="{xy(i,bottom)[0]}" y="242" text-anchor="middle">{points[i]["fecha"][:7]}</text>' for i in sorted(set((0,len(points)//2,len(points)-1))))
    return f'<svg viewBox="0 0 900 260" role="img" aria-label="{html.escape(label)}"><title>{html.escape(label)} ({html.escape(unit)})</title>{grid}{lines}{dates}</svg>'


def render_informe(result):
    stats=result['train']['estadisticas']; contrast=result['validacion']['contrastes']
    nucleus=result['conjuntos_propuestos']['nucleo_volumen_dinamica_costo']
    coverage = tabla(['Conjunto propuesto','Train','Validación','Retrospectiva: cobertura','Mínimo 60'], [
        [label.replace('_',' '), *p['meses_por_split'].values(), 'Cumple' if p['cumple_minimo_train'] else 'Insuficiente']
        for label,p in result['conjuntos_propuestos'].items()])
    dictionary = tabla(['Candidata','Dimensión','Dirección económica propuesta','Estado'], [
        [ETIQUETAS[name][0],ETIQUETAS[name][1],ETIQUETAS[name][3],
         'Núcleo propuesto' if name in nucleus['features'] else ('Sensibilidad de costo' if name==RATE_DELTA else 'Revisar como alternativa/descriptor')]
        for name in FEATURES_ICC])
    summaries=tabla(['Variable','Unidad','N train','Mediana','Mínimo','Máximo','Extremos IQR','Autocorr. 1m'],[
        [ETIQUETAS[name][0],ETIQUETAS[name][2],s['n'],fmt(s['mediana']),fmt(s['min']),fmt(s['max']),s['n_extremos_iqr'],fmt(s['autocorrelacion_1m']['valor'])]
        for name,s in stats.items()])
    alerts=[r for r in result['train']['pares'] if r['alerta_correlacion_alta']]
    alerts.sort(key=lambda r:max(abs(r[k]['valor']) if r[k]['valor'] is not None else 0 for k in ('pearson','spearman')),reverse=True)
    correlations=tabla(['Par','N','Pearson','Spearman','Spearman primera mitad','Spearman segunda mitad'],[
        [ETIQUETAS[r['a']][0]+' / '+ETIQUETAS[r['b']][0],r['pearson']['n'],fmt(r['pearson']['valor'],3),fmt(r['spearman']['valor'],3),
         fmt(r['primera_mitad_spearman']['valor'],3),fmt(r['segunda_mitad_spearman']['valor'],3)] for r in alerts])
    sign_changes=[r for r in result['train']['pares'] if r['cambio_signo_entre_mitades']]
    stability=tabla(['Par con cambio de signo','N primera mitad','Spearman primera','N segunda mitad','Spearman segunda'],[
        [ETIQUETAS[r['a']][0]+' / '+ETIQUETAS[r['b']][0],r['primera_mitad_spearman']['n'],fmt(r['primera_mitad_spearman']['valor'],3),
         r['segunda_mitad_spearman']['n'],fmt(r['segunda_mitad_spearman']['valor'],3)] for r in sign_changes])
    comparison=[]
    common_lookup={(r['a'],r['b']):r for r in result['train']['pares_muestra_comun_14']}
    for a,b in ((G1,G3),(G3,DELTA_STOCK_REAL),(G3,G12),(STOCK_REAL,RATE)):
        pair=next(r for r in result['train']['pares'] if {r['a'],r['b']}=={a,b})
        shared=common_lookup[(pair['a'],pair['b'])]
        comparison.append([ETIQUETAS[a][0]+' / '+ETIQUETAS[b][0],pair['pearson']['n'],fmt(pair['pearson']['valor'],3),
                           shared['pearson']['n'],fmt(shared['pearson']['valor'],3)])
    common_table=tabla(['Comparación','N por par','Pearson por par','N común','Pearson común'],comparison)
    validation=tabla(['Variable','N validación','Fuera del rango de train','% fuera','Cambio de mediana / IQR train'],[
        [ETIQUETAS[name][0],v['n'],v['fuera_rango_train_n'],fmt(v['fuera_rango_train_pct'],1),fmt(v['cambio_mediana_en_iqr_train'])]
        for name,v in contrast.items()])
    trajectories=''.join(f'<section class="plot"><h3>{html.escape(ETIQUETAS[name][0])}</h3><p>{html.escape(ETIQUETAS[name][2])}</p>{grafico_svg(points,ETIQUETAS[name][0],ETIQUETAS[name][2])}</section>' for name,points in result['trayectorias_train_validacion'].items())
    limitations='<ul>'+''.join(f'<li>{html.escape(s)}</li>' for s in result['limitaciones'])+'</ul>'
    provenance=result['procedencia']
    return f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Evaluación de candidatas ICC</title>
<style>body{{font:17px system-ui,sans-serif;color:#182b3a;background:#f8fafc;margin:0}}main{{max-width:1140px;margin:auto;padding:42px 28px}}h1{{font-size:38px}}h2{{font-size:26px;margin-top:46px;color:#204b6b}}h3{{margin-bottom:4px}}p,li{{line-height:1.6}}table{{border-collapse:collapse;width:100%;font-size:14px;background:white;margin:18px 0}}th{{background:#204b6b;color:white;text-align:left}}th,td{{padding:10px 12px;border-bottom:1px solid #d7e1e8}}td:nth-child(n+2){{font-variant-numeric:tabular-nums}}.plot{{margin:28px 0}}svg{{width:100%;background:white;font:15px system-ui,sans-serif}}code{{overflow-wrap:anywhere}}@media print{{section,table{{break-inside:avoid}}body{{background:white}}}}</style>
<main><h1>Evaluación de candidatas ICC</h1><p>Corrida {html.escape(provenance['run_origen'])}. Features 3.0. Protocolo temporal {result['version_protocolo']}.</p>
<h2>Qué aporta esta evaluación</h2><p>Revisa las 14 candidatas y sus coberturas. La propuesta económica inicial combina stock real, crecimiento real trimestral y TNA UVA. Tiene {nucleus['meses_por_split']['train']} meses train, sin exigir las 14 juntas. El consumidor S1 ya fue adoptado explícitamente en D22; su método y resultados se documentan en criterios_datos.md. Este diagnóstico no toma esa decisión ni ejecuta entrenamiento.</p>
<p>La TNA UVA describe costo parcial. El stock mide saldo vigente. No hay una medición directa de acceso individual. Esta evaluación conserva todas las variables y no entrena modelos.</p>
<h2>Separación temporal</h2><p>Train: agosto 2016–febrero 2022. Validación: marzo 2022–diciembre 2023. Retrospectiva 2024–junio 2026 aporta solo conteos de cobertura. La reserva posterior queda fuera del análisis económico. Las estadísticas y gráficos económicos usan exclusivamente train/validación. Las identidades matemáticas se verifican en todo el CSV como control estructural.</p>
{coverage}<p>Los conjuntos son hipótesis para revisar. El mínimo sigue en 60 meses. Ninguna selección queda aprobada por cumplirlo.</p>
<h2>Propuesta para discutir</h2>{dictionary}<p>Comparar crecimiento mensual/trimestral y cambio absoluto como alternativas evita dar varios votos a la misma dinámica. Las cinco participaciones casi suman 100: describen destinos, sin dirección de favorabilidad aprobada. El cambio de tasa es una sensibilidad opcional de costo. La decisión D22 fija R/g3/r y el método S1; las otras columnas siguen disponibles como alternativas o descriptores.</p>
<h2>Comportamiento en train</h2>{summaries}<p>Extremos: regla exploratoria 1,5 × IQR, sin eliminar ni modificar datos. Autocorrelación: pares de meses adyacentes, con al menos 18 observaciones y calendario intacto.</p>
<h2>Redundancia en train</h2>{correlations}<p>Alertas con |Pearson| o |Spearman| ≥ 0,85, al menos {result['min_pares_correlacion']} meses por par. El N cambia entre pares por sus ventanas. El diagnóstico JSON también incluye una comparación sobre los {result['train']['meses_muestra_comun_14']} meses comunes de las 14. Esa muestra sirve para comparar correlaciones, no fija el train del modelo.</p>
<p>Las mitades dividen el calendario de train. Requieren 18 pares cada una. Las correlaciones pueden cambiar entre etapas y no demuestran causalidad. No se reportan p-valores que supongan meses independientes.</p>
<h2>Sensibilidad temporal y de muestra</h2>{common_table}<p>Comparación sobre meses disponibles por par y sobre una misma muestra completa. Ambas usan train. La primera mitad termina en {result["train"]["fin_primera_mitad"]} en los dos diagnósticos.</p>{stability}<p>Se muestran cambios de signo cuando ambas mitades tienen al menos 18 pares y |Spearman| ≥ 0,15. Es una alerta exploratoria de dependencia temporal, sin selección automática.</p><h2>Contraste en validación</h2>{validation}<p>Referencias mínimo, máximo e IQR provienen solo de train. Un valor fuera del rango indica cambio de distribución, no un error. No se reajustan referencias ni se elige una selección por estos resultados.</p>
<p>Stock fuera del rango train: {contrast[STOCK_REAL]["fuera_rango_train_n"]}/{contrast[STOCK_REAL]["n"]} meses. TNA UVA fuera del rango: {contrast[RATE]["fuera_rango_train_n"]}/{contrast[RATE]["n"]}. Un percentil empírico fijo llega a 0/100 fuera de ese rango y pierde magnitud del extremo. Esto requiere revisar el diseño de la referencia, sin recalibrarla con validación.</p><h2>Trayectorias</h2><p>Gráficos de train y validación. La línea vertical marca el comienzo de validación. Las ausencias interrumpen las líneas. Cada eje conserva su unidad.</p>{trajectories}
<h2>Alcance y límites</h2>{limitations}<p>Modo de lectura: {html.escape(provenance['modo_lectura'])}. Verificación de fuentes reconstruidas: {provenance['fuentes_reconstruidas']}. Con un CSV independiente se validan su contrato y las identidades internas; los hashes declarados no prueban los archivos originales no adjuntos.</p>
<details><summary>Reproducibilidad</summary><p>SHA256 CSV: <code>{provenance['csv_sha256']}</code></p><p>SHA256 código de evaluación: <code>{provenance['codigo_evaluacion_sha256']}</code></p><p>Las salidas conservan versiones, cortes, parámetros y hashes. Misma entrada y código producen los mismos bytes.</p></details></main></html>'''


def construir_evaluacion(root=ROOT, input_path=None, minimo_pares=24):
    root=Path(root)
    if input_path is None:
        frame, source=leer_matriz_icc(root)
        from ml.features import ruta_matriz_icc
        path=ruta_matriz_icc(root,frame['run_origen'].iloc[0])
        mode='consolidacion_local_verificada'; rebuilt=True
    else:
        path=Path(input_path)
        digest=sha256(path)
        frame=cargar_csv(path)
        if digest!=sha256(path): raise ValueError('CSV cambió durante la lectura.')
        mode='csv_independiente'; rebuilt=False
    digest=sha256(path)
    result=evaluar(frame,minimo_pares)
    result['procedencia']={'run_origen':str(frame['run_origen'].iloc[0]),
                          'csv_sha256':digest,'modo_lectura':mode,'fuentes_reconstruidas':rebuilt,
                          'codigo_evaluacion_sha256':sha256(__file__),
                          'codigo_protocolo_sha256':sha256(Path(__file__).with_name('baseline.py')),
                          'hashes_declarados_csv':{name:str(frame[name].iloc[0]) for name in ('deflactor_sha256','series_sha256','observaciones_sha256','contrato_sha256','codigo_features_sha256')}}
    if digest!=sha256(path): raise ValueError('CSV cambió durante la evaluación.')
    return result


def exportar_evaluacion(result, root=ROOT, output_dir=None):
    output=Path(output_dir) if output_dir else Path(root)/'data_analytics'/'evaluaciones_features'/result['procedencia']['run_origen']/f'v{VERSION_EVALUACION}'
    output.mkdir(parents=True,exist_ok=True)
    report=render_informe(result).encode('utf-8')
    payload={**result,'informe_html_sha256':hashlib.sha256(report).hexdigest()}
    serialized=json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode('utf-8')
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        temp=Path(tmp)
        (temp/'informe_icc.html').write_bytes(report)
        (temp/'diagnostico_icc.json').write_bytes(serialized)
        # JSON es el registro de commit y declara el hash del informe.
        (temp/'informe_icc.html').replace(output/'informe_icc.html')
        (temp/'diagnostico_icc.json').replace(output/'diagnostico_icc.json')
    return output/'informe_icc.html',output/'diagnostico_icc.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input',type=Path,help='CSV 3.0 independiente, sin reconstrucción de fuentes.')
    parser.add_argument('--output-dir',type=Path,help='Directorio de resultados; dos archivos, sin fuentes.')
    parser.add_argument('--min-pares',type=int,default=24,help='Mínimo exploratorio por correlación. Default 24.')
    args=parser.parse_args()
    try:
        result=construir_evaluacion(args.root,args.input,args.min_pares)
        paths=exportar_evaluacion(result,args.root,args.output_dir)
    except (ValueError,FileNotFoundError,KeyError) as exc:
        parser.exit(2,f'No se generó la evaluación: {exc}\n')
    print('Evaluación ICC: 14 candidatas, sin selección automática ni entrenamiento.')
    print('Origen:',result['procedencia']['run_origen'])
    for label,profile in result['conjuntos_propuestos'].items():
        print(label,profile['meses_por_split'])
    print('Metodología de baseline:', 'aprobada' if result['protocolo']['metodologia_aprobada'] else 'pendiente')
    for path in paths:print('Salida:',path)


if __name__=='__main__':
    main()
