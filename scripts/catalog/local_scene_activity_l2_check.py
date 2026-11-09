#!/usr/bin/env python3
"""
Level 2 checks (a) pin-shift and (b) launch pairs for the local scene activity tag and Aura, offline.
Criteria are fixed in docs/LOCAL_SCENE_ACTIVITY_L2.md (commit before this script was run). Reads stored files only; no API, no Overpass.

  PYTHONPATH=. python3 scripts/catalog/local_scene_activity_l2_check.py --reads <local_scene_brand_reads.jsonl> --out analysis/ls_l2
"""
import argparse, glob, json, math, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from pillars import local_scene_v2 as ls  # noqa: E402
from apply_aura import AURA_CLASSES, AURA_MAX_JOBS_PER_RESIDENT, AURA_MIN_MIX, jobs_per_resident  # noqa: E402

SHIFT_M = 500.0
COVER_M = 1000          # gated radius: shifted circle stays inside the 1,500 m reads
SHIPPED_M = 1200
READ_M = 1500
TIERS = ["Quiet", "Some", "Vibrant"]
NAMED = ["Murray Hill", "Battery Park City", "Hell's Kitchen", "Santa Monica", "Larchmont", "Rye", "Silver Lake", "Echo Park",
         "Los Feliz", "Atwater Village", "Sunnyside", "Bay Ridge", "Bronxville", "Pelham", "Hastings-on-Hudson"]
PAIRS = [(("nyc", "West Village"), ("nyc", "Pelham Bay")), (("nyc", "Tribeca"), ("nyc", "Battery Park City")),
         (("nyc", "Carroll Gardens"), ("nyc", "Pelham")), (("nyc", "Bronxville"), ("nyc", "Pelham Manor")),
         (("la", "Silver Lake"), ("nyc", "Sunnyside")), (("nyc", "Park Slope"), ("nyc", "Bay Ridge"))]


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(a))


def tier(n, qv, vf):
    return None if n is None else "Vibrant" if n >= vf else "Quiet" if n < qv else "Some"


def mid_rank(pool, x):
    n = len(pool)
    return 100.0 * (sum(1 for v in pool if v < x) + 0.5 * sum(1 for v in pool if v == x)) / n


