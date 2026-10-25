#!/usr/bin/env python3
"""
Rewrite the diversity pillar's race entropy in catalog composites files from raw ACS B02001 counts.

New formula (pillars/diversity.py): drop B02001_009/_010 (parts of _008), normalize race entropy by the
fixed seven groups. Income and age entropy are untouched. Headline diversity = mean of the components
present, contribution = score x weight / 100, total_score follows.

Raw counts are not stored in the catalog, so they come from a file produced by a one-off Census pull
(keys "metro|name|lat|lon"). Places are skipped, not guessed, when the raw counts are missing, when
recomputing the OLD formula from them does not reproduce the stored race_entropy, or when the stored
headline does not reproduce from its parts.

  cd /path/to/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_diversity_race_offline.py --raw data/backups_diversity_fix_2026-10-24/raw_race_counts.jsonl            # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_diversity_race_offline.py --raw ... --write --backup-dir data/backups_diversity_fix_2026-10-24
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from pillars.diversity import RACE_CATEGORY_COUNT, RACE_SUBSET_KEYS, _normalized_entropy  # noqa: E402


def old_race_entropy(race_counts):
    v = list(race_counts.values())
    nz = sum(1 for x in v if x > 0)
    return _normalized_entropy(v, nz) if nz >= 2 else None


def new_race_entropy(race_counts):
    v = [x for k, x in race_counts.items() if k not in RACE_SUBSET_KEYS]
    nz = sum(1 for x in v if x > 0)
    return _normalized_entropy(v, RACE_CATEGORY_COUNT) if nz >= 2 else None


def headline(breakdown):
    vals = [breakdown[k] for k in ("race_entropy", "income_entropy", "age_entropy") if breakdown.get(k) is not None]
    return max(0.0, min(100.0, round(sum(vals) / len(vals), 1))) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")

    raw = {}
    for line in open(a.raw):
        r = json.loads(line)
        if "race_counts" in r:
            raw[r["key"]] = r["race_counts"]

    skipped = {"no_raw": 0, "old_not_reproduced": 0, "headline_not_reproduced": 0, "single_group": 0}
    skipped_names = {k: [] for k in skipped}
    changed = 0
    total_sum_ok = total_delta = 0
    deltas = []
    stray = 0
    per_file = {}
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out_lines = []
        n_changed = 0
        old_vals = {}
        with open(path, encoding="utf-8") as fh:
            text_lines = fh.read().split("\n")
        for line in text_lines:
            if not line.strip():
                out_lines.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out_lines.append(line)
                continue
            s = rec.get("score") or {}
            co = s.get("coordinates") or {}
            div = ((s.get("livability_pillars") or {}).get("diversity"))
            bd = (div or {}).get("breakdown") or {}
            if not div or bd.get("race_entropy") is None or not co.get("lat"):
                out_lines.append(line)
                continue
            cat = rec.get("catalog")
            nm = cat.get("name") if isinstance(cat, dict) else s.get("input")
            key = f"{metro}|{nm}|{co['lat']:.5f}|{co['lon']:.5f}"
            rc = raw.get(key)
            if rc is None:
                skipped["no_raw"] += 1; skipped_names["no_raw"].append(key); out_lines.append(line); continue
            o = old_race_entropy(rc)
            if o is None or abs(round(o, 1) - bd["race_entropy"]) > 0.11:
                skipped["old_not_reproduced"] += 1; skipped_names["old_not_reproduced"].append(key); out_lines.append(line); continue
            if headline(bd) is None or abs(headline(bd) - div["score"]) > 0.06:
                skipped["headline_not_reproduced"] += 1; skipped_names["headline_not_reproduced"].append(key); out_lines.append(line); continue
            n = new_race_entropy(rc)
            if n is None:
                skipped["single_group"] += 1; skipped_names["single_group"].append(key); out_lines.append(line); continue

            old_score = div["score"]
            old_total = s.get("total_score")
            pillars = s["livability_pillars"]
            old_sum = sum((v.get("contribution") or 0) for v in pillars.values() if isinstance(v, dict))
            old_vals[key] = {"diversity": json.loads(json.dumps(div)), "total_score": old_total,
                             "total_score_breakdown_diversity": (s.get("total_score_breakdown") or {}).get("diversity")}

            bd["race_entropy"] = round(n, 1)
            new_score = headline(bd)
            bd["diversity_score"] = new_score
            div["score"] = new_score
            if isinstance(div.get("summary"), dict) and "diversity_entropy_score" in div["summary"]:
                div["summary"]["diversity_entropy_score"] = new_score
            w = div.get("weight") or 0.0
            div["contribution"] = round(new_score * w / 100.0, 4)
            tb = (s.get("total_score_breakdown") or {}).get("diversity")
            if isinstance(tb, dict):
                tb["score"] = new_score
                tb["contribution"] = div["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in pillars.values() if isinstance(v, dict))
            if old_total is not None:
                if abs(round(old_sum, 2) - old_total) <= 0.0051:
                    s["total_score"] = round(new_sum, 2); total_sum_ok += 1
                else:
                    s["total_score"] = round(old_total + (new_sum - old_sum), 2); total_delta += 1
                deltas.append(s["total_score"] - old_total)
            # any other copy of the old diversity score string in the record?
            if f'"diversity_score": {old_score}' in line.replace(f'"diversity_score": {old_score},', '', 0) and False:
                stray += 1
            out_lines.append(json.dumps(rec, ensure_ascii=False))
            n_changed += 1
        per_file[metro] = n_changed
        changed += n_changed
        if a.write and n_changed:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            bdir = Path(a.backup_dir)
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, bdir / os.path.basename(path))
            with open(bdir / (metro + "_old_diversity_values.json"), "w") as fh:
                json.dump(old_vals, fh)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(out_lines))
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print("records changed:", changed, per_file)
    print("skipped:", skipped)
    print("total_score method: sum-of-contributions", total_sum_ok, "| delta", total_delta)
    if deltas:
        print("total_score delta mean %.3f min %.1f max %.1f" % (sum(deltas) / len(deltas), min(deltas), max(deltas)))
    json.dump(skipped_names, open(os.path.join(os.path.dirname(a.raw), "skipped_places.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
