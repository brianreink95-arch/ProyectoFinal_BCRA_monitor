"""Infraestructura común: archivos, claves, metadata y ejecución de pipelines.

Las reglas de A/B/C viven exclusivamente en base_a.py, base_b.py y base_c.py. Este módulo no es una CLI.
"""
from pathlib import Path
import hashlib
import json
import platform
import zipfile
import importlib.util
import sys
import numpy as np
import pandas as pd

FAMILIES = ['hipotecarios', 'personales', 'prendarios', 'tarjetas']
CANONICAL_C = '20260910_234243_324893'
SEGMENTS = {883: 'Personas humanas', 885: 'Prestadoras financieras',
            891: 'PyMEs', 892: 'No PyMEs'}
RATE_LABELS = {7: 'BADLAR privados', 14: 'Personales', 135: 'TAMAR',
               145: 'Adelantos 1–7 días', 1189: 'Plazo fijo',
               1199: 'Adelantos fija', 1215: 'Tarjetas (total)',
               1216: 'Documentos firma', 1218: 'Prendarios fija',
               1220: 'Tarjetas tasa no cero', 1240: 'Hipotecarios UVA'}

def fingerprint(root):
    root = Path(root)
    return {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in ['data_a', 'data_b', 'data_c']
            for p in sorted((root / base).rglob('*')) if p.is_file()}

def resolve_data_root(data_root=None, here=None):
    here = Path(here or Path.cwd()).resolve()
    if data_root is not None:
        root = Path(data_root).expanduser().resolve()
        if not all((root / n).is_dir() for n in ['data_a', 'data_b', 'data_c']):
            raise FileNotFoundError(f'Faltan data_a/data_b/data_c en {root}')
        return root
    for root in [here / 'inputs', here, *here.parents, here.parent / 'scripts']:
        if all((root / n).is_dir() for n in ['data_a', 'data_b', 'data_c']):
            return root
    archive = here / 'data_all.zip'
    if archive.exists():
        root = here / 'inputs'
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (root / name).resolve().is_relative_to(root.resolve()):
                    raise ValueError(f'Ruta insegura en ZIP: {name}')
            z.extractall(root)
        return resolve_data_root(root)
    raise FileNotFoundError('Indicar DATA_ROOT o colocar data_all.zip junto al notebook.')

def read_csv(path, **kwargs):
    return pd.read_csv(path, encoding='utf-8-sig', **kwargs)

def require_unique(df, cols, name):
    if df.duplicated(cols).any():
        raise ValueError(f'{name}: clave duplicada {cols}; requiere revisión.')

def save_table(df, name, output):
    dest = Path(output) / 'tablas'; dest.mkdir(parents=True, exist_ok=True)
    df.to_csv(dest / f'{name}.csv', index=False, encoding='utf-8-sig')

def runtime_metadata():
    return {'python': platform.python_version(), 'pandas': pd.__version__,
            'numpy': np.__version__}

def write_csv(df, path):
    """Exportación atómica; comprobar registros antes de publicar el archivo."""
    import csv
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    try:
        df.to_csv(temp, index=False, encoding='utf-8-sig')
        with temp.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            if next(reader) != list(df.columns) or sum(1 for _ in reader) != len(df):
                raise ValueError(f'Exportación CSV incompleta: {path.name}')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)

PIPELINE_FILES = {'a': 'base_a.py',
                  'b': 'base_b.py',
                  'c': 'base_c.py'}
_MODULES = {}


def get_pipeline(base):
    """Importar la implementación única de cada base, sin ejecutar su CLI."""
    if base not in PIPELINE_FILES:
        raise ValueError(f'Base desconocida: {base}')
    if base not in _MODULES:
        path = Path(__file__).resolve().parent.parent / PIPELINE_FILES[base]
        name = f'bcra_pipeline_{base}'
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        _MODULES[base] = module
    return _MODULES[base]


def build_analytical_run(root, output_root=None, bases=('a', 'b', 'c'), run_c=None,
                         extract=(), acquisition_options=None):
    """Corrida nueva, comprobación de integridad y publicación de pointer al completar."""
    from datetime import datetime, timezone
    root = Path(root).resolve()
    output_root = Path(output_root or root / 'data_analytics').resolve()
    for name in ['data_a', 'data_b', 'data_c', 'analisis', 'config', 'lib', 'docs', 'archivo_obsoleto']:
        if output_root.is_relative_to(root / name):
            raise ValueError(f'La salida no puede escribirse dentro de {name}.')
    if not bases or not set(bases).issubset({'a', 'b', 'c'}) or len(set(bases)) != len(bases):
        raise ValueError('Seleccionar una o más bases diferentes entre a, b y c.')
    if not set(extract).issubset(set(bases)):
        raise ValueError('No se puede extraer una base que no será procesada.')
    if run_c and 'c' in extract:
        raise ValueError('No combinar run C histórico con nueva extracción de C.')
    for base in dict.fromkeys(extract):
        print(f'Extrayendo Base {base.upper()}...', flush=True)
        acquired = get_pipeline(base).acquire(root, **(acquisition_options or {}).get(base, {}))
        if base == 'c':
            run_c = acquired  # transformar la corrida recién capturada, sin fallback silencioso
    before = fingerprint(root)
    now = datetime.now(timezone.utc)
    run_id = now.strftime('%Y%m%d_%H%M%S_%f')
    dest = output_root / 'runs' / run_id
    dest.mkdir(parents=True, exist_ok=False)
    metadata = {'run_id': run_id, 'created_at_utc': now.isoformat(),
                'status': 'running', 'bases': list(bases), 'runtime': runtime_metadata(),
                'acquired_bases': list(dict.fromkeys(extract)),
                'source_sha256': before,
                'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), Path(__file__).parent / 'relacional.py', *[Path(__file__).parent.parent / PIPELINE_FILES[b] for b in bases]]},
                'catalog_sha256': hashlib.sha256((root / 'config/catalogo_base_a.csv').read_bytes()).hexdigest(),
                'schema_version': '1.0',
                'schema_sha256': hashlib.sha256((root / 'config/esquema_tablas.json').read_bytes()).hexdigest()}
    meta_path = dest / 'run_metadata.json'
    def save_meta():
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    save_meta()
    try:
        summaries = {}
        for base in bases:
            print(f'Transformando Base {base.upper()}...', flush=True)
            if base == 'c':
                summaries[base] = get_pipeline(base).transform_c(root, dest / 'base_c', run_c)
            else:
                summaries[base] = getattr(get_pipeline(base), f'transform_{base}')(root, dest / f'base_{base}')
        if fingerprint(root) != before:
            raise ValueError('Los insumos cambiaron durante la transformación; repetir la corrida.')
        metadata.update(status='completed', summary=summaries, inputs_unchanged=True)
        metadata['outputs'] = [{'path': str(p.relative_to(dest)).replace('\\', '/'),
                                'size_bytes': p.stat().st_size,
                                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                               for p in sorted(dest.rglob('*.csv'))]
        save_meta()
        # Las corridas individuales no reemplazan el puntero de la consolidación ABC.
        pointer = 'latest.json' if set(bases) == {'a', 'b', 'c'} else 'latest_' + ''.join(bases) + '.json'
        temp = output_root / (pointer + '.tmp')
        temp.write_text(json.dumps({'run_id': run_id, 'path': f'runs/{run_id}',
                                    'bases': list(bases)}, indent=2), encoding='utf-8')
        temp.replace(output_root / pointer)
    except Exception as exc:
        metadata.update(status='failed', error=str(exc))
        save_meta()
        raise
    print(f'Corrida completada: {dest}', flush=True)
    return dest, metadata
