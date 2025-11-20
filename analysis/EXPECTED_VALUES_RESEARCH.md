# Expected Values Research Methodology

## Overview

This document tracks research-backed expected values for all HomeFit pillars. Expected values are based on real-world data from OSM, Census, and external research sources, not arbitrary targets.

## Research Principles

1. **Data-Driven**: All expected values derived from actual data samples
2. **Transparent**: Full methodology and sources documented
3. **Validated**: Cross-referenced with external research where available
4. **Contextual**: Values vary by area type (urban_core, suburban, exurban, rural)
5. **Confidence Levels**: Document sample sizes and confidence intervals

## Data Collection Methodology

### Sample Strategy
- **Minimum Sample Size**: 20+ locations per area type (target: 50+)
- **Geographic Diversity**: Cover all major US regions
- **Area Type Distribution**: Representative samples across urban/suburban/exurban/rural
- **Data Sources**: Primary = OSM, Secondary = Census, External Research

### Collection Process
1. Sample locations from test cases and known benchmarks
2. Query OSM for each pillar's data
3. Calculate medians, percentiles (25th, 75th)
4. Cross-reference with external research sources
5. Document methodology and confidence levels

## Pillar-Specific Research

### 1. Active Outdoors Pillar

#### Research Questions
- What is the median number of parks within 1km by area type?
- What is the typical park area (hectares) by area type?
- What are accessibility standards (e.g., 10-minute walk to park)?

#### Data Sources
- **Primary**: OSM (parks, playgrounds, trails, water, camping)
- **External Research**:
  - Trust for Public Land: ParkScore database
  - NRPA: National Recreation and Park Association standards
  - Urban planning studies (10-min walk = ~800m standard)

#### Current Findings
*To be populated from research script results*

| Area Type | Parks (1km) | Park Area (ha) | Source | Sample Size | Date |
|-----------|-------------|----------------|--------|-------------|------|
| urban_core | TBD | TBD | OSM + TPL | TBD | TBD |
| suburban | TBD | TBD | OSM + TPL | TBD | TBD |
| exurban | TBD | TBD | OSM + TPL | TBD | TBD |
| rural | TBD | TBD | OSM + TPL | TBD | TBD |

