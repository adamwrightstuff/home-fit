"""Shared Places API key and HOMEFIT_PLACES_FALLBACK_* flags."""
from __future__ import annotations

import os
from typing import Optional


def google_places_api_key() -> Optional[str]:
    return (os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("HOMEFIT_GOOGLE_PLACES_API_KEY") or "").strip() or None


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def places_master_fallback_enabled() -> bool:
    return _truthy("HOMEFIT_PLACES_FALLBACK_ENABLED")


def places_na_fallback_enabled() -> bool:
    return bool(google_places_api_key()) and places_master_fallback_enabled()


def places_sf_fallback_enabled() -> bool:
    if not google_places_api_key():
        return False
    return places_master_fallback_enabled() or _truthy("HOMEFIT_PLACES_SF_FALLBACK_ENABLED")


def places_ao_fallback_enabled() -> bool:
    if not google_places_api_key():
        return False
    return places_master_fallback_enabled() or _truthy("HOMEFIT_PLACES_AO_FALLBACK_ENABLED")
