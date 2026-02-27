## Social Fabric Index (`social_fabric` pillar)

### 1. Purpose

New pillar `social_fabric` (Phase 2B). Scores structural and demographic factors that support local belonging and civic capacity. It is:

- Distinct from `neighborhood_amenities` (commercial businesses, convenience).
- Distinct from `active_outdoors` (parks, trails, outdoor recreation).

Version 1 (Phase 2B) ships with:

1. **Stability** (residential rootedness; Census B07003)  
2. **Civic gathering** (civic, non-commercial third places; OSM)

The **Diversity** and **Engagement** sub-indices are defined here but can be implemented in a later sub-phase (2B′).

All sub-scores and the pillar score are on 0–100.

---

### 2. Data requirements

#### 2.1 Census

Add the following ACS tables to the Census pipeline (tract or block-group geography, aligned with existing lookups):

- **B07003 – Geographical Mobility (1-year)**
  - `B07003_001E` – total population 1 year and over.  
  - `B07003_002E` – same house 1 year ago.  
  - **Stability ratio** = `B07003_002E / B07003_001E`.

- **B02001 – Race**
  - Full race distribution, for future Diversity entropy.

- **B19001 – Household Income in the Past 12 Months**
  - Full income bracket distribution, for future Diversity entropy.

- **Age distribution**
  - Prefer a collapsed table with \<18, 18–64, 65+ buckets (e.g. C01001*), or aggregate B01001 into three buckets if needed.

For SFI v1, only B07003 is required. Diversity can be implemented once B02001/B19001/age are wired up.

#### 2.2 IRS BMF (optional; Phase 2B′)

Defined but **not required** for SFI v1.

- Source: IRS Exempt Organizations Business Master File.  
- Filter:
  - NTEE codes: `A`, `O`, `P`, `S` (Arts/Culture, Youth Development, Human Services, Community Improvement).  
  - Active status: use the appropriate BMF field/value indicating currently active exemption (to be confirmed in ingest spec).  
- Geography:
  - Tract-based or radius-based lookup from preprocessed data files; no PostGIS assumed.
  - Denominator for per-capita: matching tract (or area) population from Census.

#### 2.3 OSM – civic nodes

New Overpass query separate from `query_local_businesses()`:

- **Include (civic, non-commercial):**
  - `amenity=library`  
  - `amenity=community_centre`  
  - `amenity=place_of_worship`  
  - `amenity=townhall`  
  - `leisure=community_garden`

- **Exclude / do not request (already scored elsewhere):**
  - `leisure=park`, `leisure=playground`, `leisure=dog_park` (Active Outdoors pillar)  
  - All commercial amenity/shop tags used in `neighborhood_amenities` (cafes, restaurants, bars, shops, etc.).

- Radius: 800 m around the geocoded point.

Implement as a new function (e.g. `query_civic_nodes(lat, lon, radius_m=800)`).

---

### 3. Sub-index definitions

#### 3.1 Stability (0–100)

- Input: stability ratio \(x = \text{same_house_1yr} / \text{total_1yr}\) from B07003.
- Curve (x in percentage points 0–100):

If \(x \le 85\):
\[
\text{Stability} = \frac{x}{85} \times 100
\]

If \(x > 85\):
\[
\text{Stability} = \max\bigl(0,\ 100 - 2 \times (x - 85)\bigr)
\]

- 85 % → 100  
- 90 % → 90  
- 95 % → 80  
- 100 % → 70

Handle missing / zero totals gracefully (score = null or 0 with low data_quality).

SFI v1 **must** include this sub-score.

#### 3.2 Diversity (0–100) — defined, may ship later

Compute three entropies and combine:

1. **Race entropy** \(H_\text{race}\) from B02001:
   - Category probabilities \(p_i\) over race categories.  
   - \(H_\text{race} = -\sum_i p_i \log p_i\).  
   - Normalize:
     \[
     H^\*_\text{race} = 100 \times \frac{H_\text{race}}{\log(n_\text{race})}
     \]
     where \(n_\text{race}\) = number of race categories with non-zero support.

2. **Income entropy** \(H_\text{income}\) from B19001:
   - Same pattern over income brackets; normalize by \(\log(n_\text{income})\) to 0–100.

