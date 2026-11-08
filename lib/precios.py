"""IPC nacional mensual: lectura validada y deflación sin red.

Los nominales conservan su escala. El factor es 100 / IPC del mismo mes;
tasas y ratios nunca se pasan a esta función. La ingesta vive en base_a.py.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

BASE_IPC = '2016-12'
IPC_COLUMNS = ['fecha_mes', 'ipc_nacional', 'factor_deflacion', 'periodo_base', 'version_fuente']
ESTADOS_AJUSTE = ['ajustado', 'no_aplica', 'sin_observacion', 'sin_valor_nominal',
                  'unidad_no_validada', 'anterior_base', 'ipc_no_publicado', 'ipc_faltante']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validar_ipc(frame):
    """Rechazar cambios de base, duplicados, huecos y factores inconsistentes."""
    if list(frame.columns) != IPC_COLUMNS or frame.empty:
        raise ValueError('IPC: columnas incorrectas o índice vacío.')
    result = frame.copy()
    dates = pd.to_datetime(result.fecha_mes, format='%Y-%m-%d', errors='raise')
    if dates.isna().any() or not dates.eq(dates + pd.offsets.MonthEnd(0)).all():
        raise ValueError('IPC: fechas nulas o distintas del cierre mensual.')
    if dates.duplicated().any():
        raise ValueError('IPC: mes duplicado.')
    if not result.periodo_base.eq(BASE_IPC).all():
        raise ValueError('IPC: se requiere base diciembre de 2016 = 100.')
    if result.version_fuente.isna().any() or result.version_fuente.nunique() != 1:
        raise ValueError('IPC: se requiere una única versión de fuente.')
    if not result.version_fuente.astype(str).str.fullmatch(r'[0-9a-f]{64}').all():
        raise ValueError('IPC: versión de fuente debe ser SHA-256.')
    for col in ['ipc_nacional', 'factor_deflacion']:
        result[col] = pd.to_numeric(result[col], errors='raise')
        if not np.isfinite(result[col]).all() or result[col].le(0).any():
            raise ValueError(f'IPC: {col} debe ser positivo y finito.')
    if not np.allclose(result.factor_deflacion, 100 / result.ipc_nacional, rtol=1e-12, atol=0):
        raise ValueError('IPC: factor distinto de 100 / IPC.')
    result = result.assign(fecha_mes=dates.dt.strftime('%Y-%m-%d')).sort_values('fecha_mes').reset_index(drop=True)
    expected = pd.date_range('2016-12-31', result.fecha_mes.iloc[-1], freq='ME').strftime('%Y-%m-%d').tolist()
    if result.fecha_mes.tolist() != expected or not np.isclose(result.ipc_nacional.iloc[0], 100, rtol=0, atol=1e-10):
        raise ValueError('IPC: falta base 100 o continuidad mensual desde diciembre de 2016.')
    return result


def cargar_ipc(root):
    """Consumir la versión inmutable indicada por latest; nunca descargar aquí."""
    folder = Path(root) / 'data_a/ipc'
    pointer = folder / 'latest.json'
    if not pointer.exists():
        raise FileNotFoundError('Falta IPC nacional. Ejecutar python base_a.py --ipc-only una vez; luego usar --offline.')
    info = json.loads(pointer.read_text(encoding='utf-8'))
    version = str(info['version_fuente'])
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise ValueError('IPC: versión inválida en el puntero.')
    location = folder / 'versions' / version
    metadata = json.loads((location / 'metadata.json').read_text(encoding='utf-8'))
    for name, digest in metadata['files_sha256'].items():
        if Path(name).name != name or sha256(location / name) != digest:
            raise ValueError(f'IPC: archivo modificado o ruta inválida: {name}')
    if sha256(location / 'serie_ipc_divisiones.csv') != version:
        raise ValueError('IPC: versión no coincide con publicación original.')
    if metadata['periodo_base'] != BASE_IPC or metadata['version_fuente'] != version:
        raise ValueError('IPC: metadata incompatible con fuente.')
    table = validar_ipc(pd.read_csv(location / 'ipc_nacional.csv', encoding='utf-8-sig'))
    if not table.version_fuente.eq(version).all():
        raise ValueError('IPC: tabla pertenece a otra versión.')
    if [table.fecha_mes.iloc[0], table.fecha_mes.iloc[-1]] != [metadata['desde'], metadata['hasta']]:
        raise ValueError('IPC: cobertura declarada incompatible.')
    return table, metadata


def ajustar_montos(frame, columnas, ipc, *, fecha='fecha', observado=None,
                   elegible=None, no_aplica=None):
    """Agregar importes constantes y una FK mensual nullable sin cambiar filas.

columnas: {columna nominal: columna constante}. observado distingue huecos
de cero observado. elegible valida unidades; no_aplica excluye tasas/ratios.
Un índice estructuralmente inválido se rechaza en cargar/validar_ipc.
Un mes no disponible conserva el nominal y registra el motivo.
"""
    result = frame.copy()
    ipc = validar_ipc(ipc)
    dates = pd.to_datetime(result[fecha], errors='raise')
    if dates.isna().any():
        raise ValueError('Deflación: fecha nula.')
    months = dates.dt.to_period('M').dt.to_timestamp('M').dt.strftime('%Y-%m-%d')
    index = ipc.set_index('fecha_mes')
    if index.index.duplicated().any():
        raise ValueError('Deflación: IPC duplicado.')
    factors = months.map(index.factor_deflacion)
    observed = pd.Series(True, index=result.index) if observado is None else observado.reindex(result.index).fillna(False).astype(bool)
    eligible = pd.Series(True, index=result.index) if elegible is None else elegible.reindex(result.index).fillna(False).astype(bool)
    excluded = pd.Series(False, index=result.index) if no_aplica is None else no_aplica.reindex(result.index).fillna(False).astype(bool)
    status = pd.Series('ajustado', index=result.index, dtype='string')
    status.loc[factors.isna() & months.gt(ipc.fecha_mes.max())] = 'ipc_no_publicado'
    status.loc[factors.isna() & months.le(ipc.fecha_mes.max())] = 'ipc_faltante'
    status.loc[~eligible] = 'unidad_no_validada'
    status.loc[months.lt('2016-12-31')] = 'anterior_base'
    primary = pd.to_numeric(result[next(iter(columnas))], errors='raise')
    status.loc[primary.isna()] = 'sin_valor_nominal'
    status.loc[~observed] = 'sin_observacion'
    status.loc[excluded] = 'no_aplica'
    available = status.eq('ajustado')
    for nominal, constant in columnas.items():
        values = pd.to_numeric(result[nominal], errors='raise')
        if not np.isfinite(values.dropna()).all():
            raise ValueError(f'Deflación: valor no finito en {nominal}.')
        result[constant] = (values * factors).where(available)
    result['ipc_fecha_mes'] = months.where(available).astype('string')
    result['estado_ajuste_ipc'] = status
    return result


def resumen_ajuste(frame):
    return {str(k): int(v) for k, v in frame.estado_ajuste_ipc.value_counts().items()}


def validar_referencias_ipc(frames, ipc):
    """Validar FK entre bases y coherencia de estados antes del puntero final."""
    valid_months = set(ipc.fecha_mes)
    for name, frame in frames.items():
        available = frame.estado_ajuste_ipc.eq('ajustado')
        if not frame.loc[available, 'ipc_fecha_mes'].isin(valid_months).all():
            raise ValueError(f'{name}: referencia huérfana a IPC.')
        if frame.loc[~available, 'ipc_fecha_mes'].notna().any():
            raise ValueError(f'{name}: referencia IPC sin ajuste calculable.')
