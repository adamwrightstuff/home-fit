"""Metro expansion agent: preflight checks and failure-cause reporting.

See docs/METRO_EXPANSION_PLAYBOOK.md.  Run with:
    PYTHONPATH=. python -m scripts.metro_agent preflight --metro austin --csv data/austin_metro_place_catalog.csv
    PYTHONPATH=. python -m scripts.metro_agent diagnose --input data/austin_metro_place_catalog_scores_merged.composites_recomputed.jsonl
"""
