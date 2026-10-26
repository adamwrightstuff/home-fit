#!/usr/bin/env python3
"""
Education pin sensitivity (DPv2 P6), offline: re-score each place with the pin moved SHIFT_MI miles north, south, east and
west and store how far the score moves in breakdown.pin_sensitivity. No API calls (sockets are blocked), no score changes.

  PYTHONPATH=. python3 scripts/catalog/compute_education_pin_sensitivity.py [--metro la] [--dry-run]

Stored: {shift_mi, max_change, mean_change, n_shifts, n_no_score}. A shift that lands where no school is rated counts in
n_no_score and not in the changes.

The flag: a place whose largest change exceeds FLAG_CUTOFF points gets a data_warnings entry and summary.pin_sensitive
(the score is still valid, so the pillar is not marked degraded). FLAG_CUTOFF = 15 is an owner judgment (2026-10-26), no source.
`--flag-only` re-applies the flag from the stored measurement without re-scoring. A re-run of rescore_education_offline.py
replaces the breakdown and drops this measurement: run this script again afterwards.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import math
import os
import socket
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)


def _blocked(*a, **k):
    raise OSError("network blocked: this script is offline")


socket.socket.connect = _blocked
socket.create_connection = _blocked

from data_sources import school_snapshot  # noqa: E402
from data_sources.schools_api import normalize_state  # noqa: E402
from pillars.schools import get_school_data  # noqa: E402
from scripts.catalog.rescore_education_offline import _area_type  # noqa: E402

SHIFT_MI = 0.5
FLAG_CUTOFF = 15.0   # owner judgment 2026-10-26, no source
FLAG_TEXT = "pin_sensitive: the score moves more than 15 points when the pin moves 0.5 mile"


def _apply_flag(p: dict) -> bool:
    ps = (p.get("breakdown") or {}).get("pin_sensitivity") or {}
    dq = p.setdefault("data_quality", {})
    warns = [w for w in (dq.get("data_warnings") or []) if not str(w).startswith("pin_sensitive")]
    sm = p.setdefault("summary", {})
    sm.pop("pin_sensitive", None)
    flagged = ps.get("max_change") is not None and ps["max_change"] > FLAG_CUTOFF
    if flagged:
        warns.append(FLAG_TEXT)
        sm["pin_sensitive"] = FLAG_TEXT
    dq["data_warnings"] = warns
    return flagged


def _score(sc, st, cat, lat, lon, early):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            s, _, bd = get_school_data((sc.get("location_info") or {}).get("zip"), st, (sc.get("location_info") or {}).get("city"),
                                       lat, lon, _area_type(sc), cat.get("name"), early_ed_override=early,
                                       early_ed_unknown=early is None)
        except Exception:  # noqa: BLE001
            return None
    return s if bd.get("model") == "zoned_v1" else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--metro", action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--flag-only", action="store_true", help="re-apply the flag from the stored measurement, no re-scoring")
    args = ap.parse_args()
    dlat = SHIFT_MI / 69.0
    for path in sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(path).split("_metro")[0]
        if args.metro and metro not in args.metro:
            continue
        out, n, nflag = [], 0, 0
        for line in open(path):
            row = json.loads(line)
            sc, cat = row.get("score") or {}, row.get("catalog") or {}
            p = (sc.get("livability_pillars") or {}).get("quality_education")
            st = normalize_state((sc.get("location_info") or {}).get("state"))
            if p and args.flag_only:
                nflag += _apply_flag(p)
            elif p and p.get("score") is not None and school_snapshot.load_state(st):
                lat, lon = float(cat["lat"]), float(cat["lon"])
                early = (p.get("breakdown") or {}).get("early_ed")
                base = _score(sc, st, cat, lat, lon, early)
                if base is not None:
                    dlon = dlat / math.cos(math.radians(lat))
                    shifted = [_score(sc, st, cat, la, lo, early)
                               for la, lo in ((lat + dlat, lon), (lat - dlat, lon), (lat, lon + dlon), (lat, lon - dlon))]
                    ok = [abs(s - base) for s in shifted if s is not None]
                    p["breakdown"]["pin_sensitivity"] = {
                        "shift_mi": SHIFT_MI,
                        "max_change": round(max(ok), 2) if ok else None,
                        "mean_change": round(sum(ok) / len(ok), 2) if ok else None,
                        "n_shifts": len(ok), "n_no_score": 4 - len(ok),
                    }
                    n += 1
                    nflag += _apply_flag(p)
            out.append(json.dumps(row, ensure_ascii=False))
        print(f"{metro}: measured {n}, flagged {nflag}")
        if not args.dry_run:
            with open(path + ".tmp", "w") as f:
                f.write("\n".join(out) + "\n")
            os.replace(path + ".tmp", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
