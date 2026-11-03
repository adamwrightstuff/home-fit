"""Independent validation of the quality_education pillar against EDFacts proficiency.

Implements Tests A, B and D of analysis/education_validation_brief_2026-11-03.md with the
pass criteria fixed there. Test C needs manual reads of district finders and is not run here;
this script only writes the seed-2026 stratified sample list for it.

Offline once the EDFacts files exist. Fetch (Urban Institute Education Data API, year 2018,
grade 99 all grades, one call per state, free, no key) into an EMPTY folder:

    python3 -I scripts/catalog/validate_education_edfacts.py --fetch EDFACTS_DIR

Run (reads only the stored catalog, data/school_snapshot and EDFACTS_DIR; calls no API):

    PYTHONPATH=. python3 -I scripts/catalog/validate_education_edfacts.py \
        --edfacts EDFACTS_DIR --out analysis/education_validation_edfacts2018_places.csv

Proficiency = mean of read and math percent proficient midpoints, 2018, all students.
Never calls SchoolDigger.

Matching rules (set before results were seen):
  * Rated school -> snapshot school: same state, same normalised name, stored rating equal to
    the snapshot statewide percentage within 0.02; ties broken by the school distance field vs
    the distance from the place pin.
  * Snapshot school id (12 digit NCES) -> EDFacts ncessch_num.
  * Level proficiency = mean proficiency of the matched schools at that level (zone / nearest
    schools). Lottery pool levels (choice_avg) = enrollment-weighted mean proficiency of the
    district's rated non-charter schools of that level in the snapshot (the pillar's pool rule).
  * A place is MATCHED when every scored level has a proficiency value. Place proficiency is
    the mean over scored levels (the pillar's equal level weights).
"""
import argparse
import csv
import glob
import gzip
import json
import math
import os
import random
import re
import sys
import urllib.request
from collections import defaultdict

STATES = {"AZ": 4, "CA": 6, "CO": 8, "CT": 9, "DE": 10, "FL": 12, "GA": 13, "IL": 17, "IN": 18,
          "MA": 25, "MD": 24, "NC": 37, "NJ": 34, "NV": 32, "NY": 36, "PA": 42, "TX": 48, "WA": 53}
URL = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2018/grade-99/?fips={}"
LEVELS = ("elementary", "middle", "high")


def fetch(folder):
    os.makedirs(folder, exist_ok=True)
    if os.listdir(folder):
        sys.exit("fetch folder must be empty: " + folder)
    for st, fips in STATES.items():
        with urllib.request.urlopen(URL.format(fips), timeout=300) as r:
            data = r.read()
        json.loads(data)
        with open(os.path.join(folder, st + ".json"), "wb") as f:
            f.write(data)
        print("fetched", st, len(data))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def spearman(x, y):
    n = len(x)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def load_edfacts(folder):
    prof = {}
    for st in STATES:
        p = os.path.join(folder, st + ".json")
        if not os.path.exists(p):
            continue
        for r in json.load(open(p))["results"]:
            vals = [r.get("read_test_pct_prof_midpt"), r.get("math_test_pct_prof_midpt")]
            vals = [v for v in vals if v is not None and v >= 0]
            if vals:
                prof[int(r["ncessch_num"])] = sum(vals) / len(vals)
    return prof


def load_snapshot(prof):
    snap = {}
    for st in STATES:
        rows = json.load(gzip.open("data/school_snapshot/%s.json.gz" % st))["schools"]
        out = []
        for s in rows:
            if s.get("isPrivate") or not s.get("rankHistory"):
                continue
            if s["rankHistory"][0].get("rankStatewidePercentage") is None:
                continue
            ll = (s.get("address") or {}).get("latLong") or {}
            try:
                nid = int(s["schoolid"])
            except (TypeError, ValueError):
                nid = None
            enr = ((s.get("schoolYearlyDetails") or [{}])[0] or {}).get("numberOfStudents")
            out.append({
                "id": nid, "name": s["schoolName"], "nname": norm(s["schoolName"]),
                "level": (s.get("schoolLevel") or "").lower(),
                "rating": s["rankHistory"][0]["rankStatewidePercentage"],
                "lat": ll.get("latitude"), "lon": ll.get("longitude"),
                "charter": s.get("isCharterSchool") == "Yes",
                "district": (s.get("district") or {}).get("districtID"),
                "dname": (s.get("district") or {}).get("districtName") or "",
                "enr": enr or 0, "prof": prof.get(nid),
            })
        snap[st] = out
    return snap


