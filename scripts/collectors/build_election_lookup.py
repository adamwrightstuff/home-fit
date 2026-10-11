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
    "WA": "PRECINCTNA",
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
    """Normalize precinct name for matching.

    Handles several NY naming schemes:
      Ward-ED:  CSV 'Town of Albany Ward 3 ED 5' / SHP 'Albany City 3-5' -> 'ALBANY 3-5'
      NYC:      CSV '001/41' (ED/AD)               / SHP '41001' (ADED)   -> '41001'
      Nassau:   CSV '113001' (1+5-digit)            / SHP 'Glen Cove 13001' -> numeric only
    """
    s = s.upper().strip()

    # NYC boroughs: CSV format 'EEE/AD' -> canonical 'ADED' matching shapefile
    m = re.match(r"^(\d{1,3})/(\d{1,2})$", s)
    if m:
        ed = m.group(1).zfill(3)
        ad = m.group(2).zfill(2)
        return ad + ed

    # Nassau: pure 6-digit CSV code -> drop leading digit to match 5-digit shapefile numeric
    m = re.match(r"^(\d)(\d{5})$", s)
    if m:
        return m.group(2)

    # Strip leading jurisdiction qualifier from CSV names
    s = re.sub(r"^(TOWN OF|CITY OF|VILLAGE OF)\s+", "", s)
    # Convert 'NAME Ward W ED E' -> 'NAME W-E'
    m = re.match(r"^(.+?)\s+WARD\s+(\d+)\s+ED\s+(\d+)", s)
    if m:
        name = re.sub(r"\b(CITY|TOWN|VILLAGE)\b", "", m.group(1)).strip()
        name = re.sub(r"\s+", " ", name).strip()
        return f"{name} {m.group(2)}-{m.group(3)}"
    # Strip inline CITY/TOWN/VILLAGE qualifiers (shapefile: 'Albany City 3-5')
    s = re.sub(r"\b(CITY|TOWN|VILLAGE)\b", "", s)
    s = re.sub(r"[^A-Z0-9 \-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_municipality(precinct_raw: str) -> str:
    """Extract municipality name from a CSV precinct string for sub-county fallback."""
    s = precinct_raw.upper().strip()
    s = re.sub(r"^(TOWN OF|CITY OF|VILLAGE OF|TOWNSHIP OF)\s+", "", s)
    # NJ: 'Atlantic City W1 D1' / 'Buena Borough D01' / 'Brigantine Ward 01'
    s = re.sub(r"\s+W\d+(\s+D\d+)?$", "", s)
    s = re.sub(r"\s+D\d+$", "", s)
    # NJ Burlington: 'Bass River Township Election District 1'
    # NJ Camden: 'Audubon District 1'
    s = re.sub(r"\s+(ELECTION\s+)?DISTRICT.*$", "", s)
    # Remove trailing 'Ward X ED Y ...' or bare 'Ward X' or bare 'ED Y' or bare number
    s = re.sub(r"\s+WARD\s+\d+.*$", "", s)
    s = re.sub(r"\s+ED\s+\d+.*$", "", s)
    s = re.sub(r"\s+\d+(-\d+)?$", "", s)
    # Strip trailing bare 'ED' left after number removal
    s = re.sub(r"\s+ED$", "", s)
    # NJ abbreviations: Boro, Twp
    s = re.sub(r"\b(BORO|TWP)\b", "", s)
    s = re.sub(r"\b(CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP)\b", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_shp(s: str) -> str:
    """Normalize a shapefile PRECINCT name to match _normalize() output for CSV."""
    s = s.upper().strip()
    # Pure numeric (NYC boroughs): already in canonical form
    if re.match(r"^\d+$", s):
        return s
    # Nassau: 'Glen Cove 13001' -> keep just the numeric suffix
    m = re.match(r"^[A-Z ]+\s+(\d{5})$", s)
    if m:
        return m.group(1)
    # Ward-ED: 'Albany City 3-5' -> 'ALBANY 3-5'
    s = re.sub(r"\b(CITY|TOWN|VILLAGE)\b", "", s)
    s = re.sub(r"[^A-Z0-9 \-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _shp_municipality(precinct_raw: str) -> str:
    """Extract municipality name from a shapefile PRECINCT string."""
    s = precinct_raw.upper().strip()
    s = re.sub(r"\b(CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP)\b", "", s)
    # Strip NJ ward/congressional-district suffixes e.g. 'W1 CD11', 'W3'
    s = re.sub(r"\s+W\d+(\s+CD\d+)?$", "", s)
    # Remove trailing number or ward-ed suffix
    s = re.sub(r"\s+\d+(-\d+)?$", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


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
    cnty = str(row.get("CNTY_CODE") or row.get("CNTY") or "").strip()
    if cnty and state_fips:
        return f"{state_fips.zfill(2)}{cnty.zfill(3)}"
    # WA and some states: COUNTY column already holds the 5-digit FIPS code
    county_raw = str(row.get("COUNTY") or "").strip()
    if re.match(r"^\d{5}$", county_raw):
        return county_raw
    # NJ: COUNTY name — resolved later via county_name_to_fips
    return None


def _load_2024_votes(csv_path: str) -> tuple[dict, dict, dict]:
    """
    Returns:
      precinct_votes:     (county_fips, norm_precinct) -> (dem, rep)
      municipality_votes: (county_fips, municipality)  -> (dem, rep)
      county_votes:       county_fips -> (dem, rep)
    """
    prec_dem: dict[tuple, int] = {}
    prec_rep: dict[tuple, int] = {}
    muni_dem: dict[tuple, int] = {}
    muni_rep: dict[tuple, int] = {}
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
            prec_raw = row.get("precinct") or ""
            prec = _normalize(prec_raw)
            muni = _extract_municipality(prec_raw)
            party = (row.get("party_simplified") or "").upper().strip()
            if party not in ("DEMOCRAT", "REPUBLICAN"):
                continue
            try:
                votes = int(row.get("votes") or 0)
            except ValueError:
                continue
            mode = (row.get("mode") or "").upper().strip()

            # Precinct-level (all modes summed)
            pkey = (fips, prec)
            if party == "DEMOCRAT":
                prec_dem[pkey] = prec_dem.get(pkey, 0) + votes
            else:
                prec_rep[pkey] = prec_rep.get(pkey, 0) + votes

            # Municipality-level: use jurisdiction_name when jurisdiction_fips indicates sub-county
            # granularity (len > 5 means it encodes a place/MCD, not just the county).
            # NJ jurisdiction_name is county-level; CT is town-level with 10-digit fips.
            jurisdiction = (row.get("jurisdiction_name") or "").strip().upper()
            jfips = str(row.get("jurisdiction_fips") or "").strip()
            sub_county_jurisdiction = jurisdiction if (jurisdiction and len(jfips) > 5) else ""
            muni_key_name = sub_county_jurisdiction if sub_county_jurisdiction else muni
            if muni_key_name:
                mkey = (fips, muni_key_name)
                if party == "DEMOCRAT":
                    muni_dem[mkey] = muni_dem.get(mkey, 0) + votes
                else:
                    muni_rep[mkey] = muni_rep.get(mkey, 0) + votes

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

    precinct_votes = {k: (prec_dem.get(k, 0), prec_rep.get(k, 0)) for k in set(prec_dem) | set(prec_rep)}
    municipality_votes = {k: (muni_dem.get(k, 0), muni_rep.get(k, 0)) for k in set(muni_dem) | set(muni_rep)}

    county_votes = {}
    for fips in set(total_dem) | set(total_rep) | set(split_dem) | set(split_rep):
        if fips in total_dem or fips in total_rep:
            county_votes[fips] = (total_dem.get(fips, 0), total_rep.get(fips, 0))
        else:
            county_votes[fips] = (split_dem.get(fips, 0), split_rep.get(fips, 0))

    return precinct_votes, municipality_votes, county_votes



# ---------------------------------------------------------------------------
# State-specific exact matchers (TX, DE, MD, IL-Chicago) and rank alignment (PA).
#
# 2024 precinct IDs rarely share a naming scheme with the 2020 shapefile. Where a
# deterministic key exists we join on it; where only the *order* is shared (PA),
# we align by rank within a county and accept it only if the 2020 and 2024 lean
# correlate (>= _RANK_MIN_CORR), so a misaligned join falls back to the county tier
# instead of producing confident wrong numbers.
# ---------------------------------------------------------------------------

_RANK_MIN_CORR = 0.90
# States whose precinct names/boundaries changed between 2020 and 2024 (DE redistricting,
# Chicago's 2022 ward remap): an unmatched precinct gets NO 2024 votes instead of the
# county aggregate, so the lookup reports a flagged 2020 lean rather than a flat county one.
_PRECINCT_ONLY_STATES = {"IL", "DE", "IN"}


def _ints(s: str) -> tuple | None:
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums) if nums else None


def _shp_key_tx(row) -> tuple | None:
    try:
        return ("48" + str(int(row["CNTY"])).zfill(3), f"{int(row['CNTYKEY'])}{row['PREC']}")
    except (KeyError, ValueError, TypeError):
        return None


def _csv_key_tx(fips: str, prec: str) -> tuple:
    return (fips, prec.strip())


def _shp_key_de(row) -> tuple | None:
    return ("10", str(row.get("PRECINCT") or "").strip())


def _csv_key_de(fips: str, prec: str) -> tuple:
    return ("10", prec.strip())


def _shp_key_md(row) -> tuple | None:
    n = _ints(str(row.get("NUMBER") or ""))
    code = str(row.get("JURSCODE") or "").strip().upper()
    return (code, n) if n else None


def _shp_key_il(row) -> tuple | None:
    """Chicago only: 'CHICAGO WD 50 PCT 27' -> ('17031', ('W', 50, 27))."""
    m = re.match(r"^CHICAGO WD (\d+) PCT (\d+)$", str(row.get("NAME") or "").upper().strip())
    if m:
        return ("17031", ("W", int(m.group(1)), int(m.group(2))))
    return None


def _csv_key_il(fips: str, prec: str) -> tuple | None:
    m = re.match(r"^WARD (\d+) PRECINCT (\d+)$", prec.upper().strip())
    if m:
        return ("17031", ("W", int(m.group(1)), int(m.group(2))))
    return None


_EXACT_MATCHERS = {
    "TX": (_shp_key_tx, _csv_key_tx),
    "DE": (_shp_key_de, _csv_key_de),
    "IL": (_shp_key_il, _csv_key_il),
}

# Pennsylvania: order-aligned within county, validated by correlation.
_RANK_STATES = {"PA": ("PRECINCT", "COUNTYFP")}


def _load_raw_precinct_votes(csv_path: str) -> tuple[dict, dict]:
    """Return ({(county_fips, raw_precinct): (dem, rep)}, {county_fips: county_name}).

    Uses the TOTAL mode when a file carries it, otherwise sums all modes
    (never both -- summing TOTAL plus its splits double counts)."""
    import collections
    csv.field_size_limit(10**9)
    sep = "\t" if csv_path.endswith(".tab") else ","
    total = collections.defaultdict(lambda: [0, 0])
    split = collections.defaultdict(lambda: [0, 0])
    names: dict = {}
    # no newline="": some Dataverse .tab files carry stray \r that otherwise swallows rows
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=sep):
            if "PRESIDENT" not in (row.get("office") or "").upper():
                continue
            party = (row.get("party_simplified") or "").upper().strip()
            if party not in ("DEMOCRAT", "REPUBLICAN"):
                continue
            try:
                votes = int(row.get("votes") or 0)
            except ValueError:
                continue
            fips = str(row.get("county_fips") or "").strip()
            key = (fips, (row.get("precinct") or "").strip())
            names[fips] = (row.get("county_name") or "").strip().upper()
            idx = 0 if party == "DEMOCRAT" else 1
            if (row.get("mode") or "").upper().strip() == "TOTAL":
                total[key][idx] += votes
            else:
                split[key][idx] += votes
    out = {k: tuple(v) for k, v in split.items()}
    out.update({k: tuple(v) for k, v in total.items()})
    return out, names


def _md_code_to_fips(names: dict) -> dict:
    """MD shapefile JURSCODE is the first 4 letters of the county name; ambiguous prefixes are dropped."""
    seen: dict = {}
    for fips, name in names.items():
        seen.setdefault(name[:4], set()).add(fips)
    return {code: next(iter(f)) for code, f in seen.items() if len(f) == 1}


def _rank_align_county(l20: list, ids_votes: list) -> tuple[list, float] | None:
    """Align CSV precincts (sorted by id) to shapefile rows (sorted by id) by rank.

    ids_votes is [(dem, rep)] sorted. l20 is [lean_2020] sorted. When counts differ by
    one, drop the single CSV/shapefile element that maximises correlation. Returns
    (list of csv index per shp index, correlation) or None."""
    import numpy as np
    n_s, n_c = len(l20), len(ids_votes)
    if abs(n_s - n_c) > 1 or n_s < 5:
        return None
    l24 = np.array([(d - r) / max(1, d + r) for d, r in ids_votes])
    a20 = np.array(l20)
    best = None
    if n_s == n_c:
        c = float(np.corrcoef(l24, a20)[0, 1])
        return list(range(n_c)), c
    if n_c == n_s + 1:  # one extra CSV precinct
        for drop in range(n_c):
            keep = [i for i in range(n_c) if i != drop]
            c = float(np.corrcoef(l24[keep], a20)[0, 1])
            if best is None or c > best[1]:
                best = (keep, c)
    else:  # one extra shapefile precinct: that precinct gets no 2024 match
        for drop in range(n_s):
            keep = [i for i in range(n_s) if i != drop]
            c = float(np.corrcoef(l24, a20[keep])[0, 1])
            if best is None or c > best[1]:
                mapping = [-1] * n_s
                for ci, si in enumerate(keep):
                    mapping[si] = ci
                best = (mapping, c)
    return best



def _validated(state: str, gdf, overrides: dict, dem_cols: list, rep_cols: list) -> dict:
    """Keep an exact join only if 2020 and 2024 precinct leans correlate (>= _RANK_MIN_CORR).
    A name that was reused for a different geography shows up as near-zero correlation."""
    import numpy as np
    a, b = [], []
    for idx, (d24, r24, _) in overrides.items():
        row = gdf.loc[idx]
        d20, r20 = _sum_cols(row, dem_cols), _sum_cols(row, rep_cols)
        if d20 + r20 >= 50 and d24 + r24 >= 50:
            a.append((d20 - r20) / (d20 + r20))
            b.append((d24 - r24) / (d24 + r24))
    if len(a) < 20:
        print(f"  VALIDATION ({state}): too few joined precincts ({len(a)}); discarding")
        return {}
    c = float(np.corrcoef(a, b)[0, 1])
    print(f"  VALIDATION ({state}): 2020 vs 2024 precinct-lean corr = {c:.3f} (need >= {_RANK_MIN_CORR})")
    return overrides if c >= _RANK_MIN_CORR else {}


def _build_overrides(state: str, gdf, csv_2024: str, dem_cols: list, rep_cols: list) -> dict:
    out: dict = {}
    raw, names = _load_raw_precinct_votes(csv_2024)

    if state in _EXACT_MATCHERS:
        shp_key, csv_key = _EXACT_MATCHERS[state]
        votes: dict = {}
        for (fips, prec), v in raw.items():
            k = csv_key(fips, prec)
            if k:
                votes[k] = v
        for idx, row in gdf.iterrows():
            k = shp_key(row)
            if k and k in votes:
                out[idx] = (votes[k][0], votes[k][1], "precinct")
        print(f"  exact join ({state}): {len(out)} of {len(gdf)} shapefile precincts")
        out = _validated(state, gdf, out, dem_cols, rep_cols)

    elif state == "MD":
        code_to_fips = _md_code_to_fips(names)
        votes = {}
        for (fips, prec), v in raw.items():
            n = _ints(prec)
            if n:
                votes[(fips, n)] = v
        for idx, row in gdf.iterrows():
            k = _shp_key_md(row)
            fips = code_to_fips.get(k[0]) if k else None
            if fips and (fips, k[1]) in votes:
                out[idx] = (votes[(fips, k[1])][0], votes[(fips, k[1])][1], "precinct")
        print(f"  exact join (MD): {len(out)} of {len(gdf)} shapefile precincts")
        out = _validated(state, gdf, out, dem_cols, rep_cols)

    elif state in _RANK_STATES:
        pcol, ccol = _RANK_STATES[state]
        by_county: dict = {}
        for (fips, prec), v in raw.items():
            if prec.isdigit():
                by_county.setdefault(fips, []).append((int(prec), v))
        sfp = _STATE_FIPS[state]
        ok = bad = 0
        for fips, items in by_county.items():
            items.sort()
            sub = gdf[gdf[ccol].astype(str).str.zfill(3) == fips[2:]].sort_values(pcol)
            l20 = [
                (_sum_cols(r, dem_cols) - _sum_cols(r, rep_cols)) / max(1, _sum_cols(r, dem_cols) + _sum_cols(r, rep_cols))
                for _, r in sub.iterrows()
            ]
            res = _rank_align_county(l20, [v for _, v in items])
            if not res or res[1] < _RANK_MIN_CORR:
                bad += 1
                continue
            mapping, corr = res
            shp_idx = list(sub.index)
            for si, ci in enumerate(mapping):
                if ci is not None and ci >= 0:
                    dem, rep = items[ci][1]
                    out[shp_idx[si]] = (dem, rep, "precinct")
            ok += 1
        print(f"  rank join ({state}): {ok} counties aligned (corr>={_RANK_MIN_CORR}), {bad} fell back to county tier; {len(out)} precincts")
    return out

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
    municipality_votes: dict = {}
    county_votes: dict = {}
    county_name_to_fips: dict[str, str] = {}
    if csv_2024:
        print(f"Loading 2024 CSV: {csv_2024}")
        precinct_votes, municipality_votes, county_votes = _load_2024_votes(csv_2024)
        print(f"  {len(precinct_votes)} precinct entries, {len(municipality_votes)} municipality entries, {len(county_votes)} county entries")

        # Build county name → fips for NJ-style shapefiles
        sep = "\t" if csv_2024.endswith(".tab") else ","
        with open(csv_2024, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=sep):
                name = (row.get("county_name") or "").strip().upper()
                fips = str(row.get("county_fips") or "").strip()
                if name and fips:
                    county_name_to_fips[name] = fips

    gdf["_centroid"] = gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    # State-specific exact / rank-aligned 2024 joins: shapefile index -> (dem, rep, tier)
    overrides: dict = {}
    if csv_2024:
        overrides = _build_overrides(state.upper(), gdf, csv_2024, dem_cols, rep_cols)

    records = []
    matched_precinct = 0
    matched_municipality = 0
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

        # Get 2024 votes — exact/rank override → precinct → municipality → county
        dem_24, rep_24 = 0, 0
        match_tier = "none"
        if row.name in overrides:
            dem_24, rep_24, match_tier = overrides[row.name]
            matched_precinct += 1
        elif csv_2024 and fips5:
            prec_raw = str(row.get(prec_col) or "") if prec_col else ""
            prec_name = _normalize_shp(prec_raw)
            prec_key = (fips5, prec_name)
            muni_name = _shp_municipality(prec_raw)
            muni_key = (fips5, muni_name)
            if prec_key in precinct_votes:
                dem_24, rep_24 = precinct_votes[prec_key]
                matched_precinct += 1
                match_tier = "precinct"
            elif muni_key in municipality_votes:
                dem_24, rep_24 = municipality_votes[muni_key]
                matched_municipality += 1
                match_tier = "municipality"
            elif fips5 in county_votes and state.upper() not in _PRECINCT_ONLY_STATES:
                dem_24, rep_24 = county_votes[fips5]
                matched_county += 1
                match_tier = "county"
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
            "match_tier": match_tier,
        })

    if csv_2024:
        total = matched_precinct + matched_municipality + matched_county + no_match
        print(f"  2024 join: {matched_precinct} precinct ({round(matched_precinct/total*100)}%), "
              f"{matched_municipality} municipality ({round(matched_municipality/total*100)}%), "
              f"{matched_county} county ({round(matched_county/total*100)}%), "
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
