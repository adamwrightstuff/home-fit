"""
Patch is_charter_school onto every school in by_level arrays across both catalogs.

Sources (in priority order):
1. Web-verified overrides (manually confirmed today via live web searches)
2. NCES CCD 2018-19 flat file (96k schools, authoritative federal source)
3. Name contains "charter" → charter=True fallback
4. Unresolved → None (will populate from SchoolDigger when API access restored)

Field name matches SchoolDigger's isCharterSchool response field (snake_case).
Run:
    python3 scripts/catalog/patch_school_charter_flag.py
"""

import csv
import json
import re
import os

NCES_FILE = "/tmp/nces_schools/ccd_sch_029_1819_w_0a_04082019.csv"

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]

# Manually web-verified today (2026-07-10) via CDE, NCES, GreatSchools, school sites
WEB_VERIFIED: dict[str, bool] = {
    "environmental charter middle gardena": True,
    "environmental charter high gardena": True,
    "gaspar de portola charter middle": True,
    "kindle education public charter school": True,
    "citizens of the world charter school east valley": True,
    "da vinci communications": True,
    "da vinci science": True,
    "da vinci design": True,
    "wiseburn middle": False,
    "beverly vista middle": False,
    "dolores huerta middle": False,
    "brooklyn avenue": False,
    "boyle heights hilda solis high": False,
    "stem innovation academy of the oranges": False,
    "barack obama school for social justice": False,
    "aviation elementary": False,
    "del aire elementary": False,
    "hermosa vista": False,
    "hollywood elementary": False,
    # Round 2 web-verified (2026-07-10)
    "california creative learning academy middle school": True,   # formerly Los Feliz Charter, LAUSD charter
    "high technical la": True,        # High Tech LA — confirmed charter (LAUSD)
    "high tech la": True,
    "city honors international preparatory high": True,           # Inglewood Unified district charter
    "science technology research early college": False,           # NYC DOE regular public, Brooklyn
    "leaders of excellence advocacy and discovery": False,        # NYC DOE, Bronx District 7
    "la merced academy": False,                                   # Montebello Unified regular public
    "bennett kew leadership academy of excellence": False,        # Inglewood Unified regular public
    "bergen county institute for science and technology": False,  # Bergen County Vocational-Technical, public
    "p technical norwalk": False,                                 # Norwalk CT public magnet (P-TECH)
    "p tech norwalk": False,
    "the academy of information technology engineering": False,   # Stamford CT public inter-district magnet
    "academy of information technology engineering": False,
    "concord magnet school": False,                               # Norwalk CT public magnet
    # NYC DOE standard naming — all traditional public schools
    "junior high school": False,      # prefix match handled in resolve_charter
    "middle school": False,           # prefix match
    "bard high school early college bronx": False,
    "science technology research early college": False,
    "ballet technicalnyyc public school for dance": False,
    "christa mcauliffe school": False,
    "madeleine brennan school": False,
    "emily warren roebling school": False,
    "brooklyn green school": False,
    "lenox academy": False,
    "explore middle school": False,
    "exploratory school": False,
    "dock street school for steam studies": False,
    "bridges a school for exploration and equity": False,
    "bronx academy for multimedia": False,
    "isaac newton middle school for math and science": False,
    "east side elementary school": False,
    # Round 3 web-verified (2026-07-10)
    "ballet technical": False,             # NYC DOE Ballet Tech — public
    "bronx academy for multi media": False,  # NYC DOE — public
    "cesar e chavez learning acads": False,  # LAUSD campus with 4 small schools — all public (not charter)
    "bradoaks elementary science academy": False,  # Monrovia USD public
    "daniel phelan language academy": False,       # Whittier City SD public
    "delia bolden elementary": False,              # public
    "ernest s mcbride senior high": False,         # public
    "joseph f brandt elementary": False,           # public
}


