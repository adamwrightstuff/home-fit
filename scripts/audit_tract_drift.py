#!/usr/bin/env python3
"""
Audit tract-resolution drift across the catalog.

Root issue: a place is scored at ONE pin -> ONE census tract, and that resolution is unstable
(Harrison's pin resolved a ~28-min Purchase tract at build, a 39-min central tract now). Every
tract-based pillar (commute, diversity, transit share, resident econ) inherits this.

Measure it directly: stored build-time mean_commute_minutes vs a FRESH get_commute_time, for
every place. Big gap => the pin's tract resolution (or its value) drifted. For drifted places,
also re-fetch diversity + transit share to see if the drift propagated to other tract pillars.

Output: data/tract_drift_audit.jsonl (resumable). Census-only, throttled + retried.
Usage: python3 scripts/audit_tract_drift.py
"""
from __future__ import annotations
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_sources.census_api import get_commute_time, get_census_tract, get_transit_mode_share  # noqa

CATALOGS = ["data/nyc_metro_place_catalog_scores_merged.jsonl",
            "data/la_metro_place_catalog_scores_merged.jsonl"]
OUT = "data/tract_drift_audit.jsonl"


def retry(fn, *a, tries=4):
    for i in range(tries):
        try:
            v = fn(*a)
        except Exception:
            v = None
        if v is not None:
            return v
        time.sleep(1.2 * (i + 1))
    return None


def stored_commute_min(sc):
    t = sc.get("livability_pillars", {}).get("public_transit_access", {})
    s = t.get("summary", {}) or {}
    if isinstance(s.get("mean_commute_minutes"), (int, float)):
        return s["mean_commute_minutes"]
    d = (t.get("details", {}) or {}).get("commute_time", {}) or {}
    return d.get("mean_minutes")


def main():
    done = set()
    if os.path.isfile(OUT):
        for line in open(OUT):
            try: done.add(json.loads(line)["name"])
            except Exception: pass
    out = open(OUT, "a")
    rows = []
    for fn in CATALOGS:
        if not os.path.isfile(fn): continue
        for line in open(fn):
            r = json.loads(line)
            rows.append((r["catalog"], r["score"]))
    todo = [(c, s) for c, s in rows if c.get("name") not in done]
    print(f"{len(todo)} places to audit ({len(done)} done)", flush=True)
    for i, (cat, sc) in enumerate(todo, 1):
        nm = cat.get("name", "")
        lat, lon = float(cat["lat"]), float(cat["lon"])
        stored = stored_commute_min(sc)
        fresh = retry(get_commute_time, lat, lon)
        tract = retry(get_census_tract, lat, lon)
        tid = f"{tract['state_fips']}/{tract['county_fips']}/{tract['tract_fips']}" if tract else None
        drift = (abs(stored - fresh) if isinstance(stored, (int, float)) and fresh else None)
        rec = {"name": nm, "stored_commute_min": stored, "fresh_commute_min": fresh,
               "drift_min": round(drift, 1) if drift is not None else None, "fresh_tract": tid}
        out.write(json.dumps(rec) + "\n"); out.flush()
        flag = " <== DRIFT" if (drift is not None and drift > 3) else ""
        print(f"[{i}/{len(todo)}] {nm:22s} stored={stored} fresh={fresh} drift={rec['drift_min']}{flag}", flush=True)
        time.sleep(0.4)
    # summary
    allrecs = [json.loads(l) for l in open(OUT)]
    drifts = [r for r in allrecs if isinstance(r.get("drift_min"), (int, float))]
    big = [r for r in drifts if r["drift_min"] > 3]
    huge = [r for r in drifts if r["drift_min"] > 8]
    print(f"\n=== {len(drifts)} measurable / {len(big)} drift>3min / {len(huge)} drift>8min ===", flush=True)
    for r in sorted(big, key=lambda x: -x["drift_min"])[:25]:
        print(f"   {r['name']:22s} stored={r['stored_commute_min']} fresh={r['fresh_commute_min']} (Δ{r['drift_min']})", flush=True)


if __name__ == "__main__":
    main()
