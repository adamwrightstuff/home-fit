"""
Data Sources Package
Pure API clients for external data sources.

Many modules live alongside this package (e.g. cache, arch_diversity, data_quality) and are
imported explicitly: ``from data_sources import census_api`` or ``from data_sources import X``.
``__all__`` lists the names historically re-exported from this entrypoint; it is not exhaustive.
"""

from . import census_api
from . import osm_api
from . import nyc_api
from . import schools_api
from . import geocoding
from . import transitland_api

__all__ = ['census_api', 'osm_api', 'nyc_api', 'schools_api', 'geocoding', 'transitland_api']