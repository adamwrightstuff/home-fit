# `scripts/`

- **Documented admin flows:** [docs/ADMIN_TOOLS.md](../docs/ADMIN_TOOLS.md) (scoring batches, health checks, baseline rebuilds).
- **One-off / diagnostic tools:** [DEV_SCRIPTS.md](./DEV_SCRIPTS.md) (everything else, grouped by purpose).
- **Automation:** GitHub Actions run `collector.py` and `collect_active_outdoors.py`; Railway build uses `build_nrhp_db.py` (see `railway.json`).

Run Python scripts from the **repository root** with `PYTHONPATH=.` unless the script docstring says otherwise.
