#!/usr/bin/env python3
"""
Build ``data/lodes_h8_commuter.parquet``: aggregate LODES WAC+RAC JT00 totals
into H3 resolution 8 cells for workplace / residence job skew (WRR).

Usage (from repo root, with PYTHONPATH=. and optional deps installed)::

    python3 scripts/baselines/build_lodes_h8_commuter.py --states ny,ca,nj
    python3 scripts/baselines/build_lodes_h8_commuter.py --states all \\
        --year 2022 --output data/lodes_h8_commuter.parquet

Requirements for the builder: ``duckdb``, ``h3``, ``pyarrow`` (omit ``duckdb`` at scoring runtime).

Data sources:
- WAC: https://lehd.ces.census.gov/data/lodes/LODES8/{st}/wac/{st}_wac_S000_JT00_{year}.csv.gz
- RAC: parallel path replacing ``wac`` with ``rac``, column ``h_geocode``
- GEO xwalk centroids:
  ``https://lehd.ces.census.gov/data/lodes/LODES8/{st}/{st}_xwalk.csv.gz``

WRR semantics (approximate commuter skew):
``wrr_jobs = sum(workplace_jobs) / max(1, sum(RAC.C000 jobs associated with resident blocks))``
per cell. RAC ``C000`` is an employment tally (not Census population).

After the Parquet exists, set ``LODES_H8_COMMUTER_PARQUET`` or rely on the default
``data/lodes_h8_commuter.parquet`` for ``data_sources.lodes_h8_commuter_context``.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO_ROOT, "data", "lodes_h8_commuter.parquet")
CACHE = os.path.join(REPO_ROOT, "data", "cache", "lodes")
DEFAULT_YEAR = os.getenv("LODES_BUILD_YEAR", "2022")


def _state_codes() -> List[str]:
    return [
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "dc", "fl", "ga", "hi", "ia",
        "id", "il", "in", "ks", "ky", "la", "ma", "md", "me", "mi", "mn", "mo", "ms",
        "mt", "nc", "nd", "ne", "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa",
        "pr", "ri", "sc", "sd", "tn", "tx", "ut", "va", "vi", "vt", "wa", "wi", "wv",
        "wy",
    ]


def download(url: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 1000:
        return
    print(f"  fetch {url}")
    urllib.request.urlretrieve(url, dest_path)


def h8_for_lat_lon(lat: float, lon: float) -> str:
    import h3

    fn = getattr(h3, "latlng_to_cell", None)
    if callable(fn):  # h3-py 4.x positional (lat,lng,res)
        return str(fn(lat, lon, 8))
    return str(h3.latlng_to_cell((lat, lon), 8))  # type: ignore[misc]


def aggregate_state(st: str, year: str) -> DefaultDict[str, Tuple[int, int]]:
    """Return dict h8 -> (wac_jobs, rac_c000)."""
    import duckdb

    st = st.lower()
    base = f"https://lehd.ces.census.gov/data/lodes/LODES8/{st}"
    wac_url = f"{base}/wac/{st}_wac_S000_JT00_{year}.csv.gz"
    rac_url = f"{base}/rac/{st}_rac_S000_JT00_{year}.csv.gz"
    xwalk_url = f"{base}/{st}_xwalk.csv.gz"

    os.makedirs(CACHE, exist_ok=True)
    wac_p = os.path.join(CACHE, f"{st}_wac_{year}.csv.gz")
    rac_p = os.path.join(CACHE, f"{st}_rac_{year}.csv.gz")
    xw_p = os.path.join(CACHE, f"{st}_xwalk_{year}.csv.gz")

    download(wac_url, wac_p)
    download(rac_url, rac_p)
    download(xwalk_url, xw_p)

    con = duckdb.connect(":memory:")
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW blk AS
        SELECT
          CAST(w.w_geocode AS VARCHAR) AS geoid,
          COALESCE(CAST(w.C000 AS BIGINT), 0) AS wjobs,
          COALESCE(CAST(r.C000 AS BIGINT), 0) AS racjobs,
          CAST(xw.blklatdd AS DOUBLE) AS lat,
          CAST(xw.blklondd AS DOUBLE) AS lon
        FROM read_csv_auto('{wac_p}') w
        LEFT JOIN read_csv_auto('{rac_p}') r
          ON CAST(w.w_geocode AS VARCHAR) = CAST(r.h_geocode AS VARCHAR)
        INNER JOIN read_csv_auto('{xw_p}') xw
          ON CAST(w.w_geocode AS VARCHAR) = CAST(xw.tabblk2020 AS VARCHAR)
        WHERE xw.blklatdd IS NOT NULL AND xw.blklondd IS NOT NULL
        """
    )
    cur = con.execute("SELECT geoid, wjobs, racjobs, lat, lon FROM blk")
    out: DefaultDict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    batch = cur.fetchmany(250_000)
    while batch:
        for _geoid, wjobs, racjobs, lat, lon in batch:
            if lat is None or lon is None:
                continue
            hid = h8_for_lat_lon(float(lat), float(lon))
            w_acc, r_acc = out[hid]
            out[hid] = (w_acc + int(wjobs or 0), r_acc + int(racjobs or 0))
        batch = cur.fetchmany(250_000)
    print(f"  {st.upper()} H3-L8 cells: {len(out):,}")
    return out


