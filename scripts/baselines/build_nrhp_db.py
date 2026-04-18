#!/usr/bin/env python3
"""
Build a local SQLite (RTree) index for NRHP locations during deploy/build.

Intended usage (Railway build step):
  python3 scripts/build_nrhp_db.py --out data_cache/nrhp.sqlite

Data source:
  NPS ArcGIS Feature Service (NRHP locations)
  https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer/0
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


LAYER_URL = "https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer/0/query"


def _fetch_count(session: requests.Session) -> int:
    resp = session.get(
        LAYER_URL,
        params={
            "f": "json",
            "where": "1=1",
            "returnCountOnly": "true",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return int(data.get("count") or 0)


def _fetch_page(
    session: requests.Session,
    *,
    offset: int,
    limit: int,
) -> List[Dict[str, Any]]:
    # Keep outFields minimal to reduce payload size.
    out_fields = ",".join(
        [
            "OBJECTID",
            "NRIS_Refnum",
            "RESNAME",
            "ResType",
            "CertDate",
            "Is_NHL",
            "STATUS",
            "State",
        ]
    )
    resp = session.get(
        LAYER_URL,
        params={
            "f": "json",
            "where": "1=1",
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "orderByFields": "OBJECTID",
            "resultOffset": str(offset),
            "resultRecordCount": str(limit),
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    feats = data.get("features") or []
    return [f for f in feats if isinstance(f, dict)]


def _iter_rows(features: Iterable[Dict[str, Any]]) -> Iterable[Tuple[int, str, str, str, int, str, str, float, float]]:
    for f in features:
        attrs = (f.get("attributes") or {}) if isinstance(f.get("attributes"), dict) else {}
        geom = (f.get("geometry") or {}) if isinstance(f.get("geometry"), dict) else {}

        oid = attrs.get("OBJECTID")
        if oid is None:
            continue
        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            continue

        x = geom.get("x")
        y = geom.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        lon = float(x)
        lat = float(y)

        nris = str(attrs.get("NRIS_Refnum") or "")
        name = str(attrs.get("RESNAME") or "")
        res_type = str(attrs.get("ResType") or "")
        cert_date = str(attrs.get("CertDate") or "")
        is_nhl = 1 if str(attrs.get("Is_NHL") or "").strip() in {"1", "Y", "Yes", "true", "True"} else 0
        status = str(attrs.get("STATUS") or "")
        state = str(attrs.get("State") or "")

        yield (oid_int, nris, name, res_type, is_nhl, status, state, lat, lon)


def _init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    cur.execute("DROP TABLE IF EXISTS nrhp_index;")
    cur.execute("DROP TABLE IF EXISTS nrhp;")

    cur.execute(
        """
        CREATE TABLE nrhp (
            id INTEGER PRIMARY KEY,
            nris_refnum TEXT,
            name TEXT,
            res_type TEXT,
            is_nhl INTEGER,
            status TEXT,
            state TEXT,
            lat REAL,
            lon REAL
        );
        """
    )

    # RTree index for fast bbox candidate selection.
    cur.execute(
        """
        CREATE VIRTUAL TABLE nrhp_index USING rtree(
            id,
            min_lon, max_lon,
            min_lat, max_lat
        );
        """
    )
    conn.commit()


def _insert_rows(conn: sqlite3.Connection, rows: List[Tuple[int, str, str, str, int, str, str, float, float]]) -> None:
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO nrhp (id, nris_refnum, name, res_type, is_nhl, status, state, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        rows,
    )
    cur.executemany(
        """
        INSERT INTO nrhp_index (id, min_lon, max_lon, min_lat, max_lat)
        VALUES (?, ?, ?, ?, ?);
        """,
        [(rid, lon, lon, lat, lat) for (rid, _nris, _name, _rt, _nhl, _st, _state, lat, lon) in rows],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NRHP SQLite (RTree) index from NPS ArcGIS service.")
    parser.add_argument("--out", type=str, default="data_cache/nrhp.sqlite", help="Output SQLite path")
    parser.add_argument("--page-size", type=int, default=2000, help="ArcGIS page size")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "HomeFit/1.0 (deploy build)"})

    total = _fetch_count(session)
    if total <= 0:
        print("NRHP: count is 0; nothing to build.")
        return 1

    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    try:
        _init_db(conn)

        page_size = max(100, int(args.page_size))
        inserted = 0

        for offset in range(0, total, page_size):
            feats = _fetch_page(session, offset=offset, limit=page_size)
            rows = list(_iter_rows(feats))
            if not rows:
                continue

            cur = conn.cursor()
            cur.execute("BEGIN;")
            _insert_rows(conn, rows)
            conn.commit()

            inserted += len(rows)
            print(f"NRHP: {inserted}/{total} rows inserted...")

        # Basic indexes for attribute lookups (optional; keep minimal)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nrhp_state ON nrhp(state);")
        conn.commit()
    finally:
        conn.close()

    # Atomic replace
    os.replace(str(tmp_path), str(out_path))
    print(f"NRHP: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

