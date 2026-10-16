import gzip
import json

from data_sources import school_snapshot as ss


def _raw(name, did, charter="No", pct=50.0):
    return {"schoolid": name, "schoolName": name, "schoolLevel": "Elementary", "isCharterSchool": charter,
            "isPrivate": False, "district": {"districtID": did, "districtName": "D" + did},
            "address": {"city": "X", "zip": "1", "latLong": {"latitude": 1.0, "longitude": 2.0}},
            "rankHistory": [{"year": 2026, "rankStars": 3, "rankStatewidePercentage": pct, "rankMovement": 1, "extra": 1}],
            "schoolYearlyDetails": [{"pupilTeacherRatio": 12.0, "numberOfStudents": 300, "x": 1}], "junk": "drop me"}


def test_slim_keeps_scoring_fields_and_drops_the_rest():
    s = ss.slim(_raw("A", "1"))
    assert "junk" not in s and s["rankHistory"][0] == {"year": 2026, "rankStars": 3, "rankStatewidePercentage": 50.0, "rankMovement": 1}
    assert s["address"]["latLong"] == {"latitude": 1.0, "longitude": 2.0} and s["district"]["districtID"] == "1"


def test_load_state_indexes_districts_and_charters(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEFIT_SCHOOL_SNAPSHOT_DIR", str(tmp_path))
    ss._mem.clear()
    schools = [ss.slim(_raw("A", "1")), ss.slim(_raw("B", "1")), ss.slim(_raw("C", "2", charter="Yes"))]
    with gzip.open(tmp_path / "ZZ.json.gz", "wt") as f:
        json.dump({"meta": {"count": 3}, "schools": schools}, f)
    assert [s["schoolName"] for s in ss.district_schools("ZZ", "1")] == ["A", "B"]
    assert [s["schoolName"] for s in ss.state_charters("ZZ")] == ["C"]
    assert ss.district_schools("QQ", "1") is None   # no snapshot for the state -> caller falls back to the API
    ss._mem.clear()
