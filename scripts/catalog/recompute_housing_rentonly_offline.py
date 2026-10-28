#!/usr/bin/env python3
"""
Offline: housing places with no owner-occupied home value leave value efficiency out and rescale the rest to 100.

The old rule scored value efficiency 0 when the tract (or the whole pool) had no median owner value, which cost these
places 1 to 15 points (owner decision 2026-10-28 to change it). With efficiency at 0 the stored total is affordability
plus space out of 100, so the rescaled score is the stored total times 100/80. The breakdown value efficiency becomes
None. Composites are recomputed for the changed rows only; other rows stay byte-for-byte unchanged.

  PYTHONPATH=. python3 scripts/catalog/recompute_housing_rentonly_offline.py                          # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_housing_rentonly_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rent_only(h: dict) -> bool:
    sm = h.get("summary") or {}
    if h.get("score") is None or sm.get("rentonly_rescaled"):
        return False
    pool = sm.get("pooling")
    if pool:
        return pool.get("median_home_value") is None and pool.get("value_efficiency") == 0
    return sm.get("median_home_value") is None and (sm.get("median_gross_rent") or 0) > 0 \
        and (h.get("breakdown") or {}).get("value_efficiency") == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    fixed = []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        old = Path(path).read_text(encoding="utf-8").split("\n")
        new, n = [], 0
        for line in old:
            if not line.strip():
                new.append(line)
                continue
            rec = json.loads(line)
            s = rec.get("score") or {}
            h = (s.get("livability_pillars") or {}).get("housing_value")
            if not (isinstance(h, dict) and rent_only(h)):
                new.append(line)
                continue
            before = h["score"]
            h["score"] = round(min(100.0, before * 100.0 / 80.0), 1)
            h["contribution"] = round(h["score"] * (h.get("weight") or 0) / 100.0, 4)
            sm = h["summary"]
            sm["rentonly_rescaled"] = True
            if sm.get("pooling") is not None:
                sm["pooling"]["value_efficiency"] = None
            if isinstance(h.get("breakdown"), dict):
                h["breakdown"]["value_efficiency"] = None
            tb = (s.get("total_score_breakdown") or {}).get("housing_value")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = h["score"], h["contribution"]
            fixed.append((metro, rec["catalog"]["name"], before, h["score"]))
            new.append(json.dumps(rec, ensure_ascii=False))
            n += 1
        if a.write and n:
            bd = Path(a.backup_dir)
            bd.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, bd / os.path.basename(path))
            Path(path).write_text("\n".join(new), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "catalog" / "recompute_catalog_composites.py"),
                            "--input", path, "--in-place", "--no-census"], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            after = Path(path).read_text(encoding="utf-8").split("\n")      # keep the recompute only for the changed rows
            Path(path).write_text("\n".join(b if '"rentonly_rescaled"' in b else o for o, b in zip(old, after)), encoding="utf-8")
    print(f"{'WROTE' if a.write else 'dry run'}: {len(fixed)} rows")
    for m, n_, b, s_ in fixed:
        print(f"  {m} {n_}: {b} -> {s_}")


if __name__ == "__main__":
    main()
