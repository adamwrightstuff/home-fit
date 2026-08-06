"""
Climate preference scoring.

Maps a user's weather preferences (4 axes) onto a 0-100 match score
for any place that has a NASA POWER climate profile.

Preference schema
-----------------
{
    "cold_tolerance":  "dealbreaker" | "tolerable" | "love",
    "heat_tolerance":  "dealbreaker" | "fine"       | "love",
    "rain_tolerance":  "dealbreaker" | "meh"        | "vibe",
    "seasons":         "want_4"      | "mild_ok"    | "want_consistency",
}

Any key can be omitted — omitted axes are excluded from the score.

Score
-----
Each active axis contributes 0-100. Overall is the mean of active axes.
A missing climate profile returns None.
"""

from typing import Optional


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _linear(val: float, bad: float, good: float) -> float:
    """Map val linearly from bad→0 to good→100, clamped."""
    if good == bad:
        return 50.0
    raw = (val - bad) / (good - bad) * 100.0
    return _clamp(raw, 0.0, 100.0)


def _axis_cold(jan_f: float, pref: str) -> float:
    """Score cold-winter preference. bad=cold (10°F), good=mild (50°F)."""
    if pref == "tolerable":
        return 50.0
    if pref == "dealbreaker":        # hates cold → mild winters score high
        return _linear(jan_f, bad=35.0, good=52.0)
    if pref == "love":               # loves cold → cold winters score high
        return _linear(jan_f, bad=45.0, good=20.0)
    return 50.0


def _axis_heat(jul_f: float, pref: str) -> float:
    """Score summer-heat preference. range: 56°F–93°F."""
    if pref == "fine":
        return 50.0
    if pref == "dealbreaker":        # hates heat → cool summers score high
        return _linear(jul_f, bad=80.0, good=65.0)
    if pref == "love":               # loves heat → hot summers score high
        return _linear(jul_f, bad=70.0, good=85.0)
    return 50.0


def _axis_rain(avg_solar: float, annual_precip_in: float, pref: str) -> float:
    """
    Score rain/grey preference.
    Grey index = 0 (sunny/dry) → 1 (grey/wet), derived from solar + precip.
    """
    if pref == "meh":
        return 50.0
    # Solar: 3.4 (grey) → 5.8 (sunny); normalize to 0-1 sunny
    solar_norm = _clamp((avg_solar - 3.4) / (5.8 - 3.4), 0.0, 1.0)
    # Precip: 6in (dry) → 55in (wet); normalize to 0-1 wet
    precip_norm = _clamp((annual_precip_in - 6.0) / (55.0 - 6.0), 0.0, 1.0)
    # Grey index (higher = greyer, wetter)
    grey = 0.6 * (1.0 - solar_norm) + 0.4 * precip_norm
    if pref == "dealbreaker":        # hates grey/rain → sunny/dry scores high
        return _clamp((1.0 - grey) * 100.0, 0.0, 100.0)
    if pref == "vibe":               # loves grey/rain → grey/wet scores high
        return _clamp(grey * 100.0, 0.0, 100.0)
    return 50.0


def _axis_seasons(swing_f: float, pref: str) -> float:
    """Score seasonal-variation preference. swing = Jul mean - Jan mean."""
    if pref == "mild_ok":
        return 50.0
    if pref == "want_4":             # wants big seasons → high swing scores high
        return _linear(swing_f, bad=18.0, good=40.0)
    if pref == "want_consistency":   # wants year-round consistency → low swing scores high
        return _linear(swing_f, bad=30.0, good=10.0)
    return 50.0


def score_climate_match(
    climate: Optional[dict],
    prefs: dict,
) -> Optional[dict]:
    """
    Score a NASA POWER climate profile against user preferences.

    Args:
        climate: dict with 'months' list (from catalog_climate_profiles.jsonl)
        prefs:   dict with keys cold_tolerance, heat_tolerance, rain_tolerance, seasons

    Returns:
        {score: 0-100, axes: {cold_winter, summer_heat, rain_grey, seasonal}} or None
    """
    if not climate or not climate.get("months"):
        return None

    months = climate["months"]
    by_month = {m["month"]: m for m in months}

    jan_f = by_month.get(1, {}).get("avg_temp_f")
    jul_f = by_month.get(7, {}).get("avg_temp_f")
    if jan_f is None or jul_f is None:
        return None

    annual_precip = sum(m.get("avg_precip_in", 0.0) or 0.0 for m in months)
    solar_vals = [m.get("solar_kwh_m2_day") for m in months if m.get("solar_kwh_m2_day") is not None]
    avg_solar = sum(solar_vals) / len(solar_vals) if solar_vals else 4.5
    swing = jul_f - jan_f

    axes = {}

    if "cold_tolerance" in prefs:
        axes["cold_winter"] = round(_axis_cold(jan_f, prefs["cold_tolerance"]), 1)

    if "heat_tolerance" in prefs:
        axes["summer_heat"] = round(_axis_heat(jul_f, prefs["heat_tolerance"]), 1)

    if "rain_tolerance" in prefs:
        axes["rain_grey"] = round(_axis_rain(avg_solar, annual_precip, prefs["rain_tolerance"]), 1)

    if "seasons" in prefs:
        axes["seasonal"] = round(_axis_seasons(swing, prefs["seasons"]), 1)

    if not axes:
        return None

    overall = round(sum(axes.values()) / len(axes), 1)
    return {"score": overall, "axes": axes}


def load_climate_index(path: str = "data/catalog_climate_profiles.jsonl") -> dict:
    """Load climate profiles into a dict keyed by (name, source)."""
    import json
    index = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            index[(r["name"], r["source"])] = r.get("climate")
    return index
