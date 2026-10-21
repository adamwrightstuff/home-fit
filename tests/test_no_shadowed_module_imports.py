"""A name imported at module level must not also be imported inside a function that uses it earlier.

Python makes the name local to the whole function, so the early use raises UnboundLocalError. This crashed
natural_beauty (`osm_api`) for any place with no tree canopy data, found while scoring Las Vegas.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted(list((ROOT / "pillars").glob("*.py")) + list((ROOT / "data_sources").glob("*.py")))


def _module_level_names(tree: ast.Module) -> set:
    names = set()
    for n in tree.body:
        if isinstance(n, ast.ImportFrom):
            names |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.Import):
            names |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return names


def shadowed(path: Path):
    tree = ast.parse(path.read_text())
    top = _module_level_names(tree)
    bad = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        local = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    nm = a.asname or a.name
                    if nm in top:
                        local[nm] = min(local.get(nm, 10**9), n.lineno)
        for nm, first_import in local.items():
            uses = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == nm and n.lineno < first_import]
            if uses:
                bad.append((fn.name, nm, first_import, uses[:3]))
    return bad


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_function_shadows_a_module_import_it_uses_earlier(path):
    assert shadowed(path) == []
