#!/usr/bin/env python3
"""
Status Signal collector: reads data/locations.csv, calls the API with only the four
Status Signal pillars (housing_value, social_fabric, economic_security, neighborhood_amenities),
and appends raw JSON to data/results.csv.

Idempotent: skips locations already in results.csv. Restartable.

Default API: https://home-fit-production.up.railway.app (override with HOMEFIT_BASE_URL for local).

Usage (from project root):
  python3 scripts/collect_status_signal.py
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
LOCATIONS_CSV = DATA_DIR / "locations.csv"
RESULTS_CSV = DATA_DIR / "results.csv"

HOMEFIT_BASE_URL = (os.getenv("HOMEFIT_BASE_URL", "https://home-fit-production.up.railway.app") or "https://home-fit-production.up.railway.app").strip()
HOMEFIT_API_KEY = os.getenv("HOMEFIT_API_KEY", None)

MIN_DELAY_AFTER_RESPONSE_SECONDS = 5.0
ADAPTIVE_DELAY_FACTOR = 0.1
INITIAL_DELAY_SECONDS = 10.0
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0
REQUEST_TIMEOUT_SECONDS = 300

ONLY_PILLARS = "housing_value,social_fabric,economic_security,neighborhood_amenities"


def call_api(location: str) -> Optional[Dict]:
    base_url = HOMEFIT_BASE_URL.rstrip('/')
    url = f"{base_url}/score"
    if not base_url:
        logger.error("HOMEFIT_BASE_URL is empty")
        return None
    params = {
        "location": location,
        "only": ONLY_PILLARS,
        "enable_schools": "false",
    }
    headers = {}
    if HOMEFIT_API_KEY:
        headers["Authorization"] = f"Bearer {HOMEFIT_API_KEY}"

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"API {response.status_code} for '{location}': {response.text[:200]}")
            if 400 <= response.status_code < 500:
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for '{location}' (attempt {attempt + 1}/{MAX_RETRIES})")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error for '{location}': {e}")
        if attempt < MAX_RETRIES - 1:
            delay = INITIAL_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.info(f"Retrying in {delay:.1f}s...")
            time.sleep(delay)
    logger.error(f"Failed for '{location}' after {MAX_RETRIES} attempts")
    return None


def load_processed() -> Set[str]:
    if not RESULTS_CSV.exists():
        return set()
    processed = set()
    with open(RESULTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if 'location' not in (reader.fieldnames or []):
            return set()
        for row in reader:
            loc = row.get('location', '').strip()
            if loc:
                processed.add(loc)
    logger.info(f"Loaded {len(processed)} already in results.csv")
    return processed


def load_locations() -> list[str]:
    if not LOCATIONS_CSV.exists():
        logger.error(f"Not found: {LOCATIONS_CSV}")
        sys.exit(1)
    locations = []
    with open(LOCATIONS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if 'location' not in (reader.fieldnames or []):
            logger.error("locations.csv must have a 'location' column")
            sys.exit(1)
        for row in reader:
            loc = row.get('location', '').strip()
            if loc:
                locations.append(loc)
    logger.info(f"Loaded {len(locations)} from locations.csv")
    return locations


def ensure_header():
    if RESULTS_CSV.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_CSV, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow(['location', 'timestamp', 'raw_json'])
    logger.info(f"Created {RESULTS_CSV}")


def append_result(location: str, raw_json: Dict):
    with open(RESULTS_CSV, 'a', encoding='utf-8', newline='') as f:
        csv.writer(f, quoting=csv.QUOTE_MINIMAL).writerow([
            location,
            datetime.utcnow().isoformat() + 'Z',
            json.dumps(raw_json),
        ])


def main():
    if not HOMEFIT_BASE_URL:
        logger.error("Set HOMEFIT_BASE_URL (e.g. export HOMEFIT_BASE_URL=http://localhost:8000)")
        sys.exit(1)
    ensure_header()
    all_locs = load_locations()
    processed = load_processed()
    unprocessed = [loc for loc in all_locs if loc not in processed]
    to_process = len(unprocessed)
    if to_process == 0:
        logger.info("All locations already in results.csv. Done.")
        return
    logger.info("Status Signal collector (4 pillars only)")
    logger.info(f"To process: {to_process} (skipping {len(processed)} already in results.csv)")
    successful = failed = 0
    for i, location in enumerate(unprocessed, 1):
        logger.info(f"[{i}/{to_process}] {location}")
        try:
            start = time.time()
            response = call_api(location)
            elapsed = time.time() - start
            if response is not None:
                append_result(location, response)
                successful += 1
                logger.info(f"  OK ({elapsed:.1f}s)")
            else:
                failed += 1
                logger.error("  Failed")
            if i < to_process:
                delay = MIN_DELAY_AFTER_RESPONSE_SECONDS + (elapsed * ADAPTIVE_DELAY_FACTOR)
                logger.info(f"  Waiting {delay:.1f}s...")
                time.sleep(delay)
        except KeyboardInterrupt:
            logger.info("Interrupted. Rerun to resume.")
            sys.exit(0)
        except Exception as e:
            failed += 1
            logger.error(f"  Error: {e}")
    logger.info(f"Done. OK: {successful}, Failed: {failed}")


if __name__ == "__main__":
    main()
