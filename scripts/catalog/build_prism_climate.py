"""
Replace the temperature and precipitation in data/catalog_climate_profiles.jsonl with PRISM 1991-2020 normals.

Why: the NASA POWER values come from a ~55 km grid, so every place inside one box gets the same number (all of NYC had
8 distinct January values; Astoria 28.1F vs Hoboken 33.9F across one box edge). PRISM normals are 800 m (or 4 km) and
account for coastline and elevation. Data is free to reproduce and distribute (https://prism.oregonstate.edu/terms/);
credit: PRISM Climate Group, Oregon State University, https://prism.oregonstate.edu.

Only avg_temp_f and avg_precip_in change. Solar, humidity, wind and snow stay as they were (PRISM has none of them).
Places PRISM cannot answer (outside the 48 states, or over open water with no land within ~3 cells) keep the old values.

  PYTHONPATH=. python3 scripts/catalog/build_prism_climate.py              # 800 m, ~1.4 GB download, cached
  PYTHONPATH=. python3 scripts/catalog/build_prism_climate.py --res 4km    # ~60 MB, coarser
  PYTHONPATH=. python3 scripts/catalog/build_prism_climate.py --anchors    # print a few known cities and stop

Each monthly grid is downloaded once into data_cache/prism/ (PRISM blocks a file downloaded twice in 24 h, so the
zips are kept); delete that folder afterwards if you need the disk space.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

REPO = Path(__file__).resolve().parents[2]
PROFILES = REPO / "data" / "catalog_climate_profiles.jsonl"
CACHE = REPO / "data_cache" / "prism"
BASE = "https://data.prism.oregonstate.edu/normals/us/{res}/{var}/monthly/prism_{var}_us_{tag}_2020{mm:02d}_avg_30y.zip"
TAG = {"800m": "30s", "4km": "25m"}
MM_TO_IN = 0.0393701
SOURCE_LABEL = "prism_1991_2020_{res}"
SEARCH_CELLS = 3  # look this many cells out for land when a point lands on a no-data (water) cell

ANCHORS = {
    "Central Park NYC": (40.7829, -73.9654),
    "Astoria NYC": (40.7720, -73.9300),
    "Carroll Gardens NYC": (40.6800, -73.9994),
    "Hoboken NJ": (40.7440, -74.0320),
    "Chicago O'Hare": (41.9780, -87.9040),
    "Austin": (30.2672, -97.7431),
    "Los Angeles (LAX)": (33.9416, -118.4085),
    "Seattle (SeaTac)": (47.4502, -122.3088),
}


def _download(url: str, dest: Path, log=print) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    for attempt in range(1, 5):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            tmp.replace(dest)
            return
        except Exception as e:  # noqa: BLE001
            log(f"    download retry {attempt}/4: {str(e)[:80]}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not download {url}")


def _sample(zip_path: Path, points: List[Tuple[float, float]]) -> List[Optional[float]]:
    """Value of the grid at each (lat, lon); nearest land cell within SEARCH_CELLS when the point is on no-data."""
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    tif = next(n for n in _zip_names(zip_path) if n.endswith(".tif"))
    out: List[Optional[float]] = []
    with rasterio.open(f"/vsizip/{zip_path}/{tif}") as ds:
        nodata = ds.nodata if ds.nodata is not None else -9999.0
        for lat, lon in points:
            try:
                row, col = ds.index(lon, lat)
            except Exception:  # noqa: BLE001
                out.append(None)
                continue
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                out.append(None)
                continue
            r0, c0 = max(row - SEARCH_CELLS, 0), max(col - SEARCH_CELLS, 0)
            win = ds.read(1, window=Window(c0, r0, min(2 * SEARCH_CELLS + 1, ds.width - c0), min(2 * SEARCH_CELLS + 1, ds.height - r0)))
            valid = win != nodata
            if not valid.any():
                out.append(None)
                continue
            rr, cc = np.nonzero(valid)
            d = (rr + r0 - row) ** 2 + (cc + c0 - col) ** 2
            k = int(np.argmin(d))
            out.append(float(win[rr[k], cc[k]]))
    return out


def _zip_names(zip_path: Path) -> List[str]:
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        return z.namelist()


def sample_all(points: List[Tuple[float, float]], res: str, log=print) -> Dict[str, List[List[Optional[float]]]]:
    """{'tmean': [12 lists of per-point °C], 'ppt': [12 lists of per-point mm]}"""
    out: Dict[str, List[List[Optional[float]]]] = {"tmean": [], "ppt": []}
    for var in ("tmean", "ppt"):
        for mm in range(1, 13):
            url = BASE.format(res=res, var=var, tag=TAG[res], mm=mm)
            dest = CACHE / res / Path(url).name
            log(f"  {var} month {mm:02d}…")
            _download(url, dest, log)
            out[var].append(_sample(dest, points))
    return out


def build_profile(old: Optional[dict], tmean_c: List[Optional[float]], ppt_mm: List[Optional[float]], res: str) -> Optional[dict]:
    """New climate dict, or None when PRISM had no answer for this point (caller keeps the old one)."""
    if any(v is None for v in tmean_c) or any(v is None for v in ppt_mm):
        return None
    old_months = {m["month"]: m for m in (old or {}).get("months", [])}
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months = []
    for i in range(12):
        m = dict(old_months.get(i + 1, {"month": i + 1, "month_name": names[i]}))
        m["avg_temp_f"] = round(tmean_c[i] * 9 / 5 + 32, 1)
        m["avg_precip_in"] = round(ppt_mm[i] * MM_TO_IN, 2)
        months.append(m)
    new = dict(old or {})
    new["months"] = months
    new["temp_precip_source"] = SOURCE_LABEL.format(res=res)
    new["normals_period"] = "1991-2020"
    return new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", choices=["800m", "4km"], default="800m")
    ap.add_argument("--anchors", action="store_true", help="print temperatures for a few known cities and stop")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; do not write")
    a = ap.parse_args()

    if a.anchors:
        names = list(ANCHORS)
        s = sample_all([ANCHORS[n] for n in names], a.res)
        print(f"PRISM 1991-2020 {a.res}: January / July mean (°F), July minus January")
        for i, n in enumerate(names):
            jan = s["tmean"][0][i] * 9 / 5 + 32
            jul = s["tmean"][6][i] * 9 / 5 + 32
            print(f"  {n:22s} Jan {jan:5.1f}  Jul {jul:5.1f}  swing {jul - jan:4.1f}")
        return 0

    rows = [json.loads(l) for l in PROFILES.read_text().splitlines() if l.strip()]
    pts = [(float(r["lat"]), float(r["lon"])) for r in rows]
    s = sample_all(pts, a.res)

    changed = kept = 0
    biggest: List[Tuple[float, str]] = []
    for i, r in enumerate(rows):
        t = [s["tmean"][m][i] for m in range(12)]
        p = [s["ppt"][m][i] for m in range(12)]
        new = build_profile(r.get("climate"), t, p, a.res)
        if new is None:
            kept += 1
            continue
        old_jan = next((m["avg_temp_f"] for m in (r.get("climate") or {}).get("months", []) if m["month"] == 1), None)
        if old_jan is not None:
            biggest.append((abs(new["months"][0]["avg_temp_f"] - old_jan), f"{r['name']} ({r['source']})"))
        r["climate"] = new
        changed += 1
    biggest.sort(reverse=True)
    print(f"{changed} places updated from PRISM, {kept} kept their old values (outside PRISM coverage)")
    for d, n in biggest[:5]:
        print(f"  biggest January change: {n}  {d:.1f}°F")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    tmp = PROFILES.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    tmp.replace(PROFILES)
    print(f"wrote {PROFILES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