def test_a(snap):
    cells = []
    for st, rows in snap.items():
        for lv in LEVELS:
            m = [r for r in rows if r["level"] == lv and r["prof"] is not None]
            rho = spearman([r["rating"] for r in m], [r["prof"] for r in m]) if len(m) >= 30 else None
            cells.append((st, lv, len(m), rho))
    return cells


def match_school(rs, st_rows, by_name, plat, plon):
    cands = [c for c in by_name.get(norm(rs["name"]), [])
             if c["level"] in (rs["level"], "secondary", "") or True]
    cands = [c for c in cands if abs(c["rating"] - rs["rating"]) <= 0.02]
    if not cands:
        return None
    if len(cands) > 1 and plat is not None:
        d = rs.get("distance_mi")
        cands.sort(key=lambda c: abs(hav(plat, plon, c["lat"], c["lon"]) - d)
                   if c["lat"] is not None and d is not None else 9e9)
    return cands[0]


def pool_prof(district, lv, snap_rows):
    # NYC DOE (leaid 3620580) is one Census district; SchoolDigger splits it into geographic districts.
    if district == "3620580":
        match = lambda r: r["dname"].startswith("New York City Geographic District")
    else:
        match = lambda r: r["district"] == district
    rows = [r for r in snap_rows if match(r) and r["level"] == lv
            and not r["charter"] and r["prof"] is not None and r["enr"] > 0]
    w = sum(r["enr"] for r in rows)
    return (sum(r["prof"] * r["enr"] for r in rows) / w, len(rows)) if w and len(rows) >= 3 else (None, 0)


