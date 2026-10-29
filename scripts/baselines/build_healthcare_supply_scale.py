#!/usr/bin/env python3
"""
Build data/healthcare_supply_scale.json: primary care facility supply per resident within one fixed radius, from a fresh read.

The primary care part compares clinics and doctors within 10 km to the number of residents within 10 km, with one scale for
every place (no area type, no density input). The reference values are catalog medians, a descriptive scale and not an
external standard (TODO: source; the federal primary care shortage ratio of 3,500 residents per provider counts providers,
OpenStreetMap lists facilities).

Inputs: the fresh read (analysis/hc_fresh_read/run.py output) and the catalog place list. Population within the radius is
density x disk area from the local tract tables (an approximation).

  PYTHONPATH=. python3 scripts/baselines/build_healthcare_supply_scale.py --fresh analysis/hc_fresh_read/healthcare_fresh.json
"""
import argparse
import glob
import json
import statistics as st
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.healthcare_access import HEALTHCARE_RADIUS_M, people_within  # noqa: E402

OUT = REPO_ROOT / "data" / "healthcare_supply_scale.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", required=True)
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    args = ap.parse_args()
    fresh = json.load(open(args.fresh))
    prim, n = [], 0
    for path in sorted(glob.glob(args.glob)):
        for line in open(path):
            c = json.loads(line)["catalog"]
            v = fresh.get(f"{c['name']}|{c['state_abbr']}")
            if not v or v.get("outcome") != "ok":
                continue
            pop = people_within(float(c["lat"]), float(c["lon"]), HEALTHCARE_RADIUS_M)
            if not pop:
                continue
            n += 1
            prim.append(1000.0 * (len(v["clinics"]) + len(v["doctors"])) / pop)
    doc = {
        "radius_m": HEALTHCARE_RADIUS_M,
        "expected_clinics_doctors_per_1000": round(st.median(prim), 4),
        "n_places": n,
        "status": "DESCRIPTIVE: catalog medians of a fresh 10 km read, not an external standard. TODO: source a published benchmark.",
        "source_fresh_read": Path(args.fresh).name,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    print(doc)


if __name__ == "__main__":
    main()
