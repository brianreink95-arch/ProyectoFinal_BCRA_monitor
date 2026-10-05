#!/usr/bin/env python3
"""Base C — extracción + transformación en un único script.

Secciones: 1) configuración/imports; 2) maestro, consulta y panel fuente;
3) transformación analítica de saldos activos y transiciones; 4) CLI del pipeline.
Default: consultar el maestro completo y transformar exactamente esa corrida.
--offline: transformar la última corrida válida o --run-c explícito.
Ejemplos: python base_c.py
          python base_c.py --offline"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from lib.common import read_csv, require_unique, write_csv, build_analytical_run
from lib.common import CANONICAL_C

BASE_URL = "https://api.bcra.gob.ar"
TIMEOUT = (10, 45)
TZ = ZoneInfo("America/Argentina/Buenos_Aires")


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 2. EXTRACCIÓN Y TRANSFORMACIÓN DE RESPUESTAS FUENTE
# -----------------------------------------------------------------------------

def normalize_cuit(value: Any) -> str:
    cuit = re.sub(r"\D", "", str(value))
    if len(cuit) != 11:
        raise ValueError(f"CUIT inválido: {value!r}")
    return cuit


def valid_cuit_check_digit(cuit: str) -> bool:
    """Valida dígito verificador de CUIT argentino."""
    cuit = normalize_cuit(cuit)
    nums = [int(x) for x in cuit]
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

    total = sum(n * w for n, w in zip(nums[:10], weights))
    r = 11 - (total % 11)

    if r == 11:
        check = 0
    elif r == 10:
        check = 9
    else:
        check = r

    return check == nums[10]


def json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_safe),
        encoding="utf-8",
    )


def append_csv(path: Path, df: pd.DataFrame) -> None:
    if df.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        old = pd.read_csv(path, dtype=str)
        combined = pd.concat([old, df.astype(str)], ignore_index=True, sort=False)
    else:
        combined = df

    combined.to_csv(path, index=False)




# ---------------------------------------------------------------------
# Input maestro
# ---------------------------------------------------------------------

def load_master(input_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    empresas = pd.read_excel(
        input_path,
        sheet_name="Empresas",
        dtype=str,
        engine="openpyxl",
    ).fillna("")

    required = {
        "empresa_id",
        "rubro",
        "razon_social",
        "cuit_normalizado",
        "subsectores",
        "perfil_sectorial",
        "grupo_economico",
        "estado_seleccion",
    }

    missing = required - set(empresas.columns)
    if missing:
        raise ValueError(
            "Faltan columnas requeridas en hoja Empresas: "
            + ", ".join(sorted(missing))
        )

    empresas["cuit_normalizado"] = empresas["cuit_normalizado"].map(normalize_cuit)
    empresas["cuit_check_digit_valido"] = empresas["cuit_normalizado"].map(
        valid_cuit_check_digit
    )

    duplicated = empresas["cuit_normalizado"].duplicated(keep=False)
    if duplicated.any():
        dups = empresas.loc[duplicated, ["cuit_normalizado", "razon_social"]]
        raise ValueError(
            "La hoja Empresas contiene CUIT duplicados:\n"
            + dups.to_string(index=False)
        )

    try:
        empresa_subsector = pd.read_excel(
            input_path,
            sheet_name="Empresa_Subsector",
            dtype=str,
            engine="openpyxl",
        ).fillna("")
        empresa_subsector["cuit_normalizado"] = (
            empresa_subsector["cuit_normalizado"].map(normalize_cuit)
        )
    except ValueError:
        # Fallback: explotar el campo subsectores del maestro.
        rows = []
        for row in empresas.itertuples(index=False):
            subs = [
                x.strip()
                for x in str(row.subsectores).split(";")
                if x.strip()
            ]
            for subsector in subs:
                rows.append({
                    "cuit_normalizado": row.cuit_normalizado,
                    "razon_social": row.razon_social,
                    "rubro": row.rubro,
                    "subsector": subsector,
                })
        empresa_subsector = pd.DataFrame(rows)

    return empresas, empresa_subsector


# ---------------------------------------------------------------------
# API BCRA
# ---------------------------------------------------------------------

def get_history(
    session: requests.Session,
    cuit: str,
    retries: int = 4,
) -> dict[str, Any]:
    url = f"{BASE_URL}/centraldedeudores/v1.0/Deudas/Historicas/{cuit}"

    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT)

            if r.status_code == 200:
                try:
                    payload = r.json()
                except ValueError as exc:
                    return {
                        "http_status": 200,
                        "outcome": "invalid_json",
                        "payload": None,
                        "message": str(exc),
                    }

                return {
                    "http_status": 200,
                    "outcome": "ok",
                    "payload": payload,
                    "message": None,
                }

            if r.status_code == 404:
                return {
                    "http_status": 404,
                    "outcome": "no_data",
                    "payload": None,
                    "message": r.text[:1000],
                }

            # Mantenimiento: cortar, no seguir generando falsos negativos.
            if r.status_code == 503:
                return {
                    "http_status": 503,
                    "outcome": "maintenance",
                    "payload": None,
                    "message": r.text[:1000],
                }

            if r.status_code == 429:
                if attempt < retries - 1:
                    wait = min(2 ** attempt, 12)
                    print(f"[retry] {cuit} -> HTTP 429; esperando {wait}s")
                    time.sleep(wait)
                    continue

                return {
                    "http_status": 429,
                    "outcome": "rate_limited",
                    "payload": None,
                    "message": r.text[:1000],
                }

            if 500 <= r.status_code < 600:
                if attempt < retries - 1:
                    wait = min(2 ** attempt, 12)
                    print(
                        f"[retry] {cuit} -> HTTP {r.status_code}; "
                        f"esperando {wait}s"
                    )
                    time.sleep(wait)
                    continue

                return {
                    "http_status": r.status_code,
                    "outcome": "server_error",
                    "payload": None,
                    "message": r.text[:1000],
                }

            return {
                "http_status": r.status_code,
                "outcome": "client_error",
                "payload": None,
                "message": r.text[:1000],
            }

        except requests.exceptions.SSLError as exc:
            kind = "ssl_error"
        except requests.exceptions.ProxyError as exc:
            kind = "proxy_error"
        except requests.exceptions.ConnectTimeout as exc:
            kind = "connect_timeout"
        except requests.exceptions.ReadTimeout as exc:
            kind = "read_timeout"
        except requests.exceptions.ConnectionError as exc:
            kind = "connection_error"
        except requests.exceptions.RequestException as exc:
            kind = "request_error"

        if attempt < retries - 1:
            wait = min(2 ** attempt, 12)
            print(f"[retry] {cuit} -> {kind}: {exc}; esperando {wait}s")
            time.sleep(wait)
            continue

        return {
            "http_status": None,
            "outcome": "local_error",
            "payload": None,
            "message": f"{kind}: {exc}",
        }

    return {
        "http_status": None,
        "outcome": "local_error",
        "payload": None,
        "message": "Falló luego de todos los reintentos.",
    }


# ---------------------------------------------------------------------
# Parsing y panel
# ---------------------------------------------------------------------

def flatten_history(
    company: pd.Series,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    results = payload.get("results") or {}

    denominacion_bcra = results.get("denominacion")
    periodos = results.get("periodos") or []

    rows = []

    for p in periodos:
        periodo = str(p.get("periodo", ""))

        for entity in p.get("entidades") or []:
            rows.append({
                "empresa_id": company["empresa_id"],
                "cuit_normalizado": company["cuit_normalizado"],
                "razon_social": company["razon_social"],
                "denominacion_bcra": denominacion_bcra,
                "rubro": company["rubro"],
                "subsectores": company["subsectores"],
                "perfil_sectorial": company["perfil_sectorial"],
                "grupo_economico": company["grupo_economico"],
                "periodo": periodo,
                "entidad": entity.get("entidad"),
                "situacion": entity.get("situacion"),
                # BCRA: miles de pesos
                "monto_miles_pesos": entity.get("monto"),
                "en_revision": entity.get("enRevision"),
                "proceso_judicial": entity.get("procesoJud"),
            })

    return rows










# ---------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def extract_base_c(input_path, root, max_companies=None, sleep=0.25):
    """Consultar el maestro seleccionado y generar una corrida C inmutable."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo de entrada: {input_path}"
        )

    now = datetime.now(TZ)
    run_date = now.date().isoformat()
    run_id = now.strftime("%Y%m%d_%H%M%S_%f")
    run_at = now.isoformat()

    root = Path(root)
    run_dir = root / "runs" / run_date / run_id

    raw_debt_dir = run_dir / "raw" / "deudas"
    processed_dir = run_dir / "processed"

    # Run_id único => no sobreescritura accidental.
    raw_debt_dir.mkdir(parents=True, exist_ok=False)
    processed_dir.mkdir(parents=True, exist_ok=False)

    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir.resolve()}")

    empresas, empresa_subsector = load_master(input_path)

    # Sólo seleccionadas y CUIT únicos.
    if "estado_seleccion" in empresas.columns:
        selected_mask = empresas["estado_seleccion"].str.contains(
            "SELECCIONADA",
            case=False,
            na=False,
        )
        if selected_mask.any():
            empresas = empresas[selected_mask].copy()

    if max_companies:
        empresas = empresas.head(max_companies).copy()

    empresas = empresas.reset_index(drop=True)

    # Guardar maestro usado en esta corrida para trazabilidad.
    empresas.to_csv(
        processed_dir / "base_c_empresas_input.csv",
        index=False,
    )

    empresa_subsector.to_csv(
        processed_dir / "base_c_empresa_subsector_input.csv",
        index=False,
    )

    session = requests.Session()
    session.headers.update({
        "User-Agent": "ProyectoFinalCAECE/BaseC/1.0",
        "Accept": "application/json",
        "Accept-Language": "es-AR",
    })

    coverage_rows = []
    long_rows = []

    stopped_for_maintenance = False

    for i, (_, company) in enumerate(empresas.iterrows(), start=1):
        cuit = company["cuit_normalizado"]
        razon = company["razon_social"]

        print(f"[{i}/{len(empresas)}] {razon} — {cuit}")

        result = get_history(session, cuit)

        coverage_rows.append({
            "empresa_id": company["empresa_id"],
            "cuit_normalizado": cuit,
            "razon_social": razon,
            "rubro": company["rubro"],
            "subsectores": company["subsectores"],
            "attempted": True,
            "http_status": result["http_status"],
            "outcome": result["outcome"],
            "message": result["message"],
        })

        if result["outcome"] == "ok":
            payload = result["payload"]

            write_json(
                raw_debt_dir / f"{cuit}.json",
                payload,
            )

            rows = flatten_history(
                company,
                payload,
            )

            long_rows.extend(rows)

            print(f"  HTTP 200 -> {len(rows):,} filas empresa-entidad-mes")

        elif result["outcome"] == "no_data":
            print("  HTTP 404 -> sin información BCRA (resultado válido)")

        elif result["outcome"] == "maintenance":
            print("  HTTP 503 -> Central de Deudores en mantenimiento")
            print("  [STOP] Se corta la corrida para evitar falsos negativos.")
            stopped_for_maintenance = True
            break

        else:
            print(
                f"  {result['outcome']} "
                f"(HTTP {result['http_status']})"
            )

        time.sleep(sleep)

    # Empresas no intentadas por mantenimiento.
    attempted = {r["cuit_normalizado"] for r in coverage_rows}

    if stopped_for_maintenance:
        remaining = empresas[
            ~empresas["cuit_normalizado"].isin(attempted)
        ]

        for _, company in remaining.iterrows():
            coverage_rows.append({
                "empresa_id": company["empresa_id"],
                "cuit_normalizado": company["cuit_normalizado"],
                "razon_social": company["razon_social"],
                "rubro": company["rubro"],
                "subsectores": company["subsectores"],
                "attempted": False,
                "http_status": None,
                "outcome": "not_attempted_maintenance",
                "message": (
                    "No se consultó porque Central de Deudores "
                    "entró en mantenimiento durante la corrida."
                ),
            })

    coverage = pd.DataFrame(coverage_rows)
    long_df = pd.DataFrame(long_rows)

    coverage.to_csv(
        processed_dir / "coverage.csv",
        index=False,
    )

    if not long_df.empty:
        long_df.to_csv(
            processed_dir / "base_c_empresa_entidad_mes.csv",
            index=False,
        )

    # La adquisición conserva insumos y cobertura. Features y targets se
    # definirán en ML; no generar paneles exploratorios ni bundles redundantes.
    panel_rows = len(long_df[['cuit_normalizado', 'periodo']].drop_duplicates()) if not long_df.empty else 0
    summary = "\n".join([
        "# Base C — adquisición de fuentes",
        f"Empresas input: {len(empresas)}",
        f"Consultadas: {int(coverage.attempted.fillna(False).sum())}",
        f"Con histórico: {int(coverage.outcome.eq('ok').sum())}",
        f"Sin información (404): {int(coverage.outcome.eq('no_data').sum())}",
        f"Filas empresa-entidad-mes: {len(long_df)}",
        f"Empresa-mes observados: {panel_rows}",
        "Unidad de montos: miles de pesos argentinos.",
        "Los errores no equivalen a ausencia de deuda. No se generan targets ML en la adquisición.",
    ])

    summary_path = run_dir / "run_summary.md"
    summary_path.write_text(
        summary,
        encoding="utf-8",
    )

    # Metadata
    run_metadata = {
        "run_id": run_id,
        "run_date": run_date,
        "run_at": run_at,
        "input_file": str(input_path.resolve()),
        "companies_input": len(empresas),
        "stopped_for_maintenance": stopped_for_maintenance,
        "api": "BCRA Central de Deudores / Deudas Historicas",
        "amount_unit": "miles de pesos",
        "immutable_run_path": str(run_dir.resolve()),
    }

    write_json(
        run_dir / "run_metadata.json",
        run_metadata,
    )

    # Manifest global de corridas.
    manifest_row = pd.DataFrame([{
        **run_metadata,
        "companies_attempted": int(
            coverage["attempted"].fillna(False).astype(bool).sum()
        ),
        "companies_ok": int((coverage["outcome"] == "ok").sum()),
        "companies_no_data": int((coverage["outcome"] == "no_data").sum()),
        "long_rows": len(long_df),
        "panel_rows": panel_rows,
    }])

    append_csv(
        root / "run_manifest.csv",
        manifest_row,
    )

    print("\n" + "=" * 80)
    print(summary)
    print("=" * 80)
    print("\nOK")
    print("Run inmutable:", run_dir.resolve())
    if stopped_for_maintenance or not coverage['outcome'].isin(['ok', 'no_data']).all():
        raise SystemExit('Corrida C incompleta; conservada para auditoría, no consolidar.')
    return run_id


