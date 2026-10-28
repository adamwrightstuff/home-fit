#!/usr/bin/env python3
"""
Offline: re-score pooled housing rows whose stored single-tract score no longer reproduces from the stored inputs.

27 LA tract-level rows were scored by older code (value efficiency above its 20 point cap, for example Chatsworth 73.0
where the current code gives about 57). For those rows only, the housing total becomes the current-code pooled score
(analysis/audit_housing_d14_exact_places.jsonl, field pooled_700), the single-tract breakdown is rebuilt from the
stored inputs, and the composites are recomputed for just those rows. Other rows are left byte-for-byte unchanged.
The pooled score here has no Zillow override and uses metro multiplier 1.0 (under 1 point difference).

  PYTHONPATH=. python3 scripts/catalog/recompute_housing_stale_offline.py                          # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_housing_stale_offline.py --write --backup-dir <dir>
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
sys.path.insert(0, str(ROOT))
from pillars.housing_value import _score_local_affordability, _score_rent_affordability, _score_space, _score_value_efficiency  # noqa: E402


def single_parts(sm: dict):
    """Current-code (affordability, space, efficiency) from stored summary inputs (blended, rent-only or owner path)."""
    v, inc, rooms = sm.get("median_home_value"), sm.get("median_household_income"), sm.get("median_rooms")
    rent, rp = sm.get("median_gross_rent"), sm.get("renter_pct")
    has_rent = rent is not None and rent > 0
    if v is not None and has_rent and rp is not None:
        oa, ra = _score_local_affordability(v, inc), _score_rent_affordability(rent, inc)
        aff = (1 - rp) * oa + rp * ra if oa is not None and ra is not None else None
        e = _score_value_efficiency(v, rooms, None)
        return aff, _score_space(rooms), (e * (1 - rp) if e is not None else None)
    if v is None and has_rent:
        sp = _score_space(rooms)
        return _score_rent_affordability(rent, inc), sp, (0.0 if sp is not None else None)
    return _score_local_affordability(v, inc), _score_space(rooms), _score_value_efficiency(v, rooms, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--pooled", default=str(ROOT / "analysis" / "audit_housing_d14_exact_places.jsonl"))
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    pooled = {}
    for l in Path(a.pooled).read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            pooled[(r["metro"], r["name"])] = r
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
            pool = ((h or {}).get("summary") or {}).get("pooling")
            p = pooled.get((metro, (rec.get("catalog") or {}).get("name")))
            stale = (p and pool and h.get("score") is not None and not p.get("value_overridden")
                     and p.get("pooled_700") is not None and abs(pool["single_tract_score"] - p["rebuilt"]) > 1.0)
            if not stale:
                new.append(line)
                continue
            aff, sp, ef = single_parts(h["summary"])
            old_score = h["score"]
            h["score"] = round(min(100.0, max(0.0, p["pooled_700"])), 1)
            h["contribution"] = round(h["score"] * (h.get("weight") or 0) / 100.0, 4)
            h["breakdown"] = {"local_affordability": round(aff, 1) if aff is not None else None,
                              "space": round(sp, 1) if sp is not None else None,
                              "value_efficiency": round(ef, 1) if ef is not None else None}
            pool["single_tract_score"] = round(p["rebuilt"], 1)
            pool["stale_fixed"] = True
            tb = (s.get("total_score_breakdown") or {}).get("housing_value")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = h["score"], h["contribution"]
            fixed.append((metro, rec["catalog"]["name"], old_score, h["score"]))
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
            after = Path(path).read_text(encoding="utf-8").split("\n")      # keep the recompute only for the fixed rows
            Path(path).write_text("\n".join(b if '"stale_fixed"' in b else o for o, b in zip(old, after)), encoding="utf-8")
    print(f"{'WROTE' if a.write else 'dry run'}: {len(fixed)} rows")
    for m, n_, o, s_ in fixed:
        print(f"  {m} {n_}: {o} -> {s_}")


if __name__ == "__main__":
    main()
