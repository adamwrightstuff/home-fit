#!/usr/bin/env python3
"""
Offline healthcare recompute for the distance-based pharmacy term (design principles v2).

Pharmacy points = 15 x _pharmacy_distance_fraction(nearest pharmacy km), from the stored nearest_pharmacy_km.
With no stored pharmacy and hospitals, urgent care or clinics mapped, the pharmacy part is unknown and the score is
scaled over the other four parts; with nothing mapped it stays a real zero. The hospital bonus is rebuilt from the
stored hospital count (stored totals reproduce from the parts plus that bonus). Doctors are not stored, so the
"anything mapped" test uses hospitals, urgent care and clinics only.

Writes new files only. Usage, from the repo root:
  PYTHONPATH=. python3 scripts/catalog/recompute_healthcare_pharmacy_distance_offline.py --out-dir analysis/hc_recompute
"""
from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.healthcare_access import _pharmacy_distance_fraction, healthcare_total

PART_KEYS = ("hospital_access", "primary_care", "specialized_care", "emergency_services")
VERSION = "healthcare_pharmacy_distance_offline_2026-10-28"


def recompute(row: dict):
    hc = ((row.get("score") or {}).get("livability_pillars") or {}).get("healthcare_access")
    if not hc or hc.get("score") is None:
        return row, None
    b, s = hc["breakdown"], hc["summary"]
    if any(b.get(k) is None for k in PART_KEYS) or s.get("hospital_count") is None:
        return row, None
    nearest = s.get("nearest_pharmacy_km")
    mapped = (s.get("hospital_count") or 0) + (s.get("urgent_care_count") or 0) + (s.get("clinic_count") or 0) > 0
    note = ""
    if nearest is not None:
        pharm = 15.0 * _pharmacy_distance_fraction(float(nearest))
    elif mapped:
        pharm, note = None, "pharmacies_unknown"
    else:
        pharm, note = 0.0, "nothing_mapped_real_zero"
    bonus = min(5.0, max(0, int(s["hospital_count"]) - 1) * 0.5)
    parts = {k: float(b[k]) for k in PART_KEYS}
    parts["pharmacies"] = pharm
    new_score = round(healthcare_total(parts, bonus), 1)

    out = copy.deepcopy(row)
    nhc = out["score"]["livability_pillars"]["healthcare_access"]
    nhc["score"] = new_score
    if nhc.get("weight") is not None:
        nhc["contribution"] = round(new_score * float(nhc["weight"]) / 100.0, 4)
    nhc["breakdown"]["pharmacies"] = None if pharm is None else round(pharm, 1)
    if pharm is None:
        nhc["summary"]["pharmacies_unknown"] = True
    nhc["dpv2_recompute"] = {"version": VERSION, "stored_score": hc["score"], "stored_pharmacies": b.get("pharmacies"), "note": note}
    cat = row["catalog"]
    rec = dict(place=cat["name"], state=cat["state_abbr"], area_type=(hc.get("area_classification") or {}).get("area_type"),
               nearest_pharmacy_km=nearest, stored_score=hc["score"], new_score=new_score, delta=round(new_score - hc["score"], 1),
               stored_pharmacies=b.get("pharmacies"), new_pharmacies=None if pharm is None else round(pharm, 1), note=note)
    return out, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(glob.glob(args.glob)):
        with open(path) as fin, open(out_dir / Path(path).name, "w") as fout:
            for line in fin:
                row = json.loads(line)
                new_row, rec = recompute(row)
                if rec:
                    rec["file"] = Path(path).name
                    records.append(rec)
                fout.write(json.dumps(new_row, ensure_ascii=False) + "\n")
    with open(out_dir / "diff.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(f"wrote {len(records)} place records to {out_dir}")


if __name__ == "__main__":
    main()
