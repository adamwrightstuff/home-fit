#!/usr/bin/env python3
"""
Build status signal breakdown (wealth, education, occupation, brand) from saved score JSONs
and write a markdown report. Uses compute_status_signal_with_breakdown + brand matches.

Usage (from project root):
  PYTHONPATH=. python3 scripts/status_signal_breakdown_md.py score_a.json score_b.json -o analysis/status_signal_breakdown.md
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def get_business_list(data: dict) -> list:
    pillars = data.get("livability_pillars") or {}
    na = pillars.get("neighborhood_amenities") or {}
    breakdown = na.get("breakdown") or {}
    return breakdown.get("business_list") or na.get("business_list") or []


def load_breakdown(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pillars = data.get("livability_pillars") or {}
    housing = pillars.get("housing_value")
    social = pillars.get("social_fabric")
    economic = pillars.get("economic_security")
    amenities = pillars.get("neighborhood_amenities")
    business_list = get_business_list(data)
    coords = data.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    state = (data.get("location_info") or {}).get("state")

    census_tract = None
    if lat is not None and lon is not None:
        try:
            from data_sources.census_api import get_census_tract
            census_tract = get_census_tract(lat, lon)
        except Exception:
            pass

    from pillars.status_signal import compute_status_signal_with_breakdown, _brand_matches_for_business_list

    loc = data.get("location_info") or {}
    city = loc.get("city")
    score, breakdown = compute_status_signal_with_breakdown(
        housing,
        social,
        economic,
        business_list,
        census_tract,
        state,
        city=city,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
    )
    brand_matches = _brand_matches_for_business_list(business_list) if business_list else []

    return {
        "input": data.get("input", path),
        "status_signal_json": data.get("status_signal"),
        "status_signal_computed": score,
        "breakdown": breakdown,
        "brand_matches": brand_matches,
        "business_count": len(business_list),
    }


def to_markdown(results: list) -> str:
    lines = [
        "# Status Signal Breakdown: Tribeca vs Carroll Gardens",
        "",
        "Formula: **Brand 35% + Wealth 25% + Education 20% + Occupation 20%**",
        "",
        "---",
        "",
    ]
    for r in results:
        name = r["input"].split(",")[0].strip()
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- **Location:** {r['input']}")
        lines.append(f"- **Status signal (from JSON):** {r['status_signal_json']}")
        lines.append(f"- **Status signal (recomputed):** {r['status_signal_computed']}")
        lines.append(f"- **Businesses in radius:** {r['business_count']}")
        lines.append("")
        b = r.get("breakdown") or {}
        lines.append("### Component scores (0–100)")
        lines.append("")
        lines.append("| Component | Weight | Score | Contribution |")
        lines.append("|----------|--------|-------|--------------|")
        for key, label in [("wealth", "Wealth"), ("education", "Education"), ("occupation", "Occupation"), ("brand", "Brand")]:
            s = b.get(key)
            w = {"wealth": 0.25, "education": 0.20, "occupation": 0.20, "brand": 0.35}[key]
            contrib = round((s or 0) * w, 1) if s is not None else "—"
            score_str = round(s, 1) if s is not None else "—"
            lines.append(f"| {label} | {int(w*100)}% | {score_str} | {contrib} |")
        lines.append("")
        lines.append("### Brand category matches")
        lines.append("")
        for m in r.get("brand_matches", []):
            names = m.get("matched_names", [])
            lines.append(f"- **{m['category']}** (weight {m['weight']}, category score {m['cat_score']})")
            if names:
                # Show first 15, then "and N more" if needed
                show = names[:15]
                extra = len(names) - 15
                names_str = ", ".join(f"\"{n}\"" for n in show)
                if extra > 0:
                    names_str += f" *(+{extra} more)*"
                lines.append(f"  - {names_str}")
            else:
                lines.append("  - *(none)*")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main():
    out_path = None
    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "-o" and i + 1 < len(sys.argv):
            out_path = sys.argv[i + 1]
            i += 2
            continue
        if not sys.argv[i].startswith("-"):
            args.append(sys.argv[i])
        i += 1
    if not args:
        print("Usage: status_signal_breakdown_md.py <score_json> [<score_json> ...] [-o out.md]", file=sys.stderr)
        sys.exit(1)

    results = []
    for path in args:
        if not os.path.isfile(path):
            print(f"Skip (not found): {path}", file=sys.stderr)
            continue
        results.append(load_breakdown(path))

    md = to_markdown(results)
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Wrote {out_path}")
    else:
        print(md)


if __name__ == "__main__":
    main()
