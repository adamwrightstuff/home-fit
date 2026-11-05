#!/usr/bin/env python3
"""
Set the diversity pillar weight to 0 in every catalog record and rescale the other weights to sum to 100.
Contributions and total_score follow (total = sum of contributions x 100 / weights of scored pillars, the stored rule).
The diversity score, breakdown and raw_shares are kept as data. Backups required with --write.

  PYTHONPATH=. python3 scripts/catalog/diversity_weight_zero_offline.py
  PYTHONPATH=. python3 scripts/catalog/diversity_weight_zero_offline.py --write --backup-dir data/backups_diversity_weight_zero_2026-10-28
"""
import argparse, json, shutil, statistics as S
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); ap.add_argument("--backup-dir")
    a = ap.parse_args()
    if a.write and not a.backup_dir: raise SystemExit("--write requires --backup-dir")
    deltas, n, off = [], 0, []
    for path in sorted(ROOT.glob("data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
        lines = path.read_text().split("\n"); ch = False
        for i, l in enumerate(lines):
            if not l.strip(): continue
            r = json.loads(l); s = r["score"]; P = s.get("livability_pillars") or {}; dv = P.get("diversity")
            if not dv or not (dv.get("weight") or 0) > 0: continue
            wd = dv["weight"]; k = 100.0 / (100.0 - wd)
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict)); ot = s.get("total_score")
            for name, v in P.items():
                if not isinstance(v, dict) or v.get("weight") is None: continue
                v["weight"] = 0.0 if name == "diversity" else v["weight"] * k
                if v.get("score") is not None and name != "diversity": v["contribution"] = round(v["score"] * v["weight"] / 100.0, 4)
                if name == "diversity": v["contribution"] = 0.0; v["importance_level"] = v.get("importance_level")
            ta = s.get("token_allocation")
            if isinstance(ta, dict):
                for name in list(ta):
                    if isinstance(ta[name], (int, float)): ta[name] = 0.0 if name == "diversity" else ta[name] * k
            for name, tb in (s.get("total_score_breakdown") or {}).items():
                if isinstance(tb, dict) and name in P and isinstance(P[name], dict):
                    if "weight" in tb: tb["weight"] = P[name]["weight"]
                    if "contribution" in tb: tb["contribution"] = P[name].get("contribution", tb["contribution"])
            pres = [v for v in P.values() if isinstance(v, dict) and v.get("score") is not None and (v.get("weight") or 0) > 0]
            new = round(sum(v.get("contribution") or 0 for v in pres) * 100.0 / sum(v["weight"] for v in pres), 2)
            if ot is not None:
                if abs(round(old_sum * 100.0 / (100.0 - 0) , 2) - ot) > 0.06 and abs(round(old_sum, 2) - ot) > 0.06:
                    off.append((path.name, r["catalog"].get("name"), ot))
                deltas.append(new - ot); s["total_score"] = new
            lines[i] = json.dumps(r, ensure_ascii=False); ch = True; n += 1
        if ch and a.write:
            b = Path(a.backup_dir); b.mkdir(parents=True, exist_ok=True); shutil.copy2(path, b / path.name); path.write_text("\n".join(lines))
    print("WROTE" if a.write else "DRY RUN", n, "places; total change mean", round(S.mean(deltas), 2), "min", round(min(deltas), 2), "max", round(max(deltas), 2))
    print(len(off), "places whose stored total did not follow either rule (changed anyway):", off[:5])


if __name__ == "__main__":
    main()