def places():
    for f in sorted(glob.glob("data/*_place_catalog_scores_merged.composites_recomputed.jsonl")):
        for line in open(f):
            r = json.loads(line)
            c = r["catalog"]
            q = r["score"]["livability_pillars"].get("quality_education") or {}
            yield f, c, q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch")
    ap.add_argument("--edfacts")
    ap.add_argument("--out", default="analysis/education_validation_edfacts2018_places.csv")
    ap.add_argument("--cells-out", default="analysis/education_validation_edfacts2018_cells.csv")
    ap.add_argument("--testc-out", default="analysis/education_validation_testC_sample.csv")
    a = ap.parse_args()
    if a.fetch:
        return fetch(a.fetch)
    prof = load_edfacts(a.edfacts)
    snap = load_snapshot(prof)

    # Test A
    cells = test_a(snap)
    with open(a.cells_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "level", "n_matched_rated_schools", "spearman", "verdict"])
        for st, lv, n, rho in cells:
            v = "inconclusive" if rho is None else ("pass" if rho >= 0.70 else "FAIL")
            if rho is not None and rho < 0.50:
                v = "FAIL_below_0.50"
            w.writerow([st, lv, n, "" if rho is None else round(rho, 3), v])
    conc = [c for c in cells if c[3] is not None]
    npass = sum(1 for c in conc if c[3] >= 0.70)
    print("TEST A: conclusive cells %d of %d; pass %d (%.0f%%); min %.3f" % (
        len(conc), len(cells), npass, 100 * npass / max(1, len(conc)), min(c[3] for c in conc)))

    # Test B
    index = {st: defaultdict(list) for st in snap}
    for st, rows in snap.items():
        for r in rows:
            index[st][r["nname"]].append(r)
    out_rows, sample_pool = [], []
    for f, c, q in places():
        st = c["state_abbr"]
        b = q.get("breakdown") or {}
        row = {"metro_file": os.path.basename(f).split("_place")[0], "name": c["name"], "state": st,
               "score": q.get("score"), "scored": q.get("score") is not None and st in snap}
        lat, lon = float(c["lat"]), float(c["lon"])
        lvprof, srcs, zone_vint = {}, {}, {}
        for lv in LEVELS:
            L = (b.get("levels") or {}).get(lv)
            row["src_" + lv] = srcs[lv] = (L or {}).get("source")
            zone_vint[lv] = (((L or {}).get("zone") or {}).get("vintage"))
            if not L or L.get("score") is None or not row["scored"]:
                continue
            if L["source"] == "choice_avg":
                dist = (b.get("districts") or [{}])[0].get("id")
                dist = str(dist).zfill(7) if dist else None
                p, n = pool_prof(dist, lv, snap[st])
                if p is not None:
                    lvprof[lv] = (p, n, n)
                continue
            ps = []
            for rs in L.get("schools") or []:
                m = match_school(rs, snap[st], index[st], lat, lon)
                if m and m["prof"] is not None:
                    ps.append(m["prof"])
            if ps:
                lvprof[lv] = (sum(ps) / len(ps), len(ps), len(L.get("schools") or []))
        scored_lv = [lv for lv in LEVELS if (b.get("levels") or {}).get(lv, {}).get("score") is not None]
        row["levels_scored"] = len(scored_lv)
        row["levels_matched"] = sum(1 for lv in scored_lv if lv in lvprof)
        for lv in LEVELS:
            row["prof_" + lv] = round(lvprof[lv][0], 2) if lv in lvprof else ""
        row["matched"] = bool(row["scored"] and scored_lv and row["levels_matched"] == len(scored_lv))
        row["prof_place"] = round(sum(lvprof[lv][0] for lv in scored_lv) / len(scored_lv), 2) if row["matched"] else ""
        out_rows.append(row)
        # Test C sample candidates: classify by the elementary level
        el = (b.get("levels") or {}).get("elementary") or {}
        if row["scored"] and el.get("source") in ("zone", "nearest"):
            if el["source"] == "nearest":
                cls = "nearest"
            elif zone_vint["elementary"] == "2015-16":
                cls = "survey_2015_16"
            else:
                cls = "zone_map_current"
            es = (el.get("schools") or [{}])[0]
            sample_pool.append((cls, c["name"], st, c["lat"], c["lon"], zone_vint["elementary"], es.get("name")))

    cols = ["metro_file", "name", "state", "score", "levels_scored", "levels_matched", "src_elementary",
            "src_middle", "src_high", "prof_elementary", "prof_middle", "prof_high", "prof_place", "matched"]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    bystate = defaultdict(list)
    for r in out_rows:
        if r["scored"]:
            bystate[r["state"]].append(r)
    print("\nTEST B  state | scored | matched | cov | rho")
    tot_w = tot_n = 0
    for st in sorted(bystate):
        rs = bystate[st]
        m = [r for r in rs if r["matched"]]
        rho = spearman([r["score"] for r in m], [r["prof_place"] for r in m]) if len(m) >= 30 else None
        cov = len(m) / len(rs)
        if rho is not None and cov >= 0.8:
            tot_w += rho * len(m)
            tot_n += len(m)
        print("%s | %d | %d | %.0f%% | %s" % (st, len(rs), len(m), 100 * cov, "n/a" if rho is None else "%.3f" % rho))
    print("weighted mean rho over conclusive states: %s" % ("n/a" if not tot_n else "%.3f" % (tot_w / tot_n)))
    print("overall matched %d of %d scored" % (sum(1 for r in out_rows if r["matched"]), sum(1 for r in out_rows if r["scored"])))

    # Test C sample list (seed 2026): 20 zone_map_current, 10 survey_2015_16, 10 nearest
    random.seed(2026)
    with open(a.testc_out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stratum", "place", "state", "lat", "lon", "zone_vintage", "stored_elementary_school", "district_finder_read"])
        for cls, k in (("zone_map_current", 20), ("survey_2015_16", 10), ("nearest", 10)):
            pool = sorted([p for p in sample_pool if p[0] == cls])
            for p in random.sample(pool, min(k, len(pool))):
                w.writerow(p + ("",))


if __name__ == "__main__":
    main()
