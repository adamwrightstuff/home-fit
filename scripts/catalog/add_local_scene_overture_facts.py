#!/usr/bin/env python3
"""
Overture Maps venue facts for the Local Scene ladder (owner decision 2026-11-13). Free; no paid API.

Reads the Overture Maps Places release from the public S3 bucket with DuckDB, one bounding box per metro, and writes
score.local_scene_v2.overture for every catalog place: the same facts as the OpenStreetMap read (venues_total, culture_venues, shares,
independent_venues_1200m) counted from Overture venues of the same seven types in the same measured area.

Measured area: the amenities pin circle (1,200 or 1,500 m, the radius the stored business list used) for places measured as a pin
circle; for places OSM measured by town boundary, an equal-area circle around the pin (radius sqrt(area / pi), 800 to 4,000 m). The town
boundary polygons are not used for Overture, an approximation recorded in the stored block (geography: equal_area_circle).

Overture rows kept: operating_status open, a primary name, confidence 0.5 or more (missing confidence kept), not registry-only (a row whose
only source besides Overture itself is BrightQuery, a business registry that lists legal entities, not storefronts), mapped to one of
the seven types. A venue is a chain when Overture gives it a brand name or brand wikidata id.

Needs duckdb (pip install duckdb) and network access to s3://overturemaps-us-west-2. A full run reads about 21 metro boxes.

  python3 scripts/catalog/add_local_scene_overture_facts.py                  # dry run
  python3 scripts/catalog/add_local_scene_overture_facts.py --write
  python3 scripts/catalog/add_local_scene_overture_facts.py --write --release 2026-10-21.0 --metros nyc la
"""
import argparse, glob, json, math, os, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402

DEFAULT_RELEASE = "2026-10-21.0"
MIN_CONFIDENCE = 0.5
BBOX_MARGIN_DEG = 0.06
FILTERS = "operating open; confidence >= 0.5; not BrightQuery-only; seven venue types"

_SQL_KEEP = """(basic_category in ('restaurant','cafe','coffee_shop','bar','art_gallery','bookstore','movie_theater','theatre','performing_arts_theater')
  or taxonomy.primary in ('restaurant','cafe','coffee_shop','bar','pub','wine_bar','cocktail_bar','brewery','art_gallery','bookstore','book_store','record_store','movie_theater','theater','performing_arts_venue'))"""


def venue_type(primary, basic):
    """Map an Overture category to one of the seven ladder types, or None."""
    if primary in ("cafe", "coffee_shop") or basic in ("cafe", "coffee_shop"):
        return "cafe"
    if primary in ("bar", "pub", "wine_bar", "cocktail_bar", "brewery") or basic == "bar":
        return "bar"
    if basic == "restaurant" or primary == "restaurant":
        return "restaurant"
    if primary == "art_gallery" or basic == "art_gallery":
        return "gallery"
    if primary in ("bookstore", "book_store") or basic == "bookstore":
        return "bookstore"
    if primary == "record_store":
        return "records"
    if primary in ("movie_theater", "theatre", "theater", "performing_arts_theater", "performing_arts_venue") or basic in ("movie_theater", "theatre", "performing_arts_theater"):
        return "theater"
    return None


def keep_row(confidence, sources) -> bool:
    if confidence is not None and confidence < MIN_CONFIDENCE:
        return False
    real = set(sources or []) - {"Overture", "Overture-signals"}
    return real != {"BrightQuery"}


def pin_radius(score) -> int:
    """1,200 m when the farthest stored amenities listing is within 1,210 m, else 1,500 m (same rule as the OSM read)."""
    bl = ((((score.get("livability_pillars") or {}).get("neighborhood_amenities") or {}).get("breakdown")) or {}).get("business_list") or []
    mx = max((b["distance_m"] for b in bl if b.get("distance_m") is not None), default=None)
    return 1200 if (mx is not None and mx <= 1210) else 1500


def measured_area(score):
    """(geography, radius_m, area_km2) for the Overture count, mirroring how OSM measured the place."""
    v2 = score.get("local_scene_v2") or {}
    if v2.get("geography") == "town_boundary" and v2.get("area_km2"):
        area = float(v2["area_km2"])
        return "town_boundary", max(800.0, min(4000.0, math.sqrt(area / math.pi) * 1000.0)), area
    r = pin_radius(score)
    return "pin_circle", float(r), math.pi * (r / 1000.0) ** 2


def facts_for(rows, lat, lon, geography, radius_m, area_km2):
    kx = 111320.0 * math.cos(math.radians(lat))
    venues = []
    for nm, primary, basic, brand, wikidata, conf, sources, vla, vlo in rows:
        if abs(vla - lat) * 111320.0 > radius_m or abs(vlo - lon) * kx > radius_m:
            continue
        d = math.hypot((vla - lat) * 111320.0, (vlo - lon) * kx)
        if d > radius_m or not keep_row(conf, sources):
            continue
        t = venue_type(primary, basic)
        if t:
            venues.append({"type": t, "distance_m": d, "brand": brand, "brand_wikidata": wikidata})
    if geography == "town_boundary":
        f = ls.boundary_facts(venues, area_km2)
        f.pop("hangouts_5min", None)
    else:
        f = ls.place_facts(venues, int(radius_m))
    f["independent_venues_1200m"] = ls.independent_venue_count(venues)
    return f


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--release", default=DEFAULT_RELEASE)
    ap.add_argument("--metros", nargs="*", default=None)
    a = ap.parse_args()
    try:
        import duckdb
    except ImportError:
        sys.exit("duckdb is required: pip install duckdb")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET threads=8;")
    src = f"s3://overturemaps-us-west-2/release/{a.release}/theme=places/type=place/*"
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(path).name.split("_metro_")[0]
        if a.metros and metro not in a.metros:
            continue
        rows = load(path)
        targets = [r for r in rows if r.get("success") and isinstance(r.get("score"), dict)]
        lats = [float(r["catalog"]["lat"]) for r in targets]
        lons = [float(r["catalog"]["lon"]) for r in targets]
        m = BBOX_MARGIN_DEG
        q = f"""select names.primary, taxonomy.primary, basic_category, brand.names.primary, brand.wikidata, confidence,
            list_transform(sources, lambda s: s.dataset), (bbox.ymin+bbox.ymax)/2, (bbox.xmin+bbox.xmax)/2
          from read_parquet('{src}', hive_partitioning=1)
          where bbox.xmin between ({min(lons) - m}) and ({max(lons) + m}) and bbox.ymin between ({min(lats) - m}) and ({max(lats) + m})
            and operating_status='open' and names.primary is not null and {_SQL_KEEP}"""
        box = con.execute(q).fetchall()
        for r in targets:
            s = r["score"]
            lat, lon = float(r["catalog"]["lat"]), float(r["catalog"]["lon"])
            geography, radius_m, area = measured_area(s)
            f = facts_for(box, lat, lon, geography, radius_m, area)
            f.update({"source": "overture", "release": a.release, "filters": FILTERS, "radius_m": round(radius_m),
                      "area_km2": round(area, 2), "geography": geography,
                      "area_method": "town_boundary_equal_area_circle" if geography == "town_boundary" else "pin_circle"})
            v2 = s.setdefault("local_scene_v2", {})
            v2["overture"] = f
        print(f"{metro}: {len(targets)} places, {len(box)} Overture rows read")
        if a.write:
            tmp = Path(path).with_name(Path(path).name + ".tmp")
            tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            os.replace(tmp, path)
    if not a.write:
        print("dry run: pass --write to save")


if __name__ == "__main__":
    main()
