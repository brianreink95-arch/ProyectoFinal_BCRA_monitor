#!/usr/bin/env python3
"""Base B — extracción + transformación en un único script.

Secciones: 1) configuración/imports; 2) captura inmutable y normalización;
3) consolidación y transformación analítica; 4) CLI del pipeline.
Default: capturar las cuatro familias y transformar el histórico completo válido.
--offline: consolidar snapshots guardados. --extract-only: sólo capturar.
Ejemplos: python base_b.py
          python base_b.py --offline"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from lib.common import read_csv, require_unique, write_csv, build_analytical_run
from lib.common import FAMILIES

BASE_URL = "https://api.bcra.gob.ar"
TIMEOUT = (10, 45)
TZ = ZoneInfo("America/Argentina/Buenos_Aires")

ENDPOINTS = {
    "hipotecarios": "/transparencia/v1.0/Prestamos/Hipotecarios",
    "personales": "/transparencia/v1.0/Prestamos/Personales",
    "prendarios": "/transparencia/v1.0/Prestamos/Prendarios",
    "tarjetas": "/transparencia/v1.0/TarjetasCredito",
}

RATIO_COLS = ["relacionCuotaIngreso", "relacionMontoTasacion"]
RATE_COLS = [
    "tasaEfectivaAnualMaxima",
    "costoFinancieroEfectivoTotalMaximo",
    "tasaEfectivaAnualMaximaFinanciacion",
    "tasaEfectivaAnualMaximaAdelantoEfectivo",
]

FAMILY_FIELDS = [
    "producto_snapshot", "codigoEntidad", "nombreCompleto", "nombreCorto",
    "destinoFondos", "denominacion", "beneficiario", "segmento",
    "territorioValidez",
]

VARIANT_FIELDS = [
    "plazoMaximoOtorgable", "plazoMinimoOtorgable",
    "montoMaximoOtorgable", "montoMinimoOtorgable",
    "ingresoMinimoMensual", "antiguedadLaboralMinimaMeses",
    "edadMaximaSolicitada", "relacionCuotaIngreso_pct",
    "relacionMontoTasacion_pct", "tipoTasa", "moneda",
    "tipoVehiculo", "antiguedadVehiculo", "cuotaInicial",
]


# -----------------------------------------------------------------------------
# 2. EXTRACCIÓN Y TRANSFORMACIÓN DE RESPUESTAS FUENTE
# -----------------------------------------------------------------------------

def request_json(session, url, retries=4):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return 200, r.json(), None
            if r.status_code == 429 or 500 <= r.status_code < 600:
                if attempt < retries - 1:
                    wait = min(2 ** attempt, 8)
                    print(f"[retry] HTTP {r.status_code}; {wait}s -> {url}")
                    time.sleep(wait)
                    continue
            return r.status_code, None, r.text[:1000]
        except requests.RequestException as exc:
            if attempt < retries - 1:
                time.sleep(min(2 ** attempt, 8))
                continue
            return None, None, f"{type(exc).__name__}: {exc}"


def extract_rows(payload):
    results = payload.get("results") or []
    if isinstance(results, list):
        return results
    if isinstance(results, dict):
        for value in results.values():
            if isinstance(value, list):
                return value
        return [results]
    return []


def canonical_hash(payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_text(value):
    if pd.isna(value):
        return ""
    s = str(value).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())


def key_from_fields(row, fields, prefix):
    canonical = "|".join(
        f"{field}={normalize_text(row.get(field, ''))}" for field in fields
    )
    return f"{prefix}_{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"


def information_age_bucket(days):
    if pd.isna(days): return "unknown"
    if days < 0: return "future_date_check"
    if days < 30: return "<30d"
    if days < 90: return "30-89d"
    if days < 365: return "90-364d"
    if days < 730: return "1-2y"
    return ">=2y"


def normalize_ratios(df):
    out = df.copy()
    audit = []
    for col in RATIO_COLS:
        if col not in out.columns:
            continue
        x = pd.to_numeric(out[col], errors="coerce")
        out[f"{col}_raw"] = out[col]
        pct = x.copy()
        frac = (x > 0) & (x <= 1)
        pct.loc[frac] = x.loc[frac] * 100
        out[f"{col}_pct"] = pct
        audit.append({
            "column": col,
            "n_non_null": int(x.notna().sum()),
            "n_fractional_0_1_converted": int(frac.sum()),
            "n_values_1_100": int(((x > 1) & (x <= 100)).sum()),
            "n_outside_expected_ratio_range": int(((pct < 0) | (pct > 100)).sum()),
        })
    return out, pd.DataFrame(audit)


def add_information_age(df, snapshot_date):
    out = df.copy()
    if "fechaInformacion" not in out.columns:
        out["information_age_days"] = np.nan
        out["information_age_bucket"] = "unknown"
        return out

    info = pd.to_datetime(out["fechaInformacion"], errors="coerce")
    snap = pd.Timestamp(snapshot_date)
    out["information_age_days"] = (snap - info.dt.normalize()).dt.days
    out["information_age_bucket"] = out["information_age_days"].map(information_age_bucket)
    return out


def read_manifest_csv(path):
    return pd.read_csv(path, dtype=str) if path.exists() else pd.DataFrame()


def append_csv(path, df):
    if df is None or df.empty:
        return
    old = read_manifest_csv(path)
    combined = df if old.empty else pd.concat([old, df], ignore_index=True, sort=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)


def previous_hash(manifest, producto):
    if manifest.empty:
        return None
    req = {"producto", "http_status", "sha256", "run_at"}
    if not req.issubset(manifest.columns):
        return None
    m = manifest[
        (manifest["producto"] == producto)
        & (manifest["http_status"].astype(str) == "200")
        & manifest["sha256"].fillna("").ne("")
    ].sort_values("run_at")
    return None if m.empty else m.iloc[-1]["sha256"]


def quality_flags(df, producto, snapshot_date, snapshot_id, run_at, dup_count):
    rows = []

    def add(column, flag, severity, count, detail):
        rows.append({
            "snapshot_date": snapshot_date,
            "snapshot_id": snapshot_id,
            "run_at": run_at,
            "producto": producto,
            "column": column,
            "flag": flag,
            "severity": severity,
            "count": count,
            "detail": detail,
        })

    if dup_count:
        add("*", "exact_duplicate_rows", "info", dup_count,
            "Eliminados sólo en processed; raw/flattened se conserva.")

    for col in RATIO_COLS:
        pct_col = f"{col}_pct"
        if pct_col in df.columns:
            x = pd.to_numeric(df[pct_col], errors="coerce")
            bad = int(((x < 0) | (x > 100)).sum())
            if bad:
                add(col, "ratio_outside_0_100_after_normalization", "review", bad,
                    "Revisar manualmente; no se elimina.")

    for col in RATE_COLS:
        if col in df.columns:
            x = pd.to_numeric(df[col], errors="coerce")
            negative = int((x < 0).sum())
            extreme = int((x > 1000).sum())
            if negative:
                add(col, "negative_rate_or_sentinel", "review", negative,
                    "Puede ser sentinel/convención. No se elimina automáticamente.")
            if extreme:
                add(col, "extreme_rate_gt_1000", "info", extreme,
                    "Valor extremo; conservar y revisar.")

    if "information_age_days" in df.columns:
        stale = int((pd.to_numeric(df["information_age_days"], errors="coerce") >= 730).sum())
        if stale:
            add("fechaInformacion", "information_age_ge_2y", "info", stale,
                "No implica producto obsoleto.")

    if "offer_variant_key" in df.columns:
        collisions = int((df.groupby("offer_variant_key").size() > 1).sum())
        if collisions:
            add("offer_variant_key", "offer_variant_key_collision", "review", collisions,
                "Puede haber atributos estructurales adicionales no incluidos.")

    return rows


def collision_rows(df, key_col, producto, snapshot_date, snapshot_id, run_at):
    if key_col not in df.columns:
        return []
    counts = df.groupby(key_col).size()
    return [{
        "snapshot_date": snapshot_date,
        "snapshot_id": snapshot_id,
        "run_at": run_at,
        "producto": producto,
        "key_type": key_col,
        "key": key,
        "rows_with_same_key": int(n),
    } for key, n in counts[counts > 1].items()]

def extract_base_b(root):
    """Capturar las cuatro familias en un snapshot inmutable y auditar calidad."""
    now = datetime.now(TZ)
    snapshot_date = now.date().isoformat()
    snapshot_id = now.strftime("%Y%m%d_%H%M%S_%f")
    run_at = now.isoformat()

    root = Path(root)
    run_dir = root / "snapshots" / snapshot_date / snapshot_id
    raw_dir = run_dir / "raw"
    flat_dir = run_dir / "flattened"
    proc_dir = run_dir / "processed"

    # Exist_ok=False garantiza que una colisión accidental falle antes de pisar datos.
    raw_dir.mkdir(parents=True, exist_ok=False)
    flat_dir.mkdir(parents=True, exist_ok=False)
    proc_dir.mkdir(parents=True, exist_ok=False)

    manifest_path = root / "manifest.csv"
    flags_path = root / "quality_flags.csv"
    audit_path = root / "ratio_normalization_audit.csv"
    collisions_path = root / "key_collisions.csv"

    manifest_history = read_manifest_csv(manifest_path)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "ProyectoFinalCAECE/1.0",
        "Accept": "application/json",
        "Accept-Language": "es-AR",
    })

    manifest_rows, flags, audits, collisions = [], [], [], []

    print("snapshot_id:", snapshot_id)
    print("snapshot inmutable:", run_dir.resolve())

    for producto, endpoint in ENDPOINTS.items():
        print(f"\n=== {producto.upper()} ===")
        status, payload, error = request_json(session, BASE_URL + endpoint)
        prev_sha = previous_hash(manifest_history, producto)

        if status != 200 or payload is None:
            print(f"ERROR HTTP {status}: {error}")
            manifest_rows.append({
                "snapshot_date": snapshot_date, "snapshot_id": snapshot_id,
                "run_at": run_at, "producto": producto, "http_status": status,
                "raw_rows": 0, "exact_duplicates_removed": 0, "processed_rows": 0,
                "entidades": 0, "fecha_info_min": "", "fecha_info_max": "",
                "sha256": "", "previous_sha256": prev_sha or "",
                "changed_vs_previous": "", "raw_path": "", "flattened_path": "",
                "processed_path": "", "error": error or "",
            })
            continue

        raw_path = raw_dir / f"{producto}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        flat = pd.json_normalize(extract_rows(payload))
        flat.insert(0, "snapshot_date", snapshot_date)
        flat.insert(1, "snapshot_id", snapshot_id)
        flat.insert(2, "snapshot_run_at", run_at)
        flat.insert(3, "producto_snapshot", producto)

        flat_path = flat_dir / f"{producto}.csv"
        flat.to_csv(flat_path, index=False)

        meta_cols = {"snapshot_date", "snapshot_id", "snapshot_run_at", "producto_snapshot"}
        source_cols = [c for c in flat.columns if c not in meta_cols]
        dup_mask = flat.duplicated(subset=source_cols, keep="first")
        dup_count = int(dup_mask.sum())
        processed = flat.loc[~dup_mask].copy()

        processed, audit = normalize_ratios(processed)
        if not audit.empty:
            audit.insert(0, "snapshot_date", snapshot_date)
            audit.insert(1, "snapshot_id", snapshot_id)
            audit.insert(2, "run_at", run_at)
            audit.insert(3, "producto", producto)
            audits.append(audit)

        processed = add_information_age(processed, snapshot_date)

        processed["product_family_key"] = processed.apply(
            lambda row: key_from_fields(row, FAMILY_FIELDS, "fam"), axis=1
        )

        variant_fields = FAMILY_FIELDS + [c for c in VARIANT_FIELDS if c in processed.columns]
        processed["offer_variant_key"] = processed.apply(
            lambda row: key_from_fields(row, variant_fields, "var"), axis=1
        )
        processed["product_key_version"] = "v2_family_variant"

        for col in RATE_COLS:
            if col in processed.columns:
                x = pd.to_numeric(processed[col], errors="coerce")
                processed[f"{col}__extreme_gt_1000"] = x > 1000
                processed[f"{col}__negative_or_sentinel"] = x < 0

        proc_path = proc_dir / f"{producto}.csv"
        processed.to_csv(proc_path, index=False)

        flags.extend(quality_flags(
            processed, producto, snapshot_date, snapshot_id, run_at, dup_count
        ))
        collisions.extend(collision_rows(
            processed, "product_family_key", producto, snapshot_date, snapshot_id, run_at
        ))
        collisions.extend(collision_rows(
            processed, "offer_variant_key", producto, snapshot_date, snapshot_id, run_at
        ))

        sha = canonical_hash(payload)
        changed = "" if prev_sha is None else str(sha != prev_sha)

        entity_col = next(
            (c for c in ["codigoEntidad", "descripcionEntidad", "entidad"] if c in processed.columns),
            None
        )
        entidades = int(processed[entity_col].nunique()) if entity_col else 0

        if "fechaInformacion" in processed.columns:
            dates = pd.to_datetime(processed["fechaInformacion"], errors="coerce")
            fmin = "" if pd.isna(dates.min()) else dates.min().isoformat()
            fmax = "" if pd.isna(dates.max()) else dates.max().isoformat()
        else:
            fmin = fmax = ""

        manifest_rows.append({
            "snapshot_date": snapshot_date,
            "snapshot_id": snapshot_id,
            "run_at": run_at,
            "producto": producto,
            "http_status": 200,
            "raw_rows": len(flat),
            "exact_duplicates_removed": dup_count,
            "processed_rows": len(processed),
            "entidades": entidades,
            "fecha_info_min": fmin,
            "fecha_info_max": fmax,
            "sha256": sha,
            "previous_sha256": prev_sha or "",
            "changed_vs_previous": changed,
            "raw_path": str(raw_path),
            "flattened_path": str(flat_path),
            "processed_path": str(proc_path),
            "error": "",
        })

        print(
            f"HTTP 200 | raw={len(flat):,} | dup={dup_count:,} | "
            f"processed={len(processed):,} | changed={changed or 'sin previo'}"
        )

    # Combinado del snapshot
    frames = []
    for producto in ENDPOINTS:
        p = proc_dir / f"{producto}.csv"
        if p.exists():
            frames.append(pd.read_csv(p, low_memory=False))
    if frames:
        pd.concat(frames, ignore_index=True, sort=False).to_csv(
            proc_dir / "all_products.csv", index=False
        )

    # Tablas append-only
    append_csv(manifest_path, pd.DataFrame(manifest_rows))
    append_csv(flags_path, pd.DataFrame(flags))
    if audits:
        append_csv(audit_path, pd.concat(audits, ignore_index=True))
    append_csv(collisions_path, pd.DataFrame(collisions))

    # Metadata del snapshot
    (run_dir / "snapshot_metadata.json").write_text(
        json.dumps({
            "snapshot_date": snapshot_date,
            "snapshot_id": snapshot_id,
            "run_at": run_at,
            "immutable_path": str(run_dir.resolve()),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # latest/ es sólo conveniencia; el histórico inmutable no se toca.
    latest_pointer = root / "latest_snapshot.json"

    latest_pointer.write_text(
        json.dumps(
            {
                "snapshot_date": snapshot_date,
                "snapshot_id": snapshot_id,
                "run_at": run_at,
                "path": str(run_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nOK")
    print("Snapshot INMUTABLE:", run_dir.resolve())
    print("Latest pointer:", latest_pointer.resolve())
    print("Manifest append-only:", manifest_path.resolve())
    if len(manifest_rows) != len(ENDPOINTS) or any(r['http_status'] != 200 for r in manifest_rows):
        raise SystemExit('Snapshot B incompleto; conservado para auditoría, no consolidar.')
    return snapshot_id


def acquire(root, *, data_root=None):
    """Capturar un snapshot B nuevo; nunca reemplaza un snapshot histórico."""
    root = Path(root).resolve()
    return extract_base_b(Path(data_root) if data_root is not None else root / 'data_b')


# -----------------------------------------------------------------------------
# 3. TRANSFORMACIÓN Y CONSOLIDACIÓN ANALÍTICA (SIN RED)
# -----------------------------------------------------------------------------

def load_b(root):
    p = Path(root) / 'data_b'
    manifest = read_csv(p / 'manifest.csv', dtype={'snapshot_id': str})
    frames, inventory = [], []
    for meta in sorted((p / 'snapshots').glob('*/*/snapshot_metadata.json')):
        info = json.loads(meta.read_text(encoding='utf-8-sig'))
        sid = info['snapshot_id']; day = info['snapshot_date']
        m = manifest[manifest.snapshot_id.eq(sid)]
        complete = (len(m) == 4 and set(m.producto) == set(FAMILIES)
                    and m.http_status.eq(200).all()
                    and all((meta.parent / 'processed' / f'{f}.csv').exists() for f in FAMILIES))
        inventory.append({'snapshot_id': sid, 'snapshot_date': day, 'completo': complete,
                          'motivo': 'disponible' if complete else 'incompleto'})
        if not complete:
            continue
        for family in FAMILIES:
            d = read_csv(meta.parent / 'processed' / f'{family}.csv', dtype={'codigoEntidad': str})
            if not d.snapshot_id.eq(sid).all() or not d.snapshot_date.eq(day).all():
                raise ValueError(f'Metadatos inconsistentes en {sid}/{family}')
            expected = int(m.loc[m.producto.eq(family), 'processed_rows'].iloc[0])
            if len(d) != expected:
                raise ValueError(f'Cantidad no reconciliada con manifest: {sid}/{family}')
            d['family'] = family
            d['fila_fuente'] = np.arange(1, len(d) + 1)
            frames.append(d)
    if not frames:
        raise ValueError('No hay snapshots completos de Base B.')
    present_ids = {r['snapshot_id'] for r in inventory}
    for row in manifest[['snapshot_id','snapshot_date']].drop_duplicates().itertuples():
        if row.snapshot_id not in present_ids:
            inventory.append({'snapshot_id': row.snapshot_id, 'snapshot_date': row.snapshot_date,
                              'completo': False, 'motivo': 'registrado_sin_archivos_fisicos'})
    b = pd.concat(frames, ignore_index=True)
    inventory = pd.DataFrame(inventory).sort_values(['snapshot_date', 'snapshot_id'])
    selected = inventory[inventory.completo].drop_duplicates('snapshot_date', keep='last')
    inventory['seleccionado_dia'] = inventory.snapshot_id.isin(selected.snapshot_id)
    b['seleccionado_dia'] = b.snapshot_id.isin(selected.snapshot_id)
    b['denominacion_eda'] = b.get('denominacion', pd.Series(index=b.index, dtype=str)).fillna('No informada').str.strip()
    b['denominacion_eda'] = b.denominacion_eda.replace({'Dolares estadounidenses': 'USD', 'Dólares estadounidenses': 'USD'})
    b['tipo_tasa_eda'] = b.get('tipoTasa', pd.Series(index=b.index, dtype=str)).fillna('No informado').str.strip()
    mapping = {'tea': 'tasaEfectivaAnualMaxima', 'cftea': 'costoFinancieroEfectivoTotalMaximo',
               'tea_adelanto': 'tasaEfectivaAnualMaximaAdelantoEfectivo',
               'monto_max': 'montoMaximoOtorgable', 'plazo_meses': 'plazoMaximoOtorgable',
               'ingreso_min': 'ingresoMinimoMensual'}
    exclusions = []
    for dest, src in mapping.items():
        b[dest] = pd.to_numeric(b[src], errors='coerce') if src in b else np.nan
    card = b.family.eq('tarjetas')
    b.loc[card, 'tea'] = pd.to_numeric(b.loc[card, 'tasaEfectivaAnualMaximaFinanciacion'], errors='coerce')
    for metric in mapping:
        invalid = b[metric].lt(0) | ~np.isfinite(b[metric].fillna(0))
        exclusions.append({'metrica': metric, 'valores_invalidos_separados': int(invalid.sum())})
        b.loc[invalid, metric] = np.nan
    b['snapshot_date'] = pd.to_datetime(b.snapshot_date)
    b['fecha_informacion_eda'] = pd.to_datetime(b.fechaInformacion, errors='coerce')
    b['antiguedad_dias_eda'] = (b.snapshot_date - b.fecha_informacion_eda).dt.days
    return b, inventory, pd.DataFrame(exclusions)

def summarize_b(b, by_entity=False, freshness=False):
    keys = ['snapshot_date', 'snapshot_id', 'family', 'denominacion_eda', 'tipo_tasa_eda']
    if by_entity:
        keys += ['codigoEntidad', 'descripcionEntidad']
    if freshness:
        b = b[b.antiguedad_dias_eda.between(0, 365)].copy()
    rows = []
    for key, g in b.groupby(keys, dropna=False, sort=True):
        row = dict(zip(keys, key))
        row.update(n_registros=len(g), n_entidades=g.codigoEntidad.nunique(),
                   n_familias_logicas=g.product_family_key.nunique(),
                   n_fecha_informacion_desconocida=int(g.antiguedad_dias_eda.isna().sum()),
                   n_antiguedad_mayor_365=int(g.antiguedad_dias_eda.gt(365).sum()))
        for metric in ['tea', 'cftea', 'tea_adelanto', 'monto_max', 'plazo_meses', 'ingreso_min']:
            s = g[metric].dropna()
            row[f'{metric}_n'] = len(s)
            for name, q in [('p25', .25), ('mediana', .5), ('p75', .75), ('p95', .95)]:
                row[f'{metric}_{name}'] = s.quantile(q) if len(s) else np.nan
            row[f'{metric}_min'] = s.min() if len(s) else np.nan
            row[f'{metric}_max'] = s.max() if len(s) else np.nan
            bank = g.groupby('codigoEntidad')[metric].median().dropna()
            row[f'{metric}_mediana_entidades'] = bank.median() if len(bank) else np.nan
            row[f'{metric}_n_entidades_validas'] = len(bank)
        rows.append(row)
    return pd.DataFrame(rows)

def transform_b(root, output):
    """Entidades, snapshots y observaciones de ofertas para IAP y contexto ICC."""
    from lib.relacional import exportar_tablas, id_estable, fecha_iso
    b, inventory, exclusions = load_b(root)
    latest_sid = inventory.loc[inventory.completo, 'snapshot_id'].max()
    # Código es identidad del prestador en B; nombre actualizado a la última captura.
    entities = b.sort_values(['snapshot_date','snapshot_id']).drop_duplicates('codigoEntidad',keep='last')[
        ['codigoEntidad','descripcionEntidad']].rename(columns={'codigoEntidad':'codigo_entidad','descripcionEntidad':'nombre'})
    captures = b[['snapshot_id','snapshot_run_at']].drop_duplicates()
    require_unique(captures,['snapshot_id'],'Fecha de captura B')
    snapshots = inventory.merge(captures,on='snapshot_id',how='left',validate='one_to_one').rename(
        columns={'snapshot_date':'fecha','snapshot_run_at':'fecha_captura'})
    snapshots['fecha'] = fecha_iso(snapshots.fecha)
    offers = pd.DataFrame({'observacion_id':[id_estable('oferta',sid,family,row)
        for sid,family,row in b[['snapshot_id','family','fila_fuente']].itertuples(index=False,name=None)]},index=b.index)
    direct = {'snapshot_id':'snapshot_id','codigo_entidad':'codigoEntidad','familia':'family','fila_fuente':'fila_fuente',
        'denominacion':'denominacion_eda','tipo_tasa':'tipo_tasa_eda','clave_familia_provisional':'product_family_key',
        'clave_variante_provisional':'offer_variant_key','nombre_completo':'nombreCompleto','nombre_corto':'nombreCorto',
        'destino_fondos':'destinoFondos','beneficiario':'beneficiario','territorio_validez':'territorioValidez','segmento':'segmento'}
    for target,source in direct.items():
        offers[target] = b[source].astype('string') if source in b else pd.Series(pd.NA,index=b.index,dtype='string')
    offers['fila_fuente'] = b.fila_fuente
    offers['fecha_informacion'] = b.fecha_informacion_eda.dt.strftime('%Y-%m-%d')
    offers['antiguedad_dias'] = b.antiguedad_dias_eda
    numeric = {'tea':'tea','cftea':'cftea','tea_adelanto':'tea_adelanto','monto_min':'montoMinimoOtorgable',
        'monto_max':'monto_max','plazo_meses':'plazo_meses','ingreso_min':'ingreso_min',
        'antiguedad_laboral_min_meses':'antiguedadLaboralMinimaMeses','edad_max':'edadMaximaSolicitada',
        'relacion_cuota_ingreso_pct':'relacionCuotaIngreso_pct','relacion_monto_tasacion_pct':'relacionMontoTasacion_pct',
        'cuota_inicial':'cuotaInicial','cargo_cancelacion_anticipada':'cargoMaximoCancelacionAnticipada',
        'comision_administracion_mantenimiento':'comisionMaximaAdministracionMantenimiento',
        'comision_renovacion':'comisionMaximaRenovacion'}
    separated = {}
    for target,source in numeric.items():
        raw = b[source] if source in b else pd.Series(np.nan,index=b.index)
        values = pd.to_numeric(raw,errors='coerce')
        invalid = values.lt(0) | ~np.isfinite(values.fillna(0))
        separated[target] = int((invalid | (raw.notna() & values.isna())).sum())
        offers[target] = values.mask(invalid)
    validation = exportar_tablas(root,'b',{'entidades':entities,'snapshots':snapshots,'ofertas':offers},output)
    # B permanece nominal por criterio explícito: todavía no hay un consumidor
    # temporal ni unidades/fecha aplicable validadas para cada campo monetario.
    # Denominación UVA/USD y cargos porcentuales no se asumen importes ARS.
    return {'registros':len(b),'snapshots_completos':int(inventory.completo.sum()),
            'snapshots_excluidos':int((~inventory.completo).sum()),'ultimo_snapshot':latest_sid,
            'registros_ultimo':int(b.snapshot_id.eq(latest_sid).sum()),'relacional':validation,
            'calidad_metricas_originales':exclusions.to_dict('records'),'valores_adicionales_separados':separated,
            'ajuste_ipc':{'estado':'diferido', 'criterio':'docs/criterios_datos.md D08; validar unidades, fechas y consumidor antes de deflactar B'}}

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
    parser.add_argument('--root', type=Path, default=None, help='Salida fuente B (compatibilidad); default PROJECT_ROOT/data_b.')
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.root is not None and args.root.resolve() != root / 'data_b' and not args.extract_only:
        parser.error('--root indica la carpeta fuente B; para otro proyecto usar --project-root, o --extract-only.')
    options = {'data_root': args.root}
    if args.extract_only:
        acquire(root, **options)
        return
    build_analytical_run(root, args.out_root, bases=('b',),
                        extract=() if args.offline else ('b',),
                        acquisition_options={'b': options})


if __name__ == '__main__':
    main()
