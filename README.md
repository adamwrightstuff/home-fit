# HomeFit

**Personalized livability scoring API**

HomeFit evaluates locations across 9 purpose-driven pillars to provide comprehensive livability scores based on objective, research-backed data.

---

## Overview

HomeFit is a data-driven livability scoring system that measures what matters most for quality of life. The system evaluates any location across 9 pillars—from outdoor recreation and natural beauty to transit access and housing value—using objective metrics from authoritative data sources.

### Core Philosophy

HomeFit follows strict design principles to ensure consistent, reliable scoring:

- **Research-backed, not artificially tuned** - Expected values come from empirical research, not target scores
- **Objective and data-driven** - All metrics are measurable (counts, distances, ratios, diversity measures)
- **Scalable and general** - No hardcoded city exceptions; works consistently across all locations
- **Transparent and documented** - Detailed breakdowns expose all scoring components
- **Context-aware** - Expectations adapt to area type (urban/suburban/exurban/rural), not arbitrary thresholds

### How Scoring Works

The overall livability score (0–100) is a **weighted average** of 9 pillar scores:

```
total_score = Σ(pillar_score × pillar_weight / 100)
```

**Default weighting**: Equal distribution (~11.11 tokens per pillar, totaling 100)
**Customizable**: Users can prioritize pillars via `priorities` parameter (High/Medium/Low/None) or explicit `tokens` parameter

Each pillar score is independently calculated using:
1. **Data collection** from authoritative sources (OSM, Census, GEE, Transitland, etc.)
2. **Context detection** that classifies area type to set appropriate expectations
3. **Metric calculation** using objective measurements
4. **Score computation** via research-backed scoring curves

### Data Sources

- **OSM API**: Buildings, businesses, parks, healthcare, transit stations
- **Census API**: Population density, housing data, commute times, tree canopy
- **Google Earth Engine (GEE)**: Tree canopy, topography, landcover
- **Transitland API**: Transit routes, stops, schedules
- **SchoolDigger API**: School quality ratings
- **Airport Database**: Airport locations and classifications
- **NYC Street Trees API**: Street tree data (NYC only)

---

## The 9 Pillars

### 1. Active Outdoors
Measures access to outdoor recreation and adventure opportunities. Evaluates local parks and playgrounds for daily outdoor activities, regional trails and camping for wilderness adventures, and waterfront access for water-based recreation. Considers both immediate neighborhood access (parks within 1-2km) and regional opportunities (trails within 15-50km depending on area type).

**Components**: Daily Urban Outdoors (30%) - local parks and facilities; Wild Adventure Backbone (50%) - trails, camping, canopy; Waterfront Lifestyle (20%) - beaches, lakes, coastlines

### 2. Built Beauty
Assesses architectural quality, urban form, and street character. Evaluates building diversity (height variety, type diversity, footprint variation), architectural character (materials, historic fabric, modern design), and street-scale qualities (block grain, streetwall continuity, setback consistency, facade rhythm). Rewards cohesive, well-designed built environments that create appealing neighborhoods.

**Components**: Architectural diversity (0-50 points) - height, type, form metrics; Built enhancers (0-6 points) - artwork, fountains, landmarks

### 3. Natural Beauty
Measures tree canopy, scenic features, and natural landscape quality. Combines multi-radius tree canopy analysis (local street trees, neighborhood canopy, regional green spaces) with scenic bonuses for topography (mountain views, varied terrain), landcover (forests, wetlands), and water features (lakes, coastlines). Climate-adjusted expectations ensure fair evaluation across different regions.

**Components**: Tree score (0-50 points) - canopy coverage, green view, biodiversity; Scenic bonus (0-35 points) - topography, landcover, water features

### 4. Neighborhood Amenities
Evaluates walkability and access to daily conveniences. Measures business density and variety within walking distance (daily essentials, social venues, cultural spots, services), proximity to businesses, and vibrancy of downtown/commercial clusters. Context-aware thresholds ensure appropriate expectations for urban cores vs. suburbs.

**Components**: Home Walkability (0-60 points) - density, variety, proximity to businesses; Location Quality (0-40 points) - downtown proximity, cluster vibrancy

### 5. Air Travel Access
Assesses proximity and quality of nearby airports for travel convenience. Scores the best 3 airports within 150km, with higher weights for international and major hubs. Uses exponential distance decay (optimal at 25-30km) and awards redundancy bonuses for multiple airport options, ensuring travel flexibility.

**Components**: Airport proximity (weighted by airport type - international/major/regional) + Redundancy bonus (multiple airports)

### 6. Public Transit Access
Measures availability and quality of public transportation. Evaluates route counts for heavy rail (subway/metro/commuter), light rail (streetcar/tram), and bus services. Scores the best single mode plus multimodal bonuses. For commuter rail suburbs, includes bonuses for frequency, weekend service, hub connectivity, and destination diversity. Considers commute times as a quality indicator.

