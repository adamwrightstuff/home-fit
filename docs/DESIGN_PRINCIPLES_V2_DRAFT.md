# HomeFit Design Principles v2 (DRAFT, local only)

Status: proposal for review. Not yet merged into `DESIGN_PRINCIPLES.md`. Nothing here changes scoring.

v2 keeps v1 principles 1 to 6 (research-backed, objective, scalable, transparent, smooth, area-type context) and adds the rules below. Where v2 conflicts with v1, v2 wins and v1 should be edited.

## Part 1: Principles

### A. Define the pillar

1. **Declare the reference frame.** Say whether people judge this thing against a fixed standard (criterion-referenced), the nation (national norm), or similar places (area-type or metro norm), and cite evidence for the choice. Default expectation: harm and physical-cost pillars (safety, air and flood risk, healthcare access, school proficiency, transit time) use fixed standards. Pillars people adapt to or read socially (housing value, economic position, amenities, diversity, beauty) may use peer norms. Area-type baselines are a peer-norm choice, not a neutral default.
2. **State the construct in one sentence.** Access, exposure, resident outcomes, or opportunity. Example: economic security measures reachable job-market opportunity, not resident outcomes.
3. **Choose the measurement area from lived experience.** Access pillars use a reachable-distance standard such as a walk-time radius. Pillars describing the people living there use an area a resident would call their neighborhood. A pin plus a circle is a design choice and needs a stated reason.

### B. Build the number

4. **Every weight, threshold, and curve parameter has a source and a recorded range.** Source is a citation or a documented fit (see the Ridge addendum in v1). The range is how far it could plausibly move given the evidence. A number with no source is a TODO, not a parameter.
5. **No double counting across pillars.** Pillars are independent in code but can proxy the same thing (income inside both housing and economic security). Document shared inputs and test the composite for the overlap.

### C. Test it

6. **Test sensitivity.** Shift the pin, change the radius, perturb each weight across its recorded range. Report how far scores move. Pillars that read one census tract at the pin are the likeliest to be unstable.
7. **Validate against an independent source matched to the frame.** Safety: police precinct data. Transit: timetables. Schools: state data. Perceptual pillars (beauty): human-rating rank correlation, Spearman 0.7 or higher on 15+ places. Regression tests guard stability only and do not count as validation.
8. **Test across all places before adopting any change.** A complaint about one place is a prompt to investigate, not evidence. Run every candidate change on the full catalog and report who moves and why.

### D. Ship it safely

9. **Fail loudly, then keep trying.** Decided 2026-10-24. Missing or broken required data means the pillar shows "no data" and drops out of the headline (weight redistributed); a missing optional piece means score from the rest, marked degraded with the reason; impossible values count as failure. Never substitute a neutral or hard-coded value. Failed pillars are queued for retry and backfill until data arrives. A believable wrong number is worse than a null.
10. **Launch check: do places that should differ actually differ?** Define pairs or groups with known differences before scoring. Also check for floor and ceiling clumping and report spread by area type.
11. **Disclose data limits.** Record coverage, vintage, and sampling bias per pillar (FBI agency sample, OSM sparsity in rural areas). Surface them as confidence in the API response.
12. **Re-validate on a schedule.** When a source changes or quarterly, whichever is first. Includes checking the live scorer against the catalog (see `docs/LIVE_SCORER_VS_EXPLORER.md`).

## Part 2: Pillar spec sheet (one per pillar)

Copy this block into each pillar's doc and fill every field. "Unknown" is an allowed answer and becomes an audit finding.

```
Pillar:
Construct (one sentence):
Reference frame: fixed standard | national norm | area-type norm | metro norm
  Evidence for the frame (tier 1 published study | tier 2 revealed-preference proxy | tier 3 survey):
Measurement area: pin + radius | walk-time | tract | place | other
  Reason:
Inputs and data sources (with vintage):
Parameters:
  name | value | source | plausible range | sensitivity result
Shared inputs with other pillars:
Pin-shift sensitivity (shift distance, median and p95 score change):
Independent validation source and result:
All-places check (date, n, summary):
Fail-loud conditions (what is rejected, what is flagged):
Launch check pairs (should differ / should be similar) and result:
Known data limits:
Last re-validated:
```

## Part 3: Audit order (proposed)

Read-only audit, output is a gap table per pillar with recommended fix and expected score impact. No code or catalog changes.

1. Pillars reading a single tract at the pin: housing value, diversity, social fabric.
2. Pillars with known unsourced weights: amenities (60/40 split), economic security (0.40/0.15/0.20/0.25), education bonuses, social fabric (1.2 multipliers).
3. Access pillars: transit, healthcare, active outdoors, amenities (measurement area check).
4. Remaining pillars: climate risk, natural beauty, built environment, air travel.
5. Community safety last, since it already went through most of this process and serves as the worked example.

## Part 4: Provisional reference frames (for owner approval)

Method: one standard web search per topic, read from search summaries only, not the full papers. Tiers: 1 published study, 2 revealed-preference proxy, 3 survey. "Unverified" means I did not see the source for that claim. Every row is a recommendation to approve or overrule, not a finding.

