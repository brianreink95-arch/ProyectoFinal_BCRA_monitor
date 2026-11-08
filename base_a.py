#!/usr/bin/env python3
"""Base A — extracción + transformación en un único script.

Secciones: 1) configuración/imports; 2) extracción BCRA, IPC INDEC,
auditoría de unidades y staging; 3) transformación nominal/constante;
4) CLI del pipeline.
Default: descargar, validar y transformar. --offline: transformar datos guardados.
Salidas fuente: data_a/. Salidas analíticas: data_analytics/runs/<id>/base_a/.
Ejemplos: python base_a.py
          python base_a.py --offline"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import shutil
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from lib.common import read_csv, require_unique, write_csv, build_analytical_run, remove_tree
from lib.precios import (BASE_IPC, validar_ipc, cargar_ipc, ajustar_montos,
                        resumen_ajuste, sha256)
import numpy as np

BASE_URL = "https://api.bcra.gob.ar"
TIMEOUT = (10, 30)
IPC_URL = 'https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv'
IPC_METADATA_URL = 'https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_metadatos.txt'
UNIDADES_URL = 'https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/'
# Hoja/columna oficial: stocks ML de PH para ICC. El XLS está en miles de ARS;
# los valores de la API coinciden con XLS/1000 redondeado: millones de ARS.
UNIDADES_ICC = {927: ('perser_priv.xls', 'Prest-Hip', 17),
                1145: ('perser_dest.xls', 'fis', 22),
                1146: ('perser_dest.xls', 'fis', 23),
                1147: ('perser_dest.xls', 'fis', 25),
                1148: ('perser_dest.xls', 'fis', 26),
                1149: ('perser_dest.xls', 'fis', 29)}

# Seleccion definitiva de Base A. Las series derivables y los agregados MEyML
# no se ingieren.
DEFAULT_SERIES = {
    14: "tasa_prestamos_personales",
    883: "prestamos_personas_humanas",
    885: "prestamos_prestadoras_servicios_financieros",
    891: "prestamos_pymes",
    892: "prestamos_empresas_no_pymes",
    927: "hipotecarios_ml_personas_humanas",
    929: "hipotecarios_ml_prestadoras_servicios_financieros",
    935: "hipotecarios_ml_pymes",
    936: "hipotecarios_ml_empresas_no_pymes",
    938: "hipotecarios_me_personas_humanas",
    940: "hipotecarios_me_prestadoras_servicios_financieros",
    946: "hipotecarios_me_pymes",
    947: "hipotecarios_me_empresas_no_pymes",
    1145: "hipotecarios_ml_ph_construccion",
    1146: "hipotecarios_ml_ph_refaccion",
    1147: "hipotecarios_ml_ph_compra_nuevas",
    1148: "hipotecarios_ml_ph_compra_usadas",
    1149: "hipotecarios_ml_ph_otras",
    1153: "hipotecarios_me_ph_construccion",
    1154: "hipotecarios_me_ph_refaccion",
    1155: "hipotecarios_me_ph_compra_nuevas",
    1156: "hipotecarios_me_ph_compra_usadas",
    1157: "hipotecarios_me_ph_otras",
    1169: "hipotecarios_ml_pj_construccion",
    1170: "hipotecarios_ml_pj_refaccion",
    1171: "hipotecarios_ml_pj_compra_nuevas",
    1172: "hipotecarios_ml_pj_compra_usadas",
    1173: "hipotecarios_ml_pj_otras",
    1177: "hipotecarios_me_pj_construccion",
    1178: "hipotecarios_me_pj_refaccion",
    1179: "hipotecarios_me_pj_compra_nuevas",
    1180: "hipotecarios_me_pj_compra_usadas",
    1181: "hipotecarios_me_pj_otras",
    1215: "tasa_financiaciones_tarjetas",
    1218: "tasa_prendarios_fija",
    1240: "tasa_hipotecarios_uva",
    # Prendarios por tipo de titular
    960: "prendarios_ml_personas_humanas",
    962: "prendarios_ml_prestadoras_servicios_financieros",
    968: "prendarios_ml_pymes",
    969: "prendarios_ml_empresas_no_pymes",

    971: "prendarios_me_personas_humanas",
    973: "prendarios_me_prestadoras_servicios_financieros",
    979: "prendarios_me_pymes",
    980: "prendarios_me_empresas_no_pymes",

    # Prendarios por destino - Personas humanas
    1150: "prendarios_ml_ph_automotores",
    1151: "prendarios_ml_ph_maquinarias",
    1152: "prendarios_ml_ph_otros",

    1158: "prendarios_me_ph_automotores",
    1159: "prendarios_me_ph_maquinarias",
    1160: "prendarios_me_ph_otros",

    # Prendarios por destino - Personas jurídicas
    1174: "prendarios_ml_pj_automotores",
    1175: "prendarios_ml_pj_maquinarias",
    1176: "prendarios_ml_pj_otros",

    1182: "prendarios_me_pj_automotores",
    1183: "prendarios_me_pj_maquinarias",
    1184: "prendarios_me_pj_otros",

    # Tasas de crédito a personas
    1220: "tasa_tarjetas_distinta_cero",

    # Tasas de crédito a empresas
    1199: "tasa_adelantos_cuenta_corriente_fija",
    1216: "tasa_documentos_sola_firma_fija",
    145: "tasa_adelantos_empresas_privadas_1_7_dias",

    # Tasas de referencia / fondeo
    7: "tasa_badlar_privados",
    135: "tasa_tamar",
    1189: "tasa_plazo_fijo_pesos",

    # Inflación:
    27: "inflacion_mensual",
    28: "inflacion_interanual",

    
}

FORBIDDEN_SERIES = {884}


# -----------------------------------------------------------------------------
# 2. EXTRACCIÓN Y TRANSFORMACIÓN DE RESPUESTAS FUENTE
# -----------------------------------------------------------------------------

def request_json(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    retries: int = 4,
) -> tuple[int | None, Any, str | None]:
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 200:
                try:
                    return 200, response.json(), None
                except ValueError as exc:
                    return 200, None, f"JSON invalido: {exc}"

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt < retries - 1:
                    wait = min(2**attempt, 8)
                    print(f"[retry] HTTP {response.status_code}; esperando {wait}s: {response.url}")
                    time.sleep(wait)
                    continue

            return response.status_code, None, response.text[:1000]

        except requests.exceptions.SSLError as exc:
            return None, None, f"ssl_error: {exc}"
        except requests.exceptions.ProxyError as exc:
            return None, None, f"proxy_error: {exc}"
        except requests.exceptions.ConnectTimeout as exc:
            return None, None, f"connect_timeout: {exc}"
        except requests.exceptions.ReadTimeout as exc:
            return None, None, f"read_timeout: {exc}"
        except requests.exceptions.ConnectionError as exc:
            return None, None, f"connection_error: {exc}"
        except requests.exceptions.RequestException as exc:
            if attempt < retries - 1:
                time.sleep(min(2**attempt, 8))
                continue
            return None, None, f"request_error: {exc}"

    return None, None, "Fallo luego de todos los reintentos."


def date_bounds(dataframe: pd.DataFrame | None) -> tuple[str | None, str | None]:
    if dataframe is None or dataframe.empty:
        return None, None
    date_column = next((column for column in ("fecha", "date") if column in dataframe.columns), None)
    if date_column is None:
        return None, None
    dates = pd.to_datetime(dataframe[date_column], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def add_summary(
    summary: list[dict[str, Any]],
    test: str,
    url: str,
    status: int | None,
    rows: int | None,
    ok: bool,
    message: str | None = None,
    dataframe: pd.DataFrame | None = None,
) -> None:
    fecha_min, fecha_max = date_bounds(dataframe)
    summary.append({
        "test": test,
        "ok": ok,
        "http_status": status,
        "rows": rows,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "url": url,
        "message": message,
    })


def save_raw(payload: Any, path: Path) -> None:
    if payload is not None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_monetary_catalog(session: requests.Session) -> pd.DataFrame:
    url = f"{BASE_URL}/estadisticas/v4.0/monetarias"
    status, payload, error = request_json(session, url, {"limit": 3000, "offset": 0})
    if status != 200 or not payload:
        raise RuntimeError(f"No se pudo obtener catalogo monetario: {status} {error}")
    return pd.json_normalize(payload.get("results", []))


def fetch_monetary_history(
    session: requests.Session,
    variable_id: int,
    desde: str | None,
    hasta: str | None,
) -> tuple[int | None, pd.DataFrame, str | None]:
    url = f"{BASE_URL}/estadisticas/v4.0/monetarias/{variable_id}"
    limit, offset, rows = 3000, 0, []

    while True:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if desde:
            params["desde"] = desde
        if hasta:
            params["hasta"] = hasta
        status, payload, error = request_json(session, url, params)
        if status != 200 or not payload:
            return status, pd.DataFrame(rows), error

        detail = []
        for result in payload.get("results") or []:
            if isinstance(result, dict):
                for item in result.get("detalle") or []:
                    if isinstance(item, dict):
                        detail.append({"idVariable": result.get("idVariable", variable_id), **item})

        rows.extend(detail)
        if len(detail) < limit:
            break
        offset += limit

    return 200, pd.DataFrame(rows), None


def fetch_methodology(
    session: requests.Session,
    variable_id: int,
) -> tuple[int | None, pd.DataFrame, str | None]:
    url = f"{BASE_URL}/estadisticas/v4.0/metodologia/{variable_id}"
    status, payload, error = request_json(session, url)
    if status != 200 or not payload:
        return status, pd.DataFrame(), error
    return 200, pd.json_normalize(payload.get("results", [])), None


def fetch_currency_master(session: requests.Session) -> tuple[int | None, pd.DataFrame, Any, str | None]:
    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Maestros/Divisas"
    status, payload, error = request_json(session, url)
    if status != 200 or not payload:
        return status, pd.DataFrame(), payload, error
    return 200, pd.json_normalize(payload.get("results") or []), payload, None


def fetch_current_fx(session: requests.Session) -> tuple[int | None, pd.DataFrame, Any, str | None]:
    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Cotizaciones"
    status, payload, error = request_json(session, url)
    if status != 200 or not payload:
        return status, pd.DataFrame(), payload, error

    results = payload.get("results") or {}
    detail = results.get("detalle") or [] if isinstance(results, dict) else []
    dataframe = pd.json_normalize(detail)
    if not dataframe.empty and isinstance(results, dict):
        dataframe.insert(0, "fecha", results.get("fecha"))
    return 200, dataframe, payload, None


def fetch_currency_history(
    session: requests.Session,
    moneda: str,
    desde: str | None,
    hasta: str | None,
) -> tuple[int | None, pd.DataFrame, Any, str | None]:
    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Cotizaciones/{moneda}"
    limit, offset, rows = 999, 0, []

    while True:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if desde and hasta:
            params["fechadesde"] = desde
            params["fechahasta"] = hasta
        status, payload, error = request_json(session, url, params)
        if status != 200 or not payload:
            return status, pd.DataFrame(rows), payload, error

        results = payload.get("results") or []
        if isinstance(results, list):
            detail = results
        elif isinstance(results, dict):
            detail = results.get("detalle") or [results]
        else:
            detail = []
        rows.extend(item for item in detail if isinstance(item, dict))
        if len(detail) < limit:
            break
        offset += limit

    return 200, pd.DataFrame(rows), payload, None

def extract_base_a(out, desde=None, hasta=None):
    """Descargar A en el directorio indicado. Falla si la adquisición es incompleta."""
    out = Path(out)
    hasta = hasta or date.today().isoformat()
    raw_dir = out / "raw"
    processed_dir = out / "processed"
    metadata_dir = out / "metadata"
    logs_dir = out / "logs"
    for directory in (raw_dir, processed_dir, metadata_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "ProyectoFinalCAECE/1.0",
        "Accept": "application/json",
        "Accept-Language": "es-AR",
    })
    summary: list[dict[str, Any]] = []

    print("\n=== 1. ESTADISTICAS MONETARIAS ===")
    catalog_url = f"{BASE_URL}/estadisticas/v4.0/monetarias"
    monetary_complete = False
    try:
        catalog = fetch_monetary_catalog(session)
        catalog.to_csv(metadata_dir / "bcra_monetarias_catalog.csv", index=False)

        catalog["idVariable"] = pd.to_numeric(catalog["idVariable"], errors="raise").astype(int)
        catalog_ids = {
            int(value) for value in catalog["idVariable"]
        }
        missing_ids = set(DEFAULT_SERIES) - catalog_ids
        forbidden_present = FORBIDDEN_SERIES & catalog_ids
        if missing_ids:
            raise RuntimeError(f"Faltan series seleccionadas en el catalogo: {sorted(missing_ids)}")
        if forbidden_present:
            print(f"[control] La serie prohibida esta presente en el catalogo, pero no sera ingerida: {sorted(forbidden_present)}")

        selected = catalog[catalog["idVariable"].isin(DEFAULT_SERIES)].copy()
        selected.insert(1, "nombre_corto", selected["idVariable"].map(DEFAULT_SERIES))
        mortgage_aggregate = selected[
            selected["descripcion"].astype(str).str.contains("hipotec", case=False, na=False)
            & selected["moneda"].astype(str).str.upper().eq("MEYML")
        ]
        if not mortgage_aggregate.empty:
            ids = mortgage_aggregate["idVariable"].tolist()
            raise RuntimeError(f"Se seleccionaron hipotecarios agregados MEyML: {ids}")
        selected.to_csv(metadata_dir / "bcra_monetarias_selected_catalog.csv", index=False)
        meta = selected.set_index("idVariable").to_dict(orient="index")

        histories: list[pd.DataFrame] = []
        methods: list[pd.DataFrame] = []
        history_ok = 0
        for variable_id, short_name in DEFAULT_SERIES.items():
            metadata = meta[variable_id]
            series_desde = desde or metadata.get("primerFechaInformada")
            url = f"{BASE_URL}/estadisticas/v4.0/monetarias/{variable_id}"
            status, dataframe, error = fetch_monetary_history(
                session, variable_id, series_desde, hasta
            )
            valid = status == 200 and not dataframe.empty
            if valid:
                dataframe.insert(1, "nombre_corto", short_name)
                for column in ("descripcion", "categoria", "periodicidad", "unidadExpresion", "moneda"):
                    dataframe.insert(dataframe.columns.size, column, metadata.get(column))
                duplicate_count = dataframe.duplicated(subset=["idVariable", "fecha"]).sum()
                if duplicate_count:
                    valid = False
                    error = f"{duplicate_count} duplicados de idVariable + fecha"
                else:
                    histories.append(dataframe)
                    history_ok += 1
            elif status == 200:
                error = "Respuesta HTTP valida pero sin observaciones"

            print(f"[{variable_id}] historico -> HTTP {status}; filas={len(dataframe):,}; {metadata.get('descripcion')}")
            add_summary(summary, f"monetaria_{variable_id}_historico", url, status, len(dataframe), valid, error, dataframe)

            murl = f"{BASE_URL}/estadisticas/v4.0/metodologia/{variable_id}"
            mstatus, mdf, merror = fetch_methodology(session, variable_id)
            if not mdf.empty:
                mdf.insert(0, "idVariable", variable_id)
                mdf.insert(1, "nombre_corto", short_name)
                methods.append(mdf)
            add_summary(summary, f"monetaria_{variable_id}_metodologia", murl, mstatus, len(mdf), mstatus == 200 and not mdf.empty, merror, mdf)

        if history_ok == len(DEFAULT_SERIES):
            history = pd.concat(histories, ignore_index=True)
            if history.duplicated(subset=["idVariable", "fecha"]).any():
                raise RuntimeError("El consolidado contiene duplicados de idVariable + fecha")
            history.to_csv(processed_dir / "bcra_monetarias_history_long.csv", index=False)
            monetary_complete = True
        else:
            print(f"[control] No se sobrescribe el historico monetario: {history_ok}/{len(DEFAULT_SERIES)} series completas")

        if methods:
            pd.concat(methods, ignore_index=True).to_csv(metadata_dir / "bcra_monetarias_metodologia.csv", index=False)
        add_summary(summary, "monetarias_catalog", catalog_url, 200, len(catalog), monetary_complete, None)
    except Exception as exc:
        print("ERROR catalogo monetario:", exc)
        add_summary(summary, "monetarias_catalog", catalog_url, None, None, False, str(exc))

    print("\n=== 2. ESTADISTICAS CAMBIARIAS ===")
    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Maestros/Divisas"
    status, dataframe, payload, error = fetch_currency_master(session)
    if status == 200 and not dataframe.empty:
        save_raw(payload, raw_dir / "bcra_divisas_raw.json")
        dataframe.to_csv(processed_dir / "bcra_divisas.csv", index=False)
    add_summary(summary, "cambiarias_maestro_divisas", url, status, len(dataframe), status == 200 and not dataframe.empty, error, dataframe)

    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Cotizaciones"
    status, dataframe, payload, error = fetch_current_fx(session)
    if status == 200 and not dataframe.empty:
        save_raw(payload, raw_dir / "bcra_cotizaciones_raw.json")
        dataframe.to_csv(processed_dir / "bcra_cotizaciones_snapshot.csv", index=False)
    add_summary(summary, "cambiarias_cotizaciones_actuales", url, status, len(dataframe), status == 200 and not dataframe.empty, error, dataframe)

    url = f"{BASE_URL}/estadisticascambiarias/v1.0/Cotizaciones/USD"
    status, dataframe, payload, error = fetch_currency_history(session, "USD", desde, hasta)
    if status == 200 and not dataframe.empty:
        save_raw(payload, raw_dir / "bcra_usd_history_raw.json")
        dataframe.to_csv(processed_dir / "bcra_usd_history.csv", index=False)
    add_summary(summary, "cambiarias_usd_historico", url, status, len(dataframe), status == 200 and not dataframe.empty, error, dataframe)

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(logs_dir / "bcra_api_test_summary.csv", index=False)

    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    if not summary_df.empty:
        print(summary_df[["test", "ok", "http_status", "rows", "fecha_min", "fecha_max"]].to_string(index=False))
        print(f"\nTests OK: {int(summary_df['ok'].sum())}/{len(summary_df)}")
    print(f"\nArchivos guardados en: {out.resolve()}")
    required = summary_df['test'].str.startswith('cambiarias_')
    if not monetary_complete or not summary_df.loc[required, 'ok'].all():
        raise SystemExit('Extracción A incompleta; revisar logs antes de transformar.')

# 2.2. FUENTE OFICIAL IPC: PUBLICACIÓN ORIGINAL + NORMALIZACIÓN VERSIONADA

def publicar_version(folder, version, files, metadata):
    """Conservar versiones inmutables y mover el puntero al final de la ingesta."""
    folder = Path(folder)
    versions = folder / 'versions'
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / version
    metadata = {**metadata, 'version_fuente': version,
                'files_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    if destination.exists():
        previous = json.loads((destination / 'metadata.json').read_text(encoding='utf-8'))
        if previous['files_sha256'] != metadata['files_sha256']:
            raise ValueError('Intento de cambiar una versión inmutable de fuente.')
        for name, digest in previous['files_sha256'].items():
            if sha256(destination / name) != digest:
                raise ValueError(f'Versión fuente alterada: {name}')
    else:
        with tempfile.TemporaryDirectory(prefix='version_stage_', dir=folder) as tmp:
            stage = Path(tmp) / version
            stage.mkdir()
            for name, data in files.items():
                (stage / name).write_bytes(data)
            (stage / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            stage.replace(destination)
    pointer = folder / 'latest.json.tmp'
    pointer.write_text(json.dumps({'version_fuente': version}, indent=2), encoding='utf-8')
    pointer.replace(folder / 'latest.json')
    return destination


def parsear_ipc(raw, raw_metadata):
    """Seleccionar niveles nacionales; no encadenar variaciones redondeadas."""
    metadata_text = raw_metadata.decode('utf-8-sig')
    if 'Diciembre 2016=100' not in metadata_text or 'Indice_IPC:' not in metadata_text:
        raise ValueError('INDEC: cambiaron los metadatos o la base del IPC.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    source = pd.read_csv(io.StringIO(text), sep=';', dtype='string')
    required = {'Codigo', 'Descripcion', 'Clasificador', 'Periodo', 'Indice_IPC', 'Region'}
    if not required.issubset(source.columns):
        raise ValueError('INDEC: columnas desconocidas en publicación IPC.')
    selected = source.loc[source.Codigo.eq('0') & source.Region.eq('Nacional')].copy()
    if selected.empty or not selected.Descripcion.eq('NIVEL GENERAL').all():
        raise ValueError('INDEC: no se encontró nivel general nacional.')
    if not selected.Periodo.str.fullmatch(r'\d{6}').all():
        raise ValueError('INDEC: período IPC inválido.')
    dates = pd.to_datetime(selected.Periodo, format='%Y%m', errors='raise') + pd.offsets.MonthEnd(0)
    levels = pd.to_numeric(selected.Indice_IPC.str.replace(',', '.', regex=False), errors='raise')
    version = hashlib.sha256(raw).hexdigest()
    table = pd.DataFrame({'fecha_mes': dates.dt.strftime('%Y-%m-%d'), 'ipc_nacional': levels,
                          'factor_deflacion': 100 / levels, 'periodo_base': BASE_IPC,
                          'version_fuente': version})
    return validar_ipc(table)


def adquirir_ipc(root):
    """Descargar original INDEC, validar y conservar la publicación versionada."""
    with requests.Session() as session:
        r = session.get(IPC_URL, timeout=TIMEOUT)
        r.raise_for_status()
        m = session.get(IPC_METADATA_URL, timeout=TIMEOUT)
        m.raise_for_status()
    table = parsear_ipc(r.content, m.content)
    metadata_text = m.content.decode('utf-8-sig')
    update = re.search(r'Actualizado al:\s*(\d{2}/\d{2}/\d{4})', metadata_text)
    publication = datetime.strptime(update.group(1), '%d/%m/%Y').date().isoformat() if update else None
    metadata = {'fuente': 'INDEC', 'url': IPC_URL, 'url_metadatos': IPC_METADATA_URL,
                'adquirido_en_utc': datetime.now(timezone.utc).isoformat(),
                'fecha_actualizacion_fuente': publication, 'periodo_base': BASE_IPC,
                'desde': table.fecha_mes.iloc[0], 'hasta': table.fecha_mes.iloc[-1],
                'meses': len(table), 'uso': 'retrospectivo; no reconstruye disponibilidad histórica'}
    # La versión incluye también los metadatos utilizados: si cambian sin cambiar
    # el CSV, conservar los anteriores y rechazar la ambigüedad para revisión.
    files = {'serie_ipc_divisiones.csv': r.content, 'serie_ipc_metadatos.txt': m.content,
             'ipc_nacional.csv': table.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')}
    publicar_version(Path(root) / 'data_a/ipc', table.version_fuente.iloc[0], files, metadata)
    return metadata


# 2.3. EVIDENCIA DE UNIDADES DEL SUBCONJUNTO ICC

def auditar_unidades_icc(root, publicaciones=None):
    """Contrastar valores API contra XLS oficial; habilitar solo meses probados.