def acquire(root, *, input_path=None, data_root=None, max_companies=None, sleep=0.25):
    """Consultar C; 404 es cobertura válida, error o mantenimiento detienen el flujo."""
    root = Path(root).resolve()
    return extract_base_c(input_path or root / 'config/empresas_base_c.xlsx',
                          data_root or root / 'data_c', max_companies=max_companies, sleep=sleep)


# -----------------------------------------------------------------------------
# 3. TRANSFORMACIÓN Y CONSOLIDACIÓN ANALÍTICA (SIN RED)
# -----------------------------------------------------------------------------

def choose_c(root, run_id=CANONICAL_C):
    dirs = [p.parent for p in (Path(root) / 'data_c/runs').glob('*/*/run_metadata.json')]
    candidates = []
    for p in dirs:
        info = json.loads((p / 'run_metadata.json').read_text(encoding='utf-8-sig'))
        complete = all((p/'processed'/f).exists() for f in [
            'base_c_empresa_entidad_mes.csv','base_c_empresas_input.csv',
            'base_c_empresa_subsector_input.csv','coverage.csv'])
        if complete:
            candidates.append((int(info.get('companies_input', 0)), p.name, p))
    if run_id is not None:
        matches = [p for _, sid, p in candidates if sid == run_id]
        if len(matches) != 1:
            raise ValueError(f'Run C no disponible de manera unívoca: {run_id}')
        return matches[0]
    if not candidates:
        raise ValueError('No hay un run C completo.')
    return sorted(candidates)[-1][2]

