"""Write frontend/lib/catalogCentroids.json: [lat, lon] for every catalog place, all metros.

The acquaintance priority uses it to tell which catalog neighborhood a person lives in (the nearest
center point) on every page, without loading the catalog. Rerun when a metro's place catalog changes:
    python3 scripts/catalog/build_catalog_centroids.py
"""
import csv
import glob
import json

points = []
for path in sorted(glob.glob('data/*_metro_place_catalog.csv')):
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            try:
                points.append([round(float(row['lat']), 5), round(float(row['lon']), 5)])
            except (KeyError, TypeError, ValueError):
                continue
with open('frontend/lib/catalogCentroids.json', 'w') as f:
    json.dump(points, f, separators=(',', ':'))
print(f'{len(points)} centroids')
