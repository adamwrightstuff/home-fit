# Pillar audit against v2 principles (read-only, first pass)

Date: 2026-10-24. Companion to `docs/DESIGN_PRINCIPLES_V2_DRAFT.md`. Local only, not pushed.

Scope and limits. This is a static read of the code plus targeted greps. I ran no scoring, made no live API calls, and ran no pin-shift or all-places tests, so every sensitivity and validation line below is a to-do, not a result. Housing value, diversity, social fabric, economic security, education, amenities, air travel, climate risk, and healthcare were read in part or in full. Transit, active outdoors, and natural beauty were only skimmed (headers and greps), so their rows are thin. Community safety was checked for weights only.

The existing `analysis/pillar_design_principles_audit.md` declares all pillars compliant. Under v2 that is no longer true: it checked for target-score tuning, not for sourced weights, measurement area, sensitivity, validation, or fail-loud behavior.

## Findings that look like real defects (verify before fixing)

1. **Diversity race entropy double counts multiracial residents.** `get_diversity_data` pulls B02001_008 (two or more races) and also B02001_009 and _010, which are subsets of _008. The category list therefore overlaps, so the multiracial share is counted twice and entropy is inflated where it is high. Not measured yet. Census B02001 also has no Hispanic category, so Hispanic residents sit inside "White alone" or "Some other race".
2. **Diversity entropy is normalized by the number of non-empty categories, not the full category set.** A tract with two non-empty groups at 70/30 and the same tract with three tiny extra groups present score very differently, so the score jumps with the presence of a few people. It also breaks the smoothness principle. Not measured yet.
3. **Climate flood sub-score is neutral or maxed on failure.** Memory notes the FEMA source is dead and returning 30/30 everywhere. In code, flood falls back to a neutral 15 of 30 when data is missing, heat, flood, and trend all go neutral on missing data, but air goes to 0 on missing data. The treatment is inconsistent and violates fail-loud. Also air uses 35 ug/m3 (the EPA 24-hour level) as the zero point for what is an annual-style proxy; I believe the annual standard is much lower (about 9), but verify before citing.
4. **Social fabric weights contradict their own comments.** The comment says participation 70, social capital 20, peer civic 10, rootedness 0. The code uses rootedness 0.10, so participation is 0.60 when all inputs exist, and weights silently shift to participation when cohesion or civic data is missing. Missing stability data is scored 0 at 0.10 weight. The module docstring still describes a 1.2x multiplier composite that no longer exists, so that item from the design lessons is already stale. The validation comment says "non-circular", but `atlas_civic_orgs` is both a validation target and 35% of the engagement input.
5. **Economic security uses a peer norm where the v2 frame says absolute.** Market-quality inputs are normalized within Census division by area type. The job-access blend (0.55 job access, 0.45 market quality) is unsourced and wrapped in a bare `except Exception` that silently falls back to market quality alone. Memory says gravity coverage is five metros and broken for Boston and Las Vegas, so most places silently run on the fallback.
6. **Community safety weight is not derived in this checkout.** The user's lesson says the safety weight is now derived, but the code still has a fixed 0.35 property weight and a 0.15 commercial override, and `community_safety.py` is not among the modified files. Either the derivation lives elsewhere or it has not landed.

## Per-pillar gap table

| Pillar | Frame today vs v2 provisional | Unsourced parameters | Measurement area | Fail-loud | Priority |
|---|---|---|---|---|---|
| Housing value | Tract price-to-income ratio, local income by default (income-relative, close to v2). But it measures what current residents can afford, not what a mover can, unless user income is supplied | 50/30/20 split; ratio steps; rooms thresholds; rent bands beyond the 30% standard; value-efficiency metro multipliers 1.5 and 1.3 (own TODO says not research-backed, keyed on metro population, step jumps) | Single tract, with a geo_level fallback | Fallback scores hard-coded per area type when Census fails; outside urban areas returns 0 silently. Diversity raises instead, which is the right pattern | High |
| Diversity | Entropy, higher is better. v2 says preference-dependent | Equal-weight mean of race, income, age; age entropy rewards equal thirds of youth, prime, and seniors with no source | Place for non-urban-core, tract for urban core, so the same score means different areas | Raises on no data (good) | High (defects 1 and 2) |
| Social fabric | Mixed. Cohesion peer-normalized by area type, infrastructure absolute. Chetty found economic connectedness predicts mobility and civic engagement does not; `ec_zip` appears only in a comment, never as an input | 0.20, 0.10, 0.10, remainder; 0.65 and 0.35 engagement blend; 0.7 and 0.3 tract and place; 0.8 and 0.2 tenure; node type weights | Tract plus place, civic radius by density bands | Silent reweighting when inputs are missing; Overpass retries then scores thin results | High |
| Economic security | Peer-normalized by division and area type vs v2 absolute | 0.40, 0.15, 0.20, 0.25; sub-weights; 0.55 and 0.45 blend; remote-worker weights (derived arithmetically from E and R) | CBSA data plus a gravity grid in few metros | Bare except fallback | High |
| Neighborhood amenities | 60/40 split; log curve anchored at 400 businesses is absolute while other expectations are by area type | 60/40; tier weights 0.45, 0.30, 0.25; vibrant thresholds "raised" from 50 to 100 and from 40 to 60 with the goal "make it harder to max out", which is target-score tuning under v1 | Radius profile by area type | Treats no businesses as an empty walkable area, with a confidence cap and warning | High |
| Education | Rank-style SchoolDigger ratings, close to the relative frame | Access bonus +2 per rating at 85 or above, capped +5; early-ed bonus 0 to 3 from OSM within 2 km; far cap 15 mi | District and nearest-school logic, 3 mi widening | Mostly flagged by source labels | Medium |
| Climate risk | Fixed standard (v2). Sub-weights 25, 20, 30, 25 | Weights; 30 to 42 C heat range; trend zero at 0.5 C per decade | 500 m heat buffer; FEMA zone at pin | Neutral on missing, inconsistent (finding 3) | High |
| Air travel | Drive-time bands by area type, service level by class. v2 wants service weighted by real nonstops and frequency | Speeds "tuned so a 25 km..."; time bands; service scores 100 and 92; +7 cap for second airport within 60 min; 150 km cutoff | Pin to airport | Airport database failure silently drops to a legacy list | Medium |
| Healthcare | Ratio to area-type expected counts. v2 wants a fixed standard with distance decay | Curve points; the comment calls 1.5x and 2.5x both 85, so the "excellent" tier adds nothing | Radius profile | 44 fallback or default mentions; Places and NPI augmentation | Medium |
| Community safety | National percentile, one scale for all area types | 0.65 and 0.35; 0.15 commercial override; trend up to 5 points | Neighborhood circles, radius floor test exists | Returns None when no data (good) | Low (already worked) |
| Public transit | Not audited beyond header; 19 broad exception handlers and a "lowered from 10+ to 7+" threshold edit | not reviewed | not reviewed | needs review | Medium |
| Active outdoors | Not audited beyond header | not reviewed | not reviewed | needs review | Medium |
| Natural beauty | Not audited; 43 broad exception handlers and 134 fallback or neutral mentions across 4,590 lines | not reviewed | not reviewed | needs review | Medium |

