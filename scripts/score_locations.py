#!/usr/bin/env python3
"""
Score each location in data/locations.csv via the API and print location,total_score.
Run from project root with backend at http://localhost:8000:
  PYTHONPATH=. python3 scripts/score_locations.py
  PYTHONPATH=. python3 scripts/score_locations.py > scores.csv
"""
import csv
import os
import sys
import time

# Project root for imports and data path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    import requests

    locations_path = os.path.join(ROOT, "data", "locations.csv")
    base_url = os.environ.get("HOMEFIT_API_URL", "http://localhost:8000")
    timeout = int(os.environ.get("HOMEFIT_TIMEOUT", "120"))
    delay = float(os.environ.get("HOMEFIT_DELAY", "1.0"))

    locations = []
    with open(locations_path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip() or row[0].strip().lower() == "location":
                continue
            locations.append(row[0].strip())

    print("location,total_score", flush=True)
    for i, loc in enumerate(locations):
        try:
            r = requests.get(
                f"{base_url}/score",
                params={"location": loc},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            total = data.get("total_score")
            if total is None:
                total = ""
            else:
                total = round(float(total), 1)
            print(f'"{loc}",{total}', flush=True)
        except Exception as e:
            print(f'"{loc}",error:{e}', flush=True)
        if i < len(locations) - 1 and delay > 0:
            time.sleep(delay)


if __name__ == "__main__":
    main()
