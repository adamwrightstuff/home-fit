# Private Overpass server (on demand)

Why: the public Overpass servers stopped serving scripted requests in October 2026 (403 white-list message,
502 "for human-operated tools", 500s, hangs; same from a phone hotspot, so not an IP block). Pillars that need
OpenStreetMap (active outdoors, healthcare, neighborhood amenities, natural beauty, early-education bonus) cannot
be scored without one.

Design: run it only while scoring. Hourly billed server, kept as a snapshot between uses. Nothing is exposed to
the internet: the server listens on its own localhost and you reach it through an SSH tunnel.

## One time: build (a few hours, roughly $1 to $3 of server time)
1. Create a server at Hetzner (or similar): Ubuntu 24.04, 4 vCPU, 8 GB RAM, 80 GB or more disk, US region.
   Add your SSH key. Add a firewall allowing only SSH (port 22).
2. `scp scripts/overpass_server/setup.sh root@SERVER:/root/ && ssh root@SERVER bash /root/setup.sh`
3. Watch `docker logs -f overpass` until the load finishes and the container stops, then `docker start overpass`.
4. Check disk use with `df -h /srv/overpass` and note it here: ______
5. Power off, take a snapshot named `overpass-homefit-YYYY-MM`, delete the server.

## Each time you score (about $0.05 an hour)
1. Create a server from the snapshot, wait for boot, `docker start overpass` if it is not already running.
2. Tunnel: `ssh -N -L 12345:localhost:12345 root@SERVER` (leave running)
3. In a second terminal, from the project root:
   `OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python -m scripts.metro_agent health --metro philadelphia --fix`
4. Delete the server when done. Keep the snapshot (about 40 GB, under $1 a month).

## Refresh
OpenStreetMap changes daily but park, clinic and shop counts move slowly. Rebuild the snapshot about once a year
or when a new state is added (edit STATES in setup.sh).

## Limits
Live scoring on Railway still uses the public servers. An always-on server would fix that (about $30 to $40 a month).
