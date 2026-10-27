# Public transit: DPv2 status (2026-10-26)

Spec sheet is in `docs/PILLAR_TRANSIT.md`; audit in `analysis/audit_transit_2026-10-25.md`. "Judgment" means a number with no source, recorded with its measured range.

| Principle | Status | Evidence |
|---|---|---|
| P1 frame | Partial | Fixed standard with decay is the frame (tier 1 walking studies, summaries only); implemented as a hard circle with no decay |
| P2 construct | Met (stated) | Access to transit service near home; commute removed from the score |
| P3 measurement area | Open | 1.5 to 3 km radii are judgment and exceed published walks (0.33 to 1.0 mi). Published catchments tested and not adopted (within-metro worse, pin shift worse) |
| P4 sourced weights | Met as documented judgment | Subway, light rail, bus, anchor and radius are judgments with ranges; commuter rail 3 is a documented fit (range 2 to 4) |
| P5 double counting | Met | Commute counted once (Happiness); removed from this score |
| P6 sensitivity | Partial | Weights measured; pin shift p95 9.6 points, above the 5-point gate, recorded as a known limitation |
| P7 validation | Met with caveat | ACS transit share (0.691) and no-vehicle (0.609) across 1,471 places; not timetables |
| P8 all-places check | Met | All 1,476 places recomputed; 440 moved more than 5 |
| P9 fail loud | Met | Failed reads raise; fallbacks removed; 273 zero and fallback places re-read, 269 confirmed no service, 4 had service |
| P10 launch check | Met | Launch check PASS, gap +56.1 vs 20 |
| P11 disclose limits | Partial | Limits are in the doc; confirmed zeros still carry confidence 0 in the API response |
| P12 re-validate | Met | Quarterly (next 2027-01-26) with commands in the spec sheet; live vs catalog still manual |

## Open
Pin-shift instability (P6), radius (P3), no decay curve (P1), no timetable validation (P7, would need a national stop-frequency table), confidence 0 on confirmed zeros (P11).

## Owner sign-off
Not yet given.
