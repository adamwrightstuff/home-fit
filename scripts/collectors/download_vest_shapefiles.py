"""
Download VEST precinct data from Harvard Dataverse and build election lookup JSON.

Sources:
  2020 shapefiles: doi:10.7910/DVN/K7760H  (per-state zips with geometry + votes)
  2024 results:    doi:10.7910/DVN/NYTPDU  (per-state CSV, votes only)

Usage:
    # Download + build for NYC metro states
    PYTHONPATH=. python3 scripts/collectors/download_vest_shapefiles.py --states NY NJ CT --build

    # Download only (inspect before building)
    PYTHONPATH=. python3 scripts/collectors/download_vest_shapefiles.py --states CA

    # Build from already-downloaded files
    PYTHONPATH=. python3 scripts/collectors/download_vest_shapefiles.py --states NY --build

Downloaded files land in --download-dir (default: /tmp/vest_shapefiles).
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILD_SCRIPT = _REPO_ROOT / "scripts" / "collectors" / "build_election_lookup.py"

DATAVERSE_API = "https://dataverse.harvard.edu/api"

# Pre-resolved file IDs from Harvard Dataverse (avoids runtime search API calls)
# 2020 shapefile zips: doi:10.7910/DVN/K7760H
_SHPZIP_2020: dict[str, int] = {
    "CT": 4986646,   # ct_2020.zip  (2 MB)
    "NJ": 12070367,  # nj_2020.zip  (7 MB)
    "NY": 5259468,   # ny_2020.zip  (24 MB)
    "CA": 5206371,   # ca_2020.zip
}

# 2024 per-state CSV/tab: doi:10.7910/DVN/NYTPDU
_CSV_2024: dict[str, tuple[int, str]] = {
    "CT": (13731178, "2024-ct-precinct-general.tab"),
    "NJ": (13731174, "2024-nj-precinct-general.tab"),
    "NY": (13731135, "2024-ny-precinct-general.csv"),
    "CA": (13731130, "2024-ca-precinct-general.csv"),
}


_UA = "Mozilla/5.0 (compatible; homefit-data-fetcher/1.0)"


def _download(url: str, dest: Path, label: str) -> None:
    print(f"  Downloading {label}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                buf = resp.read(1 << 16)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                if total:
                    pct = downloaded * 100 // total
                    mb = downloaded // 1024 // 1024
                    print(f"\r    {mb} MB / {total // 1024 // 1024} MB ({pct}%)", end="", flush=True)
    print()


def _dataverse_file_url(file_id: int) -> str:
    return f"{DATAVERSE_API}/access/datafile/{file_id}"


def _find_shp(directory: Path) -> Path | None:
    shps = list(directory.rglob("*.shp"))
    if not shps:
        return None
    shps.sort(key=lambda p: len(p.parts))
    return shps[0]


def fetch_2020_shapefile(state: str, dl_dir: Path) -> Path | None:
    state = state.upper()
    extract_dir = dl_dir / f"{state.lower()}_2020_shp"
    cached = _find_shp(extract_dir)
    if cached:
        print(f"  [cached 2020 shp] {cached}")
        return cached

    file_id = _SHPZIP_2020.get(state)
    if not file_id:
        print(f"  ERROR: No 2020 shapefile file ID registered for {state}.")
        print(f"  Look up the file ID at: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/K7760H")
        return None

    zip_dest = dl_dir / f"{state.lower()}_2020.zip"
    if not zip_dest.exists():
        _download(_dataverse_file_url(file_id), zip_dest, f"{state} 2020 shapefile zip")
    else:
        print(f"  [cached zip] {zip_dest}")

    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Extracting → {extract_dir}")
    with zipfile.ZipFile(zip_dest) as zf:
        zf.extractall(extract_dir)

    shp = _find_shp(extract_dir)
    if not shp:
        print(f"  ERROR: No .shp found after extracting {zip_dest}")
    return shp


def fetch_2024_csv(state: str, dl_dir: Path) -> Path | None:
    state = state.upper()
    entry = _CSV_2024.get(state)
    if not entry:
        print(f"  No 2024 CSV file ID registered for {state} — skipping 2024 data.")
        return None

    file_id, filename = entry
    dest = dl_dir / filename
    if dest.exists():
        print(f"  [cached 2024 csv] {dest}")
        return dest

    _download(_dataverse_file_url(file_id), dest, f"{state} 2024 precinct CSV ({filename})")
    return dest


def build_lookup(state: str, shp_2020: Path, csv_2024: Path | None) -> bool:
    cmd = [
        sys.executable, str(_BUILD_SCRIPT),
        "--state", state.upper(),
        "--shp2020", str(shp_2020),
    ]
    if csv_2024:
        cmd += ["--csv2024", str(csv_2024)]

    print(f"\n--- Building lookup for {state} ---")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Download VEST data and build precinct JSON")
    parser.add_argument("--states", nargs="+", required=True, help="State abbreviations (e.g. NY NJ CT)")
    parser.add_argument("--build", action="store_true", help="Run build_election_lookup.py after downloading")
    parser.add_argument("--download-dir", default="/tmp/vest_shapefiles", help="Directory for downloaded files")
    args = parser.parse_args()

    dl_dir = Path(args.download_dir)
    dl_dir.mkdir(parents=True, exist_ok=True)
    print(f"Download directory: {dl_dir}\n")

    ok, failed = [], []
    for state in [s.upper() for s in args.states]:
        print(f"=== {state} ===")
        shp_20 = fetch_2020_shapefile(state, dl_dir)
        if not shp_20:
            failed.append(state)
            continue
        csv_24 = fetch_2024_csv(state, dl_dir)
        if args.build:
            if build_lookup(state, shp_20, csv_24):
                ok.append(state)
            else:
                failed.append(state)
        else:
            print(f"  {state} ready. Run with --build to generate data/election/{state.lower()}_precincts.json")
            ok.append(state)
        time.sleep(0.3)

    print(f"\n=== Done ===")
    if ok:
        print(f"  OK: {', '.join(ok)}")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
