#!/usr/bin/env python3
"""
Offline healthcare recompute for the one-scale design (design principles v2), from a fresh 10 km read.

Per place, from analysis/hc_fresh_read/healthcare_fresh.json:
  hospital access   distance to the nearest hospital (15); the hospital count is not scored
  primary care      clinics plus doctors per resident vs the catalog-median supply (25)
  emergency         distance to the nearest emergency-room hospital (10)
  pharmacies        distance to the nearest pharmacy (15); unknown when clinics or hospitals are mapped but no pharmacy
Specialized care keeps its stored value (its input includes an NPI registry fallback that is not stored). The hospital bonus
is rebuilt from the fresh hospital count. Places without a successful fresh read keep their stored values. New files only.

  PYTHONPATH=. python3 scripts/catalog/recompute_healthcare_dpv2_offline.py --fresh analysis/hc_fresh_read/healthcare_fresh.json --out-dir analysis/hc_dpv2
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

from pillars.healthcare_access import (  # noqa: E402
    HEALTHCARE_BUDGETS, HEALTHCARE_RADIUS_M, _distance_to_hospital_score, _load_supply_scale, _pharmacy_distance_fraction,
    _score_hospitals, capacity_score, healthcare_total, people_within,
)

VERSION = "healthcare_dpv2_offline_2026-10-28"


def nearest(items, only_er=False):
    d = [f["d"] for f in items if f.get("d") is not None and (f["er"] or not only_er)]
    return min(d) if d else None


def recompute(row, fresh, scale):
    hc = ((row.get("score") or {}).get("livability_pillars") or {}).get("healthcare_access")
    if not hc or hc.get("score") is None:
        return row, None
    cat = row["catalog"]
    v = fresh.get(f"{cat['name']}|{cat['state_abbr']}")
    if not v or v.get("outcome") not in ("ok", "empty"):
        return row, None
    b = hc["breakdown"]
    if b.get("specialized_care") is None:
        return row, None
    lat, lon = float(cat["lat"]), float(cat["lon"])
    residents = people_within(lat, lon, HEALTHCARE_RADIUS_M)
    hospitals, clinics, doctors = v.get("hospitals", []), v.get("clinics", []), v.get("doctors", [])
    pharmacies, urgent = v.get("pharmacies", []), v.get("urgent_care", [])

    cap = None  # hospital count is not scored (a count is not capacity); hospital access is the distance part only
    nh = nearest(hospitals)
    if nh is None:
        _, db = _score_hospitals(lat, lon)
        nh = db["distance_km"] if db else float("inf")
    dist = _distance_to_hospital_score(nh, 15.0)
    hospital_access = dist
    primary = capacity_score(len(clinics) + len(doctors), residents, scale["expected_clinics_doctors_per_1000"], 1000.0, 25.0)
    if primary is not None:
        primary = min(25.0, primary)
    ner = nearest(hospitals, only_er=True)
    if ner is None:
        _, db = _score_hospitals(lat, lon)
        ner = db["distance_km"] if db else float("inf")
    emergency = min(10.0, _distance_to_hospital_score(ner, 10.0))
    nph = nearest(pharmacies)
    mapped = bool(hospitals or urgent or clinics or doctors)
    note = ""
    if nph is not None:
        pharm = 15.0 * _pharmacy_distance_fraction(nph)
    elif mapped:
        pharm, note = None, "pharmacies_unknown"
    else:
        pharm, note = 0.0, "nothing_mapped_real_zero"
    budgets = dict(HEALTHCARE_BUDGETS)
    budgets["hospital_access"] = 15.0
    if residents is None:
        note = (note + ";" if note else "") + "residents_unknown"
    parts = {"hospital_access": hospital_access, "primary_care": primary, "specialized_care": float(b["specialized_care"]),
             "emergency_services": emergency, "pharmacies": pharm}
    bonus = min(5.0, max(0, len(hospitals) - 1) * 0.5)
    new_score = round(healthcare_total(parts, bonus, budgets), 1)

    out = copy.deepcopy(row)
    n = out["score"]["livability_pillars"]["healthcare_access"]
    n["score"] = new_score
    if n.get("weight") is not None:
        n["contribution"] = round(new_score * float(n["weight"]) / 100.0, 4)
    n["breakdown"].update(
        hospital_access=round(hospital_access, 1), primary_care=None if primary is None else round(primary, 1),
        emergency_services=round(emergency, 1), pharmacies=None if pharm is None else round(pharm, 1))
    sm = n["summary"]
    sm.update(hospital_count=len(hospitals), urgent_care_count=len(urgent), clinic_count=len(clinics), pharmacy_count=len(pharmacies),
              facility_radius_m=HEALTHCARE_RADIUS_M, residents_within_radius=None if residents is None else round(residents))
    if nph is not None:
        sm["nearest_pharmacy_km"] = round(nph, 2)
    else:
        sm.pop("nearest_pharmacy_km", None)
    if pharm is None:
        sm["pharmacies_unknown"] = True
    else:
        sm.pop("pharmacies_unknown", None)
    n["dpv2_recompute"] = {"version": VERSION, "stored_score": hc["score"], "stored_breakdown": {k: b.get(k) for k in b}, "note": note}
    rec = dict(place=cat["name"], state=cat["state_abbr"], area_type=(hc.get("area_classification") or {}).get("area_type"),
               stored_score=hc["score"], new_score=new_score, delta=round(new_score - hc["score"], 1),
               stored_hospital=b.get("hospital_access"), new_hospital=round(hospital_access, 1),
               stored_primary=b.get("primary_care"), new_primary=None if primary is None else round(primary, 1),
               stored_emergency=b.get("emergency_services"), new_emergency=round(emergency, 1),
               stored_pharm=b.get("pharmacies"), new_pharm=None if pharm is None else round(pharm, 1), residents=None if residents is None else round(residents), note=note)
    return out, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", required=True)
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    fresh, scale = json.load(open(args.fresh)), _load_supply_scale()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(glob.glob(args.glob)):
        with open(path) as fin, open(out_dir / Path(path).name, "w") as fout:
            for line in fin:
                new_row, rec = recompute(json.loads(line), fresh, scale)
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