3. **Age entropy** \(H_\text{age}\):
   - Use 3 buckets (Youth, Prime, Seniors) from the chosen age table.  
   - Normalize by \(\log(3)\) to 0–100.

- **Composite Diversity**:
\[
\text{Diversity} = \frac{H^\*_\text{race} + H^\*_\text{income} + H^\*_\text{age}}{3}
\]

If any component is missing, average only over available components and mark data_quality accordingly.

#### 3.3 Civic gathering (0–100)

- Input: civic nodes from `query_civic_nodes` within 800 m.
- Raw metric: `count_civic = number of civic nodes within 800 m`.

Normalization options (pick one and keep it consistent):

- **Threshold-based:**  
  - Example (per area_type):
    - 0 → 0 pts  
    - 1–2 → 40 pts  
    - 3–5 → 70 pts  
    - 6+ → 100 pts  
  - Interpolate linearly within ranges.

- **z-score vs region:**  
  - For each Census Division (or CBSA), compute mean and SD of `count_civic`.  
  - \(z = (\text{count}_\text{civic} - \mu) / \sigma\); clip to ±3.  
  - Map z to 0–100: e.g. \(z=-3 \to 0\), \(z=0 \to 50\), \(z=+3 \to 100\).

Implementation can start with a simple threshold curve; z-score normalization can be added later if needed.

SFI v1 **must** include this sub-score.

#### 3.4 Engagement (0–100) — optional / Phase 2B′

- Input: `orgs_per_1k = (count of active NTEE A/O/P/S orgs in area) / (population / 1000)`.
- Normalize per region (Census Division or CBSA), similar to Civic:
  - Compute mean and SD of `orgs_per_1k`; z-score; clip ±3; map to 0–100.
- If BMF is not yet integrated, Engagement can be omitted (null) and excluded from the combined SFI until Phase 2B′.

---

### 4. Combining into SFI (0–100)

Given sub-scores:

- \(S\) = Stability  
- \(D\) = Diversity (optional initially)  
- \(C\) = Civic gathering  
- \(E\) = Engagement (optional)

Weights:

- Stability: 1.2  
- Civic gathering: 1.2  
- Diversity: 1.0  
- Engagement: 1.0

When all four sub-scores are present:
\[
\text{SFI} = \frac{1.2S + 1.0D + 1.2C + 1.0E}{4.4}
\]

For SFI v1 (Stability + Civic only):
\[
\text{SFI} = \frac{1.2S + 1.2C}{2.4}
\]

If/when Diversity is added without Engagement:
\[
\text{SFI} = \frac{1.2S + 1.0D + 1.2C}{3.4}
\]

Always renormalize by the sum of the active weights so SFI remains in [0, 100].

Handle missing sub-indices by rescaling weights only over available components and documenting in `data_quality`.

---

### 5. Normalization strategy

- **Reference region:** Census Division (or CBSA where available) for any z-score–based normalizations (Diversity sub-components, Civic, Engagement).
- **Clipping:** For any z-score \(z\), clip to [-3, 3] before mapping to 0–100.
- **Mapping:** e.g.
\[
\text{score} = \frac{z + 3}{6} \times 100
\]
so z = -3 → 0, z = 0 → 50, z = +3 → 100.

---

### 6. API contract

Add to the main score response:

- `social_fabric`:
  - `score`: SFI (0–100).  
  - `weight`, `contribution`: same pattern as other pillars.  
  - `breakdown`:
    - `stability` (0–100)  
    - `diversity` (0–100 or null until implemented)  
    - `civic_gathering` (0–100)  
    - `engagement` (0–100 or null until implemented)  
  - `summary`: key raw metrics (stability %, civic node count, orgs_per_1k when present).  
  - `data_quality`: completeness, tier, confidence, sources.  
  - `area_classification`: area_type etc., consistent with other pillars.

**Qualitative label (optional, rule-based):**

Example rules:

- If Stability ≥ 80 and Civic ≥ 70 → `"Social anchor (high stability and civic life)"`.  
- If Stability < 50 and Diversity ≥ 60 → `"Dynamic but transient (diverse, lower rootedness)"`.  
- If all sub-scores < 40 → `"Weak social fabric (low stability, low civic presence)"`.

Logic should be deterministic and based solely on sub-score bands.

