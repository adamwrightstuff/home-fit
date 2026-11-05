# Natural beauty: what is still required to be DPv2 verified (2026-10-27)

Read-only. Checked against main: local main is e0917b3, origin/main is 81708ff (3 safety commits ahead, none touch natural beauty files). Pillar code and the 8 changed catalog files are identical on both. Catalog check run on all 1,476 stored places. Nothing in this file changes scoring.

## Bottom line

Not verified. Fail-loud (P9) is done and shipped. Four principles are met or nearly met on evidence, and five are open: P1 (frame), P4 (sources), P6 (pin shift), P7 (validation) and P12 (schedule). P4, P7 and the desert question cannot be closed by code; they need research or owner decisions. Amenities was signed off with P7 left open and noted, so the same pattern is available here if you choose it.

## Status by principle (confirmed against main)

| # | Principle | Status | Evidence on main |
|---|---|---|---|
| P1 | Reference frame | Open | Draft says shared absolute scale. Code divides green view and canopy by a regional median (peer norm); terrain and water are absolute. Mixed frame, never declared, and no tier 1 to 3 evidence for the peer part (Place Pulse test: +0.005) |
| P2 | Construct in one sentence | Partial | Doc describes two kinds of beauty; no one-sentence construct, no stated reference frame |
| P3 | Measurement area | Open | Radii (canopy 400/1000/2000 m, green view 1200 m, terrain and water radii) have no recorded reason |
| P4 | Sourced weights with ranges | Open | Every weight, curve breakpoint, regional baseline and the percentile scale is judgment or unsourced. Sensitivity ranges exist in the 2026-10-25 audit but are not in a spec sheet |
| P5 | No double counting | Partial | Green view and canopy share satellite inputs (0.7/0.3 pairing, untested); overlap with Active Outdoors on water and parks argued, never tested |
| P6 | Sensitivity | Partial | Weight and normalization sensitivity done offline. A true pin-shift test (same place, pin moved 250 and 500 m) not run |
| P7 | Independent validation (Spearman 0.7+, 15+ places) | Open | Best pieces: terrain vs ScenicOrNot 0.41, streets vs Place Pulse 0.37 (Pearson). The final blend has no validation; deserts have no rating data |
| P8 | All-places check | Meets | 1,476 places, per-metro deltas, for both the two-part change and the fail-loud rewrite |
| P9 | Fail loudly | Meets for scoring | Code and catalog done (below). Live path tested by 14 unit tests; no real GEE or Overpass outage has been exercised |
| P10 | Launch check | Meets | Two pre-registered natural beauty contrasts passing; spread check runs. Caveat: spread is forced by the percentile scale, so it tests little |
| P11 | Data limits disclosed | Partial | 192 places now carry a degraded flag with the reason. 238 older-shape places still store confidence None and 3 store 0. Instrument mismatch, 2007 to 2012 photos and Britain-only ScenicOrNot are in the proposal file, not in the API response |
| P12 | Re-validation schedule | Open | No schedule. Live scorer versus catalog not diffed for this pillar (TS mirror not checked) |

## What the fail-loud work closed (verified on main today)

- Missing water no longer scored 5.0: 1 place still shows the old signature, 192 carry a degraded flag with the reason.
- Both streets and scenery required; San Fernando is no data (score None, contribution 0.0).
- Proxy rule removed; composite-fallback green view is labeled and flagged.
- All 1,476 stored places carry the two-part method label (the 121 stale breakdowns from the first audit are gone). 62 older-shape breakdowns from the first rewrite remain without the new degraded keys.

## Update 2026-10-27 (same day)

Steps 1 and 2 done by owner decision: the regional median is kept and recorded as an unsourced judgment, and the spec sheet and parameter table are in `docs/PILLAR_NATURAL_BEAUTY.md` (also corrected the water radius there from 3 km to the 15 km the code queries, and replaced the outdated missing-greenery text with the shipped fail-loud rules). P1 and P2 are now declared; P4 stays open because the table records that nothing is sourced. Not committed. Remaining: steps 3 to 7.

### Later the same day: step 5 to 7 findings

