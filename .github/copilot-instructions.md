# Project instructions

CAECE Final Project: Observatorio de Financiamiento y Endeudamiento en Argentina.
Read ESTADO_PROYECTO.md and README.md first. Consult docs/diseno_tablas.md for the table contract and docs/plan_ml.md for modeling scope.

- Persist exactly the 13 relational tables in config/esquema_tablas.json: 3 A (including the IPC deflator), 3 B, 7 C.
- Every table must have a grain, PK/FK and a mapped ICC/IAP/IEF consumer. Do not export unused EDA views.
- Pipelines base_a.py/base_b.py/base_c.py own extraction and transformation. actualizar_bases.py coordinates them.
- Base CLI default: extract+transform. --offline reprocesses saved sources; --extract-only acquires only.
- Coordinator defaults to offline ABC; --extract updates selected sources. Publish latest only after completion.
- lib/common.py owns runs/files. lib/relacional.py enforces types, nullability, PK/FK and atomic CSV row counts.
- lib/eda.py reuses domain functions for explanatory notebooks; notebooks do not run operational acquisition.
- Preserve historical sources, B snapshots and C captures, including audit evidence of incomplete acquisitions.
- New C acquisitions do not export legacy targets/panels/bundles. Retain old source artifacts for historical EDA.
- A units/absolute stock scale remain explicit; preserve 1199 precoverage exception without changing original zeros.
- B observation identity is snapshot+family+source row, not a persistent product ID. Do not silently deduplicate variants.
- C CUIT is the company unit. Preserve 100 companies/102 memberships, 404s, gaps and reported zeros.
  Positive balances govern active risk and concentration. Sector membership must not multiply training rows.
- C creditor IDs are technical names, not an automatic legal crosswalk to B entity codes.
- Acquisition failure cannot silently feed a successful run. Online C transforms the exact newly acquired full-master run.
  Smoke tests require --extract-only. A validates staging with the catalog and table contract before publishing cache.
- ML work follows the documented plan: feature dictionaries and temporal splits before models; baselines first.
  Fit preprocessing/calibration on train only. Do not claim point-in-time historical validation without vintages.
- Model targets, scores and new data sources require a defined consumer. Do not create unused stub scripts/dependencies.
- Keep code paths portable, update docs, and run relevant semantic and relational tests after changes.

- Start ICC work from LEEME_ICC.md. The PH S1 pilot lives in ml/ and independent extensions live under experimentos/icc/.
- Base C IEF runs through ml/ief.py, ml/baseline_ief.py and ml/isolation_ief.py. Read docs/modelo_ief.md before editing it. Preserve the fixed temporal splits and train reference. Use a new output directory for reproductions, and run docs.validar_ief and docs.validar_modelo_ief after changes.