Una diferencia superior al redondeo rechaza la ingesta: puede indicar revisión
o cambio de escala y requiere resolverlo, no aplicar un factor supuesto.
publicaciones permite validar el parser con originales oficiales guardados.
"""
    h = read_csv(Path(root) / 'data_a/processed/bcra_monetarias_history_long.csv')
    h['fecha'] = pd.to_datetime(h.fecha, errors='raise').dt.strftime('%Y-%m-%d')
    files = {}
    sheets = {}
    for name in sorted({x[0] for x in UNIDADES_ICC.values()}):
        if publicaciones is None:
            response = requests.get(UNIDADES_URL + name, timeout=TIMEOUT)
            response.raise_for_status()
            raw = response.content
        else:
            raw = publicaciones[name]
        files[name] = raw
    records = []
    for sid, (name, sheet, column) in UNIDADES_ICC.items():
        if (name, sheet) not in sheets:
            sheets[name, sheet] = pd.read_excel(io.BytesIO(files[name]), sheet_name=sheet, header=None, engine='xlrd')
        official = sheets[name, sheet].copy()
        if 'thousands of pesos' not in str(official.iloc[3, 3]) or 'domestic currency' not in str(official.iloc[5, 16 if sid == 927 else 20]):
            raise ValueError('BCRA: cambió la unidad o estructura de las tablas oficiales.')
        official['periodo'] = pd.to_numeric(official[2], errors='coerce').astype('Int64').astype('string')
        official = official.loc[official.periodo.notna() & official.periodo.str[-2:].between('01', '12')].copy()
        official['fecha'] = (pd.to_datetime(official.periodo, format='%Y%m', errors='raise') + pd.offsets.MonthEnd(0)).dt.strftime('%Y-%m-%d')
        subset = h.loc[h.idVariable.eq(sid) & h.fecha.ge('2016-12-31'), ['fecha', 'valor']]
        check = subset.merge(official[['fecha', column]], on='fecha', validate='one_to_one')
        if check.empty:
            raise ValueError(f'No hay meses comparables para auditar escala de {sid}.')
        official_millions = pd.to_numeric(check[column], errors='raise') / 1000
        differences = pd.to_numeric(check.valor, errors='raise') - official_millions
        if not np.isfinite(official_millions).all() or differences.abs().gt(0.500001).any():
            raise ValueError(f'Escala/revisión {sid}: API no coincide con XLS/1000 redondeado; revisar fuentes.')
        records.extend({'serie_id': sid, 'fecha': row.fecha, 'valor_api': float(row.valor),
                        'unidad_validada': 'millones_ARS', 'valor_xls_miles_ars': float(value)}
                       for row, value in zip(check.itertuples(index=False), check[column]))
    certificate = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    files['contraste.json'] = certificate
    version = hashlib.sha256(b''.join(files[k] for k in sorted(files))).hexdigest()
    metadata = {'adquirido_en_utc': datetime.now(timezone.utc).isoformat(),
                'fuentes': {name: UNIDADES_URL + name for name in files if name.endswith('.xls')},
                'filas_contrastadas': len(records), 'unidad_validada': 'millones_ARS',
                'criterio': 'API = XLS en miles de ARS / 1000, tolerancia de redondeo 0.500001',
                'advertencia': 'unidad declarada por API miles de ARS contradice escala contrastada'}
    publicar_version(Path(root) / 'data_a/unidades_icc', version, files, metadata)
    return metadata


def unidades_icc_validadas(root, observations):
    """No extender la certificación a meses/valores que no fueron contrastados."""
    folder = Path(root) / 'data_a/unidades_icc'
    if not (folder / 'latest.json').exists():
        return pd.Series(False, index=observations.index), {'estado': 'sin_contraste_oficial'}
    version = json.loads((folder / 'latest.json').read_text(encoding='utf-8'))['version_fuente']
    if not re.fullmatch(r'[0-9a-f]{64}', str(version)):
        raise ValueError('Unidades ICC: versión inválida.')
    location = folder / 'versions' / version
    metadata = json.loads((location / 'metadata.json').read_text(encoding='utf-8'))
    for name, digest in metadata['files_sha256'].items():
        if Path(name).name != name or sha256(location / name) != digest:
            raise ValueError('Unidades ICC: evidencia original alterada.')
    evidence = pd.DataFrame(json.loads((location / 'contraste.json').read_text(encoding='utf-8')))
    require_unique(evidence, ['serie_id', 'fecha'], 'Contraste oficial ICC')
    lookup = evidence.set_index(['serie_id', 'fecha']).valor_api
    keys = pd.MultiIndex.from_frame(observations[['serie_id', 'fecha']])
    values = pd.Series(lookup.reindex(keys).to_numpy(), index=observations.index)
    # Exactitud respecto de los nominales auditados, sin inferir escala nueva.
    eligible = values.notna() & observations.valor_original.eq(values)
    return eligible, {'version_fuente': version, **metadata}


def acquire(root, *, out=None, desde=None, hasta=None):
    """Extraer y validar A en staging; publicar el cache sólo al terminar bien."""
    root = Path(root).resolve()
    destination = Path(out) if out is not None else root / 'data_a'
    with tempfile.TemporaryDirectory(prefix='base_a_stage_', dir=root) as tmp:
        staging_root = Path(tmp)
        stage = staging_root / 'data_a'
        if destination.exists():
            shutil.copytree(destination, stage)
        extract_base_a(stage, desde=desde, hasta=hasta)
        adquirir_ipc(staging_root)
        auditar_unidades_icc(staging_root)
        (staging_root / 'config').mkdir()
        shutil.copy2(root / 'config/catalogo_base_a.csv', staging_root / 'config/catalogo_base_a.csv')
        shutil.copy2(root / 'config/esquema_tablas.json', staging_root / 'config/esquema_tablas.json')
        transform_a(staging_root, staging_root / 'validation')
        # Publicar directorio validado como unidad; restaurar cache previo si
        # falla el intercambio. Las versiones IPC/unidades previas se conservan.
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = destination.with_name(destination.name + '.backup')
        if backup.exists():
            raise ValueError(f'Existe backup de adquisición pendiente de revisión: {backup}')
        previous = destination.exists()
        if previous:
            destination.replace(backup)
        try:
            shutil.move(str(stage), str(destination))
        except Exception:
            if destination.exists():
                remove_tree(destination)
            if previous:
                backup.replace(destination)
            raise
        if previous:
            remove_tree(backup)
    return None


# -----------------------------------------------------------------------------
# 3. TRANSFORMACIÓN Y CONSOLIDACIÓN ANALÍTICA (SIN RED)
# -----------------------------------------------------------------------------

def load_a_inputs(root, catalog_path):
    p = Path(root) / 'data_a'
    h = read_csv(p / 'processed/bcra_monetarias_history_long.csv')
    cat = read_csv(catalog_path)
    require_unique(cat, ['serie_id'], 'Catálogo A')
    h['fecha'] = pd.to_datetime(h['fecha'], errors='raise')
    h['valor'] = pd.to_numeric(h['valor'], errors='raise')
    require_unique(h, ['idVariable', 'fecha'], 'Base A')
    missing = set(h.idVariable) - set(cat.serie_id)
    if missing:
        raise ValueError(f'Series nuevas sin decisión en catálogo: {sorted(missing)}')
    # Excepción congelada en el notebook de calidad. El original conserva los ceros.
    h['valor_eda'] = h['valor']
    mask = h.idVariable.eq(1199) & h.fecha.lt('1993-06-01') & h.valor.eq(0)
    h.loc[mask, 'valor_eda'] = np.nan
    h['excepcion_1199_precobertura'] = mask
    h['mes'] = h.fecha.dt.to_period('M')
    return h.sort_values(["idVariable", "fecha"]), cat

def load_a(root, catalog_path):
    """Vistas calculadas solamente para los notebooks explicativos."""
    h, cat = load_a_inputs(root, catalog_path)
    p = Path(root) / "data_a"
    monthly = h.groupby(['idVariable', 'mes'], as_index=False).agg(
        valor_eda=('valor_eda', 'mean'), n_observaciones=('valor_eda', 'count'),
        ultima_observacion=('fecha', 'max'))
    # Mensual: una observación/mes. Diaria: media de observaciones disponibles.
    monthly = monthly.merge(cat[['serie_id', 'frecuencia', 'tipo_valor']],
                            left_on='idVariable', right_on='serie_id', validate='many_to_one')
    asof = h.fecha.max()
    monthly['mes_diario_abierto'] = monthly.frecuencia.eq('D') & monthly.mes.eq(asof.to_period('M'))
    monthly['fecha'] = monthly.mes.dt.to_timestamp('M')
    wide = monthly.pivot(index='fecha', columns='idVariable', values='valor_eda').sort_index()
    wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq='ME'))
    fx = read_csv(p / 'processed/bcra_usd_history.csv')
    fx_rows = []
    for row in fx.itertuples():
        detail = ast.literal_eval(row.detalle) if isinstance(row.detalle, str) else row.detalle
        for item in detail:
            fx_rows.append({'fecha': row.fecha, **item})
    return h.sort_values(['idVariable', 'fecha']), cat, monthly, wide, pd.DataFrame(fx_rows)

def transform_a(root, output, ipc=None):
    """Hechos nominales/constantes ICC y deflactor compartido; sin vistas de EDA."""
    from lib.relacional import exportar_tablas, fecha_iso
    h, cat = load_a_inputs(root, Path(root) / 'config/catalogo_base_a.csv')
    if h.valor.isna().any() or not np.isfinite(h.valor).all():
        raise ValueError('Base A: valores originales nulos o no finitos.')
    expected = set(cat.serie_id)
    if set(h.idVariable) != expected:
        raise ValueError('Base A: el histórico no contiene exactamente el catálogo vigente.')
    metadata = read_csv(Path(root) / 'data_a/metadata/bcra_monetarias_selected_catalog.csv')
    require_unique(metadata, ['idVariable'], 'Metadatos A')
    if set(metadata.idVariable) != expected:
        raise ValueError('Base A: el catálogo seleccionado no coincide con el analítico.')
    for source, target in [('descripcion', 'descripcion'), ('moneda', 'moneda'), ('unidadExpresion', 'unidad')]:
        check = cat[['serie_id', target]].merge(metadata[['idVariable', source]],
            left_on='serie_id', right_on='idVariable', suffixes=('_analitico', '_fuente'), validate='one_to_one')
        left = target + '_analitico' if target == source else target
        right = source + '_fuente' if target == source else source
        if not check[left].astype(str).str.strip().eq(check[right].astype(str).str.strip()).all():
            raise ValueError(f'Base A: cambió el metadato {source}; revisar catálogo analítico.')
    observations = h[['idVariable','fecha','valor','valor_eda','excepcion_1199_precobertura']].rename(
        columns={'idVariable':'serie_id','valor':'valor_original','valor_eda':'valor_analitico',
                 'excepcion_1199_precobertura':'excepcion_precobertura'}).copy()
    observations['fecha'] = fecha_iso(observations.fecha)
    if ipc is None:
        ipc, _ = cargar_ipc(root)
    if not set(cat.loc[cat.ajuste_ipc, 'serie_id']).issubset(UNIDADES_ICC):
        raise ValueError('Ajuste IPC: serie sin criterio/evidencia implementados.')
    selected = cat.loc[cat.ajuste_ipc]
    if not (selected.tipo_valor.eq('stock_nominal') & selected.frecuencia.eq('M') &
            selected.moneda.eq('ML') & selected.unidad_validada.eq('millones_ARS') &
            selected.consumidor_ajuste.eq('ICC')).all():
        raise ValueError('Ajuste IPC: unidad, frecuencia, moneda o consumidor incompatible.')
    decision = observations.serie_id.map(cat.set_index('serie_id').ajuste_ipc).fillna(False)
    eligible, unit_metadata = unidades_icc_validadas(root, observations)
    observations = ajustar_montos(observations, {'valor_analitico': 'valor_constante_dic2016'},
                                  ipc, elegible=eligible & decision, no_aplica=~decision)
    validation = exportar_tablas(root, 'a', {'series':cat.rename(columns={'rol_eda':'rol_analitico'}),
                                           'observaciones':observations,
                                           'deflactor_ipc':ipc}, output)
    return {'observaciones':len(h),'series':len(cat),'excepciones_1199':int(h.excepcion_1199_precobertura.sum()),
            'hasta':h.fecha.max().isoformat(),'stocks_escala_pendiente':int(cat.validacion_escala.eq('pendiente_escala_absoluta').sum()),
            'ajuste_ipc':resumen_ajuste(observations), 'contraste_unidades':unit_metadata,
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
    mode.add_argument('--ipc-only', action='store_true',
                      help='Adquirir/validar solo IPC nacional INDEC; no vuelve a descargar BCRA.')
    mode.add_argument('--audit-units-only', action='store_true',
                      help='Contrastar stocks ICC guardados contra tablas oficiales BCRA.')
    parser.add_argument('--out', type=Path, default=None, help='Salida fuente A; default PROJECT_ROOT/data_a.')
    parser.add_argument('--desde', default=None, help='Fecha inicial opcional para la descarga.')
    parser.add_argument('--hasta', default=None, help='Fecha final de descarga; default hoy.')
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.ipc_only or args.audit_units_only:
        if args.out is not None or args.desde is not None or args.hasta is not None:
            parser.error('Las ingestas de IPC/unidades usan PROJECT_ROOT sin --out/--desde/--hasta.')
        result = adquirir_ipc(root) if args.ipc_only else auditar_unidades_icc(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.out is not None and args.out.resolve() != root / 'data_a' and not args.extract_only:
        parser.error('Para una salida fuente personalizada usar --extract-only; para otro proyecto usar --project-root.')
    options = {'out': args.out, 'desde': args.desde, 'hasta': args.hasta}
    if args.extract_only:
        acquire(root, **options)
        return
    build_analytical_run(root, args.out_root, bases=('a',),
                        extract=() if args.offline else ('a',),
                        acquisition_options={'a': options})


if __name__ == '__main__':
    main()
