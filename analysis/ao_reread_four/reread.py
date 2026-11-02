"""Re-read parks and playgrounds (2,000 m, same query as the first pass) for the four places scored with an empty park read.
Usage, from the repo root, with OVERPASS_URL set to the tunnel that holds the place's state:
  OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 analysis/ao_reread_four/reread.py CA
  OVERPASS_URL=http://localhost:12346/api/interpreter PYTHONPATH=. python3 analysis/ao_reread_four/reread.py NV
Writes analysis/ao_reread_four/parks_fresh_<STATE>.json in the format of ao_fresh_parks_uncovered/parks_fresh.json."""
import glob, json, os, sys, time

from data_sources import osm_api

WANT = {("Larkspur", "CA"), ("Orinda", "CA"), ("Woodside", "CA"), ("Moapa Town", "NV")}
state = sys.argv[1].upper()
here = os.path.dirname(os.path.abspath(__file__))
places = []
for f in sorted(glob.glob("data/*_merged.composites_recomputed.jsonl")):
    for line in open(f):
        c = json.loads(line)["catalog"]
        if (c["name"], c["state_abbr"]) in WANT and c["state_abbr"] == state:
            places.append(c)
res = {}
for c in places:
    t = time.time()
    r = osm_api.query_green_spaces(float(c["lat"]), float(c["lon"]), radius_m=2000)
    res[f'{c["name"]}|{c["state_abbr"]}'] = dict(
        outcome=(r or {}).get("_overpass_outcome"),
        parks=[dict(distance_m=q.get("distance_m"), area_sqm=q.get("area_sqm"), name=q.get("name")) for q in ((r or {}).get("parks") or [])],
        playgrounds=[dict(distance_m=q.get("distance_m")) for q in ((r or {}).get("playgrounds") or [])],
        secs=round(time.time() - t, 1),
    )
    print(c["name"], c["state_abbr"], res[f'{c["name"]}|{c["state_abbr"]}']["outcome"], len(res[f'{c["name"]}|{c["state_abbr"]}']["parks"]), "parks", flush=True)
json.dump(res, open(os.path.join(here, f"parks_fresh_{state}.json"), "w"))
