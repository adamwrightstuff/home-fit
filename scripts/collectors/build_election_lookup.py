"""
Build precinct election lookup JSON from VEST shapefiles + 2024 CSV.

Source: Voting and Election Science Team (VEST) — Harvard Dataverse
  2020 shapefiles: doi:10.7910/DVN/K7760H  (per-state zips with geometry)
  2024 results:    doi:10.7910/DVN/NYTPDU  (per-state CSV, no geometry)

The 2020 shapefile provides geometry (precinct centroids) and 2020 votes.
The 2024 CSV is joined to 2020 geometry at the **county level** as the
common denominator — county FIPS is reliable across both sources.

Usage:
    PYTHONPATH=. python3 scripts/collectors/build_election_lookup.py \
        --state NY \
        --shp2020 /tmp/vest/ny_2020/ny_2020.shp \
        --csv2024 /tmp/vest/2024-ny-precinct-general.csv

    # 2020-only (no 2024 data):
    PYTHONPATH=. python3 scripts/collectors/build_election_lookup.py \
        --state NJ --shp2020 /tmp/vest/nj_2020/nj_2020.shp

Output: data/election/<state_lower>_precincts.json
"""

import argparse
import csv
import json
import os
import sys

try:
    import geopandas as gpd
except ImportError:
    print("geopandas required: pip install geopandas")
    sys.exit(1)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_OUTPUT_DIR = os.path.join(_REPO_ROOT, "data", "election")


# ---------------------------------------------------------------------------
# VEST 2020 shapefile helpers
# ---------------------------------------------------------------------------

def _find_vote_cols(columns: list[str], year: str, party: str) -> list[str]:
    """Find VEST vote columns by prefix (e.g. G20PRED* for 2020 Dem)."""
    year2 = year[-2:]
    prefix = f"G{year2}PRE{party[0].upper()}"
    return [c for c in columns if c.upper().startswith(prefix)]


def _sum_cols(row, cols: list[str]) -> int:
    total = 0
    for c in cols:
        v = row.get(c, 0)
        try:
            total += int(v or 0)
        except (ValueError, TypeError):
            pass
    return total


def _county_fips_from_row(row, state_fips: str) -> str | None:
    """Build 5-digit county FIPS from shapefile row. Handles STATEFP, STATEFP20 variants."""
    # Try standard and year-suffixed column names
    sfp = str(row.get("STATEFP") or row.get("STATEFP20") or "").strip()
    cfp = str(row.get("COUNTYFP") or row.get("COUNTYFP20") or "").strip()
    if sfp and cfp:
        return f"{sfp.zfill(2)}{cfp.zfill(3)}"
    if cfp and state_fips:
        return f"{state_fips.zfill(2)}{cfp.zfill(3)}"
    # VEST CA-style: FIPS_CODE holds the full county FIPS but may drop the leading zero
    # (Alameda = '6001' -> '06001'). CNTY_CODE is the bare county code (-> state + county).
    fipsc = str(row.get("FIPS_CODE") or "").strip()
    if fipsc:
        return fipsc.zfill(5)
    cnty = str(row.get("CNTY_CODE") or "").strip()
    if cnty and state_fips:
        return f"{state_fips.zfill(2)}{cnty.zfill(3)}"
    return None


# ---------------------------------------------------------------------------
# 2024 CSV aggregation (county level)
# ---------------------------------------------------------------------------

_SPLIT_MODES = frozenset({"ELECTION DAY", "EARLY VOTING", "ABSENTEE", "MAIL-IN",
                          "PROVISIONAL", "EMERGENCY", "FEDERAL/OVERSEAS", "STATE/FED"})


def _load_2024_county_votes(csv_path: str) -> dict[str, tuple[int, int]]:
    """
    Parse VEST 2024 per-state CSV, return county_fips → (dem, rep) totals.

    Strategy: prefer mode=TOTAL rows that have party-level data. For counties
    that report TOTAL without party breakdown (some NJ counties report only
    UNDERVOTES/OVERVOTES in TOTAL mode), fall back to summing split modes.
    """
    # total_dem/rep: counties where TOTAL mode has party-level rows
    total_dem: dict[str, int] = {}
    total_rep: dict[str, int] = {}
    # split_dem/rep: sum of split modes (EL DAY + EARLY + ABSENTEE + etc.)
    split_dem: dict[str, int] = {}
    split_rep: dict[str, int] = {}

    sep = "\t" if csv_path.endswith(".tab") else ","
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            office = (row.get("office") or "").upper().strip()
            if "PRESIDENT" not in office:
                continue
            fips = str(row.get("county_fips") or "").strip()
            if not fips:
                continue
            party = (row.get("party_simplified") or "").upper().strip()
            if party not in ("DEMOCRAT", "REPUBLICAN"):
                continue
            try:
                votes = int(row.get("votes") or 0)
            except ValueError:
                continue
            mode = (row.get("mode") or "").upper().strip()
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

    # Merge: use TOTAL data if available for a county, else split sum
    result: dict[str, tuple[int, int]] = {}
    all_fips = set(total_dem) | set(total_rep) | set(split_dem) | set(split_rep)
    for fips in all_fips:
        if fips in total_dem or fips in total_rep:
            result[fips] = (total_dem.get(fips, 0), total_rep.get(fips, 0))
        else:
            result[fips] = (split_dem.get(fips, 0), split_rep.get(fips, 0))
    return result


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def _infer_state_fips(shp_path: str, gdf) -> str:
    """Try to infer state FIPS from the shapefile data."""
    if "STATEFP" in gdf.columns:
        vals = gdf["STATEFP"].dropna().unique()
        if len(vals) == 1:
            return str(vals[0]).strip()
    # Fallback: derive from shapefile directory/filename (not reliable, warn)
    return ""