def norm(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[-/]", " ", n)          # hyphens and slashes → space before stripping
    n = re.sub(r"[^a-z0-9 ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def load_nces(path: str) -> dict[tuple[str, str], bool]:
    lookup: dict[tuple[str, str], bool] = {}
    if not os.path.exists(path):
        print(f"⚠️  NCES file not found at {path} — skipping NCES lookup")
        return lookup
    with open(path, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            key = (norm(row["SCH_NAME"]), row["ST"].strip().upper())
            lookup[key] = row["CHARTER_TEXT"].strip() == "Yes"
    print(f"Loaded {len(lookup):,} schools from NCES")
    return lookup


def resolve_charter(name: str, state: str, nces: dict) -> bool | None:
    n = norm(name)

    # NYC DOE naming conventions — always traditional public schools
    if re.match(r"^(junior high school|middle school \d|ps \d|is \d|jhs \d)", n):
        return False

    # LAUSD district-run magnet schools — not charters (district operated, not independently chartered)
    if state == "CA" and "magnet" in n and "charter" not in n:
        return False

    # NYC DOE specialized/alternative schools with non-standard names — all traditional public
    nyc_public_patterns = [
        "ballet technical", "high school construction trades", "academy for college prep",
        "cesar e chavez learning", "brooklyn green school", "dock street school",
        "bridges a school", "exploratory school", "explore middle school",
        "isaac newton middle", "bard high school early college",
    ]
    if state == "NY" and any(p in n for p in nyc_public_patterns):
        return False

    # 1. Web-verified overrides
    for key, val in WEB_VERIFIED.items():
        if key in n or n == key:
            return val

    # 2. NCES lookup by name+state
    result = nces.get((n, state))
    if result is not None:
        return result

    # 3. Try other states (cross-border schools like Bronx charters in Westchester radius)
    for st in ["NY", "NJ", "CA", "CT"]:
        result = nces.get((n, st))
        if result is not None:
            return result

    # 4. Name contains "charter" → almost certainly charter
    if "charter" in n:
        return True

    # 5. Unknown
    return None


def infer_state(place_name: str, school_name: str, is_la: bool) -> str:
    if is_la:
        return "CA"
    sn = school_name.lower()
    pn = place_name.lower()
    if any(x in sn for x in ["bronx", "brooklyn", "manhattan", "queens", "harlem"]):
        return "NY"
    if any(x in pn for x in ["hoboken", "jersey city", "morristown", "montclair",
                               "maplewood", "millburn", "summit", "leonia", "ridgewood",
                               "westfield", "cranford", "nutley", "hackensack", "teaneck",
                               "englewood", "fort lee", "edgewater", "tenafly"]):
        return "NJ"
    if any(x in pn for x in ["stamford", "greenwich", "westport", "darien", "norwalk",
                               "bridgeport", "fairfield", "trumbull", "new canaan"]):
        return "CT"
    return "NY"


def patch_catalog(path: str, nces: dict, is_la: bool) -> tuple[int, int, int]:
    lines = []
    patched = total = unknown = 0

    with open(path) as f:
        raw_lines = f.readlines()

    for line in raw_lines:
        line = line.strip()
        if not line:
            lines.append(line)
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue

        cat = d.get("catalog", {})
        place_name = cat.get("place_name") or cat.get("name") or ""
        edu = d.get("score", {}).get("livability_pillars", {}).get("quality_education", {})
        by_level = edu.get("by_level")

        if by_level:
            for lvl, schools in by_level.items():
                for s in schools or []:
                    sname = s.get("name", "")
                    if not sname:
                        continue
                    total += 1
                    state = infer_state(place_name, sname, is_la)
                    is_charter = resolve_charter(sname, state, nces)
                    s["is_charter_school"] = is_charter
                    if is_charter is None:
                        unknown += 1
                    patched += 1

        lines.append(json.dumps(d, separators=(",", ":")))

    with open(path, "w") as f:
        f.write("\n".join(lines))
        if lines and lines[-1]:
            f.write("\n")

    return patched, total, unknown


def main():
    nces = load_nces(NCES_FILE)

    for path in CATALOGS:
        if not os.path.exists(path):
            print(f"Skipping {path} (not found)")
            continue
        is_la = "la_metro" in path
        patched, total, unknown = patch_catalog(path, nces, is_la)
        pct_known = round(100 * (total - unknown) / total, 1) if total else 0
        print(f"{path}: {patched} schools patched, {unknown}/{total} unknown ({pct_known}% resolved)")

    print("\nDone. Add school.get('isCharterSchool') to pillars/schools.py:~170 when SchoolDigger access is restored.")


if __name__ == "__main__":
    main()
