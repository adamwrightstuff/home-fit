# Trovamo UX principles (DRAFT for owner edit, 2026-11-05)

Source: the owner's six rules from an internal workflow tool, inspired by Airbnb and Canva. They are design conventions, not research findings. Nothing here is evidence-backed and nothing is audited except where noted. Nothing here changes code.

How this sits beside DPv2: DPv2 governs whether a number is right. These govern whether the person using Trovamo can find, set and trust it. A feature should pass both.

## The rules, as they apply to Trovamo

1. **One primary action per state.** Each screen state has one obvious next step: on search, run the search; on a results list, open a place; on a place page, save or compare. Everything else is visibly secondary.
2. **One home per action.** A setting is changed in exactly one place and every other surface reads it and links back. Example to audit: work address, commute mode and office days are edited on the profile page, but the filter sheet has its own "Commute over" control and the priorities have a separate commute level. That is three homes for commute (read from code 2026-11-05, not yet fixed).
3. **Controls follow selection.** Controls that only make sense after a choice appear after that choice: office days and commute mode after a work address; a school preference after a family filter; a custom weight after a pillar is switched on. Nothing greyed out waiting.
4. **Quiet by default.** A new visitor sees the score and a few clear facts. Personal layers (commute, people, income, preferences) are off until chosen and show only on the cards they change. Warnings and data limits show on the place they affect, not on every card. Defaults match what the evidence supports for most people (for example commute priority None).
5. **Start from a suggestion.** Offer a sensible starting point the user can accept or change: the nearest work hub for a typed address, a preset set of priorities, a suggested place list. The user should never face an empty form.
6. **Search finds, panels edit.** The search box locates a place, hub or metro and nothing else. Changing weights, filters and personal settings happens in a panel or page built for editing, not in the search results.

## Candidate additions (not from the owner, for discussion)
- **Say what a number means in the place it appears.** Each score says its basis in one line (for example "to the nearest of 12 hubs, 3.2 mi from your address"). This is DPv2 principle 11 shown in the interface.
- **No silent gaps.** If a number is missing, show "no data" or "no route" with the reason, never a blank or a neutral value (DPv2 principle 9 shown in the interface).

## Worked example: commute time
- One home: move work address, mode and office days to the profile page only; the filter sheet shows the current hub and links back.
- Controls follow selection: show mode and office days only when a work address is set.
- Quiet: commute stays off by default; "no route" label only on the affected card.
- Suggestion: the picker already snaps a typed address to the nearest hub and says how far it is.
- Search finds: the work picker finds a hub; it does not edit weights.
Audit of the other controls and pages against these rules has not been done.