def build_c(long, master):
    c = long.copy()
    c['cuit_normalizado'] = c.cuit_normalizado.astype(str)
    master = master.copy()
    master['cuit_normalizado'] = master.cuit_normalizado.astype(str)
    require_unique(master, ['cuit_normalizado'], 'Maestro C')
    require_unique(c, ['cuit_normalizado', 'periodo', 'entidad'], 'Long C')
    if not set(c.cuit_normalizado).issubset(set(master.cuit_normalizado)):
        raise ValueError('Hay CUIT fuera del maestro seleccionado.')
    c['fecha'] = pd.to_datetime(c.periodo.astype(str), format='%Y%m', errors='raise')
    c['monto_miles_pesos'] = pd.to_numeric(c.monto_miles_pesos, errors='raise')
    if (c.monto_miles_pesos.isna() | ~np.isfinite(c.monto_miles_pesos) | c.monto_miles_pesos.lt(0)).any():
        raise ValueError('Monto nulo/no finito/negativo: detener interpretación de exposición.')
    c['situacion'] = pd.to_numeric(c.situacion, errors='coerce')
    active = c[c.monto_miles_pesos.gt(0)].copy()
    keys = ['cuit_normalizado', 'fecha']
    reporting = c.groupby(keys).agg(n_entidades_reportadas=('entidad','nunique'),
                                  situacion_max_reportada=('situacion','max'))
    rows = []
    for key, g in active.groupby(keys):
        amount = g.monto_miles_pesos
        total = amount.sum(); weights = amount / total
        valid = g.situacion.isin([1, 2, 3, 4, 5, 6])
        row = dict(zip(keys, key))
        row.update(deuda_total_positiva=total, n_entidades_con_saldo_positivo=g.entidad.nunique(),
                   situacion_max_activa=g.situacion.max() if valid.all() else np.nan,
                   hhi_deuda_positiva=float(weights.pow(2).sum()),
                   participacion_acreedor_principal=float(weights.max()))
        conditions = {'situacion_1': g.situacion.eq(1), 'situacion_2': g.situacion.eq(2),
                      'situacion_3_mas': g.situacion.isin([3,4,5,6]), 'situacion_desconocida': ~valid}
        for label, mask in conditions.items():
            row['deuda_' + label] = amount[mask].sum()
            row['pct_deuda_' + label] = 100 * amount[mask].sum() / total
        rows.append(row)
    months = pd.date_range(c.fecha.min(), c.fecha.max(), freq='MS')
    grid = pd.MultiIndex.from_product([master.cuit_normalizado, months], names=keys)
    panel = reporting.reindex(grid)
    if rows:
        panel = panel.join(pd.DataFrame(rows).set_index(keys))
    else:
        for col in ['deuda_total_positiva','n_entidades_con_saldo_positivo','situacion_max_activa',
                    'hhi_deuda_positiva','participacion_acreedor_principal']:
            panel[col] = np.nan
        for s in ['situacion_1','situacion_2','situacion_3_mas','situacion_desconocida']:
            panel['deuda_'+s] = np.nan; panel['pct_deuda_'+s] = np.nan
    panel['mes_observado'] = panel.n_entidades_reportadas.notna()
    # Solamente los meses efectivamente reportados sin saldos positivos reciben cero.
    for col in ['deuda_total_positiva','n_entidades_con_saldo_positivo',
                'deuda_situacion_1','deuda_situacion_2','deuda_situacion_3_mas','deuda_situacion_desconocida']:
        panel.loc[panel.mes_observado, col] = panel.loc[panel.mes_observado, col].fillna(0)
    panel['empresa_con_deuda_activa'] = panel.deuda_total_positiva.gt(0).astype('boolean')
    panel.loc[~panel.mes_observado, 'empresa_con_deuda_activa'] = pd.NA
    panel['estado_eda'] = 'SIN_OBSERVACION'
    panel.loc[panel.mes_observado & panel.deuda_total_positiva.eq(0), 'estado_eda'] = 'SIN_SALDO_POSITIVO'
    panel.loc[panel.deuda_total_positiva.gt(0), 'estado_eda'] = 'ACTIVA_SITUACION_DESCONOCIDA'
    for s in range(1,7):
        panel.loc[panel.situacion_max_activa.eq(s), 'estado_eda'] = str(s)
    panel = panel.reset_index().merge(master, on='cuit_normalizado', how='left', validate='many_to_one')
    return c, active, panel.sort_values(keys).reset_index(drop=True)

