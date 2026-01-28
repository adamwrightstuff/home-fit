import csv
import math
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _clamp01(x: float) -> float:
    return _clamp(x, 0.0, 1.0)


def _relu(x: float) -> float:
    return x if x > 0 else 0.0


def _gauss(x: float, mu: float, sigma: float) -> float:
    """Gaussian bump in [0,1] centered at mu."""
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-(z * z))


def _sat01(x: float, cap: float) -> float:
    """Saturating linear 0..cap -> 0..1, then flat."""
    if cap <= 0:
        return 0.0
    return _clamp01(x / cap)


def _compute_feature_bundle(row: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute normalized features + interpretable proxies from the existing metrics.
    This lets us tune weights without changing feature definitions.
    """
    # Existing features
    height = float(row.get("height_diversity") or 0.0)
    typ = float(row.get("type_diversity") or 0.0)
    foot = float(row.get("footprint_variation") or 0.0)
    cov = float(row.get("built_coverage") or 0.0)

    # Normalize
    h = _clamp01(height / 100.0)
    t = _clamp01(typ / 100.0)
    f = _clamp01(foot / 100.0)
    c = _clamp01(cov)  # already 0-1

    # 1) Diminishing returns on raw "diversity"
    h_div = _sat01(min(h, 0.60), 0.60)
    t_div = _sat01(min(t, 0.55), 0.55)
    f_div = _sat01(min(f, 0.70), 0.70)

    variety = 0.45 * h_div + 0.40 * t_div + 0.15 * f_div  # 0..1 (bounded)

    # 2) Coherence / fine-grain historic fabric proxies
    # Pleasant coverage bands (historic districts can be "spacious" and still beautiful)
    cov_mid = _gauss(c, mu=0.22, sigma=0.10)      # typical walkable urban fabric
    cov_spacious = _gauss(c, mu=0.14, sigma=0.07) # historic plazas/courtyards / low-coverage cores
    coverage_pleasant = max(cov_mid, cov_spacious)

    # Historic-fabric bands:
    # - "Rowhouse historic": low height/type diversity but very coherent fabric (Brooklyn Heights, Savannah squares)
    # - "Organic historic": high footprint variation but still coherent (Beacon Hill / older mixed cores)
    rowhouse_hist = (
        _gauss(h, mu=0.14, sigma=0.14) *
        _gauss(t, mu=0.22, sigma=0.18) *
        _gauss(f, mu=0.88, sigma=0.14) *
        cov_mid
    )
    # "Organic historic" should be harder to trigger in low-rise sprawl. We bias it toward
    # places with meaningful height mix and moderate mixed-use.
    organic_hist = (
        _gauss(h, mu=0.50, sigma=0.22) *
        _gauss(t, mu=0.38, sigma=0.22) *
        _gauss(f, mu=0.90, sigma=0.12) *
        max(cov_mid, _gauss(c, mu=0.18, sigma=0.10))
    )
    spacious_hist = (
        _gauss(h, mu=0.22, sigma=0.22) *
        _gauss(t, mu=0.30, sigma=0.22) *
        _gauss(f, mu=0.92, sigma=0.10) *
        cov_spacious
    )

    # Mixed-use historic cores with lower coverage (Charleston) and "village mixed" (German Village)
    mixed_use_hist = (
        _gauss(h, mu=0.70, sigma=0.22) *
        _gauss(t, mu=0.60, sigma=0.22) *
        _gauss(f, mu=0.78, sigma=0.20) *
        coverage_pleasant
    )
    village_mixed = (
        _gauss(h, mu=0.12, sigma=0.14) *
        _gauss(t, mu=0.55, sigma=0.22) *
        _gauss(f, mu=0.90, sigma=0.14) *
        max(_gauss(c, mu=0.18, sigma=0.08), cov_mid)
    )

    historic_fabric = max(rowhouse_hist, organic_hist, spacious_hist, mixed_use_hist, village_mixed)

    # Cozy/charming low-diversity band (Carmel/Seaside/Litchfield patterns)
    cozy_height = _gauss(h, mu=0.05, sigma=0.12)
    cozy_type = _gauss(t, mu=0.16, sigma=0.22)
    cozy_foot = _gauss(f, mu=0.32, sigma=0.28)
    cozy_cov = max(_gauss(c, mu=0.10, sigma=0.08), _gauss(c, mu=0.05, sigma=0.05))
    cozy_charm = cozy_height * cozy_type * cozy_foot * cozy_cov  # 0..1

    # 3) Penalize auto-oriented / megaproject patterns using proxies
    # Proxy: high footprint variation + low coverage often indicates parking lots / large paved voids.
    parking_void_proxy = _relu((0.20 - c) / 0.20) * _relu((f - 0.70) / 0.30)  # 0..~1

    # Proxy: "complex but unpleasant" megaprojects (Hudson Yards): high coverage + very high footprint variety
    # plus low type diversity (single-use enclave) → penalty.
    megaproject_proxy = _relu((c - 0.26) / 0.22) * _relu((f - 0.82) / 0.18) * _relu((0.30 - t) / 0.30)

    # Proxy: strip development (lots of "types" + low coverage + high footprint variety).
    strip_proxy = _relu((t - 0.35) / 0.65) * _relu((0.20 - c) / 0.20) * _relu((f - 0.55) / 0.45)

    # Proxy: low-rise + moderate type diversity + moderate coverage tends to be "sprawl complexity"
    # (big boxes, arterials, parking) even if the footprint metric isn't extreme.
    lowrise_sprawl_proxy = (
        _relu((0.14 - h) / 0.14) *
        _relu((t - 0.18) / 0.82) *
        _relu((c - 0.10) / 0.25)
    )

    # If user supplies ParkingFraction later, use it directly.
    parking_fraction = row.get("ParkingFraction")
    parking_frac_0_1 = None
    if parking_fraction is not None:
        try:
            pf = _clamp01(float(parking_fraction))
            parking_frac_0_1 = pf
            parking_void_proxy = max(parking_void_proxy, pf)
        except (TypeError, ValueError):
            pass

    # Block size / street width / frontage proxies (optional)
    block_size = row.get("BlockSize")
    street_wh = row.get("StreetWidthToHeight")
    frontage_cont = row.get("FrontageContinuity")
    if block_size is not None:
        try:
            bs = float(block_size)
            # >180m blocks start to feel auto-oriented; >300m is severe.
            # Soften: treat block size as a strong signal but don't immediately force max penalty.
            megaproject_proxy = max(megaproject_proxy, 0.75 * _clamp01((bs - 180.0) / 160.0))
        except (TypeError, ValueError):
            pass
    if street_wh is not None:
        try:
            swh = float(street_wh)
            # >1.5 starts feeling wide; >2.5 is severe.
            # Soften: wide streets hurt a lot, but avoid saturating to 1.0 too easily.
            parking_void_proxy = max(parking_void_proxy, 0.8 * _clamp01((swh - 1.6) / 1.4))
        except (TypeError, ValueError):
            pass
    if frontage_cont is not None:
        try:
            fc = _clamp01(float(frontage_cont) / 100.0)
            # Low frontage continuity should amplify auto penalties.
            strip_proxy *= (1.0 + (1.0 - fc) * 0.6)
            # High frontage continuity is a strong positive for historic/cozy fabric.
            historic_fabric = max(historic_fabric, 0.65 * fc * coverage_pleasant)
            # Cozy charm should require decent frontage continuity.
            cozy_charm *= (0.55 + 0.45 * fc)
        except (TypeError, ValueError):
            pass

    # Gate "cozy" and "historic" rewards by parking dominance when provided.
    # If ParkingFraction is high, it shouldn't look "cozy" no matter the low-diversity metrics.
    if parking_frac_0_1 is not None:
        cozy_gate = 1.0 - _clamp01((parking_frac_0_1 - 0.18) / 0.35)  # starts fading >18%, mostly gone >53%
        historic_gate = 1.0 - _clamp01((parking_frac_0_1 - 0.25) / 0.45)
        cozy_charm *= (0.35 + 0.65 * cozy_gate)
        historic_fabric *= (0.55 + 0.45 * historic_gate)

    # If user supplies a future explicit coherence metric, blend it in as a strong historic signal.
    historic_coherence_input = row.get("HistoricCoherence")
    if historic_coherence_input is not None:
        try:
            hc = _clamp01(float(historic_coherence_input) / 100.0)
            # Combine: either the heuristic historic proxy fires OR user-provided coherence does.
            historic_fabric = max(historic_fabric, hc)
        except (TypeError, ValueError):
            pass

    # Additional penalty: extremely high footprint variety is not automatically good (unless historic).
    extreme_foot = _relu((f - 0.92) / 0.08) * _clamp01((0.30 - c) / 0.30)

    return {
        "variety": variety,
        "historic_fabric": historic_fabric,
        "cozy_charm": cozy_charm,
        "parking_void": parking_void_proxy,
        "megaproject": megaproject_proxy,
        "strip": strip_proxy,
        "lowrise_sprawl": lowrise_sprawl_proxy,
        "extreme_foot": extreme_foot,
        # keep raw normalized for potential future use
        "h": h,
        "t": t,
        "f": f,
        "c": c,
    }


@dataclass(frozen=True)
class Weights:
    base: float
    w_variety: float
    w_historic: float
    w_cozy: float
    p_parking: float
    p_megaproject: float
    p_strip: float
    p_sprawl: float
    p_extreme_foot: float
    softcap_k: float  # controls saturation near 100


DEFAULT_WEIGHTS = Weights(
    base=32.0,
    w_variety=38.0,
    w_historic=52.0,
    w_cozy=52.0,
    p_parking=34.0,
    p_megaproject=60.0,
    p_strip=40.0,
    p_sprawl=34.0,
    p_extreme_foot=18.0,
    softcap_k=1.35,
)


def compute_beauty_score(row: Dict[str, Any], weights: Weights = DEFAULT_WEIGHTS) -> float:
    """
    Revised architectural beauty score (0–100).

    - **Reward historic coherence / fine-grain fabric**: `historic_fabric` proxy.
    - **Reward cute/cozy intentional uniformity**: `cozy_charm` proxy.
    - **Penalize car-dominant patterns**: parking/strip/low-rise sprawl proxies.
    - **Limit "diversity = good"**: variety is saturating and not dominant.
    """
    feats = _compute_feature_bundle(row)

    raw = (
        weights.base
        + weights.w_variety * feats["variety"]
        + weights.w_historic * feats["historic_fabric"]
        + weights.w_cozy * feats["cozy_charm"]
        - weights.p_parking * feats["parking_void"]
        - weights.p_megaproject * feats["megaproject"]
        - weights.p_strip * feats["strip"]
        - weights.p_sprawl * feats["lowrise_sprawl"]
        - weights.p_extreme_foot * feats["extreme_foot"]
    )

    # Soft cap: prevent maxing out at 100 too easily while keeping 0 stable.
    # Maps raw roughly into 0–100 with saturation near the top.
    x = raw / 100.0
    capped = 100.0 * (math.tanh(weights.softcap_k * x) / math.tanh(weights.softcap_k))
    return float(_clamp(capped, 0.0, 100.0))


@dataclass
class RowResult:
    name: str
    category: str
    expected_min: float
    expected_max: float
    old_score: float
    new_score: float

    @property
    def expected_mid(self) -> float:
        return (self.expected_min + self.expected_max) / 2.0

    @property
    def old_err(self) -> float:
        return self.old_score - self.expected_mid

    @property
    def new_err(self) -> float:
        return self.new_score - self.expected_mid


def _read_calibration_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, Any]] = []
        for r in reader:
            rows.append(r)
        return rows


def _norm_name_tokens(name: str) -> List[str]:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    parts = [p for p in s.split() if p]
    # Drop super-common noise tokens
    stop = {"district", "downtown", "town", "center", "area", "historic", "the", "of"}
    return [p for p in parts if p not in stop]


def _best_match_row(name: str, candidates: List[Dict[str, Any]], name_key: str) -> Optional[Dict[str, Any]]:
    """
    Very lightweight fuzzy match by token overlap (to merge enriched rows with
    the original metrics table).
    """
    toks = set(_norm_name_tokens(name))
    if not toks:
        return None
    best = None
    best_score = 0.0
    for c in candidates:
        ctoks = set(_norm_name_tokens(str(c.get(name_key) or "")))
        if not ctoks:
            continue
        overlap = len(toks & ctoks)
        denom = max(1, len(toks | ctoks))
        score = overlap / denom
        if score > best_score:
            best_score = score
            best = c
    # Require minimum similarity to avoid bad merges
    if best_score >= 0.35:
        return best
    return None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        s = str(value).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def main() -> None:
    # Prefer enriched calibration set when present.
    path = "analysis/arch_beauty_calibration_enriched.csv"
    rows = _read_calibration_csv(path)
    legacy_rows = _read_calibration_csv("analysis/arch_beauty_calibration.csv")

    parsed_rows: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for r in rows:
        # Merge in the original metrics (height/type/footprint/coverage) if missing in the enriched file.
        legacy = _best_match_row(str(r.get("name") or ""), legacy_rows, name_key="name")

        base_row = {
            # If you use the enriched schema, these fields may not exist yet.
            "height_diversity": _to_float(r.get("height_diversity")) or _to_float((legacy or {}).get("height_diversity")) or 0.0,
            "type_diversity": _to_float(r.get("type_diversity")) or _to_float((legacy or {}).get("type_diversity")) or 0.0,
            "footprint_variation": _to_float(r.get("footprint_variation")) or _to_float((legacy or {}).get("footprint_variation")) or 0.0,
            "built_coverage": _to_float(r.get("built_coverage")) or _to_float((legacy or {}).get("built_coverage")) or 0.0,
            # Optional placeholders (populate later)
            "ParkingFraction": _to_float(r.get("ParkingFraction"), default=0.0) if r.get("ParkingFraction") not in (None, "") else None,
            "BlockSize": _to_float(r.get("BlockSize"), default=0.0) if r.get("BlockSize") not in (None, "") else None,
            "StreetWidthToHeight": _to_float(r.get("StreetWidthToHeight"), default=0.0) if r.get("StreetWidthToHeight") not in (None, "") else None,
            "FrontageContinuity": _to_float(r.get("FrontageContinuity"), default=0.0) if r.get("FrontageContinuity") not in (None, "") else None,
            "HistoricCoherence": _to_float(r.get("HistoricCoherence"), default=0.0) if r.get("HistoricCoherence") not in (None, "") else None,
        }
        meta = {
            "name": str(r.get("name") or ""),
            "category": str(r.get("category") or ""),
            "old_score": _to_float(r.get("final_score")) or _to_float(r.get("actual_score")),
        }
        # Expected band: if the dataset provides min/max, use them; otherwise derive from expected_score ± 7.5.
        expected_min = _to_float(r.get("expected_min"), default=float("nan"))
        expected_max = _to_float(r.get("expected_max"), default=float("nan"))
        if math.isfinite(expected_min) and math.isfinite(expected_max) and expected_max > 0:
            meta["expected_min"] = expected_min
            meta["expected_max"] = expected_max
        else:
            exp = _to_float(r.get("expected_score"))
            meta["expected_min"] = _clamp(exp - 7.5, 0.0, 100.0)
            meta["expected_max"] = _clamp(exp + 7.5, 0.0, 100.0)

        parsed_rows.append((base_row, meta))

    # ------------------------------------------------------------
    # Quick calibration search over weights (no external deps).
    # Objective: fit expected bands while pushing ugly down and beautiful up.
    # ------------------------------------------------------------
    def objective(w: Weights) -> float:
        loss = 0.0
        for row, meta in parsed_rows:
            s = compute_beauty_score(row, weights=w)
            mid = (meta["expected_min"] + meta["expected_max"]) / 2.0
            # squared error to midpoint
            loss += (s - mid) ** 2
            # band penalty (asymmetric): beautiful should not be below min; ugly should not be above max
            cat = meta["category"]
            if cat.startswith("BEAUTIFUL"):
                if s < meta["expected_min"]:
                    loss += 10.0 * (meta["expected_min"] - s) ** 2
            if cat.startswith("UGLY"):
                if s > meta["expected_max"]:
                    loss += 20.0 * (s - meta["expected_max"]) ** 2
                # Also penalize collapsing uglies to 0 (we still want differentiation 15–30-ish).
                if s < meta["expected_min"]:
                    loss += 6.0 * (meta["expected_min"] - s) ** 2
            # mild penalty for out-of-band either direction
            if s < meta["expected_min"]:
                loss += 1.5 * (meta["expected_min"] - s) ** 2
            elif s > meta["expected_max"]:
                loss += 1.5 * (s - meta["expected_max"]) ** 2
        return loss / max(1, len(parsed_rows))

    best_w = DEFAULT_WEIGHTS
    best_loss = objective(best_w)

    rng = random.Random(42)
    for _ in range(25000):
        cand = Weights(
            base=rng.uniform(20.0, 45.0),
            w_variety=rng.uniform(20.0, 55.0),
            w_historic=rng.uniform(25.0, 85.0),
            w_cozy=rng.uniform(25.0, 90.0),
            p_parking=rng.uniform(20.0, 140.0),
            p_megaproject=rng.uniform(30.0, 160.0),
            p_strip=rng.uniform(20.0, 140.0),
            p_sprawl=rng.uniform(20.0, 140.0),
            p_extreme_foot=rng.uniform(0.0, 40.0),
            softcap_k=rng.uniform(0.9, 2.2),
        )
        cand_loss = objective(cand)
        if cand_loss < best_loss:
            best_loss = cand_loss
            best_w = cand

    print("Best weights found:")
    print(best_w)
    print(f"Objective: {best_loss:.2f}\n")

    results: List[RowResult] = []
    for row, meta in parsed_rows:
        new_score = compute_beauty_score(row, weights=best_w)
        results.append(
            RowResult(
                name=meta["name"],
                category=meta["category"],
                expected_min=meta["expected_min"],
                expected_max=meta["expected_max"],
                old_score=meta["old_score"],
                new_score=round(new_score, 1),
            )
        )

    # Sort by category then name for readability
    results.sort(key=lambda x: (x.category, x.name))

    # Print table
    print("name\tcategory\texpected\told\tnew\told_err\tnew_err")
    for rr in results:
        expected = f"{int(rr.expected_min)}-{int(rr.expected_max)}"
        print(
            f"{rr.name}\t{rr.category}\t{expected}\t"
            f"{rr.old_score:.0f}\t{rr.new_score:.1f}\t"
            f"{rr.old_err:+.1f}\t{rr.new_err:+.1f}"
        )

    # Summary stats
    def mae(vals: List[float]) -> float:
        return sum(abs(v) for v in vals) / max(1, len(vals))

    old_errs = [rr.old_err for rr in results]
    new_errs = [rr.new_err for rr in results]
    print("\nMAE vs expected midpoint:")
    print(f"- old: {mae(old_errs):.2f}")
    print(f"- new: {mae(new_errs):.2f}")

    # Band hit-rate
    def in_band(rr: RowResult, score: float) -> bool:
        return rr.expected_min <= score <= rr.expected_max

    old_hit = sum(1 for rr in results if in_band(rr, rr.old_score))
    new_hit = sum(1 for rr in results if in_band(rr, rr.new_score))
    print("\nIn-band count:")
    print(f"- old: {old_hit}/{len(results)}")
    print(f"- new: {new_hit}/{len(results)}")


if __name__ == "__main__":
    main()

