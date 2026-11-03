"""Recent-year (2023-24) rerun of Test A for NY high schools and Test D for CA places.

Companion to validate_education_edfacts.py; same fixed bars (analysis/education_validation_brief_2026-11-03.md).
Offline. Inputs are official state files the owner approved, each unpacked in its own folder:

  CA: CDE CAASPP 2023-24 research files sb_ca2024_1_csv_v1.zip (all students, caret-delimited) and
      sb_ca2024entities_csv.zip, from caaspp-elpac.ets.org. Unzip both into one empty folder.
  NY: NYSED data.nysed.gov SRC2024.zip (Access database). Export with mdbtools:
      mdb-export SRC2024_Group5.mdb "Annual Regents Exams" > Annual_Regents_Exams.csv

    python3 -I scripts/catalog/validate_education_recent.py --ca CA_DIR --ny NY_CSV_DIR

Proficiency definitions:
  CA: mean of ELA and math percent Standard Met and Above, grade 13 (all grades), all students, school rows.
  NY high: tested-weighted mean percent proficient (level 3+) over a school's 2024 Regents exams, all students;
      suppressed cells dropped, schools with fewer than 20 tested exam takers dropped.
Matching: snapshot school to state file by normalised name (CA also by zip). NY has no zip or NCES id in the
Regents table, so only names that are unique in both the snapshot's rated NY high schools and the state file are
used; the matched subset is reported, not assumed representative.
"""
import argparse
import csv
import gzip
import json
import os
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_education_edfacts import norm, spearman  # noqa: E402


def snap_rows(st):
    rows = json.load(gzip.open("data/school_snapshot/%s.json.gz" % st))["schools"]
    out = []
    for s in rows:
        if s.get("isPrivate") or not s.get("rankHistory"):
            continue
        rat = s["rankHistory"][0].get("rankStatewidePercentage")
        if rat is None:
            continue
        a = s.get("address") or {}
        out.append({"name": s["schoolName"], "nname": norm(s["schoolName"]), "level": (s.get("schoolLevel") or "").lower(),
                    "rating": rat, "zip": (a.get("zip") or "")[:5], "city": a.get("city")})
    return out


def read_caret(path):
    with open(path, encoding="latin-1") as f:
        r = csv.reader(f, delimiter="^")
        head = next(r)
        for row in r:
            yield dict(zip(head, row))


def ca_prof(folder):
    ents = {}
    for r in read_caret(os.path.join(folder, "sb_ca2024entities_csv.txt")):
        if r["School Code"] != "0000000":
            ents[(r["County Code"], r["District Code"], r["School Code"])] = (r["School Name"], r["Zip Code"][:5])
    acc = defaultdict(dict)
    for r in read_caret(os.path.join(folder, "sb_ca2024_1_csv_v1.txt")):
        if r["Grade"] != "13" or r["Student Group ID"] != "1" or r["School Code"] == "0000000":
            continue
        try:
            acc[(r["County Code"], r["District Code"], r["School Code"])][r["Test ID"]] = float(r["Percentage Standard Met and Above"])
        except ValueError:
            pass
    out = defaultdict(list)
    for k, d in acc.items():
        if "1" in d and "2" in d and k in ents:
            nm, z = ents[k]
            out[(norm(nm), z)].append((d["1"] + d["2"]) / 2)
    return out


def ny_prof(folder):
    tot, cnt, names = defaultdict(float), defaultdict(float), {}
    for r in csv.DictReader(open(os.path.join(folder, "Annual_Regents_Exams.csv"))):
        if r["YEAR"] != "2024" or r["SUBGROUP_NAME"] != "All Students" or r["ENTITY_CD"][-4:] == "0000":
            continue
        try:
            t, p = float(r["TESTED"]), float(r["PER_PROF"])
        except ValueError:
            continue
        tot[r["ENTITY_CD"]] += t * p
        cnt[r["ENTITY_CD"]] += t
        names[r["ENTITY_CD"]] = r["ENTITY_NAME"]
    byname = defaultdict(list)
    for k, n in cnt.items():
        if n >= 20:
            byname[norm(names[k])].append(tot[k] / n)
    return byname


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ca")
    ap.add_argument("--ny")
    a = ap.parse_args()
    if a.ny:
        by = ny_prof(a.ny)
        hs = [r for r in snap_rows("NY") if r["level"] == "high"]
        cnt = defaultdict(int)
        for r in hs:
            cnt[r["nname"]] += 1
        m = [(r["rating"], by[r["nname"]][0]) for r in hs if cnt[r["nname"]] == 1 and len(by.get(r["nname"], [])) == 1]
        rho = spearman([x for x, _ in m], [y for _, y in m]) if len(m) >= 30 else None
        print("NY high 2023-24 Regents: snapshot rated high schools %d, uniquely matched %d, spearman %s" % (
            len(hs), len(m), "n/a" if rho is None else "%.3f" % rho))
    if a.ca:
        pr = ca_prof(a.ca)
        sn = snap_rows("CA")
        print("CA 2023-24 (ELA+math met and above, all grades) Test A by level:")
        for lv in ("elementary", "middle", "high"):
            m = []
            n_all = 0
            for r in sn:
                if r["level"] != lv:
                    continue
                n_all += 1
                v = pr.get((r["nname"], r["zip"]))
                if v and len(v) == 1:
                    m.append((r["rating"], v[0]))
            rho = spearman([x for x, _ in m], [y for _, y in m]) if len(m) >= 30 else None
            print("  %s: rated %d, matched %d, spearman %s" % (lv, n_all, len(m), "n/a" if rho is None else "%.3f" % rho))
        print("CA Test D schools:")
        for name, zp in (("Dr. Martin Luther King Junior Academy", None), ("Walnut Grove Elementary", None),
                         ("Clarksburg Middle", None), ("Delta High", None), ("Tamalpais High", None)):
            for r in sn:
                if r["nname"] == norm(name):
                    v = pr.get((r["nname"], r["zip"]))
                    print("  %s (%s) rating %.1f  2024 proficiency %s" % (r["name"], r["city"], r["rating"], v))


if __name__ == "__main__":
    main()
