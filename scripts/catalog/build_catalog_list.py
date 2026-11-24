#!/usr/bin/env python3
"""
Build the slimmed catalog list served by GET /catalog/list (see catalog_api.py).

Writes data_cache/catalog_list.json and catalog_list.json.gz from data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl.
Run at image build time so the API never parses the catalog per request:

  PYTHONPATH=. python3 scripts/catalog/build_catalog_list.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import catalog_api  # noqa: E402


def main() -> None:
    n, source = catalog_api.build_list_files()
    print(f"catalog list: {n} places, source={source}")
    if not n:
        sys.exit("no catalog rows found; is data/ present in this build?")


if __name__ == "__main__":
    main()
