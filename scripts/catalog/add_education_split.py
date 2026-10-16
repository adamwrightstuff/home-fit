#!/usr/bin/env python3
"""
Add the public-only / charter-only education split to every catalog place, offline.

Reads breakdown.rated_schools (every rated school that fed the score, with its charter flag),
applies the same formula as the live scorer (pillars.schools.split_scores) and writes
breakdown.split = {public: {score, n_rated, confidence}, charter: {...}}. No API calls.
The combined quality_education score is NOT changed; the script also re-derives it from
rated_schools and reports any place whose stored score does not match.

  PYTHONPATH=. python3 scripts/catalog/add_education_split.py
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from pillars.schools import score_from_ratings, split_scores  # noqa: E402

METROS = ("nyc", "la", "sf", "seattle", "austin", "chicago", "philadelphia")


def main() -> None:
    for m in METROS:
        path = os.path.join(REPO, "data", f"{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl")
        out, n_split, mism, no_list = [], 0, [], 0
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                p = ((row.get("score") or {}).get("livability_pillars") or {}).get("quality_education") or {}
                b = p.get("breakdown") or {}
                rs = b.get("rated_schools")
                if b.get("model") == "zoned_v1":
                    n_split += 1  # the zoned model writes its own split (public headline vs charter choice)
                elif rs:
                    early = float(b.get("early_ed_bonus") or 0)
                    total = score_from_ratings([float(s["rating"]) for s in rs], early)["score"]
                    if p.get("score") is not None and abs(total - float(p["score"])) > 0.05:
                        mism.append((row["catalog"]["name"], p["score"], round(total, 2)))
                    b["split"] = split_scores(rs, early)
                    n_split += 1
                else:
                    no_list += 1
                out.append(json.dumps(row, ensure_ascii=False))
        tmp = path + ".splittmp"
        with open(tmp, "w") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, path)
        print(f"{m}: split added to {n_split} places, {no_list} without a school list, "
              f"{len(mism)} stored scores differ from re-derived: {mism[:5]}")


if __name__ == "__main__":
    main()
