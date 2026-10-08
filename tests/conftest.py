"""Pytest config: these two files are standalone scripts (they exit at import and need live services),
not pytest tests. Run them directly with python."""

collect_ignore = ["test_natural_beauty_regression.py", "test_built_beauty_golden_set.py"]
