"""Contrato de tablas CSV: tipos, claves y relaciones, sin motor de base de datos."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd


def id_estable(*parts):
    """Identidad técnica reproducible; no supone identidad comercial entre capturas."""
    payload = json.dumps([str(p) for p in parts], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def fecha_iso(values):
    return pd.to_datetime(values, errors='raise').dt.strftime('%Y-%m-%d')


def booleanos(values):
    """No convertir valores desconocidos a False."""
    mapping = {'true': True, 'false': False, 'si': True, 'sí': True, 'no': False}
    text = values.astype('string').str.lower()
    invalid = values.notna() & ~text.isin(mapping)
    if invalid.any():
        raise ValueError(f'Booleanos desconocidos: {values[invalid].unique().tolist()}')
    return text.map(mapping).astype('boolean')


def validar_tablas(tablas, contrato):
    """Validar una base completa antes de escribir cualquier tabla de esa base."""
    expected = set(contrato)
    if set(tablas) != expected:
        raise ValueError(f'Tablas distintas del contrato: {set(tablas) ^ expected}')
    for name, frame in tablas.items():
        spec = contrato[name]
        if set(frame.columns) != set(spec['columns']):
            raise ValueError(f'{name}: columnas fuera del contrato: {set(frame.columns) ^ set(spec["columns"])}')
        pk = spec['primary_key']
        if frame[pk].isna().any().any() or frame.duplicated(pk).any():
            raise ValueError(f'{name}: clave primaria nula o duplicada {pk}')
        for col, rule in spec['columns'].items():
            s = frame[col]
            missing = s.isna() | s.astype('string').str.strip().eq('').fillna(False)
            if not rule['nullable'] and missing.any():
                raise ValueError(f'{name}.{col}: nulos no permitidos')
            valid = s[~missing]
            kind = rule['type']
            if kind in ['integer', 'number']:
                number = pd.to_numeric(valid, errors='coerce')
                if number.isna().any() or not np.isfinite(number.to_numpy(dtype=float)).all():
                    raise ValueError(f'{name}.{col}: números inválidos')
                if kind == 'integer' and not number.mod(1).eq(0).all():
                    raise ValueError(f'{name}.{col}: se esperaba entero')
                if 'minimum' in rule and number.lt(rule['minimum']).any():
                    raise ValueError(f'{name}.{col}: debajo del mínimo')
                if 'maximum' in rule and number.gt(rule['maximum']).any():
                    raise ValueError(f'{name}.{col}: encima del máximo')
            elif kind == 'boolean':
                if not valid.astype(str).str.lower().isin(['true', 'false']).all():
                    raise ValueError(f'{name}.{col}: se esperaba booleano')
            elif kind in ['date', 'datetime']:
                dates = pd.to_datetime(valid, format='%Y-%m-%d' if kind == 'date' else 'ISO8601',
                                       errors='coerce', utc=True)
                if dates.isna().any():
                    raise ValueError(f'{name}.{col}: fechas inválidas')
                pattern = r'^\d{4}-\d{2}-\d{2}$' if kind == 'date' else r'.*(Z|[+-]\d{2}:\d{2})$'
                if not valid.astype(str).str.match(pattern).all():
                    raise ValueError(f'{name}.{col}: formato temporal incorrecto')
            elif kind == 'text' and not all(isinstance(x, str) for x in valid):
                raise ValueError(f'{name}.{col}: se esperaba texto, preservar identificadores')
            if 'enum' in rule and not valid.isin(rule['enum']).all():
                raise ValueError(f'{name}.{col}: categoría fuera del contrato')
            if 'pattern' in rule and not valid.astype(str).str.match(rule['pattern']).all():
                raise ValueError(f'{name}.{col}: formato inválido')
        for fk in spec.get('foreign_keys', []):
            child = frame[fk['columns']]
            if fk.get('nullable'):
                child = child.dropna()
            if child.isna().any().any():
                raise ValueError(f'{name}: FK nula {fk["columns"]}')
            if fk.get('base'):
                # Las referencias entre bases se validan con el deflactor
                # único de la corrida en lib.common antes de publicar latest.
                continue
            parent = tablas[fk['table']][fk['references']]
            parent_keys = set(parent.itertuples(index=False, name=None))
            if any(key not in parent_keys for key in child.itertuples(index=False, name=None)):
                raise ValueError(f'{name}: FK huérfana hacia {fk["table"]}')
    return {name: {'rows': len(frame), 'primary_key': contrato[name]['primary_key'],
                   'foreign_keys_validated': len(contrato[name].get('foreign_keys', []))}
            for name, frame in tablas.items()}


def exportar_tablas(root, base, tablas, output):
    from lib.common import write_csv
    schema = json.loads((Path(root) / 'config/esquema_tablas.json').read_text(encoding='utf-8'))
    contract = schema['bases'][base]
    validation = validar_tablas(tablas, contract)
    output = Path(output)
    for name, frame in tablas.items():
        ordered = frame[list(contract[name]['columns'])].sort_values(contract[name]['primary_key']).reset_index(drop=True)
        write_csv(ordered, output / f'{name}.csv')
    return validation