**Components**: Best single mode score (heavy rail/light rail/bus) + Multimodal bonus + Commute time weighting + Commuter rail bonuses (frequency, weekend service, hubs, destinations)

### 7. Healthcare Access
Evaluates access to medical facilities and healthcare services. Measures hospital proximity (count and distance), primary care availability (clinics, urgent care), specialty care diversity, emergency services, and pharmacy access. Area-type-specific expectations ensure appropriate scoring for urban centers vs. rural areas.

**Components**: Hospital access (0-35 points) - count and distance; Primary care (0-25 points); Specialty care (0-15 points); Emergency services (0-10 points); Pharmacy access (0-15 points)

### 8. Quality Education
Assesses school quality and educational opportunities. Core K-12 scoring based on average school ratings (elementary, middle, high schools) from SchoolDigger. Includes bonuses for early education access and nearby colleges/universities, recognizing the value of educational opportunities beyond K-12.

**Components**: Average K-12 school rating (0-90 points) + Early education bonus (0-5 points) + College/University bonus (0-5 points)

### 9. Housing Value
Measures housing affordability, space, and value efficiency. Evaluates price-to-income ratio (local affordability), median rooms (space per household), and rooms per $100k (value efficiency). Metro-adjusted thresholds prevent double-penalization in high-cost markets while still rewarding value.

**Components**: Affordability (0-50 points) - price-to-income ratio; Space (0-30 points) - median rooms; Value Efficiency (0-20 points) - rooms per $100k

---

## Context-Aware Adaptation

The system automatically adapts search radii and expectations based on:

- **Area Type Classification**: urban_core, suburban, exurban, rural (detected via morphological analysis)
- **Location Scope**: neighborhood vs. city-wide queries
- **Climate Context**: Adjusts natural beauty expectations by climate zone

**Example Radius Adaptations**:
- Active Outdoors: Local 1km (urban/suburban) or 2km (exurban/rural); regional 15km or 50km
- Neighborhood Amenities: Query 1km (neighborhood) or 1.5km (city); walkability 800m/1000m
- Public Transit: Nearby routes within ~1.5km
- Healthcare: Facilities 5–20km and pharmacies 2–8km by area type
- Built Beauty: 2km default context window, area-type adjustments via radius profiles
- Natural Beauty: 1km canopy core (urban core/residential), up to 3km fallback for cities
- Air Travel: Airports within 150km

No public parameters are needed to control these; they follow sensible defaults derived from the location.

---

## API Usage

### Production Endpoint

**API**: `https://home-fit-production.up.railway.app`

**Web Interface**: Deployed on Vercel

### Basic Request

```bash
GET /score?location="123 Main St, City, State"
```

### Custom Pillar Priorities

```bash
GET /score?location="City, State"&priorities={"active_outdoors":"High","built_beauty":"High","housing_value":"Medium"}
```

Priority levels: `High` (weight 3), `Medium` (weight 2), `Low` (weight 1), `None` (weight 0)

### Enable School Scoring

```bash
GET /score?location="City, State"&enable_schools=true
```

### Response Format

```json
{
  "location": "City, State",
  "total_score": 75.3,
  "livability_pillars": {
    "active_outdoors": {
      "score": 82.5,
      "weight": 11.11,
      "contribution": 9.17,
      "breakdown": {...},
      "summary": {...}
    },
    ...
  },
  "area_classification": {
    "area_type": "suburban",
    "density": 1250.5,
    "coverage": 0.15
  }
}
```

For detailed API documentation, see [openapi.json](./openapi.json)

---

## Deployment

### API (Backend)
- **Platform**: Railway
- **Runtime**: Python/FastAPI (uvicorn)
- **Endpoint**: `https://home-fit-production.up.railway.app`

### Frontend (Web Interface)
- **Platform**: Vercel
- **Framework**: Next.js
- **Configuration**: Root directory `frontend`, auto-deploys on git push

See [DEPLOY_INSTRUCTIONS.md](./DEPLOY_INSTRUCTIONS.md) and [frontend/DEPLOYMENT.md](./frontend/DEPLOYMENT.md) for detailed deployment instructions.

---

## Technical Documentation

- **[Design Principles](./DESIGN_PRINCIPLES.md)** - Core principles guiding scoring methodology
- **[Pillar Scoring Explanation](./analysis/PILLAR_SCORING_EXPLANATION.md)** - Detailed scoring logic for each pillar
- **[Pillar Scoring Methodology Summary](./analysis/pillar_scoring_methodology_summary.md)** - High-level methodology overview

---

## Development

### Requirements

See [requirements.txt](./requirements.txt) for Python dependencies.

### Testing

See test files in the `tests/` and `scripts/` directories for examples.

---

## License

[Add your license here]