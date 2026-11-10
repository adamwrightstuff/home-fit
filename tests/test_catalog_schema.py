"""The served catalog files carry only keys the app uses (pillar_registry is the source of truth)."""
import glob
import json
import unittest

from pillar_registry import PRIORITY_KEYS


class CatalogSchemaTest(unittest.TestCase):
    def test_pillar_keys_are_registered(self):
        files = glob.glob("data/*_merged.composites_recomputed.jsonl")
        self.assertTrue(files)
        for f in files:
            with open(f) as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    s = json.loads(line)["score"]
                    for section in ("livability_pillars", "total_score_breakdown"):
                        extra = set(s.get(section) or {}) - set(PRIORITY_KEYS)
                        self.assertFalse(extra, f"{f} {section} has unregistered keys {extra}")


if __name__ == "__main__":
    unittest.main()
