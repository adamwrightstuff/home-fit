#!/usr/bin/env python3
"""
Offline: add `household_type` to each catalog place (score.livability_pillars.diversity.household_type) from the
household type pull joined to the geography the diversity read used (docs/WHO_LIVES_HERE.md). No API calls. Additive: no
other field changes, no scoring. Places with no match keep no household_type (the panel then omits the group).

  python3 scripts/catalog/add_household_type_offline.py --join <pull_dir>/household_type_by_place.json
"""
import argparse, glob, json
from pathlib import Path

STATE_FIPS = {"AZ": "04", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13", "IL": "17", "IN": "18", "MA": "25",
              "MD": "24", "NC": "37", "NJ": "34", "NV": "32", "NY": "36", "PA": "42", "TX": "48", "WA": "53"}

REPO = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--join", required=True)
    a = ap.parse_args()
    join = json.load(open(a.join))
    added = missing = 0
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(path).name.split("_metro_")[0]
        out = []
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            s = r.get("score") if r.get("success") else None
            if isinstance(s, dict):
                h = join.get(f"{metro}|{r['catalog']['name']}|{STATE_FIPS.get(r['catalog'].get('state_abbr'))}")
                lp = s.get("livability_pillars")
                if h and isinstance(lp, dict):
                    div = lp.get("diversity")
                    if not isinstance(div, dict):
                        div = lp["diversity"] = {}
                    div["household_type"] = {
                        "pct_with_children": h["pct_with_children"], "pct_living_alone": h["pct_living_alone"],
                        "pct_married_couple": h["pct_married_couple"], "pct_family": h["pct_family"],
                        "pct_with_65plus": h["pct_with_65plus"], "households": h["households"],
                        "geo": h["geo"], "geoid": h["geoid"], "source": "ACS 2022 5-year B11001, B11005, B11007",
                    }
                    added += 1
                else:
                    missing += 1
            out.append(json.dumps(r, ensure_ascii=False))
        Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"household_type added for {added} places, none for {missing}")


if __name__ == "__main__":
    main()
