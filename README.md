# Python Starter

Quickly get started with [Python](https://www.python.org/) using this starter! 

- If you want to upgrade Python, you can change the image in the [Dockerfile](./.devcontainer/Dockerfile).

## Radius behavior (defaults)

The API automatically adapts search radii per pillar based on detected area context (urban_core, suburban, exurban, rural) and location scope (neighborhood vs city). These defaults are centralized and consistent across pillars; no parameters are required.

Examples of defaults:
- Active Outdoors: local 1km (urban/suburban) or 2km (exurban/rural); regional 15km or 50km
- Neighborhood Amenities: query 1km (neighborhood) or 1.5km (city); walkability 800m/1000m
- Public Transit: nearby routes within ~1.5km
- Healthcare: facilities 5–20km and pharmacies 2–8km by area type
- Built Beauty (architecture/form): 2km default context window, area-type adjustments via radius profiles
- Natural Beauty (trees & scenic context): 1km canopy core (urban core/residential), up to 3km fallback for cities; 2km+ for suburban/exurban contexts
- Natural Beauty scoring blends multi-radius canopy sampling, NDVI-based green view indices, biodiversity entropy, and area-type canopy expectations to reward both lush streets and regional scenery.
- Air Travel: airports within 100km

No public parameters are needed to control these; they follow sensible defaults derived from the location.

## Built Beauty Scoring Notes

- Height variety now considers standard deviation and single-story share to better capture subtle differences.
- Building type diversity blends raw OSM tags with normalized use categories (residential, civic, retail, etc.).
- Material analysis aggregates canonical groups (brick, wood, stone, concrete, glass, metal, stucco, clay) and factors their entropy into the score.
- Landmarks incorporate heritage designations and Census vintage data; median year is now smoothed via area-type percentiles so historic fabric gains credit without sharp cliffs.
- Diverse eras are rewarded only when setbacks, street rhythm, and material consistency confirm a coherent streetscape; otherwise age variety stays neutral.
- Modern districts can earn a dedicated form bonus when tower clusters, design review cues, and modern materials create a cohesive skyline.
- Street-scale character is reinforced through block grain, streetwall, setback, and facade rhythm, with an added street character bonus when coverage is cohesive.
- Coverage expectations are area-type specific, so lower-density suburbs and exurbs are not over-penalized for intentional openness.