def transitions_c(panel):
    p = panel.sort_values(['cuit_normalizado','fecha']).copy()
    gb = p.groupby('cuit_normalizado')
    p['fecha_origen'] = gb.fecha.shift()
    p['estado_origen'] = gb.estado_eda.shift()
    p['situacion_origen'] = gb.situacion_max_activa.shift()
    p['mes_origen_observado'] = gb.mes_observado.shift().eq(True)
    ordinal = p.fecha.dt.year * 12 + p.fecha.dt.month
    p['adyacente'] = ordinal.groupby(p.cuit_normalizado).diff().eq(1)
    pairs = p[p.adyacente & p.mes_origen_observado & p.mes_observado].copy()
    valid = pairs.situacion_origen.notna() & pairs.situacion_max_activa.notna()
    risk = pairs[valid].copy()
    risk['evento'] = np.select([risk.situacion_max_activa.gt(risk.situacion_origen),
                               risk.situacion_max_activa.lt(risk.situacion_origen)],
                              ['Empeora','Mejora'], default='Permanece')
    risk_matrix = pd.crosstab(risk.situacion_origen, risk.situacion_max_activa).reindex(
        index=range(1,7), columns=range(1,7), fill_value=0)
    reporting_matrix = pd.crosstab(pairs.estado_origen, pairs.estado_eda)
    return pairs, risk, risk_matrix, reporting_matrix

