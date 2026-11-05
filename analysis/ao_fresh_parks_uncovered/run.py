"""Fresh park and playground read (2 km) for the catalog places the private Overpass server did not cover.
Same query as the first pass (osm_api.query_green_spaces). Resumable: rerun the same command and finished places are skipped.
Usage: python3 analysis/ao_fresh_parks_uncovered/run.py   (run from /Users/adamwright/Dev/home-fit-context)
Needs a local Overpass endpoint that holds AZ CO FL GA MA NC NV, at localhost:12346."""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.getcwd()
sys.path.insert(0, REPO)
os.environ["OVERPASS_URL"] = "http://localhost:12346/api/interpreter"
from data_sources import osm_api

OUT = os.path.join(HERE, "parks_fresh.json")
places = json.load(open(os.path.join(HERE, "places.json")))
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
lock = threading.Lock()

def run(p):
    k = f'{p["name"]}|{p["state"]}'
    if res.get(k, {}).get("outcome") == "overpass_ok":
        return
    t = time.time()
    try:
        r = osm_api.query_green_spaces(float(p["lat"]), float(p["lon"]), radius_m=2000)
    except Exception:
        r = None
    v = dict(
        outcome=(r or {}).get("_overpass_outcome") if r else "exception",
        parks=[dict(distance_m=q.get("distance_m"), area_sqm=q.get("area_sqm"), name=q.get("name")) for q in ((r or {}).get("parks") or [])],
        playgrounds=[dict(distance_m=q.get("distance_m")) for q in ((r or {}).get("playgrounds") or [])],
        secs=round(time.time() - t, 1),
    )
    with lock:
        res[k] = v
        if len(res) % 25 == 0:
            json.dump(dict(res), open(OUT, "w"))
            print("done", len(res), "of", len(places), flush=True)

with ThreadPoolExecutor(4) as ex:
    list(ex.map(run, places))
with lock:
    json.dump(dict(res), open(OUT, "w"))
    ok = sum(1 for v in res.values() if v["outcome"] == "overpass_ok")
    print("finished", len(res), "ok", ok, flush=True)