def pctl(vals, q):
    s = sorted(vals)
    k = (len(s) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reads", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    reads = {}
    for line in open(a.reads, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            reads[r["key"]] = r
    P = []
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(path).name.split("_metro_")[0]
        for l in open(path, encoding="utf-8"):
            if not l.strip():
                continue
            d = json.loads(l)
            s = d.get("score") if d.get("success") else None
            if not isinstance(s, dict):
                continue
            c = d["catalog"]
            key = f"{float(c['lat']):.5f},{float(c['lon']):.5f}"
            v2 = s.get("local_scene_v2") or {}
            P.append(dict(metro=metro, name=c["name"], state=c.get("state_abbr"), lat=float(c["lat"]), lon=float(c["lon"]), key=key,
                          read=reads.get(key), stored_n=v2.get("independent_venues_1200m"), stored_bucket=s.get("local_scene_bucket"),
                          geo=v2.get("geography"), band=v2.get("density_band"), combined=v2.get("combined"), few=v2.get("few_venues"),
                          aura=bool(s.get("aura")), cls=(s.get("status_signal_breakdown") or {}).get("archetype"),
                          jpr=jobs_per_resident(s), s=s))
    R = {"n_catalog_scored": len(P), "n_with_read": sum(1 for p in P if p["read"])}

    # step 0: data checks
    mism = []
    maxdisc = 0.0
    for p in P:
        if not p["read"]:
            continue
        cnt = ls.independent_venue_count(p["read"]["venues"], SHIPPED_M)
        if p["stored_n"] is not None and cnt != p["stored_n"]:
            mism.append((p["name"], p["metro"], cnt, p["stored_n"]))
        for v in p["read"]["venues"]:
            if v.get("lat") is not None and v.get("distance_m") is not None:
                maxdisc = max(maxdisc, abs(hav(p["lat"], p["lon"], v["lat"], v["lon"]) - v["distance_m"]))
    R["stored_vs_recomputed_1200_mismatches"] = len(mism)
    R["stored_vs_recomputed_examples"] = mism[:10]
    R["max_distance_discrepancy_m"] = round(maxdisc, 1)
    base1200 = [p["stored_n"] for p in P if p["stored_n"] is not None]
    R["rule_on_1200_counts"] = {"median": pctl(base1200, 0.5), "p85_ceil": math.ceil(pctl(base1200, 0.85))}

    # venue sets inside the covered area, coordinates only
    for p in P:
        p["vs"] = []
        if p["read"]:
            for v in p["read"]["venues"]:
                if v.get("type") in ls.VENUE_TYPES and v.get("lat") is not None and v.get("distance_m") is not None and v["distance_m"] <= READ_M:
                    p["vs"].append(v)

    def shifted_pins(p):
        dlat = SHIFT_M / 111320.0
        dlon = SHIFT_M / (111320.0 * math.cos(math.radians(p["lat"])))
        return {"N": (p["lat"] + dlat, p["lon"]), "S": (p["lat"] - dlat, p["lon"]), "E": (p["lat"], p["lon"] + dlon), "W": (p["lat"], p["lon"] - dlon)}

    def venues_from(p, lat, lon, radius):
        out_v = []
        for v in p["vs"]:
            d = hav(lat, lon, v["lat"], v["lon"])
            if d <= radius:
                w = dict(v)
                w["distance_m"] = d
                out_v.append(w)
        return out_v

    def indep(vs):
        return sum(1 for v in vs if not ls._has_brand(v))

    # baseline at 1,000 m, cuts by the shipped rule
    for p in P:
        if p["read"]:
            vb = venues_from(p, p["lat"], p["lon"], COVER_M)
            p["b_vs"] = vb
            p["b_n"] = indep(vb)
    base = [p["b_n"] for p in P if p["read"]]
    qv, vf = pctl(base, 0.5), math.ceil(pctl(base, 0.85))
    R["cuts_1000"] = {"quiet_below": qv, "vibrant_from": vf}

    # baseline mix at 1,000 m for pin-circle places, pools by (geography, band)
    pools = defaultdict(lambda: ([], []))
    for p in P:
        if not p["read"]:
            continue
        f = ls.place_facts(p["b_vs"], COVER_M)
        p["b_facts"] = f
        if p["geo"] == "pin_circle" and p["band"] is not None:
            if f["culture_share"] is not None:
                pools[("pin_circle", p["band"])][0].append(f["culture_share"])
            if f["hangout_share"] is not None:
                pools[("pin_circle", p["band"])][1].append(f["hangout_share"])

    def mix(p, f):
        """(combined, few) at the shifted or baseline facts f; towns held as stored."""
        if p["geo"] != "pin_circle":
            return p["combined"], bool(p["few"])
        if p["band"] is None or f["culture_share"] is None or f["hangout_share"] is None:
            return None, True
        cp, hp = pools[("pin_circle", p["band"])]
        return (mid_rank(cp, f["culture_share"]) + mid_rank(hp, f["hangout_share"])) / 2, f["few_venues"]

    def class_ok(p):
        return p["cls"] in AURA_CLASSES and not (p["jpr"] is not None and p["jpr"] > AURA_MAX_JOBS_PER_RESIDENT)

    def aura_at(p, n, f):
        c, few = mix(p, f)
        return bool(n >= vf and c is not None and c >= AURA_MIN_MIX and not few and class_ok(p))

    tiers_tr = Counter()
    per_place = []
    tier_changes = []  # (base tier, shifted tier)
    jumps = 0
    nshift = same = 0
    by_base = defaultdict(lambda: [0, 0])
    abs_ch, rel_ch = [], []
    sec_dir = Counter()
    sec_same = sec_n = 0
    aura_keep = defaultdict(lambda: [0, 0])
    gains = defaultdict(int)
    base_aura = set()
    for p in P:
        if not p["read"]:
            continue
        bt = tier(p["b_n"], qv, vf)
        p["b_tier"] = bt
        p["b_aura"] = aura_at(p, p["b_n"], p["b_facts"])
        if p["b_aura"]:
            base_aura.add((p["metro"], p["name"]))
        row = dict(metro=p["metro"], name=p["name"], b_n=p["b_n"], b_tier=bt, stored_n=p["stored_n"], stored_bucket=p["stored_bucket"],
                   b_aura=p["b_aura"], stored_aura=p["aura"], shifts={})
        for dname, (la, lo) in shifted_pins(p).items():
            vsft = venues_from(p, la, lo, COVER_M)
            n = indep(vsft)
            st = tier(n, qv, vf)
            f = ls.place_facts(vsft, COVER_M)
            ao = aura_at(p, n, f)
            nshift += 1
            by_base[bt][1] += 1
            if st == bt:
                same += 1
                by_base[bt][0] += 1
            if abs(TIERS.index(st) - TIERS.index(bt)) == 2:
                jumps += 1
            abs_ch.append(abs(n - p["b_n"]))
            rel_ch.append(abs(n - p["b_n"]) / max(p["b_n"], 1))
            tier_changes.append((bt, st))
            if p["b_aura"]:
                aura_keep[p["name"]][1] += 1
                if ao:
                    aura_keep[p["name"]][0] += 1
            elif ao:
                gains[(p["metro"], p["name"])] += 1
            # secondary: shipped radius and shipped cuts, truncated beyond the 1,500 m reads
            sv = venues_from(p, la, lo, SHIPPED_M)
            sn = indep(sv)
            sbt = tier(p["stored_n"], 13, 71)
            sst = tier(sn, 13, 71)
            sec_n += 1
            if sst == sbt:
                sec_same += 1
            else:
                sec_dir["down" if TIERS.index(sst) < TIERS.index(sbt) else "up"] += 1
            row["shifts"][dname] = dict(n=n, tier=st, aura=ao, n1200=sn, tier1200=sst)
        row["changed_shifts"] = sum(1 for s_ in row["shifts"].values() if s_["tier"] != bt)
        per_place.append(row)

    kept = sum(v[0] for v in aura_keep.values())
    total_k = sum(v[1] for v in aura_keep.values())
    stored_aura = {(p["metro"], p["name"]) for p in P if p["aura"]}
    R["pin_shift_covered_1000m"] = dict(
        shifts=nshift,
        tier_unchanged_pct=round(100 * same / nshift, 1),
        vibrant_retention_pct=round(100 * by_base["Vibrant"][0] / by_base["Vibrant"][1], 1),
        two_tier_jump_pct=round(100 * jumps / nshift, 2),
        by_baseline_tier={t: dict(shifts=by_base[t][1], unchanged_pct=round(100 * by_base[t][0] / by_base[t][1], 1)) for t in TIERS if by_base[t][1]},
        median_abs_change=statistics.median(abs_ch), p95_abs_change=round(pctl(abs_ch, 0.95), 1),
        median_rel_change=round(statistics.median(rel_ch), 3), p95_rel_change=round(pctl(rel_ch, 0.95), 3),
        places_changing_in_2plus_shifts=sum(1 for r in per_place if r["changed_shifts"] >= 2),
        baseline_tier_counts=dict(Counter(r["b_tier"] for r in per_place)),
    )
    gates = R["pin_shift_covered_1000m"]
    R["pin_shift_gates"] = dict(
        g1_tier_unchanged_ge_85=gates["tier_unchanged_pct"] >= 85,
        g2_vibrant_retention_ge_80=gates["vibrant_retention_pct"] >= 80,
        g3_two_tier_jumps_le_1=gates["two_tier_jump_pct"] <= 1.0)
    R["pin_shift_secondary_1200m_truncated"] = dict(shifts=sec_n, tier_unchanged_pct=round(100 * sec_same / sec_n, 1), changed_direction=dict(sec_dir))
    R["aura"] = dict(
        baseline_aura_1000m=len(base_aura), stored_aura=len(stored_aura), overlap=len(base_aura & stored_aura),
        only_stored=sorted(stored_aura - base_aura), only_baseline=sorted(base_aura - stored_aura),
        retention_pct=round(100 * kept / total_k, 1) if total_k else None,
        retention_by_place={k: f"{v[0]}/{v[1]}" for k, v in sorted(aura_keep.items())},
        gainers=sorted([k, v] for k, v in gains.items()),
        n_gainers=len(gains))
    R["aura_gates"] = dict(g1_retention_ge_80=(R["aura"]["retention_pct"] or 0) >= 80, g2_gainers_le_10=len(gains) <= 10)

    # named places
    named = {}
    for r in per_place:
        if r["name"] in NAMED:
            named.setdefault(r["name"], []).append(dict(metro=r["metro"], b_n=r["b_n"], b_tier=r["b_tier"], stored_n=r["stored_n"],
                                                       stored_bucket=r["stored_bucket"], shifts={k: (v["n"], v["tier"]) for k, v in r["shifts"].items()}))
    R["named"] = named

    # (b) launch pairs
    idx = {(r["metro"], r["name"]): r for r in per_place}
    lab = {"Low": 0, "Some": 1, "High": 2}
    pairs = []
    ok = 0
    for (m1, n1), (m2, n2) in PAIRS:
        r1, r2 = idx.get((m1, n1)), idx.get((m2, n2))
        if not r1 or not r2:
            pairs.append(dict(pair=f"{n1} over {n2}", error="place not found or no read"))
            continue
        t1, t2 = lab.get(r1["stored_bucket"]), lab.get(r2["stored_bucket"])
        passed = t1 is not None and t2 is not None and t1 > t2
        ok += passed
        pairs.append(dict(pair=f"{n1} over {n2}", first=dict(n=r1["stored_n"], bucket=r1["stored_bucket"], n1000=r1["b_n"]),
                          second=dict(n=r2["stored_n"], bucket=r2["stored_bucket"], n1000=r2["b_n"]), passed=passed))
    R["launch_pairs"] = dict(passed=ok, of=len(PAIRS), pass_rule_ge_5=ok >= 5, detail=pairs)

    # all-places check on stored tiers
    allp = Counter(p["stored_bucket"] for p in P)
    bym = defaultdict(Counter)
    for p in P:
        bym[p["metro"]][p["stored_bucket"]] += 1
    R["all_places_stored_tiers"] = dict(overall=dict(allp), no_read=sum(1 for p in P if not p["read"]), by_metro={k: dict(v) for k, v in bym.items()},
                                        zero_count=sum(1 for p in P if p["stored_n"] == 0))
    json.dump(R, open(out / "results.json", "w"), indent=1, default=str)
    json.dump(per_place, open(out / "per_place.json", "w"))
    print(json.dumps({k: v for k, v in R.items() if k not in ("named",)}, indent=1, default=str))
    print("NAMED", json.dumps(named, default=str))


if __name__ == "__main__":
    main()