def load_c(root, run_id=CANONICAL_C):
    run = choose_c(root, run_id)
    p = run / 'processed'
    master = read_csv(p/'base_c_empresas_input.csv', dtype={'cuit_normalizado':str})
    links = read_csv(p/'base_c_empresa_subsector_input.csv', dtype={'cuit_normalizado':str})
    links['subsector'] = links.subsector.str.strip()
    require_unique(links, ['cuit_normalizado','subsector'], 'Pertenencias C')
    if set(links.cuit_normalizado) != set(master.cuit_normalizado) or links.subsector.isna().any():
        raise ValueError('Pertenencias sectoriales incompletas o CUIT ajenos al maestro.')
    long = read_csv(p/'base_c_empresa_entidad_mes.csv', dtype={'cuit_normalizado':str})
    coverage = read_csv(p/'coverage.csv', dtype={'cuit_normalizado':str})
    long, active, panel = build_c(long, master)
    return run, master, links, coverage, long, active, panel

def choose_operational_c(root, run_id=None):
    """Elegir la última corrida exitosa del universo maestro completo, sin smoke tests.

    Un 404 es un resultado válido. Un error/503 no equivale a ausencia de deuda.
    Para reproducir una corrida específica, usar run_id; también se valida su cobertura.
    """
    root = Path(root)
    current = pd.read_excel(root / 'config/empresas_base_c.xlsx', sheet_name='Empresas', dtype=str).fillna('')
    selected = current.estado_seleccion.str.contains('SELECCIONADA', case=False, na=False)
    if selected.any():
        current = current[selected]
    expected = set(current.cuit_normalizado.str.replace(r'\D', '', regex=True))
    candidates = []
    rejected = []
    for meta in sorted((root / 'data_c/runs').glob('*/*/run_metadata.json')):
        if run_id is not None and meta.parent.name != run_id:
            continue
        try:
            info = json.loads(meta.read_text(encoding='utf-8-sig'))
            p = meta.parent / 'processed'
            master = read_csv(p / 'base_c_empresas_input.csv', dtype={'cuit_normalizado': str})
            coverage = read_csv(p / 'coverage.csv', dtype={'cuit_normalizado': str})
            require_unique(master, ['cuit_normalizado'], 'Input C')
            require_unique(coverage, ['cuit_normalizado'], 'Coverage C')
            if set(master.cuit_normalizado) != expected or set(coverage.cuit_normalizado) != expected:
                raise ValueError('Universo incompleto o diferente al maestro vigente')
            if info.get('stopped_for_maintenance'):
                raise ValueError('Corrida interrumpida por mantenimiento')
            if not coverage.outcome.isin(['ok', 'no_data']).all():
                raise ValueError('Cobertura contiene errores de consulta')
            if not coverage.attempted.astype(str).str.lower().eq('true').all():
                raise ValueError('Hay empresas no consultadas')
            if not (p / 'base_c_empresa_entidad_mes.csv').is_file():
                raise ValueError('Sin histórico procesado; no se puede establecer ventana mensual')
            candidates.append(meta.parent)
        except (ValueError, OSError, KeyError) as exc:
            rejected.append(f'{meta.parent.name}: {exc}')
    if not candidates:
        raise ValueError('No existe una corrida C válida para el maestro completo. ' + '; '.join(rejected))
    return sorted(candidates, key=lambda p: p.name)[-1]

