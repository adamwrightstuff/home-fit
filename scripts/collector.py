#!/usr/bin/env python3
"""
HomeFit API Collector

Reads locations from data/locations.csv, calls the HomeFit API for each unprocessed
location, and saves raw JSON responses to data/results.csv.

Idempotent: skips locations already in results.csv.
Restartable: safe to interrupt and resume.
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
LOCATIONS_CSV = DATA_DIR / "locations.csv"
RESULTS_CSV = DATA_DIR / "results.csv"

# API configuration from environment variables
HOMEFIT_BASE_URL = os.getenv("HOMEFIT_BASE_URL", "").strip()
HOMEFIT_API_KEY = os.getenv("HOMEFIT_API_KEY", None)

# Rate limiting and retry configuration
# Conservative delay: wait for full response + additional delay to avoid overwhelming external APIs (OSM, Census, etc.)
MIN_DELAY_AFTER_RESPONSE_SECONDS = 5.0  # Minimum delay after receiving a response
ADAPTIVE_DELAY_FACTOR = 0.1  # Add 10% of response time as additional delay
INITIAL_DELAY_SECONDS = 10.0  # Initial backoff delay before first retry
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0  # Exponential backoff multiplier
REQUEST_TIMEOUT_SECONDS = 300  # 5 minutes for API calls


def call_homefit_api(location: str) -> Optional[Dict]:
    """
    Call the HomeFit API scoring endpoint for a given location.
    
    Args:
        location: Location string (e.g., "Carroll Gardens Brooklyn NY")
    
    Returns:
        JSON response as dict, or None if request failed after retries
    """
    # Ensure base URL doesn't have trailing slash
    base_url = HOMEFIT_BASE_URL.rstrip('/')
    url = f"{base_url}/score"
    
    if not base_url:
        logger.error("HOMEFIT_BASE_URL is empty - this should have been caught earlier")
        return None
    params = {
        "location": location,
        "enable_schools": "false"  # Disable schools to preserve quota
    }
    
    headers = {}
    if HOMEFIT_API_KEY:
        headers["Authorization"] = f"Bearer {HOMEFIT_API_KEY}"
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Calling API for '{location}' (attempt {attempt + 1}/{MAX_RETRIES})")
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"API returned non-200 status {response.status_code} for '{location}': "
                    f"{response.text[:200]}"
                )
                # Don't retry on client errors (4xx), but retry on server errors (5xx)
                if 400 <= response.status_code < 500:
                    return None
                # For 5xx errors, continue to retry
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for '{location}' (attempt {attempt + 1}/{MAX_RETRIES})")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error for '{location}' (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
        
        # Exponential backoff before retry (except on last attempt)
        if attempt < MAX_RETRIES - 1:
            backoff_delay = INITIAL_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.info(f"Retrying in {backoff_delay:.1f} seconds...")
            time.sleep(backoff_delay)
    
    logger.error(f"Failed to get response for '{location}' after {MAX_RETRIES} attempts")
    return None


def load_processed_locations() -> Set[str]:
    """
    Load set of locations that have already been processed.
    
    Returns:
        Set of location strings that are already in results.csv
    """
    if not RESULTS_CSV.exists():
        return set()
    
    processed = set()
    try:
        with open(RESULTS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if 'location' not in reader.fieldnames:
                logger.warning("results.csv missing 'location' column, treating as empty")
                return set()
            
            for row in reader:
                location = row.get('location', '').strip()
                if location:
                    processed.add(location)
        
        logger.info(f"Loaded {len(processed)} already-processed locations from results.csv")
    except Exception as e:
        logger.error(f"Error reading results.csv: {e}")
        raise
    
    return processed


def load_locations_to_process() -> list[str]:
    """
    Load locations from locations.csv that need to be processed.
    
    Returns:
        List of location strings from locations.csv
    """
    if not LOCATIONS_CSV.exists():
        logger.error(f"locations.csv not found at {LOCATIONS_CSV}")
        sys.exit(1)
    
    locations = []
    try:
        with open(LOCATIONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if 'location' not in reader.fieldnames:
                logger.error("locations.csv must have a 'location' column")
                sys.exit(1)
            
            for row in reader:
                location = row.get('location', '').strip()
                if location:
                    locations.append(location)
        
        logger.info(f"Loaded {len(locations)} locations from locations.csv")
    except Exception as e:
        logger.error(f"Error reading locations.csv: {e}")
        raise
    
    return locations


def ensure_results_csv_header():
    """
    Ensure results.csv exists with the correct header row.
    Creates the file with header if it doesn't exist.
    """
    if RESULTS_CSV.exists():
        return
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create file with header
    with open(RESULTS_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['location', 'timestamp', 'raw_json'])
    
    logger.info(f"Created results.csv with header at {RESULTS_CSV}")


def append_result(location: str, raw_json: Dict):
    """
    Append a result row to results.csv.
    
    Args:
        location: Location string
        raw_json: JSON response as dict
    """
    timestamp = datetime.utcnow().isoformat() + 'Z'
    json_str = json.dumps(raw_json)
    
    try:
        with open(RESULTS_CSV, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            # CSV writer will properly escape the JSON string
            writer.writerow([location, timestamp, json_str])
        
        logger.debug(f"Appended result for '{location}'")
    except Exception as e:
        logger.error(f"Error appending result for '{location}': {e}")
        raise


def main():
    """Main collector function."""
    try:
        # Validate that base URL is set (fail early with clear error)
        if not HOMEFIT_BASE_URL:
            logger.error("=" * 80)
            logger.error("ERROR: HOMEFIT_BASE_URL environment variable is not set!")
            logger.error("=" * 80)
            logger.error("To fix this:")
            logger.error("1. Go to your GitHub repo → Settings → Secrets and variables → Actions")
            logger.error("2. Add a secret named 'HOMEFIT_BASE_URL' with your API URL")
            logger.error("   Example: 'https://your-api.example.com' or 'http://localhost:8000'")
            logger.error("3. If using an API key, also add 'HOMEFIT_API_KEY' secret")
            logger.error("=" * 80)
            sys.exit(1)
        
        # Ensure results.csv exists with header
        ensure_results_csv_header()
        
        # Load locations and determine what needs processing
        all_locations = load_locations_to_process()
        processed_locations = load_processed_locations()
        
        # Filter to unprocessed locations
        unprocessed = [loc for loc in all_locations if loc not in processed_locations]
        
        total_count = len(all_locations)
        already_processed_count = len(processed_locations)
        to_process_count = len(unprocessed)
        
        logger.info("=" * 80)
        logger.info("HomeFit API Collector")
        logger.info("=" * 80)
        logger.info(f"Total locations: {total_count}")
        logger.info(f"Already processed: {already_processed_count}")
        logger.info(f"To process this run: {to_process_count}")
        logger.info(f"API base URL: {HOMEFIT_BASE_URL}")
        if HOMEFIT_API_KEY:
            logger.info(f"API key: {'*' * 20} (configured)")
        else:
            logger.info("API key: (not set)")
        logger.info("=" * 80)
        
        if to_process_count == 0:
            logger.info("All locations already processed. Nothing to do.")
            return
        
        # Process each unprocessed location
        successful = 0
        failed = 0
        
        for i, location in enumerate(unprocessed, 1):
            logger.info(f"\n[{i}/{to_process_count}] Processing: {location}")
            
            try:
                # Track time to make adaptive delay
                start_time = time.time()
                response = call_homefit_api(location)
                response_time = time.time() - start_time
                
                if response is not None:
                    append_result(location, response)
                    successful += 1
                    logger.info(f"✓ Successfully processed '{location}' (took {response_time:.1f}s)")
                else:
                    failed += 1
                    logger.error(f"✗ Failed to process '{location}'")
                
                # Conservative rate limiting: wait for full response, then add delay
                # This ensures we don't overwhelm external APIs (OSM, Census, etc.) that the HomeFit API calls
                if i < to_process_count:
                    # Adaptive delay: minimum delay + percentage of response time
                    adaptive_delay = MIN_DELAY_AFTER_RESPONSE_SECONDS + (response_time * ADAPTIVE_DELAY_FACTOR)
                    logger.info(f"Waiting {adaptive_delay:.1f}s before next request...")
                    time.sleep(adaptive_delay)
                    
            except KeyboardInterrupt:
                logger.info("\n\nInterrupted by user. Exiting cleanly...")
                logger.info(f"Processed {successful} locations successfully, {failed} failed")
                logger.info("Results saved. You can rerun the script to continue.")
                sys.exit(0)
            except Exception as e:
                failed += 1
                logger.error(f"Unexpected error processing '{location}': {e}", exc_info=True)
                # Continue to next location
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Successfully processed: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total processed this run: {successful + failed}")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user. Exiting cleanly...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