def process(state: str, shp_2020: str, csv_2024: str | None) -> list[dict]:
    print(f"Loading 2020 shapefile: {shp_2020}")
    gdf = gpd.read_file(shp_2020).to_crs(epsg=4326)
    print(f"  {len(gdf)} records, columns: {list(gdf.columns[:12])}")

    # Detect 2020 D/R vote columns
    cols = list(gdf.columns)
    dem_cols = _find_vote_cols(cols, "2020", "D")
    rep_cols = _find_vote_cols(cols, "2020", "R")
    if not dem_cols or not rep_cols:
        print(f"ERROR: Could not find 2020 presidential vote columns in {cols}")
        sys.exit(1)
    print(f"  2020 D cols: {dem_cols}, R cols: {rep_cols}")

    # Load 2024 county aggregates if provided
    county_2024: dict[str, tuple[int, int]] = {}
    if csv_2024:
        print(f"Loading 2024 CSV: {csv_2024}")
        county_2024 = _load_2024_county_votes(csv_2024)
        print(f"  {len(county_2024)} counties with 2024 data")

    state_fips = _infer_state_fips(shp_2020, gdf)
    if not state_fips:
        # Use Census state FIPS lookup for common states
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
        state_fips = _STATE_FIPS.get(state.upper(), "")
        if state_fips:
            print(f"  Inferred state FIPS: {state_fips} (from state arg)")

    # Build county FIPS from shapefile for NJ-style data that lacks STATEFP/COUNTYFP
    # For NJ: shapefile has COUNTY (name) → look up from 2024 county_fips keys
    county_name_to_fips: dict[str, str] = {}
    if "COUNTY" in gdf.columns and state_fips and csv_2024:
        # Build reverse map: normalized county name → fips
        for fips in county_2024:
            if fips[:2] == state_fips:
                # We'll populate this from 2024 CSV county_name field below
                pass
        # Load county_name → fips from the 2024 CSV directly
        sep = "\t" if csv_2024.endswith(".tab") else ","
        with open(csv_2024, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                name = (row.get("county_name") or "").strip().upper()
                fips = str(row.get("county_fips") or "").strip()
                if name and fips and name not in county_name_to_fips:
                    county_name_to_fips[name] = fips

    # Compute centroids in a projected CRS then back to WGS84 coords
    gdf["_centroid"] = gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    records = []
    no_2024_count = 0
    for _, row in gdf.iterrows():
        centroid = row["_centroid"]
        if centroid is None or centroid.is_empty:
            continue

        dem_20 = _sum_cols(row, dem_cols)
        rep_20 = _sum_cols(row, rep_cols)
        if dem_20 + rep_20 == 0:
            continue

        # Resolve county FIPS for this row
        fips5 = _county_fips_from_row(row, state_fips)
        if not fips5 and "COUNTY" in gdf.columns:
            county_name_raw = str(row.get("COUNTY") or "").strip().upper()
            fips5 = county_name_to_fips.get(county_name_raw)

        # Look up 2024 county aggregate
        dem_24, rep_24 = 0, 0
        if fips5 and fips5 in county_2024:
            dem_24, rep_24 = county_2024[fips5]
        elif county_2024:
            no_2024_count += 1

        records.append({
            "lat": round(centroid.y, 6),
            "lon": round(centroid.x, 6),
            "dem_2020": dem_20,
            "rep_2020": rep_20,
            "dem_2024": dem_24,
            "rep_2024": rep_24,
        })

    if no_2024_count:
        print(f"  Warning: {no_2024_count} records had no 2024 county match")
    print(f"Built {len(records)} precinct records for {state}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Build election lookup from VEST shapefile + optional 2024 CSV")
    parser.add_argument("--state", required=True, help="State abbreviation (e.g. NY)")
    parser.add_argument("--shp2020", required=True, help="Path to 2020 VEST shapefile (.shp)")
    parser.add_argument("--csv2024", help="Path to 2024 VEST per-state CSV or .tab file (optional)")
    args = parser.parse_args()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    records = process(args.state.upper(), args.shp2020, args.csv2024)

    out_path = os.path.join(_OUTPUT_DIR, f"{args.state.lower()}_precincts.json")
    with open(out_path, "w") as f:
        json.dump(records, f, separators=(",", ":"))
    print(f"Written to {out_path} ({os.path.getsize(out_path) // 1024} KB)")


if __name__ == "__main__":
    main()
