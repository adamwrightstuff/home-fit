"""Load the pure scoring functions from pillars/housing_value.py WITHOUT importing the module
(importing pulls in data_sources, which initialises Earth Engine and other services)."""
import ast, sys
from typing import Optional, Dict, Tuple

_src = open(sys.argv[1] + '/pillars/housing_value.py').read()
_tree = ast.parse(_src)
_want = {'_score_rent_affordability', '_score_local_affordability', '_score_space', '_score_value_efficiency'}
_ns = {'Optional': Optional, 'Dict': Dict, 'Tuple': Tuple}
for n in _tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in _want:
        exec(compile(ast.Module([n], []), 'hv', 'exec'), _ns)
rent_aff = _ns['_score_rent_affordability']
own_aff = _ns['_score_local_affordability']
space = _ns['_score_space']
_eff = _ns['_score_value_efficiency']


def efficiency(value, rooms, adj):
    """adj is the metro multiplier (1.0, 1.3, 1.5) the pillar applies via regional_baseline_manager."""
    # replicate by monkeypatching: call with metro_name None then rescale thresholds via a local copy
    if value is None or not rooms or rooms <= 0 or value <= 0:
        return None
    r = (rooms / value) * 100000
    ex, go, mo = 0.5 * adj, 0.2 * adj, 0.1 * adj
    if r >= ex:
        if r >= 1.0:
            return 20.0
        rs = 1.0 - ex
        return 18.0 + 2.0 * min(1.0, (r - ex) / rs) if rs > 0 else 18.0
    if r >= go:
        return 14.0 + 4.0 * (r - go) / (ex - go)
    if r >= mo:
        return 10.0 + 4.0 * (r - mo) / (go - mo)
    return 10.0 * min(1.0, r / mo) if r > 0 else 0.0


def score(v, inc, rooms, rent, rp, adj):
    """Returns (total, aff, space, eff) following get_housing_value_score branch logic; None if not scoreable."""
    ow = (1 - rp) if rp is not None else None
    has_rent = rent is not None and rent > 0
    has_val = v is not None
    if has_val and has_rent and ow is not None:
        oa, ra = own_aff(v, inc), rent_aff(rent, inc)
        aff = ow * oa + rp * ra if oa is not None and ra is not None else None
        sp = space(rooms)
        e = efficiency(v, rooms, adj)
        eff = e * ow if e is not None else None
    elif (not has_val) and has_rent:
        aff = rent_aff(rent, inc)
        sp = space(rooms)
        eff = 0.0 if sp is not None else None
    else:
        aff = own_aff(v, inc)
        sp = space(rooms)
        eff = efficiency(v, rooms, adj)
    comps = {'a': (aff, 50.0), 's': (sp, 30.0), 'e': (eff, 20.0)}
    pres = {k: x for k, x in comps.items() if x[0] is not None}
    if 'a' not in pres or len(pres) < 2:
        return None, aff, sp, eff
    tot = sum(x[0] for x in pres.values()) * (100.0 / sum(x[1] for x in pres.values()))
    return tot, aff, sp, eff