| Pillar | Provisional frame | Tier | What the evidence says | Caveat |
|---|---|---|---|---|
| Community safety | Fixed standard (absolute exposure to harm) | 2 | Hedonic work (Bartley 2000, DOJ) shows people pay for lower crime rates | I did not confirm whether prices respond to absolute or relative rates (Gibbons 2004 not retrieved). The current national-share score is a norm-based proxy for an absolute risk; keep it only if we say why |
| Climate risk | Fixed standard (absolute hazard) | 2 | Flood-risk discounts exist but are small and depend on disclosure (3.3% "extreme" vs "severe", 8% UK, larger where sellers must disclose) | Prices respond to salience, so markets under-price the hazard; frame by physical risk, not price response |
| Healthcare | Fixed standard with distance decay | 1 | Mortality rises with drive time to capable hospitals; ER closure effects largest at 30+ added minutes | No universal 30-minute cutoff; effect depends on condition and hospital capability. Do not hard-code 30 |
| Public transit | Fixed standard with distance decay | 1 | 400 m bus and 800 m rail are planning conventions; observed 85th percentile walks were ~524 m bus and ~1,259 m commuter rail (Montreal) | Willingness to walk varies by service type; a decay curve beats a cutoff |
| Active outdoors | Fixed access standard with decay | 1 | 800 m is a common benchmark; results are mixed and park size can matter more than proximity | Not a validated cutoff; consider park size as a second input |
| Neighborhood amenities | Hybrid: fixed walk-time access, expectations by area type | 2 | Amenity-rich cities grew faster (Glaeser, Kolko, Saiz 2001) | No evidence found that people grade amenity counts against peer places; the area-type expectation is unsupported so far |
| Education | Relative (standardized rank within state) | 2 | Capitalization studies use standardized test scores; ~2% price per 5% score (Black 1999), under 4% per SD in later fixed-effects work | Evidence supports relative standing, not an absolute proficiency bar. Possible nonlinearity at the bottom |
| Housing value | Income-relative cost burden (local income, not a peer norm) | 1 | Ratio (30% of income) and residual-income measures are the standard approaches and disagree on who is burdened (CRS) | No consensus. Median multiple is a relative measure and is the most conservative |
| Economic security | Absolute opportunity, no peer norm | 1 | Neighbors' income effects on wellbeing are mixed (Luttmer 2005 negative; Deaton and Stone find little at city level) | Relative-income evidence is about happiness, not about job-market opportunity. Evidence for this construct's frame is weak |
| Social fabric | Outcome-linked absolute, check our inputs | 1 | Chetty et al. 2022: economic connectedness predicts upward mobility; cohesion and civic engagement do not | Our inputs may be the weakly predictive ones. Audit which of ours map to economic connectedness |
| Diversity | No fixed good or bad; preference-dependent | 1 | White preferences respond continuously to minority share (Bruch and Mare); tipping points reported at 5% to 20% | Likely should not be a single-direction score; consider making it opt-in or preference-weighted |
| Natural beauty | Shared absolute scale, validated by human ratings | 1 | Cross-cultural landscape preference agreement is high (r 0.76 to 0.89 Australia vs US) | Samples skew urban and Western; subgroup differences exist; test across subgroups |
| Air travel | Fixed access (time to airport and service level) | none | Found only noise and proximity hedonics with conflicting signs; nothing pricing flight frequency or destinations | Evidence gap. Needs a targeted search before this pillar's frame is defended |

### Part 4b: Deeper pass on the four weakest rows

Same method, extended searches, still read from summaries. These supersede the rows above for these four pillars.

| Pillar | Revised frame | Tier | New evidence | Remaining gap |
|---|---|---|---|---|
| Community safety | Fixed standard, measured risk (not perceived safety), by crime type | 1 and 2 | Gibbons 2004 (London): criminal damage density lowers prices (a tenth of an SD lower adds ~1% in Inner London); burglary showed no measurable price effect. Perceived crime often outruns measured crime and tracks physical disorder and demographics | Still no direct test of absolute vs relative rates. Type matters: check whether our Part I composite weights crimes the way residents' choices imply. State in the spec that the score measures risk, not felt safety |
| Economic security | Absolute opportunity with commute-time decay, no peer norm | 1 | Moretti: large labor markets attract workers (more potential employers, better for specialized couples); commute time sharply reduces the estimated agglomeration wage gain; housing constraints block movers | No study found that estimates a market-potential model as a migration predictor. Chetty and Hendren show place effects on children's earnings, which is mobility, not job access |
| Neighborhood amenities | Fixed walk-time access, valuing variety; drop or justify area-type expectations | 1 | Couture and Handbury: walking-time restaurant and nightlife density explains young college graduates' urban location choices about as much as jobs, schools, and housing cost; a welfare paper finds variety effects drive much of the welfare gap | Evidence is for young college graduates. Still no support for grading counts against peer places |
| Air travel | Fixed access: drive time to an airport, weighted by service (nonstop destinations, frequency) | 1 | Brueckner 2003: 10% more enplanements ~1% more service employment; a European study finds gains within ~60 km. Airport choice studies: access time dominates, most for business travelers, but people drive farther for the nonstop they want | Distance-only scoring is not supported. Common 2-hour catchment is arbitrary. Elasticities are region-specific |

Implications for the audit: safety needs a crime-type check before any rescore; economic security should keep its gravity design and document the commute decay source; amenities need either evidence for the area-type expectation or removal of it; air travel should be scored on service reachable within a drive-time decay, not distance alone.

Patterns worth your attention: three pillars (education, housing value, diversity) look more relative or preference-dependent than the doc assumed, and four (economic security, amenities, air travel, community safety) have a gap between the frame I'd propose and the evidence I found.

## Open decisions for the owner

1. Which pillars get a fixed standard versus a peer norm, once evidence is gathered per pillar.
2. DECIDED: frame evidence is taken in order of preference. First a published study, then a revealed-preference proxy (migration, price premiums), then a user survey only if neither is available. Record which tier supported each pillar's frame.
3. Audit order and who signs off a pillar as compliant.