def transform_c(root, output, run_id=None):
    """Dimensiones y hechos de deuda para IEF; no exportar matrices ni transiciones de EDA."""
    from lib.relacional import exportar_tablas, id_estable, fecha_iso, booleanos
    selected = choose_operational_c(root,run_id)
    run,master,links,coverage,long,active,panel = load_c(root,selected.name)
    require_unique(panel,['cuit_normalizado','fecha'],'Panel analítico C')
    if set(master.cuit_normalizado) != set(panel.cuit_normalizado):
        raise ValueError('Se perdió una empresa del universo seleccionado.')
    if not np.isclose(panel.deuda_total_positiva.sum(),active.monto_miles_pesos.sum()):
        raise ValueError('No reconcilia exposición empresa-mes con saldos positivos.')
    pct=['pct_deuda_situacion_1','pct_deuda_situacion_2','pct_deuda_situacion_3_mas','pct_deuda_situacion_desconocida']
    if not np.allclose(panel.loc[panel.deuda_total_positiva.gt(0),pct].sum(axis=1),100):
        raise ValueError('Las participaciones de situación no suman 100.')
    companies=master.drop(columns=['subsectores']).copy()
    for col in companies.columns:
        if col not in ['cuit_formato_valido','cuit_check_digit_valido']:
            companies[col]=companies[col].astype('string')
    for col in ['cuit_formato_valido','cuit_check_digit_valido']:companies[col]=booleanos(companies[col])
    sectors=links[['rubro','subsector']].drop_duplicates().copy()
    sectors['subsector_id']=[id_estable('subsector',r,s) for r,s in sectors.itertuples(index=False,name=None)]
    memberships=links.merge(sectors,on=['rubro','subsector'],validate='many_to_one')[
        ['cuit_normalizado','subsector_id','documento_soporte','estado_seleccion']]
    sectors=sectors.rename(columns={'subsector':'nombre'})
    creditors=pd.DataFrame({'nombre_fuente':sorted(long.entidad.drop_duplicates())})
    creditors['acreedor_id']=creditors.nombre_fuente.map(lambda x:id_estable('acreedor_c',x))
    debt=long.merge(creditors,left_on='entidad',right_on='nombre_fuente',validate='many_to_one')
    debt=debt[['cuit_normalizado','fecha','acreedor_id','situacion','monto_miles_pesos','en_revision','proceso_judicial']].copy()
    debt['run_fuente']=run.name
    debt['fecha']=fecha_iso(debt.fecha)
    for col in ['en_revision','proceso_judicial']:debt[col]=booleanos(debt[col])
    info=json.loads((run/'run_metadata.json').read_text(encoding='utf-8-sig'))
    names=long[['cuit_normalizado','denominacion_bcra']].drop_duplicates()
    require_unique(names,['cuit_normalizado'],'Denominación C de la captura')
    queries=coverage[['cuit_normalizado','attempted','http_status','outcome','message']].merge(
        names,on='cuit_normalizado',how='left',validate='one_to_one').rename(columns={
            'attempted':'intentada','outcome':'resultado','message':'mensaje','denominacion_bcra':'denominacion_empresa_bcra'})
    queries['run_fuente']=run.name;queries['fecha_captura']=info['run_at']
    queries['intentada']=booleanos(queries.intentada)
    monthly=panel.drop(columns=[c for c in master.columns if c!='cuit_normalizado']).rename(columns={'estado_eda':'estado'}).copy()
    monthly['run_fuente']=run.name
    legal=long.copy()
    for col in ['en_revision','proceso_judicial']:legal[col]=booleanos(legal[col])
    # Flags sobre entidades reportadas, incluso si el saldo es cero. Un hueco queda desconocido.
    def flag_any(values):
        return True if values.eq(True).any() else (pd.NA if values.isna().any() else False)
    legal=legal.groupby(['cuit_normalizado','fecha'])[['en_revision','proceso_judicial']].agg(flag_any).reset_index()
    monthly=monthly.merge(legal,on=['cuit_normalizado','fecha'],how='left',validate='one_to_one')
    for col in ['en_revision','proceso_judicial']:monthly[col]=booleanos(monthly[col])
    monthly['fecha']=fecha_iso(monthly.fecha)
    tables={'empresas':companies,'subsectores':sectors,'empresa_subsector':memberships,'acreedores':creditors,
            'consultas':queries,'deuda_entidad_mes':debt,'empresa_mes':monthly}
    validation=exportar_tablas(root,'c',tables,output)
    return {'run_id':run.name,'empresas':len(master),'pertenencias':len(links),
            'filas_empresa_entidad_mes':len(long),'filas_empresa_mes':len(panel),
            'meses':int(panel.fecha.nunique()),'meses_sin_observacion':int((~panel.mes_observado).sum()),
            'relacional':validation}

