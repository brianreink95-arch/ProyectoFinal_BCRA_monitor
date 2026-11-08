"""Coordinador de los pipelines A/B/C: ejecución conjunta y trazabilidad.

Las reglas de extracción/transformación están en base_a.py, base_b.py y base_c.py.
Default: reprocesar las tres bases guardadas, sin red.
--extract a b c: actualizar las tres desde BCRA antes de procesarlas.
--extract b: actualizar sólo B y procesar las tres bases.
--refresh-ipc: actualizar IPC nacional INDEC y procesar fuentes guardadas.

Cada ejecución publica una corrida ABC completa; no hace un join entre bases
ni calcula modelos/índices. Para procesar una sola base, ejecutar su script.
"""
from pathlib import Path
import argparse
from lib.common import build_analytical_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent,
                        help='Raíz del proyecto; default carpeta del script.')
    parser.add_argument('--out-root', type=Path, default=None,
                        help='Salida analítica; default ROOT/data_analytics.')
    parser.add_argument('--extract', choices=['a', 'b', 'c'], nargs='+', default=[],
                        help='Bases que se actualizarán desde BCRA antes de procesar ABC.')
    parser.add_argument('--run-c', default=None,
                        help='Run C histórico específico; incompatible con --extract c.')
    parser.add_argument('--refresh-ipc', action='store_true',
                        help='Actualizar IPC nacional INDEC antes de consolidar, sin recapturar BCRA si no se indica --extract.')
    args = parser.parse_args()
    if args.run_c and 'c' in args.extract:
        parser.error('--run-c reproduce una corrida histórica; no combinar con --extract c.')
    build_analytical_run(args.root, args.out_root, extract=args.extract, run_c=args.run_c,
                         refresh_ipc=args.refresh_ipc)


if __name__ == '__main__':
    main()
