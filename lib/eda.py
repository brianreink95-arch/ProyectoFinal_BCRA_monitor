"""Adaptador del EDA final: usa las mismas reglas que los pipelines base_a.py, base_b.py y base_c.py."""
from pathlib import Path
import sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'lib/common.py').is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib.common import (FAMILIES, CANONICAL_C, SEGMENTS, RATE_LABELS,
                             fingerprint, resolve_data_root, read_csv, require_unique,
                             save_table, runtime_metadata, get_pipeline)
load_a = get_pipeline('a').load_a
load_b = get_pipeline('b').load_b
summarize_b = get_pipeline('b').summarize_b
choose_c = get_pipeline('c').choose_c
build_c = get_pipeline('c').build_c
transitions_c = get_pipeline('c').transitions_c
load_c = get_pipeline('c').load_c
