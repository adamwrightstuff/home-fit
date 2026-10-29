#!/usr/bin/env python3
"""
Natural beauty face-validity test (design principles v2, P7). Offline, no API calls, no scoring changes.

No human rating data covers deserts or the final blend, so this checks that the blend does not rank places in an
order the people who know them would reject.  A rater is shown pairs (A/B order randomized, no scores) and
answers which has the more beautiful natural surroundings (street greenery, terrain, water), or "?" when they do
not know a place.  Agreement is scored on decided pairs only.

  make   writes analysis/natural_beauty_face_validity_sheet.csv (blind, give this to raters) and
         analysis/natural_beauty_face_validity_key.json (scores, keep private until scoring)
  score  reads one or more filled sheets and reports agreement with the stored score order

Pairs are drawn only where the stored scores differ by at least GAP points, so a disagreement is a real
disagreement with the blend, not a coin flip.  The 75% pass line is a judgment, not a sourced threshold.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/natural_beauty_face_validity.py make
  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/natural_beauty_face_validity.py score analysis/natural_beauty_face_validity_sheet.csv
"""
import csv
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "analysis" / "natural_beauty_face_validity_sheet.csv"
KEY = ROOT / "analysis" / "natural_beauty_face_validity_key.json"
N_PLACES, GAP, N_PAIRS, SEED, PASS_LINE = 24, 12.0, 60, 11, 0.75
ARID_METROS = {"phoenix", "las_vegas"}


def load():
    rows = []
    for p in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(p).name.split("_metro")[0]
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            at = ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type") or "unknown"
            if isinstance(nb.get("score"), (int, float)):
                rows.append({"id": f'{r["catalog"]["name"]}, {r["catalog"]["state_abbr"]}', "metro": metro, "type": at, "score": nb["score"]})
    return rows


def make():
    rng = random.Random(SEED)
    rows = load()
    # Places are drawn by metro and area type, never by score, so the choice cannot favor the blend.
    by = {}
    for r in rows:
        by.setdefault((r["metro"], r["type"]), []).append(r)
    keys = sorted(by)
    rng.shuffle(keys)
    places, arid = [], [r for r in rows if r["metro"] in ARID_METROS]
    places += rng.sample(arid, 6)  # arid places are the unvalidated case, so oversample them
    for k in keys:
        if len(places) >= N_PLACES:
            break
        c = rng.choice(by[k])
        if c not in places:
            places.append(c)
    pairs = [(a, b) for i, a in enumerate(places) for b in places[i + 1:] if abs(a["score"] - b["score"]) >= GAP]
    rng.shuffle(pairs)
    arid_pairs = [p for p in pairs if (p[0]["metro"] in ARID_METROS) != (p[1]["metro"] in ARID_METROS)]
    chosen = arid_pairs[:N_PAIRS // 3] + [p for p in pairs if p not in arid_pairs[:N_PAIRS // 3]][: N_PAIRS - min(len(arid_pairs), N_PAIRS // 3)]
    key, out = [], []
    for i, (a, b) in enumerate(chosen, 1):
        if rng.random() < 0.5:
            a, b = b, a
        key.append({"pair": i, "a": a["id"], "b": b["id"], "a_score": a["score"], "b_score": b["score"], "arid_vs_other": (a["metro"] in ARID_METROS) != (b["metro"] in ARID_METROS)})
        out.append([i, a["id"], b["id"], ""])
    with open(SHEET, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pair", "place_a", "place_b", "more_beautiful_natural_surroundings (A, B, or ?)"])
        w.writerows(out)
    KEY.write_text(json.dumps(key, indent=1))
    print(f"{len(places)} places, {len(chosen)} pairs written to {SHEET}")
    print("Places (no scores):", "; ".join(sorted(p["id"] for p in places)))


def score(paths):
    key = {k["pair"]: k for k in json.loads(KEY.read_text())}
    tot = {"all": [0, 0], "arid": [0, 0]}
    wrong = []
    for path in paths:
        for row in csv.reader(open(path, encoding="utf-8")):
            if not row or not row[0].isdigit():
                continue
            ans = (row[3] or "").strip().upper()
            if ans not in ("A", "B"):
                continue
            k = key[int(row[0])]
            agree = (ans == "A") == (k["a_score"] > k["b_score"])
            for g in ("all",) + (("arid",) if k["arid_vs_other"] else ()):
                tot[g][0] += agree
                tot[g][1] += 1
            if not agree:
                wrong.append(f'{k["a"]} ({k["a_score"]:.0f}) vs {k["b"]} ({k["b_score"]:.0f}): rater chose {ans}')
    for g, (a, n) in tot.items():
        if n:
            print(f"{g}: {a}/{n} decided pairs agree with the blend ({a / n:.0%}); pass line {PASS_LINE:.0%} (judgment)")
    print("\nDisagreements:" if wrong else "\nNo disagreements.")
    for w in wrong:
        print("  " + w)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "make":
        make()
    elif len(sys.argv) >= 3 and sys.argv[1] == "score":
        score(sys.argv[2:])
    else:
        sys.exit(__doc__)
