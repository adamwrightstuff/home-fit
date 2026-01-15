"""
Centralized Retry Configuration for HomeFit API
Provides configurable retry profiles for different query types across all pillars.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Callable
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class RetryProfile(Enum):
    """Retry behavior profiles for different query types."""
    CRITICAL = "critical"      # Critical queries (parks, transit) - retry all attempts
    STANDARD = "standard"       # Standard queries (amenities, housing) - moderate retries
    NON_CRITICAL = "non_critical"  # Non-critical queries (Phase 2/3 beauty metrics) - fail fast
    CENSUS = "census"           # Census API specific profile
    SCHOOLS = "schools"         # SchoolDigger API specific profile
    HEALTHCARE = "healthcare"   # Healthcare queries - more retries, don't fail fast


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 4
    base_wait: float = 1.0
    fail_fast: bool = False  # If True, give up after 2 attempts on rate limit
    max_wait: float = 10.0  # Maximum wait time between retries
    exponential_backoff: bool = True
    retry_on_timeout: bool = True
    retry_on_429: bool = True  # Retry on rate limits
    
    def __post_init__(self):
        """Validate configuration."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_wait < 0:
            raise ValueError("base_wait must be >= 0")
        if self.max_wait < self.base_wait:
            raise ValueError("max_wait must be >= base_wait")


# Retry profiles for different query types
RETRY_PROFILES: Dict[RetryProfile, RetryConfig] = {
    RetryProfile.CRITICAL: RetryConfig(
        max_attempts=3,  # Reduced from 6 to 3 for faster failure (caching handles retries)
        base_wait=1.0,  # Reduced from 2.0
        fail_fast=True,  # Fail fast on rate limits to avoid 8+ minute waits
        max_wait=10.0,  # Reduced from 30.0 to prevent excessive delays
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
    RetryProfile.STANDARD: RetryConfig(
        max_attempts=3,
        base_wait=1.0,
        fail_fast=False,
        max_wait=10.0,
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
    RetryProfile.NON_CRITICAL: RetryConfig(
        max_attempts=2,
        base_wait=1.0,
        fail_fast=True,  # Non-critical queries should fail fast to avoid hangs
        max_wait=10.0,
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
    RetryProfile.CENSUS: RetryConfig(
        max_attempts=3,
        base_wait=1.0,
        fail_fast=False,
        max_wait=5.0,
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
    RetryProfile.SCHOOLS: RetryConfig(
        max_attempts=3,
        base_wait=1.0,
        fail_fast=False,
        max_wait=5.0,
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
    RetryProfile.HEALTHCARE: RetryConfig(
        max_attempts=5,  # More attempts than CRITICAL
        base_wait=2.0,  # Longer base wait
        fail_fast=False,  # Don't fail fast on rate limits - keep retrying
        max_wait=20.0,  # Longer max wait for complex queries
        exponential_backoff=True,
        retry_on_timeout=True,
        retry_on_429=True,
    ),
}


# Query type to profile mapping
QUERY_TYPE_PROFILES: Dict[str, RetryProfile] = {
    # ALL queries are CRITICAL for scoring
    "parks": RetryProfile.CRITICAL,
    "green_spaces": RetryProfile.CRITICAL,
    "healthcare": RetryProfile.HEALTHCARE,  # Use dedicated healthcare profile
    "hospitals": RetryProfile.HEALTHCARE,  # Use dedicated healthcare profile
    "transit": RetryProfile.CRITICAL,
    "transit_routes": RetryProfile.CRITICAL,
    "transit_stops": RetryProfile.CRITICAL,
    "amenities": RetryProfile.CRITICAL,  # Changed from STANDARD
    "businesses": RetryProfile.CRITICAL,  # Changed from STANDARD
    "housing": RetryProfile.CRITICAL,  # Changed from STANDARD
    "census": RetryProfile.CENSUS,
    "schools": RetryProfile.SCHOOLS,
    "architectural_diversity": RetryProfile.CRITICAL,  # Changed from STANDARD
    "block_grain": RetryProfile.CRITICAL,  # Changed from NON_CRITICAL
    "streetwall_continuity": RetryProfile.CRITICAL,  # Changed from NON_CRITICAL
    "setback_consistency": RetryProfile.CRITICAL,  # Changed from NON_CRITICAL
    "facade_rhythm": RetryProfile.CRITICAL,  # Changed from NON_CRITICAL
    "nature_features": RetryProfile.CRITICAL,  # Changed from NON_CRITICAL
    "water_features": RetryProfile.CRITICAL,  # Water proximity is critical for natural beauty + outdoors
}


def get_retry_config(query_type: str, profile: Optional[RetryProfile] = None) -> RetryConfig:
    """
    Get retry configuration for a query type.
    
    Args:
        query_type: Type of query (e.g., "parks", "transit", "block_grain")
        profile: Optional override profile (if None, uses query_type mapping)
    
    Returns:
        RetryConfig for the query type
    """
    if profile is not None:
        return RETRY_PROFILES[profile]
    
    # Look up profile by query type
    profile = QUERY_TYPE_PROFILES.get(query_type, RetryProfile.STANDARD)
    return RETRY_PROFILES[profile]


def create_custom_config(
    max_attempts: int = 4,
    base_wait: float = 1.0,
    fail_fast: bool = False,
    max_wait: float = 10.0,
    **kwargs
) -> RetryConfig:
    """
    Create a custom retry configuration.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_wait: Base wait time in seconds
        fail_fast: If True, give up after 2 attempts on rate limit
        max_wait: Maximum wait time between retries
        **kwargs: Additional configuration options
    
    Returns:
        Custom RetryConfig
    """
    return RetryConfig(
        max_attempts=max_attempts,
        base_wait=base_wait,
        fail_fast=fail_fast,
        max_wait=max_wait,
        **kwargs
    )


def register_query_type(query_type: str, profile: RetryProfile):
    """
    Register a new query type with a retry profile.
    
    Args:
        query_type: Name of the query type
        profile: Retry profile to use
    """
    QUERY_TYPE_PROFILES[query_type] = profile
    logger.debug(f"Registered query type '{query_type}' with profile '{profile.value}'")


def get_profile_for_pillar(pillar_name: str, query_type: str) -> RetryConfig:
    """
    Get retry configuration for a specific pillar and query type.
    
    This allows pillar-specific overrides if needed.
    
    Args:
        pillar_name: Name of the pillar (e.g., "active_outdoors", "neighborhood_beauty")
        query_type: Type of query within the pillar
    
    Returns:
        RetryConfig for the query
    """
    # Pillar-specific overrides can be added here
    # For now, use the query_type mapping
    return get_retry_config(query_type)

