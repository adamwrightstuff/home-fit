# DPv2 adoption: sign-off rule, document updates, re-validation (DRAFT for owner edit, 2026-10-31)

Everything below is a proposal. Nothing here is in force until the owner edits and approves it.

## 1. What "compliant" means (proposed)

A pillar is rated at one of four levels. The level is written at the top of its spec sheet.

| Level | Name | Requirements |
|---|---|---|
| 0 | Not audited | No spec sheet. |
| 1 | Converted | Spec sheet filled. Reference frame declared with its evidence tier. Shared place facts come from the place context (principles 13 to 17). No scoring value keys on the area-type label, or each remaining use is listed with a reason. Failed or unmeasurable data is left out or flagged, never replaced by a neutral number (principle 9). |
| 2 | Verified | Level 1, plus: pin-shift sensitivity reported; all-places check with spread by area type and floor/ceiling clumping; launch pairs; independent validation against a source we did not build from (or a written reason none exists), with pass criteria fixed before the results; every unsourced parameter listed as a TODO with a plausible range or "unknown". |
| 3 | Sourced | Level 2, plus every weight, threshold and curve parameter has a source and a recorded range (principle 4 met in full). |

A pillar may ship and be scored at Level 1 or 2. Level 3 is the target, not a gate. User-facing copy may call a pillar "validated" only at Level 2 with independent validation passed on the full catalog, not a subset.

## 2. Who signs off (proposed)

- The owner signs off Levels 1 and 2. The sign-off is a dated line in the spec sheet: level, date, and the list of TODOs accepted.
- The checks for Level 2 are run by someone other than whoever built or converted the pillar (another session or agent), so the builder does not grade their own work. Pass criteria are written down first.
- A change to a signed-off pillar's scoring drops it back to Level 1 until the all-places check, pin-shift and validation are rerun.

## 3. Current standing (from what this working session verified)

Healthcare: Level 2 in progress, not signed off (validation covered 668 of 1,476 places; pharmacy unvalidated; shortage-area check inconclusive; hospital curve parameters unsourced). Active outdoors: Level 1 candidate (facilities term and water multipliers still on type tables; no pin-shift or independent validation run in this session). Every other pillar: not assessed here; other sessions did that work and their status needs to be entered by the owner.

## 4. Document updates to make once approved

1. `DESIGN_PRINCIPLES_V2_DRAFT.md`: change the title from "DRAFT, local only" to "Adopted <date>" and move it out of draft. Fix Part 4 rows marked "unverified" or cite them as unverified in the pillar spec sheet.
2. `DESIGN_PRINCIPLES.md` (v1): add a banner at the top: "Principle 6 (area-type expectations) is superseded by DPv2 for converted pillars. Principles 1 to 5 still apply."
3. `CLAUDE.md`, replace the paragraph "Area-type adaptation drives radii, thresholds, and expectations..." with: "Pillars converted to DPv2 take shared facts from the place context and do not key scoring on the area-type label; pillars not yet converted still use area-type tables until they are. See docs/DESIGN_PRINCIPLES_V2_DRAFT.md." Also change "detects area type" in the pillar structure paragraph to "reads the area type and density factors from the place context", and point the Design Rules section at v2 for converted pillars.

## 5. Re-validation (principle 12)

Proposed: the owner owns it. Every pillar is re-validated quarterly, or sooner when its data source changes. The re-validation is the Level 2 checks rerun and the spec sheet's "Last re-validated" date updated. A scheduled reminder can be set up once the owner agrees to the cadence.
