"""
Error handling and fallback mechanisms for HomeFit API
Provides graceful degradation when external APIs fail
"""

import os
import logging
import time
import asyncio
from typing import Any, Optional, Dict, Tuple, Callable
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HomeFitError(Exception):
    """Base exception for HomeFit errors."""
    pass


class APIError(HomeFitError):
    """Exception for API-related errors."""
    def __init__(self, message: str, api_name: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.api_name = api_name
        self.status_code = status_code


class DataUnavailableError(HomeFitError):
    """Exception for when required data is unavailable."""
    pass


def check_api_credentials() -> Dict[str, bool]:
    """
    Check which API credentials are available.
    
    Returns:
        Dict mapping API names to availability status
    """
    credentials = {
        "census": bool(os.getenv("CENSUS_API_KEY")),
        "schools": bool(os.getenv("SCHOOLDIGGER_APPID") and os.getenv("SCHOOLDIGGER_APPKEY")),
        "transit": True,  # Transitland doesn't require credentials
        "osm": True,      # OSM doesn't require credentials
        "geocoding": True,  # Nominatim doesn't require credentials
    }
    
    return credentials


def with_fallback(fallback_value: Any, log_error: bool = True):
    """
    Decorator to provide fallback values when functions fail.
    
    Args:
        fallback_value: Value to return if function fails
        log_error: Whether to log the error
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.warning(f"Function {func.__name__} failed: {e}. Using fallback.")
                return fallback_value
        return wrapper
    return decorator


def with_retry(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry failed API calls.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying...")
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            raise last_exception
        return wrapper
    return decorator


def safe_api_call(api_name: str, required: bool = True):
    """
    Decorator for safe API calls with proper error handling.
    
    Args:
        api_name: Name of the API being called
        required: Whether this API call is required for the pillar
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except APIError as e:
                logger.error(f"API error in {api_name}: {e}")
                if required:
                    raise DataUnavailableError(f"Required API {api_name} is unavailable")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in {api_name}: {e}")
                if required:
                    raise DataUnavailableError(f"Unexpected error in {api_name}")
                return None
        return wrapper
    return decorator


def get_fallback_score(pillar_name: str, reason: str = "API unavailable") -> Tuple[float, Dict]:
    """
    Get a fallback score when data is unavailable.
    
    Args:
        pillar_name: Name of the pillar
        reason: Reason for fallback
    
    Returns:
        Tuple of (score, breakdown)
    """
    fallback_scores = {
        "active_outdoors": 30,  # Conservative score for outdoor access
        "neighborhood_beauty": 40,  # Moderate score for beauty
        "neighborhood_amenities": 25,  # Low score for amenities
        "air_travel_access": 20,  # Low score for air travel
        "public_transit_access": 15,  # Low score for transit
        "healthcare_access": 35,  # Moderate score for healthcare
        "quality_education": 50,  # Neutral score for education
        "housing_value": 45,  # Moderate score for housing
    }
    
    score = fallback_scores.get(pillar_name, 30)
    
    breakdown = {
        "score": score,
        "breakdown": {
            "fallback": score,
            "reason": reason
        },
        "summary": {
            "fallback_used": True,
            "reason": reason,
            "note": f"Data unavailable for {pillar_name} pillar"
        }
    }
    
    logger.warning(f"Using fallback score {score} for {pillar_name}: {reason}")
    return score, breakdown


def validate_required_data(data: Any, data_name: str) -> bool:
    """
    Validate that required data is present and valid.
    
    Args:
        data: Data to validate
        data_name: Name of the data for error messages
    
    Returns:
        True if data is valid, False otherwise
    """
    if data is None:
        logger.warning(f"Required data {data_name} is None")
        return False
    
    if isinstance(data, dict) and not data:
        logger.warning(f"Required data {data_name} is empty dict")
        return False
    
    if isinstance(data, list) and not data:
        logger.warning(f"Required data {data_name} is empty list")
        return False
    
    return True


def handle_api_timeout(timeout_seconds: int = 30):
    """
    Decorator to handle API timeouts gracefully.
    For async functions, uses asyncio.wait_for for proper timeout handling.
    For sync functions, relies on the underlying HTTP library timeout.
    
    Args:
        timeout_seconds: Timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"Function {func.__name__} timed out after {timeout_seconds}s")
                raise APIError(f"Request timed out after {timeout_seconds} seconds", func.__name__, 408)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    logger.warning(f"Function {func.__name__} timed out")
                    raise APIError(f"Request timed out after {timeout_seconds} seconds", func.__name__, 408)
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
