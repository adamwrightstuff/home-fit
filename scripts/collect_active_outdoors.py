#!/usr/bin/env python3
"""
Active Outdoors pillar collector.

Reads locations from data/active_outdoors_locations.csv, calls the HomeFit API
with only=active_outdoors and diagnostics=true for each location, and writes:
  - analysis/active_outdoors_scores_YYYYMMDD.jsonl (full response per line)
  - analysis/active_outdoors_summary_YYYYMMDD.csv (location, score, components, category, expected_score_range)

Default API: https://home-fit-production.up.railway.app (override with HOMEFIT_BASE_URL for local).

Uses same env and rate-limiting pattern as scripts/collector.py.
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"
LOCATIONS_CSV = DATA_DIR / "active_outdoors_locations.csv"

HOMEFIT_BASE_URL = (
    os.getenv("HOMEFIT_BASE_URL", "https://home-fit-production.up.railway.app")
    or "https://home-fit-production.up.railway.app"
).strip()
HOMEFIT_API_KEY = os.getenv("HOMEFIT_API_KEY", None)

MIN_DELAY_AFTER_RESPONSE_SECONDS = 5.0
ADAPTIVE_DELAY_FACTOR = 0.1
INITIAL_DELAY_SECONDS = 10.0
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0
REQUEST_TIMEOUT_SECONDS = 300


def call_active_outdoors_api(location: str) -> Optional[Dict]:
    """Call /score with only=active_outdoors and diagnostics=true."""
    base_url = HOMEFIT_BASE_URL.rstrip("/")
    url = f"{base_url}/score"
    if not base_url:
        logger.error("HOMEFIT_BASE_URL is empty")
        return None
    params = {
        "location": location,
        "only": "active_outdoors",
        "diagnostics": "true",
        "enable_schools": "false",
    }
    headers = {}
    if HOMEFIT_API_KEY:
        headers["Authorization"] = f"Bearer {HOMEFIT_API_KEY}"

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"API returned {response.status_code} for '{location}': {response.text[:200]}"
            )
            if 400 <= response.status_code < 500:
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for '{location}' (attempt {attempt + 1}/{MAX_RETRIES})")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error for '{location}' (attempt {attempt + 1}/{MAX_RETRIES}): {e}")

        if attempt < MAX_RETRIES - 1:
            backoff = INITIAL_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.info(f"Retrying in {backoff:.1f}s...")
            time.sleep(backoff)

    logger.error(f"Failed for '{location}' after {MAX_RETRIES} attempts")
    return None


def load_locations() -> List[Dict[str, str]]:
    """Load rows from active_outdoors_locations.csv (location, city, state, category, expected_score_range)."""
    if not LOCATIONS_CSV.exists():
        logger.error(f"Locations file not found: {LOCATIONS_CSV}")
        sys.exit(1)
    rows = []
    with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "location" not in (reader.fieldnames or []):
            logger.error("CSV must have 'location' column")
            sys.exit(1)
        for row in reader:
            loc = (row.get("location") or "").strip()
            if loc:
                rows.append({
                    "location": loc,
                    "city": (row.get("city") or "").strip(),
                    "state": (row.get("state") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "expected_score_range": (row.get("expected_score_range") or "").strip(),
                })
    logger.info(f"Loaded {len(rows)} locations from {LOCATIONS_CSV}")
    return rows


def extract_ao_summary(response: Dict) -> Dict:
    """Extract active_outdoors score and breakdown from API response."""
    pillars = response.get("livability_pillars") or response.get("pillars") or {}
    ao = pillars.get("active_outdoors") or {}
    score = ao.get("score")
    breakdown = ao.get("breakdown") or {}
    return {
        "score": score if score is not None else "",
        "daily_urban_outdoors": breakdown.get("daily_urban_outdoors", ""),
        "wild_adventure": breakdown.get("wild_adventure", ""),
        "waterfront_lifestyle": breakdown.get("waterfront_lifestyle", ""),
    }


def main() -> None:
    if not HOMEFIT_BASE_URL:
        logger.error("HOMEFIT_BASE_URL is empty.")
        logger.error("Set it in GitHub Actions secrets or export HOMEFIT_BASE_URL for a different API.")
        sys.exit(1)

    locations = load_locations()
    if not locations:
        logger.error("No locations to process.")
        sys.exit(1)

    date_suffix = datetime.utcnow().strftime("%Y%m%d")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = ANALYSIS_DIR / f"active_outdoors_scores_{date_suffix}.jsonl"
    summary_path = ANALYSIS_DIR / f"active_outdoors_summary_{date_suffix}.csv"

    logger.info("=" * 80)
    logger.info("Active Outdoors collector (scores + details)")
    logger.info("=" * 80)
    logger.info(f"Locations: {len(locations)}")
    logger.info(f"API base: {HOMEFIT_BASE_URL}")
    logger.info(f"JSONL: {jsonl_path}")
    logger.info(f"Summary CSV: {summary_path}")
    logger.info("=" * 80)

    summary_header = [
        "location", "city", "state", "category", "expected_score_range",
        "score", "daily_urban_outdoors", "wild_adventure", "waterfront_lifestyle",
    ]
    summary_file = open(summary_path, "w", encoding="utf-8", newline="")
    summary_writer = csv.DictWriter(summary_file, fieldnames=summary_header)
    summary_writer.writeheader()

    successful = 0
    failed = 0

    try:
        with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
            for i, row in enumerate(locations, 1):
                loc = row["location"]
                logger.info(f"[{i}/{len(locations)}] {loc}")

                start = time.time()
                response = call_active_outdoors_api(loc)
                elapsed = time.time() - start

                if response is None:
                    failed += 1
                    summary_writer.writerow({
                        "location": loc,
                        "city": row["city"],
                        "state": row["state"],
                        "category": row["category"],
                        "expected_score_range": row["expected_score_range"],
                        "score": "",
                        "daily_urban_outdoors": "",
                        "wild_adventure": "",
                        "waterfront_lifestyle": "",
                    })
                    continue

                jsonl_file.write(json.dumps({"location": loc, "response": response}) + "\n")
                ao = extract_ao_summary(response)
                summary_writer.writerow({
                    "location": loc,
                    "city": row["city"],
                    "state": row["state"],
                    "category": row["category"],
                    "expected_score_range": row["expected_score_range"],
                    "score": ao.get("score", ""),
                    "daily_urban_outdoors": ao.get("daily_urban_outdoors", ""),
                    "wild_adventure": ao.get("wild_adventure", ""),
                    "waterfront_lifestyle": ao.get("waterfront_lifestyle", ""),
                })
                summary_file.flush()
                successful += 1
                logger.info(f"  score={ao.get('score', '')} (took {elapsed:.1f}s)")

                if i < len(locations):
                    delay = MIN_DELAY_AFTER_RESPONSE_SECONDS + (elapsed * ADAPTIVE_DELAY_FACTOR)
                    logger.info(f"  waiting {delay:.1f}s...")
                    time.sleep(delay)
    except KeyboardInterrupt:
        logger.info("Interrupted. Results saved so far.")
    finally:
        summary_file.close()

    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Success: {successful}, Failed: {failed}")
    logger.info(f"JSONL: {jsonl_path}")
    logger.info(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
