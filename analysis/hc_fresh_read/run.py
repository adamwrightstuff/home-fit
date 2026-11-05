"""Fresh healthcare read at ONE common radius (10 km) for every catalog place, for the density-free healthcare redesign.
Same query as the pillar (osm_api.query_healthcare_facilities). Keeps only what scoring needs: per facility its distance,
ER tag and specialty tags. Resumable: rerun the same command and finished places are skipped.
Run from the repo root of a current checkout:  PYTHONPATH=. python3 analysis/hc_fresh_read/run.py
Needs the private Overpass tunnel on localhost:12346 (all 18 states)."""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getcwd())
os.environ["OVERPASS_URL"] = "http://localhost:12346/api/interpreter"
from data_sources import osm_api

RADIUS_M = 10000
OUT = os.path.join(HERE, "healthcare_fresh.json")
KINDS = ("hospitals", "urgent_care", "clinics", "pharmacies", "doctors")


def slim(f):
    tags = f.get("tags") or {}
    return dict(
        d=f.get("distance_km"),
        er=1 if (tags.get("emergency") == "yes" or f.get("emergency") == "yes") else 0,
        spec=tags.get("healthcare:speciality") or "",
    )


def read_one(p, query=None):
    query = query or osm_api.query_healthcare_facilities
    t = time.time()
    try:
        r = query(float(p["lat"]), float(p["lon"]), radius_m=RADIUS_M)
    except Exception:
        r = None
    if not r or r.get("_query_failed"):
        return dict(outcome="failed" if r is None or r.get("_query_failed") else "empty", secs=round(time.time() - t, 1))
    v = {k: [slim(f) for f in (r.get(k) or [])] for k in KINDS}
    total = sum(len(x) for x in v.values())
    v.update(outcome="ok" if total else "empty", secs=round(time.time() - t, 1))
    return v


def main():
    places = json.load(open(os.path.join(HERE, "places.json")))
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    lock = threading.Lock()

    def run(p):
        k = f'{p["name"]}|{p["state"]}'
        if res.get(k, {}).get("outcome") == "ok":
            return
        v = read_one(p)
        with lock:
            res[k] = v
            if len(res) % 25 == 0:
                json.dump(dict(res), open(OUT, "w"))
                print("done", len(res), "of", len(places), flush=True)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(run, places))
    with lock:
        json.dump(dict(res), open(OUT, "w"))
        ok = sum(1 for v in res.values() if v["outcome"] == "ok")
        print("finished", len(res), "ok", ok, "empty", sum(v["outcome"] == "empty" for v in res.values()),
              "failed", sum(v["outcome"] == "failed" for v in res.values()), flush=True)


if __name__ == "__main__":
    main()