#### External Benchmarks
- **Trust for Public Land**: [ParkScore methodology](https://www.tpl.org/parkscore)
- **NRPA**: 10 acres of parkland per 1,000 residents
- **WHO**: 9m² of green space per person minimum

---

### 2. Healthcare Access Pillar

#### Research Questions
- What is the typical distance to nearest hospital by area type?
- How many pharmacies/clinics are typically within radius?
- What are CMS/HHS accessibility standards?

#### Data Sources
- **Primary**: OSM (hospitals, clinics, pharmacies, doctors)
- **External Research**:
  - CMS Provider Data
  - HHS Health Resources and Services Administration (HRSA)
  - Healthcare accessibility studies

#### Current Findings
*To be populated from research script results*

| Area Type | Hospitals (20km) | Pharmacies (8km) | Closest Hospital (km) | Source | Sample Size | Date |
|-----------|------------------|------------------|----------------------|--------|-------------|------|
| urban_core | TBD | TBD | TBD | OSM + CMS | TBD | TBD |
| suburban | TBD | TBD | TBD | OSM + CMS | TBD | TBD |
| exurban | TBD | TBD | TBD | OSM + CMS | TBD | TBD |
| rural | TBD | TBD | TBD | OSM + CMS | TBD | TBD |

#### External Benchmarks
- **CMS**: Hospital accessibility standards
- **HRSA**: Health Professional Shortage Areas (HPSA) criteria
- **AHA**: Average distance to hospital by area type

---

### 3. Neighborhood Amenities Pillar

#### Research Questions
- What is the typical business density (businesses/km²) by area type?
- What is the typical walkability score threshold?
- What are urban planning standards for mixed-use development?

#### Data Sources
- **Primary**: OSM (businesses by tier)
- **External Research**:
  - Walk Score API (if available)
  - Urban planning studies (Jane Jacobs, New Urbanism)
  - Census Business Patterns data

#### Current Findings
*To be populated from research script results*

| Area Type | Businesses (1km) | Median Distance (m) | Source | Sample Size | Date |
|-----------|------------------|-------------------|--------|-------------|------|
| urban_core | TBD | TBD | OSM | TBD | TBD |
| suburban | TBD | TBD | OSM | TBD | TBD |
| exurban | TBD | TBD | OSM | TBD | TBD |
| rural | TBD | TBD | OSM | TBD | TBD |

#### External Benchmarks
- **Walk Score**: 70+ = "Very Walkable", 90+ = "Walker's Paradise"
- **New Urbanism**: 15-minute city concept
- **Jane Jacobs**: Mixed-use, high-density neighborhoods

---

### 4. Public Transit Access Pillar

#### Research Questions
- What is typical transit coverage by area type?
- What are FTA accessibility standards?
- What is the typical distance to nearest transit stop?

#### Data Sources
- **Primary**: Transitland API, OSM (transit routes/stops)
- **External Research**:
  - FTA National Transit Database
  - GTFS feeds
  - Transit accessibility studies

#### External Benchmarks
- **FTA**: Accessibility standards for public transit
- **APTA**: American Public Transportation Association guidelines

---

### 5. Air Travel Access Pillar

#### Research Questions
- What is the typical distance to nearest major airport by area type?
- What are FAA accessibility standards?

#### Data Sources
- **Primary**: FAA Airport Data, OSM (airport locations)
- **External**: Existing `airports.json` database

#### External Benchmarks
- **FAA**: Airport accessibility data
- **Industry Standard**: 1-2 hour drive to major airport acceptable

---

### 6. Quality Education Pillar

#### Research Questions
- What is the typical number of schools within radius by area type?
- What are school district standards for accessibility?

#### Data Sources
- **Primary**: SchoolDigger API (already integrated)
- **External**: Department of Education data, OSM (school locations)

#### External Benchmarks
- **DOE**: School accessibility standards
- **School Districts**: Typical catchment area sizes

---

### 7. Housing Value Pillar

#### Research Questions
- What are typical affordability ratios by area type?
- What are HUD affordability standards?

#### Data Sources
- **Primary**: Census ACS housing data (already used)
- **External**: HUD Fair Market Rent data

#### External Benchmarks
- **HUD**: 30% of income for housing (affordability standard)
- **Census**: Median housing costs by area type

---

## Research Updates

### 2025-01-XX: Initial Research
- Created research data collection script
- Started sampling test locations
- *Status: In Progress*

---

## Confidence Levels

- **High Confidence**: 50+ samples, validated against external sources
- **Medium Confidence**: 20-49 samples, some external validation
- **Low Confidence**: <20 samples, limited validation

## Next Steps

1. ✅ Create research data collection script
2. ⏳ Run script on test locations
3. ⏳ Calculate medians and percentiles
4. ⏳ Cross-reference with external research sources
5. ⏳ Update expected values in code
6. ⏳ Document all sources and methodology

## Running the Research Script

The research data collection script is located at `scripts/research_expected_values.py`.

### Basic Usage

```bash
# Run on all area types with all sample locations
python scripts/research_expected_values.py

# Limit sample size per area type (for faster testing)
python scripts/research_expected_values.py --sample-size 5

# Process specific area types only
python scripts/research_expected_values.py --area-types urban_core suburban

# Specify custom output directory
python scripts/research_expected_values.py --output-dir analysis/my_research
```

### Output Files

The script generates three output files in the specified output directory:

1. **`expected_values_statistics.json`**: Calculated medians, percentiles (25th, 75th), min, max for each metric by area type
2. **`expected_values_raw_data.json`**: Complete raw data for each sampled location
3. **`expected_values_summary.csv`**: Summary table in CSV format for easy analysis

### Sample Locations

The script uses predefined sample locations from test cases:
- **urban_core**: 20 locations (Park Slope, West Village, Downtown Boulder, etc.)
- **suburban**: 26 locations (Bend, Park City, Bar Harbor, etc.)
- **exurban**: 2 locations
- **rural**: 1 location

### Rate Limiting

The script includes 1-2 second delays between API calls to respect rate limits. A full run on all locations may take 30-60 minutes.

### Interpreting Results

- **Median**: Use as the primary expected value (50th percentile)
- **P25/P75**: Use to define acceptable ranges
- **Sample Size**: Higher n = higher confidence
- **Min/Max**: Shows outliers and data quality issues

