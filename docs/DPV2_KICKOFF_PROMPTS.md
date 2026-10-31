# Kickoff prompts for taking a pillar through DPv2 (draft, 2026-10-31)

Paste the template into a new session and fill in the pillar. Add the pillar's specifics from the table below it.

## Template

Take the {PILLAR} pillar through design principles v2. Pull origin/main first and work in a new git worktree off origin/main, never in the shared checkout.

Read first: docs/DESIGN_PRINCIPLES_V2_DRAFT.md (principles 1 to 17 and the spec sheet template), docs/DPV2_ADOPTION_DRAFT.md (compliance levels and sign-off), docs/PILLAR_{DOC}.md, data_sources/place_context.py, and the worked examples docs/PILLAR_HEALTHCARE_ACCESS.md and analysis/active_outdoors_baseline_redesign_proposal_2026-10-27.md.

Rules: work offline from stored catalog data first. Say what data a change needs before any API call or Overpass read, and ask. Propose before changing scoring and get my explicit approval at each step. Never push to main without my explicit yes. Downloads need my permission, go in their own empty folder, and run Python with -I. No em dashes. Answer briefly, lead with the conclusion, and say plainly what is verified and what is not.

Deliver in this order: (1) the filled spec sheet in the pillar doc with the reference frame and its evidence tier (published study, then price or migration proxy, then survey); (2) an audit gap table with a recommended fix and expected score impact; (3) options with one recommendation; (4) after approval, the change with tests, a catalog recompute into new files only, and the diff for my review; (5) the Level 2 checks: pin-shift, all-places check, launch pairs, and independent validation (written up as a brief for another agent to run, with pass criteria fixed first); (6) results recorded in the spec sheet and a proposed level for my sign-off. Take shared place facts from the place context and add any new shared fact there (principles 13 to 17).

## Pillar specifics

| Pillar | Doc | Specifics to add to the prompt |
|---|---|---|
| Social fabric | SOCIAL_FABRIC | Reads a single tract at the pin; 1.2 multipliers are unsourced. Chetty et al. 2022 found economic connectedness predicts mobility and cohesion does not: audit which of our inputs map to it. |
| Economic security | ECONOMIC_SECURITY | Keep the gravity design (reachable job-market opportunity, not resident outcomes). Weights 0.40/0.15/0.20/0.25 are unsourced; document the commute-decay source. |
| Climate risk | CLIMATE_RISK | Fixed standard on physical hazard, not price response. Check source vintages and the pin-shift of each hazard layer. Air quality is already inside this pillar. |
| Air travel | AIR_TRAVEL | Evidence gap: do a targeted search first. Score service reachable within a drive-time decay (nonstop destinations, frequency), not distance alone. |
| Community safety | COMMUNITY_SAFETY | An audit exists (commit 81708ff, analysis/). Write the spec sheet from it. Crime-type check before any rescore; decide absolute versus relative rates. |
| Housing value | HOUSING_VALUE | Audits exist in analysis/audit_housing_d14*. Write the spec sheet; frame is income-relative cost burden. Pooled-tract change shipped 2026-10-28. |
| Diversity | DIVERSITY | Audits exist in analysis/audit_diversity*. Decide whether it should be a single-direction score or opt-in and preference-weighted; write the spec sheet. |
| Quality education | QUALITY_EDUCATION | Spec sheet exists but has no reference frame. Decisions already made: assigned-school construct, state percentile, equal weight, early-ed gets 0 points. |
| Active outdoors | ACTIVE_OUTDOORS | Converted for parks, playgrounds and trails but has no spec sheet. Open: facilities term (3 points, needs a fresh facility read, ask first), water multipliers, nearest-park radius still by area type, pin-shift and validation. |

Built environment is an opt-in filter, not a pillar; skip it unless the owner asks.
