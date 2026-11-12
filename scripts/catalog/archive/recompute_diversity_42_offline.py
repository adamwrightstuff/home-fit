#!/usr/bin/env python3
"""
Diversity recompute for the 42 places that are not on the new race formula or could not be checked, from the cached
state ACS pull. Needs ~42 free Census geocoder lookups (place and tract codes). Never writes to the catalog.

Geography rule (matches b73836b): the Census place (county subdivision in New England) unless it has more than 200,000
adults 25+, then the tract.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/recompute_diversity_42_offline.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from data_sources import census_api
from pillars.diversity import RACE_CATEGORY_COUNT, RACE_SUBSET_KEYS, _normalized_entropy

ROOT = Path(__file__).resolve().parents[2]
PULL = ROOT / "data/census_pull_2026-10-28"
CEILING = 200_000
PLACES = {
    "dallas": ["Carrollton", "Southlake"], "houston": ["Seabrook", "Spring"],
    "nyc": ["Cold Spring Harbor", "Croton-on-Hudson", "Cranford", "NoHo", "Maspeth", "Southport"],
    "philadelphia": ["Blue Bell", "Doylestown", "Somerton", "Rittenhouse Square", "Society Hill", "Radnor"],
    "phoenix": ["Sun Lakes", "Youngtown", "Melrose District", "Peoria", "Scottsdale", "Sun City", "Surprise", "Tolleson"],
    "raleigh": ["Apex", "Benson"], "sacramento": ["Rancho Murieta", "Natomas", "Oak Park"], "seattle": ["Ballard"],
    "sf": ["Foster City", "Fremont", "Almaden Valley", "Bayview", "Bernal Heights", "Diamond Heights", "Dogpatch",
           "Evergreen", "Financial District"],
    "denver": ["Franktown", "Idledale", "Sedalia"],
}


def load(kind):
    """geoid -> {var: float} merged over chunks. kind: div_tract | div_place | div_cousub."""
    out = {}
    for f in glob.glob(str(PULL / f"{kind}_*.json")):
        r = json.load(open(f))
        h = r[0]
        geo = [c for c in h if c in ("state", "county", "tract", "place", "county subdivision")]
        for row in r[1:]:
            g = "".join(row[h.index(c)] for c in geo)
            d = out.setdefault(g, {})
            for i, c in enumerate(h):
                if c not in geo:
                    try:
                        d[c] = max(0.0, float(row[i]))
                    except (TypeError, ValueError):
                        d[c] = 0.0
    return out


def components(d):
    race = {f"B02001_{i:03d}E": d.get(f"B02001_{i:03d}E", 0) for i in range(2, 11)}
    rv = [v for k, v in race.items() if k not in RACE_SUBSET_KEYS]
    re_ = _normalized_entropy(rv, RACE_CATEGORY_COUNT) if sum(1 for v in rv if v > 0) >= 2 else None
    inc = [d.get(f"B19001_{i:03d}E", 0) for i in range(2, 18)]
    n = sum(1 for v in inc if v > 0)
    ie = _normalized_entropy(inc, n) if n >= 2 else None
    g = lambda lo, hi: sum(d.get(f"B01001_{i:03d}E", 0) for i in range(lo, hi + 1))
    youth, prime, sen = g(3, 6) + g(27, 30), g(7, 19) + g(31, 43), g(20, 25) + g(44, 49)
    ae = _normalized_entropy([youth, prime, sen], 3) if youth + prime + sen > 0 else None
    return re_, ie, ae


def main():
    tract, place, cousub = load("div_tract"), load("div_place"), load("div_cousub")
    out = []
    for p in sorted(glob.glob(str(ROOT / "data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(p).name.split("_metro")[0]
        want = PLACES.get(metro, [])
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            name = r["catalog"].get("name")
            if name not in want:
                continue
            s = r["score"]
            co = s["coordinates"]
            lat, lon = co["lat"], co["lon"]
            div = s["livability_pillars"]["diversity"]
            rec = dict(metro=metro, name=name, stored_score=div["score"], stored=div.get("breakdown"))
            tr = census_api.get_census_tract(lat, lon)
            pg = census_api.get_place_fips_for_coordinates(lat, lon)
            data, geo = None, None
            if pg:
                gid = (pg["state_fips"] + pg["county_fips"] + pg["cousub_fips"]) if pg.get("geo_type") == "county_subdivision" \
                    else pg["state_fips"] + pg["place_fips"]
                d = (cousub if pg.get("geo_type") == "county_subdivision" else place).get(gid)
                if d and d.get("B15003_001E", 0) <= CEILING and d.get("B02001_001E", 0) > 0:
                    data, geo = d, pg.get("geo_type", "place")
            if data is None and tr:
                d = tract.get(tr["state_fips"] + tr["county_fips"] + tr["tract_fips"])
                if d and d.get("B02001_001E", 0) > 0:
                    data, geo = d, "tract"
            if data is None:
                rec.update(status="no_data", reason="place and tract both unavailable" if tr or pg else "geocoder returned nothing")
            else:
                re_, ie, ae = components(data)
                vals = [v for v in (re_, ie, ae) if v is not None]
                rec.update(status="ok", geo_level=geo, total_pop=data.get("B02001_001E"), adults_25_plus=data.get("B15003_001E"),
                           race=None if re_ is None else round(re_, 1), income=None if ie is None else round(ie, 1),
                           age=None if ae is None else round(ae, 1),
                           headline=round(sum(vals) / len(vals), 1) if vals else None)
            out.append(rec)
            print(rec["metro"], name, rec.get("status"), rec.get("geo_level"), rec.get("headline"), "stored", div["score"])
    dest = ROOT / "analysis/diversity_42_recompute.jsonl"
    dest.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    ok = [r for r in out if r["status"] == "ok" and r["headline"] is not None]
    print(f"{len(out)} places, {len(ok)} recomputed, {len(out) - len(ok)} no data; side file {dest}")


if __name__ == "__main__":
    main()