## Cross-pillar observations

- Principle 4 (sourced weights and ranges) fails everywhere except where a regression or validation was run (social fabric partly). No pillar records a plausible range for any weight.
- Principle 6 (sensitivity) has not been run for any pillar except community safety.
- Principle 7 (independent validation) exists only for social fabric (against external social capital data, with the circularity above) and for natural beauty (human ratings per the v1 doc).
- Fail-loud is inconsistent: diversity and community safety refuse to score without data, while housing, climate, social fabric, and economic security substitute fixed or neutral values.

## Offline check of diversity defects 1 and 2 (2026-10-24)

Raw race counts are not stored in the catalog (only the three entropy values) and are not in `.disk_cache`, so the defects could not be measured on real tracts offline. What was done instead: confirmed from the code that categories 008, 009, 010 overlap (009 + 010 = 008 by Census definition), and simulated six synthetic tract mixes.

- Overlap inflates race entropy by about 3 to 6 points for typical mixes (homogeneous suburb 34.6 vs 29.2 deduplicated; mixed suburb 69.5 vs 66.4; Hispanic-majority tract on the race question 84.7 vs 78.9). That is roughly 1 to 2 points on the headline, since race is one of three equal components. The bias grows with multiracial share, so it favors tracts where many residents report two or more races.
- Normalizing by non-empty categories is a real cliff in the math: a 70/30 two-group tract scores 88.1, and adding three groups at 0.1% each drops it to 39.3. A 50/50 two-group tract scores 100.
- In the stored data this cliff rarely bites: across 1,470 places, race entropy has median about 57, 95th percentile about 81, and only 0.07% at 95 or above. Most tracts evidently report a nonzero estimate in nearly every category, so the denominator is usually the full set.
- A fixed denominator is a design choice, not just a bug fix: it scores a 50/50 two-group tract at about 36, because few groups is less diverse than many.

### Measured on real tracts (22 randomly sampled catalog places, raw ACS counts pulled live, 2026-10-24)

Reproduction check: recomputing entropy from the pulled counts matched the stored race_entropy in all 22 places, so the comparison is faithful.

- Overlap inflation (as coded minus deduplicated): mean 4.4 points, median 4.2, range 0.6 to 9.2. Headline effect (race is one of three equal dimensions): mean about 1.5, up to about 3.1. Largest in Tarzana (9.2), Stapleton (9.0), Round Rock (7.3), Gainey Ranch (6.7), Allandale (6.5). Rank order is barely affected (Spearman 0.985 between coded and deduplicated).
- Normalization: this corrects the offline inference above. After deduplication, 14 of 22 places have fewer than 7 non-empty race categories (as few as 3 in Seaport District), so the denominator is not the full set in most sampled places. A fixed 7-category denominator would lower race entropy by 4.6 points on average and up to 25 (Seaport District), and changes rank order more (Spearman 0.90 against coded).
- Geography: the sampled suburbs mix tract, place, and county-subdivision levels, so the same score covers areas of very different size.
- Not changed: no scoring code or stored scores were modified. Fixes need owner approval first.

## Suggested next steps (none started)

1. Confirm defects 1 and 2 on a few tracts from stored data, then decide fix proposals with expected score impact. These are logic or data-definition changes that need your approval before any edit.
2. Decide fail-loud policy once: reject, or score with a visible low-confidence flag, then apply it consistently.
3. Run the pin-shift test on the single-tract pillars (housing, diversity, social fabric) using cached or stored data where possible to avoid new API calls.
4. Finish the unaudited rows (transit, active outdoors, natural beauty).