# -----------------------------------------------------------------------------
# 4. CLI: EXTRACCIÓN + TRANSFORMACIÓN, O REPROCESAMIENTO OFFLINE
# -----------------------------------------------------------------------------

def main():
    """Ejecutar la base completa o reprocesarla sin red con --offline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parent,
                        help='Raíz del proyecto; default carpeta de este script.')
    parser.add_argument('--out-root', type=Path, default=None,
                        help='Salida analítica; default PROJECT_ROOT/data_analytics.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--offline', action='store_true', help='Transformar datos guardados, sin llamadas BCRA.')
    mode.add_argument('--extract-only', action='store_true', help='Sólo extraer; útil para diagnóstico/smoke test.')
    parser.add_argument('--root', type=Path, default=None, help='Salida fuente C (compatibilidad); default PROJECT_ROOT/data_c.')
    parser.add_argument('--input', type=Path, default=None, help='Maestro XLSX; default PROJECT_ROOT/config/empresas_base_c.xlsx.')
    parser.add_argument('--max-companies', type=int, default=None, help='Smoke test; requiere --extract-only.')
    parser.add_argument('--sleep', type=float, default=0.25, help='Pausa entre consultas de C.')
    parser.add_argument('--run-c', default=None, help='Run histórico específico; requiere --offline.')
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.root is not None and args.root.resolve() != root / 'data_c' and not args.extract_only:
        parser.error('--root indica la carpeta fuente C; para otro proyecto usar --project-root, o --extract-only.')
    if args.input is not None and args.input.resolve() != root / 'config/empresas_base_c.xlsx' and not args.extract_only:
        parser.error('Maestro alternativo: usar --extract-only; el analítico utiliza el maestro del proyecto.')
    if args.max_companies is not None and not args.extract_only:
        parser.error('--max-companies requiere --extract-only para no transformar una corrida anterior por accidente.')
    if args.run_c and not args.offline:
        parser.error('--run-c requiere --offline: reproduce una corrida histórica.')
    options = {'input_path': args.input, 'data_root': args.root, 'max_companies': args.max_companies, 'sleep': args.sleep}
    if args.extract_only:
        acquire(root, **options)
        return
    build_analytical_run(root, args.out_root, bases=('c',),
                        extract=() if args.offline else ('c',),
                        acquisition_options={'c': options}, run_c=args.run_c)


if __name__ == '__main__':
    main()
