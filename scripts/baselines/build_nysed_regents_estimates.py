"""
Build data/nysed_regents_estimates.json: an estimated school rating for NY public schools that SchoolDigger
leaves unrated but whose Regents results NYSED publishes (Babylon Junior-Senior High is one).

Rating = SchoolDigger's statewide percentile, which is what the education pillar scores. The estimate maps a school's
tested-weighted Regents percent proficient (all students, 2024, at least 20 exam takers) onto that scale with an
isotonic (monotone) fit to the NY high schools that have both numbers. Matching is by normalised name and only
when the name is unique among NY snapshot schools and among NYSED entities (the Regents table has no zip or NCES id).
Only schools with no SchoolDigger rating get an estimate; a rated school is never touched.

Inputs: Annual_Regents_Exams.csv, exported with mdbtools from SRC2024_Group5.mdb in
https://data.nysed.gov/files/essa/23-24/SRC2024.zip:
    mdb-export SRC2024_Group5.mdb "Annual Regents Exams" > Annual_Regents_Exams.csv

    PYTHONPATH=. python3 scripts/baselines/build_nysed_regents_estimates.py Annual_Regents_Exams.csv
"""
import csv
import gzip
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
YEAR = "2024"
MIN_TESTED = 20


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def isotonic(points):
    """Pool-adjacent-violators fit of y on x (both lists sorted by x). Returns [(x, fitted_y)]."""
    blocks = []  # [sum_y, n, x_lo, x_hi]
    for x, y in points:
        blocks.append([y, 1, x, x])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            b = blocks.pop()
            blocks[-1][0] += b[0]
            blocks[-1][1] += b[1]
            blocks[-1][3] = b[3]
    out = []
    for s, n, lo, hi in blocks:
        out.append(((lo + hi) / 2.0, s / n))
    return out


def interp(fit, x):
    if x <= fit[0][0]:
        return fit[0][1]
    if x >= fit[-1][0]:
        return fit[-1][1]
    for (x0, y0), (x1, y1) in zip(fit, fit[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def main(path):
    agg = defaultdict(lambda: [0.0, 0.0])
    ent = {}
    for r in csv.DictReader(open(path, encoding="utf-8", errors="replace")):
        if r["YEAR"] != YEAR or r["SUBGROUP_NAME"] != "All Students" or not r["ENTITY_CD"].strip("0"):
            continue
        try:
            t, p = float(r["TESTED"]), float(r["PER_PROF"])
        except ValueError:
            continue  # suppressed cell ("s")
        a = agg[r["ENTITY_CD"]]
        a[0] += t
        a[1] += t * p
        ent[r["ENTITY_CD"]] = r["ENTITY_NAME"]
    prof = defaultdict(list)
    for cd, (t, tp) in agg.items():
        if t >= MIN_TESTED:
            prof[norm(ent[cd])].append((tp / t, t))

    snap = json.load(gzip.open(os.path.join(ROOT, "data", "school_snapshot", "NY.json.gz")))["schools"]
    by_name = defaultdict(list)
    for s in snap:
        if not s.get("isPrivate"):
            by_name[norm(s["schoolName"])].append(s)

    pairs = []
    for n, ss in by_name.items():
        if len(ss) != 1 or len(prof.get(n, [])) != 1:
            continue
        s = ss[0]
        rh = s.get("rankHistory") or []
        if rh and (s.get("schoolLevel") or "").lower() == "high" and rh[0].get("rankStatewidePercentage") is not None:
            pairs.append((prof[n][0][0], float(rh[0]["rankStatewidePercentage"])))
    pairs.sort()
    fit = isotonic(pairs)

    est = {}
    for n, ss in by_name.items():
        if len(ss) != 1 or len(prof.get(n, [])) != 1:
            continue
        s = ss[0]
        if s.get("rankHistory") or str(s.get("highGrade")) not in ("11", "12"):
            continue  # rated already, or not a secondary school (a same-named elementary school must not get one)
        p, tested = prof[n][0]
        est[str(s["schoolid"])] = {"name": s["schoolName"], "rating": round(interp(fit, p), 2),
                                   "regents_pct_proficient": round(p, 1), "tested": int(tested)}
    out = {"meta": {"source": "NYSED SRC2024 Annual Regents Exams, 2024, all students",
                    "method": "isotonic fit of SchoolDigger statewide percentile on tested-weighted percent proficient",
                    "calibration_pairs": len(pairs), "min_tested": MIN_TESTED}, "schools": est}
    dest = os.path.join(ROOT, "data", "nysed_regents_estimates.json")
    json.dump(out, open(dest, "w"), indent=1, sort_keys=True)
    print("calibration pairs %d, estimates %d -> %s" % (len(pairs), len(est), dest))
    for k, v in list(est.items())[:10]:
        print(k, v)


if __name__ == "__main__":
    main(sys.argv[1])