def merge_global(parts: Iterable[Dict[str, Tuple[int, int]]]) -> Dict[str, Tuple[int, int]]:
    merged: Dict[str, Tuple[int, int]] = {}
    for d in parts:
        for hid, pair in d.items():
            w0, r0 = merged.get(hid, (0, 0))
            wj, racj = pair
            merged[hid] = (w0 + wj, r0 + racj)
    return merged


def print_global_wrr_stats(rows: List[Tuple[str, int, int, float]]) -> None:
    """Write global WRR distribution for QA (no geo filter)."""
    vals = sorted(r[3] for r in rows)
    if not vals:
        return
    n = len(vals)

    def pct(p: float) -> float:
        return float(vals[min(int(n * p), n - 1)])

    summaries = {
        "n_h3_cells": n,
        "wrr_jobs_p50": round(pct(0.50), 4),
        "wrr_jobs_p90": round(pct(0.90), 4),
        "wrr_jobs_p95": round(pct(0.95), 4),
        "wrr_jobs_p99": round(pct(0.99), 4),
        "wrr_jobs_max": round(vals[-1], 4),
    }
    path = os.path.join(REPO_ROOT, "analysis", "lodes_h8_wrr_summary.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
    print("Wrote", path)
    print(json.dumps(summaries, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--states",
        required=True,
        help="Comma-separated state abbrevs or 'all' (50 states + DC omitted from some LODES dirs).",
    )
    ap.add_argument("--year", default=DEFAULT_YEAR, help="LODES JT00 snapshot year.")
    ap.add_argument("--output", default=DEFAULT_OUT)
    ns = ap.parse_args()

    if ns.states.strip().lower() == "all":
        states = _state_codes()
    else:
        states = [x.strip().lower() for x in ns.states.split(",") if x.strip()]

    global_cells: Dict[str, Tuple[int, int]] = {}
    part_dicts: List[Dict[str, Tuple[int, int]]] = []
    for st in states:
        try:
            part_dicts.append(dict(aggregate_state(st, ns.year)))
        except Exception as e:
            print(f" Skip {st}: {e}")

    global_cells = merge_global(part_dicts)
    rows_sorted: List[Tuple[str, int, int, float]] = []
    for hid, (wj, rac) in sorted(global_cells.items()):
        wrr = wj / max(1, rac)
        rows_sorted.append((hid, int(wj), int(rac), float(wrr)))

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.table(
            {
                "h8": [r[0] for r in rows_sorted],
                "workplace_jobs": pa.array([r[1] for r in rows_sorted], type=pa.int64()),
                "rac_c000": pa.array([r[2] for r in rows_sorted], type=pa.int64()),
                "wrr_jobs": pa.array([round(r[3], 6) for r in rows_sorted], type=pa.float64()),
            }
        )
        os.makedirs(os.path.dirname(ns.output), exist_ok=True)
        pq.write_table(table, ns.output, compression="zstd")
        print(f"Wrote {ns.output} ({len(rows_sorted):,} cells)")
    except ImportError:
        print("pyarrow not installed — install with: python3 -m pip install pyarrow")
        raise

    print_global_wrr_stats(rows_sorted)


if __name__ == "__main__":
    main()