- **New defect, fixed locally (uncommitted):** the live response step (`_calculate_data_quality_summary` in `main.py`) overwrote each pillar's own `degraded` and `degraded_reasons` with only the stale-cache and rate-limit signals, so the fail-loud flags I shipped (and other pillars' own reasons) never reached a live response. Reproduced offline (flag True after the scorer, False after the summary), then fixed by keeping the pillar's own reasons and adding the signals; two tests added. Effect on live output: pillars that record `degraded_reasons` now show them; no scores change. This was not caught earlier because the stored catalog flags were written by the offline script, not through this path.
- **Confidence is not tied to degraded state (DECIDED 2026-10-27: leave as is, rely on the degraded flag and reasons, recorded as a known limit in the pillar doc):** pillar confidence for new-shape places is a flat 89 ("excellent") for all 1,235, derived from whether certain keys exist (`_assess_natural_beauty_completeness`), so 163 degraded places show status success, confidence 89, tier excellent. Capping confidence for degraded places needs a number with no source, so I did not do it.
- **238 older-shape places have no confidence:** they carry no key to derive it from; any value would be invented. Left as stored (null). Two NYC places (Glendale and one more) store confidence 0 with status success; not touched.
- **TS mirror checked:** constants and the percentile table match Python. **Region script hardened:** `recompute_natural_beauty_region_offline.py` now skips a no-data place instead of stopping (dry run: 0 places, unchanged).
- **Re-validation schedule added** to the pillar doc (next due 2027-01-27).

## Required steps, in order

Each step lists what it needs. "Owner" means it cannot move without your decision.

1. **Declare the frame and the construct (P1, P2). Owner decision.** Either say beauty is a shared absolute scale and remove the regional median, or say it is a peer-norm pillar and record the evidence tier. Today the code contradicts the approved frame. Dropping the regional median moves scores a mean of 5.9 points (p95 17, max 34.7; Phoenix -19.9, Seattle +14.0). Keeping it requires stating it as an unsourced judgment (tracker D12). Cost: a paragraph, plus a catalog rewrite only if you choose to drop it.
2. **Fill the spec sheet and record ranges (P3, P4, P5). Documentation.** One block with every parameter, source or "judgment", and its plausible range. Sensitivities already exist: within-part 0.7/0.3 moves scores 4 points on average at 0.6 or 0.8; the 50/50 blend moves 5 at 0.4 or 0.6. Curves, regional baselines and the percentile scale stay TODO unless a citation is found. Cost: offline, no API.
3. **Pin-shift test (P6). Needs live or cached reads.** Same place, pin moved 250 and 500 m, report median and p95 score change against the 5-point gate. Terrain and water are step-like in distance and neighboring pins differ by tens of points in the catalog, so this is the likeliest place for a gate failure. Cost: GEE and Overpass calls for the shifted pins; run a small pilot first.
4. **Independent validation of the blended score (P7). Research.** Spearman on 15+ matched places: Place Pulse photos for streets, ScenicOrNot for scenery, then the blend. State plainly that deserts are unvalidated. The owner has said no paid rating panels, so deserts stay open unless an in-product rating route is built. Amenities precedent: sign off with P7 open and noted.
5. **Disclose limits and finish metadata (P11). Offline, no score change.** Set confidence for the 238 older-shape places (and the 3 stored 0), add the degraded keys to the 62 older-shape breakdowns, surface the data limits in the API response.
6. **Schedule re-validation and diff live against catalog (P12). Small.** Add a quarterly or source-change trigger and compare the live scorer with the catalog and the TS mirror for this pillar.
7. **Optional hardening.** Exercise one real GEE or Overpass failure on a live score to confirm the no-data path end to end; make `recompute_natural_beauty_region_offline.py` catch NaturalBeautyNoData so it cannot stop on a no-data place.

## Honest read on sign-off

Steps 1, 2, 5 and 6 are documentation or offline and close in a session. Step 3 needs a small live pilot. Step 4 is the only one that may never fully close (deserts and the blend have no human rating source). Following the amenities precedent, natural beauty can be signed off after steps 1 to 3, 5 and 6, with P7 open and noted.

## Not verified here

I did not rerun the pin-shift or validation numbers; they come from the 2026-10-25 audit and the two-part proposal. I did not diff the TS mirror. The Colorado-era test failure in the full suite (metro agent state) predates this work and is unrelated.
