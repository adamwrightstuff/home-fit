"""
Build precinct election lookup JSON from VEST shapefiles + 2024 CSV.

Source: Voting and Election Science Team (VEST) — Harvard Dataverse
  2020 shapefiles: doi:10.7910/DVN/K7760H  (per-state zips with geometry)
  2024 results:    doi:10.7910/DVN/NYTPDU  (per-state CSV, no geometry)

The 2020 shapefile provides geometry (precinct centroids) and 2020 votes.
The 2024 CSV is joined to 2020 geometry first at precinct level (county_fips +
normalized precinct name), falling back to county-level aggregates for unmatched
precincts.

Usage:
    PYTHONPATH=. python3 scripts/collectors/build_election_lookup.py \
        --state NY \
        --shp2020 ~/Downloads/ny_2020/ny_2020.shp \
        --csv2024 ~/Downloads/2024-ny-precinct-general.csv

Output: data/election/<state_lower>_precincts.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

try:
    import geopandas as gpd
except ImportError:
    print("geopandas required: pip install geopandas")
    sys.exit(1)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_OUTPUT_DIR = os.path.join(_REPO_ROOT, "data", "election")

# Per-state precinct name column in the 2020 shapefile
_PRECINCT_COL = {
    "NY": "PRECINCT",
    "CA": "SRPREC",
    "CT": "NAME20",
    "NJ": "MUNINAME",
}

# Per-state county FIPS derivation
_STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
    "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}

_SPLIT_MODES = frozenset({
    "ELECTION DAY", "EARLY VOTING", "ABSENTEE", "MAIL-IN",
    "PROVISIONAL", "EMERGENCY", "FEDERAL/OVERSEAS", "STATE/FED",
})


def _normalize(s: str) -> str:
    """Normalize precinct name for fuzzy matching."""
    s = s.upper().strip()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_vote_cols(columns: list, year: str, party: str) -> list:
    year2 = year[-2:]
    prefix = f"G{year2}PRE{party[0].upper()}"
    return [c for c in columns if c.upper().startswith(prefix)]


def _sum_cols(row, cols: list) -> int:
    total = 0
    for c in cols:
        try:
            total += int(row.get(c) or 0)
        except (ValueError, TypeError):
            pass
    return total


def _county_fips_from_row(row, state_fips: str) -> str | None:
    sfp = str(row.get("STATEFP") or row.get("STATEFP20") or "").strip()
    cfp = str(row.get("COUNTYFP") or row.get("COUNTYFP20") or "").strip()
    if sfp and cfp:
        return f"{sfp.zfill(2)}{cfp.zfill(3)}"
    if cfp and state_fips:
        return f"{state_fips.zfill(2)}{cfp.zfill(3)}"
    fipsc = str(row.get("FIPS_CODE") or "").strip()
    if fipsc:
        return fipsc.zfill(5)
    cnty = str(row.get("CNTY_CODE") or "").strip()
    if cnty and state_fips:
        return f"{state_fips.zfill(2)}{cnty.zfill(3)}"
    # NJ: COUNTY name — resolved later via county_name_to_fips
    return None


def _load_2024_votes(csv_path: str) -> tuple[dict, dict]:
    """
    Returns:
      precinct_votes: (county_fips, norm_precinct) -> (dem, rep)
      county_votes:   county_fips -> (dem, rep)
    """
    # Raw accumulators
    prec_dem: dict[tuple, int] = {}
    prec_rep: dict[tuple, int] = {}
    total_dem: dict[str, int] = {}
    total_rep: dict[str, int] = {}
    split_dem: dict[str, int] = {}
    split_rep: dict[str, int] = {}

    sep = "\t" if csv_path.endswith(".tab") else ","
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            office = (row.get("office") or "").upper()
            if "PRESIDENT" not in office:
                continue
            fips = str(row.get("county_fips") or "").strip()
            prec = _normalize(row.get("precinct") or "")
            party = (row.get("party_simplified") or "").upper().strip()
            if party not in ("DEMOCRAT", "REPUBLICAN"):
                continue
            try:
                votes = int(row.get("votes") or 0)
            except ValueError:
                continue
            mode = (row.get("mode") or "").upper().strip()

            # Precinct-level accumulation (all modes summed per precinct)
            key = (fips, prec)
            if party == "DEMOCRAT":
                prec_dem[key] = prec_dem.get(key, 0) + votes
            else:
                prec_rep[key] = prec_rep.get(key, 0) + votes

            # County-level fallback
            if mode == "TOTAL":
                if party == "DEMOCRAT":
                    total_dem[fips] = total_dem.get(fips, 0) + votes
                else:
                    total_rep[fips] = total_rep.get(fips, 0) + votes
            elif mode in _SPLIT_MODES:
                if party == "DEMOCRAT":
                    split_dem[fips] = split_dem.get(fips, 0) + votes
                else:
                    split_rep[fips] = split_rep.get(fips, 0) + votes

    precinct_votes = {}
    all_keys = set(prec_dem) | set(prec_rep)
    for k in all_keys:
        precinct_votes[k] = (prec_dem.get(k, 0), prec_rep.get(k, 0))

    county_votes = {}
    all_fips = set(total_dem) | set(total_rep) | set(split_dem) | set(split_rep)
    for fips in all_fips:
        if fips in total_dem or fips in total_rep:
            county_votes[fips] = (total_dem.get(fips, 0), total_rep.get(fips, 0))
        else:
            county_votes[fips] = (split_dem.get(fips, 0), split_rep.get(fips, 0))

    return precinct_votes, county_votes


def process(state: str, shp_2020: str, csv_2024: str | None) -> list[dict]:
    print(f"Loading 2020 shapefile: {shp_2020}")
    gdf = gpd.read_file(shp_2020).to_crs(epsg=4326)
    print(f"  {len(gdf)} records")

    cols = list(gdf.columns)
    dem_cols = _find_vote_cols(cols, "2020", "D")
    rep_cols = _find_vote_cols(cols, "2020", "R")
    if not dem_cols or not rep_cols:
        print(f"ERROR: Could not find 2020 vote columns in {cols}")
        sys.exit(1)

    state_fips = _STATE_FIPS.get(state.upper(), "")
    prec_col = _PRECINCT_COL.get(state.upper())

    # Load 2024 data
    precinct_votes: dict = {}
    county_votes: dict = {}
    county_name_to_fips: dict[str, str] = {}
    if csv_2024:
        print(f"Loading 2024 CSV: {csv_2024}")
        precinct_votes, county_votes = _load_2024_votes(csv_2024)
        print(f"  {len(precinct_votes)} precinct entries, {len(county_votes)} county entries")

        # Build county name → fips for NJ-style shapefiles
        sep = "\t" if csv_2024.endswith(".tab") else ","
        with open(csv_2024, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=sep):
                name = (row.get("county_name") or "").strip().upper()
                fips = str(row.get("county_fips") or "").strip()
                if name and fips:
                    county_name_to_fips[name] = fips

    gdf["_centroid"] = gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    records = []
    matched_precinct = 0
    matched_county = 0
    no_match = 0

    for _, row in gdf.iterrows():
        centroid = row["_centroid"]
        if centroid is None or centroid.is_empty:
            continue

        dem_20 = _sum_cols(row, dem_cols)
        rep_20 = _sum_cols(row, rep_cols)
        if dem_20 + rep_20 == 0:
            continue

        # Resolve county FIPS
        fips5 = _county_fips_from_row(row, state_fips)
        if not fips5:
            county_name_raw = str(row.get("COUNTY") or "").strip().upper()
            fips5 = county_name_to_fips.get(county_name_raw)

        # Get 2024 votes — try precinct match first, fall back to county
        dem_24, rep_24 = 0, 0
        if csv_2024 and fips5:
            prec_name = _normalize(str(row.get(prec_col) or "")) if prec_col else ""
            prec_key = (fips5, prec_name)
            if prec_key in precinct_votes:
                dem_24, rep_24 = precinct_votes[prec_key]
                matched_precinct += 1
            elif fips5 in county_votes:
                dem_24, rep_24 = county_votes[fips5]
                matched_county += 1
            else:
                no_match += 1
        elif csv_2024:
            no_match += 1

        records.append({
            "lat": round(centroid.y, 6),
            "lon": round(centroid.x, 6),
            "dem_2020": dem_20,
            "rep_2020": rep_20,
            "dem_2024": dem_24,
            "rep_2024": rep_24,
        })

    if csv_2024:
        total = matched_precinct + matched_county + no_match
        print(f"  2024 join: {matched_precinct} precinct-level ({round(matched_precinct/total*100)}%), "
              f"{matched_county} county-fallback ({round(matched_county/total*100)}%), "
              f"{no_match} unmatched")

    print(f"Built {len(records)} precinct records for {state}")
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--shp2020", required=True)
    parser.add_argument("--csv2024")
    args = parser.parse_args()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    records = process(args.state.upper(), args.shp2020, args.csv2024)

    out_path = os.path.join(_OUTPUT_DIR, f"{args.state.lower()}_precincts.json")
    with open(out_path, "w") as f:
        json.dump(records, f, separators=(",", ":"))
    print(f"Written to {out_path} ({os.path.getsize(out_path) // 1024} KB)")


if __name__ == "__main__":
    main()
